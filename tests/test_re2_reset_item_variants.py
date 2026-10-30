"""Reset-only identities preserve source declarations and acquisition identity."""

import copy
import json
import struct
from pathlib import Path

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    item_command,
)
from test_re2_room_write_partitions import END, source
from test_re2_tracking import profile as profile, snapshot as snapshot

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re2.live_tracking import poll_re2
from games.re2.re2_profile import Re2Profile
from games.re2.room_data import decode_room, reset_item_variants
from games.re2.scenario_items import item_identity_candidates, scenario_item_candidates
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus

ROOT = Path(__file__).resolve().parents[1]


def test_decoder_binds_reset_only_type_to_real_creators_without_rewriting_them():
    initial = item_command(20, 15, 9)
    reset = b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 9)
    _, room, _ = source(initial + END, (END, reset + END), (), (0,))
    (item,) = room["items"]
    (variant,) = room["reset_item_variants"]
    assert (item["type"], item["amount"], item["amounts"]) == (20, 15, [15])
    assert variant == {
        "offset": room["programs"]["17:1"]["entry"],
        "creator_offsets": [item["offset"]],
        "slot": 8,
        "type": 22,
        "amount": 8,
        "global_id": 9,
        "sat": 0x31,
    }
    assert not room["candidate_list_complete"]
    before = copy.deepcopy(room["items"])
    candidates = item_identity_candidates(room)
    assert [(row["offset"], row["type"], row["amounts"]) for row in candidates] == [
        (item["offset"], 20, [15]),
        (item["offset"], 22, [8]),
    ]
    assert room["items"] == before


@pytest.mark.parametrize(
    "fault",
    [
        "different-gid",
        "different-slot",
        "negative-slot",
        "past-registry",
        "geometry",
        "creator-geometry",
        "creator-kind",
        "already-declared",
    ],
)
def test_decoder_withholds_unbound_or_already_represented_reset_variants(fault):
    initial = bytearray(item_command(20, 15, 9))
    reset = bytearray(b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 9))
    if fault == "different-gid":
        struct.pack_into("<H", reset, 8, 10)
    elif fault == "different-slot":
        reset[1] = 7
    elif fault == "negative-slot":
        reset[1] = 255
    elif fault == "past-registry":
        reset[1] = 32
    elif fault == "geometry":
        reset[3] |= 0x80
    elif fault == "creator-geometry":
        initial[3] |= 0x80
    elif fault == "creator-kind":
        initial[2] = 0
    else:
        struct.pack_into("<H", reset, 4, 20)
    _, room, _ = source(bytes(initial) + END, (END, bytes(reset) + END), (), (0,))
    assert room["reset_item_variants"] == []


def test_decoder_reuses_all_matching_creators_and_keeps_existing_raw_variants():
    initial = item_command(20, 15, 9) + item_command(20, 30, 9)
    reset = b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 9)
    _, room, _ = source(initial + END, (END, reset + END), (), (0,))
    assert room["reset_item_variants"][0]["creator_offsets"] == sorted(
        row["offset"] for row in room["items"]
    )
    initial += item_command(22, 8, 9)
    _, room, _ = source(initial + END, (END, reset + END), (), (0,))
    assert room["reset_item_variants"] == []
    room["scenario_item_variants"] = [
        {"global_id": 9, "offsets": [room["items"][0]["offset"]]}
    ]
    assert scenario_item_candidates(room) == [room["items"][0]]


def test_decoder_rejects_a_decoded_reset_packet_that_drifted_from_source():
    reset = b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 9)
    data, room, _ = source(item_command(20, 15, 9) + END, (END, reset + END), (), (0,))
    room["programs"]["17:1"]["commands"][0]["data"][0] ^= 1
    with pytest.raises(ValueError, match="reset command"):
        reset_item_variants(data, room["items"], room["programs"])


