"""Lifecycle gating: title/demo states must not record visits.

RE1-LIFECYCLE-002 records the discriminator evidence. The pinned profile
gates on the lifecycle byte at 0x800C866C: 0x00 reads as title, demo, or
other non-gameplay state, while tested Jill gameplay reads 0x07. Only the
0x00 value suppresses visits, so untested gameplay phases stay fail-open.
The demo-RAM cases below substitute the lifecycle byte in copies of the
donated Herb fixture; flag changes are synthetic and prove the gate logic,
not a natural demo transition.
"""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from test_live_items import RamReader, fixture_ram
from track import PollStatus, poll_once

from emulator.duckstation_gdb import MemRead
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import Tracker

LIFECYCLE_OFFSET = 0xC866C


@pytest.fixture
def ram(tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    assert ram[LIFECYCLE_OFFSET] == 0x07
    return ram


def test_demo_byte_records_no_visit(ram):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    assert profile.lifecycle_address == 0x800C866C
    ram[LIFECYCLE_OFFSET] = 0x00
    tracker = Tracker()
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status == PollStatus.NonGameplay
    assert "visits not recorded" in result.text
    assert tracker.rooms == {}
    assert tracker.current is None


@pytest.mark.parametrize("lifecycle", [0x07, 0x01, 0xFF])
def test_nonzero_lifecycle_byte_still_displays_and_records_visit(ram, lifecycle):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    # Only zero is validated as non-gameplay; synthetic nonzero values guard
    # against accidentally requiring Jill's observed 0x07 value.
    ram[LIFECYCLE_OFFSET] = lifecycle
    tracker = Tracker()
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status == PollStatus.Display
    assert "Current room: 00-09" in result.text
    assert tracker.current is not None
    assert len(tracker.rooms) == 1


def test_demo_then_gameplay_keeps_only_gameplay_visit(ram):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    tracker = Tracker()
    ram[LIFECYCLE_OFFSET] = 0x00
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.NonGameplay
    )
    ram[LIFECYCLE_OFFSET] = 0x07
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status == PollStatus.Display
    assert list(tracker.rooms) == ["00-09"]


def test_lifecycle_read_failure_is_not_gameplay(ram):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    tracker = Tracker()
    reader = RamReader(ram)
    reader.fail_address = 0x800C866C
    result = poll_once(profile, tracker, reader.read_memory)
    assert result.status == PollStatus.ReadFailure
    assert tracker.rooms == {}


def test_lifecycle_flip_during_poll_retries(ram):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
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


@pytest.mark.parametrize("lifecycle", [0x00, 0x08])
def test_lifecycle_flip_at_final_room_read_cannot_publish(ram, lifecycle):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")

    class LateReader(RamReader):
        room_reads = 0

        def read_memory(self, address, length):
            if address == profile.room_address:
                self.room_reads += 1
                if self.room_reads == 3:
                    # A same-room lifecycle change can leave the room/source
                    # checks valid while making their pending visit stale.
                    self.ram[LIFECYCLE_OFFSET] = lifecycle
            return super().read_memory(address, length)

    tracker = Tracker()
    result = poll_once(profile, tracker, LateReader(ram).read_memory)
    assert result.status == PollStatus.Retry
    assert tracker.rooms == {}
    assert tracker.current is None
    assert profile.room_observations == {}
