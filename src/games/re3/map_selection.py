"""Candidate snapshot-bound map predicates for SLUS-00923. RE3-MAP-009/011/012.

Native row visibility, physical room ownership and tracker visits are separate.
"""

from __future__ import annotations

import struct
from enum import Enum
from typing import NamedTuple

from games.bit_flags import msb_flag_location
from games.re3.capture_data import capture_failure
from games.re3.map_conditions import (
    decode_map_conditions,
    decode_map_detail_conditions,
    detail_metadata,
    group_zero_metadata_allows,
    quad_requirements,
)
from games.re3.map_data import decode_map_layout, native_group_for_record
from games.re3.map_detail_predicates import (
    DetailSelection,
    select_group_one_detail,
)
from games.re3.map_predicate import FlagReader
from games.re3.map_row_predicates import native_row_visible
from games.re3.map_shape_predicates import group_zero_shape_allowed
from games.re3.room_data import RoomFormatFailure


class _SelectionScope(Enum):
    GroupZero = "group-zero"
    GroupOne = "group-one"
    Rows = "rows"


# RE3-MAP-012 compares the complete gate/helper code too. The four general
# capture windows alone do not witness these particular native instructions.
_ROW_GATE_CODE_WINDOWS = (
    (0x80070348, 0x74),
    (0x80071668, 0x3C),
    (0x800716A4, 0x1D4),
    (0x80073BC8, 0x104),
    (0x80078930, 0x24),
)


class _BoundMapSelection(NamedTuple):
    layout: dict
    record: dict
    table: dict
    native_group: int
    prefix_size: int
    flag: FlagReader


def _bind_selected_map_source(
    data: bytes,
    executable: bytes,
    ram: bytes,
    selected_record_index: int,
    scope: _SelectionScope,
    condition_records: list[dict],
) -> _BoundMapSelection | RoomFormatFailure:
    """Bind decoded table info before either source selection can evaluate RAM."""
    assert isinstance(scope, _SelectionScope)
    if type(selected_record_index) is not int or not 0 <= selected_record_index <= 8:
        return RoomFormatFailure(
            "map-selection-input", 0, "selected MAP record index must be 0 through 8"
        )
    failure = capture_failure(executable, ram)
    if failure is not None:
        return failure
    layout = decode_map_layout(data, executable)
    if isinstance(layout, RoomFormatFailure):
        return layout
    record = layout["records"][selected_record_index]
    table = condition_records[selected_record_index]
    # Alternate source records 7/8 still invoke the native predicate with
    # groups 0/1. Current-location AA is independent of browsed-group AB.
    group = native_group_for_record(selected_record_index)
    if ram[0xE026B] != group:
        return RoomFormatFailure(
            "map-selection-binding",
            0xE026B,
            "displayed group differs from the explicit MAP record",
        )
    if len(record["directory"]) > 256 or any(
        scope is not _SelectionScope.Rows
        and len(row["primitive_groups"][0 if scope is _SelectionScope.GroupZero else 1])
        > 256
        for row in record["directory"]
    ):
        return RoomFormatFailure(
            "map-selection-source",
            record["offset"] + record["sections"][0]["offset"],
            "source row or quad count exceeds native byte arguments",
        )

    def word(address: int) -> int:
        return struct.unpack_from("<I", ram, address - 0x80000000)[0]

    pointer, section_pointer = word(0x800E028C), word(0x800E0274)
    # A contiguous source prefix covers the header, section-0 directory/quads
    # and bounded condition tables. Separate header/section-1 matches would
    # leave loaded geometry unchecked; mutable image sections are excluded.
    source_start = record["offset"]
    source_end = (
        table["table_offset"] + table["bounded_size"]
        if scope in (_SelectionScope.GroupZero, _SelectionScope.Rows)
        else source_start + table["source_prefix_size"]
    )
    prefix_size = source_end - source_start
    if pointer % 4 or not 0x80000000 <= pointer <= 0x80200000 - prefix_size:
        return RoomFormatFailure(
            "map-selection-binding",
            0xE028C,
            "loaded MAP pointer cannot contain the source prefix",
        )
    if (
        section_pointer % 4
        or not 0x80000000 <= section_pointer <= 0x801FFFFC
        or section_pointer != pointer + record["sections"][1]["offset"]
    ):
        return RoomFormatFailure(
            "map-selection-binding",
            0xE0274,
            "loaded section-1 pointer differs from the explicit source",
        )
    start = pointer - 0x80000000
    if ram[start : start + prefix_size] != data[source_start:source_end]:
        return RoomFormatFailure(
            "map-selection-binding",
            start,
            "loaded MAP bytes differ from the explicit source prefix",
        )

    def flag(bank: int, index: int) -> int:
        address, mask = msb_flag_location(bank, index)
        return word(address) & mask

    return _BoundMapSelection(layout, record, table, group, prefix_size, flag)


