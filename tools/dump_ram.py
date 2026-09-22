"""Dump PS1 RAM over the DuckStation GDB server.

Usage:
  python3 tools/dump_ram.py --address 0x80000000 --length 2097152 --out /tmp/ram_a.bin

Dumps are for controlled comparisons only. Keep dumps out of git.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--address", required=True, help="hex PS1 address, e.g. 0x80000000")
    ap.add_argument("--length", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--chunk", type=int, default=2048)
    args = ap.parse_args()

    address = int(args.address, 16)
    remaining = args.length
    out = bytearray()
    gdb = DuckStationGdb(args.host, args.port)
    err = gdb.connect()
    if err:
        print(err, file=sys.stderr)
        return 1
    try:
        offset = 0
        while remaining > 0:
            n = min(remaining, args.chunk)
            res = gdb.read_memory(address + offset, n)
            if not res.ok:
                print(f"read failed at 0x{address + offset:x}: {res.error}", file=sys.stderr)
                return 1
            out.extend(res.data)
            offset += n
            remaining -= n
    finally:
        gdb.close()
    args.out.write_bytes(bytes(out))
    print(f"wrote {len(out)} bytes to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
