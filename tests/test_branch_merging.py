"""RE1-ANALYSIS-004: conservative joins at matching script control states."""

from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import RamReader
from test_native_callbacks import interaction
from test_tracking_rules import branch, compile_program, door, guard

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    RuleCommand,
    RuleProcedure,
    evaluate_room_program,
    read_rule_snapshot,
)

pytest_plugins = ("test_tracking_rules",)


def calculate(program, rules, ram, epoch, flags=bytes([255]) * 32):
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error
    return evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, flags, (), epoch
    )


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("section", ["init", "main", "ordered"])
def test_independent_registry_branches_preserve_items_without_path_explosion(
    rules, epoch, section
):
    code = b"".join(
        branch(
            bytes((6, 2, 0, 1)),
            interaction(slot, 2, 1, 7),
            interaction(slot, 2, 1, 8),
        )
        for slot in range(2, 15)
    )
    fixed = pickup(0, 0x44, 111) + door(1, 8, 0x34)
    init, main, event = fixed + b"\0", b"\0", bytes(4)
    if section == "init":
        init = code + fixed + b"\0"
    elif section == "main":
        main = code + fixed + b"\0"
    else:
        init = (
            b"".join(interaction(slot, 2) for slot in range(2, 15))
            + fixed
            + bytes((0x14, 0, 0, 0, 0))
        )
        # Event packets have a byte length. Short setters exercise the same
        # registry joins while keeping this whole procedure within that bound.
        code = b"".join(
            branch(
                bytes((0x10, 0)),
                bytes((0x13, slot, 2, 129)),
                bytes((0x13, slot, 2, 0)),
            )
            for slot in range(2, 15)
        )
        event = indexed(block(code + fixed + b"\0") + b"\xff")
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    result = calculate(compile_program(rules, init, main, event), rules, ram, epoch)
    assert result.items.list_complete and not result.unresolved_item_slots
    assert [(item.aot_id, item.state) for item in result.items.items] == [
        (0, RuntimeItemState.Available)
    ]
    assert result.doors == ((1, door(1, 8, 0x34)),)
    assert not result.unresolved_door_slots and bytes(ram) == before


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("writer", ["flag", "scalar-alias"])
def test_distinct_physical_shadows_preserve_descriptor_guard_correlations(
    rules, epoch, writer
):
    index = 9
    yes, no = bytes((5, 4, index, 0)), bytes((5, 4, index, 1))
    if writer == "scalar-alias":
        bases = list(rules[0].flag_bases)
        bases[4] = rules[0].byte_variables_base + 12
        rules = replace(rules[0], flag_bases=tuple(bases)), rules[1]
        index = 31
        yes, no = bytes((8, 12, 1, 0)), bytes((8, 12, 0, 0))
    code = (
        branch(
            bytes((6, 2, 0, 1)),
            pickup(0, 0x26, 63) + yes,
            pickup(0, 0x44, 111) + no,
        )
        + guard(bytes((4, 4, index, 1)), pickup(0, 0x26, 63))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    assert result.items.list_complete
    assert [(item.item_type, item.global_id) for item in result.items.items] == [
        (0x26, 63)
    ]


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("consumer", ["door", "movement", "flags", "map", "quantity"])
def test_missing_creator_remains_an_alternative_for_source_consumers(
    rules, epoch, consumer
):
    creator, command = {
        "door": (door(2, 8, 0x34), bytes((0x24, 2, 1, 0))),
        "movement": (interaction(2, 5), bytes((0x24, 2, 5, 0))),
        "flags": (interaction(2, 7), bytes((0x24, 2, 7, 0))),
        "map": (pickup(2, 0x4E, 79), bytes((0x24, 2, 15, 0))),
        "quantity": (pickup(2, 0x44, 111), bytes((0x4C, 1, 2, 12))),
    }[consumer]
    code = guard(bytes((6, 2, 0, 1)), creator) + command + pickup(0, 0x26, 63) + b"\0"
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    assert not result.items.list_complete and 0 in result.unresolved_item_slots


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_different_callback_targets_keep_untouched_flag_alternatives(rules, epoch):
    code = (
        branch(bytes((6, 2, 0, 1)), interaction(0, 7, 1, 7), interaction(0, 7, 1, 8))
        + bytes((0x24, 0, 7, 0))
        + guard(bytes((4, 1, 7, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (1,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_joined_callback_parameters_retain_every_reachable_event(rules, epoch):
    code = branch(
        bytes((6, 2, 0, 1)), interaction(0, 2, 0, 0), interaction(0, 2, 0, 1)
    ) + bytes((0x24, 0, 9, 0, 0))
    event = indexed(
        block(pickup(1, 0x44, 111) + b"\0") + b"\xff",
        block(pickup(2, 0x26, 63) + b"\0") + b"\xff",
    )
    result = calculate(
        compile_program(rules, code, event=event),
        rules,
        bytearray(2 * 1024 * 1024),
        epoch,
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (1, 2)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("kind", ["item", "door"])
def test_joining_retains_conflicting_item_identities_and_door_targets(
    rules, epoch, kind
):
    yes, no = (
        (pickup(0, 0x44, 111), pickup(0, 0x26, 63))
        if kind == "item"
        else (door(0, 8, 0x34), door(0, 10, 0x33))
    )
    code = branch(bytes((6, 2, 0, 1)), yes, no) + b"\0"
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    if kind == "item":
        assert not result.items.list_complete and result.unresolved_item_slots == (0,)
    else:
        assert result.unresolved_door_slots == (0,) and not result.doors


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_joined_availability_alternatives_reread_acquisition_on_reversal(rules, epoch):
    code = (
        pickup(0, 0x44, 111)
        + branch(
            bytes((6, 2, 0, 1)), bytes((0x13, 0, 0, 129)), bytes((0x13, 0, 4, 129))
        )
        + door(1, 8, 0x34)
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    for taken in (False, True, False):
        flags = bytearray([255]) * 32
        if taken:
            flags[14] &= ~1
        result = calculate(program, rules, ram, epoch, bytes(flags))
        assert result.items.list_complete == taken
        if taken:
            assert result.items.items[0].state is RuntimeItemState.Taken
        else:
            assert result.unresolved_item_slots == (0,)
        assert result.doors == ((1, door(1, 8, 0x34)),)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_quantity_alternatives_do_not_supply_an_invented_scalar_guard(rules, epoch):
    one, two = bytearray(pickup(0, 0x44, 111)), bytearray(pickup(0, 0x44, 111))
    one[11], two[11] = 1, 2
    code = (
        branch(bytes((6, 2, 0, 1)), bytes(one), bytes(two))
        + bytes((0x4C, 0, 0, 12))
        + guard(bytes((6, 12, 0, 1)), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (1,)
    assert result.items.items[0].amount is ItemQuantityState.Unreconstructed


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("consumer", ["quantity", "parameters"])
def test_descriptor_reads_preserve_guards_that_pass_for_all_input_values(
    rules, epoch, consumer
):
    if consumer == "quantity":
        one, two = bytearray(pickup(0, 0x44, 111)), bytearray(pickup(0, 0x44, 111))
        one[11], two[11] = 1, 2
        prefix = branch(bytes((6, 2, 0, 1)), bytes(one), bytes(two))
        read = bytes((0x4C, 0, 0, 12))
    else:
        bases = list(rules[0].flag_bases)
        bases[1] = rules[0].byte_variables_base + 12
        rules = replace(rules[0], flag_bases=tuple(bases)), rules[1]
        prefix = bytes((8, 12, 0, 0)) + branch(
            bytes((6, 2, 0, 1)), interaction(0, 7, 1, 31), interaction(0, 7, 1, 30)
        )
        read = bytes((0x24, 0, 7, 0))
    code = prefix + read + guard(bytes((6, 12, 2, 1)), pickup(1, 0x26, 63)) + b"\0"
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    assert result.items.list_complete
    assert any(item.aot_id == 1 and item.global_id == 63 for item in result.items.items)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("alternatives", [32, 255, 256])
def test_joining_keeps_the_descriptor_budget(rules, epoch, alternatives):
    code = (
        b"".join(
            guard(bytes((6, 2, 0, 1)), interaction(0, 2, 1, index))
            for index in range(alternatives)
        )
        + pickup(1, 0x44, 111)
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    # The never-created path contributes None as one more descriptor choice.
    assert result.items.list_complete == (alternatives <= 255)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_distinct_relevant_flag_states_still_obey_the_procedure_budget(rules, epoch):
    code = b"".join(
        branch(bytes((6, 2, 0, 1)), bytes((5, 4, index, 0)), bytes((5, 4, index, 1)))
        for index in range(13)
    )
    code += b"".join(guard(bytes((4, 4, index, 0)), b"") for index in range(13))
    code += pickup(0, 0x44, 111) + b"\0"
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (0,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_matching_pc_with_different_if_stacks_keeps_the_invalid_path(rules, epoch):
    program = compile_program(rules, pickup(0, 0x44, 111) + b"\0")
    procedure = program.procedures[0]
    start = procedure.start
    commands = (
        RuleCommand(start, start + 2, "if", (start + 8,)),
        RuleCommand(start + 2, start + 4, "uncertain-test", ()),
        RuleCommand(start + 4, start + 6, "if", (start + 8,)),
        RuleCommand(start + 6, start + 8, "uncertain-test", ()),
        RuleCommand(start + 8, start + 10, "endif", ()),
    ) + tuple(
        replace(command, offset=command.offset + 10, next=command.next + 10)
        for command in procedure.commands
    )
    program = replace(
        program,
        procedures=(RuleProcedure(start, procedure.end + 10, commands),),
        main_procedures=(),
    )
    result = calculate(program, rules, bytearray(2 * 1024 * 1024), epoch)
    # One predecessor reaches ENDIF after its IF was already popped. A valid
    # predecessor at the same PC must not conceal that malformed path.
    assert not result.items.list_complete and result.unresolved_item_slots == (0,)
