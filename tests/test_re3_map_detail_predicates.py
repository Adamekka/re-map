"""RE3-MAP-011: source-boundary cases using original synthetic inputs."""

import pytest

from games.re3.map_detail_predicates import (
    GROUP_ONE_SYSTEM_STYLE,
    GroupOneShapeDecision,
    group_one_shape_decision,
)


def flag_reader(bits):
    # The native helper returns the selected word mask, including masks whose
    # low byte is zero. Shape predicates consume its truth value, not a byte.
    return lambda bank, index: (
        0x80000000 >> (index & 31) if (bank, index) in bits else 0
    )


@pytest.mark.parametrize(
    "group,row,primitive,key,phase,rejected",
    [
        (0, 0, 0, 1, -128, True),
        (0, 1, 0, 1, 2, True),
        (0, 0, 0, 1, 3, False),
        (0, 0, 0, 1, 127, False),
        (0, 0, 0, 0, 2, False),
        (1, 0, 0, 0x101, -128, True),
        (1, 1, 0, 0x101, 8, True),
        (1, 0, 0, 0x101, 9, False),
        (1, 0, 0, 0x101, 127, False),
        (1, 1, 2, 0x101, 8, False),
        (1, 1, 2, 0x101, 9, True),
        (1, 10, 0, 0x10A, 3, True),
        (1, 10, 0, 0x10A, 4, False),
        (1, 10, 2, 0x10A, 3, False),
        (1, 10, 2, 0x10A, 4, True),
        (1, 16, 0, 0x110, 3, False),
        (1, 16, 0, 0x110, 4, True),
        (1, 16, 3, 0x110, 3, True),
        (1, 16, 3, 0x110, 4, False),
        (3, 22, 2, 0x316, -128, False),
        (3, 22, 2, 0x316, 9, False),
        (3, 22, 2, 0x316, 10, True),
        (3, 22, 2, 0x316, 127, True),
        (3, 22, 2, 0x315, 9, True),
    ],
)
def test_signed_phase_boundaries(group, row, primitive, key, phase, rejected):
    decision = group_one_shape_decision(
        group, row, primitive, key, phase, 0, flag_reader(set())
    )
    assert decision is (
        GroupOneShapeDecision.Reject
        if rejected
        else GroupOneShapeDecision.CheckMetadata
    )


@pytest.mark.parametrize("raw_stage", [0, 1, 2, 3, 4, 5, 0x8002, 0xFFFE, 0xFFFF])
@pytest.mark.parametrize("row,primitive", [(11, 1), (11, 2), (12, 0), (12, 255)])
def test_raw_stage_has_exact_unsigned_two_three_four_membership(
    raw_stage, row, primitive
):
    decision = group_one_shape_decision(
        1, row, primitive, 0x10C, 0, raw_stage, flag_reader(set())
    )
    assert decision is (
        GroupOneShapeDecision.Reject
        if raw_stage in (2, 3, 4)
        else GroupOneShapeDecision.CheckMetadata
    )


@pytest.mark.parametrize("primitive", [0, 3, 255])
def test_raw_stage_does_not_exclude_other_row_eleven_quads(primitive):
    assert (
        group_one_shape_decision(
            1, 11, primitive, 0x10C, 0, 2, flag_reader({(0x800D1FA0, 214)})
        )
        is GroupOneShapeDecision.CheckMetadata
    )


