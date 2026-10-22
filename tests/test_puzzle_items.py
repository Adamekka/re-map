"""RE1-CLEAR-005: known puzzle items remain until their pickup flag changes."""

import json
import struct
import sys
from dataclasses import replace
from pathlib import Path

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / name) for name in ("src", "tools")
]

import pytest
from build_cache_metadata import scan_cache_rdt
from test_cache_metadata import pickup, source
from test_live_items import REPO, RamReader, fixture_ram
from test_tracking_rules import branch, guard
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from games.re1.room_cache import RoomDependency, RoomMutableField
from games.re1.room_items import RuntimeItemState, RuntimeRoomItems
from games.re1.tracking_engine import validate_current_room
from games.re1.tracking_rules import (
    RoomProgram,
    evaluate_room_program,
    read_rule_snapshot,
)
from tracker.exploration_state import RoomCompletion, Tracker


@pytest.fixture
def dormant_room(tmp_path, request):
    profile_path = REPO / "profiles/re1_directors_cut_slus00551.json"
    profile = Re1Profile.load(profile_path)
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    item = bytearray(pickup(5, 0x44, 111))
    item[23], item[24] = 129, 1
    creator = bytes(item)
    scenario = getattr(request, "param", "mandatory")
    if scenario == "optional":
        creator = guard(bytes((4, 4, 64, 0)), creator)
    elif scenario == "alternative":
        creator = branch(bytes((4, 4, 64, 0)), creator, pickup(5, 0x26, 13))
    # Opcode 12 replaces all three registry words but preserves the pointer.
    init = creator + bytes((0x12, 5, 0, 0)) + bytes(6) + b"\0"
    main = guard(bytes((4, 4, 65, 0)), bytes((0x13, 5, 4, 193))) + b"\0"
    if scenario == "forced":
        main = bytes((0x24, 5, 4, 0, 0))
    elif scenario == "permanent":
        main = b"\0"
    rdt = source(init, main, bytes(4))
    name = "PSX/STAGE1/ROOM1091.RDT"
    row = scan_cache_rdt(rdt, name, json.loads(profile_path.read_text()))
    original = next(s for s in profile.room_sources if s.source_rdt == name)
    updated = replace(
        original,
        **{
            section + "_" + field: row[section + "_" + field]
            for section in ("init", "main", "events")
            for field in ("offset", "size", "sha256")
        },
        dependencies=tuple(
            RoomDependency(int(d["address_ps1"], 0), d["width"], d["mask"])
            for d in row["dependencies"]
        ),
        item_global_ids=tuple(row["item_global_ids"]),
        cache_complete=row["cache_complete"],
        door_cache_complete=row["door_cache_complete"],
        mutable_fields=tuple(RoomMutableField(**f) for f in row["mutable_fields"]),
    )
    profile.room_sources = tuple(
        updated if s == original else s for s in profile.room_sources
    )
    program = RoomProgram.load(row["tracking_program"])
    profile.room_programs[name] = program
    # Keep synthetic scripts in room-data RAM, preserving executable identity.
    base = 0x80130000
    start = base - 0x80000000
    ram[start : start + len(rdt)] = rdt
    struct.pack_into("<I", ram, 0xCAB10, base)
    struct.pack_into(
        "<4I",
        ram,
        start + 0x60,
        *(base + row[s + "_offset"] for s in ("init", "main", "events")),
        base + row["events_offset"] + row["events_size"],
    )
    creator_offset = next(
        c.offset for p in program.procedures for c in p.commands if c.kind == "item"
    )
    ram[0xB8160 : 0xB8160 + 24 * 12] = bytes(24 * 12)
    struct.pack_into("<I", ram, 0xB7ED8, 0x800B819C)
    struct.pack_into("<BBHHHI", ram, 0xB819C, 0, 0, 0, 0, 0, base + creator_offset + 2)
    ram[0xB7DCC:0xB7DD0] = bytes(4)
    controls = struct.unpack_from("<I", ram, 0xC3000)[0]
    struct.pack_into("<I", ram, 0xC3000, controls & ~0xC00)
    return profile, ram


def test_overwritten_dormancy_activation_acquisition_and_reversal(dormant_room):
    profile, ram = dormant_room
    tracker = Tracker()
    room = RoomId(0, 9)
    for handler, remaining, completion in (
        (0, True, RoomCompletion.Incomplete),
        (4, True, RoomCompletion.Incomplete),
        (0, False, RoomCompletion.Cleared),
        (4, True, RoomCompletion.Incomplete),
        (0, True, RoomCompletion.Incomplete),
    ):
        ram[0xB819C] = handler
        ram[0xC86EA] = ram[0xC86EA] | 1 if remaining else ram[0xC86EA] & ~1
        result = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert result.status == PollStatus.Display, result.text
        assert tracker.room_state(room).completion == completion
        assert tracker.room_state(room).list_complete
        cached = profile.room_observations[room].observation
        if remaining:
            assert len(cached.items) == 1
        else:
            assert all(item.state.value == "taken" for item in cached.items)


def test_collection_proof_preserves_native_availability_uncertainty(dormant_room):
    profile, ram = dormant_room
    program = profile.room_programs["PSX/STAGE1/ROOM1091.RDT"]
    layout = profile.tracking_rule_layout
    snapshot = read_rule_snapshot(layout, (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), layout, snapshot, bytes(ram[0xC86DC:0xC86FC]), ()
    )
    assert not result.items.list_complete
    assert result.unresolved_item_slots == (5,)
    assert result.collection_items.list_complete
    assert result.unresolved_collection_slots == ()
    assert result.collection_items.items[0].state == RuntimeItemState.Uncollected


