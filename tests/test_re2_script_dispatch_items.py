"""Current code/binding witnesses for parked pickups, RE2-DISPATCH-001."""

import hashlib
import json
import struct
import copy
from dataclasses import replace

import pytest
from test_re2_tracking import profile as profile, snapshot as snapshot
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    ROOT,
    item_command,
    synthetic_room,
)

from games.re2.room_data import decode_room
from games.re2.script_dispatch_items import (
    ScriptItemDispatchConfig,
    ScriptItemDispatchSupport,
    script_dispatch_relations,
    script_item_dispatch,
)
from games.re2.live_tracking import poll_re2
from emulator.duckstation_gdb import MemRead
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


def if_else(test, yes, no):
    return (
        bytes([6, 0])
        + struct.pack("<H", len(test) + len(yes) + 4)
        + test
        + yes
        + bytes([7, 0])
        + struct.pack("<H", len(no) + 4)
        + no
    )


@pytest.fixture
def dispatch_source():
    def build(case, four_point=False):
        message = bytes.fromhex("2b000200ffff")
        dispatch = bytes([0x47, 4])
        callback = (
            if_else(
                bytes([0x21, 4, 7, 0]),
                bytes([0x22, 4, 7, 1]) + message,
                if_else(bytes([0x21, 8, 9, 0]), dispatch, message),
            )
            + b"\x01\0"
        )
        if case == "immediate":
            callback = dispatch + b"\x01\0"
        elif case == "missing-progress":
            callback = if_else(bytes([0x21, 4, 7, 0]), message, dispatch) + b"\x01\0"
        elif case == "other-dispatch":
            callback = (
                if_else(bytes([0x21, 4, 7, 0]), bytes([0x47, 3]), dispatch) + b"\x01\0"
            )
        elif case == "cycle":
            callback = bytes([0x22, 4, 7, 7]) + message + b"\x01\0"
        elif case in (
            "acquisition-set",
            "acquisition-clear",
            "acquisition-toggle",
            "acquisition-alias",
        ):
            operation = {
                "acquisition-set": 1,
                "acquisition-clear": 0,
                "acquisition-toggle": 7,
                "acquisition-alias": 1,
            }[case]
            callback = (
                bytes([0x22, 99 if case == "acquisition-alias" else 8, 9, operation])
                + dispatch
                + b"\x01\0"
            )
        elif case == "copy":
            callback = bytes([0x1D, 0, 0, 0]) + dispatch + b"\x01\0"
        elif case == "call":
            callback = bytes([0x18, 0]) + dispatch + b"\x01\0"
        elif case in ("stop-write", "system-alias-write"):
            callback = (
                bytes([0x22, 2 if case == "stop-write" else 4, 0, 1])
                + dispatch
                + b"\x01\0"
            )
        elif case == "invalid-write":
            callback = bytes([0x22, 4, 7, 2]) + dispatch + b"\x01\0"
        elif case in ("invalid-check", "unknown-bank", "outside-bit"):
            test = bytes(
                [
                    0x21,
                    255 if case == "unknown-bank" else 1,
                    255 if case == "outside-bit" else 1,
                    2 if case == "invalid-check" else 0,
                ]
            )
            callback = if_else(test, dispatch, dispatch) + b"\x01\0"
        elif case == "orphan-endif":
            callback = b"\x08\0" + dispatch + b"\x01\0"
        elif case == "early-end":
            callback = if_else(bytes([0x21, 4, 7, 0]), b"\x01\0", dispatch) + b"\x01\0"
        elif case == "nine-flags":
            callback = b""
            for bit in range(9):
                callback += if_else(bytes([0x21, 4, bit, 0]), b"\0", b"\0")
            callback += dispatch + b"\x01\0"
        elif case == "if-depth-nine":
            callback = dispatch
            for _ in range(9):
                callback = if_else(bytes([0x21, 4, 7, 0]), callback, dispatch)
            callback += b"\x01\0"
        elif case == "too-many-steps":
            callback = bytes(300) + dispatch + b"\x01\0"

        pickup = bytearray(item_command(20, 15, 9, slot=4))
        pickup[3] = 0
        struct.pack_into("<4h", pickup, 6, 32000, 32000, 1, 1)
        creator = bytes(
            [0x67 if four_point else 0x2C, 6, 5, 0xB1 if four_point else 0x31]
        )
        creator += bytes(18 if four_point else 10) + bytes([0xFF, 0, 0x18, 1, 0, 0])
        if case == "noncanonical":
            creator = creator[:-1] + b"\x01"
        elif case == "missing-procedure":
            creator = creator[:-3] + bytes([9, 0, 0])
        elif case == "bad-target-slot":
            pickup[1] = 32
            callback = bytes([0x47, 32, 1, 0])
        unrelated = b"\x01\0"
        if case == "copy-elsewhere":
            unrelated = bytes([0x1D, 0, 2, 0, 0x32, 0]) + bytes(6) + b"\x01\0"
        data = bytearray(
            synthetic_room(bytes(pickup) + creator + b"\x01\0", (unrelated, callback))
        )
        text = b"\xfa\x02\x01\xee\x02\xef\x03\xf0\x04\xf9\x05\xfc\xfd\0\xfe\0"
        for section in (13, 14):
            struct.pack_into("<I", data, 8 + section * 4, len(data))
            data.extend(
                struct.pack("<4H", 8, 10, 12, 12 + len(text))
                + b"\xfe\0" * 2
                + text
                + b"\xfe\0"
            )
        data = bytes(data)
        room = decode_room(
            data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
        )
        profile = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
        banks = {
            row["bank"]: (int(row["address_ps1"], 0), row["width"])
            for row in profile["flag_banks"]
        }
        banks[99] = banks[8]
        return data, room, banks

    return build


