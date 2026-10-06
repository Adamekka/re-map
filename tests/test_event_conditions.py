"""RE1-EVENT-004: synthetic ordered blocks, not natural event validation."""

from dataclasses import replace

import pytest
from test_cache_metadata import indexed_event, pickup
from test_tracking_rules import branch, compile_program, door, evaluate, guard

from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import RoomProgram, RuleCommand, RuleProcedure

pytest_plugins = ("test_tracking_rules",)


def block(*procedures):
    payload = b"".join(
        (len(code) + 2).to_bytes(2, "little") + code for code in procedures
    ) + bytes(2)
    assert len(payload) + 2 <= 255
    return bytes((6, len(payload) + 2)) + payload


@pytest.mark.parametrize("operation,expected", [(0, 1), (1, 0)])
@pytest.mark.parametrize("group", [1, 4, 7])
def test_progress_write_makes_later_item_and_door_branch_impossible(
    rules, operation, expected, group
):
    updates = bytes((0x13, 0, 0, 0, 0x13, 1, 0, 0))
    code = (
        bytes((5, group, 31, operation))
        + guard(bytes((4, group, 31, expected)), updates)
        + b"\0"
    )
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0",
        event=indexed_event(block(code) + b"\xff"),
    )
    assert len(program.event_blocks) == 1
    assert not program.event_effects
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert result.items.items[0].state == RuntimeItemState.Available
    assert len(result.doors) == 1
    assert not result.unresolved_door_slots


def test_contradictory_historical_progress_guards_cannot_both_pass(rules):
    code = (
        guard(bytes((4, 1, 31, 0)), guard(bytes((4, 1, 31, 1)), bytes((0x13, 0, 0, 0))))
        + b"\0"
    )
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 31)
    for value in (0, mask, 0):
        ram[address - 0x80000000] = value
        assert evaluate(program, rules, ram).items.list_complete


