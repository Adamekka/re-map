"""Offline debug view from extracted RAM. No emulator, no window.

Usage:
  python3 tools/track_offline.py RAM.BIN --profile profiles/re1_ntsc_u_slus00170.json --items data/room_items_slus00551.json

Reads room bytes and item flag bytes at the profile addresses, feeds the
Tracker, and prints the milestone 1 debug view. Polarity 1=present and
0=taken is a Candidate assumption from RE1-PICKUP-001, stated in output.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import Tracker
from ui.debug_view import render


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ram", type=Path)
    ap.add_argument("--profile", type=Path, default=Path("profiles/re1_ntsc_u_slus00170.json"))
    ap.add_argument("--items", type=Path, default=Path("data/room_items_slus00551.json"))
    args = ap.parse_args()

    profile = Re1Profile.load(args.profile)
    if not profile.has_room_addresses():
        print("profile lacks room addresses", file=sys.stderr)
        return 2
    assert profile.stage_address is not None and profile.room_address is not None
    ram = args.ram.read_bytes()
    if len(ram) < 0x200000:
        print(f"short ram image: {len(ram)}", file=sys.stderr)
        return 2

    def u8(virt: int) -> int:
        return ram[virt - 0x80000000]

    main_loc = u8(profile.stage_address)
    sub_loc = u8(profile.room_address)
    rid = RoomId(stage=main_loc, room=sub_loc)

    rows = json.loads(args.items.read_text())["rooms"]
    row = next((r for r in rows if r["main"] == main_loc and r["sub"] == sub_loc), None)

    tracker = Tracker()
    tracker.mark_current(rid)
    if row is None:
        rec = tracker.room_state(rid)
        print(render(rid, rec, profile.profile_id))
        print("Room table: no row for this room")
        return 0

    total = len(row["items"])
    collected = 0
    for it in row["items"]:
        addr = int(it["candidate_flag_offset"], 16)
        taken = not Re1Profile.is_bit_set(ram[addr], it["candidate_flag_mask"])
        collected += taken
        state = "taken" if taken else "present?"
        print(f"- {it['type_name']} x{it['amount']} gid={it['global_id']}: {state} (assumes 1=present 0=taken, Candidate)")
    tracker.update_room_items(
        rid,
        total=total,
        collected=collected,
        list_complete=bool(row["list_complete"]),
        any_available_uncollected=False,
        any_unknown=True,
    )
    rec = tracker.room_state(rid)
    print(render(rid, rec, profile.profile_id))
    print(f"Room table: {row['name']}, list complete: {'yes' if row['list_complete'] else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
