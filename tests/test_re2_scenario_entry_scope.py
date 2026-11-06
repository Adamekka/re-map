"""Source-directed entry hazards remain distinct from native work ownership."""

import copy
import json
import struct
from pathlib import Path

import pytest
from test_re2_room_write_partitions import md1, object_command
from test_re2_startup_declarations import END, contract, described, item

from games.re2.scenario_entry_scope import scenario_entry_scope
from games.re2.scenario_selection import (
    SCENARIO_NATIVE_WORK_AUDIT,
    ScenarioSelectionFailure,
    VerifiedScenarioEntryScope,
    bind_scenario_context,
)


@pytest.fixture
def profile():
    return json.loads(
        (
            Path(__file__).resolve().parents[1] / "profiles/re2_leon_a_slus00748.json"
        ).read_text()
    )


def scoped(profile, init=END, main=(END, END)):
    data, room, _ = described(init, main)
    context = bind_scenario_context(profile, contract(profile, room))
    return data, room, context, scenario_entry_scope(data, room, profile, context)


def callback(procedure):
    packet = bytearray(20)
    packet[:4] = bytes((0x2C, 7, 5, 0x31))
    packet[14:] = bytes((255, 0, 0x18, procedure, 0, 0))
    return bytes(packet)


def render_recipe(record):
    return (
        bytes((0x53, record, 2, 7, 0x80, 1))
        + b"\x09\x0a\x1e\0"
        + b"\x0d\0\x08\0\x05\0"
        + bytes((0x74, record, 0xFF, 0x7F))
        + b"\x02\0\x0e\0"
    )


def test_all_canonical_entries_are_retained_including_late_shared_callees(profile):
    data, room, _, result = scoped(
        profile, main=(b"\x18\x02" + END, b"\x18\x02" + END, item() + END)
    )
    assert isinstance(result, VerifiedScenarioEntryScope)
    assert result.native_domain_audit == SCENARIO_NATIVE_WORK_AUDIT
    assert result.protected_programs == frozenset(room["programs"])
    assert result.entry_locations == frozenset(
        (key, program["entry"]) for key, program in room["programs"].items()
    )
    assert result.matches_source(data, room["programs"])
    assert not result.matches_source(data[:-1] + b"\xff", room["programs"])


@pytest.mark.parametrize("mutation", ["bytes", "programs", "corpus", "guard"])
def test_source_and_native_work_guards_are_mandatory(profile, mutation):
    data, room, context, result = scoped(profile)
    assert isinstance(result, VerifiedScenarioEntryScope)
    if mutation == "bytes":
        data = data[:-1] + b"\xff"
    elif mutation == "programs":
        room = copy.deepcopy(room)
        room["programs"]["17:0"]["commands"][0]["opcode"] = 0
    elif mutation == "corpus":
        room = room | {"id": "00-03"}
    else:
        profile["runtime_layout"]["scenario_reset_mask"] = 0
    assert isinstance(
        scenario_entry_scope(data, room, profile, context), ScenarioSelectionFailure
    )


