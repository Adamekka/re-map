"""Offline door-target projection over the committed room manifest.

Decodes every unique init/main Door_set target byte from
data/room_manifest_slus00551.json through the shared
games.re1.door_state.decode_door_target rule, with the stage-remap flag
clear and set. Compiled event procedures contribute one additional
event-only pair (RE1-DOORS-011); the tool reports it separately so the
init/main counts stay comparable with the recorded static audit.

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


def collect_event_doors(
    manifest: dict,
) -> set[tuple[tuple[int, int], int]]:
    """Return unique (source, target byte) doors from event procedures only."""
    unique: set[tuple[tuple[int, int], int]] = set()
    for row in manifest["rooms"]:
        program = row["tracking_program"]
        source = (row["room_main"], row["room_sub"])
        for block in program["event_blocks"]:
            for procedure in block:
                for command in procedure["commands"]:
                    if command["kind"] == "door":
                        unique.add((source, command["args"][7]))
        for command in program["event_commands"] + program["event_effects"]:
            if command["kind"] == "door":
                unique.add((source, command["args"][7]))
    return unique


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
    event_unique = collect_event_doors(manifest)
    event_only = sorted(pair for pair in event_unique if pair not in unique)

    def known(target: RoomId) -> bool:
        return (target.stage, target.room) in rooms

    projection = []
    for source, byte in sorted(unique):
        clear = decode_door_target(byte, source[0], False)
        remapped = decode_door_target(byte, source[0], True)
        projection.append((source, byte, clear, remapped))
    # Compare decoder results so filtering shares the native rule rather than
    # maintaining a second encoded-stage predicate beside it.
    affected = [row for row in projection if row[2] != row[3]]
    unknown_clear = [row for row in projection if not known(row[2])]
    unknown_remap = [row for row in projection if not known(row[3])]
    print(f"unique init/main doors: {len(unique)}")
    print(f"remap-affected (encoded stage 1/2): {len(affected)}")
    print(f"unknown targets with remap clear: {len(unknown_clear)}")
    print(f"unknown targets with remap set: {len(unknown_remap)}")
    print(f"unique event doors: {len(event_unique)}")
    print(f"event-only doors: {len(event_only)}")

    rows = affected if args.affected_only else projection
    for source, byte, clear, remapped in rows:
        clear_mark = "known" if known(clear) else "unknown"
        remap_mark = "known" if known(remapped) else "unknown"
        print(
            f"  {source[0]:02X}-{source[1]:02X} -> {byte:#04x}: "
            f"clear {clear} ({clear_mark}) | remap {remapped} ({remap_mark})"
        )
    if args.affected_only:
        return 0
    print("unknown with remap set:")
    for source, byte, _, _ in unknown_remap:
        print(f"  {source[0]:02X}-{source[1]:02X} -> {byte:#04x}")
    print("event-only doors:")
    for source, byte in event_only:
        clear = decode_door_target(byte, source[0], False)
        remapped = decode_door_target(byte, source[0], True)
        print(
            f"  {source[0]:02X}-{source[1]:02X} -> {byte:#04x}: "
            f"clear {clear} | remap {remapped}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
