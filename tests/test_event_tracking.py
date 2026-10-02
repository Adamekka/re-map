"""Shared post-init rules. Flag/registry replacements here are synthetic."""

from dataclasses import replace

import pytest
from test_cache_metadata import indexed_event, pickup
from test_live_items import RamReader, fixture_ram
from test_tracking_rules import (
    REPO,
    branch,
    compile_program,
    door,
    evaluate,
    guard,
)
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import read_rule_snapshot
from tracker.exploration_state import RoomCompletion, Tracker
from ui.map_view import map_state

pytest_plugins = ("test_tracking_rules",)


def test_main_flags_refresh_multiple_items_and_door_definitions_and_reverse(rules):
    init = pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + door(2, 8, 0x34) + b"\0"
    main = (
        branch(
            bytes((4, 1, 31, 0)),
            bytes((0x13, 0, 4, 1, 0x13, 1, 0, 1)) + door(2, 10, 0x35),
            bytes((0x13, 0, 0, 1, 0x13, 1, 4, 1)) + door(2, 8, 0x34),
        )
        + b"\0"
    )
    program = compile_program(rules, init, main)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 31)
    for value, states, target in (
        (0, (RuntimeItemState.Unavailable, RuntimeItemState.Available), 8),
        (mask, (RuntimeItemState.Available, RuntimeItemState.Unavailable), 10),
        (0, (RuntimeItemState.Unavailable, RuntimeItemState.Available), 8),
    ):
        ram[address - 0x80000000] = value
        result = evaluate(program, rules, ram)
        assert result.items.list_complete
        assert tuple(item.state for item in result.items.items) == states
        assert result.doors[0][1][15] == target
        assert not result.unresolved_door_slots


def test_main_tests_use_fresh_flags_after_initialization(rules):
    init = bytes((5, 1, 0, 2)) + pickup(0, 0x44, 111) + b"\0"
    main = (
        branch(bytes((4, 1, 0, 0)), bytes((0x13, 0, 4, 1)), bytes((0x13, 0, 0, 1)))
        + b"\0"
    )
    program = compile_program(rules, init, main)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 0)
    ram[address - 0x80000000] = mask
    assert (
        evaluate(program, rules, ram).items.items[0].state == RuntimeItemState.Available
    )
    assert ram[address - 0x80000000] == mask


def test_unavailable_main_door_is_explicit_and_can_reopen(rules):
    main = (
        branch(bytes((4, 1, 32, 0)), bytes((0x13, 2, 0, 0)), bytes((0x13, 2, 1, 1)))
        + b"\0"
    )
    program = compile_program(rules, door(2, 8, 0x34) + b"\0", main)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 32)
    for value, disabled in ((mask, True), (0, False), (mask, True)):
        ram[address - 0x80000000] = value
        result = evaluate(program, rules, ram)
        assert bool(result.disabled_doors) == disabled
        assert bool(result.doors) != disabled
        assert not result.unresolved_door_slots


