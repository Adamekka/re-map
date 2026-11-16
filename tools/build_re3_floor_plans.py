"""Generate numeric RE3 floor plans from the pinned owned CUE. RE3-PLAN-001.

Usage: python3 tools/build_re3_floor_plans.py /path/to/owned.cue OUTPUT.json

Room outlines are unions of native MAP_U quads, selected by the projected
camera zones of the rooms that the native map binding places on each row. The
output holds polygons, labels and door segments only: no pixels or game bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_item_table import _read_file
from list_psx_files import _read_dir, _sector_data
from map_geometry import trace_floor_cells
from output_safety import aliases_input
from re3_map_geometry import extract_map_contours

from games.re3 import EXECUTABLE_SHA256, MAP_U_SHA256
from games.re3.map_data import (
    WORLD_UNITS_PER_MAP_UNIT,
    MapPositionContext,
    compile_map_position_layout,
    resolve_native_map_position,
)
from games.re3.map_shape_predicates import group_zero_shape_allowed
from games.re3.room_data import RoomFormatFailure, decode_ard, decode_room
from games.re3.script_doors import door_creators

PROFILE_ID = "re3_jill_hard_slus00923"
EXECUTABLE_NAME = "SLUS_009.23"
MAP_PATH = "CD_DATA/ETC/MAP_U.MAP"
# Native records 7/8 replace groups 0/1 when system bit 0x80 is set. Their
# meaning is unresolved, so the floor plans use the ordinary records 0..6.
ORDINARY_RECORDS = 7
# A quad belongs to a room when its rooms' projected camera zones cover at least
# half of its drawn cells. Context drawings such as neighbouring building
# footprints stay below 0.4 on this disc; room quads are mostly fully covered.
ZONE_COVERAGE = 0.5
# Shorter detail strokes are mostly native map lettering; stair
# treads and furniture outlines are longer.
DETAIL_STROKE = 4
# Door triggers lie inside rooms. Snap only to a wall this close, in map units.
DOOR_SNAP_DISTANCE = 6
I32 = (-0x80000000, 0x7FFFFFFF)
# Inputs of the native room/row/layer binding (RE3-MAP-004), as tracker
# conditions: PS1 virtual address, mask and the context field they feed.
BINDING_FLAGS = (
    (0x800D1FB8, 0x00800000, "flag_1fb8"),
    (0x800D1FBC, 0x00004000, "flag_1fbc"),
    (0x800D1FC0, 0x00000001, "flag_1fc0"),
)
PREVIOUS_ROOM = (0x800D1F7C, 0xFFFF, 0x0503)
# One phase from each interval the native shape predicates distinguish, so a
# room drawn differently on its lower and upper levels keeps both footprints.
PHASES = (0, 3, 4, 9, 10)
# Native shape selection is evaluated as if the player stood in each row. Story
# flags default to clear. The park gate flag is set because while it is clear
# the native map draws a placeholder block instead of every park room; the
# factory flag is set because while it is clear a walkway shared by two rooms
# is hidden.
FLOOR_PLAN_FLAGS = {(0x800D20CC, 9), (0x800D258C, 69)}
# Rooms overlapping by at least this share of the smaller outline are stacked
# levels of one building, which the native map draws on the same page.
STACKED_SHARE = 0.25
# Item names start after a terminator at this executable address and are
# indexed by item type through the u16 offset table that follows them.
ITEM_NAME_BASE = 0x8009BEE4
ITEM_NAME_TABLE = 0x8009C7C0
ITEM_COUNT = 194


def read_disc(cue: Path) -> tuple[bytes, bytes, dict[str, tuple[str, bytes]]]:
    match = re.search(r'FILE\s+"([^"]+)"', cue.read_text())
    if match is None:
        raise ValueError("CUE lacks its data track")
    with (cue.parent / match[1]).open("rb") as stream:
        pvd = _sector_data(stream, 16)
        if pvd[:7] != b"\x01CD001\x01":
            raise ValueError("data track lacks an ISO9660 primary volume")
        queue = [("", *struct.unpack_from("<I", pvd, 158), *struct.unpack_from("<I", pvd, 166))]
        files = {}
        while queue:
            prefix, lba, size = queue.pop()
            for name, extent, length, is_directory in _read_dir(stream, lba, size):
                if name in (".", ".."):
                    continue
                path = f"{prefix}/{name}" if prefix else name
                if is_directory:
                    queue.append((path, extent, length))
                else:
                    files[path] = (extent, length)

        def read(path: str) -> bytes:
            if path not in files:
                raise ValueError(f"disc lacks {path}")
            return _read_file(stream, *files[path])

        executable = read(EXECUTABLE_NAME)
        if hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256:
            raise ValueError("disc executable is not the pinned SLUS-00923 revision")
        map_data = read(MAP_PATH)
        if hashlib.sha256(map_data).hexdigest() != MAP_U_SHA256:
            raise ValueError("disc map resource is not the pinned MAP_U.MAP")
        sources = {}
        for path in sorted(files):
            source = re.fullmatch(r"CD_DATA/STAGE([1-7])/R\1([0-9A-F]{2})\.ARD", path)
            if source is not None:
                key = f"{int(source[1]) - 1:02d}-{int(source[2], 16):02x}"
                sources[key] = (path, read(path))
    if len(sources) != 169:
        raise ValueError("pinned disc must contain 169 RE3 room sources")
    return executable, map_data, sources


def decode_text(data: bytes) -> str:
    """Decode the game's single-byte English text; unknown codes are errors."""
    text, index = [], 0
    while index < len(data):
        value = data[index]
        if value == 0xEA:
            # Two-byte glyph pairs draw the S.T.A.R.S. logo letters.
            logo = data[index : index + 10]
            if logo != bytes([0xEA, 0x24, 0xEA, 0x25, 0xEA, 0x26, 0xEA, 0x27, 0xEA, 0x24]):
                raise ValueError("unsupported glyph sequence in game text")
            text.append("S.T.A.R.S.")
            index += 10
            continue
        if value == 0x00:
            text.append(" ")
        elif value == 0x01:
            text.append(".")
        elif 0x0C <= value <= 0x15:
            text.append(chr(ord("0") + value - 0x0C))
        elif 0x1D <= value < 0x1D + 26:
            text.append(chr(ord("A") + value - 0x1D))
        elif 0x3D <= value < 0x3D + 26:
            text.append(chr(ord("a") + value - 0x3D))
        elif value == 0x3A:
            text.append("'")
        elif value == 0x3B:
            text.append("-")
        else:
            raise ValueError(f"unsupported game text code 0x{value:02x}")
        index += 1
    return "".join(text)


