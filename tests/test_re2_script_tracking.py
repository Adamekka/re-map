"""Script evaluation inside the live RE2 reader. RE2-EVAL-001.

Synthetic coherent snapshots only; native validation is recorded separately.
"""

from __future__ import annotations

import pytest
from test_re2_tracking import ROOT, build_snapshot

from games.bit_flags import msb_flag_location
from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.fixture
def leon(script_evaluation):
    return Re2Profile.load(ROOT / "profiles" / "re2_leon_a_slus00748.json")


def test_departed_rooms_resolve_every_item_and_door(leon):
    profile, _, _, read = build_snapshot(leon, "00-01")
    tracker = Tracker()
    for key in profile.rooms:
        tracker.mark_current(RoomId(*(int(part, 16) for part in key.split("-"))))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    departed = {key: record for key, record in tracker.rooms.items() if key != "00-01"}
    assert all(
        record.completion is not RoomCompletion.Unknown for record in departed.values()
    )
    assert not [
        item
        for record in departed.values()
        for item in record.items
        if item.state == "unknown"
    ]
    assert not [
        door
        for door in tracker.doors
        if str(door.source) != "00-01" and door.state == "UNCHECKED"
    ]


def test_fresh_acquisition_and_rewind_reach_departed_evaluations(leon):
    profile, _, put, read = build_snapshot(leon, "00-01")
    room = "01-00"
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 0))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    remaining = [
        item for item in tracker.rooms[room].items if item.state == "uncollected"
    ]
    assert remaining and tracker.rooms[room].completion is RoomCompletion.Incomplete
    layout = profile.runtime_layout
    bank = layout["item_bank_early"]
    address, _ = profile.flag_banks[bank]
    gids = sorted(profile.script_evaluation.item_ids[room])
    for collected in (True, False, True):
        for gid in gids:
            word, mask = msb_flag_location(address, gid)
            current = int.from_bytes(read(word, 4).data, "little")
            put(word, current | mask if collected else current & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        states = {item.state for item in tracker.rooms[room].items}
        if collected:
            assert states == {"taken"}
            assert tracker.rooms[room].completion is RoomCompletion.Cleared
        else:
            assert "uncollected" in states
            assert tracker.rooms[room].completion is RoomCompletion.Incomplete


def test_absent_pickup_alternatives_do_not_block_clearance(script_evaluation):
    # RE2-COLLECT-024: Claire B's room 01-0c has two possible types for ID 207.
    # The room resets that pickup's slot, leaving only ID 170 required.
    profile = Re2Profile.load(ROOT / "profiles" / "re2_claire_b_slus00756.json")
    profile, _, put, read = build_snapshot(profile, "00-04")
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 0x0C))
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]

    for collected, ambiguous_taken, completion in (
        (False, False, RoomCompletion.Incomplete),
        (True, False, RoomCompletion.Cleared),
        (True, True, RoomCompletion.Unknown),
        (True, False, RoomCompletion.Cleared),
        (False, False, RoomCompletion.Incomplete),
    ):
        for gid, taken in ((170, collected), (207, ambiguous_taken)):
            address, mask = msb_flag_location(bank, gid)
            word = int.from_bytes(read(address, 4).data, "little")
            put(address, word | mask if taken else word & ~mask, 4)

        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["01-0c"]
        assert record.completion is completion
        assert record.list_complete is (not ambiguous_taken)
        assert record.total_items == 1 + ambiguous_taken
        assert record.collected_items == collected + ambiguous_taken
        if ambiguous_taken:
            [unknown_identity] = [
                item for item in record.items if item.label == "Collectible"
            ]
            assert unknown_identity.state == "taken"
            assert unknown_identity.quantity is ItemQuantityState.Unreconstructed


