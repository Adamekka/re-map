"""RE2-SCENARIO-011: qualified identity effects, without presence rights."""

import json
from dataclasses import replace

import pytest
from test_re2_door_native_frames import polling
from test_re2_metadata import ROOT
from test_re2_native_frame_execution import execute as execute
from test_re2_positive_prefix import owned as owned
from test_re2_startup_declarations import END, contract, described

from games.re2.door_authority import compile_door_access
from games.re2.identity_filtering import (
    IdentityFilteringFailure,
    NormalEngineIdentityFiltering,
    normal_engine_identity_filtering,
)
from games.re2.known_puzzle_items import known_declared_items_from_prefix
from games.re2.native_control import TASK_BASE, TASK_WIDTH, ControlField, control_field
from games.re2.native_entry_fields import NativeTaskPhase, _task_fields, _TaskFields
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    SourceEntryPolicy,
    _source_entry_roles,
)
from games.re2.positive_prefix import (
    VerifiedNormalEnginePositivePrefix,
    normal_engine_positive_prefix,
)
from games.re2.scenario_entry_scope import (
    _ScopePolicy,
    _source_scope_facts,
    _SourceScopeFacts,
)
from games.re2.scenario_selection import (
    ScenarioItemVariant,
    ScenarioSourceWriteWitnesses,
    ScopedScenarioItems,
    SourceWritePolicy,
    bind_scenario_context,
    scenario_source_write_witnesses,
    scoped_scenario_items,
)
from games.re2.script_dispatch_items import script_item_dispatch
from games.re2.source_task_control import TaskControlSupport
from games.re2.structured_control import (
    ControlFrameFailure,
    ControlFrames,
    NativeStructuredControl,
    structured_control,
)


def test_owned_target_uses_public_identity_factory_and_preserves_both_alternatives(
    owned,
):
    p, _, _, _, sources, bound, entry, rooms = owned
    source, room = sources["01-19"], rooms["01-19"]
    result = normal_engine_identity_filtering(source, room, p, bound)
    assert type(result) is NormalEngineIdentityFiltering
    assert scoped_scenario_items(source, room, p, result.context, result) == (
        ScopedScenarioItems((), (ScenarioItemVariant(117, (2762,)),))
    )
    assert [(r["offset"], r["type"], r["amount"]) for r in room["items"]] == [
        (2762, 20, 15),
        (2826, 70, 1),
    ]
    generated = next(
        r
        for r in json.loads((ROOT / "data/rooms_slus00748.json").read_text())["rooms"]
        if r["id"] == "01-19"
    )
    assert generated["identity_filtering_items"] == {
        "absent_item_ids": [],
        "item_variants": [{"global_id": 117, "offsets": [2762]}],
    }
    assert not generated["collection_item_ids"]
    assert not generated["known_direct_pickups"] and not generated["known_puzzle_items"]
    assert (
        type(normal_engine_positive_prefix(source, room, p, bound))
        is not VerifiedNormalEnginePositivePrefix
    )
    with pytest.raises(AssertionError):
        known_declared_items_from_prefix(
            source, room, p, entry, script_item_dispatch(p), result
        )
    with pytest.raises(AssertionError):
        compile_door_access(source, room, p, result)


@pytest.mark.parametrize("nesting", range(6))
def test_wait_borrows_level_without_allocating_a_fifth_loop_frame(nesting):
    body = b"\x0b\x0c"
    for _ in range(nesting):
        body = (
            b"\x0d\0"
            + (len(body) + 2).to_bytes(2, "little")
            + b"\x01\0"
            + body
            + b"\x0e\0"
        )
    data, room, _ = described(END, (body + END, END))
    frame = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeIdentityFiltering
    )
    assert (type(frame) is NativeStructuredControl) is (nesting <= 4)
    if nesting <= 4:
        at = next(
            r["offset"]
            for r in room["programs"]["17:0"]["commands"]
            if r["opcode"] == 0x0B
        )
        assert dict(frame.edges)[at] == (at + 1,)
        assert dict(frame.edges)[at + 1] == (at + 1, at + 2)
        assert {
            (pos, write)
            for pos, field, _, write in frame.accesses
            if field is ControlField.LoopLevel
        } >= {(pos, write) for pos in (at, at + 1) for write in (False, True)}


