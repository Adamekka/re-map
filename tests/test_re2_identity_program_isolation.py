"""RE2-SCENARIO-012: isolation never grants an unowned member write."""

import hashlib
from dataclasses import replace

import pytest
from test_re2_native_frame_execution import execute as execute
from test_re2_positive_prefix import owned as owned

from games.re2.identity_filtering import (
    IdentityFilteringPolicy,
    NormalEngineIdentityFiltering,
    normal_engine_identity_filtering,
)
from games.re2.identity_program_isolation import (
    IdentityIsolationSupport,
    IdentityProgramIsolation,
    identity_program_isolation,
)
from games.re2.identity_source_effects import (
    _MEMBER_WINDOWS,
    IdentitySourceFailure,
    identity_primitive_reservations,
    member_if_predicates,
)
from games.re2.native_control import (
    TASK_BASE,
    TASK_WIDTH,
    ControlField,
    NumericCountPolicy,
    control_field,
    native_nonyielding,
    numeric_count_word,
)
from games.re2.native_entry_fields import NativeTaskPhase, _task_fields
from games.re2.native_sound_calls import SoundReaderFailure, sound_reader_scalar_calls
from games.re2.positive_entry_domain import _foreign_fields_disjoint
from games.re2.room_sound_bindings import (
    InitialSoundLayout,
    RoomSoundBindingFailure,
    RoomSoundBindings,
    compacted_sound_layout,
    room_sound_bindings,
)
from games.re2.room_write_partitions import SourceRange
from games.re2.scenario_entry_scope import (
    DoorSourceFailure,
    _ScopePolicy,
    _source_scope_facts,
)
from games.re2.scenario_selection import (
    ScenarioSelectionFailure,
    SourceCopyWrite,
    bind_scenario_context,
    scoped_scenario_items,
)
from games.re2.source_task_control import TaskControlSupport
from games.re2.structured_control import ControlFrames


@pytest.fixture(scope="module")
def target(owned):
    profile, _, _, _, sources, bound, _, rooms = owned
    cap = normal_engine_identity_filtering(
        sources["03-05"], rooms["03-05"], profile, bound
    )
    assert type(cap) is NormalEngineIdentityFiltering
    return cap


def derive(owned, cap, **changes):
    profile, _, _, _, sources, bound, _, rooms = owned
    inputs = dict(
        data=sources["03-05"],
        room=rooms["03-05"],
        profile=profile,
        bound=bound,
        native=cap.native_entries,
        source=cap.source_roles,
        writes=cap.source_writes,
        auxiliary_fields=cap.auxiliary_fields,
        auxiliary_reads=cap.auxiliary_break_reads,
        registered=cap.must_registered,
        dispatches=cap.dispatches,
        owner=IdentityFilteringPolicy.TrustedNormalEngine,
    )
    inputs.update(changes)
    return identity_program_isolation(**inputs)


def test_target_joint_preflight_keeps_raw_candidates_and_opaque_ifs(owned, target):
    profile, _, _, _, sources, bound, _, rooms = owned
    isolation = target.program_isolation
    assert type(isolation) is IdentityProgramIsolation
    assert set(rooms["03-05"]["programs"]) - isolation.entered_programs == {"17:6"}
    assert len(isolation.entered_programs) == 12
    assert target.protected_programs == frozenset(rooms["03-05"]["programs"])
    assert (72, 4) in isolation.protected_source and (
        76,
        4,
    ) in isolation.protected_source
    assert (3728, 2100) not in isolation.protected_source
    assert all(
        any(
            start <= row["offset"] < start + width
            for start, width in isolation.protected_source
        )
        for program in rooms["03-05"]["programs"].values()
        for row in program["commands"]
    )
    assert [
        (f.offset, f.if_cells, f.work_offsets) for f in target.member_if_predicates
    ] == [
        (3760, (0xC0,), (3752,)),
        (3806, (0xC4,), (3798,)),
        (3860, (0xC0,), (3752, 3798)),
        (4118, (0xC0,), (4110,)),
    ]
    result = scoped_scenario_items(
        sources["03-05"],
        rooms["03-05"],
        profile,
        bind_scenario_context(profile, bound.declarations),
        target,
    )
    assert result.absent_item_ids == ()
    assert [(r.global_id, r.offsets) for r in result.item_variants] == [(191, (3922,))]
    assert [
        (r["offset"], r["type"], r["amount"])
        for r in rooms["03-05"]["items"]
        if r["global_id"] == 191
    ] == [(3896, 31, 1), (3922, 21, 7)]
    assert any(
        r["offset"] == 3866 and r["global_id"] == 190 for r in rooms["03-05"]["items"]
    )


