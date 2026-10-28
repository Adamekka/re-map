"""RE2-STARTUP-001: source-bound setup and collective pickup presence."""

import copy
import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    ROOT,
    item_command,
    synthetic_room,
)

from games.re2.clip_effect_proof import ClipEffectSupport, clipping_effect_proof
from games.re2.event_presence import source_presence
from games.re2.room_data import collection_presence, decode_room
from games.re2.room_write_partitions import ScaWritePartition, sca_write_partition
from games.re2.scenario_items import (
    ScenarioItemProof,
    scenario_effect_pool,
    scenario_flags,
    scenario_item_proofs,
)
from games.re2.startup_effects import (
    StartupEffectAuditConfig,
    StartupEffectAuditSupport,
    StartupEffectReceipt,
    certify_startup_effects,
    startup_effect_audit,
)

END = b"\x01\0"
CLIP = bytes([0x73, 0]) + bytes(6)
SCA = bytes([0x37, 0, 0x80, 0])


@pytest.fixture
def raw_profile():
    return json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())


def source(init=END, main=(END,)):
    data = bytearray(synthetic_room(init, main))
    data.extend(bytes((-len(data)) % 4))
    collision = len(data)
    struct.pack_into("<I", data, 8 + 6 * 4, collision)
    data.extend(bytes(64))
    struct.pack_into("<I", data, collision + 4, 4)
    data = bytes(data)
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    return data, room


def certify(data, room, raw_profile, required=frozenset({(1, 1)})):
    banks = {
        row["bank"]: (int(row["address_ps1"], 0), row["width"])
        for row in raw_profile["flag_banks"]
    }
    return certify_startup_effects(
        data,
        room,
        required,
        banks,
        clipping_effect_proof(raw_profile),
        startup_effect_audit(raw_profile),
    )


def test_missing_startup_audit_is_explicitly_unaudited():
    assert startup_effect_audit({}) is StartupEffectAuditSupport.Unaudited


@pytest.mark.parametrize(
    "fault",
    ["null", "extra", "audit", "hash", "revision", "missing-field", "boolean"],
)
def test_startup_audit_requires_its_exact_native_revision(raw_profile, fault):
    if fault == "null":
        raw_profile["startup_effect_audit"] = None
    elif fault == "extra":
        raw_profile["startup_effect_audit"]["other"] = 1
    elif fault == "revision":
        raw_profile["executable_identity"] = "another revision SHA256 " + "0" * 64
    elif fault == "missing-field":
        del raw_profile["startup_effect_audit"]["audit"]
    else:
        field = "executable_sha256" if fault == "hash" else "audit"
        raw_profile["startup_effect_audit"][field] = (
            False if fault == "boolean" else "other"
        )
    with pytest.raises(ValueError, match="startup effect audit"):
        startup_effect_audit(raw_profile)


def test_startup_audit_roundtrip_and_missing_native_support(raw_profile):
    audit = startup_effect_audit(raw_profile)
    assert isinstance(audit, StartupEffectAuditConfig)
    data, room = source(SCA + END)
    banks = {
        row["bank"]: (int(row["address_ps1"], 0), row["width"])
        for row in raw_profile["flag_banks"]
    }
    assert (
        certify_startup_effects(
            data, room, frozenset({(1, 1)}), banks, ClipEffectSupport.Unaudited, audit
        )
        is StartupEffectAuditSupport.Unaudited
    )
    assert (
        certify_startup_effects(
            data,
            room,
            frozenset({(1, 1)}),
            banks,
            clipping_effect_proof(raw_profile),
            StartupEffectAuditSupport.Unaudited,
        )
        is StartupEffectAuditSupport.Unaudited
    )


@pytest.mark.parametrize("setup", [SCA, CLIP, CLIP + SCA])
def test_setup_receipt_proves_presence_without_changing_fixed_context(
    raw_profile, setup
):
    data, room = source(END, (setup + item_command(20, 15, 9) + END,))
    flags = scenario_flags(raw_profile)
    kwargs = dict(clipping=clipping_effect_proof(raw_profile))
    old = scenario_item_proofs(
        data,
        room,
        flags,
        raw_profile["flag_banks"],
        scenario_effect_pool(raw_profile),
        **kwargs,
    )
    new = scenario_item_proofs(
        data,
        room,
        flags,
        raw_profile["flag_banks"],
        scenario_effect_pool(raw_profile),
        startup_audit=startup_effect_audit(raw_profile),
        **kwargs,
    )
    assert old.fixed_context_preserved and new.fixed_context_preserved
    assert old.startup_effects is StartupEffectAuditSupport.Unaudited
    assert isinstance(new.startup_effects, StartupEffectReceipt)
    offsets = frozenset(item["offset"] for item in room["items"])
    assert collection_presence(data, room, PRESENCE_FLAGS, offsets, frozenset()) == (
        [],
        [],
    )
    required, conditional = collection_presence(
        data,
        room,
        PRESENCE_FLAGS,
        offsets,
        frozenset(),
        startup_effects=new.startup_effects,
    )
    assert 9 in required or conditional == [
        {"global_id": 9, "presence": {"kind": "required"}}
    ]


