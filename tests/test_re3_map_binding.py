"""RE3-MAP-003/004: original synthetic layouts and explicit captured contexts."""

import hashlib
import struct
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re3 import map_data
from games.re3.capture_data import CODE_WINDOWS, RAM_SIZE
from games.re3.room_data import RoomFormatFailure


def synthetic_layout(*, records=9, rows=64, anchors=64):
    result = bytearray()
    for record in range(records):
        directory_size = 4 + rows * 8 + 12
        projection_size = 52 + anchors * 8
        sizes = [directory_size, projection_size, 4, 4]
        data = bytearray(2048)
        struct.pack_into("<I", data, 0, 4)
        offset = 36
        for index, size in enumerate(sizes):
            struct.pack_into("<II", data, 4 + index * 8, offset, size)
            offset += size
        struct.pack_into("<I", data, 36, rows)
        for row in range(rows):
            struct.pack_into("<IHH", data, 40 + row * 8, 4 + rows * 8, int(row == 0), 0)
        struct.pack_into(
            "<4B2h4B", data, 36 + 4 + rows * 8, 1, 2, 4, 5, -6, 7, 0, 0, 0, 0
        )
        start = 36 + directory_size
        end = 32 + anchors * 8
        struct.pack_into(
            "<8I", data, start, 32, end, end + 8, end + 12, end + 16, 9, 8, 7
        )
        for row in range(anchors):
            struct.pack_into(
                "<4h",
                data,
                start + 32 + row * 8,
                100 + row,
                -100 - row,
                -1000 + row,
                2000 - row,
            )
        layered = record in (2, 4, 5, 6)
        struct.pack_into(
            "<2h4B",
            data,
            start + end,
            -160,
            -120,
            int(layered),
            3 if layered else 0,
            6,
            7,
        )
        result.extend(data)
    return result


@pytest.fixture
def context(monkeypatch):
    executable = bytearray(0xA0000)
    ram = bytearray(RAM_SIZE)
    for index, address in enumerate(CODE_WINDOWS):
        window = bytes(range(index * 32, index * 32 + 32))
        offset = 0x800 + address - 0x80010000
        executable[offset : offset + 32] = window
        ram[address - 0x80000000 : address - 0x80000000 + 32] = window
    table = 0x800 + 0x800A0430 - 0x80010000
    executable[table : table + 4] = b"\xff" * 4
    # Use the real mandatory hash gate on wholly original executable bytes.
    monkeypatch.setattr(
        map_data, "EXECUTABLE_SHA256", hashlib.sha256(executable).hexdigest()
    )
    return SimpleNamespace(
        executable=executable, ram=ram, data=synthetic_layout(), table=table
    )


def test_numeric_layout_preserves_anchors_and_opaque_header_words(context):
    result = map_data.decode_map_layout(context.data, context.executable)
    assert not isinstance(result, RoomFormatFailure)
    assert result["schema"] == "re3-static-map-layout-v1"
    assert result["records"][0]["projection_anchors"][1]["map_origin_xy"] == [101, -101]
    assert result["records"][0]["projection_anchors"][1]["world_origin_xz"] == [
        -999,
        1999,
    ]
    assert result["records"][0]["projection_header_words"][5:] == [9, 8, 7]
    assert result["records"][0]["layer_metadata"]["layer_count"] == 0
    assert result["floor_labels"] == result["room_floor_binding"] == "unresolved"


@pytest.mark.parametrize(
    "dx,dz,expected",
    [(-449, 449, [101, -101]), (-450, 450, [100, -102]), (450, -450, [102, -100])],
)
def test_projection_truncates_toward_zero_and_reverses_world_z(
    context, dx, dz, expected
):
    struct.pack_into("<h", context.ram, 0xD1F78, 1)
    struct.pack_into("<i", context.ram, 0xCCBF8, -999 + dx)
    struct.pack_into("<i", context.ram, 0xCCC00, 1999 + dz)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_map_xy"] == expected
    assert result["loaded_room_binding"] == "unchecked"
    assert result["campaign_admission"] == "unresolved"


@pytest.mark.parametrize(
    "stage,room,x,z,word,expected",
    [
        (1, 15, -8823, 0, 0, [1, 15]),
        (1, 15, -8822, 0, 0, [1, 16]),
        (3, 21, 799, 0, 0, [3, 21]),
        (3, 21, 800, 0, 0, [3, 17]),
        (4, 2, 0, 0, 0, [4, 2]),
        (4, 2, 0, 0, 1, [4, 17]),
        (2, 23, 0, -11301, 0, [2, 23]),
        (2, 23, 0, -11300, 0, [2, 2]),
        (5, 1, 0, 0, 0, [0, 1]),
        (6, 1, 0, 0, 0, [1, 1]),
    ],
)
def test_native_room_boundary_cases_keep_original_stage_context(
    context, stage, room, x, z, word, expected
):
    struct.pack_into("<2h", context.ram, 0xD1F76, stage, room)
    struct.pack_into("<i", context.ram, 0xCCBF8, x)
    struct.pack_into("<i", context.ram, 0xCCC00, z)
    struct.pack_into("<I", context.ram, 0xD1FC0, word)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_stage_room"] == expected


def test_event_bit_can_prevent_the_position_dependent_room_remap(context):
    struct.pack_into("<2h", context.ram, 0xD1F76, 2, 23)
    struct.pack_into("<I", context.ram, 0xD1FB8, 0x00800000)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_stage_room"] == [2, 23]


