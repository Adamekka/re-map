"""RE2-LIVE-001 / RE2-COLLECT-001: coherent collection and flag rewind.

These tests exercise interpretation contracts; they are not gameplay evidence.
RE2-COLLECT-002 checks known items alongside unresolved slot identities.
RE2-DOOR-001/002/003 record separate runtime evidence for door flag contracts.
RE2-PLAYER-001 supplies measured movement references for heading regressions.
RE2-FLOOR-001 supplies native floor changes within one room source.
"""

import copy
import hashlib
import json
import logging
import math
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from games.runtime_identity import RuntimeSignature
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.player_position import ApproximatePosition, RoomOnlyPosition
from tracker.polling import PollStatus
from ui.map_view import map_state

HEADING_MOVEMENTS = json.loads(
    (ROOT / "tests/fixtures/re2/heading-movements.json").read_text()
)["measurements"]


@pytest.mark.parametrize("keep_unresolved_checks", [False, True])
def test_counter_initialized_items_rewind_after_departure_without_cached_presence(
    snapshot, keep_unresolved_checks
):
    """RE2-COLLECT-012: known items survive inactive pointers and fresh starts."""
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-15"])
    assert source["collection_item_ids"] == [101, 209]
    # Isolate counter presence here; RE2-COLLECT-013 separately tests the
    # conditional proofs through unrelated startup flag writes.
    source["conditional_item_presence"] = []
    # Keep this earlier regression's conflicting identity unresolved; the
    # scenario-selected variant has its own fresh-state/clearance tests below.
    source["scenario_item_variants"] = []
    if not keep_unresolved_checks:
        source["items"] = [
            item for item in source["items"] if item["global_id"] in (101, 209)
        ]
    profile = replace(profile, rooms=profile.rooms | {"00-15": source})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0x15))
    for acquired, counter in [(False, 0), (True, 51), (False, 0), (True, 51)]:
        put(0x800CC9F4, 0x04000000 if acquired else 0, 4)
        put(0x800CCA00, 0x00004000 if acquired else 0, 4)
        put(0x800CC926, counter, 2)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-15"]
        known = [
            item
            for item in record.items
            if item.label
            in (profile.names["items"]["20"], profile.names["items"]["80"])
        ]
        assert len(known) == 2
        assert all(
            item.state == ("taken" if acquired else "uncollected") for item in known
        )
        assert record.completion is (
            RoomCompletion.Incomplete
            if not acquired
            else RoomCompletion.Unknown
            if keep_unresolved_checks
            else RoomCompletion.Cleared
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(0, 0x15))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["00-15"].items == record.items
        assert fresh.rooms["00-15"].completion is record.completion
        assert set(tracker.rooms) == {"00-01", "00-15"}


@pytest.mark.parametrize(
    "source,gid", [("00-06", 8), ("00-0c", 32), ("00-15", 40), ("00-15", 104)]
)
def test_flag_guarded_pickups_rebuild_after_departure_and_acquisition_reversal(
    snapshot, source, gid
):
    """RE2-COLLECT-013: reconstruct the conditions compatible with this profile."""
    profile, _, put, read = snapshot
    room = RoomId(int(source[:2], 16), int(source[3:], 16))
    item_types = {
        item["type"]
        for item in profile.rooms[source]["items"]
        if item["global_id"] == gid
    }
    assert len(item_types) == 1
    label = profile.names["items"][str(next(iter(item_types)))]
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    tracker.mark_current(room)
    for acquired in (False, True, False, True):
        put(
            0x800CC9E8 + gid // 32 * 4, (0x80000000 >> (gid % 32)) if acquired else 0, 4
        )
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms[source]
        item = next(item for item in record.items if item.label == label)
        assert item.state == ("taken" if acquired else "uncollected")
        if not acquired:
            assert record.completion is RoomCompletion.Incomplete
        fresh = Tracker()
        fresh.mark_current(room)
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms[source].items == record.items
        assert fresh.rooms[source].completion is record.completion


@pytest.mark.parametrize("acquired", [False, True])
@pytest.mark.parametrize("second_bit", [False, True])
def test_opposite_scenario_condition_cannot_publish_or_record_visits(
    snapshot, acquired, second_bit
):
    """RE2-COLLECT-013: the fifth proof cannot authorize another scenario."""
    from games.re2.event_presence import presence_matches

    profile, _, put, read = snapshot
    rule = profile.rooms["00-10"]["conditional_item_presence"][0]
    assert rule["global_id"] == 17
    assert rule["presence"]["any_of"] == [
        [{"bank": 1, "bit": 1, "expected": 1}, {"bank": 1, "bit": 6, "expected": 0}]
    ]
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0x10))
    put(0x800CC9E8, (0x80000000 >> 17) if acquired else 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    item_type = next(
        item["type"]
        for item in profile.rooms["00-10"]["items"]
        if item["global_id"] == 17
    )
    item = next(
        item
        for item in tracker.rooms["00-10"].items
        if item.label == profile.names["items"][str(item_type)]
    )
    assert item.state == ("taken" if acquired else "unknown")
    before = copy.deepcopy(tracker)
    # A true compound predicate is outside the pinned Leon A scenario. Never
    # weaken that gate just to exercise the generated alternative's happy path.
    put(0x800C7D04, 0x40000000 | (0x02000000 if second_bit else 0), 4)
    assert presence_matches(
        rule["presence"],
        lambda bank, bit: {(1, 1): True, (1, 6): second_bit}[bank, bit],
    ) is (not second_bit)
    assert poll_re2(profile, tracker, read).status is PollStatus.WrongGame
    assert tracker == before


@pytest.mark.parametrize("movement", HEADING_MOVEMENTS, ids=lambda row: row["after"])
def test_heading_agrees_with_native_forward_displacement(snapshot, movement):
    profile, _, put, read = snapshot
    put(0x800C7D9A, movement["yaw"], 2)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.player_heading == movement["published_heading"]
    # Native forward displacement is an independent reference for the sign and
    # offset; a two-degree bound covers the observed native motion differences.
    motion_heading = math.degrees(math.atan2(movement["dx"], movement["dz"])) % 360
    assert abs((tracker.player_heading - motion_heading + 180) % 360 - 180) < 2


def test_heading_rewinds_from_fresh_yaw_without_resetting_visits(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0))
    for movement in [HEADING_MOVEMENTS[index] for index in (0, 3, 0, 3)]:
        put(0x800C7D9A, movement["yaw"], 2)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        assert map_state(tracker)["player_heading"] == movement["published_heading"]
        assert set(tracker.rooms) == {"00-00", "00-01"}


