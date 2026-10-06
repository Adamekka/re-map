"""Shared rule semantics across collectibles, doors, story flags and rewinds."""

import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from build_cache_metadata import scan_cache_rdt
from test_cache_metadata import indexed_event, pickup, source
from test_live_items import RamReader, fixture_ram
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import (
    RoomProgram,
    RuleCommand,
    RuleProcedure,
    TrackingRuleLayout,
    evaluate_room_program,
    read_rule_snapshot,
)
from tracker.exploration_state import RoomCompletion, Tracker


@pytest.fixture
def rules():
    bases = tuple(0x80001000 + group * 0x100 for group in range(10))
    layout = TrackingRuleLayout(
        bases,
        (0, 1, 2, 3, 7, 8),
        (),
        0x80000209,
        ((0x80000209, 255), (0x8000020A, 128), (0x8000020B, 2)),
        0x8000020A,
        128,
        0x8000020B,
        2,
        0x80000200,
        0x800010E0,
    )
    profile = {
        "cache_audits": [],
        "script_flag_bases": [hex(base) for base in bases],
        "cache_context_dependencies": [
            {"address_ps1": "0x80000209", "width": 1, "mask": "0xFF"}
        ],
    }
    return layout, profile


def compile_program(rules, code, main=b"\0", event=bytes(4)):
    row = scan_cache_rdt(source(code, main, event), "PSX/STAGE1/ROOM1091.RDT", rules[1])
    return RoomProgram.load(row["tracking_program"])


def branch(condition, yes, no):
    return (
        bytes((1, len(condition) + len(yes) + 2))
        + condition
        + yes
        + bytes((2, len(no) + 2))
        + no
    )


def guard(condition, body):
    return bytes((1, len(condition) + len(body) + 2)) + condition + body + bytes((3, 0))


def evaluate(program, rules, ram, flags=bytes([255]) * 32):
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    return evaluate_room_program(
        program,
        RoomId(0, 9),
        rules[0],
        snapshot,
        flags,
        ((0x44, "Green Herb"), (0x26, "Chemical")),
    )


def door(slot, target, key):
    raw = bytearray(26)
    raw[0], raw[1], raw[14], raw[15], raw[24], raw[25] = (
        0x0C,
        slot,
        0x85,
        target,
        key,
        1,
    )
    struct.pack_into("<hhHH", raw, 2, -100, 300, 500, 40)
    return bytes(raw)


def test_story_changes_select_items_and_door_definitions_and_reverse(rules):
    test = bytes((4, 1, 32, 0))
    yes = pickup(1, 0x44, 35) + door(2, 10, 0x33)
    no = pickup(1, 0x26, 63) + door(2, 8, 0x34)
    program = compile_program(rules, branch(test, yes, no) + b"\0")
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 32)
    for value, expected_type, target in ((0, 0x26, 8), (mask, 0x44, 10), (0, 0x26, 8)):
        ram[address - 0x80000000] = value
        result = evaluate(program, rules, ram)
        assert result.items.list_complete
        assert result.items.items[0].item_type == expected_type
        assert result.items.items[0].state == RuntimeItemState.Available
        assert result.doors[0][1][15] == target
        assert struct.unpack_from("<hhHH", result.doors[0][1], 2) == (
            -100,
            300,
            500,
            40,
        )


def test_absent_later_item_does_not_block_clear_and_returns_after_story_flag(rules):
    program = compile_program(
        rules, guard(bytes((4, 1, 63, 0)), pickup(1, 0x44, 111)) + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 63)
    tracker = Tracker()
    room = RoomId(0, 9)
    tracker.mark_current(room)
    for value, expected in (
        (0, RoomCompletion.Cleared),
        (mask, RoomCompletion.Incomplete),
        (0, RoomCompletion.Cleared),
    ):
        ram[address - 0x80000000] = value
        result = evaluate(program, rules, ram).items
        tracker.update_room_items(
            room,
            len(result.items),
            0,
            result.list_complete,
            bool(result.items),
            not result.list_complete,
        )
        assert tracker.room_state(room).completion == expected


