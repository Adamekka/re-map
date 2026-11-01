"""RE2-SCENARIO-001: scenario, entry and source-write capabilities stay separate."""

import copy
import json
import struct
from dataclasses import replace
from pathlib import Path

import pytest
from test_re2_known_puzzle_items import conditional as guarded
from test_re2_room_write_partitions import END, source
from test_re2_startup_declarations import conditional, contract, item

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.room_data import decode_room
from games.re2.scenario_selection import (
    SCENARIO_ENTRY_AUDIT,
    SCENARIO_NATIVE_WORK_AUDIT,
    ScenarioItemVariant,
    ScenarioContextLayout,
    ScenarioSelectionFailure,
    ScopedScenarioItems,
    VerifiedScenarioContext,
    VerifiedScenarioEntryScope,
    bind_scenario_context,
    camera_record_write_witnesses,
    floor_flag_write_witnesses,
    scoped_scenario_items,
    scenario_context_layout,
)
from games.re2.script_control_limits import programs_digest
from games.re2.startup_entry_selection import EntrySelectionSource


@pytest.fixture
def profile():
    return json.loads(
        (
            Path(__file__).resolve().parents[1] / "profiles/re2_leon_a_slus00748.json"
        ).read_text()
    )


def prepared(profile, init, main, cameras):
    data, _, parts = source(init, main, (), cameras)
    room = decode_room(
        data,
        "PL0/RDT/ROOM1020.RDT",
        frozenset(
            (row["bank"], row["bit"]) for row in profile["presence_condition_flags"]
        ),
        presence_counter_indices(profile),
        presence_flag_write_proof(profile)[0],
    )
    room.update(stage=0, room=2, id="00-02")
    # This test-only receipt isolates query interpretation. Production receives
    # it from the independent native entry/write factory, never from this helper.
    context = bind_scenario_context(profile, contract(profile, room))
    assert isinstance(context, VerifiedScenarioContext)
    scope = VerifiedScenarioEntryScope(
        SCENARIO_ENTRY_AUDIT,
        SCENARIO_NATIVE_WORK_AUDIT,
        context.declaration_contract.executable_sha256,
        room["sha256"],
        programs_digest(room["programs"]),
        frozenset(room["programs"]),
        frozenset((key, p["entry"]) for key, p in room["programs"].items()),
    )
    return data, room, context, scope, parts


@pytest.mark.parametrize("bit", [0, 1])
def test_conditional_identity_does_not_grant_presence_or_global_context(profile, bit):
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (conditional(item(kind=20), item(kind=7), bank=1, bit=bit) + END,),
        (0,),
    )
    before = copy.deepcopy(room)
    result = scoped_scenario_items(data, room, profile, context, scope)
    assert isinstance(result, ScopedScenarioItems)
    selected = result.item_variants[0]
    assert selected.global_id == 154
    assert selected.offsets == tuple(
        r["offset"] for r in room["items"] if r["type"] == 20
    )
    assert result.absent_item_ids == ()
    assert not hasattr(result, "fixed_context_preserved")
    assert not hasattr(result, "presence")
    assert not hasattr(selected, "amount")
    assert room == before


def test_independent_reset_preserves_a_catalog_alternative(profile):
    reset = bytes((0x46, 7, 2, 0x31)) + struct.pack("<3H", 7, 5, 154)
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (
            conditional(item(kind=20), item(kind=7), bank=1, bit=1) + END,
            END,
            reset + END,
        ),
        (0,),
    )
    assert room["candidate_list_complete"]
    assert scoped_scenario_items(
        data, room, profile, context, scope
    ) == ScopedScenarioItems((), ())


def test_reset_only_identity_keeps_incomplete_catalog_unresolved(profile):
    reset = bytes((0x46, 7, 2, 0x31)) + struct.pack("<3H", 26, 5, 154)
    data, room, context, scope, _ = prepared(
        profile, END, (item() + END, END, reset + END), (0,)
    )
    assert not room["candidate_list_complete"]
    assert scoped_scenario_items(
        data, room, profile, context, scope
    ) == ScopedScenarioItems((), ())


