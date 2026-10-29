"""Synthetic quantity effects; RE1-QUANTITY-001 records native evidence and limits."""

import json
from dataclasses import replace

import pytest
from test_cache_metadata import pickup
from test_event_activation import indexed
from test_event_conditions import block
from test_live_items import RamReader
from test_tracking_rules import branch, compile_program, door, guard

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re1.room_items import RuntimeItemState
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)
from tracker.exploration_state import ItemDetail, RoomCompletion, Tracker
from ui.map_view import map_state

pytest_plugins = ("test_tracking_rules",)


def calculate(program, rules, ram, flags, epoch):
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    assert not snapshot.error
    return evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, flags, ((0x44, "Green Herb"),), epoch
    )


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("amount", [0, 9, 255])
def test_scalar_write_changes_quantity_without_changing_acquisition(
    rules, epoch, amount
):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + bytes((8, 12, amount, 0, 0x4C, 1, 0, 12, 0)),
    )
    ram = bytearray(2 * 1024 * 1024)
    ram[rules[0].byte_variables_base - 0x80000000 + 12] = amount ^ 255
    before = bytes(ram)
    flags = bytearray([255] * 32)
    for taken in (False, True, False):
        flags[14] = 254 if taken else 255
        result = calculate(program, rules, ram, bytes(flags), epoch)
        assert result.items.list_complete
        item = result.items.items[0]
        assert (
            item.amount == amount and item.item_type == 0x44 and item.global_id == 111
        )
        assert item.state == (
            RuntimeItemState.Taken if taken else RuntimeItemState.Available
        )
    assert bytes(ram) == before


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_read_after_write_preserves_scalar_aliases_and_supported_guard(rules, epoch):
    code = (
        pickup(0, 0x44, 111)
        + bytes((8, 12, 7, 0, 0x4C, 1, 0, 12, 0x4C, 0, 0, 9))
        + guard(bytes((6, 9, 0, 7)), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        bytes([255]) * 32,
        epoch,
    )
    assert result.items.list_complete
    assert [i.aot_id for i in result.items.items] == [0, 1]
    assert result.items.items[0].amount == 7


@pytest.mark.parametrize("transfer", [1, 2])
@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_unknown_amount_keeps_item_identity_and_completion_knowledge(
    rules, transfer, epoch
):
    code = pickup(0, 0x44, 111) + bytes((0x4C, transfer, 0, 12, 0))
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        bytes(32),
        epoch,
    )
    assert result.items.list_complete and not result.unresolved_item_slots
    assert result.items.items[0].amount is ItemQuantityState.Unreconstructed
    assert result.items.items[0].state == RuntimeItemState.Taken


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_different_amount_paths_join_without_merging_different_items(rules, epoch):
    code = (
        pickup(0, 0x44, 111)
        + branch(bytes((0x1A, 0x26)), bytes((8, 12, 1, 0)), bytes((8, 12, 2, 0)))
        + bytes((0x4C, 1, 0, 12, 0))
    )
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        bytes([255]) * 32,
        epoch,
    )
    assert (
        result.items.list_complete
        and result.items.items[0].amount is ItemQuantityState.Unreconstructed
    )
    divergent = branch(
        bytes((0x1A, 0x26)), pickup(0, 0x44, 111), pickup(0, 0x26, 63)
    ) + bytes((0x4C, 1, 0, 12, 0))
    result = calculate(
        compile_program(rules, divergent),
        rules,
        bytearray(2 * 1024 * 1024),
        bytes([255]) * 32,
        epoch,
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (0,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_unknown_quantity_guard_still_blocks_availability(rules, epoch):
    code = (
        pickup(0, 0x44, 111)
        + bytes((8, 12, 0, 0, 0x4C, 2, 0, 12))
        + branch(bytes((6, 12, 0, 0)), bytes((0x13, 0, 0, 129)), b"")
        + b"\0"
    )
    ram = bytearray(2 * 1024 * 1024)
    result = calculate(
        compile_program(rules, code), rules, ram, bytes([255]) * 32, epoch
    )
    assert not result.items.list_complete and result.unresolved_item_slots == (0,)


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_quantity_read_of_immutable_source_can_control_a_later_pickup(rules, epoch):
    code = (
        pickup(0, 0x44, 111)
        + bytes((0x4C, 0, 0, 12))
        + guard(bytes((6, 12, 0, 0)), pickup(1, 0x26, 63))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        bytes([255]) * 32,
        epoch,
    )
    assert result.items.list_complete and [i.aot_id for i in result.items.items] == [
        0,
        1,
    ]


@pytest.mark.parametrize("synchronous", [False, True])
@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
def test_optional_event_quantity_write_does_not_erase_item_identity(
    rules, synchronous, epoch
):
    code = bytes((8, 12, 7, 0, 0x4C, 1, 0, 12, 0))
    event = indexed(
        (block(code) if synchronous else bytes((7, 6, 0x4C, 1, 0, 12))) + b"\xff"
    )
    init = pickup(0, 0x44, 111) + bytes((0x14, 0, 0, 0, 0))
    program = compile_program(rules, init, event=event)
    if not synchronous:
        assert [(c.kind, c.args) for c in program.event_effects] == [
            ("quantity-transfer", (1, 0, 12))
        ]
    result = calculate(
        program, rules, bytearray(2 * 1024 * 1024), bytes([255]) * 32, epoch
    )
    assert (
        result.items.list_complete
        and result.items.items[0].amount is ItemQuantityState.Unreconstructed
    )


@pytest.mark.parametrize("source", ["missing", "door", "generic"])
def test_quantity_write_requires_an_audited_item_source(rules, source):
    init = b""
    if source == "door":
        init = door(0, 8, 0x34)
    elif source == "generic":
        init = bytes((0x0D, 0)) + bytes(8) + bytes((16, 129)) + bytes(6)
    code = init + pickup(1, 0x44, 111) + bytes((0x4C, 1, 0, 12, 0))
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        bytes(32),
        RoomRuleEpoch.Reentry,
    )
    assert not result.items.list_complete


def test_unreachable_quantity_write_does_not_hide_a_known_item(rules):
    code = (
        pickup(1, 0x44, 111)
        + guard(bytes((6, 1, 0, 10)), bytes((0x4C, 1, 0, 12)))
        + b"\0"
    )
    result = calculate(
        compile_program(rules, code),
        rules,
        bytearray(2 * 1024 * 1024),
        bytes(32),
        RoomRuleEpoch.Reentry,
    )
    assert (
        result.items.list_complete
        and result.items.items[0].state == RuntimeItemState.Taken
    )


def test_repeated_creator_cannot_restore_a_mutated_source_quantity(rules):
    code = pickup(0, 0x44, 111) + bytes((8, 12, 7, 0, 0x4C, 1, 0, 12, 0))
    program = compile_program(rules, code, main=pickup(0, 0x44, 111) + b"\0")
    result = calculate(
        program,
        rules,
        bytearray(2 * 1024 * 1024),
        bytes([255]) * 32,
        RoomRuleEpoch.Reentry,
    )
    assert result.items.list_complete
    assert result.items.items[0].amount is ItemQuantityState.Unreconstructed


def test_quantity_read_is_not_a_descriptor_event_effect(rules):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed(bytes((7, 6, 0x4C, 0, 0, 12, 0xFF))),
    )
    assert not program.event_effects
    with pytest.raises(ValueError, match="event effects"):
        replace(program, event_effects=program.event_commands)


def test_map_payload_reports_remaining_and_collected_with_explicit_amount_state():
    tracker = Tracker(player_heading=90.0)
    room = RoomId(0, 9)
    tracker.mark_current(room)
    tracker.region_visits["mansion1f:09"] = str(room)
    tracker.current_region = "mansion1f:09"
    for taken in (False, True, False):
        tracker.update_room_items(room, 1, int(taken), True, not taken, False)
        tracker.rooms[str(room)].items = (
            ItemDetail(
                "Green Herb",
                "taken" if taken else "available",
                ItemQuantityState.Unreconstructed,
                False,
            ),
        )
        payload = json.loads(json.dumps(map_state(tracker)))
        record = payload["rooms"][0]
        assert record["state"] == (
            RoomCompletion.Cleared.value if taken else RoomCompletion.Incomplete.value
        )
        assert record["items"][0]["quantity"] == "unreconstructed"


@pytest.mark.parametrize("quantity", [None, True, -1, "unreconstructed"])
def test_invalid_quantity_does_not_silently_default(quantity):
    with pytest.raises(AssertionError, match="quantity"):
        ItemDetail("Herb", "available", quantity, False)
