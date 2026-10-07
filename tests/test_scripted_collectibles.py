"""RE1-COLLECT-002/003: synthetic access/acquisition checks, not gameplay evidence."""

import json
import struct
from dataclasses import asdict, replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import REPO, RamReader, fixture_ram
from test_tracking_rules import branch, compile_program, guard

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re1.event_state import EventProgram
from games.re1.re1_profile import Re1Profile
from games.re1.room_items import RuntimeItemState, observe_room_items
from games.re1.scripted_collectibles import scripted_collectible_access
from games.re1.tracking_engine import validate_current_room
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)

pytest_plugins = ("test_tracking_rules", "test_room_items")


def setter(slot, handler, record, entry):
    return bytes((0x12, slot, handler, 129)) + struct.pack("<HHH", record, entry, 0)


def confirmation(body):
    return (
        bytes((7, 6, 0x0B, 0x82, 255, 0))
        + bytes((0xFC, 6, 6, 5, 2, 128, 0xFE, 0xFD))
        + block(guard(bytes((6, 5, 0, 0)), body) + b"\0")
        + b"\xff"
    )


def chain(slot, handler):
    return indexed(
        confirmation(bytes((0x14, 0, 3, 1))),
        block(setter(slot, handler, 0, 0) + bytes((0x24, slot, handler, 0, 0)))
        + bytes((7, 6, 0x0B, 0, 255, 0, 0xFF)),
    )


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("item_type,handler", [(0x44, 4), (0x50, 15)])
@pytest.mark.parametrize("route", ["direct", "confirmation", "child"])
def test_access_keeps_fresh_acquisition_and_restores_earlier_state(
    rules, epoch, item_type, handler, route
):
    award = bytes((0x24, 4, handler, 0))
    event = {
        "direct": indexed(bytes((7, 6)) + award + b"\xff"),
        "confirmation": indexed(confirmation(award)),
        "child": chain(4, handler),
    }[route]
    program = compile_program(
        rules, pickup(4, item_type, 79) + setter(4, 9, 2, 0) + b"\0", event=event
    )
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error and program.coverage_complete
    flag = rules[0].acquisition.flag(item_type, 79)
    for taken in (False, True, False):
        flags = bytearray([255] * 32)
        if taken:
            flags[flag.address - rules[0].acquisition.flags_address] &= ~flag.mask
        before = bytes(flags)
        result = evaluate_room_program(
            program, RoomId(0, 9), rules[0], snapshot, flags, (), epoch
        )
        assert result.items.list_complete and not result.unresolved_item_slots
        assert len(result.items.items) == 1
        item = result.items.items[0]
        assert (item.aot_id, item.item_type, item.global_id) == (4, item_type, 79)
        assert item.state is (
            RuntimeItemState.Taken if taken else RuntimeItemState.Available
        )
        assert bytes(flags) == before


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("item_type", [0x44, 0x4D, 0x50])
def test_taken_scripted_items_resolve_without_access_and_reverse(
    rules, epoch, item_type
):
    descriptor = bytearray(pickup(4, item_type, 79))
    descriptor[11] = 6
    program = compile_program(
        rules,
        bytes(descriptor) + setter(4, 9, 2, 0) + b"\0",
        event=indexed(bytes((1, 0xFF))),
    )
    assert program.coverage_complete
    assert not scripted_collectible_access(program.event_program, 4, item_type, 2, 0)
    ram = bytearray(2 * 1024 * 1024)
    flag = rules[0].acquisition.flag(item_type, 79)
    for taken in (False, True, False):
        flags = bytearray([255] * 32)
        value = flag.mask if taken == flag.acquired_when_set else 0
        if (
            rules[0].acquisition.flags_address
            <= flag.address
            < (rules[0].acquisition.flags_address + 32)
        ):
            index = flag.address - rules[0].acquisition.flags_address
            flags[index] = flags[index] & ~flag.mask | value
        else:
            ram[flag.address - 0x80000000] = value
        snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
        assert not snapshot.error
        result = evaluate_room_program(
            program, RoomId(0, 9), rules[0], snapshot, bytes(flags), (), epoch
        )
        assert result.coverage_complete and result.items.list_complete is taken
        if taken:
            assert not result.unresolved_item_slots
            (item,) = result.items.items
            assert (item.aot_id, item.item_type, item.global_id, item.amount) == (
                4,
                item_type,
                79,
                6,
            )
            assert item.state is RuntimeItemState.Taken
        else:
            assert not result.items.items and result.unresolved_item_slots == (4,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("barrier", ["source", "mutable", "invalid-target", "decode"])
def test_taken_scripted_items_retain_source_and_execution_barriers(
    rules, epoch, barrier
):
    target = 255 if barrier == "invalid-target" else 0
    program = compile_program(
        rules,
        pickup(4, 0x44, 79)
        + setter(4, 9, 2, target)
        + (
            bytes((0x14, 0, 2, target))
            if barrier in ("invalid-target", "decode")
            else b""
        )
        + b"\0",
        event=indexed(bytes((0xFD, 0xFF)) if barrier == "decode" else bytes((1, 0xFF))),
    )
    if barrier == "source":
        program = replace(
            program, coverage_complete=False, reentry_coverage_complete=False
        )
    elif barrier == "mutable":
        program = replace(program, mutable_slots=(4,))
    snapshot = read_rule_snapshot(
        rules[0], (program,), RamReader(bytearray(2 * 1024 * 1024)).read_memory
    )
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes(32), (), epoch
    )
    assert not result.items.list_complete and not result.items.items
    assert result.unresolved_item_slots == (4,)


