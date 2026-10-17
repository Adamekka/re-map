"""Shared acquisition rules, native activation and fresh cached-state checks."""

import json
import struct
from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_live_items import REPO, RamReader, fixture_ram
from test_tracking_rules import branch, compile_program
from track import PollStatus, poll_once

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re1.acquisition_state import (
    AcquisitionFlag,
    AcquisitionLayout,
    FixedAcquisitionRule,
    GlobalIdAcquisitionRule,
)
from games.re1.re1_profile import Re1Profile
from games.re1.room_cache import refresh_cached_items
from games.re1.room_items import RuntimeItemState, observe_room_items
from games.re1.tracking_engine import refresh_visited_room
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)
from tracker.exploration_state import Tracker
from ui.map_view import map_state

pytest_plugins = ("test_tracking_rules", "test_room_items")


@pytest.mark.parametrize(
    "gid,offset,mask",
    [(0, 3, 128), (31, 0, 1), (32, 7, 128), (111, 14, 1), (255, 28, 1)],
)
def test_ordinary_flags_keep_native_word_order(layout, gid, offset, mask):
    flag = layout.acquisition.flag(0x44, gid)
    assert flag == AcquisitionFlag(0x800C86DC + offset, mask, False)
    flags = bytearray([255] * 32)
    assert not layout.acquisition.collected(flag, bytes(flags), {})
    flags[offset] &= ~mask
    assert layout.acquisition.collected(flag, bytes(flags), {})


def test_separate_flag_has_explicit_polarity_and_no_global_id_dependency(layout):
    for gid in (0, 111, 255):
        flag = layout.acquisition.flag(0x4D, gid)
        assert flag == AcquisitionFlag(0x800C870C, 1, True)
        for ordinary in (bytes(32), bytes([255]) * 32):
            assert not layout.acquisition.collected(flag, ordinary, {flag.address: 0})
            assert layout.acquisition.collected(flag, ordinary, {flag.address: 1})
    with pytest.raises(AssertionError, match="dependency"):
        layout.acquisition.collected(flag, bytes(32), {})


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "overlap",
        "polarity",
        "mask",
        "address",
        "selector",
        "objects",
        "range",
    ],
)
def test_invalid_profile_rules_fail_at_startup(layout, change):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())[
        "acquisition_rules"
    ]
    if change == "missing":
        raw.pop()
    elif change == "overlap":
        raw[1]["item_types"] = [0x4C, 0x4D]
    elif change == "polarity":
        raw[1]["acquired_when_set"] = 1
    elif change == "mask":
        raw[1]["mask"] = 3
    elif change == "address":
        raw[1]["address_ps1"] = "0x80200000"
    elif change == "selector":
        raw[1]["index"] = "guess"
    elif change == "objects":
        raw = [None]
    else:
        raw[1]["item_types"] = [0x4D]
    with pytest.raises(ValueError, match="acquisition"):
        AcquisitionLayout.load(raw, layout.acquisition_flags_address, 32)


def test_profile_requires_rules_and_shares_one_layout(tmp_path):
    path = REPO / "profiles/re1_directors_cut_slus00551.json"
    profile = Re1Profile.load(path)
    assert (
        profile.runtime_room_layout.acquisition
        is profile.tracking_rule_layout.acquisition
    )
    raw = json.loads(path.read_text())
    del raw["acquisition_rules"]
    missing = tmp_path / "missing.json"
    missing.write_text(json.dumps(raw))
    with pytest.raises(KeyError, match="acquisition_rules"):
        Re1Profile.load(missing)


@pytest.mark.parametrize("handler", [0, 4])
def test_live_radio_uses_actual_handler_and_rewinds_separate_flag(
    layout, tmp_path, handler
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer + 8] = 0x4D
    ram[0xB819C] = handler
    for ordinary in (0, 1):
        ram[0xC86EA] = ordinary
        for owned, expected in [
            (
                0,
                RuntimeItemState.Available
                if handler == 4
                else RuntimeItemState.Unavailable,
            ),
            (1, RuntimeItemState.Taken),
            (
                0,
                RuntimeItemState.Available
                if handler == 4
                else RuntimeItemState.Unavailable,
            ),
        ]:
            ram[0xC870C] = owned
            result = observe_room_items(
                layout, RoomId(0, 9), RamReader(ram).read_memory
            )
            assert result.ok and result.list_complete
            assert result.items[0].item_type == 0x4D
            assert result.items[0].state == expected


