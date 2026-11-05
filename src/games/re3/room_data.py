"""Bounded candidate RE3 PS1 layouts. See RE3-ROOM-001 through RE3-ROOM-003.

Successful decoding establishes source boundaries, not script execution,
item presence, door access, room clearance or a playable floor plan.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from itertools import pairwise


@dataclass(frozen=True)
class RoomFormatFailure:
    kind: str
    offset: int
    detail: str


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
        offset = (offset + size + 2047) & ~2047
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

    def section_end(section: int) -> int:
        return min(
            [value for index, value in enumerate(offsets) if index != 2 and value > offsets[section]]
            + [len(data)]
        )

    camera_start, camera_end = offsets[7], section_end(7)
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

    start, end = offsets[8], section_end(8)
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

    start, end = offsets[6], section_end(6)
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

    begin, end = offsets[16], section_end(16)
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
            "unresolved_tail_size": section_end(6) - (offsets[6] + count * 16),
        },
        "initializer": {"offset": begin, "end": end, "procedures": procedures},
        # RE3-ROOM-003: a source directory is not an execution proof. In
        # particular slot 17 is not decoded as RE2's second script section.
        "script_semantics": "unresolved",
        "completion": "unknown",
    }