def test_decoder_exports_one_variant_for_aliased_script_tables():
    reset = b"\x46\x08\x02\x31" + struct.pack("<3H", 22, 8, 9)
    data, room, _ = source(item_command(20, 15, 9) + reset + END, (END,), (), (0,))
    aliased = bytearray(data)
    struct.pack_into("<I", aliased, 8 + 17 * 4, room["section_offsets"][16])
    room = decode_room(
        bytes(aliased), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["programs"]["16:0"]["entry"] == room["programs"]["17:0"]["entry"]
    assert len(room["items"]) == len(room["reset_item_variants"]) == 1


@pytest.fixture
def catalog():
    path = ROOT / "profiles/re2_leon_a_slus00748.json"
    raw = json.loads(path.read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((path.parent / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    room = next(room for room in document["rooms"] if room["id"] == "00-11")
    assert len(room["reset_item_variants"]) == 1
    return raw, document, room


def load_catalog(tmp_path, raw, document):
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(raw | {"room_metadata_path": str(metadata)}))
    return Re2Profile.load(profile_path)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "not-list",
        "not-object",
        "duplicate",
        "overlap",
        "boolean-offset",
        "past-source",
        "wrong-creators",
        "empty-creators",
        "duplicate-creators",
        "slot",
        "gid",
        "same-type",
        "geometry",
        "amount",
        "type",
        "extra-field",
        "four-point",
        "proof-types",
        "proof-duplicate-types",
        "proof-scalar-type",
    ],
)
def test_catalog_rejects_unbound_reset_identity_and_puzzle_types(
    tmp_path, catalog, fault
):
    raw, document, room = catalog
    (variant,) = room["reset_item_variants"]
    if fault == "missing":
        del room["reset_item_variants"]
    elif fault == "not-list":
        room["reset_item_variants"] = None
    elif fault == "not-object":
        room["reset_item_variants"] = [None]
    elif fault == "duplicate":
        room["reset_item_variants"].append(variant)
    elif fault == "overlap":
        room["reset_item_variants"].append(variant | {"offset": variant["offset"] + 1})
    elif fault == "boolean-offset":
        variant["offset"] = True
    elif fault == "past-source":
        variant["offset"] = room["size"]
    elif fault == "wrong-creators":
        variant["creator_offsets"][0] += 1
    elif fault == "empty-creators":
        variant["creator_offsets"] = []
    elif fault == "duplicate-creators":
        variant["creator_offsets"] *= 2
    elif fault == "slot":
        variant["slot"] = 31
    elif fault == "gid":
        variant["global_id"] += 1
    elif fault == "same-type":
        variant["type"] = room["items"][0]["type"]
    elif fault == "geometry":
        variant["sat"] |= 0x80
    elif fault == "amount":
        variant["amount"] = 65536
    elif fault == "type":
        variant["type"] = 65536
    elif fault == "extra-field":
        variant["active"] = True
    elif fault == "four-point":
        room["items"][0]["four_point"] = True
    elif fault == "proof-types":
        room["known_puzzle_items"][0]["item_types"] = [57]
    elif fault == "proof-duplicate-types":
        room["known_puzzle_items"][0]["item_types"] = [57, 61, 61]
    else:
        room["known_puzzle_items"][0]["item_types"] = 57
    with pytest.raises(ValueError, match="RE2 (reset item|known puzzle-item)"):
        load_catalog(tmp_path, raw, document)


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
def test_reset_only_puzzle_target_remains_generic_and_rewinds(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0x11))
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    story = profile.flag_banks[4][0]
    for acquired, activated in [
        (False, False),
        (False, True),
        (True, True),
        (False, False),
    ]:
        put(bank + 4, 0x100 if acquired else 0, 4)
        put(story + 4, 0x100 if activated else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        room = tracker.rooms["00-11"]
        (item,) = room.items
        assert (item.label, item.state, item.quantity, item.quantity_is_unit_count) == (
            "Collectible",
            "taken" if acquired else "uncollected",
            ItemQuantityState.Unreconstructed,
            False,
        )
        assert not room.list_complete
        assert room.completion is (
            RoomCompletion.Unknown if acquired else RoomCompletion.Incomplete
        )
        fresh = Tracker()
        fresh.mark_current(RoomId(0, 0x11))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms["00-11"] == room


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-11"], indirect=True)
@pytest.mark.parametrize("item_type,gid", [(57, 55), (61, 55), (62, 55), (61, 56)])
def test_current_reset_payload_selects_only_bound_live_identity(
    snapshot, item_type, gid
):
    profile, _, put, read = snapshot
    definition = profile.rooms["00-11"]["items"][0]
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    pointer = 0x80100000 + definition["offset"] + 2
    put(registry + definition["slot"] * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, 0x31, 1)
    put(pointer + 12, item_type, 2)
    put(pointer + 16, gid, 2)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    room = tracker.rooms["00-11"]
    (item,) = room.items
    if item_type in (57, 61) and gid == 55:
        assert (item.label, item.state, item.quantity) == (
            profile.names["items"][str(item_type)],
            "available",
            1,
        )
    else:
        assert (item.label, item.state, item.quantity) == (
            "Collectible",
            "uncollected",
            ItemQuantityState.Unreconstructed,
        )
        assert not room.doors_complete


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-11"], indirect=True)
def test_inactive_or_collected_reset_payload_does_not_cache_a_specific_identity(
    snapshot,
):
    profile, _, put, read = snapshot
    definition = profile.rooms["00-11"]["items"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    put(pointer + 12, 61, 2)
    for acquired, kind in [(False, 2), (True, 0), (False, 2)]:
        put(pointer, kind, 1)
        put(pointer + 1, 0, 1)
        put(bank + 4, 0x100 if acquired else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        room = tracker.rooms["00-11"]
        (item,) = room.items
        assert (item.label, item.state, item.quantity) == (
            "Collectible",
            "taken" if acquired else "uncollected",
            ItemQuantityState.Unreconstructed,
        )
        assert not room.list_complete
        assert room.completion is (
            RoomCompletion.Unknown if acquired else RoomCompletion.Incomplete
        )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-11"], indirect=True)
def test_reset_identity_does_not_bypass_live_geometry_binding(snapshot):
    profile, _, put, read = snapshot
    pointer = 0x80100000 + profile.rooms["00-11"]["items"][0]["offset"] + 2
    put(pointer + 1, 0xB1, 1)
    put(pointer + 12, 61, 2)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    room = tracker.rooms["00-11"]
    (item,) = room.items
    assert item.label == "Collectible" and item.state == "uncollected"
    assert not room.doors_complete


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-11"], indirect=True)
def test_reset_payload_coherence_failure_preserves_the_previous_publication(snapshot):
    profile, _, put, read = snapshot
    definition = profile.rooms["00-11"]["items"][0]
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    pointer = 0x80100000 + definition["offset"] + 2
    put(registry + definition["slot"] * 4, pointer, 4)
    put(pointer + 1, 0x31, 1)
    put(pointer + 12, 61, 2)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    reads = 0

    def torn(address, width):
        nonlocal reads
        if (address, width) == (pointer, 18):
            reads += 1
            if reads > 1:
                put(pointer + 12, 62, 2)
        return read(address, width)

    assert poll_re2(profile, tracker, torn).status is PollStatus.Retry
    assert tracker == before
