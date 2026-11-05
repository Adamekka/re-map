"""RE3-MAP-008: original synthetic native quad requirement tables."""

import struct

import pytest
from test_re3_map_binding import context as context

from games.re3.map_conditions import decode_map_conditions
from games.re3.room_data import RoomFormatFailure


@pytest.fixture
def tables(context):
    starts = []
    for index in range(9):
        base = index * 2048
        start, size = struct.unpack_from("<II", context.data, base + 12)
        struct.pack_into("<I", context.data, base + 16, size + 128)
        for section in (2, 3):
            offset = base + 4 + section * 8
            old = struct.unpack_from("<I", context.data, offset)[0]
            struct.pack_into("<I", context.data, offset, old + 128)
        table = struct.unpack_from("<I", context.data, base + start + 12)[0]
        struct.pack_into("<I", context.data, base + start + 16, table + 128)
        context.data[base + start + table] = 0xFF
        starts.append(base + start + table)
    return context, starts


def test_identity_is_required_before_metadata_parsing(tables):
    context, _ = tables
    result = decode_map_conditions(context.data, context.executable + b"changed")
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"


@pytest.mark.parametrize("record", range(9))
def test_empty_tables_and_all_records_preserve_source_offsets(tables, record):
    context, starts = tables
    result = decode_map_conditions(context.data, context.executable)
    assert not isinstance(result, RoomFormatFailure)
    assert result["records"][record] == {
        "index": record,
        "table_offset": starts[record],
        "bounded_size": 128,
        "terminator_offset": starts[record],
        "requirements": [],
    }
    assert result["status"] == "candidate-source-conditions"
    assert result["shape_selection"] == result["tracker_visibility"] == "unresolved"
    assert result["primitive_group"] == 0
    assert all(key not in result for key in ("rooms", "visited", "completion"))


@pytest.mark.parametrize(
    "selector,bank", [(0, 0x800D20CC), (1, 0x800D1FA0), (255, 0x800D1FA0)]
)
@pytest.mark.parametrize(
    "index,word_offset,mask",
    [(0, 0, 0x80000000), (31, 0, 1), (32, 4, 0x80000000), (255, 28, 1)],
)
def test_native_selector_and_msb_word_boundaries(
    tables, selector, bank, index, word_offset, mask
):
    context, starts = tables
    start = starts[0]
    context.data[start : start + 5] = bytes((3, 2, index, selector, 255))
    result = decode_map_conditions(context.data, context.executable)
    assert result["records"][0]["requirements"] == [
        {
            "offset": start,
            "row_index": 3,
            "primitive_index": 2,
            "flag_index": index,
            "bank_selector": selector,
            "flag_bank_address_ps1": bank,
            "flag_word_address_ps1": bank + word_offset,
            "flag_word_mask": mask,
        }
    ]


def test_duplicate_targets_preserve_every_ordered_requirement(tables):
    context, starts = tables
    start = starts[0]
    context.data[start : start + 13] = bytes(
        (4, 1, 31, 0, 4, 1, 32, 2, 4, 1, 31, 0, 255)
    )
    result = decode_map_conditions(context.data, context.executable)
    entries = result["records"][0]["requirements"]
    assert [
        (row["row_index"], row["primitive_index"], row["flag_index"]) for row in entries
    ] == [(4, 1, 31), (4, 1, 32), (4, 1, 31)]
    assert [row["offset"] for row in entries] == [start, start + 4, start + 8]


@pytest.mark.parametrize("size", [1, 2, 3, 4])
def test_sentinel_consumes_only_its_first_byte(tables, size):
    context, starts = tables
    section = struct.unpack_from("<I", context.data, 12)[0]
    table = starts[0] - section
    struct.pack_into("<I", context.data, section + 16, table + size)
    context.data[starts[0] : starts[0] + 4] = b"\xff\x03\x02\x01"
    result = decode_map_conditions(context.data, context.executable)
    assert not isinstance(result, RoomFormatFailure)
    assert result["records"][0]["requirements"] == []


@pytest.mark.parametrize("size", [1, 2, 3])
def test_partial_non_sentinel_entry_is_rejected_before_crossing_extent(tables, size):
    context, starts = tables
    section = struct.unpack_from("<I", context.data, 12)[0]
    struct.pack_into("<I", context.data, section + 16, starts[0] - section + size)
    context.data[starts[0]] = 1
    result = decode_map_conditions(context.data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-conditions"
    assert result.offset == starts[0]
    assert "truncated" in result.detail


def test_terminator_in_next_section_does_not_rescue_an_unterminated_table(tables):
    context, starts = tables
    start = starts[0]
    context.data[start : start + 128] = bytes(128)
    context.data[start + 128] = 255
    result = decode_map_conditions(context.data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-conditions"
    assert result.offset == start
    assert "terminator" in result.detail


def test_late_failure_returns_no_partial_export(tables):
    context, starts = tables
    context.data[starts[8] : starts[8] + 128] = bytes(128)
    result = decode_map_conditions(context.data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.offset == starts[8]
