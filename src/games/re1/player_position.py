"""RE1-PLAYER-003: explicitly approximate room-local world-to-map placement."""

from __future__ import annotations

import json
import math
import struct
from dataclasses import dataclass
from pathlib import Path

from games.game_profile import RoomId
from games.re1.map_layout import MapLocation, MapUnavailable, Re1MapLayout
from tracker.player_position import ApproximatePosition, RoomOnlyPosition


@dataclass(frozen=True)
class Re1PositionLayout:
    choices: dict[
        tuple[str, int], tuple[MapLocation, tuple[int, ...] | RoomOnlyPosition]
    ]
    floors: dict[tuple[str, str], frozenset[tuple[int, int]]]

    @staticmethod
    def load(path: Path, manifest: dict, maps: Re1MapLayout) -> Re1PositionLayout:
        document = json.loads(path.read_text())
        try:
            if (
                document["schema"] != 1
                or document["profile_id"] != manifest["profile_id"]
                or document["executable_identity"] != manifest["executable_identity"]
            ):
                raise ValueError("position bounds disagree with the game revision")
            floors = {}
            for area in maps.document["areas"]:
                for region in area["rooms"]:
                    rings = region["rings"]
                    if any(
                        type(v) is not int for ring in rings for p in ring for v in p
                    ) or any(
                        a[0] != b[0] and a[1] != b[1]
                        for ring in rings
                        for a, b in zip(ring, ring[1:] + ring[:1])
                    ):
                        raise ValueError(
                            "position outlines require orthogonal integer cell edges"
                        )
                    top = min(y for ring in rings for _, y in ring)
                    bottom = max(y for ring in rings for _, y in ring)
                    cells = set()
                    for y in range(top, bottom):
                        # Pair orthogonal scanline crossings once per row.
                        # Even/odd fill retains stairwells and courtyard holes.
                        crossings = sorted(
                            a[0]
                            for ring in rings
                            for a, b in zip(ring, ring[1:] + ring[:1])
                            if (a[1] > y + 0.5) != (b[1] > y + 0.5)
                        )
                        if len(crossings) % 2:
                            raise ValueError("position outline has an open scanline")
                        for left, right in zip(crossings[::2], crossings[1::2]):
                            cells.update((x, y) for x in range(left, right))
                    if not cells:
                        raise ValueError("position outline has no floor cells")
                    floors[area["id"], region["id"]] = frozenset(cells)
            expected = {row["source_rdt"]: row for row in manifest["rooms"]}
            sources = {}
            choices = {}
            for row in document["sources"]:
                name = row["source_rdt"]
                if (
                    name not in expected
                    or name in sources
                    or row["source_sha256"] != expected[name]["source_sha256"]
                    or type(row["camera_count"]) is not int
                    or not 1 <= row["camera_count"] <= 256
                ):
                    raise ValueError("invalid or mismatched position source")
                sources[name] = row
                cameras = set()
                for entry in row["regions"]:
                    if not entry["cameras"]:
                        raise ValueError("position region needs explicit cameras")
                    if entry["status"] == "approximate":
                        bounds = tuple(entry["world_bounds"])
                        if (
                            len(bounds) != 4
                            or any(
                                type(v) is not int or not -32768 <= v <= 32767
                                for v in bounds
                            )
                            or bounds[0] >= bounds[2]
                            or bounds[1] >= bounds[3]
                        ):
                            raise ValueError("invalid position coordinate bounds")
                    elif (
                        entry["status"] == "unavailable"
                        and isinstance(entry["reason"], str)
                        and entry["reason"]
                    ):
                        bounds = RoomOnlyPosition(entry["reason"])
                    else:
                        raise ValueError("invalid position availability")
                    for camera in entry["cameras"]:
                        if (
                            type(camera) is not int
                            or not 0 <= camera < row["camera_count"]
                            or camera in cameras
                        ):
                            raise ValueError("invalid or duplicate position camera")
                        cameras.add(camera)
                        location = maps.select(
                            RoomId(
                                expected[name]["room_main"], expected[name]["room_sub"]
                            ),
                            camera,
                        )
                        if not isinstance(location, MapLocation) or (
                            location.area,
                            location.region,
                        ) != (entry["area"], entry["region"]):
                            raise ValueError(
                                "position region disagrees with native map selection"
                            )
                        choices[name, camera] = location, bounds
                if cameras != set(range(row["camera_count"])):
                    raise ValueError("position source must cover every camera")
            if set(sources) != set(expected):
                raise ValueError("position bounds must cover every source RDT")
            return Re1PositionLayout(choices, floors)
        except (KeyError, TypeError, IndexError) as error:
            raise ValueError(
                f"Malformed player position configuration: {error}"
            ) from error

    def project(
        self,
        sources: tuple[str, ...],
        camera: int,
        location: MapLocation | MapUnavailable,
        data: bytes,
    ) -> ApproximatePosition | RoomOnlyPosition:
        if len(data) != 12:
            raise ValueError("player position needs a complete X/Y/Z block")
        if not isinstance(location, MapLocation) or not location.outlined:
            return RoomOnlyPosition("This room has no map outline for positioning.")
        if not sources or any(
            (source, camera) not in self.choices for source in sources
        ):
            return RoomOnlyPosition("Position is unavailable for this room camera.")
        entries = [self.choices[source, camera] for source in sources]
        if any(entry[0] != location for entry in entries):
            return RoomOnlyPosition("Position and room map bindings disagree.")
        if any(isinstance(entry[1], RoomOnlyPosition) for entry in entries):
            return RoomOnlyPosition("This room has no usable coordinate bounds.")
        bounds = {entry[1] for entry in entries}
        if len(bounds) != 1:
            return RoomOnlyPosition("This room's position bounds are unresolved.")
        left, near, right, far = bounds.pop()
        cells = self.floors[location.area, location.region]
        map_left = min(x for x, _ in cells)
        map_top = min(y for _, y in cells)
        width = max(x for x, _ in cells) + 1 - map_left
        height = max(y for _, y in cells) + 1 - map_top
        x, _, z = struct.unpack("<3i", data)
        px = map_left + (x - left) * width / (right - left)
        py = map_top + (far - z) * height / (far - near)
        if (math.floor(px), math.floor(py)) not in cells:
            # Stylized concave rooms distort a bounds projection. Constrain the
            # estimate to this room's floor, never a hole or adjacent room. The
            # 0.1-cell inset keeps the marker's center off the boundary itself.
            px, py = min(
                (
                    (min(max(px, cx + 0.1), cx + 0.9), min(max(py, cy + 0.1), cy + 0.9))
                    for cx, cy in cells
                ),
                key=lambda point: ((point[0] - px) ** 2 + (point[1] - py) ** 2, point),
            )
        return ApproximatePosition(px, py)
