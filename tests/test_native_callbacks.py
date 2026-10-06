"""RE1-SCD-016/017: synthetic forced movement and registry flag callbacks."""

import struct
from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import RamReader
from test_tracking_rules import branch, compile_program, door, guard

from games.game_profile import RoomId
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)

pytest_plugins = ("test_tracking_rules",)


def interaction(slot, handler, group=1, index=7, operation=1):
    raw = bytearray(18)
    raw[0], raw[1], raw[10], raw[11] = 0x0D, slot, handler, 129
    struct.pack_into("<HHH", raw, 12, group, index, operation)
    return bytes(raw)


def evaluate(program, rules, ram, epoch, flags=bytes([255]) * 32):
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error
    return evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, flags, (), epoch
    )


@pytest.mark.parametrize("handler", [5, 6])
@pytest.mark.parametrize("op", [0x24, 0x2D])
@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_movement_preserves_items_doors_and_disabled_source(rules, handler, op, epoch):
    code = (
        interaction(0, handler)
        + bytes((0x13, 0, 0, 0))
        + door(1, 8, 0x34)
        + pickup(2, 0x44, 111)
        + guard(bytes((op, 0, handler, 0)), b"")
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    result = evaluate(program, rules, ram, epoch)
    assert result.items.list_complete
    assert [item.aot_id for item in result.items.items] == [2]
    assert result.doors == ((1, door(1, 8, 0x34)),)
    assert not result.unresolved_door_slots and not program.mutable_slots
    assert bytes(ram) == before


@pytest.mark.parametrize("handler", [5, 6])
def test_pending_movement_is_not_a_cross_tick_invariant(rules, handler):
    code = (
        interaction(0, handler)
        + bytes((5, 5, 41, 0, 0x24, 0, handler, 0))
        + guard(bytes((4, 5, 41, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Reentry,
    )
    assert result.unresolved_item_slots == (1,)


@pytest.mark.parametrize("handler", [5, 6])
@pytest.mark.parametrize("old", [0, 1])
def test_movement_forgets_its_consumed_dialog_bit_and_preserves_other_bits(
    rules, handler, old
):
    code = (
        interaction(0, handler)
        + bytes((5, 6, 25, old, 5, 6, 24, 0, 0x24, 0, handler, 0))
        + guard(bytes((4, 6, 25, 1)), pickup(1, 0x44, 111))
        + guard(bytes((4, 6, 24, 0)), pickup(2, 0x26, 63))
        + b"\0"
    )
    result = evaluate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Current,
    )
    assert result.unresolved_item_slots == (1,)
    assert [item.aot_id for item in result.items.items] == [2]


@pytest.mark.parametrize("handler", [5, 6])
def test_movement_without_a_source_is_unresolved(rules, handler):
    program = compile_program(
        rules, bytes((0x24, 0, handler, 0)) + pickup(1, 0x44, 111) + b"\0"
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), RoomRuleEpoch.Reentry)
    assert not result.items.list_complete


@pytest.mark.parametrize("handler", [5, 6])
@pytest.mark.parametrize("section", ["main", "events"])
def test_movement_in_main_and_indexed_events_preserves_other_interactions(
    rules, handler, section
):
    callback = bytes((0x24, 0, handler, 0))
    init = interaction(0, handler) + door(1, 8, 0x34) + pickup(2, 0x44, 111)
    program = compile_program(
        rules,
        init + (bytes((0x14, 0, 0, 0)) if section == "events" else b"") + b"\0",
        callback + b"\0" if section == "main" else b"\0",
        indexed(bytes((7, 6)) + callback + b"\xff")
        if section == "events"
        else bytes(4),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), RoomRuleEpoch.Reentry)
    assert result.items.list_complete and len(result.items.items) == 1
    assert result.doors == ((1, door(1, 8, 0x34)),) and not result.unresolved_door_slots


@pytest.mark.parametrize(
    "group,index",
    [(g, i) for g in range(10) for i in (0, 31, 32, 255)] + [(5, 65535), (6, 65535)],
)
@pytest.mark.parametrize("operation", [0, 65535])
def test_flag_callback_uses_native_bank_aliases_and_full_operation(
    rules, group, index, operation
):
    target = index & 31 if group in (5, 6) else index
    code = (
        interaction(0, 7, group, index, operation)
        + bytes((5, group, target, 0 if operation == 0 else 1, 0x24, 0, 7, 0))
        + guard(bytes((4, group, target, 0 if operation else 1)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Current,
    )
    assert result.items.list_complete and len(result.items.items) == 1


@pytest.mark.parametrize("group,index", [(10, 0), (65535, 0), (0, 256), (7, 65535)])
def test_unbounded_native_flag_targets_reject_coverage(rules, group, index):
    program = compile_program(
        rules,
        interaction(0, 7, group, index)
        + bytes((0x24, 0, 7, 0))
        + pickup(1, 0x44, 111)
        + b"\0",
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), RoomRuleEpoch.Current)
    assert not result.items.list_complete


@pytest.mark.parametrize("op,item_type", [(0x24, 0x44), (0x2D, 0x26)])
def test_callback_return_does_not_control_the_scd_return(rules, op, item_type):
    code = (
        interaction(0, 7)
        + branch(bytes((op, 0, 7, 0)), pickup(1, 0x44, 111), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = evaluate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Current,
    )
    assert result.items.list_complete and result.items.items[0].item_type == item_type


def test_unguarded_zero_return_skips_the_remaining_procedure(rules):
    code = interaction(0, 7) + bytes((0x2D, 0, 7, 0)) + pickup(1, 0x44, 111) + b"\0"
    result = evaluate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Current,
    )
    assert result.items.list_complete and result.items.items == ()


@pytest.mark.parametrize("op", [0x24, 0x2D])
def test_pending_flag_updates_follow_the_callback_flag_write(rules, op):
    code = (
        interaction(0, 7, 5, 20, 0)
        + guard(bytes((op, 0, 7, 0)), b"")
        + guard(bytes((4, 5, 20, 0 if op == 0x2D else 1)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Current,
    )
    assert result.items.list_complete and len(result.items.items) == 1


def test_extended_setter_replaces_all_three_parameters_and_short_setter_retains_them(
    rules,
):
    setter = bytes((0x12, 0, 16, 0)) + struct.pack("<HHH", 1, 32, 0)
    code = (
        interaction(0, 7, 2, 7, 1)
        + setter
        + bytes((0x13, 0, 0, 0, 0x24, 0, 7, 0))
        + guard(bytes((4, 1, 32, 1)), pickup(1, 0x44, 111))
        + b"\0"
    )
    program = compile_program(rules, code)
    assert program.event_program.registry_writes[-1][1:] == (0, 1, 32, 0)
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), RoomRuleEpoch.Current)
    assert result.items.list_complete and len(result.items.items) == 1


@pytest.mark.parametrize("creator", [b"", pickup(0, 0x44, 111)])
def test_flag_callback_requires_reconstructed_parameters(rules, creator):
    program = compile_program(
        rules, creator + bytes((0x24, 0, 7, 0)) + pickup(1, 0x26, 63) + b"\0"
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), RoomRuleEpoch.Current)
    assert not result.items.list_complete


def test_callback_shadow_changes_activation_without_granting_acquisition(rules):
    program = compile_program(
        rules,
        interaction(0, 7, 7, 111, 0)
        + bytes((0x24, 0, 7, 0))
        + pickup(1, 0x44, 111)
        + b"\0",
    )
    flags = bytearray([255]) * 32
    for acquired, state in (
        (False, "unavailable"),
        (True, "taken"),
        (False, "unavailable"),
    ):
        # GlobalId 111 selects byte 14, bit 0 under the native MSB-first word layout.
        # The callback clears this bit before the creator, disabling its handler.
        # Fresh acquisition still decides whether the item is already taken.
        flags[14] = 254 if acquired else 255
        result = evaluate(
            program,
            rules,
            bytearray(2 * 1024 * 1024),
            RoomRuleEpoch.Current,
            bytes(flags),
        )
        assert result.items.list_complete and result.items.items[0].state.value == state


def test_callback_writes_share_physical_aliases_between_flag_banks(rules):
    bases = list(rules[0].flag_bases)
    bases[3] = bases[0] + 4
    rules = replace(rules[0], flag_bases=tuple(bases)), rules[1]
    code = (
        interaction(0, 7, 0, 32, 1)
        + bytes((5, 3, 0, 1, 0x24, 0, 7, 0))
        + guard(bytes((4, 3, 0, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Current,
    )
    assert result.items.list_complete and len(result.items.items) == 1


def test_parameter_alternatives_keep_untouched_bits_and_read_fresh_saved_values(rules):
    code = (
        branch(bytes((0x10, 0)), interaction(0, 7, 1, 7), interaction(0, 7, 1, 8))
        + bytes((0x24, 0, 7, 0))
        + guard(bytes((4, 1, 7, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 7)
    for value, complete in ((0, False), (mask, True), (0, False)):
        ram[address - 0x80000000] = value
        result = evaluate(program, rules, ram, RoomRuleEpoch.Reentry)
        assert result.items.list_complete == complete


def test_source_context_bytes_cannot_supply_an_unreconstructed_local_bit(rules):
    bases = list(rules[0].flag_bases)
    bases[5] = rules[0].byte_variables_base + 8
    rules = replace(rules[0], flag_bases=tuple(bases)), rules[1]
    code = (
        branch(bytes((0x10, 0)), interaction(0, 7, 5, 16), interaction(0, 7, 5, 17))
        + bytes((0x24, 0, 7, 0))
        + guard(bytes((4, 5, 16, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    ram[rules[0].character_address - 0x80000000] = 128
    result = evaluate(compile_program(rules, code), rules, ram, RoomRuleEpoch.Reentry)
    assert result.unresolved_item_slots == (1,)


@pytest.mark.parametrize("synchronous", [True, False])
def test_event_dispatch_preserves_flag_writes_and_optional_execution(
    rules, synchronous
):
    writes = bytes((0x24, 0, 7, 0, 5, 4, 9, 1))
    event = indexed(
        (
            block(writes + b"\0")
            if synchronous
            else bytes((7, 6)) + writes[:4] + bytes((7, 6)) + writes[4:]
        )
        + b"\xff"
    )
    init = interaction(0, 7, 4, 9) + bytes((0x14, 0, 0, 0, 0))
    main = guard(bytes((4, 4, 9, 0)), pickup(1, 0x44, 111)) + b"\0"
    result = evaluate(
        compile_program(rules, init, main, event),
        rules,
        bytearray(2 * 1024 * 1024),
        RoomRuleEpoch.Reentry,
    )
    assert result.items.list_complete == synchronous


def test_snapshot_reads_callback_targets_and_reports_external_read_failure(rules):
    program = compile_program(
        rules, interaction(0, 7, 1, 255) + bytes((0x24, 0, 7, 0, 0))
    )
    reader = RamReader(bytearray(2 * 1024 * 1024))
    snapshot = read_rule_snapshot(rules[0], (program,), reader.read_memory)
    target = rules[0].flag(1, 255)[0]
    assert target in dict(snapshot.values)
    reader.fail_address = target
    snapshot = read_rule_snapshot(rules[0], (program,), reader.read_memory)
    assert "injected read failure" in snapshot.error and snapshot.values == ()


def test_registry_schema_requires_the_third_word_and_u16_parameters(rules):
    program = compile_program(rules, interaction(0, 7) + b"\0")
    with pytest.raises(ValueError, match="registry metadata"):
        replace(
            program.event_program,
            registry_writes=(program.event_program.registry_writes[0][:-1],),
        )
    with pytest.raises(ValueError, match="registry metadata"):
        replace(program.event_program, registry_writes=((24, 0, 1, 7, 65536),))
