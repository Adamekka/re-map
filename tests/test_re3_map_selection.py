"""RE3-MAP-009: synthetic source binding and copied-native predicate cases."""

import struct

import pytest
from test_re3_map_binding import context as context
from test_re3_map_conditions import tables as tables

from games.re3.map_selection import decode_native_map_selection
from games.re3.map_shape_predicates import group_zero_shape_allowed
from games.re3.room_data import RoomFormatFailure


@pytest.fixture
def selected(tables):
    context, starts = tables
    context.table_starts = starts
    # Distinct original geometry makes a wrong-record witness observable.
    # Identical synthetic records would legitimately match the same bytes.
    for record in range(9):
        struct.pack_into("<h", context.data, record * 2048 + 558, 7 + record)

    def bind(record):
        base = record * 2048
        section = struct.unpack_from("<I", context.data, base + 12)[0]
        end = section + struct.unpack_from("<I", context.data, base + section + 16)[0]
        context.ram[0x1B0000 : 0x1B0000 + end] = context.data[base : base + end]
        struct.pack_into("<I", context.ram, 0xE028C, 0x801B0000)
        struct.pack_into("<I", context.ram, 0xE0274, 0x801B0000 + section)
        context.ram[0xE026B] = record if record < 7 else record - 7
        return end

    context.bind = bind
    return context


@pytest.mark.parametrize("record", range(9))
def test_all_explicit_records_bind_without_inferring_visits(selected, record):
    size = selected.bind(record)
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, record
    )
    assert not isinstance(result, RoomFormatFailure)
    assert result["selected_record_index"] == record
    assert result["selected_native_group"] == (record if record < 7 else record - 7)
    assert result["loaded_source_prefix_bytes"] == size
    assert result["rows"][0] == {
        "index": 0,
        "group0_count": 1,
        "group0_allowed_indices": [0],
    }
    assert result["native_row_visibility"] == "unchecked"
    assert all(
        result[key] == "unresolved"
        for key in (
            "group1_selection",
            "room_ownership",
            "campaign_admission",
            "tracker_visibility",
        )
    )
    assert all(key not in result for key in ("rooms", "visited", "completion"))


@pytest.mark.parametrize("record", [-1, 9, True, 1.0, "0", None])
def test_invalid_explicit_record_is_a_modeled_failure(selected, record):
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, record
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-input"


def test_executable_identity_precedes_snapshot_interpretation(selected):
    result = decode_native_map_selection(
        selected.data, selected.executable + b"changed", b"", 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"


@pytest.mark.parametrize("failure", ["short", "code"])
def test_capture_size_and_code_witnesses_are_required(selected, failure):
    selected.bind(0)
    if failure == "short":
        selected.ram.pop()
    else:
        selected.ram[0x11B80] ^= 1
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "capture"


@pytest.mark.parametrize("field", [0xE028C, 0xE0274])
@pytest.mark.parametrize(
    "pointer", [0, 1, 0x1B0000, 0xA01B0000, 0x801FFFFC, 0x80200000, 0xFFFFFFFF]
)
def test_invalid_or_unrelated_pointers_fail_explicitly(selected, field, pointer):
    selected.bind(0)
    struct.pack_into("<I", selected.ram, field, pointer)
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-binding"
    assert result.offset == field


@pytest.mark.parametrize("at", [0, 40, 552, 1120])
def test_header_directory_geometry_and_requirements_are_one_source_witness(
    selected, at
):
    selected.bind(0)
    selected.ram[0x1B0000 + at] ^= 1
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-selection-binding"
    assert "source prefix" in result.detail


def test_bytes_after_the_required_prefix_are_outside_this_witness(selected):
    size = selected.bind(0)
    selected.ram[0x1B0000 + size] ^= 1
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert not isinstance(result, RoomFormatFailure)


def test_browsed_group_does_not_require_current_location_to_match(selected):
    selected.bind(5)
    selected.ram[0xE026A] = 0
    selected.ram[0xE026C] = 13
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 5
    )
    assert result["current_native_key"] == 13
    assert result["selected_native_group"] == 5
    selected.ram[0xE026B] = 0
    mismatch = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 5
    )
    assert isinstance(mismatch, RoomFormatFailure)
    assert mismatch.offset == 0xE026B


def test_current_variant_bit_does_not_silently_replace_the_loaded_source(selected):
    selected.bind(0)
    struct.pack_into("<I", selected.ram, 0xCC858, 0x80)
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert result["selected_record_index"] == 0
    wrong = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 7
    )
    assert isinstance(wrong, RoomFormatFailure)
    assert "source" in wrong.detail


def test_metadata_duplicates_conjoin_and_acquisition_reverses_without_a_cache(selected):
    start = selected.table_starts[5]
    selected.data[start : start + 9] = bytes((0, 0, 31, 0, 0, 0, 32, 255, 255))
    selected.bind(5)

    def allowed():
        result = decode_native_map_selection(
            selected.data, selected.executable, selected.ram, 5
        )
        assert not isinstance(result, RoomFormatFailure)
        return result["rows"][0]["group0_allowed_indices"]

    assert allowed() == []
    struct.pack_into("<I", selected.ram, 0xD20CC, 1)
    assert allowed() == []
    struct.pack_into("<I", selected.ram, 0xD1FA4, 0x80000000)
    assert allowed() == [0]
    struct.pack_into("<I", selected.ram, 0xD20CC, 0)
    assert allowed() == []
    struct.pack_into("<I", selected.ram, 0xD2124, 0x04000000)
    assert allowed() == [0]
    struct.pack_into("<I", selected.ram, 0xD2124, 0)
    assert allowed() == []


