"""Candidate bounded registration/pickup effects through the real consumer."""

import copy
import hashlib
import struct
from dataclasses import replace

import pytest
from test_re2_native_frame_execution import execute as execute  # noqa: PLC0414
from test_re2_positive_prefix import owned as owned  # noqa: PLC0414
from test_re2_startup_declarations import END, described, item

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.identity_filtering import (
    IdentityFilteringFailure,
    NormalEngineIdentityFiltering,
    _identity_dispatch,
    _IdentityDispatch,
    _IdentityDispatchKind,
    normal_engine_identity_filtering,
)
from games.re2.identity_pickup_effects import (
    _PICKUP_WINDOWS,
    NormalPickupFailure,
    PickupSourceDomain,
    normal_pickup_source_domain,
)
from games.re2.native_control import (
    TASK_BASE,
    TASK_WIDTH,
    NumericCountPolicy,
    native_nonyielding,
)
from games.re2.native_entry_fields import NativeTaskPhase, _task_fields, _TaskFields
from games.re2.native_entry_inventory import native_entry_inventory
from games.re2.positive_entry_domain import PositiveEntryFailure, _auxiliary_break_reads
from games.re2.program_entry_domain import EnteredFrameDomain, entered_frame_domain
from games.re2.room_data import decode_room
from games.re2.room_write_partitions import SourceRange
from games.re2.scenario_selection import (
    ScopedScenarioItems,
    SourceWritePolicy,
    scenario_source_write_witnesses,
    scoped_scenario_items,
)
from games.re2.source_registration import guaranteed_registration
from games.re2.structured_control import (
    ControlFrames,
    NativeStructuredControl,
    PredicateOutcome,
    structured_control,
)


@pytest.fixture(scope="module")
def pickup(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    result = normal_engine_identity_filtering(
        sources["01-04"], rooms["01-04"], p, bound
    )
    assert type(result) is NormalEngineIdentityFiltering
    return result


def test_actual_factory_and_consumer_exclude_gid0_without_new_presence(owned, pickup):
    p, _, _, _, sources, bound, _, rooms = owned
    result = scoped_scenario_items(
        sources["01-04"], rooms["01-04"], p, pickup.context, pickup
    )
    assert result == ScopedScenarioItems((0,), ())
    assert len(pickup.auxiliary_fields) == 54
    assert len(pickup.auxiliary_break_reads) == 126
    assert 4 in pickup.must_registered
    assert guaranteed_registration(
        pickup.source_data,
        rooms["01-04"],
        pickup.source_roles.edges,
        atomic_opcodes=bound.ordinary_ingress.atomic_opcodes,
    ) == frozenset((0, 1, 2))
    assert {f.slot for f in pickup.dispatches} == {4}
    assert pickup.dispatches[0].kind is _IdentityDispatchKind.NormalPickup
    assert pickup.dispatches[0].effect in pickup.pickup_effects
    assert {e.slot for e in pickup.pickup_effects} == {4, 5}
    effect = pickup.dispatches[0].effect
    assert [
        (o.offset, o.item_type, o.amount, o.global_id, o.physical)
        for o in effect.origins
    ] == [(6732, 20, 15, 3, (255, 1))]
    assert effect.disabled_counters == frozenset((0, 1))
    assert effect.inventory_extent == (0x800D4A38, 0x800D4E38)
    assert effect.header_timeline == (0x800DCBCC, 0x800A93A8, 0x80068EE4, 0x8003210C)
    assert not hasattr(effect, "quantity") and not hasattr(effect, "present")
    assert not {"17:12", "17:23", "17:24"} & pickup.program_isolation.entered_programs
    assert len(pickup.source_roles.native_fields.frames) == 21
    assert len(pickup.source_roles.native_fields.entries) == 119


def test_registration_binds_fixed_ck_but_keeps_unknown_both_paths(pickup):
    control = pickup.registration_control
    edges = {(key, at): targets for key, at, targets in control.edges}
    assert edges["16:0", 6466] == (6548,)
    assert edges["17:0", 6608] == (6616,)
    assert edges["17:0", 6620] == (6634,)
    assert edges["17:0", 6718] == (6722, 6732)
    assert ("17:0", 6726, "17:6", tuple(range(2, 10))) in control.births
    fixed = {
        (key, at): (packet, address, mask, actual)
        for key, at, packet, address, mask, actual in control.fixed_packets
    }
    assert fixed["17:0", 6608] == (bytes.fromhex("21010601"), 0x800CFBD8, 0x02000000, 0)


@pytest.mark.parametrize(
    "prefix", [END, b"\x02\0", b"\x04\0\x18\x01", b"\x04\x01\x18\x01"]
)
def test_registration_keeps_early_end_yield_and_owner_replacement_boundaries(prefix):
    data, room, _ = described(END, (prefix + item(slot=4) + END, END))
    frame = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeIdentityRegistration
    )
    assert type(frame) is NativeStructuredControl
    edges = tuple(("17:0", at, targets) for at, targets in frame.edges)
    assert 4 not in guaranteed_registration(
        data, room, edges, atomic_opcodes=frozenset((0x4E, 2, 4))
    )