@pytest.mark.parametrize(
    "fault", ["index", "count", "selector", "late", "yield", "overlap"]
)
def test_unsafe_setup_effects_do_not_authorize_presence(raw_profile, fault):
    setup = SCA
    if fault == "selector":
        setup = bytes([0x73, 3]) + bytes(6)
    elif fault == "late":
        setup = bytes([0x2D]) + bytes(37) + CLIP
    elif fault == "yield":
        setup = b"\x02" + CLIP
    data, room = source(END, (setup + item_command(20, 15, 9) + END,))
    if fault in ("count", "index"):
        data = bytearray(data)
        if fault == "count":
            struct.pack_into("<I", data, room["section_offsets"][6] + 4, 0)
        else:
            data[room["programs"]["17:0"]["entry"] + 1] = 4
        data = bytes(data)
    elif fault == "overlap":
        room = copy.deepcopy(room)
        first = room["programs"]["17:0"]["commands"][0]
        room["programs"]["17:0"]["commands"].append(
            {
                "offset": first["offset"] + 1,
                "next": first["next"],
                "opcode": 1,
                "kind": "end",
            }
        )
    receipt = certify(data, room, raw_profile)
    assert receipt is StartupEffectAuditSupport.Unaudited


def test_collision_asset_must_not_overlap_script_table(raw_profile):
    # SCA's count shares an encoded task command here. The native SCA bounds
    # alone are valid, but its record domain overlaps the initializer table.
    init = b"\0\0\x04\0\0\0" + SCA + bytes(80) + END
    data, room = source(init)
    data = bytearray(data)
    struct.pack_into("<I", data, 8 + 6 * 4, room["section_offsets"][16])
    data = bytes(data)
    room["section_offsets"][6] = room["section_offsets"][16]
    at = next(
        row["offset"]
        for row in room["programs"]["16:0"]["commands"]
        if row["opcode"] == 0x37
    )
    assert isinstance(
        sca_write_partition(data, tuple(room["section_offsets"]), at), ScaWritePartition
    )
    assert certify(data, room, raw_profile) is StartupEffectAuditSupport.Unaudited


def test_receipt_binds_source_and_only_preserved_used_predicates(raw_profile):
    guard = bytes([6, 0, 6, 0, 0x21, 4, 7, 1, 8, 0])
    data, room = source(END, (CLIP + guard + item_command(20, 15, 9) + END,))
    receipt = certify(data, room, raw_profile)
    assert isinstance(receipt, StartupEffectReceipt)
    assert receipt.locations_for(
        data, room["programs"], frozenset({(1, 1)}), frozenset()
    )
    assert not receipt.locations_for(
        data, room["programs"], PRESENCE_FLAGS, frozenset()
    )
    with pytest.raises(AssertionError, match="another source"):
        receipt.locations_for(data + b"\0", room["programs"], frozenset(), frozenset())
    assert (
        certify(data, room, raw_profile, frozenset({(1, 15)}))
        is StartupEffectAuditSupport.Unaudited
    )
    assert (
        certify(data, room, raw_profile, frozenset({(4, 7)}))
        is StartupEffectAuditSupport.Unaudited
    )


def test_unused_configured_predicate_does_not_withhold_receipt(raw_profile):
    data, room = source(SCA + END)
    receipt = certify(data, room, raw_profile)
    assert isinstance(receipt, StartupEffectReceipt)
    assert receipt.locations_for(data, room["programs"], PRESENCE_FLAGS, frozenset())


@pytest.mark.parametrize(
    "difference", ["none", "quantity", "identity", "type", "award"]
)
@pytest.mark.parametrize("scheduled", [False, True])
def test_opaque_alternatives_share_only_one_pickup_identity(difference, scheduled):
    first = item_command(20, 15, 9)
    second = item_command(
        21 if difference == "type" else 20,
        30 if difference == "quantity" else 15,
        10 if difference == "identity" else 9,
    )
    if difference == "award":
        first = second = bytes([0x76, 53, 1])
    comparison = bytes([0x23, 0, 27, 0, 2, 5])
    body = (
        bytes([6, 0])
        + struct.pack("<H", len(comparison + first) + 4)
        + comparison
        + first
        + bytes([7, 0])
        + struct.pack("<H", len(second) + 4)
        + second
        + END
    )
    if scheduled:
        data, room = source(END, (bytes([4, 255, 24, 1]) + END, body))
        key = "17:1"
    else:
        data, room = source(END, (body,))
        key = "17:0"
    targets = {
        (key, row["offset"])
        for row in room["programs"][key]["commands"]
        if row["kind"] in ("item", "award")
    }
    assert len(targets) == 2
    result = source_presence(
        data,
        room["programs"],
        targets,
        "scheduled" if scheduled else "startup",
        PRESENCE_FLAGS,
        frozenset(),
    )
    assert result == {
        "kind": "required" if difference in ("none", "quantity") else "unresolved"
    }


def test_failed_scenario_proof_cannot_carry_setup_receipt():
    receipt = StartupEffectReceipt(
        hashlib.sha256(END).hexdigest(), frozenset({("16:0", 0)}), frozenset()
    )
    with pytest.raises(AssertionError, match="preserved fixed context"):
        ScenarioItemProof(False, [], [], startup_effects=receipt)
    with pytest.raises(AssertionError):
        replace(ScenarioItemProof(False, [], []), startup_effects=False)


def test_owned_source_catalog_keeps_both_equivalent_creators_and_all_four_items():
    document = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    room = next(
        room
        for room in document["rooms"]
        if room["sha256"]
        == "94f38aa44a170d207c7625a41e24c595da82af57ad46f9fad7383600a0e92a0e"
    )
    assert room["fixed_context_preserved"] is True
    assert room["scenario_absent_item_ids"] == [61, 171]
    assert room["scenario_item_variants"] == [
        {"global_id": 56, "offsets": [6534, 6560]}
    ]
    assert room["collection_item_ids"] == []
    assert room["conditional_item_presence"] == [
        {"global_id": gid, "presence": {"kind": "required"}}
        for gid in (56, 60, 110, 199)
    ]
