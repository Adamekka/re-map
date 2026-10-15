"""Extract numeric Mansion 1F outlines from the owner's SLUS-00551 disc.

The indexed map separates room floor shades and door markers by palette
group. Output contains coordinates and provenance, never texture pixels
or palette colors. Runtime region selection still needs gameplay validation.

Usage: python3 tools/build_floor_plan.py GAME.CUE OUTPUT.JSON
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_item_table import _read_file
from extract_psx_file import _find
from list_psx_files import _sector_data


class DoorMarkerPolicy(Enum):
    ReciprocalHalves = "reciprocal-halves"
    FullAndBoundaryMarkers = "full-and-boundary-markers"


def extract_floor_plan(
    data: bytes, marker_policy: DoorMarkerPolicy = DoorMarkerPolicy.ReciprocalHalves
) -> dict:
    if len(data) < 20 or struct.unpack_from("<II", data) != (16, 9):
        raise ValueError("Mansion map must be an 8-bit indexed TIM")
    palette_size, _, _, palette_width, palette_height = struct.unpack_from(
        "<I4H", data, 8
    )
    image_offset = 8 + palette_size
    if (
        palette_size != 524
        or (palette_width, palette_height) != (256, 1)
        or image_offset + 12 > len(data)
    ):
        raise ValueError("Mansion map has an unsupported palette block")
    image_size, _, _, word_width, height = struct.unpack_from(
        "<I4H", data, image_offset
    )
    width = word_width * 2
    if (
        width == 0
        or height == 0
        or image_size != 12 + width * height
        or image_offset + image_size != len(data)
    ):
        raise ValueError("Mansion map has an invalid image block")
    pixels = data[image_offset + 12 :]

    def components(points):
        remaining = set(points)
        result = []
        while remaining:
            queue = [min(remaining)]
            remaining.remove(queue[0])
            for x, y in queue:
                for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                    if point in remaining:
                        remaining.remove(point)
                        queue.append(point)
            result.append(set(queue))
        return result

    rooms = []
    markers = []
    floor_owners = {}
    for room_id in range(32):
        # The game edits six CLUT entries per region and highlights entry
        # 16 + 6*region. Keeping its shade indices also includes stair detail.
        palette_base = 12 + 6 * room_id
        floor_pixels = {
            (offset % width, offset // width)
            for offset, index in enumerate(pixels)
            if palette_base + 2 <= index <= palette_base + 5
        }
        door_pixels = {
            (offset % width, offset // width)
            for offset, index in enumerate(pixels)
            if index == palette_base + 1
        }
        if not floor_pixels:
            if door_pixels:
                raise ValueError(f"Region {room_id:02X} has doors without a floor")
            continue
        floor_owners.update((point, f"{room_id:02X}") for point in floor_pixels)
        edges = set()
        for x, y in floor_pixels:
            for a, b in (
                ((x, y), (x + 1, y)),
                ((x + 1, y), (x + 1, y + 1)),
                ((x + 1, y + 1), (x, y + 1)),
                ((x, y + 1), (x, y)),
            ):
                if (b, a) in edges:
                    edges.remove((b, a))
                else:
                    edges.add((a, b))
        rings = []
        while edges:
            a, b = min(edges)
            start = a
            ring = [a]
            while True:
                edges.remove((a, b))
                if b == start:
                    break
                ring.append(b)
                successors = [end for begin, end in edges if begin == b]
                if len(successors) != 1:
                    raise ValueError(f"Region {room_id:02X} has an ambiguous contour")
                a, b = b, successors[0]
            # Collapse only collinear cell edges. Smoothing would invent room shape.
            ring = [
                point
                for i, point in enumerate(ring)
                if (point[0] - ring[i - 1][0])
                * (ring[(i + 1) % len(ring)][1] - point[1])
                != (point[1] - ring[i - 1][1])
                * (ring[(i + 1) % len(ring)][0] - point[0])
            ]
            area = (
                sum(
                    a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])
                )
                / 2
            )
            rings.append((area, ring))
        rings.sort(key=lambda entry: abs(entry[0]), reverse=True)
        if sum(area for area, _ in rings) != len(floor_pixels):
            raise ValueError(
                f"Region {room_id:02X} contour does not preserve floor area"
            )
        center = tuple(
            sum(point[axis] + 0.5 for point in floor_pixels) / len(floor_pixels)
            for axis in (0, 1)
        )
        # Concave-room centroids can land on a wall. Keep labels in the largest
        # interior space, using distance from the centroid only to break ties.
        clearance = {
            (x, y): 0
            for x, y in floor_pixels
            if any(
                point not in floor_pixels
                for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
            )
        }
        queue = sorted(clearance)
        for x, y in queue:
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if point in floor_pixels and point not in clearance:
                    clearance[point] = clearance[(x, y)] + 1
                    queue.append(point)
        label_pixel = min(
            floor_pixels,
            key=lambda point: (
                -clearance[point],
                sum((point[axis] + 0.5 - center[axis]) ** 2 for axis in (0, 1)),
                point,
            ),
        )
        rooms.append(
            {
                "id": f"{room_id:02X}",
                "rings": [ring for _, ring in rings],
                "ring_roles": ["outer" if area > 0 else "hole" for area, _ in rings],
                "label": [coordinate + 0.5 for coordinate in label_pixel],
                # Preserve interior shade geometry separately: merging it into
                # the floor contour erases the native stair treads and rails.
                "detail_segments": [],
            }
        )
        for y in range(height):
            x = 0
            while x < width:
                if pixels[y * width + x] != palette_base + 2:
                    x += 1
                    continue
                start = x
                while x < width and pixels[y * width + x] == palette_base + 2:
                    x += 1
                rooms[-1]["detail_segments"].append(
                    [[start + 0.5, y + 0.5], [x - 0.5, y + 0.5]]
                )
        for marker in components(door_pixels):
            markers.append(
                {
                    "room": f"{room_id:02X}",
                    "center": [
                        sum(point[axis] + 0.5 for point in marker) / len(marker)
                        for axis in (0, 1)
                    ],
                    "bounds": [
                        min(x for x, _ in marker),
                        min(y for _, y in marker),
                        max(x for x, _ in marker) + 1,
                        max(y for _, y in marker) + 1,
                    ],
                    "cells": len(marker),
                }
            )

    if not rooms:
        raise ValueError("Mansion map contains no room floor groups")
    doors = []
    paired = set()
    for i, marker in enumerate(markers):
        if i in paired:
            continue
        # Each door in this map has reciprocal room-owned half markers exactly
        # 1.5 pixels apart. Require that encoding instead of guessing a neighbor.
        candidates = [
            (j, other)
            for j, other in enumerate(markers)
            if j != i
            and other["room"] != marker["room"]
            and sum(
                (marker["center"][axis] - other["center"][axis]) ** 2 for axis in (0, 1)
            )
            == 2.25
        ]
        if not candidates and marker_policy is DoorMarkerPolicy.FullAndBoundaryMarkers:
            x0, y0, x1, y1 = marker["bounds"]
            if marker["cells"] != (x1 - x0) * (y1 - y0):
                raise ValueError(
                    f"Region {marker['room']} has a nonrectangular full marker"
                )
            boundaries = (
                [(x0 - 1, y) for y in range(y0, y1)],
                [(x1, y) for y in range(y0, y1)],
                [(x, y0 - 1) for x in range(x0, x1)],
                [(x, y1) for x in range(x0, x1)],
            )
            owners = []
            for boundary in boundaries:
                values = {floor_owners.get(point) for point in boundary}
                owners.append(values.pop() if len(values) == 1 else None)
            sides = [
                side for side, owner in enumerate(owners) if owner == marker["room"]
            ]
            if len(sides) != 1:
                raise ValueError(
                    f"Region {marker['room']} has an ambiguous full marker"
                )
            side = sides[0]
            opposite = side ^ 1
            other_room = owners[opposite]
            if any(
                owner is not None
                for n, owner in enumerate(owners)
                if n not in (side, opposite)
            ):
                raise ValueError(
                    f"Region {marker['room']} has an ambiguous marker wall"
                )
            # Some maps encode a complete doorway once, or an exit at the plan
            # boundary. Require a full owned floor edge; never guess a neighbor.
            axis = 1 if side < 2 else 0
            plane = marker["center"][1 - axis] if other_room else (x0, x1, y0, y1)[side]
            segment = (
                [[plane, y0], [plane, y1]] if axis == 1 else [[x0, plane], [x1, plane]]
            )
            room_ids = sorted([marker["room"]] + ([other_room] if other_room else []))
            doors.append(
                {
                    "id": "-".join(room_ids) + (f"-exit-{i}" if not other_room else ""),
                    "rooms": room_ids,
                    "segment": segment,
                    "sides": [{"room": marker["room"], "point": marker["center"]}],
                    "encoding": "full" if other_room else "boundary",
                }
            )
            paired.add(i)
            continue
        if len(candidates) != 1 or candidates[0][0] in paired:
            raise ValueError(f"Region {marker['room']} has an unpaired door marker")
        j, other = candidates[0]
        paired.update((i, j))
        room_ids = sorted((marker["room"], other["room"]))
        normal = [other["center"][axis] - marker["center"][axis] for axis in (0, 1)]
        if normal[0] != 0 and normal[1] != 0:
            raise ValueError(f"Door {'-'.join(room_ids)} has a diagonal wall normal")
        axis = 0 if normal[0] == 0 else 1
        wall_axis = 1 - axis
        plane = (marker["center"][wall_axis] + other["center"][wall_axis]) / 2
        segment = [[0.0, 0.0], [0.0, 0.0]]
        segment[0][axis] = min(marker["bounds"][axis], other["bounds"][axis])
        segment[1][axis] = max(marker["bounds"][axis + 2], other["bounds"][axis + 2])
        segment[0][wall_axis] = segment[1][wall_axis] = plane
        doors.append(
            {
                "id": "-".join(room_ids),
                "rooms": room_ids,
                "segment": segment,
                "sides": [
                    {"room": half["room"], "point": half["center"]}
                    for half in (marker, other)
                ],
            }
        )
    points = [point for room in rooms for ring in room["rings"] for point in ring]
    min_x, min_y = (min(point[axis] for point in points) for axis in (0, 1))
    max_x, max_y = (max(point[axis] for point in points) for axis in (0, 1))
    return {
        "schema": 1,
        "status": "Candidate",
        "coordinate_space": "TIM-local cell edges; X right, Y down",
        "bounds": [min_x, min_y, max_x - min_x, max_y - min_y],
        "rooms": rooms,
        "doors": sorted(doors, key=lambda door: door["id"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    cue = args.cue.read_text()
    match = re.search(r'FILE\s+"([^"]+)"', cue)
    if match is None:
        parser.error("CUE has no image FILE entry")
    with (args.cue.parent / match[1]).open("rb") as image:
        pvd = _sector_data(image, 16)
        root_lba = struct.unpack_from("<I", pvd, 158)[0]
        root_size = struct.unpack_from("<I", pvd, 166)[0]
        extent, size = _find(image, root_lba, root_size, "PSX/ITEM_M2/MAP01.TIM")
        data = _read_file(image, extent, size)
        executable_extent, executable_size = _find(
            image, root_lba, root_size, "SLUS_005.51"
        )
        executable = _read_file(image, executable_extent, executable_size)
    executable_hash = hashlib.sha256(executable).hexdigest()
    if (
        executable_hash
        != "0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6"
    ):
        parser.error("Disc executable does not match the pinned SLUS-00551 revision")
    map_hash = hashlib.sha256(data).hexdigest()
    if map_hash != "0385b147fe2a698e7ece61e82a8cfa704bfc4903b1afc884afed5955602da20f":
        parser.error("Mansion map does not match the pinned SLUS-00551 revision")
    try:
        plan = extract_floor_plan(data)
    except ValueError as error:
        parser.error(str(error))
    plan["source"] = {
        "serial": "SLUS-00551",
        "file": "PSX/ITEM_M2/MAP01.TIM",
        "lba": extent,
        "size": size,
        "sha256": map_hash,
        "executable_sha256": executable_hash,
        "method_authored": "2026-09-29; Codex; Model: GPT-6.1 Sol",
        "palette_evidence_va": ["0x80032B2C", "0x80032E84"],
        "selector_evidence_va": "0x80033798",
        "limits": [
            "Static disc and executable evidence; no map-screen gameplay validation",
            "Regions 1D and 1E are camera-dependent subspaces of Art Room and Bar",
            "Region 1F runtime identity is unresolved",
            "No game-world-to-map transform is established",
            "Door marker presence does not establish lock or availability state",
        ],
    }
    plan["region_selection"] = {
        "main": 0,
        "ordinary_sub_ids": [f"{room:02X}" for room in range(29)],
        "camera_subspaces": [
            {"room": "07", "cameras": [3, 4, 5, 6], "region": "1D"},
            {"room": "0F", "cameras": [3, 4], "region": "1E"},
        ],
        "other_map_cases": [
            {"room": "10", "cameras": [0], "map_selector": 2, "region": "1E"}
        ],
        "unresolved_region_ids": ["1F"],
    }
    item_table = json.loads(
        (
            Path(__file__).resolve().parents[1] / "data/item_table_slus00551.json"
        ).read_text()
    )
    for door in plan["doors"]:
        directions = []
        for source, target in (door["rooms"], reversed(door["rooms"])):
            sites = []
            for room in item_table["rooms"]:
                if not re.fullmatch(
                    rf"PSX/STAGE1/ROOM1{source}[01]\.RDT", room["file"]
                ):
                    continue
                for row in room.get("doors", []):
                    if row["next_stage"] == 0 and row["next_room"] == int(target, 16):
                        sites.append(
                            {
                                "file": room["file"],
                                "section": row["scd"],
                                "offset": row["addr"],
                                "raw_id": row["id"],
                                "object_id": row["id"] & 0x7F,
                            }
                        )
            directions.append({"from": source, "to": target, "rdt_sites": sites})
        door["directions"] = directions
    args.output.write_text(json.dumps(plan, indent=2) + "\n")
    print(f"rooms={len(plan['rooms'])} doors={len(plan['doors'])} -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