def test_late_reset_prevents_absence_even_without_an_ordinary_creator_path(profile):
    reset = bytes((0x46, 7, 2, 0x31)) + struct.pack("<3H", 20, 15, 154)
    data, room, context, scope, _ = prepared(
        profile, END, (guarded(1, 1, 1, item()) + END, END, reset + END), (0,)
    )
    assert scoped_scenario_items(
        data, room, profile, context, scope
    ) == ScopedScenarioItems((), ())


def test_supported_scenario_excludes_only_the_guarded_identity(profile):
    data, room, context, scope, _ = prepared(
        profile, END, (guarded(1, 1, 1, item()) + item(gid=155) + END,), (0,)
    )
    result = scoped_scenario_items(data, room, profile, context, scope)
    assert result == ScopedScenarioItems((154,), ())


@pytest.mark.parametrize("position", ["before", "after"])
def test_exact_automatic_scheduling_keeps_possible_caller_continuation(
    profile, position
):
    body = conditional(item(kind=20), item(kind=7), bank=1, bit=1)
    schedule = bytes((4, 255, 0x18, 2))
    body = schedule + body if position == "before" else body + schedule
    data, room, context, scope, _ = prepared(profile, END, (body + END, END, END), (0,))
    result = scoped_scenario_items(data, room, profile, context, scope)
    assert isinstance(result, ScopedScenarioItems) and len(result.item_variants) == 1


@pytest.mark.parametrize(
    "schedule",
    [bytes((4, 0, 0x18, 2)), bytes((4, 255, 0x18, 99)), bytes((3, 0, 0x18, 2))],
)
def test_unbound_or_replacing_query_control_withholds_identity(profile, schedule):
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (
            schedule + conditional(item(kind=20), item(kind=7), bank=1, bit=1) + END,
            END,
            END,
        ),
        (0,),
    )
    assert scoped_scenario_items(
        data, room, profile, context, scope
    ) == ScopedScenarioItems((), ())


def test_hidden_creator_entry_removes_conditional_selection(profile):
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (conditional(item(kind=20), item(kind=7), bank=1, bit=1) + END,),
        (0,),
    )
    alternative = next(r["offset"] for r in room["items"] if r["type"] == 7)
    scope = replace(
        scope, entry_locations=scope.entry_locations | {("17:0", alternative)}
    )
    assert scoped_scenario_items(
        data, room, profile, context, scope
    ) == ScopedScenarioItems((), ())


def test_standalone_native_predicate_cannot_be_an_opaque_fallthrough(profile):
    predicate = bytes((0x23, 0, 1, 0, 0, 0))
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (predicate + conditional(item(kind=20), item(kind=7), bank=1, bit=1) + END,),
        (0,),
    )
    assert scoped_scenario_items(
        data, room, profile, context, scope
    ) == ScopedScenarioItems((), ())


def test_uncertified_creator_program_is_not_assumed_absent(profile):
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (
            conditional(item(kind=20), item(kind=7), bank=1, bit=1) + END,
            END,
            item(kind=7) + END,
        ),
        (0,),
    )
    scope = replace(
        scope,
        protected_programs=frozenset(("17:0",)),
        entry_locations=frozenset((("17:0", room["programs"]["17:0"]["entry"]),)),
    )
    assert scoped_scenario_items(
        data, room, profile, context, scope
    ) == ScopedScenarioItems((), ())


@pytest.mark.parametrize(
    "writer",
    [bytes((0x22, 1, 1, 1)), bytes((0x46, 2, 6, 0x31)) + struct.pack("<3H", 1, 257, 1)],
)
def test_explicit_or_wrapped_kind6_writer_rejects_the_scenario_premise(profile, writer):
    data, room, context, scope, _ = prepared(
        profile, END, (guarded(1, 1, 1, item()) + END, END, writer + END), (0,)
    )
    assert (
        scoped_scenario_items(data, room, profile, context, scope)
        is ScenarioSelectionFailure.SourceMutation
    )