@pytest.mark.parametrize(
    "group,row,primitive,key,phase,bits,rejected",
    [
        (0, 13, 255, 0, 0, set(), True),
        (0, 13, 255, 0xD, 0, set(), False),
        (0, 7, 255, 0, 0, set(), True),
        (0, 7, 255, 7, 0, set(), False),
        (0, 7, 255, 0, 0, {(0x800D2008, 12)}, False),
        (0, 27, 255, 0, 0, set(), True),
        (0, 28, 255, 0x1B, 0, set(), False),
        (0, 27, 255, 0x1C, 0, set(), False),
        (0, 28, 255, 0, 0, {(0x800D2008, 35)}, False),
        (0, 38, 2, 0, 0, set(), True),
        (0, 38, 2, 0, 0, {(0x800D1FA0, 86)}, False),
        (1, 3, 1, 0x104, 0, set(), True),
        (1, 4, 0, 0, 0, set(), True),
        (1, 4, 0, 0x104, 0, set(), False),
        (1, 11, 3, 0, 0, set(), True),
        (1, 11, 3, 0, 0, {(0x800D1FA0, 214)}, False),
        (1, 1, 255, 0, 0, set(), True),
        (1, 1, 255, 0x101, 9, set(), False),
        (1, 1, 255, 0, 0, {(0x800D2008, 47)}, False),
        (1, 12, 255, 0, 0, set(), True),
        (1, 12, 255, 0, 0, {(0x800D2008, 33)}, False),
        (1, 13, 255, 0x10D, 0, set(), False),
        (1, 13, 255, 0, 0, {(0x800D2008, 34)}, False),
        (1, 16, 255, 0, 0, set(), True),
        (1, 16, 255, 0x10F, 0, set(), False),
        (1, 16, 255, 0, 0, {(0x800D1FA0, 2)}, False),
        (1, 16, 255, 0, 0, {(0x800D2008, 95)}, False),
        (1, 17, 255, 0, 0, set(), True),
        (1, 17, 255, 0x111, 0, set(), False),
        (1, 17, 255, 0x112, 0, set(), False),
        (1, 17, 255, 0, 0, {(0x800D1FA0, 13)}, False),
        (1, 17, 255, 0, 0, {(0x800D2008, 64)}, False),
        (1, 19, 255, 0, 0, set(), True),
        (1, 20, 255, 0x113, 0, set(), False),
        (1, 19, 255, 0x114, 0, set(), False),
        (1, 20, 255, 0, 0, {(0x800D2008, 36)}, False),
        (1, 0, 1, 0, 0, set(), True),
        (1, 0, 1, 0, 0, {(0x800D1FA0, 86)}, False),
        (1, 14, 1, 0, 0, {(0x800D1FA0, 157)}, True),
        (1, 14, 2, 0, 0, {(0x800D1FA0, 157)}, False),
        (1, 20, 8, 0x114, 0, set(), True),
        (1, 20, 8, 0x114, 0, {(0x800D1FA0, 96)}, False),
        (2, 1, 2, 0, 0, {(0x800D1FA0, 200)}, True),
        (2, 2, 0, 0, 0, set(), False),
        (2, 3, 255, 0, 0, {(0x800D1FA0, 55)}, True),
        (2, 4, 0, 0, 0, {(0x800D1FA0, 55)}, False),
        (3, 12, 255, 0, 0, set(), True),
        (3, 21, 255, 0, 0, {(0x800D20CC, 9)}, False),
        (3, 0, 4, 0, 0, {(0x800D2028, 39)}, True),
        (3, 0, 4, 0, 0, {(0x800D2028, 54)}, True),
        (3, 0, 4, 0, 0, {(0x800D2028, 39), (0x800D2028, 54)}, False),
        (3, 0, 3, 0, 0, {(0x800D1FA0, 187)}, True),
        (3, 0, 3, 0, 0, set(), False),
        (4, 0, 6, 0, 0, set(), True),
        (4, 0, 6, 0, 0, {(0x800D1FA0, 234)}, False),
        (4, 10, 1, 0, 0, {(0x800D1F2C, 5)}, True),
        (4, 10, 1, 0, 0, set(), False),
        (4, 10, 2, 0, 0, set(), True),
        (4, 10, 2, 0, 0, {(0x800D1F2C, 5)}, False),
        (4, 8, 0, 0, 0, {(0x800D20CC, 35)}, True),
        (4, 3, 3, 0, 0, set(), True),
        (4, 8, 1, 0x409, 0, {(0x800D1FC0, 26)}, True),
        (4, 9, 1, 0x409, 0, {(0x800D1FC0, 26)}, False),
        (4, 9, 1, 0x408, 0, {(0x800D1FC0, 26)}, True),
        (4, 12, 1, 0x40D, 0, set(), True),
        (4, 12, 1, 0x40C, 0, set(), False),
        (4, 15, 0, 0x40D, 0, {(0x800D1FC0, 4)}, True),
        (4, 15, 0, 0x40D, 0, set(), False),
        (4, 15, 1, 0x40D, 0, set(), True),
        (4, 15, 1, 0x40D, 0, {(0x800D1FC0, 4)}, False),
    ],
)
def test_source_family_targets_and_flag_alternatives(
    group, row, primitive, key, phase, bits, rejected
):
    assert group_one_shape_decision(
        group, row, primitive, key, phase, 0, flag_reader(bits)
    ) is (
        GroupOneShapeDecision.Reject
        if rejected
        else GroupOneShapeDecision.CheckMetadata
    )


