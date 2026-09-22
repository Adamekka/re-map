"""Live debug loop: poll room bytes over GDB and print debug view.

Polls only the configured addresses at ~10 Hz. Unknown addresses exit
with a clear diagnostic instead of guessing.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb
from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import Tracker
from ui.debug_view import render


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", type=Path, default=Path("profiles/re1_ntsc_u.json"))
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--hz", type=float, default=10.0)
    args = ap.parse_args()

    profile = Re1Profile.load(args.profile)
    if profile.stage_address is None or profile.room_address is None:
        print(f"profile {profile.profile_id} has no validated room addresses; refusing to guess")
        print("Run room A vs B diffs first, then fill profiles/*.json with evidence.")
        return 2

    tracker = Tracker()
    gdb = DuckStationGdb(args.host, args.port)
    err = gdb.connect()
    if err:
        print(err, file=sys.stderr)
        return 1
    try:
        period = 1.0 / max(1.0, min(args.hz, 30.0))
        while True:
            stage = gdb.read_u8(profile.stage_address)
            room = gdb.read_u8(profile.room_address)
            if not stage.ok or not room.ok:
                print(f"read failed: {stage.error} {room.error}", file=sys.stderr)
                time.sleep(period)
                continue
            rid = RoomId(stage=int.from_bytes(stage.data, "little"), room=int.from_bytes(room.data, "little"))
            tracker.mark_current(rid)
            rec = tracker.room_state(rid)
            print("\x1b[2J\x1b[H" + render(rid, rec, profile.profile_id))
            time.sleep(period)
    except KeyboardInterrupt:
        return 0
    finally:
        gdb.close()


if __name__ == "__main__":
    raise SystemExit(main())
