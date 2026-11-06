"""Candidate quad condition tables for SLUS-00923. RE3-MAP-008/010.

This exports source conditions, not selected contours or tracker visibility.
"""

from __future__ import annotations

from typing import NamedTuple

from games.bit_flags import msb_flag_location
from games.re3.map_data import decode_map_layout
from games.re3.room_data import RoomFormatFailure


class _QuadConditionEntry(NamedTuple):
    offset: int
    row: int
    primitive: int
    flag_index: int
    control: int


class _QuadConditionTable(NamedTuple):
    entries: tuple[_QuadConditionEntry, ...]
    terminator_offset: int


def _decode_condition_table(
    data: bytes, start: int, limit: int
) -> _QuadConditionTable | RoomFormatFailure:
    assert 0 <= start <= limit <= len(data), "source extents must already be checked"
    entries, offset = [], start
    while offset < limit:
        # Native scans test only the row byte before returning at the sentinel.
        # Its other three bytes need not be present or all 0xFF.
        if data[offset] == 0xFF:
            return _QuadConditionTable(tuple(entries), offset)
        if offset + 4 > limit:
            return RoomFormatFailure(
                "map-conditions", offset, "truncated quad requirement"
            )
        entries.append(_QuadConditionEntry(offset, *data[offset : offset + 4]))
        offset += 4
    return RoomFormatFailure(
        "map-conditions", start, "missing quad requirement terminator"
    )


def decode_map_conditions(data: bytes, executable: bytes) -> dict | RoomFormatFailure:
    """Decode bounded, ordered metadata after the mandatory executable check.

    All byte offsets refer to the MAP file. Flag addresses are PS1 virtual
    addresses of little-endian u32 words; masks use native MSB-first indexing.
    """
    layout = decode_map_layout(data, executable)
    if isinstance(layout, RoomFormatFailure):
        return layout
    records = []
    for record in layout["records"]:
        section_start = record["offset"] + record["sections"][1]["offset"]
        start, limit = [
            section_start + offset for offset in record["projection_header_words"][3:5]
        ]
        table = _decode_condition_table(data, start, limit)
        if isinstance(table, RoomFormatFailure):
            return table
        entries = []
        for entry in table.entries:
            # Native code treats every nonzero selector as the first bank.
            # Preserve its raw value rather than narrowing the format to 0/1.
            bank = 0x800D1FA0 if entry.control else 0x800D20CC
            address, mask = msb_flag_location(bank, entry.flag_index)
            entries.append(
                {
                    "offset": entry.offset,
                    "row_index": entry.row,
                    "primitive_index": entry.primitive,
                    "flag_index": entry.flag_index,
                    "bank_selector": entry.control,
                    "flag_bank_address_ps1": bank,
                    "flag_word_address_ps1": address,
                    "flag_word_mask": mask,
                }
            )
        records.append(
            {
                "index": record["index"],
                "table_offset": start,
                "bounded_size": limit - start,
                "terminator_offset": table.terminator_offset,
                "requirements": entries,
            }
        )
    return {
        "schema": "re3-static-map-conditions-v1",
        "status": "candidate-source-conditions",
        "evidence_kind": "offline-only",
        "map_sha256": layout["sha256"],
        "executable_sha256": layout["executable_sha256"],
        "primitive_group": 0,
        "records": records,
        "shape_selection": "unresolved",
        "tracker_visibility": "unresolved",
    }


def decode_map_detail_conditions(
    data: bytes, executable: bytes
) -> dict | RoomFormatFailure:
    """Export group-1 admission/style tables without evaluating game state.

    Admission flags must be clear, unlike group 0. Style selectors outside
    0–3 are explicitly retained as native ignored entries, not another bank.
    All offsets use MAP bytes; flag words are u32 LE in PS1 virtual RAM.
    """
    layout = decode_map_layout(data, executable)
    if isinstance(layout, RoomFormatFailure):
        return layout
    records = []
    for record in layout["records"]:
        section = record["sections"][1]
        base = record["offset"] + section["offset"]
        offsets = record["projection_header_words"]
        style_start, style_limit = base + offsets[2], base + offsets[3]
        admission_start, admission_limit = base + offsets[4], base + section["size"]
        style = _decode_condition_table(data, style_start, style_limit)
        if isinstance(style, RoomFormatFailure):
            return style
        admission = _decode_condition_table(data, admission_start, admission_limit)
        if isinstance(admission, RoomFormatFailure):
            return admission
        requirements = []
        for entry in admission.entries:
            # Group 1 tests only control bit 0 for bank selection. Other bits
            # include the acquisition-byte requirement, not alternate banks.
            bank = 0x800D1FA0 if entry.control & 1 else 0x800D20CC
            address, mask = msb_flag_location(bank, entry.flag_index)
            requirements.append(
                {
                    "offset": entry.offset,
                    "row_index": entry.row,
                    "primitive_index": entry.primitive,
                    "flag_index": entry.flag_index,
                    "control_byte": entry.control,
                    "reject_if_acquisition_byte_clear": bool(entry.control & 0x10),
                    "flag_bank_address_ps1": bank,
                    "flag_word_address_ps1": address,
                    "flag_word_mask": mask,
                }
            )
        conditions = []
        for entry in style.entries:
            condition = {
                "offset": entry.offset,
                "row_index": entry.row,
                "primitive_index": entry.primitive,
                "flag_index": entry.flag_index,
                "bank_selector": entry.control,
            }
            if entry.control <= 3:
                bank = (0x800D20CC, 0x800D1FA0, 0x800D1FC8, 0x800D1FE8)[entry.control]
                address, mask = msb_flag_location(bank, entry.flag_index)
                condition.update(
                    kind="flag-test",
                    flag_bank_address_ps1=bank,
                    flag_word_address_ps1=address,
                    flag_word_mask=mask,
                )
            else:
                # The native selector skips unknown values; resolving them as
                # selector 1 would invent an extra style condition.
                condition["kind"] = "ignored-bank-selector"
            conditions.append(condition)
        records.append(
            {
                "index": record["index"],
                "source_prefix_size": section["offset"] + section["size"],
                "admission": {
                    "table_offset": admission_start,
                    "bounded_size": admission_limit - admission_start,
                    "terminator_offset": admission.terminator_offset,
                    "requirements": requirements,
                },
                "style": {
                    "table_offset": style_start,
                    "bounded_size": style_limit - style_start,
                    "terminator_offset": style.terminator_offset,
                    "conditions": conditions,
                },
            }
        )
    return {
        "schema": "re3-static-map-detail-conditions-v1",
        "status": "candidate-source-conditions",
        "evidence_kind": "offline-only",
        "map_sha256": layout["sha256"],
        "executable_sha256": layout["executable_sha256"],
        "primitive_group": 1,
        "records": records,
        "shape_selection": "unresolved",
        "tracker_visibility": "unresolved",
    }
