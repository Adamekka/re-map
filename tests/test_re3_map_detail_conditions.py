"""RE3-MAP-010: original synthetic group-1 admission and style tables."""

import struct

import pytest
from test_re3_map_binding import context as context

from games.re3.map_conditions import decode_map_detail_conditions
from games.re3.room_data import RoomFormatFailure


@pytest.fixture
def details(context):
    starts = []
    for index in range(9):
        base = index * 2048
        section, old_size = struct.unpack_from("<II", context.data, base + 12)
        style = struct.unpack_from("<I", context.data, base + section + 8)[0]
        size = style + 384
        struct.pack_into("<I", context.data, base + 16, size)
        struct.pack_into(
            "<2I", context.data, base + section + 12, style + 128, style + 256
        )
        # Header word 5 is zero in the owned records, not the admission bound.
        struct.pack_into("<I", context.data, base + section + 20, 0)
        for slot in (2, 3):
            at = base + 4 + slot * 8
            offset = struct.unpack_from("<I", context.data, at)[0]
            struct.pack_into("<I", context.data, at, offset + size - old_size)
        locations = [base + section + style + i * 128 for i in range(3)]
        for start in locations:
            context.data[start] = 255
        starts.append(locations)
    return context, starts


@pytest.mark.parametrize("index", range(9))
def test_all_records_export_bounded_empty_tables_and_full_section_prefix(
    details, index
):
    context, starts = details
    result = decode_map_detail_conditions(context.data, context.executable)
    assert not isinstance(result, RoomFormatFailure)
    record = result["records"][index]
    for name, start, key in (
        ("style", starts[index][0], "conditions"),
        ("admission", starts[index][2], "requirements"),
    ):
        assert record[name] == {
            "table_offset": start,
            "bounded_size": 128,
            "terminator_offset": start,
            key: [],
        }
    assert record["source_prefix_size"] == starts[index][2] + 128 - index * 2048
    assert result["primitive_group"] == 1
    assert result["shape_selection"] == result["tracker_visibility"] == "unresolved"
    assert all(key not in result for key in ("rooms", "visited", "completion"))


@pytest.mark.parametrize(
    "control,bank,acquisition",
    [
        (0, 0x800D20CC, False),
        (1, 0x800D1FA0, False),
        (2, 0x800D20CC, False),
        (3, 0x800D1FA0, False),
        (0x10, 0x800D20CC, True),
        (0x11, 0x800D1FA0, True),
        (0xE0, 0x800D20CC, False),
        (255, 0x800D1FA0, True),
    ],
)
def test_admission_uses_only_bank_bit_zero_and_retains_other_control_bits(
    details, control, bank, acquisition
):
    context, starts = details
    start = starts[0][2]
    context.data[start : start + 5] = bytes((9, 3, 32, control, 255))
    result = decode_map_detail_conditions(context.data, context.executable)
    assert result["records"][0]["admission"]["requirements"] == [
        {
            "offset": start,
            "row_index": 9,
            "primitive_index": 3,
            "flag_index": 32,
            "control_byte": control,
            "reject_if_acquisition_byte_clear": acquisition,
            "flag_bank_address_ps1": bank,
            "flag_word_address_ps1": bank + 4,
            "flag_word_mask": 0x80000000,
        }
    ]


@pytest.mark.parametrize(
    "selector,bank",
    [(0, 0x800D20CC), (1, 0x800D1FA0), (2, 0x800D1FC8), (3, 0x800D1FE8)],
)
@pytest.mark.parametrize(
    "index,offset,mask",
    [(0, 0, 0x80000000), (31, 0, 1), (32, 4, 0x80000000), (255, 28, 1)],
)
def test_style_has_four_exact_banks_and_native_msb_word_boundaries(
    details, selector, bank, index, offset, mask
):
    context, starts = details
    start = starts[0][0]
    context.data[start : start + 5] = bytes((2, 7, index, selector, 255))
    result = decode_map_detail_conditions(context.data, context.executable)
    assert result["records"][0]["style"]["conditions"] == [
        {
            "offset": start,
            "row_index": 2,
            "primitive_index": 7,
            "flag_index": index,
            "bank_selector": selector,
            "kind": "flag-test",
            "flag_bank_address_ps1": bank,
            "flag_word_address_ps1": bank + offset,
            "flag_word_mask": mask,
        }
    ]


