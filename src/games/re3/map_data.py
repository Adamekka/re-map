"""Candidate MAP_U geometry and native row binding for SLUS-00923.

RE3-MAP-001/002/003/004 supply numeric source metadata and projection,
not room contours, floor labels, ownership, visits, items or completion.
No image is exported.
"""

from __future__ import annotations

import hashlib
import struct

from games.player_heading import heading_degrees
from games.re3 import EXECUTABLE_SHA256
from games.re3.capture_data import capture_failure
from games.re3.map_layer import native_map_layer
from games.re3.room_data import RoomFormatFailure, decode_map

# Native signed division at 0x800706DC projects 450 world units to one map unit.
WORLD_UNITS_PER_MAP_UNIT = 450


def decode_map_primitives(data: bytes, executable: bytes) -> dict | RoomFormatFailure:
    """Export numeric quad geometry after checking the actual executable bytes.

    Offsets in the result and map failures are MAP-file byte offsets. An
    identity failure refers to the whole supplied executable, at offset zero.
    Destination edges are directed native map coordinates before pan and zoom.
    """
    if hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256:
        return RoomFormatFailure(
            "map-identity",
            0,
            "executable does not match the pinned SLUS-00923 map decoder",
        )
    result = decode_map(data)
    if isinstance(result, RoomFormatFailure):
        return result
    for record in result["records"]:
        section_start = record["offset"] + record["sections"][0]["offset"]
        for row in record["directory"]:
            consumed = sum(row["attributes"]) * 12
            if consumed > row["bounded_size"]:
                return RoomFormatFailure(
                    "map-primitives",
                    section_start + 8 + row["index"] * 8,
                    "counted MAP quads exceed their bounded payload",
                )
            groups, offset = [], section_start + row["offset"]
            for count in row["attributes"]:
                primitives = []
                for _ in range(count):
                    u0, v0, u1, v1, x, y, *style = struct.unpack_from(
                        "<4B2h4B", data, offset
                    )
                    # RE3-MAP-002: the native renderer adds one to signed
                    # endpoint differences. Wrapping a negative width at 256
                    # would change an actual quad in record 3, row 0.
                    primitives.append(
                        {
                            "offset": offset,
                            "uv_inclusive": [u0, v0, u1, v1],
                            "destination_xyxy": [
                                x,
                                y,
                                x + u1 - u0 + 1,
                                y + v1 - v0 + 1,
                            ],
                            "style_bytes": style,
                        }
                    )
                    offset += 12
                groups.append(primitives)
            row["primitive_groups"] = groups
            # A zero-count alias can bound another row's real payload. Keep
            # unconsumed bytes explicit; an empty draw list is not an empty room.
            row["unconsumed_size"] = row["bounded_size"] - consumed
    return {
        "schema": "re3-static-map-primitives-v1",
        "evidence_kind": "offline-only",
        "executable_sha256": EXECUTABLE_SHA256,
        "geometry_kind": "textured-quads",
        "coordinate_space": "native map coordinates before pan and zoom; X right, Y down",
        "room_floor_binding": "unresolved",
        **result,
    }


