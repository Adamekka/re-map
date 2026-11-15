"""RE2-DOOR-013: raw ingress, both IF39 edges and door-only operand rights."""

import copy
from dataclasses import replace

import pytest
from test_re2_initializer_control import described as framed
from test_re2_positive_prefix import owned as owned

from games.re2.door_authority import (
    DoorAuthority,
    compile_door_access,
    compile_door_authority,
)
from games.re2.door_operand_roles import DoorOperandRoles, door_operand_roles
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.native_control import TASK_WIDTH
from games.re2.native_entry_fields import NativeTaskPhase, _task_fields, _TaskFields
from games.re2.native_entry_inventory import (
    NativeEntryInventory,
    native_entry_inventory,
)
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    _foreign_fields_disjoint,
)
from games.re2.program_entry_domain import (
    EnteredFrameDomain,
    FrameDomain,
    entered_frame_domain,
)
from games.re2.room_data import decode_room
from games.re2.scenario_selection import (
    ScenarioSourceWriteWitnesses,
    SourceCopyWrite,
    SourceWritePolicy,
    scenario_source_write_witnesses,
)
from games.re2.structured_control import (
    ControlFrames,
    NativeStructuredControl,
    PredicateOutcome,
    StructuredControl,
    structured_control,
)


@pytest.fixture(scope="module")
def target(owned):
    profile, _, _, _, sources, bound, _, rooms = owned
    authority = compile_door_authority(sources["00-01"], rooms["00-01"], profile, bound)
    assert type(authority) is DoorAuthority
    return authority


def test_real_factory_gains_only_target_and_keeps_reset_alternatives(owned, target):
    profile, _, _, _, sources, _, _, rooms = owned
    facts, unsupported, excluded = compile_door_access(
        sources["00-01"], rooms["00-01"], profile, target
    )
    assert [
        (
            f.slot,
            f.creator_offsets,
            f.stage,
            f.room,
            f.floor,
            f.lock_id,
            f.lock_type,
            f.enabled,
            f.activation_mask,
        )
        for f in facts
    ] == [(1, (6082,), 0, 2, 0, 0, 0, True, 0x31)]
    assert unsupported == (
        {
            "slot": 0,
            "creator_offsets": [6050],
            "reasons": ["history_dependent_kind_reset"],
        },
    )
    assert not excluded
    binding = target.entry_binding
    assert type(binding.frame_domain) is EnteredFrameDomain
    assert len(binding.frame_domain.entered_programs) == 32
    assert set(rooms["00-01"]["programs"]) - binding.frame_domain.entered_programs == {
        "17:11",
        "17:12",
        "17:33",
        "17:34",
    }
    assert (
        set(dict(binding.source_fields.frames)) == binding.frame_domain.entered_programs
    )
    frame = dict(binding.source_fields.frames)["17:19"]
    assert dict(frame.edges)[8644] == (8652, 8656)
    assert binding.operands.copy_predicates == (("17:19", 8632, 8644),)
    assert {
        (task, depth)
        for key, task, depth in binding.source_fields.entries
        if key == "17:19"
    } == {(9, 0)}
    assert {
        offset
        for _, _, task, _, receiver, offset, _ in binding.source_fields.stores
        if task != receiver
    } == {0x64, 0x68}
    assert len(binding.auxiliary_fields) == 54 and len(binding.auxiliary_reads) == 126


@pytest.mark.parametrize("outcome", list(PredicateOutcome))
def test_canonical39_uses_actual_false_pop_and_true_else(outcome):
    data, room = framed(bytes.fromhex("06000c003900000000005e010700080022050001"))
    program = room["programs"]["17:0"]
    header = next(r for r in program["commands"] if r["opcode"] == 6)
    predicate = next(r for r in program["commands"] if r["opcode"] == 0x39)
    frame = structured_control(
        data,
        program,
        ControlFrames.NativeDoors,
        predicates=((predicate["offset"], outcome),),
    )
    assert type(frame) is NativeStructuredControl
    assert dict(frame.edges)[predicate["offset"]] == (
        predicate["next"],
        header["target"],
    )
    assert header["target"] in frame.reached
    assert any(
        at == predicate["offset"] and not write for at, _, _, write in frame.accesses
    )


