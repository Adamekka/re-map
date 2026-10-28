"""RE2-CLIP-001: bounded revision opt-in, not native gameplay evidence."""

import copy
import json
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    ROOT,
    item_command,
    synthetic_room,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re2.clip_effect_proof import (
    ClipEffectProof,
    ClipEffectSupport,
    clipping_effect_proof,
)
from games.re2.room_data import decode_room
from games.re2.re2_profile import Re2Profile
from games.re2.scenario_items import (
    scenario_effect_pool,
    scenario_flags,
    scenario_item_proofs,
)


def check_packet(proof, packet, fixed_words):
    data = packet + b"\x01\0\x01\0"
    programs = {
        "16:0": {
            "entry": len(packet) + 2,
            "commands": [
                {
                    "offset": len(packet) + 2,
                    "next": len(packet) + 4,
                    "kind": "end",
                    "opcode": 1,
                }
            ],
        },
        "17:0": {
            "entry": 0,
            "commands": [
                {"offset": 0, "next": len(packet), "kind": "other", "opcode": 0x73},
                {
                    "offset": len(packet),
                    "next": len(packet) + 2,
                    "kind": "end",
                    "opcode": 1,
                },
            ],
        },
    }
    return proof.preserves_context(data, programs, "17:0", 0, fixed_words)


@pytest.fixture
def raw_profile():
    return {
        "runtime_layout": {
            "system_flags_address_ps1": "0x800CFB74",
            "status_flags_address_ps1": "0x800CFBD8",
        },
        "scenario_clipping": {
            "status_address_ps1": "0x800CFBD8",
            "parameter_writes": [
                {"address_ps1": "0x800CFB7D", "width": 1},
                {"address_ps1": "0x800CFB7E", "width": 2},
                {"address_ps1": "0x800CFB82", "width": 2},
                {"address_ps1": "0x800CFB80", "width": 2},
            ],
        },
    }


def test_missing_clipping_proof_is_explicitly_unaudited():
    assert clipping_effect_proof({}) is ClipEffectSupport.Unaudited


@pytest.mark.parametrize("value", [None, False, [], {}, {"enabled": True}])
def test_explicit_invalid_clipping_proof_never_becomes_unaudited(value):
    with pytest.raises(ValueError, match="RE2 clipping write proof"):
        clipping_effect_proof({"scenario_clipping": value})


@pytest.mark.parametrize(
    "fault",
    [
        "missing-status",
        "integer-status",
        "malformed-status",
        "unaligned-status",
        "unmapped-status",
        "layout-mismatch",
        "missing-layout",
        "missing-system",
        "unaligned-system",
        "overlapping-system",
        "missing-parameter",
        "extra-parameter",
        "extra-field",
        "boolean-width",
        "wrong-width",
        "integer-address",
        "malformed-address",
        "unaligned-parameter",
        "unmapped-parameter",
        "overlapping-parameters",
        "overlapping-status",
    ],
)
def test_clipping_proof_requires_every_revision_bound_store(raw_profile, fault):
    raw = raw_profile["scenario_clipping"]
    rows = raw["parameter_writes"]
    if fault == "missing-status":
        del raw["status_address_ps1"]
    elif fault == "integer-status":
        raw["status_address_ps1"] = 0x800CFBD8
    elif fault == "malformed-status":
        raw["status_address_ps1"] = "bad address"
    elif fault == "unaligned-status":
        raw["status_address_ps1"] = "0x800CFBD9"
    elif fault == "unmapped-status":
        raw["status_address_ps1"] = "0x80200000"
    elif fault == "layout-mismatch":
        raw_profile["runtime_layout"]["status_flags_address_ps1"] = "0x800CFBDC"
    elif fault == "missing-layout":
        del raw_profile["runtime_layout"]
    elif fault == "missing-system":
        del raw_profile["runtime_layout"]["system_flags_address_ps1"]
    elif fault == "unaligned-system":
        raw_profile["runtime_layout"]["system_flags_address_ps1"] = "0x800CFB75"
    elif fault == "overlapping-system":
        raw_profile["runtime_layout"]["system_flags_address_ps1"] = "0x800CFBD8"
    elif fault == "missing-parameter":
        rows.pop()
    elif fault == "extra-parameter":
        rows.append({"address_ps1": "0x800CFB84", "width": 2})
    elif fault == "extra-field":
        rows[0]["mask"] = 1
    elif fault == "boolean-width":
        rows[0]["width"] = True
    elif fault == "wrong-width":
        rows[1]["width"] = 1
    elif fault == "integer-address":
        rows[0]["address_ps1"] = 0x800CFB7D
    elif fault == "malformed-address":
        rows[0]["address_ps1"] = "bad address"
    elif fault == "unaligned-parameter":
        rows[1]["address_ps1"] = "0x800CFB7F"
    elif fault == "unmapped-parameter":
        rows[0]["address_ps1"] = "0x7FFFFFFF"
    elif fault == "overlapping-parameters":
        rows[2]["address_ps1"] = rows[1]["address_ps1"]
    else:
        rows[0]["address_ps1"] = raw["status_address_ps1"]
    with pytest.raises(ValueError, match="RE2 clipping write proof"):
        clipping_effect_proof(raw_profile)


