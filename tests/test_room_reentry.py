"""Synthetic room-entry epochs; recorded gameplay replay is RE1-REENTRY-004."""

import struct
from dataclasses import replace

import pytest
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import RamReader
from test_tracking_rules import branch, compile_program, door, guard

from games.game_profile import RoomId
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)

pytest_plugins = ("test_tracking_rules",)


def interaction(handler=16, entry=0):
    raw = bytearray(18)
    raw[0], raw[1], raw[10], raw[11] = 0x0D, 5, handler, 129
    struct.pack_into("<HH", raw, 12, 0, entry)
    return bytes(raw)


def reenter(program, rules, ram, epoch=RoomRuleEpoch.Reentry):
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error
    return evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )


def test_reset_guard_excludes_unstarted_event_without_erasing_current_history(rules):
    main = guard(bytes((4, 4, 9, 0)), bytes((0x14, 0, 0, 0))) + b"\0"
    event = indexed(bytes((7, 6, 0x13, 5, 4, 129, 0xFF)))
    program = compile_program(rules, interaction() + b"\0", main, event)
    ram = bytearray(2 * 1024 * 1024)
    # Another room's bytes deliberately contradict the modeled entry reset.
    ram[
        rules[0].flag_bases[4] - 0x80000000 : rules[0].flag_bases[4] - 0x80000000 + 32
    ] = bytes([255]) * 32
    before = bytes(ram)
    assert reenter(program, rules, ram).items.list_complete
    assert not reenter(program, rules, ram).items.items
    assert reenter(
        program, rules, ram, RoomRuleEpoch.Current
    ).unresolved_item_slots == (5,)
    assert bytes(ram) == before


