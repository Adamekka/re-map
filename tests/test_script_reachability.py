"""Synthetic reachability checks; natural runtime limits are RE1-REENTRY-005."""

import struct
import sys
from dataclasses import asdict, replace
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest
from scan_events import scan_event_program
from test_event_activation import indexed, setup
from test_event_conditions import block
from test_live_items import RamReader
from test_room_reentry import interaction, reenter
from test_tracking_rules import compile_program, guard

from games.re1.event_state import EventFailure, EventProgram
from games.re1.room_cache import CachedRoomObservation
from games.re1.room_items import RuntimeRoomItems
from games.re1.tracking_engine import refresh_visited_room, validate_current_room
from games.re1.tracking_rules import RoomProgram, RoomRuleEpoch, read_rule_snapshot

pytest_plugins = ("test_tracking_rules",)


@pytest.mark.parametrize(
    "bad",
    [
        bytes((1, 7, 0xFF)),
        bytes((0xFD, 0xFF)),
        bytes((0xFB, 0xFF)),
        bytes((0xFC, 255, 0)),
        bytes((5, 0, 255, 0, 0xFF)),
        bytes((8, 255)),
        bytes((0xFA, 0, 1, 0)) * 5 + b"\xff",
        bytes((6, 3, 255, 255)),
    ],
)
def test_event_failures_keep_ownership_without_discarding_clean_entries(bad):
    data = bytes(0x20) + indexed(b"\xff", bad)
    scan = scan_event_program(data, 0x20, len(data))
    assert scan.table_complete and scan.status != "clean"
    assert {failure.entry for failure in scan.failures} == {1}
    assert any(point.entry == 0 and point.phase == "ending" for point in scan.points)


def test_aliases_retain_each_failed_owner():
    data = bytes(0x20) + struct.pack("<III", 12, 12, 0) + bytes((1, 7, 0xFF))
    scan = scan_event_program(data, 0x20, len(data))
    assert {failure.entry for failure in scan.failures} == {0, 1}


def test_exhausted_decoder_budget_cannot_drop_unprocessed_entry_failures():
    data = bytes(0x20) + indexed(b"\xff", bytes(16384) + b"\xff")
    scan = scan_event_program(data, 0x20, len(data))
    assert scan.table_complete
    assert {failure.entry for failure in scan.failures} == {0, 1}


@pytest.mark.parametrize("started", [False, True])
@pytest.mark.parametrize("has_slots", [False, True])
def test_unused_failure_can_be_excluded_but_started_failure_blocks_empty_rooms(
    rules, started, has_slots
):
    init = interaction() if has_slots else b""
    init += bytes((0x14, 0, 0, 1)) if started else b""
    program = compile_program(
        rules, init + b"\0", event=indexed(b"\xff", bytes((1, 7, 0xFF)))
    )
    assert not program.coverage_complete and program.reentry_coverage_complete
    result = reenter(program, rules, bytearray(2 * 1024 * 1024))
    assert result.coverage_complete != started
    assert result.items.list_complete != started
    current = reenter(program, rules, bytearray(2 * 1024 * 1024), RoomRuleEpoch.Current)
    assert not current.coverage_complete and not current.items.list_complete


@pytest.mark.parametrize("native", [bytes((5, 0, 1, 0)), bytes((8, 1))])
def test_child_start_and_restart_reach_the_failed_target(rules, native):
    program = compile_program(
        rules,
        bytes((0x14, 0, 0, 0, 0)),
        event=indexed(native + b"\xff", bytes((1, 7, 0xFF))),
    )
    result = reenter(program, rules, bytearray(2 * 1024 * 1024))
    assert not result.coverage_complete and not result.items.list_complete


@pytest.mark.parametrize("handler,forced", [(9, False), (16, True)])
def test_registered_and_forced_callbacks_reach_failed_events(rules, handler, forced):
    init = interaction(handler, 1)
    init += bytes((0x24, 5, 9, 0)) if forced else b""
    program = compile_program(
        rules, init + b"\0", event=indexed(b"\xff", bytes((1, 7, 0xFF)))
    )
    assert not reenter(program, rules, bytearray(2 * 1024 * 1024)).coverage_complete


def test_story_changes_reversal_and_unknown_local_conditions_recheck_failures(rules):
    main = guard(bytes((4, 1, 7, 0)), bytes((0x14, 0, 0, 0))) + b"\0"
    program = compile_program(rules, b"\0", main, indexed(bytes((1, 7, 0xFF))))
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 7)
    for value, complete in ((0, True), (mask, False), (0, True)):
        ram[address - 0x80000000] = value
        assert reenter(program, rules, ram).coverage_complete == complete
    main = guard(bytes((4, 4, 64, 0)), bytes((0x14, 0, 0, 0))) + b"\0"
    program = compile_program(rules, b"\0", main, indexed(bytes((1, 7, 0xFF))))
    assert not reenter(program, rules, ram).coverage_complete


def test_flag_only_dispatch_can_make_a_failed_event_reachable_on_a_later_tick(rules):
    event = indexed(
        bytes((7, 6, 5, 4, 9, 0, 0xFF)),
        bytes((1, 7, 0xFF)),
    )
    main = guard(bytes((4, 4, 9, 0)), bytes((0x14, 0, 0, 1))) + b"\0"
    program = compile_program(rules, bytes((0x14, 0, 0, 0, 0)), main, event)
    assert not reenter(program, rules, bytearray(2 * 1024 * 1024)).coverage_complete