@pytest.mark.parametrize("case", ["repeat", "immediate", "copy-elsewhere"])
@pytest.mark.parametrize("four_point", [False, True])
def test_dispatch_relation_proves_all_initial_flags_with_parked_item(
    dispatch_source, case, four_point
):
    data, room, banks = dispatch_source(case, four_point)
    relations = script_dispatch_relations(
        data, room, 8, banks, 32, dispatch_config(banks)
    )
    assert len(relations) == 1
    relation = relations[0]
    assert relation["item_offset"] == room["items"][0]["offset"]
    assert relation["target_slot"] == 4 and relation["callback_slot"] == 6
    assert relation["callback_four_point"] is four_point
    assert relation["procedure"] == 1
    for key in ("program_proof", "table_proof", "callback_proof"):
        proof = relation[key]
        assert (
            hashlib.sha256(
                data[proof["offset"] : proof["offset"] + proof["width"]]
            ).hexdigest()
            == proof["sha256"]
        )
    assert relation["table_proof"]["width"] == 2


@pytest.mark.parametrize(
    "case",
    [
        "missing-progress",
        "other-dispatch",
        "cycle",
        "acquisition-set",
        "acquisition-clear",
        "acquisition-toggle",
        "acquisition-alias",
        "copy",
        "call",
        "invalid-write",
        "invalid-check",
        "unknown-bank",
        "outside-bit",
        "orphan-endif",
        "early-end",
        "nine-flags",
        "if-depth-nine",
        "too-many-steps",
        "noncanonical",
        "missing-procedure",
        "bad-target-slot",
    ],
)
def test_unproved_or_mutating_callbacks_do_not_establish_presence(
    dispatch_source, case
):
    data, room, banks = dispatch_source(case)
    assert (
        script_dispatch_relations(data, room, 8, banks, 32, dispatch_config(banks))
        == []
    )


def test_callback_table_entry_drift_cannot_reuse_the_old_body_proof(dispatch_source):
    original, room, banks = dispatch_source("repeat")
    relations = script_dispatch_relations(
        original, room, 8, banks, 32, dispatch_config(banks)
    )
    assert len(relations) == 1
    data = bytearray(original)
    table = room["section_offsets"][17]
    entry = relations[0]["table_proof"]["offset"]
    data[entry : entry + 2] = data[table : table + 2]
    assert (
        script_dispatch_relations(
            bytes(data), room, 8, banks, 32, dispatch_config(banks)
        )
        == []
    )