def test_physical_bank_alias_rejects_the_scenario_premise(profile):
    alias = next(r for r in profile["flag_banks"] if r["bank"] == 5)
    alias["address_ps1"] = "0x800CFBD4"
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (guarded(1, 1, 1, item()) + END, END, bytes((0x22, 5, 33, 1)) + END),
        (0,),
    )
    assert (
        scoped_scenario_items(data, room, profile, context, scope)
        is ScenarioSelectionFailure.SourceMutation
    )


def test_copy_cannot_rewrite_a_predicate_operand(profile):
    body = (
        bytes((0x1D, 0, 5, 0))
        + conditional(item(kind=20), item(kind=7), bank=1, bit=1)
        + END
    )
    data, room, context, scope, _ = prepared(profile, END, (body,), (0,))
    assert (
        scoped_scenario_items(data, room, profile, context, scope)
        is ScenarioSelectionFailure.SourceMutation
    )


def test_source_and_entry_receipts_cannot_be_reused_after_drift(profile):
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (conditional(item(kind=20), item(kind=7), bank=1, bit=1) + END,),
        (0,),
    )
    assert (
        scoped_scenario_items(
            data, room, profile, context, replace(scope, programs_sha256="0" * 64)
        )
        is ScenarioSelectionFailure.SourceBinding
    )
    changed = copy.deepcopy(room)
    changed["items"][0]["type"] = 30
    assert (
        scoped_scenario_items(data, changed, profile, context, scope)
        is ScenarioSelectionFailure.SourceBinding
    )


def test_corpus_identity_does_not_inherit_stage_zero_route_restriction(profile):
    data, room, context, scope, _ = prepared(
        profile,
        END,
        (conditional(item(kind=20), item(kind=7), bank=1, bit=1) + END,),
        (0,),
    )
    room.update(stage=1, room=2, id="01-02", source="PL0/RDT/ROOM2020.RDT")
    declaration = context.declaration_contract
    selection = replace(
        declaration.selection,
        sources=(
            EntrySelectionSource(room["id"], room["source"], len(data), room["sha256"]),
        ),
    )
    context = replace(
        context, declaration_contract=replace(declaration, selection=selection)
    )
    assert not selection.covers_source(data, room)
    result = scoped_scenario_items(data, room, profile, context, scope)
    assert isinstance(result, ScopedScenarioItems) and len(result.item_variants) == 1


@pytest.mark.parametrize(
    "packet,cameras,expected",
    [
        (bytes((0x61, 5, 1, 0)), (5, 7), True),
        (bytes((0x61, 5, 2, 0)), (5, 7), False),
        (bytes((0x61, 6, 0, 0)), (5, 7), False),
    ],
)
def test_camera_write_requires_a_real_first_match_and_bounded_relative_record(
    profile, packet, cameras, expected
):
    data, room, context, scope, parts = prepared(profile, END, (packet + END,), cameras)
    result = camera_record_write_witnesses(data, room)
    if expected:
        assert len(result.writes) == 1
        assert (result.writes[0].offset, result.writes[0].width) == (
            parts["rvd"] + 20,
            1,
        )
        assert [(r.offset, r.width) for r in result.reads] == [
            (parts["rvd"] + 2, 1),
            (parts["rvd"] + 22, 1),
            (parts["rvd"] + 42, 1),
        ]
    else:
        assert result is ScenarioSelectionFailure.CameraWrite


def test_repeated_camera_flag_writes_preserve_search_identity(profile):
    packets = bytes((0x61, 5, 1, 0, 0x61, 5, 0, 1))
    data, room, context, scope, parts = prepared(profile, END, (packets + END,), (5, 7))
    result = camera_record_write_witnesses(data, room)
    assert [(r.offset, r.width) for r in result.writes] == [
        (parts["rvd"] + 20, 1),
        (parts["rvd"], 1),
    ]


