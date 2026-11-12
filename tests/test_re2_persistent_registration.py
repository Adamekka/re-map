"""RE2-SCENARIO-008: only sealed persistent registration refines Reset origins."""

import copy
import struct
from dataclasses import fields, replace

import pytest
from test_re2_positive_prefix import owned as owned  # noqa: PLC0414
from test_re2_positive_prefix import prefix_inputs as prefix_inputs  # noqa: PLC0414
from test_re2_startup_declarations import END, conditional, item

from games.re2.known_puzzle_items import (
    _DeclaredPrefixFacts,
    _known_declared_items,
    known_declared_items_from_prefix,
)
from games.re2.persistent_registration import (
    RegistrationFailure,
    VerifiedPersistentRegistration,
    persistent_registration,
)
from games.re2.positive_prefix import normal_engine_positive_prefix
from games.re2.scenario_entry_scope import scenario_guard_scope
from games.re2.scenario_selection import (
    SCENARIO_ENTRY_AUDIT,
    SCENARIO_NATIVE_WORK_AUDIT,
    ScenarioSelectionFailure,
    ScenarioSelectionSupport,
    ScopedScenarioItems,
    VerifiedScenarioEntryScope,
    scoped_scenario_items,
)
from games.re2.script_control_limits import programs_digest
from games.re2.script_dispatch_items import script_item_dispatch
from games.re2.source_task_control import TaskControlSupport, source_task_control_scope


def interaction(slot=7, kind=0, four_point=False):
    return bytes(
        (0x67 if four_point else 0x2C, slot, kind, 0xB1 if four_point else 0x31)
    ) + bytes(24 if four_point else 16)


def reset(slot=7, gid=154):
    return bytes((0x46, slot, 2, 0x31)) + struct.pack("<3H", 20, 15, gid)


def query(inputs, *, refined, entry_change=False):
    data, room, profile, entry, dispatch, prefix = inputs
    # Synthetic source-only entry receipt isolates origin-query control. The
    # owned factory test separately requires every real native/resource binder.
    scope = VerifiedScenarioEntryScope(
        SCENARIO_ENTRY_AUDIT,
        SCENARIO_NATIVE_WORK_AUDIT,
        entry.executable_sha256,
        room["sha256"],
        programs_digest(room["programs"]),
        frozenset(room["programs"]),
        frozenset((k, p["entry"]) for k, p in room["programs"].items()),
    )
    if entry_change:
        scope = replace(
            scope,
            entry_locations=frozenset(
                (k, p["commands"][-1]["offset"]) for k, p in room["programs"].items()
            ),
        )
    registration = (
        persistent_registration(*inputs)
        if refined
        else ScenarioSelectionSupport.Unaudited
    )
    assert not isinstance(registration, RegistrationFailure)
    return scoped_scenario_items(
        data, room, profile, prefix.context, scope, registration=registration
    )


def test_owned_registration_removes_only_the_reset_identity(owned):
    profile, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-09"], rooms["00-09"]
    prefix = normal_engine_positive_prefix(data, room, profile, bound)
    registration = persistent_registration(
        data, room, profile, entry, script_item_dispatch(profile), prefix
    )
    assert type(registration) is VerifiedPersistentRegistration
    assert registration.registered_slots == frozenset((0, 1, 2, 3, 8))
    assert tuple(slot for _, _, slot in registration.dispatches) == (1, 2, 2, 3)
    assert registration.source_kinds == frozenset((0, 1, 2, 4, 5))
    scope = scenario_guard_scope(
        data,
        room,
        profile,
        prefix.context,
        source_task_control_scope(
            data, room, profile, prefix.context, bound.ordinary_ingress
        ),
    )
    assert scoped_scenario_items(data, room, profile, prefix.context, scope) == (
        ScopedScenarioItems((146,), ())
    )
    assert scoped_scenario_items(
        data, room, profile, prefix.context, scope, registration=registration
    ) == ScopedScenarioItems((146, 205), ())


