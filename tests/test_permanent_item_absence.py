"""RE1-CLEAR-007: source-proven absence is separate from puzzle dormancy."""

from dataclasses import replace

import pytest
from test_cache_metadata import indexed_event, pickup
from test_live_items import REPO, RamReader, fixture_ram
from test_tracking_rules import compile_program, evaluate, guard
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from games.re1.room_items import RuntimeItemState, RuntimeRoomItems
from games.re1.tracking_engine import validate_current_room
from games.re1.tracking_rules import (
    RoomRuleEpoch,
    evaluate_room_program,
    read_rule_snapshot,
)
from tracker.exploration_state import RoomCompletion, Tracker

pytest_plugins = ("test_tracking_rules", "test_puzzle_items")


@pytest.mark.parametrize("flags", [bytes([255]) * 32, bytes(32)])
def test_only_explicit_disablement_proves_permanent_absence(rules, flags):
    ram = bytearray(2 * 1024 * 1024)
    program = compile_program(rules, pickup(5, 0x44, 111) + b"\0")
    result = evaluate(program, rules, ram, flags)
    assert result.collection_items.items[0].state is not RuntimeItemState.Unavailable
    program = compile_program(rules, pickup(5, 0x44, 111) + bytes((0x13, 5, 0, 0, 0)))
    result = evaluate(program, rules, ram, flags)
    assert result.collection_items.list_complete
    assert result.collection_items.items[0].state is RuntimeItemState.Unavailable


@pytest.mark.parametrize("later", ["main-enable", "event-enable", "award", "recreate"])
def test_later_slot_effects_keep_the_puzzle_reward(rules, later):
    init = pickup(5, 0x44, 111) + bytes((0x13, 5, 0, 0, 0))
    main, events = b"\0", bytes(4)
    if later == "main-enable":
        main = guard(bytes((4, 0, 40, 1)), bytes((0x13, 5, 4, 0))) + b"\0"
    elif later == "event-enable":
        events = indexed_event(bytes((7, 6, 0x13, 5, 4, 0, 0xFF)))
    elif later == "award":
        main = bytes((0x24, 5, 4, 0, 0))
    else:
        main = pickup(5, 0x44, 111) + b"\0"
    result = evaluate(
        compile_program(rules, init, main, events),
        rules,
        bytearray(2 * 1024 * 1024),
    )
    assert result.collection_items.list_complete
    assert result.collection_items.items[0].state in (
        RuntimeItemState.Uncollected,
        RuntimeItemState.Available,
    )


@pytest.mark.parametrize("epoch", list(RoomRuleEpoch))
@pytest.mark.parametrize("value", [0, 1])
def test_conditional_disablement_and_incomplete_sources_do_not_prove_absence(
    rules, epoch, value
):
    init = (
        pickup(5, 0x44, 111)
        + guard(bytes((4, 0, 40, 1)), bytes((0x13, 5, 0, 0)))
        + b"\0"
    )
    program = compile_program(rules, init)
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(0, 40)
    ram[address - 0x80000000] = mask if value else 0
    snapshot = read_rule_snapshot(rules[0], (program,), RamReader(ram).read_memory)
    result = evaluate_room_program(
        program, RoomId(0, 9), rules[0], snapshot, bytes([255]) * 32, (), epoch
    )
    assert result.collection_items.list_complete
    assert result.collection_items.items[0].state in (
        RuntimeItemState.Uncollected,
        RuntimeItemState.Available,
    )
    program = replace(program, coverage_complete=False)
    result = evaluate(program, rules, ram)
    assert not result.collection_items.list_complete


@pytest.mark.parametrize("dormant_room", ["permanent"], indirect=True)
def test_current_permanent_absence_and_live_contradiction(dormant_room):
    profile, ram = dormant_room
    tracker = Tracker()
    room = RoomId(0, 9)
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status is PollStatus.Display, result.text
    assert tracker.room_state(room).completion is RoomCompletion.Cleared
    assert tracker.room_state(room).items == ()
    ram[0xB819C] = 4
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status is PollStatus.Display, result.text
    record = tracker.room_state(room)
    assert record.completion is not RoomCompletion.Cleared
    assert any(item.state == "available" for item in record.items)
    assert not record.list_complete


@pytest.mark.parametrize("dormant_room", ["permanent"], indirect=True)
def test_an_acquisition_bit_does_not_make_a_permanently_absent_item_visible(
    dormant_room,
):
    profile, ram = dormant_room
    source = next(
        s for s in profile.room_sources if s.source_rdt.endswith("ROOM1091.RDT")
    )
    program = profile.room_programs[source.source_rdt]
    snapshot = read_rule_snapshot(
        profile.tracking_rule_layout, (program,), RamReader(ram).read_memory
    )
    layout = profile.runtime_room_layout
    item = evaluate_room_program(
        program,
        source.room,
        profile.tracking_rule_layout,
        snapshot,
        bytes(ram[0xC86DC:0xC86FC]),
        layout.item_labels,
    ).collection_items.items[0]
    result = validate_current_room(
        profile,
        RuntimeRoomItems(
            ok=True,
            items=(replace(item, state=RuntimeItemState.Taken),),
            list_complete=True,
        ),
        (source,),
        snapshot,
        bytes(ram[0xC86DC:0xC86FC]),
    )
    assert result.items.list_complete
    assert result.items.items[0].state is RuntimeItemState.Unavailable


@pytest.mark.parametrize("fresh_tracker", [False, True])
def test_meeting_room_source_and_acquisition_reversal(tmp_path, fresh_tracker):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    room = RoomId(3, 0x0F)
    flag = profile.runtime_room_layout.acquisition.flag(61, 105)
    # These are offline source-selection and acquisition substitutions, not
    # gameplay, normal-save persistence or support for a Chris playthrough.
    for character, remaining in (
        (1, True),
        (0, True),
        (1, False),
        (0, False),
        (1, True),
    ):
        if fresh_tracker:
            tracker = Tracker()
            profile.room_reentry_evaluations.clear()
        tracker.mark_current(room)
        ram[0xC8669] = character
        ram[0xC3002] = ram[0xC3002] | 0x80 if character == 1 else ram[0xC3002] & ~0x80
        offset = flag.address - 0x80000000
        ram[offset] = ram[offset] | flag.mask if remaining else ram[offset] & ~flag.mask
        result = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert result.status is PollStatus.Display, result.text
        record = tracker.room_state(room)
        assert record.list_complete
        if character == 1:
            assert record.items == ()
            assert record.completion is RoomCompletion.Cleared
        else:
            assert [item.label for item in record.items] == ["Small Key"]
            assert record.items[0].state == ("available" if remaining else "taken")