def test_camera_swaps_expand_every_possible_first_match_before_relative_write(profile):
    packets = bytes((0x4B, 0, 1, 0x4B, 1, 2, 0x61, 0, 1, 0))
    data, room, context, scope, parts = prepared(
        profile, END, (packets + END,), (0, 1, 2)
    )
    # The original first match is zero, but two swaps can move camera zero to
    # the final row. Its requested following row is then outside the resource.
    assert (
        camera_record_write_witnesses(data, room)
        is ScenarioSelectionFailure.CameraWrite
    )


def test_camera_swap_components_preserve_safe_flag_targets(profile):
    packets = bytes((0x4B, 0, 1, 0x4B, 1, 2, 0x61, 0, 0, 0))
    data, room, context, scope, parts = prepared(
        profile, END, (packets + END,), (0, 1, 2)
    )
    proof = camera_record_write_witnesses(data, room)
    assert {write.offset for write in proof.writes if write.width == 1} == {
        parts["rvd"],
        parts["rvd"] + 20,
        parts["rvd"] + 40,
    }
    assert {write.offset for write in proof.writes if write.width == 2} == {
        parts["rvd"] + 2,
        parts["rvd"] + 22,
        parts["rvd"] + 42,
    }


def test_camera_swap_uses_first_occurrences_of_repeated_labels(profile):
    packets = bytes((0x4B, 0, 1, 0x61, 0, 1, 0))
    data, room, context, scope, parts = prepared(
        profile, END, (packets + END,), (0, 1, 0)
    )
    proof = camera_record_write_witnesses(data, room)
    assert {write.offset for write in proof.writes if write.width == 1} == {
        parts["rvd"] + 20,
        parts["rvd"] + 40,
    }


@pytest.mark.parametrize("other", [3, 255])
def test_camera_swap_requires_existing_labels_and_preserves_the_sentinel(
    profile, other
):
    data, room, context, scope, _ = prepared(
        profile, END, (bytes((0x4B, 0, other)) + END,), (0, 1)
    )
    assert (
        camera_record_write_witnesses(data, room)
        is ScenarioSelectionFailure.CameraWrite
    )


@pytest.mark.parametrize("count,index", [(2, 0), (2, 1), (2, 2), (0, 0)])
def test_floor_flags_use_counted_twelve_byte_records(profile, count, index):
    packet = bytes((0x38, index, 1))
    data, room, context, scope, parts = prepared(profile, END, (packet + END,), (0,))
    raw = bytearray(data)
    start = parts["floor"]
    asset = struct.pack("<HH", count, 0) + bytes(count * 12)
    raw[start:start] = asset
    struct.pack_into("<I", raw, 8 + 11 * 4, start)
    struct.pack_into("<I", raw, 8 + 2 * 4, start + len(asset))
    data = bytes(raw)
    room = decode_room(data, room["source"], frozenset(), frozenset(), frozenset())
    proof = floor_flag_write_witnesses(data, room)
    assert [(r.offset, r.width) for r in proof.reads] == [(start, 2)]
    expected = [(start + 12 + index * 12, 2)] if index < count else []
    assert [(r.offset, r.width) for r in proof.writes] == expected


def test_floor_count_cannot_extend_into_the_next_source_section(profile):
    data, room, context, scope, parts = prepared(
        profile, END, (bytes((0x38, 0, 1)) + END,), (0,)
    )
    raw = bytearray(data)
    start = parts["floor"]
    raw[start:start] = struct.pack("<HH", 2, 0) + bytes(12)
    struct.pack_into("<I", raw, 8 + 11 * 4, start)
    struct.pack_into("<I", raw, 8 + 2 * 4, start + 16)
    data = bytes(raw)
    room = decode_room(data, room["source"], frozenset(), frozenset(), frozenset())
    assert (
        floor_flag_write_witnesses(data, room)
        is ScenarioSelectionFailure.SourceMutation
    )


