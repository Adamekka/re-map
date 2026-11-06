"""Candidate group-1 shape rules for SLUS-00923. RE3-MAP-011.

These numeric source rules stop before metadata admission. They do not establish
native row visibility, room ownership or tracker visits.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal, NamedTuple

from games.re3.map_predicate import (
    Exclusion,
    FlagReader,
    Predicate,
    evaluate_map_predicate,
    quad_is_excluded,
)


class GroupOneShapeDecision(Enum):
    Reject = "reject"
    AllowWithoutMetadata = "allow-without-metadata"
    CheckMetadata = "check-metadata"


class DetailQuadPredicate(NamedTuple):
    group: int
    phase: Literal["before-system-return", "after-system-return"]
    condition: Predicate
    exclude_when_true: tuple[Exclusion, ...]
    exclude_when_false: tuple[Exclusion, ...]
    source_virtual: str


# Native groups 2-4 have no system early return, so their ordinary source
# families belong to the second phase and always run.
GROUP_ONE_PREDICATES: tuple[DetailQuadPredicate, ...] = (
    DetailQuadPredicate(
        0,
        "before-system-return",
        (
            "all",
            (("eq", "current_key", 1), ("signed_lt", "phase_i8", 3)),
        ),
        ((0, (0,)), (1, (0,))),
        (),
        "0x80072DDC..0x80072E28",
    ),
    DetailQuadPredicate(
        0,
        "before-system-return",
        ("eq", "current_key", 0xD),
        (),
        ((13, "all"),),
        "0x80072E2C..0x80072E38",
    ),
    DetailQuadPredicate(
        0,
        "after-system-return",
        ("any", (("eq", "current_key", 7), ("bit", 0x800D2008, 12))),
        (),
        ((7, "all"),),
        "0x80072E54..0x80072E80",
    ),
    DetailQuadPredicate(
        0,
        "after-system-return",
        (
            "any",
            (
                ("eq", "current_key", 0x1B),
                ("eq", "current_key", 0x1C),
                ("bit", 0x800D2008, 35),
            ),
        ),
        (),
        ((27, "all"), (28, "all")),
        "0x80072E84..0x80072EBC",
    ),
    DetailQuadPredicate(
        0,
        "after-system-return",
        ("bit", 0x800D1FA0, 86),
        (),
        ((38, (2,)),),
        "0x80072EC0..0x80072EE8",
    ),
    DetailQuadPredicate(
        1,
        "before-system-return",
        (
            "all",
            (("eq", "current_key", 0x101), ("signed_lt", "phase_i8", 9)),
        ),
        ((0, (0, 1)), (1, (0, 1))),
        ((1, (2,)),),
        "0x80072EEC..0x80072F64",
    ),
    DetailQuadPredicate(
        1,
        "before-system-return",
        ("eq", "current_key", 0x104),
        ((3, (1,)),),
        ((4, (0,)),),
        "0x80072F68..0x80072FA8",
    ),
    DetailQuadPredicate(
        1,
        "before-system-return",
        (
            "all",
            (("eq", "current_key", 0x10A), ("signed_lt", "phase_i8", 4)),
        ),
        ((10, (0, 1)), (11, (0, 3))),
        ((10, (2,)),),
        "0x80072FAC..0x80073020",
    ),
    DetailQuadPredicate(
        1,
        "before-system-return",
        ("bit", 0x800D1FA0, 214),
        (),
        ((11, (3,)),),
        "0x80073024..0x80073050",
    ),
    DetailQuadPredicate(
        1,
        "before-system-return",
        (
            "all",
            (
                ("eq", "current_key", 0x110),
                ("not", ("signed_lt", "phase_i8", 4)),
            ),
        ),
        ((16, (0, 1, 2)),),
        ((16, (3,)),),
        "0x80073054..0x800730B0",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        ("any", (("eq", "current_key", 0x101), ("bit", 0x800D2008, 47))),
        (),
        ((1, "all"),),
        "0x800730F4..0x8007311C",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        ("any", (("eq", "current_key", 0x10C), ("bit", 0x800D2008, 33))),
        (),
        ((12, "all"),),
        "0x80073120..0x80073148",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        ("any", (("eq", "current_key", 0x10D), ("bit", 0x800D2008, 34))),
        (),
        ((13, "all"),),
        "0x8007314C..0x80073174",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        (
            "any",
            (
                ("eq", "current_key", 0x10F),
                ("eq", "current_key", 0x110),
                ("bit", 0x800D1FA0, 2),
                ("bit", 0x800D2008, 95),
            ),
        ),
        (),
        ((16, "all"),),
        "0x80073178..0x800731BC",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        (
            "any",
            (
                ("eq", "current_key", 0x111),
                ("eq", "current_key", 0x112),
                ("bit", 0x800D1FA0, 13),
                ("bit", 0x800D2008, 64),
            ),
        ),
        (),
        ((17, "all"),),
        "0x800731C0..0x80073200",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        (
            "any",
            (
                ("eq", "current_key", 0x113),
                ("eq", "current_key", 0x114),
                ("bit", 0x800D2008, 36),
            ),
        ),
        (),
        ((19, "all"), (20, "all")),
        "0x80073204..0x80073238",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        ("bit", 0x800D1FA0, 86),
        (),
        ((0, (1,)),),
        "0x8007323C..0x80073260",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        ("bit", 0x800D1FA0, 157),
        ((13, "all"), (14, (1,))),
        (),
        "0x80073264..0x80073294",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        ("bit", 0x800D1FA0, 96),
        (),
        ((20, (8,)),),
        "0x80073298..0x800732C8",
    ),
    DetailQuadPredicate(
        1,
        "after-system-return",
        (
            "any",
            (
                ("eq", "raw_stage_u16", 2),
                ("eq", "raw_stage_u16", 3),
                ("eq", "raw_stage_u16", 4),
            ),
        ),
        ((11, (1, 2)), (12, "all")),
        (),
        "0x800732CC..0x8007330C",
    ),
    DetailQuadPredicate(
        2,
        "after-system-return",
        ("bit", 0x800D1FA0, 200),
        ((1, (2,)), (2, (0,))),
        (),
        "0x80073310..0x80073350",
    ),
    DetailQuadPredicate(
        2,
        "after-system-return",
        ("bit", 0x800D1FA0, 55),
        (
            (1, (1,)),
            (3, "all"),
            (4, (1,)),
            (10, "all"),
            (11, "all"),
            (12, "all"),
        ),
        (),
        "0x80073354..0x800733B8",
    ),
    DetailQuadPredicate(
        3,
        "after-system-return",
        (
            "all",
            (("eq", "current_key", 0x316), ("signed_lt", "phase_i8", 10)),
        ),
        (),
        ((22, (2,)),),
        "0x800733BC..0x800733F0",
    ),
    DetailQuadPredicate(
        3,
        "after-system-return",
        ("bit", 0x800D20CC, 9),
        (),
        (
            (1, "all"),
            (12, "all"),
            (13, "all"),
            (14, "all"),
            (15, "all"),
            (16, "all"),
            (17, "all"),
            (18, "all"),
            (19, "all"),
            (20, "all"),
            (21, "all"),
        ),
        "0x800733F4..0x80073468",
    ),
    DetailQuadPredicate(
        3,
        "after-system-return",
        ("all", (("bit", 0x800D2028, 39), ("bit", 0x800D2028, 54))),
        (),
        ((0, (4,)),),
        "0x8007346C..0x800734A4",
    ),
    DetailQuadPredicate(
        3,
        "after-system-return",
        ("bit", 0x800D1FA0, 187),
        ((0, (3, 4)),),
        (),
        "0x800734A8..0x800734D4",
    ),
    DetailQuadPredicate(
        4,
        "after-system-return",
        ("bit", 0x800D1FA0, 234),
        (),
        ((0, (6,)),),
        "0x800734D8..0x80073500",
    ),
    DetailQuadPredicate(
        4,
        "after-system-return",
        ("bit", 0x800D1F2C, 5),
        ((0, (4, 5)), (10, (1,)), (11, (0,))),
        ((0, (7, 8)), (10, (2,)), (11, (1,))),
        "0x80073504..0x800735BC",
    ),
    DetailQuadPredicate(
        4,
        "after-system-return",
        ("bit", 0x800D20CC, 35),
        ((3, (1,)), (8, (0,))),
        ((3, (3,)), (8, (2,))),
        "0x800735C0..0x80073640",
    ),
    DetailQuadPredicate(
        4,
        "after-system-return",
        ("all", (("eq", "current_key", 0x409), ("bit", 0x800D1FC0, 26))),
        ((8, (1,)), (9, (0,))),
        ((8, (3,)), (9, (1,))),
        "0x80073644..0x800736D4",
    ),
    DetailQuadPredicate(
        4,
        "after-system-return",
        ("eq", "current_key", 0x40D),
        ((12, (1,)), (13, (0,))),
        (),
        "0x800736D8..0x80073710",
    ),
    DetailQuadPredicate(
        4,
        "after-system-return",
        ("all", (("eq", "current_key", 0x40D), ("bit", 0x800D1FC0, 4))),
        ((13, (1,)), (15, (0,))),
        (),
        "0x80073714..0x80073764",
    ),
    DetailQuadPredicate(
        4,
        "after-system-return",
        (
            "all",
            (("eq", "current_key", 0x40D), ("not", ("bit", 0x800D1FC0, 4))),
        ),
        ((13, (2,)), (15, (1,))),
        (),
        "0x80073768..0x8007379C",
    ),
)


# The source's system-style branch uses only these native group 0/1 members;
# it bypasses the style metadata table entirely.
GROUP_ONE_SYSTEM_STYLE: tuple[
    frozenset[tuple[int, int]], frozenset[tuple[int, int]]
] = (
    frozenset(((6, 3), (9, 3), (10, 2), (12, 0), (15, 0), (16, 0))),
    frozenset(
        (
            (4, 2),
            (6, 1),
            (8, 1),
            (8, 2),
            (11, 2),
            (12, 1),
            (12, 2),
            (12, 3),
            (20, 1),
            (22, 0),
        )
    ),
)


def group_one_shape_decision(
    group: int,
    row: int,
    primitive: int,
    current_key: int,
    phase_i8: int,
    raw_stage_u16: int,
    flag: FlagReader,
) -> GroupOneShapeDecision:
    """Evaluate pinned source shapes; callers bind inputs and scan metadata."""
    assert all(
        type(value) is int and 0 <= value <= 255 for value in (group, row, primitive)
    )
    assert type(current_key) is int and 0 <= current_key <= 0xFFFF
    assert type(phase_i8) is int and -128 <= phase_i8 <= 127
    assert type(raw_stage_u16) is int and 0 <= raw_stage_u16 <= 0xFFFF
    fields = {
        "current_key": current_key,
        "phase_i8": phase_i8,
        "raw_stage_u16": raw_stage_u16,
    }

    def is_excluded(
        phase: Literal["before-system-return", "after-system-return"],
    ) -> bool:
        for family in GROUP_ONE_PREDICATES:
            if family.group != group or family.phase != phase:
                continue
            exclusions = (
                family.exclude_when_true
                if evaluate_map_predicate(family.condition, fields, flag)
                else family.exclude_when_false
            )
            if quad_is_excluded(exclusions, row, primitive):
                return True
        return False

    if is_excluded("before-system-return"):
        return GroupOneShapeDecision.Reject
    # This branch returns from the native function before later shape families
    # and metadata, but only for native groups 0/1.
    if flag(0x800CC858, 24):
        if group == 0:
            return GroupOneShapeDecision.AllowWithoutMetadata
        if group == 1:
            if row == 16 and primitive in (1, 2):
                return GroupOneShapeDecision.Reject
            return GroupOneShapeDecision.AllowWithoutMetadata
    if is_excluded("after-system-return"):
        return GroupOneShapeDecision.Reject
    return GroupOneShapeDecision.CheckMetadata