def decode_map_layout(data: bytes, executable: bytes) -> dict | RoomFormatFailure:
    """Decode RE3-MAP-003 numeric anchors and the ordered native remap table."""
    result = decode_map_primitives(data, executable)
    if isinstance(result, RoomFormatFailure):
        return result
    # The native size table has nine records. Extra input must not legitimize
    # an otherwise out-of-range alternate-map selector.
    if len(result["records"]) != 9:
        return RoomFormatFailure(
            "map-layout", 0, "native projection requires nine MAP records"
        )
    for record in result["records"]:
        section = record["sections"][1]
        start = record["offset"] + section["offset"]
        size = section["size"]
        if size < 32:
            return RoomFormatFailure("map-layout", start, "truncated projection header")
        offsets = struct.unpack_from("<8I", data, start)
        if (
            offsets[0] != 32
            or any(not 32 <= value <= size for value in offsets[:5])
            or list(offsets[:5]) != sorted(set(offsets[:5]))
            or (offsets[1] - offsets[0]) % 8
            or offsets[2] - offsets[1] < 8
        ):
            return RoomFormatFailure(
                "map-layout", start, "unsupported projection extents"
            )
        anchors = []
        for index, offset in enumerate(range(offsets[0], offsets[1], 8)):
            map_x, map_y, world_x, world_z = struct.unpack_from(
                "<4h", data, start + offset
            )
            anchors.append(
                {
                    "index": index,
                    "offset": start + offset,
                    "map_origin_xy": [map_x, map_y],
                    "world_origin_xz": [world_x, world_z],
                }
            )
        record["projection_anchors"] = anchors
        header = data[start + offsets[1] : start + offsets[1] + 8]
        record["layer_metadata"] = {
            "offset": start + offsets[1],
            "raw_prefix": list(header),
            "layered": bool(header[4]),
            "layer_count": header[5],
        }
        record["projection_header_words"] = list(offsets)

    # The pinned native loop consumes ordered four-byte rows until its sentinel.
    # Keeping order matters: a later row can remap an earlier row's destination.
    start = 0x800 + 0x800A0430 - 0x80010000
    # This revision stores 49 remaps and a sentinel in this 200-byte span.
    end = start + 200
    if end > len(executable):
        return RoomFormatFailure(
            "map-layout-executable", start, "truncated room remap table"
        )
    remaps = []
    for offset in range(start, end, 4):
        source_stage, source_room, target_stage, target_room = executable[
            offset : offset + 4
        ]
        if source_stage == 0xFF:
            break
        if source_stage > 6 or target_stage > 6:
            return RoomFormatFailure(
                "map-layout-executable", offset, "unsupported room remap stage"
            )
        remaps.append(
            {
                "source": [source_stage, source_room],
                "target": [target_stage, target_room],
            }
        )
    else:
        return RoomFormatFailure(
            "map-layout-executable", start, "missing room remap terminator"
        )
    return {
        **result,
        "schema": "re3-static-map-layout-v1",
        "room_remaps": remaps,
        "world_units_per_map_unit": WORLD_UNITS_PER_MAP_UNIT,
        "floor_labels": "unresolved",
    }


