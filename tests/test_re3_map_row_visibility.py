"""RE3-MAP-012: source-bound native reveal, separate from tracker visits."""

import struct

import pytest
from test_re3_map_binding import context as context
from test_re3_map_conditions import tables as tables
from test_re3_map_selection import selected as selected

from games.re3.capture_data import capture_failure
from games.re3.map_selection import decode_native_map_row_visibility
from games.re3.room_data import RoomFormatFailure


@pytest.fixture
def rows(selected):
    original_bind = selected.bind

    def bind(record):
        size = original_bind(record)
        base = record * 2048
        section = struct.unpack_from("<I", selected.data, base + 12)[0]
        header = struct.unpack_from("<I", selected.data, base + section + 4)[0]
        selected.ram[0xE026D] = selected.data[base + section + header + 4]
        selected.ram[0xE0270] = selected.data[base + section + header + 5]
        return size

    selected.bind = bind
    return selected


def visibility(rows, record=0):
    result = decode_native_map_row_visibility(
        rows.data, rows.executable, rows.ram, record
    )
    assert not isinstance(result, RoomFormatFailure), result
    return result


def visible_indices(result):
    return [row["index"] for row in result["rows"] if row["native_visible"]]


@pytest.mark.parametrize("record", range(9))
def test_all_explicit_sources_bind_without_creating_tracker_exploration(rows, record):
    size = rows.bind(record)
    result = visibility(rows, record)
    assert result["schema"] == "re3-native-map-row-visibility-v1"
    assert result["selected_record_index"] == record
    assert result["selected_native_group"] == (record if record < 7 else record - 7)
    assert result["loaded_source_prefix_bytes"] == size
    assert not result["native_map_acquired"]
    assert len(result["rows"]) == 64
    assert visible_indices(result) == []
    assert all(
        result[key] == "unresolved"
        for key in ("room_ownership", "campaign_admission", "tracker_visibility")
    )
    assert all(key not in result for key in ("visited", "rooms", "completion"))


def test_full_acquisition_mask_bypasses_visit_cutoff_and_reverses_freshly(rows):
    rows.bind(0)
    # Visit bits alone cannot reveal row 48. The structural gate still rejects
    # row 17 even when its native visited bit is set.
    struct.pack_into("<I", rows.ram, 0xD20DC, 0x40044000)
    struct.pack_into("<I", rows.ram, 0xD20E0, 0x8000)
    before = visibility(rows)
    assert visible_indices(before) == [1, 13]
    struct.pack_into("<I", rows.ram, 0xD2124, 0x80000000)
    after = visibility(rows)
    assert after["native_map_acquired"]
    assert 48 in visible_indices(after)
    assert 17 not in visible_indices(after)
    struct.pack_into("<I", rows.ram, 0xD2124, 0)
    assert visibility(rows) == before


def test_acquired_group_four_still_requires_visits_for_rows_eleven_through_fifteen(
    rows,
):
    rows.bind(4)
    struct.pack_into("<I", rows.ram, 0xD2124, 0x08000000)
    assert set(visible_indices(visibility(rows, 4))) == {4, 5, 6, 7, *range(16, 64)}
    struct.pack_into("<I", rows.ram, 0xD20FC, 0x80000)
    result = visibility(rows, 4)
    assert 12 in visible_indices(result)
    assert all(row not in visible_indices(result) for row in (11, 13, 14, 15))


def test_selected_layer_browses_independently_of_current_layer_and_location(rows):
    rows.bind(2)
    struct.pack_into("<I", rows.ram, 0xD2124, 0x20000000)
    rows.ram[0xE026A] = 0
    rows.ram[0xE026C] = 13
    rows.ram[0xE026E] = 2
    rows.ram[0xE026F] = 0
    before = visibility(rows, 2)
    assert before["current_native_key"] == 13
    assert before["selected_layer_i8"] == 2
    assert visible_indices(before) == [12]
    rows.ram[0xE026F] = 255
    assert visibility(rows, 2) == before
    rows.ram[0xE026E] = 1
    assert visible_indices(visibility(rows, 2)) == [10, 11, *range(13, 64)]


@pytest.mark.parametrize(
    "offset,value", [(0xE026D, 0), (0xE0270, 0), (0xE026E, 3), (0xE026E, 255)]
)
def test_cached_layer_metadata_and_selected_range_must_bind_to_source(
    rows, offset, value
):
    rows.bind(2)
    rows.ram[offset] = value
    result = decode_native_map_row_visibility(rows.data, rows.executable, rows.ram, 2)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-binding"
    assert result.offset == offset


