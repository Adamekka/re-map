"""Decode game Map Visited bytes into room name lists.

The game tracks visited rooms itself in 0xC8710 onward, one room per bit
per RA notes. The tracker reads these as game-derived visited state,
reread on every load, separate from its own observation history.

Usage:
  python3 tools/map_visited.py RAM.BIN
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from join_ra_rdt import norm  # noqa: E402

MD = REPO / "docs" / "re1_ram_map_user_provided.md"


def parse_visited(text: str) -> list[tuple[int, int, str]]:
    rows: list[tuple[int, int, str]] = []
    # Join wrapped lines first.
    joined: list[str] = []
    in_group = False
    for line in text.splitlines():
        if re.match(r"- Map Visited 0x", line):
            joined.append(line.strip())
            in_group = True
        elif line.startswith("- "):
            in_group = False
        elif in_group and re.match(r"\s+Bit\d", line):
            joined[-1] += " " + line.strip()
    for line in joined:
        m = re.match(r"- Map Visited (0x[0-9a-fA-F]+) (.*)$", line)
        if not m:
            continue
        off = int(m.group(1), 16)
        for bm in re.finditer(r"Bits?(\d+)(?:-(\d+))?\s+([^,]+?)(?=, Bits?\d|$)", m.group(2)):
            lo = int(bm.group(1))
            hi = int(bm.group(2)) if bm.group(2) else lo
            label = bm.group(3).strip()
            if not label or label in ("???", "empty as given"):
                continue
            rows.append((off, sum(1 << b for b in range(lo, hi + 1)), label))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ram", type=Path)
    args = ap.parse_args()
    ram = args.ram.read_bytes()
    for off, mask, label in parse_visited(MD.read_text()):
        val = ram[off]
        hit = "VISITED" if val & mask else "-"
        print(f"{hit} 0x{off:05X}:{mask:#04x} {label} (ram=0x{val:02x})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
