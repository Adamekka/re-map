"""Shared captured-RAM bounds and code witnesses for RE3-RUNTIME-001."""

from games.re3.room_data import RoomFormatFailure

RAM_SIZE = 2 * 1024 * 1024
# These sampled windows bind the capture to the caller's verified executable;
# they do not establish campaign admission or valid game-derived state.
CODE_WINDOWS = (0x80011B80, 0x80020000, 0x80040000, 0x80060000)


def capture_failure(executable: bytes, ram: bytes) -> RoomFormatFailure | None:
    """Check a snapshot after the caller's mandatory complete executable gate.

    Failure offsets use the captured main-RAM byte space. Both public callers
    verify the complete executable before reaching these sampled comparisons.
    """
    if len(ram) != RAM_SIZE:
        return RoomFormatFailure(
            "capture", 0, "Capture must contain exactly 2 MiB of PS1 RAM"
        )
    for address in CODE_WINDOWS:
        offset = 0x800 + address - 0x80010000
        expected = executable[offset : offset + 32]
        start = address - 0x80000000
        if len(expected) != 32 or ram[start : start + 32] != expected:
            return RoomFormatFailure(
                "capture",
                start,
                f"Capture code window differs at PS1 virtual 0x{address:08X}",
            )
    return None
