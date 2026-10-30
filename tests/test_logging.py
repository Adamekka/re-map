"""CLI startup failures must remain available after terminal output disappears."""

import socket
import json
import logging
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from test_re2_tracking import profile as profile, snapshot as snapshot

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import track
from tracker.polling import PollResult, PollStatus


def test_connection_failure_is_written_to_file(tmp_path: Path):
    log = tmp_path / "logs/tracker.log"
    # A bound, non-listening port gives a connection refusal without another server racing us.
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        result = subprocess.run(
            [
                sys.executable,
                str(REPO / "tools/track.py"),
                "--once",
                "--port",
                str(reserved.getsockname()[1]),
                "--log-file",
                str(log),
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    assert result.returncode == 1
    assert f"Log file: {log}" in result.stdout
    contents = log.read_text()
    assert "Tracker started:" in contents
    assert "Expected runtime signature SHA256:" in contents
    assert "ERROR" in contents
    assert "GDB connection failed: connect failed:" in contents


def test_unexpected_profile_error_keeps_traceback(tmp_path: Path):
    profile = tmp_path / "invalid.json"
    profile.write_text("{")
    log = tmp_path / "tracker.log"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/track.py"),
            "--once",
            "--profile",
            str(profile),
            "--log-file",
            str(log),
        ],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 1
    contents = log.read_text()
    assert "Tracker failed unexpectedly" in contents
    assert "Traceback" in contents
    assert "JSONDecodeError" in contents


def test_unwritable_log_path_reports_startup_failure(tmp_path: Path):
    result = subprocess.run(
        [sys.executable, str(REPO / "tools/track.py"), "--log-file", str(tmp_path)],
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 2
    assert "cannot open log file" in result.stderr


@pytest.mark.parametrize(
    "profile_id,status,text,expected",
    [
        (
            "re2_claire_b_slus00592",
            PollStatus.WrongGame,
            "This profile requires Claire B",
            "Waiting for Resident Evil 2, Claire B.",
        ),
        (
            "re2_leon_a_slus00421",
            PollStatus.WrongGame,
            "This profile requires Leon A",
            "Waiting for Resident Evil 2, Leon A.",
        ),
        (
            "re2_leon_a_slus00748",
            PollStatus.UnsupportedSettings,
            "Unsupported RE2 game settings. Load a supported Leon A savestate.",
            "Unsupported RE2 game settings. Load a supported Leon A savestate.",
        ),
        (
            "re2_claire_b_slus00592",
            PollStatus.UnsupportedRoom,
            "This room cannot be tracked yet. Visits were not recorded.",
            "This room cannot be tracked yet. Visits were not recorded.",
        ),
        (
            "re2_claire_b_slus00592",
            PollStatus.ReadFailure,
            "transport failed",
            "Game connection interrupted. Check DuckStation and its GDB server.",
        ),
    ],
)
def test_live_map_publishes_scenario_and_unsupported_room_messages(
    tmp_path, monkeypatch, profile_id, status, text, expected
):
    # Keep the real CLI publication path while replacing its external I/O.
    server = Mock(spec=track.MapServer)
    server.snapshot = b"{}"
    server.serve_forever.return_value = None
    gdb = Mock(spec=track.DuckStationGdb)
    gdb.connected = True
    gdb.connect.return_value = None
    gdb.resume.return_value = None
    monkeypatch.setattr(track, "MapServer", Mock(return_value=server))
    monkeypatch.setattr(track, "DuckStationGdb", Mock(return_value=gdb))
    monkeypatch.setattr(track, "poll_once", Mock(return_value=PollResult(status, text)))
    monkeypatch.setattr(track.time, "sleep", Mock(side_effect=KeyboardInterrupt))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--map",
            "--profile",
            str(REPO / "profiles" / (profile_id + ".json")),
            "--history-file",
            str(tmp_path / "history.json"),
            "--log-file",
            str(tmp_path / "tracker.log"),
        ],
    )
    root_logger = logging.getLogger()
    old_handlers, old_level = root_logger.handlers[:], root_logger.level
    # CLI logging uses force=True; detach pytest handlers so it cannot close them.
    root_logger.handlers = []
    try:
        assert track.main() == 0
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = old_handlers
        root_logger.setLevel(old_level)
    snapshot = json.loads(server.snapshot)
    assert snapshot["status"] == "waiting"
    assert snapshot["current"] is None and snapshot["rooms"] == []
    assert snapshot["error"] == expected
    gdb.read_memory.assert_not_called()


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
def test_unsupported_settings_map_recovers_from_fresh_game_state(
    tmp_path, monkeypatch, capsys, snapshot
):
    observed_profile, _, put, read = snapshot
    layout = observed_profile.runtime_layout
    system_address = int(layout["system_flags_address_ps1"], 0)
    put(system_address, layout["gameplay_mask"], 4)
    server = Mock(spec=track.MapServer)
    server.snapshot = b"{}"
    server.serve_forever.return_value = None
    gdb = Mock(spec=track.DuckStationGdb)
    gdb.connected = True
    gdb.connect.return_value = ""
    gdb.resume.return_value = ""
    gdb.read_memory.side_effect = read
    monkeypatch.setattr(track, "MapServer", Mock(return_value=server))
    monkeypatch.setattr(track, "DuckStationGdb", Mock(return_value=gdb))
    monkeypatch.setattr(track.Re2Profile, "load", Mock(return_value=observed_profile))
    history_path = tmp_path / "history.json"
    snapshots = []

    def next_poll(period):
        snapshots.append(json.loads(server.snapshot))
        if len(snapshots) == 1:
            assert not history_path.exists()
            put(
                system_address, layout["gameplay_mask"] | layout["system_mode_value"], 4
            )
        else:
            raise KeyboardInterrupt

    monkeypatch.setattr(track.time, "sleep", next_poll)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--map",
            "--profile",
            str(REPO / "profiles/re2_leon_a_slus00748.json"),
            "--history-file",
            str(history_path),
            "--log-file",
            str(tmp_path / "tracker.log"),
        ],
    )
    root_logger = logging.getLogger()
    old_handlers, old_level = root_logger.handlers[:], root_logger.level
    # Preserve pytest's handlers across the CLI's force=True logging setup.
    root_logger.handlers = []
    try:
        assert track.main() == 0
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = old_handlers
        root_logger.setLevel(old_level)
    message = "Unsupported RE2 game settings. Load a supported Leon A savestate."
    assert snapshots[0] == {
        "status": "waiting",
        "current": None,
        "rooms": [],
        "error": message,
    }
    assert snapshots[1]["status"] == "display"
    assert snapshots[1]["current"] == "00-01"
    assert json.loads(history_path.read_text())["rooms"] == ["00-01"]
    output = capsys.readouterr().out
    assert message in output and "; waiting for game" not in output
    assert (
        "WARNING track: Poll unsupported-settings"
        in (tmp_path / "tracker.log").read_text()
    )
    gdb.connect.assert_called_once()
    gdb.resume.assert_called_once()


