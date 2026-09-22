"""Byte diff for controlled RAM comparisons.

Usage:
  python3 tools/ram_diff.py a.bin b.bin [--width 16] [--max 100]

Why this exists: AGENTS.md requires save-in-A, dump, move or pick up,
dump again, compare. This script keeps that loop small and repeatable.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a", type=Path)
    ap.add_argument("b", type=Path)
    ap.add_argument("--width", type=int, default=16)
    ap.add_argument("--max", type=int, default=100)
    args = ap.parse_args()

    da = args.a.read_bytes()
    db = args.b.read_bytes()
    if len(da) != len(db):
        print(f"size differs: {len(da)} vs {len(db)}", file=sys.stderr)
        return 2
    changed = [i for i in range(len(da)) if da[i] != db[i]]
    print(f"size={len(da)} changed_bytes={len(changed)}")
    for i in changed[: args.max]:
        print(f"0x{i:06x}: 0x{da[i]:02x} -> 0x{db[i]:02x}")
    if len(changed) > args.max:
        print(f"... and {len(changed) - args.max} more")
    # Bit-level detail for the first few changes helps flag bitfields.
    for i in changed[: min(8, args.max)]:
        xor = da[i] ^ db[i]
        bits = [str(b) for b in range(8) if xor & (1 << b)]
        print(f"  0x{i:06x} bits changed: {','.join(bits)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