def test_callback_final_message_uses_the_actual_entry_without_a_synthetic_successor(
    dispatch_source,
):
    original, room, banks = dispatch_source("repeat")
    data = bytearray(original)
    for row in room["programs"]["17:1"]["commands"]:
        if row["opcode"] == 0x2B:
            data[row["offset"] + 2] = 3
    relations = script_dispatch_relations(
        bytes(data), room, 8, banks, 32, dispatch_config(banks)
    )
    assert len(relations) == 1
    proofs = relations[0]["message_proofs"]
    for section in (13, 14):
        table = room["section_offsets"][section]
        entry = next(proof for proof in proofs if proof["offset"] == table + 6)
        assert entry["width"] == 2
        start = table + int.from_bytes(data[table + 6 : table + 8], "little")
        text = next(proof for proof in proofs if proof["offset"] == start)
        assert (
            text["width"] == 2
            and text["sha256"] == hashlib.sha256(b"\xfe\0").hexdigest()
        )


@pytest.mark.parametrize("case", ["self-slot", "oversized-body", "aliased-program"])
def test_compiler_only_emits_loadable_unique_relations(dispatch_source, case):
    data, room, banks = dispatch_source("immediate")
    callback = next(
        row
        for row in room["programs"]["16:0"]["commands"]
        if row["kind"] == "interaction"
    )
    if case == "self-slot":
        callback["slot"] = room["items"][0]["slot"]
    elif case == "oversized-body":
        room["programs"]["17:1"]["limit"] = room["programs"]["17:1"]["entry"] + 4097
    else:
        room["programs"]["aliased"] = room["programs"]["16:0"]
    relations = script_dispatch_relations(
        data, room, 8, banks, 32, dispatch_config(banks)
    )
    assert len(relations) == (1 if case == "aliased-program" else 0)


def dispatch_config(banks):
    return ScriptItemDispatchConfig(0x800D8CBC, (banks[4], banks[8]))


@pytest.mark.parametrize("bank", [4, 8])
def test_messages_cannot_assume_system_or_aliased_guard_flags_are_preserved(
    dispatch_source, bank
):
    data, room, banks = dispatch_source("repeat")
    config = dispatch_config(banks)
    banks[bank] = banks[0]
    assert script_dispatch_relations(data, room, 8, banks, 32, config) == []


@pytest.mark.parametrize("case", ["stop-write", "system-alias-write"])
def test_callbacks_cannot_write_native_scheduler_control_words(dispatch_source, case):
    data, room, banks = dispatch_source(case)
    config = dispatch_config(banks)
    if case == "system-alias-write":
        banks[4] = banks[0]
    assert script_dispatch_relations(data, room, 8, banks, 32, config) == []


@pytest.mark.parametrize("section", [13, 14])
@pytest.mark.parametrize(
    "mutation",
    [
        "choice",
        "name",
        "return",
        "conditional",
        "missing-operand",
        "missing-end",
        "trailing-control",
        "odd-directory",
        "missing-entry",
        "backward-entry",
        "outside-resource",
        "mode",
        "stop-mask",
        "padding",
    ],
)
def test_messages_require_both_bounded_nonchoice_resources(
    dispatch_source, section, mutation
):
    original, room, banks = dispatch_source("repeat")
    data = bytearray(original)
    table = room["section_offsets"][section]
    start = table + int.from_bytes(data[table + 4 : table + 6], "little")
    end = table + int.from_bytes(data[table + 6 : table + 8], "little")
    if mutation in ("choice", "name", "return"):
        data[start] = {"choice": 0xFB, "name": 0xF8, "return": 0xF7}[mutation]
    elif mutation == "conditional":
        data[start : start + 2] = b"\xfa\0"
    elif mutation == "missing-operand":
        data[end - 2 : end] = b"\0\xee"
    elif mutation == "missing-end":
        data[start:end] = bytes(end - start)
    elif mutation == "trailing-control":
        data[start : start + 2] = b"\xfe\0"
    elif mutation == "padding":
        data[start:end] = b"\xfe\0" + bytes(end - start - 2)
    elif mutation == "odd-directory":
        data[table] = 9
    elif mutation == "missing-entry":
        data[table : table + 2] = b"\x04\0"
    elif mutation == "backward-entry":
        data[table + 6 : table + 8] = b"\x08\0"
    elif mutation == "outside-resource":
        data[table + 6 : table + 8] = b"\xff\xff"
    else:
        message = next(
            row for row in room["programs"]["17:1"]["commands"] if row["opcode"] == 0x2B
        )
        data[message["offset"] + (3 if mutation == "mode" else 4)] = 1
    relations = script_dispatch_relations(
        bytes(data), room, 8, banks, 32, dispatch_config(banks)
    )
    assert bool(relations) is (mutation == "padding")
    if relations:
        assert len(relations[0]["message_proofs"]) == 4


