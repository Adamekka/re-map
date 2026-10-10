"""Lifecycle gating: title/demo states must not record visits.

RE1-LIFECYCLE-002 records the discriminator evidence. The pinned profile
gates on the lifecycle byte at 0x800C866C: 0x00 reads as title, demo, or
other non-gameplay state, while tested Jill gameplay reads 0x07. Only the
0x00 value suppresses visits, so untested gameplay phases stay fail-open.
The demo-RAM cases below substitute the lifecycle byte in copies of the
donated Herb fixture; flag changes are synthetic and prove the gate logic,
not a natural demo transition.
"""

import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from track import PollStatus, poll_once

from emulator.duckstation_gdb import MemRead
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import Tracker

LIFECYCLE_OFFSET = 0xC866C


def fixture_ram() -> bytearray:
    output = Path("/tmp/re-map-lifecycle-herb.bin")
    subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/extract_sav_ram.py"),
            str(REPO / "tests/fixtures/slus00551_green_herb_before.sav"),
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    ram = bytearray(output.read_bytes())
    assert ram[LIFECYCLE_OFFSET] == 0x07
    return ram


def ram_reader(ram: bytearray, fail_address: int = -1):
    def read_memory(address: int, length: int) -> MemRead:
        if address == fail_address:
            return MemRead(ok=False, data=b"", error="injected read failure")
        offset = address - 0x80000000
        if offset < 0 or offset + length > len(ram):
            return MemRead(ok=False, data=b"", error="outside PS1 RAM")
        return MemRead(ok=True, data=bytes(ram[offset : offset + length]))

    return read_memory


def test_demo_byte_records_no_visit():
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    assert profile.lifecycle_address == 0x800C866C
    ram = fixture_ram()
    ram[LIFECYCLE_OFFSET] = 0x00
    tracker = Tracker()
    result = poll_once(profile, tracker, ram_reader(ram))
    assert result.status == PollStatus.NonGameplay
    assert "visits not recorded" in result.text
    assert tracker.rooms == {}
    assert tracker.current is None


def test_gameplay_byte_still_displays_and_records_visit():
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    tracker = Tracker()
    result = poll_once(profile, tracker, ram_reader(fixture_ram()))
    assert result.status == PollStatus.Display
    assert "Current room: 00-09" in result.text
    assert tracker.current is not None
    assert len(tracker.rooms) == 1


def test_demo_then_gameplay_keeps_only_gameplay_visit():
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram()
    tracker = Tracker()
    ram[LIFECYCLE_OFFSET] = 0x00
    assert poll_once(profile, tracker, ram_reader(ram)).status == PollStatus.NonGameplay
    ram[LIFECYCLE_OFFSET] = 0x07
    result = poll_once(profile, tracker, ram_reader(ram))
    assert result.status == PollStatus.Display
    assert list(tracker.rooms) == ["00-09"]


def test_lifecycle_read_failure_is_not_gameplay():
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    tracker = Tracker()
    result = poll_once(
        profile, tracker, ram_reader(fixture_ram(), fail_address=0x800C866C)
    )
    assert result.status == PollStatus.ReadFailure
    assert tracker.rooms == {}


def test_lifecycle_flip_during_poll_retries():
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram()
    calls = {"lifecycle": 0}

    def flipping(address: int, length: int) -> MemRead:
        if address == 0x800C866C:
            calls["lifecycle"] += 1
            # First read sees gameplay; the end-of-poll recheck sees demo.
            value = 0x07 if calls["lifecycle"] == 1 else 0x00
            return MemRead(ok=True, data=bytes((value,)))
        offset = address - 0x80000000
        return MemRead(ok=True, data=bytes(ram[offset : offset + length]))

    tracker = Tracker()
    result = poll_once(profile, tracker, flipping)
    assert result.status == PollStatus.Retry
    assert tracker.rooms == {}
