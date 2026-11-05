"""RE2-LIVE-001: mutable door destinations must stay in the revision catalog."""

import copy

import pytest
import test_re2_tracking

from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import DoorUnlockState, Tracker
from tracker.polling import PollStatus

# Register the shared fixtures under the names their dependencies request.
profile = test_re2_tracking.profile
snapshot = test_re2_tracking.snapshot


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
@pytest.mark.parametrize(
    "target", [RoomId(255, 255), RoomId(0, 255), RoomId(7, 0), RoomId(6, 47)]
)
@pytest.mark.parametrize(
    ("snapshot", "four_point"),
    [("00-01", False), ("05-08", True)],
    indirect=["snapshot"],
)
def test_unlisted_live_door_target_withholds_the_whole_publication(
    snapshot, target, four_point
):
    profile, _, put, read = snapshot
    source = str(profile.read_current_room(read).room)
    definition = next(
        door
        for door in profile.rooms[source]["doors"]
        if door["four_point"] is four_point
    )
    pointer = 0x80100000 + definition["offset"] + 2
    operand = 20 if definition["four_point"] else 12
    tracker = Tracker()
    before = copy.deepcopy(tracker)

    put(pointer + operand + 8, target.stage, 1)
    put(pointer + operand + 9, target.room, 1)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Room door destination is unresolved"
    assert tracker == before


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
def test_live_door_destination_and_lock_rebuild_after_invalid_state_and_rewind(
    snapshot,
):
    profile, _, put, read = snapshot
    definition = profile.rooms["00-01"]["doors"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    operand = 20 if definition["four_point"] else 12
    key_address, _ = profile.flag_banks[profile.runtime_layout["key_bank"]]
    tracker = Tracker()
    visits = None
    for target, unlocked in (
        (RoomId(0, 0), False),
        (RoomId(1, 4), True),
        (RoomId(255, 255), False),
        (RoomId(0, 0), False),
        (RoomId(1, 4), True),
    ):
        put(pointer + operand + 8, target.stage, 1)
        put(pointer + operand + 9, target.room, 1)
        put(pointer + operand + 15, 0x82, 1)
        put(pointer + operand + 16, 89, 1)
        put(key_address, 0x20000000 if unlocked else 0, 4)
        before = copy.deepcopy(tracker)
        result = poll_re2(profile, tracker, read)
        if target == RoomId(255, 255):
            assert result.status is PollStatus.Retry
            assert tracker == before
            continue
        assert result.status is PollStatus.Display
        door = next(
            door
            for door in tracker.doors
            if door.observation_id == f"00-01:{definition['offset']}"
        )
        assert door.target == target
        assert door.unlock_state is (
            DoorUnlockState.Unlocked if unlocked else DoorUnlockState.Locked
        )
        assert door.state == ("OPEN" if unlocked else "LOCKED")
        fresh = Tracker()
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert tracker == fresh
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize("profile", ["re2_claire_b_slus00592"], indirect=True)
def test_live_door_can_target_an_explicitly_unsupported_room(snapshot):
    profile, _, put, read = snapshot
    assert "06-05" in profile.unsupported_sources
    definition = profile.rooms["00-01"]["doors"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    operand = 20 if definition["four_point"] else 12
    put(pointer + operand + 8, 6, 1)
    put(pointer + operand + 9, 5, 1)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.doors[0].target == RoomId(6, 5)
    assert set(tracker.rooms) == {"00-01"}
