"""Candidate native row visibility for SLUS-00923. RE3-MAP-012.

Native reveal rules do not establish tracker exploration or room ownership.
Source/capture coherence belongs to the caller's mandatory binding path.
"""

from games.re3.map_layer import native_map_layer
from games.re3.map_predicate import FlagReader


def native_row_visible(
    group: int,
    row: int,
    current_key: int,
    raw_stage_u16: int,
    layer_mode_u8: int,
    selected_layer_i8: int,
    flag: FlagReader,
) -> bool:
    """Evaluate 0x80070348's reveal gate and original row/layer predicates."""
    assert type(group) is int and 0 <= group <= 6
    assert type(row) is int and 0 <= row <= 255
    assert type(current_key) is int and 0 <= current_key <= 0xFFFF
    assert type(raw_stage_u16) is int and 0 <= raw_stage_u16 <= 0xFFFF
    assert type(layer_mode_u8) is int and 0 <= layer_mode_u8 <= 255
    assert type(selected_layer_i8) is int and -128 <= selected_layer_i8 <= 127

    # This caller tests the full acquisition mask, independently of group 1's
    # low-byte admission cache. Supported acquisition masks have a zero low byte.
    acquired = flag(0x800D2124, group)
    if not acquired and row >= 48:
        return False
    # The original visit helper strides two words per group. Retain the full
    # index: semantic bank labels can alias the same physical word. The caller
    # still requires visits for acquired native group 4, rows 11-15.
    if (not acquired or group == 4 and 11 <= row <= 15) and not flag(
        0x800D20DC, 64 * group + row
    ):
        return False

    if group == 0 and 17 <= row <= 26:
        return False
    if group == 1:
        if current_key in (0x10C, 0x115) and flag(0x800D1FA0, 58) and row != 12:
            return False
        if raw_stage_u16 in (2, 3, 4) and row == 12:
            return False
        if row == (16 if current_key == 0x10F else 15):
            return False
        if row == (17 if current_key == 0x112 else 18):
            return False
    if group == 3:
        if row == (17 if flag(0x800D1FA0, 196) else 21):
            return False
        if current_key == 0x310:
            if row in (17, 21, 13):
                return False
        elif row == 16:
            return False

    # AE is the signed browsed layer. The current-layer AF value is separate
    # and is not an input to this native predicate.
    return not layer_mode_u8 or selected_layer_i8 == native_map_layer(group, row)
