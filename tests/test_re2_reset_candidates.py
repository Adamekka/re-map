"""RE2-RESET-001: enumeration is independent of presence and clearance proof."""

import copy
import json
import struct
from pathlib import Path

import pytest
from test_re2_metadata import item_command
from test_re2_positive_prefix import owned as owned
from test_re2_reset_item_variants import catalog as catalog
from test_re2_reset_item_variants import load_catalog
from test_re2_room_write_partitions import END, source
from test_re2_script_dispatch_items import dispatch_snapshot as dispatch_snapshot
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from games.re2.reset_candidates import (
    DescriptorOrigin,
    NullOrigin,
    ResetCandidateSupport,
    compile_reset_candidates,
    reset_candidate_config,
    tracking_item_candidates,
    validate_reset_candidates,
)
from games.re2.scenario_selection import (
    ScenarioSelectionFailure,
)
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus

ROOT = Path(__file__).resolve().parents[1]
RAW = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
CONFIG = reset_candidate_config(RAW)


def compile_synthetic(initial, reset, *, prefix=b""):
    data, room, _ = source(prefix + initial + END, (END, reset + END), (), (0,))
    room.update(compile_reset_candidates(data, room, CONFIG, RAW))
    room["scenario_item_variants"] = []
    validate_reset_candidates(room, CONFIG)
    return data, room


@pytest.mark.parametrize(
    "opcode,kind,four_point",
    [(0x2C, 0, False), (0x3B, 1, False), (0x67, 0, True), (0x68, 1, True)],
)
def test_reset_candidates_bind_nonitem_constructor_geometry_and_real_null_alias(
    opcode, kind, four_point
):
    from games.re2.room_data import OPCODE_WIDTHS

    creator = bytes((opcode, 8, kind, 0x31)) + bytes(OPCODE_WIDTHS[opcode] - 4)
    _, room = compile_synthetic(
        creator, b"\x46\x08\x02\x31" + struct.pack("<3H", 20, 15, 9)
    )
    (reset,) = room["reset_item_candidates"]
    (descriptor,) = room["reset_candidate_descriptors"]
    assert reset["origins"] == [
        {
            "kind": "descriptor",
            "offset": descriptor["offset"],
            "four_point": four_point,
        },
        {"kind": "unregistered_null_alias"},
    ]
    assert room["items"] == []
    assert room["reset_item_variants"] == []
    assert not room["candidate_list_complete"]
    rows = tracking_item_candidates(room, CONFIG, selected=False)
    assert [r["origin"] for r in rows] == [
        DescriptorOrigin(descriptor["offset"], four_point),
        NullOrigin.UnregisteredAlias,
    ]
    assert all(r["global_id"] == 9 for r in rows)


def test_no_creator_is_an_explicit_null_alias_without_fabricated_offset():
    _, room = compile_synthetic(
        b"", b"\x46\x0b\x02\x31" + struct.pack("<3H", 27, 100, 129)
    )
    assert room["reset_item_candidates"][0]["origins"] == [
        {"kind": "unregistered_null_alias"}
    ]
    (row,) = tracking_item_candidates(room, CONFIG, selected=False)
    assert row["origin"] is NullOrigin.UnregisteredAlias
    assert "offset" not in row


