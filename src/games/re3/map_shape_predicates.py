"""Candidate group-0 shape predicates for SLUS-00923. RE3-MAP-009.

These numeric source rules do not include metadata requirements, native row
visibility, room ownership or tracker visits.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal, NamedTuple, TypeAlias

Field: TypeAlias = Literal["current_key", "phase_i8", "overlay_u16"]
Predicate: TypeAlias = (
    tuple[Literal["eq", "signed_lt"], Field, int]
    | tuple[Literal["bit"], int, int]
    | tuple[Literal["not"], "Predicate"]
    | tuple[Literal["all", "any"], tuple["Predicate", ...]]
)
Exclusion: TypeAlias = tuple[int, tuple[int, ...] | Literal["all"]]


class QuadPredicate(NamedTuple):
    group: int
    phase: Literal["overlay", "early", "late"]
    condition: Predicate
    exclude_when_true: tuple[Exclusion, ...]
    exclude_when_false: tuple[Exclusion, ...]
    source_virtual: str


# This early branch also decides whether either flag-dependent alternative
# is reached, so all three families share the same condition.
GROUP1_ROW10_EARLY: Predicate = (
    "all",
    (("eq", "current_key", 0x10A), ("signed_lt", "phase_i8", 4)),
)


GROUP_ZERO_PREDICATES: tuple[QuadPredicate, ...] = (
    QuadPredicate(
        0,
        "overlay",
        ("eq", "overlay_u16", 1),
        ((0, (0,)),),
        ((0, (1,)),),
        "0x80071994..0x80071A4C",
    ),
    QuadPredicate(
        4,
        "overlay",
        ("eq", "overlay_u16", 2),
        ((3, (0,)),),
        ((3, (2, 3)),),
        "0x80071A04..0x80071AA0",
    ),
    QuadPredicate(
        0,
        "early",
        (
            "all",
            (
                ("eq", "current_key", 0x1),
                ("signed_lt", "phase_i8", 3),
            ),
        ),
        (
            (0, (0,)),
            (1, (1, 2)),
        ),
        ((1, (0,)),),
        "0x80071ACC..0x80071B40",
    ),
    QuadPredicate(
        0,
        "early",
        ("eq", "current_key", 0xD),
        ((13, (1,)),),
        (),
        "0x80071B44..0x80071B68",
    ),
    QuadPredicate(
        0,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x4),
                ("bit", 0x800D2008, 59),
            ),
        ),
        ((4, (2, 3)),),
        ((4, (1,)),),
        "0x80071B80..0x80071BD0",
    ),
    QuadPredicate(
        0,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x7),
                ("bit", 0x800D2008, 12),
            ),
        ),
        ((7, (1, 2, 3)),),
        ((7, (0,)),),
        "0x80071BD4..0x80071C34",
    ),
    QuadPredicate(
        0,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x1B),
                ("eq", "current_key", 0x1C),
                ("bit", 0x800D2008, 35),
            ),
        ),
        ((27, (1, 2, 3)),),
        (
            (27, (0,)),
            (28, (0,)),
        ),
        "0x80071C38..0x80071CB4",
    ),
    QuadPredicate(
        0,
        "late",
        ("bit", 0x800D1FA0, 141),
        ((47, (0,)),),
        ((47, (1,)),),
        "0x80071CB8..0x80071CE0",
    ),
    QuadPredicate(
        1,
        "early",
        (
            "all",
            (
                ("eq", "current_key", 0x101),
                ("signed_lt", "phase_i8", 9),
            ),
        ),
        (
            (0, (0,)),
            (1, (0, 1, 2, 3, 4, 5, 6, 11, 12, 13)),
        ),
        (
            (0, (4,)),
            (1, (7, 8, 9, 10)),
        ),
        "0x80071CE4..0x80071DC0",
    ),
    QuadPredicate(
        1,
        "early",
        ("eq", "current_key", 0x104),
        ((3, (1,)),),
        ((4, (2,)),),
        "0x80071DC4..0x80071E00",
    ),
    QuadPredicate(
        1,
        "early",
        GROUP1_ROW10_EARLY,
        (
            (10, (0, 2, 3)),
            (11, (3,)),
        ),
        ((10, (1,)),),
        "0x80071E04..0x80071EAC",
    ),
    QuadPredicate(
        1,
        "early",
        (
            "all",
            (
                ("not", GROUP1_ROW10_EARLY),
                ("bit", 0x800D1FA0, 214),
            ),
        ),
        ((10, (2,)),),
        (),
        "0x80071E50..0x80071EAC",
    ),
    QuadPredicate(
        1,
        "early",
        (
            "all",
            (
                ("not", GROUP1_ROW10_EARLY),
                ("not", ("bit", 0x800D1FA0, 214)),
            ),
        ),
        ((10, (3,)),),
        (),
        "0x80071E50..0x80071EAC",
    ),
    QuadPredicate(
        1,
        "early",
        (
            "all",
            (
                ("eq", "current_key", 0x110),
                ("not", ("signed_lt", "phase_i8", 4)),
            ),
        ),
        ((16, (0, 1)),),
        ((16, (2,)),),
        "0x80071EB0..0x80071F00",
    ),
    QuadPredicate(
        1,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x101),
                ("bit", 0x800D2008, 47),
            ),
        ),
        ((1, (1, 2, 3, 4, 5, 6, 11)),),
        ((1, (0, 12, 13)),),
        "0x80071F1C..0x80071FB0",
    ),
    QuadPredicate(
        1,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x10C),
                ("bit", 0x800D2008, 33),
            ),
        ),
        ((12, (3, 4)),),
        ((12, (0, 1, 2)),),
        "0x80071FB4..0x8007201C",
    ),
    QuadPredicate(
        1,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x10D),
                ("bit", 0x800D2008, 34),
            ),
        ),
        ((13, (2, 3)),),
        ((13, (0,)),),
        "0x80072020..0x8007207C",
    ),
    QuadPredicate(
        1,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x10F),
                ("eq", "current_key", 0x110),
                ("bit", 0x800D1FA0, 2),
                ("bit", 0x800D2008, 95),
            ),
        ),
        ((16, (5, 6)),),
        ((16, (0, 1, 2, 3)),),
        "0x80072080..0x80072108",
    ),
    QuadPredicate(
        1,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x111),
                ("eq", "current_key", 0x112),
                ("bit", 0x800D1FA0, 13),
                ("bit", 0x800D2008, 64),
            ),
        ),
        ((17, (1, 2, 3)),),
        ((17, (0,)),),
        "0x8007210C..0x80072188",
    ),
    QuadPredicate(
        1,
        "late",
        (
            "any",
            (
                ("eq", "current_key", 0x113),
                ("eq", "current_key", 0x114),
                ("bit", 0x800D2008, 36),
            ),
        ),
        ((20, (4, 5, 6)),),
        (
            (19, (0,)),
            (20, (0, 1, 2, 3)),
        ),
        "0x8007218C..0x8007221C",
    ),
    QuadPredicate(
        1,
        "late",
        ("bit", 0x800D1FA0, 141),
        ((1, (12,)),),
        ((1, (13,)),),
        "0x80072220..0x80072260",
    ),
    QuadPredicate(
        1,
        "late",
        ("bit", 0x800D1FA0, 157),
        (
            (13, (0, 2, 3)),
            (14, (0,)),
        ),
        (
            (13, (4,)),
            (14, (2,)),
        ),
        "0x80072264..0x800722D8",
    ),
    QuadPredicate(
        2,
        "early",
        ("bit", 0x800D1FA0, 200),
        ((2, (0,)),),
        ((1, (1,)),),
        "0x800722DC..0x80072324",
    ),
    QuadPredicate(
        2,
        "early",
        ("bit", 0x800D1FA0, 55),
        (
            (3, (0,)),
            (4, (0,)),
            (10, (0,)),
            (11, (0,)),
            (12, (0,)),
        ),
        (
            (3, (1,)),
            (4, (1,)),
            (10, (1,)),
            (11, (1,)),
            (12, (1,)),
        ),
        "0x80072328..0x80072434",
    ),
    QuadPredicate(
        3,
        "early",
        (
            "all",
            (
                ("eq", "current_key", 0x316),
                ("signed_lt", "phase_i8", 10),
            ),
        ),
        ((22, (0,)),),
        ((22, (1, 2)),),
        "0x80072438..0x8007248C",
    ),
    QuadPredicate(
        3,
        "early",
        ("bit", 0x800D20CC, 9),
        ((0, (8, 9, 10, 11, 12)),),
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
        "0x80072490..0x80072538",
    ),
    QuadPredicate(
        3,
        "early",
        (
            "all",
            (
                ("bit", 0x800D2028, 39),
                ("bit", 0x800D2028, 54),
            ),
        ),
        ((0, (16, 17)),),
        ((0, (18,)),),
        "0x8007253C..0x800725A0",
    ),
    QuadPredicate(
        3,
        "early",
        ("bit", 0x800D1FA0, 187),
        ((0, (0, 16, 17, 18)),),
        ((0, (13, 14, 19)),),
        "0x800725A4..0x80072608",
    ),
    QuadPredicate(
        3,
        "early",
        ("bit", 0x800D1FA0, 196),
        ((16, (4,)),),
        ((16, (5,)),),
        "0x8007260C..0x80072658",
    ),
    QuadPredicate(
        4,
        "early",
        (
            "any",
            (
                ("eq", "current_key", 0x40E),
                ("eq", "current_key", 0x40F),
                (
                    "all",
                    (
                        ("eq", "current_key", 0x40D),
                        ("bit", 0x800D1FC0, 29),
                    ),
                ),
            ),
        ),
        ((13, (0,)),),
        ((13, (1,)),),
        "0x8007265C..0x800726D4",
    ),
    QuadPredicate(
        4,
        "early",
        ("bit", 0x800D258C, 69),
        (),
        (
            (3, (1,)),
            (7, (1,)),
        ),
        "0x800726D8..0x80072728",
    ),
)


def group_zero_shape_allowed(
    group: int,
    row: int,
    primitive: int,
    current_key: int,
    phase_i8: int,
    overlay_u16: int,
    flag: Callable[[int, int], bool],
) -> bool:
    """Evaluate pinned source geometry only; callers separately bind inputs."""
    assert all(
        type(value) is int and 0 <= value <= 255 for value in (group, row, primitive)
    )
    assert type(current_key) is int and 0 <= current_key <= 0xFFFF
    assert type(phase_i8) is int and -128 <= phase_i8 <= 127
    assert type(overlay_u16) is int and 0 <= overlay_u16 <= 0xFFFF
    fields = {
        "current_key": current_key,
        "phase_i8": phase_i8,
        "overlay_u16": overlay_u16,
    }

    def evaluate(node: Predicate) -> bool:
        match node:
            case ("eq", field, expected):
                return fields[field] == expected
            case ("signed_lt", field, threshold):
                return fields[field] < threshold
            case ("bit", bank, index):
                return flag(bank, index)
            case ("not", condition):
                return not evaluate(condition)
            case ("all", conditions):
                return all(evaluate(condition) for condition in conditions)
            case ("any", conditions):
                return any(evaluate(condition) for condition in conditions)
        assert False, "pinned shape predicate has an unsupported operator"

    for family in GROUP_ZERO_PREDICATES:
        if family.group != group:
            continue
        # The native override skips only late families for map groups 0/1.
        # Overlay and early families still reject before that branch.
        if family.phase == "late" and flag(0x800CC858, 24):
            continue
        exclusions = (
            family.exclude_when_true
            if evaluate(family.condition)
            else family.exclude_when_false
        )
        if any(
            target_row == row and (quads == "all" or primitive in quads)
            for target_row, quads in exclusions
        ):
            return False
    return True
