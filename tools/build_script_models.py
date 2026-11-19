"""Compile room script models from the pinned owned CUE. RE2-EVAL-001.

The output holds only control flow, flag/variable operations and interaction
operands with source offsets. Each source must match the room catalog's
SHA256, so models cannot drift from the sources the tracker binds at runtime.

Usage:
  python3 tools/build_script_models.py CUE PROFILE OUTPUT
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_item_table import _read_file
from disc_cue import read_cue_tracks
from extract_psx_file import _find
from list_psx_files import _sector_data
from output_safety import DerivedTextOutput

from games.re2.script_model import compile_room_scripts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("profile", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        tracks = read_cue_tracks(args.cue)
        profile = json.loads(args.profile.read_text())
        catalog_path = args.profile.parent / profile["room_metadata_path"]
        output = DerivedTextOutput(
            args.output, (args.cue, *tracks, args.profile, catalog_path)
        )
        catalog = json.loads(catalog_path.read_text())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Cannot prepare RE2 script export: {error}", file=sys.stderr)
        return 1
    if catalog["executable_identity"] != profile["executable_identity"]:
        print("Room catalog belongs to another revision.", file=sys.stderr)
        return 1
    sources = {}
    with tracks[0].open("rb") as stream:
        pvd = _sector_data(stream, 16)
        if pvd[:7] != b"\x01CD001\x01":
            print("Data track lacks an ISO9660 primary volume.", file=sys.stderr)
            return 1
        root = struct.unpack_from("<I", pvd, 158)[0]
        root_size = struct.unpack_from("<I", pvd, 166)[0]
        name, digest = profile["executable_identity"].split(" SHA256 ")
        executable = _read_file(stream, *_find(stream, root, root_size, name))
        if hashlib.sha256(executable).hexdigest() != digest:
            print("Disc executable does not match the profile.", file=sys.stderr)
            return 1
        for room in catalog["rooms"]:
            data = _read_file(stream, *_find(stream, root, root_size, room["source"]))
            if hashlib.sha256(data).hexdigest() != room["sha256"]:
                print(
                    f"{room['source']} differs from the room catalog.", file=sys.stderr
                )
                return 1
            sources[room["id"]] = {
                "sha256": room["sha256"],
                "program": compile_room_scripts(data),
            }
    document = {
        "schema": 1,
        "profile_id": profile["profile_id"],
        "executable_identity": profile["executable_identity"],
        "research_ids": ["RE2-EVAL-001"],
        "sources": sources,
    }
    try:
        output.write_text(json.dumps(document, separators=(",", ":")) + "\n")
    except (OSError, ValueError) as error:
        print(f"Cannot save RE2 script models: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