def test_position_and_heading_share_the_initial_moving_snapshot(snapshot):
    profile, _, put, read = snapshot
    put(0x800C7D5C, -16523 & 0xFFFFFFFF, 4)
    put(0x800C7D64, -13300 & 0xFFFFFFFF, 4)
    put(0x800C7D9A, 779, 2)

    def moving_read(address, width):
        result = read(address, width)
        if address == 0x800C7CE0:
            put(0x800C7D5C, -16600 & 0xFFFFFFFF, 4)
            put(0x800C7D64, -14000 & 0xFFFFFFFF, 4)
            put(0x800C7D9A, 1739, 2)
        return result

    tracker = Tracker()
    assert poll_re2(profile, tracker, moving_read).status is PollStatus.Display
    assert isinstance(tracker.player_position, ApproximatePosition)
    assert (tracker.player_position.x, tracker.player_position.y) == pytest.approx(
        (96.50444444444445, 79.33333333333334)
    )
    assert tracker.player_heading == 158.466796875
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.player_position != ApproximatePosition(
        96.50444444444445, 79.33333333333334
    )
    assert tracker.player_heading == 242.841796875


def test_unplaced_pose_replaces_the_previous_position(snapshot):
    profile, _, put, read = snapshot
    put(0x800C7D5C, -16523 & 0xFFFFFFFF, 4)
    put(0x800C7D64, -13300 & 0xFFFFFFFF, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert isinstance(tracker.player_position, ApproximatePosition)
    put(0x800C7D5C, 0, 4)
    put(0x800C7D64, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert isinstance(tracker.player_position, RoomOnlyPosition)
    assert map_state(tracker)["player_position"]["kind"] == "room"


def test_complete_room_change_during_pose_read_cannot_publish(snapshot):
    profile, _, put, read = snapshot
    put(0x800C7D5C, -16523 & 0xFFFFFFFF, 4)
    put(0x800C7D64, -13300 & 0xFFFFFFFF, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changed_room(address, width):
        result = read(address, width)
        if address == 0x800C7CE0:
            put(profile.room_address, 0, 2)
        return result

    result = poll_re2(profile, tracker, changed_room)
    assert result.status is PollStatus.Retry
    assert "Player room changed during pose read" in result.text
    assert tracker == before


def test_floor_change_during_pose_read_cannot_publish(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changed_floor(address, width):
        result = read(address, width)
        if address == 0x800C7CE0:
            put(0x800C7E2A, 1, 1)
        return result

    result = poll_re2(profile, tracker, changed_floor)
    assert result.status is PollStatus.Retry
    assert "Game state changed during read" in result.text
    assert tracker == before


@pytest.mark.parametrize("short", [True, False])
def test_failed_pose_snapshot_preserves_the_previous_publication(snapshot, short):
    profile, _, put, read = snapshot
    put(0x800C7D5C, -16523 & 0xFFFFFFFF, 4)
    put(0x800C7D64, -13300 & 0xFFFFFFFF, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def failed_read(address, width):
        if address == 0x800C7CE0:
            return MemRead(True, b"x") if short else MemRead(False, b"", "disconnected")
        return read(address, width)

    assert poll_re2(profile, tracker, failed_read).status is PollStatus.ReadFailure
    assert tracker == before


@pytest.fixture(scope="module")
def profile():
    return Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")


@pytest.fixture(params=["00-01"])
def snapshot(request, profile):
    source = request.param
    room = copy.deepcopy(profile.rooms[source])
    # These generic reader cases deliberately model an unproven source. The
    # actual scripted reward's generated proof is checked separately below.
    room["collection_item_ids"] = []
    for proof in room["proofs"]:
        proof["sha256"] = hashlib.sha256(bytes(proof["width"])).hexdigest()
    profile = replace(
        profile,
        rooms={**profile.rooms, source: room},
        runtime_signature=RuntimeSignature(
            (0x80010000,), 32, hashlib.sha256(bytes(32)).hexdigest()
        ),
    )
    ram = bytearray(0x200000)

    def put(address, value, width):
        ram[address & 0x1FFFFF : (address & 0x1FFFFF) + width] = value.to_bytes(
            width, "little"
        )

    put(0x800C7CE4, 0x40000000 | profile.runtime_layout["system_mode_value"], 4)
    put(0x800C7D24, 1, 4)
    stage, number = source.split("-")
    put(profile.stage_address, int(stage), 2)
    put(profile.room_address, int(number, 16), 2)
    put(0x800C6494, 0x80100000, 4)
    for index, offset in enumerate(room["section_offsets"]):
        put(0x80100008 + index * 4, 0x80100000 + offset if offset else 0, 4)
    for kind, definitions in ((2, room["items"]), (1, room["doors"])):
        for definition in definitions:
            pointer = 0x80100000 + definition["offset"] + 2
            put(0x800C66C8 + definition["slot"] * 4, pointer, 4)
            put(pointer, kind, 1)
            operand = 20 if definition["four_point"] else 12
            if kind == 2:
                for index, name in enumerate(("type", "amount", "global_id")):
                    put(pointer + operand + index * 2, definition[name], 2)
            else:
                for index, name in (
                    (8, "stage"),
                    (9, "room"),
                    (15, "lock_id"),
                    (16, "lock_type"),
                ):
                    put(pointer + operand + index, definition[name], 1)

    def read(address, width):
        return MemRead(
            True, bytes(ram[address & 0x1FFFFF : (address & 0x1FFFFF) + width])
        )

    return profile, ram, put, read


def test_pickups_rewind_without_erasing_visits(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Incomplete
    assert [item.label for item in tracker.rooms["00-01"].items].count(
        "Handgun ammo"
    ) == 2
    region = tracker.current_region
    for definition in profile.rooms["00-01"]["items"]:
        put(0x800C66C8 + definition["slot"] * 4, 0, 4)
    put(0x800CC9E8, 0xC0010000, 4)  # IDs 0, 1 and 15 use high bits in each LE word.
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Cleared
    assert all(item.state == "taken" for item in tracker.rooms["00-01"].items)
    put(0x800CC9E8, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Unknown
    assert tracker.region_visits == {region: "00-01"}
    assert map_state(tracker)["current_detail"]["items"][0]["state"] == "unknown"


def test_disabled_candidates_do_not_establish_presence_or_clearance(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    for definition in profile.rooms["00-01"]["items"]:
        put(0x80100000 + definition["offset"] + 2, 0, 1)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Unknown
    assert all(item.state == "unknown" for item in tracker.rooms["00-01"].items)
    put(0x800C66C8 + 11 * 4, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Unknown


def test_generated_scripted_reward_tracks_activation_collection_and_rewind(snapshot):
    profile, _, put, read = snapshot
    room = copy.deepcopy(profile.rooms["00-01"])
    room["collection_item_ids"] = Re2Profile.load(
        ROOT / "profiles/re2_leon_a_slus00421.json"
    ).rooms["00-01"]["collection_item_ids"]
    assert room["collection_item_ids"] == [0, 1, 15]
    profile = replace(profile, rooms={**profile.rooms, "00-01": room})
    reward = next(item for item in room["items"] if item["global_id"] == 15)
    pointer = 0x80100000 + reward["offset"] + 2
    tracker = Tracker()
    for kind, flags, expected in (
        (0, 0xC0000000, "uncollected"),
        (2, 0xC0000000, "available"),
        (0, 0xC0010000, "taken"),
        (0, 0xC0000000, "uncollected"),
    ):
        for item in room["items"]:
            put(0x80100000 + item["offset"] + 2, 0, 1)
        put(pointer, kind, 1)
        put(pointer + 14, 4, 2)
        put(0x800CC9E8, flags, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-01"]
        detail = next(item for item in record.items if item.label == "Shotgun")
        assert detail.state == expected
        assert detail.quantity == (
            4 if kind == 2 else ItemQuantityState.Unreconstructed
        )
        assert record.completion is (
            RoomCompletion.Cleared if expected == "taken" else RoomCompletion.Incomplete
        )


@pytest.mark.parametrize("snapshot", ["01-08", "00-0f"], indirect=True)
@pytest.mark.parametrize("departed", [False, True])
@pytest.mark.parametrize("alternatives", [False, True])
def test_native_pickup_quantities_reconstruct_from_fresh_mode_and_collection_flags(
    snapshot, departed, alternatives
):
    # RE2-QUANTITY-001: the same native rule applies to both observed creators,
    # including before prompt entry, after departure and with no cached amount.
    profile, _, put, read = snapshot
    source_key = str(profile.read_current_room(read).room)
    source = copy.deepcopy(profile.rooms[source_key])
    item = next(item for item in source["items"] if item["type"] == 30)
    assert item["amount"] == 3
    item["amounts"] = [3, 4] if alternatives else [3]
    source.update(
        items=[item],
        collection_item_ids=[item["global_id"]],
        conditional_item_presence=[],
        scenario_absent_item_ids=[],
        event_awards=[],
        candidate_list_complete=True,
    )
    rooms = {**profile.rooms, source_key: source}
    if departed:
        # Reuse the synthetic source binding to exercise a departed room
        # without claiming another real room shares these source bytes.
        rooms[f"{source['stage']:02x}-00"] = {**source, "room": 0, "items": []}
        put(profile.room_address, 0, 2)
    profile = replace(profile, rooms=rooms)
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    pointer = 0x80100000 + item["offset"] + 2
    put(pointer + 14, 4 if alternatives else 3, 2)
    tracker = Tracker()
    tracker.mark_current(RoomId(source["stage"], source["room"]))
    for mode in (0, 0x40, 0, 0x40):
        put(0x800C7CE4, 0x40000000 | mode, 4)
        for active, acquired in ((True, False), (False, True), (False, False)):
            put(
                0x800C66C8 + item["slot"] * 4,
                pointer if active and not departed else 0,
                4,
            )
            flag_address = 0x800CC9E8 + item["global_id"] // 32 * 4
            put(
                flag_address,
                0x80000000 >> (item["global_id"] % 32) if acquired else 0,
                4,
            )
            fresh = Tracker()
            fresh.mark_current(RoomId(source["stage"], source["room"]))
            for observation in (tracker, fresh):
                if not mode:
                    # RE2-COLLECT-011 pins the observed native setup. The
                    # quantity handler's flag-clear branch remains offline-only.
                    before = copy.deepcopy(observation)
                    assert (
                        poll_re2(profile, observation, read).status
                        is PollStatus.WrongGame
                    )
                    assert observation == before
                    continue
                assert poll_re2(profile, observation, read).status is PollStatus.Display
                record = observation.rooms[source_key]
                detail = record.items[0]
                assert detail.state == (
                    "taken"
                    if acquired
                    else "available"
                    if active and not departed
                    else "uncollected"
                )
                assert detail.quantity == 2
                assert record.completion is (
                    RoomCompletion.Cleared if acquired else RoomCompletion.Incomplete
                )


@pytest.mark.parametrize("short", [False, True])
def test_pickup_quantity_mode_coherence_rejects_torn_or_short_reads(snapshot, short):
    profile, _, _, read = snapshot
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changing_read(address, width):
        if address == 0x800C7CE4:
            return (
                MemRead(True, b"x")
                if short
                else MemRead(True, (0x40000000).to_bytes(4, "little"))
            )
        return read(address, width)

    result = poll_re2(profile, tracker, changing_read)
    assert result.status is (PollStatus.ReadFailure if short else PollStatus.Retry)
    assert tracker == before


def test_pickup_quantity_override_does_not_change_event_delivery_amounts(snapshot):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-01"])
    award = copy.deepcopy(profile.rooms["01-02"]["event_awards"][0])
    award.update(item_type=30, amount=3)
    source["event_awards"] = [award]
    profile = replace(profile, rooms={**profile.rooms, "00-01": source})
    put(0x800C7CE4, 0x40000040, 4)
    put(0x800CC9E8, 0x04000000, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    detail = tracker.rooms["00-01"].items[-1]
    assert detail.state == "taken" and detail.quantity == 3


@pytest.mark.parametrize("already_observed", [False, True])
def test_mode_mismatch_cannot_publish_or_erase_prior_exploration(
    snapshot, already_observed
):
    profile, _, put, read = snapshot
    tracker = Tracker()
    if already_observed:
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    put(0x800C7CE4, 0x40000000, 4)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.WrongGame
    assert (
        result.text
        == "Unsupported RE2 game settings. Load a supported Leon A savestate."
    )
    assert tracker == before
    put(0x800C7CE4, 0x40000040, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert set(tracker.rooms) == {"00-01"}


def test_mode_coherence_is_independent_of_the_quantity_override(snapshot):
    profile, _, _, read = snapshot
    # Keep the quantity predicate unchanged while only the required mode bit
    # changes at the final read, so its old coherence mask cannot hide a tear.
    profile = replace(
        profile,
        runtime_layout={
            **profile.runtime_layout,
            "pickup_quantity_override": {
                **profile.runtime_layout["pickup_quantity_override"],
                "system_mask": 0x20,
            },
        },
    )
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changing(address, width):
        if address == 0x800C7CE4:
            return MemRead(True, (0x40000000).to_bytes(4, "little"))
        return read(address, width)

    assert poll_re2(profile, tracker, changing).status is PollStatus.Retry
    assert tracker == before


@pytest.mark.parametrize("departed", [False, True])
def test_source_established_items_remain_required_until_fresh_collection(
    snapshot, departed
):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-01"])
    # This synthetic source has a complete presence proof. The real source's
    # unsupported startup scripts are covered by the metadata regressions.
    source["collection_item_ids"] = [0, 1, 15]
    rooms = {**profile.rooms, "00-01": source}
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 1))
    if departed:
        rooms["00-00"] = {**source, "stage": 0, "room": 0}
        put(profile.room_address, 0, 2)
    profile = replace(profile, rooms=rooms)
    for definition in source["items"]:
        # Model a reset that destroys mutable item operands, then a missing
        # registry. Neither changes the source-established acquisition identity.
        pointer = 0x80100000 + definition["offset"] + 2
        put(pointer, 0, 1)
        put(pointer + 12, 0, 6)
        put(0x800C66C8 + definition["slot"] * 4, 0, 4)
    visits = None
    for flags, expected in (
        (0, RoomCompletion.Incomplete),
        (0xC0010000, RoomCompletion.Cleared),
        (0, RoomCompletion.Incomplete),
    ):
        put(0x800CC9E8, flags, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-01"]
        assert record.completion is expected
        assert record.total_items == 3
        assert record.collected_items == (3 if flags else 0)
        assert {item.state for item in record.items} == (
            {"taken"} if flags else {"uncollected"}
        )
        if visits is None:
            visits = dict(tracker.region_visits)
        assert tracker.region_visits == visits
    # A fresh tracker reconstructs collection from metadata and flags, without
    # retaining an earlier item list, clearance verdict or observation cache.
    fresh = Tracker()
    fresh.mark_current(RoomId(0, 1))
    assert poll_re2(profile, fresh, read).status is PollStatus.Display
    assert fresh.rooms["00-01"].completion is RoomCompletion.Incomplete


def test_known_remaining_item_wins_over_unresolved_coverage(snapshot):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-01"])
    source["collection_item_ids"] = [0]
    source["candidate_list_complete"] = False
    profile = replace(profile, rooms={**profile.rooms, "00-01": source})
    for definition in source["items"]:
        put(0x800C66C8 + definition["slot"] * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    record = tracker.rooms["00-01"]
    assert record.completion is RoomCompletion.Incomplete
    assert not record.list_complete
    assert {item.state for item in record.items} == {"uncollected", "unknown"}
    assert record.reason


def test_ambiguous_item_identity_stays_unknown_even_with_acquisition_flag(snapshot):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-01"])
    source["items"].append({**source["items"][0], "type": 20, "offset": 100})
    profile = replace(profile, rooms={**profile.rooms, "00-01": source})
    for definition in source["items"]:
        put(0x800C66C8 + definition["slot"] * 4, 0, 4)
    put(0x800CC9E8, 0xC0010000, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Unknown
    assert any(item.state == "unknown" for item in tracker.rooms["00-01"].items)


@pytest.mark.parametrize("departed", [False, True])
@pytest.mark.parametrize("coverage", [False, True])
def test_event_collection_rewinds_without_inventory_or_activation(
    snapshot, departed, coverage
):
    profile, _, put, read = snapshot
    award = profile.rooms["01-02"]["event_awards"][0]
    source = "01-02" if departed else "00-01"
    room = {
        **profile.rooms[source],
        "items": [],
        "collection_item_ids": [],
        "event_awards": [award],
        "candidate_list_complete": coverage,
    }
    profile = replace(profile, rooms={**profile.rooms, source: room})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    if departed:
        tracker.mark_current(RoomId(1, 2))
    visits = None
    for acquired in (False, True, False, True):
        put(0x800CC9E8, 0x04000000 if acquired else 0, 4)
        # Activation/completion and inventory possession are separate facts.
        put(0x800CC980, 0x01000000 if not acquired else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms[source]
        assert record.completion is (
            RoomCompletion.Cleared if acquired and coverage else RoomCompletion.Unknown
        )
        assert record.total_items == 1
        assert record.collected_items == int(acquired)
        assert record.items[0].state == ("taken" if acquired else "unknown")
        assert record.items[0].label == (
            profile.names["items"]["53"] if acquired else "Event collectible"
        )
        assert record.items[0].quantity == (
            1 if acquired else ItemQuantityState.Unreconstructed
        )
        if visits is None:
            visits = dict(tracker.region_visits)
        assert tracker.region_visits == visits
    fresh = Tracker()
    if departed:
        fresh.mark_current(RoomId(1, 2))
    assert poll_re2(profile, fresh, read).status is PollStatus.Display
    assert fresh.rooms[source].collected_items == 1


def test_unbound_event_awards_remain_separate_unresolved_checks(snapshot):
    profile, _, put, read = snapshot
    award = profile.rooms["01-02"]["event_awards"][0]
    source = {
        **profile.rooms["00-01"],
        "items": [],
        "collection_item_ids": [],
        "event_awards": [
            award,
            {
                **award,
                "collection": {"kind": "unresolved"},
                "presence": {"kind": "unresolved"},
            },
        ],
    }
    profile = replace(profile, rooms={**profile.rooms, "00-01": source})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    put(0x800CC9E8, 0xFFFFFFFF, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    record = tracker.rooms["00-01"]
    assert record.completion is RoomCompletion.Unknown
    assert [item.state for item in record.items] == ["taken", "unknown"]
    assert record.total_items == 2 and record.collected_items == 1


@pytest.mark.parametrize("failure", ["changed", "short"])
def test_event_flag_checks_are_part_of_final_snapshot_coherence(snapshot, failure):
    profile, _, put, read = snapshot
    award = copy.deepcopy(profile.rooms["01-02"]["event_awards"][0])
    # A separate word makes this check depend on the event reader rather than
    # an ordinary pickup that already happens to consume the same word.
    award["collection"]["bit"] = 40
    room = {**profile.rooms["00-01"], "event_awards": [award]}
    profile = replace(profile, rooms={**profile.rooms, "00-01": room})
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changed(address, width):
        if address == 0x800CC9EC:
            if failure == "short":
                return MemRead(True, b"\0")
            put(address, 0x00800000, 4)
        return read(address, width)

    result = poll_re2(profile, tracker, changed)
    assert result.status is (
        PollStatus.Retry if failure == "changed" else PollStatus.ReadFailure
    )
    assert tracker == before


@pytest.mark.parametrize("departed", [False, True])
def test_unrelated_proven_items_survive_ambiguity_collection_and_rewind(
    snapshot, departed
):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-01"])
    # Synthetic source: two mandatory identities and one conflicting identity.
    # Decoder regressions separately establish the slot-local presence proof.
    source["items"].append({**source["items"][0], "type": 20, "offset": 100})
    source["collection_item_ids"] = [0, 1]
    rooms = {**profile.rooms, "00-01": source}
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 1))
    if departed:
        rooms["00-00"] = {**source, "stage": 0, "room": 0}
        put(profile.room_address, 0, 2)
    profile = replace(profile, rooms=rooms)
    for definition in source["items"]:
        put(0x800C66C8 + definition["slot"] * 4, 0, 4)
    visits = None
    for flags, expected in (
        (0, RoomCompletion.Incomplete),
        (0xC0010000, RoomCompletion.Unknown),
        (0, RoomCompletion.Incomplete),
    ):
        put(0x800CC9E8, flags, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-01"]
        assert record.completion is expected
        assert record.collected_items == (2 if flags else 0)
        states = [item.state for item in record.items]
        assert states.count("unknown") == 1
        assert states.count("taken" if flags else "uncollected") == 2
        assert record.reason
        if visits is None:
            visits = dict(tracker.region_visits)
        assert tracker.region_visits == visits
    fresh = Tracker()
    fresh.mark_current(RoomId(0, 1))
    assert poll_re2(profile, fresh, read).status is PollStatus.Display
    assert fresh.rooms["00-01"].completion is RoomCompletion.Incomplete


@pytest.mark.parametrize(
    ("address", "value", "status"),
    [
        (0x800C7CE4, 0, PollStatus.NonGameplay),
        (0x800C7CE4, 0x40002000, PollStatus.NonGameplay),
        (0x800C7CE4, 0x42000000, PollStatus.Retry),
        (0x800C7D04, 0x80000000, PollStatus.WrongGame),
    ],
)
def test_non_gameplay_and_other_scenarios_never_reveal_rooms(
    snapshot, address, value, status
):
    profile, _, put, read = snapshot
    put(address, value, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is status
    assert tracker == Tracker()


def test_source_mismatch_and_invalid_registry_do_not_mutate_history(snapshot):
    profile, _, put, read = snapshot
    put(0x800C6494, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Retry
    assert tracker == Tracker()
    put(0x800C6494, 0x80100000, 4)
    put(0x800C66C8, 0x80000004, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Retry
    assert tracker == Tracker()


def test_short_read_and_flag_change_withhold_entire_snapshot(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    assert (
        poll_re2(profile, tracker, lambda address, width: MemRead(True, b"")).status
        is PollStatus.ReadFailure
    )

    def change(address, width):
        if address == 0x800CC9E8:
            put(address, 0x80000000, 4)
        return read(address, width)

    assert poll_re2(profile, tracker, change).status is PollStatus.Retry
    assert tracker == Tracker()


def test_key_flags_rewind_and_doors_keep_source_id(snapshot):
    profile, _, put, read = snapshot
    definition = profile.rooms["00-01"]["doors"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    put(pointer + 27, 0x82, 1)
    put(pointer + 28, 89, 1)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    door = next(door for door in tracker.doors if door.target == RoomId(0, 0))
    assert (door.state, door.key_label, door.observation_id) == (
        "LOCKED",
        "Spade Key",
        "00-01:6050",
    )
    put(0x800CCB60, 0x20000000, 4)
    poll_re2(profile, tracker, read)
    assert tracker.doors[0].state == "OPEN"
    assert tracker.doors[0].key_label == ""
    put(0x800CCB60, 0, 4)
    poll_re2(profile, tracker, read)
    assert tracker.doors[0].state == "LOCKED"
    assert tracker.doors[0].key_label == "Spade Key"


def test_native_map_contexts_select_one_region_without_revealing_it(profile):
    for room in profile.rooms:
        rows = profile.map_layout.locations[room]
        for row in rows:
            values = {
                address: expected ^ (mask if negate else 0)
                for address, mask, expected, negate in row["conditions"]
            }
            assert profile.map_layout.select(
                room,
                row["floor_min"],
                lambda address, width, values=values: values[address],
            ) == (row["area"], row["region"])
    assert Tracker().region_visits == {}


@pytest.mark.parametrize("snapshot", ["00-16"], indirect=True)
def test_native_floor_changes_and_restores_keep_both_region_visits(snapshot):
    profile, _, put, read = snapshot
    references = json.loads(
        (ROOT / "tests/fixtures/re2/floor-transitions.json").read_text()
    )
    assert references["profile_id"] == profile.profile_id
    assert references["research_id"] == "RE2-FLOOR-001"
    tracker = Tracker()
    explored = {}
    for observation in references["observations"]:
        assert observation["room"] == [0, 22]
        put(0x800C7E2A, observation["floor"], 1)
        for offset, coordinate in enumerate(observation["world_position"]):
            put(0x800C7D5C + offset * 4, coordinate & 0xFFFFFFFF, 4)
        put(0x800C7D9A, observation["yaw"], 2)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        area, region = observation["area"], observation["region"]
        explored[f"{area}:{region}"] = "00-16"
        assert tracker.current_region == f"{area}:{region}"
        assert tracker.region_visits == explored
        assert set(tracker.rooms) == {"00-16"}
        state = map_state(tracker)
        assert (state["area"], state["map_region"]) == (area, region)
        assert {
            f"{area_id}:{visit['id']}": visit["room"]
            for area_id, visits in state["explored_areas"].items()
            for visit in visits
        } == explored
    assert len(explored) == 2


def test_shared_camera_positions_do_not_bind_the_wrong_room(snapshot):
    profile, _, put, read = snapshot
    put(0x80100008, 0x80100001, 4)
    tracker = Tracker()
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert "section layout" in result.text
    assert tracker == Tracker()


@pytest.mark.parametrize("index", range(2, 23))
def test_sound_relocation_does_not_relax_other_sections(snapshot, index):
    profile, _, put, read = snapshot
    expected = profile.rooms["00-01"]["section_offsets"][index]
    put(0x80100008 + index * 4, 0x80100000 + expected + 4, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Retry
    assert tracker == Tracker()


@pytest.mark.parametrize(
    "fault",
    [
        "none",
        "spacing",
        "unaligned",
        "null",
        "both-null",
        "below-room",
        "bounds",
        "edt",
        "vh",
        "camera",
        "torn",
        "edt-torn",
        "vh-torn",
        "short",
    ],
)
def test_paired_sound_relocation_requires_bounded_coherent_source_proofs(
    snapshot, fault
):
    """RE2-SOURCE-001: no native RAM or sound assets are embedded in fixtures."""
    profile, _, put, read = snapshot
    room = copy.deepcopy(profile.rooms["00-01"])
    for proof in room["sound_proofs"]:
        proof["sha256"] = hashlib.sha256(bytes(proof["width"])).hexdigest()
    profile = replace(profile, rooms={**profile.rooms, "00-01": room})
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    # An explicit test location models only the moved sound bytes. Native
    # pointer values and content hashes are checked in the capture replay.
    start = 0x80100000 + room["size"] - 256
    start &= ~3
    if fault == "unaligned":
        start += 1
    if fault == "bounds":
        start = 0x80200000
    if fault == "below-room":
        start = 0x80100060
    put(0x80100008, start, 4)
    put(0x8010000C, start + 192, 4)
    if fault == "spacing":
        put(0x8010000C, start + 196, 4)
    if fault == "null":
        put(0x80100008, 0, 4)
    if fault == "both-null":
        put(0x80100008, 0, 4)
        put(0x8010000C, 0, 4)
    if fault in ("edt", "vh"):
        put(start + (0 if fault == "edt" else 192), 1, 1)
    if fault == "camera":
        put(0x80100000 + room["proofs"][0]["offset"], 1, 1)
    header_reads = 0
    sound_reads = {}

    def changed_read(address, width):
        nonlocal header_reads
        if address == 0x80100008 and width == 92:
            header_reads += 1
            if fault == "torn" and header_reads == 2:
                packet = bytearray(read(address, width).data)
                packet[0] ^= 4
                return MemRead(True, bytes(packet))
        if fault == "short" and address == start:
            return MemRead(True, bytes(width - 1))
        if address in (start, start + 192):
            sound_reads[address] = sound_reads.get(address, 0) + 1
            if (
                fault == ("edt-torn" if address == start else "vh-torn")
                and sound_reads[address] == 2
            ):
                packet = bytearray(read(address, width).data)
                packet[0] ^= 1
                return MemRead(True, bytes(packet))
        return read(address, width)

    result = poll_re2(profile, tracker, changed_read)
    if fault == "none":
        assert result.status is PollStatus.Display
        assert tracker == before
        # Restoring the original header must re-read item flags, rather than
        # carrying the relocated publication forward after a savestate load.
        for index, offset in enumerate(room["section_offsets"][:2]):
            put(0x80100008 + index * 4, 0x80100000 + offset, 4)
        for definition in room["items"]:
            put(0x800C66C8 + definition["slot"] * 4, 0, 4)
        put(0x800CC9E8, 0xC0010000, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        assert tracker.rooms["00-01"].items != before.rooms["00-01"].items
    else:
        assert result.status is (
            PollStatus.ReadFailure if fault == "short" else PollStatus.Retry
        )
        assert tracker == before


def test_disabled_door_does_not_become_open_from_a_key_flag(snapshot):
    profile, _, put, read = snapshot
    definition = profile.rooms["00-01"]["doors"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    put(pointer + 27, 0x82, 1)
    put(pointer + 28, 89, 1)
    put(0x80100000 + definition["offset"] + 2, 0, 1)
    put(0x800CCB60, 0xFFFFFFFF, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.doors[0].state == "BLOCKED"
    assert tracker.doors[0].key_label == ""


@pytest.mark.parametrize(
    "name,filename",
    [
        ("re1_directors_cut_slus00551", "visit-history.json"),
        ("re2_leon_a_slus00421", "re2-leon-a.json"),
    ],
)
def test_cli_defaults_isolate_game_histories(monkeypatch, tmp_path, name, filename):
    sys.path.insert(0, str(ROOT / "tools"))
    import track

    from tracker.visit_history import HistoryError

    paths = []

    def history(path, identity, regions, new_playthrough):
        paths.append(path)
        raise HistoryError("test stop before connecting")

    monkeypatch.setattr(track, "VisitHistory", history)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--profile",
            str(ROOT / "profiles" / (name + ".json")),
            "--log-file",
            str(tmp_path / "tracker.log"),
            "--once",
        ],
    )
    assert track.main() == 1
    assert paths == [ROOT / ".local" / filename]


def test_cli_restarts_rebuild_item_and_door_state(snapshot, monkeypatch, tmp_path):
    """RE2-SESSION-001: synthetic CLI regression, separate from native evidence."""
    sys.path.insert(0, str(ROOT / "tools"))
    import track

    profile, _, put, read = snapshot
    definition = profile.rooms["00-01"]["doors"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    put(pointer + 27, 0x82, 1)
    put(pointer + 28, 89, 1)

    class LocalReader:
        connected = True  # The synthetic reader owns memory, not a connection.
        read_memory = staticmethod(read)

        def connect(self):
            return ""

        def resume(self):
            return ""

        def close(self):
            pass  # Test memory has no external resource to release.

    publications = []
    poll = track.poll_once

    def observe_poll(profile, tracker, read_memory):
        result = poll(profile, tracker, read_memory)
        if result.status is PollStatus.Display:
            publications.append(map_state(tracker))
        return result

    monkeypatch.setattr(track, "poll_once", observe_poll)
    monkeypatch.setattr(track, "DuckStationGdb", lambda *args: LocalReader())
    monkeypatch.setattr(track.Re2Profile, "load", lambda path: profile)
    path = tmp_path / "agent-history.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "track.py",
            "--profile",
            str(ROOT / "profiles/re2_leon_a_slus00421.json"),
            "--once",
            "--history-file",
            str(path),
            "--log-file",
            str(tmp_path / "tracker.log"),
        ],
    )
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    root.handlers = []
    histories = []
    try:
        for acquired in (False, True, False, True):
            put(0x800CC9E8, 0xC0010000 if acquired else 0, 4)
            put(0x800CCB60, 0x20000000 if acquired else 0, 4)
            for item in profile.rooms["00-01"]["items"]:
                # Model collected items with missing descriptors. Keeping an
                # active item with its acquisition bit set models a torn read.
                put(
                    0x800C66C8 + item["slot"] * 4,
                    0 if acquired else 0x80100000 + item["offset"] + 2,
                    4,
                )
            assert track.main() == 0
            histories.append(json.loads(path.read_text()))
            state = publications[-1]
            assert state["current"] == "00-01"
            assert state["current_detail"]["state"] == (
                "CLEARED" if acquired else "INCOMPLETE"
            )
            assert {item["state"] for item in state["current_detail"]["items"]} == {
                "taken" if acquired else "available"
            }
            door = next(
                door
                for door in state["doors"]
                if door["observation_id"] == "00-01:6050"
            )
            assert (door["state"], door["key_label"]) == (
                ("OPEN", "") if acquired else ("LOCKED", "Spade Key")
            )
    finally:
        for handler in root.handlers:
            handler.close()
        root.handlers = handlers
        root.setLevel(level)
    assert len(publications) == 4
    assert all(history == histories[0] for history in histories)
    assert histories[0]["rooms"] == ["00-01"]
    assert histories[0]["regions"] == {"re2-00:01": "00-01"}
    assert set(histories[0]) == {
        "schema",
        "identity",
        "playthrough_id",
        "rooms",
        "regions",
    }


def test_unbound_live_door_withholds_door_coverage(snapshot):
    profile, _, put, read = snapshot
    put(0x800C66C8 + 31 * 4, 0x80100300, 4)
    put(0x80100300, 1, 1)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert not tracker.rooms["00-01"].doors_complete
    assert tracker.rooms["00-01"].door_reason


def test_foreign_room_in_history_reports_a_recoverable_failure(snapshot):
    profile, _, _, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(255, 255))
    assert poll_re2(profile, tracker, read).status is PollStatus.ReadFailure
    assert set(tracker.rooms) == {"255-ff"}


def test_departed_door_retains_fresh_unlock_knowledge_without_claiming_access(snapshot):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-00"])
    source["doors"][0].update(lock_id=0x82, lock_type=89)
    profile = replace(profile, rooms={**profile.rooms, "00-00": source})
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0))
    put(0x800CCB60, 0x20000000, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    door = next(door for door in tracker.doors if door.source == RoomId(0, 0))
    assert door.state == "UNCHECKED"
    assert door.label == "Unlocked; access unconfirmed"
    assert door.key_label == ""
    put(0x800CCB60, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    door = next(door for door in tracker.doors if door.source == RoomId(0, 0))
    assert door.label == "Door conditions unresolved"
    assert door.key_label == "Spade Key"


@pytest.mark.parametrize("departed", [False, True])
@pytest.mark.parametrize("coverage", [False, True])
def test_required_event_item_remains_until_collection_and_rewinds(
    snapshot, departed, coverage
):
    profile, _, put, read = snapshot
    award = profile.rooms["01-02"]["event_awards"][0]
    source = "01-02" if departed else "00-01"
    room = {
        **profile.rooms[source],
        "items": [],
        "collection_item_ids": [],
        "event_awards": [award],
        "candidate_list_complete": coverage,
    }
    profile = replace(profile, rooms={**profile.rooms, source: room})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    if departed:
        tracker.mark_current(RoomId(1, 2))
    visits = None
    for acquired, story, expected in [
        (0, 0, "uncollected"),
        (0, 0x01000000, "unknown"),
        (0x04000000, 0x01000000, "taken"),
        (0x04000000, 0, "taken"),
        (0, 0, "uncollected"),
    ]:
        put(0x800CC9E8, acquired, 4)
        put(0x800CC980, story, 4)
        # The event may be inactive; only the source proof and fresh gate matter.
        put(0x800C7D08, 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms[source]
        assert record.items[0].state == expected
        assert record.items[0].label == (
            "Event collectible"
            if expected == "unknown"
            else profile.names["items"]["53"]
        )
        assert record.completion is (
            RoomCompletion.Incomplete
            if expected == "uncollected"
            else RoomCompletion.Cleared
            if expected == "taken" and coverage
            else RoomCompletion.Unknown
        )
        if visits is None:
            visits = dict(tracker.region_visits)
        assert tracker.region_visits == visits
    fresh = Tracker()
    if departed:
        fresh.mark_current(RoomId(1, 2))
    assert poll_re2(profile, fresh, read).status is PollStatus.Display
    assert fresh.rooms[source].completion is RoomCompletion.Incomplete


@pytest.mark.parametrize("failure", ["changed", "short"])
def test_event_presence_gate_participates_in_snapshot_coherence(snapshot, failure):
    profile, _, put, read = snapshot
    room = {
        **profile.rooms["00-01"],
        "event_awards": profile.rooms["01-02"]["event_awards"],
    }
    profile = replace(profile, rooms={**profile.rooms, "00-01": room})
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changed(address, width):
        if address == 0x800CC980:
            if failure == "short":
                return MemRead(True, b"\0")
            put(address, 0x01000000, 4)
        return read(address, width)

    result = poll_re2(profile, tracker, changed)
    assert result.status is (
        PollStatus.Retry if failure == "changed" else PollStatus.ReadFailure
    )
    assert tracker == before


@pytest.mark.parametrize("departed", [False, True])
@pytest.mark.parametrize("coverage", [False, True])
def test_conditional_pickup_survives_departure_and_fresh_flag_reversal(
    snapshot, departed, coverage
):
    profile, _, put, read = snapshot
    source = "01-07" if departed else "00-01"
    original = profile.rooms["01-07"]
    item = original["items"][0]
    # Use a mutable story gate here; the native case's gate is also in the
    # Leon A scenario mask, whose opposite correctly rejects the whole game.
    rule = {
        "global_id": item["global_id"],
        "presence": {
            "kind": "conditions",
            "any_of": [[{"bank": 4, "bit": 7, "expected": 0}]],
        },
    }
    room = {
        **profile.rooms[source],
        "items": [item],
        "collection_item_ids": [],
        "conditional_item_presence": [rule],
        "event_awards": [],
        "candidate_list_complete": coverage,
    }
    profile = replace(profile, rooms={**profile.rooms, source: room})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    if departed:
        tracker.mark_current(RoomId(1, 7))
    visits = None
    address, _ = profile.flag_banks[8]
    word_address = address + item["global_id"] // 32 * 4
    mask = 0x80000000 >> (item["global_id"] % 32)
    for acquired, gate, state in [
        (False, 0, "uncollected"),
        (False, 0x01000000, "unknown"),
        (True, 0x01000000, "taken"),
        (True, 0, "taken"),
        (False, 0, "uncollected"),
    ]:
        put(word_address, mask if acquired else 0, 4)
        put(0x800CC980, gate, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms[source]
        assert record.items[0].state == state
        assert record.completion is (
            RoomCompletion.Incomplete
            if state == "uncollected"
            else RoomCompletion.Cleared
            if state == "taken" and coverage
            else RoomCompletion.Unknown
        )
        if visits is None:
            visits = dict(tracker.region_visits)
        assert tracker.region_visits == visits
    fresh = Tracker()
    if departed:
        fresh.mark_current(RoomId(1, 7))
    assert poll_re2(profile, fresh, read).status is PollStatus.Display
    assert fresh.rooms[source].items == tracker.rooms[source].items


@pytest.mark.parametrize("failure", ["changed", "short"])
def test_conditional_pickup_gate_is_part_of_coherent_publication(snapshot, failure):
    profile, _, put, read = snapshot
    original = profile.rooms["01-07"]
    item = original["items"][0]
    room = {
        **profile.rooms["00-01"],
        "items": [item],
        "collection_item_ids": [],
        "event_awards": [],
        "conditional_item_presence": [
            {
                "global_id": item["global_id"],
                "presence": {
                    "kind": "conditions",
                    "any_of": [[{"bank": 5, "bit": 1, "expected": 0}]],
                },
            }
        ],
    }
    profile = replace(profile, rooms={**profile.rooms, "00-01": room})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changed(address, width):
        if address == 0x800CC9A0:
            if failure == "short":
                return MemRead(True, b"\0")
            put(address, 0x40000000, 4)
        return read(address, width)

    result = poll_re2(profile, tracker, changed)
    assert result.status is (
        PollStatus.Retry if failure == "changed" else PollStatus.ReadFailure
    )
    assert tracker == before


@pytest.mark.parametrize("departed", [False, True])
@pytest.mark.parametrize("unproven", [False, True])
@pytest.mark.parametrize("shared_acquisition", [False, True])
@pytest.mark.parametrize(
    "excluded_source,excluded_gid",
    [("00-0f", 157), ("01-02", 249), ("01-02", 116), ("01-08", 158), ("01-09", 70)],
)
def test_scenario_exclusions_allow_only_resolved_clearance_and_rewind(
    snapshot, departed, unproven, shared_acquisition, excluded_source, excluded_gid
):
    profile, _, put, read = snapshot
    source = "00-0f" if departed else "00-01"
    actual = profile.rooms["00-0f"]
    candidates = [item for item in actual["items"] if item["global_id"] != 157]
    candidates.extend(
        item
        for item in profile.rooms[excluded_source]["items"]
        if item["global_id"] == excluded_gid
    )
    conditions = [
        rule for rule in actual["conditional_item_presence"] if rule["global_id"] != 157
    ]
    if unproven:
        # This synthetic source lacks a presence rule for the added identity;
        # the mode-pinned ID116 is now one of the exclusions under test.
        candidates.append(
            next(
                item
                for item in profile.rooms["01-08"]["items"]
                if item["global_id"] == 159
            )
        )
    room = {
        **profile.rooms[source],
        "items": candidates,
        "collection_item_ids": [],
        "conditional_item_presence": conditions,
        "scenario_absent_item_ids": [excluded_gid],
        "event_awards": [],
        "candidate_list_complete": True,
    }
    profile = replace(profile, rooms={**profile.rooms, source: room})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    if departed:
        tracker.mark_current(RoomId(0, 15))
    visits = None
    for count in [0, 1, 2, 0, 2]:
        put(0x800CC9EC, 0x02000000 if count >= 1 else 0, 4)  # ID 38.
        put(
            0x800CC9F8,
            0x00100000 if count == 2 else 0,
            4,
        )  # ID 139.
        address = profile.flag_banks[8][0] + excluded_gid // 32 * 4
        mask = 0x80000000 >> (excluded_gid % 32)
        word = int.from_bytes(read(address, 4).data, "little") & ~mask
        put(address, word | (mask if shared_acquisition else 0), 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms[source]
        assert record.total_items == 2 + int(unproven)
        assert record.collected_items == count
        assert len(record.items) == 2 + int(unproven)
        assert record.completion is (
            RoomCompletion.Incomplete
            if count < 2
            else RoomCompletion.Unknown
            if unproven
            else RoomCompletion.Cleared
        )
        if visits is None:
            visits = dict(tracker.region_visits)
        assert tracker.region_visits == visits
    fresh = Tracker()
    if departed:
        fresh.mark_current(RoomId(0, 15))
    assert poll_re2(profile, fresh, read).status is PollStatus.Display
    assert fresh.rooms[source] == tracker.rooms[source]


def test_scenario_exclusion_cannot_hide_a_live_pickup(snapshot):
    profile, _, _, read = snapshot
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    room = {
        **profile.rooms["00-01"],
        "scenario_absent_item_ids": [
            item["global_id"] for item in profile.rooms["00-01"]["items"]
        ],
    }
    profile = replace(profile, rooms={**profile.rooms, "00-01": room})
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Pickup disagrees with fixed scenario proof"
    assert tracker == before


def test_scenario_exclusions_require_the_same_coherent_scenario_snapshot(snapshot):
    profile, _, put, read = snapshot
    room = {
        **profile.rooms["00-01"],
        "items": profile.rooms["00-0f"]["items"],
        "collection_item_ids": [],
        "conditional_item_presence": profile.rooms["00-0f"][
            "conditional_item_presence"
        ],
        "scenario_absent_item_ids": [157],
    }
    profile = replace(profile, rooms={**profile.rooms, "00-01": room})
    for slot in range(32):
        put(0x800C66C8 + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def changing(address, width):
        if address == 0x800C7D04:
            put(address, 0x40000000, 4)
        return read(address, width)

    assert poll_re2(profile, tracker, changing).status is PollStatus.Retry
    assert tracker == before
    assert poll_re2(profile, tracker, read).status is PollStatus.WrongGame
    assert tracker == before


def test_scenario_selected_identity_rebuilds_after_departure(snapshot):
    """RE2-COLLECT-014: no remembered descriptor is needed to select identity."""
    profile, _, put, read = snapshot
    source = profile.rooms["00-15"]
    assert source["scenario_item_variants"] == [{"global_id": 103, "offsets": [5332]}]
    # Set other independent acquisition bits explicitly so this identity is
    # the only remaining check. The fixture is a synthetic read, not gameplay.
    tracker = Tracker()
    # This seeds prior exploration only. The fixture's live room stays 00-01,
    # so every poll below rebuilds the selected identity while departed.
    tracker.mark_current(RoomId(0, 0x15))
    for acquired in (False, True, False, True):
        words = {}
        for gid in (101, 40, 104, 209, *([103] if acquired else [])):
            address = 0x800CC9E8 + gid // 32 * 4
            words[address] = words.get(address, 0) | (0x80000000 >> (gid % 32))
        for address, value in words.items():
            put(address, value, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        assert tracker.current == RoomId(0, 1)
        record = tracker.rooms["00-15"]
        item = next(
            item for item in record.items if item.label == profile.names["items"]["7"]
        )
        assert item.state == ("taken" if acquired else "uncollected")
        assert item.quantity == 5
        assert not any(item.label == "Collectible" for item in record.items)
        assert record.completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Incomplete
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(0, 0x15))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["00-15"].items == record.items
        assert fresh.rooms["00-15"].completion is record.completion


@pytest.mark.parametrize("snapshot", ["00-15"], indirect=True)
@pytest.mark.parametrize("excluded", [False, True])
def test_live_creator_must_agree_with_scenario_selected_variant(snapshot, excluded):
    profile, _, put, read = snapshot
    selected = next(
        item
        for item in profile.rooms["00-15"]["items"]
        if item["offset"] == (5396 if excluded else 5332)
    )
    put(0x800C66C8 + 13 * 4, 0x80100000 + selected["offset"] + 2, 4)
    tracker = Tracker()
    before = copy.deepcopy(tracker)
    result = poll_re2(profile, tracker, read)
    if excluded:
        assert result.status is PollStatus.Retry
        assert result.text == "Pickup disagrees with fixed scenario variant"
        assert tracker == before
    else:
        assert result.status is PollStatus.Display
        item = next(
            item
            for item in tracker.rooms["00-15"].items
            if item.label == profile.names["items"]["7"]
        )
        assert item.state == "available" and item.quantity == 5