def test_copy_cannot_change_the_camera_search_identity(profile):
    body = (
        bytes((0x61, 5, 0, 0, 0x1D, 0, 0, 0))
        + conditional(item(kind=20), item(kind=7), bank=1, bit=1)
        + END
    )
    data, room, context, scope, parts = prepared(profile, END, (body,), (5, 7))
    copy_row = next(
        row for row in room["programs"]["17:0"]["commands"] if row["opcode"] == 0x1D
    )
    delta = parts["rvd"] + 2 - copy_row["next"]
    assert 0 <= delta < 256
    raw = bytearray(data)
    raw[copy_row["offset"] + 2] = delta
    data = bytes(raw)
    room = decode_room(
        data,
        room["source"],
        frozenset((r["bank"], r["bit"]) for r in profile["presence_condition_flags"]),
        presence_counter_indices(profile),
        presence_flag_write_proof(profile)[0],
    )
    room.update(id="00-02", stage=0, room=2)
    context = bind_scenario_context(profile, contract(profile, room))
    scope = replace(
        scope,
        source_sha256=room["sha256"],
        programs_sha256=programs_digest(room["programs"]),
    )
    assert (
        scoped_scenario_items(data, room, profile, context, scope)
        is ScenarioSelectionFailure.SourceMutation
    )


@pytest.mark.parametrize(
    "fault",
    [
        "status",
        "mask",
        "value",
        "executable",
        "reset",
        "work",
        "missing-reset",
        "missing-work",
    ],
)
def test_native_scenario_binding_rejects_other_layouts_and_modes(profile, fault):
    data, room, context, scope, _ = prepared(profile, END, (END,), (0,))
    if fault == "status":
        profile["runtime_layout"]["status_flags_address_ps1"] = "0x800CFBDC"
    elif fault == "mask":
        profile["runtime_layout"]["scenario_mask"] &= ~0x40000000
    elif fault == "value":
        profile["runtime_layout"]["scenario_value"] |= 0x40000000
    elif fault == "reset":
        profile["runtime_layout"]["scenario_reset_mask"] = 0
    elif fault == "work":
        profile["runtime_layout"]["scenario_work_address_ps1"] = "0x800CE328"
    elif fault == "missing-reset":
        del profile["runtime_layout"]["scenario_reset_mask"]
    elif fault == "missing-work":
        del profile["runtime_layout"]["scenario_work_address_ps1"]
    else:
        profile["executable_identity"] = "different SHA256 " + "0" * 64
    assert (
        bind_scenario_context(profile, context.declaration_contract)
        is ScenarioSelectionFailure.NativeContract
    )
    assert scenario_context_layout(profile) is ScenarioSelectionFailure.NativeContract


def test_profile_layout_validation_does_not_mint_a_native_capability(profile):
    layout = scenario_context_layout(profile)
    assert isinstance(layout, ScenarioContextLayout)
    assert not isinstance(layout, VerifiedScenarioContext)
    assert not hasattr(layout, "declaration_contract")


@pytest.mark.parametrize("fault", ["address", "width", "duplicate"])
def test_profile_layout_requires_the_exact_status_bank_abi(profile, fault):
    bank = next(row for row in profile["flag_banks"] if row["bank"] == 1)
    if fault == "address":
        bank["address_ps1"] = "0x800CFBDC"
    elif fault == "width":
        bank["width"] = 8
    else:
        profile["flag_banks"].append(copy.deepcopy(bank))
    assert scenario_context_layout(profile) is ScenarioSelectionFailure.NativeContract


def test_result_invariants_reject_conflicting_or_implicit_facts():
    with pytest.raises(AssertionError):
        ScopedScenarioItems((154,), (ScenarioItemVariant(154, (100,)),))
    with pytest.raises(AssertionError):
        ScenarioItemVariant(True, (100,))
    with pytest.raises(AssertionError):
        ScenarioItemVariant(154, ())