@pytest.mark.parametrize("levels,accepted", [(3, True), (4, False), (8, False)])
def test_call_height_includes_the_root_frame(profile, levels, accepted):
    # Each link uses a fresh call frame. There are four frames in total,
    # rather than four nested calls in addition to the base frame.
    chain = tuple(
        b"\x18" + bytes((number + 1,)) + END for number in range(2, levels + 1)
    )
    _, _, _, result = scoped(profile, main=(b"\x18\x02" + END, END, *chain, END))
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize("operation", [3, 5, 0x17, 0x19, 0x6C, 0x6E])
def test_unproved_task_and_source_operations_cannot_inherit_a_scope(profile, operation):
    from games.re2.room_data import OPCODE_WIDTHS

    packet = bytearray(OPCODE_WIDTHS[operation])
    packet[0] = operation
    if operation == 0x17:
        # A local forward jump still needs native IF/loop-depth ownership.
        struct.pack_into("<h", packet, 4, len(packet))
    _, _, _, result = scoped(profile, main=(bytes(packet) + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


def test_kind_five_dispatch_retains_the_self_replacement_hazard(profile):
    _, _, _, result = scoped(
        profile, init=callback(2) + END, main=(END, b"\x47\x07" + END, END)
    )
    assert result is ScenarioSelectionFailure.EntryScope


def test_player_callback_without_aot_on_has_a_canonical_entry(profile):
    _, _, _, result = scoped(profile, init=callback(2) + END, main=(END, END, END))
    assert isinstance(result, VerifiedScenarioEntryScope)
    assert any(key == "17:2" for key, _ in result.entry_locations)


def test_root_replacement_abandons_old_control_and_retains_fresh_target(profile):
    _, room, _, result = scoped(
        profile,
        init=callback(2) + END,
        main=(END, END, b"\x03\0\x18\x03\x08\0" + END, item() + END),
    )
    # The abandoned ENDIF must not consume a frame in the replacement target.
    assert isinstance(result, VerifiedScenarioEntryScope)
    assert ("17:3", room["programs"]["17:3"]["entry"]) in result.entry_locations


@pytest.mark.parametrize(
    "packet",
    [b"\x03\x01\x18\x02", b"\x03\0\x17\x02", b"\x03\0\x18\xff"],
)
def test_replacement_requires_canonical_namespace_and_bounded_target(profile, packet):
    _, _, _, result = scoped(profile, main=(packet + END, END, END))
    assert result is ScenarioSelectionFailure.EntryScope


def test_replacement_does_not_grant_initializer_table_borrowing_rights(profile):
    _, _, _, result = scoped(
        profile, init=b"\x03\0\x18\x02" + END, main=(END, END, END)
    )
    assert result is ScenarioSelectionFailure.EntryScope


@pytest.mark.parametrize(
    "main",
    [
        (b"\x18\x02" + END, END, b"\x03\0\x18\x03" + END, END),
        (
            b"\x18\x02" + END,
            END,
            b"\x18\x03" + END,
            b"\x03\0\x18\x04" + END,
            END,
        ),
        (
            b"\x18\x02" + END,
            END,
            b"\x03\0\x18\x03" + END,
            b"\x03\0\x18\x04" + END,
            END,
        ),
        (
            b"\x03\0\x18\x02" + END,
            END,
            b"\x18\x03" + END,
            b"\x03\0\x18\x04" + END,
            END,
        ),
    ],
)
def test_replacement_cannot_inherit_direct_transitive_or_replaced_call_frames(
    profile, main
):
    _, _, _, result = scoped(profile, main=main)
    assert result is ScenarioSelectionFailure.EntryScope


def test_replacement_target_still_needs_fresh_control_frames(profile):
    _, _, _, result = scoped(
        profile, main=(b"\x03\0\x18\x02" + END, END, b"\x08\0" + END)
    )
    assert result is ScenarioSelectionFailure.EntryScope


def test_replacement_target_calls_still_reserve_the_root_frame(profile):
    chain = tuple(bytes((0x18, number + 1)) + END for number in range(2, 6))
    _, _, _, result = scoped(profile, main=(b"\x03\0\x18\x02" + END, END, *chain, END))
    assert result is ScenarioSelectionFailure.EntryScope


@pytest.mark.parametrize("record", [0, 1, 2, 3])
def test_render_update_reuses_the_initialized_record_in_a_bounded_loop(profile, record):
    _, _, _, result = scoped(profile, main=(render_recipe(record) + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "wrong_record", "record_bounds", "blend", "rgb", "mutator", "copy"],
)
def test_render_update_cannot_borrow_uninitialized_or_mutated_ownership(
    profile, mutation
):
    packet = bytearray(render_recipe(2))
    if mutation == "missing":
        del packet[:6]
    elif mutation == "wrong_record":
        packet[1] = 1
    elif mutation == "record_bounds":
        packet[1] = packet[17] = 4
    elif mutation == "blend":
        packet[2] = 4
    elif mutation == "rgb":
        packet[3] = 8
    elif mutation == "mutator":
        packet[6:6] = b"\x22\x04\x07\x01"
    else:
        # Source Copy could otherwise rewrite 74's record selector after the
        # recipe's immutable source bytes had been checked.
        packet[:0] = b"\x1d\x04\x11\0"
    _, _, _, result = scoped(profile, main=(bytes(packet) + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


def test_render_initializer_must_dominate_even_a_structurally_valid_loop_entry(profile):
    # A failed predicate enters the FOR after skipping 53 and its sleep. Both
    # paths have legal loop frames, so adjacency cannot establish ownership.
    bypass = b"\x06\0\x12\0\x21\x04\x07\0"
    _, _, _, result = scoped(profile, main=(bypass + render_recipe(2) + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


@pytest.mark.parametrize("record,accepted", [(1, True), (4, False), (255, False)])
def test_other_procedures_cannot_invalidate_render_record_ownership(
    profile, record, accepted
):
    # Independent canonical workers can run while the recipe sleeps. Their
    # initializers must also stay in the same initialized native-work domain.
    other = bytes((0x53, record, 2, 7, 0x80, 1)) + END
    _, _, _, result = scoped(profile, main=(render_recipe(2) + END, other))
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize("flags,accepted", [(0, True), (0x40, False), (0x80, False)])
def test_model_attachments_cannot_inherit_bounded_task_storage(
    profile, flags, accepted
):
    packet = bytearray(object_command(0))
    packet[3] = flags
    # Repetition can move the attachment queue into another task's PC. An
    # ordinary model resource alone does not bound that additional queue.
    data, room, _ = described(
        bytes(packet) * 47 + END, main=(END, END), models=(md1(0, 0),)
    )
    context = bind_scenario_context(profile, contract(profile, room))
    result = scenario_entry_scope(data, room, profile, context)
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize(
    "model,flags,slot,accepted",
    [
        (0x22, 0x0010, 0, True),
        (0x22, 0x4011, 31, True),
        (0x22, 0x4402, 1, True),
        (0x22, 0x4004, 0, False),
        (0x22, 0x4010, 0, False),
        (0x21, 0x0010, 0, False),
        (0x22, 0x0010, 255, False),
    ],
)
def test_constructor_presets_do_not_inherit_another_native_entry_role(
    profile, model, flags, slot, accepted
):
    packet = bytearray(22)
    packet[:4] = bytes((0x44, 0, slot, model))
    struct.pack_into("<H", packet, 4, flags)
    _, _, _, result = scoped(profile, main=(bytes(packet) + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize(
    "selector,accepted", [(23, True), (29, True), (30, False), (255, False)]
)
def test_member_writes_require_a_bounded_numeric_actor_field(
    profile, selector, accepted
):
    _, _, _, result = scoped(
        profile, main=(bytes((0x34, selector, 0xFF, 0xFF)) + END, END)
    )
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize("operation", [0x35, 0x3D])
@pytest.mark.parametrize(
    "member,counter,accepted",
    [(13, 16, True), (30, 16, False), (13, 128, False), (13, 255, False)],
)
def test_member_counter_copy_uses_the_native_operand_order(
    profile, operation, member, counter, accepted
):
    operands = (member, counter) if operation == 0x35 else (counter, member)
    _, _, _, result = scoped(profile, main=(bytes((operation, *operands)) + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize(
    "packet,displacement",
    [
        (b"\x2e\x03\0", 1),
        (b"\x2f\0\0\0", 1),
        (b"\x34\x17\0\0", 1),
        (b"\x35\x0d\x10", 1),
        (b"\x3d\x10\x0d", 2),
        (b"\x09\x0a\x01\0", 1),
        (b"\x0d\0\x03\0\x02\0\x02\x0e\0", 2),
    ],
)
def test_copy_cannot_change_native_qualification_or_control_operands(
    profile, packet, displacement
):
    # The original selector/frame shape is valid. Its mutation must still
    # invalidate a receipt even when the command's opcode remains unchanged.
    copy_packet = bytes((0x1D, 4, displacement, 0))
    _, _, _, result = scoped(profile, main=(copy_packet + packet + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


@pytest.mark.parametrize(
    "packet,displacement",
    [
        (b"\x23\0\x04\0\0\0", 4),
        (b"\x32\0\0\0\0\0\0\0", 4),
        (b"\x6d\0\0\0", 2),
    ],
)
def test_copy_can_change_admitted_scalar_immediates(profile, packet, displacement):
    copy_packet = bytes((0x1D, 4, displacement, 1))
    _, _, _, result = scoped(profile, main=(copy_packet + packet + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope)


@pytest.mark.parametrize(
    "packet",
    [b"\x24\xff\0\0", b"\x25\xff\0", b"\x26\0\0\xff\0\0", b"\x27\0\xff\0"],
)
def test_counter_destinations_stay_in_the_audited_save_region(profile, packet):
    _, _, _, result = scoped(profile, main=(packet + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


@pytest.mark.parametrize(
    "selector,accepted", [(0, True), (9, True), (11, True), (12, False), (255, False)]
)
def test_delta_selectors_cannot_write_other_task_fields(profile, selector, accepted):
    _, _, _, result = scoped(profile, main=(bytes((0x2F, selector, 0, 0)) + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize(
    "category,index,accepted",
    [
        (1, 0, True),
        (3, 31, True),
        (3, 32, False),
        (4, 31, True),
        (4, 255, False),
        (0, 0, False),
    ],
)
def test_source_work_selection_stays_in_native_owned_tables(
    profile, category, index, accepted
):
    _, _, _, result = scoped(profile, main=(bytes((0x2E, category, index)) + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize("loop_kind", ["for", "while", "do"])
def test_structured_loop_frames_can_repeat_without_a_termination_claim(
    profile, loop_kind
):
    body = b"\x02"
    if loop_kind == "for":
        packet = b"\x0d\0" + struct.pack("<hH", len(body) + 2, 2) + body + b"\x0e\0"
    elif loop_kind == "while":
        packet = (
            b"\x0f\x04"
            + struct.pack("<h", 4 + len(body) + 2)
            + b"\x21\x04\x07\0"
            + body
            + b"\x10\0"
        )
    else:
        packet = (
            b"\x11\0"
            + struct.pack("<h", len(body) + 6)
            + body
            + b"\x12\x04\x21\x04\x07\0"
        )
    _, _, _, result = scoped(profile, main=(packet + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope)


@pytest.mark.parametrize(
    "levels,sleep,accepted",
    [(3, True, True), (4, False, True), (4, True, False), (5, False, False)],
)
def test_nested_loops_reserve_a_real_native_slot_for_sleep(
    profile, levels, sleep, accepted
):
    body = b"\x09\x0a\x01\0" if sleep else b"\x02"
    for _ in range(levels):
        body = b"\x0d\0" + struct.pack("<hH", len(body) + 2, 2) + body + b"\x0e\0"
    _, _, _, result = scoped(profile, main=(body + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope) is accepted


@pytest.mark.parametrize("control", [b"\x04\xff\x18\x02", b"\x18\x02\0\0"])
def test_native_loop_condition_region_cannot_hide_calls_or_scheduling(profile, control):
    packet = b"\x0f\x04" + struct.pack("<h", len(control) + 3) + control + b"\x02\x10\0"
    _, _, _, result = scoped(profile, main=(packet + END, END, END))
    assert result is ScenarioSelectionFailure.EntryScope


def test_loop_tail_cannot_leave_an_if_frame_open(profile):
    body = b"\x06\0\x08\0\x21\x04\x07\0\x02"
    packet = b"\x0d\0" + struct.pack("<hH", len(body) + 2, 2) + body + b"\x0e\0\x08\0"
    _, _, _, result = scoped(profile, main=(packet + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


def test_failed_predicate_inside_a_loop_retains_its_native_loop_slot(profile):
    check = b"\x21\x04\x07\0"
    loop = b"\x0d\0" + struct.pack("<hH", len(check) + 2, 2) + check + b"\x0e\0"
    outer = b"\x06\0" + struct.pack("<H", 4 + len(loop) + 2) + check + loop + b"\x08\0"
    suffix = b"\x02"
    for _ in range(4):
        suffix = b"\x0d\0" + struct.pack("<hH", len(suffix) + 2, 2) + suffix + b"\x0e\0"
    # Failure of the second predicate jumps out of the outer IF while the
    # first loop remains entered. The following fourth loop would be a fifth
    # occupied native slot, even though the ordinary forward path balances.
    _, _, _, result = scoped(profile, main=(outer + suffix + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


def test_flat_switch_cases_have_owned_loop_and_if_frames(profile):
    body = b"\x02\x1a\0"
    case = b"\x14\0" + struct.pack("<HH", len(body), 0)
    switch = (
        b"\x13\x01"
        + struct.pack("<H", len(case) + len(body) + 2)
        + case
        + body
        + b"\x16\0"
    )
    _, _, _, result = scoped(profile, main=(switch + END, END))
    assert isinstance(result, VerifiedScenarioEntryScope)
    # A branch into the closing marker cannot manufacture a switch frame.
    _, _, _, result = scoped(profile, main=(b"\x16\0" + END, END))
    assert result is ScenarioSelectionFailure.EntryScope


def test_switch_break_cannot_silently_abandon_an_if_frame(profile):
    body = b"\x06\0\x08\0\x21\x04\x07\0\x1a\0\x08\0"
    case = b"\x14\0" + struct.pack("<HH", len(body), 0)
    switch = (
        b"\x13\x01"
        + struct.pack("<H", len(case) + len(body) + 2)
        + case
        + body
        + b"\x16\0"
    )
    _, _, _, result = scoped(profile, main=(switch + END, END))
    assert result is ScenarioSelectionFailure.EntryScope
