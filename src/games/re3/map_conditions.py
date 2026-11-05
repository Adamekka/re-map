"""Candidate group-0 quad requirements for SLUS-00923. RE3-MAP-008.

This exports source conditions, not selected contours or tracker visibility.
"""

from __future__ import annotations

from games.bit_flags import msb_flag_location
from games.re3.map_data import decode_map_layout
from games.re3.room_data import RoomFormatFailure


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
        entries, offset = [], start
        while offset < limit:
            # The native loop tests only the row byte before returning at the
            # sentinel. Its other three bytes need not be present or all 0xFF.
            row = data[offset]
            if row == 0xFF:
                break
            if offset + 4 > limit:
                return RoomFormatFailure(
                    "map-conditions", offset, "truncated quad requirement"
                )
            row, primitive, index, selector = data[offset : offset + 4]
            # Native code treats every nonzero selector as the first bank.
            # Preserve its raw value rather than narrowing the format to 0/1.
            bank = 0x800D1FA0 if selector else 0x800D20CC
            address, mask = msb_flag_location(bank, index)
            entries.append(
                {
                    "offset": offset,
                    "row_index": row,
                    "primitive_index": primitive,
                    "flag_index": index,
                    "bank_selector": selector,
                    "flag_bank_address_ps1": bank,
                    "flag_word_address_ps1": address,
                    "flag_word_mask": mask,
                }
            )
            offset += 4
        else:
            return RoomFormatFailure(
                "map-conditions", start, "missing quad requirement terminator"
            )
        records.append(
            {
                "index": record["index"],
                "table_offset": start,
                "bounded_size": limit - start,
                "terminator_offset": offset,
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
