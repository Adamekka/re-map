"""Live-poll regressions using controlled SLUS-00551 item states."""

import json
import logging
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

import track
from track import PollStatus, poll_once

from emulator.duckstation_gdb import MemRead
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import Tracker
from ui.map_view import map_state


class RamReader:
    def __init__(self, ram: bytearray):
        self.ram = ram
        self.fail_address = -1

    def read_memory(self, address: int, length: int) -> MemRead:
        if address == self.fail_address:
            return MemRead(ok=False, data=b"", error="injected read failure")
        offset = address - 0x80000000
        if offset < 0 or offset + length > len(self.ram):
            return MemRead(ok=False, data=b"", error="outside PS1 RAM")
        return MemRead(ok=True, data=bytes(self.ram[offset : offset + length]))


def fixture_ram(name: str, tmp_path: Path) -> bytearray:
    output = tmp_path / f"{name}.bin"
    subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/extract_sav_ram.py"),
            str(REPO / "tests/fixtures" / name),
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    return bytearray(output.read_bytes())


@pytest.mark.parametrize(
    "kind,room,label",
    [("green_herb", "00-09", "Green Herb"), ("chemical", "00-18", "Chemical")],
)
def test_live_poll_rechecks_pickup_after_state_load(tmp_path, kind, room, label):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    before = RamReader(fixture_ram(f"slus00551_{kind}_before.sav", tmp_path))
    after = RamReader(fixture_ram(f"slus00551_{kind}_after.sav", tmp_path))
    tracker = Tracker()
    available = poll_once(profile, tracker, before.read_memory)
    assert available.status == PollStatus.Display
    assert f"Current room: {room}" in available.text
    assert f"{label}: available" in available.text
    assert (
        "Items: 1\nCollected: 0\nState: INCOMPLETE\nList complete: yes"
        in available.text
    )
    taken = poll_once(profile, tracker, after.read_memory)
    assert taken.status == PollStatus.Display
    assert f"{label}: taken" in taken.text
    assert "Items: 1\nCollected: 1\nState: CLEARED\nList complete: yes" in taken.text
    restored = poll_once(profile, tracker, before.read_memory)
    assert restored.status == PollStatus.Display
    assert f"{label}: available" in restored.text
    assert "State: INCOMPLETE" in restored.text


def test_live_poll_reads_all_room_doors(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status == PollStatus.Display
    assert len(tracker.doors) == 5
    armor = next(door for door in tracker.doors if door.target.room == 0x14)
    assert armor.state == "LOCKED"
    assert armor.label == "Locked · Armor Key"
    ram[0xC86B7] |= 8
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    armor = next(door for door in tracker.doors if door.target.room == 0x14)
    assert armor.state == "OPEN"
    ram[0xC86B7] &= ~8
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    armor = next(door for door in tracker.doors if door.target.room == 0x14)
    assert armor.state == "LOCKED"


def test_live_poll_rejects_wrong_game_and_read_failure(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    ram[0x4484C] ^= 1
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.WrongGame
    )
    assert tracker.rooms == {}
    ram[0x4484C] ^= 1
    reader = RamReader(ram)
    reader.fail_address = 0x800C86DC
    result = poll_once(profile, tracker, reader.read_memory)
    assert result.status == PollStatus.ReadFailure
    assert "injected read failure" in result.text
    assert tracker.rooms == {}


def test_room_transition_during_poll_is_retried(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)

    class SwitchingReader(RamReader):
        def __init__(self, ram):
            super().__init__(ram)
            self.room_reads = 0

        def read_memory(self, address, length):
            if address == 0x800C8661:
                self.room_reads += 1
                if self.room_reads == 2:
                    return MemRead(ok=True, data=b"\x08")
            return super().read_memory(address, length)

    tracker = Tracker()
    result = poll_once(profile, tracker, SwitchingReader(ram).read_memory)
    assert result.status == PollStatus.Retry
    assert tracker.rooms == {}


def test_map_reveals_only_observed_regions_and_keeps_secret_space_separate(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    state = map_state(tracker)
    assert [(room["id"], room["state"]) for room in state["rooms"]] == [
        ("09", "INCOMPLETE")
    ]
    assert state["rooms"][0]["items"][0]["label"] == "Green Herb"
    assert len(state["doors"]) == 5
    assert "14" not in [room["id"] for room in state["rooms"]]


def test_live_log_records_item_changes_and_read_failures(tmp_path, monkeypatch):
    before = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    after = fixture_ram("slus00551_green_herb_after.sav", tmp_path)

    class LoggedReader(RamReader):
        connected = True  # The fixture reader has no network transport.

        def connect(self):
            return ""

        def resume(self):
            return ""

        def close(self):
            # The in-memory test reader owns no socket.
            pass

    reader = LoggedReader(before)
    log = tmp_path / "tracker.log"
    monkeypatch.setattr(track, "DuckStationGdb", lambda host, port: reader)
    monkeypatch.setattr(sys, "argv", ["track.py", "--log-file", str(log)])
    sleeps = 0

    def advance_state(period):
        nonlocal sleeps
        sleeps += 1
        if sleeps == 1:
            reader.ram = after
        elif sleeps == 2:
            reader.fail_address = 0x800C86DC
        else:
            raise KeyboardInterrupt

    monkeypatch.setattr(track.time, "sleep", advance_state)
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers = []
    try:
        assert track.main() == 0
        contents = log.read_text()
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = handlers
        root.setLevel(level)
    assert "Green Herb: available" in contents
    assert "Green Herb: taken" in contents
    assert "Poll read-failure" in contents
    assert "0x800c86dc length=32 received=0 error='injected read failure'" in contents
    assert "Tracker stopped by user" in contents
    assert "GDB closed" in contents


def test_profile_rejects_ambiguous_or_invalid_identity_config(tmp_path: Path):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    raw["room_manifest_path"] = str(REPO / "data/room_manifest_slus00551.json")
    raw["floor_plans_path"] = str(REPO / "data/floor_plans_slus00551.json")
    raw["pilot_items"][0]["flag_mask"] = "0x01"
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(raw))
    assert Re1Profile.load(profile_path).pilot_items[0].flag_mask == 1

    raw["pilot_items"][0]["flag_mask"] = "01"
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="0x prefix"):
        Re1Profile.load(profile_path)

    raw["pilot_items"][0]["flag_mask"] = 1
    raw["runtime_signature"]["concatenated_sha256"] = "A" * 64
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="lowercase hex"):
        Re1Profile.load(profile_path)

    raw["runtime_signature"]["concatenated_sha256"] = "0" * 64
    raw["pilot_items"][1]["room_sub"] = "0x09"
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="duplicate pilot item room"):
        Re1Profile.load(profile_path)

    raw["pilot_items"][1]["room_sub"] = 18
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="0x-prefixed"):
        Re1Profile.load(profile_path)

    raw["pilot_items"][1]["room_sub"] = "0x18"
    del raw["pilot_items"][0]["conditions"]
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="explicit conditions list"):
        Re1Profile.load(profile_path)

    raw["pilot_items"][0]["conditions"] = []
    raw["pilot_items"][1]["conditions"][0]["expected_masked_value"] = "0x04"
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="expected value must fit"):
        Re1Profile.load(profile_path)

    raw["pilot_item"] = raw.pop("pilot_items")[0]
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="renamed to pilot_items"):
        Re1Profile.load(profile_path)


