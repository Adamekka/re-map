"""Tracker output must preserve its inputs and the history writer lock."""

import json
import logging
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import track
from test_re3_tracking import coherent as coherent  # noqa: PLC0414
from test_re3_tracking import live as live  # noqa: PLC0414
from test_re3_tracking import tracking as tracking  # noqa: PLC0414

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


@pytest.fixture
def disc_input(tmp_path):
    cue, image = tmp_path / "owned.cue", tmp_path / "owned track.bin"
    cue.write_text(
        'REM Previous FILE "ignored.bin" BINARY\n'
        f'FILE "{image.name}" BINARY\n  TRACK 01 MODE2/2352\n'
    )
    image.write_bytes(b"disposable track content")
    return cue, image


@pytest.mark.parametrize("source", ["cue", "track", "audio"])
@pytest.mark.parametrize("alias", ["direct", "symlink", "backup-hardlink"])
def test_log_output_cannot_alias_either_owned_disc_file(
    disc_input, tmp_path, monkeypatch, capsys, source, alias
):
    cue, image = disc_input
    audio = tmp_path / "audio.bin"
    audio.write_bytes(b"disposable audio")
    with cue.open("a") as output:
        output.write(f"FILE {audio.name} BINARY\n  TRACK 02 AUDIO\n")
    media = {"cue": cue, "track": image, "audio": audio}[source]
    before = media.read_bytes()
    log = tmp_path / "tracker.log"
    if alias == "direct":
        log = media
    elif alias == "symlink":
        log.symlink_to(media)
    else:
        log.with_name(log.name + ".3").hardlink_to(media)
    handler, loader = Mock(), Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(track, "load_owned_sources", loader)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--profile",
            str(REPO / "profiles/re3_jill_hard_slus00923.json"),
            "--disc",
            str(cue),
            "--log-file",
            str(log),
        ],
    )
    assert track.main() == 2
    assert "choose another --log-file" in capsys.readouterr().err
    assert media.read_bytes() == before
    handler.assert_not_called()
    loader.assert_not_called()


@pytest.mark.parametrize(
    "cue_bytes, diagnostic",
    [
        (b"no track here\n", "names no data track"),
        (b'FILE "owned.bin" BINARY\nREM \xff\n', "utf-8"),
        (b'FILE "owned\0.bin" BINARY\n', "embedded null byte"),
        (b'FILE "owned.bin\n', "invalid CUE FILE directive"),
        (
            b'FILE "track.bin" BINARY\nFILE"owned.bin" BINARY\n',
            "invalid CUE FILE directive",
        ),
    ],
)
def test_unparseable_cue_rejects_startup_before_opening_outputs(
    tmp_path, monkeypatch, capsys, cue_bytes, diagnostic
):
    cue = tmp_path / "malformed.cue"
    cue.write_bytes(cue_bytes)
    log = tmp_path / "owned.bin"
    log.write_bytes(b"disposable disc content")
    handler = Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(
        sys, "argv", ["track.py", "--disc", str(cue), "--log-file", str(log)]
    )
    assert track.main() == 2
    error = capsys.readouterr().err
    assert "RE3 disc rejected:" in error and diagnostic in error
    assert log.read_bytes() == b"disposable disc content"
    handler.assert_not_called()


def test_log_alias_check_requires_access_to_the_disc_identity(
    disc_input, tmp_path, monkeypatch, capsys
):
    cue, image = disc_input
    log = tmp_path / "tracker.log"
    log.hardlink_to(image)
    before = log.read_bytes()
    original_stat = Path.stat

    def denied_stat(path, *args, **kwargs):
        if path == image:
            raise PermissionError("cannot inspect track path")
        return original_stat(path, *args, **kwargs)

    handler = Mock()
    monkeypatch.setattr(Path, "stat", denied_stat)
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(
        sys, "argv", ["track.py", "--disc", str(cue), "--log-file", str(log)]
    )
    assert track.main() == 2
    assert "cannot inspect track path" in capsys.readouterr().err
    assert log.read_bytes() == before
    handler.assert_not_called()


def test_log_rotation_cannot_move_a_symlink_on_the_disc_track_path(
    disc_input, tmp_path, monkeypatch, capsys
):
    cue, image = disc_input
    directory = tmp_path / "tracks"
    directory.mkdir()
    image = image.rename(directory / image.name)
    backup = tmp_path / "tracker.log.1"
    backup.symlink_to(directory, target_is_directory=True)
    cue.write_text(f'FILE "{backup.name}/{image.name}" BINARY\n')
    handler = Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(
        sys,
        "argv",
        ["track.py", "--disc", str(cue), "--log-file", str(tmp_path / "tracker.log")],
    )
    assert track.main() == 2
    assert "path is a directory" in capsys.readouterr().err
    assert backup.is_symlink()
    assert (backup / image.name).read_bytes() == image.read_bytes()
    handler.assert_not_called()


@pytest.mark.parametrize("source", ["profile", "cue", "track"])
@pytest.mark.parametrize("output", ["history", "lock"])
def test_history_output_cannot_alias_tracker_inputs(
    disc_input, tmp_path, monkeypatch, capsys, source, output
):
    cue, image = disc_input
    profile = tmp_path / "profile.json"
    profile.write_text('{"profile_id": "re3_jill_hard_slus00923"}')
    media = {"profile": profile, "cue": cue, "track": image}[source]
    before = media.read_bytes()
    history = media if output == "history" else tmp_path / "history.json"
    if output == "lock":
        history.with_name(history.name + ".lock").symlink_to(media)
    handler, loader = Mock(), Mock()
    monkeypatch.setattr(track, "RotatingFileHandler", handler)
    monkeypatch.setattr(track, "load_owned_sources", loader)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--profile",
            str(profile),
            "--disc",
            str(cue),
            "--history-file",
            str(history),
            "--new-playthrough",
            "--log-file",
            str(tmp_path / "tracker.log"),
        ],
    )
    assert track.main() == 2
    assert "choose another --history-file" in capsys.readouterr().err
    assert media.read_bytes() == before
    handler.assert_not_called()
    loader.assert_not_called()


def test_separate_paths_allow_re3_tracking_and_history_writes(
    history_case, disc_input, tracking, tmp_path, monkeypatch, capsys
):
    _, _, gdb_factory = history_case
    cue, image = disc_input
    before = cue.read_bytes(), image.read_bytes()
    profile, _, read, _ = tracking
    loader = Mock(return_value=(b"synthetic executable", ()))
    profile_loader = Mock(return_value=profile)
    monkeypatch.setattr(track, "load_owned_sources", loader)
    monkeypatch.setattr(track.Re3Profile, "load", profile_loader)
    gdb = gdb_factory.return_value
    gdb.connected = True
    gdb.connect.return_value = ""
    gdb.resume.return_value = ""
    gdb.read_memory.side_effect = read
    profile_path = REPO / "profiles/re3_jill_hard_slus00923.json"
    history = tmp_path / "re3-visits.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--once",
            "--profile",
            str(profile_path),
            "--disc",
            str(cue),
            "--history-file",
            str(history),
            "--log-file",
            str(tmp_path / "tracker.log"),
        ],
    )
    assert track.main() == 0
    assert "Current room: 00-00" in capsys.readouterr().out
    assert json.loads(history.read_text())["rooms"] == ["00-00"]
    assert (cue.read_bytes(), image.read_bytes()) == before
    loader.assert_called_once_with(image)
    profile_loader.assert_called_once_with(profile_path, b"synthetic executable", ())
