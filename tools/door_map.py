"""Topology map from the door graph. No geometry, just connectivity.

Nodes are RDT files, edges are Door_set targets. Runtime names attach
where the filename rule plus RA SubLocation lists agree. Unresolved
numbering stays numeric, never guessed.

Usage:
  python3 tools/door_map.py [--dot out.dot] [ROOM...]
  Without args, prints the Mansion 1F (STAGE1, stage 0 targets) subgraph.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from join_ra_rdt import parse_rooms  # noqa: E402

TABLE = REPO / "data" / "item_table_slus00551.json"
MD = REPO / "docs" / "re1_ram_map_user_provided.md"


def file_room(path: str) -> tuple[int, str] | None:
    m = re.search(r"STAGE([0-9A-Z])/ROOM([0-9A-F]{4})\.RDT", path)
    if not m:
        return None
    return m.group(1), m.group(2)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dot", type=Path, default=None)
    ap.add_argument("rooms", nargs="*", default=[])
    args = ap.parse_args()

    table = json.loads(TABLE.read_text())["rooms"]
    rooms = parse_rooms(MD.read_text())
    inv = {(m, s): n for n, (m, s) in rooms.items() if m == 0}

    # STAGE1 files whose doors target stage 0 form the Mansion 1F subgraph.
    nodes: dict[str, list] = {}
    for r in table:
        fr = file_room(r["file"])
        if not fr or fr[0] != "1":
            continue
        try:
            self_room = int(fr[1][1:3], 16)
        except ValueError:
            continue
        edges = []
        for d in r.get("doors", []):
            if d["next_stage"] != 0:
                continue
            edges.append(d["next_room"])
        nodes[f"{self_room:02X}"] = sorted(set(edges))

    if args.rooms:
        want = {x.upper() for x in args.rooms}
        nodes = {k: [e for e in v] for k, v in nodes.items() if k in want}
    print(f"nodes={len(nodes)} edges={sum(len(v) for v in nodes.values())}")
    for k in sorted(nodes):
        name = inv.get((0, int(k, 16)), "?")
        targets = []
        for e in nodes[k]:
            tname = inv.get((0, e), "?")
            targets.append(f"{e:02X}({tname})")
        print(f"  {k} {name} -> {', '.join(targets)}")
    if args.dot:
        lines = ["digraph mansion1f {", '  rankdir=LR; node [shape=box];']
        for k in sorted(nodes):
            name = inv.get((0, int(k, 16)), k)
            lines.append(f'  "{k}" [label="{k} {name}"];')
        for k in sorted(nodes):
            for e in nodes[k]:
                if f"{e:02X}" in nodes:
                    lines.append(f'  "{k}" -> "{e:02X}";')
        lines.append("}")
        args.dot.write_text("\n".join(lines) + "\n")
        print(f"wrote {args.dot}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
