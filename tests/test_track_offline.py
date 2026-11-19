"""Offline snapshots use the revision-bound live interpretation without I/O to an emulator."""

import json
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import track
import track_offline
from test_live_items import fixture_ram
from test_re2_tracking import profile as profile  # noqa: PLC0414
from test_re2_tracking import snapshot as snapshot  # noqa: PLC0414
from test_re3_tracking import coherent as coherent  # noqa: PLC0414
from test_re3_tracking import live as live  # noqa: PLC0414
from test_re3_tracking import tracking as tracking  # noqa: PLC0414


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


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
def test_offline_cli_uses_the_re2_profile_and_reader(
    snapshot, tmp_path, monkeypatch, capsys
):
    profile, ram, _, _ = snapshot
    loader = Mock(return_value=profile)
    monkeypatch.setattr(track.Re2Profile, "load", loader)
    profile_path = REPO / "profiles/re2_leon_a_slus00748.json"
    capture = tmp_path / "re2.bin"
    capture.write_bytes(ram)
    monkeypatch.setattr(
        sys, "argv", ["track_offline.py", str(capture), "--profile", str(profile_path)]
    )
    assert track_offline.main() == 0
    output = capsys.readouterr()
    assert not output.err
    assert "Profile: re2_leon_a_slus00748" in output.out
    assert "Current room: 00-01" in output.out
    loader.assert_called_once_with(profile_path)


def test_offline_cli_loads_the_re3_disc_and_reads_the_snapshot(
    tracking, tmp_path, monkeypatch, capsys
):
    profile, _, _, ram = tracking
    media = Mock(return_value=(b"synthetic executable", ()))
    loader = Mock(return_value=profile)
    monkeypatch.setattr(track, "load_owned_sources", media)
    monkeypatch.setattr(track.Re3Profile, "load", loader)
    profile_path = REPO / "profiles/re3_jill_hard_slus00923.json"
    cue, image = tmp_path / "test.cue", tmp_path / "data track.bin"
    cue.write_text(f'FILE "{image.name}" BINARY\n')
    capture = tmp_path / "re3.bin"
    capture.write_bytes(ram)
    input_paths = set(tmp_path.iterdir())
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track_offline.py",
            str(capture),
            "--profile",
            str(profile_path),
            "--disc",
            str(cue),
        ],
    )
    monkeypatch.chdir(tmp_path)
    assert track_offline.main() == 0
    output = capsys.readouterr()
    assert not output.err
    assert "Profile: re3_jill_hard_slus00923" in output.out
    assert "Current room: 00-00" in output.out
    assert "Handgun ammo: uncollected" in output.out
    media.assert_called_once_with(image)
    loader.assert_called_once_with(profile_path, b"synthetic executable", ())
    assert set(tmp_path.iterdir()) == input_paths


@pytest.mark.parametrize(
    "case, diagnostic",
    [
        ("missing-disc", "RE3 tracking needs --disc"),
        ("bad-disc", "RE3 disc rejected:"),
        ("unknown-home", "Could not determine home directory"),
        ("bad-profile", "profile_id must be a string"),
    ],
)
def test_offline_cli_reports_invalid_profile_or_disc(
    tmp_path, monkeypatch, capsys, case, diagnostic
):
    capture = tmp_path / "snapshot.bin"
    capture.write_bytes(bytes(0x200000))
    profile = REPO / "profiles/re3_jill_hard_slus00923.json"
    if case == "bad-profile":
        profile = tmp_path / "bad.json"
        profile.write_text('{"profile_id": 42}')
    arguments = ["track_offline.py", str(capture), "--profile", str(profile)]
    if case == "bad-disc":
        cue = tmp_path / "bad.cue"
        cue.write_text('FILE "missing.bin" BINARY\n')
        arguments.extend(("--disc", str(cue)))
    elif case == "unknown-home":
        arguments.extend(("--disc", "~re-map-user-that-does-not-exist/game.cue"))
    monkeypatch.setattr(sys, "argv", arguments)
    assert track_offline.main() == 2
    output = capsys.readouterr()
    assert diagnostic in output.err and not output.out


@pytest.mark.parametrize("identity", [None, "invalid"])
def test_offline_cli_reports_a_malformed_re3_identity_as_a_profile_error(
    tmp_path, monkeypatch, capsys, identity
):
    profile = tmp_path / "profile.json"
    profile.write_text(
        json.dumps(
            {
                "profile_id": "re3_jill_hard_slus00923",
                "executable_identity": identity,
            }
        )
    )
    cue = tmp_path / "test.cue"
    cue.write_text('FILE "data track.bin" BINARY\n')
    capture = tmp_path / "re3.bin"
    capture.write_bytes(bytes(0x200000))
    monkeypatch.setattr(track, "load_owned_sources", Mock(return_value=(b"", ())))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track_offline.py",
            str(capture),
            "--profile",
            str(profile),
            "--disc",
            str(cue),
        ],
    )
    assert track_offline.main() == 2
    output = capsys.readouterr()
    assert f"Cannot load profile {profile}: executable_identity" in output.err
    assert not output.out
