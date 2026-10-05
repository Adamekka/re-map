"""Breakpoint capture contracts. Event activity/CPU execution here is synthetic."""

import json
import struct
import sys

import pytest
from test_event_capture import FakeGdb
from test_live_items import REPO, RamReader, fixture_ram

sys.path.insert(0, str(REPO / "tools"))

import capture_events

from emulator.duckstation_gdb import DebugFailure, MemRead, NoStop, WriteWatchStop
from games.re1.event_capture import CaptureFailure, EventCapture
from games.re1.event_state import EventInitializer
from games.re1.re1_profile import Re1Profile


@pytest.fixture(scope="module")
def configuration():
    path = REPO / "profiles/re1_directors_cut_slus00551.json"
    raw = json.loads(path.read_text())["event_capture_initializer"]
    return Re1Profile.load(path), EventInitializer(
        *(
            int(raw[key], 0)
            for key in ("address", "activity_write_address", "commit_address")
        ),
        raw["sha256"],
    )


class BreakpointGdb(FakeGdb):
    def __init__(self, profile, initializer, ram):
        super().__init__()
        self.profile, self.initializer, self.ram = profile, initializer, ram
        self.reader = RamReader(ram)
        self.pc = 0x800262A0
        self.slot = 0
        self.steps = 0
        self.watches = []
        self.operations = []
        self.bad_step = False
        self.bad_register = False
        self.bad_record = False
        self.install_failure = False
        self.install_interrupt = False

    def read_memory(self, address, width):
        return self.reader.read_memory(address, width)

    def read_register(self, index):
        if self.bad_register:
            return MemRead(False, b"", "register read failed")
        if index == 37:
            value = self.pc
        else:
            assert index == 4
            value = self.profile.event_layout.pool_address + self.slot * 52
            if self.bad_record:
                value += 52
        return MemRead(True, value.to_bytes(4, "little"))

    def activity_write(self, slot, active):
        self.paused, self.slot = True, slot
        base = self.profile.event_layout.pool_address + slot * 52
        self.ram[base - 0x80000000 + 2] = active
        self.pc = self.initializer.activity_write_address + 4 if active else 0x800262A0
        return WriteWatchStop(5, base + 2)

    def single_step(self):
        self.steps += 1
        base = self.profile.event_layout.pool_address - 0x80000000 + self.slot * 52
        if self.pc == self.initializer.activity_write_address + 4:
            self.ram[base : base + 2] = bytes(2)
        if self.pc == self.initializer.commit_address - 8:
            self.ram[base + 3] = 255
        if self.pc == self.initializer.commit_address:
            room_base = int.from_bytes(self.ram[0xCAB10:0xCAB14], "little")
            table = int.from_bytes(self.ram[0xB835C:0xB8360], "little")
            entry = int.from_bytes(
                self.ram[table - 0x80000000 : table - 0x80000000 + 4], "little"
            )
            assert entry >= room_base
            struct.pack_into("<I", self.ram, base + 8, entry)
            self.pc = 0x80025CCC
        else:
            self.pc += 8 if self.bad_step else 4
        return ""

    def change_write_watchpoint(self, action, address, width):
        assert width == 1
        self.operations.append((action, address))
        if action == "insert":
            self.watches.append(address)
            if self.install_interrupt:
                raise KeyboardInterrupt
            if self.install_failure and len(self.watches) == 3:
                return "unsupported"
        else:
            self.watches.remove(address)
        return ""


@pytest.mark.parametrize("slot", range(8))
def test_all_slots_complete_the_initializer_before_source_binding(
    configuration, tmp_path, slot
):
    profile, initializer = configuration
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    gdb = BreakpointGdb(profile, initializer, ram)
    gdb.connect()
    stop = gdb.activity_write(slot, 1)
    result, trigger = capture_events.capture_breakpoint(gdb, profile, initializer, stop)
    assert isinstance(result, EventCapture)
    assert trigger["slot"] == slot and trigger["steps"] == 13
    assert gdb.steps == 13 and not gdb.paused
    assert len(result.events.events) == 1
    assert result.events.events[0].owners and not result.events.events[0].reason
    stopped, trigger = capture_events.capture_breakpoint(
        gdb, profile, initializer, gdb.activity_write(slot, 0)
    )
    assert isinstance(stopped, EventCapture) and not stopped.events.events
    assert trigger["steps"] == 0 and not gdb.paused


@pytest.mark.parametrize(
    "fault", ["register", "record", "path", "code", "identity", "foreign", "signal"]
)
def test_bad_breakpoint_inputs_resume_without_a_guessed_capture(
    configuration, tmp_path, fault
):
    profile, initializer = configuration
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    gdb = BreakpointGdb(profile, initializer, ram)
    gdb.connect()
    stop = gdb.activity_write(0, 1)
    gdb.bad_register, gdb.bad_record, gdb.bad_step = (
        fault == "register",
        fault == "record",
        fault == "path",
    )
    if fault == "code":
        ram[initializer.address - 0x80000000] ^= 1
    if fault == "identity":
        ram[profile.runtime_signature.window_addresses[0] - 0x80000000] ^= 1
    if fault == "foreign":
        stop = WriteWatchStop(5, 0x80000000)
    if fault == "signal":
        stop = WriteWatchStop(2, stop.address)
    with pytest.raises(ConnectionError):
        capture_events.capture_breakpoint(gdb, profile, initializer, stop)
    assert not gdb.paused and gdb.resumes == 1
    assert gdb.steps <= 1


