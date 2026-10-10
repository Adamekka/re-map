"""Exploration persistence, fresh game interpretation and safe history writes."""

import json
import logging
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import track
from test_live_items import RamReader, fixture_ram

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import DoorDetail, ItemDetail, RoomCompletion, Tracker
from tracker.visit_history import HistoryError, HistoryIdentity, VisitHistory
from ui.map_view import map_state


@pytest.fixture
def identity():
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    return HistoryIdentity(
        raw["profile_id"], raw["runtime_signature"]["concatenated_sha256"], "jill"
    )


@pytest.fixture
def region_rooms():
    raw = json.loads((REPO / "data/floor_plans_slus00551.json").read_text())
    return {
        f"{plan['id']}:{room['id']}": set(room["room_ids"])
        for plan in raw["areas"]
        for room in plan["rooms"]
    }


def test_restart_restores_exact_visits_without_game_derived_verdicts(
    tmp_path, identity, region_rooms
):
    path = tmp_path / "visits.json"
    history = VisitHistory(path, identity, region_rooms, False)
    tracker = Tracker()
    for room in (RoomId(0, 7), RoomId(0, 9), RoomId(3, 5), RoomId(6, 0)):
        tracker.mark_current(room)
        tracker.update_room_items(room, 1, 1, True, False, False)
        tracker.rooms[str(room)].items = (ItemDetail("Green Herb", "taken", 1),)
    tracker.region_visits = {
        "mansion1f:07": "00-07",
        "mansion1f:1D": "00-07",
        "mansion1f:09": "00-09",
        "guardhouse1f:05": "03-05",
    }
    tracker.doors = (DoorDetail(RoomId(0, 9), RoomId(0, 20), "OPEN", "Open"),)
    history.save(tracker)
    playthrough_id = history.playthrough_id
    history.close()
    raw = json.loads(path.read_text())
    assert set(raw) == {"schema", "identity", "playthrough_id", "rooms", "regions"}
    assert "items" not in path.read_text() and "OPEN" not in path.read_text()
    restored_history = VisitHistory(path, identity, region_rooms, False)
    restored = restored_history.restore()
    restored_history.close()
    assert restored_history.playthrough_id == playthrough_id
    assert restored.region_visits == tracker.region_visits
    assert set(restored.rooms) == set(tracker.rooms)
    assert restored.current is None and restored.current_region == ""
    assert not restored.doors
    assert all(
        record.visited
        and record.completion is RoomCompletion.Unknown
        and not record.items
        and not record.list_complete
        and not record.doors_complete
        for record in restored.rooms.values()
    )


def test_restart_refreshes_departed_room_and_reverses_flags_without_reentry(
    tmp_path, identity, region_rooms
):
    path = tmp_path / "visits.json"
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb_after = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    tracker = Tracker()
    assert (
        track.poll_once(profile, tracker, RamReader(herb_after).read_memory).status
        is track.PollStatus.Display
    )
    history = VisitHistory(path, identity, region_rooms, False)
    history.save(tracker)
    history.close()
    history = VisitHistory(path, identity, region_rooms, False)
    tracker = history.restore()
    fresh_profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    # Change the acquired and unlock bits in a different current room, so the
    # regression cannot pass merely by rereading the Herb's live registry.
    chemical[0xC86EA] &= ~1
    chemical[0xC86B7] |= 8
    reader = RamReader(chemical)
    assert (
        track.poll_once(fresh_profile, tracker, reader.read_memory).status
        is track.PollStatus.Display
    )
    herb = tracker.rooms["00-09"]
    assert herb.completion is RoomCompletion.Cleared
    assert herb.items[0].label == "Green Herb" and herb.items[0].state == "taken"
    armor = next(
        door
        for door in tracker.doors
        if str(door.source) == "00-09" and door.target.room == 20
    )
    assert armor.state == "OPEN"
    history.save(tracker)
    chemical[0xC86EA] |= 1
    chemical[0xC86B7] &= ~8
    assert (
        track.poll_once(fresh_profile, tracker, reader.read_memory).status
        is track.PollStatus.Display
    )
    assert herb.completion is RoomCompletion.Incomplete
    assert herb.items[0].state == "available"
    armor = next(
        door
        for door in tracker.doors
        if str(door.source) == "00-09" and door.target.room == 20
    )
    assert armor.state == "LOCKED"
    history.save(tracker)
    history.close()
    assert set(tracker.rooms) == {"00-09", "00-18"}
    assert tracker.region_visits == {"mansion1f:09": "00-09", "mansion1f:18": "00-18"}
    assert [room["id"] for room in map_state(tracker)["rooms"]] == ["09", "18"]
    assert not fresh_profile.room_observations.get(RoomId(0, 9))


