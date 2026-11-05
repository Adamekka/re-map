"""Bounded candidate RE3 PS1 layouts. See RE3-ROOM-001 through RE3-ROOM-004.

Successful decoding establishes source boundaries, not script execution,
item presence, door access, room clearance or a playable floor plan.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class RoomFormatFailure:
    kind: str
    offset: int
    detail: str


def aligned_block_size(size: int) -> int:
    assert size >= 0, "block alignment requires a nonnegative size"
    # ARD objects and MAP records both pad to the same 2048-byte block boundary.
    return (size + 2047) & ~2047


def room_section_end(offsets: Sequence[int], section: int, size: int) -> int:
    """Bound a decoded section, excluding opaque slot 2 from pointer ordering."""
    assert len(offsets) == 22 and 0 <= section < 22 and section != 2
    assert 96 <= offsets[section] <= size
    return min(
        [
            value
            for index, value in enumerate(offsets)
            if index != 2 and value > offsets[section]
        ]
        + [size]
    )


def decode_ard(data: bytes) -> dict | RoomFormatFailure:
    """Read the ten-object layout observed on SLUS-00923, without exporting bytes."""
    if len(data) < 2048 or len(data) % 2048:
        return RoomFormatFailure("ard", 0, "ARD needs complete 2048-byte blocks")
    length, count = struct.unpack_from("<II", data)
    if length != len(data) or count != 10:
        return RoomFormatFailure("ard", 0, "unsupported ARD length or object count")
    objects, offset = [], 2048
    for index in range(count):
        size, tag = struct.unpack_from("<II", data, 8 + index * 8)
        if offset + size > length:
            return RoomFormatFailure("ard", offset, "ARD object exceeds its container")
        objects.append(
            {"index": index, "offset": offset, "size": size, "tag": tag}
        )
        # RE3-ROOM-001: exact-boundary objects consume no extra block. The
        # pinned reevengi loader's strict-next alignment fails on this disc.
        offset = aligned_block_size(offset + size)
    if offset != length or objects[8]["size"] == 0:
        return RoomFormatFailure("ard", offset, "unsupported ARD end or empty RDT")
    return {"size": length, "sha256": hashlib.sha256(data).hexdigest(), "objects": objects}


def decode_room(data: bytes) -> dict | RoomFormatFailure:
    """Read geometry records and procedure envelopes, leaving all commands unresolved."""
    if len(data) < 96 or data[1] == 0:
        return RoomFormatFailure("rdt", 0, "RDT needs its 96-byte header and cameras")
    offsets = struct.unpack_from("<22I", data, 8)
    # RE3-ROOM-002: slot 2 is opaque. Four owned sources contain an out-of-file
    # word here; treating it as a section pointer would reject intact rooms.
    for index, value in enumerate(offsets):
        if index != 2 and value and not 96 <= value <= len(data):
            return RoomFormatFailure("rdt", 8 + index * 4, "section exceeds the RDT")
    for section in (6, 7, 8, 16):
        if not offsets[section] or offsets[section] == len(data):
            return RoomFormatFailure("rdt", 8 + section * 4, "required section is empty")
    if len({offsets[section] for section in (6, 7, 8, 16)}) != 4:
        return RoomFormatFailure("rdt", 8, "required sections alias incompatible layouts")

    camera_start, camera_end = offsets[7], room_section_end(offsets, 7, len(data))
    if camera_start + data[1] * 32 != camera_end:
        return RoomFormatFailure("rdt", camera_start, "unsupported camera table extent")
    cameras = []
    for index in range(data[1]):
        offset = camera_start + index * 32
        attributes = struct.unpack_from("<2H", data, offset)
        coordinates = struct.unpack_from("<6i", data, offset + 4)
        mask_offset = struct.unpack_from("<I", data, offset + 28)[0]
        if mask_offset and not 96 <= mask_offset < len(data):
            return RoomFormatFailure("rdt", offset + 28, "camera mask exceeds the RDT")
        cameras.append(
            {
                "offset": offset,
                "attributes": list(attributes),
                "from_xyz": list(coordinates[:3]),
                "to_xyz": list(coordinates[3:]),
                "mask_offset": mask_offset,
            }
        )

    start, end = offsets[8], room_section_end(offsets, 8, len(data))
    if end - start < 4 or (end - start - 4) % 20 or data[end - 4 : end] != b"\xff" * 4:
        return RoomFormatFailure("rdt", start, "unsupported camera-zone extent or terminator")
    zones = []
    for offset in range(start, end - 4, 20):
        attributes, camera0, camera1, *coordinates = struct.unpack_from("<HBB8h", data, offset)
        if attributes == 0xFFFF:
            return RoomFormatFailure("rdt", offset, "premature camera-zone terminator")
        zones.append(
            {
                "offset": offset,
                "attributes": attributes,
                "camera_bytes": [camera0, camera1],
                "points_xz": [coordinates[i : i + 2] for i in range(0, 8, 2)],
            }
        )

    start, end = offsets[6], room_section_end(offsets, 6, len(data))
    if end - start < 16:
        return RoomFormatFailure("rdt", start, "truncated collision header")
    count, *header_words = struct.unpack_from("<4I", data, start)
    if count < 1 or start + count * 16 > end:
        return RoomFormatFailure("rdt", start, "collision records exceed their section")
    collisions = []
    for offset in range(start + 16, start + count * 16, 16):
        coordinates = struct.unpack_from("<4h", data, offset)
        # The primary sources disagree on the remaining words' meanings.
        # Preserve their numeric values without assigning floor/shape masks.
        attributes = struct.unpack_from("<4H", data, offset + 8)
        collisions.append(
            {"offset": offset, "coordinates_xz": list(coordinates), "attributes": list(attributes)}
        )

    begin, end = offsets[16], room_section_end(offsets, 16, len(data))
    if end - begin < 2:
        return RoomFormatFailure("rdt", begin, "truncated procedure table")
    first = struct.unpack_from("<H", data, begin)[0]
    if first < 2 or first % 2 or first >= end - begin:
        return RoomFormatFailure("rdt", begin, "invalid procedure table size")
    entries = struct.unpack_from(f"<{first // 2}H", data, begin)
    if list(entries) != sorted(set(entries)) or any(
        not first <= value < end - begin for value in entries
    ):
        return RoomFormatFailure("rdt", begin, "invalid procedure offsets")
    procedures = [
        {
            "index": index,
            "offset": begin + entry,
            "size": following - entry,
            "sha256": hashlib.sha256(data[begin + entry : begin + following]).hexdigest(),
        }
        for index, (entry, following) in enumerate(pairwise((*entries, end - begin)))
    ]
    return {
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "header_bytes": list(data[:8]),
        "section_words": list(offsets),
        "cameras": cameras,
        "camera_zones": zones,
        "collision": {
            "offset": offsets[6],
            "count_including_header": count,
            "header_words": header_words,
            "records": collisions,
            "unresolved_tail_size": (
                room_section_end(offsets, 6, len(data)) - (offsets[6] + count * 16)
            ),
        },
        "initializer": {"offset": begin, "end": end, "procedures": procedures},
        # RE3-ROOM-003: a source directory is not an execution proof. In
        # particular slot 17 is not decoded as RE2's second script section.
        "script_semantics": "unresolved",
        "completion": "unknown",
    }


def decode_map(data: bytes) -> dict | RoomFormatFailure:
    """Catalog MAP_U's record/section directories without decoding image payloads."""
    if not data or len(data) % 2048:
        return RoomFormatFailure("map", 0, "MAP needs complete 2048-byte blocks")
    records, base = [], 0
    while base < len(data):
        count = struct.unpack_from("<I", data, base)[0]
        if count != 4:
            return RoomFormatFailure("map", base, "unsupported MAP section count")
        sections, expected = [], 36
        for index in range(count):
            offset, size = struct.unpack_from("<II", data, base + 4 + index * 8)
            if offset != expected or not size or base + offset + size > len(data):
                return RoomFormatFailure("map", base + 4 + index * 8, "invalid MAP section extent")
            sections.append({
                "index": index, "offset": offset, "size": size,
                "sha256": hashlib.sha256(data[base + offset : base + offset + size]).hexdigest(),
            })
            expected = offset + size
        start = base + sections[0]["offset"]
        size = sections[0]["size"]
        if size < 4:
            return RoomFormatFailure("map", start, "truncated MAP directory")
        entries = struct.unpack_from("<I", data, start)[0]
        table_end = 4 + entries * 8
        if not entries or table_end > size:
            return RoomFormatFailure("map", start, "invalid MAP directory count")
        rows = []
        for index in range(entries):
            offset, attribute0, attribute1 = struct.unpack_from("<IHH", data, start + 4 + index * 8)
            if not table_end <= offset <= size:
                return RoomFormatFailure("map", start + 4 + index * 8, "MAP entry exceeds section 0")
            rows.append({"index": index, "offset": offset, "attributes": [attribute0, attribute1]})
        # RE3-ROOM-004: directory entries can share payload offsets. A repeated
        # offset is an alias, not proof that a room has zero geometry/items.
        bounds = sorted({row["offset"] for row in rows} | {size})
        ends = dict(pairwise(bounds))
        for row in rows:
            row["bounded_size"] = 0 if row["offset"] == size else ends[row["offset"]] - row["offset"]
        padded_end = aligned_block_size(base + expected)
        if padded_end > len(data):
            return RoomFormatFailure("map", base, "truncated MAP record padding")
        records.append({
            "index": len(records), "offset": base, "size": expected,
            "padded_size": padded_end - base, "sections": sections, "directory": rows,
        })
        base = padded_end
    return {
        "size": len(data), "sha256": hashlib.sha256(data).hexdigest(),
        "records": records, "spatial_semantics": "unresolved",
    }