@pytest.mark.parametrize(
    "body",
    [
        b"\x0b",
        b"\x0c",
        b"\x0b\0\x0c",
        b"\x0b\x02\0\x0c",
        b"\x0b\x18\x01\x0c",
        b"\x17\xff\xff\0\x07\0\x0b\x0c",
        b"\x18\x01\x0c",
        b"\x0b\x0c\x19\0",
        polling(b"\x0b\x0c")[:-2],
        b"\x06\0\x01\0\x0b\x0c\x08\0",
    ],
)
def test_wait_rejects_unpaired_or_branch_return_and_stale_token_ingress(body):
    data, room, _ = described(END, (body + END, END))
    assert (
        structured_control(
            data, room["programs"]["17:0"], ControlFrames.NativeIdentityFiltering
        )
        is ControlFrameFailure.Unsupported
    )


@pytest.mark.parametrize(
    "producer", [b"", b"\x04\xff\x18\x02", b"\x04\x02\x18\x02\x04\x02\x18\x02"]
)
def test_all_programs_check_pairs_and_producers_supply_real_task_depths(producer):
    for body, accepted in ((b"\x0b\x0c", True), (b"\x0c", False)):
        data, room, _ = described(END, (producer + END, END, body + END))
        result = _task_fields(
            data,
            room["programs"],
            phase=NativeTaskPhase.Ordinary,
            role=ControlFrames.NativeIdentityFiltering,
        )
        assert (type(result) is _TaskFields) is accepted
        if accepted:
            entries = {
                (task, depth) for key, task, depth in result.entries if key == "17:2"
            }
            assert entries == (
                set()
                if not producer
                else {
                    (task, 0) for task in (range(2, 10) if producer[1] == 255 else (2,))
                }
            )
            for key, _, task, depth, field, cell, width, _ in result.control:
                if key == "17:2" and field is ControlField.LoopLevel:
                    assert (cell, width) == (task * TASK_WIDTH + 8 + depth, 1)
            assert all(
                value == 255
                for *_, field, _, _, value in result.initializations
                if field is ControlField.LoopLevel
            )


@pytest.mark.parametrize("calls", [3, 4])
def test_wait_keeps_native_call_depth_limit(calls):
    programs = [b"\x18" + bytes((i + 1,)) + END for i in range(calls)] + [
        b"\x0b\x0c" + END
    ]
    data, room, _ = described(END, tuple(programs))
    result = _task_fields(
        data,
        room["programs"],
        phase=NativeTaskPhase.Ordinary,
        role=ControlFrames.NativeIdentityFiltering,
    )
    assert (type(result) is _TaskFields) is (calls == 3)
    if calls == 3:
        assert (f"17:{calls}", 1, calls) in result.entries


@pytest.fixture
def effect_scope(owned):
    p = owned[0]

    def check(body, policy, source_policy):
        data, room, _ = described(END, (body + END, END))
        context = bind_scenario_context(p, contract(p, room))
        writes = scenario_source_write_witnesses(
            data, room, p, policy=SourceWritePolicy.IdentityFiltering
        )
        if type(writes) is not ScenarioSourceWriteWitnesses:
            return writes
        roles = _source_entry_roles(
            data, room["programs"], writes, policy=source_policy
        )
        if type(roles) is PositiveEntryFailure:
            return roles
        return _source_scope_facts(
            data, room, p, context, policy, TaskControlSupport.Unaudited, roles
        )

    return check