@pytest.mark.parametrize("reverse,expected", [(False, [1, 3]), (True, [0, 2])])
def test_remap_table_is_one_ordered_pass_not_a_dictionary_or_recursive_lookup(
    context, monkeypatch, reverse, expected
):
    rows = [(0, 1, 0, 2), (0, 2, 1, 3)]
    if reverse:
        rows.reverse()
    context.executable[context.table : context.table + 12] = (
        bytes(sum((list(r) for r in rows), [])) + b"\xff" * 4
    )
    monkeypatch.setattr(
        map_data, "EXECUTABLE_SHA256", hashlib.sha256(context.executable).hexdigest()
    )
    struct.pack_into("<h", context.ram, 0xD1F78, 1)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_stage_room"] == expected


def test_early_position_remap_returns_before_the_table(context, monkeypatch):
    context.executable[context.table : context.table + 8] = (
        bytes([1, 16, 0, 4]) + b"\xff" * 4
    )
    monkeypatch.setattr(
        map_data, "EXECUTABLE_SHA256", hashlib.sha256(context.executable).hexdigest()
    )
    struct.pack_into("<2h", context.ram, 0xD1F76, 1, 15)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_stage_room"] == [1, 16]


def test_table_destination_is_a_map_group_not_another_raw_stage(context, monkeypatch):
    context.executable[context.table : context.table + 8] = (
        bytes([0, 16, 5, 0]) + b"\xff" * 4
    )
    monkeypatch.setattr(
        map_data, "EXECUTABLE_SHA256", hashlib.sha256(context.executable).hexdigest()
    )
    struct.pack_into("<h", context.ram, 0xD1F78, 16)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_stage_room"] == [5, 0]
    assert result["map_record_index"] == 5


@pytest.mark.parametrize(
    "stage,room,layer", [(2, 12, 2), (2, 10, 1), (4, 3, 1), (4, 8, 1), (4, 7, 0)]
)
def test_layer_indices_remain_native_indices_without_floor_labels(
    context, stage, room, layer
):
    struct.pack_into("<2h", context.ram, 0xD1F76, stage, room)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_layer_index"] == layer
    assert result["floor_labels"] == "unresolved"


@pytest.mark.parametrize("previous,expected", [(0, 0), (0x503, 1)])
def test_story_layer_override_keeps_the_previous_room_condition(
    context, previous, expected
):
    struct.pack_into("<2h", context.ram, 0xD1F76, 4, 3)
    struct.pack_into("<I", context.ram, 0xD1FBC, 0x4000)
    struct.pack_into("<H", context.ram, 0xD1F7C, previous)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["native_layer_index"] == expected


@pytest.mark.parametrize(
    "stage,flags,record", [(0, 0x80, 7), (1, 0x80, 8), (0, 0x100, 0)]
)
def test_alternate_map_bit_is_separate_from_the_difficulty_bit(
    context, stage, flags, record
):
    struct.pack_into("<h", context.ram, 0xD1F76, stage)
    struct.pack_into("<I", context.ram, 0xCC858, flags)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert result["map_record_index"] == record


@pytest.mark.parametrize("rows,anchors", [(8, 64), (64, 8)])
def test_binding_requires_both_a_drawing_row_and_a_projection_anchor(
    context, rows, anchors
):
    struct.pack_into("<h", context.ram, 0xD1F78, 8)
    result = map_data.decode_native_map_position(
        synthetic_layout(rows=rows, anchors=anchors), context.executable, context.ram
    )
    assert isinstance(result, RoomFormatFailure)
    assert "outside its source tables" in result.detail


@pytest.mark.parametrize(
    "change",
    [
        "record",
        "signed-stage",
        "signed-room",
        "capture-size",
        "code-window",
        "executable",
    ],
)
def test_incoherent_contexts_return_modeled_failures_without_partial_positions(
    context, change
):
    if change == "record":
        struct.pack_into("<h", context.ram, 0xD1F76, 2)
        struct.pack_into("<I", context.ram, 0xCC858, 0x80)
    elif change == "signed-stage":
        struct.pack_into("<h", context.ram, 0xD1F76, -1)
    elif change == "signed-room":
        struct.pack_into("<h", context.ram, 0xD1F78, -1)
    elif change == "capture-size":
        context.ram.pop()
    elif change == "code-window":
        context.ram[CODE_WINDOWS[0] - 0x80000000] ^= 1
    else:
        context.executable.append(0)
    result = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert isinstance(result, RoomFormatFailure)


@pytest.mark.parametrize(
    "field,value", [(0, 28), (1, 31), (1, 33), (2, 33), (4, 0xFFFF)]
)
def test_projection_headers_are_bounded_before_reading_anchors(context, field, value):
    start = 36 + 4 + 64 * 8 + 12
    struct.pack_into("<I", context.data, start + field * 4, value)
    result = map_data.decode_map_layout(context.data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-layout"


def test_restoring_an_earlier_capture_reverses_the_binding_and_projection(context):
    initial = bytes(context.ram)
    before = map_data.decode_native_map_position(
        context.data, context.executable, initial
    )
    struct.pack_into("<2h", context.ram, 0xD1F76, 1, 15)
    struct.pack_into("<i", context.ram, 0xCCBF8, 1000)
    during = map_data.decode_native_map_position(
        context.data, context.executable, context.ram
    )
    assert during["native_stage_room"] != before["native_stage_room"]
    assert during["native_map_xy"] != before["native_map_xy"]
    assert (
        map_data.decode_native_map_position(context.data, context.executable, initial)
        == before
    )
