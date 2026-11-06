"""RE2-SCENARIO-006: normal-engine roles retain source/control boundaries."""

import struct

import pytest
from test_re2_scenario_entry_scope import callback, scoped
from test_re2_scenario_entry_scope import profile as profile  # noqa: PLC0414
from test_re2_startup_declarations import END

from games.re2.scenario_entry_scope import scenario_guard_scope
from games.re2.scenario_selection import (
    ScenarioSelectionFailure,
    VerifiedScenarioEntryScope,
    VerifiedScenarioGuardScope,
)


@pytest.mark.parametrize("opcode", [0x34, 0x35, 0x3D])
@pytest.mark.parametrize("selector", [0, 1, 5, 7, 12, 30, 255])
def test_trusted_members_grant_only_explicit_scalar_selectors(
    profile, opcode, selector
):
    packet = (
        bytes((opcode, selector, 0xFF, 0xFF))
        if opcode == 0x34
        else bytes((opcode, selector, 16))
        if opcode == 0x35
        else bytes((opcode, 16, selector))
    )
    data, room, context, strict = scoped(profile, main=(packet + END, END))
    accepted = selector in (0, 1, 5, 7, 12)
    result = scenario_guard_scope(data, room, profile, context)
    assert isinstance(result, VerifiedScenarioGuardScope) is accepted
    # Selector 12 was already admitted for counter copies by the strict recipe.
    assert isinstance(strict, VerifiedScenarioEntryScope) is (
        selector == 12 and opcode != 0x34
    )


@pytest.mark.parametrize("opcode", [0x35, 0x3D])
@pytest.mark.parametrize("counter", [128, 255])
def test_trusted_scalar_copy_retains_counter_destination_bounds(
    profile, opcode, counter
):
    operands = (7, counter) if opcode == 0x35 else (counter, 7)
    data, room, context, _ = scoped(
        profile, main=(bytes((opcode, *operands)) + END, END)
    )
    assert (
        scenario_guard_scope(data, room, profile, context)
        is ScenarioSelectionFailure.EntryScope
    )


@pytest.mark.parametrize(
    "category,index,accepted",
    [
        (1, 0, True),
        (3, 31, True),
        (4, 31, True),
        (3, 32, False),
        (4, 32, False),
        (3, 255, False),
        (5, 0, False),
    ],
)
def test_trusted_members_still_require_bounded_work_selection(
    profile, category, index, accepted
):
    data, room, context, _ = scoped(
        profile, main=(bytes((0x2E, category, index, 0x34, 7, 0, 0)) + END, END)
    )
    assert (
        isinstance(
            scenario_guard_scope(data, room, profile, context),
            VerifiedScenarioGuardScope,
        )
        is accepted
    )


@pytest.mark.parametrize(
    "model,slot,padding,accepted",
    [
        (0x21, 0, 0, True),
        (0x2A, 31, 0, True),
        (0x21, 32, 0, False),
        (0x21, 255, 0, False),
        (0x0F, 0, 0, False),
        (0x50, 0, 0, False),
        (0x21, 0, 1, False),
    ],
)
def test_normal_constructor_does_not_grant_out_of_record_source_writes(
    profile, model, slot, padding, accepted
):
    packet = bytearray(22)
    packet[:4] = bytes((0x44, padding, slot, model))
    struct.pack_into("<H", packet, 4, 0x4000)
    data, room, context, strict = scoped(profile, main=(bytes(packet) + END, END))
    assert strict is ScenarioSelectionFailure.EntryScope
    assert (
        isinstance(
            scenario_guard_scope(data, room, profile, context),
            VerifiedScenarioGuardScope,
        )
        is accepted
    )


@pytest.mark.parametrize(
    "first,second,accepted",
    [(0, 2, True), (33, 0, True), (34, 0, False), (0, 255, False)],
)
def test_position_predicate_keeps_both_actor_selectors_in_the_pointer_table(
    profile, first, second, accepted
):
    check = bytes((0x85, first, second, 0, 0, 0x84))
    body = b"\x06\0\x08\0" + check + b"\x08\0"
    data, room, context, strict = scoped(profile, main=(body + END, END))
    assert strict is ScenarioSelectionFailure.EntryScope
    assert (
        isinstance(
            scenario_guard_scope(data, room, profile, context),
            VerifiedScenarioGuardScope,
        )
        is accepted
    )