def test_all_acquisition_word_boundaries_and_last_item_rewind(rules):
    gids = (0, 31, 32, 63, 111, 255)
    program = compile_program(
        rules,
        b"".join(pickup(slot, 0x44, gid) for slot, gid in enumerate(gids)) + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    flags = bytearray([255] * 32)
    for count in range(len(gids) + 1):
        result = evaluate(program, rules, ram, bytes(flags)).items
        assert result.list_complete
        assert (
            sum(item.state == RuntimeItemState.Taken for item in result.items) == count
        )
        if count < len(gids):
            gid = gids[count]
            flags[4 * (gid // 32) + 3 - (gid % 32) // 8] &= ~(128 >> (gid % 8))
    result = evaluate(program, rules, ram).items
    assert all(item.state == RuntimeItemState.Available for item in result.items)


def test_unknown_camera_or_local_bank_only_affects_guarded_slots(rules):
    # The active room's camera/local bank cannot stand in for a departed room.
    for condition in (bytes((6, 2, 0, 1)), bytes((4, 4, 1, 0))):
        program = compile_program(
            rules,
            pickup(0, 0x44, 1)
            + branch(condition, pickup(1, 0x44, 2), pickup(1, 0x26, 3))
            + b"\0",
        )
        result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
        assert not result.items.list_complete
        assert [item.aot_id for item in result.items.items] == [0]
        assert result.unresolved_item_slots == (1,)


def test_unknown_paths_with_identical_interactions_can_agree(rules):
    same = pickup(1, 0x44, 111)
    program = compile_program(rules, branch(bytes((6, 2, 0, 1)), same, same) + b"\0")
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert len(result.items.items) == 1


def test_dormant_award_and_map_are_distinct_from_absent_or_taken(rules):
    program = compile_program(
        rules,
        pickup(1, 0x44, 111) + bytes((0x13, 1, 3, 1)) + pickup(2, 0x4E, 32) + b"\0",
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024)).items
    assert result.list_complete
    assert result.items[0].state == RuntimeItemState.Unavailable
    assert result.items[1].kind.value == "map"
    flags = bytearray([255] * 32)
    flags[0xE] &= ~1
    assert (
        evaluate(program, rules, bytearray(2 * 1024 * 1024), bytes(flags))
        .items.items[0]
        .state
        == RuntimeItemState.Taken
    )


def test_flag_writes_have_local_semantics_without_changing_game_memory(rules):
    code = (
        bytes((5, 4, 31, 0)) + guard(bytes((4, 4, 31, 0)), pickup(1, 0x44, 111)) + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    assert len(evaluate(program, rules, ram).items.items) == 1
    assert not any(ram)


def test_procedure_end_and_else_failures_use_native_parent_stack(rules):
    inner = branch(bytes((4, 1, 0, 0)), b"\0", bytes((6, 2, 0, 0)))
    code = (
        guard(bytes((4, 1, 1, 0)), inner + pickup(1, 0x44, 111))
        + pickup(2, 0x26, 63)
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 1)
    ram[address - 0x80000000] = mask
    result = evaluate(program, rules, ram)
    assert [item.aot_id for item in result.items.items] == [2]
    assert result.unresolved_item_slots == (1,)
    address, mask = rules[0].flag(1, 0)
    ram[address - 0x80000000] |= mask
    result = evaluate(program, rules, ram)
    assert result.items.items == ()
    assert result.items.list_complete


def test_dynamic_event_writers_and_quantity_changes_only_block_affected_slots(rules):
    program = compile_program(
        rules,
        pickup(1, 0x44, 111) + pickup(2, 0x26, 63) + b"\0",
        event=indexed_event(bytes((7, 6, 0x13, 1, 0, 1, 0xFF))),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert [item.aot_id for item in result.items.items] == [2]
    assert result.unresolved_item_slots == (1,)
    program = compile_program(
        rules,
        pickup(1, 0x44, 111) + pickup(2, 0x26, 63) + b"\0",
        main=bytes((0x4C, 1, 2, 0, 0)),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert [item.aot_id for item in result.items.items] == [1]
    assert result.unresolved_item_slots == (2,)


def test_rule_read_failure_is_explicit(rules):
    program = compile_program(
        rules, guard(bytes((4, 1, 31, 0)), pickup(1, 0x44, 111)) + b"\0"
    )
    reader = RamReader(bytearray(2 * 1024 * 1024))
    reader.fail_address = rules[0].flag(1, 31)[0]
    result = read_rule_snapshot(rules[0], (program,), reader.read_memory)
    assert "injected read failure" in result.error
    assert result.values == ()


@pytest.mark.parametrize("kind", ["green_herb", "chemical"])
def test_generated_program_matches_real_donated_pickup_states(tmp_path, kind):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    for phase in ("before", "after"):
        ram = fixture_ram(f"slus00551_{kind}_{phase}.sav", tmp_path)
        tracker = Tracker()
        assert (
            poll_once(profile, tracker, RamReader(ram).read_memory).status
            == PollStatus.Display
        )
        room = tracker.current
        cached = profile.room_observations[room]
        for script in cached.sources:
            program = profile.room_programs[script.source_rdt]
            snapshot = read_rule_snapshot(
                profile.tracking_rule_layout, (program,), RamReader(ram).read_memory
            )
            result = evaluate_room_program(
                program,
                room,
                profile.tracking_rule_layout,
                snapshot,
                bytes(ram[0xC86DC:0xC86FC]),
                profile.runtime_room_layout.item_labels,
            )
            assert result.items.list_complete
            actual = cached.observation.items
            assert [
                (item.item_type, item.global_id, item.state)
                for item in result.items.items
            ] == [(item.item_type, item.global_id, item.state) for item in actual]


def test_same_room_save_load_during_poll_publishes_nothing(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()

    class LoadingReader(RamReader):
        flag_reads = 0

        def read_memory(self, address, length):
            if address == 0x800C86DC and length == 32:
                self.flag_reads += 1
                if self.flag_reads == 4:
                    self.ram[0xC86EA] ^= 1
            return super().read_memory(address, length)

    result = poll_once(profile, tracker, LoadingReader(ram).read_memory)
    assert result.status == PollStatus.Retry
    assert tracker.rooms == {}
    assert profile.room_observations == {}


def test_event_source_identity_validates_relocation_and_every_other_byte(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    source_row = next(
        row for row in profile.room_sources if row.source_rdt.endswith("1091.RDT")
    )
    base = int.from_bytes(ram[0xCAB10:0xCAB14], "little") - 0x80000000
    field = next(
        field for field in source_row.mutable_fields if field.kind == "event-pointer"
    )
    for offset in (
        source_row.events_offset + field.offset,
        source_row.events_offset + source_row.events_size - 1,
    ):
        corrupt = bytearray(ram)
        corrupt[base + offset] ^= 1
        tracker = Tracker()
        assert (
            poll_once(profile, tracker, RamReader(corrupt).read_memory).status
            == PollStatus.Retry
        )
        assert tracker.rooms == {}


@pytest.mark.parametrize("invalid", ["branch", "operand", "kind", "slot"])
def test_rule_construction_rejects_invalid_metadata(invalid):
    with pytest.raises(ValueError, match="tracking"):
        if invalid == "branch":
            RuleProcedure(
                0x100,
                0x104,
                (
                    RuleCommand(0x100, 0x102, "if", (0x103,)),
                    RuleCommand(0x102, 0x103, "end", ()),
                ),
            )
        elif invalid == "operand":
            RuleCommand(0x100, 0x104, "flag-test", (1, 256, 0))
        elif invalid == "slot":
            RuleCommand(0x100, 0x11A, "item", (24, 0x44, 1, 111, 1))
        else:
            RuleCommand(0x100, 0x102, "pretend-success", ())


def test_partial_current_registry_cannot_look_cleared(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB81A4:0xB81A8] = bytes(4)
    ram[0xB819C] = 0
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    record = tracker.room_state(RoomId(0, 9))
    assert record.completion == RoomCompletion.Unknown
    assert record.reason == "Room items are still updating."


def test_source_choices_cover_all_rows_and_the_fixed_variant_exception():
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    assert len(profile.room_sources) == 334
    assert len(profile.room_source_choices) == 636
    for alternate in (0, 1):
        assert profile.room_source_choices[RoomId(0, 6), 0, alternate].endswith(
            "1060.RDT"
        )
        assert profile.room_source_choices[RoomId(0, 6), 1, alternate].endswith(
            "1061.RDT"
        )
        for variant in (0, 1):
            assert profile.room_source_choices[
                RoomId(0, 0x12), variant, alternate
            ].endswith("8120.RDT" if alternate else "1120.RDT")
    assert profile.room_source_choices[RoomId(0, 0x18), 1, 0].endswith("1180.RDT")
    assert profile.room_source_choices[RoomId(0, 0x18), 1, 1].endswith("1180.RDT")


def test_transient_bank_equality_cannot_authorize_observed_item_reuse(tmp_path, rules):
    from dataclasses import replace

    from games.re1.room_cache import RoomDependency
    from games.re1.tracking_engine import refresh_visited_room

    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    script = replace(
        cached.sources[0], dependencies=(RoomDependency(0x800C300B, 1, 128),)
    )
    cached = replace(cached, sources=(script,), context=(0,))
    program = compile_program(
        rules, guard(bytes((4, 4, 0, 0)), pickup(5, 0x44, 111)) + b"\0"
    )
    profile.room_programs[script.source_rdt] = program
    snapshot = read_rule_snapshot(
        profile.tracking_rule_layout, (program,), RamReader(ram).read_memory
    )
    result = refresh_visited_room(
        profile, cached, (0,), snapshot, bytes(ram[0xC86DC:0xC86FC])
    )
    assert not result.items.list_complete
    assert result.items.items == ()


def test_dormant_scripted_awards_resolve_from_acquisition_and_rewind(rules):
    program = compile_program(
        rules,
        pickup(1, 0x44, 111) + bytes((0x13, 1, 3, 1, 0)),
        main=bytes((0x24, 1, 4, 0, 0)),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete
    assert result.unresolved_item_slots == (1,)
    flags = bytearray([255] * 32)
    flags[14] &= ~1
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), bytes(flags))
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Taken
    assert not evaluate(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


@pytest.mark.parametrize("change", ["room", "registry", "source"])
def test_late_room_changes_cannot_publish_stale_observations(tmp_path, change):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)

    class LateReader(RamReader):
        room_reads = 0
        registry_reads = 0
        source_reads = 0

        def read_memory(self, address, length):
            if address == 0x800C8661:
                self.room_reads += 1
                if change == "room" and self.room_reads == 3:
                    self.ram[0xC8661] = 8
            if address == 0x800B8160:
                self.registry_reads += 1
                if change == "registry" and self.registry_reads == 3:
                    self.ram[0xB8160] = 0
            if address == 0x800CAB10:
                self.source_reads += 1
                if change == "source" and self.source_reads == 5:
                    self.ram[0xCAB11] ^= 1
            return super().read_memory(address, length)

    tracker = Tracker()
    assert (
        poll_once(profile, tracker, LateReader(ram).read_memory).status
        == PollStatus.Retry
    )
    assert tracker.rooms == {}
    assert profile.room_observations == {}


def test_unsupported_predicate_keeps_both_failure_and_continuation(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 1) + bytes((7, 0, 1, 0, 0, 0)) + pickup(1, 0x26, 63) + b"\0",
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert [item.aot_id for item in result.items.items] == [0]
    assert result.unresolved_item_slots == (1,)
    assert not result.items.list_complete


def test_live_registry_resolves_present_uncertain_items_and_explains_missing_ones(
    tmp_path, rules
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    name = next(
        source.source_rdt
        for source in profile.room_sources
        if source.source_rdt.endswith("1091.RDT")
    )
    profile.room_programs[name] = compile_program(
        rules, guard(bytes((6, 2, 0, 1)), pickup(5, 0x44, 111)) + b"\0"
    )
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert tracker.room_state(RoomId(0, 9)).list_complete
    ram[0xB819C] = 0
    ram[0xB81A4:0xB81A8] = bytes(4)
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert (
        tracker.room_state(RoomId(0, 9)).reason
        == "Room item conditions are unresolved."
    )


@pytest.mark.parametrize("handler", (8, 13, 16))
def test_live_noncollectible_slots_resolve_uncertainty_and_rewind(
    tmp_path, rules, handler
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    name = next(
        source.source_rdt
        for source in profile.room_sources
        if source.source_rdt.endswith("1091.RDT")
    )
    profile.room_programs[name] = compile_program(
        rules, guard(bytes((6, 2, 0, 1)), pickup(5, 0x44, 111)) + b"\0"
    )
    tracker = Tracker()
    for live_handler, pending, completion in (
        (4, False, RoomCompletion.Incomplete),
        (handler, False, RoomCompletion.Cleared),
        (handler, True, RoomCompletion.Incomplete),
        (handler, False, RoomCompletion.Cleared),
        (4, False, RoomCompletion.Incomplete),
    ):
        ram[0xB819C] = live_handler
        struct.pack_into("<I", ram, 0xB7DCC, 0x800B819C)
        flags = struct.unpack_from("<I", ram, 0xC3000)[0] & ~0xC00
        struct.pack_into("<I", ram, 0xC3000, flags | (0x400 if pending else 0))
        assert (
            poll_once(profile, tracker, RamReader(ram).read_memory).status
            == PollStatus.Display
        )
        record = tracker.room_state(RoomId(0, 9))
        assert record.list_complete and record.completion == completion
        assert {room for room in tracker.rooms} == {"00-09"}


def test_noncollectible_evidence_does_not_bypass_expected_pickup_or_source_coverage(
    tmp_path,
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 16
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    record = tracker.room_state(RoomId(0, 9))
    assert not record.list_complete and record.completion == RoomCompletion.Unknown
    assert record.reason == "Room items are still updating."
    # A taken acquisition bit removes the expected available pickup. Incomplete
    # script coverage must still block clearance even with live typewriter proof.
    ram[0xC86EA] &= ~1
    name = profile.room_observations[RoomId(0, 9)].sources[0].source_rdt
    profile.room_programs[name] = replace(
        profile.room_programs[name], coverage_complete=False
    )
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    record = tracker.room_state(RoomId(0, 9))
    assert not record.list_complete and record.completion == RoomCompletion.Unknown
    assert record.reason == "Room item conditions are unresolved."


@pytest.mark.parametrize("award_slot", (5, 6))
def test_noncollectible_slot_does_not_resolve_dormant_awards(
    tmp_path, rules, award_slot
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 16
    name = next(
        source.source_rdt
        for source in profile.room_sources
        if source.source_rdt.endswith("1091.RDT")
    )
    program = compile_program(
        rules,
        guard(bytes((6, 2, 0, 1)), pickup(5, 0x44, 111))
        + (pickup(6, 0x26, 13) if award_slot == 6 else b"")
        + bytes((0x13, award_slot, 3, 0, 0)),
        main=bytes((0x24, award_slot, 4, 0, 0)),
    )
    profile.room_programs[name] = program
    snapshot = read_rule_snapshot(
        profile.tracking_rule_layout, (program,), RamReader(ram).read_memory
    )
    expected = evaluate_room_program(
        program,
        RoomId(0, 9),
        profile.tracking_rule_layout,
        snapshot,
        bytes(ram[0xC86DC:0xC86FC]),
        profile.runtime_room_layout.item_labels,
    )
    assert award_slot in expected.unresolved_item_slots
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert not tracker.room_state(RoomId(0, 9)).list_complete
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Unknown


@pytest.mark.parametrize(
    "change", ("pending-start", "pending-target", "unrelated-control")
)
def test_late_pending_state_changes_cannot_publish_noncollectible_coverage(
    tmp_path, rules, change
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 16
    struct.pack_into("<I", ram, 0xB7DCC, 0x800B819C)
    flags = struct.unpack_from("<I", ram, 0xC3000)[0] & ~0xC00
    struct.pack_into(
        "<I", ram, 0xC3000, flags | (0x400 if change == "pending-target" else 0)
    )
    name = next(
        source.source_rdt
        for source in profile.room_sources
        if source.source_rdt.endswith("1091.RDT")
    )
    profile.room_programs[name] = compile_program(
        rules, guard(bytes((6, 2, 0, 1)), pickup(5, 0x44, 111)) + b"\0"
    )

    class LateReader(RamReader):
        registry_reads = 0

        def read_memory(self, address, length):
            if address == 0x800B8160:
                self.registry_reads += 1
                if self.registry_reads == 3:
                    # Change state after the observer's own coherent recheck.
                    if change == "pending-target":
                        struct.pack_into("<I", self.ram, 0xB7DCC, 0x800B8190)
                    else:
                        value = struct.unpack_from("<I", self.ram, 0xC3000)[0]
                        struct.pack_into(
                            "<I",
                            self.ram,
                            0xC3000,
                            value ^ (1 if change == "unrelated-control" else 0x400),
                        )
            return super().read_memory(address, length)

    tracker = Tracker()
    result = poll_once(profile, tracker, LateReader(ram).read_memory)
    if change == "unrelated-control":
        assert result.status == PollStatus.Display
        assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Cleared
    else:
        assert result.status == PollStatus.Retry
        assert tracker.rooms == {} and profile.room_observations == {}


def test_past_room_reconstruction_cannot_reuse_live_noncollectible_evidence(
    tmp_path, rules
):
    from games.re1.tracking_engine import refresh_visited_room

    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 16
    name = next(
        source.source_rdt
        for source in profile.room_sources
        if source.source_rdt.endswith("1091.RDT")
    )
    program = compile_program(
        rules, guard(bytes((6, 2, 0, 1)), pickup(5, 0x44, 111)) + b"\0"
    )
    profile.room_programs[name] = program
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    assert cached.observation.list_complete
    assert cached.observation.non_collectible_slots == (5,)
    # This source is deliberately ineligible for cached-item reuse; only its
    # historical rules can now supply a verdict for a room no longer current.
    cached = replace(
        cached, sources=(replace(cached.sources[0], cache_complete=False),)
    )
    snapshot = read_rule_snapshot(
        profile.tracking_rule_layout, (program,), RamReader(ram).read_memory
    )
    result = refresh_visited_room(
        profile, cached, cached.context, snapshot, bytes(ram[0xC86DC:0xC86FC])
    )
    assert not result.items.list_complete
    assert result.items.items == () and result.items.non_collectible_slots == ()


@pytest.mark.parametrize("limit", ["stack", "paths"])
def test_analysis_budgets_report_unresolved_without_guessing_clear(rules, limit):
    if limit == "stack":
        code = pickup(1, 0x44, 111)
        for _ in range(17):
            # Constant room comparison admits every nested IF in this cached room.
            code = guard(bytes((6, 1, 0, 9)), code)
    else:
        code = b"".join(
            branch(bytes((6, 2, 0, 1)), bytes((5, 4, bit, 0)), bytes((5, 4, bit, 1)))
            for bit in range(13)
        ) + pickup(1, 0x44, 111)
    program = compile_program(rules, code + b"\0")
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete
    assert result.unresolved_item_slots == (1,)


def test_builder_rejects_unbounded_slots_before_emitting_a_profile(rules):
    with pytest.raises(ValueError, match="tracking.*slot"):
        compile_program(rules, pickup(24, 0x44, 111) + b"\0")


def test_changed_door_handlers_are_explicitly_unresolved(rules):
    program = compile_program(rules, door(2, 8, 0x34) + bytes((0x13, 2, 2, 1, 0)))
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.doors == ()
    assert result.unresolved_door_slots == (2,)


def test_unresolved_door_coverage_reaches_the_map_without_changing_item_clearance(
    tmp_path,
):
    from dataclasses import replace

    from ui.map_view import map_state

    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    for name, program in tuple(profile.room_programs.items()):
        if name.endswith("1091.RDT"):
            profile.room_programs[name] = replace(
                program,
                mutable_slots=tuple(
                    sorted(set(program.mutable_slots) | set(program.door_slots))
                ),
            )
    cached = profile.room_observations[RoomId(0, 9)]
    profile.room_observations[RoomId(0, 9)] = replace(
        cached,
        sources=tuple(
            replace(source, door_cache_complete=False) for source in cached.sources
        ),
    )
    assert (
        poll_once(profile, tracker, RamReader(chemical).read_memory).status
        == PollStatus.Display
    )
    record = tracker.room_state(RoomId(0, 9))
    assert record.completion == RoomCompletion.Cleared
    assert not record.doors_complete
    assert record.door_reason == "Door access needs another visit."
    row = next(row for row in map_state(tracker)["rooms"] if row["id"] == "09")
    assert not row["doors_complete"] and row["door_reason"] == record.door_reason


def test_overlapping_flag_banks_share_written_physical_bits(rules):
    from dataclasses import replace

    bases = list(rules[0].flag_bases)
    bases[8] = bases[0] + 16
    layout = replace(rules[0], flag_bases=tuple(bases))
    program = compile_program(
        rules,
        bytes((5, 0, 128, 0))
        + guard(bytes((4, 8, 0, 0)), pickup(1, 0x44, 111))
        + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(layout, (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program,
        RoomId(0, 9),
        layout,
        snapshot,
        bytes([255]) * 32,
        ((0x44, "Green Herb"),),
    )
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Available
    assert not any(ram)
