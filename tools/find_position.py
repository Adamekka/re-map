"""Find player position by triple-diffing RAM across walks.

Dump while paused, walk while resumed in a fixed facing, dump again.
16-bit addrs changing monotonically in small steps are position leads.

Usage:
  python3 tools/find_position.py [--outdir /tmp]
"""
from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb

BASE = 0x80000000
SIZE = 0x200000
CHUNK = 2048


def dump(gdb: DuckStationGdb) -> bytes:
    out = bytearray()
    for off in range(0, SIZE, CHUNK):
        for _ in range(5):
            r = gdb.read_memory(BASE + off, min(CHUNK, SIZE - off))
            if r.ok:
                break
            time.sleep(0.2)
        if not r.ok:
            raise IOError(f"dump failed at 0x{off:x}: {r.error}")
        out.extend(r.data)
    return bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=Path, default=Path("/tmp"))
    ap.add_argument("--port", type=int, default=2345)
    args = ap.parse_args()

    from pynput.keyboard import Controller, Key

    gdb = DuckStationGdb(port=args.port)
    if gdb.connect():
        return 1
    kb = Controller()
    snaps = []
    try:
        gdb.interrupt()
        snaps.append(dump(gdb))
        print("dump A ok", flush=True)
        for tag in ("B", "C"):
            gdb.resume()
            kb.press(Key.up)
            time.sleep(2.0)
            kb.release(Key.up)
            time.sleep(0.3)
            gdb.interrupt()
            snaps.append(dump(gdb))
            print(f"dump {tag} ok", flush=True)
    finally:
        try:
            kb.release(Key.up)
        except Exception:
            pass
        gdb.interrupt()
        gdb.close()
    a, b, c = snaps
    for i, s in enumerate(snaps):
        (args.outdir / f"pos_{'ABC'[i]}.bin").write_bytes(s)
    leads = []
    for off in range(0, SIZE - 1, 2):
        va = struct.unpack_from("<H", a, off)[0]
        vb = struct.unpack_from("<H", b, off)[0]
        vc = struct.unpack_from("<H", c, off)[0]
        dab, dbc = (vb - va) & 0xFFFF, (vc - vb) & 0xFFFF
        # Same direction, small steps, nonzero. Handle wrap via signed delta.
        sab = dab if dab < 0x8000 else dab - 0x10000
        sbc = dbc if dbc < 0x8000 else dbc - 0x10000
        if sab != 0 and sbc != 0 and (sab > 0) == (sbc > 0) and abs(sab) < 3000 and abs(sbc) < 3000:
            leads.append((off, va, vb, vc))
    print(f"leads: {len(leads)}", flush=True)
    for off, va, vb, vc in leads[:40]:
        print(f"  0x{off:06x}: {va} -> {vb} -> {vc}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
