"""Closed-loop navigation to a door box using player pos and facing.

Calibrates facing-to-direction, then pursues the nearest door center in
aim/walk bursts until the room changes. Aborts on HP loss or timeout.

Usage:
  python3 tools/navigate.py --tx 24400 --tz 1650 [--toroom 8]
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb

PX, PZ, FA = 0x800C5158, 0x800C5160, 0x800C5148
ROOM = 0x800C8660
HP = 0x800C51AC
MOD = 65536


def rd(gdb: DuckStationGdb, addr: int) -> int | None:
    for _ in range(5):
        r = gdb.read_memory(addr, 2)
        if r.ok:
            return struct.unpack("<H", r.data)[0]
        time.sleep(0.15)
    return None


def s16(v: int) -> int:
    return v if v < 0x8000 else v - 0x10000


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tx", type=float, required=True)
    ap.add_argument("--tz", type=float, required=True)
    ap.add_argument("--toroom", type=int, default=-1)
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--budget", type=float, default=240.0)
    args = ap.parse_args()

    from pynput.keyboard import Controller, Key

    gdb = DuckStationGdb(port=args.port)
    if gdb.connect():
        return 1
    kb = Controller()
    t0 = time.time()
    hp0 = rd(gdb, HP)

    def facing() -> int | None:
        return rd(gdb, FA)

    def pos() -> tuple | None:
        x, z = rd(gdb, PX), rd(gdb, PZ)
        if x is None or z is None:
            return None
        return (s16(x), s16(z))

    def room() -> tuple | None:
        r = gdb.read_memory(ROOM, 2)
        return (r.data[0], r.data[1]) if r.ok else None

    start_room = room()
    print(f"start room={start_room} hp={hp0:#x}", flush=True)
    try:
        gdb.resume()
        # Calibrate: two facings 1s of left turn apart, 1s walk each.
        dirs = []
        for i in range(2):
            f = facing()
            kb.press(Key.up)
            time.sleep(1.0)
            kb.release(Key.up)
            p0 = pos()
            kb.press(Key.up)
            time.sleep(1.0)
            kb.release(Key.up)
            time.sleep(0.2)
            p1 = pos()
            dx, dz = p1[0] - p0[0], p1[1] - p0[1]
            dirs.append((f, dx, dz))
            print(f"cal {i}: facing={f} d=({dx},{dz})", flush=True)
            kb.press(Key.left)
            time.sleep(1.0)
            kb.release(Key.left)
            time.sleep(0.2)
        (f0, dx0, dz0), (f1, dx1, dz1) = dirs
        # Facing decreases on left turn. Angle of motion per facing unit:
        a0 = math.atan2(dz0, dx0)
        a1 = math.atan2(dz1, dx1)
        df = (f1 - f0) % MOD
        if df > MOD / 2:
            df -= MOD
        da = a1 - a0
        while da > math.pi:
            da -= 2 * math.pi
        while da < -math.pi:
            da += 2 * math.pi
        k = da / df if df else 0
        print(f"turn {df} units rotated motion {da:.3f} rad, k={k:.5f}", flush=True)
        if not k:
            print("calibration failed", flush=True)
            return 2
        # Pursue.
        while time.time() - t0 < args.budget:
            p = pos()
            f = facing()
            cur_room = room()
            if cur_room is None:
                time.sleep(0.5)
                continue
            if cur_room != start_room:
                print(f"ROOM CHANGE {start_room} -> {cur_room}", flush=True)
                return 0
            hp = rd(gdb, HP)
            if hp is not None and hp0 is not None and hp + 0x30 < hp0:
                print(f"hp drop {hp0:#x} -> {hp:#x}, aborting", flush=True)
                return 3
            want = math.atan2(args.tz - p[1], args.tx - p[0])
            have = a0 + k * ((f - f0) % MOD if ((f - f0) % MOD) < MOD / 2 else ((f - f0) % MOD) - MOD)
            err = want - have
            while err > math.pi:
                err -= 2 * math.pi
            while err < -math.pi:
                err += 2 * math.pi
            dist = math.hypot(args.tx - p[0], args.tz - p[1])
            print(f"pos={p} f={f} err={err:.2f} dist={dist:.0f}", flush=True)
            if abs(err) > 0.25:
                # Turn toward target. Facing decreases on left.
                # d(err)/d(left-turn) = -k*|dF|. With k<0 (check sign),
                # pick the key that reduces |err|.
                key = Key.left if (err * k < 0) else Key.right
                kb.press(key)
                time.sleep(min(0.8, abs(err) * 0.8))
                kb.release(key)
            else:
                kb.press(Key.up)
                time.sleep(1.2)
                kb.release(Key.up)
            time.sleep(0.2)
        print("budget out", flush=True)
        return 4
    finally:
        for k in ("up", "left", "right"):
            try:
                kb.release(getattr(Key, k))
            except Exception:
                pass
        gdb.interrupt()
        gdb.close()


if __name__ == "__main__":
    raise SystemExit(main())
