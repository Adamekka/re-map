"""Pinned command behavior. Script and RAM replacements here are synthetic."""

from dataclasses import replace

import pytest
from test_cache_metadata import indexed_event, pickup
from test_tracking_rules import branch, compile_program, door, evaluate, guard

from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import RuleCommand

pytest_plugins = ("test_tracking_rules",)


@pytest.mark.parametrize(
    "setup",
    [
        bytes((0x0E, 0)),
        bytes((0x1B, 0, 0, 255)) + bytes(18),
        bytes((0x1F,)) + bytes(27),
        bytes((0x35, 0, 0, 0)),
        bytes((0x14, 0, 0, 0)),
        bytes((0x17,)) + bytes(9),
    ],
)
def test_audited_setup_continues_to_multiple_items_and_a_door(rules, setup):
    program = compile_program(
        rules,
        setup + pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + door(2, 8, 0x34) + b"\0",
        event=indexed_event(bytes((0xFF,))),
    )
    ram = bytearray(2 * 1024 * 1024)
    before = evaluate(program, rules, ram)
    assert before.items.list_complete
    assert [item.state for item in before.items.items] == [
        RuntimeItemState.Available
    ] * 2
    assert len(before.doors) == 1
    flags = bytearray([255] * 32)
    flags[14] &= ~1
    flags[4] &= ~1
    assert all(
        item.state == RuntimeItemState.Taken
        for item in evaluate(program, rules, ram, bytes(flags)).items.items
    )
    assert evaluate(program, rules, ram).items.items == before.items.items


def test_a_true_inventory_predicate_retains_both_native_outcomes(rules):
    program = compile_program(
        rules, guard(bytes((0x1A, 0x26)), pickup(0, 0x44, 111)) + b"\0"
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (0,)
    assert not result.items.list_complete


def test_an_unsupported_side_effect_cannot_authorize_clearance(rules):
    program = compile_program(
        rules, pickup(0, 0x44, 111) + bytes((0x24, 0, 2, 0)) + b"\0"
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024), bytes(32))
    assert not result.items.list_complete
    assert result.unresolved_item_slots == (0,)
    assert result.items.coverage_reason == "Room script coverage is incomplete."


