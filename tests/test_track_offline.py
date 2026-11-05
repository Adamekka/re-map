"""Offline snapshots use the revision-bound live interpretation without I/O to an emulator."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import track
import track_offline
from test_live_items import fixture_ram


@pytest.mark.parametrize(
    "kind,room,label",
    [("green_herb", "00-09", "Green Herb"), ("chemical", "00-18", "Chemical")],
)
@pytest.mark.parametrize("when", ["before", "after"])
def test_offline_cli_uses_the_verified_profile_and_captured_item_state(
    tmp_path, monkeypatch, capsys, kind, room, label, when
):
    ram = fixture_ram(f"slus00551_{kind}_{when}.sav", tmp_path)
    path = tmp_path / "snapshot.bin"
    path.write_bytes(ram)
    gdb, history, server = Mock(), Mock(), Mock()
    monkeypatch.setattr(track, "DuckStationGdb", gdb)
    monkeypatch.setattr(track, "VisitHistory", history)
    monkeypatch.setattr(track, "MapServer", server)
    monkeypatch.setattr(sys, "argv", ["track_offline.py", str(path)])
    monkeypatch.chdir(tmp_path)
    assert track_offline.main() == 0
    output = capsys.readouterr()
    assert not output.err
    assert "Profile: re1_directors_cut_slus00551" in output.out
    assert f"Current room: {room}" in output.out
    assert f"{label}: {'taken' if when == 'after' else 'available'}" in output.out
    assert f"State: {'CLEARED' if when == 'after' else 'INCOMPLETE'}" in output.out
    assert "List complete: yes" in output.out
    gdb.assert_not_called()
    history.assert_not_called()
    server.assert_not_called()


@pytest.mark.parametrize("fault", ["short", "long", "wrong-game", "non-gameplay"])
def test_offline_cli_rejects_invalid_snapshots_without_a_room_verdict(
    tmp_path, monkeypatch, capsys, fault
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    if fault == "short":
        ram.pop()
    elif fault == "long":
        ram.append(0)
    elif fault == "wrong-game":
        profile = track.Re1Profile.load(
            REPO / "profiles/re1_directors_cut_slus00551.json"
        )
        ram[profile.runtime_signature.window_addresses[0] - 0x80000000] ^= 1
    else:
        ram[0xC866C] = 0
    path = tmp_path / "snapshot.bin"
    path.write_bytes(ram)
    monkeypatch.setattr(sys, "argv", ["track_offline.py", str(path)])
    assert track_offline.main() != 0
    output = capsys.readouterr()
    assert output.err and not output.out
    assert "State:" not in output.err


def test_offline_cli_reports_an_unreadable_snapshot(tmp_path, monkeypatch, capsys):
    path = tmp_path / "missing.bin"
    monkeypatch.setattr(sys, "argv", ["track_offline.py", str(path)])
    assert track_offline.main() == 2
    assert "Cannot read RAM image" in capsys.readouterr().err
