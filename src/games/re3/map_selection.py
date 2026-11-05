"""Candidate snapshot-bound group-0 predicates for SLUS-00923. RE3-MAP-009.

Native row visibility, physical room ownership and tracker visits are separate.
"""

from __future__ import annotations

import struct

from games.bit_flags import msb_flag_location
from games.re3.capture_data import capture_failure
from games.re3.map_conditions import decode_map_conditions
from games.re3.map_data import decode_map_layout
from games.re3.map_shape_predicates import group_zero_shape_allowed
from games.re3.room_data import RoomFormatFailure


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
    table = conditions["records"][selected_record_index]
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
        len(row["primitive_groups"][0]) > 256 for row in record["directory"]
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
    # and bounded requirement table. Separate header/section-1 matches would
    # leave loaded geometry unchecked; mutable image sections are excluded.
    source_start = record["offset"]
    source_end = table["table_offset"] + table["bounded_size"]
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

    def flag(bank: int, index: int) -> bool:
        address, mask = msb_flag_location(bank, index)
        return bool(word(address) & mask)

    current_key = ram[0xE026A] << 8 | ram[0xE026C]
    phase = struct.unpack_from("<b", ram, 0xCCBCD)[0]
    overlay = struct.unpack_from("<H", ram, 0xE0278)[0]
    acquired = flag(0x800D2124, group)
    rows = []
    for row in record["directory"]:
        allowed = []
        for primitive in range(len(row["primitive_groups"][0])):
            # No matching entry imposes no prefix requirement. Duplicate
            # targets remain conjunctive; acquisition bypasses only this test.
            metadata_allows = acquired or all(
                word(entry["flag_word_address_ps1"]) & entry["flag_word_mask"]
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
