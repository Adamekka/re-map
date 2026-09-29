"""CLI startup failures must remain available after terminal output disappears."""

import socket
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


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