@pytest.mark.parametrize(
    "fault",
    [
        "no_owner",
        "native",
        "native_windows",
        "aux",
        "frame",
        "source",
        "dispatch",
        "descriptor",
        "compaction",
        "allocation",
    ],
)
def test_missing_isolation_premise_withdraws_exclusion(owned, target, fault):
    changes = {}
    if fault == "no_owner":
        changes["owner"] = IdentityFilteringPolicy.Unaudited
    if fault == "native":
        changes["native"] = IdentityIsolationSupport.Binding
    if fault == "native_windows":
        changes["native"] = replace(target.native_entries, windows=())
    if fault == "aux":
        changes["auxiliary_fields"] = target.auxiliary_fields[:-1]
    if fault == "frame":
        changes["source"] = replace(
            target.source_roles,
            native_fields=replace(
                target.source_roles.native_fields,
                frames=target.source_roles.native_fields.frames[:-1],
            ),
        )
    if fault == "source":
        changes["data"] = bytes((target.source_data[0] ^ 1,)) + target.source_data[1:]
    if fault == "dispatch":
        changes["dispatches"] = ()
    if fault == "descriptor":
        room = dict(owned[-1]["03-05"])
        programs = dict(room["programs"])
        key = next(
            k
            for k, p in programs.items()
            if any(r["kind"] == "reset" for r in p["commands"])
        )
        program = dict(programs[key])
        rows = [dict(r) for r in program["commands"]]
        reset = next(r for r in rows if r["kind"] == "reset")
        reset["interaction"] = 5
        program["commands"] = rows
        programs[key] = program
        room["programs"] = programs
        changes["room"] = room
    if fault == "compaction":
        changes["source"] = replace(target.source_roles, compactions=())
    if fault == "allocation":
        changes["source"] = replace(target.source_roles, primitive_reservations=())
    assert type(derive(owned, target, **changes)) is IdentityIsolationSupport


@pytest.mark.parametrize("region", [(72, 4), (76, 4), (3628, 1), (5827, 1)])
def test_explicit_metadata_write_withdraws_isolation(owned, target, region):
    writes = replace(
        target.source_writes,
        record_writes=(*target.source_writes.record_writes, SourceRange(*region)),
    )
    assert derive(owned, target, writes=writes) is IdentityIsolationSupport.Metadata


@pytest.mark.parametrize(
    "mode", ["whole", "producer", "call", "replacement", "interior"]
)
def test_entry_changes_require_operative_checks_and_reject_the_unowned_store(
    owned, target, mode
):
    p, _, _, _, sources, bound, _, rooms = owned
    room = rooms["03-05"]
    source = target.source_roles
    fields = source.native_fields
    if mode == "whole":
        isolation = IdentityIsolationSupport.WholeSource
    else:
        fields = replace(fields, entries=(*fields.entries, ("17:6", 2, 0)))
        if mode == "producer":
            fields = replace(
                fields, producers=(*fields.producers, ("17:0", 0, "17:6", (2,)))
            )
        if mode == "call":
            fields = replace(fields, calls=(*fields.calls, ("17:0", "17:6")))
        if mode == "replacement":
            fields = replace(
                fields, replacements=(*fields.replacements, ("17:0", 0, "17:6"))
            )
        if mode == "interior":
            frame = dict(fields.frames)["17:0"]
            frame = replace(
                frame,
                edges=(*frame.edges, (room["programs"]["17:0"]["entry"], (5575,))),
            )
            fields = replace(
                fields,
                frames=tuple(
                    (k, frame if k == "17:0" else f) for k, f in fields.frames
                ),
            )
        source = replace(
            source,
            native_fields=fields,
            entry_locations=source.entry_locations | {("17:6", 5574)},
        )
        isolation = derive(owned, target, source=source)
        if mode == "interior":
            assert isolation is IdentityIsolationSupport.Entries
        else:
            # A changed raw entry cannot reuse the old entered-only frames.
            # The real compiler must derive the new domain and check that owner.
            assert isolation is IdentityIsolationSupport.Entries
    assert (
        type(
            _source_scope_facts(
                sources["03-05"],
                room,
                p,
                bind_scenario_context(p, bound.declarations),
                _ScopePolicy.NativeIdentityFiltering,
                TaskControlSupport.Unaudited,
                source,
                isolation=isolation,
            )
        )
        is ScenarioSelectionFailure
    )