def test_acquisition_bypasses_metadata_but_cannot_bypass_overlay_selection(selected):
    start = selected.table_starts[0]
    selected.data[start : start + 5] = bytes((0, 0, 32, 0, 255))
    selected.bind(0)
    struct.pack_into("<I", selected.ram, 0xD2124, 0x80000000)
    struct.pack_into("<H", selected.ram, 0xE0278, 1)
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert result["native_map_acquired"]
    assert result["rows"][0]["group0_allowed_indices"] == []
    struct.pack_into("<H", selected.ram, 0xE0278, 0)
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert result["rows"][0]["group0_allowed_indices"] == [0]


def test_late_override_cannot_bypass_metadata(selected):
    start = selected.table_starts[0]
    selected.data[start : start + 5] = bytes((0, 0, 32, 0, 255))
    selected.bind(0)
    struct.pack_into("<I", selected.ram, 0xCC858, 0x80)
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert result["rows"][0]["group0_allowed_indices"] == []


def test_flag_dependent_geometry_reverses_after_an_earlier_snapshot(selected):
    selected.bind(3)
    before = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 3
    )
    assert before["rows"][0]["group0_allowed_indices"] == [0]
    struct.pack_into("<I", selected.ram, 0xD1FB4, 0x10)
    after = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 3
    )
    assert after["rows"][0]["group0_allowed_indices"] == []
    struct.pack_into("<I", selected.ram, 0xD1FB4, 0)
    assert (
        decode_native_map_selection(selected.data, selected.executable, selected.ram, 3)
        == before
    )


@pytest.mark.parametrize(
    "rows,quads,accepted",
    [(257, 0, False), (1, 257, False), (256, 0, True), (1, 256, True)],
)
def test_native_byte_arguments_have_explicit_supported_source_bounds(
    selected, rows, quads, accepted
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
            "<IHH", record, 40 + row * 8, 4 + rows * 8, quads if row == 0 else 0, 0
        )
    struct.pack_into("<8I", record, projection, 32, 40, 48, 52, 56, 0, 0, 0)
    record[projection + 52] = 255
    selected.data = record + selected.data[2048:]
    selected.bind(0)
    result = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    if accepted:
        assert not isinstance(result, RoomFormatFailure)
        assert len(result["rows"]) == rows
        assert result["rows"][0]["group0_count"] == quads
    else:
        assert isinstance(result, RoomFormatFailure)
        assert result.kind == "map-selection-source"


def test_signed_phase_is_reread_on_earlier_snapshot_reversal(selected):
    selected.bind(0)
    selected.ram[0xE026C] = 1
    selected.ram[0xCCBCD] = 255
    before = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert before["phase_i8"] == -1
    assert before["rows"][0]["group0_allowed_indices"] == []
    selected.ram[0xCCBCD] = 4
    after = decode_native_map_selection(
        selected.data, selected.executable, selected.ram, 0
    )
    assert after["rows"][0]["group0_allowed_indices"] == [0]
    selected.ram[0xCCBCD] = 255
    assert (
        decode_native_map_selection(selected.data, selected.executable, selected.ram, 0)
        == before
    )


@pytest.mark.parametrize(
    "group,row,quad,key,phase,overlay,bits,expected",
    [
        (0, 0, 0, 0x6FF, 0, 1, (), False),
        (0, 0, 0, 0x6FF, 0, 0, (), True),
        (0, 1, 0, 1, 2, 0, (), True),
        (0, 1, 1, 1, 2, 0, (), False),
        (0, 1, 0, 1, 3, 0, (), False),
        (0, 1, 1, 1, 3, 0, (), True),
        (1, 11, 3, 0x10A, 3, 0, (), False),
        (1, 16, 2, 0x110, 4, 0, (), True),
        (1, 16, 2, 0x110, 3, 0, (), False),
        (3, 12, 0, 0x6FF, 0, 0, (), False),
        (3, 12, 0, 0x6FF, 0, 0, ((0x800D20CC, 9),), True),
        (4, 7, 1, 0x6FF, 0, 0, (), False),
        (4, 7, 1, 0x6FF, 0, 0, ((0x800D258C, 69),), True),
        (0, 4, 1, 0x6FF, 0, 0, (), False),
        (0, 4, 1, 0x6FF, 0, 0, ((0x800CC858, 24),), True),
        (0, 1, 0, 0x6FF, 0, 0, ((0x800CC858, 24),), False),
        (0, 0, 1, 0x6FF, 0, 0, ((0x800CC858, 24),), False),
    ],
)
def test_native_shape_boundaries_and_late_override_scope(
    group, row, quad, key, phase, overlay, bits, expected
):
    assert (
        group_zero_shape_allowed(
            group,
            row,
            quad,
            key,
            phase,
            overlay,
            lambda bank, index: (bank, index) in bits,
        )
        is expected
    )


@pytest.mark.parametrize("raw_phase", range(256))
def test_native_signed_threshold_includes_every_byte_encoding(raw_phase):
    phase = raw_phase if raw_phase < 128 else raw_phase - 256
    assert group_zero_shape_allowed(
        0, 1, 0, 1, phase, 0, lambda bank, index: False
    ) is (phase < 3)
