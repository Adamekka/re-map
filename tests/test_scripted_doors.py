"""RE1-DOORS-006: synthetic access proofs, never natural traversal evidence."""

import json
import struct
from dataclasses import asdict, replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import REPO, RamReader, fixture_ram
from test_tracking_rules import branch, compile_program, door, guard

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re1.door_state import DoorState, parse_door
from games.re1.event_state import EventProgram
from games.re1.re1_profile import Re1Profile
from games.re1.room_items import observe_room_items
from games.re1.scripted_doors import ScriptedDoorAccess, scripted_door_access
from games.re1.tracking_engine import refresh_visited_room, validate_current_room
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)

pytest_plugins = ("test_tracking_rules", "test_room_items")


def setter(slot, entry):
    return bytes((0x12, slot, 9, 129)) + struct.pack("<HHH", 9, entry, 0)


def confirmation(slot, character=False):
    body = (bytes((8, 9, 0, 0)) if character else b"") + bytes((0x24, slot, 1, 0))
    return (
        bytes((7, 6, 0x0B, 0x82, 255, 0))
        + bytes((0xFC, 6, 6, 5, 2, 128, 0xFE, 0xFD))
        + block(guard(bytes((6, 5, 0, 0)), body) + b"\0")
        + b"\xff"
    )


def calculate(program, rules, epoch):
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error and program.coverage_complete
    return evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("character", [False, True])
def test_confirmed_delegation_preserves_geometry_and_real_lock_state(
    rules, epoch, character
):
    original = door(2, 8, 0x34)
    program = compile_program(
        rules,
        original + setter(2, 0) + pickup(0, 0x44, 111) + b"\0",
        event=indexed(confirmation(2, character)),
    )
    result = calculate(program, rules, epoch)
    assert result.items.list_complete and len(result.items.items) == 1
    assert result.doors == ((2, original[:25] + bytes((129,))),)
    assert not result.disabled_doors and not result.unresolved_door_slots
    for unlocked, expected in (
        (False, DoorState.LOCKED),
        (True, DoorState.OPEN),
        (False, DoorState.LOCKED),
    ):
        flags = bytearray(8)
        flags[3] = 4 if unlocked else 0
        observed = parse_door(2, result.doors[0][1], RoomId(0, 9), bytes(flags), 0, 0)
        assert observed.state is expected
        assert (observed.x, observed.z, observed.width, observed.depth) == (
            -100,
            300,
            500,
            40,
        )
        assert observed.target == RoomId(0, 8)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("wait", ["completion", "external", "counter"])
def test_message_only_events_prove_blocked_passage(rules, epoch, wait):
    code = bytes((7, 6, 0x0B, 0x80, 255, 0))
    code += {
        "completion": bytes((0xFC, 6, 6, 5, 2, 128, 0xFE, 0xFD)),
        "external": bytes((0xF6, 0xF7)),
        "counter": bytes((0xF8, 0xF9, 1, 0)),
    }[wait]
    code += bytes((7, 6, 5, 6, 23, 0, 0xFF))
    program = compile_program(
        rules, door(2, 8, 0x34) + setter(2, 0) + b"\0", event=indexed(code)
    )
    result = calculate(program, rules, epoch)
    assert not result.doors and not result.unresolved_door_slots
    assert result.disabled_doors == ((2, door(2, 8, 0x34)[:25] + bytes((129,))),)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize(
    "change",
    [
        "story",
        "inventory",
        "missing-prompt",
        "missing-wait",
        "external-wait",
        "overlap",
        "child",
        "non-door",
    ],
)
def test_a_possible_callback_is_not_an_access_proof(rules, epoch, change):
    event = confirmation(2)
    if change in ("story", "inventory"):
        condition = bytes((4, 1, 31, 0)) if change == "story" else bytes((0x10, 0x34))
        event = (
            event[:14]
            + block(guard(condition, bytes((0x24, 2, 1, 0))) + b"\0")
            + b"\xff"
        )
    elif change == "missing-prompt":
        event = event[6:]
    elif change == "missing-wait":
        event = event[:6] + event[14:]
    elif change == "external-wait":
        event = bytes((0xF6, 0xF7)) + event
    elif change == "overlap":
        event = bytes((7, 3)) + event[2:]
    elif change == "child":
        event = bytes((5, 9, 1, 0, 0xFF))
    else:
        event = event[:-1] + bytes((7, 6, 0x13, 2, 1, 129, 0xFF))
    events = indexed(event, confirmation(2)) if change == "child" else indexed(event)
    program = compile_program(
        rules, door(2, 8, 0x34) + setter(2, 0) + b"\0", event=events
    )
    assert not any(rule.entry == 0 for rule in program.event_program.door_rules)
    result = calculate(program, rules, epoch)
    assert result.unresolved_door_slots == (2,)
    assert not result.doors and not result.disabled_doors


