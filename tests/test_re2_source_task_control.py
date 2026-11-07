"""RE2-SCENARIO-007: closed task/input certificates stay scenario-only."""

import copy
import struct
from dataclasses import replace

import pytest
from test_re2_scenario_entry_scope import profile as profile  # noqa: PLC0414
from test_re2_startup_declarations import END, contract, described, item

import games.re2.source_task_control as control_module
from games.re2.ordinary_task_ingress import (
    INGRESS_AUDIT,
    VerifiedOrdinaryTaskIngress,
    _OrdinaryIngressDerivation,
)
from games.re2.scenario_entry_scope import scenario_entry_scope, scenario_guard_scope
from games.re2.scenario_selection import (
    ScenarioSelectionFailure,
    VerifiedScenarioGuardScope,
    bind_scenario_context,
    scoped_scenario_items,
)
from games.re2.source_task_control import (
    TaskControlFailure,
    TaskControlSupport,
    VerifiedSourceTaskControl,
    _animation_frontiers,
    _Binding,
    _Empty,
    _Frontier,
    _ItemUI,
    _PickupAnimation,
    _PickupOwner,
    _ui_completion_frontiers,
    _UIPhase,
    source_task_control_scope,
)

STOP = b"\x22\x02\x07\x01"
CLEAR = b"\x22\x02\x07\0"
MESSAGE = b"\x2b\0\0\0\0\xff"
REQUEST = b"\x36\x02\x0a\x01\x01" + bytes(7)
ATOMIC = frozenset(
    (
        0,
        0x21,
        0x22,
        0x23,
        0x26,
        0x29,
        0x2C,
        0x2E,
        0x2F,
        0x30,
        0x32,
        0x34,
        0x35,
        0x36,
        0x3B,
        0x3C,
        0x3D,
        0x46,
        0x4E,
        0x51,
        0x53,
        0x67,
        0x68,
        0x69,
    )
)


def reset(slot, target):
    return bytes((0x46, slot, 5, 0x31, 255, 0, 0x18, target, 0, 0))


def callback(slot, target):
    return (
        bytes((0x2C, slot, 5, 0x31)) + bytes(10) + bytes((255, 0, 0x18, target, 0, 0))
    )


def cycle(prefix, target):
    return prefix + b"\x17\xff\xff\0" + struct.pack("<h", target - len(prefix))


