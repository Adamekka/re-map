"""RE1-SCD-021/022: synthetic interaction writes and conditional item lifetimes."""

from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import RamReader
from test_tracking_rules import branch, compile_program, door, guard

from games.game_profile import RoomId
from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)

pytest_plugins = ("test_tracking_rules",)


@pytest.mark.parametrize("opcode,index", [(0x10, 18), (0x11, 19)])
@pytest.mark.parametrize("epoch", RoomRuleEpoch)
@pytest.mark.parametrize("actual,expected", [(0, 0), (128, 128), (255, 255), (255, 0)])
def test_same_run_interaction_write_selects_unsigned_item_and_door_branches(
    rules, opcode, index, epoch, actual, expected
):
    code = (
        bytes((8, index, actual, 255))
        + branch(
            bytes((opcode, expected)),
            pickup(0, 0x44, 111) + door(1, 8, 0x34),
            pickup(0, 0x26, 63) + door(1, 10, 0x33),
        )
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    ram[rules[0].byte_variables_base - 0x80000000 + index] = actual ^ 255
    before = bytes(ram)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    for flags, state in (
        (bytes([255]) * 32, RuntimeItemState.Available),
        (bytes(32), RuntimeItemState.Taken),
        (bytes([255]) * 32, RuntimeItemState.Available),
    ):
        result = evaluate_room_program(
            program, RoomId(0, 9), rules[0], snapshot, flags, (), epoch
        )
        assert result.items.list_complete and not result.unresolved_door_slots
        assert len(result.items.items) == 1 and len(result.doors) == 1
        item = result.items.items[0]
        assert item.item_type == (0x44 if actual == expected else 0x26)
        assert item.state == state
        assert result.doors[0][1][15] == (8 if actual == expected else 10)
    assert bytes(ram) == before


@pytest.mark.parametrize("opcode,index", [(0x10, 18), (0x11, 19)])
@pytest.mark.parametrize("epoch", RoomRuleEpoch)
@pytest.mark.parametrize("value", [0, 0x34, 255])
def test_unwritten_interaction_stays_unresolved_without_reading_current_ram(
    rules, opcode, index, epoch, value
):
    program = compile_program(
        rules, guard(bytes((opcode, value)), pickup(0, 0x44, 111)) + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    address = rules[0].byte_variables_base + index
    ram[address - 0x80000000] = value
    reader = RamReader(ram)
    reader.fail_address = address
    snapshot = read_rule_snapshot(rules[0], (program,), reader.read_memory)
    assert not snapshot.error and address not in dict(snapshot.values)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.unresolved_item_slots == (0,)
    assert not result.items.list_complete and not result.items.items


@pytest.mark.parametrize("opcode,index", [(0x10, 18), (0x11, 19)])
@pytest.mark.parametrize("epoch", RoomRuleEpoch)
def test_flag_alias_replaces_an_interaction_shadow(rules, opcode, index, epoch):
    layout = replace(
        rules[0],
        flag_bases=rules[0].flag_bases[:9] + (rules[0].byte_variables_base + 16,),
    )
    profile = dict(rules[1])
    profile["script_flag_bases"] = [hex(base) for base in layout.flag_bases]
    scoped = layout, profile
    # Bank words use MSB-first indices over little-endian bytes. Clear the
    # high bit of the same physical byte after setting it to 255.
    flag_index = (19 - index) * 8
    assert layout.flag(9, flag_index) == (layout.byte_variables_base + index, 128)
    program = compile_program(
        scoped,
        bytes((8, index, 255, 0, 5, 9, flag_index, 1))
        + guard(bytes((opcode, 127)), pickup(0, 0x44, 111))
        + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(layout, (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), layout, snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.items.list_complete and len(result.items.items) == 1


@pytest.mark.parametrize("opcode,index", [(0x10, 18), (0x11, 19)])
@pytest.mark.parametrize("epoch", RoomRuleEpoch)
def test_quantity_copy_forgets_a_preceding_interaction_write(
    rules, opcode, index, epoch
):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111)
        + bytes((0x4C, 2, 0, 7))
        + bytes((8, index, 0x34, 0, 0x4C, 0, 0, index))
        + guard(bytes((opcode, 0x34)), pickup(1, 0x26, 63))
        + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.unresolved_item_slots == (1,)
    assert [item.aot_id for item in result.items.items] == [0]
    assert not result.items.list_complete


@pytest.mark.parametrize("epoch", RoomRuleEpoch)
def test_map_callback_does_not_reuse_an_earlier_acquisition_interaction(rules, epoch):
    program = compile_program(
        rules,
        pickup(0, 0x4E, 111)
        + bytes((8, 19, 0x34, 0, 0x24, 0, 15, 0))
        + guard(bytes((0x11, 0x34)), pickup(1, 0x26, 63))
        + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.unresolved_item_slots == (1,)
    assert [item.aot_id for item in result.items.items] == [0]


@pytest.mark.parametrize("opcode,index", [(0x10, 18), (0x11, 19)])
@pytest.mark.parametrize("epoch", RoomRuleEpoch)
@pytest.mark.parametrize("event", [False, True])
def test_initializer_interaction_cannot_rule_out_a_later_player_action(
    rules, opcode, index, epoch, event
):
    change = guard(bytes((opcode, 0x34)), bytes((0x13, 0, 0, 1))) + b"\0"
    init = pickup(0, 0x44, 111) + bytes((8, index, 0, 0))
    if event:
        program = compile_program(
            rules,
            init + bytes((0x14, 0, 0, 0, 0)),
            bytes((8, index, 0, 0, 0)),
            indexed(block(change) + b"\xff"),
        )
    else:
        program = compile_program(rules, init + b"\0", change)
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.unresolved_item_slots == (0,)
    assert not result.items.list_complete


@pytest.mark.parametrize("opcode,index", [(0x10, 18), (0x11, 19)])
@pytest.mark.parametrize("epoch", RoomRuleEpoch)
def test_synchronous_event_procedures_share_their_interaction_write(
    rules, opcode, index, epoch
):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + bytes((0x14, 0, 0, 0, 0)),
        event=indexed(
            block(
                bytes((8, index, 0, 0, 0)),
                guard(bytes((opcode, 0x34)), bytes((0x13, 0, 0, 1))) + b"\0",
            )
            + b"\xff"
        ),
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.items.list_complete
    assert [item.state for item in result.items.items] == [RuntimeItemState.Available]


@pytest.mark.parametrize("opcode", [0x10, 0x11])
def test_truncated_interaction_predicate_cannot_authorize_clearance(rules, opcode):
    program = compile_program(rules, bytes((opcode,)))
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, ()
    )
    assert not result.items.list_complete and not result.coverage_complete
