"""RE2-SCENARIO-012: acquired identity, fresh flags and independent presence."""

import copy

import pytest
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from emulator.duckstation_gdb import MemRead
from games.bit_flags import msb_flag_location
from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-01", "03-05"], indirect=True)
def test191_rewinds_and_reconstructs_without_new_presence(snapshot):
    revision, _, put, read = snapshot
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = revision.flag_banks[revision.runtime_layout["item_bank_early"]][0]
    other_address, other_mask = msb_flag_location(bank, 190)
    # Hold the separate190 pickup collected to isolate191's contribution.
    put(
        other_address,
        int.from_bytes(read(other_address, 4).data, "little") | other_mask,
        4,
    )
    address, mask = msb_flag_location(bank, 191)
    tracker = Tracker()
    tracker.mark_current(RoomId(3, 5))
    visits = None
    for acquired in (False, True, False, True):
        value = int.from_bytes(read(address, 4).data, "little")
        put(address, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(revision, tracker, read).status is PollStatus.Display
        room = tracker.rooms["03-05"]
        assert room.completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Unknown
        )
        assert [r.state for r in room.items] == [
            "taken",
            "taken" if acquired else "unknown",
        ]
        # Existing quantity interpretation uses the retained creator operand7;
        # filtering adds no new award/amount rule or required-uncollected right.
        assert (room.items[1].label, room.items[1].quantity) == (
            revision.names["items"]["21"],
            7,
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(3, 5))
        assert poll_re2(revision, fresh, read).status is PollStatus.Display
        assert fresh == tracker
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-05"], indirect=True)
@pytest.mark.parametrize("offset", [3896, 3922])
@pytest.mark.parametrize("sat", [0, 0x31])
def test191_current_descriptor_presence_or_contradiction_is_independent(
    snapshot, offset, sat
):
    revision, _, put, read = snapshot
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = revision.flag_banks[revision.runtime_layout["item_bank_early"]][0]
    address, mask = msb_flag_location(bank, 190)
    put(address, int.from_bytes(read(address, 4).data, "little") | mask, 4)
    tracker = Tracker()
    assert poll_re2(revision, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    base = int.from_bytes(
        read(int(revision.runtime_layout["loaded_rdt_address_ps1"], 0), 4).data,
        "little",
    )
    selected = next(
        r for r in revision.rooms["03-05"]["items"] if r["offset"] == offset
    )
    pointer = base + offset + 2
    put(registry + selected["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, sat | (0x80 if selected["four_point"] else 0), 1)
    payload = 20 if selected["four_point"] else 12
    for index, name in enumerate(("type", "amount", "global_id")):
        put(pointer + payload + 2 * index, selected[name], 2)
    result = poll_re2(revision, tracker, read)
    if offset == 3896:
        assert result.status is PollStatus.Retry
        assert tracker == before
    else:
        assert result.status is PollStatus.Display
        assert tracker.rooms["03-05"].completion is (
            RoomCompletion.Incomplete if sat else RoomCompletion.Unknown
        )
        assert tracker.rooms["03-05"].items[1].state == (
            "available" if sat else "unknown"
        )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-01"], indirect=True)
@pytest.mark.parametrize("failure", ["failed", "short", "incoherent", "source"])
def test191_failure_never_partially_publishes(snapshot, failure):
    revision, _, put, read = snapshot
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(3, 5))
    assert poll_re2(revision, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    address = revision.flag_banks[1][0]
    source_address = 0x80100000 + revision.rooms["00-01"]["proofs"][0]["offset"]
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
@pytest.mark.parametrize("snapshot", ["00-01"], indirect=True)
@pytest.mark.parametrize("bank,bit", [(1, 0), (1, 1), (1, 6), (0, 25)])
def test191_changed_applicability_cannot_retain_a_selected_identity(
    snapshot, bank, bit
):
    revision, _, put, read = snapshot
    registry = int(revision.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(3, 5))
    assert poll_re2(revision, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    address, mask = msb_flag_location(revision.flag_banks[bank][0], bit)
    put(address, int.from_bytes(read(address, 4).data, "little") ^ mask, 4)
    result = poll_re2(revision, tracker, read)
    assert result.status is not PollStatus.Display
    assert tracker == before
