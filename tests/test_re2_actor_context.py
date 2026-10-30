"""RE2-DS-005: resource-dependent interpretation must use fresh source guards."""

import copy

import pytest
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["01-01", "01-04"], indirect=True)
def test_actor_context_and_acquisition_rebuild_without_cached_clearance(snapshot):
    p, _, put, read = snapshot
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0)
    # The generic fixture registers both scenario alternatives. A collected
    # pickup is inactive here; the flag must supply its collection state.
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 1))
    acquired_address = p.flag_banks[8][0] + 92 // 32 * 4
    guard_address = p.flag_banks[4][0]
    enemy_address = p.flag_banks[6][0]
    for acquired, enemy_dead, story_done in (
        (True, False, True),
        (True, True, True),
        (True, True, False),
        (False, True, False),
        (False, False, True),
        (False, True, True),
        (False, False, False),
        (True, False, False),
        (True, False, True),
    ):
        put(acquired_address, (0x80000000 >> (92 % 32)) if acquired else 0, 4)
        put(enemy_address, (0x80000000 >> 24) if enemy_dead else 0, 4)
        put(guard_address, (0x80000000 >> 5) if story_done else 0, 4)
        assert poll_re2(p, tracker, read).status is PollStatus.Display
        record = tracker.rooms["01-01"]
        (item,) = record.items
        assert item.state == (
            "taken" if acquired else "unknown" if enemy_dead else "uncollected"
        )
        assert item.label == ("Collectible" if enemy_dead else "Handgun ammo")
        assert item.quantity == (
            ItemQuantityState.Unreconstructed if enemy_dead else 15
        )
        assert record.list_complete == (not enemy_dead)
        assert record.completion is (
            RoomCompletion.Cleared
            if acquired and not enemy_dead
            else RoomCompletion.Unknown
            if enemy_dead
            else RoomCompletion.Incomplete
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(1, 1))
        assert poll_re2(p, fresh, read).status is PollStatus.Display
        assert fresh.rooms["01-01"] == record
        assert set(tracker.rooms) == {"01-01", str(tracker.current)}


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["01-01"], indirect=True)
def test_invalid_actor_context_keeps_a_fresh_live_item_without_scenario_exclusion(
    snapshot,
):
    p, _, put, read = snapshot
    put(p.flag_banks[6][0], 0x80000000 >> 24, 4)
    # This observation contradicts the guarded variant selection. Without its
    # precondition the reader retains the live fact and an incomplete list.
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    record = tracker.rooms["01-01"]
    (item,) = record.items
    assert (item.label, item.state, item.quantity) == ("Shotgun shells", "available", 7)
    assert record.completion is RoomCompletion.Incomplete
    assert not record.list_complete


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
@pytest.mark.parametrize("short", [False, True])
def test_actor_precondition_participates_in_atomic_coherence(snapshot, short):
    p, _, put, read = snapshot
    put(p.flag_banks[8][0] + 92 // 32 * 4, 0x80000000 >> (92 % 32), 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 1))
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    address = p.flag_banks[6][0]

    def changing_read(a, n):
        if (a, n) == (address, 4):
            return MemRead(
                True, b"x" if short else (0x80000000 >> 24).to_bytes(4, "little")
            )
        return read(a, n)

    assert poll_re2(p, tracker, changing_read).status is (
        PollStatus.ReadFailure if short else PollStatus.Retry
    )
    assert tracker == before
