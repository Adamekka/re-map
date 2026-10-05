"""Event capture regressions; activity and state edits are synthetic."""

import json
import struct
import sys

import pytest
from test_live_items import REPO, RamReader, fixture_ram

sys.path.insert(0, str(REPO / "tools"))

import capture_events

from emulator.duckstation_gdb import MemRead
from games.re1.event_capture import (
    CaptureFailure,
    EventCapture,
    observed_changes,
    read_event_capture,
    read_event_watch,
)
from games.re1.re1_profile import Re1Profile


@pytest.fixture(scope="module")
def profile():
    return Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")


@pytest.fixture
def ram(tmp_path):
    return fixture_ram("slus00551_green_herb_before.sav", tmp_path)


def capture(profile, ram):
    result = read_event_capture(profile, RamReader(ram).read_memory)
    assert isinstance(result, EventCapture), result
    return result


def activate(profile, ram, baseline, slots):
    source = baseline.sources[0]
    point = next(
        point
        for point in profile.room_programs[source.source_rdt].event_program.points
        if point.state == 0 and point.depth == 0
    )
    base = int.from_bytes(ram[0xCAB10:0xCAB14], "little")
    for slot in slots:
        start = (
            profile.event_layout.pool_address
            - 0x80000000
            + slot * profile.event_layout.stride
        )
        ram[start], ram[start + 2], ram[start + 3] = point.state, 1, 255
        struct.pack_into("<I", ram, start + 8, base + point.offset)


def test_all_slots_capture_stop_and_restore_without_history(profile, ram):
    before = capture(profile, ram)
    assert before.watch.positions == ()
    activate(profile, ram, before, range(8))
    active_ram = ram[:]
    active = capture(profile, ram)
    assert len(active.events.events) == 8
    assert all(event.owners and not event.reason for event in active.events.events)
    assert observed_changes(before, active) == [
        {"kind": "became-active", "slot": slot} for slot in range(8)
    ]
    for slot in range(8):
        ram[
            profile.event_layout.pool_address
            - 0x80000000
            + slot * profile.event_layout.stride
            + 2
        ] = 0
    stopped = capture(profile, ram)
    assert observed_changes(active, stopped) == [
        {"kind": "became-inactive", "slot": slot} for slot in range(8)
    ]
    assert stopped.record() == before.record()
    ram[:] = active_ram
    assert capture(profile, ram) == active
    assert profile.room_observations == {}


def test_pickup_and_door_flags_change_without_an_active_event(profile, ram):
    before = capture(profile, ram)
    ram[0xC86EA] &= ~1
    ram[0xC86B7] |= 8
    after = capture(profile, ram)
    assert not after.events.events
    assert after.observation.items[0].state.value == "taken"
    assert any(door.state.value == "locked" for door, _ in before.doors)
    assert before.doors != after.doors
    changes = observed_changes(before, after)
    assert {"kind": "read-changed", "name": "acquisition"} in changes
    assert {"kind": "read-changed", "name": "unlock"} in changes
    json.dumps(after.record())


def test_in_place_source_change_is_watched_but_unmatched_source_is_rejected(
    profile, ram
):
    before = capture(profile, ram)
    item = before.observation.items[0]
    # This room has no audited quantity writer. Altering its immutable source
    # must create a watch change without manufacturing a source-bound capture.
    ram[item.source_address - 0x80000000 + 11] ^= 1
    assert read_event_watch(profile, RamReader(ram).read_memory) != before.watch
    failure = read_event_capture(profile, RamReader(ram).read_memory)
    assert (
        isinstance(failure, CaptureFailure) and failure.status == "source-unavailable"
    )


def test_inactive_fields_and_counters_do_not_create_false_transitions(profile, ram):
    before = capture(profile, ram)
    offset = profile.event_layout.pool_address - 0x80000000
    ram[offset : offset + 52] = bytes([255]) * 52
    ram[offset + 2] = 0
    assert capture(profile, ram) == before
    activate(profile, ram, before, [0])
    active = capture(profile, ram)
    ram[offset + 0x2C] ^= 1
    assert capture(profile, ram) == active