def item_names(executable: bytes) -> dict[str, str]:
    """RE3-PLAN-003: item type names from the executable's own table."""
    if hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256:
        raise ValueError("item names require the pinned executable")
    load = struct.unpack_from("<I", executable, 0x18)[0]

    def offset(address: int) -> int:
        return address - load + 0x800

    table = struct.unpack_from(f"<{ITEM_COUNT}H", executable, offset(ITEM_NAME_TABLE))
    if list(table) != sorted(set(table)) or table[0] != 0:
        raise ValueError("item name offsets must increase from zero")
    names = {}
    for item, start in enumerate(table):
        begin = offset(ITEM_NAME_BASE) + start
        end = executable.index(0xF7, begin)
        name = decode_text(executable[begin:end])
        # Item 0 is "no item"; BOTU marks slots without a released item.
        if name and name != "BOTU":
            names[str(item)] = name
    return names


def cells_from_rings(rings: list, roles: list) -> set[tuple[int, int]]:
    """Rasterize exact unit-cell contours back into their cells."""
    cells = set()
    for ring, role in zip(rings, roles):
        inside = set()
        ys = [y for _, y in ring]
        for y in range(min(ys), max(ys)):
            crossings = sorted(
                a[0]
                for a, b in zip(ring, ring[1:] + ring[:1])
                if a[0] == b[0] and min(a[1], b[1]) <= y < max(a[1], b[1])
            )
            for left, right in zip(crossings[::2], crossings[1::2]):
                inside.update((x, y) for x in range(left, right))
        cells = cells | inside if role == "outer" else cells - inside
    return cells


def floor_plan_flag(bank: int, index: int) -> int:
    return 0x80000000 >> (index % 32) if (bank, index) in FLOOR_PLAN_FLAGS else 0


def signed_area(ring: list) -> float:
    return sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1])) / 2


def within(bounds: dict, x: float, z: float) -> bool:
    return all(
        low <= value <= high
        for axis, value in (("x", x), ("z", z))
        if axis in bounds
        for low, high in [bounds[axis]]
    )