@pytest.mark.parametrize(
    "field,value",
    [
        ("slot", 32),
        ("global_id", 256),
        ("sat", 128),
        ("type", True),
        ("amount", -1),
        ("offset", False),
    ],
)
def test_loader_rejects_malformed_candidate_scalars(field, value):
    _, room = compile_synthetic(
        item_command(20, 15, 9), b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 10)
    )
    room["reset_item_candidates"][0][field] = value
    with pytest.raises(ValueError, match="RE2 reset"):
        validate_reset_candidates(room, CONFIG)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "overlap",
        "unsorted",
        "fake-origin",
        "null-offset",
        "wrong-slot",
        "geometry",
        "boolean-geometry",
        "unknown-status",
        "extra-field",
    ],
)
def test_loader_rejects_unbound_or_ambiguous_companion(catalog, tmp_path, fault):
    raw, document, _ = catalog
    room = next(r for r in document["rooms"] if r["id"] == "05-10")
    row = room["reset_item_candidates"][0]
    if fault == "missing":
        del room["reset_item_candidates"]
    elif fault == "duplicate":
        room["reset_item_candidates"].append(copy.deepcopy(row))
    elif fault == "overlap":
        room["reset_item_candidates"].append(row | {"offset": row["offset"] + 1})
    elif fault == "unsorted":
        room["reset_candidate_descriptors"].reverse()
    elif fault == "fake-origin":
        row["origins"][0]["offset"] += 1
    elif fault == "null-offset":
        row["origins"][-1]["offset"] = 0
    elif fault == "wrong-slot":
        row["slot"] = 31
    elif fault == "geometry":
        row["origins"][0]["four_point"] = True
    elif fault == "boolean-geometry":
        row["origins"][0]["four_point"] = 0
    elif fault == "unknown-status":
        room["reset_candidate_source_failure"] = "arbitrary"
    else:
        row["required"] = True
    with pytest.raises(ValueError, match="RE2 reset"):
        load_catalog(tmp_path, raw, document)


def test_source_copy_into_reset_payload_withholds_observation_without_claiming_absence():
    initial = item_command(20, 15, 9)
    reset = b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 10)
    # Copy is relative to its next instruction. Target the later reset's type.
    data, room = compile_synthetic(initial, reset, prefix=b"\x1d\x00\x00\x01")
    reset_at = room["reset_item_candidates"][0]["offset"]
    copy_at = room["programs"]["16:0"]["entry"]
    changed = bytearray(data)
    changed[copy_at + 2] = reset_at + 4 - copy_at - 4
    from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES

    from games.re2.room_data import decode_room

    room = decode_room(
        bytes(changed), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room.update(
        compile_reset_candidates(
            bytes(changed),
            room,
            CONFIG,
            RAW,
        )
    )
    assert room["reset_candidate_source_failure"] != "none"
    room["scenario_item_variants"] = []
    added = [
        r
        for r in tracking_item_candidates(room, CONFIG, selected=False)
        if r["global_id"] == 10
    ]
    assert added and not any(r["observable"] for r in added)
    assert not room["candidate_list_complete"]


@pytest.mark.parametrize(
    "macro,target_byte,blocked",
    [
        (b"\x09\x0a\x01\0", 1, True),
        (b"\x09\x0a\x01\0", 2, False),
        (b"\x0b\x0c", 1, True),
    ],
)
def test_source_copy_preserves_sleep_helper_opcodes_but_allows_duration(
    macro, target_byte, blocked
):
    from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES

    from games.re2.room_data import decode_room

    reset = b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 10)
    data, room, _ = source(
        b"\x1d\0\0\0" + macro + item_command(20, 15, 9) + END,
        (END, reset + END),
        (),
        (0,),
    )
    changed = bytearray(data)
    copy_at = room["programs"]["16:0"]["entry"]
    changed[copy_at + 2] = target_byte
    changed[copy_at + 3] = 0 if blocked else 1
    room = decode_room(
        bytes(changed), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room.update(compile_reset_candidates(bytes(changed), room, CONFIG, RAW))
    room["scenario_item_variants"] = []
    added = [
        row
        for row in tracking_item_candidates(room, CONFIG, selected=False)
        if row["global_id"] == 10
    ]
    assert added
    assert (room["reset_candidate_source_failure"] != "none") is blocked
    assert all(row["observable"] is not blocked for row in added)


@pytest.mark.parametrize(
    "room_id,old_gid,new_gid,diagnostic",
    [
        ("05-10", 46, 129, "pickup flag outside its bank"),
        ("03-01", 129, 5, "aliased RE2 event award and pickup"),
    ],
)
def test_reset_only_acquisitions_obey_bank_bounds_and_award_isolation(
    catalog, tmp_path, room_id, old_gid, new_gid, diagnostic
):
    raw, document, _ = catalog
    room = next(row for row in document["rooms"] if row["id"] == room_id)
    candidates = [
        row for row in room["reset_item_candidates"] if row["global_id"] == old_gid
    ]
    assert candidates
    for row in candidates:
        row["global_id"] = new_gid
    with pytest.raises(ValueError, match=diagnostic):
        load_catalog(tmp_path, raw, document)


def test_explicit_source_failure_retains_possible_rows_without_positive_authority():
    _, room = compile_synthetic(
        item_command(20, 15, 9), b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 10)
    )
    room["reset_candidate_source_failure"] = (
        ScenarioSelectionFailure.SourceMutation.value
    )
    assert not any(
        r["observable"]
        for r in tracking_item_candidates(room, CONFIG, selected=False)
        if r["global_id"] == 10
    )


