"""Offline door-target projection regression for the stage-remap rule.

RE1-DOORS-010/011 record the shared decode and the static 343-door
projection, plus one event-only pair for 344 overall. This test replays
that projection from the committed room manifest through the production
decoder, with no emulator, game bytes, or private captures. It guards
the recorded properties: the two late-game crossings resolve under the
remap flag, the Courtyard crossing disambiguates between two known
rooms, enabling the flag never moves a door from a known room to an
unknown one, and the single event-only pair is unaffected by the flag.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
# The CLI lives in the source tree; import its collector to test the code it runs.
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

from door_map import collect_doors, collect_event_doors

from games.re1.door_state import decode_door_target


def load_projection():
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    return collect_doors(manifest)


def load_event_doors():
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    return collect_event_doors(manifest)


def test_projection_counts_match_recorded_static_audit():
    rooms, unique = load_projection()
    affected = {
        (source, byte)
        for source, byte in unique
        if decode_door_target(byte, source[0], False)
        != decode_door_target(byte, source[0], True)
    }
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


def test_single_event_only_pair_is_unaffected_by_remap():
    rooms, unique = load_projection()
    event_unique = load_event_doors()
    event_only = sorted(pair for pair in event_unique if pair not in unique)
    assert event_only == [((3, 15), 0x0C)]
    clear = decode_door_target(0x0C, 3, False)
    remapped = decode_door_target(0x0C, 3, True)
    assert (clear.stage, clear.room) == (3, 0x0C)
    assert (remapped.stage, remapped.room) == (3, 0x0C)
    assert (clear.stage, clear.room) in rooms


@pytest.mark.parametrize("affected_only", [False, True])
def test_cli_reports_static_counts_and_filters_rows(affected_only):
    result = subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/door_map.py"),
            *(["--affected-only"] if affected_only else []),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    lines = result.stdout.splitlines()
    assert lines[:6] == [
        "unique init/main doors: 343",
        "remap-affected (encoded stage 1/2): 16",
        "unknown targets with remap clear: 8",
        "unknown targets with remap set: 6",
        "unique event doors: 7",
        "event-only doors: 1",
    ]
    assert sum(" | remap " in line for line in lines) == (16 if affected_only else 344)
    for expected in (
        "02-00 -> 0x3b: clear 00-1b (known) | remap 05-1b (known)",
        "05-10 -> 0x5c: clear 01-1c (unknown) | remap 06-1c (known)",
        "06-1C -> 0x30: clear 00-10 (unknown) | remap 05-10 (known)",
    ):
        assert "  " + expected in lines
    if not affected_only:
        assert "  03-0F -> 0x0c: clear 03-0c | remap 03-0c" in lines
