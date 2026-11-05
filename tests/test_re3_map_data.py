"""RE3-MAP-001/002: synthetic drawing records, never gameplay evidence."""

import hashlib
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re3 import map_data
from games.re3.room_data import RoomFormatFailure

SYNTHETIC_EXECUTABLE = b"original synthetic executable identity for map tests"


@pytest.fixture
def synthetic_identity(monkeypatch):
    # Owned executable bytes must never enter fixtures. Replace only the hash
    # gate so the same required identity check runs on original synthetic data.
    monkeypatch.setattr(
        map_data, "EXECUTABLE_SHA256", hashlib.sha256(SYNTHETIC_EXECUTABLE).hexdigest()
    )


def synthetic_map():
    data = bytearray(2048)
    struct.pack_into("<I", data, 0, 4)
    for index, (offset, size) in enumerate(((36, 64), (100, 4), (104, 4), (108, 4))):
        struct.pack_into("<II", data, 4 + index * 8, offset, size)
    struct.pack_into("<I", data, 36, 3)
    for index, (offset, first, second) in enumerate(
        ((28, 1, 1), (28, 0, 0), (52, 1, 0))
    ):
        struct.pack_into("<IHH", data, 40 + index * 8, offset, first, second)
    for offset, values in (
        (64, (11, 22, 14, 26, -17, 31, 7, 3, 201, 255)),
        (76, (40, 50, 40, 50, 1, -2, 4, 0, 0, 0)),
        (88, (9, 8, 5, 4, 100, -100, 0, 2, 0, 0)),
    ):
        struct.pack_into("<4B2h4B", data, offset, *values)
    return data


def test_executable_identity_is_required_before_parsing():
    result = map_data.decode_map_primitives(b"", SYNTHETIC_EXECUTABLE)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"


def test_modified_executable_is_rejected(synthetic_identity):
    result = map_data.decode_map_primitives(
        synthetic_map(), SYNTHETIC_EXECUTABLE + b"x"
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"


def test_groups_keep_inclusive_endpoints_signed_destinations_and_opaque_style(
    synthetic_identity,
):
    result = map_data.decode_map_primitives(synthetic_map(), SYNTHETIC_EXECUTABLE)
    assert not isinstance(result, RoomFormatFailure)
    row = result["records"][0]["directory"][0]
    assert row["attributes"] == [1, 1]
    assert row["primitive_groups"] == [
        [
            {
                "offset": 64,
                "uv_inclusive": [11, 22, 14, 26],
                "destination_xyxy": [-17, 31, -13, 36],
                "style_bytes": [7, 3, 201, 255],
            }
        ],
        [
            {
                "offset": 76,
                "uv_inclusive": [40, 50, 40, 50],
                "destination_xyxy": [1, -2, 2, -1],
                "style_bytes": [4, 0, 0, 0],
            }
        ],
    ]
    assert row["unconsumed_size"] == 0
    assert result["geometry_kind"] == "textured-quads"
    assert result["spatial_semantics"] == result["room_floor_binding"] == "unresolved"
    assert result["evidence_kind"] == "offline-only"
    assert all(
        key not in result
        for key in ("rooms", "floors", "items", "doors", "completion", "visited")
    )


def test_reversed_endpoints_preserve_directed_geometry_instead_of_wrapping(
    synthetic_identity,
):
    result = map_data.decode_map_primitives(synthetic_map(), SYNTHETIC_EXECUTABLE)
    row = result["records"][0]["directory"][2]
    assert row["primitive_groups"][0][0]["destination_xyxy"] == [100, -100, 97, -103]


def test_zero_count_alias_preserves_the_envelope_without_reading_its_bytes(
    synthetic_identity,
):
    result = map_data.decode_map_primitives(synthetic_map(), SYNTHETIC_EXECUTABLE)
    first, alias, _ = result["records"][0]["directory"]
    assert first["offset"] == alias["offset"] == 28
    assert alias["primitive_groups"] == [[], []]
    assert alias["unconsumed_size"] == first["bounded_size"] == 24


def test_aliases_can_select_different_groups_without_reordering_the_directory(
    synthetic_identity,
):
    data = synthetic_map()
    struct.pack_into("<IHH", data, 48, 28, 0, 2)
    result = map_data.decode_map_primitives(data, SYNTHETIC_EXECUTABLE)
    first, alias, last = result["records"][0]["directory"]
    assert [r["index"] for r in (first, alias, last)] == [0, 1, 2]
    assert alias["primitive_groups"] == [
        [],
        first["primitive_groups"][0] + first["primitive_groups"][1],
    ]


def test_unsorted_rows_and_record_relative_offsets_remain_source_ordered(
    synthetic_identity,
):
    data = synthetic_map()
    first, last = data[40:48], data[56:64]
    data[40:48], data[56:64] = last, first
    result = map_data.decode_map_primitives(data * 2, SYNTHETIC_EXECUTABLE)
    assert [r["offset"] for r in result["records"]] == [0, 2048]
    for index, record in enumerate(result["records"]):
        rows = record["directory"]
        assert [r["offset"] for r in rows] == [52, 28, 28]
        assert rows[0]["primitive_groups"][0][0]["offset"] == 88 + index * 2048
        assert rows[2]["primitive_groups"][1][0]["offset"] == 76 + index * 2048


def test_uncounted_tail_is_explicit_instead_of_becoming_extra_quads(synthetic_identity):
    data = synthetic_map()
    struct.pack_into("<H", data, 46, 0)
    result = map_data.decode_map_primitives(data, SYNTHETIC_EXECUTABLE)
    row = result["records"][0]["directory"][0]
    assert [len(group) for group in row["primitive_groups"]] == [1, 0]
    assert row["unconsumed_size"] == 12


@pytest.mark.parametrize("field", [44, 46, 60, 62])
@pytest.mark.parametrize("count", [3, 0xFFFF])
def test_counts_cannot_cross_the_next_distinct_payload_or_section_end(
    synthetic_identity, field, count
):
    data = synthetic_map()
    struct.pack_into("<H", data, field, count)
    result = map_data.decode_map_primitives(data, SYNTHETIC_EXECUTABLE)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-primitives"
    assert result.offset == (44 if field < 48 else 60)


def test_zero_length_payload_is_allowed_only_with_zero_counts(synthetic_identity):
    data = synthetic_map()
    struct.pack_into("<IHH", data, 56, 64, 0, 0)
    result = map_data.decode_map_primitives(data, SYNTHETIC_EXECUTABLE)
    assert not isinstance(result, RoomFormatFailure)
    assert result["records"][0]["directory"][2]["unconsumed_size"] == 0
    struct.pack_into("<H", data, 60, 1)
    assert isinstance(
        map_data.decode_map_primitives(data, SYNTHETIC_EXECUTABLE), RoomFormatFailure
    )


@pytest.mark.parametrize("size", [0, 35, 63, 87, 99, 112, 2047])
def test_truncated_input_is_a_modeled_map_failure(synthetic_identity, size):
    result = map_data.decode_map_primitives(
        synthetic_map()[:size], SYNTHETIC_EXECUTABLE
    )
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map"


def test_bad_later_record_returns_no_partial_export(synthetic_identity):
    data = synthetic_map() * 2
    struct.pack_into("<H", data, 2048 + 44, 3)
    result = map_data.decode_map_primitives(data, SYNTHETIC_EXECUTABLE)
    assert isinstance(result, RoomFormatFailure)
    assert result.offset == 2048 + 44