def setup(profile, fault):
    helper_time = 30 if fault == "long_helper" else 2
    helper = REQUEST + bytes((9, 10, helper_time, 0)) + END
    if fault == "receiver_loop":
        helper = b"\x0d\0\x06\0\x01\0" + b"\x09\x0a\x02\0\x0e\0" + END
    if fault == "receiver_call":
        helper = b"\x18\x06" + helper
    worker = (
        STOP + (MESSAGE + b"\x02\x04\xff\x18\x03") * 4 + reset(9, 4) + b"\x47\x09" + END
    )
    if fault == "busy_fallthrough":
        # Native 2B falls through while busy and retains STOP6. The following
        # scripted47 must honor that gate instead of forcing another birth.
        worker = (
            STOP
            + (MESSAGE + b"\x02\x04\xff\x18\x03") * 4
            + MESSAGE * 2
            + b"\x04\xff\x18\x03"
            + reset(9, 4)
            + b"\x47\x09"
            + END
        )
    child = MESSAGE + b"\x02" + REQUEST + b"\x02" + MESSAGE + END
    if fault == "extra_gap":
        child = MESSAGE + b"\x02" + REQUEST + b"\x02\x02" + MESSAGE + END
    if fault == "message_mask":
        child = child.replace(MESSAGE, MESSAGE[:-1] + b"\xfc")
    if fault == "phase_writer":
        child = b"\x22\x01\x18\x01" + child
    if fault == "member_selector":
        child = b"\x34\x2b\0\0" + child
    handoff = (
        b"\x46\x09"
        + bytes(8)
        + STOP
        + b"\x09\x0a\x01\0\x47\x0b\x02"
        + STOP
        + b"\x09\x0a\x01\0"
        + CLEAR
        + END
    )
    poll = b"\x06\0\x08\0\x23\0\x1a\0\x01\0\x08\0\x02"
    poll = cycle(poll, 0)
    persistent = cycle(b"\x51\0\x01\x01\x01\x40\x02", 0)
    start = (
        callback(9, 2)
        + callback(11, 10)
        + item(slot=10, flags=0)
        + b"\x04\xff\x18\x09\x04\xff\x18\x07"
        + END
    )
    if fault == "automatic":
        start = start.replace(b"\x05\x31", b"\x05\x41")
    if fault == "autonomous":
        persistent = cycle(b"\x04\xff\x18\x03\x02", 0)
    if fault == "independent_clear":
        persistent = cycle(CLEAR + b"\x02", 0)
    if fault == "persistent_reset":
        persistent = cycle(reset(11, 2) + b"\x02", 0)
    if fault == "assignment":
        start = start.replace(
            b"\x04\xff\x18\x09\x04\xff\x18\x07", b"\x04\xff\x18\x07\x04\xff\x18\x09"
        )
    if fault == "frame_birth":
        frame = b"\x04\xff\x18\x03" + END
    else:
        frame = END
    if fault == "copy_control":
        child = b"\x1d\x04\x01\0" + child
    if fault == "preserved_counter":
        child = b"\x24\x05\0\0" + child
    # Both initializer branches remain possible, even in the fixed Leon A
    # query. The alternate branch ends before installing the callback chain.
    start = b"\x06\0\x0c\0\x21\x01\x06\x01\x04\xff\x18\x09" + END + b"\0\0" + start
    creators = (
        b"\x06\0\x32\0\x21\x01\x01\x01"
        + item(gid=82)
        + item(gid=48, slot=8)
        + b"\x08\0"
        + END
    )
    init = (
        bytes((0x3B, 2, 1, 0x31))
        + bytes(28)
        + b"\x46\x02\x04\x31\x12\0\0\0\0\xff"
        + END
    )
    if fault == "kind4_mask":
        init = init[:-3] + b"\xfc" + END
    if fault == "unregistered_reset":
        init = init[32:]
    if fault == "startup_for":
        start = b"\x0d\0\x06\0\x04\0\x04\xff\x18\x09\x0e\0" + start
    if fault == "startup_predicate":
        start = b"\x85\0\x02\0\0\x84" + start
    reentered, poisoned = END, END
    if fault == "reset_reexecution":
        start = start.replace(callback(11, 10), b"\x18\x05")
        reentered = callback(11, 10) + END
        poisoned = b"\x09\x0a\x2c\x01" + END
        worker = STOP + reset(11, 6) + b"\x04\xff\x18\x05\x02\x47\x0b" + CLEAR + END
    if fault in ("acquired_item", "acquired_four_point"):
        declaration = item(slot=11, flags=0)
        # This case isolates acquired creator reexecution. A parked source
        # cannot first start an unrelated manual UI before its Reset.
        declaration = declaration[:3] + b"\0" + declaration[4:]
        if fault == "acquired_four_point":
            declaration = b"\x69" + declaration[1:14] + bytes(8) + declaration[14:]
        # Reexecute a source record whose payload was changed to kind5. The
        # acquired path must clear that mutable record again, and scripted47
        # must advance without requesting UI or dispatching its old target.
        start = start.replace(callback(11, 10), b"\x18\x05")
        reentered = declaration + END
        worker = STOP + reset(11, 6) + b"\x04\xff\x18\x05\x02\x47\x0b" + CLEAR + END
    if fault == "scripted_stop6":
        init = END
        start = (
            callback(9, 2)
            + callback(11, 10)
            + b"\x04\xff\x18\x09\x04\xff\x18\x07"
            + END
        )
        worker = MESSAGE + b"\x47\x0b\x09\x0a\x1e\0" + END
        helper = handoff = reentered = poisoned = creators = END
        persistent = poll = cycle(b"\x02", 0)
        child = b"\x46\x09" + bytes(8) + END
    if fault == "pending_selected_reset":
        init = END
        start = (
            callback(9, 2)
            + item(slot=11, flags=0)
            + b"\x04\xff\x18\x09\x04\xff\x18\x07"
            + END
        )
        worker = (
            STOP
            + b"\x46\x0b\x02\x31"
            + struct.pack("<3H", 20, 15, 154)
            + b"\x47\x0b"
            + reset(11, 10)
            + b"\x09\x0a\x01\0\x47\x0b"
            + CLEAR
            + b"\x09\x0a\x1e\0"
            + END
        )
        helper = handoff = reentered = poisoned = creators = END
        persistent = poll = cycle(b"\x02", 0)
        child = b"\x46\x09" + bytes(8) + END
    data, room, _ = described(
        init,
        (
            start,
            frame,
            worker,
            helper,
            handoff,
            reentered,
            poisoned,
            persistent,
            creators,
            poll,
            child,
        ),
    )
    context = bind_scenario_context(profile, contract(profile, room))
    # Explicit test seam supplies only native premises. Production obtains
    # these through the real once-bound executable/resource/corpus factory.
    derivation = _OrdinaryIngressDerivation(
        INGRESS_AUDIT,
        context.declaration_contract.executable_sha256,
        context.declaration_contract.selection,
        frozenset((2, 10)),
        ((2, "a" * 64), (10, "b" * 64)),
        frozenset((5,)),
        ATOMIC,
    )
    ingress = VerifiedOrdinaryTaskIngress(
        derivation.audit,
        derivation.executable_sha256,
        derivation.selection,
        derivation.covered_models,
        derivation.auxiliary_programs,
        derivation.preserved_counters,
        derivation.atomic_opcodes,
        derivation,
    )
    return data, room, context, ingress


