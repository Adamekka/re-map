"""Offline door-target projection over the committed room manifest.

Decodes every unique init/main Door_set target byte from
data/room_manifest_slus00551.json through the shared
games.re1.door_state.decode_door_target rule, with the stage-remap flag
clear and set. Event procedures are out of scope here; RE1-DOORS-011
counts one additional event-only pair separately.

Usage:
  python3 tools/door_map.py [--affected-only]

Exit status is zero when the projection runs. Unknown targets are
reported, not guessed; several exist by design (for example stair and
elevator transitions with no room file).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from games.game_profile import RoomId
from games.re1.door_state import decode_door_target

MANIFEST = REPO / "data" / "room_manifest_slus00551.json"


def collect_doors(
    manifest: dict,
) -> tuple[set[tuple[int, int]], set[tuple[tuple[int, int], int]]]:
    """Return (logical rooms, unique (source, target byte) init/main doors)."""
    rooms = {(row["room_main"], row["room_sub"]) for row in manifest["rooms"]}
    unique: set[tuple[tuple[int, int], int]] = set()
    for row in manifest["rooms"]:
        program = row["tracking_program"]
        for procedure in program["procedures"] + program["main_procedures"]:
            for command in procedure["commands"]:
                if command["kind"] == "door":
                    unique.add(
                        ((row["room_main"], row["room_sub"]), command["args"][7])
                    )
    return rooms, unique


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--affected-only",
        action="store_true",
        help="list only the doors the remap flag can change",
    )
    args = ap.parse_args()

    manifest = json.loads(MANIFEST.read_text())
    rooms, unique = collect_doors(manifest)

    def known(target: RoomId) -> bool:
        return (target.stage, target.room) in rooms

    affected = sorted(
        (source, byte) for source, byte in unique if (byte >> 5) in (1, 2)
    )
    unknown_clear = sorted(
        (source, byte)
        for source, byte in unique
        if not known(decode_door_target(byte, source[0], False))
    )
    unknown_remap = sorted(
        (source, byte)
        for source, byte in unique
        if not known(decode_door_target(byte, source[0], True))
    )
    print(f"unique init/main doors: {len(unique)}")
    print(f"remap-affected (encoded stage 1/2): {len(affected)}")
    print(f"unknown targets with remap clear: {len(unknown_clear)}")
    print(f"unknown targets with remap set: {len(unknown_remap)}")

    rows = affected if args.affected_only else sorted(unique)
    for source, byte in rows:
        clear = decode_door_target(byte, source[0], False)
        remapped = decode_door_target(byte, source[0], True)
        clear_mark = "known" if known(clear) else "unknown"
        remap_mark = "known" if known(remapped) else "unknown"
        print(
            f"  {source[0]:02X}-{source[1]:02X} -> {byte:#04x}: "
            f"clear {clear} ({clear_mark}) | remap {remapped} ({remap_mark})"
        )
    if args.affected_only:
        return 0
    print("unknown with remap set:")
    for source, byte in unknown_remap:
        print(f"  {source[0]:02X}-{source[1]:02X} -> {byte:#04x}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