@pytest.mark.parametrize("control,key", [(0x40, 0x34), (0x80, 0x33), (0xC0, 0xFE)])
def test_character_changes_cannot_reuse_character_dependent_lock_inputs(
    rules, control, key
):
    raw = bytearray(door(2, 8, key))
    raw[14] = control
    program = compile_program(
        rules, bytes(raw) + setter(2, 0) + b"\0", event=indexed(confirmation(2, True))
    )
    assert (
        scripted_door_access(program.event_program, 2, 0, bytes(raw))
        is ScriptedDoorAccess.Unresolved
    )
    assert calculate(program, rules, RoomRuleEpoch.Reentry).unresolved_door_slots == (
        2,
    )


def test_delegation_to_a_different_slot_does_not_supply_access(rules):
    program = compile_program(
        rules,
        door(1, 8, 0x34) + door(2, 10, 0x33) + setter(2, 0) + b"\0",
        event=indexed(confirmation(1)),
    )
    result = calculate(program, rules, RoomRuleEpoch.Reentry)
    assert result.unresolved_door_slots == (2,)
    assert [slot for slot, _ in result.doors] == [1]


def test_single_dispatch_uses_one_command_and_skips_a_larger_span(rules):
    event = bytes((7, 10, 0x24, 2, 1, 0, 0x13, 2, 0, 129, 0xFF))
    program = compile_program(
        rules, door(2, 8, 0x34) + setter(2, 0) + b"\0", event=indexed(event)
    )
    result = calculate(program, rules, RoomRuleEpoch.Current)
    assert [slot for slot, _ in result.doors] == [2]
    assert not result.disabled_doors and not result.unresolved_door_slots
    assert program.event_program.door_rules[0].door_slots == (2,)


@pytest.mark.parametrize(
    "corruption", ["dispatch", "slot", "character", "entry", "missing"]
)
def test_door_proof_schema_and_owned_effects_are_mandatory(rules, corruption):
    program = compile_program(
        rules, door(2, 8, 0x34) + setter(2, 0) + b"\0", event=indexed(confirmation(2))
    )
    raw = asdict(program.event_program)
    if corruption == "missing":
        del raw["door_rules"]
        with pytest.raises(KeyError, match="door_rules"):
            EventProgram.load(raw)
        return
    if corruption == "dispatch":
        raw["door_rules"][0]["dispatches"] = ()
    elif corruption == "entry":
        raw["door_rules"][0]["entry"] = 255
    elif corruption == "slot":
        raw["door_rules"][0]["door_slots"] = (1,)
    else:
        raw["door_rules"][0]["changes_character"] = True
    with pytest.raises(ValueError, match="scripted door"):
        replace(program, event_program=EventProgram.load(raw))


def test_live_script_sources_are_candidates_until_the_bound_profile_proves_access(
    layout, tmp_path
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 9
    struct.pack_into("<H", ram, 0xB8170, 0)
    before = bytes(ram)
    observed = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert observed.ok and observed.scripted_doors[0][0::2] == (1, 0)
    assert 1 not in {
        slot for slot, _ in observed.active_doors + observed.disabled_doors
    }
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    source = next(
        s for s in profile.room_sources if s.source_rdt == "PSX/STAGE1/ROOM1091.RDT"
    )
    rules = (
        profile.tracking_rule_layout,
        json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text()),
    )
    for code, active in (
        (confirmation(1), True),
        (bytes((7, 6, 0x0B, 0x80, 255, 0, 0xFF)), False),
    ):
        program = compile_program(
            rules, door(1, 0x14, 0x34) + setter(1, 0) + b"\0", event=indexed(code)
        )
        profile.room_programs[source.source_rdt] = program
        snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
        tracked = validate_current_room(
            profile, observed, (source,), snapshot, bytes(ram[0xC86DC:0xC86FC])
        )
        target = tracked.doors if active else tracked.disabled_doors
        assert 1 in {slot for slot, _ in target}
        assert tracked.doors_complete and not tracked.items.scripted_doors
    assert bytes(ram) == before


