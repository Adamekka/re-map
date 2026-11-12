"""Pinned MIPS control facts used by the scenario-only task interpreter."""

from __future__ import annotations

import struct

from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    NATIVE_LOOP_FRAME_COUNT,
)

# Native task/frame arithmetic is shared by ordinary and auxiliary Goto checks.
TASK_BASE = 0x800D7860
TASK_WIDTH = 0x174
IF_FRAME_BASE = 0xC0
IF_FRAME_WIDTH = 0x20
# Goto increments the encoded FF level without byte-wrapping that arithmetic;
# fresh task initialization instead installs the canonical IF_FRAME_BASE.
GOTO_FF_IF_BASE = IF_FRAME_BASE + 0x400


def goto_if_cell(task: int, depth: int) -> tuple[int, int]:
    """Return the receiving task/offset of FF IF-pointer's next target store."""
    assert 0 <= task < 14 and 0 <= depth < NATIVE_CALL_FRAME_COUNT
    displacement = task * TASK_WIDTH + GOTO_FF_IF_BASE + depth * IF_FRAME_WIDTH
    return divmod(displacement, TASK_WIDTH)


def loop_end_cell(depth: int, loop: int) -> int:
    """Native Break reads this u32LE end pointer in the shared loop frame."""
    assert 0 <= depth < NATIVE_CALL_FRAME_COUNT and 0 <= loop < NATIVE_LOOP_FRAME_COUNT
    return 0x60 + depth * 16 + loop * 4


def native_bytes(executable: bytes, address: int, width: int) -> bytes:
    offset = address - 0x80010000 + 0x800
    if width < 0 or not 0x800 <= offset <= len(executable) - width:
        raise ValueError("native control lookup is outside the executable")
    return executable[offset : offset + width]


def native_nonyielding(
    executable: bytes, entry: int, switches: dict[int, tuple[int, ...]]
) -> bool:
    """Close calls/branches; reject indirect, cooperative and external transfers.

    Loops need no termination proof here: spinning cannot advance the outer
    input clock. A handler returning one is insufficient if a callee can yield.
    Switch destinations are separately bounded pinned-native table entries.
    """
    pending, seen = [entry], set()
    try:

        def delay_is_plain(address):
            word = int.from_bytes(native_bytes(executable, address + 4, 4), "little")
            op, function = word >> 26, word & 63
            return op not in (1, 2, 3, 4, 5, 6, 7) and not (
                op == 0 and function in (8, 9, 12, 13)
            )

        while pending:
            address = pending.pop()
            if address in seen:
                continue
            if len(seen) >= 16384 or address in (
                0x8001AAA0,
                0x8001AAA8,
                0x80031E80,
                0x80031F6C,
                0x80031F94,
            ):
                return False
            seen.add(address)
            word = int.from_bytes(native_bytes(executable, address, 4), "little")
            op, function = word >> 26, word & 63
            if op == 0 and function in (8, 9):
                # Only a real return or an explicitly bounded native switch
                # closes the graph. No arbitrary callback inherits atomicity.
                if not delay_is_plain(address):
                    return False
                if function == 8 and word >> 21 & 31 == 31:
                    continue
                if function == 8 and address in switches:
                    pending.extend(switches[address])
                    continue
                return False
            if op in (2, 3):
                target = (address + 4) & 0xF0000000 | (word & 0x3FFFFFF) << 2
                pending.append(target)
                if not delay_is_plain(address):
                    return False
                if op == 3:
                    pending.append(address + 8)
            elif op in (1, 4, 5, 6, 7):
                distance = struct.unpack("<h", (word & 65535).to_bytes(2, "little"))[0]
                pending.extend((address + 4 + distance * 4, address + 8))
                if not delay_is_plain(address):
                    return False
            elif op == 0 and function in (12, 13):
                return False
            else:
                pending.append(address + 4)
        return True
    except (ValueError, struct.error):
        return False