@pytest.mark.parametrize("local_index", [9, 64])
def test_invalid_scd_target_obeys_its_guard_without_hiding_reachable_failure(
    rules, local_index
):
    code = guard(bytes((4, 4, local_index, 0)), bytes((0x14, 0, 0, 255))) + b"\0"
    program = compile_program(rules, code)
    assert not program.coverage_complete and program.reentry_coverage_complete
    assert reenter(program, rules, bytearray(2 * 1024 * 1024)).coverage_complete == (
        local_index == 9
    )


@pytest.mark.parametrize("started", [False, True])
@pytest.mark.parametrize("handler", [4, 15])
def test_award_without_creator_blocks_only_a_reachable_path(rules, started, handler):
    event = indexed(bytes((7, 6, 0x24, 5, handler, 0, 0xFF)))
    init = bytes((0x14, 0, 0, 0)) if started else b""
    program = compile_program(rules, init + b"\0", event=event)
    assert program.item_slots == (5,) and not program.coverage_complete
    result = reenter(program, rules, bytearray(2 * 1024 * 1024))
    assert result.coverage_complete != started and result.items.list_complete != started


def test_invalid_scd_start_inside_a_dispatch_retains_its_own_guard(rules):
    body = guard(bytes((4, 4, 9, 0)), bytes((0x14, 0, 0, 255))) + b"\0"
    program = compile_program(
        rules, bytes((0x14, 0, 0, 0, 0)), event=indexed(block(body) + b"\xff")
    )
    assert not program.event_program.failures
    assert reenter(program, rules, bytearray(2 * 1024 * 1024)).coverage_complete


@pytest.mark.parametrize("handler", [3, 4, 15])
def test_generic_pickup_source_uncertainty_is_kept_on_its_reachable_slot(
    rules, handler
):
    code = guard(bytes((4, 1, 7, 0)), interaction(handler)) + b"\0"
    program = compile_program(rules, code)
    assert program.item_slots == (5,) and not program.coverage_complete
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 7)
    for value, complete in ((0, True), (mask, False), (0, True)):
        ram[address - 0x80000000] = value
        result = reenter(program, rules, ram)
        assert result.items.list_complete == complete


@pytest.mark.parametrize(
    "event", [bytes((4, 0, 0, 0)), bytes((255, 0, 0, 0, 0, 0, 0, 0))]
)
def test_malformed_tables_remain_global_failures_even_without_starts(rules, event):
    program = compile_program(rules, b"\0", event=event)
    assert not program.coverage_complete and not program.reentry_coverage_complete
    assert not reenter(program, rules, bytearray(2 * 1024 * 1024)).coverage_complete


def test_failure_and_reentry_metadata_are_required_and_validated(rules):
    program = compile_program(rules, b"\0", event=indexed(bytes((1, 7, 0xFF))))
    raw = asdict(program)
    del raw["reentry_coverage_complete"]
    with pytest.raises(KeyError):
        RoomProgram.load(raw)
    raw = asdict(program.event_program)
    del raw["failures"]
    with pytest.raises(KeyError):
        EventProgram.load(raw)
    with pytest.raises(ValueError, match="ownership"):
        replace(program.event_program, failures=(EventFailure(255, 10, "unknown"),))
    with pytest.raises(ValueError, match="complete event decoding"):
        replace(program, coverage_complete=True)


def test_required_guard_read_failure_cannot_supply_a_reachability_proof(rules):
    program = compile_program(
        rules,
        guard(bytes((4, 1, 7, 0)), bytes((0x14, 0, 0, 0))) + b"\0",
        event=indexed(bytes((1, 7, 0xFF))),
    )
    reader = RamReader(bytearray(2 * 1024 * 1024))
    reader.fail_address = rules[0].flag(1, 7)[0]
    assert read_rule_snapshot(rules[0], (program,), reader.read_memory).error


def test_empty_room_door_coverage_and_cached_proof_reverse_with_story_state(rules):
    init = guard(bytes((4, 1, 7, 0)), bytes((0x14, 0, 0, 0))) + b"\0"
    ram, script, program = setup(rules, init, indexed(bytes((1, 7, 0xFF))))
    profile = SimpleNamespace(
        tracking_rule_layout=rules[0],
        runtime_room_layout=SimpleNamespace(item_labels=()),
        room_programs={script.source_rdt: program},
        room_reentry_evaluations={},
        room_source_choices={(script.room, 0, 0): script.source_rdt},
        room_sources=(script,),
    )
    cached = CachedRoomObservation(
        RuntimeRoomItems(ok=True), (script,), (), (), (0, 0, 0), False
    )
    address, mask = rules[0].flag(1, 7)
    for value, complete in ((0, True), (mask, False), (0, True)):
        ram[address - 0x80000000] = value
        snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
        result = refresh_visited_room(profile, cached, (), snapshot, bytes([255]) * 32)
        assert (
            result.items.list_complete == complete and result.doors_complete == complete
        )
        assert not result.items.items and not result.doors
        # A complete live registry cannot prove that undecoded historical
        # scripts never ran. Current coverage keeps its existing barrier.
        current = validate_current_room(
            profile,
            RuntimeRoomItems(ok=True, list_complete=True),
            (script,),
            snapshot,
            bytes([255]) * 32,
        )
        assert not current.items.list_complete and not current.doors_complete