def test_unframed39_has_no_continuation_right():
    data, room = framed(bytes.fromhex("3900000000005e01"))
    for role in ControlFrames:
        assert not isinstance(
            structured_control(data, room["programs"]["17:0"], role),
            StructuredControl,
        )


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "suspend",
        "operand",
        "counter",
        "work",
        "interior",
        "native",
        "source",
    ],
)
def test_bound_copy_prefix_rejects_missing_or_changed_dependencies(
    owned, target, fault
):
    profile, _, exe, _, sources, _, _, rooms = owned
    data, room = sources["00-01"], rooms["00-01"]
    if fault == "missing":
        fields = _task_fields(
            data,
            room["programs"],
            phase=NativeTaskPhase.Ordinary,
            role=ControlFrames.NativeDoors,
            frame_domain=target.entry_binding.frame_domain,
        )
        assert type(fields) is PositiveEntryFailure
        return
    raw = bytearray(exe if fault == "native" else data)
    if fault == "native":
        raw[0x800154EC - 0x80010000 + 0x800] ^= 1
        exe = bytes(raw)
    elif fault == "source":
        raw[0] ^= 1
        data = bytes(raw)
    else:
        at, packet = {
            "suspend": (8636, bytes.fromhex("090a0000")),
            "operand": (8638, b"\x04"),
            "counter": (8637, b"\x18"),
            "work": (8630, b"\x80"),
            "interior": (8686, bytes.fromhex("17ffff00ceff")),
        }[fault]
        raw[at : at + len(packet)] = packet
        data = bytes(raw)
        room = decode_room(
            data,
            room["source"],
            frozenset(
                (r["bank"], r["bit"]) for r in profile["presence_condition_flags"]
            ),
            presence_counter_indices(profile),
            presence_flag_write_proof(profile)[0],
        )
    writes = scenario_source_write_witnesses(
        data, room, profile, policy=SourceWritePolicy.NormalDoors
    )
    result = door_operand_roles(data, room, profile, exe, writes)
    if type(result) is DoorOperandRoles:
        assert not result.copy_predicates
    else:
        assert type(result) is str


@pytest.mark.parametrize(
    "offset,width", [(72, 2), (76, 2), (8632, 1), (8637, 1), (10214, 1)]
)
def test_copy_changes_to_raw_entry_control_or_write_metadata_withdraw_domain(
    owned, target, offset, width
):
    writes = replace(
        target.entry_binding.source_writes,
        copies=(
            *target.entry_binding.source_writes.copies,
            SourceCopyWrite(("17:0", 0), offset, width),
        ),
    )
    assert (
        entered_frame_domain(
            target.entry_binding.source_data, owned[-1]["00-01"], writes
        )
        is FrameDomain.Unproved
    )


@pytest.mark.parametrize(
    "kind", ["event", "call", "replacement", "callback", "reset", "unentered_producer"]
)
def test_actual_raw_ingress_changes_withdraw_unentered_owner_exclusion(owned, kind):
    profile, _, exe, _, sources, _, _, rooms = owned
    data, room = sources["00-01"], rooms["00-01"]
    raw = bytearray(data)
    key = "17:33" if kind == "unentered_producer" else "17:0"
    if kind in ("callback", "reset"):
        row = next(
            r
            for p in room["programs"].values()
            for r in p["commands"]
            if r["kind"] == ("reset" if kind == "reset" else "interaction")
        )
        at = row["offset"]
        payload = 4 if kind == "reset" else 22 if row["opcode"] == 0x67 else 14
        raw[at + 2] = 5
        raw[at + payload : at + payload + 4] = bytes((255, 0, 24, 34))
    else:
        row = next(
            r for r in room["programs"][key]["commands"] if r["next"] - r["offset"] >= 4
        )
        at = row["offset"]
        packet = (
            bytes((0x18, 34))
            if kind == "call"
            else bytes((3, 0, 24, 34))
            if kind == "replacement"
            else bytes((4, 255, 24, 34))
        )
        raw[at : row["next"]] = packet + bytes(row["next"] - at - len(packet))
    changed = decode_room(
        bytes(raw),
        room["source"],
        frozenset((r["bank"], r["bit"]) for r in profile["presence_condition_flags"]),
        presence_counter_indices(profile),
        presence_flag_write_proof(profile)[0],
    )
    inventory = native_entry_inventory(
        bytes(raw), changed["programs"], NativeTaskPhase.Ordinary
    )
    assert type(inventory) is NativeEntryInventory
    assert "17:34" in {key for key, _, _ in inventory.entries}
    writes = scenario_source_write_witnesses(
        bytes(raw), changed, profile, policy=SourceWritePolicy.NormalDoors
    )
    domain = entered_frame_domain(bytes(raw), changed, writes)
    if type(domain) is EnteredFrameDomain:
        assert "17:34" in domain.entered_programs
        # No mutable Work3 selector permission follows the new entry.
        assert (10215, 10217) not in domain.inert_operands
        operands = door_operand_roles(bytes(raw), changed, profile, exe, writes)
        assert type(operands) is DoorOperandRoles
        assert not isinstance(
            structured_control(
                bytes(raw), changed["programs"]["17:34"], ControlFrames.NativeDoors
            ),
            NativeStructuredControl,
        )
        assert (
            type(
                _task_fields(
                    bytes(raw),
                    changed["programs"],
                    phase=NativeTaskPhase.Ordinary,
                    role=ControlFrames.NativeDoors,
                    frame_domain=domain,
                    copy_predicates=operands.copy_predicates,
                )
            )
            is PositiveEntryFailure
        )


