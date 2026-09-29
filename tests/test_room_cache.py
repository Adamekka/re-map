"""Room/load identity and cached acquisition reversals must remain explicit."""

import hashlib
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from test_live_items import RamReader, fixture_ram
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from games.re1.room_cache import RoomMutableField, RoomScriptSource, match_room_source
from tracker.exploration_state import RoomCompletion, Tracker
from ui.map_view import map_state


def test_source_binding_rejects_old_rdt_during_a_room_transition(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xC8661] = 8
    tracker = Tracker()
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status == PollStatus.Retry
    assert tracker.rooms == {}
    assert tracker.region_visits == {}
    assert profile.room_observations == {}


def test_source_binding_checks_script_content_not_just_the_header(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    source = next(
        source
        for source in profile.room_sources
        if source.source_rdt.endswith("1091.RDT")
    )
    ram[0x121C00 + source.init_offset + source.init_size - 1] ^= 1
    result = match_room_source(
        profile.runtime_room_layout,
        profile.room_sources,
        RoomId(0, 9),
        RamReader(ram).read_memory,
    )
    assert not result.ok and result.retry
    assert "script identity" in result.error


def test_prior_herb_room_rereads_acquisition_flags_after_a_load(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Incomplete
    assert (
        poll_once(profile, tracker, RamReader(chemical).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Cleared
    # This models replacing the persistent pickup bytes while remaining in another room.
    chemical[0xC86EA] |= 1
    assert (
        poll_once(profile, tracker, RamReader(chemical).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Incomplete


def test_a_rewind_cannot_reuse_an_empty_past_room_manifest(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    herb[0xB81A4:0xB81A8] = bytes(4)
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).total_items == 0
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Cleared
    chemical[0xC86EA] |= 1
    assert (
        poll_once(profile, tracker, RamReader(chemical).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Unknown
    assert (
        tracker.room_state(RoomId(0, 9)).reason
        == "Re-enter this room to refresh its items."
    )


def test_changed_story_branch_invalidates_prior_chemical_completion(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    chemical = fixture_ram("slus00551_chemical_after.sav", tmp_path)
    herb = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(chemical).read_memory).status
        == PollStatus.Display
    )
    herb[0xC3006] |= 2
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 24)).completion == RoomCompletion.Unknown


@pytest.mark.parametrize("pointer", [0, 0x7FFFFFFF, 0x801FFFA0, 0x80200000])
def test_source_binding_rejects_out_of_ram_pointers_before_reading(pointer, tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xCAB10:0xCAB14] = pointer.to_bytes(4, "little")
    reader = RamReader(ram)
    reads = []

    def read(address, length):
        reads.append(address)
        return reader.read_memory(address, length)

    result = match_room_source(
        profile.runtime_room_layout, profile.room_sources, RoomId(0, 9), read
    )
    assert not result.ok and not result.retry
    assert "outside PS1 RAM" in result.error
    assert reads == [profile.runtime_room_layout.loaded_rdt_pointer_address]


@pytest.mark.parametrize(
    ("parameter", "quantity", "corrupt_opcode", "accepted"),
    [
        (0x184, 2, False, True),
        (0, 250, False, True),
        (1, 2, False, False),
        (0, 250, True, False),
    ],
)
def test_source_identity_accepts_only_audited_runtime_mutations(
    parameter, quantity, corrupt_opcode, accepted
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    layout = profile.runtime_room_layout
    ram = bytearray(layout.ram_size)
    base = layout.ram_base + 0x1000
    struct.pack_into(
        "<I", ram, layout.loaded_rdt_pointer_address - layout.ram_base, base
    )
    struct.pack_into(
        "<4I", ram, 0x1060, base + 0x100, base + 0x11A, base + 0x11E, base + 0x122
    )
    original = bytearray(26)
    original[0] = 0x18
    original[11] = 2
    struct.pack_into("<H", original, 24, 0x184)
    source = RoomScriptSource(
        room=RoomId(0, 0),
        source_rdt="synthetic.RDT",
        init_offset=0x100,
        init_size=26,
        init_sha256=hashlib.sha256(original).hexdigest(),
        main_offset=0x11A,
        main_size=4,
        main_sha256=hashlib.sha256(bytes(4)).hexdigest(),
        dependencies=(),
        item_global_ids=(),
        cache_complete=False,
        door_cache_complete=False,
        mutable_fields=(
            RoomMutableField("init", 24, 2, "item-parameter-mask", 0x184),
            RoomMutableField("init", 11, 1, "item-quantity", 2),
        ),
    )
    live = bytearray(original)
    struct.pack_into("<H", live, 24, parameter)
    live[11] = quantity
    if corrupt_opcode:
        live[0] ^= 1
    ram[0x1100:0x111A] = live
    result = match_room_source(
        layout, (source,), source.room, RamReader(ram).read_memory
    )
    assert result.ok == accepted
    assert result.retry == (not accepted)


@pytest.mark.parametrize("invalid", ["overlap", "out-of-range", "wrong-kind"])
def test_mutable_field_invariants_are_enforced_at_construction(invalid):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    source = next(source for source in profile.room_sources if source.mutable_fields)
    field = source.mutable_fields[0]
    with pytest.raises(ValueError, match="mutable field"):
        if invalid == "wrong-kind":
            replace(field, kind="any-byte")
        elif invalid == "overlap":
            replace(source, mutable_fields=(field, field))
        else:
            replace(source, mutable_fields=(replace(field, offset=source.init_size),))


def test_item_cache_does_not_authorize_reusing_a_mutable_door_definition(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    profile.room_sources = tuple(
        replace(source, door_cache_complete=False) for source in profile.room_sources
    )
    tracker = Tracker()
    herb = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    assert any(door.source == RoomId(0, 9) for door in tracker.doors)
    assert (
        poll_once(profile, tracker, RamReader(chemical).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Cleared
    assert not any(door.source == RoomId(0, 9) for door in tracker.doors)
    assert any(door.source == RoomId(0, 24) for door in tracker.doors)


def test_reusing_a_profile_with_a_new_tracker_keeps_history_in_the_old_session(
    tmp_path,
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    assert (
        poll_once(profile, Tracker(), RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(chemical).read_memory).status
        == PollStatus.Display
    )
    assert set(tracker.rooms) == {"00-18"}
    assert not any(door.source == RoomId(0, 9) for door in tracker.doors)


def test_unbound_room_id_cannot_reveal_an_unresolved_floor_plan_region(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    ram[0xC8661] = 0x1F
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert tracker.region_visits == {}
    assert tracker.current_region == ""
    assert map_state(tracker)["area"] == "unmapped"