def test_dispatch_configuration_is_explicit():
    assert script_item_dispatch({}) is ScriptItemDispatchSupport.Unaudited
    raw = {
        "script_item_dispatch": {
            "main_table_address_ps1": "0x800D8CBC",
            "message_preserved_flag_ranges": [
                {"address_ps1": "0x800D4874", "width": 8}
            ],
        }
    }
    assert script_item_dispatch(raw) == ScriptItemDispatchConfig(
        0x800D8CBC, ((0x800D4874, 8),)
    )


@pytest.mark.parametrize(
    "profile_id",
    [
        "re2_leon_a_slus00748",
        "re2_claire_b_slus00756",
        "re2_leon_a_slus00421",
        "re2_claire_b_slus00592",
    ],
)
def test_dispatch_native_capability_does_not_spread_to_unaudited_revisions(profile_id):
    from games.re2.re2_profile import Re2Profile

    loaded = Re2Profile.load(ROOT / "profiles" / f"{profile_id}.json")
    if profile_id == "re2_leon_a_slus00748":
        assert loaded.script_item_dispatch == ScriptItemDispatchConfig(
            0x800D8CBC, ((0x800D4874, 8), (0x800D48BC, 32))
        )
        assert [
            (key, len(room["script_item_dispatch_relations"]))
            for key, room in loaded.rooms.items()
            if room["script_item_dispatch_relations"]
        ] == [("00-09", 1), ("01-04", 1)]
    else:
        assert loaded.script_item_dispatch is ScriptItemDispatchSupport.Unaudited
        assert not any(
            room.get("script_item_dispatch_relations", [])
            for room in loaded.rooms.values()
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        {},
        [],
        {"main_table_address_ps1": "0x800D8CBC"},
        {"main_table_address_ps1": "oops", "message_preserved_flag_ranges": []},
        {"main_table_address_ps1": "0x800D8CBD", "message_preserved_flag_ranges": []},
        {"main_table_address_ps1": "0x800D8CBC", "message_preserved_flag_ranges": []},
        {
            "main_table_address_ps1": "0x800D8CBC",
            "message_preserved_flag_ranges": [
                {"address_ps1": "0x800D4874", "width": True}
            ],
        },
        {
            "main_table_address_ps1": "0x800D8CBC",
            "message_preserved_flag_ranges": [{"address_ps1": "0x800D4874", "width": 8}]
            * 2,
        },
    ],
)
def test_dispatch_configuration_rejects_missing_or_malformed_contract(value):
    with pytest.raises(ValueError):
        script_item_dispatch({"script_item_dispatch": value})