@pytest.mark.parametrize("cell", [0x64, 0x68])
def test_foreign_cells_check_every_auxiliary_and_reject_new_break_read(target, cell):
    binding = target.entry_binding
    for model, fields in binding.auxiliary_fields:
        actual = tuple(r[-1] for r in binding.auxiliary_reads if r[0] == model)
        assert _foreign_fields_disjoint(frozenset((cell,)), actual)
        assert not _foreign_fields_disjoint(frozenset((cell,)), (*actual, cell))
        assert type(fields) is _TaskFields
        assert not [
            row
            for row in fields.loop_reads
            if row[2] == 12 and cell <= row[4] + 3 and row[4] <= cell + 3
        ]
        assert not [
            row
            for row in fields.control
            if not row[7]
            and 12 * TASK_WIDTH + cell < row[5] + row[6]
            and row[5] < 12 * TASK_WIDTH + cell + 4
        ]


@pytest.mark.parametrize(
    "fault", ["owner", "native", "source", "ingress", "metadata", "operative"]
)
def test_real_factory_never_seals_missing_required_premise(owned, fault):
    p, _, _, _, sources, bound, _, rooms = owned
    profile, room, data = (
        copy.deepcopy(p),
        copy.deepcopy(rooms["00-01"]),
        sources["00-01"],
    )
    if fault == "owner":
        del profile["trusted_door_policy"]
    elif fault == "native":
        raw = bytearray(bound.entry_resources.executable)
        raw[0x80056610 - 0x80010000 + 0x800] ^= 1
        bound = replace(
            bound, entry_resources=replace(bound.entry_resources, executable=bytes(raw))
        )
    elif fault in ("source", "operative"):
        raw = bytearray(data)
        raw[8630 if fault == "operative" else 0] ^= 128
        data = bytes(raw)
    elif fault == "ingress":
        with pytest.raises(AssertionError):
            replace(
                bound,
                ordinary_ingress=replace(
                    bound.ordinary_ingress, preserved_counters=frozenset()
                ),
            )
        return
    else:
        room["programs"]["17:34"]["entry"] += 1
    result = compile_door_authority(data, room, profile, bound)
    assert type(result) is not DoorAuthority


def test_missing_no_entry_knowledge_runs_original_whole_source_frames(owned, target):
    data = target.entry_binding.source_data
    programs = owned[-1]["00-01"]["programs"]
    for domain in FrameDomain:
        assert (
            type(
                _task_fields(
                    data,
                    programs,
                    phase=NativeTaskPhase.Ordinary,
                    role=ControlFrames.NativeDoors,
                    frame_domain=domain,
                    copy_predicates=target.entry_binding.operands.copy_predicates,
                )
            )
            is PositiveEntryFailure
        )


@pytest.mark.parametrize("selector", range(6))
def test_effect_tail_binding_never_grants_header_selector_copy(owned, target, selector):
    profile, _, exe, _, sources, _, _, rooms = owned
    raw = bytearray(sources["00-01"])
    raw[10022] = selector
    data = bytes(raw)
    room = decode_room(
        data,
        rooms["00-01"]["source"],
        frozenset((r["bank"], r["bit"]) for r in profile["presence_condition_flags"]),
        presence_counter_indices(profile),
        presence_flag_write_proof(profile)[0],
    )
    writes = scenario_source_write_witnesses(
        data, room, profile, policy=SourceWritePolicy.NormalDoors
    )
    assert (
        door_operand_roles(data, room, profile, exe, writes)
        == "door_effect_selector_mutation"
    )
    # The other three policies receive no tail range from the new native role.
    assert (10038, 10040) in target.entry_binding.operands.effect_tails