def test_scripted_kind5_preserves_the_stop6_skip_path(profile):
    data, room, context, ingress = setup(profile, "scripted_stop6")
    assert room["candidate_list_complete"]
    # Message owns STOP6, so scripted47 cannot start the callback-disabling
    # worker. After Message closes, the original external root can reenter
    # while its first instance is still asleep.
    control = source_task_control_scope(data, room, profile, context, ingress)
    assert control is TaskControlFailure.InputLease
    assert (
        scenario_guard_scope(data, room, profile, context, control)
        is ScenarioSelectionFailure.EntryScope
    )


def test_busy_message_handoff_keeps_the_native_scripted_dispatch_gate(profile):
    data, room, context, ingress = setup(profile, "busy_fallthrough")
    control = source_task_control_scope(data, room, profile, context, ingress)
    assert isinstance(control, VerifiedSourceTaskControl), control
    assert dict(control.owners)[9] == ()


def test_pending_ui_selected_record_cannot_be_retargeted(profile):
    data, room, context, ingress = setup(profile, "pending_selected_reset")
    assert room["candidate_list_complete"]
    # Accepted native UI can clear this source record after Reset changes it
    # to kind5. Its later dispatch may then leave the external callback live.
    control = source_task_control_scope(data, room, profile, context, ingress)
    assert control is TaskControlFailure.SourceMutation
    assert (
        scenario_guard_scope(data, room, profile, context, control)
        is ScenarioSelectionFailure.EntryScope
    )


def test_joint_frontier_qualifies_only_scenario_exclusions(profile):
    data, room, context, ingress = setup(profile, "none")
    control = source_task_control_scope(data, room, profile, context, ingress)
    assert isinstance(control, VerifiedSourceTaskControl), control
    assert dict(control.owners)[2] == ("17:9",)
    assert dict(control.owners)[3] == ("17:7",)
    assert dict(control.owners)[9] == ()
    assert len(control.dispatches) == 2
    assert (
        scenario_entry_scope(data, room, profile, context)
        is ScenarioSelectionFailure.EntryScope
    )
    assert (
        scenario_guard_scope(data, room, profile, context, TaskControlSupport.Unaudited)
        is ScenarioSelectionFailure.EntryScope
    )
    guard = scenario_guard_scope(data, room, profile, context, control)
    assert isinstance(guard, VerifiedScenarioGuardScope), guard
    selected = scoped_scenario_items(data, room, profile, context, guard)
    assert selected.absent_item_ids == (48, 82)
    assert selected.item_variants == ()