def test_registry_bound_includes_last_slot_and_excludes_retained_records(profile, ram):
    before = capture(profile, ram)
    registry = next(data for name, _, data in before.watch.fields if name == "registry")
    bound = int.from_bytes(
        ram[
            profile.runtime_room_layout.aot_bound_address
            - 0x80000000 : profile.runtime_room_layout.aot_bound_address
            - 0x80000000
            + 4
        ],
        "little",
    )
    assert len(registry) == bound - profile.runtime_room_layout.aot_base + 12
    assert any(
        name == f"source-{len(registry) // 12 - 1}"
        for name, _, _ in before.watch.fields
    )
    offset = profile.runtime_room_layout.aot_base - 0x80000000 + len(registry)
    ram[offset : offset + 12] = bytes([9]) * 12
    assert capture(profile, ram) == before


def test_room_change_does_not_report_prior_room_events_as_stopped(
    profile, ram, tmp_path
):
    before = capture(profile, ram)
    activate(profile, ram, before, [0])
    active = capture(profile, ram)
    after = capture(profile, fixture_ram("slus00551_chemical_before.sav", tmp_path))
    assert observed_changes(active, after) == [{"kind": "room-source-changed"}]


def test_unrelated_transient_flag_is_recorded_without_triggering_a_pause(profile, ram):
    before = capture(profile, ram)
    address, mask = profile.tracking_rule_layout.flag(5, 64)
    ram[address - 0x80000000] ^= mask
    after = capture(profile, ram)
    assert before.watch.fields != after.watch.fields
    assert before.watch.trigger_fields == after.watch.trigger_fields
    assert any(row["name"] == "script-flags-5" for row in after.record()["reads"])


@pytest.mark.parametrize(
    "field",
    [
        "stage",
        "registry",
        "acquisition",
        "unlock",
        "script-flags-0",
        "source-0",
        "pool",
    ],
)
@pytest.mark.parametrize("short", [False, True])
def test_failed_and_short_reads_never_produce_a_snapshot(profile, ram, field, short):
    baseline = capture(profile, ram)
    address = (
        profile.event_layout.pool_address
        if field == "pool"
        else next(
            address for name, address, _ in baseline.watch.fields if name == field
        )
    )
    reader = RamReader(ram)

    def failed(location, width):
        if location == address:
            return MemRead(
                short,
                bytes(width - 1) if short else b"",
                "" if short else "disconnected",
            )
        return reader.read_memory(location, width)

    result = read_event_capture(profile, failed)
    assert isinstance(result, CaptureFailure) and result.status == "read-failure"
    assert "short read" in result.error if short else "disconnected" in result.error


def test_mixed_flag_snapshot_is_rejected(profile, ram):
    reader = RamReader(ram)

    def changing(address, width):
        result = reader.read_memory(address, width)
        if address == profile.runtime_room_layout.acquisition_flags_address:
            ram[0xC86EA] ^= 1
        return result

    result = read_event_capture(profile, changing)
    assert isinstance(result, CaptureFailure) and result.status == "changed"


def test_wrong_game_and_unbound_event_are_explicit(profile, ram):
    baseline = capture(profile, ram)
    activate(profile, ram, baseline, [0])
    struct.pack_into(
        "<I", ram, profile.event_layout.pool_address - 0x80000000 + 8, 0x80000000
    )
    result = capture(profile, ram)
    assert result.events.events[0].reason and not result.events.events[0].owners
    address = profile.runtime_signature.window_addresses[0]
    ram[address - 0x80000000] ^= 1
    failure = read_event_capture(profile, RamReader(ram).read_memory)
    assert isinstance(failure, CaptureFailure) and failure.status == "wrong-game"


def test_log_fingerprints_source_bytes_instead_of_serializing_game_commands(
    profile, ram
):
    result = capture(profile, ram)
    source_reads = [
        row for row in result.record()["reads"] if row["name"].startswith("source-")
    ]
    assert source_reads and all(
        "sha256" in row and "hex" not in row for row in source_reads
    )
    assert "memory_markers" not in result.record()


