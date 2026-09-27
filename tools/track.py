"""Live debug loop: poll room bytes over GDB and print debug view.

Polls only the configured addresses at ~10 Hz. Unknown addresses exit
with a clear diagnostic instead of guessing.
"""

from __future__ import annotations

import argparse
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb
from games.re1.re1_profile import MemoryResult, PilotItemState, Re1Profile
from tracker.exploration_state import Tracker
from ui.debug_view import render


class PollStatus(Enum):
    Display = "display"
    ReadFailure = "read-failure"
    Retry = "retry"
    WrongGame = "wrong-game"


@dataclass(frozen=True)
class PollResult:
    status: PollStatus
    text: str


def poll_once(
    profile: Re1Profile,
    tracker: Tracker,
    read_memory: Callable[[int, int], MemoryResult],
) -> PollResult:
    identity = profile.verify_runtime(read_memory)
    if not identity.ok:
        return PollResult(
            PollStatus.ReadFailure, f"game identity read failed: {identity.error}"
        )
    if not identity.value:
        return PollResult(
            PollStatus.WrongGame,
            f"running game does not match profile {profile.profile_id}",
        )

    current = profile.read_current_room(read_memory)
    if not current.ok or current.room is None:
        return PollResult(PollStatus.ReadFailure, current.error)
    rid = current.room
    pilot = next((pilot for pilot in profile.pilot_items if pilot.room == rid), None)
    item = profile.observe_pilot_item(pilot, read_memory) if pilot is not None else None
    if item is not None and item.state == PilotItemState.ReadFailure:
        return PollResult(PollStatus.ReadFailure, f"item read failed: {item.reason}")
    current_again = profile.read_current_room(read_memory)
    if not current_again.ok or current_again.room is None:
        return PollResult(
            PollStatus.ReadFailure, f"room recheck failed: {current_again.error}"
        )
    if current_again.room != rid:
        # A door transition between reads must not combine two room states.
        return PollResult(PollStatus.Retry, "room changed during read; retry")

    tracker.mark_current(rid)
    details = []
    if item is not None and item.state in (
        PilotItemState.Available,
        PilotItemState.Taken,
        PilotItemState.AvailabilityUnknown,
    ):
        assert pilot is not None
        details.append(f"Room data: {Path(pilot.source_rdt).name}")
    if item is not None and item.state == PilotItemState.Available:
        tracker.update_room_items(rid, 1, 0, False, True, True)
        assert pilot is not None
        details.append(
            f"{pilot.label}: available (validated active item object)"
        )
    elif item is not None and item.state == PilotItemState.Taken:
        tracker.update_room_items(rid, 1, 1, False, False, True)
        assert pilot is not None
        details.append(f"{pilot.label}: taken (pickup flag cleared)")
    elif item is not None and item.state == PilotItemState.AvailabilityUnknown:
        tracker.update_room_items(rid, 1, 0, False, False, True)
        assert pilot is not None
        details.append(
            f"{pilot.label}: availability unknown ({item.reason})"
        )
    else:
        tracker.update_room_items(rid, 0, 0, False, False, True)
        if item is not None and item.state == PilotItemState.UnsupportedState:
            details.append(f"Items for this room state: unknown ({item.reason})")
    rec = tracker.room_state(rid)
    details.append("Visited scope: this tracker session")
    return PollResult(
        PollStatus.Display,
        render(rid, rec, profile.profile_id) + "\n" + "\n".join(details),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--profile",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "profiles/re1_directors_cut_slus00551.json",
    )
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=2345)
    ap.add_argument("--hz", type=float, default=10.0)
    ap.add_argument("--once", action="store_true", help="read one snapshot and exit")
    args = ap.parse_args()

    profile = Re1Profile.load(args.profile)
    if not profile.has_room_addresses():
        print(
            f"profile {profile.profile_id} has no validated room addresses; refusing to guess"
        )
        print("Run room A vs B diffs first, then fill profiles/*.json with evidence.")
        return 2
    if profile.runtime_signature is None:
        print(
            f"profile {profile.profile_id} has no runtime identity check; refusing live reads"
        )
        return 2

    tracker = Tracker()
    gdb = DuckStationGdb(args.host, args.port)
    err = gdb.connect()
    if err:
        print(err, file=sys.stderr)
        return 1
    err = gdb.resume()
    if err:
        gdb.close()
        print(f"resume failed: {err}", file=sys.stderr)
        return 1
    try:
        period = 1.0 / max(1.0, min(args.hz, 30.0))
        last_wait_reason = ""
        while True:
            result = poll_once(profile, tracker, gdb.read_memory)
            if result.status == PollStatus.WrongGame:
                if args.once:
                    print(result.text, file=sys.stderr)
                    return 2
                if result.text != last_wait_reason:
                    print("\x1b[2J\x1b[H" + result.text + "; waiting for game")
                    last_wait_reason = result.text
                time.sleep(period)
                continue
            if result.status == PollStatus.Retry:
                if args.once:
                    print(result.text, file=sys.stderr)
                    return 1
                time.sleep(period)
                continue
            if result.status == PollStatus.ReadFailure:
                if args.once:
                    print(result.text, file=sys.stderr)
                    return 1
                if result.text != last_wait_reason:
                    print("\x1b[2J\x1b[H" + result.text, file=sys.stderr)
                    last_wait_reason = result.text
                time.sleep(period)
                continue
            last_wait_reason = ""
            print(("" if args.once else "\x1b[2J\x1b[H") + result.text)
            if args.once:
                return 0
            time.sleep(period)
    except KeyboardInterrupt:
        return 0
    finally:
        gdb.close()


if __name__ == "__main__":
    raise SystemExit(main())
