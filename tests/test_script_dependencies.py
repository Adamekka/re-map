"""RE1-ANALYSIS-001: whole-room shadow dependencies, synthetic source programs."""

from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import RamReader
from test_native_callbacks import interaction
from test_tracking_rules import branch, compile_program, door, guard

from games.game_profile import RoomId
from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import (
    RoomRuleEpoch,
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
@pytest.mark.parametrize("writer", ["flag", "byte", "word"])
def test_unread_branch_writes_collapse_without_losing_items_or_doors(
    rules, epoch, writer
):
    code = b""
    for index in range(13):
        if writer == "flag":
            yes, no = bytes((5, 4, index, 0)), bytes((5, 4, index, 1))
        elif writer == "byte":
            yes, no = bytes((8, index + 20, 0, 0)), bytes((8, index + 20, 1, 0))
        else:
            yes = bytes((0x31, index, 0, 0))
            no = bytes((0x31, index, 1, 0))
        code += branch(bytes((6, 2, 0, 1)), yes, no)
    code += pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0"
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    result = calculate(program, rules, ram, epoch)
    assert result.items.list_complete and result.unresolved_item_slots == ()
    assert result.items.items[0].state is RuntimeItemState.Available
    assert result.doors == ((1, door(1, 8, 0x34)),)
    assert not result.unresolved_door_slots
    assert bytes(ram) == before


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("separate", [False, True])
@pytest.mark.parametrize("reader", ["flag", "byte", "word", "quantity"])
def test_alias_reads_in_later_procedures_preserve_written_bits(
    rules, epoch, separate, reader
):
    layout = replace(rules[0], word_variables_base=rules[0].flag_bases[4])
    rules = layout, rules[1]
    write = bytes((0x31, 0, 1, 0))
    if reader == "flag":
        read = guard(bytes((4, 4, 31, 0)), pickup(0, 0x44, 111))
    elif reader == "word":
        read = guard(bytes((7, 0, 0, 0, 1, 0)), pickup(0, 0x44, 111))
    else:
        # Relocate a saved flag bank onto scalar 12. A flag writer and scalar
        # reader must observe the same physical bit despite different indices.
        bases = list(layout.flag_bases)
        bases[1] = layout.byte_variables_base + 12
        rules = replace(layout, flag_bases=tuple(bases)), rules[1]
        write = bytes((8, 12, 0, 0, 5, 1, 31, 0))
        read = (
            guard(bytes((6, 12, 0, 1)), pickup(0, 0x44, 111))
            if reader == "byte"
            else pickup(0, 0x44, 111) + bytes((0x4C, 1, 0, 12))
        )
    program = compile_program(rules, write + read + b"\0")
    if separate:
        procedure = program.procedures[0]
        boundary = next(
            c.offset for c in procedure.commands if c.kind == "if" or c.kind == "item"
        )
        program = replace(
            program,
            procedures=(
                RuleProcedure(
                    procedure.start,
                    boundary,
                    tuple(c for c in procedure.commands if c.offset < boundary),
                ),
                RuleProcedure(
                    boundary,
                    procedure.end,
                    tuple(c for c in procedure.commands if c.offset >= boundary),
                ),
            ),
        )
    result = calculate(program, rules, bytearray(2 * 1024 * 1024), epoch)
    assert result.items.list_complete and len(result.items.items) == 1
    if reader == "quantity":
        assert result.items.items[0].amount == 1


@pytest.mark.parametrize("synchronous", [False, True])
def test_event_flag_dependency_survives_until_a_later_main_tick(rules, synchronous):
    write = bytes((5, 4, 9, 0))
    event = indexed(
        (block(write + b"\0") if synchronous else bytes((7, 6)) + write) + b"\xff"
    )
    main = guard(bytes((4, 4, 9, 0)), pickup(0, 0x44, 111)) + b"\0"
    program = compile_program(rules, bytes((0x14, 0, 0, 0, 0)), main, event)
    result = calculate(
        program, rules, bytearray(2 * 1024 * 1024), RoomRuleEpoch.Reentry
    )
    # Optional event execution can make the main creator appear on a later tick.
    assert not result.items.list_complete and result.unresolved_item_slots == (0,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_callback_parameter_alternatives_preserve_quantity_aliases(rules, epoch):
    bases = list(rules[0].flag_bases)
    bases[1] = rules[0].byte_variables_base + 12
    rules = replace(rules[0], flag_bases=tuple(bases)), rules[1]
    code = (
        bytes((8, 12, 3, 0))
        + branch(bytes((0x10, 0)), interaction(0, 7, 1, 31), interaction(0, 7, 1, 30))
        + bytes((0x24, 0, 7, 0))
        + pickup(1, 0x44, 111)
        + bytes((0x4C, 1, 1, 12, 0))
    )
    result = calculate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024), epoch
    )
    assert result.items.list_complete and result.items.items[0].amount == 3


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_quantity_read_only_in_an_event_retains_its_scalar_dependency(rules, epoch):
    item = bytearray(pickup(0, 0x44, 111))
    item[11] = 3
    write = bytes((8, 12, 3, 0))
    read = bytes((0x4C, 1, 0, 12, 0x4C, 0, 0, 9))
    impossible = guard(bytes((6, 9, 0, 4)), bytes((0x13, 0, 0, 0)))
    event = indexed(block(write + b"\0", read + impossible + b"\0") + b"\xff")
    program = compile_program(
        rules,
        bytes(item) + bytes((0x14, 0, 0, 0, 0)),
        event=event,
    )
    result = calculate(program, rules, bytearray(2 * 1024 * 1024), epoch)
    # Quantity uncertainty outside the event must not erase the branch proof
    # inside its ordered procedure list: scalar 12 -> quantity -> scalar 9.
    assert result.items.list_complete and [i.aot_id for i in result.items.items] == [0]


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("bad", ["bank", "callback", "effect"])
def test_unread_unsupported_effects_still_block_completion(rules, epoch, bad):
    command = {
        "bank": bytes((5, 10, 0, 0)),
        "callback": bytes((0x24, 0, 7, 0)),
        "effect": bytes((0x4B, 0)),
    }[bad]
    program = compile_program(rules, command + pickup(1, 0x44, 111) + b"\0")
    if bad == "effect":
        procedure = program.procedures[0]
        unsupported = replace(procedure.commands[0], kind="unsupported-effect", args=())
        program = replace(
            program,
            procedures=(
                replace(procedure, commands=(unsupported,) + procedure.commands[1:]),
            ),
        )
    result = calculate(program, rules, bytearray(2 * 1024 * 1024), epoch)
    assert not result.items.list_complete
    assert result.unresolved_item_slots == (1,)
