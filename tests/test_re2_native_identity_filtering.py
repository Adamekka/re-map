"""Bound native identity filtering independently of door and presence rights."""

import hashlib
import struct
from dataclasses import replace

import pytest
from test_re2_door_native_frames import polling
from test_re2_positive_prefix import owned as owned
from test_re2_startup_declarations import END, contract, described

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.identity_filtering import (
    _NATIVE_IDENTITY_WINDOWS,
    IdentityFilteringFailure,
    NormalEngineIdentityFiltering,
    _identity_dispatch,
    _IdentityDispatch,
    _IdentityDispatchKind,
    normal_engine_identity_filtering,
)
from games.re2.native_control import native_bytes
from games.re2.native_entry_fields import NativeTaskPhase, _task_fields
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    SourceEntryPolicy,
    _NativeIdentityEntryRoles,
    _source_entry_roles,
)
from games.re2.room_data import decode_room
from games.re2.scenario_entry_scope import (
    _ScopePolicy,
    _source_scope_facts,
    _SourceScopeFacts,
)
from games.re2.scenario_selection import (
    ScopedScenarioItems,
    SourceCopyWrite,
    SourceWritePolicy,
    bind_scenario_context,
    scenario_source_write_witnesses,
    scoped_scenario_items,
)
from games.re2.source_task_control import TaskControlSupport
from games.re2.structured_control import (
    ControlFrames,
    NativeStructuredControl,
    PredicateOutcome,
    structured_control,
)


def test_owned_native_identity_selects_the_single_scenario_creator(owned):
    profile, _, _, _, sources, bound, _, rooms = owned
    source, room = sources["00-08"], rooms["00-08"]
    authority = normal_engine_identity_filtering(source, room, profile, bound)
    assert type(authority) is NormalEngineIdentityFiltering
    result = scoped_scenario_items(
        source,
        room,
        profile,
        bind_scenario_context(profile, bound.declarations),
        authority,
    )
    assert type(result) is ScopedScenarioItems
    assert result.absent_item_ids == ()
    assert [(row.global_id, row.offsets) for row in result.item_variants] == [
        (213, (6934,))
    ]


def test_complete_owned_factory_and_query_consequences(owned):
    profile, _, _, _, sources, bound, _, rooms = owned
    expected_sources = {
        "00-07",
        "00-08",
        "00-0a",
        "00-0d",
        "00-0e",
        "00-0f",
        "00-17",
        "00-18",
        "00-1a",
        "00-1b",
        "01-03",
        "01-07",
        "01-0a",
        "01-0c",
        "01-0f",
        "01-13",
        "01-19",
        "01-1b",
        "02-00",
        "02-02",
        "02-07",
        "02-08",
        "03-08",
        "03-0b",
        "03-0f",
        "05-00",
        "05-05",
        "05-0b",
        "05-0e",
        "05-0f",
        "05-14",
    }
    expected_queries = {
        "00-08": ((), ((213, (6934,)),)),
        "00-0d": ((), ((206, (2242,)),)),
        "00-0f": ((157,), ()),
        "01-03": ((36,), ()),
        "01-0c": ((), ((207, (7534,)),)),
        "01-13": ((24,), ()),
        "01-19": ((), ((117, (2762,)),)),
        "03-08": ((), ((185, (10558,)),)),
    }
    supported, queries = set(), {}
    context = bind_scenario_context(profile, bound.declarations)
    for key, room in rooms.items():
        authority = normal_engine_identity_filtering(sources[key], room, profile, bound)
        if type(authority) is not NormalEngineIdentityFiltering:
            assert type(authority) is IdentityFilteringFailure
            continue
        supported.add(key)
        assert type(authority.source_roles) is _NativeIdentityEntryRoles
        assert len(authority.auxiliary_fields) == 54
        assert {
            task for _, task, _ in authority.source_roles.native_fields.entries
        } <= set(range(10))
        query = scoped_scenario_items(sources[key], room, profile, context, authority)
        assert type(query) is ScopedScenarioItems
        if query.absent_item_ids or query.item_variants:
            queries[key] = (
                query.absent_item_ids,
                tuple((v.global_id, v.offsets) for v in query.item_variants),
            )
    assert len(rooms) == 125
    assert supported == expected_sources
    assert queries == expected_queries
    assert not rooms["00-11"]["candidate_list_complete"]


