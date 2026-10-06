"""RE1-SCD-015: synthetic forced callbacks, aliases and fresh unlock reversal."""

from dataclasses import replace

import pytest
from test_cache_metadata import indexed_event, pickup
from test_live_items import RamReader, fixture_ram
from test_tracking_rules import REPO, branch, compile_program, door, evaluate, guard
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import RuleCommand, RuleProcedure, read_rule_snapshot
from tracker.exploration_state import RoomCompletion, Tracker
from ui.map_view import map_state

pytest_plugins = ("test_tracking_rules",)


@pytest.mark.parametrize("op", [0x24, 0x2D])
@pytest.mark.parametrize("section", ["init", "main", "events"])
def test_forced_door_preserves_definition_without_a_mutable_slot_barrier(
    rules, op, section
):
    callback = bytes((op, 0, 1, 0))
    init = door(0, 8, 0x34) + pickup(1, 0x44, 111)
    program = compile_program(
        rules,
        init + (guard(callback, b"") if section == "init" else b"") + b"\0",
        guard(callback, b"") + b"\0" if section == "main" else b"\0",
        indexed_event(bytes((7, 6)) + callback + b"\xff")
        if section == "events"
        else bytes(4),
    )
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    result = evaluate(program, rules, ram)
    assert program.mutable_slots == ()
    assert result.doors == ((0, door(0, 8, 0x34)),)
    assert not result.unresolved_door_slots
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Available
    assert bytes(ram) == before


