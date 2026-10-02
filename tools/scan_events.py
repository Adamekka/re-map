"""Find embedded SCD commands through the pinned RE1 event interpreter.

This decoder follows every indexed entry in VM state 0, including FA/FB loops
and FC/FD deferred SCD dispatch. Widths and transitions come from the named
SLUS-00551 interpreter in RE1-CACHE-002 and RE1-EVENT-001. Malformed paths reject
coverage; payload bytes are never scanned as free-standing commands.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from scan_scd import _opcode_size, walk_procedures

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re1.scd_semantics import NONZERO_RETURN_OPCODES, ZERO_RETURN_OPCODES


def scan_event_commands(
    data: bytes, start: int, end: int
) -> tuple[list[tuple[int, int, bytes]], str]:
    if not 0 < start < end <= len(data):
        return [], "bad indexed event range"
    entries = []
    cursor = start
    while cursor + 4 <= end:
        relative = struct.unpack_from("<I", data, cursor)[0]
        cursor += 4
        if relative == 0:
            break
        target = start + relative
        if not start < target < end:
            return [], "indexed event pointer is outside its section"
        entries.append(target)
    else:
        return [], "indexed event table has no sentinel"
    if any(target < cursor for target in entries):
        return [], "indexed event pointer overlaps its table"
    operations: dict[int, tuple[int, int, bytes]] = {}
    # Waits, counters, loops and calls share the native record's depth byte.
    # Frames retain only initialized fields; using a stale native field is unsupported.
    pending = [(entry, 0, ()) for entry in entries]
    seen = set()
    issues = []

    def record(operation: tuple[int, int, bytes]) -> None:
        command, opcode, raw = operation
        if opcode == 0x14 and raw[3] >= len(entries):
            issues.append(f"SCD event creation index outside table at 0x{command:x}")
        operations[command] = operation

    widths = {
        0: {0: 1, 1: 1, 2: 1, 3: 1, 4: 3, 5: 4, 8: 2, 9: 2},
        1: {
            0: 1,
            0x80: 1,
            0x82: 1,
            0x83: 7,
            0x84: 4,
            0x85: 4,
            0x86: 1,
            0x87: 4,
            0x88: 4,
            0x89: 2,
            0x8A: 2,
            0x8B: 1,
        },
        2: {0: 1, 1: 1, 2: 1, 3: 1, 4: 1, 5: 4, 6: 4, 7: 8, 8: 3, 9: 2, 10: 4, 11: 8},
    }
    while pending:
        address, state, stack = pending.pop()
        key = (address, state, stack)
        if key in seen:
            continue
        # The native 0x34-byte event record contains four return/call/counter slots.
        if len(seen) >= 16384 or len(stack) > 4:
            issues.append("event control flow exceeds bounded analysis")
            break
        seen.add(key)
        if not cursor <= address < end:
            issues.append(f"event path leaves section at 0x{address:x}")
            continue
        op = data[address]
        width = 0
        next_state = state
        next_stack = stack
        if op == 0xFF:
            continue
        if op == 0xFE:
            width = 1
        elif op == 0xF6:
            width = 1
            next_stack = stack + (("wait", 0, 0),)
        elif op == 0xF7:
            if not stack:
                issues.append(f"event wait end has no frame at 0x{address:x}")
                continue
            # This native pop reads no stored frame fields, so any existing
            # frame can be discarded after the external wait condition clears.
            width = 1
            next_stack = stack[:-1]
        elif op == 0xF8:
            # F8 reads the counter at +2 but advances only to +1. The next
            # byte is executable, normally F9, rather than skipped padding.
            if address + 4 > end:
                issues.append(f"event counter read truncated at 0x{address:x}")
                continue
            width = 1
            next_stack = stack + (("counter", 0, 0),)
        elif op == 0xF9:
            if not stack or stack[-1][0] not in ("counter", "loop"):
                issues.append(
                    f"event counter end has no counter frame at 0x{address:x}"
                )
                continue
            # A u16 decrement eventually exits, including a zero starting value.
            # Repeating F9 changes no source command or VM state.
            width = 3
            next_stack = stack[:-1]
        elif op == 0xFA:
            width = 4
            next_stack = stack + (("loop", address + 4, 0),)
        elif op == 0xFB:
            if not stack or stack[-1][0] != "loop":
                issues.append(f"event loop end has no frame at 0x{address:x}")
                continue
            pending.append((stack[-1][1], state, stack))
            width = 1
            next_stack = stack[:-1]
        elif op == 0xFC:
            if address + 2 > end:
                issues.append(f"event call header truncated at 0x{address:x}")
                continue
            target = address + data[address + 1]
            pending.append((target, state, stack + (("call", target, address + 2),)))
            continue
        elif op == 0xFD:
            if not stack or stack[-1][0] != "call":
                issues.append(f"deferred event command has no frame at 0x{address:x}")
                continue
            _, repeat, command = stack[-1]
            size, status = _opcode_size(data[command:end], 0)
            if status != "clean":
                issues.append(f"deferred SCD at 0x{command:x}: {status}")
                continue
            record((command, data[command], data[command : command + size]))
            # FD repeats only on nonzero. Audited zero returns cannot repeat,
            # while audited nonzero handlers cannot expose a later exit path.
            if data[command] not in ZERO_RETURN_OPCODES:
                pending.append((repeat, state, stack))
            if data[command] in NONZERO_RETURN_OPCODES:
                continue
            width = 1
            next_stack = stack[:-1]
        elif state == 0 and op in (6, 7):
            if address + 2 > end:
                issues.append(f"embedded SCD header truncated at 0x{address:x}")
                continue
            width = data[address + 1]
            if width == 0 or address + width > end:
                issues.append(f"embedded SCD extent invalid at 0x{address:x}")
                continue
            if op == 6:
                # The runner reads its entire length-prefixed list and sentinel
                # independently of the VM jump width. Only this source section
                # bounds those reads, including an empty list's zero sentinel.
                found, status = walk_procedures(data[address + 2 : end], address + 2)
            else:
                # Single-command dispatch reads its operands independently of the VM's advance width.
                # Some real AOT updates intentionally consume fields beyond the shorter wrapper.
                if address + 2 >= end:
                    issues.append(f"embedded SCD opcode truncated at 0x{address:x}")
                    continue
                size, status = _opcode_size(data[address + 2 : end], 0)
                found = (
                    [
                        (
                            address + 2,
                            data[address + 2],
                            data[address + 2 : address + 2 + size],
                        )
                    ]
                    if size
                    else []
                )
            if status != "clean":
                issues.append(f"embedded SCD at 0x{address:x}: {status}")
                # Procedure walking can retain raw candidates for diagnostics.
                # A failed embedded block cannot establish reachable event effects.
                continue
            for operation in found:
                record(operation)
        elif state == 1 and op == 0x81:
            if address + 2 > end:
                issues.append(f"look-at command truncated at 0x{address:x}")
                continue
            width = 10 if data[address + 1] & 15 else 2
        elif state == 3:
            width = 2
        elif state == 0 and op >= 10:
            # The native state-0 default disables the event and returns from
            # the tick. It cannot execute bytes following this terminating opcode.
            continue
        else:
            width = widths.get(state, {}).get(op, 0)
            if width == 0:
                issues.append(
                    f"unsupported event state {state} opcode 0x{op:02x} at 0x{address:x}"
                )
                continue
        if address + width > end:
            issues.append(f"event command truncated at 0x{address:x}")
            continue
        if op < 0xF6:
            if state == 0 and op == 1:
                next_state = 1
            elif state == 0 and op in (2, 3):
                next_state = 2
            elif state == 0 and op == 5 and data[address + 2] >= len(entries):
                issues.append(f"event creation index outside table at 0x{address:x}")
            elif state == 0 and op == 8:
                index = data[address + 1]
                if index >= len(entries):
                    issues.append(
                        f"event reinitialization index outside table at 0x{address:x}"
                    )
                else:
                    pending.append((entries[index], 0, ()))
                continue
            elif state == 1 and op in (0x80, 0x8B) or state == 2 and op == 1:
                next_state = 0
        pending.append((address + width, next_state, next_stack))
    return sorted(operations.values()), "clean" if not issues else "; ".join(issues)
