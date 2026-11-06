"""RE3-MAP-011: bound group-1 admission, style and fresh snapshot state."""

import struct

import pytest
from test_re3_map_binding import context as context
from test_re3_map_detail_conditions import details as details

from games.re3.map_selection import decode_native_map_detail_selection
from games.re3.room_data import RoomFormatFailure


@pytest.fixture
def selected_details(details):
    context, starts = details
    context.table_starts = starts
    for record in range(9):
        base = record * 2048
        # Shared original quads exercise predicates at every numeric row.
        # Their distinct coordinates also expose a wrong explicit record.
        for row in range(64):
            struct.pack_into("<HH", context.data, base + 44 + row * 8, 0, 1)
        struct.pack_into("<h", context.data, base + 558, 7 + record)
        context.data[base + 560] = 4

    def bind(record):
        base = record * 2048
        section, size = struct.unpack_from("<II", context.data, base + 12)
        end = section + size
        context.ram[0x1B0000 : 0x1B0000 + end] = context.data[base : base + end]
        struct.pack_into("<I", context.ram, 0xE028C, 0x801B0000)
        struct.pack_into("<I", context.ram, 0xE0274, 0x801B0000 + section)
        context.ram[0xE026B] = record if record < 7 else record - 7
        return end

    context.bind = bind
    return context


def selection(selected, record=5):
    result = decode_native_map_detail_selection(
        selected.data, selected.executable, selected.ram, record
    )
    assert not isinstance(result, RoomFormatFailure), result
    return result


def allowed(result, row=40):
    return result["rows"][row]["group1_allowed"]


PLAIN = {
    "index": 0,
    "requested_palette_variant": 0,
    "effective_palette_variant": 0,
}
STYLED = {
    "index": 0,
    "requested_palette_variant": 2,
    "effective_palette_variant": 2,
}


@pytest.mark.parametrize("record", range(9))
def test_explicit_record_binding_retains_unresolved_tracker_contracts(
    selected_details, record
):
    size = selected_details.bind(record)
    result = selection(selected_details, record)
    assert result["schema"] == "re3-native-map-detail-selection-v1"
    assert result["selected_record_index"] == record
    assert result["selected_native_group"] == (record if record < 7 else record - 7)
    assert result["loaded_source_prefix_bytes"] == size
    assert result["rows"][40] == {
        "index": 40,
        "group1_count": 1,
        "group1_allowed": [PLAIN],
    }
    assert result["native_row_visibility"] == "unchecked"
    assert all(
        result[key] == "unresolved"
        for key in ("room_ownership", "campaign_admission", "tracker_visibility")
    )
    assert all(key not in result for key in ("rooms", "visited", "completion"))


@pytest.mark.parametrize("record", [-1, 9, True, 1.0, "0", None])
def test_invalid_explicit_record_is_a_modeled_failure(selected_details, record):
    result = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable, selected_details.ram, record
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-input"


def test_identity_precedes_snapshot_interpretation(selected_details):
    result = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable + b"changed", b"", 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"


@pytest.mark.parametrize("failure", ["short", "code"])
def test_complete_capture_and_code_witnesses_are_required(selected_details, failure):
    selected_details.bind(0)
    if failure == "short":
        selected_details.ram.pop()
    else:
        selected_details.ram[0x11B80] ^= 1
    result = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable, selected_details.ram, 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "capture"


@pytest.mark.parametrize("field", [0xE028C, 0xE0274])
@pytest.mark.parametrize(
    "pointer", [0, 1, 0x1B0000, 0xA01B0000, 0x801FFFFC, 0x80200000, 0xFFFFFFFF]
)
def test_pointer_aliases_alignment_bounds_and_relationship_are_explicit(
    selected_details, field, pointer
):
    selected_details.bind(0)
    struct.pack_into("<I", selected_details.ram, field, pointer)
    result = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable, selected_details.ram, 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-binding"
    assert result.offset == field