def test_current_room_temporary_flags_cannot_resolve_past_main_updates(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        guard(bytes((4, 4, 0, 0)), bytes((0x13, 0, 0, 1))) + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    assert not evaluate(program, rules, ram).items.list_complete


def test_a_false_one_way_main_guard_does_not_erase_an_earlier_update(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        guard(bytes((4, 1, 0, 0)), bytes((0x13, 0, 0, 1))) + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    assert evaluate(program, rules, ram).unresolved_item_slots == (0,)
    address, mask = rules[0].flag(1, 0)
    ram[address - 0x80000000] = mask
    result = evaluate(program, rules, ram)
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Unavailable


def test_optional_event_disable_resolves_taken_item_and_rewinds(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + b"\0",
        event=indexed_event(bytes((7, 6, 0x13, 0, 0, 1, 0xFF))),
    )
    ram = bytearray(2 * 1024 * 1024)
    before = evaluate(program, rules, ram)
    assert before.unresolved_item_slots == (0,)
    assert [item.aot_id for item in before.items.items] == [1]
    flags = bytearray([255] * 32)
    flags[14] &= ~1
    after = evaluate(program, rules, ram, bytes(flags))
    assert after.items.list_complete
    assert after.items.items[0].state == RuntimeItemState.Taken
    assert evaluate(program, rules, ram).unresolved_item_slots == (0,)


def test_event_mode_only_update_preserves_known_item_availability(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(bytes((7, 6, 0x13, 0, 4, 0x81, 0xFF))),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Available


def test_event_handler_with_wrong_descriptor_kind_remains_unresolved(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(bytes((7, 6, 0x13, 0, 15, 0x81, 0xFF))),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (0,)
    assert not result.items.list_complete


def test_event_order_and_repetition_do_not_select_a_last_descriptor(rules):
    replacement = pickup(0, 0x26, 63)
    event = indexed_event(
        bytes((7, len(replacement) + 2))
        + replacement
        + bytes((7, 6, 0x13, 0, 0, 1, 0xFF))
    )
    program = compile_program(rules, pickup(0, 0x44, 111) + b"\0", event=event)
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (0,)
    assert result.items.items == ()
    assert not result.items.list_complete


def test_event_effect_budget_preserves_independent_slots(rules):
    from games.re1.tracking_rules import RuleCommand

    program = compile_program(rules, pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + b"\0")
    effects = tuple(
        RuleCommand(
            0x1000 + index * 26,
            0x1000 + (index + 1) * 26,
            "item",
            (0, 0x44 + index // 256, index % 256, 111, 1),
        )
        for index in range(300)
    )
    result = evaluate(
        replace(program, event_effects=effects), rules, bytearray(2 * 1024 * 1024)
    )
    assert result.unresolved_item_slots == (0,)
    assert [item.aot_id for item in result.items.items] == [1]


@pytest.mark.parametrize("handler", [4, 15])
def test_forced_awards_use_persistent_flags_without_inventing_completion(
    rules, handler
):
    item_type = 0x44 if handler == 4 else 0x4E
    program = compile_program(
        rules,
        pickup(0, item_type, 111) + b"\0",
        event=indexed_event(bytes((7, 6, 0x24, 0, handler, 0, 0xFF))),
    )
    ram = bytearray(2 * 1024 * 1024)
    before = evaluate(program, rules, ram)
    assert before.items.list_complete
    assert before.items.items[0].state == RuntimeItemState.Available
    flags = bytearray([255] * 32)
    flags[14] &= ~1
    assert (
        evaluate(program, rules, ram, bytes(flags)).items.items[0].state
        == RuntimeItemState.Taken
    )
    assert (
        evaluate(program, rules, ram).items.items[0].state == RuntimeItemState.Available
    )


def test_forced_door_preserves_coverage_while_dynamic_quantity_remains_unresolved(
    rules,
):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0",
        bytes((0x4C, 1, 0, 0, 0x24, 1, 1, 0, 0)),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (0,)
    assert result.unresolved_door_slots == ()
    assert result.doors == ((1, door(1, 8, 0x34)),)


def test_got_item_zero_result_takes_the_native_if_failure_path(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        guard(bytes((0x2D, 0, 4, 0)), pickup(1, 0x26, 63)) + b"\0",
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert [item.aot_id for item in result.items.items] == [0]
    # The historical writer audit is wider than current control flow. It keeps
    # this candidate unresolved, but the zero return must never publish it as available.
    assert result.unresolved_item_slots == (1,)


def test_failed_main_flag_read_is_modeled_explicitly(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        guard(bytes((4, 1, 31, 0)), bytes((0x13, 0, 0, 1))) + b"\0",
    )
    address, _ = rules[0].flag(1, 31)
    ram = RamReader(bytearray(2 * 1024 * 1024))
    ram.fail_address = address
    snapshot = read_rule_snapshot(rules[0], (program,), ram.read_memory)
    assert snapshot.error and "injected read failure" in snapshot.error


def test_main_bit_allowlist_does_not_read_an_adjacent_temporary_flag(rules):
    layout = replace(rules[0], persistent_flag_bits=((5, 8), (5, 46)))
    scoped = layout, rules[1]
    main = (
        branch(bytes((4, 5, 8, 0)), bytes((0x13, 0, 4, 1)), bytes((0x13, 0, 0, 1)))
        + branch(bytes((4, 5, 9, 0)), bytes((0x13, 1, 4, 1)), bytes((0x13, 1, 0, 1)))
        + b"\0"
    )
    program = compile_program(
        scoped, pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + b"\0", main
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = layout.flag(5, 8)
    _, temporary_mask = layout.flag(5, 9)
    for value, state in (
        (temporary_mask, RuntimeItemState.Unavailable),
        (temporary_mask | mask, RuntimeItemState.Available),
    ):
        ram[address - 0x80000000] = value
        result = evaluate(program, scoped, ram)
        assert result.items.items[0].state == state
        assert result.unresolved_item_slots == (1,)


def test_extended_setter_preserves_source_identity_and_updates_handler(rules):
    enable = bytes((0x12, 0, 4, 0x81)) + bytes(6)
    disable = bytes((0x12, 0, 0, 0x81)) + bytes(6)
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        branch(bytes((4, 1, 0, 0)), enable, disable) + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 0)
    for value, state in (
        (0, RuntimeItemState.Unavailable),
        (mask, RuntimeItemState.Available),
    ):
        ram[address - 0x80000000] = value
        result = evaluate(program, rules, ram)
        assert result.items.list_complete
        assert result.items.items[0].state == state
        assert result.items.items[0].global_id == 111


def test_undefined_flag_writer_rejects_coverage_instead_of_branching(rules):
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", bytes((5, 10, 0, 0, 0))
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete
    assert result.unresolved_item_slots == (0,)
    assert result.items.coverage_reason == "Room script coverage is incomplete."


def test_live_door_state_mismatch_does_not_prove_complete_initialization(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    herb[0xB816C] = 0
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    assert not tracker.room_state(RoomId(0, 9)).doors_complete
    assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Cleared


def test_disabled_live_door_and_past_story_reversal_reach_map(tmp_path, rules):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    main = (
        branch(bytes((4, 1, 0, 0)), bytes((0x13, 1, 0, 0)), bytes((0x13, 1, 1, 0x81)))
        + b"\0"
    )
    updates = compile_program(rules, b"\0", main).main_procedures
    for name, program in tuple(profile.room_programs.items()):
        if name.endswith("1091.RDT"):
            # Keep the real init rules, but place this synthetic main block
            # after them so the mandatory nonoverlap invariant still holds.
            delta = program.procedures[-1].end + 2 - updates[0].start
            relocated = tuple(
                replace(
                    procedure,
                    start=procedure.start + delta,
                    end=procedure.end + delta,
                    commands=tuple(
                        replace(
                            command,
                            offset=command.offset + delta,
                            next=command.next + delta,
                            args=(command.args[0] + delta,)
                            if command.kind in ("if", "else")
                            else command.args,
                        )
                        for command in procedure.commands
                    ),
                )
                for procedure in updates
            )
            profile.room_programs[name] = replace(
                program, main_procedures=relocated, event_effects=(), mutable_slots=()
            )
    address, mask = profile.tracking_rule_layout.flag(1, 0)
    herb[address - 0x80000000] |= mask
    herb[0xB816C] = 0
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    assert (
        next(door for door in tracker.doors if door.target == RoomId(0, 20)).state
        == "BLOCKED"
    )
    for disabled in (False, True, False):
        if disabled:
            chemical[address - 0x80000000] |= mask
        else:
            chemical[address - 0x80000000] &= ~mask
        assert (
            poll_once(profile, tracker, RamReader(chemical).read_memory).status
            == PollStatus.Display
        )
        door_state = next(
            door
            for door in tracker.doors
            if door.source == RoomId(0, 9) and door.target == RoomId(0, 20)
        )
        assert door_state.state == ("BLOCKED" if disabled else "LOCKED")
        assert tracker.room_state(RoomId(0, 9)).completion == RoomCompletion.Cleared
        row = next(row for row in map_state(tracker)["rooms"] if row["id"] == "09")
        assert row["doors_complete"]
        assert len(tracker.region_visits) == 2
