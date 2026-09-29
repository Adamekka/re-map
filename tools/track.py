"""Live debug loop: poll room bytes over GDB and print debug view.

Polls only the configured addresses at ~10 Hz. Unknown addresses exit
with a clear diagnostic instead of guessing.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb
from games.re1.re1_profile import MemoryResult, PilotItemState, Re1Profile
from tracker.exploration_state import Tracker
from ui.debug_view import render
from ui.map_view import MAP_PROFILE_ID, MapServer, mansion_graph, map_state

logger = logging.getLogger(__name__)


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
    ap.add_argument("--map", action="store_true", help="serve the live Mansion 1F map on localhost:8765")
    ap.add_argument(
        "--log-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "logs/tracker.log",
        help="diagnostic log path (default: logs/tracker.log in the repository)",
    )
    args = ap.parse_args()
    log_path = args.log_file.expanduser().resolve()
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Continuous polling must not grow diagnostics without a limit.
        handler = RotatingFileHandler(
            log_path, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
    except OSError as exc:
        print(f"cannot open log file {log_path}: {exc}", file=sys.stderr)
        return 2
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[handler],
        force=True,
    )
    print(f"Log file: {log_path}", flush=True)
    logger.info(
        "Tracker started: python=%s profile=%s gdb=%s:%s hz=%s map=%s once=%s",
        sys.version.split()[0],
        args.profile,
        args.host,
        args.port,
        args.hz,
        args.map,
        args.once,
    )
    if args.map and args.once:
        logger.error("The live map needs continuous tracking; omit --once")
        print("the live map needs continuous tracking; omit --once", file=sys.stderr)
        return 2

    profile = Re1Profile.load(args.profile)
    logger.info(
        "Profile loaded: id=%s revision=%s", profile.profile_id, profile.revision
    )
    if not profile.has_room_addresses():
        logger.error("Profile %s has no validated room addresses", profile.profile_id)
        print(
            f"profile {profile.profile_id} has no validated room addresses; refusing to guess"
        )
        print("Run room A vs B diffs first, then fill profiles/*.json with evidence.")
        return 2
    if profile.runtime_signature is None:
        logger.error("Profile %s has no runtime identity check", profile.profile_id)
        print(
            f"profile {profile.profile_id} has no runtime identity check; refusing live reads"
        )
        return 2
    if args.map and profile.profile_id != MAP_PROFILE_ID:
        logger.error("Map unavailable for profile %s", profile.profile_id)
        print(f"map unavailable for profile {profile.profile_id}", file=sys.stderr)
        return 2
    logger.info(
        "Expected runtime signature SHA256: %s",
        profile.runtime_signature.concatenated_sha256,
    )

    tracker = Tracker()
    gdb = DuckStationGdb(args.host, args.port)
    err = gdb.connect()
    if err:
        logger.error("GDB connection failed: %s", err)
        print(err, file=sys.stderr)
        return 1
    logger.info("GDB connected")
    err = gdb.resume()
    if err:
        gdb.close()
        logger.error("GDB resume failed: %s", err)
        print(f"resume failed: {err}", file=sys.stderr)
        return 1
    logger.info("GDB resume sent")
    map_server = None
    map_thread = None
    item_labels = {item.room: item.label for item in profile.pilot_items}
    try:
        if args.map:
            try:
                map_server = MapServer(8765, mansion_graph())
            except (OSError, ValueError) as exc:
                logger.exception("Map startup failed")
                print(f"map unavailable: {exc}", file=sys.stderr)
                return 1

            def serve_map() -> None:
                try:
                    map_server.serve_forever()
                except Exception:
                    logger.exception("Map server thread failed")
                    raise

            map_thread = Thread(target=serve_map, daemon=True)
            try:
                map_thread.start()
            except RuntimeError as exc:
                logger.exception("Map thread startup failed")
                print(f"map unavailable: {exc}", file=sys.stderr)
                return 1
            print("Room map: http://127.0.0.1:8765")
            logger.info("Map listening at http://127.0.0.1:8765")
        period = 1.0 / max(1.0, min(args.hz, 30.0))
        map_line = "\nRoom map: http://127.0.0.1:8765" if map_server is not None else ""
        map_line += f"\nLog file: {log_path}"
        last_wait_reason = ""
        last_logged_result = None
        next_log_at = 0.0
        reads: list[str] = []

        def read_for_log(address: int, length: int) -> MemoryResult:
            result = gdb.read_memory(address, length)
            if not result.ok:
                detail = f"error={result.error!r}"
            elif length >= 32:
                # Signature windows contain game code; retain hashes rather than dump it.
                detail = f"sha256={hashlib.sha256(result.data).hexdigest()}"
            else:
                detail = f"hex={result.data.hex()}"
            reads.append(
                f"{address:#010x} length={length} received={len(result.data)} {detail}"
            )
            return result

        while True:
            reads.clear()
            result = poll_once(profile, tracker, read_for_log)
            if map_server is not None:
                snapshot = (
                    map_state(tracker, item_labels)
                    if result.status == PollStatus.Display
                    else {"status": "waiting", "current": None, "rooms": []}
                )
                map_server.snapshot = json.dumps(snapshot).encode("utf-8")
            now = time.monotonic()
            # Log changes immediately and unchanged state every 30s so stalls remain visible.
            if result != last_logged_result or now >= next_log_at:
                level = (
                    logging.ERROR
                    if result.status == PollStatus.ReadFailure
                    else logging.WARNING
                    if result.status == PollStatus.WrongGame
                    else logging.INFO
                )
                logger.log(
                    level,
                    "Poll %s\n%s\nReads: %s",
                    result.status.value,
                    result.text,
                    "; ".join(reads),
                )
                if map_server is not None:
                    logger.info("Map state: %s", map_server.snapshot.decode("utf-8"))
                last_logged_result = result
                next_log_at = now + 30.0
            if result.status == PollStatus.WrongGame:
                if args.once:
                    print(result.text, file=sys.stderr)
                    return 2
                if result.text != last_wait_reason:
                    print(
                        "\x1b[2J\x1b[H" + result.text + "; waiting for game" + map_line
                    )
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
                    print("\x1b[2J\x1b[H" + result.text + map_line, file=sys.stderr)
                    last_wait_reason = result.text
                time.sleep(period)
                continue
            last_wait_reason = ""
            print(("" if args.once else "\x1b[2J\x1b[H") + result.text + map_line)
            if args.once:
                return 0
            time.sleep(period)
    except KeyboardInterrupt:
        logger.info("Tracker stopped by user")
        return 0
    finally:
        try:
            if map_server is not None:
                try:
                    if map_thread is not None and map_thread.is_alive():
                        map_server.shutdown()
                        map_thread.join(timeout=2)
                finally:
                    map_server.server_close()
        finally:
            gdb.close()
            logger.info("GDB closed")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("Tracker failed unexpectedly")
        raise