def test_isolation_is_not_a_positive_or_door_permission(owned, target):
    p, _, _, _, sources, bound, _, rooms = owned
    for policy in (
        _ScopePolicy.TrustedPositivePrefix,
        _ScopePolicy.TrustedDoors,
        _ScopePolicy.AuditedNativeWork,
    ):
        result = _source_scope_facts(
            sources["03-05"],
            rooms["03-05"],
            p,
            bind_scenario_context(p, bound.declarations),
            policy,
            TaskControlSupport.Unaudited,
            target.source_roles,
            isolation=target.program_isolation,
        )
        assert type(result) in (ScenarioSelectionFailure, DoorSourceFailure)


@pytest.mark.parametrize("offset", range(0x9C, 0xC4))
def test_numeric_word_permission_covers_only_complete_aligned_counts(offset):
    accepted = offset in range(0xA0, 0xC0, 4)
    assert numeric_count_word(offset) is accepted
    assert _foreign_fields_disjoint(
        frozenset((offset,)), (), numeric_counts=NumericCountPolicy.IdentityConservative
    ) is (accepted or _foreign_fields_disjoint(frozenset((offset,)), ()))
    if accepted:
        assert not _foreign_fields_disjoint(frozenset((offset,)), ())
        assert not _foreign_fields_disjoint(
            frozenset((offset,)),
            (offset,),
            numeric_counts=NumericCountPolicy.IdentityConservative,
        )


def test_no_pointer_or_level_field_is_numeric_count_storage():
    for depth in range(4):
        for field, indices in (
            (ControlField.Active, (0,)),
            (ControlField.IfLevel, (0,)),
            (ControlField.LoopLevel, (0,)),
            (ControlField.IfPointer, (0,)),
            (ControlField.CallReturn, (0,)),
            (ControlField.CallDepth, (0,)),
            (ControlField.ProgramCounter, (0,)),
            (ControlField.LoopStart, range(4)),
            (ControlField.LoopEnd, range(4)),
            (ControlField.SavedIf, range(4)),
            (ControlField.IfTarget, range(0xC0, 0xE0, 4)),
        ):
            for index in indices:
                cell, _ = control_field(depth, field, index)
                assert not numeric_count_word(cell)


def test_count_role_cannot_be_given_to_door_frames(owned):
    with pytest.raises(AssertionError):
        _task_fields(
            owned[4]["03-05"],
            owned[-1]["03-05"]["programs"],
            phase=NativeTaskPhase.Ordinary,
            role=ControlFrames.NativeDoors,
            numeric_counts=NumericCountPolicy.IdentityConservative,
        )


@pytest.mark.parametrize("fault", ["floor", "edt", "vab", "directory", "mask"])
def test_both_compacted_layouts_rederive_current_ranges(owned, target, fault):
    for fact in target.source_roles.compactions:
        layout = fact.layout
        origin = layout.origin
        assert origin.section_offsets[5] == 55028 and origin.section_offsets[2] == 58324
        assert (
            hashlib.sha256(origin.source_data).hexdigest()
            == owned[-1]["03-05"]["sha256"]
        )
        assert (
            type(room_sound_bindings(layout, frozenset(range(48)))) is RoomSoundBindings
        )
        changes = {
            "floor": {"retained_floor": origin.retained_floor},
            "edt": {"edt": layout.edt + 4},
            "vab": {"vab": layout.vab + 4},
            "directory": {"directory_pairs": ()},
            "mask": {"mask": 0},
        }[fault]
        assert (
            room_sound_bindings(replace(layout, **changes), frozenset(range(48)))
            is RoomSoundBindingFailure.Layout
        )
    initial = InitialSoundLayout(
        owned[4]["03-05"], tuple(owned[-1]["03-05"]["section_offsets"]), 58324
    )
    assert compacted_sound_layout(initial, 0xE0000000) is RoomSoundBindingFailure.Layout


