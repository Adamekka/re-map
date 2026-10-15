"""RE1-PLAYER-002: native yaw, coherent publication and state reversal."""

import json
import struct

import pytest
from test_live_items import REPO, RamReader, fixture_ram
from track import PollStatus, poll_once

from emulator.duckstation_gdb import MemRead
from games.re1.map_layout import decode_player_heading
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import Tracker
from ui.map_view import map_state


@pytest.mark.parametrize(
    "yaw,heading",
    [(0, 90), (1024, 180), (2048, 270), (3072, 0), (4096, 90), (0xFC00, 0)],
)
def test_native_quarter_turns_and_high_bits(yaw, heading):
    assert decode_player_heading(struct.pack("<H", yaw)) == heading


@pytest.mark.parametrize("data", [b"", b"\x00", bytes(3)])
def test_heading_rejects_partial_or_oversized_reads(data):
    with pytest.raises(ValueError, match="halfword"):
        decode_player_heading(data)


@pytest.mark.parametrize(
    "fixture,heading",
    [("chemical", 220.078125), ("green_herb", 208.828125)],
)
def test_publishes_the_fixture_yaw_instead_of_a_derived_matrix_component(
    tmp_path, fixture, heading
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram(f"slus00551_{fixture}_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        is PollStatus.Display
    )
    assert map_state(tracker)["player_heading"] == heading


@pytest.mark.parametrize("address", [None, "0x801FFFFF", "0x7FFFFFFF"])
def test_runtime_profile_requires_a_complete_facing_address(tmp_path, address):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    if address is None:
        del raw["player_facing_address_ps1"]
    else:
        raw["player_facing_address_ps1"] = address
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="player_facing_address_ps1"):
        Re1Profile.load(path)


def test_fresh_heading_reverses_without_caching_or_requiring_stationary_player(
    tmp_path,
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    reader = RamReader(ram)
    tracker = Tracker()
    offset = profile.player_facing_address - 0x80000000
    original = bytes(ram[offset : offset + 2])
    for yaw in (0, 1024, 2048, 3072, 0):
        struct.pack_into("<H", ram, offset, yaw)
        assert (
            poll_once(profile, tracker, reader.read_memory).status is PollStatus.Display
        )
        assert map_state(tracker)["player_heading"] == decode_player_heading(
            struct.pack("<H", yaw)
        )
    ram[offset : offset + 2] = original
    assert poll_once(profile, tracker, reader.read_memory).status is PollStatus.Display
    assert tracker.player_heading == decode_player_heading(original)


@pytest.mark.parametrize("short", [False, True])
def test_heading_read_failure_does_not_publish_a_visit(tmp_path, short):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    reader = RamReader(ram)
    tracker = Tracker()

    def read(address, width):
        if address == profile.player_facing_address:
            return MemRead(
                ok=short, data=b"\x00" if short else b"", error="injected failure"
            )
        return reader.read_memory(address, width)

    result = poll_once(profile, tracker, read)
    assert result.status is PollStatus.ReadFailure
    assert "player facing" in result.text
    assert tracker.current is None and tracker.player_heading is None
    assert not tracker.rooms and not tracker.region_visits
    assert not profile.room_observations


def test_camera_change_during_heading_read_does_not_reveal_a_floor(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    tracker = Tracker()

    def read(address, width):
        if address == profile.player_facing_address:
            ram[profile.camera_address - 0x80000000] ^= 1
        return reader.read_memory(address, width)

    result = poll_once(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert "camera changed" in result.text
    assert not tracker.rooms and not tracker.region_visits
    assert tracker.player_heading is None