def test_original_identity_source_policy_keeps_its_narrow_frame_domain(owned):
    profile, _, _, _, sources, _, _, rooms = owned
    data, room = sources["00-08"], rooms["00-08"]
    writes = scenario_source_write_witnesses(
        data, room, profile, policy=SourceWritePolicy.IdentityFiltering
    )
    assert (
        type(
            _source_entry_roles(
                data,
                room["programs"],
                writes,
                policy=SourceEntryPolicy.IdentityFiltering,
            )
        )
        is PositiveEntryFailure
    )
    assert (
        type(
            _source_entry_roles(
                data,
                room["programs"],
                writes,
                policy=SourceEntryPolicy.NativeIdentityFiltering,
            )
        )
        is _NativeIdentityEntryRoles
    )


def test_native_identity_predicate86_pops_the_if_on_its_false_edge():
    data, room, _ = described(END, (b"\x06\0\x03\0\x86\x08\0" + END, END))
    result = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeIdentityFiltering
    )
    assert type(result) is NativeStructuredControl
    at = room["programs"]["17:0"]["entry"] + 4
    assert dict(result.edges)[at] == (at + 1, at + 3)


@pytest.mark.parametrize(
    "middle", [b"", b"\x22\x02\x08\x01", b"\x02\0", b"\x18\x01", b"\x3e\0\x0c\x03\0\0"]
)
def test_native_identity_requires_its_own_fresh_foreign_predicate(middle):
    data, room, _ = described(END, (polling(middle), END))
    result = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeIdentityFiltering
    )
    assert (type(result) is NativeStructuredControl) is (middle == b"")


def test_native_identity_does_not_treat_predicate86_as_foreign_atomic():
    block = b"\x06\0\x03\0\x86\x08\0"
    body = block + b"\x17\xff\xff\0" + struct.pack("<h", -len(block)) + END
    data, room, _ = described(END, (body, END))
    assert (
        type(
            structured_control(
                data, room["programs"]["17:0"], ControlFrames.NativeIdentityFiltering
            )
        )
        is not NativeStructuredControl
    )


def test_native_identity_cannot_prune_frames_with_a_door_predicate_hint():
    data, room, _ = described(END, (END,))
    at = room["programs"]["17:0"]["entry"]
    with pytest.raises(AssertionError):
        structured_control(
            data,
            room["programs"]["17:0"],
            ControlFrames.NativeIdentityFiltering,
            predicates=((at, PredicateOutcome.Matches),),
        )
    with pytest.raises(AssertionError):
        _task_fields(
            data,
            room["programs"],
            phase=False,
            role=ControlFrames.NativeIdentityFiltering,
        )
    with pytest.raises(AssertionError):
        _task_fields(
            data,
            room["programs"],
            phase=NativeTaskPhase.Ordinary,
            role=ControlFrames.IdentityFiltering,
        )


@pytest.mark.parametrize("at,width,digest", _NATIVE_IDENTITY_WINDOWS)
def test_additional_native_roles_are_bound_before_identity_rights(
    owned, at, width, digest
):
    profile, _, executable, _, sources, bound, _, rooms = owned
    assert hashlib.sha256(native_bytes(executable, at, width)).hexdigest() == digest
    for offset in (at, at + width - 1):
        changed = bytearray(executable)
        changed[offset - 0x80010000 + 0x800] ^= 1
        altered = replace(
            bound,
            entry_resources=replace(bound.entry_resources, executable=bytes(changed)),
        )
        assert (
            normal_engine_identity_filtering(
                sources["00-08"], rooms["00-08"], profile, altered
            )
            is IdentityFilteringFailure.Binding
        )


