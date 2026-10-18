"""RE2-SCD-001 / RE2-MAP-001 / RE2-COLLECT-001: source contracts, not gameplay."""

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


def synthetic_room(init, main_procedures=(b"\x01\0",)):
    data = bytearray(132)
    data[1] = 1
    struct.pack_into("<I", data, 8 + 7 * 4, 100)
    struct.pack_into("<I", data, 8 + 16 * 4, 132)
    data.extend(b"\x02\0" + init)
    struct.pack_into("<I", data, 8 + 17 * 4, len(data))
    offset = 2 * len(main_procedures)
    for procedure in main_procedures:
        data.extend(struct.pack("<H", offset))
        offset += len(procedure)
    data.extend(b"".join(main_procedures))
    return bytes(data)


def item_command(item_type, amount, gid, slot=8):
    item = bytearray(22)
    item[0:4] = bytes([0x4E, slot, 2, 0x31])
    struct.pack_into("<3H", item, 14, item_type, amount, gid)
    return bytes(item)


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
    assert result["collection_item_ids"] == []


def test_inactive_reward_keeps_its_initializer_collection_identity():
    data = synthetic_room(
        item_command(20, 15, 9) + bytes([0x46, 8, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0])
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == [9]


@pytest.mark.parametrize("second_type,expected", [(20, [9]), (21, [])])
def test_presence_joins_branches_only_when_every_path_has_the_same_identity(
    second_type, expected
):
    # Both branches create ID 9; differing amounts do not change identity.
    script = (
        bytes([6, 0, 30, 0, 0x21, 4, 0, 1])
        + item_command(20, 15, 9)
        + bytes([7, 0, 28, 0])
        + item_command(second_type, 30, 9)
        + bytes([0, 0, 1, 0])
    )
    assert (
        decode_room(synthetic_room(script), "synthetic")["collection_item_ids"]
        == expected
    )


def test_optional_creator_and_uncalled_procedure_do_not_establish_presence():
    optional = (
        bytes([6, 0, 28, 0, 0x21, 4, 0, 1])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    assert (
        decode_room(synthetic_room(optional), "synthetic")["collection_item_ids"] == []
    )
    data = synthetic_room(
        bytes([1, 0]), (bytes([1, 0]), item_command(20, 15, 9) + bytes([1, 0]))
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_init_gosub_uses_main_table_and_returns_to_its_caller():
    data = synthetic_room(
        bytes([0x18, 1]) + item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), item_command(30, 1, 10, slot=9) + bytes([0x19, 0])),
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == [9, 10]


@pytest.mark.parametrize(
    "prefix,suffix",
    [
        (bytes([2]), b""),  # Unsupported task control.
        (bytes([0x21, 4, 0, 1]), b""),  # Predicate outside a supported if.
        (b"", bytes([0x46, 8, 2, 0, 20, 0, 15, 0, 9, 0])),  # Identity reset.
        (b"", bytes([0x2C, 8, 0, 0]) + bytes(16)),  # Slot repurposed.
    ],
)
def test_unsupported_effects_cannot_authorize_an_item(prefix, suffix):
    data = synthetic_room(prefix + item_command(20, 15, 9) + suffix + bytes([1, 0]))
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_recursive_calls_and_missing_callees_cannot_establish_presence():
    for procedure in (0, 255):
        data = synthetic_room(
            bytes([1, 0]),
            (item_command(20, 15, 9) + bytes([0x18, procedure, 1, 0]),),
        )
        assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_replaced_item_slot_does_not_turn_both_initializers_into_required_items():
    data = synthetic_room(
        item_command(20, 15, 9) + item_command(30, 1, 10) + bytes([1, 0])
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_item_initializer_with_an_unresolved_interaction_is_not_a_presence_proof():
    item = bytearray(item_command(20, 15, 9))
    item[2] = 5
    assert (
        decode_room(synthetic_room(item + bytes([1, 0])), "synthetic")[
            "collection_item_ids"
        ]
        == []
    )


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
