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
from games.re1.door_state import parse_door
from games.re1.re1_profile import MemoryResult, Re1Profile
from games.re1.room_cache import (
    CachedRoomObservation,
    match_room_source,
    read_cache_context,
    refresh_cached_items,
)
from games.re1.room_items import RuntimeItemState, observe_room_items
from tracker.exploration_state import DoorDetail, ItemDetail, Tracker
from ui.debug_view import render
from ui.map_view import MAP_PROFILE_ID, MapServer, mansion_floor_plan, map_state

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
    layout, doors_layout = profile.runtime_room_layout, profile.door_state_layout
    if layout is None or doors_layout is None:
        return PollResult(
            PollStatus.ReadFailure,
            "runtime room interpretation unavailable for this profile",
        )
    source_query = match_room_source(layout, profile.room_sources, rid, read_memory)
    if not source_query.ok:
        return PollResult(
            PollStatus.Retry if source_query.retry else PollStatus.ReadFailure,
            source_query.error,
        )
    observation = observe_room_items(layout, rid, read_memory)
    if not observation.ok:
        return PollResult(
            PollStatus.Retry if observation.retry else PollStatus.ReadFailure,
            observation.error,
        )
    door_values = []
    for address, width in (
        (doors_layout.unlock_flags_address, doors_layout.unlock_flags_width),
        (doors_layout.player_state_address, 1),
        (doors_layout.special_flag_address, 1),
        (layout.acquisition_flags_address, layout.acquisition_flags_width),
    ):
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            return PollResult(
                PollStatus.ReadFailure,
                f"state read failed: {result.error or 'short read'}",
            )
        door_values.append(result.data)
    flags = door_values[3]

    def remaining(gid: int) -> bool:
        index = 4 * (gid // 32) + 3 - (gid % 32) // 8
        assert 0 <= index < len(flags), (
            "validated GlobalId must fit the acquisition block"
        )
        return bool(flags[index] & (0x80 >> (gid % 8)))

    if any(
        item.state != RuntimeItemState.Unavailable
        and (item.state == RuntimeItemState.Available) != remaining(item.global_id)
        for item in observation.items
    ):
        return PollResult(PollStatus.Retry, "pickup changed during room read")
    context, error = read_cache_context(source_query.sources, read_memory)
    if error:
        return PollResult(PollStatus.ReadFailure, error)
    represented = {
        item.global_id
        for item in observation.items
        if item.state != RuntimeItemState.Unavailable
    }
    absent_gids = {
        gid
        for source in source_query.sources
        for gid in source.item_global_ids
        if gid not in represented
    }
    current_cached = CachedRoomObservation(
        observation,
        source_query.sources,
        context,
        tuple((gid, remaining(gid)) for gid in sorted(absent_gids)),
    )
    refreshed = {rid: observation}
    past_contexts = {}
    for room, cached in profile.room_observations.items():
        if room == rid or str(room) not in tracker.rooms:
            continue
        past_context, error = read_cache_context(cached.sources, read_memory)
        if error:
            return PollResult(PollStatus.ReadFailure, error)
        past_contexts[room] = past_context
        refreshed[room] = refresh_cached_items(cached, past_context, flags)
    decoded_doors = []
    raw_sources = dict(profile.door_observations)
    raw_sources[rid] = observation.active_doors
    for source, raw_doors in raw_sources.items():
        if source != rid:
            if source not in past_contexts:
                # A reused profile may retain observations from another tracker session.
                continue
            cached = profile.room_observations[source]
            if (
                not cached.sources
                or not all(script.door_cache_complete for script in cached.sources)
                or past_contexts[source] != cached.context
            ):
                # Item coverage and door definitions have separate script audits.
                # A later interaction can replace a door without changing items.
                continue
        for slot, raw in raw_doors:
            try:
                door = parse_door(
                    slot,
                    raw,
                    source,
                    door_values[0],
                    door_values[1][0],
                    door_values[2][0],
                )
            except ValueError as exc:
                return PollResult(
                    PollStatus.ReadFailure, f"door interpretation failed: {exc}"
                )
            label = door.reason
            key_name = dict(layout.item_labels).get(door.lock_type)
            if (
                door.state.value == "locked"
                and door.reason == "Requires a key"
                and key_name
            ):
                label = "Locked · " + key_name
            decoded_doors.append(
                DoorDetail(source, door.target, door.state.name, label)
            )
    camera = (
        read_memory(profile.camera_address, 1)
        if profile.camera_address is not None
        else None
    )
    if camera is None or not camera.ok or len(camera.data) != 1:
        return PollResult(PollStatus.ReadFailure, "camera read failed")
    current_again = profile.read_current_room(read_memory)
    if not current_again.ok or current_again.room is None:
        return PollResult(
            PollStatus.ReadFailure, f"room recheck failed: {current_again.error}"
        )
    if current_again.room != rid:
        # Publish nothing until every memory read belongs to the same room.
        return PollResult(PollStatus.Retry, "room changed during read; retry")
    tracker.mark_current(rid)
    # Only source-bound Mansion rooms have a confirmed ordinary floor-plan region.
    region = (
        f"mansion1f:{rid.room:02X}" if rid.stage == 0 and source_query.sources else ""
    )
    # The original map separates secret spaces inside one RDT room by camera.
    if region and rid.room == 7 and 3 <= camera.data[0] <= 6:
        region = "mansion1f:1D"
    elif region and rid.room == 15 and camera.data[0] in (3, 4):
        region = "mansion1f:1E"
    elif region and rid.room == 16 and camera.data[0] == 0:
        region = ""
    tracker.current_region = region
    if region:
        tracker.region_visits[region] = str(rid)
    profile.room_observations[rid] = current_cached
    profile.door_observations[rid] = observation.active_doors
    for room, result in refreshed.items():
        normal_items = tuple(
            item for item in result.items if item.state != RuntimeItemState.Unavailable
        )
        tracker.update_room_items(
            room,
            len(normal_items),
            sum(item.state == RuntimeItemState.Taken for item in normal_items),
            result.list_complete,
            any(item.state == RuntimeItemState.Available for item in normal_items),
            not result.list_complete,
        )
        record = tracker.room_state(room)
        record.items = tuple(
            ItemDetail(item.label or "Collectible item", item.state.value, item.amount)
            for item in normal_items
        )
        record.reason = (
            "" if result.list_complete else "Re-enter this room to refresh its items."
        )
    tracker.doors = tuple(decoded_doors)
    record = tracker.room_state(rid)
    details = [f"{item.label}: {item.state}" for item in record.items]
    details.extend(
        f"Door to {door.target}: {door.label}"
        for door in tracker.doors
        if door.source == rid
    )
    details.append("Visited scope: this tracker session")
    return PollResult(
        PollStatus.Display,
        render(rid, record, profile.profile_id) + "\n" + "\n".join(details),
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
    ap.add_argument(
        "--map",
        action="store_true",
        help="serve the live Mansion 1F map on localhost:8765",
    )
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
    if profile.runtime_room_layout is None or profile.door_state_layout is None:
        print(
            f"profile {profile.profile_id} has no runtime room/door layout",
            file=sys.stderr,
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
        if not args.map:
            return 1
    else:
        logger.info("GDB connected")
        err = gdb.resume()
        if err:
            gdb.close()
            logger.error("GDB resume failed: %s", err)
            print(f"resume failed: {err}", file=sys.stderr)
            if not args.map:
                return 1
        else:
            logger.info("GDB resume sent")
    map_server = None
    map_thread = None
    try:
        if args.map:
            try:
                map_server = MapServer(8765, mansion_floor_plan())
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
        next_reconnect_at = time.monotonic() + 1.0
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
            if not gdb.connected and time.monotonic() >= next_reconnect_at:
                # A closed emulator should not require restarting the live tracker.
                error = gdb.connect()
                if not error:
                    error = gdb.resume()
                    if error:
                        gdb.close()
                    else:
                        logger.info("GDB reconnected and resumed")
                if error:
                    logger.warning("GDB reconnect failed: %s", error)
                next_reconnect_at = time.monotonic() + 1.0
            reads.clear()
            result = poll_once(profile, tracker, read_for_log)
            if map_server is not None:
                snapshot = (
                    map_state(tracker)
                    if result.status == PollStatus.Display
                    else {
                        "status": "waiting",
                        "current": None,
                        "rooms": [],
                        "error": (
                            "Changing rooms..."
                            if result.status == PollStatus.Retry
                            else "Waiting for Resident Evil Director's Cut."
                            if result.status == PollStatus.WrongGame
                            else "Game connection interrupted. Check DuckStation and its GDB server."
                        ),
                    }
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
