"""RE2-SCENARIO-001: scoped facts never grant presence or bypass fresh state."""

import copy
import json
from pathlib import Path

import pytest
from test_re2_tracking import snapshot as snapshot

from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def profile():
    return Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00748.json")


@pytest.mark.parametrize("snapshot", ["00-01", "01-0b"], indirect=True)
def test_office_absences_preserve_full_independent_list_and_flag_rewind(snapshot):
    """RE2-SCENARIO-007: task isolation grants absence, never presence."""
    profile, _, put, read = snapshot
    source = profile.rooms["01-0b"]
    assert source["scoped_scenario_items"] == {
        "absent_item_ids": [48, 82],
        "item_variants": [],
    }
    assert not source["fixed_context_preserved"]
    assert {i["global_id"] for i in source["items"]} == {48, 74, 78, 81, 82, 84, 217}
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    # A valid A scenario cannot register the fixture's raw B alternatives.
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 11))
    visits = None
    required = {74, 78, 81, 84}
    for taken in (set(), {48, 82}, required, required | {217}, {48, 74, 82}, set()):
        for gid in (48, 74, 78, 81, 82, 84, 217):
            address, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(read(address, 4).data, "little")
            put(address, value | mask if gid in taken else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["01-0b"]
        assert record.list_complete and len(record.items) == 5
        assert sum(i.state == "taken" for i in record.items) == len(taken - {48, 82})
        assert sum(i.state == "uncollected" for i in record.items) == len(
            required - taken
        )
        assert sum(i.state == "unknown" for i in record.items) == (217 not in taken)
        assert record.completion is (
            RoomCompletion.Incomplete
            if required - taken
            else RoomCompletion.Unknown
            if 217 not in taken
            else RoomCompletion.Cleared
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(1, 11))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["01-0b"] == record
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize("snapshot", ["01-0b"], indirect=True)
@pytest.mark.parametrize("gid", [48, 82])
@pytest.mark.parametrize("sat", [0, 0x31])
def test_office_live_excluded_creator_rejects_atomically(snapshot, gid, sat):
    profile, _, put, read = snapshot
    item = next(i for i in profile.rooms["01-0b"]["items"] if i["global_id"] == gid)
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    pointer = 0x80100000 + item["offset"] + 2
    put(registry + item["slot"] * 4, pointer, 4)
    put(pointer + 1, sat, 1)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Pickup disagrees with fixed scenario proof"
    assert tracker == before


@pytest.mark.parametrize("snapshot", ["00-01", "01-13"], indirect=True)
def test_normal_engine_guard_excludes_b_item_without_caching_completion(snapshot):
    """RE2-SCENARIO-005: absence cannot replace another item's acquisition."""
    profile, _, put, read = snapshot
    source = profile.rooms["01-13"]
    assert source["scoped_scenario_items"] == {
        "absent_item_ids": [24],
        "item_variants": [],
    }
    assert not source["fixed_context_preserved"]
    assert {item["global_id"] for item in source["items"]} == {24, 253}
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    # The generic fixture registers every raw alternative. A valid Leon A
    # registry cannot contain the B-only item; contradictions are tested below.
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 0x13))
    visits = None
    for excluded_taken, other_taken in (
        (False, True),
        (True, True),
        (True, False),
        (False, False),
        (False, True),
    ):
        for gid, acquired in ((24, excluded_taken), (253, other_taken)):
            address, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(read(address, 4).data, "little")
            put(address, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["01-13"]
        assert record.list_complete and len(record.items) == 1
        assert record.items[0].state == ("taken" if other_taken else "unknown")
        assert record.completion is (
            RoomCompletion.Cleared if other_taken else RoomCompletion.Unknown
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(1, 0x13))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["01-13"] == record
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize("snapshot", ["01-13"], indirect=True)
@pytest.mark.parametrize("sat", [0, 0x31])
def test_normal_engine_guard_rejects_a_live_b_item_atomically(snapshot, sat):
    profile, _, put, read = snapshot
    source = profile.rooms["01-13"]
    excluded = next(item for item in source["items"] if item["global_id"] == 24)
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    pointer = 0x80100000 + excluded["offset"] + 2
    put(registry + excluded["slot"] * 4, pointer, 4)
    put(pointer + 1, sat, 1)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Pickup disagrees with fixed scenario proof"
    assert tracker == before


@pytest.mark.parametrize("snapshot", ["00-01", "00-09"], indirect=True)
def test_side_entrance_exclusion_keeps_independent_checks_and_rewinds(snapshot):
    """RE2-SCENARIO-006/008: absence never collects the remaining puzzle item."""
    profile, _, put, read = snapshot
    source = profile.rooms["00-09"]
    assert source["scoped_scenario_items"] == {
        "absent_item_ids": [146, 205],
        "item_variants": [],
    }
    assert not source["fixed_context_preserved"]
    assert {item["global_id"] for item in source["items"]} == {13, 146, 205}
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    # The fixture registers every raw creator. Remove those registrations so
    # this test exercises game acquisition, not the contradictory B descriptor.
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 9))
    visits = None
    for excluded, first, second in (
        (False, False, False),
        (True, False, False),
        (True, True, False),
        (False, False, True),
        (False, False, False),
    ):
        for gid, acquired in ((146, excluded), (13, first), (205, second)):
            address, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(read(address, 4).data, "little")
            put(address, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-09"]
        assert record.list_complete and len(record.items) == 1
        assert record.items[0].state == ("taken" if first else "uncollected")
        assert record.completion is (
            RoomCompletion.Cleared if first else RoomCompletion.Incomplete
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(0, 9))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["00-09"] == record
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize("snapshot", ["00-09"], indirect=True)
@pytest.mark.parametrize("sat", [0, 0x31])
@pytest.mark.parametrize("gid", [146, 205])
def test_side_entrance_live_excluded_creator_rejects_atomically(snapshot, sat, gid):
    """RE2-SCENARIO-006/008: absence cannot hide a fresh contradiction."""
    profile, _, put, read = snapshot
    source = profile.rooms["00-09"]
    excluded = next(item for item in source["items"] if item["global_id"] == gid)
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    pointer = 0x80100000 + excluded["offset"] + 2
    put(registry + excluded["slot"] * 4, pointer, 4)
    put(pointer + 1, sat, 1)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Pickup disagrees with fixed scenario proof"
    assert tracker == before


@pytest.mark.parametrize("target,gid", [("01-00", 152)])
def test_scoped_identity_collection_rewinds_without_cached_verdict(
    snapshot, target, gid
):
    profile, _, put, read = snapshot
    source = profile.rooms[target]
    assert not source["fixed_context_preserved"]
    assert gid in {
        r["global_id"] for r in source["scoped_scenario_items"]["item_variants"]
    }
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    # The generic fixture registers every alternative in its current room.
    # This test isolates fresh acquisition reconstruction after departure.
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    for item in source["items"]:
        address = bank + item["global_id"] // 32 * 4
        value = int.from_bytes(read(address, 4).data, "little")
        put(address, value | (0x80000000 >> (item["global_id"] % 32)), 4)
    target_id = RoomId(int(target[:2]), int(target[3:], 16))
    tracker = Tracker()
    tracker.mark_current(target_id)
    visits = None
    for acquired in (True, False, True, False):
        address, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
        value = int.from_bytes(read(address, 4).data, "little")
        put(address, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms[target]
        assert record.list_complete
        assert all(item.label != "Collectible" for item in record.items)
        assert record.completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Unknown
        )
        fresh = Tracker()
        fresh.mark_current(target_id)
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms[target] == record
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


def test_unsafe_rooftop_entry_keeps_collected_identity_unresolved(snapshot):
    profile, _, put, read = snapshot
    source = profile.rooms["00-08"]
    assert source["scoped_scenario_items"] == {
        "absent_item_ids": [],
        "item_variants": [],
    }
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    put(bank + 213 // 32 * 4, 0x80000000 >> (213 % 32), 4)
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 8))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    record = tracker.rooms["00-08"]
    assert record.completion is RoomCompletion.Unknown
    assert not record.list_complete
    assert [(item.label, item.state) for item in record.items] == [
        ("Collectible", "taken")
    ]


