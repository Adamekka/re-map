"""RE2-LIVE-001: synthetic coherence, revision isolation and flag rewind.

These tests exercise interpretation contracts; they are not gameplay evidence.
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


def test_disabled_pickups_are_dormant_and_missing_ones_remain_unknown(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    for definition in profile.rooms["00-01"]["items"]:
        put(0x80100000 + definition["offset"] + 2, 0, 1)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Cleared
    assert all(item.state == "dormant" for item in tracker.rooms["00-01"].items)
    put(0x800C66C8 + 11 * 4, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-01"].completion is RoomCompletion.Unknown


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
    put(0x800CCB60, 0, 4)
    poll_re2(profile, tracker, read)
    assert tracker.doors[0].state == "LOCKED"


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
    put(0x80100000 + definition["offset"] + 2, 0, 1)
    put(0x800CCB60, 0xFFFFFFFF, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.doors[0].state == "BLOCKED"


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
    put(0x800CCB60, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    door = next(door for door in tracker.doors if door.source == RoomId(0, 0))
    assert door.label == "Door conditions unresolved"
