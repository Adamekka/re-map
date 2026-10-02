"""RE1-SCD-009 through 014: synthetic effects and deferred-return regressions."""

from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_scan_events import scan
from test_tracking_rules import branch, compile_program, door, evaluate, guard

from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import RuleCommand

pytest_plugins = ("test_tracking_rules",)


def test_lighting_preserves_flag_shadows_then_reaches_items_and_a_door(rules):
    code = (
        bytes((5, 6, 128, 0, 0x46))
        + bytes(43)
        + guard(bytes((4, 6, 128, 0)), pickup(0, 0x44, 111))
        + pickup(1, 0x26, 63)
        + door(2, 8, 0x34)
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert [item.aot_id for item in result.items.items] == [0, 1]
    assert len(result.doors) == 1


@pytest.mark.parametrize("mode", [0, 1, 2, 255])
def test_every_movie_mode_sets_bit_17_and_preserves_an_unrelated_shadow(rules, mode):
    code = (
        bytes((5, 5, 14, 1, 5, 5, 13, 0, 0x1E, mode, 93, 0))
        + guard(bytes((4, 5, 14, 0, 4, 5, 13, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and len(result.items.items) == 1


@pytest.mark.parametrize("index", [240, 247, 248, 255])
def test_particle_clear_zeros_both_flag_alias_bytes(rules, index):
    code = (
        bytes((5, 4, index, 0, 0x48, 0))
        + guard(bytes((4, 4, index, 1)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and len(result.items.items) == 1


@pytest.mark.parametrize("index", [224, 239])
def test_particle_clear_preserves_the_upper_record_halfword(rules, index):
    code = (
        bytes((5, 4, index, 0, 0x48, 0))
        + guard(bytes((4, 4, index, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and len(result.items.items) == 1


def test_particle_clear_and_word_tests_share_physical_shadow_bits(rules):
    layout = replace(rules[0], word_variables_base=rules[0].flag_bases[4] + 28)
    scoped = layout, rules[1]
    code = (
        bytes((0x31, 0, 255, 255, 0x48, 0))
        + guard(bytes((7, 0, 0, 0, 0, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(scoped, code), scoped, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and len(result.items.items) == 1


def test_inventory_removal_keeps_both_results_without_resetting_world_pickups(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + guard(bytes((0x2C, 0x42)), pickup(1, 0x26, 63)) + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    before = evaluate(program, rules, ram)
    assert before.unresolved_item_slots == (1,)
    assert before.items.items[0].state == RuntimeItemState.Available
    flags = bytearray([255] * 32)
    flags[14] &= ~1
    assert (
        evaluate(program, rules, ram, bytes(flags)).items.items[0].state
        == RuntimeItemState.Taken
    )
    assert evaluate(program, rules, ram).items.items == before.items.items


def test_inventory_removal_zero_result_can_end_an_unguarded_procedure(rules):
    result = evaluate(
        compile_program(rules, bytes((0x2C, 0x42)) + pickup(0, 0x44, 111) + b"\0"),
        rules,
        bytearray(2 * 1024 * 1024),
    )
    assert result.unresolved_item_slots == (0,)


@pytest.mark.parametrize("byte_index", [7, 41])
def test_inventory_compaction_forgets_overlapping_word_shadows(rules, byte_index):
    layout = replace(
        rules[0], word_variables_base=rules[0].byte_variables_base + byte_index - 1
    )
    scoped = layout, rules[1]
    code = (
        bytes((0x31, 0, 0, 1))
        + guard(bytes((0x2C, 0x42)), b"")
        + guard(bytes((7, 0, 0, 0, 0, 1)), pickup(0, 0x44, 111))
        + b"\0"
    )
    assert evaluate(
        compile_program(scoped, code), scoped, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


@pytest.mark.parametrize("op", [0x24, 0x2D])
@pytest.mark.parametrize("slot", [0, 1])
def test_document_callback_preserves_a_set_pending_bit_and_descriptor_mode(
    rules, op, slot
):
    code = (
        bytes((5, 5, 23, 0))
        + pickup(0, 0x44, 111)
        + door(1, 8, 0x34)
        + guard(bytes((op, slot, 13, 0)), b"")
        + guard(bytes((4, 5, 23, 0)), pickup(2, 0x26, 63))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert [item.aot_id for item in result.items.items] == [0, 2]
    assert len(result.doors) == 1 and result.doors[0][1] == door(1, 8, 0x34)


@pytest.mark.parametrize("op", [0x24, 0x2D])
def test_document_callback_with_unmodeled_parameter_cannot_prove_a_pending_bit(
    rules, op
):
    code = (
        pickup(0, 0x44, 111)
        + bytes((5, 5, 23, 1))
        + guard(bytes((op, 0, 13, 0)), b"")
        + guard(bytes((4, 5, 23, 1)), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (1,)
    assert [item.aot_id for item in result.items.items] == [0]


@pytest.mark.parametrize("old", [0, 1])
def test_got_item_callback_sets_bit_10_and_toggles_bit_11_before_skipping_body(
    rules, old
):
    code = (
        pickup(0, 0x44, 111)
        + bytes((5, 5, 20, int(not old), 5, 5, 21, 1))
        + branch(bytes((0x2D, 0, 13, 0)), pickup(1, 0x44, 35), pickup(1, 0x26, 63))
        + guard(bytes((4, 5, 21, 0, 4, 5, 20, old)), pickup(2, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert [(item.aot_id, item.item_type) for item in result.items.items] == [
        (0, 0x44),
        (1, 0x26),
        (2, 0x44),
    ]


def test_inventory_award_does_not_keep_a_pending_bit_shadow_when_parameter_is_unknown(
    rules,
):
    code = (
        pickup(0, 0x44, 111)
        + bytes((5, 5, 20, 1, 0x24, 0, 4, 0))
        + guard(bytes((4, 5, 20, 1)), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (1,)


@pytest.mark.parametrize("op,expected", [(0x24, 0), (0x2D, 1)])
def test_inventory_callback_preserves_a_set_bit_before_the_got_item_toggle(
    rules, op, expected
):
    code = (
        pickup(0, 0x44, 111)
        + bytes((5, 5, 20, 0))
        + guard(bytes((op, 0, 4, 0)), b"")
        + guard(bytes((4, 5, 20, expected)), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert [item.aot_id for item in result.items.items] == [0, 1]


@pytest.mark.parametrize("group,index", [(7, 111), (8, 124), (8, 129)])
def test_map_award_discards_earlier_acquisition_and_ownership_shadows(
    rules, group, index
):
    item_type = 0x53 if group == 8 and index == 129 else 0x4E
    code = (
        pickup(0, item_type, 111)
        + bytes((5, group, index, 1, 0x24, 0, 15, 0))
        + guard(bytes((4, group, index, 1)), pickup(1, 0x26, 63))
        + b"\0"
    )
    assert evaluate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (1,)


@pytest.mark.parametrize("item_type", [0x44, 0x54, 0xFF])
def test_forced_map_callback_rejects_non_map_source_types(rules, item_type):
    code = pickup(0, item_type, 111) + bytes((0x24, 0, 15, 0, 0))
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete
    assert result.items.coverage_reason == "Room script coverage is incomplete."


def test_map_award_preserves_an_unrelated_ownership_shadow(rules):
    code = (
        pickup(0, 0x4E, 111)
        + bytes((5, 8, 129, 1, 0x24, 0, 15, 0))
        + guard(bytes((4, 8, 129, 1)), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert [item.aot_id for item in result.items.items] == [0, 1]


def test_map_award_forgets_the_overlapping_scalar_word(rules):
    layout = replace(rules[0], word_variables_base=rules[0].byte_variables_base + 18)
    scoped = layout, rules[1]
    code = (
        pickup(0, 0x4E, 111)
        + bytes((0x31, 0, 0, 1, 0x24, 0, 15, 0))
        + guard(bytes((7, 0, 0, 0, 0, 1)), pickup(1, 0x26, 63))
        + b"\0"
    )
    assert evaluate(
        compile_program(scoped, code), scoped, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (1,)


@pytest.mark.parametrize("op,reaches_following", [(0x24, False), (0x2D, True)])
def test_callback_deferred_return_selects_repeat_or_exit(op, reaches_following):
    callback = bytes((op, 0, 13, 0))
    update = bytes((7, 6, 0x13, 5, 4, 0))
    operations, status = scan(bytes((0xFC, 6)) + callback + b"\xfd" + update + b"\xff")
    assert status == "clean"
    assert [opcode for _, opcode, _ in operations] == (
        [op, 0x13] if reaches_following else [op]
    )


@pytest.mark.parametrize("command", [bytes((0x1E, 1, 0, 0)), bytes((0x48, 0))])
def test_audited_movie_and_particle_returns_cannot_exit_a_deferred_repeat(command):
    code = (
        bytes((0xFC, len(command) + 2))
        + command
        + bytes((0xFD, 7, 6, 0x13, 5, 4, 0, 0xFF))
    )
    operations, status = scan(code)
    assert status == "clean"
    assert [op for _, op, _ in operations] == [command[0]]


@pytest.mark.parametrize("state_entry", [1, 2])
def test_global_ff_terminates_before_actor_or_motion_dispatch(state_entry):
    operations, status = scan(bytes((state_entry, 0xFF, 7, 6, 0x13, 5, 4, 0)))
    assert status == "clean" and operations == []


@pytest.mark.parametrize(
    "kind,args",
    [
        ("inventory-remove", (-1,)),
        ("inventory-remove", (256,)),
        ("aot-callback", (24, 13, 1)),
        ("aot-callback", (0, 2, 1)),
        ("aot-callback", (0, 13, 2)),
        ("local-flag-clear", ()),
        ("local-flag-clear", (7, 0, 1)),
        ("local-flag-clear", (4, 240, 17)),
    ],
)
def test_effect_metadata_rejects_invalid_operands(kind, args):
    with pytest.raises(ValueError):
        RuleCommand(0x100, 0x110, kind, args)