def test_toggle_between_guards_changes_their_relation(rules):
    code = (
        guard(
            bytes((4, 1, 31, 0)),
            bytes((5, 1, 31, 2)) + guard(bytes((4, 1, 31, 1)), bytes((0x13, 0, 0, 0))),
        )
        + b"\0"
    )
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_a_false_current_guard_does_not_erase_a_possible_earlier_event(rules):
    code = guard(bytes((4, 1, 31, 0)), bytes((0x13, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 31)
    for value in (mask, 0, mask):
        ram[address - 0x80000000] = value
        before = bytes(ram)
        assert evaluate(program, rules, ram).unresolved_item_slots == (0,)
        assert bytes(ram) == before


def test_one_block_keeps_only_its_final_item_and_door_updates(rules):
    init = pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + door(2, 8, 0x34) + b"\0"
    code = (
        bytes(
            (
                0x13,
                0,
                0,
                0,
                0x13,
                1,
                0,
                0,
                0x13,
                2,
                0,
                0,
                0x13,
                0,
                4,
                1,
                0x13,
                1,
                4,
                1,
                0x13,
                2,
                1,
                1,
            )
        )
        + b"\0"
    )
    program = compile_program(rules, init, event=indexed_event(block(code) + b"\xff"))
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete
    assert [item.state for item in result.items.items] == [
        RuntimeItemState.Available
    ] * 2
    assert len(result.doors) == 1
    assert not result.unresolved_door_slots


def test_ordered_procedure_list_retains_writes_between_procedures(rules):
    first = bytes((5, 1, 31, 0, 0))
    second = guard(bytes((4, 1, 31, 1)), bytes((0x13, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(block(first, second) + b"\xff"),
    )
    assert len(program.event_blocks[0]) == 2
    assert evaluate(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


@pytest.mark.parametrize("separator", [b"", b"\xfe", bytes((0xF8, 0xF9, 1, 0))])
def test_separate_dispatches_do_not_share_historical_flag_shadows(rules, separator):
    first = bytes((5, 1, 31, 0, 0))
    second = guard(bytes((4, 1, 31, 1)), bytes((0x13, 0, 0, 0))) + b"\0"
    event = indexed_event(block(first) + separator + block(second) + b"\xff")
    program = compile_program(rules, pickup(0, 0x44, 111) + b"\0", event=event)
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_single_dispatch_updates_keep_intermediate_possibilities(rules):
    event = indexed_event(bytes((7, 6, 0x13, 0, 0, 0, 7, 6, 0x13, 0, 4, 1, 0xFF)))
    program = compile_program(rules, pickup(0, 0x44, 111) + b"\0", event=event)
    assert not program.event_blocks
    assert len(program.event_effects) == 2
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_physical_flag_aliases_share_progress_inside_a_block(rules):
    bases = list(rules[0].flag_bases)
    bases[3] = bases[2] + 8
    layout = replace(rules[0], flag_bases=tuple(bases))
    code = (
        bytes((5, 2, 64, 0))
        + guard(bytes((4, 3, 0, 1)), bytes((0x13, 0, 0, 0)))
        + b"\0"
    )
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert evaluate(
        program, (layout, rules[1]), bytearray(2 * 1024 * 1024)
    ).items.list_complete


def test_variable_write_invalidates_an_earlier_flag_assumption(rules):
    # Word variable 16 aliases bank 1's first word in this explicit test layout.
    code = (
        guard(
            bytes((4, 1, 31, 0)),
            bytes((0x31, 16, 0, 0))
            + guard(bytes((4, 1, 31, 1)), bytes((0x13, 0, 0, 0))),
        )
        + b"\0"
    )
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_camera_forgetting_does_not_retain_an_earlier_local_assumption(rules):
    code = (
        guard(
            bytes((4, 4, 31, 0)),
            bytes((9, 0)) + guard(bytes((4, 4, 31, 1)), bytes((0x13, 0, 0, 0))),
        )
        + b"\0"
    )
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_zero_callback_return_ends_the_procedure_before_later_updates(rules):
    code = bytes((0x2D, 1, 13, 0, 0x13, 0, 0, 0, 0))
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert evaluate(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


def test_unsupported_block_cannot_prune_independent_effects_or_other_slots(rules):
    code = bytes((0x13, 0, 0, 0, 0x13, 0, 4, 1, 0))
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + b"\0",
        event=indexed_event(block(code) + b"\xff"),
    )
    procedure = program.event_blocks[0][0]
    bad = replace(procedure.commands[0], kind="unsupported-effect", args=())
    procedure = replace(procedure, commands=(bad,) + procedure.commands[1:])
    # Keep a real disabled candidate after the unsupported command.
    disabled = replace(procedure.commands[1], args=(0, 0, 0))
    procedure = replace(procedure, commands=(bad, disabled) + procedure.commands[2:])
    result = evaluate(
        replace(program, event_blocks=((procedure,),)),
        rules,
        bytearray(2 * 1024 * 1024),
    )
    assert result.unresolved_item_slots == (0,)
    assert [item.aot_id for item in result.items.items] == [1]


def test_event_budget_cannot_authorize_partial_pruning(rules):
    program = compile_program(rules, pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + b"\0")
    commands = tuple(
        RuleCommand(0x1000 + i, 0x1001 + i, "constant-test", (1,)) for i in range(4100)
    )
    commands += (RuleCommand(0x2004, 0x2008, "aot-handler", (0, 0, 0)),)
    procedure = RuleProcedure(0x1000, 0x2008, commands)
    result = evaluate(
        replace(program, event_blocks=((procedure,),)),
        rules,
        bytearray(2 * 1024 * 1024),
    )
    assert result.unresolved_item_slots == (0,)
    assert [item.aot_id for item in result.items.items] == [1]


def test_snapshot_reversal_refreshes_main_rules_and_acquisition_after_event_analysis(
    rules,
):
    init = pickup(0, 0x44, 111) + b"\0"
    main = (
        branch(bytes((4, 1, 31, 0)), bytes((0x13, 0, 0, 1)), bytes((0x13, 0, 4, 1)))
        + b"\0"
    )
    event = indexed_event(
        block(
            bytes((5, 4, 31, 0))
            + guard(bytes((4, 4, 31, 1)), bytes((0x13, 0, 0, 0)))
            + b"\0"
        )
        + b"\xff"
    )
    program = compile_program(rules, init, main, event)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 31)
    taken = bytearray([255] * 32)
    taken[14] &= ~1
    for progress, flags, state in (
        (0, bytes([255]) * 32, RuntimeItemState.Available),
        (mask, bytes([255]) * 32, RuntimeItemState.Unavailable),
        (0, bytes(taken), RuntimeItemState.Taken),
        (0, bytes([255]) * 32, RuntimeItemState.Available),
    ):
        ram[address - 0x80000000] = progress
        result = evaluate(program, rules, ram, flags)
        assert result.items.list_complete
        assert result.items.items[0].state == state


def test_partial_source_cannot_claim_completion_from_a_clean_block(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(block(bytes((0x13, 0, 4, 1, 0))) + b"\xff"),
    )
    result = evaluate(
        replace(program, coverage_complete=False), rules, bytearray(2 * 1024 * 1024)
    )
    assert not result.items.list_complete


def test_block_order_and_required_schema_are_enforced(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(block(b"\0", bytes((0x13, 0, 4, 1, 0))) + b"\xff"),
    )
    with pytest.raises(ValueError, match="out of order"):
        replace(program, event_blocks=(program.event_blocks[0][::-1],))
    with pytest.raises(ValueError, match="overlaps"):
        replace(program, event_blocks=(program.procedures,))
    with pytest.raises(KeyError, match="event_blocks"):
        RoomProgram.load({"procedures": [], "main_procedures": []})


def test_written_byte_progress_is_visible_to_a_later_scalar_test(rules):
    code = (
        bytes((8, 8, 3, 0)) + guard(bytes((6, 8, 0, 2)), bytes((0x13, 0, 0, 0))) + b"\0"
    )
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert evaluate(program, rules, bytearray(2 * 1024 * 1024)).items.list_complete


def test_unwritten_byte_progress_does_not_read_another_rooms_live_bytes(rules):
    code = guard(bytes((6, 8, 0, 2)), bytes((0x13, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    ram = bytearray(2 * 1024 * 1024)
    for value in (2, 3, 2):
        ram[rules[0].byte_variables_base - 0x80000000 + 8] = value
        assert evaluate(program, rules, ram).unresolved_item_slots == (0,)


def test_one_command_reached_as_both_block_and_deferred_dispatch_stays_independent(
    rules,
):
    # The procedure's length bytes FC/04 also form the VM's call header
    # after its short wrapper jump. FD is both a handler operand and VM return.
    code = bytes((0x13, 0, 0xFD, 1, 0x13, 0, 4, 1)) + bytes(0x4FC - 2 - 8)
    payload = bytes((6, 2, 0xFC, 4)) + code + bytes(2)
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(payload)
    )
    assert program.coverage_complete
    assert len(program.event_blocks) == 1
    assert [c.args for c in program.event_effects] == [(0, 0xFD, 1)]
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_malformed_event_branch_cannot_establish_coverage(rules):
    code = bytes((1, 1, 0x13, 0, 0, 0, 0))
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert not program.event_blocks
    assert not program.event_effects
    assert not program.coverage_complete
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


def test_final_event_closure_runs_without_main_procedures(rules):
    code = (
        bytes((5, 4, 31, 0))
        + guard(bytes((4, 4, 31, 1)), bytes((0x13, 0, 0, 0)))
        + b"\0"
    )
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert evaluate(
        replace(program, main_procedures=()), rules, bytearray(2 * 1024 * 1024)
    ).items.list_complete
    disable = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(block(bytes((0x13, 0, 0, 0, 0))) + b"\xff"),
    )
    assert evaluate(
        replace(disable, main_procedures=()), rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)


@pytest.mark.parametrize(
    "index,partial,unresolved", [(1, False, False), (16, False, True), (1, True, True)]
)
def test_ordered_word_progress_obeys_scalar_bounds_and_requires_all_bits(
    rules, index, partial, unresolved
):
    setter = bytes((8, 22, 3, 0)) if partial else bytes((0x31, index, 3, 0))
    comparison = bytes((7, 0, index, 0, 2, 0))
    code = setter + guard(comparison, bytes((0x13, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", event=indexed_event(block(code) + b"\xff")
    )
    assert (
        bool(evaluate(program, rules, bytearray(2 * 1024 * 1024)).unresolved_item_slots)
        == unresolved
    )


@pytest.mark.parametrize("mode", [0, 2])
def test_quantity_copy_forgets_earlier_byte_progress_in_a_block(rules, mode):
    code = (
        bytes((8, 8, 3, 0, 0x4C, mode, 1, 8))
        + guard(bytes((6, 8, 0, 2)), bytes((0x13, 0, 0, 0)))
        + b"\0"
    )
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + b"\0",
        event=indexed_event(block(code) + b"\xff"),
    )
    assert (
        0 in evaluate(program, rules, bytearray(2 * 1024 * 1024)).unresolved_item_slots
    )


@pytest.mark.parametrize("opcode", [0x24, 0x2D])
@pytest.mark.parametrize("key", [0x34, 0xFF])
def test_ordered_door_callback_preserves_source_and_forgets_dialog_aliases(
    rules, opcode, key
):
    code = (
        bytes((5, 6, 31, 1, opcode, 1, 1, 0))
        + guard(bytes((4, 6, 31, 0)), bytes((0x13, 1, 0, 0)))
        + b"\0"
    )
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + door(1, 8, key) + b"\0",
        event=indexed_event(block(code) + b"\xff"),
    )
    ram = bytearray(2 * 1024 * 1024)
    before = bytes(ram)
    result = evaluate(program, rules, ram)
    assert result.items.list_complete
    assert bytes(ram) == before
    if opcode == 0x24:
        assert result.unresolved_door_slots == (1,)
    else:
        assert not result.unresolved_door_slots
        assert result.doors[0][1][24] == key


@pytest.mark.parametrize("error", ["range", "gid"])
def test_startup_validates_ordered_blocks_against_source_and_acquisition_bounds(
    tmp_path, error
):
    import json

    from test_tracking_rules import REPO

    from games.re1.re1_profile import Re1Profile

    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    row = next(r for r in manifest["rooms"] if r["tracking_program"]["event_blocks"])
    start = row["events_offset"] - 1 if error == "range" else row["events_offset"]
    if error == "gid":
        raw["runtime_room_layout"]["acquisition_flags_width"] = 16
        # Isolate the new block check from existing initializer acquisition IDs.
        for source_row in manifest["rooms"]:
            for section in ("procedures", "main_procedures"):
                for procedure in source_row["tracking_program"][section]:
                    for command in procedure["commands"]:
                        if command["kind"] == "item":
                            command["args"][3] %= 128
            for command in (
                source_row["tracking_program"]["event_effects"]
                + source_row["tracking_program"]["event_commands"]
            ):
                if command["kind"] == "item":
                    command["args"][3] %= 128
    # The replacement intentionally loses the original dispatch payloads.
    # Isolate the mandatory source/ID bounds from semantic coverage checking.
    row["tracking_program"]["coverage_complete"] = False
    row["tracking_program"]["reentry_coverage_complete"] = False
    row["tracking_program"]["event_blocks"] = [
        [
            {
                "start": start,
                "end": start + 26,
                "commands": [
                    {
                        "offset": start,
                        "next": start + 26,
                        "kind": "item",
                        "args": [0, 0x44, 1, 128, 1],
                    }
                ],
            }
        ]
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    raw["room_manifest_path"] = str(manifest_path)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(
        ValueError,
        match="outside source events" if error == "range" else "item ID exceeds",
    ):
        Re1Profile.load(profile_path)


def test_compiler_cannot_bypass_event_scan_failure_with_a_complete_claim(rules):
    from build_cache_metadata import scan_cache_rdt
    from build_tracking_program import build_tracking_program
    from scan_events import scan_event_program
    from test_cache_metadata import source

    data = source(pickup(0, 0x44, 111) + b"\0", b"\0", indexed_event(b"\xfd\xff"))
    row = scan_cache_rdt(data, "PSX/STAGE1/ROOM1091.RDT", rules[1])
    scan = scan_event_program(
        data, row["events_offset"], row["events_offset"] + row["events_size"]
    )
    assert scan.status != "clean"
    assert not build_tracking_program(data, row, [], True, scan)["coverage_complete"]


def test_clean_width_decode_with_invalid_semantic_procedure_prevents_completeness(
    rules,
):
    event = indexed_event(block(b"", bytes((0x13, 0, 4, 1, 0))) + b"\xff")
    program = compile_program(rules, pickup(0, 0x44, 111) + b"\0", event=event)
    assert not program.event_blocks
    assert not program.coverage_complete
    assert evaluate(
        program, rules, bytearray(2 * 1024 * 1024)
    ).unresolved_item_slots == (0,)
