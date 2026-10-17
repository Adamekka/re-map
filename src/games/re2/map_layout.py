"""Pinned RE2 native map selections, independent of in-game map ownership."""

from __future__ import annotations

import json
import math
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Re2MapLayout:
    document: dict
    locations: dict[str, tuple[dict, ...]]

    @staticmethod
    def load(
        path: Path, profile_id: str, executable_identity: str, rooms: dict
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
            document, {key: tuple(rows) for key, rows in locations.items()}
        )

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
