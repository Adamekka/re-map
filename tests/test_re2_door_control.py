"""Door frame rights stay separate from existing positive and guard policies."""

import json
import struct
from enum import Enum, IntEnum

import pytest
from test_re2_immutable_open_doors import door
from test_re2_metadata import ROOT
from test_re2_startup_declarations import END, contract, described

from games.re2.normal_engine_binding import typed_binding_digest
from games.re2.scenario_entry_scope import (
    DoorSourceFacts,
    DoorSourceFailure,
    _ScopePolicy,
    _source_scope_facts,
)
from games.re2.scenario_selection import ScenarioSelectionFailure, bind_scenario_context
from games.re2.source_task_control import TaskControlSupport
from games.re2.structured_control import (
    ControlFrameFailure,
    ControlFrames,
    PredicateOutcome,
    StructuredControl,
    structured_control,
)


@pytest.mark.parametrize("expected", [0, 1])
def test_only_door_frames_prune_an_immutable_fixed_scenario_branch(expected):
    body = bytearray(
        b"\x06\0"
        + struct.pack("<H", len(door()) + 6)
        + b"\x21\x01\0\0"
        + door()
        + b"\x08\0"
        + END
    )
    body[7] = expected
    data, room, _ = described(END, (bytes(body), END))
    program = room["programs"]["17:0"]
    check = next(r for r in program["commands"] if r["kind"] == "flag_check")
    creator = room["doors"][0]["offset"]
    outcome = (
        PredicateOutcome.Matches if expected == 0 else PredicateOutcome.DoesNotMatch
    )
    pruned = structured_control(
        data, program, ControlFrames.Doors, predicates=((check["offset"], outcome),)
    )
    assert type(pruned) is StructuredControl
    assert (creator in pruned.reached) == (expected == 0)
    assert program["commands"][-1]["offset"] in pruned.reached
    for role in (
        ControlFrames.Strict,
        ControlFrames.FreshPositive,
        ControlFrames.Doors,
        ControlFrames.IdentityFiltering,
    ):
        opaque = structured_control(data, program, role)
        assert type(opaque) is StructuredControl
        assert creator in opaque.reached
        if role is not ControlFrames.Doors:
            with pytest.raises(AssertionError):
                structured_control(
                    data, program, role, predicates=((check["offset"], outcome),)
                )
    p = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    context = bind_scenario_context(p, contract(p, room))
    source = _source_scope_facts(
        data, room, p, context, _ScopePolicy.TrustedDoors, TaskControlSupport.Unaudited
    )
    assert type(source) is DoorSourceFacts
    assert (("17:0", creator) in source.reached) == (expected == 0)


@pytest.mark.parametrize(
    "bank,bit,operation,accepted",
    [(2, 7, 7, True), (1, 6, 7, False), (30, 57, 7, False), (2, 7, 2, False)],
)
def test_door_flag_operations_use_shared_native_toggle_and_alias_rules(
    bank, bit, operation, accepted
):
    p = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    data, room, _ = described(
        door() + END, (bytes((0x22, bank, bit, operation)) + END, END)
    )
    context = bind_scenario_context(p, contract(p, room))
    result = _source_scope_facts(
        data, room, p, context, _ScopePolicy.TrustedDoors, TaskControlSupport.Unaudited
    )
    if accepted:
        assert type(result) is DoorSourceFacts
    else:
        assert result == DoorSourceFailure("scenario_flag_write")


@pytest.mark.parametrize("slot", [0, 1])
def test_door_explicit_startup_task_permission_does_not_reach_positive_policy(slot):
    p = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    data, room, _ = described(door() + END, (bytes((4, slot, 0x18, 1)) + END, END))
    context = bind_scenario_context(p, contract(p, room))
    for policy in _ScopePolicy:
        result = _source_scope_facts(
            data, room, p, context, policy, TaskControlSupport.Unaudited
        )
        if policy is _ScopePolicy.TrustedDoors:
            assert type(result) is DoorSourceFacts
        else:
            assert result is ScenarioSelectionFailure.EntryScope


@pytest.mark.parametrize(
    "body,accepted", [(b"\x09\x0a\x01\0", True), (b"\x0a\0\0", False)]
)
def test_embedded_sleep_helper_has_no_standalone_frame_right(body, accepted):
    data, room, _ = described(END, (body + END, END))
    program = room["programs"]["17:0"]
    for role in (
        ControlFrames.Strict,
        ControlFrames.FreshPositive,
        ControlFrames.Doors,
        ControlFrames.IdentityFiltering,
    ):
        result = structured_control(data, program, role)
        assert isinstance(result, StructuredControl) == accepted
        if not accepted:
            assert result is (
                ControlFrameFailure.DoorControl
                if role is ControlFrames.Doors
                else ControlFrameFailure.Unsupported
            )


def test_neutral_binding_digest_keeps_exact_types_and_rejects_mutable_receipts():
    assert typed_binding_digest((True, ())) != typed_binding_digest((1, ()))
    assert typed_binding_digest((b"a", ())) != typed_binding_digest((b"b", ()))
    for mutable in ([], bytearray(b"a"), {"value": 1}):
        with pytest.raises(ValueError, match="binding field"):
            typed_binding_digest((mutable, ()))


def test_neutral_binding_digest_preserves_enum_class_and_value_types():
    class First(Enum):
        Entry = "entry"

    class Second(Enum):
        Entry = "entry"

    class Numeric(IntEnum):
        Entry = 1

    assert (
        len(
            {
                typed_binding_digest(value)
                for value in (
                    First.Entry,
                    Second.Entry,
                    Numeric.Entry,
                    "entry",
                    1,
                    True,
                )
            }
        )
        == 6
    )