@pytest.mark.parametrize(
    "category,index,accepted",
    [
        (3, 0, True),
        (3, 31, True),
        (3, 32, False),
        (3, 127, False),
        (3, 128, False),
        (3, 255, False),
        (0, 0, False),
        (1, 0, False),
        (2, 0, False),
        (4, 0, False),
        (255, 0, False),
    ],
)
def test_render60_requires_its_own_category_and_unsigned_actor_bounds(
    effect_scope, category, index, accepted
):
    body = bytes((0x60, category, index, 255, 128, 0)) + bytes.fromhex(
        "ffff00800000ff7f"
    )
    assert (
        type(
            effect_scope(
                body,
                _ScopePolicy.NativeIdentityFiltering,
                SourceEntryPolicy.NativeIdentityFiltering,
            )
        )
        is _SourceScopeFacts
    ) is accepted


@pytest.mark.parametrize(
    "value,accepted", [(0, True), (127, True), (128, False), (255, False)]
)
def test_audio5f_retains_only_its_explicit_scalar_domain(effect_scope, value, accepted):
    assert (
        type(
            effect_scope(
                bytes((0x5F, value)),
                _ScopePolicy.NativeIdentityFiltering,
                SourceEntryPolicy.NativeIdentityFiltering,
            )
        )
        is _SourceScopeFacts
    ) is accepted


@pytest.mark.parametrize(
    "mode,accepted", [(0, True), (1, False), (2, False), (255, False)]
)
def test_music59_keeps_mode_zero_only(effect_scope, mode, accepted):
    assert (
        type(
            effect_scope(
                bytes((0x59, mode, 0, 0)),
                _ScopePolicy.NativeIdentityFiltering,
                SourceEntryPolicy.NativeIdentityFiltering,
            )
        )
        is _SourceScopeFacts
    ) is accepted


@pytest.mark.parametrize(
    "body", [b"\x0b\x0c", b"\x5f\x7f", b"\x59\0\0\0", b"\x60\x03\0" + bytes(11)]
)
def test_old_identity_policy_receives_no_new_effect_right(effect_scope, body):
    assert (
        type(
            effect_scope(
                body,
                _ScopePolicy.IdentityFiltering,
                SourceEntryPolicy.IdentityFiltering,
            )
        )
        is not _SourceScopeFacts
    )


@pytest.mark.parametrize("body", [b"\x59\0\0\0", b"\x60\x03\0" + bytes(11)])
def test_native_halfword_source_reads_require_even_packet_offsets(effect_scope, body):
    assert (
        type(
            effect_scope(
                b"\0" + body,
                _ScopePolicy.NativeIdentityFiltering,
                SourceEntryPolicy.NativeIdentityFiltering,
            )
        )
        is not _SourceScopeFacts
    )


@pytest.mark.parametrize(
    "delta,word,accepted",
    [(i, False, 6 <= i < 14) for i in range(15)]
    + [(i, True, i in (6, 8, 10, 12)) for i in range(14)],
)
def test_render_copy_changes_only_aligned_numeric_halfwords(
    effect_scope, delta, word, accepted
):
    body = bytes((0x1D, 4, delta, word)) + b"\x60\x03\0" + bytes(11)
    assert (
        type(
            effect_scope(
                body,
                _ScopePolicy.NativeIdentityFiltering,
                SourceEntryPolicy.NativeIdentityFiltering,
            )
        )
        is _SourceScopeFacts
    ) is accepted


@pytest.mark.parametrize("packet", [b"\x0b\x0c", b"\x5f\x40", b"\x59\0\0\0"])
@pytest.mark.parametrize("word", [False, True])
def test_wait_and_audio_packets_get_no_copy_permission(effect_scope, packet, word):
    body = bytes((0x1D, 4, 1, word)) + packet
    assert (
        type(
            effect_scope(
                body,
                _ScopePolicy.NativeIdentityFiltering,
                SourceEntryPolicy.NativeIdentityFiltering,
            )
        )
        is not _SourceScopeFacts
    )