@pytest.mark.parametrize(
    "settings,accepted",
    [
        ({}, True),
        ({"four": True}, True),
        ({"four": True, "sat": 0xB1}, True),
        ({"lock": 0x7F}, True),
        ({"lock": 0x80}, False),
        ({"sat": 0x80}, False),
        ({"width": 30}, False),
        ({"kind": 2}, False),
        ({"reset": True}, False),
        ({"copy_at": 31}, False),
        ({"copy_at": 32}, True),
        ({"registered": False}, False),
        ({"model": 255}, False),
    ],
)
def test_only_immutable_registered_unlocked_physical_door_callbacks_are_admitted(
    owned, settings, accepted
):
    profile, _, _, _, sources, bound, _, rooms = owned
    # The helper returns unsealed footprint data. These synthetic descriptors
    # never enter a public capability; owned integration tests cover that boundary.
    writes = scenario_source_write_witnesses(
        sources["00-08"],
        rooms["00-08"],
        profile,
        policy=SourceWritePolicy.IdentityFiltering,
    )
    four = settings.get("four", False)
    size, payload = (40, 22) if four else (32, 14)
    packet = bytearray(size)
    packet[:4] = bytes(
        (0x68 if four else 0x3B, 0, settings.get("kind", 1), settings.get("sat", 0x31))
    )
    packet[payload + 12] = settings.get("model", 14)
    packet[payload + 15] = settings.get("lock", 0)
    packet = packet[: settings.get("width", size)]
    rows = [
        {
            "offset": 0,
            "next": len(packet),
            "kind": "door",
            "opcode": 0x68 if four else 0x3B,
        }
    ]
    if settings.get("reset", False):
        at = len(packet)
        packet.extend(b"\x46\0\x01" + bytes(7))
        rows.append({"offset": at, "next": at + 10, "kind": "reset", "opcode": 0x46})
    if "copy_at" in settings:
        writes = replace(
            writes, copies=(SourceCopyWrite(("17:0", 0), settings["copy_at"], 2),)
        )
    result = _identity_dispatch(
        bytes(packet),
        {"programs": {"17:0": {"commands": rows}}},
        0,
        frozenset({0}) if settings.get("registered", True) else frozenset(),
        writes,
        bound.ordinary_ingress.covered_models,
    )
    assert (type(result) is _IdentityDispatch) is accepted
    if accepted:
        assert result.kind is _IdentityDispatchKind.PendingDoor


@pytest.fixture
def changed_native_scope(owned):
    profile, _, _, _, sources, _, _, rooms = owned

    def check(changes):
        data = bytearray(sources["00-08"])
        for offset, value in changes.items():
            data[offset] = value
        data = bytes(data)
        # An explicit test receipt isolates source operand rules. The public
        # owned factory independently rejects any changed source fingerprint.
        room = decode_room(
            data,
            rooms["00-08"]["source"],
            frozenset(
                (r["bank"], r["bit"]) for r in profile["presence_condition_flags"]
            ),
            presence_counter_indices(profile),
            presence_flag_write_proof(profile)[0],
        )
        room.update(id="00-02", stage=0, room=2)
        context = bind_scenario_context(profile, contract(profile, room))
        writes = scenario_source_write_witnesses(
            data, room, profile, policy=SourceWritePolicy.IdentityFiltering
        )
        roles = _source_entry_roles(
            data,
            room["programs"],
            writes,
            policy=SourceEntryPolicy.NativeIdentityFiltering,
        )
        if type(roles) is not _NativeIdentityEntryRoles:
            return roles
        return _source_scope_facts(
            data,
            room,
            profile,
            context,
            _ScopePolicy.NativeIdentityFiltering,
            TaskControlSupport.Unaudited,
            roles,
        )

    return check


@pytest.mark.parametrize(
    "offset,value,accepted",
    [
        (7245, 0, True),
        (7245, 3, True),
        (7245, 4, False),
        (7245, 255, False),
        (7246, 0, True),
        (7246, 3, True),
        (7246, 4, False),
        (7246, 255, False),
        (7247, 0, True),
        (7247, 7, True),
        (7247, 8, False),
        (7247, 255, False),
        (7253, 0, True),
        (7253, 3, True),
        (7253, 4, False),
        (7253, 255, False),
    ],
)
def test_native_identity_renderer_keeps_record_blend_and_rgb_selectors_bounded(
    changed_native_scope, offset, value, accepted
):
    assert (
        type(changed_native_scope({offset: value})) is _SourceScopeFacts
    ) is accepted


@pytest.mark.parametrize("bits", [0, 1, 0x7FFF, 0x8000, 0xFFFF])
def test_native_identity_renderer_coefficient_uses_the_whole_native_halfword(
    changed_native_scope, bits
):
    low, high = struct.pack("<H", bits)
    assert type(changed_native_scope({7254: low, 7255: high})) is _SourceScopeFacts
