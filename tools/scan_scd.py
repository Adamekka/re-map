"""Scan RE1 RDT script chunks for item opcodes using reevengi scd1.xml sizes.

Local helper only. Prints 0x0D/0x12/0x13/0x18 entries with raw fields.
Bytecode walking follows both sides of IF blocks and stops at procedure
termination. Unknown opcodes stop the walk with a warning.

Usage:
  python3 tools/scan_scd.py /tmp/room1070.rdt
"""
from __future__ import annotations

import argparse
import struct
from pathlib import Path

# Fixed sizes from reevengi src/g_re1/scd1.xml. 1+opcodes absent below are
# variable length (0x17, 0x28, 0x33) or undefined.
# SLUS-00551's opcode 0x20 and 0x21 handlers each advance the script by 0xE.
SIZES = {
    0x00: 2, 0x01: 2, 0x02: 2, 0x03: 2, 0x04: 4, 0x05: 4, 0x06: 4,
    0x07: 6, 0x08: 4, 0x09: 2, 0x0A: 2, 0x0B: 4, 0x0C: 26, 0x0D: 18,
    0x0E: 2, 0x0F: 8, 0x10: 2, 0x11: 2, 0x12: 10, 0x13: 4, 0x14: 4,
    0x15: 2, 0x16: 2, 0x18: 26, 0x19: 4, 0x1A: 2, 0x1B: 22,
    0x1C: 6, 0x1D: 2, 0x1E: 4, 0x1F: 30, 0x20: 14, 0x21: 14,
    0x22: 4, 0x23: 2, 0x24: 4, 0x25: 4, 0x26: 1, 0x27: 2, 0x29: 2,
    0x2A: 12, 0x2B: 4, 0x2C: 2, 0x2D: 4, 0x2E: 1, 0x2F: 4,
    0x30: 12, 0x31: 4, 0x32: 4, 0x34: 8, 0x35: 4, 0x36: 4,
    0x37: 4, 0x38: 4, 0x39: 2, 0x3A: 4, 0x3B: 6, 0x3C: 6,
    0x3D: 12, 0x3E: 2, 0x3F: 6, 0x40: 18, 0x41: 4, 0x42: 4,
    0x43: 4, 0x44: 2, 0x45: 2, 0x46: 46, 0x47: 16, 0x48: 2,
    0x49: 2, 0x4A: 2, 0x4B: 2, 0x4C: 4, 0x4D: 2, 0x4E: 4,
    0x4F: 2, 0x50: 2,
}
ITEM_OPS = {0x0D, 0x12, 0x13, 0x18}


def _opcode_size(code: bytes, pos: int) -> tuple[int, str]:
    op = code[pos]
    if op == 0x33:
        # Variable: opcode + type + u0 + u1, then type-dependent tail.
        if pos + 4 > len(code):
            return 0, f"truncated opcode 0x33 at +{pos}"
        typ = code[pos + 1]
        extra = 2 if typ in (0, 4, 6, 7) else 4 if typ in (1, 3, 5, 8, 9, 10) else 0
        size = 4 + extra
    elif op == 0x17:
        # Variable: opcode + u0 + u16 + type u16, then 2 more u16 if type==0.
        if pos + 6 > len(code):
            return 0, f"truncated opcode 0x17 at +{pos}"
        typ = struct.unpack_from("<H", code, pos + 4)[0]
        size = 10 if typ == 0 else 6
    else:
        size = SIZES.get(op)
        if size is None:
            return 0, f"unknown/variable opcode 0x{op:02x} at +{pos}"
    if pos + size > len(code):
        return 0, f"truncated opcode 0x{op:02x} at +{pos}"
    return size, "clean"


