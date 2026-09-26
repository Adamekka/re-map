"""Drive DuckStation with keyboard input while polling room over GDB.

Usage:
  python3 tools/drive.py --keys Up,Up,K --hold 0.6 --poll 10

Sends key holds and taps with pynput, printing Main/Sub/Camera after each
step. The emulator window must be focused. macOS may ask for
accessibility permission on first use.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb

KEYMAP = {
    "Up": "up", "Down": "down", "Left": "left", "Right": "right",
    "W": "w", "A": "a", "S": "s", "D": "d",
    "I": "i", "J": "j", "K": "k", "L": "l",
    "Q": "q", "E": "e", "Enter": "enter",
}


def room(gdb: DuckStationGdb) -> str:
    vals = []
    for a in (0x800C8660, 0x800C8661, 0x800C8662, 0x800C8454):
        r = gdb.read_memory(a, 1)
        vals.append(f"{r.data[0]:02x}" if r.ok else "??")
    return f"main={vals[0]} sub={vals[1]} cam={vals[2]} state={vals[3]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keys", default="")
    ap.add_argument("--hold", type=float, default=0.6)
    ap.add_argument("--port", type=int, default=2345)
    args = ap.parse_args()

    from pynput.keyboard import Controller, Key

    gdb = DuckStationGdb(port=args.port)
    err = gdb.connect()
    if err:
        print(err, file=sys.stderr)
        return 1
    kb = Controller()
    print("start", room(gdb), flush=True)
    try:
        for name in [k for k in args.keys.split(",") if k]:
            key = KEYMAP.get(name, name)
            special = getattr(Key, key, None) if len(key) > 1 else None
            k = special or key
            kb.press(k)
            time.sleep(args.hold)
            kb.release(k)
            time.sleep(0.3)
            print(f"{name}:", room(gdb), flush=True)
    finally:
        gdb.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