@pytest.mark.parametrize("at", [0, 40, 552, "style", "admission", "last"])
def test_full_section_one_contiguous_source_witness(selected_details, at):
    size = selected_details.bind(0)
    if at == "style":
        at = selected_details.table_starts[0][0]
    elif at == "admission":
        at = selected_details.table_starts[0][2]
    elif at == "last":
        at = size - 1
    selected_details.ram[0x1B0000 + at] ^= 1
    result = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable, selected_details.ram, 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-binding"
    assert "source prefix" in result.detail


def test_mutable_sections_after_source_prefix_are_excluded(selected_details):
    size = selected_details.bind(0)
    selected_details.ram[0x1B0000 + size] ^= 1
    selection(selected_details, 0)


def test_current_location_browsed_group_and_retained_variant_are_independent(
    selected_details,
):
    selected_details.bind(5)
    selected_details.ram[0xE026A] = 0
    selected_details.ram[0xE026C] = 13
    assert selection(selected_details)["current_native_key"] == 13
    selected_details.ram[0xE026B] = 0
    result = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable, selected_details.ram, 5
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.offset == 0xE026B
    selected_details.bind(0)
    struct.pack_into("<I", selected_details.ram, 0xCC858, 0x80)
    assert selection(selected_details, 0)["selected_record_index"] == 0
    wrong = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable, selected_details.ram, 7
    )
    assert isinstance(wrong, RoomFormatFailure)
    assert "source" in wrong.detail


def test_duplicate_admission_entries_require_every_flag_clear_and_rewind(
    selected_details,
):
    start = selected_details.table_starts[5][2]
    selected_details.data[start : start + 9] = bytes((40, 0, 31, 0, 40, 0, 32, 3, 255))
    selected_details.bind(5)
    before = selection(selected_details)
    assert allowed(before) == [PLAIN]
    for address, mask in ((0xD20CC, 1), (0xD1FA4, 0x80000000)):
        struct.pack_into("<I", selected_details.ram, address, mask)
        assert allowed(selection(selected_details)) == []
        struct.pack_into("<I", selected_details.ram, address, 0)
        assert selection(selected_details) == before


@pytest.mark.parametrize(
    "record,mask",
    [
        (0, 0x80000000),
        (1, 0x40000000),
        (2, 0x20000000),
        (3, 0x10000000),
        (4, 0x08000000),
        (5, 0x04000000),
        (6, 0x02000000),
        (7, 0x80000000),
        (8, 0x40000000),
    ],
)
def test_native_acquisition_mask_truncates_to_zero_for_every_supported_group(
    selected_details, record, mask
):
    start = selected_details.table_starts[record][2]
    selected_details.data[start : start + 5] = bytes((40, 0, 0, 0x10, 255))
    selected_details.bind(record)
    assert allowed(selection(selected_details, record)) == []
    struct.pack_into("<I", selected_details.ram, 0xD2124, mask)
    result = selection(selected_details, record)
    assert result["native_map_acquisition_byte"] == 0
    assert allowed(result) == []


def test_system_early_return_skips_metadata_but_cannot_skip_prior_shape_tests(
    selected_details,
):
    start = selected_details.table_starts[0][2]
    selected_details.data[start : start + 5] = bytes((40, 0, 0, 0x10, 255))
    selected_details.bind(0)
    assert allowed(selection(selected_details, 0)) == []
    struct.pack_into("<I", selected_details.ram, 0xCC858, 0x80)
    selected_details.ram[0xE026C] = 1
    selected_details.ram[0xCCBCD] = 2
    result = selection(selected_details, 0)
    assert allowed(result) == [PLAIN]
    assert allowed(result, 0) == []
    assert allowed(result, 12) == [STYLED]


def test_later_group_system_mask_rejects_only_matching_metadata(selected_details):
    start = selected_details.table_starts[2][2]
    selected_details.data[start : start + 5] = bytes((40, 0, 0, 0, 255))
    selected_details.bind(2)
    assert allowed(selection(selected_details, 2)) == [PLAIN]
    struct.pack_into("<I", selected_details.ram, 0xCC858, 0x80)
    result = selection(selected_details, 2)
    assert allowed(result) == []
    assert allowed(result, 41) == [PLAIN]


