"""Diagnostic output must never overwrite exploration or its writer lock."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import track

from tracker.exploration_state import Tracker


@pytest.fixture
def history_case(tmp_path, monkeypatch):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    identity = track.HistoryIdentity(
        raw["profile_id"], raw["runtime_signature"]["concatenated_sha256"], "jill"
    )
    path = tmp_path / "visits.json"
    history = track.VisitHistory(path, identity, {}, False)
    tracker = Tracker()
    tracker.mark_current(track.RoomId(0, 9))
    history.save(tracker)
    history.close()
    gdb = Mock()
    monkeypatch.setattr(track, "DuckStationGdb", gdb)
    root_logger = logging.getLogger()
    old_handlers, old_level = root_logger.handlers[:], root_logger.level
    # Real CLI logging uses force=True; keep it from closing pytest's handlers.
    root_logger.handlers = []
    try:
        yield path, identity, gdb
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = old_handlers
        root_logger.setLevel(old_level)


@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
@pytest.mark.parametrize("new_playthrough", [False, True])
def test_log_alias_rejection_preserves_history_before_connecting(
    history_case, tmp_path, monkeypatch, capsys, alias, new_playthrough
):
    path, identity, gdb = history_case
    before = path.read_bytes()
    log = path if alias == "direct" else tmp_path / "tracker.log"
    if alias == "symlink":
        log.symlink_to(path)
    elif alias == "hardlink":
        log.hardlink_to(path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--once",
            *(["--new-playthrough"] if new_playthrough else []),
            "--history-file",
            str(path),
            "--log-file",
            str(log),
        ],
    )
    result = track.main()
    assert path.read_bytes() == before
    assert result == 2
    assert "log output must differ from exploration history" in capsys.readouterr().err
    gdb.assert_not_called()
    restored = track.VisitHistory(path, identity, {}, False)
    try:
        assert restored.rooms == ("00-09",)
        assert restored.playthrough_id == json.loads(before)["playthrough_id"]
    finally:
        restored.close()


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
def test_rotation_destinations_cannot_replace_history_or_detach_a_live_lock(
    history_case, tmp_path, monkeypatch, capsys, index, alias
):
    path, identity, gdb = history_case
    writer = track.VisitHistory(path, identity, {}, False)
    lock = path.with_name(path.name + ".lock")
    # A large base log would rotate before its first startup message.
    log = lock if index == 0 and alias == "direct" else tmp_path / "tracker.log"
    destination = log if index == 0 else Path(f"{log}.{index}")
    protected = lock if index == 0 else path
    if alias == "direct" and index:
        path.rename(destination)
        path.symlink_to(destination)
    elif alias == "symlink":
        destination.symlink_to(protected)
    elif alias == "hardlink":
        if destination.exists():
            destination.unlink()
        destination.hardlink_to(protected)
    log.write_bytes(b"x" * (2 * 1024 * 1024))
    before, lock_before = path.read_bytes(), lock.read_bytes()
    inode = lock.stat().st_ino
    monkeypatch.setattr(
        sys,
        "argv",
        ["track.py", "--once", "--history-file", str(path), "--log-file", str(log)],
    )
    try:
        assert track.main() == 2
        assert "choose another --log-file" in capsys.readouterr().err
        assert path.read_bytes() == before
        assert lock.read_bytes() == lock_before and lock.stat().st_ino == inode
        with pytest.raises(track.HistoryError, match="history is in use"):
            track.VisitHistory(writer.path, identity, {}, False)
        gdb.assert_not_called()
    finally:
        writer.close()


@pytest.mark.parametrize(
    "filename",
    [
        "visit-history.json",
        *(target.history_filename for target in track.RE2_TARGETS.values()),
    ],
)
@pytest.mark.parametrize("exists", [False, True])
def test_default_histories_are_protected_before_profile_loading(
    tmp_path, monkeypatch, capsys, filename, exists
):
    monkeypatch.setattr(track, "__file__", str(tmp_path / "tools/track.py"))
    path = tmp_path / ".local" / filename
    if exists:
        path.parent.mkdir()
        path.write_bytes(b"retained history")
    handler, profile, gdb = Mock(), Mock(), Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(track.Re1Profile, "load", profile)
    monkeypatch.setattr(track, "DuckStationGdb", gdb)
    monkeypatch.setattr(sys, "argv", ["track.py", "--log-file", str(path)])
    assert track.main() == 2
    assert "log output must differ" in capsys.readouterr().err
    if exists:
        assert path.read_bytes() == b"retained history"
    else:
        assert not path.parent.exists()
    handler.assert_not_called()
    profile.assert_not_called()
    gdb.assert_not_called()


def test_new_explicit_history_cannot_be_created_as_a_log(tmp_path, monkeypatch, capsys):
    path = tmp_path / "not-created" / "history.json"
    handler = Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(
        sys,
        "argv",
        ["track.py", "--history-file", str(path), "--log-file", str(path)],
    )
    assert track.main() == 2
    assert "choose another --log-file" in capsys.readouterr().err
    assert not path.parent.exists()
    handler.assert_not_called()


def test_alias_check_failure_stops_before_opening_output(tmp_path, monkeypatch, capsys):
    handler = Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(
        track,
        "aliases_input",
        Mock(side_effect=PermissionError("cannot inspect inode")),
    )
    log = tmp_path / "not-created" / "tracker.log"
    monkeypatch.setattr(sys, "argv", ["track.py", "--log-file", str(log)])
    assert track.main() == 2
    assert "cannot check log output paths" in capsys.readouterr().err
    assert not log.parent.exists()
    handler.assert_not_called()


@pytest.mark.parametrize("index", range(4))
@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
def test_log_and_rotation_destinations_cannot_overwrite_the_selected_profile(
    history_case, tmp_path, monkeypatch, capsys, index, alias
):
    history, _, gdb = history_case
    log = tmp_path / "tracker.log"
    destination = log if index == 0 else Path(f"{log}.{index}")
    profile = destination if alias == "direct" else tmp_path / "profile.json"
    before = (REPO / "profiles/re1_directors_cut_slus00551.json").read_bytes()
    profile.write_bytes(before)
    if alias == "symlink":
        destination.symlink_to(profile)
    elif alias == "hardlink":
        destination.hardlink_to(profile)
    if index:
        log.write_bytes(b"x" * (2 * 1024 * 1024))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--profile",
            str(profile),
            "--history-file",
            str(history),
            "--log-file",
            str(log),
        ],
    )
    try:
        result = track.main()
    finally:
        assert profile.read_bytes() == before
    assert result == 2
    assert "choose another --log-file" in capsys.readouterr().err
    gdb.assert_not_called()


@pytest.mark.parametrize("exists", [False, True])
def test_default_profile_is_protected_before_opening_log_output(
    tmp_path, monkeypatch, capsys, exists
):
    monkeypatch.setattr(track, "__file__", str(tmp_path / "tools/track.py"))
    path = tmp_path / "profiles/re1_directors_cut_slus00551.json"
    if exists:
        path.parent.mkdir()
        path.write_bytes(b"retained profile")
    handler = Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(sys, "argv", ["track.py", "--log-file", str(path)])
    assert track.main() == 2
    assert "choose another --log-file" in capsys.readouterr().err
    if exists:
        assert path.read_bytes() == b"retained profile"
    else:
        assert not path.parent.exists()
    handler.assert_not_called()


def test_profile_guard_uses_the_same_literal_tilde_path_as_profile_loading(
    history_case, tmp_path, monkeypatch, capsys
):
    history, _, gdb = history_case
    profile = tmp_path / "~" / "profile.json"
    profile.parent.mkdir()
    before = (REPO / "profiles/re1_directors_cut_slus00551.json").read_bytes()
    profile.write_bytes(before)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--profile",
            "~/profile.json",
            "--history-file",
            str(history),
            "--log-file",
            str(profile),
        ],
    )
    try:
        result = track.main()
    finally:
        assert profile.read_bytes() == before
    assert result == 2
    assert "choose another --log-file" in capsys.readouterr().err
    gdb.assert_not_called()