def test_an_invalid_event_target_cannot_authorize_a_following_pickup(rules):
    program = compile_program(
        rules,
        bytes((0x14, 0, 0, 1)) + pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(bytes((0xFF,))),
    )
    assert not program.coverage_complete
    assert not evaluate(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


def test_an_unreachable_unsupported_effect_does_not_reject_a_known_branch(rules):
    program = compile_program(
        rules,
        guard(bytes((6, 1, 0, 10)), bytes((0x24, 0, 2, 0)))
        + pickup(0, 0x44, 111)
        + b"\0",
    )
    assert evaluate(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


def test_byte_setter_updates_character_comparison_without_writing_ram(rules):
    program = compile_program(
        rules,
        bytes((8, 9, 1, 0))
        + branch(bytes((6, 9, 0, 1)), pickup(0, 0x44, 111), pickup(0, 0x26, 63))
        + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    result = evaluate(program, rules, ram)
    assert result.items.list_complete
    assert result.items.items[0].item_type == 0x44
    assert ram[rules[0].character_address - 0x80000000] == 0


def test_word_setter_then_comparison_does_not_read_a_prior_rooms_scalar(rules):
    code = (
        bytes((0x31, 2, 0x34, 0x12))
        + branch(
            bytes((7, 0, 2, 0, 0x34, 0x12)), pickup(0, 0x44, 111), pickup(0, 0x26, 63)
        )
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert result.items.items[0].item_type == 0x44
    unresolved = compile_program(
        rules, guard(bytes((7, 0, 2, 0, 0x34, 0x12)), pickup(0, 0x44, 111)) + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    base = rules[0].word_variables_base - 0x80000000
    ram[base + 4 : base + 6] = bytes((0x34, 0x12))
    assert evaluate(unresolved, rules, ram).unresolved_item_slots == (0,)


def test_high_word_indices_remain_unresolved_even_after_a_write(rules):
    code = (
        bytes((0x31, 16, 1, 0))
        + guard(bytes((7, 0, 16, 0, 1, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    assert evaluate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


@pytest.mark.parametrize(
    "comparison,available",
    [(0, False), (1, True), (2, True), (3, False), (4, False), (5, True)],
)
def test_word_comparisons_use_unsigned_halfwords_and_ignore_packet_padding(
    rules, comparison, available
):
    code = (
        bytes((0x31, 2, 255, 255))
        + guard(bytes((7, 255, 2, comparison, 0, 128)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert bool(result.items.items) == available


def test_main_does_not_reuse_an_initializer_word_shadow(rules):
    program = compile_program(
        rules,
        bytes((0x31, 2, 1, 0)) + pickup(0, 0x44, 111) + b"\0",
        branch(
            bytes((7, 0, 2, 0, 1, 0)), bytes((0x13, 0, 4, 1)), bytes((0x13, 0, 0, 1))
        )
        + b"\0",
    )
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_word_setter_and_flag_writer_share_the_same_physical_bits(rules):
    layout = replace(rules[0], word_variables_base=rules[0].flag_bases[1] - 32)
    scoped = layout, rules[1]
    for value, kind in ((0, 0x26), (0x8000, 0x44)):
        code = (
            bytes((0x31, 16, value & 255, value >> 8))
            + branch(bytes((4, 1, 16, 0)), pickup(0, 0x44, 111), pickup(0, 0x26, 63))
            + b"\0"
        )
        result = evaluate(
            compile_program(scoped, code), scoped, bytearray(2 * 1024 * 1024)
        )
        assert result.items.list_complete
        assert result.items.items[0].item_type == kind
    # A subsequent flag clear overrides the variable write through its physical alias.
    code = (
        bytes((0x31, 16, 0, 0x80, 5, 1, 16, 1))
        + guard(bytes((4, 1, 16, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    assert (
        evaluate(
            compile_program(scoped, code), scoped, bytearray(2 * 1024 * 1024)
        ).items.items
        == ()
    )


@pytest.mark.parametrize("counter,direction", [(1, 0), (0xFFFF, 0x7FFF), (0, 123)])
def test_counter_setter_updates_words_and_preserves_direction_for_zero(
    rules, counter, direction
):
    code = (
        bytes((0x31, 1, 123, 0, 0x1C, 1, counter & 255, counter >> 8, 0, 0))
        + guard(
            bytes((7, 0, 1, 0, direction & 255, direction >> 8)), pickup(0, 0x44, 111)
        )
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert len(result.items.items) == 1


def test_quantity_copy_forgets_the_previous_character_shadow(rules):
    code = (
        bytes((8, 9, 1, 0, 0x4C, 0, 2, 9))
        + guard(bytes((6, 9, 0, 1)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (0,)


@pytest.mark.parametrize("mode", [0, 1, 2])
def test_quantity_modes_read_or_mutate_the_descriptor_slot(rules, mode):
    code = pickup(0, 0x44, 111) + bytes((0x4C, mode, 0, 8)) + b"\0"
    program = compile_program(rules, code)
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert program.mutable_slots == (() if mode == 0 else (0,))
    assert result.items.list_complete == (mode == 0)
    if mode == 0:
        assert result.items.items[0].item_type == 0x44
    else:
        assert result.unresolved_item_slots == (0,)


def test_native_quantity_default_does_not_access_a_slot_or_change_a_variable(rules):
    code = (
        bytes((8, 9, 1, 0, 0x4C, 255, 255, 9))
        + guard(bytes((6, 9, 0, 1)), pickup(0, 0x44, 111))
        + b"\0"
    )
    program = compile_program(rules, code)
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert program.mutable_slots == ()
    assert result.items.list_complete
    assert len(result.items.items) == 1


def test_unrecognized_word_comparison_retains_both_outcomes(rules):
    code = (
        bytes((0x31, 2, 1, 0))
        + guard(bytes((7, 0, 2, 6, 1, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    assert evaluate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


@pytest.mark.parametrize(
    "setup,group,index",
    [
        (bytes((0x0B, 0, 0, 0)), 6, 31),
        (bytes((0x1B, 0, 0, 255)) + bytes(18), 6, 160),
        (bytes((0x1B, 0, 0, 255)) + bytes(18), 4, 200),
        (bytes((0x2A,)) + bytes(11), 4, 224),
        (bytes((0x3D,)) + bytes(5), 4, 224),
        (bytes((0x3E,)) + bytes(1), 4, 224),
        (bytes((0x42,)) + bytes(3), 4, 224),
    ],
)
def test_native_local_effect_forgets_prior_flag_writes(rules, setup, group, index):
    code = (
        bytes((5, group, index, 0))
        + setup
        + guard(bytes((4, group, index, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (0,)


def test_camera_control_writes_the_native_flag_bit(rules):
    for setup, item_type in [
        (bytes((0x23, 1)), 0x44),
        (bytes((0x23, 0)), 0x26),
        (bytes((9, 0)), 0x44),
        (bytes((0x0A, 0)), 0x26),
    ]:
        code = (
            setup
            + branch(bytes((4, 5, 11, 0)), pickup(0, 0x44, 111), pickup(0, 0x26, 63))
            + b"\0"
        )
        result = evaluate(
            compile_program(rules, code), rules, bytearray(2 * 1024 * 1024)
        )
        assert result.items.list_complete
        assert result.items.items[0].item_type == item_type


@pytest.mark.parametrize("group", [4, 6, 9])
def test_camera_rebuild_discards_prior_local_flag_shadows(rules, group):
    code = (
        bytes((5, group, 0, 0, 9, 0))
        + guard(bytes((4, group, 0, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    assert evaluate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


@pytest.mark.parametrize("control", [1, 0x81])
def test_player_control_clears_only_its_low_bits_and_preserves_other_flags(
    rules, control
):
    code = (
        bytes((5, 5, 29, 0, 5, 5, 30, 0, 5, 5, 24, 1, 0x0F, control))
        + bytes(6)
        + guard(
            bytes((4, 5, 29, 0, 4, 5, 30, 1, 4, 5, 31, 0, 4, 5, 24, int(control == 1))),
            pickup(0, 0x44, 111),
        )
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert len(result.items.items) == 1


def test_player_control_forgets_graphics_pointer_flag_aliases(rules):
    code = (
        bytes((5, 6, 224, 0, 0x0F, 1))
        + bytes(6)
        + guard(bytes((4, 6, 224, 0)), pickup(0, 0x44, 111))
        + b"\0"
    )
    assert evaluate(
        compile_program(rules, code), rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


@pytest.mark.parametrize(
    "kind,args",
    [
        ("constant-test", (2,)),
        ("variable-write", ()),
        ("variable-write", (1, 9)),
        ("variable-write", (1, 9, 256)),
        ("variable-write", (3, 0, 1)),
        ("word-test", (0, 0, 65536)),
        ("local-flag-forget", (1, 0, 1)),
        ("local-flag-forget", (6, 255, 2)),
        ("quantity-transfer", (0, 24, 9)),
        ("quantity-transfer", (2, 24, 9)),
        ("quantity-transfer", (3, 0, 9)),
    ],
)
def test_new_semantics_reject_invalid_metadata(kind, args):
    with pytest.raises(ValueError):
        RuleCommand(0x100, 0x110, kind, args)


def test_variable_banks_are_required_and_must_match_character_layout(rules):
    with pytest.raises(ValueError, match="tracking variables"):
        replace(rules[0], byte_variables_base=0x80000201)
    with pytest.raises(ValueError, match="tracking variables"):
        replace(rules[0], word_variables_base=0x801FFE02)