def test_disagreeing_sources_do_not_clear_a_missing_puzzle_item(dormant_room):
    profile, ram = dormant_room
    original = next(
        s for s in profile.room_sources if s.source_rdt == "PSX/STAGE1/ROOM1091.RDT"
    )
    alternative = replace(original, source_rdt="synthetic-alternative.RDT")
    # Model conflicting verified metadata directly at the validator boundary;
    # this alternative is not installed in RAM or accepted by the source matcher.
    document = json.loads(
        (REPO / "profiles/re1_directors_cut_slus00551.json").read_text()
    )
    row = scan_cache_rdt(
        source(pickup(5, 0x26, 13) + bytes((0x13, 5, 0, 0)) + b"\0", b"\0", bytes(4)),
        original.source_rdt,
        document,
    )
    profile.room_programs[alternative.source_rdt] = RoomProgram.load(
        row["tracking_program"]
    )
    programs = tuple(
        profile.room_programs[s.source_rdt] for s in (original, alternative)
    )
    snapshot = read_rule_snapshot(
        profile.tracking_rule_layout, programs, RamReader(ram).read_memory
    )
    result = validate_current_room(
        profile,
        RuntimeRoomItems(ok=True, list_complete=True),
        (original, alternative),
        snapshot,
        bytes(ram[0xC86DC:0xC86FC]),
    )
    assert not result.items.items
    assert not result.items.list_complete


@pytest.mark.parametrize("offset", (1, 2, 4, 6))
def test_changed_registry_cannot_hide_a_source_established_puzzle_item(
    dormant_room, offset
):
    profile, ram = dormant_room
    ram[0xB819C + offset] ^= 1
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Incomplete


@pytest.mark.parametrize("dormant_room", ["optional", "alternative"], indirect=True)
def test_possible_stale_creator_cannot_resolve_dormancy(dormant_room):
    profile, ram = dormant_room
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Unknown


@pytest.mark.parametrize("dormant_room", ["forced"], indirect=True)
def test_dormant_forced_award_remains_until_acquisition(dormant_room):
    profile, ram = dormant_room
    tracker = Tracker()
    for remaining, completion in (
        (True, RoomCompletion.Incomplete),
        (False, RoomCompletion.Cleared),
        (True, RoomCompletion.Incomplete),
    ):
        ram[0xC86EA] = ram[0xC86EA] | 1 if remaining else ram[0xC86EA] & ~1
        assert (
            poll_once(profile, tracker, RamReader(ram).read_memory).status
            == PollStatus.Display
        )
        assert tracker.room_state(RoomId(0, 9)).completion == completion


def test_pending_award_uses_descriptor_despite_overwritten_fields(dormant_room):
    profile, ram = dormant_room
    struct.pack_into("<I", ram, 0xB7DCC, 0x800B819C)
    controls = struct.unpack_from("<I", ram, 0xC3000)[0]
    struct.pack_into("<I", ram, 0xC3000, controls | 0x400)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Incomplete


def test_fresh_pickup_flag_resolves_after_an_inactive_registry_read(
    dormant_room,
):
    profile, ram = dormant_room

    class LoadingReader(RamReader):
        count = 0

        def read_memory(self, address, length):
            if (address, length) == (0x800C86DC, 32):
                self.count += 1
                if self.count == 3:
                    self.ram[0xC86EA] &= ~1
            return super().read_memory(address, length)

    tracker = Tracker()
    assert (
        poll_once(profile, tracker, LoadingReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Cleared


@pytest.mark.parametrize("drop_cache", [False, True])
def test_puzzle_item_survives_departure_cache_loss_and_rewind(
    dormant_room, tmp_path, drop_cache
):
    profile, before = dormant_room
    away = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    tracker = Tracker()
    puzzle = RoomId(0, 9)
    for ram, collected in (
        (before, False),
        (away, False),
        (away, True),
        (before, True),
        (before, False),
    ):
        ram[0xC86EA] = ram[0xC86EA] & ~1 if collected else ram[0xC86EA] | 1
        if drop_cache:
            # A restarted tracker must derive the same verdict without old AOT data.
            profile.room_observations.clear()
            profile.room_reentry_evaluations.clear()
        result = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert result.status == PollStatus.Display, result.text
        record = tracker.room_state(puzzle)
        assert record.list_complete
        assert record.completion == (
            RoomCompletion.Cleared if collected else RoomCompletion.Incomplete
        )
        if collected:
            assert all(item.state == "taken" for item in record.items)
        else:
            assert record.items[0].state == "uncollected"


def test_pinned_armor_room_uses_collection_before_and_after_puzzle(tmp_path):
    # The actual SLUS-00551 program exercises the reported case. These flag
    # changes are synthetic reversals, not a claim of new puzzle gameplay.
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    armor = RoomId(1, 5)
    tracker.mark_current(armor)
    tracker.region_visits["mansion2f:05"] = str(armor)
    for solved, collected in (
        (False, False),
        (True, False),
        (True, True),
        (False, False),
    ):
        ram[0xC8704] = ram[0xC8704] | 0x20 if solved else ram[0xC8704] & ~0x20
        ram[0xC86E3] = ram[0xC86E3] & ~8 if collected else ram[0xC86E3] | 8
        result = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert result.status == PollStatus.Display, result.text
        record = tracker.room_state(armor)
        assert record.list_complete
        assert record.completion == (
            RoomCompletion.Cleared if collected else RoomCompletion.Incomplete
        )
        assert [item.label for item in record.items] == ["Sun Crest"]
        expected_states = ("taken",) if collected else ("available", "uncollected")
        assert record.items[0].state in expected_states
        assert set(tracker.rooms) == {"00-09", "01-05"}
