"""Candidate MAP_U textured quads for the pinned SLUS-00923 executable.

RE3-MAP-001/002 establish static drawing primitives, not room outlines,
room/floor binding, ownership, visits, items or completion. No image is exported.
"""

from __future__ import annotations

import hashlib
import struct

from games.re3 import EXECUTABLE_SHA256
from games.re3.room_data import RoomFormatFailure, decode_map


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