def test_current_door_slots_follow_the_live_registry(leon):
    profile, _, put, read = build_snapshot(leon, "00-01")
    definition = profile.rooms["00-01"]["doors"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    registry = (
        int(profile.runtime_layout["aot_table_address_ps1"], 0) + definition["slot"] * 4
    )
    observation = f"00-01:{definition['offset']}"

    def door():
        tracker = Tracker()
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        return [d for d in tracker.doors if d.observation_id == observation]

    [live] = door()
    assert live.state == "OPEN"
    # A message written over the door in place blocks it.
    put(pointer, 4, 1)
    assert [d.state for d in door()] == ["BLOCKED"]
    # A door descriptor whose geometry bit disagrees cannot be trusted.
    put(pointer, 1, 1)
    put(pointer + 1, 0x31 | (0x00 if definition["four_point"] else 0x80), 1)
    assert [d.state for d in door()] == ["UNCHECKED"]
    # An empty slot holds no door now.
    put(registry, 0, 4)
    assert door() == []


def test_map_state_lists_doors_absent_in_game_state(leon):
    from ui.map_view import map_state

    profile, _, put, read = build_snapshot(leon, "00-01")
    definition = profile.rooms["00-01"]["doors"][0]
    put(
        int(profile.runtime_layout["aot_table_address_ps1"], 0)
        + definition["slot"] * 4,
        0,
        4,
    )
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert f"00-01:{definition['offset']}" in map_state(tracker)["absent_doors"]
    # A rewind that restores the slot removes the absence.
    tracker = Tracker()
    profile, _, _, read = build_snapshot(leon, "00-01")
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert map_state(tracker)["absent_doors"] == []


def test_inventory_change_during_a_poll_publishes_nothing(leon):
    from dataclasses import replace

    from games.scd_state import ScriptStateCache

    profile, _, _, read = build_snapshot(leon, "00-01")
    evaluation = profile.script_evaluation

    def checks():
        return [
            [offset * 10, offset * 10 + 10, *row]
            for offset, row in enumerate([["if", 30], ["has", 98], ["end"], ["end"]])
        ]

    # Source 05-01 checks a carried item in two procedures, so a poll consumes
    # the inventory count twice.
    profile = replace(
        profile,
        script_evaluation=replace(
            evaluation,
            models={
                **evaluation.models,
                "05-01": {"init:0": checks(), "main:0": checks(), "main:1": checks()},
            },
        ),
        script_cache=ScriptStateCache(),
    )
    tracker = Tracker()
    tracker.mark_current(RoomId(5, 1))
    reads = 0

    def changing(address, width):
        nonlocal reads
        result = read(address, width)
        if address == evaluation.inventory_count_address and width == 1:
            reads += 1
            if reads > 1:
                # A savestate load adds an item after the first sample.
                return type(result)(True, bytes([1]), "")
        return result

    assert poll_re2(profile, tracker, changing).status is PollStatus.Retry


def award_case(leon, presence=None, collection=None, model=None):
    """Leon's 01-02 award with an optional replaced proof, binding or model."""
    from dataclasses import replace

    from games.scd_state import ScriptStateCache

    profile, _, put, read = build_snapshot(leon, "00-01")
    room = "01-02"
    [award] = profile.rooms[room]["event_awards"]
    award = {
        **award,
        "presence": presence or award["presence"],
        "collection": collection or award["collection"],
    }
    evaluation = profile.script_evaluation
    profile = replace(
        profile,
        rooms={**profile.rooms, room: {**profile.rooms[room], "event_awards": [award]}},
        script_evaluation=replace(
            evaluation,
            models={**evaluation.models, room: model or evaluation.models[room]},
        ),
        script_cache=ScriptStateCache(),
    )
    name = profile.names["items"][str(award["item_type"])]

    def set_flag(bank, bit, value):
        word, mask = msb_flag_location(profile.flag_banks[bank][0], bit)
        current = int.from_bytes(read(word, 4).data, "little")
        put(word, current | mask if value else current & ~mask, 4)

    def award_rows():
        tracker = Tracker()
        tracker.mark_current(RoomId(1, 2))
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        return [
            (item.label, item.state)
            for item in tracker.rooms[room].items
            if item.label in (name, "Event collectible")
        ]

    # 8:5 is the award's real acquisition flag.
    for bank, bit in ((1, 1), (4, 7), (8, 5)):
        set_flag(bank, bit, False)
    return name, set_flag, award_rows


@pytest.mark.parametrize("proven", [False, True])
def test_award_presence_follows_the_room_scripts(leon, proven):
    # Claire B binds the same award without a presence proof. With Leon's
    # proof, a failing condition defers to the evaluation as well.
    name, set_flag, award_rows = award_case(
        leon, presence=None if proven else {"kind": "unresolved"}
    )
    # Entering starts the award's event.
    assert award_rows() == [(name, "uncollected")]
    # No procedure can run it once its event has happened.
    set_flag(4, 7, True)
    assert award_rows() == []
    # Acquisition still wins.
    set_flag(8, 5, True)
    assert award_rows() == [(name, "taken")]


def test_award_without_a_bound_flag_ignores_the_evaluation(leon):
    # Without its acquisition flag a delivered award would stay listed, and an
    # absent one cannot be told from a delivered one.
    unresolved = {"kind": "unresolved"}
    _, set_flag, award_rows = award_case(
        leon, presence=unresolved, collection=unresolved
    )
    expected = [("Event collectible", "unknown")]
    assert award_rows() == expected
    set_flag(4, 7, True)
    assert award_rows() == expected


def test_award_under_unreadable_state_stays_unknown(leon):
    model = leon.script_evaluation.models["01-02"]
    # Entry starts the award's event behind an unreadable condition instead
    # of the 4:7 check, and the event awards at once. The real event waits
    # first, so later analysis would resume it and find the award obtainable.
    main = [
        row[:2] + ["cond", 0] if row[2:] == ["ck", 4, 7, 0] else row
        for row in model["main:0"]
    ]
    assert main != model["main:0"]
    event = [[8944, 8947, "award"], [8947, 8949, "end"]]
    _, _, award_rows = award_case(
        leon,
        presence={"kind": "unresolved"},
        model={**model, "main:0": main, "main:2": event},
    )
    assert award_rows() == [("Event collectible", "unknown")]
