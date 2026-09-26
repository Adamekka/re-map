"""Blind door walk with room-change feedback. Tank controls, camera agnostic.

Resumes the game, sweeps facing angles, walks rays, polls Main/Sub over
GDB. Stops when Sub changes or the step budget runs out. Dumps RAM at
start and on any room change. Pauses the game on exit.

Usage:
  python3 tools/walk_doors.py [--rays 10] [--walk 3.0] [--outdir /tmp]
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb


def read_room(gdb: DuckStationGdb) -> tuple[int | None, int | None, int | None]:
    ms = gdb.read_memory(0x800C8660, 3)
    if not ms.ok:
        return None, None, None
    return ms.data[0], ms.data[1], ms.data[2]


def dump_ram(gdb: DuckStationGdb, path: Path, base: int = 0x80000000, size: int = 0x200000) -> bool:
    out = bytearray()
    for off in range(0, size, 2048):
        r = gdb.read_memory(base + off, min(2048, size - off))
        if not r.ok:
            print(f"dump failed at 0x{base + off:x}: {r.error}", flush=True)
            return False
        out.extend(r.data)
    path.write_bytes(bytes(out))
    print(f"dumped {len(out)} bytes to {path}", flush=True)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rays", type=int, default=10)
    ap.add_argument("--walk", type=float, default=3.0)
    ap.add_argument("--turn", type=float, default=0.4)
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--outdir", type=Path, default=Path("/tmp"))
    args = ap.parse_args()

    from pynput.keyboard import Controller, Key

    gdb = DuckStationGdb(port=args.port)
    if gdb.connect():
        print("gdb connect failed", file=sys.stderr)
        return 1
    kb = Controller()
    start = read_room(gdb)
    print(f"start room main={start[0]} sub={start[1]} cam={start[2]}", flush=True)
    if start[0] is None:
        gdb.close()
        return 1
    gdb.resume()
    found = None
    try:
        dump_ok = True
        for ray in range(args.rays):
            # Turn to a new facing, then walk.
            kb.press(Key.left)
            time.sleep(args.turn)
            kb.release(Key.left)
            kb.press("k")
            kb.press(Key.up)
            t0 = time.time()
            while time.time() - t0 < args.walk:
                time.sleep(0.5)
                cur = read_room(gdb)
                if cur[0] is not None and (cur[0], cur[1]) != (start[0], start[1]):
                    found = cur
                    break
            kb.release(Key.up)
            kb.release("k")
            # Tap action in case a door prompt is up.
            kb.press("k")
            time.sleep(0.3)
            kb.release("k")
            time.sleep(0.3)
            cur = read_room(gdb)
            print(f"ray {ray}: main={cur[0]} sub={cur[1]} cam={cur[2]}", flush=True)
            if found is not None:
                break
            # Health check: abort if nearly dead.
            hp = gdb.read_memory(0x800C51AC, 1)
            if hp.ok and hp.data[0] < 0x20:
                print(f"low health 0x{hp.data[0]:02x}, aborting", flush=True)
                break
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
        if found is not None:
            dump_ram(gdb, args.outdir / "ram_roomB.bin")
        gdb.close()
    if found is not None:
        print(f"ROOM CHANGE main={found[0]} sub={found[1]} cam={found[2]}", flush=True)
        return 0
    print("no room change within budget", flush=True)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
