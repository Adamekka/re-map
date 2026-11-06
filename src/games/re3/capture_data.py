"""Shared captured-RAM bounds and code witnesses for RE3-RUNTIME-001."""

from games.re3.room_data import RoomFormatFailure

RAM_SIZE = 2 * 1024 * 1024
# These sampled windows bind the capture to the caller's verified executable;
# they do not establish campaign admission or valid game-derived state.
CODE_WINDOWS = (0x80011B80, 0x80020000, 0x80040000, 0x80060000)


def capture_failure(
    executable: bytes,
    ram: bytes,
    additional_code_windows: tuple[tuple[int, int], ...] = (),
) -> RoomFormatFailure | None:
    """Check a snapshot after the caller's mandatory complete executable gate.

    Failure offsets use the captured main-RAM byte space. Public callers
    verify the complete executable before reaching these comparisons. Explicit
    extra spans cannot replace the four mandatory sampled witnesses.
    """
    if len(ram) != RAM_SIZE:
        return RoomFormatFailure(
            "capture", 0, "Capture must contain exactly 2 MiB of PS1 RAM"
        )
    for address, width in (
        *((address, 32) for address in CODE_WINDOWS),
        *additional_code_windows,
    ):
        assert type(address) is int and type(width) is int
        assert width > 0 and 0x80010000 <= address <= 0x80200000 - width
        offset = 0x800 + address - 0x80010000
        expected = executable[offset : offset + width]
        start = address - 0x80000000
        if len(expected) != width or ram[start : start + width] != expected:
            return RoomFormatFailure(
                "capture",
                start,
                f"Capture code window differs at PS1 virtual 0x{address:08X}",
            )
    return None
