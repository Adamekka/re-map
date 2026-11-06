"""Candidate snapshot-bound map predicates for SLUS-00923. RE3-MAP-009/011.

Native row visibility, physical room ownership and tracker visits are separate.
"""

from __future__ import annotations

import struct
from typing import NamedTuple

from games.bit_flags import msb_flag_location
from games.re3.capture_data import capture_failure
from games.re3.map_conditions import decode_map_conditions, decode_map_detail_conditions
from games.re3.map_data import decode_map_layout
from games.re3.map_detail_predicates import (
    GROUP_ONE_SYSTEM_STYLE,
    GroupOneShapeDecision,
    group_one_shape_decision,
)
from games.re3.map_predicate import FlagReader
from games.re3.map_shape_predicates import group_zero_shape_allowed
from games.re3.room_data import RoomFormatFailure


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
    primitive_group: int,
    condition_records: list[dict],
) -> _BoundMapSelection | RoomFormatFailure:
    """Bind decoded table info before either source selection can evaluate RAM."""
    assert type(primitive_group) is int and primitive_group in (0, 1)
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
    group = (
        selected_record_index
        if selected_record_index < 7
        else selected_record_index - 7
    )
    if ram[0xE026B] != group:
        return RoomFormatFailure(
            "map-selection-binding",
            0xE026B,
            "displayed group differs from the explicit MAP record",
        )
    if len(record["directory"]) > 256 or any(
        len(row["primitive_groups"][primitive_group]) > 256
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
        if primitive_group == 0
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
        data, executable, ram, selected_record_index, 0, conditions["records"]
    )
    if isinstance(bound, RoomFormatFailure):
        return bound
    layout, record, table, group, prefix_size, flag = bound

    current_key = ram[0xE026A] << 8 | ram[0xE026C]
    phase = struct.unpack_from("<b", ram, 0xCCBCD)[0]
    overlay = struct.unpack_from("<H", ram, 0xE0278)[0]
    acquired = bool(flag(0x800D2124, group))
    rows = []
    for row in record["directory"]:
        allowed = []
        for primitive in range(len(row["primitive_groups"][0])):
            # No matching entry imposes no prefix requirement. Duplicate
            # targets remain conjunctive; acquisition bypasses only this test.
            metadata_allows = acquired or all(
                flag(entry["flag_bank_address_ps1"], entry["flag_index"])
                for entry in table["requirements"]
                if (entry["row_index"], entry["primitive_index"])
                == (row["index"], primitive)
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
        data, executable, ram, selected_record_index, 1, conditions["records"]
    )
    if isinstance(bound, RoomFormatFailure):
        return bound
    layout, record, table, group, prefix_size, flag = bound
    current_key = ram[0xE026A] << 8 | ram[0xE026C]
    phase = struct.unpack_from("<b", ram, 0xCCBCD)[0]
    raw_stage = struct.unpack_from("<H", ram, 0xD1F76)[0]
    system = bool(flag(0x800CC858, 24))
    # SB at 0x80072DAC preserves only the raw helper mask's low byte. Boolean
    # normalization would invent acquisition for every supported group 0-6.
    acquisition_byte = flag(0x800D2124, group) & 0xFF
    rows = []
    for row in record["directory"]:
        allowed = []
        for index, primitive in enumerate(row["primitive_groups"][1]):
            decision = group_one_shape_decision(
                group, row["index"], index, current_key, phase, raw_stage, flag
            )
            if decision is GroupOneShapeDecision.Reject:
                continue
            # Earlier native allows bypass the table. Once the scan is reached,
            # matching entries reject in system/acquisition/flag order, and
            # duplicates remain conjunctive. No matching entry imposes a test.
            if decision is GroupOneShapeDecision.CheckMetadata and any(
                system
                or (entry["reject_if_acquisition_byte_clear"] and not acquisition_byte)
                or flag(entry["flag_bank_address_ps1"], entry["flag_index"])
                for entry in table["admission"]["requirements"]
                if (entry["row_index"], entry["primitive_index"])
                == (row["index"], index)
            ):
                continue
            if system:
                # The native system branch bypasses style metadata and has
                # fixed membership only for native groups 0/1.
                styled = (
                    group < 2 and (row["index"], index) in GROUP_ONE_SYSTEM_STYLE[group]
                )
            else:
                # The first recognized matching unset flag selects this style;
                # duplicate entries are alternatives and ignored selectors skip.
                styled = any(
                    not flag(entry["flag_bank_address_ps1"], entry["flag_index"])
                    for entry in table["style"]["conditions"]
                    if entry["kind"] == "flag-test"
                    and (entry["row_index"], entry["primitive_index"])
                    == (row["index"], index)
                )
            requested_variant = 2 * bool(styled)
            # The renderer at 0x8007116C forces native kind 7 to variant zero.
            effective_variant = (
                0 if primitive["style_bytes"][0] == 7 else requested_variant
            )
            allowed.append(
                {
                    "index": index,
                    "requested_palette_variant": requested_variant,
                    "effective_palette_variant": effective_variant,
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
