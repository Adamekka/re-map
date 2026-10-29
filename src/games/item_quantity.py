"""Quantity uncertainty is separate from item identity and collection state."""

from enum import Enum


# A string enum lets existing JSON snapshots encode the explicit amount state.
class ItemQuantityState(str, Enum):
    Unreconstructed = "unreconstructed"


def parse_unit_count_item_types(values: object) -> frozenset[int]:
    if (
        type(values) is not list
        or any(type(value) is not int or not 0 <= value <= 255 for value in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError(
            "unit_count_item_types requires an explicit list of unique byte IDs"
        )
    return frozenset(values)
