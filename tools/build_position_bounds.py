"""RE1-PLAYER-003: extract candidate position bounds from the owner's disc.

Camera-boundary extents approximate each room's coordinate range. They are
not collision outlines or a native world-to-map transform. Only numeric
bounds and provenance are exported, never camera/background assets.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from build_floor_plans import AREAS, EXE_SHA256, native_location
from build_item_table import _read_file
from extract_psx_file import _find
from list_psx_files import _sector_data

REPO = Path(__file__).resolve().parents[1]


def camera_boundaries(data: bytes) -> tuple[int, dict[int, list[tuple[int, int]]]]:
    """Read bounded RVD records. RE1 to=9 records belong to camera `from`."""
    if len(data) < 0x94 or not data[1]:
        raise ValueError("position source needs an RDT header and cameras")
    start, end = struct.unpack_from("<2I", data, 0x48)
    if not 0x94 <= start < end <= len(data):
        raise ValueError("camera boundary section is outside the source RDT")
    cameras = {}
    for offset in range(start, end - 3, 20):
        target, camera = struct.unpack_from("<2H", data, offset)
        if target == 0xFFFF:
            return data[1], cameras
        if offset + 20 > end:
            raise ValueError("camera boundary record is truncated")
        if target == 9:
            values = struct.unpack_from("<8h", data, offset + 4)
            cameras.setdefault(camera, []).extend(zip(values[::2], values[1::2]))
    raise ValueError("camera boundary section has no terminator")


def build_bounds(cue: Path) -> dict:
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    match = re.search(r'FILE\s+"([^"]+)"', cue.read_text())
    if match is None:
        raise ValueError("CUE has no image FILE entry")
    sources = {}
    with (cue.parent / match[1]).open("rb") as image:
        pvd = _sector_data(image, 16)
        root = struct.unpack_from("<I", pvd, 158)[0]
        length = struct.unpack_from("<I", pvd, 166)[0]
        extent, size = _find(image, root, length, "SLUS_005.51")
        if hashlib.sha256(_read_file(image, extent, size)).hexdigest() != EXE_SHA256:
            raise ValueError("Disc executable does not match pinned SLUS-00551")
        for row in manifest["rooms"]:
            name = row["source_rdt"]
            if name in sources:
                continue
            extent, size = _find(image, root, length, name)
            data = _read_file(image, extent, size)
            if hashlib.sha256(data).hexdigest() != row["source_sha256"]:
                raise ValueError(f"Position source hash disagrees with {name}")
            try:
                count, boundaries = camera_boundaries(data)
            except ValueError as error:
                raise ValueError(f"{name}: {error}") from error
            groups = {}
            for camera in range(count):
                selector, region = native_location(
                    row["room_main"], row["room_sub"], camera
                )
                groups.setdefault((selector, region), []).append(camera)
            regions = []
            for (selector, region), cameras in sorted(groups.items()):
                points = [point for cam in cameras for point in boundaries.get(cam, [])]
                entry = {
                    "area": AREAS[selector][0],
                    "region": f"{region:02X}",
                    "cameras": cameras,
                }
                if points:
                    bounds = [
                        min(x for x, _ in points),
                        min(z for _, z in points),
                        max(x for x, _ in points),
                        max(z for _, z in points),
                    ]
                else:
                    bounds = []
                if bounds and bounds[0] < bounds[2] and bounds[1] < bounds[3]:
                    entry.update(status="approximate", world_bounds=bounds)
                else:
                    entry.update(
                        status="unavailable",
                        reason="This room has no usable coordinate bounds.",
                    )
                regions.append(entry)
            sources[name] = {
                "source_rdt": name,
                "source_sha256": row["source_sha256"],
                "camera_count": count,
                # Some RDTs retain boundaries for unused cameras. Record those
                # IDs explicitly, but never assign them a live position mapping.
                "unused_boundary_cameras": sorted(set(boundaries) - set(range(count))),
                "regions": regions,
            }
    return {
        "schema": 1,
        "profile_id": manifest["profile_id"],
        "executable_identity": manifest["executable_identity"],
        "research_ids": ["RE1-PLAYER-003"],
        "method": "camera-boundary extents; +X right, +Z up; approximate",
        "sources": list(sources.values()),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.write_text(json.dumps(build_bounds(args.cue), indent=2) + "\n")