def test_cached_script_access_rechecks_progress_after_loaded_state_reversal(tmp_path):
    from track import PollStatus, poll_once

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
    program = compile_program(
        rules,
        door(1, 0x14, 0x34)
        + branch(bytes((4, 1, 7, 0)), setter(1, 0), setter(1, 1))
        + b"\0",
        event=indexed(confirmation(1), bytes((7, 6, 0x0B, 0x80, 255, 0, 0xFF))),
    )
    for source in cached.sources:
        profile.room_programs[source.source_rdt] = program
    address, mask = rules[0].flag(1, 7)
    for value, delegated in ((mask, True), (0, False), (mask, True)):
        ram[address - 0x80000000] = ram[address - 0x80000000] & ~mask | value
        snapshot = read_rule_snapshot(rules[0], (program,), reader.read_memory)
        tracked = refresh_visited_room(
            profile, cached, cached.context, snapshot, bytes(ram[0xC86DC:0xC86FC])
        )
        assert tracked.doors_complete
        assert bool(tracked.doors) is delegated
        assert bool(tracked.disabled_doors) is not delegated


def test_alias_disagreement_cannot_publish_a_live_scripted_door(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 9
    struct.pack_into("<H", ram, 0xB8170, 0)
    observed = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    sources = tuple(
        s
        for s in profile.room_sources
        if s.source_rdt in ("PSX/STAGE1/ROOM1090.RDT", "PSX/STAGE1/ROOM1091.RDT")
    )
    assert len(sources) == 2
    rules = (
        profile.tracking_rule_layout,
        json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text()),
    )
    for source, code in zip(sources, (confirmation(1), b"\xff"), strict=True):
        profile.room_programs[source.source_rdt] = compile_program(
            rules, door(1, 0x14, 0x34) + setter(1, 0) + b"\0", event=indexed(code)
        )
    snapshot = read_rule_snapshot(
        rules[0],
        tuple(profile.room_programs[s.source_rdt] for s in sources),
        RamReader(ram).read_memory,
    )
    tracked = validate_current_room(
        profile, observed, sources, snapshot, bytes(ram[0xC86DC:0xC86FC])
    )
    assert not tracked.doors_complete
    assert 1 not in {slot for slot, _ in tracked.doors + tracked.disabled_doors}


def test_unresolved_live_access_prevents_coverage_when_current_rules_see_no_door(
    layout, tmp_path
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 9
    struct.pack_into("<H", ram, 0xB8170, 0)
    observed = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    source = next(
        s for s in profile.room_sources if s.source_rdt == "PSX/STAGE1/ROOM1091.RDT"
    )
    rules = (
        profile.tracking_rule_layout,
        json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text()),
    )
    # A changed setup guard can reconstruct absence while its earlier registry
    # descriptor is still live. An unsupported target supplies no access proof.
    program = compile_program(
        rules,
        branch(bytes((4, 1, 7, 0)), door(1, 0x14, 0x34) + setter(1, 0), b"") + b"\0",
        event=indexed(bytes((1, 0xFF))),
    )
    profile.room_programs[source.source_rdt] = program
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    expected = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes(ram[0xC86DC:0xC86FC]), ()
    )
    assert expected.coverage_complete
    assert not expected.doors + expected.disabled_doors + expected.unresolved_door_slots
    assert not program.event_program.door_rules
    tracked = validate_current_room(
        profile, observed, (source,), snapshot, bytes(ram[0xC86DC:0xC86FC])
    )
    assert not tracked.doors_complete


@pytest.mark.parametrize("failure", ["pointer", "pending", "short", "read", "changed"])
def test_live_script_candidates_cannot_bypass_read_and_award_failures(
    layout, tmp_path, failure
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 9
    reader = RamReader(ram)
    source = struct.unpack_from("<I", ram, 0xB8174)[0] - 2
    if failure == "pointer":
        struct.pack_into("<I", ram, 0xB8174, 0x801FFFF0)
    elif failure == "pending":
        struct.pack_into("<I", ram, 0xB7DCC, 0x800B816C)
        main = struct.unpack_from("<I", ram, 0xC3000)[0]
        struct.pack_into("<I", ram, 0xC3000, main | layout.pending_item_mask)
    calls = 0

    def read(address, width):
        nonlocal calls
        if address == source and failure in ("short", "read"):
            return (
                MemRead(ok=True, data=b"", error="")
                if failure == "short"
                else MemRead(ok=False, data=b"", error="disconnected")
            )
        if address == layout.aot_base and failure == "changed":
            calls += 1
            if calls == 2:
                ram[0xB8170] ^= 1
        return reader.read_memory(address, width)

    result = observe_room_items(layout, RoomId(0, 9), read)
    assert not result.ok and not result.scripted_doors and not result.list_complete
    assert result.retry is (failure == "changed")
