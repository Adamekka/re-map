"""RE2-MAP-001 / RE2-PLAYER-002: pinned native selections and guarded placement."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from tracker.player_position import ApproximatePosition, RoomOnlyPosition


@dataclass(frozen=True)
class Re2MapProjection:
    world_bias: int
    units_per_pixel: int

    def __post_init__(self) -> None:
        if (
            type(self.world_bias) is not int
            or not -0x80000000 <= self.world_bias <= 0x7FFFFFFF
            or type(self.units_per_pixel) is not int
            or not 1 <= self.units_per_pixel <= 0x7FFFFFFF
        ):
            raise ValueError("invalid RE2 map projection bias or scale")

    def project(
        self, origin: tuple[int, int], x: float, z: float
    ) -> tuple[float, float]:
        # Preserve subpixel motion for the approximate tracker marker. The
        # original game's integer draw coordinates quantize this projection.
        return (
            origin[0] + (x + self.world_bias) / self.units_per_pixel,
            origin[1] - (z + self.world_bias) / self.units_per_pixel,
        )


@dataclass(frozen=True)
class Re2MapLayout:
    document: dict
    locations: dict[str, tuple[dict, ...]]
    regions: dict[tuple[str, str], dict]
    projection: Re2MapProjection

    @staticmethod
    def load(
        path: Path,
        profile_id: str,
        executable_identity: str,
        rooms: dict,
        projection: Re2MapProjection,
    ) -> Re2MapLayout:
        document = json.loads(path.read_text())
        if (
            document["schema"] != 1
            or document["profile_id"] != profile_id
            or document["executable_identity"] != executable_identity
            or document["stage_modulus"] != 256
        ):
            raise ValueError("RE2 map metadata disagrees with the pinned revision")
        regions = {}
        for area in document["areas"]:
            if area["id"] in regions or ":" in area["id"]:
                raise ValueError("invalid or duplicate RE2 map area")
            regions[area["id"]] = {}
            for entry in area["rooms"]:
                if (
                    "world_origin" not in entry
                    or type(entry["world_origin"]) is not list
                    or len(entry["world_origin"]) != 2
                    or any(
                        type(value) is not int or not -32768 <= value <= 32767
                        for value in entry["world_origin"]
                    )
                ):
                    raise ValueError("RE2 map region requires a signed native origin")
                if (
                    entry["id"] in regions[area["id"]]
                    or not entry["name"]
                    or not entry["room_ids"]
                    or any(key not in rooms for key in entry["room_ids"])
                ):
                    raise ValueError("invalid RE2 map region")
                if (
                    not entry["rings"]
                    or len(entry["rings"]) != len(entry["ring_roles"])
                    or any(len(ring) < 3 for ring in entry["rings"])
                ):
                    raise ValueError("invalid RE2 map outlines")
                points = [
                    entry["label"],
                    *(point for ring in entry["rings"] for point in ring),
                    *(
                        point
                        for segment in entry["detail_segments"]
                        for point in segment
                    ),
                ]
                if any(
                    len(point) != 2
                    or any(
                        type(v) not in (int, float) or not math.isfinite(v)
                        for v in point
                    )
                    for point in points
                ):
                    raise ValueError("invalid RE2 map coordinates")
                regions[area["id"]][entry["id"]] = entry["room_ids"]
            for door in area["doors"]:
                if any(key not in regions[area["id"]] for key in door["rooms"]):
                    raise ValueError("RE2 door lacks an owning map region")
        locations = {}
        for row in document["locations"]:
            if (
                row["room"] not in rooms
                or not 0 <= row["floor_min"] <= row["floor_max"] <= 255
            ):
                raise ValueError("invalid RE2 map selection")
            if (
                row["area"] != "unmapped"
                and row["room"] not in regions[row["area"]][row["region"]]
            ):
                raise ValueError("RE2 map selection disagrees with region ownership")
            locations.setdefault(row["room"], []).append(row)
        if set(locations) != set(rooms):
            raise ValueError("RE2 map selections must cover the room catalog")
        return Re2MapLayout(
            document,
            {key: tuple(rows) for key, rows in locations.items()},
            {
                (area["id"], entry["id"]): entry
                for area in document["areas"]
                for entry in area["rooms"]
            },
            projection,
        )

    def project(
        self, area: str, region: str, x: int, z: int
    ) -> ApproximatePosition | RoomOnlyPosition:
        if area == "unmapped":
            return RoomOnlyPosition("This room has no map outline for positioning.")
        entry = self.regions[area, region]
        px, py = self.projection.project(tuple(entry["world_origin"]), x, z)
        inside = False
        for ring in entry["rings"]:
            for first, last in zip(ring, ring[1:] + ring[:1]):
                # Even/odd filling preserves holes and disconnected floor
                # islands. A boundary point cannot establish interior placement.
                if (
                    (px - first[0]) * (last[1] - first[1])
                    == (py - first[1]) * (last[0] - first[0])
                    and min(first[0], last[0]) <= px <= max(first[0], last[0])
                    and min(first[1], last[1]) <= py <= max(first[1], last[1])
                ):
                    return RoomOnlyPosition(
                        "The position is on this room's mapped boundary."
                    )
                if (first[1] > py) != (last[1] > py) and px < (
                    (last[0] - first[0]) * (py - first[1]) / (last[1] - first[1])
                    + first[0]
                ):
                    inside = not inside
        if not inside:
            return RoomOnlyPosition(
                "The position falls outside this room's mapped floor."
            )
        return ApproximatePosition(px, py)

    def select(
        self, room: str, floor: int, value: Callable[[int, int], int]
    ) -> tuple[str, str]:
        matches = [
            row
            for row in self.locations[room]
            if row["floor_min"] <= floor <= row["floor_max"]
            and all(
                ((value(address, (mask.bit_length() + 7) // 8) & mask) == expected)
                != negate
                for address, mask, expected, negate in row["conditions"]
            )
        ]
        if len(matches) != 1:
            raise ValueError("RE2 map selection is unresolved or ambiguous")
        return matches[0]["area"], matches[0]["region"]
