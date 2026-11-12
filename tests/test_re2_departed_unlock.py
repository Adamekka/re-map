"""RE2-DOOR-008: historical unlock flags survive interaction alternatives."""

import copy
from dataclasses import replace

import pytest
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import DoorUnlockState, Tracker
from tracker.polling import PollStatus
from ui.map_view import map_state


@pytest.mark.parametrize(
    "profile",
    [
        "re2_leon_a_slus00421",
        "re2_claire_b_slus00592",
        "re2_leon_a_slus00748",
        "re2_claire_b_slus00756",
    ],
    indirect=True,
)
@pytest.mark.parametrize("competitor", ["open", "same_lock", "item"])
@pytest.mark.parametrize("bit", [2, 33])
def test_departed_alternatives_preserve_only_positive_unlock_evidence(
    snapshot, competitor, bit
):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-00"])
    definition = source["doors"][0]
    definition.update(lock_id=0x80 | bit, lock_type=89)
    if competitor == "item":
        source["items"].append(
            {**profile.rooms["00-01"]["items"][0], "slot": definition["slot"]}
        )
    else:
        source["doors"].append(
            {
                **definition,
                "offset": definition["offset"] + 64,
                "lock_id": 0 if competitor == "open" else 0x80 | bit,
                "lock_type": 0 if competitor == "open" else 89,
            }
        )
    profile = replace(profile, rooms=profile.rooms | {"00-00": source})
    key_address, _ = profile.flag_banks[profile.runtime_layout["key_bank"]]
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0))
    visits = None
    for unlocked in (False, True, False, True):
        put(key_address + bit // 32 * 4, 0x80000000 >> (bit % 32) if unlocked else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        door = next(
            door
            for door in tracker.doors
            if door.observation_id == f"00-00:{definition['offset']}"
        )
        assert door.state == "UNCHECKED"
        assert door.unlock_state is (
            DoorUnlockState.Unlocked if unlocked else DoorUnlockState.Unknown
        )
        assert door.key_label == ("" if unlocked else "Spade Key")
        assert door.label == (
            "Unlocked; access unconfirmed" if unlocked else "Door conditions unresolved"
        )
        published = next(
            row
            for row in map_state(tracker)["doors"]
            if row["observation_id"] == door.observation_id
        )
        assert published["unlock_state"] == door.unlock_state.value
        fresh = Tracker()
        fresh.mark_current(RoomId(0, 0))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh == tracker
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stage", 1),
        ("room", 2),
        ("floor", 1),
        ("center", [123, 456]),
        ("four_point", True),
        ("activation_floor", 1),
        ("lock_id", 0x83),
        ("lock_type", 91),
        ("offset", None),
    ],
)
def test_conflicting_departed_doors_cannot_borrow_a_set_unlock_bit(
    snapshot, field, value
):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-00"])
    definition = source["doors"][0]
    definition.update(lock_id=0x82, lock_type=89)
    alternative = {**definition, "offset": definition["offset"] + 64}
    alternative[field] = definition["offset"] if field == "offset" else value
    source["doors"].append(alternative)
    profile = replace(profile, rooms=profile.rooms | {"00-00": source})
    key_address, _ = profile.flag_banks[profile.runtime_layout["key_bank"]]
    put(key_address, 0x20000000, 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    doors = [door for door in tracker.doors if door.source == RoomId(0, 0)]
    assert len(doors) == 2
    assert all(door.state == "UNCHECKED" for door in doors)
    assert all(door.unlock_state is DoorUnlockState.Unknown for door in doors)
    assert doors[0].key_label == "Spade Key"


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize(
    ("source", "offset", "bit", "key_name"),
    [
        ("00-14", 2562, 9, "Spade Key"),
        ("01-04", 6430, 5, "Spade Key"),
        ("01-0b", 12090, 4, "Heart Key"),
    ],
)
def test_reported_key_doors_rebuild_from_fresh_flags(
    snapshot, source, offset, bit, key_name
):
    profile, _, put, read = snapshot
    tracker = Tracker()
    stage, room = source.split("-")
    tracker.mark_current(RoomId(int(stage, 16), int(room, 16)))
    key_address, _ = profile.flag_banks[profile.runtime_layout["key_bank"]]
    for unlocked in (False, True, False):
        put(key_address, 0x80000000 >> bit if unlocked else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        door = next(
            door
            for door in tracker.doors
            if door.observation_id == f"{source}:{offset}"
        )
        # RE2-DOOR-009 closes this source's access alternatives. The other
        # two reported sources retain the independent historical unlock rule.
        known_access = source == "00-14"
        assert door.state == (
            ("OPEN" if unlocked else "LOCKED") if known_access else "UNCHECKED"
        )
        assert door.unlock_state is (
            DoorUnlockState.Unlocked
            if unlocked
            else DoorUnlockState.Locked
            if known_access
            else DoorUnlockState.Unknown
        )
        assert door.key_label == ("" if unlocked else key_name)


@pytest.mark.parametrize("fault", ["changed", "short"])
def test_departed_alternative_unlock_read_is_atomic(snapshot, fault):
    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 4))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    key_address, _ = profile.flag_banks[profile.runtime_layout["key_bank"]]

    def torn_read(address, width):
        if address == key_address and width == 4:
            if fault == "short":
                return MemRead(True, b"\x00")
            put(key_address, 0x04000000, 4)
        return read(address, width)

    assert poll_re2(profile, tracker, torn_read).status is (
        PollStatus.Retry if fault == "changed" else PollStatus.ReadFailure
    )
    assert tracker == before
