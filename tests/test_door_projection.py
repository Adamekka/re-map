"""Offline door-target projection regression for the stage-remap rule.

RE1-DOORS-010/011 record the shared decode and the static 343-door
projection. This test replays that projection from the committed room
manifest through the production decoder, with no emulator, game bytes,
or private captures. It guards the three recorded properties: the two
late-game crossings resolve under the remap flag, the Courtyard crossing
disambiguates between two known rooms, and enabling the flag never moves
a door from a known room to an unknown one.
"""

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from games.re1.door_state import decode_door_target


def load_projection():
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    rooms = {(row["room_main"], row["room_sub"]) for row in manifest["rooms"]}
    unique = set()
    for row in manifest["rooms"]:
        program = row["tracking_program"]
        for procedure in program["procedures"] + program["main_procedures"]:
            for command in procedure["commands"]:
                if command["kind"] == "door":
                    unique.add(
                        ((row["room_main"], row["room_sub"]), command["args"][7])
                    )
    return rooms, unique


def test_projection_counts_match_recorded_static_audit():
    rooms, unique = load_projection()
    affected = {(s, b) for s, b in unique if (b >> 5) in (1, 2)}
    assert len(rooms) == 159
    assert len(unique) == 343
    assert len(affected) == 16


def test_kitchen_and_stairway_resolve_under_remap():
    rooms, _ = load_projection()
    kitchen_clear = decode_door_target(0x30, 6, False)
    kitchen_remap = decode_door_target(0x30, 6, True)
    assert (kitchen_clear.stage, kitchen_clear.room) not in rooms
    assert (kitchen_remap.stage, kitchen_remap.room) == (5, 0x10)
    assert (kitchen_remap.stage, kitchen_remap.room) in rooms
    stair_clear = decode_door_target(0x5C, 5, False)
    stair_remap = decode_door_target(0x5C, 5, True)
    assert (stair_clear.stage, stair_clear.room) not in rooms
    assert (stair_remap.stage, stair_remap.room) == (6, 0x1C)
    assert (stair_remap.stage, stair_remap.room) in rooms


def test_courtyard_disambiguates_between_known_rooms():
    rooms, _ = load_projection()
    clear = decode_door_target(0x3B, 2, False)
    remapped = decode_door_target(0x3B, 2, True)
    assert (clear.stage, clear.room) == (0, 0x1B)
    assert (remapped.stage, remapped.room) == (5, 0x1B)
    assert (clear.stage, clear.room) in rooms
    assert (remapped.stage, remapped.room) in rooms


def test_remap_never_moves_known_target_to_unknown():
    rooms, unique = load_projection()
    regressed = [
        (source, byte)
        for source, byte in unique
        if (
            decode_door_target(byte, source[0], False).stage,
            decode_door_target(byte, source[0], False).room,
        )
        in rooms
        and (
            decode_door_target(byte, source[0], True).stage,
            decode_door_target(byte, source[0], True).room,
        )
        not in rooms
    ]
    assert regressed == []
