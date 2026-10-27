"""RE2-LIFETIME-001: source lifetime and synthetic fresh-state reconstruction.

These checks do not establish native gameplay or savestate observations.
"""

import json
import struct

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    ROOT,
    SCENARIO_EFFECT_POOL,
    item_command,
    synthetic_room,
)
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re2.live_tracking import poll_re2
from games.re2.room_data import collection_presence, decode_room
from games.re2.scenario_items import scenario_item_proofs, scenario_presence_flags
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.mark.parametrize(
    "case,excluded",
    [
        ("fixed-false", True),
        ("fixed-true", False),
        ("story", False),
        ("compound", False),
        ("uncalled", False),
        ("for", False),
        ("write", False),
        ("incomplete", False),
        ("door", False),
        ("reset", False),
        ("generic-item", False),
    ],
)
def test_generic_creator_lifetime_uses_whole_source_reachability(case, excluded):
    generic = bytes([0x2C, 8, 4, 0x31]) + bytes(16)
    if case == "door":
        generic = bytes([0x3B, 8, 1, 0x31]) + bytes(28)
    elif case == "reset":
        generic = bytes([0x46, 8, 4, 0]) + bytes(6)
    elif case == "generic-item":
        generic = bytes([0x2C, 8, 2, 0x31]) + bytes(16)
    checks = bytes([0x21, 4, 7, 1] if case == "story" else [0x21, 1, 1, 1])
    if case == "compound":
        checks = bytes([0x21, 4, 7, 1]) + checks
    guard = (
        bytes([6, 0])
        + struct.pack("<H", len(checks) + len(generic) + 2)
        + checks
        + generic
        + bytes([8, 0])
    )
    startup = item_command(20, 15, 9) + item_command(39, 1, 10, slot=9)
    extra = ()
    if case == "uncalled":
        extra = (generic + bytes([1, 0]),)
    elif case == "for":
        # Opaque loop procedures retain every creator, including a fixed-false
        # declaration. A loop count is not a lifetime exclusion proof.
        loop = bytes([0x0D, 0]) + struct.pack("<hH", len(guard) + 2, 0)
        extra = (loop + guard + bytes([0x0E, 0, 1, 0]),)
    else:
        startup += guard
    if case == "write":
        extra = (bytes([0x22, 1, 1, 1, 1, 0]),)
    data = synthetic_room(bytes([1, 0]), (startup + bytes([1, 0]), *extra))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    if case == "incomplete":
        room["candidate_list_complete"] = False
    fixed = [{"bank": 1, "bit": 1, "expected": int(case == "fixed-true")}]
    banks = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())[
        "flag_banks"
    ]
    proof = scenario_item_proofs(data, room, fixed, banks, SCENARIO_EFFECT_POOL)
    generic_offset = next(
        row["offset"]
        for program in room["programs"].values()
        for row in program["commands"]
        if row["kind"] == {"door": "door", "reset": "reset"}.get(case, "interaction")
    )
    assert (generic_offset in proof.unreachable_creator_offsets) is (
        excluded or case in ("door", "reset")
    )
    assert proof.fixed_context_preserved is (
        case not in ("write", "incomplete", "generic-item")
    )
    room["fixed_context_preserved"] = proof.fixed_context_preserved
    fixed_flags = (
        frozenset((row["bank"], row["bit"], row["expected"]) for row in fixed)
        if proof.fixed_context_preserved
        else frozenset()
    )
    required, conditional = collection_presence(
        data,
        room,
        scenario_presence_flags(PRESENCE_FLAGS, fixed, proof.fixed_context_preserved),
        frozenset(item["offset"] for item in room["items"]),
        fixed_flags,
        unreachable_creator_offsets=proof.unreachable_creator_offsets,
    )
    assert conditional == []
    assert required == ([9, 10] if excluded else [10] if case != "incomplete" else [])


@pytest.mark.parametrize("invalid", ["context", "offset", "type"])
def test_creator_lifetime_exclusions_require_source_bound_fixed_context(invalid):
    data = synthetic_room(item_command(20, 15, 9) + bytes([1, 0]))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["fixed_context_preserved"] = invalid != "context"
    offset = room["items"][0]["offset"]
    with pytest.raises(AssertionError):
        collection_presence(
            data,
            room,
            PRESENCE_FLAGS,
            frozenset({offset}),
            frozenset({(1, 1, 0)}) if invalid != "context" else frozenset(),
            unreachable_creator_offsets=(
                {offset} if invalid == "type" else frozenset({offset + 1})
            ),
        )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-01", "01-02"], indirect=True)
def test_generated_creator_lifetime_rewinds_independently_of_conditional_award(
    snapshot,
):
    profile, _, put, read = snapshot
    source = profile.rooms["01-02"]
    assert source["fixed_context_preserved"]
    assert source["scenario_absent_item_ids"] == [116, 249]
    assert {
        row["global_id"]: row["presence"] for row in source["conditional_item_presence"]
    } == {gid: {"kind": "required"} for gid in (111, 113, 114, 115)}
    layout = profile.runtime_layout
    registry = int(layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[layout["item_bank_early"]][0]
    story = profile.flag_banks[4][0]
    award_bank = profile.flag_banks[8][0]
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 2))
    visits = None
    for acquired in (False, True, False, True):
        # Independent pickups stay collected while this acquisition reverses.
        word = sum(0x80000000 >> (gid % 32) for gid in (111, 113, 114))
        put(
            bank + 115 // 32 * 4,
            word | ((0x80000000 >> (115 % 32)) if acquired else 0),
            4,
        )
        put(story, 0x80000000 >> 7, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["01-02"]
        assert record.list_complete
        assert [(item.label, item.state) for item in record.items] == [
            (profile.names["items"]["91"], "taken"),
            (profile.names["items"]["38"], "taken"),
            (profile.names["items"]["20"], "taken" if acquired else "uncollected"),
            ("Event collectible", "unknown"),
        ]
        assert [item.quantity for item in record.items] == [
            1,
            1,
            15,
            ItemQuantityState.Unreconstructed,
        ]
        assert record.completion is (
            RoomCompletion.Unknown if acquired else RoomCompletion.Incomplete
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(1, 2))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh == tracker
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits
    # The direct award has its own sufficient condition and collection flag.
    # Visiting or acquiring the physical pickups cannot make it required.
    put(story, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["01-02"].items[-1].state == "uncollected"
    put(award_bank, 0x80000000 >> 5, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["01-02"].completion is RoomCompletion.Cleared
    put(award_bank, 0, 4)
    put(story, 0x80000000 >> 7, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["01-02"].completion is RoomCompletion.Unknown