def test_taken_scripted_items_do_not_merge_different_source_identities(rules):
    program = compile_program(
        rules,
        branch(bytes((6, 2, 0, 1)), pickup(4, 0x44, 79), pickup(4, 0x50, 80))
        + setter(4, 9, 2, 0)
        + b"\0",
        event=indexed(bytes((1, 0xFF))),
    )
    snapshot = read_rule_snapshot(
        rules[0], (program,), RamReader(bytearray(2 * 1024 * 1024)).read_memory
    )
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes(32), (), RoomRuleEpoch.Reentry
    )
    assert result.coverage_complete
    assert not result.items.list_complete and not result.items.items
    assert result.unresolved_item_slots == (4,)


@pytest.mark.parametrize(
    "failure",
    [
        "story",
        "inventory",
        "no-prompt",
        "no-wait",
        "wrong-wait",
        "external-wait",
        "actor",
        "cycle",
        "auto-child",
        "wrong-slot",
        "wrong-type",
        "wrong-setter",
        "side-effect",
        "native-child",
        "root-overwrite",
        "auto-root",
        "second-award",
        "toggle-award",
    ],
)
def test_reachable_awards_do_not_bypass_unsupported_routes(rules, failure):
    root = confirmation(bytes((0x14, 0, 3, 1)))
    child = block(setter(4, 15, 0, 0) + bytes((0x24, 4, 15, 0, 0))) + b"\xff"
    record = 2
    if failure in ("story", "inventory"):
        condition = bytes((4, 1, 7, 0)) if failure == "story" else bytes((0x10, 0x34))
        root = (
            root[:14]
            + block(guard(condition, bytes((0x14, 0, 3, 1))) + b"\0")
            + b"\xff"
        )
    elif failure == "no-prompt":
        root = root[6:]
    elif failure == "no-wait":
        root = root[:6] + root[14:]
    elif failure == "wrong-wait":
        root = root[:9] + bytes((4,)) + root[10:]
    elif failure == "external-wait":
        root = bytes((0xF6, 0xF7)) + root
    elif failure == "actor":
        child = bytes((1, 0xFF))
    elif failure == "cycle":
        child = block(bytes((0x14, 0, 4, 0, 0))) + b"\xff"
    elif failure == "auto-child":
        root = confirmation(bytes((0x14, 0, 9, 1)))
    elif failure == "wrong-slot":
        child = block(setter(5, 15, 0, 0) + bytes((0x24, 5, 15, 0, 0))) + b"\xff"
    elif failure == "wrong-type":
        child = block(setter(4, 4, 0, 0) + bytes((0x24, 4, 4, 0, 0))) + b"\xff"
    elif failure == "wrong-setter":
        child = block(setter(5, 15, 0, 0) + bytes((0x24, 4, 15, 0, 0))) + b"\xff"
    elif failure == "side-effect":
        child = block(bytes((5, 1, 7, 1)) + bytes((0x24, 4, 15, 0, 0))) + b"\xff"
    elif failure == "native-child":
        root = bytes((5, 3, 1, 0, 0xFF))
    elif failure == "root-overwrite":
        record = 3
    elif failure == "auto-root":
        record = 9
    elif failure == "second-award":
        child = block(bytes((0x24, 4, 15, 0, 0x24, 4, 15, 0, 0))) + b"\xff"
    else:
        child = block(bytes((0x2D, 4, 15, 0, 0))) + b"\xff"
    program = compile_program(
        rules,
        pickup(4, 0x50, 79) + setter(4, 9, record, 0) + b"\0",
        event=indexed(root, child),
    )
    assert not scripted_collectible_access(program.event_program, 4, 0x50, record, 0)
    snapshot = read_rule_snapshot(
        rules[0], (program,), RamReader(bytearray(2 * 1024 * 1024)).read_memory
    )
    result = evaluate_room_program(
        program,
        RoomId(0, 9),
        rules[0],
        snapshot,
        bytes([255]) * 32,
        (),
        RoomRuleEpoch.Current,
    )
    assert not result.items.list_complete and 4 in result.unresolved_item_slots


