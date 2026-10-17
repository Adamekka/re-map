import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.game_profile import RoomId
from tracker.exploration_state import RoomCompletion, Tracker
from ui.debug_view import render


def test_unvisited_defaults_to_unvisited():
    t = Tracker()
    rec = t.room_state(RoomId(stage=0, room=0))
    assert rec.visited is False
    assert rec.completion == RoomCompletion.Unvisited


def test_one_remaining_forces_incomplete():
    t = Tracker()
    rid = RoomId(stage=1, room=2)
    t.mark_current(rid)
    state = t.update_room_items(
        rid,
        total=3,
        collected=2,
        list_complete=True,
        any_required_uncollected=True,
        any_unknown=False,
    )
    assert state == RoomCompletion.Incomplete


def test_full_collection_clears_when_list_complete():
    t = Tracker()
    rid = RoomId(stage=1, room=2)
    t.mark_current(rid)
    state = t.update_room_items(
        rid,
        total=3,
        collected=3,
        list_complete=True,
        any_required_uncollected=False,
        any_unknown=False,
    )
    assert state == RoomCompletion.Cleared
    # Leave and return keeps cleared when counts unchanged.
    state2 = t.update_room_items(
        rid,
        total=3,
        collected=3,
        list_complete=True,
        any_required_uncollected=False,
        any_unknown=False,
    )
    assert state2 == RoomCompletion.Cleared


def test_unknown_list_never_claims_cleared():
    t = Tracker()
    rid = RoomId(stage=1, room=3)
    t.mark_current(rid)
    state = t.update_room_items(
        rid,
        total=1,
        collected=1,
        list_complete=False,
        any_required_uncollected=False,
        any_unknown=False,
    )
    assert state == RoomCompletion.Unknown


def test_any_unknown_forces_unknown():
    t = Tracker()
    rid = RoomId(stage=1, room=4)
    t.mark_current(rid)
    state = t.update_room_items(
        rid,
        total=2,
        collected=2,
        list_complete=True,
        any_required_uncollected=False,
        any_unknown=True,
    )
    assert state == RoomCompletion.Unknown


def test_debug_view_shows_required_lines():
    t = Tracker()
    rid = RoomId(stage=1, room=5)
    t.mark_current(rid)
    t.update_room_items(
        rid,
        total=3,
        collected=2,
        list_complete=True,
        any_required_uncollected=True,
        any_unknown=False,
    )
    out = render(rid, t.room_state(rid), "re1_ntsc_u")
    assert "Current room:" in out
    assert "Visited: yes" in out
    assert "Items: 3" in out
    assert "Collected: 2" in out
    assert "INCOMPLETE" in out
