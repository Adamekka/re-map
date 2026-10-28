"""RE2-DOOR-006: slot identity groups list entries, never map observations."""

import copy
from collections import Counter
from dataclasses import replace

import pytest
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import DoorDetail, DoorUnlockState, Tracker
from tracker.polling import PollStatus
from ui.map_view import map_state


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
def test_departed_waiting_room_preserves_each_observation_and_its_shared_slot(snapshot):
    profile, _, _, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 1))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    doors = [door for door in tracker.doors if door.source == RoomId(1, 1)]
    definitions = profile.rooms["01-01"]["doors"]
    assert len(doors) == len(definitions) == 4
    assert [door.observation_id for door in doors] == [
        f"01-01:{definition['offset']}" for definition in definitions
    ]
    assert Counter(door.interaction_id for door in doors) == {
        "01-01:0": 2,
        "01-01:1": 2,
    }
    assert all(door.state == "OPEN" for door in doors)
    assert all(door.unlock_state is DoorUnlockState.Unknown for door in doors)
    published = [
        door for door in map_state(tracker)["doors"] if door["source"] == "01-01"
    ]
    assert [door["interaction_id"] for door in published] == [
        door.interaction_id for door in doors
    ]
    assert [door["observation_id"] for door in published] == [
        door.observation_id for door in doors
    ]


def test_slot_identity_survives_current_creator_and_lock_reversal(snapshot):
    profile, ram, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-01"])
    definition = source["doors"][0]
    alternative = {
        **definition,
        "offset": definition["offset"] + 400,
        "lock_id": 0x82,
        "lock_type": 89,
    }
    source["doors"].append(alternative)
    profile = replace(profile, rooms=profile.rooms | {"00-01": source})
    pointer = 0x80100000 + definition["offset"] + 2
    other_pointer = 0x80100000 + alternative["offset"] + 2
    ram[other_pointer & 0x1FFFFF : (other_pointer & 0x1FFFFF) + 30] = read(
        pointer, 30
    ).data
    put(other_pointer + 27, 0x82, 1)
    put(other_pointer + 28, 89, 1)
    registry = (
        int(profile.runtime_layout["aot_table_address_ps1"], 0) + definition["slot"] * 4
    )
    key_address, _ = profile.flag_banks[profile.runtime_layout["key_bank"]]
    tracker = Tracker()
    for active, flags, expected in (
        (pointer, 0, "OPEN"),
        (other_pointer, 0, "LOCKED"),
        (other_pointer, 0x20000000, "OPEN"),
        (other_pointer, 0, "LOCKED"),
        (pointer, 0, "OPEN"),
    ):
        put(registry, active, 4)
        put(key_address, flags, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        doors = [door for door in tracker.doors if door.target == RoomId(0, 0)]
        assert len(doors) == 1
        door = doors[0]
        assert door.interaction_id == f"00-01:{definition['slot']}"
        assert door.observation_id == f"00-01:{active - 0x80100002}"
        assert door.state == expected
        published = next(
            row
            for row in map_state(tracker)["doors"]
            if row["observation_id"] == door.observation_id
        )
        assert published["interaction_id"] == door.interaction_id


def test_doors_without_a_registry_slot_keep_separate_list_entries():
    tracker = Tracker(player_heading=90)
    tracker.mark_current(RoomId(0, 9))
    tracker.current_region = "mansion1f:09"
    tracker.region_visits[tracker.current_region] = "00-09"
    tracker.doors = (
        DoorDetail(RoomId(0, 9), RoomId(0, 10), "OPEN", "Open"),
        DoorDetail(RoomId(0, 9), RoomId(0, 10), "OPEN", "Open"),
    )
    assert [door["interaction_id"] for door in map_state(tracker)["doors"]] == [
        "",
        "",
    ]