@pytest.mark.parametrize("selector", [0, 1, 2])
@pytest.mark.parametrize(
    "fixed_word,mask,accepted",
    [
        (0x800CFBD8, 0xC2000000, True),
        (0x800CFBD8, 0x00000040, True),
        (0x800CFBD8, 0x00010000, False),
        (0x800CFBD8, 0xFFFFFFFF, False),
        (0x800CFBD4, 0xFFFFFFFF, True),
        (0x800CFBDC, 0xFFFFFFFF, True),
        (0x800CFB7C, 0x000000FF, True),
        (0x800CFB7C, 0x00000100, False),
        (0x800CFB7C, 0x00008000, False),
        (0x800CFB7C, 0x00010000, False),
        (0x800CFB7C, 0x80000000, False),
        (0x800CFB80, 0x00000001, False),
        (0x800CFB80, 0x00008000, False),
        (0x800CFB80, 0x00010000, False),
        (0x800CFB80, 0x80000000, False),
        (0x800CFB84, 0xFFFFFFFF, True),
    ],
)
def test_clipping_stores_reject_native_word_and_byte_lane_aliases(
    raw_profile, selector, fixed_word, mask, accepted
):
    proof = clipping_effect_proof(raw_profile)
    packet = bytes([0x73, selector, 0xA8, 0xB2, 0x58, 0x9E, 0xC8, 0xB5])
    assert isinstance(proof, ClipEffectProof)
    if fixed_word != proof.status_address:
        # Synthetic native-bank aliases exercise the write masks independently
        # of the production profile's narrower two-word context domain.
        proof = replace(proof, system_address=fixed_word)
    assert check_packet(proof, packet, {fixed_word: mask}) is accepted


@pytest.mark.parametrize(
    "packet",
    [
        b"",
        bytes(8),
        bytes([0x74, 0]) + bytes(6),
        bytes([0x73, 3]) + bytes(6),
        bytes([0x73, 255]) + bytes(6),
        bytes([0x73, 0]) + bytes(5),
        bytes([0x73, 0]) + bytes(7),
    ],
)
def test_unsupported_clipping_packets_cannot_preserve_context(raw_profile, packet):
    proof = clipping_effect_proof(raw_profile)
    assert proof.system_address == 0x800CFB74
    assert not check_packet(proof, packet, {})


def test_valid_proof_owns_its_config_and_enforces_direct_construction(raw_profile):
    proof = clipping_effect_proof(raw_profile)
    assert proof.status_address == 0x800CFBD8
    assert proof.parameter_writes == (
        (0x800CFB7D, 1),
        (0x800CFB7E, 2),
        (0x800CFB82, 2),
        (0x800CFB80, 2),
    )
    other = copy.deepcopy(raw_profile)
    other["scenario_clipping"]["parameter_writes"][0]["address_ps1"] = "0x800CFB84"
    assert clipping_effect_proof(other) != proof
    with pytest.raises(AssertionError):
        ClipEffectProof(proof.system_address, proof.status_address, ((0x800CFB7D, 1),))
    with pytest.raises(AssertionError):
        ClipEffectProof(proof.system_address, True, proof.parameter_writes)


@pytest.mark.parametrize("word", [0x800CFD90, 0x800E2A90, 0x80110000, 0x800CFB7C])
def test_other_fixed_words_do_not_inherit_the_geometry_context_proof(raw_profile, word):
    proof = clipping_effect_proof(raw_profile)
    assert not check_packet(proof, bytes([0x73, 0]) + bytes(6), {word: 1})