class FakeGdb:
    def __init__(self, *args):
        self.connected = False
        self.paused = False
        self.resumes = 0
        self.pause_interrupt = False
        self.resume_failure = False

    def connect(self):
        self.connected, self.paused = True, True
        return ""

    def interrupt(self):
        self.paused = True
        if self.pause_interrupt:
            raise KeyboardInterrupt
        return ""

    def resume(self):
        self.resumes += 1
        if self.resume_failure:
            return "connection lost"
        self.paused = False
        return ""

    def close(self):
        self.connected = False

    def read_memory(self, address, width):
        raise AssertionError("test substitutes the capture boundary, not memory")


@pytest.mark.parametrize("failure", ["read", "interrupt", "exception", "resume"])
def test_pause_ownership_always_attempts_resume(monkeypatch, profile, failure):
    gdb = FakeGdb()
    gdb.connect()
    gdb.pause_interrupt = failure == "interrupt"
    gdb.resume_failure = failure == "resume"

    def read(*args):
        if failure == "exception":
            raise OSError("read failed")
        return CaptureFailure("read-failure", "read failed")

    monkeypatch.setattr(capture_events, "read_event_capture", read)
    if failure in ("interrupt", "exception", "resume"):
        with pytest.raises(
            {
                "interrupt": KeyboardInterrupt,
                "exception": OSError,
                "resume": ConnectionError,
            }[failure]
        ):
            capture_events.capture_paused(gdb, profile)
    else:
        assert capture_events.capture_paused(gdb, profile).status == "read-failure"
    assert gdb.resumes == 1
    if failure != "resume":
        assert not gdb.paused


def test_cli_resets_comparison_after_a_gap_and_ignores_torn_watch_hints(
    monkeypatch, profile, ram, tmp_path
):
    before = capture(profile, ram)
    activate(profile, ram, before, [7])
    active = capture(profile, ram)
    watched = iter(
        [
            before.watch,
            active.watch,
            CaptureFailure("read-failure", "missing sample"),
            active.watch,
            before.watch,
            # This running-read hint is activity that disappears under pause.
            active.watch,
            before.watch,
        ]
    )
    captured = iter([before, active, active, before, before])
    gdb = FakeGdb()
    monkeypatch.setattr(capture_events, "DuckStationGdb", lambda *args: gdb)
    monkeypatch.setattr(capture_events, "read_event_watch", lambda *args: next(watched))
    monkeypatch.setattr(
        capture_events, "read_event_capture", lambda *args: next(captured)
    )
    clock = [0.0]
    monkeypatch.setattr(capture_events.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        capture_events.time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )
    path = tmp_path / "capture.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture_events.py",
            "--profile",
            str(REPO / "profiles/re1_directors_cut_slus00551.json"),
            "--out",
            str(path),
            "--hz",
            "1",
            "--seconds",
            "7",
        ],
    )
    assert capture_events.main() == 0
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["kind"] == "session" and rows[0]["manifest_sha256"]
    snapshots = [row for row in rows if row["kind"] == "snapshot"]
    assert [row["comparison"] for row in snapshots] == [
        "baseline",
        "continuous",
        "baseline",
        "continuous",
    ]
    assert snapshots[1]["changes"] == [{"kind": "became-active", "slot": 7}]
    assert snapshots[2]["changes"] == []
    assert snapshots[3]["changes"] == [{"kind": "became-inactive", "slot": 7}]
    assert rows[-1]["kind"] == "end" and rows[-1]["captures"] == 4
    assert rows[-1]["samples"] == 7 and gdb.resumes == 7
    assert [row["sequence"] for row in rows] == list(range(len(rows)))
    assert not gdb.paused and not gdb.connected


@pytest.mark.parametrize("out", ["repository", "existing"])
def test_cli_rejects_repository_output_and_existing_logs(monkeypatch, tmp_path, out):
    path = (
        REPO / "unwritten-event-capture.jsonl"
        if out == "repository"
        else tmp_path / "existing.jsonl"
    )
    if out == "existing":
        path.write_text("preserve")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture_events.py",
            "--profile",
            str(REPO / "profiles/re1_directors_cut_slus00551.json"),
            "--out",
            str(path),
        ],
    )
    with pytest.raises(SystemExit) as error:
        capture_events.main()
    assert error.value.code == 2
    if out == "existing":
        assert path.read_text() == "preserve"
    else:
        assert not path.exists()
