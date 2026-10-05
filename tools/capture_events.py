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

from emulator.duckstation_gdb import DuckStationGdb
from games.re1.event_capture import (
    CaptureFailure,
    EventCapture,
    observed_changes,
    read_event_capture,
    read_event_watch,
)
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
        error = gdb.resume()
        if error:
            raise ConnectionError(f"Could not resume DuckStation: {error}")
    return captured


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument(
        "--out", type=Path, required=True, help="new JSONL file outside this repository"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2345)
    parser.add_argument("--hz", type=float, default=20.0)
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
            "requested_hz": arguments.hz,
            "requested_seconds": arguments.seconds,
            "sampling_limit": "Events between polls can be missed. Changes are observations, not execution or load history.",
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

        try:
            write("session", provenance)
            error = gdb.connect()
            if error:
                raise ConnectionError(error)
            error = gdb.resume()
            if error:
                raise ConnectionError(error)
            print(f"Capture log: {path}", flush=True)
            while time.monotonic() - started < arguments.seconds:
                sampled_at = time.monotonic()
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
                        # A torn running read can disappear under pause. Do
                        # not log another copy of the same coherent observation.
                        if captured != previous:
                            write(
                                "snapshot",
                                {
                                    "comparison": "baseline"
                                    if previous is None
                                    else "continuous",
                                    "changes": []
                                    if previous is None
                                    else observed_changes(previous, captured),
                                    "pause_seconds": pause_seconds,
                                    **captured.record(),
                                },
                            )
                            captures += 1
                            print(
                                f"Snapshot {captures}: room {captured.room}, active events {len(captured.events.events)}",
                                flush=True,
                            )
                        last_watch, previous, last_failure = (
                            captured.watch,
                            captured,
                            None,
                        )
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
                    "end", {"reason": ended, "samples": samples, "captures": captures}
                )
            except OSError as error:
                exit_code = 1
                print(f"Could not finish capture log: {error}", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