def test_root_replacement_scope_resolves_identity_without_inventing_presence(snapshot):
    """RE2-SCENARIO-004: selected identity and acquisition remain separate."""
    profile, _, put, read = snapshot
    source = profile.rooms["01-14"]
    assert source["scoped_scenario_items"] == {
        "absent_item_ids": [],
        "item_variants": [{"global_id": 68, "offsets": [1032]}],
    }
    assert not source["fixed_context_preserved"]
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 0x14))
    # Collect the two independent ammo pickups so the controls isolate the
    # selected identity and the separately required weapon, while departed.
    for gid in (64, 65):
        address, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
        value = int.from_bytes(read(address, 4).data, "little")
        put(address, value | mask, 4)
    for acquired, weapon, completion in (
        (True, False, RoomCompletion.Incomplete),
        (False, False, RoomCompletion.Incomplete),
        (True, True, RoomCompletion.Cleared),
        (False, True, RoomCompletion.Unknown),
        (True, False, RoomCompletion.Incomplete),
    ):
        for gid, taken in ((68, acquired), (62, weapon)):
            address, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(read(address, 4).data, "little")
            put(address, value | mask if taken else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["01-14"]
        assert record.list_complete and record.completion is completion
        selected = next(
            i for i in record.items if i.label == profile.names["items"]["21"]
        )
        assert selected.state == ("taken" if acquired else "unknown")
        assert selected.quantity == 7 and selected.quantity_is_unit_count
        remaining = next(
            i for i in record.items if i.label == profile.names["items"]["15"]
        )
        assert remaining.state == ("taken" if weapon else "uncollected")
        assert not any(i.label == "Collectible" for i in record.items)
        fresh = Tracker()
        fresh.mark_current(RoomId(1, 0x14))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["01-14"] == record
        assert fresh.region_visits == tracker.region_visits


@pytest.mark.parametrize("snapshot", ["01-14"], indirect=True)
@pytest.mark.parametrize("sat", [0, 0x31])
def test_root_replacement_identity_rejects_a_contradictory_live_creator(snapshot, sat):
    profile, _, put, read = snapshot
    source = profile.rooms["01-14"]
    excluded = next(i for i in source["items"] if i["offset"] == 1006)
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    pointer = 0x80100000 + excluded["offset"] + 2
    put(registry + excluded["slot"] * 4, pointer, 4)
    put(pointer + 1, sat, 1)
    tracker = Tracker()
    before = copy.deepcopy(tracker)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Pickup disagrees with fixed scenario variant"
    assert tracker == before


def test_art_declared_pickups_remain_required_after_departure_and_rewind(snapshot):
    profile, _, put, read = snapshot
    source = profile.rooms["00-0b"]
    assert not source["fixed_context_preserved"]
    assert source["scenario_absent_item_ids"] == [98]
    assert {item["global_id"] for item in source["known_direct_pickups"]} == {
        95,
        99,
        220,
    }
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0x0B))
    visits = None
    for first, second in [(False, False), (True, False), (True, True), (False, False)]:
        for gid, acquired in [(95, first), (99, second), (97, True), (220, True)]:
            address, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(read(address, 4).data, "little")
            put(address, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-0b"]
        assert record.list_complete
        assert {item.label: item.state for item in record.items} == {
            profile.names["items"]["62"]: "taken" if first else "uncollected",
            profile.names["items"]["90"]: "taken",
            profile.names["items"]["21"]: "taken" if second else "uncollected",
            profile.names["items"]["30"]: "taken",
        }
        assert record.completion is (
            RoomCompletion.Cleared if first and second else RoomCompletion.Incomplete
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(0, 0x0B))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["00-0b"] == record
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits


@pytest.mark.parametrize("snapshot", ["00-0b"], indirect=True)
def test_live_opposite_scenario_creator_rejects_scoped_exclusion(snapshot):
    profile, _, put, read = snapshot
    source = profile.rooms["00-0b"]
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    item = next(item for item in source["items"] if item["global_id"] == 98)
    put(registry + item["slot"] * 4, 0x80100000 + item["offset"] + 2, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Retry
    assert tracker == before


@pytest.mark.parametrize("fault", ["below-floor", "past-ram", "unaligned", "short"])
def test_bad_native_work_ownership_never_publishes_scoped_facts(snapshot, fault):
    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 0))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    address = int(profile.runtime_layout["scenario_work_address_ps1"], 0)
    initial = int.from_bytes(read(address, 4).data, "little")
    if fault != "short":
        put(
            address,
            {
                "below-floor": initial - 4,
                "past-ram": 0x80200004,
                "unaligned": initial + 1,
            }[fault],
            4,
        )

    def interrupted(base, width):
        result = read(base, width)
        if fault == "short" and (base, width) == (address, 4):
            return type(result)(True, result.data[:3])
        return result

    assert poll_re2(profile, tracker, interrupted).status is (
        PollStatus.ReadFailure if fault == "short" else PollStatus.Retry
    )
    assert tracker == before