def test_lost_fixed_predicate_retains_early_end():
    body = bytes.fromhex("060008002101060101000800") + item(slot=4) + END
    data, room, _ = described(END, (body, END))
    at = room["programs"]["17:0"]["entry"] + 4
    frames = [
        structured_control(
            data,
            room["programs"]["17:0"],
            ControlFrames.NativeIdentityRegistration,
            predicates=predicates,
        )
        for predicates in ((), ((at, PredicateOutcome.DoesNotMatch),))
    ]
    results = [
        guaranteed_registration(
            data,
            room,
            tuple(("17:0", at, targets) for at, targets in frame.edges),
            atomic_opcodes=frozenset((6, 7, 8, 0x21, 0x4E)),
        )
        for frame in frames
    ]
    assert 4 not in results[0] and 4 in results[1]


@pytest.mark.parametrize("owner", [0, 1])
@pytest.mark.parametrize("free", [2, 5, 9, None])
def test_original_auto_installer_preserves_initializer_continuation(
    execute, owner, free
):
    table, continuation, ret, stack = 0x80170000, 0x80180004, 0x801F0000, 0x801E0000
    selected = 9 if free is None else free
    target = TASK_BASE + selected * TASK_WIDTH
    initial = [(0x800D8CC8, 0, 1), (0x800D8CBC, table, 4), (table + 12, 0x20, 2)]
    initial.extend(
        (TASK_BASE + i * TASK_WIDTH + 1, int(i != free), 1) for i in range(2, 10)
    )
    expected = [
        (TASK_BASE + owner * TASK_WIDTH + 0x1C, continuation, 4),
        (stack - 8, ret, 4),
        (stack - 0x20, 0x800538CC, 4),
    ]
    expected.extend((target + 0x158 + i * 4, 0, 4) for i in range(6))
    expected.extend(
        [
            (target + 2, 0, 1),
            (target + 0x140, target + 0xC0, 4),
            (target + 1, 1, 1),
            (target, 0, 1),
            (target + 4, 255, 1),
            (target + 8, 255, 1),
            (target + 0x1C, table + 0x20, 4),
        ]
    )
    execute(0x800538A4, owner, 0, bytes.fromhex("04ff1806"), initial, expected)


@pytest.mark.parametrize(
    "entry", [0x800538A4, 0x80053138, 0x80053924, 0x800514EC, 0x80051884]
)
def test_registration_native_callees_are_nonyielding_and_drift_cannot_be_hidden(
    owned, entry
):
    assert native_nonyielding(owned[2], entry, {})
    # This is a compiler-input rejection control. Altered code is never loaded
    # into a native guest or executed by the unchanged component fixture.
    changed = bytearray(owned[2])
    at = 0x8005322C - 0x80010000 + 0x800
    struct.pack_into("<I", changed, at, 0x0C000000 | ((0x80031E80 >> 2) & 0x3FFFFFF))
    assert not native_nonyielding(bytes(changed), 0x800538A4, {})