def test_unlayered_source_ignores_signed_selected_layer(rows):
    rows.bind(0)
    rows.ram[0xE026E] = 255
    struct.pack_into("<I", rows.ram, 0xD20DC, 0x40000000)
    result = visibility(rows)
    assert result["selected_layer_i8"] == -1
    assert visible_indices(result) == [1]


@pytest.mark.parametrize(
    "address,width",
    [
        (0x80070348, 0x74),
        (0x80071668, 0x3C),
        (0x800716A4, 0x1D4),
        (0x80073BC8, 0x104),
        (0x80078930, 0x24),
    ],
)
def test_entire_row_gate_and_original_helpers_are_capture_witnesses(
    rows, address, width
):
    rows.bind(0)
    rows.ram[address - 0x80000000 + width - 1] ^= 1
    result = decode_native_map_row_visibility(rows.data, rows.executable, rows.ram, 0)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "capture"
    assert result.offset == address - 0x80000000


def test_additional_code_spans_cannot_replace_the_general_capture_witnesses(rows):
    rows.ram[0x11B80] ^= 1
    result = capture_failure(rows.executable, rows.ram, ((0x80070348, 0x74),))
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "capture"
    assert result.offset == 0x11B80


@pytest.mark.parametrize("record", [-1, 9, True, 0.0, "0", None])
def test_explicit_record_is_checked_before_capture_fields(rows, record):
    result = decode_native_map_row_visibility(rows.data, rows.executable, b"", record)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-input"


def test_executable_identity_precedes_capture_interpretation(rows):
    result = decode_native_map_row_visibility(
        rows.data, rows.executable + b"changed", b"", 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"


@pytest.mark.parametrize("failure", ["short", "code", "AB", "CC", "B4", "source"])
def test_mandatory_capture_and_loaded_source_witnesses_remain_required(rows, failure):
    rows.bind(0)
    if failure == "short":
        rows.ram.pop()
    elif failure == "code":
        rows.ram[0x11B80] ^= 1
    elif failure == "AB":
        rows.ram[0xE026B] = 1
    elif failure in ("CC", "B4"):
        struct.pack_into(
            "<I", rows.ram, 0xE028C if failure == "CC" else 0xE0274, 0xA01B0000
        )
    else:
        rows.ram[0x1B0000 + 552] ^= 1
    result = decode_native_map_row_visibility(rows.data, rows.executable, rows.ram, 0)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == (
        "capture" if failure in ("short", "code") else "map-selection-binding"
    )


def test_variant_bit_does_not_replace_a_retained_source_and_other_fields_are_unused(
    rows,
):
    rows.bind(0)
    before = visibility(rows)
    struct.pack_into("<I", rows.ram, 0xCC858, 0x80)
    struct.pack_into("<H", rows.ram, 0xE0278, 0xFFFF)
    rows.ram[0xCCBCD] = 255
    assert visibility(rows) == before
    result = decode_native_map_row_visibility(rows.data, rows.executable, rows.ram, 7)
    assert isinstance(result, RoomFormatFailure)
    assert "source" in result.detail


@pytest.mark.parametrize("count,accepted", [(256, True), (257, False)])
def test_source_row_count_respects_the_native_byte_domain(rows, count, accepted):
    record = bytearray(4096)
    directory_size = 4 + count * 8
    struct.pack_into("<I", record, 0, 4)
    offset = 36
    for section, size in enumerate((directory_size, 60, 4, 4)):
        struct.pack_into("<II", record, 4 + section * 8, offset, size)
        offset += size
    struct.pack_into("<I", record, 36, count)
    for row in range(count):
        struct.pack_into("<IHH", record, 40 + row * 8, directory_size, 0, 0)
    projection = 36 + directory_size
    struct.pack_into("<8I", record, projection, 32, 40, 48, 52, 56, 0, 0, 0)
    record[projection + 52] = 255
    rows.data = record + rows.data[2048:]
    rows.bind(0)
    result = decode_native_map_row_visibility(rows.data, rows.executable, rows.ram, 0)
    if accepted:
        assert not isinstance(result, RoomFormatFailure)
        assert len(result["rows"]) == count
    else:
        assert isinstance(result, RoomFormatFailure)
        assert result.kind == "map-selection-source"