@pytest.mark.parametrize(
    "opcode,target",
    [
        (0x0B, 0x80053A8C),
        (0x0C, 0x80053AC0),
        (0x59, 0x80058028),
        (0x5F, 0x80058090),
        (0x60, 0x80058898),
    ],
)
def test_new_dispatch_entries_are_required_before_public_sealing(owned, opcode, target):
    p, _, exe, _, sources, bound, _, rooms = owned
    at = 0x800A74C8 + opcode * 4 - 0x80010000 + 0x800
    assert int.from_bytes(exe[at : at + 4], "little") == target
    changed = bytearray(exe)
    changed[at] ^= 1
    altered = replace(
        bound, entry_resources=replace(bound.entry_resources, executable=bytes(changed))
    )
    assert (
        normal_engine_identity_filtering(sources["01-19"], rooms["01-19"], p, altered)
        is IdentityFilteringFailure.Binding
    )


@pytest.mark.parametrize("task,depth", [(1, 0), (2, 1), (9, 3)])
@pytest.mark.parametrize("level", [0, 1, 2, 3, 255])
def test_unchanged_native_begin_increments_byte_without_frame_store(
    execute, task, depth, level
):
    current = TASK_BASE + task * TASK_WIDTH
    cell = current + control_field(depth, ControlField.LoopLevel, 0)[0]
    execute(
        0x80053A8C,
        task,
        depth,
        b"\x0b",
        [(cell, level, 1)],
        [(cell, (level + 1) & 255, 1), (current + 0x1C, 0x80180001, 4)],
    )


@pytest.mark.parametrize("task,depth", [(1, 0), (2, 1), (9, 3)])
@pytest.mark.parametrize("level", range(5))
@pytest.mark.parametrize("busy32,busy8", [(0, 0), (0x20, 0), (0, 0x80), (0x20, 0x80)])
def test_unchanged_native_wait_retains_busy_and_completion_edges(
    execute, task, depth, level, busy32, busy8
):
    current = TASK_BASE + task * TASK_WIDTH
    cell = current + control_field(depth, ControlField.LoopLevel, 0)[0]
    expected = (
        []
        if busy32 or busy8
        else [(cell, (level - 1) & 255, 1), (current + 0x1C, 0x80180001, 4)]
    )
    execute(
        0x80053AC0,
        task,
        depth,
        b"\x0c",
        [(cell, level, 1), (0x800CFBD8, busy32, 4), (0x800E873C, busy8, 1)],
        expected,
        result=2,
    )


@pytest.mark.parametrize("value", [0, 1, 70, 120, 127])
def test_unchanged_native5f_writes_only_fixed_audio_word(execute, value):
    execute(
        0x80058090,
        2,
        0,
        bytes((0x5F, value)),
        [],
        [(0x800D5B50, value, 4), (TASK_BASE + 2 * TASK_WIDTH + 0x1C, 0x80180002, 4)],
    )


@pytest.mark.parametrize("index", [0, 31])
@pytest.mark.parametrize("bits", [0, 0x7FFF, 0x8000, 0xFFFF])
def test_unchanged_native60_preserves_command_bytes_and_all_unowned_ram(
    execute, index, bits
):
    actor, record, stack, pc = 0x80170000, 0x80170040, 0x801E0000, 0x80180000
    values = (bits, bits ^ 0xFFFF, 0x8000, 0x7FFF)
    packet = bytes((0x60, 3, index, 0x12, 0x80, 0xFF)) + b"".join(
        v.to_bytes(2, "little") for v in values
    )
    initial = [
        (0x800CFE1C + 4 * index, actor, 4),
        (actor + 0x16C, record, 4),
        (record + 0x1C, 0xAB010203, 4),
        (record + 0x44, 0xCD040506, 4),
    ]
    expected = [
        (record + offset, value, 2)
        for offset, value in zip((4, 6, 0, 2), values, strict=True)
    ] + [
        (record + 0x1C, 0xABFF8012, 4),
        (record + 0x44, 0xCDFF8012, 4),
        (TASK_BASE + 2 * TASK_WIDTH + 0x1C, pc + 14, 4),
        (stack - 0x20 + 0x10, 0x11110010, 4),
        (stack - 0x20 + 0x14, 0x11110011, 4),
        (stack - 0x20 + 0x18, 0x801F0000, 4),
    ]
    execute(0x80058898, 2, 0, packet, initial, expected)