def inside_polygon(polygon: list, x: float, y: float) -> bool:
    result = False
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if (a[1] > y) != (b[1] > y) and x < (b[0] - a[0]) * (y - a[1]) / (
            b[1] - a[1]
        ) + a[0]:
            result = not result
    return result


def native_locations(layout, stage: int, room: int) -> list[dict]:
    """Partition one room's native bindings into explicit location predicates.

    The shared native resolver is the only source of branch logic. This finds
    where its outcome changes along world X/Z and the binding inputs, then
    keeps the inputs this room depends on as conditions and position bounds.
    """

    def outcome(x: int, z: int, flags: tuple[int, ...], previous: int):
        result = resolve_native_map_position(
            layout, MapPositionContext(stage, room, x, z, 0, 0, *flags, previous)
        )
        if isinstance(result, RoomFormatFailure):
            raise ValueError(f"room {stage:02d}-{room:02x}: {result.detail}")
        anchor = result.projection_anchor
        return (
            result.map_record_index,
            result.native_stage_room[1],
            result.native_layer_index,
            anchor.map_origin_xy,
            # Fold the native split-room X shift into the anchor itself.
            (
                anchor.world_origin_xz[0] - result.projection_x_adjust,
                anchor.world_origin_xz[1],
            ),
        )

    inputs = [
        *(((0, mask), name) for _, mask, name in BINDING_FLAGS),
        ((0, PREVIOUS_ROOM[2]), "previous"),
    ]
    combinations = list(itertools.product(*(values for values, _ in inputs)))
    # World positions are i16 in the room data; probe that range.
    probes = range(-0x8000, 0x8000, 0x1000)
    if (
        len(
            {
                outcome(x, z, combination[:-1], combination[-1])
                for combination in combinations
                for x in probes
                for z in probes
            }
        )
        == 1
    ):
        return [
            {
                "conditions": [],
                "position_bounds": {},
                "outcome": outcome(0, 0, combinations[0][:-1], combinations[0][-1]),
            }
        ]
    thresholds = {0: set(), 1: set()}
    samples = [*range(-0x8000, 0x8000, 0x40), 0x7FFF]
    for combination, axis, other in itertools.product(
        combinations, (0, 1), (-0x8000, 0, 0x7FFF)
    ):

        def at(value: int, axis=axis, other=other, combination=combination):
            point = (value, other) if axis == 0 else (other, value)
            return outcome(*point, combination[:-1], combination[-1])

        for low, high in itertools.pairwise(samples):
            if at(low) != at(high):
                while high - low > 1:
                    middle = (low + high) // 2
                    low, high = (middle, high) if at(middle) == at(low) else (low, middle)
                thresholds[axis].add(high)
    intervals = [
        list(zip([I32[0], *sorted(values)], [v - 1 for v in sorted(values)] + [I32[1]]))
        for values in thresholds.values()
    ]
    cells = {}
    for combination, x_range, z_range in itertools.product(combinations, *intervals):
        x, z = (max(-0x8000, min(0x7FFF, bound[0])) for bound in (x_range, z_range))
        cells[(*combination, x_range, z_range)] = outcome(
            x, z, combination[:-1], combination[-1]
        )
    # An input matters when changing it alone changes this room's outcome.
    relevant = {
        index
        for first, second in itertools.combinations(cells, 2)
        for index in range(len(first))
        if [i for i in range(len(first)) if first[i] != second[i]] == [index]
        and cells[first] != cells[second]
    }
    rows = {}
    for key, result in cells.items():
        conditions = [
            [address, mask, key[index], False]
            for index, (address, mask, _) in enumerate(BINDING_FLAGS)
            if index in relevant
        ]
        previous = len(BINDING_FLAGS)
        if previous in relevant:
            address, mask, value = PREVIOUS_ROOM
            conditions.append([address, mask, value, key[previous] != value])
        bounds = {
            axis: list(key[index])
            for axis, index in (("x", previous + 1), ("z", previous + 2))
            if index in relevant
        }
        signature = json.dumps([conditions, bounds])
        if rows.setdefault(signature, result) != result:
            raise ValueError("native binding depends on an unmodeled input")
    return [
        {"conditions": json.loads(signature)[0], "position_bounds": json.loads(signature)[1], "outcome": result}
        for signature, result in rows.items()
    ]