@pytest.mark.parametrize(
    "name", ["re2_leon_a_slus00421", "re2_claire_b_slus00592", "re2_claire_b_slus00756"]
)
def test_other_revisions_do_not_implicitly_adopt_candidates(name):
    p = Re2Profile.load(ROOT / "profiles" / (name + ".json"))
    assert p.reset_candidate_policy is ResetCandidateSupport.Unaudited
    assert all("reset_item_candidates" not in r for r in p.rooms.values())
    raw = json.loads((ROOT / "profiles" / (name + ".json")).read_text())
    raw["reset_candidate_catalog"] = RAW["reset_candidate_catalog"]
    with pytest.raises(ValueError, match="revision opt-in"):
        reset_candidate_config(raw)


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["05-10"], indirect=True)
@pytest.mark.parametrize("same_type", [False, True])
def test_changed_gid_cannot_make_two_acquisition_ids_available(snapshot, same_type):
    p, _, put, read = snapshot
    room = p.rooms["05-10"]
    creator = next(r for r in room["items"] if r["global_id"] == 14)
    typ = creator["type"] if same_type else 24
    # Same-type changed-GID is a synthetic identity control, not an owned packet.
    next(r for r in room["reset_item_candidates"] if r["global_id"] == 46)["type"] = typ
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    pointer = 0x80100000 + creator["offset"] + 2
    put(registry + creator["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, 0x31, 1)
    put(pointer + 12, typ, 2)
    put(pointer + 14, 6, 2)
    put(pointer + 16, 46, 2)
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    rows = tracking_item_candidates(room, p.reset_candidate_policy, selected=True)
    ids = list(
        dict.fromkeys(
            r["global_id"]
            for r in rows
            if r["type"] < p.runtime_layout["file_type_min"]
        )
    )
    observed = dict(zip(ids, tracker.rooms["05-10"].items, strict=True))
    assert {gid: observed[gid].state for gid in (14, 46)} == {
        14: "unknown",
        46: "available",
    }
    assert sum(item.state == "available" for item in observed.values()) == 1
    assert not tracker.rooms["05-10"].list_complete
    visits = tracker.region_visits.copy()
    bank = p.flag_banks[p.runtime_layout["item_bank_late"]][0]
    for acquired, registered in [
        (False, False),
        (True, False),
        (False, False),
        (False, True),
    ]:
        put(registry + creator["slot"] * 4, pointer if registered else 0, 4)
        put(bank + 46 // 32 * 4, (0x80000000 >> (46 % 32)) if acquired else 0, 4)
        assert poll_re2(p, tracker, read).status is PollStatus.Display
        row = tracker.rooms["05-10"]
        assert row.items[ids.index(46)].state == (
            "taken" if acquired else "available" if registered else "unknown"
        )
        fresh = Tracker()
        assert poll_re2(p, fresh, read).status is PollStatus.Display
        assert fresh.rooms["05-10"] == row
        assert tracker.region_visits == visits
        assert row.completion is not RoomCompletion.Cleared


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
def test_unregistered_reset_candidate_rewinds_and_never_reveals_unvisited_room(
    snapshot,
):
    p, _, put, read = snapshot
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert "03-01" not in tracker.rooms and "05-10" not in tracker.rooms
    tracker.mark_current(RoomId(3, 1))
    bank = p.flag_banks[p.runtime_layout["item_bank_early"]][0]
    for acquired in (False, True, False):
        put(bank + 129 // 32 * 4, (0x80000000 >> (129 % 32)) if acquired else 0, 4)
        assert poll_re2(p, tracker, read).status is PollStatus.Display
        row = tracker.rooms["03-01"]
        candidate = row.items[-1]
        assert candidate.label == "Collectible"
        assert candidate.state == ("taken" if acquired else "unknown")
        assert not row.list_complete and row.completion is not RoomCompletion.Cleared
        fresh = Tracker()
        fresh.mark_current(RoomId(3, 1))
        assert poll_re2(p, fresh, read).status is PollStatus.Display
        assert fresh.rooms["03-01"] == row


def test_actual_owned_corpus_adds_exactly_two_identities_and_preserves_raw_proofs(
    owned,
):
    raw, _, _, _, sources, _, _, decoded = owned
    p = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00748.json")
    changes = {}
    reset_count = 0
    for key, room in p.rooms.items():
        compiled = compile_reset_candidates(
            sources[key],
            decoded[key],
            CONFIG,
            raw,
        )
        assert all(room[field] == value for field, value in compiled.items())
        before = {r["global_id"] for r in room["items"]}
        after = {
            r["global_id"]
            for r in tracking_item_candidates(room, CONFIG, selected=False)
        }
        if after != before:
            changes[key] = sorted(after - before)
        assert (
            room["candidate_list_complete"] == decoded[key]["candidate_list_complete"]
        )
        assert room["reset_item_variants"] == decoded[key]["reset_item_variants"]
        reset_count += len(room["reset_item_candidates"])
    assert changes == {"03-01": [129], "05-10": [46]}
    assert reset_count == 34


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-00"], indirect=True)
def test_sixteen_explicit_corners_preserve_existing_rows_clearance_doors_and_pose(
    snapshot,
):
    import itertools
    from dataclasses import replace

    from games.bit_flags import msb_flag_location

    p, _, put, read = snapshot
    legacy_rooms = copy.deepcopy(p.rooms)
    for room in legacy_rooms.values():
        for field in (
            "reset_item_candidates",
            "reset_candidate_descriptors",
            "reset_candidate_source_failure",
        ):
            del room[field]
    legacy = replace(
        p, rooms=legacy_rooms, reset_candidate_policy=ResetCandidateSupport.Unaudited
    )
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    for acquired, actor, story, keys in itertools.product((False, True), repeat=4):
        for bank in (
            p.runtime_layout["item_bank_early"],
            p.runtime_layout["item_bank_late"],
            p.runtime_layout["key_bank"],
        ):
            address, width = p.flag_banks[bank]
            enabled = keys if bank == p.runtime_layout["key_bank"] else acquired
            for offset in range(0, width, 4):
                put(address + offset, 0xFFFFFFFF if enabled else 0, 4)
        for bank, bit, enabled in ((6, 24, actor), (4, 7, story)):
            address, mask = msb_flag_location(p.flag_banks[bank][0], bit)
            value = int.from_bytes(read(address, 4).data, "little")
            put(address, value | mask if enabled else value & ~mask, 4)
        before = Tracker()
        for room in p.rooms.values():
            before.mark_current(RoomId(room["stage"], room["room"]))
        after = copy.deepcopy(before)
        assert poll_re2(legacy, before, read).status is PollStatus.Display
        assert poll_re2(p, after, read).status is PollStatus.Display
        changes = []
        for key in p.rooms:
            old, new = before.rooms[key], after.rooms[key]
            assert (
                old.completion == new.completion
                and old.list_complete == new.list_complete
            )
            if old.items != new.items:
                assert key in ("03-01", "05-10")
                assert old.items == new.items[:-1]
                assert new.items[-1].state == ("taken" if acquired else "unknown")
                changes.append(key)
            else:
                assert old == new
        assert changes == ["03-01", "05-10"]
        for field in (
            "doors",
            "current",
            "player_heading",
            "player_position",
            "region_visits",
        ):
            assert getattr(before, field) == getattr(after, field)


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["05-10"], indirect=True)
@pytest.mark.parametrize("four_point", [False, True])
@pytest.mark.parametrize(
    "binding", ["active", "inactive", "wrong-geometry", "unmodeled-gid"]
)
def test_current_nonitem_origins_require_fresh_geometry_and_identity(
    snapshot, four_point, binding
):
    p, _, put, read = snapshot
    room = p.rooms["05-10"]
    reset = next(r for r in room["reset_item_candidates"] if r["global_id"] == 46)
    # Fixture-only origins exercise the consumer. They are not owned-source or
    # native reachability claims. Four-point origins retain constructor geometry.
    slot = 0 if four_point else 1
    descriptors = (
        [
            {
                "offset": d["offset"],
                "slot": d["slot"],
                "opcode": 0x68,
                "four_point": True,
            }
            for d in room["doors"]
            if d["slot"] == slot
        ]
        if four_point
        else [{"offset": 4000, "slot": slot, "opcode": 0x2C, "four_point": False}]
    )
    room["reset_candidate_descriptors"] = sorted(
        room["reset_candidate_descriptors"] + descriptors, key=lambda d: d["offset"]
    )
    reset["slot"] = slot
    reset["origins"] = [
        {"kind": "descriptor", "offset": d["offset"], "four_point": d["four_point"]}
        for d in descriptors
    ] + [{"kind": "unregistered_null_alias"}]
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0)
    for index in range(32):
        put(registry + index * 4, 0, 4)
    pointer = 0x80100000 + descriptors[0]["offset"] + 2
    put(registry + slot * 4, pointer, 4)
    put(pointer, 2, 1)
    geometry = four_point != (binding == "wrong-geometry")
    sat = 0 if binding == "inactive" else 0x31
    put(pointer + 1, 0 if binding == "inactive" else sat | (0x80 if geometry else 0), 1)
    operand = 20 if four_point else 12
    put(pointer + operand, 24, 2)
    put(pointer + operand + 2, 6, 2)
    put(pointer + operand + 4, 129 if binding == "unmodeled-gid" else 46, 2)
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    row = tracker.rooms["05-10"]
    assert row.items[-1].state == ("available" if binding == "active" else "unknown")
    assert not row.list_complete
    assert row.completion is not RoomCompletion.Cleared


def test_compiler_rejects_source_and_reset_packet_drift():
    data, room = compile_synthetic(
        item_command(20, 15, 9), b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 10)
    )
    with pytest.raises(ValueError, match="source binding"):
        compile_reset_candidates(data[:-1] + bytes((data[-1] ^ 1,)), room, CONFIG, RAW)
    room["reset_item_candidates"][0]["global_id"] = 11
    with pytest.raises(ValueError, match="payload does not match"):
        compile_reset_candidates(data, room, CONFIG, RAW)


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["05-10"], indirect=True)
@pytest.mark.parametrize("exclusion", ["absence", "variant"])
def test_fresh_gid_avoids_false_contradiction_with_another_acquisition_proof(
    snapshot, exclusion
):
    p, _, put, read = snapshot
    room = p.rooms["05-10"]
    creator = next(r for r in room["items"] if r["global_id"] == 45 and r["slot"] == 6)
    next(r for r in room["reset_item_candidates"] if r["global_id"] == 46)["type"] = (
        creator["type"]
    )
    # Explicit synthetic proof fields isolate the reader's contradiction guard.
    if exclusion == "absence":
        room["scenario_absent_item_ids"] = [45]
    else:
        other = next(
            r for r in room["items"] if r["global_id"] == 45 and r["slot"] != 6
        )
        room["scenario_item_variants"] = [
            {"global_id": 45, "offsets": [other["offset"]]}
        ]
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    pointer = 0x80100000 + creator["offset"] + 2
    put(registry + creator["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, 0x31, 1)
    put(pointer + 12, creator["type"], 2)
    put(pointer + 14, 6, 2)
    put(pointer + 16, 46, 2)
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker.rooms["05-10"].items[-1].state == "available"


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["05-10"], indirect=True)
def test_reset_candidate_departure_reentry_uses_fresh_state_in_both_snapshots(snapshot):
    from types import SimpleNamespace

    from test_re2_tracking import snapshot as initialize_snapshot

    p, _, put, read = snapshot
    room = p.rooms["05-10"]
    creator = next(r for r in room["items"] if r["global_id"] == 14)
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    pointer = 0x80100000 + creator["offset"] + 2
    put(registry + creator["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, 0x31, 1)
    put(pointer + 12, 24, 2)
    put(pointer + 14, 6, 2)
    put(pointer + 16, 46, 2)
    # Two independently initialized synthetic snapshots model departure/load and
    # reentry. Neither comes from a real save or the user's exploration history.
    p, _, put_departed, read_departed = initialize_snapshot.__wrapped__(
        SimpleNamespace(param="00-01"), p
    )
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker.rooms["05-10"].items[-1].state == "available"
    bank = p.flag_banks[p.runtime_layout["item_bank_late"]][0]
    for acquired in (False, True, False):
        put_departed(
            bank + 46 // 32 * 4, (0x80000000 >> (46 % 32)) if acquired else 0, 4
        )
        assert poll_re2(p, tracker, read_departed).status is PollStatus.Display
        row = tracker.rooms["05-10"]
        assert row.items[-1].state == ("taken" if acquired else "unknown")
        fresh = Tracker()
        fresh.mark_current(RoomId(5, 0x10))
        assert poll_re2(p, fresh, read_departed).status is PollStatus.Display
        assert fresh.rooms["05-10"] == row
    put(pointer + 14, 2, 2)
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker.rooms["05-10"].items[-1].state == "available"
    assert tracker.rooms["05-10"].items[-1].quantity == 2
    assert set(tracker.rooms) == {"05-10", "00-01"}


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
def test_scripted_dispatch_cannot_transfer_a_receipt_to_a_changed_gid(
    dispatch_snapshot,
):
    p, _, put, read, _, item, pointer, _ = dispatch_snapshot
    room = p.rooms["01-04"]
    gid = 250
    assert gid not in {r["global_id"] for r in room["items"]}
    # Explicit fixture-only reset possibility isolates callback receipt binding.
    # The existing synthetic callback targets the old item, not this new GID.
    descriptor = {
        "offset": item["offset"],
        "slot": item["slot"],
        "opcode": 0x69 if item["four_point"] else 0x4E,
        "four_point": item["four_point"],
    }
    assert not room["reset_item_candidates"]
    room["reset_candidate_descriptors"] = [descriptor]
    room["reset_item_candidates"] = [
        {
            "offset": 200,
            "slot": item["slot"],
            "type": item["type"],
            "amount": item["amount"],
            "global_id": gid,
            "sat": 0x31,
            "origins": [
                {
                    "kind": "descriptor",
                    "offset": item["offset"],
                    "four_point": item["four_point"],
                },
                {"kind": "unregistered_null_alias"},
            ],
        }
    ]
    put(pointer + (24 if item["four_point"] else 16), gid, 2)
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker.rooms["01-04"].items[-1].state == "unknown"


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["05-10"], indirect=True)
def test_selected_creator_keeps_reset_quantity_alternatives_without_false_retry(
    snapshot,
):
    p, _, put, read = snapshot
    room = p.rooms["05-10"]
    creator = next(r for r in room["items"] if r["global_id"] == 14)
    room["scenario_item_variants"] = [{"global_id": 14, "offsets": [creator["offset"]]}]
    # Synthetic same-identity quantity variant isolates normalization. A selected
    # origin/type must retain its reset alternative when the live amount changes.
    next(r for r in room["reset_item_candidates"] if r["global_id"] == 14)["amount"] = 3
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    pointer = 0x80100000 + creator["offset"] + 2
    put(registry + creator["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, 0x31, 1)
    put(pointer + 12, creator["type"], 2)
    put(pointer + 14, 3, 2)
    put(pointer + 16, 14, 2)
    tracker = Tracker()
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker.rooms["05-10"].items[0].state == "available"
    assert tracker.rooms["05-10"].items[0].quantity == 3
