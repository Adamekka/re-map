"""Shared evaluation of trusted, source-derived RE3 map predicates."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Literal, TypeAlias

Field: TypeAlias = Literal["current_key", "phase_i8", "overlay_u16", "raw_stage_u16"]
Predicate: TypeAlias = (
    tuple[Literal["eq"], Field, int]
    | tuple[Literal["signed_lt"], Literal["phase_i8"], int]
    | tuple[Literal["bit"], int, int]
    | tuple[Literal["not"], "Predicate"]
    | tuple[Literal["all", "any"], tuple["Predicate", ...]]
)
Exclusion: TypeAlias = tuple[int, tuple[int, ...] | Literal["all"]]
FlagReader: TypeAlias = Callable[[int, int], int]


def predicate_flags(node: Predicate) -> tuple[tuple[int, int], ...]:
    """Enumerate dependencies even when evaluation would short-circuit."""
    match node:
        case ("bit", bank, index):
            return ((bank, index),)
        case ("not", condition):
            return predicate_flags(condition)
        case ("all" | "any", conditions):
            return tuple(
                pair for child in conditions for pair in predicate_flags(child)
            )
        case ("eq" | "signed_lt", _, _):
            return ()
    assert False, "pinned map predicate has an unsupported operator"


def evaluate_map_predicate(
    node: Predicate, fields: Mapping[Field, int], flag: FlagReader
) -> bool:
    """Evaluate immutable program rules after callers decode scalar widths.

    A flag reader returns a native mask, not a normalized byte. Boolean
    conversion belongs here; native byte caches must retain the raw mask.
    """
    match node:
        case ("eq", field, expected):
            assert field in fields, "pinned map predicate needs a decoded field"
            return fields[field] == expected
        case ("signed_lt", field, threshold):
            assert field in fields, "pinned map predicate needs a decoded field"
            return fields[field] < threshold
        case ("bit", bank, index):
            return bool(flag(bank, index))
        case ("not", condition):
            return not evaluate_map_predicate(condition, fields, flag)
        case ("all", conditions):
            return all(
                evaluate_map_predicate(condition, fields, flag)
                for condition in conditions
            )
        case ("any", conditions):
            return any(
                evaluate_map_predicate(condition, fields, flag)
                for condition in conditions
            )
    assert False, "pinned map predicate has an unsupported operator"


def quad_is_excluded(
    exclusions: tuple[Exclusion, ...], row: int, primitive: int
) -> bool:
    return any(
        target_row == row and (quads == "all" or primitive in quads)
        for target_row, quads in exclusions
    )
