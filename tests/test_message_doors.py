"""RE1-DOORS-003: synthetic blocked passage and fresh state regressions."""

import json
import struct
from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import REPO, RamReader, fixture_ram
from test_tracking_rules import branch, compile_program, door, guard
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from games.re1.room_items import observe_room_items
from games.re1.tracking_engine import refresh_visited_room
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)
from tracker.exploration_state import RoomCompletion, Tracker
from ui.map_view import map_state

pytest_plugins = ("test_tracking_rules", "test_room_items")


def calculate(program, rules, epoch):
    ram = bytearray(2 * 1024 * 1024)
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error and program.coverage_complete
    return evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("section", ["init", "main", "ordered", "single"])
def test_message_setters_preserve_blocked_door_identity(rules, epoch, section):
    original = door(2, 8, 0x34)
    setter = bytes((0x13, 2, 2, 129))
    init, main, event = original + pickup(0, 0x44, 111), b"\0", bytes(4)
    if section == "init":
        init += setter
    elif section == "main":
        main = setter + b"\0"
    else:
        init += setter + bytes((0x14, 0, 0, 0))
        # The event can be pending or finished. Both histories must already
        # block passage; changing message parameters cannot change the door.
        setter = bytes((0x12, 2, 2, 129)) + struct.pack("<HHH", 143, 255, 0)
        event = indexed(
            (
                block(setter + b"\0")
                if section == "ordered"
                else bytes((7, len(setter) + 2)) + setter
            )
            + b"\xff"
        )
    result = calculate(compile_program(rules, init + b"\0", main, event), rules, epoch)
    assert result.items.list_complete and len(result.items.items) == 1
    assert not result.doors and not result.unresolved_door_slots
    assert result.disabled_doors == ((2, original[:25] + bytes((129,))),)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("ordered", [True, False])
