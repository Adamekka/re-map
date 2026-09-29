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


def test_live_poll_rechecks_herb_after_state_load(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    before = RamReader(fixture_ram("slus00551_green_herb_before.sav", tmp_path))
    after = RamReader(fixture_ram("slus00551_green_herb_after.sav", tmp_path))
    tracker = Tracker()

    first = poll_once(profile, tracker, before.read_memory)
    assert first.status == PollStatus.Display
    assert "Current room: 00-09" in first.text
    assert "Green Herb: available" in first.text
    assert "Items: 1\nCollected: 0\nState: INCOMPLETE\nList complete: no" in first.text

    taken = poll_once(profile, tracker, after.read_memory)
    assert taken.status == PollStatus.Display
    assert "Green Herb: taken" in taken.text
    assert "Items: 1\nCollected: 1\nState: UNKNOWN\nList complete: no" in taken.text

    restored = poll_once(profile, tracker, before.read_memory)
    assert restored.status == PollStatus.Display
    assert "Green Herb: available" in restored.text
    assert "Items: 1\nCollected: 0\nState: INCOMPLETE" in restored.text


def test_live_log_records_item_changes_and_read_failures(tmp_path: Path, monkeypatch):
    before = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    after = fixture_ram("slus00551_green_herb_after.sav", tmp_path)

    class LoggedReader(RamReader):
        def connect(self):
            return ""

        def resume(self):
            return ""

        def close(self):
            # This in-memory reader owns no socket to close.
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
            reader.fail_address = 0x800C86EA
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
        # CLI logging owns its handler; restore pytest's capture handlers after exercising it.
        for handler in root.handlers:
            handler.close()
        root.handlers = handlers
        root.setLevel(level)
    assert "Green Herb: available" in contents
    assert "Green Herb: taken" in contents
    assert "Poll read-failure" in contents
    assert "0x800c86ea length=1 received=0 error='injected read failure'" in contents
    assert "length=32 received=32 sha256=" in contents
    assert "Tracker stopped by user" in contents
    assert "GDB closed" in contents


def test_live_poll_requires_valid_variant_and_active_object(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()

    ram[0xB819C] = 0
    inactive = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert inactive.status == PollStatus.Display
    assert "Green Herb: availability unknown" in inactive.text
    assert "State: UNKNOWN" in inactive.text

    ram[0xB819C] = 4
    ram[0xC3002] &= 0x7F
    other_variant = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert other_variant.status == PollStatus.Display
    assert "Items: unknown" in other_variant.text
    assert "State: UNKNOWN" in other_variant.text

    ram[0xC3002] |= 0x80
    ram[0xC8669] = 0
    other_character = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert other_character.status == PollStatus.Display
    assert "character not supported" in other_character.text
    assert "State: UNKNOWN" in other_character.text

    ram[0xC8669] = 1
    ram[0xB81A4] ^= 1
    wrong_pointer = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert wrong_pointer.status == PollStatus.Display
    assert "Green Herb: availability unknown" in wrong_pointer.text
    assert "State: UNKNOWN" in wrong_pointer.text


def test_live_poll_rejects_wrong_game_and_read_failure(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()

    ram[0x4484C] ^= 1
    wrong_game = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert wrong_game.status == PollStatus.WrongGame
    assert tracker.rooms == {}

    ram[0x4484C] ^= 1
    reader = RamReader(ram)
    reader.fail_address = 0x800C86EA
    read_error = poll_once(profile, tracker, reader.read_memory)
    assert read_error.status == PollStatus.ReadFailure
    assert "injected read failure" in read_error.text
    assert tracker.rooms == {}


def test_room_transition_during_poll_is_retried(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)

    class SwitchingReader(RamReader):
        def __init__(self, ram: bytearray):
            super().__init__(ram)
            self.room_reads = 0

        def read_memory(self, address: int, length: int) -> MemRead:
            if address == 0x800C8661:
                self.room_reads += 1
                if self.room_reads == 2:
                    return MemRead(ok=True, data=b"\x08")
            return super().read_memory(address, length)

    tracker = Tracker()
    result = poll_once(profile, tracker, SwitchingReader(ram).read_memory)
    assert result.status == PollStatus.Retry
    assert "room changed during read" in result.text
    assert tracker.rooms == {}


def test_unmapped_room_stays_unknown_and_visit_history_accumulates(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    tracker = Tracker()

    herb = poll_once(profile, tracker, reader.read_memory)
    assert herb.status == PollStatus.Display
    assert "State: INCOMPLETE" in herb.text

    ram[0xC8661] = 8
    other = poll_once(profile, tracker, reader.read_memory)
    assert other.status == PollStatus.Display
    assert "Current room: 00-08" in other.text
    assert "Items: unknown\nCollected: unknown\nState: UNKNOWN" in other.text
    assert len(tracker.rooms) == 2

    ram[0xC8661] = 9
    returned = poll_once(profile, tracker, reader.read_memory)
    assert returned.status == PollStatus.Display
    assert "Current room: 00-09" in returned.text
    assert "Green Herb: available" in returned.text
    assert "State: INCOMPLETE" in returned.text
    assert len(tracker.rooms) == 2


def test_map_reveals_entered_rooms_without_cached_completion(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    labels = {item.room: item.label for item in profile.pilot_items}

    assert poll_once(profile, tracker, RamReader(ram).read_memory).status == PollStatus.Display
    first = map_state(tracker, labels)
    assert first["rooms"] == [{"id": "09", "state": "INCOMPLETE"}]
    assert first["known_item"] == "Green Herb"

    ram[0xC8661] = 8
    assert poll_once(profile, tracker, RamReader(ram).read_memory).status == PollStatus.Display
    expanded = map_state(tracker, labels)
    assert expanded["rooms"] == [
        {"id": "08", "state": "UNKNOWN"},
        {"id": "09", "state": "VISITED"},
    ]
    assert expanded["known_item"] is None

    ram[0xC8660] = 2
    assert poll_once(profile, tracker, RamReader(ram).read_memory).status == PollStatus.Display
    elsewhere = map_state(tracker, labels)
    assert elsewhere["current"] == "02-08"
    assert elsewhere["rooms"] == []

    after = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    assert poll_once(profile, tracker, RamReader(after).read_memory).status == PollStatus.Display
    restored = map_state(tracker, labels)
    assert restored["rooms"] == [
        {"id": "08", "state": "VISITED"},
        {"id": "09", "state": "UNKNOWN"},
    ]
    assert restored["known_item"] == "Green Herb"


def test_pilot_item_matches_generated_room_row():
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb, chemical = profile.pilot_items
    rooms = json.loads((REPO / "data/item_table_slus00551.json").read_text())["rooms"]
    room = next(row for row in rooms if row["file"] == herb.source_rdt)
    assert room["stats"]["init"].startswith("clean/")
    assert [(item["id"], item["gid"], item["addr"]) for item in room["items"]] == [
        (5, herb.global_id, "0x1ca5c")
    ]
    room = next(row for row in rooms if row["file"] == chemical.source_rdt)
    assert room["stats"]["init"].startswith("clean/")
    assert (1, chemical.global_id, "0x292") in [
        (item["id"], item["gid"], item["addr"]) for item in room["items"]
    ]


def test_chemical_pilot_respects_branch_before_and_after_pickup(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    before = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    after = fixture_ram("slus00551_chemical_after.sav", tmp_path)
    tracker = Tracker()

    assert "Green Herb: available" in poll_once(
        profile, tracker, RamReader(herb).read_memory
    ).text
    available = poll_once(profile, tracker, RamReader(before).read_memory)
    assert available.status == PollStatus.Display
    assert "Current room: 00-18" in available.text
    assert "Chemical: available" in available.text
    assert "Items: 1\nCollected: 0\nState: INCOMPLETE\nList complete: no" in available.text
    assert len(tracker.rooms) == 2

    taken = poll_once(profile, tracker, RamReader(after).read_memory)
    assert taken.status == PollStatus.Display
    assert "Chemical: taken" in taken.text
    assert "Items: 1\nCollected: 1\nState: UNKNOWN\nList complete: no" in taken.text

    for ram in (before, after):
        ram[0xC3006] |= 0x02
        alternate = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert alternate.status == PollStatus.Display
        assert "Items: unknown\nCollected: unknown\nState: UNKNOWN" in alternate.text
        assert "validated item branch not selected" in alternate.text
        assert "Chemical:" not in alternate.text

        ram[0xC3006] &= ~0x02
        restored = poll_once(profile, tracker, RamReader(ram).read_memory)
        expected = "Chemical: available" if ram is before else "Chemical: taken"
        assert expected in restored.text


def test_chemical_pilot_requires_active_object_and_readable_branch(tmp_path: Path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    tracker = Tracker()

    ram[0xB816C] = 0
    inactive = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert inactive.status == PollStatus.Display
    assert "Chemical: availability unknown" in inactive.text
    assert "State: UNKNOWN" in inactive.text

    ram[0xB816C] = 4
    reader = RamReader(ram)
    reader.fail_address = 0x800C3006
    failure = poll_once(profile, tracker, reader.read_memory)
    assert failure.status == PollStatus.ReadFailure
    assert "branch flag: injected read failure" in failure.text


def test_profile_rejects_ambiguous_or_invalid_identity_config(tmp_path: Path):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
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
