"""Record observed RE1 events and item/door changes in an external JSONL log.

Connecting resumes DuckStation. Changed state is briefly paused for a coherent
capture, then resumed. Polling cannot establish a complete execution history.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from emulator.duckstation_gdb import (
    DebugFailure,
    DuckStationGdb,
    NoStop,
    SignalStop,
    WriteWatchStop,
)
from games.re1.event_capture import (
    CaptureFailure,
    EventCapture,
    observed_changes,
    read_event_capture,
    read_event_watch,
)
from games.re1.event_state import EventInitializer
from games.re1.re1_profile import Re1Profile


def capture_paused(
    gdb: DuckStationGdb, profile: Re1Profile
) -> EventCapture | CaptureFailure:
    try:
        error = gdb.interrupt()
        captured = (
            CaptureFailure("pause-failed", error)
            if error
            else read_event_capture(profile, gdb.read_memory)
        )
    finally:
        # A capture/read/log failure must not strand the isolated game paused.
        # A disconnected client cannot resume; the pinned server cleans up.
        # Keep the original read failure or interruption instead of masking it.
        if gdb.connected:
            error = gdb.resume()
            if error:
                raise ConnectionError(f"Could not resume DuckStation: {error}")
    return captured


def capture_breakpoint(
    gdb: DuckStationGdb,
    profile: Re1Profile,
    initializer: EventInitializer,
    stop: WriteWatchStop,
) -> tuple[EventCapture | CaptureFailure, dict]:
    layout = profile.event_layout
    assert layout is not None, "validated breakpoint configuration"
    trigger = {"kind": "activity-write", "signal": stop.signal, "steps": 0}
    try:
        # Accesses can use KSEG0 or KSEG1; both name the same PS1 physical byte.
        addresses = {
            (layout.pool_address + slot * layout.stride + layout.active_offset)
            & 0x1FFFFFFF: slot
            for slot in range(layout.capacity)
        }
        if stop.signal != 5 or stop.address & 0x1FFFFFFF not in addresses:
            raise ConnectionError(
                "Stop does not match an owned event activity watchpoint."
            )
        slot = addresses[stop.address & 0x1FFFFFFF]
        record_address = layout.pool_address + slot * layout.stride
        trigger.update(slot=slot, address_ps1=f"0x{stop.address:08X}")
        identity = profile.verify_runtime(gdb.read_memory)
        if not identity.ok or not identity.value:
            raise ConnectionError(
                f"Game identity changed: {identity.error or 'wrong game'}"
            )
        pc = gdb.read_register(37)
        if not pc.ok:
            raise ConnectionError(pc.error)
        native_pc = int.from_bytes(pc.data, "little")
        trigger["native_pc_after_write"] = f"0x{native_pc:08X}"
        if native_pc == initializer.activity_write_address + 4:
            error = initializer.verify(gdb.read_memory)
            if error:
                raise ConnectionError(error)
            record = gdb.read_register(4)
            if not record.ok or int.from_bytes(record.data, "little") != record_address:
                raise ConnectionError(
                    "Initializer record register does not match the watched slot."
                )
            # Activity is stored first. Complete the pinned straight-line body
            # and its return delay slot before binding the new script pointer.
            for expected_pc in range(native_pc, initializer.commit_address + 4, 4):
                if native_pc != expected_pc:
                    raise ConnectionError(
                        "Event initializer left its supported instruction path."
                    )
                error = gdb.single_step()
                if error:
                    raise ConnectionError(error)
                trigger["steps"] += 1
                pc = gdb.read_register(37)
                if not pc.ok:
                    raise ConnectionError(pc.error)
                native_pc = int.from_bytes(pc.data, "little")
        captured = read_event_capture(profile, gdb.read_memory)
    finally:
        # Disconnect cleanup owns resume once a failed exchange closes GDB.
        if gdb.connected:
            error = gdb.resume()
            if error:
                raise ConnectionError(f"Could not resume DuckStation: {error}")
    return captured, trigger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument(
        "--out", type=Path, required=True, help="new JSONL file outside this repository"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2345)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--hz", type=float, default=20.0, help="polling rate, 1..30 Hz")
    mode.add_argument(
        "--breakpoints",
        action="store_true",
        help="capture writes to all eight event activity bytes",
    )
    parser.add_argument("--seconds", type=float, default=180.0)
    arguments = parser.parse_args()
    if not math.isfinite(arguments.hz) or not 1 <= arguments.hz <= 30:
        parser.error("--hz must be finite and between 1 and 30")
    if not math.isfinite(arguments.seconds) or arguments.seconds <= 0:
        parser.error("--seconds must be finite and greater than zero")
    if not 1 <= arguments.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    path = arguments.out.expanduser().resolve()
    if path.is_relative_to(Path(__file__).resolve().parents[1]):
        parser.error("--out must be outside the repository; captures stay out of Git")
    try:
        profile = Re1Profile.load(arguments.profile)
        if any(
            value is None
            for value in (
                profile.runtime_room_layout,
                profile.event_layout,
                profile.door_state_layout,
                profile.tracking_rule_layout,
                profile.stage_address,
                profile.room_address,
                profile.camera_address,
            )
        ):
            parser.error("profile lacks required event capture addresses")
        raw = json.loads(arguments.profile.read_text())
        if arguments.breakpoints:
            hook = raw["event_capture_initializer"]
            initializer = EventInitializer(
                *(
                    int(hook[key], 0) if isinstance(hook[key], str) else hook[key]
                    for key in ("address", "activity_write_address", "commit_address")
                ),
                hook["sha256"],
            )
        manifest_path = arguments.profile.parent / raw["room_manifest_path"]
        provenance = {
            "profile_id": profile.profile_id,
            "executable_identity": raw["executable_identity"],
            "profile_sha256": hashlib.sha256(
                arguments.profile.read_bytes()
            ).hexdigest(),
            "manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
            "gdb_host": arguments.host,
            "gdb_port": arguments.port,
            "capture_mode": "activity-breakpoints" if arguments.breakpoints else "poll",
            **(
                {"initializer": hook}
                if arguments.breakpoints
                else {"requested_hz": arguments.hz}
            ),
            "requested_seconds": arguments.seconds,
            "sampling_limit": (
                "CPU writes at watched byte addresses trigger capture. Wide overlapping writes and savestate restores can bypass watches. No complete execution or load history."
                if arguments.breakpoints
                else "Events between polls can be missed. Changes are observations, not execution or load history."
            ),
            "address_space": "PS1 virtual; multibyte values are little-endian",
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        output = path.open("x", encoding="utf-8")
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))
    session = str(uuid4())
    started = time.monotonic()
    gdb = DuckStationGdb(arguments.host, arguments.port)
    sequence = 0
    samples = 0
    captures = 0
    breakpoint_hits = 0
    owned_watches = []
    last_watch = None
    previous: EventCapture | None = None
    last_failure: CaptureFailure | None = None
    last_heartbeat = started
    exit_code, ended = 0, "duration"
    with output:

        def write(kind: str, data: dict) -> None:
            nonlocal sequence
            output.write(
                json.dumps(
                    {
                        "schema": 1,
                        "session": session,
                        "sequence": sequence,
                        "time_utc": datetime.now(timezone.utc).isoformat(),
                        "elapsed_seconds": time.monotonic() - started,
                        "kind": kind,
                        **data,
                    },
                    separators=(",", ":"),
                )
                + "\n"
            )
            output.flush()
            sequence += 1

        def record_capture(
            captured: EventCapture, pause_seconds: float, trigger: dict
        ) -> None:
            nonlocal captures, last_watch, previous, last_failure
            # Repeated writes can restart a slot without changing its snapshot.
            # Preserve those hits; discard identical captures from torn polls.
            if captured != previous or trigger["kind"] == "activity-write":
                write(
                    "snapshot",
                    {
                        "comparison": "baseline" if previous is None else "continuous",
                        "changes": []
                        if previous is None
                        else observed_changes(previous, captured),
                        "pause_seconds": pause_seconds,
                        "trigger": trigger,
                        **captured.record(),
                    },
                )
                captures += 1
                print(
                    f"Snapshot {captures}: room {captured.room}, active events {len(captured.events.events)}",
                    flush=True,
                )
            last_watch, previous, last_failure = captured.watch, captured, None

        try:
            write("session", provenance)
            error = gdb.connect()
            if error:
                raise ConnectionError(error)
            if arguments.breakpoints:
                pause_start = time.monotonic()
                error = gdb.interrupt()
                if error:
                    raise ConnectionError(error)
                identity = profile.verify_runtime(gdb.read_memory)
                if not identity.ok or not identity.value:
                    raise ConnectionError(
                        f"Game identity: {identity.error or 'wrong game'}"
                    )
                error = initializer.verify(gdb.read_memory)
                if error:
                    raise ConnectionError(error)
                layout = profile.event_layout
                assert layout is not None, "validated event layout"
                for slot in range(layout.capacity):
                    address = (
                        layout.pool_address
                        + slot * layout.stride
                        + layout.active_offset
                    )
                    # Include an in-flight install in cleanup if its ACK is lost.
                    owned_watches.append(address)
                    error = gdb.change_write_watchpoint("insert", address, 1)
                    if error:
                        raise ConnectionError(
                            f"Could not install event watchpoint: {error}"
                        )
                baseline = read_event_capture(profile, gdb.read_memory)
                if isinstance(baseline, EventCapture):
                    record_capture(
                        baseline, time.monotonic() - pause_start, {"kind": "baseline"}
                    )
                else:
                    write("gap", {"status": baseline.status, "error": baseline.error})
            error = gdb.resume()
            if error:
                raise ConnectionError(error)
            print(f"Capture log: {path}", flush=True)
            while time.monotonic() - started < arguments.seconds:
                sampled_at = time.monotonic()
                if arguments.breakpoints:
                    if sampled_at - last_heartbeat >= 30:
                        write(
                            "heartbeat",
                            {
                                "captures": captures,
                                "breakpoint_hits": breakpoint_hits,
                            },
                        )
                        last_heartbeat = sampled_at
                    stop = gdb.wait_stop(
                        max(0, min(0.1, arguments.seconds - (sampled_at - started)))
                    )
                    if isinstance(stop, DebugFailure):
                        raise ConnectionError(stop.error)
                    if isinstance(stop, SignalStop):
                        raise ConnectionError(
                            f"Unexpected debugger stop with signal {stop.signal}."
                        )
                    if isinstance(stop, NoStop):
                        continue
                    breakpoint_hits += 1
                    pause_start = time.monotonic()
                    captured, trigger = capture_breakpoint(
                        gdb, profile, initializer, stop
                    )
                    if isinstance(captured, EventCapture):
                        record_capture(
                            captured, time.monotonic() - pause_start, trigger
                        )
                    else:
                        write(
                            "gap",
                            {
                                "status": captured.status,
                                "error": captured.error,
                                "trigger": trigger,
                            },
                        )
                        previous, last_watch, last_failure = None, None, captured
                        if not gdb.connected:
                            raise ConnectionError(captured.error)
                    continue
                watched = read_event_watch(profile, gdb.read_memory)
                samples += 1
                if not isinstance(watched, CaptureFailure) and (
                    last_watch is None
                    or (watched.positions, watched.trigger_fields)
                    != (last_watch.positions, last_watch.trigger_fields)
                ):
                    pause_start = time.monotonic()
                    captured = capture_paused(gdb, profile)
                    pause_seconds = time.monotonic() - pause_start
                    if isinstance(captured, EventCapture):
                        record_capture(captured, pause_seconds, {"kind": "poll"})
                    else:
                        watched = captured
                if isinstance(watched, CaptureFailure):
                    if watched != last_failure:
                        write("gap", {"status": watched.status, "error": watched.error})
                        print(
                            f"Capture unavailable: {watched.error}",
                            file=sys.stderr,
                            flush=True,
                        )
                    # A gap loses continuity. Never report a stopped/restarted
                    # event by comparing across missing or invalid observations.
                    last_watch, previous, last_failure = None, None, watched
                    if not gdb.connected or watched.status in (
                        "configuration",
                        "pause-failed",
                    ):
                        raise ConnectionError(watched.error)
                if time.monotonic() - last_heartbeat >= 30:
                    write("heartbeat", {"samples": samples, "captures": captures})
                    last_heartbeat = time.monotonic()
                time.sleep(max(0, 1 / arguments.hz - (time.monotonic() - sampled_at)))
        except KeyboardInterrupt:
            ended = "interrupted"
        except (OSError, ValueError) as error:
            exit_code, ended = 1, "failure"
            print(f"Capture stopped: {error}", file=sys.stderr)
            try:
                write("failure", {"error": str(error)})
            except OSError:
                # A broken output stream cannot record its own failure.
                # The diagnostic above still reports it to the operator.
                pass
        finally:
            if owned_watches and gdb.connected:
                error = gdb.interrupt()
                if error:
                    exit_code, ended = 1, "failure"
                    print(
                        f"Could not pause for watchpoint cleanup: {error}",
                        file=sys.stderr,
                    )
                for address in reversed(owned_watches):
                    error = gdb.change_write_watchpoint("remove", address, 1)
                    if error:
                        exit_code, ended = 1, "failure"
                        print(
                            f"Could not remove event watchpoint: {error}",
                            file=sys.stderr,
                        )
                        break
            if gdb.connected:
                # GDB connect itself pauses the game. Also cover interruption
                # during startup, before the initial continue was sent.
                error = gdb.resume()
                if error:
                    exit_code, ended = 1, "failure"
                    print(f"Could not resume DuckStation: {error}", file=sys.stderr)
            gdb.close()
            try:
                write(
                    "end",
                    {
                        "reason": ended,
                        "samples": samples,
                        "captures": captures,
                        "breakpoint_hits": breakpoint_hits,
                    },
                )
            except OSError as error:
                exit_code = 1
                print(f"Could not finish capture log: {error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