def test_nested_child_chain_binds_each_distinct_record(rules):
    events = indexed(
        confirmation(bytes((0x14, 0, 3, 1))),
        block(bytes((0x14, 0, 4, 2, 0))) + b"\xff",
        bytes((7, 6, 0x24, 4, 15, 0, 0xFF)),
    )
    program = compile_program(
        rules, pickup(4, 0x50, 79) + setter(4, 9, 2, 0) + b"\0", event=events
    )
    assert scripted_collectible_access(program.event_program, 4, 0x50, 2, 0)
    assert not scripted_collectible_access(program.event_program, 4, 0x50, 3, 0)
    assert not scripted_collectible_access(program.event_program, 4, 0x50, 4, 0)
    assert [s.entry for s in program.event_program.collectible_rules[0].stages] == [
        0,
        1,
        2,
    ]


@pytest.mark.parametrize(
    "corruption",
    [
        "missing",
        "dispatch",
        "entry",
        "child-record",
        "child-target",
        "cycle",
        "handler",
        "slot",
        "writer",
    ],
)
def test_collectible_proofs_require_bounded_ownership_and_exact_effects(
    rules, corruption
):
    program = compile_program(
        rules, pickup(4, 0x50, 79) + setter(4, 9, 2, 0) + b"\0", event=chain(4, 15)
    )
    raw = asdict(program.event_program)
    if corruption == "missing":
        del raw["collectible_rules"]
        with pytest.raises(KeyError, match="collectible_rules"):
            EventProgram.load(raw)
        return
    proof = raw["collectible_rules"][0]
    if corruption == "dispatch":
        proof["stages"][0]["dispatches"] = ()
    elif corruption == "entry":
        proof["stages"][0]["entry"] = 255
    elif corruption in ("child-record", "child-target"):
        row = list(proof["stages"][0]["starts"][0])
        row[1 if corruption == "child-record" else 2] = (
            2 if corruption == "child-record" else 0
        )
        proof["stages"][0]["starts"] = (tuple(row),)
    elif corruption == "cycle":
        proof["stages"][1]["entry"] = 0
    elif corruption == "handler":
        proof["handler"] = 4
    elif corruption == "slot":
        proof["slot"] = 5
    else:
        writes = list(raw["registry_writes"])
        index = next(
            i
            for i, row in enumerate(writes)
            if row[0] > program.event_program.entries[1]
        )
        writes[index] = (*writes[index][:2], 1, 0, 0)
        raw["registry_writes"] = tuple(writes)
    with pytest.raises(ValueError, match="scripted collectible"):
        replace(program, event_program=EventProgram.load(raw))


@pytest.mark.parametrize("collected", [False, True])
def test_live_source_identity_survives_overwritten_registry_parameters(
    layout, tmp_path, collected
):
    ram = fixture_ram(
        "slus00551_green_herb_after.sav"
        if collected
        else "slus00551_green_herb_before.sav",
        tmp_path,
    )
    observed = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    item = observed.items[0]
    address = 0xB8160 + 12 * item.aot_id
    ram[address] = 9
    struct.pack_into("<HHH", ram, address + 2, 2, 0, 0)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and not result.items
    candidate, record, entry = result.scripted_collectibles[0]
    assert (candidate.item_type, candidate.global_id, candidate.source_address) == (
        item.item_type,
        item.global_id,
        item.source_address,
    )
    assert (record, entry) == (2, 0)
    assert candidate.state is (
        RuntimeItemState.Taken if collected else RuntimeItemState.Unavailable
    )
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    source = next(
        s for s in profile.room_sources if s.source_rdt == "PSX/STAGE1/ROOM1091.RDT"
    )
    rules = (
        profile.tracking_rule_layout,
        json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text()),
    )
    program = compile_program(
        rules,
        pickup(item.aot_id, item.item_type, item.global_id)
        + setter(item.aot_id, 9, 2, 0)
        + b"\0",
        event=chain(item.aot_id, 4),
    )
    profile.room_programs[source.source_rdt] = program
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    tracked = validate_current_room(
        profile, result, (source,), snapshot, bytes(ram[0xC86DC:0xC86FC])
    )
    assert tracked.items.list_complete and not tracked.items.scripted_collectibles
    assert tracked.items.items[0].state is (
        RuntimeItemState.Taken if collected else RuntimeItemState.Available
    )


