"""RE1-SCD-018/019/020: synthetic tracking and event-return regressions."""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest
from build_cache_metadata import scan_cache_rdt
from scan_events import scan_event_program
from test_cache_metadata import indexed_event, pickup, source
from test_event_conditions import block
from test_room_reentry import reenter
from test_tracking_rules import branch, compile_program, door, evaluate, guard

from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import RoomProgram, RoomRuleEpoch

pytest_plugins = ("test_tracking_rules",)

COMMANDS = (
    bytes((0x40, 0)) + bytes(14),
    bytes((0x4D, 255)),
    *(bytes((0x4E, mode, 255, 255)) for mode in (0, 1, 2, 255)),
)


@pytest.mark.parametrize("command", COMMANDS)
@pytest.mark.parametrize("section", ["init", "main", "event"])
@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_rendering_returns_preserve_items_doors_and_do_not_write_ram(
    rules, command, section, epoch
):
    code = (
        branch(command, pickup(0, 0x44, 111), pickup(0, 0x26, 63))
        + pickup(1, 0x26, 63)
        + door(2, 8, 0x34)
        + b"\0"
    )
    program = compile_program(
        rules,
        code
        if section == "init"
        else pickup(0, 0x44, 111)
        + pickup(1, 0x26, 63)
        + door(2, 8, 0x34)
        + bytes((0x14, 0, 0, 0, 0))
        if section == "event"
        else b"\0",
        code if section == "main" else b"\0",
        indexed_event(block(code) + b"\xff") if section == "event" else bytes(4),
    )
    assert program.coverage_complete
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    result = reenter(program, rules, ram, epoch)
    assert result.items.list_complete
    assert [item.item_type for item in result.items.items] == [0x44, 0x26]
    assert result.doors == ((2, door(2, 8, 0x34)),)
    assert not result.unresolved_door_slots
    assert bytes(ram) == before


@pytest.mark.parametrize("command", COMMANDS)
def test_rendering_preserves_local_shadow_flags_and_fresh_acquisition_reversal(
    rules, command
):
    # Bank 4's last bits alias the effect-pool header, which 4E only reads.
    # Bank 6's room/model pointers and bank 5's rendering bit are also preserved.
    code = (
        bytes((5, 4, 255, 0, 5, 6, 160, 0, 5, 5, 31, 0))
        + command
        + guard(
            bytes((4, 4, 255, 0, 4, 6, 160, 0, 4, 5, 31, 0)),
            pickup(0, 0x44, 111),
        )
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    for collected, expected in (
        (False, RuntimeItemState.Available),
        (True, RuntimeItemState.Taken),
        (False, RuntimeItemState.Available),
    ):
        flags = bytearray([255] * 32)
        if collected:
            # GlobalId 111 selects acquisition byte 14 bit 0 in RE1's bit order.
            flags[14] &= ~1
        result = evaluate(program, rules, ram, bytes(flags))
        assert result.items.list_complete
        assert result.items.items[0].state == expected


@pytest.mark.parametrize("command", COMMANDS)
def test_single_rendering_dispatch_preserves_a_following_ordered_item_event(
    rules, command
):
    event = indexed_event(
        bytes((7, len(command) + 2))
        + command
        + block(pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0")
        + b"\xff"
    )
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + door(1, 8, 0x34) + bytes((0x14, 0, 0, 0, 0)),
        event=event,
    )
    result = reenter(program, rules, bytearray(2 * 1024 * 1024))
    assert program.coverage_complete and result.items.list_complete
    assert [item.item_type for item in result.items.items] == [0x44]
    assert result.doors == ((1, door(1, 8, 0x34)),)


@pytest.mark.parametrize("command", COMMANDS)
def test_deferred_rendering_return_one_never_reaches_the_exit(command):
    event = indexed_event(
        bytes((0xFC, len(command) + 2))
        + command
        + bytes((0xFE, 0xFD))
        + bytes((7, 28))
        + pickup(0, 0x44, 111)
        + b"\xff"
    )
    scan = scan_event_program(b"x" + event, 1, len(event) + 1)
    assert scan.status == "clean"
    assert [(op, raw) for _, op, raw in scan.operations] == [(command[0], command)]


@pytest.mark.parametrize("index", [2, 127, 128, 255])
def test_lighting_index_that_can_reach_scripts_or_headers_rejects_clearance(
    rules, index
):
    command = bytes((0x40, index)) + bytes(14)
    program = compile_program(rules, command + pickup(0, 0x44, 111) + b"\0")
    assert program.coverage_complete
    assert program.procedures[0].commands[0].kind == "unsupported-effect"
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), bytes(32))
    assert not result.items.list_complete


@pytest.mark.parametrize("section_start,accepted", [(0xBF, False), (0xC0, True)])
def test_lighting_last_word_cannot_overlap_a_pointed_section(
    rules, section_start, accepted
):
    data = bytearray(
        source(COMMANDS[0] + pickup(0, 0x44, 111) + b"\0", b"\0", bytes(4))
    )
    # This synthetic pointed section ends the unreferenced lighting prefix.
    struct.pack_into("<I", data, 0x48, section_start)
    row = scan_cache_rdt(data, "PSX/STAGE1/ROOM1091.RDT", rules[1])
    program = RoomProgram.load(row["tracking_program"])
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete == accepted


def test_lighting_is_not_limited_to_the_three_indices_in_the_owned_event(rules):
    code = bytes((0x40, 7)) + bytes(14) + pickup(0, 0x44, 111) + b"\0"
    original = source(code, b"\0", bytes(4))
    data = bytearray(original[:0x100] + bytes(0x100) + original[0x100:])
    offsets = struct.unpack_from("<19I", data, 0x48)
    struct.pack_into(
        "<19I", data, 0x48, *(value + 0x100 if value else 0 for value in offsets)
    )
    row = scan_cache_rdt(data, "PSX/STAGE1/ROOM1091.RDT", rules[1])
    result = evaluate(
        RoomProgram.load(row["tracking_program"]), rules, bytearray(2 * 1024 * 1024)
    )
    assert result.items.list_complete and len(result.items.items) == 1