@pytest.mark.parametrize(
    "fault",
    [
        "extra_gap",
        "long_helper",
        "automatic",
        "autonomous",
        "independent_clear",
        "assignment",
        "frame_birth",
        "message_mask",
        "kind4_mask",
        "phase_writer",
        "copy_control",
        "preserved_counter",
        "receiver_loop",
        "receiver_call",
        "persistent_reset",
        "unregistered_reset",
        "startup_for",
        "startup_predicate",
        "reset_reexecution",
    ],
)
def test_source_changes_cannot_inherit_joint_task_rights(profile, fault):
    data, room, context, ingress = setup(profile, fault)
    result = source_task_control_scope(data, room, profile, context, ingress)
    assert isinstance(result, TaskControlFailure), (fault, result)


def test_earlier_persistent_native_call_needs_nonyield_closure(profile):
    data, room, context, ingress = setup(profile, "none")
    derivation = replace(
        ingress._derivation, atomic_opcodes=ingress.atomic_opcodes - {0x51}
    )
    # This explicit test seam withholds an audited native premise; production
    # callers cannot broaden a retained receipt with dataclasses.replace.
    ingress = replace(
        ingress, atomic_opcodes=derivation.atomic_opcodes, _derivation=derivation
    )
    assert (
        source_task_control_scope(data, room, profile, context, ingress)
        is TaskControlFailure.NativeClock
    )


@pytest.mark.parametrize("fault", ["data", "programs", "context", "room", "incomplete"])
def test_certificate_cannot_cross_source_context_or_resource_bindings(profile, fault):
    data, room, context, ingress = setup(profile, "none")
    control = source_task_control_scope(data, room, profile, context, ingress)
    assert isinstance(control, VerifiedSourceTaskControl)
    if fault == "data":
        data += b"\0"
    elif fault == "programs":
        room = copy.deepcopy(room)
        room["programs"]["17:4"]["commands"][0]["offset"] += 1
    elif fault == "context":
        profile = copy.deepcopy(profile)
        profile["runtime_layout"]["scenario_reset_mask"] = 0
    elif fault == "room":
        room = copy.deepcopy(room)
        room["stage"] += 1
        assert not ingress.covers(data, room)
    elif fault == "incomplete":
        room = copy.deepcopy(room)
        room["candidate_list_complete"] = False
    assert isinstance(
        scenario_guard_scope(data, room, profile, context, control),
        ScenarioSelectionFailure,
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("atomic_opcodes", frozenset(range(256))),
        ("preserved_counters", frozenset()),
        ("covered_models", frozenset(range(256))),
        ("auxiliary_programs", ()),
    ],
)
def test_ingress_derived_permissions_cannot_be_replaced(profile, field, value):
    *_, ingress = setup(profile, "none")
    with pytest.raises(AssertionError):
        replace(ingress, **{field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("dispatches", frozenset((("17:10", 1),))),
        ("gotos", frozenset((("17:10", 1),))),
        ("owners", ()),
        ("frontier_count", 1),
    ],
)
def test_task_permissions_cannot_be_replaced(profile, field, value):
    data, room, context, ingress = setup(profile, "none")
    control = source_task_control_scope(data, room, profile, context, ingress)
    assert isinstance(control, VerifiedSourceTaskControl)
    with pytest.raises(AssertionError):
        replace(control, **{field: value})


def test_scalar_member_alias_remains_rejected_by_shared_guard_checks(profile):
    data, room, context, ingress = setup(profile, "member_selector")
    control = source_task_control_scope(data, room, profile, context, ingress)
    assert isinstance(control, VerifiedSourceTaskControl)
    assert (
        scenario_guard_scope(data, room, profile, context, control)
        is ScenarioSelectionFailure.EntryScope
    )