@pytest.mark.parametrize(
    "failure", ["none", "setup", "interrupted-setup", "transport", "capture-read"]
)
def test_cli_catches_short_events_and_removes_owned_watches(
    monkeypatch, configuration, tmp_path, failure
):
    profile, initializer = configuration
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    gdb = BreakpointGdb(profile, initializer, ram)
    gdb.install_failure = failure == "setup"
    gdb.install_interrupt = failure == "interrupted-setup"
    clock = [0.0]
    actions = iter([1, 0, 1, 1])
    real_capture = capture_events.read_event_capture

    def read_capture(*args):
        if failure == "capture-read" and gdb.steps:
            gdb.close()
            # Model pinned server cleanup when the client attached while running.
            gdb.watches.clear()
            gdb.paused = False
            return CaptureFailure("read-failure", "original connection failure")
        return real_capture(*args)

    def wait(seconds):
        clock[0] += seconds
        if failure == "transport":
            return DebugFailure("transport failed")
        active = next(actions, None)
        return NoStop() if active is None else gdb.activity_write(7, active)

    monkeypatch.setattr(gdb, "wait_stop", wait, raising=False)
    monkeypatch.setattr(capture_events, "read_event_capture", read_capture)
    monkeypatch.setattr(capture_events, "DuckStationGdb", lambda *args: gdb)
    monkeypatch.setattr(capture_events.time, "monotonic", lambda: clock[0])
    path = tmp_path / "breakpoints.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture_events.py",
            "--profile",
            str(REPO / "profiles/re1_directors_cut_slus00551.json"),
            "--out",
            str(path),
            "--breakpoints",
            "--seconds",
            "1",
        ],
    )
    expected_exit = 1 if failure in ("setup", "transport", "capture-read") else 0
    assert capture_events.main() == expected_exit
    assert not gdb.watches and not gdb.connected and not gdb.paused
    inserted = [address for action, address in gdb.operations if action == "insert"]
    removed = [address for action, address in gdb.operations if action == "remove"]
    assert removed == ([] if failure == "capture-read" else list(reversed(inserted)))
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    assert rows[0]["capture_mode"] == "activity-breakpoints"
    assert "requested_hz" not in rows[0]
    assert rows[-1]["kind"] == "end"
    if failure == "none":
        assert len(inserted) == 8
        snapshots = [row for row in rows if row["kind"] == "snapshot"]
        assert len(snapshots) == 5
        assert [len(row["events"]) for row in snapshots] == [0, 1, 0, 1, 1]
        assert snapshots[-1]["changes"] == []
        assert all(row["trigger"]["slot"] == 7 for row in snapshots[1:])
        assert rows[-1]["breakpoint_hits"] == 4
    if failure == "capture-read":
        assert rows[-2]["kind"] == "failure"
        assert rows[-2]["error"] == "original connection failure"


def test_breakpoint_mode_rejects_missing_initializer_configuration(
    monkeypatch, tmp_path
):
    path = tmp_path / "profile.json"
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    raw.pop("event_capture_initializer")
    raw["room_manifest_path"] = str(REPO / "data/room_manifest_slus00551.json")
    path.write_text(json.dumps(raw))
    out = tmp_path / "unwritten.jsonl"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "capture_events.py",
            "--profile",
            str(path),
            "--out",
            str(out),
            "--breakpoints",
        ],
    )
    with pytest.raises(SystemExit) as error:
        capture_events.main()
    assert error.value.code == 2 and not out.exists()


def test_initializer_layout_rejects_an_unbounded_step_path(configuration):
    _, initializer = configuration
    with pytest.raises(ValueError, match="initializer"):
        EventInitializer(
            initializer.address,
            initializer.activity_write_address,
            initializer.commit_address + 4,
            initializer.sha256,
        )


@pytest.mark.parametrize("mode", ["poll", "breakpoint"])
@pytest.mark.parametrize("failure", ["read", "interrupted"])
def test_disconnected_capture_preserves_its_original_failure(
    monkeypatch, configuration, tmp_path, mode, failure
):
    profile, initializer = configuration
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    gdb = BreakpointGdb(profile, initializer, ram)
    gdb.connect()

    def failed_read(*args):
        gdb.close()
        if failure == "interrupted":
            raise KeyboardInterrupt
        return MemRead(False, b"", "original connection failure")

    monkeypatch.setattr(gdb, "read_memory", failed_read)

    def attempt():
        if mode == "poll":
            return capture_events.capture_paused(gdb, profile)
        return capture_events.capture_breakpoint(
            gdb, profile, initializer, gdb.activity_write(0, 1)
        )

    if failure == "interrupted":
        with pytest.raises(KeyboardInterrupt):
            attempt()
    elif mode == "breakpoint":
        with pytest.raises(ConnectionError, match="original connection failure"):
            attempt()
    else:
        result = attempt()
        assert isinstance(result, CaptureFailure)
        assert "original connection failure" in result.error
    assert not gdb.connected and gdb.resumes == 0
