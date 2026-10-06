"""RE1-AOT-003/004: source-independent disable and retained-source barriers."""

import struct

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
    evaluate_room_program,
    read_rule_snapshot,
)

pytest_plugins = ("test_tracking_rules",)


def setter(slot, handler, mode, extended):
    packet = bytes((0x12 if extended else 0x13, slot, handler, mode))
    return packet + struct.pack("<HHH", 1, 7, 1) if extended else packet


def calculate(program, rules, ram, epoch, flags=bytes([255]) * 32):
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error
    return evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, flags, (), epoch
    )


@pytest.mark.parametrize("extended", [False, True])
@pytest.mark.parametrize("mode", [0, 255])
@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("section", ["init", "main", "ordered", "standalone"])
def test_disable_without_a_creator_preserves_other_items_and_doors(
    rules, extended, mode, epoch, section
):
    disable = setter(5, 0, mode, extended)
    init = pickup(0, 0x44, 111) + door(1, 8, 0x34)
    main, event = b"\0", bytes(4)
    if section == "init":
        init += disable
    elif section == "main":
        main = disable + b"\0"
    else:
        init += bytes((0x14, 0, 0, 0))
        event = indexed(
            (
                block(disable + b"\0")
                if section == "ordered"
                else bytes((7, len(disable) + 2)) + disable
            )
            + b"\xff"
        )
    program = compile_program(rules, init + b"\0", main, event)
    assert program.coverage_complete
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    result = calculate(program, rules, ram, epoch)
    assert result.items.list_complete and not result.unresolved_item_slots
    assert [(i.aot_id, i.state) for i in result.items.items] == [
        (0, RuntimeItemState.Available)
    ]
    assert result.doors == ((1, door(1, 8, 0x34)),)
    assert not result.unresolved_door_slots and not result.disabled_doors
    assert bytes(ram) == before


@pytest.mark.parametrize("extended", [False, True])
@pytest.mark.parametrize(
    "later",
    [
        *(
            setter(5, handler, 129, extended)
            for extended in (False, True)
            for handler in (1, 4, 9, 16)
        ),
        *(
            bytes((op, 5, handler, 0))
            for op in (0x24, 0x2D)
            for handler in (1, 5, 6, 7, 9, 15)
        ),
        *(bytes((0x4C, mode, 5, 12)) for mode in (1, 2)),
    ],
)
def test_disabling_does_not_authorize_unknown_source_operations(rules, extended, later):
    code = setter(5, 0, 129, extended) + later + pickup(0, 0x44, 111) + b"\0"
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Reentry,
    )
    assert not result.items.list_complete


@pytest.mark.parametrize("extended", [False, True])
def test_quantity_read_from_a_disabled_unknown_source_stays_unknown(rules, extended):
    code = (
        setter(5, 0, 129, extended)
        + bytes((0x4C, 0, 5, 12))
        + guard(bytes((6, 12, 0, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Reentry,
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (0,)


@pytest.mark.parametrize("extended", [False, True])
@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_disabling_retains_known_item_and_door_sources_and_fresh_acquisition(
    rules, extended, epoch
):
    code = (
        pickup(0, 0x44, 111)
        + door(1, 8, 0x34)
        + setter(0, 0, 255, extended)
        + setter(1, 0, 255, extended)
        + setter(0, 4, 129, False)
        + setter(1, 1, 129, False)
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    expected_door = bytearray(door(1, 8, 0x34))
    expected_door[25] = 129
    for taken in (False, True, False):
        flags = bytearray([255]) * 32
        if taken:
            flags[14] &= ~1
        result = calculate(program, rules, ram, epoch, bytes(flags))
        assert result.items.list_complete and len(result.items.items) == 1
        item = result.items.items[0]
        assert (item.item_type, item.global_id, item.amount) == (0x44, 111, 0)
        assert item.state is (
            RuntimeItemState.Taken if taken else RuntimeItemState.Available
        )
        assert (
            result.doors == ((1, bytes(expected_door)),)
            and not result.unresolved_door_slots
        )
    assert bytes(ram) == before


@pytest.mark.parametrize("extended", [False, True])
def test_disable_alone_does_not_grant_acquisition_or_lose_known_sources(
    rules, extended
):
    code = (
        pickup(0, 0x44, 111)
        + door(1, 8, 0x34)
        + setter(0, 0, 129, extended)
        + setter(1, 0, 129, extended)
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Reentry,
    )
    assert (
        result.items.list_complete
        and result.items.items[0].state is RuntimeItemState.Unavailable
    )
    assert not result.doors and len(result.disabled_doors) == 1
    assert not result.unresolved_door_slots


@pytest.mark.parametrize("extended", [False, True])
@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_disabled_dormant_award_still_requires_fresh_acquisition(
    rules, extended, epoch
):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + setter(0, 0, 129, extended) + b"\0",
        main=bytes((0x24, 0, 4, 0, 0)),
    )
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


@pytest.mark.parametrize("extended", [False, True])
def test_disabling_retains_supported_callback_parameters(rules, extended):
    code = (
        interaction(5, 7, 1, 7, 1)
        + setter(5, 0, 129, extended)
        + bytes((0x24, 5, 7, 0))
        + guard(bytes((4, 1, 7, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Reentry,
    )
    assert result.items.list_complete and len(result.items.items) == 1


@pytest.mark.parametrize("extended", [False, True])
@pytest.mark.parametrize("new_creator", [False, True])
def test_partial_creator_branch_requires_a_new_creator_before_enabling(
    rules, extended, new_creator
):
    code = branch(bytes((0x10, 0)), pickup(5, 0x44, 111), b"") + setter(
        5, 0, 129, extended
    )
    if new_creator:
        code += pickup(5, 0x44, 111)
    code += setter(5, 4, 129, False) + pickup(0, 0x26, 63) + b"\0"
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Reentry,
    )
    assert result.items.list_complete == new_creator
    if new_creator:
        assert [i.aot_id for i in result.items.items] == [0, 5]


@pytest.mark.parametrize("extended", [False, True])
def test_story_reversal_does_not_reuse_an_earlier_creator(rules, extended):
    init = guard(bytes((4, 1, 7, 0)), pickup(5, 0x44, 111)) + b"\0"
    main = setter(5, 0, 129, extended) + setter(5, 4, 129, False) + b"\0"
    program = compile_program(rules, init, main)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 7)
    for present in (False, True, False):
        ram[address - 0x80000000] = mask if present else 0
        result = calculate(program, rules, ram, RoomRuleEpoch.Reentry)
        assert result.items.list_complete == present
        if present:
            assert result.items.items[0].state is RuntimeItemState.Available
