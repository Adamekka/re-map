"""Join RA item flag notes with RDT placed entries, side by side.

No forced associations. A flag and an RDT entry in the same room are
listed together with association marked observed or unproven. Observed
links live in track_offline.KNOWN_FLAGS, nowhere else.

Usage:
  python3 tools/join_ra_rdt.py > /tmp/join_preview.txt
  python3 tools/join_ra_rdt.py --out data/room_flags_candidate.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MD = REPO / "docs" / "re1_ram_map_user_provided.md"
TABLE = REPO / "data" / "item_table_slus00551.json"


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", s.lower())


def parse_item_flags(text: str) -> list[dict]:
    rows = []
    in_section = False
    for line in text.splitlines():
        if line.startswith("## Item Collected"):
            in_section = True
            continue
        if in_section and line.startswith("## "):
            break
        if not in_section:
            continue
        m = re.match(r"- (0x[0-9a-f]+) (.*)", line)
        if not m:
            continue
        off = int(m.group(1), 16)
        for bm in re.finditer(r"Bit(\d+)(?:-(\d+))?\s+([^,]+?)(?=, Bit\d|$)", m.group(2)):
            lo = int(bm.group(1))
            hi = int(bm.group(2)) if bm.group(2) else lo
            label = bm.group(3).strip()
            mask = sum(1 << b for b in range(lo, hi + 1))
            rows.append({"offset": off, "mask": mask, "bits": [lo, hi], "label": label})
    return rows


def parse_rooms(text: str) -> dict[str, tuple[int, int]]:
    """Normalized room name -> (main, sub). Mansion 1F only for now."""
    rooms: dict[str, tuple[int, int]] = {}
    mains = {"mansion1f": 0, "mansion2f": 1, "courtyardunderground": 2,
             "guardhouse": 3, "laboratory": 4}
    # Room lists wrap across lines. Join continuation lines first.
    joined: list[str] = []
    for line in text.splitlines():
        if re.match(r"\s+- [^:]+: 0x", line):
            joined.append(line.strip())
        elif joined and re.match(r"\s+0x[0-9a-fA-F]+ ", line):
            joined[-1] += " " + line.strip()
    for line in joined:
        m = re.match(r"- ([^:]+): (0x[0-9a-fA-F]+ .*)$", line)
        if not m:
            continue
        group, rest = m.group(1).strip(), m.group(2)
        main = mains.get(norm(group))
        if main is None:
            continue
        for rm in re.finditer(r"(0x[0-9a-fA-F]+) ([^,]+?)(?=, 0x|$)", rest):
            sub = int(rm.group(1), 16)
            key = norm(rm.group(2).strip())
            # First group wins. Later areas reuse names like Central
            # Corridor, and Mansion 1F is the runtime-verified area.
            rooms.setdefault(key, (main, sub))
    return rooms


def des(s: str) -> str:
    """Possessive-insensitive form: Keeper's Bedroom also matches Keeper Bedroom."""
    return norm(s).replace("s", "")


def room_of_flag(label: str, rooms: dict) -> tuple[int, int] | None:
    nl = norm(label)
    # "Map on Art Room" style: room is the tail after on.
    m = re.search(r" on ([a-z0-9 '\-]+)$", label, re.IGNORECASE)
    if m and norm(m.group(1)) in rooms:
        return rooms[norm(m.group(1))]
    # Otherwise the room is a leading prefix. Longest match wins so
    # Wardrobe Closet beats Wardrobe.
    best = None
    for name, room in rooms.items():
        if nl.startswith(name) or des(nl).startswith(des(name)):
            if best is None or len(name) > len(best[0]):
                best = (name, room)
    if best:
        return best[1]
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    text = MD.read_text()
    flags = parse_item_flags(text)
    rooms = parse_rooms(text)
    table = json.loads(TABLE.read_text())["rooms"]
    by_file = {r["file"]: r for r in table}

    out_rows = []
    unmatched = []
    for f in flags:
        room = room_of_flag(f["label"], rooms)
        row: dict = {"offset": hex(f["offset"]), "mask": f["mask"],
                     "label": f["label"], "source": "RA notes, Candidate"}
        if room is None:
            row["room"] = None
            unmatched.append(f["label"])
        else:
            main, sub = room
            row["room"] = {"main": main, "sub": sub}
            fname = f"PSX/STAGE1/ROOM1{sub:02X}0.RDT" if main == 0 else None
            row["file_guess"] = fname
            if fname and fname in by_file:
                placed = [i for i in by_file[fname].get("items", []) if i["x"] or i["y"]]
                row["rdt_placed"] = [
                    {"id": i["id"], "type": i["type"], "amount": i["amount"], "gid": i["gid"]}
                    for i in placed
                ]
            row["association"] = "unproven"
        out_rows.append(row)

    matched = sum(1 for r in out_rows if r["room"] is not None)
    print(f"flags={len(out_rows)} room_matched={matched} unmatched={len(unmatched)}", file=sys.stderr)
    for label in unmatched:
        print(f"  no-room: {label}", file=sys.stderr)
    if args.out:
        args.out.write_text(json.dumps({"flags": out_rows}, indent=1))
        print(f"wrote {args.out}", file=sys.stderr)
    else:
        for r in out_rows[:12]:
            print(r)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