@pytest.fixture
def dispatch_snapshot(snapshot):
    profile, ram, put, read = snapshot
    room = copy.deepcopy(profile.rooms["01-04"])
    item = next(item for item in room["items"] if item["global_id"] == 3)
    base = 0x80100000
    body = bytes([0x47, item["slot"], 1, 0])
    program_offset = room["section_offsets"][17] + 0x1000
    entry = room["section_offsets"][17] + 2
    table = (program_offset - room["section_offsets"][17]).to_bytes(2, "little")
    relation = {
        "item_offset": item["offset"],
        "callback_offset": room["section_offsets"][17] + 0x1200,
        "callback_slot": 31,
        "callback_four_point": False,
        "target_slot": item["slot"],
        "procedure": 1,
        "message_proofs": [],
        "callback_proof": {
            "offset": room["section_offsets"][17] + 0x1202,
            "width": 18,
            "sha256": hashlib.sha256(
                bytes([5, 0x31]) + bytes(10) + bytes([0xFF, 0, 0x18, 1, 0, 0])
            ).hexdigest(),
        },
        "table_proof": {
            "offset": entry,
            "width": 2,
            "sha256": hashlib.sha256(table).hexdigest(),
        },
        "program_proof": {
            "offset": program_offset,
            "width": len(body),
            "sha256": hashlib.sha256(body).hexdigest(),
        },
    }
    room["script_item_dispatch_relations"] = [relation]
    profile = replace(
        profile,
        rooms={
            key: {
                **value,
                "script_item_dispatch_relations": [relation] if key == "01-04" else [],
            }
            for key, value in profile.rooms.items()
        },
        script_item_dispatch=dispatch_config(profile.flag_banks),
    )
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + 4 * slot, 0, 4)
    target = base + item["offset"] + 2
    callback = base + relation["callback_offset"] + 2
    put(registry + 4 * item["slot"], target, 4)
    put(target, 2, 1)
    put(target + 1, 0x80 if item["four_point"] else 0, 1)
    put(registry + 4 * relation["callback_slot"], callback, 4)
    put(callback, 5, 1)
    put(callback + 1, 0x31, 1)
    put(callback + 12, int.from_bytes(bytes([0xFF, 0, 0x18, 1, 0, 0]), "little"), 6)
    put(base + entry, int.from_bytes(table, "little"), 2)
    put(base + program_offset, int.from_bytes(body, "little"), len(body))
    put(
        profile.script_item_dispatch.main_table_address,
        base + room["section_offsets"][17],
        4,
    )
    for section in (13, 14):
        table = room["section_offsets"][section]
        for offset, packet in (
            (table + 4, struct.pack("<2H", 32, 34)),
            (table + 32, b"\xfe\0"),
        ):
            put(base + offset, int.from_bytes(packet, "little"), len(packet))
            relation["message_proofs"].append(
                {
                    "offset": offset,
                    "width": len(packet),
                    "sha256": hashlib.sha256(packet).hexdigest(),
                }
            )
    return profile, ram, put, read, relation, item, target, callback


