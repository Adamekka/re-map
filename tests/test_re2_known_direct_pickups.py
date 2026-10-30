"""RE2-STARTUP-004: direct pickups require bound identities and fresh conditions."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import pytest
from test_re2_tracking import snapshot as snapshot

from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus
from tracker.visit_history import HistoryIdentity, VisitHistory

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def direct_catalog():
    path = ROOT / "profiles/re2_leon_a_slus00748.json"
    raw = json.loads(path.read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((path.parent / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    # Explicit test evidence isolates loader/reader contracts. The production
    # source compiler must independently establish these records from bytes.
    for room in document["rooms"]:
        room["known_direct_pickups"] = []
    room = next(room for room in document["rooms"] if room["id"] == "00-12")
    room["known_direct_pickups"] = [
        {
            "global_id": 22,
            "item_type": 39,
            "slot": 12,
            "creator_offsets": [11272],
            "context_conditions": [
                {
                    "kind": "conditions",
                    "any_of": [[{"bank": 1, "bit": 6, "expected": 0}]],
                }
            ],
        }
    ]
    return raw, document, room


def load_catalog(tmp_path, raw, document):
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw | {"room_metadata_path": str(metadata)}))
    return Re2Profile.load(path)


@pytest.fixture
def profile(tmp_path, direct_catalog):
    raw, document, _ = direct_catalog
    return load_catalog(tmp_path, raw, document)


def test_bound_direct_pickup_catalog_loads_with_explicit_context(profile):
    assert profile.rooms["00-12"]["known_direct_pickups"][0]["global_id"] == 22


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "not-list",
        "not-object",
        "duplicate",
        "boolean-id",
        "out-of-range-id",
        "wrong-type",
        "wrong-slot",
        "empty-creators",
        "wrong-creator",
        "duplicate-creators",
        "extra-field",
        "absent",
        "required-context",
        "missing-context",
        "null-context",
        "boolean-condition",
        "unknown-bank",
        "stage",
        "source-path",
        "source-width",
        "source-hash",
        "null-items",
        "four-point",
        "puzzle-overlap",
        "declaration-overlap",
        "unaudited",
    ],
)
def test_direct_pickup_catalog_rejects_unbound_or_ambiguous_evidence(
    tmp_path, direct_catalog, fault
):
    raw, document, room = direct_catalog
    proof = room["known_direct_pickups"][0]
    if fault == "missing":
        del room["known_direct_pickups"]
    elif fault == "not-list":
        room["known_direct_pickups"] = None
    elif fault == "not-object":
        room["known_direct_pickups"] = [None]
    elif fault == "duplicate":
        room["known_direct_pickups"].append(copy.deepcopy(proof))
    elif fault == "boolean-id":
        proof["global_id"] = True
    elif fault == "out-of-range-id":
        proof["global_id"] = 256
    elif fault == "wrong-type":
        proof["item_type"] = 40
    elif fault == "wrong-slot":
        proof["slot"] = 13
    elif fault == "empty-creators":
        proof["creator_offsets"] = []
    elif fault == "wrong-creator":
        proof["creator_offsets"] = [11273]
    elif fault == "duplicate-creators":
        proof["creator_offsets"] *= 2
    elif fault == "extra-field":
        proof["amount"] = 1
    elif fault == "absent":
        room["scenario_absent_item_ids"].append(22)
    elif fault == "required-context":
        proof["context_conditions"] = [{"kind": "required"}]
    elif fault == "missing-context":
        del proof["context_conditions"]
    elif fault == "null-context":
        proof["context_conditions"] = None
    elif fault == "boolean-condition":
        proof["context_conditions"][0]["any_of"][0][0]["expected"] = False
    elif fault == "unknown-bank":
        proof["context_conditions"][0]["any_of"][0][0]["bank"] = 255
    elif fault == "stage":
        room["stage"] = 1
    elif fault == "source-path":
        room["source"] = "PL0/RDT/ROOM1130.RDT"
    elif fault == "source-width":
        room["size"] += 4
    elif fault == "source-hash":
        room["sha256"] = "0" * 64
    elif fault == "null-items":
        room["items"] = None
    elif fault == "four-point":
        next(item for item in room["items"] if item["global_id"] == 22)[
            "four_point"
        ] = True
    elif fault == "puzzle-overlap":
        proof.update(global_id=21, item_type=59, slot=11, creator_offsets=[10656])
    elif fault == "declaration-overlap":
        room["startup_item_declarations"] = [
            {key: value for key, value in proof.items() if key != "context_conditions"}
        ]
    else:
        del raw["startup_declaration_audit"]
        del document["startup_declaration_audit"]
        for source in document["rooms"]:
            del source["startup_item_declarations"]
    with pytest.raises(ValueError, match="RE2 (known direct-pickup|known puzzle-item)"):
        load_catalog(tmp_path, raw, document)


def test_explicit_unconditional_direct_evidence_has_no_context_default(
    tmp_path, direct_catalog
):
    raw, document, room = direct_catalog
    room["known_direct_pickups"][0]["context_conditions"] = []
    loaded = load_catalog(tmp_path, raw, document)
    assert loaded.rooms["00-12"]["known_direct_pickups"][0]["context_conditions"] == []


def test_departed_direct_pickup_rewinds_and_round_trips_visits_only(snapshot, tmp_path):
    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0x12))
    bank, _ = profile.flag_banks[profile.runtime_layout["item_bank_early"]]
    identity = HistoryIdentity(
        profile.profile_id,
        profile.runtime_signature.concatenated_sha256,
        profile.target.scenario,
    )
    region_rooms = {
        area["id"] + ":" + room["id"]: set(room["room_ids"])
        for area in profile.map_layout.document["areas"]
        for room in area["rooms"]
    }
    history_path = tmp_path / "visits.json"
    for direct_acquired, puzzle_acquired in [
        (False, False),
        (True, False),
        (True, True),
        (False, True),
        (False, False),
    ]:
        value = ((0x80000000 >> 22) if direct_acquired else 0) | (
            (0x80000000 >> 21) if puzzle_acquired else 0
        )
        put(bank, value, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-12"]
        direct = next(
            item for item in record.items if item.label == profile.names["items"]["39"]
        )
        assert direct.state == ("taken" if direct_acquired else "uncollected")
        assert direct.quantity == 1
        assert record.list_complete
        assert record.completion is (
            RoomCompletion.Cleared
            if direct_acquired and puzzle_acquired
            else RoomCompletion.Incomplete
        )
        history = VisitHistory(
            history_path, identity, region_rooms, new_playthrough=True
        )
        history.save(tracker)
        history.close()
        history = VisitHistory(
            history_path, identity, region_rooms, new_playthrough=False
        )
        fresh = history.restore()
        history.close()
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["00-12"] == record
        saved = json.loads(history_path.read_text())
        assert set(saved) == {
            "schema",
            "identity",
            "playthrough_id",
            "rooms",
            "regions",
        }


def test_direct_context_is_fresh_and_acquisition_wins(snapshot):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-12"])
    source["known_direct_pickups"][0]["context_conditions"] = [
        {"kind": "conditions", "any_of": [[{"bank": 4, "bit": 24, "expected": 1}]]}
    ]
    profile = replace(profile, rooms=profile.rooms | {"00-12": source})
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0x12))
    bank, _ = profile.flag_banks[profile.runtime_layout["item_bank_early"]]
    story, _ = profile.flag_banks[4]
    for matched, acquired in [
        (False, False),
        (True, False),
        (False, False),
        (False, True),
    ]:
        put(story, 0x80000000 >> 24 if matched else 0, 4)
        put(bank, 0x80000000 >> 22 if acquired else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        direct = next(
            item
            for item in tracker.rooms["00-12"].items
            if item.label == profile.names["items"]["39"]
        )
        assert direct.state == (
            "taken" if acquired else "uncollected" if matched else "unknown"
        )
    before = copy.deepcopy(tracker)

    def torn_read(address, width):
        if (address, width) == (story, 4):
            put(story, 0x80000000 >> 24, 4)
        return read(address, width)

    assert poll_re2(profile, tracker, torn_read).status is PollStatus.Retry
    assert tracker == before


@pytest.mark.parametrize("snapshot", ["00-12"], indirect=True)
def test_live_direct_pickup_precedes_unmatched_source_context(snapshot):
    profile, _, put, read = snapshot
    source = copy.deepcopy(profile.rooms["00-12"])
    source["known_direct_pickups"][0]["context_conditions"] = [
        {"kind": "conditions", "any_of": [[{"bank": 4, "bit": 24, "expected": 1}]]}
    ]
    profile = replace(profile, rooms=profile.rooms | {"00-12": source})
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    label = profile.names["items"]["39"]
    assert (
        next(item for item in tracker.rooms["00-12"].items if item.label == label).state
        == "available"
    )
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    put(registry + 12 * 4, 0, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert (
        next(item for item in tracker.rooms["00-12"].items if item.label == label).state
        == "unknown"
    )