@pytest.mark.parametrize(
    "failure",
    [
        "corrupt",
        "schema",
        "identity",
        "uuid",
        "rooms",
        "duplicate",
        "regions",
        "region-room",
        "cached-state",
    ],
)
def test_invalid_history_is_reported_and_preserved(
    tmp_path, identity, region_rooms, failure
):
    path = tmp_path / "visits.json"
    history = VisitHistory(path, identity, region_rooms, False)
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 9))
    tracker.region_visits["mansion1f:09"] = "00-09"
    history.save(tracker)
    history.close()
    raw = json.loads(path.read_text())
    if failure == "corrupt":
        path.write_text("broken JSON")
    else:
        if failure == "schema":
            raw["schema"] = True
        elif failure == "identity":
            raw["identity"]["runtime_sha256"] = "f" * 64
        elif failure == "uuid":
            raw["playthrough_id"] = "not-a-uuid"
        elif failure == "rooms":
            raw["rooms"] = ["00-100"]
        elif failure == "duplicate":
            raw["rooms"] *= 2
        elif failure == "regions":
            raw["regions"]["mansion1f:08"] = "00-08"
        elif failure == "region-room":
            raw["regions"] = {"mansion1f:08": "00-09"}
        else:
            raw["items"] = [{"state": "taken"}]
        path.write_text(json.dumps(raw))
    original = path.read_bytes()
    with pytest.raises(HistoryError, match="Cannot restore exploration history"):
        VisitHistory(path, identity, region_rooms, False)
    assert path.read_bytes() == original
    # A rejected file must release its lock so the explicit recovery works.
    fresh = VisitHistory(path, identity, region_rooms, True)
    fresh.close()


def test_failed_save_preserves_history_and_can_retry(
    tmp_path, identity, region_rooms, monkeypatch
):
    path = tmp_path / "visits.json"
    history = VisitHistory(path, identity, region_rooms, False)
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 9))
    history.save(tracker)
    original = path.read_bytes()
    tracker.mark_current(RoomId(0, 7))
    import tracker.visit_history as module

    replace = module.os.replace
    monkeypatch.setattr(
        module.os,
        "replace",
        lambda *args: (_ for _ in ()).throw(OSError("disk unavailable")),
    )
    with pytest.raises(HistoryError, match="Cannot save exploration history"):
        history.save(tracker)
    assert path.read_bytes() == original
    assert set(tmp_path.iterdir()) == {path, path.with_name("visits.json.lock")}
    monkeypatch.setattr(module.os, "replace", replace)
    history.save(tracker)
    history.close()
    assert set(json.loads(path.read_text())["rooms"]) == {"00-09", "00-07"}


def test_unchanged_poll_does_not_write_and_new_playthrough_has_separate_identity(
    tmp_path, identity, region_rooms, monkeypatch
):
    path = tmp_path / "visits.json"
    history = VisitHistory(path, identity, region_rooms, False)
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 9))
    history.save(tracker)
    original = path.read_bytes()
    old_id = history.playthrough_id
    import tracker.visit_history as module

    with monkeypatch.context() as patch:
        patch.setattr(
            module.tempfile,
            "NamedTemporaryFile",
            lambda *a, **k: pytest.fail("unchanged visit history must not write"),
        )
        history.save(tracker)
    history.close()
    fresh = VisitHistory(path, identity, region_rooms, True)
    assert not fresh.restore().rooms and fresh.playthrough_id != old_id
    assert path.read_bytes() == original  # Reset waits for verified gameplay.
    new_tracker = Tracker()
    new_tracker.mark_current(RoomId(0, 7))
    fresh.save(new_tracker)
    fresh.close()
    assert json.loads(path.read_text())["rooms"] == ["00-07"]


def test_second_writer_is_rejected_until_the_first_closes(
    tmp_path, identity, region_rooms
):
    path = tmp_path / "visits.json"
    first = VisitHistory(path, identity, region_rooms, False)
    with pytest.raises(HistoryError, match="history is in use"):
        VisitHistory(path, identity, region_rooms, True)
    first.close()
    second = VisitHistory(path, identity, region_rooms, False)
    second.close()


@pytest.mark.parametrize("gameplay", [True, False])
def test_cli_saves_only_verified_gameplay_and_resumes_across_restarts(
    tmp_path, monkeypatch, gameplay
):
    ram = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    if not gameplay:
        ram[0xC866C] = 0

    class LocalReader(RamReader):
        connected = True  # Captured-state reader has no network connection.

        def connect(self):
            return ""

        def resume(self):
            return ""

        def close(self):
            pass  # The reader owns only test memory, not a socket.

    monkeypatch.setattr(track, "DuckStationGdb", lambda *args: LocalReader(ram))
    path = tmp_path / "visits.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--once",
            "--history-file",
            str(path),
            "--log-file",
            str(tmp_path / "tracker.log"),
        ],
    )
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers = []
    try:
        assert track.main() == (0 if gameplay else 1)
        assert path.exists() == gameplay
        if gameplay:
            before = json.loads(path.read_text())
            assert before["rooms"] == ["00-09"]
            ram[0xC86EA] |= 1
            assert track.main() == 0
            after = json.loads(path.read_text())
            assert after["playthrough_id"] == before["playthrough_id"]
            assert after["rooms"] == before["rooms"]
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = handlers
        root.setLevel(level)