def test_saved_story_changes_and_reversal_recompute_entry_start_conditions(rules):
    init = interaction() + guard(bytes((4, 1, 7, 0)), bytes((5, 4, 9, 0))) + b"\0"
    main = guard(bytes((4, 4, 9, 0)), bytes((0x14, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules, init, main, indexed(bytes((7, 6, 0x13, 5, 4, 129, 0xFF)))
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 7)
    for value, complete in ((0, True), (mask, False), (0, True)):
        ram[address - 0x80000000] = value
        assert reenter(program, rules, ram).items.list_complete == complete


def test_only_bounded_entry_bits_are_known(rules):
    main = guard(bytes((4, 4, 64, 0)), bytes((0x14, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules,
        interaction() + b"\0",
        main,
        indexed(bytes((7, 6, 0x13, 5, 4, 129, 0xFF))),
    )
    assert reenter(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (5,)


@pytest.mark.parametrize("writer", ["alias", "camera"])
def test_alias_and_native_forget_can_enable_a_later_main_event(rules, writer):
    if writer == "alias":
        layout = replace(rules[0], word_variables_base=rules[0].flag_bases[4])
        rules = layout, rules[1]
        write = bytes((0x31, 1, 0x40, 0))
    else:
        write = bytes((9, 0, 0, 0))
    main = guard(bytes((4, 4, 9, 0)), bytes((0x14, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules,
        interaction() + write + b"\0",
        main,
        indexed(bytes((7, 6, 0x13, 5, 4, 129, 0xFF))),
    )
    assert reenter(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (5,)


@pytest.mark.parametrize("synchronous", [True, False])
def test_flag_only_dispatch_enables_main_but_atomic_temporary_write_does_not(
    rules, synchronous
):
    writes = bytes((5, 4, 9, 0, 5, 4, 9, 1))
    first = (
        block(writes + b"\0")
        if synchronous
        else bytes((7, 6)) + writes[:4] + bytes((7, 6)) + writes[4:]
    )
    event = indexed(first + b"\xff", bytes((7, 6, 0x13, 5, 4, 129, 0xFF)))
    init = interaction() + bytes((0x14, 0, 0, 0, 0))
    main = guard(bytes((4, 4, 9, 0)), bytes((0x14, 0, 0, 1))) + b"\0"
    program = compile_program(rules, init, main, event)
    assert (
        reenter(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete
        == synchronous
    )


@pytest.mark.parametrize("native_start", [bytes((5, 0, 1, 0)), bytes((8, 1))])
def test_native_child_start_and_restart_keep_transitive_effects(rules, native_start):
    event = indexed(native_start + b"\xff", bytes((7, 6, 0x13, 5, 4, 129, 0xFF)))
    program = compile_program(
        rules, interaction() + bytes((0x14, 0, 0, 0, 0)), event=event
    )
    assert reenter(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (5,)


@pytest.mark.parametrize("handler,forced", [(9, False), (16, True)])
def test_registered_and_forced_event_interactions_are_optional_roots(
    rules, handler, forced
):
    init = interaction(handler) + (bytes((0x24, 5, 9, 0)) if forced else b"") + b"\0"
    program = compile_program(
        rules, init, event=indexed(bytes((7, 6, 0x13, 5, 4, 129, 0xFF)))
    )
    assert reenter(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (5,)


def test_supported_saved_bits_in_event_only_rules_are_read_and_fail_explicitly(rules):
    code = guard(bytes((4, 1, 31, 0)), bytes((0x13, 5, 4, 129))) + b"\0"
    program = compile_program(
        rules,
        interaction() + bytes((0x14, 0, 0, 0, 0)),
        event=indexed(block(code) + b"\xff"),
    )
    address, mask = rules[0].flag(1, 31)
    ram = bytearray(2 * 1024 * 1024)
    for value, complete in ((0, True), (mask, False), (0, True)):
        ram[address - 0x80000000] = value
        assert reenter(program, rules, ram).items.list_complete == complete
    reader = RamReader(ram)
    reader.fail_address = address
    assert read_rule_snapshot(rules[0], (program,), reader.read_memory).error


def test_unknown_event_effect_blocks_clearance_only_when_reachable(rules):
    event = indexed(bytes((7, 6, 0x13, 5, 4, 129, 0xFF)))
    for start in (False, True):
        init = interaction() + (bytes((0x14, 0, 0, 0)) if start else b"") + b"\0"
        program = compile_program(rules, init, event=event)
        command = replace(program.event_commands[0], kind="unsupported-effect", args=())
        program = replace(program, event_commands=(command,))
        assert (
            reenter(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete
            != start
        )


def test_display_request_does_not_make_its_transient_bit_constant(rules):
    from test_cache_metadata import pickup

    main = guard(bytes((4, 5, 13, 0)), pickup(0, 0x44, 111)) + b"\0"
    program = compile_program(rules, bytes((0x29, 5, 0)), main)
    assert not reenter(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


@pytest.mark.parametrize("index", [6, 7])
def test_display_consumer_forgets_both_scalar_word_aliases(rules, index):
    from test_cache_metadata import pickup

    init = bytes((0x31, index, 1, 0, 0x29, 5, 0))
    main = guard(bytes((7, 0, index, 0, 1, 0)), pickup(0, 0x44, 111)) + b"\0"
    program = compile_program(rules, init, main)
    assert not reenter(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


def test_same_entry_story_condition_refreshes_items_and_doors_together(rules):
    from test_cache_metadata import pickup

    code = (
        branch(
            bytes((4, 1, 7, 0)),
            pickup(0, 0x44, 111) + door(1, 8, 0x34),
            b"",
        )
        + b"\0"
    )
    program = compile_program(rules, code)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 7)
    for value, count in ((0, 0), (mask, 1), (0, 0)):
        ram[address - 0x80000000] = value
        result = reenter(program, rules, ram)
        assert result.items.list_complete
        assert len(result.items.items) == count and len(result.doors) == count
        assert not result.unresolved_door_slots


def test_missing_generic_parameter_source_cannot_authorize_forced_event(rules):
    from test_cache_metadata import pickup

    init = pickup(5, 0x44, 111) + bytes((0x24, 5, 9, 0, 0))
    program = compile_program(rules, init, event=indexed(b"\xff"))
    assert not reenter(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


def test_setter_without_an_entry_creator_cannot_discard_retained_source(rules):
    program = compile_program(rules, b"\0", bytes((0x13, 5, 4, 129, 0)))
    result = reenter(program, rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete and result.unresolved_item_slots == (5,)


def test_standalone_event_commands_are_mandatory_for_complete_dispatches(rules):
    program = compile_program(
        rules,
        interaction() + b"\0",
        event=indexed(bytes((7, 6, 0x13, 5, 4, 129, 0xFF))),
    )
    with pytest.raises(ValueError, match="dispatch lacks"):
        replace(program, event_commands=())


def test_registry_parameter_writer_must_match_its_source_command_slot(rules):
    program = compile_program(rules, interaction() + b"\0", event=indexed(b"\xff"))
    offset, _, parameter, model, operation = program.event_program.registry_writes[0]
    with pytest.raises(ValueError, match="parameter writer"):
        replace(
            program,
            event_program=replace(
                program.event_program,
                registry_writes=((offset, 6, parameter, model, operation),),
            ),
        )


def test_reentry_cache_reuses_only_identical_inputs_and_reverses_flags(
    tmp_path, monkeypatch
):
    from test_live_items import fixture_ram
    from test_tracking_rules import REPO
    from track import poll_once

    import games.re1.tracking_engine as engine
    from games.re1.re1_profile import Re1Profile
    from games.re1.room_items import RuntimeItemState
    from tracker.exploration_state import Tracker

    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    assert poll_once(profile, Tracker(), reader.read_memory).status.value == "display"
    cached = profile.room_observations[RoomId(0, 9)]
    cached = replace(
        cached,
        sources=tuple(
            replace(s, cache_complete=False, door_cache_complete=False)
            for s in cached.sources
        ),
    )
    program = profile.room_programs[cached.sources[0].source_rdt]
    snapshot = read_rule_snapshot(
        profile.tracking_rule_layout, (program,), reader.read_memory
    )
    flags = bytes(ram[0xC86DC:0xC86FC])
    calls = []
    original = engine.evaluate_room_program

    def count(*args):
        calls.append(args[0])
        return original(*args)

    monkeypatch.setattr(engine, "evaluate_room_program", count)
    for expected in (1, 1):
        result = engine.refresh_visited_room(
            profile, cached, cached.context, snapshot, flags
        )
        assert (
            len(calls) == expected
            and result.items.items[0].state == RuntimeItemState.Available
        )
    changed = flags[:14] + bytes((flags[14] & ~1,)) + flags[15:]
    result = engine.refresh_visited_room(
        profile, cached, cached.context, snapshot, changed
    )
    assert len(calls) == 2 and result.items.items[0].state == RuntimeItemState.Taken
    result = engine.refresh_visited_room(
        profile, cached, cached.context, snapshot, flags
    )
    assert len(calls) == 3 and result.items.items[0].state == RuntimeItemState.Available
    changed_snapshot = replace(snapshot, values=snapshot.values + ((0x80000100, 1),))
    engine.refresh_visited_room(
        profile, cached, cached.context, changed_snapshot, flags
    )
    assert len(calls) == 4
    profile.room_programs[cached.sources[0].source_rdt] = replace(program)
    engine.refresh_visited_room(profile, cached, cached.context, snapshot, flags)
    assert len(calls) == 5


@pytest.mark.parametrize("limit", ["stack", "paths"])
def test_reentry_analysis_limits_keep_coverage_unresolved(rules, limit):
    from test_cache_metadata import pickup

    if limit == "stack":
        code = pickup(1, 0x44, 111)
        for _ in range(17):
            code = guard(bytes((6, 1, 0, 9)), code)
    else:
        code = (
            b"".join(
                branch(
                    bytes((6, 2, 0, 1)), bytes((5, 4, bit, 0)), bytes((5, 4, bit, 1))
                )
                for bit in range(13)
            )
            + b"".join(guard(bytes((4, 4, bit, 0)), b"") for bit in range(13))
            + pickup(1, 0x44, 111)
        )
    program = compile_program(rules, code + b"\0")
    result = reenter(program, rules, bytearray(2 * 1024 * 1024))
    assert not result.items.list_complete and result.unresolved_item_slots == (1,)


@pytest.mark.parametrize(
    "clears", [((4, 0, 257),), ((1, 0, 64),), ((4, 0, 64), (4, 9, 1))]
)
def test_invalid_entry_reset_configuration_fails_at_construction(rules, clears):
    with pytest.raises(ValueError, match="room entry flag"):
        replace(rules[0], room_entry_flag_clears=clears)
