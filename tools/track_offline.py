"""Interpret one extracted PS1 RAM snapshot without connecting to an emulator.

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
from track import (
    Re3DiscError,
    TrackingProfileError,
    load_tracking_profile,
    poll_once,
    resolve_tracking_disc,
)
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
    ap.add_argument("--disc", type=Path, help="owned disc CUE, required for RE3")
    args = ap.parse_args()

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

    try:
        disc_tracks = ()
        if args.disc is not None:
            _, disc_tracks = resolve_tracking_disc(args.disc)
        profile = load_tracking_profile(args.profile, disc_tracks)
    except (Re3DiscError, TrackingProfileError) as error:
        print(str(error), file=sys.stderr)
        return 2
    except TypeError as error:
        # Offline replay has no diagnostic log. Preserve its profile error
        # for invalid field types reported by the game loaders.
        print(str(TrackingProfileError(args.profile, error)), file=sys.stderr)
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