@pytest.mark.parametrize(
    ("map_enabled", "initially_offline"), [(True, True), (True, False), (False, False)]
)
def test_live_tracker_reconnects_after_startup_or_runtime_failure(
    tmp_path, monkeypatch, map_enabled, initially_offline
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)

    class ReconnectingReader(RamReader):
        connected = False
        connects = 0
        resumes = 0
        drop_on_read = False

        def connect(self):
            self.connects += 1
            if self.connects == 1 and initially_offline:
                return "injected emulator offline"
            self.connected = True
            self.drop_on_read = False
            return ""

        def resume(self):
            self.resumes += 1
            return ""

        def close(self):
            self.connected = False

        def read_memory(self, address, length):
            if self.drop_on_read:
                self.connected = False
            if not self.connected:
                return MemRead(ok=False, data=b"", error="not connected")
            return super().read_memory(address, length)

    reader = ReconnectingReader(ram)
    server = (
        track.MapServer(
            0, json.loads((REPO / "data/floor_plans_slus00551.json").read_text())
        )
        if map_enabled
        else None
    )
    log = tmp_path / "reconnect.log"
    monkeypatch.setattr(track, "DuckStationGdb", lambda host, port: reader)
    monkeypatch.setattr(track, "MapServer", lambda port, plan: server)
    monkeypatch.setattr(
        sys,
        "argv",
        ["track.py", *(["--map"] if map_enabled else []), "--log-file", str(log)],
    )
    now = 0.0
    snapshots = []
    statuses = []

    def record_poll(profile, tracker, read_memory):
        result = poll_once(profile, tracker, read_memory)
        statuses.append(result.status)
        return result

    monkeypatch.setattr(track, "poll_once", record_poll)
    monkeypatch.setattr(track.time, "monotonic", lambda: now)

    def advance(period):
        nonlocal now
        if server is not None:
            snapshots.append(json.loads(server.snapshot))
        now += 2
        if not initially_offline and len(statuses) == 1:
            # A transport discovers closure on its next read, then marks itself disconnected.
            reader.drop_on_read = True
        if len(statuses) == (2 if initially_offline else 3):
            raise KeyboardInterrupt

    monkeypatch.setattr(track.time, "sleep", advance)
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers = []
    try:
        assert track.main() == 0
        contents = log.read_text()
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = handlers
        root.setLevel(level)
    assert statuses == (
        [PollStatus.ReadFailure, PollStatus.Display]
        if initially_offline
        else [PollStatus.Display, PollStatus.ReadFailure, PollStatus.Display]
    )
    if server is not None:
        assert snapshots[-2]["status"] == "waiting"
        assert snapshots[-1]["rooms"][0]["items"][0]["label"] == "Green Herb"
    assert reader.connects == 2
    assert reader.resumes == (1 if initially_offline else 2)
    assert not reader.connected
    assert "GDB reconnected and resumed" in contents


@pytest.mark.parametrize(
    "key", ["stage_address_ps1", "room_address_ps1", "camera_address_ps1"]
)
def test_runtime_profile_requires_room_identity_and_camera(key, tmp_path):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    raw["room_manifest_path"] = str(REPO / "data/room_manifest_slus00551.json")
    raw["floor_plans_path"] = str(REPO / "data/floor_plans_slus00551.json")
    del raw[key]
    path = tmp_path / "missing-address.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match=f"requires {key}"):
        Re1Profile.load(path)
