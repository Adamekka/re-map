"""RE3-EVAL-001: live RE3 tracking through the guarded reader and evaluator.

Synthetic coherent RAM and programs only; no gameplay confirmation.
"""

from __future__ import annotations

import json
import struct

import pytest
from test_re3_live_reader import live as live  # noqa: PLC0414
from test_re3_native_contracts import coherent as coherent  # noqa: PLC0414

from emulator.duckstation_gdb import MemRead
from games.bit_flags import msb_flag_location
from games.game_profile import RoomId
from games.re2.map_layout import Re2MapLayout, Re2MapProjection
from games.re3.tracking import RE3_TARGET, Re3Profile, poll_re3
from games.scd_state import EngineTasks
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus

FLAGS = 0x800D1F2C
ITEM_BANK = 7
ITEM_BANK_ADDRESS = 0x800D2008
STORY_BANK_ADDRESS = 0x800D1FC8


def rows(*body):
    return [[index * 10, index * 10 + 10, *row] for index, row in enumerate(body)]


@pytest.fixture
def tracking(live, tmp_path):
    catalog, ram, base = live
    # 00-00 is current; 00-01 is a departed room whose item depends on a
    # story flag (bank 5 bit 3) and whose door is replaced once it is set.
    programs = {
        "00-00": {
            "main:0": rows(["item", 4, 0x31, 20, 15, 9], ["end"]),
            "main:1": rows(["end"]),
        },
        "00-01": {
            "main:0": rows(
                ["door", 0, 0x31],
                ["if", 50],
                ["ck", 5, 3, 1],
                ["item", 3, 0x31, 21, 7, 12],
                ["reset", 0, 4, 0x31, -1, -1, -1, -1],
                ["end"],
            ),
            "main:1": rows(["end"]),
        },
    }
    door = {
        "offset": 0,
        "slot": 0,
        "activation_floor": 0,
        "stage": 0,
        "room": 0,
        "floor": 0,
        "lock_id": 0,
        "lock_type": 0,
        "four_point": False,
        "center": [0.0, 0.0],
    }
    rooms = {
        key: {
            "id": key,
            "source": f"CD_DATA/STAGE1/R10{key[-1]}.ARD",
            "stage": 0,
            "room": int(key[-2:], 16),
            "program": program,
            "doors": [door] if key == "00-01" else [],
            "item_ids": frozenset({9} if key == "00-00" else {12}),
        }
        for key, program in programs.items()
    }
    plans = tmp_path / "plans.json"
    plans.write_text(
        json.dumps(
            {
                "schema": 1,
                "profile_id": "re3_jill_hard_slus00923",
                "executable_identity": "test",
                "door_placement": "projected-wall",
                "stage_modulus": 256,
                "areas": [],
                "locations": [
                    {
                        "room": key,
                        "floor_min": 0,
                        "floor_max": 255,
                        "conditions": [],
                        "position_bounds": {},
                        "area": "unmapped",
                        "region": "",
                    }
                    for key in rooms
                ],
            }
        )
    )
    profile = Re3Profile(
        "re3_jill_hard_slus00923",
        "test",
        "test",
        RE3_TARGET,
        catalog.runtime_signature,
        catalog,
        {
            "state_blocks": [["0x800D1F2C", 1696], ["0x800CC830", 1384]],
            "aot_table_address_ps1": "0x800CC890",
            "aot_capacity": 40,
            "item_bank_early": ITEM_BANK,
            "item_bank_late": 8,
            "item_bank_stage_boundary": 2,
            "key_bank": 9,
            "unit_count_item_types": [20],
            "heading_offset_degrees": 90,
            "heading_direction": 1,
        },
        {ITEM_BANK: ITEM_BANK_ADDRESS, 5: STORY_BANK_ADDRESS, 9: 0x800D20CC},
        rooms,
        {"items": {"20": "Handgun ammo", "21": "Shotgun shells"}},
        Re2MapLayout.load(
            plans, "re3_jill_hard_slus00923", "test", rooms, Re2MapProjection(0, 450)
        ),
        EngineTasks(("main:0", "main:1"), frozenset({1})),
        {
            "variables_address_ps1": "0x800D1F46",
            "variable_count": 45,
            "entry_cleared_flags": [],
            "entry_variables": [],
            "stage_variable": 24,
            "room_variable": 25,
            "unread_variables": [],
            "approach_variables": [26, 27],
            "approach_banks": [],
        },
    )

    def put_flag(address, bit, value):
        word, mask = msb_flag_location(address, bit)
        offset = word - 0x80000000
        current = struct.unpack_from("<I", ram, offset)[0]
        struct.pack_into(
            "<I", ram, offset, current | mask if value else current & ~mask
        )

    def read(address, width):
        offset = address - 0x80000000
        return MemRead(True, bytes(ram[offset : offset + width]), "")

    return profile, put_flag, read


def test_departed_room_follows_fresh_story_flags_and_rewinds(tracking):
    profile, put_flag, read = tracking
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 1))
    for story in (False, True, False):
        put_flag(STORY_BANK_ADDRESS, 3, story)
        assert poll_re3(profile, tracker, read).status is PollStatus.Display
        departed = tracker.rooms["00-01"]
        doors = [door for door in tracker.doors if door.source == RoomId(0, 1)]
        if story:
            assert [(item.label, item.state) for item in departed.items] == [
                ("Shotgun shells", "uncollected")
            ]
            assert departed.completion is RoomCompletion.Incomplete
            assert [door.state for door in doors] == ["BLOCKED"]
        else:
            assert departed.items == ()
            assert departed.completion is RoomCompletion.Cleared
            assert [door.state for door in doors] == ["OPEN"]


def test_current_room_acquisition_flag_wins_and_reverses(tracking):
    profile, put_flag, read = tracking
    tracker = Tracker()
    for collected in (False, True, False):
        put_flag(ITEM_BANK_ADDRESS, 9, collected)
        assert poll_re3(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-00"]
        assert [item.state for item in record.items] == [
            "taken" if collected else "uncollected"
        ]
        assert record.completion is (
            RoomCompletion.Cleared if collected else RoomCompletion.Incomplete
        )


def test_owned_profile_evaluates_every_room():
    import os
    import re
    import sys
    from pathlib import Path

    from games.scd_state import GameState, Support, room_script_state

    cue = os.environ.get("RE_MAP_RE3_OWNED_CUE")
    if not cue:
        pytest.skip("Set RE_MAP_RE3_OWNED_CUE for the owned-disc profile check")
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root / "tools"))
    from re3_room_catalog import load_owned_sources

    cue_path = Path(cue)
    track = re.search(r'FILE\s+"([^"]+)"', cue_path.read_text())
    executable, sources = load_owned_sources(cue_path.parent / track[1])
    profile = Re3Profile.load(
        root / "profiles/re3_jill_hard_slus00923.json", executable, sources
    )
    assert len(profile.rooms) == 169
    unsupported = []
    for key, room in profile.rooms.items():
        result = room_script_state(
            room["program"],
            GameState(
                lambda bank, bit: False,
                lambda index: 0,
                frozenset({26, 27}),
                frozenset(),
            ),
            profile.tasks,
            {gid: (ITEM_BANK, gid) for gid in room["item_ids"]},
        )
        if result.support is not Support.Supported:
            unsupported.append((key, result.reason))
    assert unsupported == []