@pytest.mark.parametrize("collected", [False, True])
@pytest.mark.parametrize("failure", ["pointer", "read", "short", "changed"])
def test_live_candidates_keep_read_and_coherence_failures(
    layout, tmp_path, failure, collected
):
    ram = fixture_ram(
        "slus00551_green_herb_after.sav"
        if collected
        else "slus00551_green_herb_before.sav",
        tmp_path,
    )
    item = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory).items[0]
    address = 0xB8160 + 12 * item.aot_id
    ram[address] = 9
    if failure == "pointer":
        struct.pack_into("<I", ram, address + 8, 0x801FFFF0)
    reader = RamReader(ram)
    calls = 0

    def read(a, width):
        nonlocal calls
        if a == item.source_address and failure in ("read", "short"):
            return MemRead(ok=failure == "short", data=b"", error="disconnected")
        if a == layout.aot_base:
            calls += 1
            if calls == 2 and failure == "changed":
                ram[address + 4] ^= 1
        return reader.read_memory(a, width)

    result = observe_room_items(layout, RoomId(0, 9), read)
    assert not result.ok and not result.scripted_collectibles
    assert result.retry is (failure == "changed")


@pytest.mark.parametrize("collected", [False, True])
def test_pending_award_uses_descriptor_without_needing_script_access(
    layout, tmp_path, collected
):
    ram = fixture_ram(
        "slus00551_green_herb_after.sav"
        if collected
        else "slus00551_green_herb_before.sav",
        tmp_path,
    )
    item = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory).items[0]
    address = 0xB8160 + 12 * item.aot_id
    ram[address] = 9
    struct.pack_into("<I", ram, 0xB7DCC, 0x80000000 + address)
    struct.pack_into(
        "<I",
        ram,
        0xC3000,
        struct.unpack_from("<I", ram, 0xC3000)[0] | layout.pending_item_mask,
    )
    observed = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert observed.ok and not observed.scripted_collectibles
    assert observed.items[0].state is (
        RuntimeItemState.Taken if collected else RuntimeItemState.Available
    )


@pytest.mark.parametrize("aliases", [False, True])
@pytest.mark.parametrize("collected", [False, True])
def test_live_scripted_candidates_use_acquisition_or_agreed_access_when_setup_is_absent(
    layout, tmp_path, aliases, collected
):
    ram = fixture_ram(
        "slus00551_green_herb_after.sav"
        if collected
        else "slus00551_green_herb_before.sav",
        tmp_path,
    )
    item = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory).items[0]
    address = 0xB8160 + 12 * item.aot_id
    ram[address] = 9
    struct.pack_into("<HHH", ram, address + 2, 2, 0, 0)
    observed = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    sources = tuple(s for s in profile.room_sources if s.room == RoomId(0, 9))[:2]
    assert len(sources) == 2
    rules = (
        profile.tracking_rule_layout,
        json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text()),
    )
    good = compile_program(
        rules,
        pickup(item.aot_id, item.item_type, item.global_id)
        + setter(item.aot_id, 9, 2, 0)
        + b"\0",
        event=chain(item.aot_id, 4),
    )
    bad = compile_program(
        rules,
        branch(
            bytes((4, 1, 7, 0)),
            pickup(item.aot_id, item.item_type, item.global_id)
            + setter(item.aot_id, 9, 2, 0),
            b"",
        )
        + b"\0",
        event=indexed(bytes((1, 0xFF))),
    )
    profile.room_programs[sources[0].source_rdt] = good if aliases else bad
    profile.room_programs[sources[1].source_rdt] = bad
    snapshot = read_rule_snapshot(rules[0], (good, bad), RamReader(ram).read_memory)
    expected = evaluate_room_program(
        bad, RoomId(0, 9), rules[0], snapshot, bytes(ram[0xC86DC:0xC86FC]), ()
    )
    assert (
        expected.coverage_complete
        and not expected.items.items
        and not expected.unresolved_item_slots
    )
    tracked = validate_current_room(
        profile,
        observed,
        sources if aliases else (sources[1],),
        snapshot,
        bytes(ram[0xC86DC:0xC86FC]),
    )
    assert tracked.items.list_complete is collected
    if collected:
        assert tracked.items.items == (item,)
    else:
        assert not tracked.items.items