def test_pending_message_event_cannot_choose_blocked_over_open(rules, epoch, ordered):
    setter = bytes((0x13, 2, 2, 1))
    event = indexed(
        (block(setter + b"\0") if ordered else bytes((7, 6)) + setter) + b"\xff"
    )
    program = compile_program(
        rules, door(2, 8, 0x34) + bytes((0x14, 0, 0, 0, 0)), event=event
    )
    result = calculate(program, rules, epoch)
    assert result.unresolved_door_slots == (2,)
    assert not result.doors and not result.disabled_doors


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_different_message_parameters_do_not_invent_door_or_item_effects(rules, epoch):
    code = (
        door(2, 8, 0x34)
        + branch(
            bytes((6, 2, 0, 1)),
            bytes((0x12, 2, 2, 129)) + struct.pack("<HHH", 143, 255, 0),
            bytes((0x12, 2, 2, 129)) + struct.pack("<HHH", 148, 127, 65535),
        )
        + pickup(0, 0x44, 111)
        + b"\0"
    )
    result = calculate(compile_program(rules, code), rules, epoch)
    assert result.items.list_complete and not result.unresolved_door_slots
    assert len(result.disabled_doors) == 1 and not result.doors


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("conflict", ["handler", "target", "missing-source"])
def test_blocked_classification_requires_all_alternatives_to_agree(
    rules, epoch, conflict
):
    setter = bytes((0x13, 2, 2, 129))
    if conflict == "handler":
        code = door(2, 8, 0x34) + guard(bytes((6, 2, 0, 1)), setter)
    elif conflict == "target":
        code = branch(bytes((6, 2, 0, 1)), door(2, 8, 0x34), door(2, 10, 0x34))
        code += setter
    else:
        code = guard(bytes((6, 2, 0, 1)), door(2, 8, 0x34)) + setter
    result = calculate(compile_program(rules, code + b"\0"), rules, epoch)
    assert not result.doors and not result.disabled_doors
    assert result.unresolved_door_slots == (2,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_message_handler_cannot_close_incomplete_source_coverage(rules, epoch):
    program = compile_program(rules, door(2, 8, 0x34) + bytes((0x13, 2, 2, 129, 0)))
    snapshot = read_rule_snapshot(
        rules[0], (program,), RamReader(bytearray(2 * 1024 * 1024)).read_memory
    )
    assert program.coverage_complete and not snapshot.error
    result = evaluate_room_program(
        replace(program, coverage_complete=False, reentry_coverage_complete=False),
        RoomId(0, 9),
        rules[0],
        snapshot,
        bytes([255]) * 32,
        (),
        epoch,
    )
    assert result.unresolved_door_slots == (2,) and not result.disabled_doors
    assert not result.items.list_complete


@pytest.mark.parametrize("mode", [0, 129])
def test_live_message_door_preserves_source_geometry_without_granting_items(
    layout, tmp_path, mode
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    original = observe_room_items(layout, RoomId(0, 9), reader.read_memory)
    raw = dict(original.active_doors)[1]
    ram[0xB816C : 0xB816C + 2] = bytes((2, mode))
    struct.pack_into("<HHH", ram, 0xB816E, 143, 255, 0)
    before = bytes(ram)
    result = observe_room_items(layout, RoomId(0, 9), reader.read_memory)
    assert result.ok and result.list_complete and result.items == original.items
    assert result.disabled_doors == ((1, raw[:25] + bytes((mode,))),)
    assert result.message_door_slots == (1,)
    assert len(result.active_doors) == 4 and bytes(ram) == before


@pytest.mark.parametrize("change", ["pointer", "slot", "opcode", "truncated", "read"])
def test_invalid_live_message_sources_cannot_create_a_blocked_marker(
    layout, tmp_path, change
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 2
    pointer = struct.unpack_from("<I", ram, 0xB8174)[0] - 0x80000000
    reader = RamReader(ram)
    if change == "pointer":
        struct.pack_into("<I", ram, 0xB8174, 0x80121E94)
    elif change == "slot":
        ram[pointer - 1] = 3
    elif change == "opcode":
        ram[pointer - 2] = 0x13
    elif change == "truncated":
        end = struct.unpack_from("<I", ram, 0x121C00 + 0x6C)[0]
        source = end - 18
        ram[source - 0x80000000 : end - 0x80000000] = bytes((0x0C, 1)) + bytes(16)
        struct.pack_into("<I", ram, 0xB8174, source + 2)
    else:
        reader.fail_address = 0x80000000 + pointer - 2
    result = observe_room_items(layout, RoomId(0, 9), reader.read_memory)
    assert not result.ok and not result.disabled_doors
    assert not result.message_door_slots


@pytest.mark.parametrize("opcode", [0x0D, 0x18])
def test_other_message_creators_cannot_supply_door_geometry(layout, tmp_path, opcode):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 2
    pointer = struct.unpack_from("<I", ram, 0xB8174)[0] - 0x80000000
    ram[pointer - 2] = opcode
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and not result.disabled_doors


@pytest.mark.parametrize("pending", [0x400, 0x800])
def test_pending_forced_award_is_not_hidden_by_a_message_door(
    layout, tmp_path, pending
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 2
    struct.pack_into("<I", ram, 0xB7DCC, 0x800B816C)
    flags = struct.unpack_from("<I", ram, 0xC3000)[0]
    struct.pack_into("<I", ram, 0xC3000, flags | pending)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not result.ok and not result.disabled_doors
    assert "pickup has no item descriptor" in result.error


def test_live_message_door_changes_and_unlock_reversal_reach_map_markers(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    for handler, unlocked, state in (
        (2, False, "BLOCKED"),
        (2, True, "BLOCKED"),
        (1, True, "OPEN"),
        (2, True, "BLOCKED"),
        (1, False, "LOCKED"),
        (2, False, "BLOCKED"),
    ):
        ram[0xB816C] = handler
        ram[0xC86B7] = ram[0xC86B7] & ~8 | (8 if unlocked else 0)
        assert (
            poll_once(profile, tracker, RamReader(ram).read_memory).status
            == PollStatus.Display
        )
        record = tracker.room_state(RoomId(0, 9))
        assert record.doors_complete and record.completion is RoomCompletion.Incomplete
        snapshot = map_state(tracker)
        assert [room["id"] for room in snapshot["rooms"]] == ["09"]
        marker = next(
            d
            for d in snapshot["doors"]
            if d["source"] == "00-09" and d["target"] == "00-14"
        )
        assert marker["state"] == state
        if handler == 2:
            assert marker["label"] == "Passage is unavailable"
    assert any(
        set(marker["rooms"]) == {"09", "14"}
        for marker in profile.map_layout.document["areas"][0]["doors"]
    )


def test_cached_room_reconstructs_message_and_open_handlers_after_flag_reversal(
    tmp_path,
):
    path = REPO / "profiles/re1_directors_cut_slus00551.json"
    profile = Re1Profile.load(path)
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    assert (
        poll_once(profile, Tracker(), reader.read_memory).status == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    cached = replace(
        cached,
        sources=tuple(
            replace(s, cache_complete=False, door_cache_complete=False)
            for s in cached.sources
        ),
    )
    rules = profile.tracking_rule_layout, json.loads(path.read_text())
    program = compile_program(
        rules,
        door(1, 0x14, 0x34)
        + branch(
            bytes((4, 1, 7, 1)), bytes((0x13, 1, 2, 129)), bytes((0x13, 1, 1, 129))
        )
        + pickup(5, 0x44, 111)
        + b"\0",
    )
    for source in cached.sources:
        profile.room_programs[source.source_rdt] = program
    address, mask = rules[0].flag(1, 7)
    for enabled in (False, True, False):
        ram[address - 0x80000000] = ram[address - 0x80000000] & ~mask | (
            mask if enabled else 0
        )
        snapshot = read_rule_snapshot(rules[0], (program,), reader.read_memory)
        assert not snapshot.error
        result = refresh_visited_room(
            profile, cached, cached.context, snapshot, bytes(ram[0xC86DC:0xC86FC])
        )
        assert result.doors_complete and result.items.list_complete
        assert len(result.doors) == int(enabled)
        assert len(result.disabled_doors) == int(not enabled)
        assert (result.doors or result.disabled_doors)[0][1][15] == 0x14


@pytest.mark.parametrize("failure", ["reset", "source-coverage"])
def test_message_evidence_does_not_bypass_reset_or_incomplete_source(tmp_path, failure):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 0 if failure == "reset" else 2
    if failure == "source-coverage":
        for name, program in tuple(profile.room_programs.items()):
            if name.endswith("1091.RDT"):
                profile.room_programs[name] = replace(program, coverage_complete=False)
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(ram).read_memory).status
        == PollStatus.Display
    )
    assert not tracker.room_state(RoomId(0, 9)).doors_complete


def test_registry_change_discards_live_message_evidence(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 2
    reads = 0

    def changing_reader(address, length):
        nonlocal reads
        if address == layout.aot_base:
            reads += 1
            if reads == 2:
                ram[0xB816C] = 1
        return RamReader(ram).read_memory(address, length)

    result = observe_room_items(layout, RoomId(0, 9), changing_reader)
    assert not result.ok and result.retry
    assert not result.message_door_slots and not result.disabled_doors


def test_message_evidence_requires_a_successful_validated_blocked_descriptor(
    layout, tmp_path
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB816C] = 2
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.message_door_slots == (1,)
    for changes in (
        {"message_door_slots": (1, 1)},
        {"message_door_slots": (-1,)},
        {"disabled_doors": ()},
        {"ok": False},
    ):
        with pytest.raises(AssertionError):
            replace(result, **changes)
