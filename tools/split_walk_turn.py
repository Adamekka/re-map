"""Separate walk-movers from turn-movers to find player pos and facing.

Phases: dump, walk straight, dump, turn in place, dump. An address that
moves in the walk phase but not the turn phase is player position. One
that moves in the turn phase is facing or camera.

Usage:
  python3 tools/split_walk_turn.py
"""
from __future__ import annotations

import struct
import sys
import time

sys.path.insert(0, "src")

from emulator.duckstation_gdb import DuckStationGdb

START = 0x800C4000
LEN = 0x20000
CHUNK = 2048


def dump(gdb: DuckStationGdb) -> bytes:
    out = bytearray()
    for off in range(0, LEN, CHUNK):
        for _ in range(5):
            r = gdb.read_memory(START + off, min(CHUNK, LEN - off))
            if r.ok:
                break
            time.sleep(0.2)
        if not r.ok:
            raise IOError(f"dump failed at 0x{off:x}")
        out.extend(r.data)
    return bytes(out)


def main() -> int:
    from pynput.keyboard import Controller, Key

    gdb = DuckStationGdb()
    if gdb.connect():
        return 1
    kb = Controller()
    try:
        gdb.interrupt()
        a = dump(gdb)
        print("dump A ok", flush=True)
        gdb.resume()
        kb.press(Key.up)
        time.sleep(2.0)
        kb.release(Key.up)
        time.sleep(0.3)
        gdb.interrupt()
        b = dump(gdb)
        print("dump B ok", flush=True)
        gdb.resume()
        kb.press(Key.left)
        time.sleep(2.0)
        kb.release(Key.left)
        time.sleep(0.3)
        gdb.interrupt()
        c = dump(gdb)
        print("dump C ok", flush=True)
    finally:
        try:
            kb.release(Key.up)
        except Exception:
            pass
        try:
            kb.release(Key.left)
        except Exception:
            pass
        gdb.interrupt()
        gdb.close()
    open("/tmp/wtc_a.bin", "wb").write(a)
    open("/tmp/wtc_b.bin", "wb").write(b)
    open("/tmp/wtc_c.bin", "wb").write(c)
    print("=== walk-only movers (16-bit, small) ===", flush=True)
    n = 0
    for off in range(0, LEN - 1, 2):
        va = struct.unpack_from("<H", a, off)[0]
        vb = struct.unpack_from("<H", b, off)[0]
        vc = struct.unpack_from("<H", c, off)[0]
        dw = (vb - va) & 0xFFFF
        dt = (vc - vb) & 0xFFFF
        sw = dw if dw < 0x8000 else dw - 0x10000
        st = dt if dt < 0x8000 else dt - 0x10000
        if sw != 0 and st == 0 and abs(sw) < 3000:
            print(f"  walk 0x{START+off:08x}: {va} -> {vb} (turn: {vb})", flush=True)
            n += 1
            if n > 25:
                break
    print("=== turn-only movers (16-bit, small) ===", flush=True)
    n = 0
    for off in range(0, LEN - 1, 2):
        va = struct.unpack_from("<H", a, off)[0]
        vb = struct.unpack_from("<H", b, off)[0]
        vc = struct.unpack_from("<H", c, off)[0]
        dw = (vb - va) & 0xFFFF
        dt = (vc - vb) & 0xFFFF
        sw = dw if dw < 0x8000 else dw - 0x10000
        st = dt if dt < 0x8000 else dt - 0x10000
        if sw == 0 and st != 0 and abs(st) < 3000:
            print(f"  turn 0x{START+off:08x}: {vb} -> {vc}", flush=True)
            n += 1
            if n > 25:
                break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