def test_flag1_animation_captures_stop_at_later_request_and_waits_during_ui():
    state = _Frontier(
        (),
        (),
        False,
        False,
        False,
        False,
        _Empty.Message,
        _Empty.ItemUI,
        (),
        _PickupAnimation.Starting,
        _PickupOwner.Unobserved,
    )
    first = _animation_frontiers(state)
    assert all(s.item_ui is _Empty.ItemUI for s in first)
    waiting = next(s for s in first if s.animation is _PickupAnimation.Waiting)
    requested = next(
        s
        for s in _animation_frontiers(replace(waiting, stop7=True))
        if s.item_ui is not _Empty.ItemUI
    )
    assert requested.item_ui.saved7
    active = replace(waiting, item_ui=_ItemUI(False, _UIPhase.Active))
    assert _animation_frontiers(active) == {active}


def test_item_ui_cannot_restore_snapshot_before_filtered_mapping_frontier():
    state = _Frontier(
        (),
        (),
        True,
        True,
        False,
        False,
        _Empty.Message,
        _ItemUI(False, _UIPhase.Active),
        (),
        _Empty.Animation,
        _PickupOwner.Unobserved,
    )
    first = _ui_completion_frontiers(state)
    assert len(first) == 1
    fenced = first.pop()
    assert fenced.stop6 and fenced.stop7
    assert fenced.item_ui.phase is _UIPhase.Fenced
    final = _ui_completion_frontiers(fenced)
    assert fenced in final
    completed = next(s for s in final if s.item_ui is _Empty.ItemUI)
    assert not completed.stop6 and not completed.stop7


def test_accepted_ui_clears_only_its_selected_source_record_and_aliases():
    selected = _Binding(2, 0x31, "", 0, 100)
    other = _Binding(2, 0x31, "", 0, 200)
    state = _Frontier(
        (),
        (selected, selected, other),
        True,
        True,
        False,
        False,
        _Empty.Message,
        _ItemUI(False, _UIPhase.Active),
        (selected, other),
        _Empty.Animation,
        selected.record,
    )
    results = _ui_completion_frontiers(state)
    assert len(results) == 2
    accepted = next(s for s in results if s.records[0].kind == 0)
    assert accepted.records == (replace(selected, kind=0), other)
    assert accepted.bindings == (
        replace(selected, kind=0),
        replace(selected, kind=0),
        other,
    )
    assert accepted.item_ui.phase is _UIPhase.Fenced
    assert any(s.records == state.records for s in results)


@pytest.mark.parametrize("fault", ["acquired_item", "acquired_four_point"])
def test_acquired_reexecuted_item_clears_mutable_record_before_scripted_dispatch(
    profile, monkeypatch, fault
):
    data, room, context, ingress = setup(profile, fault)
    assert room["candidate_list_complete"]
    dispatch = next(
        r for r in room["programs"]["17:2"]["commands"] if r["opcode"] == 0x47
    )
    observed = []
    original = control_module.replace

    def record_transition(value, **changes):
        result = original(value, **changes)
        if isinstance(result, _Frontier):
            task = result.tasks[4]
            if (
                isinstance(task, control_module._Task)
                and task.root == "17:2"
                and task.pc == dispatch["next"]
                and result.bindings[11].kind == 0
            ):
                observed.append(result)
        return result

    monkeypatch.setattr(control_module, "replace", record_transition)
    proof = source_task_control_scope(data, room, profile, context, ingress)
    assert isinstance(proof, VerifiedSourceTaskControl), proof
    assert observed
    assert any(s.item_ui is _Empty.ItemUI for s in observed)
    for state in observed:
        binding = state.bindings[11]
        assert next(r for r in state.records if r.record == binding.record) == binding
        assert not any(
            isinstance(t, control_module._Task) and t.root == "17:6"
            for t in state.tasks
        )
