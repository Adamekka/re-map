"""Scan RE1 RDT script chunks for item opcodes using reevengi scd1.xml sizes.

Local helper only. Prints 0x0D/0x12/0x13/0x18 entries with raw fields.
Bytecode walking uses fixed opcode sizes. Variable opcodes
(0x17, 0x28, 0x33) stop the walk with a warning.

Usage:
  python3 tools/scan_scd.py /tmp/room1070.rdt
"""
from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

# Fixed sizes from reevengi src/g_re1/scd1.xml. 1+opcodes absent below are
# variable length (0x17, 0x28, 0x33) or undefined.
SIZES = {
    0x00: 2, 0x01: 2, 0x02: 2, 0x03: 2, 0x04: 4, 0x05: 4, 0x06: 4,
    0x07: 6, 0x08: 4, 0x09: 2, 0x0A: 2, 0x0B: 4, 0x0C: 26, 0x0D: 18,
    0x0E: 2, 0x0F: 8, 0x10: 2, 0x11: 2, 0x12: 10, 0x13: 4, 0x14: 4,
    0x15: 2, 0x16: 2, 0x18: 26, 0x19: 4, 0x1A: 2, 0x1B: 22,
    0x1C: 6, 0x1D: 2, 0x1E: 4, 0x1F: 30, 0x20: 16, 0x21: 18,
    0x22: 4, 0x23: 2, 0x24: 4, 0x25: 4, 0x26: 1, 0x27: 2, 0x29: 2,
    0x2A: 12, 0x2B: 4, 0x2C: 2, 0x2D: 4, 0x2E: 1, 0x2F: 4,
    0x30: 12, 0x31: 4, 0x32: 4, 0x34: 8, 0x35: 4, 0x36: 4,
    0x37: 4, 0x38: 4, 0x39: 2, 0x3A: 4, 0x3B: 6, 0x3C: 6,
    0x3D: 12, 0x3E: 2, 0x3F: 6, 0x40: 18, 0x41: 4, 0x42: 4,
    0x43: 4, 0x44: 2, 0x45: 2, 0x46: 44, 0x47: 16, 0x48: 2,
    0x49: 2, 0x4A: 2, 0x4B: 2, 0x4C: 4, 0x4D: 2, 0x4E: 4,
    0x4F: 2, 0x50: 2,
}
ITEM_OPS = {0x0D, 0x12, 0x13, 0x18}


def walk(code: bytes, base: int) -> tuple[list[tuple[int, int, bytes]], str]:
    """Walk bytecode. Returns (op list, status)."""
    ops: list[tuple[int, int, bytes]] = []
    pos = 0
    while pos < len(code):
        op = code[pos]
        size = SIZES.get(op)
        if size is None:
            return ops, f"unknown/variable opcode 0x{op:02x} at +{pos}"
        if pos + size > len(code):
            return ops, f"truncated opcode 0x{op:02x} at +{pos}"
        ops.append((base + pos, op, code[pos : pos + size]))
        pos += size
    return ops, "clean"


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
        # Chunk is u16 length prefixed procedures. Try whole span as code
        # after one u16, else raw span.
        span = d[start:end]
        (length,) = struct.unpack_from("<H", span, 0)
        cands = []
        if length + 2 <= len(span):
            cands.append(("len-prefix", span[2 : 2 + length]))
        cands.append(("raw", span))
        for label, code in cands:
            ops, status = walk(code, start + (2 if label == "len-prefix" else 0))
            items = [(a, o, b) for a, o, b in ops if o in ITEM_OPS]
            print(f"  [{label}] ops={len(ops)} status={status} item_ops={len(items)}")
            for addr, op, raw in items:
                if op == 0x18:
                    # biorand RE1 split: id u8, x/y/w/h s16, type u8, amount u8,
                    # unk8, unk2, globalid u8, ...
                    _id = raw[1]
                    x, y, w, h = struct.unpack_from("<4h", raw, 2)
                    typ, amt = raw[10], raw[11]
                    gid = raw[16]
                    print(f"    0x18 @0x{addr:x} id={_id} x={x} y={y} w={w} h={h} type=0x{typ:02x} amt={amt} gid={gid} raw={raw.hex()}")
                else:
                    print(f"    0x{op:02x} @0x{addr:x} id={raw[1]} raw={raw.hex()}")
            if status == "clean":
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
