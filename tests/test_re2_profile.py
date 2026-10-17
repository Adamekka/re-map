"""RE2-IDENTITY-001: revision isolation and complete halfword room reads."""

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re2.re2_profile import Re2Profile
from games.runtime_identity import RuntimeSignature


def test_re2_profile_pins_leon_disc_and_halfword_addresses():
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    assert profile.stage_address == 0x800CC948
    assert profile.room_address == 0x800CC94A
    assert profile.camera_address == 0x800CC94C
    assert profile.executable_identity.endswith(
        "1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef"
    )
    assert profile.read_current_room(
        lambda address, width: MemRead(
            True, {0x800CC948: b"\x01\x00", 0x800CC94A: b"\x1a\x00"}[address]
        )
    ).room == RoomId(1, 0x1A)


@pytest.mark.parametrize("data", [b"", b"\x00", b"\x00\x01", b"\xff\xff"])
def test_re2_room_rejects_short_or_invalid_halfwords(data):
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    result = profile.read_current_room(lambda address, width: MemRead(True, data))
    assert not result.ok
    assert result.room is None


def test_re2_room_preserves_transport_failure():
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    result = profile.read_current_room(
        lambda address, width: MemRead(False, b"", "disconnected")
    )
    assert not result.ok
    assert "disconnected" in result.error


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("scenario", "leon-b"),
        ("serial", "SLUS-00748"),
        ("room_value_width_bytes", 1),
        ("room_address_ps1", "0xCC94A"),
        ("stage_address_ps1", "0x801FFFFF"),
    ],
)
def test_re2_profile_rejects_incompatible_layout(tmp_path, key, value):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    raw[key] = value
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        Re2Profile.load(path)


def test_revision_signature_distinguishes_wrong_game_and_failed_read():
    signature = RuntimeSignature(
        (0x80010000, 0x80020000), 32, hashlib.sha256(bytes(64)).hexdigest()
    )
    profile = replace(
        Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json"),
        runtime_signature=signature,
    )
    assert profile.verify_runtime(
        lambda address, width: MemRead(True, bytes(width))
    ).value
    mismatch = profile.verify_runtime(
        lambda address, width: MemRead(True, b"x" * width)
    )
    assert mismatch.ok and not mismatch.value
    short = profile.verify_runtime(lambda address, width: MemRead(True, b"x"))
    assert not short.ok and "short signature" in short.error
    failure = profile.verify_runtime(
        lambda address, width: MemRead(False, b"", "disconnected")
    )
    assert not failure.ok and "disconnected" in failure.error