@pytest.mark.parametrize("four_point", [False, True])
@pytest.mark.parametrize("kind", [0, 1, 2, 4, 5])
def test_every_ordinary_and_four_point_creator_registers_independent_of_activity(
    prefix_inputs, four_point, kind
):
    packet = interaction(kind=kind, four_point=four_point)
    if kind == 1:
        packet = bytes(
            (0x68 if four_point else 0x3B, 7, 1, 0xB1 if four_point else 0x31)
        ) + bytes(36 if four_point else 28)
    elif kind == 2:
        packet = item(sat=0)
        if four_point:
            packet = bytes((0x69,)) + packet[1:14] + bytes(8) + packet[14:]
    elif kind == 5:
        packet = packet[:-6] + b"\xff\0\x18\x01\0\0"
    inputs = prefix_inputs(END, (packet + END, END))
    result = persistent_registration(*inputs)
    assert type(result) is VerifiedPersistentRegistration
    assert result.registered_slots == frozenset((7,))
    assert not hasattr(result, "absent_item_ids")
    assert not hasattr(result, "protected_programs")


@pytest.mark.parametrize("prefix", [b"\x02", b"\x04\xff\x18\x01", b"\x47\x07"])
def test_unsupported_or_yielding_prefix_does_not_register_later_creators(
    prefix_inputs, prefix
):
    inputs = prefix_inputs(END, (prefix + item() + END, END))
    result = persistent_registration(*inputs)
    if prefix == b"\x47\x07":
        assert result is RegistrationFailure.Dispatch
    else:
        assert type(result) is VerifiedPersistentRegistration
        assert result.registered_slots == frozenset()


def test_conditional_registration_intersects_all_startup_outcomes(prefix_inputs):
    inputs = prefix_inputs(
        END,
        (conditional(item(), END, bank=5, bit=7) + END, b"\x47\x07" + END),
    )
    assert persistent_registration(*inputs) is RegistrationFailure.Dispatch


def test_different_empty_slot_can_dispatch_the_null_reset(prefix_inputs):
    # Reset slot7 and scripted47 slot8 alias physical zero. The origin-only
    # query would incorrectly exclude the item without the consumer barrier.
    inputs = prefix_inputs(
        END,
        (
            conditional(b"\0", item(), bank=1, bit=1) + END,
            reset() + b"\x47\x08" + END,
        ),
    )
    assert persistent_registration(*inputs) is RegistrationFailure.Dispatch
    assert query(inputs, refined=False) == ScopedScenarioItems((), ())


@pytest.mark.parametrize(
    "origin", ["none", "ordinary", "four-point", "item", "other-procedure"]
)
def test_reset_requires_every_possible_same_slot_origin(prefix_inputs, origin):
    # The target item's creator is B-only; any other reachable same-slot
    # creator still gives Reset a non-NULL descriptor, independent of identity.
    creator = conditional(b"\0", item(), bank=1, bit=1)
    extra = {
        "none": b"",
        "ordinary": interaction(),
        "four-point": interaction(four_point=True),
        "item": item(gid=155),
        "other-procedure": b"",
    }[origin]
    main = [creator + extra + END, reset() + END]
    if origin == "other-procedure":
        main.append(interaction() + END)
    inputs = prefix_inputs(END, tuple(main))
    assert inputs[1]["candidate_list_complete"]
    assert query(inputs, refined=False) == ScopedScenarioItems((), ())
    assert query(inputs, refined=True) == ScopedScenarioItems(
        (154,) if origin == "none" else (), ()
    )


@pytest.mark.parametrize("kind", [6, 13, 14])
def test_unclosed_native_kinds_withhold_the_new_role(prefix_inputs, kind):
    inputs = prefix_inputs(END, (interaction(kind=kind) + END, END))
    assert persistent_registration(*inputs) is RegistrationFailure.Kind


def test_inactive_registration_can_be_reset_and_dispatched(prefix_inputs):
    inputs = prefix_inputs(END, (item(sat=0) + END, reset() + b"\x47\x07" + END))
    result = persistent_registration(*inputs)
    assert type(result) is VerifiedPersistentRegistration
    assert result.registered_slots == frozenset((7,))
    assert query(inputs, refined=True) == ScopedScenarioItems((), ())


def test_origin_query_cannot_skip_a_canonical_creator_entry(prefix_inputs):
    inputs = prefix_inputs(END, (item() + END, reset() + END))
    assert (
        query(inputs, refined=True, entry_change=True)
        is ScenarioSelectionFailure.EntryScope
    )


