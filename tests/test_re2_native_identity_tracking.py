"""RE2-SCENARIO-010/011: identity and presence stay separate on reversal."""

import copy
from dataclasses import replace
from types import SimpleNamespace

import pytest
import test_re2_tracking
from test_live_items import RamReader
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from emulator.duckstation_gdb import MemRead
from games.bit_flags import msb_flag_location
from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-01", "00-08", "01-19"], indirect=True)
@pytest.mark.parametrize("target,gid", [("00-08", 213), ("01-19", 117)])
def test_acquired_identity_reverses_without_granting_departed_presence(
    snapshot, target, gid
):
    revision, _, put, read = snapshot
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    # No live descriptor supplies presence in this case. Only fresh acquisition
    # can settle the selected identity; missing registry entries are not absence.
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    address, mask = msb_flag_location(
        revision.flag_banks[revision.runtime_layout["item_bank_early"]][0], gid
    )
    tracker = Tracker()
    tracker.mark_current(RoomId(*(int(part, 16) for part in target.split("-"))))
    visits = None
    for acquired in (False, True, False, True):
        value = int.from_bytes(read(address, 4).data, "little")
        put(address, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(revision, tracker, read).status is PollStatus.Display
        room = tracker.rooms[target]
        assert room.completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Unknown
        )
        assert [(row.label, row.state, row.quantity) for row in room.items] == [
            (revision.names["items"]["20"], "taken" if acquired else "unknown", 15)
        ]
        fresh = Tracker()
        fresh.mark_current(RoomId(*(int(part, 16) for part in target.split("-"))))
        assert poll_re2(revision, fresh, read).status is PollStatus.Display
        assert fresh == tracker
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize(
    "snapshot,target,offset,gid",
    [("00-08", "00-08", 6934, 213), ("01-19", "01-19", 2762, 117)],
    indirect=["snapshot"],
)
def test_current_selected_descriptor_supplies_its_own_live_presence(
    snapshot, target, offset, gid
):
    revision, _, put, read = snapshot
    room = revision.rooms[target]
    selected = next(row for row in room["items"] if row["offset"] == offset)
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    base = int.from_bytes(
        read(int(revision.runtime_layout["loaded_rdt_address_ps1"], 0), 4).data,
        "little",
    )
    pointer = base + selected["offset"] + 2
    put(registry + selected["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, 0x31 | (0x80 if selected["four_point"] else 0), 1)
    payload = 20 if selected["four_point"] else 12
    for index, field in enumerate(("type", "amount", "global_id")):
        put(pointer + payload + index * 2, selected[field], 2)
    address, mask = msb_flag_location(
        revision.flag_banks[revision.runtime_layout["item_bank_early"]][0], gid
    )
    value = int.from_bytes(read(address, 4).data, "little")
    put(address, value & ~mask, 4)
    tracker = Tracker()
    assert poll_re2(revision, tracker, read).status is PollStatus.Display
    assert tracker.rooms[target].completion is RoomCompletion.Incomplete
    assert [row.state for row in tracker.rooms[target].items] == ["available"]


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize(
    "snapshot,target,offset",
    [("00-08", "00-08", 6976), ("00-08", "00-08", 7010), ("01-19", "01-19", 2826)],
    indirect=["snapshot"],
)
@pytest.mark.parametrize("sat", [0, 0x31])
def test_current_excluded_creator_is_an_atomic_contradiction(
    snapshot, target, sat, offset
):
    revision, _, put, read = snapshot
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(revision, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    base = int.from_bytes(
        read(int(revision.runtime_layout["loaded_rdt_address_ps1"], 0), 4).data,
        "little",
    )
    item = next(
        row for row in revision.rooms[target]["items"] if row["offset"] == offset
    )
    pointer = base + offset + 2
    put(registry + item["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    # Preserve native payload geometry while varying its activation bits.
    put(pointer + 1, sat | (0x80 if item["four_point"] else 0), 1)
    payload = 20 if item["four_point"] else 12
    for index, field in enumerate(("type", "amount", "global_id")):
        put(pointer + payload + index * 2, item[field], 2)
    assert poll_re2(revision, tracker, read).status is PollStatus.Retry
    assert tracker == before


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-01"], indirect=True)
@pytest.mark.parametrize("target", ["00-08", "01-19"])
@pytest.mark.parametrize("failure", ["failed", "short", "incoherent", "source"])
def test_identity_never_publishes_after_failed_or_incoherent_flags(
    snapshot, target, failure
):
    revision, _, put, read = snapshot
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(*(int(part, 16) for part in target.split("-"))))
    assert poll_re2(revision, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    address = revision.flag_banks[1][0]
    proof = revision.rooms["00-01"]["proofs"][0]
    source_address = 0x80100000 + proof["offset"]
    hits = 0

    def broken(at, width):
        nonlocal hits
        result = read(at, width)
        if failure == "source" and at <= source_address < at + width:
            changed = bytearray(result.data)
            changed[source_address - at] ^= 1
            return MemRead(True, bytes(changed))
        if at <= address < at + width:
            hits += 1
            if failure == "failed":
                return MemRead(False, b"")
            if failure == "short":
                return MemRead(True, result.data[:-1])
            if hits > 1:
                changed = bytearray(result.data)
                changed[address - at + 3] ^= 0x80
                return MemRead(True, bytes(changed))
        return result

    assert poll_re2(revision, tracker, broken).status is not PollStatus.Display
    assert tracker == before


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize(
    "snapshot,target,gid",
    [("00-08", "00-08", 213), ("01-19", "01-19", 117)],
    indirect=["snapshot"],
)
def test_departure_reentry_and_earlier_synthetic_image_preserve_visits(
    snapshot, target, gid
):
    current_profile, current_ram, _, _ = snapshot
    other_profile, other_ram, _, _ = test_re2_tracking.snapshot.__wrapped__(
        SimpleNamespace(param="00-01"), current_profile
    )
    revision = replace(
        current_profile,
        rooms=current_profile.rooms | {"00-01": other_profile.rooms["00-01"]},
    )
    ram = bytearray(current_ram)
    read = RamReader(ram).read_memory
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0) & 0x1FFFFF
    address, mask = msb_flag_location(
        revision.flag_banks[revision.runtime_layout["item_bank_early"]][0], gid
    )
    index = address & 0x1FFFFF
    tracker = Tracker()
    for current, acquired in (
        (True, False),
        (False, False),
        (True, False),
        (False, True),
        (True, True),
        (False, False),
        (True, False),
    ):
        ram[:] = current_ram if current else other_ram
        ram[registry : registry + 128] = bytes(128)
        value = int.from_bytes(ram[index : index + 4], "little")
        ram[index : index + 4] = (value | mask if acquired else value & ~mask).to_bytes(
            4, "little"
        )
        assert poll_re2(revision, tracker, read).status is PollStatus.Display
        assert tracker.rooms[target].completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Unknown
        )
        fresh = Tracker()
        for key in tracker.rooms:
            fresh.mark_current(RoomId(*(int(part, 16) for part in key.split("-"))))
        assert poll_re2(revision, fresh, read).status is PollStatus.Display
        assert fresh.rooms == tracker.rooms and fresh.doors == tracker.doors
        assert set(tracker.rooms) <= {target, "00-01"}
    assert set(tracker.rooms) == {target, "00-01"}