@pytest.mark.parametrize(
    "group,row,primitive,key,phase,bits,expected",
    [
        (0, 0, 0, 1, 2, set(), GroupOneShapeDecision.Reject),
        (0, 13, 255, 0, 0, set(), GroupOneShapeDecision.Reject),
        (0, 7, 255, 0, 0, set(), GroupOneShapeDecision.AllowWithoutMetadata),
        (1, 0, 0, 0x101, 8, set(), GroupOneShapeDecision.Reject),
        (1, 1, 2, 0x101, 9, set(), GroupOneShapeDecision.Reject),
        (1, 11, 3, 0, 0, set(), GroupOneShapeDecision.Reject),
        (
            1,
            11,
            3,
            0,
            0,
            {(0x800D1FA0, 214)},
            GroupOneShapeDecision.AllowWithoutMetadata,
        ),
        (
            1,
            11,
            3,
            0x10A,
            3,
            {(0x800D1FA0, 214)},
            GroupOneShapeDecision.Reject,
        ),
        (1, 12, 255, 0, 0, set(), GroupOneShapeDecision.AllowWithoutMetadata),
        (1, 16, 0, 0, 0, set(), GroupOneShapeDecision.AllowWithoutMetadata),
        (1, 16, 1, 0, 0, set(), GroupOneShapeDecision.Reject),
        (1, 16, 2, 0, 0, set(), GroupOneShapeDecision.Reject),
        (1, 16, 3, 0x110, 4, set(), GroupOneShapeDecision.AllowWithoutMetadata),
        (2, 1, 2, 0, 0, {(0x800D1FA0, 200)}, GroupOneShapeDecision.Reject),
        (2, 1, 2, 0, 0, set(), GroupOneShapeDecision.CheckMetadata),
        (3, 22, 2, 0x316, 10, set(), GroupOneShapeDecision.Reject),
        (4, 0, 6, 0, 0, set(), GroupOneShapeDecision.Reject),
    ],
)
def test_system_return_preserves_earlier_rejections_and_skips_later_families(
    group, row, primitive, key, phase, bits, expected
):
    assert (
        group_one_shape_decision(
            group,
            row,
            primitive,
            key,
            phase,
            2,
            flag_reader(bits | {(0x800CC858, 24)}),
        )
        is expected
    )


@pytest.mark.parametrize("group", [5, 6, 24, 31, 255])
def test_pure_u8_domain_above_shape_switch_still_requires_metadata(group):
    # Generated high groups test the pure function's u8 domain only. They do
    # not establish valid selected records or supported game map groups.
    assert (
        group_one_shape_decision(group, 255, 255, 0xFFFF, -128, 0xFFFF, lambda *_: 1)
        is GroupOneShapeDecision.CheckMetadata
    )


@pytest.mark.parametrize(
    "position,value",
    [
        (0, -1),
        (0, 256),
        (1, -1),
        (1, 256),
        (2, -1),
        (2, 256),
        (3, -1),
        (3, 0x10000),
        (4, -129),
        (4, 128),
        (5, -1),
        (5, 0x10000),
        *[(position, True) for position in range(6)],
    ],
)
def test_decoded_scalar_widths_are_programmer_invariants(position, value):
    arguments = [0, 0, 0, 0, 0, 0]
    arguments[position] = value
    with pytest.raises(AssertionError):
        group_one_shape_decision(*arguments, flag_reader(set()))


@pytest.mark.parametrize(
    "group,row,primitive,present",
    [
        (0, 6, 3, True),
        (0, 9, 3, True),
        (0, 10, 2, True),
        (0, 12, 0, True),
        (0, 15, 0, True),
        (0, 16, 0, True),
        (0, 6, 2, False),
        (0, 16, 1, False),
        (1, 4, 2, True),
        (1, 6, 1, True),
        (1, 8, 1, True),
        (1, 8, 2, True),
        (1, 11, 2, True),
        (1, 12, 1, True),
        (1, 12, 2, True),
        (1, 12, 3, True),
        (1, 20, 1, True),
        (1, 22, 0, True),
        (1, 12, 0, False),
        (1, 16, 0, False),
    ],
)
def test_system_style_membership_has_source_targets_and_excludes_neighbours(
    group, row, primitive, present
):
    assert ((row, primitive) in GROUP_ONE_SYSTEM_STYLE[group]) is present