def project(anchor_map: tuple, anchor_world: tuple, x: float, z: float) -> tuple:
    # Continuous form of the native projection (RE3-MAP-004). The game's
    # integer truncation moves a marker by less than one map unit.
    return (
        anchor_map[0] + (x - anchor_world[0]) / WORLD_UNITS_PER_MAP_UNIT,
        anchor_map[1] - (z - anchor_world[1]) / WORLD_UNITS_PER_MAP_UNIT,
    )


def world_origin(anchor_map: tuple, anchor_world: tuple) -> list[int]:
    """Nearest integer origin for origin + world / 450 consumers."""
    return [round(value) for value in project(anchor_map, anchor_world, 0, 0)]


def polygon_cells(polygon: list) -> set[tuple[int, int]]:
    xs, ys = [p[0] for p in polygon], [p[1] for p in polygon]
    return {
        (x, y)
        for x in range(int(min(xs)) - 1, int(max(xs)) + 1)
        for y in range(int(min(ys)) - 1, int(max(ys)) + 1)
        if inside_polygon(polygon, x + 0.5, y + 0.5)
    }


def detail_segments(details: set, cells: set) -> list:
    """Thin native detail strokes, such as stair treads, as cell-centre lines."""
    segments = []
    for axis in (0, 1):
        lines = {}
        for point in details & cells:
            # A filled detail block is not a stroke along either axis.
            across = [list(point), list(point)]
            across[0][1 - axis] -= 1
            across[1][1 - axis] += 1
            if any(tuple(other) in details for other in across):
                continue
            lines.setdefault(point[1 - axis], []).append(point[axis])
        for fixed, values in sorted(lines.items()):
            values.sort()
            runs = [[values[0]]]
            for value in values[1:]:
                if value == runs[-1][-1] + 1:
                    runs[-1].append(value)
                else:
                    runs.append([value])
            for run in runs:
                if len(run) < DETAIL_STROKE:
                    continue
                segment = [[run[0] + 0.5, fixed + 0.5], [run[-1] + 0.5, fixed + 0.5]]
                segments.append(
                    segment if axis == 0 else [point[::-1] for point in segment]
                )
    return segments


def door_segment(rings: list, point: tuple) -> list | None:
    """Snap a projected trigger centre to its nearest wall edge of length >= 2."""
    best = None
    for ring in rings:
        for a, b in zip(ring, ring[1:] + ring[:1]):
            axis = 0 if a[1] == b[1] else 1
            low, high = sorted((a[axis], b[axis]))
            if high - low < 2:
                continue
            along = max(low + 1, min(high - 1, point[axis]))
            fixed = a[1 - axis]
            distance = (point[axis] - along) ** 2 + (point[1 - axis] - fixed) ** 2
            if best is None or distance < best[0]:
                best = (distance, axis, fixed, along)
    if best is None or best[0] > DOOR_SNAP_DISTANCE**2:
        return None
    _, axis, fixed, along = best
    segment = [[round(along - 1, 3), fixed], [round(along + 1, 3), fixed]]
    return segment if axis == 0 else [point[::-1] for point in segment]