@pytest.mark.parametrize(
    "field", ["prefix", "registered_slots", "dispatches", "source_kinds", "_authority"]
)
def test_compiler_owned_companion_rejects_equal_and_coordinated_substitution(
    owned, field
):
    p, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-09"], rooms["00-09"]
    prefix = normal_engine_positive_prefix(data, room, p, bound)
    cap = persistent_registration(data, room, p, entry, script_item_dispatch(p), prefix)
    value = getattr(cap, field)
    replacement = (
        set(value)
        if type(value) is frozenset
        else list(value)
        if type(value) is tuple
        else copy.deepcopy(value)
    )
    with pytest.raises(TypeError):
        replace(cap, **{field: replacement})
    with pytest.raises(TypeError):
        replace(
            cap, **{f.name: copy.deepcopy(getattr(cap, f.name)) for f in fields(cap)}
        )
    # Mandatory consumption also detects mutation bypassing frozen dataclasses.
    altered = copy.copy(cap)
    object.__setattr__(altered, field, [] if field != "prefix" else copy.copy(prefix))
    with pytest.raises((AssertionError, ValueError)):
        altered.matches(data, room, p, prefix.context.declaration_contract)


@pytest.mark.parametrize(
    "fault", ["source", "room", "programs", "profile", "contract", "ingress"]
)
def test_consumption_rechecks_all_input_bindings(owned, fault):
    p, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-09"], rooms["00-09"]
    prefix = normal_engine_positive_prefix(data, room, p, bound)
    cap = persistent_registration(data, room, p, entry, script_item_dispatch(p), prefix)
    scope = scenario_guard_scope(
        data,
        room,
        p,
        prefix.context,
        source_task_control_scope(
            data, room, p, prefix.context, bound.ordinary_ingress
        ),
    )
    room, p = copy.deepcopy(room), copy.deepcopy(p)
    contract = prefix.context.declaration_contract
    if fault == "source":
        data = data[:-1] + bytes((data[-1] ^ 1,))
    elif fault == "room":
        room["items"][0]["amount"] += 1
    elif fault == "programs":
        room["programs"]["17:0"]["entry"] += 2
    elif fault == "profile":
        p["runtime_layout"]["item_bank_early"] += 1
    elif fault == "contract":
        contract = replace(
            contract, flag_addresses=tuple(reversed(contract.flag_addresses))
        )
    else:
        room["id"] = "00-0d"
    assert not cap.matches(data, room, p, contract)
    assert (
        scoped_scenario_items(
            data,
            room,
            p,
            replace(prefix.context, declaration_contract=contract),
            scope,
            registration=cap,
        )
        is ScenarioSelectionFailure.SourceBinding
    )


def test_shared_walk_companion_preserves_positive_results(prefix_inputs):
    inputs = prefix_inputs(END, (item() + END, END))
    data, room, p, entry, dispatch, prefix = inputs
    facts = _known_declared_items(
        data,
        room,
        p,
        entry,
        dispatch,
        prefix.context.declaration_contract,
        prefix.context,
        ScenarioSelectionSupport.Unaudited,
        prefix,
    )
    assert type(facts) is _DeclaredPrefixFacts
    assert facts.items == known_declared_items_from_prefix(*inputs)


def test_guard_scope_alone_cannot_supply_initialization(owned):
    p, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-09"], rooms["00-09"]
    prefix = normal_engine_positive_prefix(data, room, p, bound)
    guard = scenario_guard_scope(
        data, room, p, prefix.context, TaskControlSupport.Unaudited
    )
    with pytest.raises(AssertionError):
        persistent_registration(data, room, p, entry, script_item_dispatch(p), guard)


def test_derived_room_changes_require_a_fresh_prefix_at_consumption(owned):
    p, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-09"], copy.deepcopy(rooms["00-09"])
    room["known_puzzle_items"] = []
    prefix = normal_engine_positive_prefix(data, room, p, bound)
    cap = persistent_registration(data, room, p, entry, script_item_dispatch(p), prefix)
    room["known_puzzle_items"].append({"global_id": 13})
    assert not cap.matches(data, room, p, bound.declarations)
    assert (
        persistent_registration(data, room, p, entry, script_item_dispatch(p), prefix)
        is RegistrationFailure.Binding
    )
    rebound = normal_engine_positive_prefix(data, room, p, bound)
    new = persistent_registration(
        data, room, p, entry, script_item_dispatch(p), rebound
    )
    assert type(new) is VerifiedPersistentRegistration
    assert new.matches(data, room, p, bound.declarations)