@pytest.mark.parametrize("selector", [4, 16, 255])
def test_unknown_style_selector_is_explicitly_ignored_without_a_fallback_bank(
    details, selector
):
    context, starts = details
    start = starts[0][0]
    context.data[start : start + 5] = bytes((2, 7, 255, selector, 255))
    result = decode_map_detail_conditions(context.data, context.executable)
    assert result["records"][0]["style"]["conditions"] == [
        {
            "offset": start,
            "row_index": 2,
            "primitive_index": 7,
            "flag_index": 255,
            "bank_selector": selector,
            "kind": "ignored-bank-selector",
        }
    ]


@pytest.mark.parametrize(
    "name,slot,key", [("style", 0, "conditions"), ("admission", 2, "requirements")]
)
def test_duplicate_targets_and_order_are_not_collapsed(details, name, slot, key):
    context, starts = details
    start = starts[0][slot]
    context.data[start : start + 13] = bytes(
        (1, 2, 31, 0, 1, 2, 32, 1, 1, 2, 31, 0, 255)
    )
    result = decode_map_detail_conditions(context.data, context.executable)
    entries = result["records"][0][name][key]
    assert [entry["flag_index"] for entry in entries] == [31, 32, 31]
    assert [entry["offset"] for entry in entries] == [start, start + 4, start + 8]


@pytest.mark.parametrize("word5", [0, 1, 0xFFFFFFFF])
def test_opaque_header_word_five_cannot_bound_group_one_admission(details, word5):
    context, starts = details
    section = struct.unpack_from("<I", context.data, 12)[0]
    struct.pack_into("<I", context.data, section + 20, word5)
    start = starts[0][2]
    context.data[start : start + 5] = bytes((1, 2, 255, 17, 255))
    result = decode_map_detail_conditions(context.data, context.executable)
    assert result["records"][0]["admission"]["requirements"][0]["flag_index"] == 255


@pytest.mark.parametrize("slot", [0, 2])
def test_a_terminator_outside_its_table_cannot_rescue_the_scan(details, slot):
    context, starts = details
    start = starts[0][slot]
    context.data[start : start + 128] = bytes(128)
    context.data[start + 128] = 255
    result = decode_map_detail_conditions(context.data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.offset == start
    assert "terminator" in result.detail


@pytest.mark.parametrize("size", [1, 2, 3])
def test_style_non_sentinel_entry_cannot_cross_into_group_zero_table(details, size):
    context, starts = details
    section = struct.unpack_from("<I", context.data, 12)[0]
    start = starts[0][0]
    struct.pack_into("<I", context.data, section + 12, start - section + size)
    context.data[start] = 1
    result = decode_map_detail_conditions(context.data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.offset == start
    assert "truncated" in result.detail


def test_style_sentinel_does_not_read_the_other_three_bytes(details):
    context, starts = details
    section = struct.unpack_from("<I", context.data, 12)[0]
    start = starts[0][0]
    struct.pack_into("<I", context.data, section + 12, start - section + 1)
    result = decode_map_detail_conditions(context.data, context.executable)
    assert not isinstance(result, RoomFormatFailure)
    assert result["records"][0]["style"]["conditions"] == []


@pytest.mark.parametrize("sentinel", [False, True])
def test_admission_at_section_end_checks_sentinel_before_full_entry_width(
    details, sentinel
):
    context, starts = details
    section, old_size = struct.unpack_from("<II", context.data, 12)
    start = starts[0][2]
    size = start - section + 1
    struct.pack_into("<I", context.data, 16, size)
    for slot in (2, 3):
        at = 4 + slot * 8
        offset = struct.unpack_from("<I", context.data, at)[0]
        struct.pack_into("<I", context.data, at, offset + size - old_size)
    context.data[start] = 255 if sentinel else 1
    result = decode_map_detail_conditions(context.data, context.executable)
    if sentinel:
        assert not isinstance(result, RoomFormatFailure)
        assert result["records"][0]["admission"]["requirements"] == []
    else:
        assert isinstance(result, RoomFormatFailure)
        assert result.offset == start
        assert "truncated" in result.detail


def test_late_admission_failure_returns_no_partial_tables(details):
    context, starts = details
    start = starts[8][2]
    context.data[start : start + 128] = bytes(128)
    result = decode_map_detail_conditions(context.data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.offset == start


def test_owned_executable_identity_remains_required_before_reading_tables(details):
    context, _ = details
    result = decode_map_detail_conditions(
        context.data, context.executable + b"modified"
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"
