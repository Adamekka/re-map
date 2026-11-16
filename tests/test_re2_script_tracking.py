"""Script evaluation inside the live RE2 reader. RE2-EVAL-001.

Synthetic coherent snapshots only; native validation is recorded separately.
"""

from __future__ import annotations

import pytest
from test_re2_tracking import ROOT, build_snapshot

from games.bit_flags import msb_flag_location
from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.fixture
def leon(script_evaluation):
    return Re2Profile.load(ROOT / "profiles" / "re2_leon_a_slus00748.json")


def test_departed_rooms_resolve_every_item_and_door(leon):
    profile, _, _, read = build_snapshot(leon, "00-01")
    tracker = Tracker()
    for key in profile.rooms:
        tracker.mark_current(RoomId(*(int(part, 16) for part in key.split("-"))))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    departed = {key: record for key, record in tracker.rooms.items() if key != "00-01"}
    assert all(
        record.completion is not RoomCompletion.Unknown for record in departed.values()
    )
    assert not [
        item
        for record in departed.values()
        for item in record.items
        if item.state == "unknown"
    ]
    assert not [
        door
        for door in tracker.doors
        if str(door.source) != "00-01" and door.state == "UNCHECKED"
    ]


def test_fresh_acquisition_and_rewind_reach_departed_evaluations(leon):
    profile, _, put, read = build_snapshot(leon, "00-01")
    room = "01-00"
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 0))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    remaining = [
        item for item in tracker.rooms[room].items if item.state == "uncollected"
    ]
    assert remaining and tracker.rooms[room].completion is RoomCompletion.Incomplete
    layout = profile.runtime_layout
    bank = layout["item_bank_early"]
    address, _ = profile.flag_banks[bank]
    gids = sorted(profile.script_evaluation.item_ids[room])
    for collected in (True, False, True):
        for gid in gids:
            word, mask = msb_flag_location(address, gid)
            current = int.from_bytes(read(word, 4).data, "little")
            put(word, current | mask if collected else current & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        states = {item.state for item in tracker.rooms[room].items}
        if collected:
            assert states == {"taken"}
            assert tracker.rooms[room].completion is RoomCompletion.Cleared
        else:
            assert "uncollected" in states
            assert tracker.rooms[room].completion is RoomCompletion.Incomplete
