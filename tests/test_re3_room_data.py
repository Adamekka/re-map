"""RE3-ROOM-001/002/003: synthetic source bounds, not gameplay evidence."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re3.room_data import RoomFormatFailure, decode_ard, decode_room


def synthetic_room():
    data = bytearray(200)
    data[1] = 1
    for section, offset in ((7, 96), (8, 128), (6, 152), (16, 184), (13, 194), (17, 196)):
        struct.pack_into("<I", data, 8 + section * 4, offset)
    struct.pack_into("<2H6iI", data, 96, 1, 0x73B7, -100, 200, -300, 400, -500, 600, 0)
    struct.pack_into("<HBB8h", data, 128, 0xFF01, 0, 1, -20, -30, 40, -30, 40, 50, -20, 50)
    data[148:152] = b"\xff" * 4
    struct.pack_into("<4I", data, 152, 2, 10, 20, 30)
    struct.pack_into("<4h4H", data, 168, -500, -600, 700, 800, 0xFE41, 0x0F55, 0x0F00, 0x8F80)
    struct.pack_into("<2H", data, 184, 4, 6)
    # Arbitrary commands deliberately stay opaque, including apparent RE2
    # item opcodes and an unsupported RE3 opcode. No semantic pass may run.
    data[188:194] = bytes((0xFE, 0, 0x3E, 0, 0x67, 0))
    data[196:200] = b"\xff" * 4
    return data


def synthetic_ard(room):
    sizes = [2048, 0, 17, 1, 11, 4, 9, 7, len(room), 3]
    offset, entries = 2048, []
    for size in sizes:
        entries.append((offset, size))
        offset = (offset + size + 2047) & ~2047
    data = bytearray(offset)
    struct.pack_into("<II", data, 0, len(data), 10)
    for index, (offset, size) in enumerate(entries):
        struct.pack_into("<II", data, 8 + index * 8, size, 100 + index)
    offset, size = entries[8]
    data[offset : offset + size] = room
    return data


def test_ard_exact_boundary_and_zero_length_objects_do_not_add_blocks():
    data = synthetic_ard(synthetic_room())
    result = decode_ard(data)
    assert not isinstance(result, RoomFormatFailure)
    assert result["objects"][0] == {"index": 0, "offset": 2048, "size": 2048, "tag": 100}
    assert result["objects"][1]["offset"] == result["objects"][2]["offset"] == 4096
    obj = result["objects"][8]
    room = decode_room(data[obj["offset"] : obj["offset"] + obj["size"]])
    assert not isinstance(room, RoomFormatFailure)
    assert room["completion"] == "unknown"


@pytest.mark.parametrize("mutation", ["length", "count", "object", "empty-rdt", "tail", "short", "partial-block"])
def test_ard_models_corrupt_or_unsupported_layouts(mutation):
    data = synthetic_ard(synthetic_room())
    if mutation == "length":
        struct.pack_into("<I", data, 0, len(data) - 1)
    elif mutation == "count":
        struct.pack_into("<I", data, 4, 11)
    elif mutation == "object":
        struct.pack_into("<I", data, 8, len(data))
    elif mutation == "empty-rdt":
        struct.pack_into("<I", data, 8 + 8 * 8, 0)
    elif mutation == "tail":
        data.extend(bytes(2048))
        struct.pack_into("<I", data, 0, len(data))
    elif mutation == "short":
        data = data[:2047]
    else:
        data.pop()
    assert isinstance(decode_ard(data), RoomFormatFailure)


def test_room_retains_signed_geometry_and_opaque_collision_words():
    result = decode_room(synthetic_room())
    assert not isinstance(result, RoomFormatFailure)
    assert len(result["section_words"]) == 22
    assert result["cameras"][0]["from_xyz"] == [-100, 200, -300]
    assert result["cameras"][0]["to_xyz"] == [400, -500, 600]
    assert result["camera_zones"][0]["points_xz"] == [[-20, -30], [40, -30], [40, 50], [-20, 50]]
    assert result["collision"]["records"] == [{
        "offset": 168,
        "coordinates_xz": [-500, -600, 700, 800],
        "attributes": [0xFE41, 0x0F55, 0x0F00, 0x8F80],
    }]
    assert result["collision"]["unresolved_tail_size"] == 0


def test_slot_two_is_preserved_but_never_used_as_a_section_boundary():
    data = synthetic_room()
    baseline = decode_room(data)
    for value in (97, 189, 0xDEADBEEF):
        struct.pack_into("<I", data, 16, value)
        result = decode_room(data)
        assert not isinstance(result, RoomFormatFailure)
        assert result["section_words"][2] == value
        assert result["initializer"] == baseline["initializer"]
        assert result["cameras"] == baseline["cameras"]


def test_procedure_envelopes_never_claim_execution_or_clearance():
    result = decode_room(synthetic_room())
    assert result["initializer"]["offset"] == 184
    assert result["initializer"]["end"] == 194
    assert [(p["offset"], p["size"]) for p in result["initializer"]["procedures"]] == [(188, 2), (190, 4)]
    assert result["script_semantics"] == "unresolved"
    assert result["completion"] == "unknown"
    assert "items" not in result and "doors" not in result


@pytest.mark.parametrize("section", [0, 1, *range(3, 22)])
@pytest.mark.parametrize("value", [95, 201])
def test_other_section_words_cannot_point_outside_the_source(section, value):
    data = synthetic_room()
    struct.pack_into("<I", data, 8 + section * 4, value)
    assert isinstance(decode_room(data), RoomFormatFailure)


@pytest.mark.parametrize("section", [6, 7, 8, 16])
@pytest.mark.parametrize("value", [0, 200])
def test_missing_required_sections_never_read_the_header_as_data(section, value):
    data = synthetic_room()
    struct.pack_into("<I", data, 8 + section * 4, value)
    assert isinstance(decode_room(data), RoomFormatFailure)


@pytest.mark.parametrize("offset,format,value", [
    (1, "B", 0), (1, "B", 2), (124, "I", 201),
    (8 + 8 * 4, "I", 129), (148, "I", 0), (128, "H", 0xFFFF),
    (152, "I", 0), (152, "I", 0xFFFFFFFF),
    (184, "H", 0), (184, "H", 3), (184, "H", 10),
    (186, "H", 4), (186, "H", 3), (186, "H", 10),
])
def test_nested_table_failures_are_modeled(offset, format, value):
    data = synthetic_room()
    struct.pack_into("<" + format, data, offset, value)
    assert isinstance(decode_room(data), RoomFormatFailure)


def test_truncations_never_escape_as_unpack_errors():
    data = synthetic_room()
    for size in range(len(data)):
        result = decode_room(data[:size])
        assert isinstance(result, (dict, RoomFormatFailure))
        if size < 196:
            assert isinstance(result, RoomFormatFailure)
