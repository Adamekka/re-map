"""Quantity uncertainty is separate from item identity and collection state."""

from enum import Enum


# A string enum lets existing JSON snapshots encode the explicit amount state.
class ItemQuantityState(str, Enum):
    Unreconstructed = "unreconstructed"