@pytest.mark.parametrize(
    "status,exit_code",
    [
        (PollStatus.UnsupportedRoom, 1),
        (PollStatus.ReadFailure, 1),
        (PollStatus.WrongGame, 2),
        (PollStatus.UnsupportedSettings, 2),
    ],
)
def test_once_failure_reports_diagnostic_without_persisting_visits(
    tmp_path, monkeypatch, capsys, status, exit_code
):
    gdb = Mock(spec=track.DuckStationGdb)
    gdb.connected = True
    gdb.connect.return_value = None
    gdb.resume.return_value = None
    message = (
        "Unsupported RE2 game settings. Load a supported Claire B savestate."
        if status is PollStatus.UnsupportedSettings
        else "The current room could not be tracked."
    )
    monkeypatch.setattr(track, "DuckStationGdb", Mock(return_value=gdb))
    monkeypatch.setattr(
        track, "poll_once", Mock(return_value=PollResult(status, message))
    )
    history = tmp_path / "history.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--once",
            "--profile",
            str(REPO / "profiles/re2_claire_b_slus00592.json"),
            "--history-file",
            str(history),
            "--log-file",
            str(tmp_path / "tracker.log"),
        ],
    )
    root_logger = logging.getLogger()
    old_handlers, old_level = root_logger.handlers[:], root_logger.level
    # Preserve pytest's handlers across the CLI's force=True logging setup.
    root_logger.handlers = []
    try:
        assert track.main() == exit_code
    finally:
        for handler in root_logger.handlers:
            handler.close()
        root_logger.handlers = old_handlers
        root_logger.setLevel(old_level)
    assert message in capsys.readouterr().err
    assert not history.exists()
    if status is PollStatus.UnsupportedSettings:
        assert (
            "WARNING track: Poll unsupported-settings"
            in (tmp_path / "tracker.log").read_text()
        )
    gdb.read_memory.assert_not_called()