def decode_native_map_selection(
    data: bytes, executable: bytes, ram: bytes, selected_record_index: int
) -> dict | RoomFormatFailure:
    """Evaluate source predicates after binding an explicit loaded MAP record.

    Source failures retain their MAP/executable offset space. Binding/capture
    failures use RAM offsets; an invalid explicit record argument uses offset 0.
    A binding failure says nothing about gameplay validity or exploration.
    """
    conditions = decode_map_conditions(data, executable)
    if isinstance(conditions, RoomFormatFailure):
        return conditions
    bound = _bind_selected_map_source(
        data,
        executable,
        ram,
        selected_record_index,
        _SelectionScope.GroupZero,
        conditions["records"],
    )
    if isinstance(bound, RoomFormatFailure):
        return bound
    layout, record, table, group, prefix_size, flag = bound

    current_key = ram[0xE026A] << 8 | ram[0xE026C]
    phase = struct.unpack_from("<b", ram, 0xCCBCD)[0]
    overlay = struct.unpack_from("<H", ram, 0xE0278)[0]
    acquired = bool(flag(0x800D2124, group))
    requirements = quad_requirements(table["requirements"])
    rows = []
    for row in record["directory"]:
        allowed = []
        for primitive in range(len(row["primitive_groups"][0])):
            metadata_allows = group_zero_metadata_allows(
                requirements, row["index"], primitive, acquired, flag
            )
            if metadata_allows and group_zero_shape_allowed(
                group, row["index"], primitive, current_key, phase, overlay, flag
            ):
                allowed.append(primitive)
        rows.append(
            {
                "index": row["index"],
                "group0_count": len(row["primitive_groups"][0]),
                "group0_allowed_indices": allowed,
            }
        )
    return {
        "schema": "re3-native-map-selection-v1",
        "status": "candidate-group0-predicates",
        "map_sha256": layout["sha256"],
        "executable_sha256": layout["executable_sha256"],
        "selected_record_index": selected_record_index,
        "selected_native_group": group,
        "current_native_key": current_key,
        "phase_i8": phase,
        "overlay_u16": overlay,
        "native_map_acquired": acquired,
        "loaded_source_prefix_bytes": prefix_size,
        "rows": rows,
        "native_row_visibility": "unchecked",
        "group1_selection": "unresolved",
        "room_ownership": "unresolved",
        "campaign_admission": "unresolved",
        "tracker_visibility": "unresolved",
    }


