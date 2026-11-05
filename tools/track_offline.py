"""Interpret one extracted RE1 RAM snapshot without connecting to an emulator.

Usage:
  python3 tools/track_offline.py /tmp/ram.bin

Uses the live tracker's revision, source, item and door checks. The snapshot
establishes only its current room; no exploration history is read or written.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import MemRead
from games.re1.re1_profile import Re1Profile
from track import poll_once
from tracker.exploration_state import Tracker
from tracker.polling import PollStatus


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("ram", type=Path)
    ap.add_argument(
        "--profile",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "profiles/re1_directors_cut_slus00551.json",
    )
    args = ap.parse_args()

    profile = Re1Profile.load(args.profile)
    try:
        ram = args.ram.read_bytes()
    except OSError as error:
        print(f"Cannot read RAM image: {error}", file=sys.stderr)
        return 2
    if len(ram) != 0x200000:
        print(
            f"RAM image must contain exactly 2097152 bytes; got {len(ram)}.",
            file=sys.stderr,
        )
        return 2

    def read_memory(address: int, length: int) -> MemRead:
        offset = address - 0x80000000
        if not 0 <= offset < offset + length <= len(ram):
            return MemRead(False, b"", "outside the captured PS1 RAM")
        return MemRead(True, ram[offset : offset + length])

    # Shared interpretation prevents offline checks from guessing another room variant.
    result = poll_once(profile, Tracker(), read_memory)
    success = result.status is PollStatus.Display
    print(result.text, file=sys.stdout if success else sys.stderr)
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