def test_validated_numeric_copies_preserve_projection_without_identity_promotion(owned):
    from games.re2.identity_filtering import (
        IdentityFilteringFailure,
        normal_engine_identity_filtering,
    )
    from games.re2.positive_entry_domain import (
        SourceEntryPolicy,
        _NativeIdentityEntryRoles,
        _source_entry_roles,
    )

    p, _, _, _, sources, bound, _, rooms = owned
    data, room = sources["01-04"], rooms["01-04"]
    writes = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.IdentityFiltering
    )
    domain = entered_frame_domain(data, room, writes)
    assert type(domain) is EnteredFrameDomain and len(writes.copies) == 8
    source = _source_entry_roles(
        data,
        room["programs"],
        writes,
        policy=SourceEntryPolicy.NativeIdentityFiltering,
        frame_domain=domain,
    )
    assert type(source) is _NativeIdentityEntryRoles
    assert (
        normal_engine_identity_filtering(data, room, p, bound)
        is IdentityFilteringFailure.Dispatch
    )


@pytest.mark.parametrize("fault", ["source", "programs", "empty", "entries"])
def test_source_bound_frame_domain_cannot_be_reused_with_changed_dependencies(
    owned, target, fault
):
    data, programs = target.entry_binding.source_data, owned[-1]["00-01"]["programs"]
    domain = target.entry_binding.frame_domain
    if fault == "source":
        data = bytes((data[0] ^ 1,)) + data[1:]
    elif fault == "programs":
        programs = copy.deepcopy(programs)
        programs["17:34"]["entry"] += 1
    elif fault == "empty":
        domain = replace(domain, entered_programs=frozenset())
    else:
        domain = replace(
            domain,
            inventory=replace(domain.inventory, entries=domain.inventory.entries[:-1]),
        )
    assert (
        _task_fields(
            data,
            programs,
            phase=NativeTaskPhase.Ordinary,
            role=ControlFrames.NativeDoors,
            frame_domain=domain,
            copy_predicates=target.entry_binding.operands.copy_predicates,
        )
        is PositiveEntryFailure.Binding
    )


def test_effect_tail_does_not_leak_to_positive_identity_or_unbound_door_policies(owned):
    from test_re2_startup_declarations import END, contract, described

    from games.re2.positive_entry_domain import SourceEntryPolicy, _source_entry_roles
    from games.re2.scenario_entry_scope import (
        DoorSourceFailure,
        _ScopePolicy,
        _source_scope_facts,
    )
    from games.re2.scenario_selection import bind_scenario_context
    from games.re2.source_task_control import TaskControlSupport

    profile = owned[0]
    packet = owned[4]["00-01"][10024:10040]
    data, room, _ = described(END, (bytes.fromhex("1d040e01") + packet + END, END))
    writes = scenario_source_write_witnesses(data, room, profile)
    assert type(writes) is ScenarioSourceWriteWitnesses
    for policy in SourceEntryPolicy:
        assert (
            _source_entry_roles(data, room["programs"], writes, policy=policy)
            is PositiveEntryFailure.SourceWrite
        )
    context = bind_scenario_context(profile, contract(profile, room))
    assert _source_scope_facts(
        data,
        room,
        profile,
        context,
        _ScopePolicy.TrustedDoors,
        TaskControlSupport.Unaudited,
    ) == DoorSourceFailure("copy_changes_unclosed_operand")


def test_gosub_in_unentered_owner_cannot_reuse_prior_exclusion(owned, target):
    profile, _, _, _, sources, bound, _, rooms = owned
    room = rooms["00-01"]
    row = next(
        r for r in room["programs"]["17:33"]["commands"] if r["next"] - r["offset"] >= 4
    )
    raw = bytearray(sources["00-01"])
    raw[row["offset"] : row["next"]] = bytes((0x18, 34)) + bytes(
        row["next"] - row["offset"] - 2
    )
    data = bytes(raw)
    changed = decode_room(
        data,
        room["source"],
        frozenset((r["bank"], r["bit"]) for r in profile["presence_condition_flags"]),
        presence_counter_indices(profile),
        presence_flag_write_proof(profile)[0],
    )
    changed.update(id="00-01", stage=0, room=1)
    inventory = native_entry_inventory(
        data, changed["programs"], NativeTaskPhase.Ordinary
    )
    assert type(inventory) is NativeEntryInventory
    assert ("17:33", "17:34") in inventory.calls
    assert not target.entry_binding.frame_domain.matches(
        data, changed["programs"], inventory
    )
    assert (
        type(compile_door_authority(data, changed, profile, bound)) is not DoorAuthority
    )