def walk(code: bytes, base: int) -> tuple[list[tuple[int, int, bytes]], str]:
    """Return opcodes reachable through either side of each IF."""
    decoded: dict[int, tuple[int, int, bytes]] = {}
    pending = [0]
    issues: list[str] = []
    while pending:
        pos = pending.pop()
        if pos == len(code) or pos in decoded:
            continue
        if pos < 0 or pos > len(code):
            issues.append(f"branch outside procedure at +{pos}")
            continue
        op = code[pos]
        size, status = _opcode_size(code, pos)
        if status != "clean":
            issues.append(status)
            continue
        decoded[pos] = (base + pos, op, code[pos : pos + size])
        if op == 0x00:
            # The pinned executable clears IF depth and ends this procedure.
            continue
        if op == 0x01:
            # A failed IF condition resumes at this block's exit; scan both
            # paths because static RDT data does not establish live flags.
            pending.append(pos + 2 + code[pos + 1])
        elif op == 0x02:
            # ELSE jumps over its alternate branch when the IF body ran.
            skip = code[pos + 1]
            if skip < size:
                issues.append(f"ELSE target inside opcode at +{pos}")
                continue
            pending.append(pos + skip)
            continue
        pending.append(pos + size)
    ordered = sorted(decoded.items())
    max_end = 0
    for offset, row in ordered:
        if offset < max_end:
            issues.append(f"overlapping branch target at +{offset}")
        max_end = max(max_end, offset + len(row[2]))
    status = "clean" if not issues else f"partial: {issues[0]} ({len(issues)} issues)"
    return [row for _, row in ordered], status


def walk_linear(code: bytes, base: int) -> list[tuple[int, int, bytes]]:
    """Keep raw candidates beyond opcode 0 when control flow is unresolved."""
    ops: list[tuple[int, int, bytes]] = []
    pos = 0
    while pos < len(code):
        size, status = _opcode_size(code, pos)
        if status != "clean":
            break
        ops.append((base + pos, code[pos], code[pos : pos + size]))
        pos += size
    return ops


def walk_procedures(span: bytes, base: int) -> tuple[list[tuple[int, int, bytes]], str]:
    """Walk length-prefixed procedures up to their zero-length sentinel."""
    ops: list[tuple[int, int, bytes]] = []
    pos = 0
    issues: list[str] = []
    while pos + 2 <= len(span):
        (length,) = struct.unpack_from("<H", span, pos)
        if length == 0:
            status = (
                "clean"
                if not issues
                else f"partial: {issues[0]} ({len(issues)} procedures)"
            )
            return sorted(ops), status
        if length < 2 or pos + length > len(span):
            return sorted(ops), f"partial: bad procedure length at +{pos}"
        code = span[pos + 2 : pos + length]
        found, status = walk(code, base + pos + 2)
        if status != "clean":
            # A malformed branch can decode payload bytes as phantom opcodes.
            # Keep only the prior linear candidates until this path is resolved.
            ops.extend(walk_linear(code, base + pos + 2))
            issues.append(f"{status.removeprefix('partial: ')} in procedure +{pos}")
        else:
            ops.extend(found)
        pos += length
    return sorted(ops), f"partial: missing procedure sentinel at +{pos}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("rdt", type=Path)
    args = ap.parse_args()
    d = args.rdt.read_bytes()
    offs = struct.unpack_from("<19I", d, 0x48)
    print(f"nItem guess bytes@0x00: {d[:8].hex()}")
    for idx, name in ((6, "init"), (7, "main"), (8, "event")):
        start = offs[idx]
        end = offs[idx + 1]
        print(f"--- chunk {name} file 0x{start:x}..0x{end:x} len {end - start}")
        span = d[start:end]
        if name == "event":
            # Event entry points are not mapped; preserve raw candidates.
            scans = [
                ("raw", walk_linear(span, start), "partial: event entry points unresolved")
            ]
        else:
            scans = [("procedures", *walk_procedures(span, start))]
        for label, ops, status in scans:
            items = [(a, o, b) for a, o, b in ops if o in ITEM_OPS]
            print(f"  [{label}] ops={len(ops)} status={status} item_ops={len(items)}")
            for addr, op, raw in items:
                if op == 0x18:
                    # RE1 layout: id u8, x/y/w/h s16, type u8, amount u8,
                    # unknown bytes 12-21, then globalid u8 at byte 22.
                    _id = raw[1]
                    x, y, w, h = struct.unpack_from("<4h", raw, 2)
                    typ, amt = raw[10], raw[11]
                    gid = raw[22]
                    print(f"    0x18 @0x{addr:x} id={_id} x={x} y={y} w={w} h={h} type=0x{typ:02x} amt={amt} gid={gid} raw={raw.hex()}")
                else:
                    print(f"    0x{op:02x} @0x{addr:x} id={raw[1]} raw={raw.hex()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
