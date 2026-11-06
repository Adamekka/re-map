"""Candidate native layer categories for SLUS-00923. RE3-MAP-012."""


def native_map_layer(group: int, row: int) -> int:
    """Evaluate the pinned 0x80073BC8 helper on decoded native arguments."""
    assert type(group) is int and 0 <= group <= 6
    assert type(row) is int and 0 <= row <= 255
    if group == 2:
        return 2 if row == 12 else int(row >= 10)
    if group == 4:
        return int(row < 4 or 8 <= row < 11)
    if group == 5:
        return int(row >= 8)
    if group == 6:
        return 2 if 5 <= row < 9 else int(row < 5)
    # The pinned helper returns layer zero for native groups 0, 1 and 3.
    return 0
