"""Revision-bound native floor selectors and numeric map geometry."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from pathlib import Path

from games.game_profile import RoomId


@dataclass(frozen=True)
class MapLocation:
    area: str
    region: str
    outlined: bool


@dataclass(frozen=True)
class MapUnavailable:
    reason: str


@dataclass(frozen=True)
class Re1MapLayout:
    document: dict
    stage_modulus: int
    choices: dict[tuple[int, int, int], MapLocation]

    @staticmethod
    def load(path: Path, profile_id: str, executable_identity: str) -> Re1MapLayout:
        document = json.loads(path.read_text())
        try:
            if (
                document["schema"] != 1
                or document["profile_id"] != profile_id
                or document["executable_identity"] != executable_identity
                or type(document["stage_modulus"]) is not int
                or document["stage_modulus"] != 5
            ):
                raise ValueError(
                    "floor plans disagree with the configured game revision"
                )
            areas = {}
            room_aliases = {}
            for plan in document["areas"]:
                if not plan["id"] or ":" in plan["id"] or plan["id"] in areas:
                    raise ValueError("invalid or duplicate map area")
                regions = {}
                for outlined, entries in (
                    (True, plan["rooms"]),
                    (False, plan["unoutlined_rooms"]),
                ):
                    for entry in entries:
                        region = entry["id"]
                        if (
                            len(region) != 2
                            or region != f"{int(region, 16):02X}"
                            or region in regions
                        ):
                            raise ValueError("invalid or duplicate map region")
                        if not entry["name"] or len(entry["room_ids"]) != len(
                            set(entry["room_ids"])
                        ):
                            raise ValueError(
                                "map region needs a name and unique room identities"
                            )
                        if any(
                            not re.fullmatch(r"[0-9a-f]{2}-[0-9a-f]{2}", alias)
                            for alias in entry["room_ids"]
                        ):
                            raise ValueError("invalid map room identity")
                        room_aliases[plan["id"], region] = {
                            (
                                int(alias[:2], 16) % document["stage_modulus"],
                                int(alias[3:], 16),
                            )
                            for alias in entry["room_ids"]
                        }
                        if outlined:
                            if not entry["rings"] or len(entry["rings"]) != len(
                                entry["ring_roles"]
                            ):
                                raise ValueError(
                                    "map outlines need rings and explicit ring roles"
                                )
                            points = [
                                entry["label"],
                                *(point for ring in entry["rings"] for point in ring),
                                *(
                                    point
                                    for segment in entry["detail_segments"]
                                    for point in segment
                                ),
                            ]
                            if (
                                any(
                                    len(segment) != 2
                                    for segment in entry["detail_segments"]
                                )
                                or any(len(ring) < 3 for ring in entry["rings"])
                                or any(
                                    len(point) != 2
                                    or any(
                                        type(v) not in (int, float)
                                        or not math.isfinite(v)
                                        for v in point
                                    )
                                    for point in points
                                )
                            ):
                                raise ValueError("invalid map outline coordinates")
                        regions[region] = MapLocation(plan["id"], region, outlined)
                if not regions:
                    raise ValueError("map area has no room regions")
                for door in plan["doors"]:
                    if not door["rooms"] or any(
                        region not in regions or not regions[region].outlined
                        for region in door["rooms"]
                    ):
                        raise ValueError("map door needs owned floor regions")
                    if len(door["segment"]) != 2 or any(
                        len(point) != 2
                        or any(
                            type(v) not in (int, float) or not math.isfinite(v)
                            for v in point
                        )
                        for point in door["segment"]
                    ):
                        raise ValueError("invalid map door segment")
                areas[plan["id"]] = regions
            choices = {}
            defaults = set()
            for row in document["locations"]:
                stage, room = row["stage"], row["room"]
                if (
                    type(stage) is not int
                    or not 0 <= stage < document["stage_modulus"]
                    or type(room) is not int
                    or not 0 <= room <= 255
                    or (stage, room) in defaults
                ):
                    raise ValueError("invalid or duplicate native room map binding")
                defaults.add((stage, room))
                camera_locations = {camera: row["default"] for camera in range(256)}
                overridden = set()
                for rule in row["camera_overrides"]:
                    if not rule["cameras"]:
                        raise ValueError("map camera override must identify cameras")
                    for camera in rule["cameras"]:
                        if (
                            type(camera) is not int
                            or not 0 <= camera <= 255
                            or camera in overridden
                        ):
                            raise ValueError("invalid or overlapping map cameras")
                        overridden.add(camera)
                        camera_locations[camera] = rule["location"]
                for camera, location in camera_locations.items():
                    try:
                        selected = areas[location["area"]][location["region"]]
                    except KeyError as error:
                        raise ValueError(
                            "native selector has no declared map region"
                        ) from error
                    if (stage, room) not in room_aliases[
                        selected.area, selected.region
                    ]:
                        raise ValueError(
                            "native selector disagrees with its map room identity"
                        )
                    choices[stage, room, camera] = selected
            if not choices:
                raise ValueError("floor plans require native room bindings")
            return Re1MapLayout(document, document["stage_modulus"], choices)

        except (KeyError, TypeError, IndexError) as error:
            raise ValueError(f"Malformed floor-plan configuration: {error}") from error

    def select(self, room: RoomId, camera: int) -> MapLocation | MapUnavailable:
        assert type(camera) is int and 0 <= camera <= 255, "camera must fit a byte"
        selected = self.choices.get(
            (room.stage % self.stage_modulus, room.room, camera)
        )
        if selected is None:
            return MapUnavailable("This room has no floor-plan binding.")
        return selected
