"""Explicit player-marker accuracy, independent of room completion."""

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class ApproximatePosition:
    x: float
    y: float

    def __post_init__(self) -> None:
        assert isfinite(self.x) and isfinite(self.y), "map position must be finite"


@dataclass(frozen=True)
class RoomOnlyPosition:
    reason: str

    def __post_init__(self) -> None:
        assert isinstance(self.reason, str) and self.reason, (
            "a room-only marker needs an explicit reason"
        )