def decode_native_map_detail_selection(
    data: bytes, executable: bytes, ram: bytes, selected_record_index: int
) -> dict | RoomFormatFailure:
    """Evaluate Candidate group-1 admission/style against a bound source.

    Source failures retain their MAP/executable offset space. Binding/capture
    failures use RAM offsets; an invalid explicit record argument uses offset 0.
    Native row visibility and gameplay admission remain separate.
    """
    conditions = decode_map_detail_conditions(data, executable)
    if isinstance(conditions, RoomFormatFailure):
        return conditions
    bound = _bind_selected_map_source(
        data,
        executable,
        ram,
        selected_record_index,
        _SelectionScope.GroupOne,
        conditions["records"],
    )
    if isinstance(bound, RoomFormatFailure):
        return bound
    layout, record, table, group, prefix_size, flag = bound
    current_key = ram[0xE026A] << 8 | ram[0xE026C]
    phase = struct.unpack_from("<b", ram, 0xCCBCD)[0]
    raw_stage = struct.unpack_from("<H", ram, 0xD1F76)[0]
    requirements, styles = detail_metadata(table)
    # SB at 0x80072DAC preserves only the raw helper mask's low byte. Boolean
    # normalization would invent acquisition for every supported group 0-6.
    acquisition_byte = flag(0x800D2124, group) & 0xFF
    rows = []
    for row in record["directory"]:
        allowed = []
        for index, primitive in enumerate(row["primitive_groups"][1]):
            detail = select_group_one_detail(
                requirements,
                styles,
                group,
                row["index"],
                index,
                primitive["style_bytes"][0],
                current_key,
                phase,
                raw_stage,
                acquisition_byte,
                flag,
            )
            if detail is DetailSelection.Reject:
                continue
            allowed.append(
                {
                    "index": detail.index,
                    "requested_palette_variant": detail.requested_palette_variant,
                    "effective_palette_variant": detail.effective_palette_variant,
                }
            )
        rows.append(
            {
                "index": row["index"],
                "group1_count": len(row["primitive_groups"][1]),
                "group1_allowed": allowed,
            }
        )
    return {
        "schema": "re3-native-map-detail-selection-v1",
        "status": "candidate-group1-predicates",
        "map_sha256": layout["sha256"],
        "executable_sha256": layout["executable_sha256"],
        "selected_record_index": selected_record_index,
        "selected_native_group": group,
        "current_native_key": current_key,
        "phase_i8": phase,
        "raw_stage_u16": raw_stage,
        "native_map_acquisition_byte": acquisition_byte,
        "loaded_source_prefix_bytes": prefix_size,
        "rows": rows,
        "native_row_visibility": "unchecked",
        "room_ownership": "unresolved",
        "campaign_admission": "unresolved",
        "tracker_visibility": "unresolved",
    }


def decode_native_map_row_visibility(
    data: bytes, executable: bytes, ram: bytes, selected_record_index: int
) -> dict | RoomFormatFailure:
    """Evaluate the native row gate, independently of tracker exploration.

    This source-bound API also checks cached source-layer coherence. It leaves
    the two per-quad selection APIs and their unchecked row visibility intact.
    """
    conditions = decode_map_conditions(data, executable)
    if isinstance(conditions, RoomFormatFailure):
        return conditions
    # The group-zero prefix already covers the complete directory and source
    # layer header. Row gating needs neither quad counts nor later image bytes.
    bound = _bind_selected_map_source(
        data,
        executable,
        ram,
        selected_record_index,
        _SelectionScope.Rows,
        conditions["records"],
    )
    if isinstance(bound, RoomFormatFailure):
        return bound
    failure = capture_failure(executable, ram, _ROW_GATE_CODE_WINDOWS)
    if failure is not None:
        return failure
    layout, record, _, group, prefix_size, flag = bound
    layer_mode, layer_count = ram[0xE026D], ram[0xE0270]
    source_mode, source_count = record["layer_metadata"]["raw_prefix"][4:6]
    for offset, actual, expected in (
        (0xE026D, layer_mode, source_mode),
        (0xE0270, layer_count, source_count),
    ):
        if actual != expected:
            return RoomFormatFailure(
                "map-selection-binding",
                offset,
                "cached layer metadata differs from the explicit source",
            )
    selected_layer = struct.unpack_from("<b", ram, 0xE026E)[0]
    if layer_mode and not 0 <= selected_layer < layer_count:
        return RoomFormatFailure(
            "map-selection-binding",
            0xE026E,
            "selected layer is outside the explicit source",
        )
    current_key = ram[0xE026A] << 8 | ram[0xE026C]
    raw_stage = struct.unpack_from("<H", ram, 0xD1F76)[0]
    return {
        "schema": "re3-native-map-row-visibility-v1",
        "status": "candidate-native-row-visibility",
        "map_sha256": layout["sha256"],
        "executable_sha256": layout["executable_sha256"],
        "selected_record_index": selected_record_index,
        "selected_native_group": group,
        "current_native_key": current_key,
        "raw_stage_u16": raw_stage,
        "layer_mode_u8": layer_mode,
        "selected_layer_i8": selected_layer,
        "layer_count_u8": layer_count,
        "native_map_acquired": bool(flag(0x800D2124, group)),
        "loaded_source_prefix_bytes": prefix_size,
        "rows": [
            {
                "index": row["index"],
                "native_visible": native_row_visible(
                    group,
                    row["index"],
                    current_key,
                    raw_stage,
                    layer_mode,
                    selected_layer,
                    flag,
                ),
            }
            for row in record["directory"]
        ],
        "room_ownership": "unresolved",
        "campaign_admission": "unresolved",
        "tracker_visibility": "unresolved",
    }