@pytest.mark.parametrize("word,mask", [(0x800CFBD9, 1), (0x800CFBD8, True), (0, 1)])
def test_programmer_error_in_fixed_word_layout_is_asserted(raw_profile, word, mask):
    with pytest.raises(AssertionError, match="aligned PS1 words"):
        check_packet(
            clipping_effect_proof(raw_profile),
            bytes([0x73, 0]) + bytes(6),
            {word: mask},
        )


@pytest.mark.parametrize(
    "case,accepted",
    [
        ("startup", True),
        ("initializer", True),
        ("aot-prefix", True),
        ("flags-prefix", True),
        ("model-after", True),
        ("model-on-other-exit", True),
        ("model-before", False),
        ("prior-initializer-model", False),
        ("fork-before", False),
        ("call-before", False),
        ("yield-before", False),
        ("event-procedure", False),
        ("frame-procedure", False),
        ("loop-after", False),
        ("model-backedge", False),
        ("initializer-reentry-call", False),
        ("initializer-reentry-fork", False),
        ("initializer-reentry-next", False),
        ("initializer-reentry-aot", False),
        ("initializer-reentry-four-point-aot", False),
        ("initializer-reentry-aot-geometry", False),
        ("initializer-reentry-reset", False),
        ("initializer-reentry-reset-geometry", False),
    ],
)
def test_clipping_requires_startup_before_model_construction(
    raw_profile, case, accepted
):
    clip, end = bytes([0x73, 0]) + bytes(6), b"\x01\0"
    model = bytes([0x2D]) + bytes(37)
    init, startup, extra, target = end, clip + end, (), "17:0"
    if case == "initializer":
        init, startup, target = clip + end, end, "16:0"
    elif case == "aot-prefix":
        startup = bytes([0x2C, 0, 4, 0x31]) + bytes(16) + clip + end
    elif case == "flags-prefix":
        startup = bytes([0x22, 32, 8, 1]) + clip + end
    elif case == "model-after":
        startup = clip + model + end
    elif case == "model-on-other-exit":
        startup = (
            bytes([6, 0])
            + struct.pack("<H", len(model) + 6)
            + bytes([0x21, 4, 7, 0])
            + model
            + end
            + clip
            + end
        )
    elif case == "model-before":
        startup = model + clip + end
    elif case == "prior-initializer-model":
        init = model + end
    elif case == "fork-before":
        startup, extra = b"\x04\xff\x18\x01" + clip + end, (end,)
    elif case == "call-before":
        startup, extra = b"\x18\x01" + clip + end, (end,)
    elif case == "yield-before":
        startup = b"\x02" + clip + end
    elif case == "event-procedure":
        startup, extra, target = end, (end, clip + end), "17:2"
    elif case == "frame-procedure":
        startup, extra, target = end, (clip + end,), "17:1"
    elif case == "loop-after":
        startup = clip + b"\x0d\0\x03\0\x01\0\0\x0e\0" + end
    elif case == "model-backedge":
        startup = (
            clip
            + model
            + b"\x17\xff\xff\0"
            + struct.pack("<h", -len(clip + model))
            + end
        )
    elif case.startswith("initializer-reentry-"):
        reentry = {
            "call": b"\x18\0",
            "fork": b"\x04\xff\x18\0",
            "next": b"\x03\xff\x18\0",
            "aot": bytes([0x2C, 0, 5, 0x31]) + bytes(10) + b"\xff\0\x18\0\0\0",
            "four-point-aot": bytes([0x67, 0, 5, 0xB1])
            + bytes(18)
            + b"\xff\0\x18\0\0\0",
            "aot-geometry": bytes([0x2C, 0, 5, 0xB1])
            + bytes(10)
            + b"\xff\0\x18\x01\0\0",
            "reset": b"\x46\0\x05\x31\xff\0\x18\0\0\0",
            "reset-geometry": b"\x46\0\x05\xb1\xff\0\x18\x01\0\0",
        }[case.removeprefix("initializer-reentry-")]
        extra = (reentry + end,)
    data = synthetic_room(init, (startup, *extra))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    offset = next(
        row["offset"]
        for row in room["programs"][target]["commands"]
        if row["opcode"] == 0x73
    )
    assert (
        clipping_effect_proof(raw_profile).preserves_context(
            data, room["programs"], target, offset, {}
        )
        is accepted
    )