@pytest.mark.parametrize(
    "at,replacement",
    [
        (6466, b"\x21\x01\x06\0"),
        (6727, b"\0"),
        (6753, b"\x80"),
        (6747, b"\x01"),
        (6751, b"\x01"),
    ],
)
def test_real_factory_rejects_changed_source_before_query(owned, at, replacement):
    p, _, _, _, sources, bound, _, rooms = owned
    data = bytearray(sources["01-04"])
    data[at : at + len(replacement)] = replacement
    assert (
        type(normal_engine_identity_filtering(bytes(data), rooms["01-04"], p, bound))
        is IdentityFilteringFailure
    )


@pytest.mark.parametrize(
    "at,value", [(6746, 276), (6746, 104), (6746, 14), (6746, 82), (6750, 256)]
)
def test_physical_source_domain_rejects_full_u16_aliases(owned, at, value):
    p, _, _, _, sources, _, _, rooms = owned
    data = bytearray(sources["01-04"])
    struct.pack_into("<H", data, at, value)
    data = bytes(data)
    room = decode_room(
        data,
        rooms["01-04"]["source"],
        frozenset((r["bank"], r["bit"]) for r in p["presence_condition_flags"]),
        presence_counter_indices(p),
        presence_flag_write_proof(p)[0],
    )
    room.update(stage=1)
    writes = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.IdentityFiltering
    )
    assert (
        normal_pickup_source_domain(data, room, writes, 4) is NormalPickupFailure.Domain
    )


@pytest.mark.parametrize("four", [False, True])
@pytest.mark.parametrize("flag", [0, 1, 2, 0x80])
def test_both_physical_geometries_and_controller_flags(owned, four, flag):
    p = owned[0]
    packet = item(slot=4, flags=flag)
    if four:
        packet = bytes((0x69,)) + packet[1:14] + bytes(8) + packet[14:]
    data, room, _ = described(END, (packet + END, END))
    writes = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.IdentityFiltering
    )
    result = normal_pickup_source_domain(data, room, writes, 4)
    assert (type(result) is PickupSourceDomain) is (flag in (0, 1))


@pytest.mark.parametrize("program", [12, 23, 24])
def test_raw_producer_reinstates_dormant_entry_and_checks(owned, program):
    p, _, _, _, sources, bound, _, rooms = owned
    data = bytearray(sources["01-04"])
    data[6729] = program
    data = bytes(data)
    room = decode_room(
        data,
        rooms["01-04"]["source"],
        frozenset((r["bank"], r["bit"]) for r in p["presence_condition_flags"]),
        presence_counter_indices(p),
        presence_flag_write_proof(p)[0],
    )
    room.update(stage=1, id="01-04", room=4)
    inventory = native_entry_inventory(data, room["programs"], NativeTaskPhase.Ordinary)
    assert f"17:{program}" in {key for key, _, _ in inventory.entries}
    writes = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.IdentityFiltering
    )
    domain = entered_frame_domain(data, room, writes)
    assert (
        type(domain) is EnteredFrameDomain
        and f"17:{program}" in domain.entered_programs
    )
    fields = _task_fields(
        data,
        room["programs"],
        phase=NativeTaskPhase.Ordinary,
        role=ControlFrames.NativeIdentityFiltering,
        frame_domain=domain,
    )
    if program == 12:
        assert type(fields) is not _TaskFields
    else:
        assert f"17:{program}" in dict(fields.frames)
    assert (
        type(normal_engine_identity_filtering(data, room, p, bound))
        is IdentityFilteringFailure
    )


def test_missing_registration_or_header_owner_cannot_use_body_fact(owned, pickup):
    _, _, _, _, sources, bound, _, rooms = owned
    assert (
        _identity_dispatch(
            sources["01-04"],
            rooms["01-04"],
            4,
            frozenset(),
            pickup.source_writes,
            bound.ordinary_ingress.covered_models,
            pickup_effects=pickup.pickup_effects,
        )
        is IdentityFilteringFailure.Dispatch
    )
    for at in (44, 6732, 6746, 6753):
        writes = replace(
            pickup.source_writes,
            record_writes=(*pickup.source_writes.record_writes, SourceRange(at, 1)),
        )
        assert (
            normal_pickup_source_domain(sources["01-04"], rooms["01-04"], writes, 4)
            is NormalPickupFailure.Lifetime
        )
    assert not isinstance(pickup.pickup_effects[0], _IdentityDispatch)