def test_live_fixed_rule_is_generic_and_can_clear_to_acquired(layout, tmp_path):
    acquisition = AcquisitionLayout(
        0x800C86DC,
        32,
        (
            GlobalIdAcquisitionRule(1, 0x43, False),
            FixedAcquisitionRule(0x44, 0x44, 0x800C8750, 4, False),
            GlobalIdAcquisitionRule(0x45, 0x53, False),
        ),
    )
    layout = replace(layout, acquisition=acquisition)
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    for byte, state in [
        (4, RuntimeItemState.Available),
        (0, RuntimeItemState.Taken),
        (4, RuntimeItemState.Available),
    ]:
        ram[0xC8750] = byte
        result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
        assert result.ok and result.items[0].state == state


@pytest.mark.parametrize("failure", ["error", "short", "changing"])
def test_separate_flag_failures_publish_no_live_evidence(layout, tmp_path, failure):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    reads = 0

    def read(address, width):
        nonlocal reads
        if address == 0x800C870C:
            reads += 1
            if failure == "error":
                return MemRead(False, b"", error="disconnected")
            if failure == "short":
                return MemRead(True, b"")
            if reads == 2:
                ram[0xC870C] ^= 1
        return reader.read_memory(address, width)

    result = observe_room_items(layout, RoomId(0, 9), read)
    assert not result.ok and result.items == ()
    assert result.retry == (failure == "changing")


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("ordinary", [False, True])
def test_reconstructed_radio_separates_activation_and_acquisition(
    rules, epoch, ordinary
):
    program = compile_program(rules, pickup(1, 0x4D, 111) + b"\0")
    ram = bytearray(2 * 1024 * 1024)
    flag = rules[0].acquisition.flag(0x4D, 111)
    flags = bytearray([255] * 32)
    if not ordinary:
        flags[14] &= ~1
    for owned in (0, 1, 0):
        ram[flag.address - 0x80000000] = owned
        snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
        result = evaluate_room_program(
            program, RoomId(0, 9), rules[0], snapshot, bytes(flags), (), epoch
        )
        assert result.items.list_complete
        assert result.items.items[0].state == (
            RuntimeItemState.Taken
            if owned
            else RuntimeItemState.Available
            if ordinary
            else RuntimeItemState.Unavailable
        )


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize(
    "operation,expected",
    [(0, RuntimeItemState.Available), (1, RuntimeItemState.Unavailable)],
)
def test_initializer_reads_same_pass_global_id_flag_writes(
    rules, epoch, operation, expected
):
    program = compile_program(
        rules, bytes((5, 7, 111, operation)) + pickup(1, 0x4D, 111) + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.items.list_complete
    assert result.items.items[0].state == expected
    assert not any(ram), "script simulation must not grant real acquisition"


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_explicit_handler_can_enable_separately_flagged_pickup(rules, epoch):
    program = compile_program(
        rules, pickup(1, 0x4D, 111) + bytes((0x13, 1, 4, 0)) + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes(32), (), epoch
    )
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Available


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_unknown_activation_shadows_cannot_claim_room_cleared(rules, epoch):
    code = (
        branch(bytes((6, 2, 0, 1)), bytes((5, 7, 111, 0)), bytes((5, 7, 111, 1)))
        + pickup(1, 0x4D, 111)
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (1,)


def test_cached_absence_proofs_follow_both_flags_even_with_the_same_global_id(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    source = replace(cached.sources[0], cache_complete=True)
    acquisition = profile.runtime_room_layout.acquisition
    ordinary = acquisition.flag(0x44, 111)
    separate = acquisition.flag(0x4D, 111)
    cached = replace(
        cached, sources=(source,), absent_flags=((ordinary, False), (separate, False))
    )
    flags = bytes(ram[0xC86DC:0xC86FC])
    assert refresh_cached_items(
        cached, cached.context, flags, acquisition, {separate.address: 0}
    ).list_complete
    assert not refresh_cached_items(
        cached, cached.context, flags, acquisition, {separate.address: 1}
    ).list_complete
    earlier = bytearray(flags)
    earlier[14] &= ~1
    assert not refresh_cached_items(
        cached, cached.context, bytes(earlier), acquisition, {separate.address: 0}
    ).list_complete


def test_reentry_computation_cache_refreshes_separate_flag_in_both_directions(
    tmp_path, rules
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    source = replace(cached.sources[0], cache_complete=False)
    program = compile_program(rules, pickup(1, 0x4D, 111) + b"\0")
    profile.room_programs[source.source_rdt] = program
    cached = replace(cached, sources=(source,))
    separate = profile.runtime_room_layout.acquisition.flag(0x4D, 111)
    flags = bytes(ram[0xC86DC:0xC86FC])
    previous = None
    for owned, expected in [
        (0, RuntimeItemState.Available),
        (1, RuntimeItemState.Taken),
        (0, RuntimeItemState.Available),
    ]:
        ram[separate.address - 0x80000000] = owned
        snapshot = read_rule_snapshot(
            profile.tracking_rule_layout, (program,), RamReader(ram).read_memory
        )
        result = refresh_visited_room(profile, cached, cached.context, snapshot, flags)
        assert result.items.list_complete and result.items.items[0].state == expected
        current = profile.room_reentry_evaluations[source.source_rdt]
        assert current is not previous
        assert (
            refresh_visited_room(profile, cached, cached.context, snapshot, flags)
            == result
        )
        assert profile.room_reentry_evaluations[source.source_rdt] is current
        previous = current


@pytest.mark.parametrize("read_number", [2, 3, 4])
def test_poll_does_not_publish_across_separate_flag_change(tmp_path, read_number):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    reads = 0

    def read(address, width):
        nonlocal reads
        if address == 0x800C870C:
            reads += 1
            if reads == read_number:
                ram[0xC870C] ^= 1
        return reader.read_memory(address, width)

    tracker = Tracker()
    assert poll_once(profile, tracker, read).status == PollStatus.Retry
    assert tracker.rooms == {} and profile.room_observations == {}


def test_normal_room_poll_ignores_radio_ownership_for_map_reveal(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    for owned in (0, 1, 0):
        ram[0xC870C] = owned
        assert (
            poll_once(profile, tracker, RamReader(ram).read_memory).status
            == PollStatus.Display
        )
        assert tracker.room_state(RoomId(0, 9)).total_items == 1
        assert tracker.room_state(RoomId(0, 9)).collected_items == 0
        assert len(map_state(tracker)["rooms"]) == 1


def test_poll_keeps_activation_proof_and_separate_collection_facts(tmp_path, rules):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xC86DF] &= ~128
    ram[0xC870C] &= ~1
    source = next(
        row for row in profile.room_sources if row.source_rdt.endswith("1091.RDT")
    )
    profile.room_sources = tuple(
        replace(row, cache_complete=True) if row is source else row
        for row in profile.room_sources
    )
    profile.room_programs[source.source_rdt] = compile_program(
        rules, pickup(5, 0x44, 111) + pickup(6, 0x4D, 0) + b"\0"
    )
    assert (
        poll_once(profile, Tracker(), RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    activation = AcquisitionFlag(0x800C86DF, 128, False)
    separate = AcquisitionFlag(0x800C870C, 1, True)
    assert (activation, True) in cached.absent_flags
    assert (separate, False) not in cached.absent_flags
    assert any(
        item.item_type == 0x4D and item.state == RuntimeItemState.Uncollected
        for item in cached.observation.items
    )
    flags = bytes(ram[0xC86DC:0xC86FC])
    assert refresh_cached_items(
        cached,
        cached.context,
        flags,
        profile.runtime_room_layout.acquisition,
        {separate.address: 0},
    ).list_complete
    changed = bytearray(flags)
    changed[3] |= 128
    assert not refresh_cached_items(
        cached,
        cached.context,
        bytes(changed),
        profile.runtime_room_layout.acquisition,
        {separate.address: 0},
    ).list_complete


def test_optional_past_creator_cannot_use_present_ownership_as_activation_history(
    rules,
):
    from test_tracking_rules import guard

    program = compile_program(
        rules,
        pickup(0, 0x44, 2) + b"\0",
        main=guard(bytes((4, 1, 2, 0)), pickup(1, 0x4D, 111)) + b"\0",
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    flags = bytearray([255] * 32)
    flags[14] &= ~1
    result = evaluate_room_program(
        program,
        RoomId(0, 9),
        rules[0],
        snapshot,
        bytes(flags),
        (),
        RoomRuleEpoch.Current,
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (1,)
    fresh = evaluate_room_program(
        program,
        RoomId(0, 9),
        rules[0],
        snapshot,
        bytes(flags),
        (),
        RoomRuleEpoch.Reentry,
    )
    assert fresh.items.list_complete and len(fresh.items.items) == 1


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_forced_radio_award_cannot_invent_collection(rules, epoch):
    program = compile_program(
        rules,
        pickup(1, 0x4D, 111) + bytes((0x13, 1, 3, 0, 0)),
        main=bytes((0x24, 1, 4, 0, 0)),
    )
    ram = bytearray(2 * 1024 * 1024)
    flag = rules[0].acquisition.flag(0x4D, 111)
    for owned in (0, 1, 0):
        ram[flag.address - 0x80000000] = owned
        snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
        result = evaluate_room_program(
            program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
        )
        assert result.items.list_complete == bool(owned)
        if owned:
            assert result.items.items[0].state == RuntimeItemState.Taken
        else:
            assert result.unresolved_item_slots == (1,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_creator_activation_preserves_physical_flag_aliases(rules, epoch):
    bases = list(rules[0].flag_bases)
    bases[1] = bases[7]
    layout = replace(rules[0], flag_bases=tuple(bases))
    metadata = {**rules[1], "script_flag_bases": [hex(base) for base in bases]}
    program = compile_program(
        (layout, metadata), bytes((5, 1, 111, 1)) + pickup(1, 0x4D, 111) + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(layout, (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), layout, snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Unavailable


def test_observed_item_cache_uses_separate_ownership_without_reconstructing(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    assert (
        poll_once(profile, Tracker(), RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    radio = replace(cached.observation.items[0], item_type=0x4D)
    cached = replace(
        cached,
        sources=(replace(cached.sources[0], cache_complete=True),),
        observation=replace(cached.observation, items=(radio,)),
        absent_flags=(),
    )
    flags = bytes(ram[0xC86DC:0xC86FC])
    for owned, expected in [
        (0, RuntimeItemState.Available),
        (1, RuntimeItemState.Taken),
        (0, RuntimeItemState.Available),
    ]:
        result = refresh_cached_items(
            cached,
            cached.context,
            flags,
            profile.runtime_room_layout.acquisition,
            {0x800C870C: owned},
        )
        assert result.list_complete and result.items[0].state == expected


@pytest.mark.parametrize("short", [False, True])
def test_separate_acquisition_read_failure_blocks_rule_snapshot(rules, short):
    program = compile_program(rules, pickup(1, 0x4D, 111) + b"\0")
    ram = bytearray(2 * 1024 * 1024)
    reader = RamReader(ram)
    flag = rules[0].acquisition.flag(0x4D, 111)

    def read(address, width):
        if address == flag.address:
            return MemRead(True, b"") if short else MemRead(False, b"", "disconnected")
        return reader.read_memory(address, width)

    snapshot = read_rule_snapshot(rules[0], (program,), read)
    assert snapshot.error and snapshot.values == ()
    assert hex(flag.address) in snapshot.error
