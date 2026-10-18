"""RE2-LIVE-001 / RE2-COLLECT-001: coherent collection and flag rewind.

These tests exercise interpretation contracts; they are not gameplay evidence.
RE2-COLLECT-002 checks known items alongside unresolved slot identities.
"""

import copy
import hashlib
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from games.runtime_identity import RuntimeSignature
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus
from ui.map_view import map_state


@pytest.fixture(scope="module")
def profile():
    return Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")


@pytest.fixture
def snapshot(profile):
    room = copy.deepcopy(profile.rooms["00-01"])
    for proof in room["proofs"]:
        proof["sha256"] = hashlib.sha256(bytes(proof["width"])).hexdigest()
    profile = replace(
        profile,
        rooms={**profile.rooms, "00-01": room},
        runtime_signature=RuntimeSignature(
            (0x80010000,), 32, hashlib.sha256(bytes(32)).hexdigest()
        ),
    )
    ram = bytearray(0x200000)

    def put(address, value, width):
        ram[address & 0x1FFFFF : (address & 0x1FFFFF) + width] = value.to_bytes(
            width, "little"
        )

    put(0x800C7CE4, 0x40000000, 4)
    put(0x800C7D24, 1, 4)
    put(profile.room_address, 1, 2)
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


def test_shared_camera_positions_do_not_bind_the_wrong_room(snapshot):
    profile, _, put, read = snapshot
    put(0x80100008, 0x80100001, 4)
    tracker = Tracker()
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert "section layout" in result.text
    assert tracker == Tracker()


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
