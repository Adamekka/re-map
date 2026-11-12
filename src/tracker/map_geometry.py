"""Validated ordered map paths shared by extraction and publication."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class MapPath:
    points: tuple[tuple[float, float], ...]

    def __post_init__(self) -> None:
        try:
            if (
                type(self.points) is not tuple
                or len(self.points) < 2
                or any(
                    type(point) is not tuple
                    or len(point) != 2
                    or any(
                        type(v) not in (int, float) or not math.isfinite(v)
                        for v in point
                    )
                    for point in self.points
                )
                or len(set(self.points)) != len(self.points)
            ):
                raise ValueError("invalid map path coordinates or repeated points")
            if not math.isfinite(self.length) or any(
                not 0 < (b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2 < math.inf
                for a, b in zip(self.points, self.points[1:])
            ):
                raise ValueError("map path edge lengths must be finite and nonzero")
        except OverflowError as error:
            raise ValueError("map path coordinates exceed finite geometry") from error

    @property
    def length(self) -> float:
        return sum(math.dist(a, b) for a, b in zip(self.points, self.points[1:]))

    def section(self, start: float, end: float) -> MapPath:
        if not 0 <= start < end <= self.length:
            raise ValueError("map path section exceeds its contour")
        points = []
        cumulative = 0.0
        for a, b in zip(self.points, self.points[1:]):
            length = math.dist(a, b)
            for at in sorted({start, end, cumulative, cumulative + length}):
                if start <= at <= end and cumulative <= at <= cumulative + length:
                    t = (at - cumulative) / length
                    # Keep the existing catalog precision when trimming paths.
                    point = tuple(round(a[k] + t * (b[k] - a[k]), 3) for k in (0, 1))
                    if not points or points[-1] != point:
                        points.append(point)
            cumulative += length
        return MapPath(tuple(points))

    @property
    def center(self) -> tuple[float, float]:
        along = self.length / 2
        for a, b in zip(self.points, self.points[1:]):
            length = math.dist(a, b)
            if along <= length:
                return tuple(a[k] + along * (b[k] - a[k]) / length for k in (0, 1))
            along -= length
        raise AssertionError("a validated path must contain its arclength midpoint")

    def distance_squared(self, point: tuple[float, float]) -> float:
        distances = []
        for a, b in zip(self.points, self.points[1:]):
            dx, dy = b[0] - a[0], b[1] - a[1]
            t = max(
                0,
                min(
                    1,
                    ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy)
                    / (dx * dx + dy * dy),
                ),
            )
            distances.append(
                (point[0] - a[0] - t * dx) ** 2 + (point[1] - a[1] - t * dy) ** 2
            )
        return min(distances)

    def on_boundary(self, rings: list) -> bool:
        def on_ring(ring: list) -> bool:
            for a, b in zip(self.points, self.points[1:]):
                dx, dy = b[0] - a[0], b[1] - a[1]
                length_squared = dx * dx + dy * dy
                spans = []
                for c, d in zip(ring, ring[1:] + ring[:1]):
                    if any((p[0] - a[0]) * dy != (p[1] - a[1]) * dx for p in (c, d)):
                        continue
                    low, high = sorted(
                        ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy for p in (c, d))
                    )
                    spans.append((max(0, low), min(length_squared, high)))
                covered = 0
                for low, high in sorted(spans):
                    if low > covered:
                        break
                    covered = max(covered, high)
                if covered < length_squared:
                    return False
            return True

        return any(on_ring(ring) for ring in rings)


def door_path(marker: dict) -> MapPath:
    """Require exactly one explicit geometry alternative, before publication."""
    kinds = {"segment", "polyline"} & marker.keys()
    if len(kinds) != 1:
        raise ValueError("map door requires exactly one segment or polyline")
    kind = kinds.pop()
    points = marker[kind]
    if type(points) is not list or any(type(p) is not list for p in points):
        raise ValueError("invalid map door path representation")
    path = MapPath(tuple(tuple(p) for p in points))
    if (kind == "segment" and len(points) != 2) or (
        kind == "polyline" and len(points) < 3
    ):
        raise ValueError("invalid map door segment or polyline")
    if kind == "polyline":
        directions = [
            (b[0] - a[0], b[1] - a[1]) for a, b in zip(path.points, path.points[1:])
        ]
        if any(x != 0 and y != 0 for x, y in directions) or any(
            len({1 if d[axis] > 0 else -1 for d in directions if d[axis]}) > 1
            for axis in (0, 1)
        ):
            raise ValueError(
                "map door polyline must follow a monotone orthogonal contour"
            )
    return path