@pytest.mark.parametrize("bound", [False, True])
def test_live_taken_candidates_keep_missing_or_incomplete_source_coverage(
    layout, tmp_path, bound
):
    ram = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    ram[0xB819C] = 9
    observed = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert (
        observed.ok
        and observed.scripted_collectibles[0][0].state is RuntimeItemState.Taken
    )
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    source = next(
        s for s in profile.room_sources if s.source_rdt == "PSX/STAGE1/ROOM1091.RDT"
    )
    program = replace(profile.room_programs[source.source_rdt], coverage_complete=False)
    profile.room_programs[source.source_rdt] = program
    snapshot = read_rule_snapshot(
        profile.tracking_rule_layout, (program,), RamReader(ram).read_memory
    )
    result = validate_current_room(
        profile,
        observed,
        (source,) if bound else (),
        snapshot,
        bytes(ram[0xC86DC:0xC86FC]),
    )
    assert not result.items.list_complete


@pytest.mark.parametrize("supported", [False, True])
def test_cached_collectible_refresh_uses_fresh_flags_after_reversal(
    tmp_path, supported
):
    from track import PollStatus, poll_once

    from games.re1.tracking_engine import refresh_visited_room
    from tracker.exploration_state import Tracker

    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    assert (
        poll_once(profile, Tracker(), reader.read_memory).status is PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    cached = replace(
        cached,
        sources=tuple(
            replace(s, cache_complete=False, door_cache_complete=False)
            for s in cached.sources
        ),
    )
    rules = (
        profile.tracking_rule_layout,
        json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text()),
    )
    original = cached.observation.items[0]
    program = compile_program(
        rules,
        pickup(original.aot_id, original.item_type, original.global_id)
        + setter(original.aot_id, 9, 2, 0)
        + b"\0",
        event=chain(original.aot_id, 4) if supported else indexed(bytes((1, 0xFF))),
    )
    for source in cached.sources:
        profile.room_programs[source.source_rdt] = program
    flag = rules[0].acquisition.flag(original.item_type, original.global_id)
    address = flag.address - 0x80000000
    for taken in (False, True, False):
        ram[address] = ram[address] & ~flag.mask if taken else ram[address] | flag.mask
        snapshot = read_rule_snapshot(rules[0], (program,), reader.read_memory)
        tracked = refresh_visited_room(
            profile, cached, cached.context, snapshot, bytes(ram[0xC86DC:0xC86FC])
        )
        assert tracked.items.list_complete is (supported or taken)
        if supported or taken:
            assert len(tracked.items.items) == 1
            assert tracked.items.items[0].state is (
                RuntimeItemState.Taken if taken else RuntimeItemState.Available
            )
        else:
            assert not tracked.items.items


@pytest.mark.parametrize("taken", [False, True])
def test_poll_retries_when_scripted_acquisition_changes_between_snapshots(
    tmp_path, taken
):
    from track import PollStatus, poll_once

    from tracker.exploration_state import Tracker

    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram(
        "slus00551_green_herb_after.sav"
        if taken
        else "slus00551_green_herb_before.sav",
        tmp_path,
    )
    layout = profile.runtime_room_layout
    ram[0xB819C] = 9
    reader = RamReader(ram)
    calls = 0

    def read(address, width):
        nonlocal calls
        if (address, width) == (layout.acquisition_flags_address, 32):
            calls += 1
            if calls == 3:
                # The observer completed its two coherent reads before the
                # poll's later snapshot sees an earlier/later acquisition bit.
                ram[0xC86EA] ^= 1
        return reader.read_memory(address, width)

    tracker = Tracker()
    result = poll_once(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "pickup changed during room read"
    assert not tracker.rooms


def test_full_record_chain_and_reused_child_records_cannot_grant_access(rules):
    for records in (tuple(range(8)), (3, 3)):
        events = indexed(
            *(
                block(bytes((0x14, 0, record, index + 1, 0))) + b"\xff"
                for index, record in enumerate(records)
            ),
            bytes((7, 6, 0x24, 4, 15, 0, 0xFF)),
        )
        program = compile_program(
            rules, pickup(4, 0x50, 79) + setter(4, 9, 2, 0) + b"\0", event=events
        )
        assert not any(
            rule.stages[0].entry == 0
            for rule in program.event_program.collectible_rules
        )
        assert not scripted_collectible_access(program.event_program, 4, 0x50, 2, 0)


def test_single_command_award_skips_unsupported_tail(rules):
    program = compile_program(
        rules,
        pickup(4, 0x50, 79) + setter(4, 9, 2, 0) + b"\0",
        event=indexed(bytes((7, 10, 0x24, 4, 15, 0, 0x13, 4, 0, 129, 0xFF))),
    )
    assert scripted_collectible_access(program.event_program, 4, 0x50, 2, 0)