def build(cue: Path, names: dict) -> dict:
    executable, map_data, sources = read_disc(cue)
    contours = extract_map_contours(map_data, executable)
    layout = compile_map_position_layout(map_data, executable)
    for result in (contours, layout):
        if isinstance(result, RoomFormatFailure):
            raise ValueError(f"native map: {result.detail}")
    rooms = {}
    for key, (path, ard) in sources.items():
        container = decode_ard(ard)
        if isinstance(container, RoomFormatFailure):
            raise ValueError(f"{path}: {container.detail}")
        rdt_object = container["objects"][8]
        rdt = ard[rdt_object["offset"] : rdt_object["offset"] + rdt_object["size"]]
        room = decode_room(rdt)
        if isinstance(room, RoomFormatFailure):
            raise ValueError(f"{path}: {room.detail}")
        doors = door_creators(rdt, room)
        if isinstance(doors, RoomFormatFailure):
            raise ValueError(f"{path}: {doors.detail}")
        stage, number = (int(part, 16) for part in key.split("-"))
        rooms[key] = {
            "room": room,
            "doors": doors,
            "locations": native_locations(layout, stage, number),
        }

    placements = {}
    for key, entry in rooms.items():
        for location in entry["locations"]:
            record, row = location["outcome"][:2]
            if record >= ORDINARY_RECORDS:
                raise ValueError("ordinary context selected an alternate record")
            placements.setdefault((record, row), []).append((key, location))

    geometry = {}
    for (record, row), members in sorted(placements.items()):
        directory = contours["records"][record]["directory"]
        if row >= len(directory):
            continue
        zone_cells = set()
        for key, location in members:
            anchor_map, anchor_world = location["outcome"][3:]
            for zone in rooms[key]["room"]["camera_zones"]:
                center = [sum(axis) / 4 for axis in zip(*zone["points_xz"])]
                # A split room projects each part through its own row only.
                if within(location["position_bounds"], *center):
                    zone_cells |= polygon_cells(
                        [project(anchor_map, anchor_world, *p) for p in zone["points_xz"]]
                    )
        scores, details = {}, set()
        for index, primitive in enumerate(directory[row]["primitive_groups"][0]):
            if primitive["contours"]["status"] != "decoded" or not any(
                group_zero_shape_allowed(
                    record, row, index, (record << 8) | row, phase, 0, floor_plan_flag
                )
                for phase in PHASES
            ):
                continue
            variant = primitive["contours"]["variants"][0]
            assert variant["requested_palette_variant"] == 0
            drawn = cells_from_rings(variant["rings"], variant["ring_roles"])
            holes = [
                -signed_area(ring)
                for ring, role in zip(variant["rings"], variant["ring_roles"])
                if role == "hole"
            ]
            # A frame around a larger empty interior outlines a whole building
            # shared by several rows, not the floor of this room.
            if not drawn or max(holes, default=0) > len(drawn):
                continue
            share = len(drawn & zone_cells) / len(drawn)
            if share < ZONE_COVERAGE:
                continue
            for cell in drawn:
                scores[cell] = max(scores.get(cell, 0), share)
            for shade in variant["shade_contours"]:
                if shade["class_index"] == 1:
                    details |= cells_from_rings(shade["rings"], shade["ring_roles"])
        if scores:
            geometry[record, row] = {
                "scores": scores,
                "details": details,
                "zones": zone_cells,
            }

    areas, locations = [], []
    region_of = {}
    for record in range(ORDINARY_RECORDS):
        layers = sorted(
            {
                location["outcome"][2]
                for (placed, _), members in placements.items()
                if placed == record
                for _, location in members
            }
        )
        for layer in layers:
            area_id = f"re3-{record}-{layer}"
            groups, unoutlined = [], []
            for placed, row in sorted(placements):
                members = [
                    (key, location)
                    for key, location in placements[placed, row]
                    if placed == record and location["outcome"][2] == layer
                ]
                if members and (record, row) in geometry:
                    groups.append({"rows": [row], "members": members, **geometry[record, row]})
                elif members:
                    # No native quad on this row is covered by its rooms.
                    unoutlined += [key for key, _ in members]
            # Rows drawing nearly the same outline show one physical room in
            # several story states or source files. Keep one shared region.
            merged = True
            while merged:
                merged = False
                for first, second in itertools.combinations(groups, 2):
                    shared = first["scores"].keys() & second["scores"].keys()
                    if len(shared) >= 0.9 * max(len(first["scores"]), len(second["scores"])):
                        first["rows"] += second["rows"]
                        first["members"] += second["members"]
                        for cell, score in second["scores"].items():
                            first["scores"][cell] = max(first["scores"].get(cell, 0), score)
                        first["details"] |= second["details"]
                        first["zones"] |= second["zones"]
                        groups.remove(second)
                        merged = True
                        break
            # Rooms sharing much of their outline are drawn on different
            # levels; both keep it. Other shared cells are wall strips and go
            # to the room whose zones best cover the quad drawing them, then
            # to a room whose zones reach the cell, then to the smaller room.
            stacked = {
                (first, second)
                for first, second in itertools.permutations(range(len(groups)), 2)
                if len(groups[first]["scores"].keys() & groups[second]["scores"].keys())
                >= STACKED_SHARE
                * min(len(groups[first]["scores"]), len(groups[second]["scores"]))
            }
            claims = {}
            for index, group in enumerate(groups):
                for cell, score in group["scores"].items():
                    claims.setdefault(cell, []).append(
                        (
                            (score, cell in group["zones"], -len(group["scores"]), -index),
                            index,
                        )
                    )
            owned = [set() for _ in groups]
            for cell, claimants in claims.items():
                winner = max(claimants)[1]
                for _, index in claimants:
                    if index == winner or (winner, index) in stacked:
                        owned[index].add(cell)
            area = {
                "id": area_id,
                "name": names["areas"][area_id],
                "rooms": [],
                "unoutlined_rooms": sorted(set(unoutlined)),
                "doors": [],
            }
            for index, group in enumerate(groups):
                cells = owned[index]
                room_ids = sorted({key for key, _ in group["members"]})
                region_id = f"{min(group['rows']):02X}"
                if not cells:
                    area["unoutlined_rooms"] += room_ids
                    continue
                rings, label = trace_floor_cells(cells)
                anchor = contours["records"][record]["projection_anchors"][min(group["rows"])]
                # Name the region after a room that is always drawn here; part
                # of a split or conditional room is a weaker witness of the place.
                primary = min(
                    (
                        bool(location["position_bounds"] or location["conditions"]),
                        location["outcome"][1],
                        key,
                    )
                    for key, location in group["members"]
                )[2]
                region = {
                    "id": region_id,
                    "name": names["rooms"][primary],
                    "room_ids": room_ids,
                    "rings": [ring for _, ring in rings],
                    "ring_roles": ["outer" if signed > 0 else "hole" for signed, _ in rings],
                    "label": [value + 0.5 for value in label],
                    "detail_segments": detail_segments(group["details"], cells),
                    "world_origin": world_origin(
                        anchor["map_origin_xy"], anchor["world_origin_xz"]
                    ),
                }
                area["rooms"].append(region)
                for key, location in group["members"]:
                    region_of[id(location)] = (area_id, region_id)
                    anchor_map, anchor_world = location["outcome"][3:]
                    for door in rooms[key]["doors"]:
                        target = f"{door.target_stage:02d}-{door.target_room:02x}"
                        if target == key or not within(
                            location["position_bounds"], *door.center
                        ):
                            continue
                        segment = door_segment(
                            region["rings"], project(anchor_map, anchor_world, *door.center)
                        )
                        if segment is None:
                            continue
                        observation = f"{key}:{door.offset}"
                        # Several location rows of one room can share a region.
                        if any(
                            marker["id"] == f"{observation}:{region_id}"
                            for marker in area["doors"]
                        ):
                            continue
                        area["doors"].append(
                            {
                                "id": f"{observation}:{region_id}",
                                "observation_id": observation,
                                "target": target,
                                "rooms": [region_id],
                                "segment": segment,
                            }
                        )
            areas.append(area)
    for key in sorted(rooms):
        for location in rooms[key]["locations"]:
            record, row, layer, anchor_map, anchor_world = location["outcome"]
            area_id, region_id = region_of.get(id(location), ("unmapped", key))
            locations.append(
                {
                    "room": key,
                    "floor_min": 0,
                    "floor_max": 255,
                    "conditions": location["conditions"],
                    "position_bounds": location["position_bounds"],
                    "area": area_id,
                    "region": region_id,
                    "world_origin": world_origin(anchor_map, anchor_world),
                    "native_anchor": {
                        "record": record,
                        "row": row,
                        "map_xy": list(anchor_map),
                        "world_xz": list(anchor_world),
                    },
                }
            )
    return {
        "schema": 1,
        "profile_id": PROFILE_ID,
        "executable_identity": f"{EXECUTABLE_NAME} SHA256 {EXECUTABLE_SHA256}",
        "research_ids": ["RE3-PLAN-001", "RE3-PLAN-002", "RE3-MAP-004", "RE3-MAP-005", "RE3-MAP-009"],
        "validation": "Candidate; see docs/research/re3/floor-plans.md",
        "door_placement": "projected-wall",
        "stage_modulus": 256,
        "world_units_per_map_unit": WORLD_UNITS_PER_MAP_UNIT,
        "areas": areas,
        "locations": locations,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--names", type=Path, default=ROOT / "data" / "re3_names.json")
    args = parser.parse_args()
    if aliases_input(args.cue, args.output):
        print("Output must differ from the input disc", file=sys.stderr)
        return 2
    try:
        document = build(args.cue, json.loads(args.names.read_text()))
    except (OSError, ValueError, KeyError) as error:
        print(f"RE3 floor plans failed: {error!r}", file=sys.stderr)
        return 2
    args.output.write_text(json.dumps(document, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
