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


def shared_door_markers(
    area: dict, rooms: dict, projection: Re2MapProjection
) -> list[dict]:
    """RE2-MAP-004: bind unique reciprocal doors to one shared wall marker."""
    if not area["doors"]:
        return []
    regions = {entry["id"]: entry for entry in area["rooms"]}
    definitions = {
        f"{key}:{door['offset']}": (key, door)
        for key, room in rooms.items()
        for door in room["doors"]
    }
    consumed, result = set(), []
    for marker in area["doors"]:
        if marker["id"] in consumed:
            continue
        if marker["observation_id"] not in definitions or len(marker["rooms"]) != 1:
            raise ValueError("RE2 door marker requires one known source observation")
        source, definition = definitions[marker["observation_id"]]
        target = f"{definition['stage']:02d}-{definition['room']:02x}"
        forward = [
            door
            for door in rooms[source]["doors"]
            if (door["stage"], door["room"])
            == (definition["stage"], definition["room"])
        ]
        reverse = (
            [
                door
                for door in rooms[target]["doors"]
                if (door["stage"], door["room"])
                == (rooms[source]["stage"], rooms[source]["room"])
            ]
            if target in rooms
            else []
        )
        owner = regions[marker["rooms"][0]]
        if source not in owner["room_ids"]:
            raise ValueError("RE2 door marker disagrees with its owning room")
        choices = []
        # Bit 7 accepts the trigger on every floor. Otherwise each destination
        # must land on the floor accepted by the opposite-side trigger.
        if (
            source != target
            and len(forward) == len(reverse) == 1
            and (
                reverse[0]["activation_floor"] & 0x80
                or reverse[0]["activation_floor"] == definition["floor"]
            )
            and (
                definition["activation_floor"] & 0x80
                or definition["activation_floor"] == reverse[0]["floor"]
            )
        ):
            for neighbor in area["rooms"]:
                if neighbor["id"] == owner["id"] or target not in neighbor["room_ids"]:
                    continue
                walls = set()
                for first_ring in owner["rings"]:
                    for a, b in zip(first_ring, first_ring[1:] + first_ring[:1]):
                        for second_ring in neighbor["rings"]:
                            for c, d in zip(
                                second_ring, second_ring[1:] + second_ring[:1]
                            ):
                                for axis in (0, 1):
                                    fixed = 1 - axis
                                    # Opposite winding puts the room interiors
                                    # on opposite sides of a separating wall.
                                    if (
                                        a[fixed] == b[fixed] == c[fixed] == d[fixed]
                                        and (b[axis] - a[axis]) * (d[axis] - c[axis])
                                        < 0
                                    ):
                                        low = max(
                                            min(a[axis], b[axis]), min(c[axis], d[axis])
                                        )
                                        high = min(
                                            max(a[axis], b[axis]), max(c[axis], d[axis])
                                        )
                                        if high > low:
                                            walls.add((axis, a[fixed], low, high))
                # Contours can split a straight wall into several segments.
                # Join touching spans before requiring room for a doorway.
                joined = []
                for axis, fixed, low, high in sorted(walls):
                    if (
                        joined
                        and joined[-1][:2] == (axis, fixed)
                        and low <= joined[-1][3]
                    ):
                        previous = joined.pop()
                        low, high = previous[2], max(high, previous[3])
                    joined.append((axis, fixed, low, high))
                # Native room maps distort the two trigger projections.
                # Average their estimates before snapping to the shared wall.
                points = (
                    projection.project(
                        tuple(owner["world_origin"]), *definition["center"]
                    ),
                    projection.project(
                        tuple(neighbor["world_origin"]), *reverse[0]["center"]
                    ),
                )
                center = [(points[0][axis] + points[1][axis]) / 2 for axis in (0, 1)]
                for axis, fixed, low, high in joined:
                    if high - low < 2:
                        continue
                    along = max(low, min(high, center[axis]))
                    distance = (center[1 - axis] - fixed) ** 2 + (
                        center[axis] - along
                    ) ** 2
                    midpoint = max(low + 1, min(high - 1, along))
                    segment = []
                    for shift in (-1, 1):
                        position = round(midpoint + shift, 3)
                        segment.append(
                            [position, fixed] if axis == 0 else [fixed, position]
                        )
                    choices.append((distance, neighbor["id"], segment))
        choices.sort(key=lambda choice: choice[0])
        # Keep the existing eight-map-unit placement bound. A tied wall or
        # multiple doors between the same sources cannot prove a pairing.
        paired = (
            bool(choices)
            and choices[0][0] <= 64
            and not (len(choices) > 1 and abs(choices[0][0] - choices[1][0]) < 1e-8)
        )
        observations = [marker["observation_id"]]
        region_ids, segment = marker["rooms"], marker["segment"]
        if paired:
            _, neighbor_id, segment = choices[0]
            reverse_id = f"{target}:{reverse[0]['offset']}"
            observations.append(reverse_id)
            region_ids = [owner["id"], neighbor_id]
            consumed.update(
                other["id"]
                for other in area["doors"]
                if other["observation_id"] == reverse_id
                and other["rooms"] == [neighbor_id]
            )
        result.append(
            {
                "id": marker["id"],
                "observation_ids": observations,
                "rooms": region_ids,
                "segment": segment,
            }
        )
    return result


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
        for area in document["areas"]:
            area["doors"] = shared_door_markers(area, rooms, projection)
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