def decode_native_map_position(
    data: bytes, executable: bytes, ram: bytes
) -> dict | RoomFormatFailure:
    """Resolve Candidate native row/layer/coordinates from an explicit snapshot.

    This does not check the loaded RDT, admit gameplay, record visits or identify
    room contours. Capture failures use RAM offsets; layout failures use the
    MAP or executable byte space indicated by their kind.
    """
    layout = decode_map_layout(data, executable)
    if isinstance(layout, RoomFormatFailure):
        return layout
    failure = capture_failure(executable, ram)
    if failure is not None:
        return failure
    stage, room = struct.unpack_from("<2h", ram, 0xD1F76)
    if not 0 <= stage <= 6 or not 0 <= room <= 255:
        return RoomFormatFailure(
            "map-context", 0xD1F76, "unsupported source stage or room"
        )
    world_x = struct.unpack_from("<i", ram, 0xCCBF8)[0]
    world_z = struct.unpack_from("<i", ram, 0xCCC00)[0]
    facing = struct.unpack_from("<H", ram, 0xCCC32)[0]
    system = struct.unpack_from("<I", ram, 0xCC858)[0]
    flag_1fb8 = struct.unpack_from("<I", ram, 0xD1FB8)[0]
    flag_1fc0 = struct.unpack_from("<I", ram, 0xD1FC0)[0]
    # RE3-MAP-004: 0x80073CCC returns early for three cases before its table
    # loop. Preserve that order rather than applying every alias unconditionally.
    split_stage1_room0f = (stage, room) == (1, 0x0F) and world_x >= -0x2276
    split_stage3_room15 = (stage, room) == (3, 0x15) and world_x >= 0x320
    native_stage, native_room = stage, room
    if split_stage1_room0f:
        native_room = 0x10
    elif split_stage3_room15:
        native_room = 0x11
    elif (stage, room) == (4, 2) and flag_1fc0 & 1:
        native_room = 0x11
    else:
        if (
            (stage, room) == (2, 0x17)
            and world_z >= -0x2C24
            and not flag_1fb8 & 0x00800000
        ):
            native_room = 2
        if native_stage >= 5:
            # Raw stages 5/6 share maps 0/1. Later table destinations 5/6 are
            # native map groups and must not undergo this folding again.
            native_stage -= 5
        for remap in layout["room_remaps"]:
            if [native_stage, native_room] == remap["source"]:
                native_stage, native_room = remap["target"]
    record_index = native_stage + 7 if system & 0x80 else native_stage
    if record_index >= len(layout["records"]):
        return RoomFormatFailure(
            "map-context", 0xCC858, "native map record is unavailable"
        )
    record = layout["records"][record_index]
    if native_room >= min(len(record["directory"]), len(record["projection_anchors"])):
        return RoomFormatFailure(
            "map-context", 0xD1F78, "native map row is outside its source tables"
        )
    # The native layer selector at 0x80073BC8 uses these row ranges. Floor
    # names remain unresolved, so the result retains numeric layer indices.
    layer = native_map_layer(native_stage, native_room)
    if record["layer_metadata"]["layered"]:
        if (stage, native_room) == (4, 3):
            flag_1fbc = struct.unpack_from("<I", ram, 0xD1FBC)[0]
            previous = struct.unpack_from("<H", ram, 0xD1F7C)[0]
            layer = 0 if flag_1fbc & 0x4000 and previous != 0x503 else 1
        if layer >= record["layer_metadata"]["layer_count"]:
            return RoomFormatFailure(
                "map-context", 0xD1F78, "native layer is outside the map metadata"
            )
    else:
        # Native code ignores layer counts on unlayered maps; zero is not a
        # missing count that should silently become an invented single floor.
        layer = 0
    adjusted_x = world_x
    if split_stage1_room0f:
        adjusted_x += 0x251D
    elif split_stage3_room15:
        adjusted_x -= 0x2328
    anchor = record["projection_anchors"][native_room]
    # SUBU wraps to signed 32 bits; the native divide truncates toward zero,
    # whereas Python's negative // rounds down. Keep both semantics explicit.
    deltas = [
        (value - origin + 0x80000000) % 0x100000000 - 0x80000000
        for value, origin in zip([adjusted_x, world_z], anchor["world_origin_xz"])
    ]
    dx, dz = [
        value // WORLD_UNITS_PER_MAP_UNIT
        if value >= 0
        else -(-value // WORLD_UNITS_PER_MAP_UNIT)
        for value in deltas
    ]
    map_x, map_y = anchor["map_origin_xy"]
    return {
        "schema": "re3-native-map-position-v1",
        "status": "candidate-native-map-binding",
        "source_stage_room": [stage, room],
        "world_position_xz": [world_x, world_z],
        # RE3-MAP-007: both movement and native arrow selection use the low
        # twelve bits; this Candidate conversion does not admit gameplay.
        "raw_facing_u16": facing,
        "player_heading_degrees": heading_degrees(facing, 90, 1),
        # Predict fresh marker initialization; cached native packets can lag.
        "native_arrow_sector": ((facing + 0x100) >> 9) & 7,
        "native_stage_room": [native_stage, native_room],
        "map_record_index": record_index,
        "native_layer_index": layer,
        "native_map_xy": [map_x + dx, map_y - dz],
        "projection_anchor": anchor,
        "map_sha256": layout["sha256"],
        "executable_sha256": layout["executable_sha256"],
        "loaded_room_binding": "unchecked",
        "campaign_admission": "unresolved",
        "floor_labels": "unresolved",
    }