@pytest.mark.parametrize("change", ["reset-initial", "reset-recheck", "work-recheck"])
def test_reset_and_work_coherence_preserve_atomic_publication(snapshot, change):
    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 0))
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    layout = profile.runtime_layout
    system = int(layout["system_flags_address_ps1"], 0)
    work = int(layout["scenario_work_address_ps1"], 0)
    if change == "reset-initial":
        put(system, int.from_bytes(read(system, 4).data, "little") | 0x1000, 4)
    calls = 0

    def changing(base, width):
        nonlocal calls
        if change == "reset-recheck" and (base, width) == (system, 4):
            # The initial SYSTEM came from the player block, so this is its
            # independent coherence read, not a second cached interpretation.
            put(system, int.from_bytes(read(system, 4).data, "little") | 0x1000, 4)
        if change == "work-recheck" and (base, width) == (work, 4):
            calls += 1
            if calls == 2:
                put(work, int.from_bytes(read(work, 4).data, "little") + 4, 4)
        return read(base, width)

    assert poll_re2(profile, tracker, changing).status is PollStatus.Retry
    assert tracker == before


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "null",
        "extra-field",
        "absent-not-list",
        "variants-not-list",
        "boolean-id",
        "foreign-id",
        "duplicate-id",
        "empty-offsets",
        "foreign-offset",
        "duplicate-offset",
        "source-hash",
        "source-width",
        "source-path",
        "reset-mask",
        "work-address",
    ],
)
def test_scoped_catalog_requires_revision_source_and_complete_identity_binding(
    tmp_path, fault
):
    path = ROOT / "profiles/re2_leon_a_slus00748.json"
    raw = json.loads(path.read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((path.parent / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    room = next(r for r in document["rooms"] if r["id"] == "01-00")
    scoped = room["scoped_scenario_items"]
    variant = scoped["item_variants"][0]
    if fault == "missing":
        del room["scoped_scenario_items"]
    elif fault == "null":
        room["scoped_scenario_items"] = None
    elif fault == "extra-field":
        scoped["presence"] = True
    elif fault == "absent-not-list":
        scoped["absent_item_ids"] = None
    elif fault == "variants-not-list":
        scoped["item_variants"] = None
    elif fault in ("boolean-id", "foreign-id"):
        variant["global_id"] = True if fault == "boolean-id" else 999
    elif fault == "duplicate-id":
        scoped["item_variants"].append(copy.deepcopy(variant))
    elif fault == "empty-offsets":
        variant["offsets"] = []
    elif fault == "foreign-offset":
        variant["offsets"] = [variant["offsets"][0] + 1]
    elif fault == "duplicate-offset":
        variant["offsets"].append(variant["offsets"][0])
    elif fault == "source-hash":
        room["sha256"] = "0" * 64
    elif fault == "source-width":
        room["size"] += 4
    elif fault == "source-path":
        room["source"] = "PL0/RDT/ROOM2010.RDT"
    elif fault == "reset-mask":
        raw["runtime_layout"]["scenario_reset_mask"] = 0
    else:
        raw["runtime_layout"]["scenario_work_address_ps1"] = "0x800CE328"
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    config = tmp_path / "profile.json"
    config.write_text(json.dumps(raw | {"room_metadata_path": str(metadata)}))
    with pytest.raises(ValueError, match="RE2"):
        Re2Profile.load(config)