@pytest.mark.parametrize(
    "case",
    [
        "enabled",
        "missing",
        "unaudited",
        "late",
        "event",
        "bad-selector",
        "fixed-bit",
        "fixed-heap",
    ],
)
def test_clipping_integration_only_exports_proven_item_variants_and_absence(
    raw_profile, case
):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    raw["scenario_clipping"] = raw_profile["scenario_clipping"]
    clip = bytes([0x73, 3 if case == "bad-selector" else 0]) + bytes(6)
    end = b"\x01\0"
    other = item_command(21, 7, 9) + item_command(38, 1, 10, slot=9)
    selected = item_command(20, 15, 9)
    branches = (
        bytes([6, 0])
        + struct.pack("<H", len(other) + 6)
        + bytes([0x21, 1, 1, 1])
        + other
        + b"\x08\0"
        + bytes([6, 0])
        + struct.pack("<H", len(selected) + 6)
        + bytes([0x21, 1, 1, 0])
        + selected
        + b"\x08\0"
    )
    startup, extra = clip + branches + end, ()
    if case == "late":
        startup = bytes([0x2D]) + bytes(37) + startup
    elif case == "event":
        startup, extra = branches + end, (clip + end,)
    data = synthetic_room(end, (startup, *extra))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    flags = scenario_flags(raw)
    if case == "fixed-bit":
        flags.append({"bank": 1, "bit": 15, "expected": 0})
    elif case == "fixed-heap":
        raw["flag_banks"].append({"bank": 99, "address_ps1": "0x80110000", "width": 4})
        flags.append({"bank": 99, "bit": 0, "expected": 0})
    arguments = (
        {}
        if case == "missing"
        else {
            "clipping": ClipEffectSupport.Unaudited
            if case == "unaudited"
            else clipping_effect_proof(raw)
        }
    )
    proof = scenario_item_proofs(
        data, room, flags, raw["flag_banks"], scenario_effect_pool(raw), **arguments
    )
    assert proof.fixed_context_preserved is (case == "enabled")
    assert proof.absent_item_ids == ([10] if case == "enabled" else [])
    assert proof.item_variants == (
        [
            {
                "global_id": 9,
                "offsets": [
                    item["offset"] for item in room["items"] if item["type"] == 20
                ],
            }
        ]
        if case == "enabled"
        else []
    )


@pytest.mark.parametrize("value", [None, (), {}, "enabled"])
def test_invalid_clipping_argument_is_a_programmer_error(value):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    data = synthetic_room(b"\x01\0")
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    with pytest.raises(AssertionError):
        scenario_item_proofs(
            data,
            room,
            scenario_flags(raw),
            raw["flag_banks"],
            scenario_effect_pool(raw),
            clipping=value,
        )


@pytest.mark.parametrize(
    "case",
    [
        "matching",
        "absent-both",
        "profile-only",
        "metadata-only",
        "drift",
        "boolean-width",
        "null-metadata",
        "null-profile",
    ],
)
def test_profile_and_catalog_bind_the_same_clipping_contract(
    raw_profile, tmp_path, case
):
    path = ROOT / "profiles/re2_leon_a_slus00748.json"
    raw = json.loads(path.read_text())
    document = json.loads((path.parent / raw["room_metadata_path"]).read_text())
    raw.pop("scenario_clipping", None)
    document.pop("scenario_clipping", None)
    if case != "absent-both":
        raw["scenario_clipping"] = copy.deepcopy(raw_profile["scenario_clipping"])
        document["scenario_clipping"] = copy.deepcopy(raw["scenario_clipping"])
    if case == "profile-only":
        del document["scenario_clipping"]
    elif case == "metadata-only":
        del raw["scenario_clipping"]
    elif case == "drift":
        document["scenario_clipping"]["parameter_writes"][0]["address_ps1"] = (
            "0x800CFB84"
        )
    elif case == "boolean-width":
        document["scenario_clipping"]["parameter_writes"][0]["width"] = True
    elif case == "null-metadata":
        document["scenario_clipping"] = None
    elif case == "null-profile":
        raw["scenario_clipping"] = None
    for field in ("floor_plans_path", "names_path"):
        raw[field] = str((path.parent / raw[field]).resolve())
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps(raw))
    if case in ("matching", "absent-both"):
        assert Re2Profile.load(profile).profile_id == raw["profile_id"]
    else:
        with pytest.raises(ValueError, match="RE2 clipping"):
            Re2Profile.load(profile)
