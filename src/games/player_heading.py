"""Shared twelve-bit yaw conversion with explicit map orientation."""

import math
from typing import Literal


def heading_degrees(
    yaw: int, offset_degrees: float, direction: Literal[-1, 1]
) -> float:
    assert type(yaw) is int and 0 <= yaw <= 0xFFFF, "yaw must be an unsigned halfword"
    assert direction in (-1, 1), "heading direction must be -1 or 1"
    assert math.isfinite(offset_degrees), "heading offset must be finite"
    # Native trig tables repeat every 4096 units even when stored yaw wraps
    # outside that phase range. Preserve the caller's raw value separately.
    return (offset_degrees + direction * (yaw & 0xFFF) * 360 / 4096) % 360