def test_cached_reader_calls_are_exact_local_facts(owned):
    exe = owned[2]
    facts = sound_reader_scalar_calls(exe)
    assert type(facts) is tuple and len(facts) == 8
    assert not native_nonyielding(exe, 0x8005C040, {})
    assert native_nonyielding(exe, 0x8005C040, {}, scalar_calls=facts)
    assert not native_nonyielding(exe, 0x8005C040, {}, scalar_calls=facts[:-1])
    assert not native_nonyielding(exe, 0x800395B8, {}, scalar_calls=facts)
    for divisor in (0, -1, 2, 0xFFFFFFFF):
        changed = (
            replace(facts[0], arguments=(divisor, *facts[0].arguments[1:])),
            *facts[1:],
        )
        assert not native_nonyielding(exe, 0x8005C040, {}, scalar_calls=changed)
    raw = bytearray(exe)
    raw[0x8005C1B4 - 0x80010000 + 0x800] ^= 1
    assert sound_reader_scalar_calls(bytes(raw)) is SoundReaderFailure.Binding


@pytest.mark.parametrize("window", _MEMBER_WINDOWS)
def test_member_native_window_or_table_mutation_withdraws_role(owned, target, window):
    raw = bytearray(owned[2])
    raw[window[0] - 0x80010000 + 0x800] ^= 1
    assert (
        member_if_predicates(
            target.source_data,
            owned[-1]["03-05"]["programs"],
            target.source_roles.native_fields,
            bytes(raw),
        )
        is IdentitySourceFailure.Native
    )


@pytest.mark.parametrize(
    "offset,value", [(3761, 1), (3762, 5), (3763, 7), (3753, 2), (3799, 2)]
)
def test_member_operand_or_work_mutations_withdraw_location(
    owned, target, offset, value
):
    raw = bytearray(target.source_data)
    raw[offset] = value
    facts = member_if_predicates(
        bytes(raw),
        owned[-1]["03-05"]["programs"],
        target.source_roles.native_fields,
        owned[2],
    )
    assert type(facts) is tuple
    assert (
        3760 not in {f.offset for f in facts}
        if offset < 3790
        else 3806 not in {f.offset for f in facts}
    )


@pytest.mark.parametrize(
    "fault", ["zero", "owner", "repeat", "later_compaction", "copy", "native"]
)
def test_primitive_reservation_requires_positive_once_owned_input(owned, target, fault):
    p, _, exe, _, _, _, _, rooms = owned
    room = rooms["03-05"]
    data = target.source_data
    fields = target.source_roles.native_fields
    writes = target.source_writes
    owner = IdentityFilteringPolicy.TrustedNormalEngine
    if fault == "zero":
        raw = bytearray(data)
        raw[4555] = 0
        data = bytes(raw)
    if fault == "owner":
        owner = IdentityFilteringPolicy.Unaudited
    if fault == "repeat":
        fields = replace(
            fields, producers=(*fields.producers, ("17:0", 0, "17:3", (2,)))
        )
    if fault == "later_compaction":
        room = dict(room)
        programs = dict(room["programs"])
        main = dict(programs["17:0"])
        main["commands"] = [
            *main["commands"],
            dict(offset=4108, next=4109, opcode=0x6C, kind="other"),
        ]
        programs["17:0"] = main
        room["programs"] = programs
    if fault == "copy":
        writes = replace(
            writes, copies=(*writes.copies, SourceCopyWrite(("17:0", 0), 4555, 1))
        )
    if fault == "native":
        raw = bytearray(exe)
        raw[0x800582F0 - 0x80010000 + 0x800] ^= 1
        exe = bytes(raw)
    result = identity_primitive_reservations(
        data, room, p, fields, writes, exe, target.source_roles.compactions, owner
    )
    assert type(result) is IdentitySourceFailure