@pytest.mark.parametrize("op", [0x24, 0x2D])
def test_forced_dispatch_preserves_a_disabled_door_and_its_mode(rules, op):
    code = (
        door(0, 8, 0x34)
        + bytes((0x13, 0, 0, 0x81))
        + guard(bytes((op, 0, 1, 0)), b"")
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    expected = bytearray(door(0, 8, 0x34))
    expected[25] = 0x81
    assert result.disabled_doors == ((0, bytes(expected)),)
    assert result.doors == () and not result.unresolved_door_slots


@pytest.mark.parametrize("op,item_type", [(0x24, 0x44), (0x2D, 0x26)])
def test_command_return_selects_the_if_arm_independently_of_callback_return(
    rules, op, item_type
):
    code = (
        door(0, 8, 0x34)
        + branch(bytes((op, 0, 1, 0)), pickup(1, 0x44, 111), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and result.items.items[0].item_type == item_type
    assert len(result.doors) == 1


@pytest.mark.parametrize("index", [0, 31, 32, 63])
@pytest.mark.parametrize("op", [0x24, 0x2D])
def test_forced_door_cannot_keep_a_false_unlock_shadow_or_clear_a_true_one(
    rules, index, op
):
    raw = bytearray(door(0, 8, 0xFE))
    raw[14] = 0x80 | index
    code = (
        bytes(raw)
        + bytes((5, 2, index, 1, 5, 2, (index + 1) % 64, 0))
        + guard(bytes((op, 0, 1, 0)), b"")
        + guard(bytes((4, 2, index, 1)), pickup(1, 0x26, 63))
        + guard(bytes((4, 2, (index + 1) % 64, 0)), pickup(2, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (1,)
    assert [item.aot_id for item in result.items.items] == [2]
    assert result.doors == ((0, bytes(raw)),)
    code = code.replace(bytes((5, 2, index, 1)), bytes((5, 2, index, 0)), 1)
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert [item.aot_id for item in result.items.items] == [2]


def test_unlocked_source_does_not_invalidate_an_unrelated_lock_shadow(rules):
    raw = bytearray(door(0, 8, 0x34))
    raw[14] = 5
    code = (
        bytes(raw)
        + bytes((5, 2, 5, 1, 0x24, 0, 1, 0))
        + guard(bytes((4, 2, 5, 1)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and len(result.items.items) == 1


@pytest.mark.parametrize("unlocked", [False, True])
def test_existing_unlock_in_fresh_ram_survives_without_a_script_shadow(rules, unlocked):
    code = (
        door(0, 8, 0x34)
        + bytes((0x24, 0, 1, 0))
        + guard(bytes((4, 2, 5, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(2, 5)
    ram[address - 0x80000000] = mask if unlocked else 0
    result = evaluate(compile_program(rules, code), rules, ram)
    assert result.items.list_complete == unlocked
    assert result.unresolved_item_slots == (() if unlocked else (1,))
    if unlocked:
        assert len(result.items.items) == 1


def test_fresh_unlock_does_not_override_a_preceding_script_clear(rules):
    code = (
        door(0, 8, 0x34)
        + bytes((5, 2, 5, 1, 0x24, 0, 1, 0))
        + guard(bytes((4, 2, 5, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(2, 5)
    ram[address - 0x80000000] = mask
    result = evaluate(compile_program(rules, code), rules, ram)
    assert result.unresolved_item_slots == (1,)


@pytest.mark.parametrize("old", [0, 1])
def test_other_side_door_preserves_the_lock_shadow(rules, old):
    code = (
        door(0, 8, 0xFF)
        + bytes((5, 2, 5, old, 0x24, 0, 1, 0))
        + guard(bytes((4, 2, 5, old)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and len(result.items.items) == 1


def test_forced_callback_snapshot_reads_all_unlock_bytes_and_rejects_failed_reads(
    rules,
):
    program = compile_program(rules, door(0, 8, 0x34) + bytes((0x24, 0, 1, 0, 0)))
    reader = RamReader(bytearray(2 * 1024 * 1024))
    before = read_rule_snapshot(rules[0], (program,), reader.read_memory)
    base = rules[0].flag_bases[2]
    assert set(range(base, base + 8)) <= dict(before.values).keys()

    reader.fail_address = base + 7
    after = read_rule_snapshot(rules[0], (program,), reader.read_memory)
    assert "injected read failure" in after.error and after.values == ()


def test_unguarded_got_item_stops_the_procedure_after_its_zero_return(rules):
    code = door(0, 8, 0x34) + bytes((0x2D, 0, 1, 0)) + pickup(1, 0x44, 111) + b"\0"
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and result.items.items == ()
    assert result.doors == ((0, door(0, 8, 0x34)),)


@pytest.mark.parametrize("old", [0, 1])
def test_traversal_pending_bit_is_conditional_and_preserves_an_existing_set(rules, old):
    code = (
        door(0, 8, 0x34)
        + bytes((5, 5, 6, old, 0x24, 0, 1, 0))
        + guard(bytes((4, 5, 6, old)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete == (old == 0)
    assert result.unresolved_item_slots == (() if old == 0 else (1,))


@pytest.mark.parametrize("index", [0, 15, 16, 31])
def test_message_backup_and_transition_clear_forget_both_local_halfwords(rules, index):
    code = (
        door(0, 8, 0x34)
        + bytes((5, 6, index, 0, 0x24, 0, 1, 0))
        + guard(bytes((4, 6, index, 0)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (1,)
    assert not result.unresolved_door_slots


@pytest.mark.parametrize("alias", ["message", "key", "local"])
def test_callback_forgets_overlapping_word_shadows(rules, alias):
    address = (
        rules[0].flag_bases[6]
        if alias == "local"
        else rules[0].byte_variables_base + (4 if alias == "message" else 6)
    )
    scoped = replace(rules[0], word_variables_base=address), rules[1]
    code = (
        door(0, 8, 0x34)
        + bytes((0x31, 0, 1, 1, 0x24, 0, 1, 0))
        + guard(bytes((7, 0, 0, 0, 1, 1)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(scoped, code), scoped, bytearray(2 * 1024 * 1024))
    assert result.unresolved_item_slots == (1,)


@pytest.mark.parametrize("initializer", [b"", pickup(0, 0x44, 111)])
def test_forced_door_requires_a_door_source_on_every_possible_path(rules, initializer):
    code = initializer + bytes((0x24, 0, 1, 0)) + pickup(1, 0x44, 111) + b"\0"
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete
    assert result.items.coverage_reason == "Room script coverage is incomplete."
    assert 1 in result.unresolved_item_slots


def test_one_missing_source_path_prevents_forced_callback_reconstruction(rules):
    code = (
        guard(bytes((6, 2, 0, 1)), door(0, 8, 0x34))
        + bytes((0x24, 0, 1, 0))
        + pickup(1, 0x44, 111)
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete and result.unresolved_item_slots == (1,)
    assert result.unresolved_door_slots == (0,)


@pytest.mark.parametrize("old", [0, 1])
def test_got_item_updates_pending_bits_after_the_door_callback(rules, old):
    code = (
        door(0, 8, 0x34)
        + bytes((5, 5, 20, old, 5, 5, 21, 1))
        + guard(bytes((0x2D, 0, 1, 0)), b"")
        + guard(bytes((4, 5, 21, 0, 4, 5, 20, 1 - old)), pickup(1, 0x44, 111))
        + b"\0"
    )
    result = evaluate(compile_program(rules, code), rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete and len(result.items.items) == 1


def test_possible_event_source_replacement_still_prevents_door_reconstruction(rules):
    replacement = door(0, 10, 0x35)
    event = indexed_event(
        bytes((7, len(replacement) + 2))
        + replacement
        + bytes((7, 6, 0x24, 0, 1, 0, 0xFF))
    )
    program = compile_program(rules, door(0, 8, 0x34) + b"\0", event=event)
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert program.mutable_slots == ()
    assert result.unresolved_door_slots == (0,) and result.doors == ()


@pytest.mark.parametrize("args", [(24, 1, 1), (0, 2, 1), (0, 1, 2)])
def test_invalid_callback_metadata_is_rejected_on_construction(args):
    with pytest.raises(ValueError, match="tracking"):
        RuleCommand(1, 5, "aot-callback", args)


def test_past_room_forced_door_reads_fresh_unlock_flags_and_rewinds_in_map(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    herb = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    chemical = fixture_ram("slus00551_chemical_before.sav", tmp_path)
    for name, program in tuple(profile.room_programs.items()):
        if name.endswith("1091.RDT"):
            # Preserve the captured init, adding a synthetic forced-door main
            # command. This probes tracking, not natural event activation.
            start = program.main_procedures[-1].end + 2
            profile.room_programs[name] = replace(
                program,
                main_procedures=program.main_procedures
                + (
                    RuleProcedure(
                        start,
                        start + 5,
                        (
                            RuleCommand(start, start + 4, "aot-callback", (1, 1, 1)),
                            RuleCommand(start + 4, start + 5, "end", ()),
                        ),
                    ),
                ),
            )
    tracker = Tracker()
    assert (
        poll_once(profile, tracker, RamReader(herb).read_memory).status
        == PollStatus.Display
    )
    cached = profile.room_observations[RoomId(0, 9)]
    profile.room_observations[RoomId(0, 9)] = replace(
        cached,
        # Force source-rule refresh, matching generated forced-callback rooms.
        sources=tuple(
            replace(source, door_cache_complete=False) for source in cached.sources
        ),
    )
    address, mask = profile.tracking_rule_layout.flag(2, 4)
    for unlocked in (False, True, False):
        if unlocked:
            chemical[address - 0x80000000] |= mask
        else:
            chemical[address - 0x80000000] &= ~mask
        before = bytes(chemical)
        assert (
            poll_once(profile, tracker, RamReader(chemical).read_memory).status
            == PollStatus.Display
        )
        tracked = next(
            door
            for door in tracker.doors
            if door.source == RoomId(0, 9) and door.target == RoomId(0, 20)
        )
        assert tracked.state == ("OPEN" if unlocked else "LOCKED")
        state = tracker.room_state(RoomId(0, 9))
        assert state.completion == RoomCompletion.Cleared
        # Fresh entry excludes the other door's unstarted event alternatives.
        # Unlock still comes from current flags rather than callback replay.
        assert state.doors_complete
        mapped = next(row for row in map_state(tracker)["rooms"] if row["id"] == "09")
        assert mapped["doors_complete"] == state.doors_complete
        assert len(tracker.region_visits) == 2
        assert bytes(chemical) == before
