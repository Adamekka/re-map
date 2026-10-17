"""RE2-SCD-001 / RE2-MAP-001: extraction contracts, not runtime confirmation."""

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from map_geometry import trace_floor_cells

from games.re2.room_data import decode_room


def synthetic_room(init):
    data = bytearray(132)
    data[1] = 1
    struct.pack_into("<I", data, 8 + 7 * 4, 100)
    struct.pack_into("<I", data, 8 + 16 * 4, 132)
    data.extend(b"\x02\0" + init)
    struct.pack_into("<I", data, 8 + 17 * 4, len(data))
    data.extend(b"\x02\0\x01\0")
    return bytes(data)


def test_conditional_return_does_not_hide_later_pickup():
    item = bytearray(22)
    item[0:4] = bytes([0x4E, 8, 2, 0x31])
    struct.pack_into("<3H", item, 14, 20, 15, 9)
    data = synthetic_room(
        bytes([6, 0, 8, 0, 0x21, 4, 0, 1, 1, 0, 0, 0]) + item + bytes([1, 0])
    )
    result = decode_room(data, "synthetic")
    assert result["items"] == [
        {
            "offset": 146,
            "slot": 8,
            "type": 20,
            "amount": 15,
            "global_id": 9,
            "four_point": False,
        }
    ]
    assert result["proofs"][0]["sha256"] == hashlib.sha256(bytes(24)).hexdigest()


def test_truncated_script_and_branch_outside_procedure_are_rejected():
    with pytest.raises(ValueError, match="truncated"):
        decode_room(synthetic_room(bytes([0x4E, 0])), "synthetic")
    with pytest.raises(ValueError, match="outside its procedure"):
        decode_room(synthetic_room(bytes([6, 0, 255, 0, 1, 0])), "synthetic")


def test_diagonal_floor_contacts_preserve_both_disconnected_cells():
    rings, label = trace_floor_cells({(0, 0), (1, 1)})
    assert len(rings) == 2
    assert sum(area for area, _ in rings) == 2
    assert label in {(0, 0), (1, 1)}


def test_generated_catalog_has_unique_room_proofs_and_only_numeric_map_data():
    rooms = json.loads((ROOT / "data/rooms_slus00421.json").read_text())
    maps = json.loads((ROOT / "data/floor_plans_slus00421.json").read_text())
    assert rooms["executable_identity"] == maps["executable_identity"]
    assert len(rooms["rooms"]) == 125
    signatures = {
        (
            tuple(room["section_offsets"]),
            tuple(proof["sha256"] for proof in room["proofs"]),
        )
        for room in rooms["rooms"]
    }
    assert len(signatures) == 125
    assert sum(len(room["items"]) for room in rooms["rooms"]) == 281
    assert sum(len(room["doors"]) for room in rooms["rooms"]) == 321
    assert len(maps["areas"]) == 20
    assert not any("programs" in room for room in rooms["rooms"])
    assert all(
        set(door) == {"id", "observation_id", "rooms", "segment"}
        for area in maps["areas"]
        for door in area["doors"]
    )
