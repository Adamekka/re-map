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
from dataclasses import replace
from logging.handlers import RotatingFileHandler
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import DuckStationGdb
from games.game_profile import RoomId
from games.re1.acquisition_state import AcquisitionFlag
from games.re1.door_state import parse_door, stage_remap_flag
from games.re1.event_state import read_event_snapshot
from games.re1.map_layout import MapLocation, MapUnavailable, decode_player_heading
from games.re1.re1_profile import MemoryResult, Re1Profile
from games.re1.room_cache import (
    CachedRoomObservation,
    match_room_source,
    read_cache_context,
)
from games.re1.room_items import RuntimeItemState, observe_room_items
from games.re1.tracking_engine import (
    reconstruct_visited_room,
    refresh_visited_room,
    validate_current_room,
)
from games.re1.tracking_rules import read_rule_snapshot
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import DoorDetail, ItemDetail, Tracker
from tracker.polling import PollResult, PollStatus
from tracker.visit_history import HistoryError, HistoryIdentity, VisitHistory
from ui.debug_view import render
from ui.map_view import MAP_PROFILE_ID, MapServer, map_state

logger = logging.getLogger(__name__)


def poll_once(
    profile: Re1Profile | Re2Profile,
    tracker: Tracker,
    read_memory: Callable[[int, int], MemoryResult],
) -> PollResult:
    if isinstance(profile, Re2Profile):
        return poll_re2(profile, tracker, read_memory)
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

    lifecycle = None
    if profile.lifecycle_address is not None:
        # Title, demo, and other non-gameplay states read 0x00 here on the
        # pinned revision (RE1-LIFECYCLE-002). Suppressing only that value
        # keeps the gate fail-open for untested gameplay phases.
        lifecycle = read_memory(profile.lifecycle_address, 1)
        if not lifecycle.ok or len(lifecycle.data) != 1:
            return PollResult(
                PollStatus.ReadFailure,
                f"lifecycle read failed: {lifecycle.error or 'short read'}",
            )
        if lifecycle.data[0] == 0x00:
            return PollResult(
                PollStatus.NonGameplay,
                "Title or demo playback; visits not recorded",
            )

    current = profile.read_current_room(read_memory)
    if not current.ok or current.room is None:
        return PollResult(PollStatus.ReadFailure, current.error)
    rid = current.room
    layout, doors_layout = profile.runtime_room_layout, profile.door_state_layout
    rule_layout = profile.tracking_rule_layout
    event_layout = profile.event_layout
    if (
        layout is None
        or doors_layout is None
        or rule_layout is None
        or event_layout is None
        or profile.player_facing_address is None
    ):
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
    loaded_pointer = read_memory(layout.loaded_rdt_pointer_address, 4)
    if not loaded_pointer.ok or len(loaded_pointer.data) != 4:
        return PollResult(
            PollStatus.ReadFailure,
            f"event room pointer read failed: {loaded_pointer.error or 'short read'}",
        )
    base = int.from_bytes(loaded_pointer.data, "little")
    registry = dict(observation.memory_markers)[layout.aot_base]
    event_snapshot = read_event_snapshot(
        event_layout,
        source_query.sources,
        profile.room_programs,
        base,
        registry,
        read_memory,
    )
    if not event_snapshot.ok:
        return PollResult(PollStatus.ReadFailure, event_snapshot.error)
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
    # Door targets remap stage 0/1 to 5/6 when this story flag is set; see
    # door_state.decode_door_target and the pinned transition at 0x8002A6E0.
    remap_address, remap_mask = stage_remap_flag(rule_layout)
    remap_result = read_memory(remap_address, 1)
    if not remap_result.ok or len(remap_result.data) != 1:
        return PollResult(
            PollStatus.ReadFailure,
            f"state read failed: {remap_result.error or 'short read'}",
        )
    stage_remap = bool(remap_result.data[0] & remap_mask)

    context, error = read_cache_context(source_query.sources, read_memory)
    if error:
        return PollResult(PollStatus.ReadFailure, error)
    visited_rooms = {
        RoomId(int(key.split("-")[0]), int(key.split("-")[1], 16))
        for key in tracker.rooms
        if key != str(rid)
    }
    # The loader can select another file after a story or character change.
    # Capture every possible source for visited rooms before selecting its rules.
    visited_sources = {
        source.source_rdt
        for source in profile.room_sources
        if source.room in visited_rooms
    }
    visited_sources.update(source.source_rdt for source in source_query.sources)
    programs = tuple(profile.room_programs[name] for name in sorted(visited_sources))
    rule_snapshot = read_rule_snapshot(rule_layout, programs, read_memory)
    if rule_snapshot.error:
        return PollResult(PollStatus.ReadFailure, rule_snapshot.error)
    rule_values = dict(rule_snapshot.values)
    # Scripted candidates already carry acquisition state before access is
    # resolved. A load between reads must not publish a stale Taken candidate.
    if any(
        (item.state == RuntimeItemState.Taken)
        != layout.acquisition.collected(
            layout.acquisition.flag(item.item_type, item.global_id), flags, rule_values
        )
        for item in tuple(
            item
            for item in observation.items
            if item.state != RuntimeItemState.Unavailable
        )
        + tuple(item for item, _, _ in observation.scripted_collectibles)
    ):
        return PollResult(PollStatus.Retry, "pickup changed during room read")
    current_evaluation = validate_current_room(
        profile, observation, source_query.sources, rule_snapshot, flags
    )
    observation = current_evaluation.items
    if any(
        event.reason for event in event_snapshot.events + event_snapshot.interactions
    ):
        # An active unbound script can change the registry beyond this room's
        # inspected program. Keep observed pickups but do not authorize clearance.
        observation = replace(
            observation,
            list_complete=False,
            coverage_reason="Room events are not yet identified.",
        )
        current_evaluation = replace(
            current_evaluation,
            doors_complete=False,
            door_reason="Door event conditions are unresolved.",
        )
    represented = {
        layout.acquisition.flag(item.item_type, item.global_id)
        for item in observation.items
        if item.state != RuntimeItemState.Unavailable
    }
    absent_flags = set()
    for source in source_query.sources:
        program = profile.room_programs[source.source_rdt]
        commands = (
            program.event_effects
            + program.event_commands
            + tuple(
                command
                for procedure in program.procedures
                + program.main_procedures
                + tuple(p for block in program.event_blocks for p in block)
                for command in procedure.commands
            )
        )
        for command in commands:
            if command.kind == "item" and 1 <= command.args[1] <= 0x53:
                flag = layout.acquisition.flag(command.args[1], command.args[3])
                activation = AcquisitionFlag(
                    *rule_layout.flag(7, command.args[3]), False
                )
                if activation != flag:
                    # A separately owned pickup can become active on reentry
                    # when its ordinary GlobalId bit changes. Ownership alone
                    # cannot authorize reuse of an observed absence.
                    absent_flags.add(activation)
                if flag not in represented:
                    # Absence must follow the actual acquisition bit. Different
                    # pickup kinds can share a GlobalId but use different banks.
                    absent_flags.add(flag)
    current_cached = CachedRoomObservation(
        observation,
        source_query.sources,
        context,
        tuple(
            (flag, layout.acquisition.collected(flag, flags, rule_values))
            for flag in sorted(absent_flags)
        ),
        tuple(
            rule_values[address] & mask
            for address, mask in rule_layout.source_selection_masks
        ),
        current_evaluation.doors_complete,
    )
    refreshed = {rid: observation}
    door_coverage = {
        rid: (current_evaluation.doors_complete, current_evaluation.door_reason)
    }
    past_contexts = {}
    raw_sources = {rid: observation.active_doors}
    disabled_sources = {rid: observation.disabled_doors}
    for room in sorted(visited_rooms, key=str):
        cached = profile.room_observations.get(room)
        if cached is None:
            # Persistence stores visits only. Reconstruct prior rooms from fresh
            # flags instead of inventing or restoring a live RAM observation.
            evaluated = reconstruct_visited_room(profile, room, rule_snapshot, flags)
        else:
            past_context, error = read_cache_context(cached.sources, read_memory)
            if error:
                return PollResult(PollStatus.ReadFailure, error)
            past_contexts[room] = past_context
            evaluated = refresh_visited_room(
                profile, cached, past_context, rule_snapshot, flags
            )
        refreshed[room] = evaluated.items
        raw_sources[room] = evaluated.doors
        disabled_sources[room] = evaluated.disabled_doors
        door_coverage[room] = evaluated.doors_complete, evaluated.door_reason
    decoded_doors = []
    for source, raw_doors in raw_sources.items():
        for slot, raw in raw_doors + disabled_sources[source]:
            try:
                door = parse_door(
                    slot,
                    raw,
                    source,
                    door_values[0],
                    door_values[1][0],
                    door_values[2][0],
                    stage_remap,
                )
            except ValueError as exc:
                return PollResult(
                    PollStatus.ReadFailure, f"door interpretation failed: {exc}"
                )
            disabled = (slot, raw) in disabled_sources[source]
            label = "Passage is unavailable" if disabled else door.reason
            key_name = dict(layout.item_labels).get(door.lock_type)
            if (
                not disabled
                and door.state.value == "locked"
                and door.reason == "Requires a key"
                and key_name
            ):
                label = "Locked · " + key_name
            decoded_doors.append(
                DoorDetail(
                    source,
                    door.target,
                    "BLOCKED" if disabled else door.state.name,
                    label,
                    key_label=key_name if door.lock_id & 0x80 and key_name else "",
                )
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
    # Rules, cached contexts and acquisition/door flags must refer to one state.
    # A save load can change all of them without changing Main/Sub.
    rule_recheck = read_rule_snapshot(rule_layout, programs, read_memory)
    if rule_recheck.error:
        return PollResult(PollStatus.ReadFailure, rule_recheck.error)
    if rule_recheck.values != rule_snapshot.values:
        return PollResult(PollStatus.Retry, "room rules changed during read; retry")
    for sources, expected in [(source_query.sources, context)] + [
        (profile.room_observations[room].sources, expected)
        for room, expected in past_contexts.items()
    ]:
        actual, error = read_cache_context(sources, read_memory)
        if error:
            return PollResult(PollStatus.ReadFailure, error)
        if actual != expected:
            return PollResult(
                PollStatus.Retry, "room conditions changed during read; retry"
            )
    for (address, width), expected in zip(
        (
            (doors_layout.unlock_flags_address, doors_layout.unlock_flags_width),
            (doors_layout.player_state_address, 1),
            (doors_layout.special_flag_address, 1),
            (layout.acquisition_flags_address, layout.acquisition_flags_width),
            (remap_address, 1),
        ),
        (*door_values, remap_result.data),
        strict=True,
    ):
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            return PollResult(
                PollStatus.ReadFailure,
                f"state recheck failed: {result.error or 'short read'}",
            )
        if result.data != expected:
            return PollResult(
                PollStatus.Retry, "item or door state changed during read; retry"
            )
    pool_again = read_memory(
        event_layout.pool_address, event_layout.capacity * event_layout.stride
    )
    if (
        not pool_again.ok
        or len(pool_again.data) != event_layout.capacity * event_layout.stride
    ):
        return PollResult(
            PollStatus.ReadFailure, f"event recheck: {pool_again.error or 'short read'}"
        )
    if event_layout.positions(pool_again.data) != event_snapshot.positions:
        return PollResult(PollStatus.Retry, "event changed during room read; retry")
    for address, expected in (
        source_query.memory_markers
        + observation.memory_markers
        + event_snapshot.memory_markers
        + ((layout.loaded_rdt_pointer_address, loaded_pointer.data),)
    ):
        result = read_memory(address, len(expected))
        if not result.ok or len(result.data) != len(expected):
            return PollResult(
                PollStatus.ReadFailure,
                f"room snapshot recheck failed: {result.error or 'short read'}",
            )
        # Only pending-item bits govern this observation. Other control bits
        # can change without invalidating the registered collectible state.
        unchanged = (
            (int.from_bytes(result.data, "little") ^ int.from_bytes(expected, "little"))
            & layout.pending_item_mask
            == 0
            if address == layout.main_flags_address
            else result.data == expected
        )
        if not unchanged:
            return PollResult(
                PollStatus.Retry, "room snapshot changed during read; retry"
            )
    # Heading may change normally during a poll. Take its latest value once,
    # then bracket it with the final camera/room/lifecycle checks instead of
    # requiring a stationary character to pass a heading equality recheck.
    facing = read_memory(profile.player_facing_address, 2)
    if not facing.ok or len(facing.data) != 2:
        return PollResult(PollStatus.ReadFailure, "player facing read failed")
    camera_again = read_memory(profile.camera_address, 1)
    if not camera_again.ok or len(camera_again.data) != 1:
        return PollResult(PollStatus.ReadFailure, "camera recheck failed")
    if camera_again.data != camera.data:
        # Cameras can cross map-region boundaries without changing Main/Sub.
        return PollResult(PollStatus.Retry, "camera changed during read; retry")
    final_room = profile.read_current_room(read_memory)
    if not final_room.ok or final_room.room is None:
        return PollResult(
            PollStatus.ReadFailure, f"room recheck failed: {final_room.error}"
        )
    if final_room.room != rid:
        return PollResult(PollStatus.Retry, "room changed during final read; retry")
    if lifecycle is not None and profile.lifecycle_address is not None:
        # Recheck after the final room/source reads so a late switch to demo
        # playback cannot publish a visit from this poll (RE1-LIFECYCLE-002).
        result = read_memory(profile.lifecycle_address, 1)
        if not result.ok or len(result.data) != 1:
            return PollResult(
                PollStatus.ReadFailure,
                f"lifecycle recheck failed: {result.error or 'short read'}",
            )
        if result.data != lifecycle.data:
            return PollResult(PollStatus.Retry, "lifecycle changed during read; retry")
    tracker.player_heading = decode_player_heading(facing.data)
    tracker.mark_current(rid)
    selection = (
        profile.map_layout.select(rid, camera.data[0])
        if profile.map_layout is not None and source_query.sources
        else MapUnavailable("This room has no verified map binding.")
    )
    if isinstance(selection, MapLocation):
        tracker.current_region = f"{selection.area}:{selection.region}"
        tracker.map_error = ""
        if selection.outlined:
            tracker.region_visits[tracker.current_region] = str(rid)
    else:
        tracker.current_region = ""
        tracker.map_error = selection.reason
    profile.room_observations[rid] = current_cached
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
        record.reason = "" if result.list_complete else result.coverage_reason
        record.doors_complete, record.door_reason = door_coverage[room]
    tracker.doors = tuple(decoded_doors)
    record = tracker.room_state(rid)
    details = [f"{item.label}: {item.state}" for item in record.items]
    details.extend(
        f"Door to {door.target}: {door.label}"
        for door in tracker.doors
        if door.source == rid
    )
    details.append("Visited scope: this playthrough")
    if record.door_reason:
        details.append(record.door_reason)
    details.append(
        f"Active events: {len(event_snapshot.events)}; registered event interactions: {len(event_snapshot.interactions)}"
    )
    for event in event_snapshot.events:
        details.append(
            f"Event slot {event.slot}: {event.phase}; owners {event.owners}; potential item slots {event.item_slots}; door slots {event.door_slots}"
            + (f"; {event.reason}" if event.reason else "")
        )
    for interaction in event_snapshot.interactions:
        details.append(
            f"Interaction {interaction.slot}: starts event {interaction.entry} in slot {interaction.requested_slot}; potential item slots {interaction.item_slots}; door slots {interaction.door_slots}"
            + (f"; {interaction.reason}" if interaction.reason else "")
        )
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
        help="serve the live multi-area map on localhost:8765",
    )
    ap.add_argument(
        "--log-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "logs/tracker.log",
        help="diagnostic log path (default: logs/tracker.log in the repository)",
    )
    ap.add_argument(
        "--history-file",
        type=Path,
        default=argparse.SUPPRESS,
        help="exploration history to resume (default: a separate file for each game)",
    )
    ap.add_argument(
        "--new-playthrough",
        action="store_true",
        help="start a fresh exploration history for the selected history file",
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

    profile_id = json.loads(args.profile.read_text())["profile_id"]
    is_re2 = profile_id == "re2_leon_a_slus00421"
    profile = Re2Profile.load(args.profile) if is_re2 else Re1Profile.load(args.profile)
    # Preserve existing Jill histories while giving Leon his own default file.
    # Explicit --history-file selections still belong to the caller.
    history_path = (
        args.history_file
        if hasattr(args, "history_file")
        else Path(__file__).resolve().parents[1]
        / ".local"
        / ("re2-leon-a.json" if is_re2 else "visit-history.json")
    )
    logger.info(
        "Profile loaded: id=%s revision=%s", profile.profile_id, profile.revision
    )
    if not is_re2 and not profile.has_room_addresses():
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
    if not is_re2 and (
        profile.runtime_room_layout is None or profile.door_state_layout is None
    ):
        print(
            f"profile {profile.profile_id} has no runtime room/door layout",
            file=sys.stderr,
        )
        return 2
    if args.map and profile.profile_id not in (MAP_PROFILE_ID, "re2_leon_a_slus00421"):
        logger.error("Map unavailable for profile %s", profile.profile_id)
        print(f"map unavailable for profile {profile.profile_id}", file=sys.stderr)
        return 2
    logger.info(
        "Expected runtime signature SHA256: %s",
        profile.runtime_signature.concatenated_sha256,
    )

    assert profile.map_layout is not None, "persistent visits require map bindings"
    region_rooms = {
        f"{plan['id']}:{room['id']}": set(room["room_ids"])
        for plan in profile.map_layout.document["areas"]
        for room in plan["rooms"]
    }
    try:
        history = VisitHistory(
            history_path.expanduser().resolve(),
            HistoryIdentity(
                profile.profile_id,
                profile.runtime_signature.concatenated_sha256,
                # Scenario identity keeps supported runs separate within a revision.
                "leon-a" if is_re2 else "jill",
            ),
            region_rooms,
            args.new_playthrough,
        )
    except HistoryError as exc:
        logger.error("%s", exc)
        print(str(exc), file=sys.stderr)
        return 1
    tracker = history.restore()
    logger.info(
        "Exploration history: file=%s playthrough=%s rooms=%s regions=%s",
        history.path,
        history.playthrough_id,
        len(tracker.rooms),
        len(tracker.region_visits),
    )
    gdb = DuckStationGdb(args.host, args.port)
    err = gdb.connect()
    if err:
        logger.error("GDB connection failed: %s", err)
        print(err, file=sys.stderr)
        if not args.map:
            history.close()
            return 1
    else:
        logger.info("GDB connected")
        err = gdb.resume()
        if err:
            gdb.close()
            logger.error("GDB resume failed: %s", err)
            print(f"resume failed: {err}", file=sys.stderr)
            if not args.map:
                history.close()
                return 1
        else:
            logger.info("GDB resume sent")
    map_server = None
    map_thread = None
    try:
        if args.map:
            try:
                assert profile.map_layout is not None, (
                    "runtime profile requires floor plans"
                )
                map_server = MapServer(8765, profile.map_layout.document)
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
            if result.status == PollStatus.Display:
                try:
                    history.save(tracker)
                except HistoryError as exc:
                    logger.error("%s", exc)
                    print(str(exc), file=sys.stderr)
                    return 1
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
                            else "Title or demo playback. Load or start gameplay to track."
                            if result.status == PollStatus.NonGameplay
                            else "Waiting for Resident Evil 2, Leon A."
                            if is_re2 and result.status == PollStatus.WrongGame
                            else "Waiting for Resident Evil Director's Cut, Jill."
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
            if result.status == PollStatus.NonGameplay:
                if args.once:
                    print(result.text, file=sys.stderr)
                    return 1
                if result.text != last_wait_reason:
                    print("\x1b[2J\x1b[H" + result.text + map_line)
                    last_wait_reason = result.text
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
            history.close()
            logger.info("GDB closed")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        logger.exception("Tracker failed unexpectedly")
        raise