@pytest.mark.parametrize("operation", range(7))
@pytest.mark.parametrize(
    "lhs,rhs",
    [
        (0, -32768),
        (0, -1),
        (0, 0),
        (0, 1),
        (13, 14),
        (14, 14),
        (15, 14),
        (255, 255),
        (255, 32767),
        (255, 256),
        (255, -1),
    ],
)
def test_original_member6_handler_boolean_and_full_ram(execute, operation, lhs, rhs):
    answer = (
        lhs == rhs,
        lhs > rhs,
        lhs >= rhs,
        lhs < rhs,
        lhs <= rhs,
        lhs != rhs,
        bool(lhs & rhs),
    )[operation]
    current = TASK_BASE + TASK_WIDTH
    work = 0x80170000
    pc = 0x80180000
    stack = 0x801E0000
    ret = 0x801F0000
    packet = bytes((0x3E, 0, 6, operation)) + rhs.to_bytes(2, "little", signed=True)
    execute(
        0x80055E8C,
        1,
        0,
        packet,
        [(current + 0x154, work, 4), (work + 8, lhs, 1)],
        [
            (current + 0x1C, pc + 6, 4),
            (stack - 8, ret, 4),
            (stack - 12, 0x11110011, 4),
            (stack - 16, 0x11110010, 4),
        ],
        result=int(answer),
    )


@pytest.mark.parametrize("shape", ["if", "standalone", "do", "foreign"])
def test_new_member_role_requires_an_owned_if_prefix(owned, shape):
    from test_re2_startup_declarations import END, described

    from games.re2.positive_entry_domain import PositiveEntryFailure

    work = b"\x2e\x01\0\0"
    member = b"\x3e\0\x06\0\x0e\0"
    if shape == "if":
        body = work + b"\x06\0\x08\0" + member + b"\x08\0" + END
    elif shape == "standalone":
        body = work + member + END
    elif shape == "do":
        # The existing DO predicate parser deliberately has no member6 role.
        body = work + b"\x0f\x06\x08\0" + member + b"\x10\0" + END
    else:
        block = b"\x06\0\x08\0" + member + b"\x08\0"
        # FF Goto installs foreign scratch; only fresh CK/CMP can consume it.
        body = (
            work
            + block
            + b"\x17\xff\xff\0"
            + (-len(block)).to_bytes(2, "little", signed=True)
            + END
        )
    data, room, _ = described(END, (body, END))
    fields = _task_fields(
        data,
        room["programs"],
        phase=NativeTaskPhase.Ordinary,
        role=ControlFrames.NativeIdentityFiltering,
        numeric_counts=NumericCountPolicy.IdentityConservative,
    )
    if shape in ("do", "foreign"):
        assert type(fields) is PositiveEntryFailure
    else:
        facts = member_if_predicates(data, room["programs"], fields, owned[2])
        assert len(facts) == (1 if shape == "if" else 0)


@pytest.mark.parametrize(
    "fault", ["member", "work", "creator", "profile", "native", "metadata", "seal"]
)
def test_genuine_factory_and_seal_reject_target_input_substitution(owned, fault):
    import copy

    from games.re2.identity_filtering import IdentityFilteringFailure

    profile, _, _, _, sources, bound, _, rooms = owned
    profile = copy.deepcopy(profile)
    room = copy.deepcopy(rooms["03-05"])
    data = sources["03-05"]
    if fault in ("member", "work", "creator"):
        at = {"member": 3762, "work": 3753, "creator": 3922}[fault]
        raw = bytearray(data)
        raw[at] ^= 1
        data = bytes(raw)
    if fault == "profile":
        profile["runtime_layout"]["system_mode_value"] = 0
    if fault == "native":
        raw = bytearray(bound.entry_resources.executable)
        raw[0x80055FC0 - 0x80010000 + 0x800] ^= 1
        bound = replace(
            bound, entry_resources=replace(bound.entry_resources, executable=bytes(raw))
        )
    if fault == "metadata":
        room["items"][0]["type"] = True
    cap = normal_engine_identity_filtering(data, room, profile, bound)
    if fault == "seal":
        assert type(cap) is NormalEngineIdentityFiltering
        object.__setattr__(
            cap, "program_isolation", IdentityIsolationSupport.WholeSource
        )
        with pytest.raises(AssertionError):
            cap.matches(data, room, profile, cap.context)
    else:
        assert type(cap) is IdentityFilteringFailure