def test_position_predicate_failure_pops_if_but_keeps_occupied_loop(profile):
    check = b"\x85\0\x02\0\0\x84"
    loop = b"\x0d\0" + struct.pack("<hH", len(check) + 2, 2) + check + b"\x0e\0"
    outer = b"\x06\0" + struct.pack("<H", len(loop) + 2) + loop + b"\x08\0"
    suffix = b"\x02"
    for _ in range(4):
        suffix = b"\x0d\0" + struct.pack("<hH", len(suffix) + 2, 2) + suffix + b"\x0e\0"
    # Only predicate failure abandons the first loop. Treating 85 as a scalar
    # fallthrough would miss the fifth occupied native loop cell in the suffix.
    data, room, context, _ = scoped(profile, main=(outer + suffix + END, END))
    assert (
        scenario_guard_scope(data, room, profile, context)
        is ScenarioSelectionFailure.EntryScope
    )


def test_camera_back_is_only_a_guard_role(profile):
    data, room, context, strict = scoped(profile, main=(b"\x2a" + END, END))
    assert strict is ScenarioSelectionFailure.EntryScope
    assert isinstance(
        scenario_guard_scope(data, room, profile, context), VerifiedScenarioGuardScope
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "wrong_slot",
        "kind_five",
        "sleep",
        "call",
        "canonical_entry",
        "if_bypass",
        "predicate_bypass",
        "copy",
    ],
)
def test_latest_door_reset_requires_uninterrupted_dominating_control(profile, mutation):
    reset = bytes((0x46, 7, 1, 0x31)) + bytes(6)
    dispatch = b"\x47\x07"
    main = (END, reset + dispatch + END, END)
    if mutation == "wrong_slot":
        main = (END, reset[:1] + b"\x06" + reset[2:] + dispatch + END, END)
    elif mutation == "kind_five":
        main = (END, b"\x46\x07\x05\x31\xff\0\x18\x02\0\0" + dispatch + END, END)
    elif mutation in ("sleep", "call"):
        separator = b"\x09\x0a\x01\0" if mutation == "sleep" else b"\x18\x02"
        main = (END, reset + separator + dispatch + END, END)
    elif mutation == "canonical_entry":
        # Reset in another procedure grants no ownership at this entry.
        main = (reset + END, dispatch + END, END)
    elif mutation == "if_bypass":
        # False IF skips Reset and enters Aot_on with otherwise legal frames.
        main = (END, b"\x06\0\x0a\0" + reset + dispatch + END, END)
    elif mutation == "predicate_bypass":
        # The IF target is the dispatch. Predicate failure can bypass Reset
        # while retaining a legal empty IF stack at the dispatch.
        prefix = b"\x06\0\x10\0\x85\0\x02\0\0\x84"
        main = (END, prefix + reset + dispatch + END, END)
    elif mutation == "copy":
        # Copy changes only the Reset descriptor kind, keeping its opcode.
        main = (END, b"\x1d\x04\x02\0" + reset + dispatch + END, END)
    data, room, context, strict = scoped(profile, init=callback(2) + END, main=main)
    assert strict is ScenarioSelectionFailure.EntryScope
    assert isinstance(
        scenario_guard_scope(data, room, profile, context), VerifiedScenarioGuardScope
    ) is (mutation == "none")


@pytest.mark.parametrize(
    "packet,displacement",
    [
        (b"\x34\x07\0\0", 1),
        (b"\x35\x07\x10", 2),
        (b"\x3d\x10\x07", 2),
        (b"\x44\0\0\x21" + bytes(18), 2),
        (b"\x85\0\x02\0\0\x84", 1),
    ],
)
def test_copy_cannot_retarget_new_native_roles(profile, packet, displacement):
    data, room, context, _ = scoped(
        profile, main=(bytes((0x1D, 4, displacement, 0)) + packet + END, END)
    )
    assert (
        scenario_guard_scope(data, room, profile, context)
        is ScenarioSelectionFailure.EntryScope
    )