def test_fixed_premise_and_exact_schema_are_mandatory(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    profile = copy.deepcopy(p)
    profile["runtime_layout"]["scenario_mask"] &= ~0x02000000
    assert (
        type(
            normal_engine_identity_filtering(
                sources["01-04"], rooms["01-04"], profile, bound
            )
        )
        is IdentityFilteringFailure
    )
    room = copy.deepcopy(rooms["01-04"])
    room["programs"]["17:0"]["commands"][1]["expected"] = True
    assert (
        type(normal_engine_identity_filtering(sources["01-04"], room, p, bound))
        is IdentityFilteringFailure
    )
    assert hashlib.sha256(sources["01-04"]).hexdigest() == rooms["01-04"]["sha256"]


def test_all54_auxiliary_bindings_and_all126_break_aliases_remain_required(
    owned, pickup
):
    resources = owned[5].entry_resources
    scripts = resources.corpus.scripts
    assert len(scripts) == 54 and len(pickup.auxiliary_break_reads) == 126
    for script in scripts:
        # The constructor rejects altered bytes before a compiler can receive
        # a stale auxiliary derivation. Never forge that bound derivation.
        with pytest.raises(AssertionError):
            replace(script, data=bytes((script.data[0] ^ 1,)) + script.data[1:])
    for _, _, _, cell in pickup.auxiliary_break_reads:
        assert (
            _auxiliary_break_reads(
                resources,
                frozenset((cell,)),
                numeric_counts=NumericCountPolicy.IdentityConservative,
            )
            is PositiveEntryFailure.ForeignConsumer
        )


@pytest.mark.parametrize("at,width,_digest", _PICKUP_WINDOWS)
def test_every_pickup_native_window_and_table_remains_bound(owned, at, width, _digest):
    p, _, exe, _, sources, bound, _, rooms = owned
    changed = bytearray(exe)
    changed[at - 0x80010000 + 0x800 + width - 1] ^= 1
    altered = replace(
        bound, entry_resources=replace(bound.entry_resources, executable=bytes(changed))
    )
    assert (
        normal_engine_identity_filtering(sources["01-04"], rooms["01-04"], p, altered)
        is IdentityFilteringFailure.Binding
    )


@pytest.mark.parametrize(
    "reset_type,accepted", [(20, True), (30, True), (104, False), (276, False)]
)
def test_every_same_slot_creator_and_reset_alternative_is_retained(
    owned, reset_type, accepted
):
    p = owned[0]
    reset = bytes((0x46, 4, 2, 0x31)) + struct.pack("<3H", reset_type, 65535, 154)
    data, room, _ = described(
        END, (item(slot=4) + item(slot=4, kind=31) + END, END, reset + END)
    )
    writes = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.IdentityFiltering
    )
    result = normal_pickup_source_domain(data, room, writes, 4)
    assert (type(result) is PickupSourceDomain) is accepted
    if accepted:
        assert len(result.origins) == 3
        if reset_type == 30:
            assert {
                at for at, _, role in result.source_effects if "amount override" in role
            } == {
                o.offset + o.payload + 2
                for o in result.origins
                if type(o.physical) is tuple
            }


@pytest.mark.parametrize("amount", [0, 255, 256, 65535])
def test_full_amount_is_only_data_and_cross_kind_alternative_rejects(owned, amount):
    p = owned[0]
    data, room, _ = described(END, (item(slot=4, amount=amount) + END, END))
    writes = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.IdentityFiltering
    )
    result = normal_pickup_source_domain(data, room, writes, 4)
    assert type(result) is PickupSourceDomain and result.origins[0].amount == amount
    data, room, _ = described(
        END, (item(slot=4) + END, END, bytes.fromhex("46040131000000000000") + END)
    )
    writes = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.IdentityFiltering
    )
    assert (
        normal_pickup_source_domain(data, room, writes, 4) is NormalPickupFailure.Domain
    )
