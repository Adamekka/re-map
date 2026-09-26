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


# Runtime Main to file folder linkage is Candidate, confirmed only for
# Main 0 -> STAGE1. Other values refuse instead of guessing.
MAIN_TO_STAGE = {0: "STAGE1"}
# Candidate flag knowledge: (main, sub, type, gid) -> (offset, mask).
# Only Art Room entries below are observed. Everything else is unknown.
KNOWN_FLAGS = {
    (0, 7, "0x2f", 24): (0xC86E3, 0x01),
    (0, 9, "0x44", 0): (0xC86EA, 0x01),
    (0, 0x18, "0x26", 0): (0xC86DE, 0x04),
}


def resolve_room_file(main: int, sub: int) -> str | None:
    stage = MAIN_TO_STAGE.get(main)
    if stage is None:
        return None
    return f"PSX/{stage}/ROOM1{sub:02X}0.RDT"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ram", type=Path)
    ap.add_argument("--profile", type=Path, default=Path("profiles/re1_ntsc_u_slus00170.json"))
    ap.add_argument("--items", type=Path, default=Path("data/item_table_slus00551.json"))
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

    table_path = Path(args.items)
    table = json.loads(table_path.read_text())
    rooms = table["rooms"] if isinstance(table, dict) and "rooms" in table else table

    tracker = Tracker()
    tracker.mark_current(rid)
    fname = resolve_room_file(main_loc, sub_loc)
    if fname is None:
        rec = tracker.room_state(rid)
        print(render(rid, rec, profile.profile_id))
        print(f"Room file linkage: Main {main_loc} has no confirmed stage folder, refusing to guess")
        return 0
    row = next((r for r in rooms if r.get("file") == fname), None)
    if row is None:
        rec = tracker.room_state(rid)
        print(render(rid, rec, profile.profile_id))
        print(f"Room file linkage: {fname} not in table (Candidate rule)")
        return 0

    placed = [i for i in row.get("items", []) if i["x"] or i["y"]]
    # Group by pickup spot. Rows identical in id and box are character or
    # mode variants of one pickup, for example Jill gets Chemical while
    # Chris gets the Broken Shotgun at the same spot and id.
    spots: dict[tuple, list] = {}
    for it in placed:
        key = (it["id"], it["x"], it["y"], it["w"], it["h"])
        spots.setdefault(key, []).append(it)
    total = len(spots)
    collected = 0
    unknown = 0
    present_known = 0
    for (pid, x, y, w, h), variants in sorted(spots.items()):
        if len(variants) == 1:
            it = variants[0]
            key = (main_loc, sub_loc, it["type"], it["gid"])
            flag = KNOWN_FLAGS.get(key)
            if flag is None:
                unknown += 1
                print(f"- type {it['type']} x{it['amount']} gid={it['gid']}: unknown (no flag observed)")
                continue
            off, mask = flag
            taken = not Re1Profile.is_bit_set(ram[off], mask)
            collected += taken
            present_known += not taken
            state = "taken" if taken else "PRESENT"
            print(f"- type {it['type']} x{it['amount']} gid={it['gid']}: {state} (flag 0x{off:X}:{mask:#x}, Candidate)")
            continue
        vdesc = ",".join(f"{v['type']}x{v['amount']}" for v in variants)
        known = [(v, KNOWN_FLAGS[(main_loc, sub_loc, v["type"], v["gid"])])
                 for v in variants
                 if (main_loc, sub_loc, v["type"], v["gid"]) in KNOWN_FLAGS]
        if not known:
            unknown += 1
            print(f"- spot id={pid} variants {vdesc}: unknown (no flag observed)")
            continue
        taken_any = False
        for v, (off, mask) in known:
            taken = not Re1Profile.is_bit_set(ram[off], mask)
            taken_any = taken_any or taken
            state = "taken" if taken else "PRESENT"
            print(f"- spot id={pid} {v['type']} x{v['amount']}: {state} (flag 0x{off:X}:{mask:#x}, Candidate)")
        collected += taken_any
        present_known += not taken_any
    tracker.update_room_items(
        rid,
        total=total,
        collected=collected,
        list_complete=False,
        any_available_uncollected=present_known > 0,
        any_unknown=True,
    )
    rec = tracker.room_state(rid)
    print(render(rid, rec, profile.profile_id))
    print(f"Room file linkage: {fname} (Candidate rule), list complete: no")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