@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
def test_parked_dispatched_pickup_rewinds_and_is_not_cached_after_departure(
    dispatch_snapshot,
):
    profile, _, put, read, _, item, target, _ = dispatch_snapshot
    tracker = Tracker()
    bank, _ = profile.flag_banks[profile.runtime_layout["item_bank_early"]]
    word, mask = (
        bank + item["global_id"] // 32 * 4,
        0x80000000 >> (item["global_id"] % 32),
    )
    label = profile.names["items"][str(item["type"])]
    for taken in (False, True, False):
        put(word, mask if taken else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        observed = next(
            row for row in tracker.rooms["01-04"].items if row.label == label
        )
        assert (observed.state, observed.quantity) == (
            "taken" if taken else "uncollected",
            item["amount"],
        )
        if not taken:
            assert tracker.rooms["01-04"].completion is RoomCompletion.Incomplete
    # A regular live SAT still means Available. The new witness does not
    # replace the native activation semantics used for ordinary pickups.
    put(target + 1, 0x31 | (0x80 if item["four_point"] else 0), 1)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert (
        next(row for row in tracker.rooms["01-04"].items if row.label == label).state
        == "available"
    )
    # Change room through an independently initialized synthetic snapshot.
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    destination = profile.rooms["00-01"]
    put(profile.stage_address, 0, 2)
    put(profile.room_address, 1, 2)
    for index, offset in enumerate(destination["section_offsets"]):
        put(0x80100008 + index * 4, 0x80100000 + offset if offset else 0, 4)
    for proof in destination["proofs"]:
        for offset in range(proof["width"]):
            put(0x80100000 + proof["offset"] + offset, 0, 1)
    destination = copy.deepcopy(destination)
    for proof in destination["proofs"]:
        proof["sha256"] = hashlib.sha256(bytes(proof["width"])).hexdigest()
    profile = replace(profile, rooms={**profile.rooms, "00-01": destination})
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert (
        next(row for row in tracker.rooms["01-04"].items if row.label == label).state
        == "unknown"
    )


@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
def test_conflicting_regular_and_dispatched_items_do_not_invent_one_identity(
    dispatch_snapshot,
):
    profile, _, put, read, _, item, _, _ = dispatch_snapshot
    room = copy.deepcopy(profile.rooms["01-04"])
    alternative = {
        **item,
        "offset": room["section_offsets"][17] + 0x1300,
        "slot": 30,
        "type": 1,
        "amount": 9,
        "amounts": [9],
        "four_point": False,
    }
    room["items"].append(alternative)
    profile = replace(profile, rooms={**profile.rooms, "01-04": room})
    pointer = 0x80100000 + alternative["offset"] + 2
    put(int(profile.runtime_layout["aot_table_address_ps1"], 0) + 30 * 4, pointer, 4)
    put(pointer, 2, 1)
    put(pointer + 1, 0x31, 1)
    for index, field in enumerate(("type", "amount", "global_id")):
        put(pointer + 12 + index * 2, alternative[field], 2)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    generic = next(
        row for row in tracker.rooms["01-04"].items if row.label == "Collectible"
    )
    assert generic.state == "unknown"
    from games.item_quantity import ItemQuantityState

    assert generic.quantity is ItemQuantityState.Unreconstructed
    assert not tracker.rooms["01-04"].list_complete


@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
@pytest.mark.parametrize(
    "mutation",
    [
        "main-table",
        "entry",
        "body",
        "callback-kind",
        "callback-sat",
        "callback-geometry",
        "callback-floor",
        "callback-rectangle",
        "text-table",
        "text",
        "callback-payload",
        "callback-binding",
        "item-type",
        "item-id",
        "item-binding",
        "unaudited",
    ],
)
def test_dispatch_requires_fresh_code_table_and_both_exact_bindings(
    dispatch_snapshot, mutation
):
    profile, _, put, read, relation, item, target, callback = dispatch_snapshot
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    if mutation == "main-table":
        put(profile.script_item_dispatch.main_table_address, 0, 4)
    elif mutation in ("entry", "body"):
        proof = relation["table_proof" if mutation == "entry" else "program_proof"]
        put(0x80100000 + proof["offset"], 0, proof["width"])
    elif mutation == "callback-kind":
        put(callback, 4, 1)
    elif mutation == "callback-sat":
        put(callback + 1, 0, 1)
    elif mutation == "callback-geometry":
        put(callback + 1, 0xB1, 1)
    elif mutation in ("callback-floor", "callback-rectangle"):
        put(callback + (3 if mutation == "callback-floor" else 4), 1, 1)
    elif mutation in ("text-table", "text"):
        proof = relation["message_proofs"][0 if mutation == "text-table" else 1]
        put(0x80100000 + proof["offset"], 0, proof["width"])
    elif mutation == "callback-payload":
        put(callback + 15, 2, 1)
    elif mutation == "callback-binding":
        put(registry + relation["callback_slot"] * 4, 0, 4)
    elif mutation in ("item-type", "item-id"):
        put(
            target
            + (20 if item["four_point"] else 12)
            + (4 if mutation == "item-id" else 0),
            255,
            2,
        )
    elif mutation == "item-binding":
        put(registry + relation["target_slot"] * 4, 0, 4)
    else:
        profile = replace(
            profile, script_item_dispatch=ScriptItemDispatchSupport.Unaudited
        )
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    label = profile.names["items"][str(item["type"])]
    assert (
        next(row for row in tracker.rooms["01-04"].items if row.label == label).state
        == "unknown"
    )


@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
@pytest.mark.parametrize(
    "field",
    ["main-table", "table_proof", "program_proof", "callback", "text-table", "text"],
)
@pytest.mark.parametrize("failure", ["failed", "short", "torn"])
def test_dispatch_consumed_reads_are_atomic(dispatch_snapshot, field, failure):
    profile, _, _, read, relation, _, _, callback = dispatch_snapshot
    if field == "main-table":
        address, width = profile.script_item_dispatch.main_table_address, 4
    elif field == "callback":
        address, width = callback, 18
    elif field in ("text-table", "text"):
        proof = relation["message_proofs"][0 if field == "text-table" else 1]
        address, width = 0x80100000 + proof["offset"], proof["width"]
    else:
        proof = relation[field]
        address, width = 0x80100000 + proof["offset"], proof["width"]
    calls = 0

    def faulty(address_read, width_read):
        nonlocal calls
        result = read(address_read, width_read)
        if (address_read, width_read) == (address, width):
            calls += 1
            if failure == "failed":
                return MemRead(False, b"", "disconnected")
            if failure == "short":
                return MemRead(True, result.data[:-1])
            if calls > 1:
                return MemRead(True, bytes([result.data[0] ^ 1]) + result.data[1:])
        return result

    tracker = Tracker()
    before = copy.deepcopy(tracker)
    assert poll_re2(profile, tracker, faulty).status is (
        PollStatus.Retry if failure == "torn" else PollStatus.ReadFailure
    )
    assert tracker == before


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "missing-capability",
        "capability-drift",
        "missing-room-field",
        "not-list",
        "extra-relation-field",
        "boolean-slot",
        "unknown-item",
        "wrong-slot",
        "same-slot",
        "callback-outside",
        "bad-geometry",
        "procedure-outside",
        "directory-offset",
        "directory-width",
        "directory-body-mismatch",
        "body-outside",
        "body-too-wide",
        "bad-hash",
        "boolean-width",
        "duplicate",
    ],
)
def test_catalog_dispatch_contract_is_required_bounded_and_bound_to_revision(
    tmp_path, case
):
    from games.re2.re2_profile import Re2Profile

    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    document = json.loads((ROOT / "profiles" / raw["room_metadata_path"]).read_text())
    config = {
        "main_table_address_ps1": "0x800D8CBC",
        "message_preserved_flag_ranges": [{"address_ps1": "0x800CC9C0", "width": 8}],
    }
    raw["script_item_dispatch"] = config
    document["script_item_dispatch"] = copy.deepcopy(config)
    for room in document["rooms"]:
        room["script_item_dispatch_relations"] = []
    room = next(row for row in document["rooms"] if row["id"] == "01-04")
    item = next(row for row in room["items"] if row["global_id"] == 3)
    table = room["section_offsets"][17]
    relation = {
        "item_offset": item["offset"],
        "callback_offset": table + 0x1200,
        "callback_slot": 31,
        "callback_four_point": False,
        "target_slot": item["slot"],
        "procedure": 1,
        "message_proofs": [],
        "callback_proof": {
            "offset": table + 0x1202,
            "width": 18,
            "sha256": hashlib.sha256(
                bytes([5, 0x31]) + bytes(10) + bytes([0xFF, 0, 0x18, 1, 0, 0])
            ).hexdigest(),
        },
        "table_proof": {
            "offset": table + 2,
            "width": 2,
            "sha256": hashlib.sha256(b"\0\x10").hexdigest(),
        },
        "program_proof": {
            "offset": table + 0x1000,
            "width": 4,
            "sha256": hashlib.sha256(bytes([0x47, item["slot"], 1, 0])).hexdigest(),
        },
    }
    room["script_item_dispatch_relations"] = [relation]
    if case == "missing-capability":
        del document["script_item_dispatch"]
    elif case == "capability-drift":
        document["script_item_dispatch"]["main_table_address_ps1"] = "0x800D8CC0"
    elif case == "missing-room-field":
        del room["script_item_dispatch_relations"]
    elif case == "not-list":
        room["script_item_dispatch_relations"] = None
    elif case == "extra-relation-field":
        relation["guess"] = True
    elif case == "boolean-slot":
        relation["target_slot"] = True
    elif case == "unknown-item":
        relation["item_offset"] += 1
    elif case == "wrong-slot":
        relation["target_slot"] = 30
    elif case == "same-slot":
        relation["callback_slot"] = relation["target_slot"]
    elif case == "callback-outside":
        relation["callback_offset"] = room["size"] - 19
    elif case == "bad-geometry":
        relation["callback_four_point"] = 0
    elif case == "procedure-outside":
        relation["procedure"] = 256
    elif case == "directory-offset":
        relation["table_proof"]["offset"] += 2
    elif case == "directory-width":
        relation["table_proof"]["width"] = 4
    elif case == "directory-body-mismatch":
        relation["program_proof"]["offset"] += 2
    elif case == "body-outside":
        relation["program_proof"]["offset"] = room["size"] - 3
    elif case == "body-too-wide":
        relation["program_proof"]["width"] = 4097
    elif case == "bad-hash":
        relation["program_proof"]["sha256"] = "unverified"
    elif case == "boolean-width":
        relation["program_proof"]["width"] = True
    elif case == "duplicate":
        room["script_item_dispatch_relations"].append(copy.deepcopy(relation))
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    for field in ("names_path", "floor_plans_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    if case == "valid":
        assert Re2Profile.load(path).script_item_dispatch == ScriptItemDispatchConfig(
            0x800D8CBC, ((0x800CC9C0, 8),)
        )
    else:
        with pytest.raises(ValueError, match="dispatch"):
            Re2Profile.load(path)