@pytest.mark.parametrize(
    "selector,index,address,mask",
    [
        (0, 31, 0xD20CC, 1),
        (1, 32, 0xD1FA4, 0x80000000),
        (2, 255, 0xD1FE4, 1),
        (3, 0, 0xD1FE8, 0x80000000),
    ],
)
def test_style_clear_flag_exact_banks_and_word_boundaries(
    selected_details, selector, index, address, mask
):
    start = selected_details.table_starts[5][0]
    selected_details.data[start : start + 5] = bytes((40, 0, index, selector, 255))
    selected_details.bind(5)
    before = selection(selected_details)
    assert allowed(before) == [STYLED]
    struct.pack_into("<I", selected_details.ram, address, mask)
    assert allowed(selection(selected_details)) == [PLAIN]
    struct.pack_into("<I", selected_details.ram, address, 0)
    assert selection(selected_details) == before


def test_style_duplicates_are_alternatives_and_unknown_selectors_are_ignored(
    selected_details,
):
    start = selected_details.table_starts[5][0]
    selected_details.data[start : start + 13] = bytes(
        (40, 0, 0, 255, 40, 0, 31, 0, 40, 0, 32, 1, 255)
    )
    selected_details.bind(5)
    struct.pack_into("<I", selected_details.ram, 0xD20CC, 1)
    assert allowed(selection(selected_details)) == [STYLED]
    struct.pack_into("<I", selected_details.ram, 0xD1FA4, 0x80000000)
    assert allowed(selection(selected_details)) == [PLAIN]


def test_kind_seven_preserves_requested_variant_and_forces_effective_zero(
    selected_details,
):
    start = selected_details.table_starts[5][0]
    selected_details.data[start : start + 5] = bytes((40, 0, 0, 0, 255))
    selected_details.data[5 * 2048 + 560] = 7
    selected_details.bind(5)
    assert allowed(selection(selected_details)) == [
        {"index": 0, "requested_palette_variant": 2, "effective_palette_variant": 0}
    ]


def test_raw_stage_is_unsigned_and_independent_of_selected_group(selected_details):
    selected_details.bind(1)
    # Permit row 12 through its independent key/story family so this test
    # observes the later unsigned raw-stage exclusion.
    struct.pack_into("<I", selected_details.ram, 0xD200C, 0x40000000)
    for stage, expected in (
        (1, [PLAIN]),
        (2, []),
        (3, []),
        (4, []),
        (5, [PLAIN]),
        (0x8002, [PLAIN]),
    ):
        struct.pack_into("<H", selected_details.ram, 0xD1F76, stage)
        result = selection(selected_details, 1)
        assert result["raw_stage_u16"] == stage
        assert allowed(result, 12) == expected


@pytest.mark.parametrize(
    "rows,quads,accepted",
    [(257, 0, False), (1, 257, False), (256, 0, True), (1, 256, True)],
)
def test_group_one_native_byte_arguments_are_bounded(
    selected_details, rows, quads, accepted
):
    directory_size = 4 + rows * 8 + quads * 12
    projection = 36 + directory_size
    record = bytearray(4096)
    struct.pack_into("<I", record, 0, 4)
    offset = 36
    for section, size in enumerate((directory_size, 60, 4, 4)):
        struct.pack_into("<II", record, 4 + section * 8, offset, size)
        offset += size
    struct.pack_into("<I", record, 36, rows)
    for row in range(rows):
        struct.pack_into(
            "<IHH", record, 40 + row * 8, 4 + rows * 8, 0, quads if row == 0 else 0
        )
    struct.pack_into("<8I", record, projection, 32, 40, 48, 52, 56, 0, 0, 0)
    record[projection + 48] = record[projection + 52] = record[projection + 56] = 255
    selected_details.data = record + selected_details.data[2048:]
    selected_details.bind(0)
    result = decode_native_map_detail_selection(
        selected_details.data, selected_details.executable, selected_details.ram, 0
    )
    if accepted:
        assert not isinstance(result, RoomFormatFailure)
        assert len(result["rows"]) == rows
        assert result["rows"][0]["group1_count"] == quads
    else:
        assert isinstance(result, RoomFormatFailure)
        assert result.kind == "map-selection-source"
