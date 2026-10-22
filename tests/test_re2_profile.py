"""RE2-IDENTITY-001 / RE2-COLLECT-001: revision and required metadata checks."""

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re2.re2_profile import Re2Profile
from games.runtime_identity import RuntimeSignature


def test_re2_profile_pins_leon_disc_and_halfword_addresses():
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    assert profile.stage_address == 0x800CC948
    assert profile.room_address == 0x800CC94A
    assert profile.camera_address == 0x800CC94C
    assert profile.executable_identity.endswith(
        "1cd618bc4390db4bd60735b0db1e91534f6134ede56fae454eb580be2aa686ef"
    )
    assert profile.read_current_room(
        lambda address, width: MemRead(
            True, {0x800CC948: b"\x01\x00", 0x800CC94A: b"\x1a\x00"}[address]
        )
    ).room == RoomId(1, 0x1A)


@pytest.mark.parametrize("data", [b"", b"\x00", b"\x00\x01", b"\xff\xff"])
def test_re2_room_rejects_short_or_invalid_halfwords(data):
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    result = profile.read_current_room(lambda address, width: MemRead(True, data))
    assert not result.ok
    assert result.room is None


def test_re2_room_preserves_transport_failure():
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    result = profile.read_current_room(
        lambda address, width: MemRead(False, b"", "disconnected")
    )
    assert not result.ok
    assert "disconnected" in result.error


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("scenario", "leon-b"),
        ("serial", "SLUS-00748"),
        ("room_value_width_bytes", 1),
        ("room_address_ps1", "0xCC94A"),
        ("stage_address_ps1", "0x801FFFFF"),
    ],
)
def test_re2_profile_rejects_incompatible_layout(tmp_path, key, value):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    raw[key] = value
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        Re2Profile.load(path)


def test_revision_signature_distinguishes_wrong_game_and_failed_read():
    signature = RuntimeSignature(
        (0x80010000, 0x80020000), 32, hashlib.sha256(bytes(64)).hexdigest()
    )
    profile = replace(
        Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json"),
        runtime_signature=signature,
    )
    assert profile.verify_runtime(
        lambda address, width: MemRead(True, bytes(width))
    ).value
    mismatch = profile.verify_runtime(
        lambda address, width: MemRead(True, b"x" * width)
    )
    assert mismatch.ok and not mismatch.value
    short = profile.verify_runtime(lambda address, width: MemRead(True, b"x"))
    assert not short.ok and "short signature" in short.error
    failure = profile.verify_runtime(
        lambda address, width: MemRead(False, b"", "disconnected")
    )
    assert not failure.ok and "disconnected" in failure.error


@pytest.mark.parametrize(
    "key,value",
    [("event_awards", None), ("event_awards", [{}]), ("candidate_list_complete", 1)],
)
def test_re2_room_metadata_fails_during_load(tmp_path, key, value):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    document["rooms"][0][key] = value
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2.*(coverage|award)"):
        Re2Profile.load(profile)


@pytest.mark.parametrize("proof", [None, [True], ["9"], [0, 0], [999]])
def test_re2_collection_proofs_are_required_validated_metadata(tmp_path, proof):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    if proof is None:
        del document["rooms"][0]["collection_item_ids"]
    else:
        document["rooms"][0]["collection_item_ids"] = proof
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2.*collection"):
        Re2Profile.load(path)


@pytest.mark.parametrize(
    "amounts", [None, [], [True], ["5"], [5, 5], [5, 4], [4], [-1, 5], [5, 65536]]
)
def test_re2_quantity_alternatives_are_required_validated_metadata(tmp_path, amounts):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    item = next(room for room in document["rooms"] if room["items"])["items"][0]
    if amounts is None:
        del item["amounts"]
    else:
        item["amounts"] = amounts
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2 source quantity"):
        Re2Profile.load(path)


@pytest.mark.parametrize(
    "override",
    [
        None,
        {},
        {"system_mask": True, "item_type": 30, "amount": 2},
        {"system_mask": 0, "item_type": 30, "amount": 2},
        {"system_mask": 65, "item_type": 30, "amount": 2},
        {"system_mask": 1 << 32, "item_type": 30, "amount": 2},
        {"system_mask": 64, "item_type": True, "amount": 2},
        {"system_mask": 64, "item_type": -1, "amount": 2},
        {"system_mask": 64, "item_type": 104, "amount": 2},
        {"system_mask": 64, "item_type": 30, "amount": True},
        {"system_mask": 64, "item_type": 30, "amount": -1},
        {"system_mask": 64, "item_type": 30, "amount": 65536},
        {"system_mask": 64, "item_type": 30, "amount": 2, "extra": 1},
    ],
)
def test_re2_quantity_override_is_required_validated_configuration(tmp_path, override):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    if override is None:
        del raw["runtime_layout"]["pickup_quantity_override"]
    else:
        raw["runtime_layout"]["pickup_quantity_override"] = override
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2 pickup quantity override"):
        Re2Profile.load(path)


def test_re2_quantity_override_pins_the_native_pickup_handler_rule():
    # RE2-QUANTITY-001: native 0x8004E330 replaces the operand before pickup.
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    assert profile.runtime_layout["pickup_quantity_override"] == {
        "system_mask": 0x40,
        "item_type": 30,
        "amount": 2,
    }


@pytest.mark.parametrize("floor", [None, True, "0", -1, 256])
def test_re2_door_activation_floor_is_required_validated_metadata(tmp_path, floor):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    door = document["rooms"][0]["doors"][0]
    if floor is None:
        del door["activation_floor"]
    else:
        door["activation_floor"] = floor
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2 door activation floor"):
        Re2Profile.load(path)


@pytest.mark.parametrize(
    "collection",
    [
        None,
        {},
        {"kind": "other"},
        {"kind": "unresolved", "bit": 5},
        {"kind": "flag"},
        {"kind": "flag", "bank": True, "bit": 5},
        {"kind": "flag", "bank": 8, "bit": True},
        {"kind": "flag", "bank": 4, "bit": 5},
        {"kind": "flag", "bank": 8, "bit": -1},
        {"kind": "flag", "bank": 8, "bit": 256},
        {"kind": "flag", "bank": 8, "bit": 0},
    ],
)
def test_re2_event_collection_rules_are_required_and_reject_aliases(
    tmp_path, collection
):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    award = next(room for room in document["rooms"] if room["event_awards"])[
        "event_awards"
    ][0]
    if collection is None:
        del award["collection"]
    else:
        award["collection"] = collection
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps(raw))
    with pytest.raises(
        ValueError, match="RE2 event award.*collection|aliased RE2 event award"
    ):
        Re2Profile.load(profile)


@pytest.mark.parametrize(
    "presence",
    [
        None,
        {},
        {"kind": "other"},
        {"kind": "required", "any_of": []},
        {"kind": "conditions"},
        {"kind": "conditions", "any_of": []},
        {"kind": "conditions", "any_of": [[]]},
        {"kind": "conditions", "any_of": [[{"bank": True, "bit": 7, "expected": 0}]]},
        {"kind": "conditions", "any_of": [[{"bank": 11, "bit": 7, "expected": 0}]]},
        {"kind": "conditions", "any_of": [[{"bank": 4, "bit": 256, "expected": 0}]]},
        {"kind": "conditions", "any_of": [[{"bank": 4, "bit": 7, "expected": True}]]},
        {"kind": "conditions", "any_of": [[{"bank": 4, "bit": 7, "expected": 2}]]},
        {
            "kind": "conditions",
            "any_of": [
                [
                    {"bank": 4, "bit": 7, "expected": 0},
                    {"bank": 4, "bit": 7, "expected": 1},
                ]
            ],
        },
    ],
)
def test_re2_event_presence_metadata_is_required_and_validated(tmp_path, presence):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    award = next(room for room in document["rooms"] if room["event_awards"])[
        "event_awards"
    ][0]
    if presence is None:
        del award["presence"]
    else:
        award["presence"] = presence
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2 event award.*presence"):
        Re2Profile.load(profile)


@pytest.mark.parametrize(
    "case",
    [
        "missing",
        "shape",
        "unknown-id",
        "boolean-id",
        "duplicate",
        "legacy-duplicate",
        "unresolved",
        "bad-bank",
        "empty-clause",
        "contradictory",
    ],
)
def test_conditional_pickup_rules_require_valid_explicit_metadata(tmp_path, case):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    room = next(room for room in document["rooms"] if room["id"] == "01-07")
    rules = room["conditional_item_presence"]
    if case == "missing":
        del room["conditional_item_presence"]
    elif case == "shape":
        room["conditional_item_presence"] = {}
    elif case == "unknown-id":
        rules[0]["global_id"] = 255
    elif case == "boolean-id":
        rules[0]["global_id"] = True
    elif case == "duplicate":
        rules.append(rules[0])
    elif case == "legacy-duplicate":
        room["collection_item_ids"].append(rules[0]["global_id"])
    elif case == "unresolved":
        rules[0]["presence"] = {"kind": "unresolved"}
    elif case == "bad-bank":
        rules[0]["presence"]["any_of"][0][0]["bank"] = 11
    elif case == "empty-clause":
        rules[0]["presence"]["any_of"] = [[]]
    elif case == "contradictory":
        rules[0]["presence"]["any_of"][0].append({"bank": 1, "bit": 6, "expected": 1})
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    profile = tmp_path / "profile.json"
    profile.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2 conditional pickup presence"):
        Re2Profile.load(profile)


@pytest.mark.parametrize(
    "case",
    ["missing", "empty", "duplicate", "bad-bank", "boolean-bit", "unsupported-rule"],
)
def test_presence_condition_flags_are_explicit_and_bound_to_metadata(tmp_path, case):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    if case == "missing":
        del raw["presence_condition_flags"]
    elif case == "empty":
        raw["presence_condition_flags"] = []
    elif case == "duplicate":
        raw["presence_condition_flags"].append(raw["presence_condition_flags"][0])
    elif case == "bad-bank":
        raw["presence_condition_flags"][0]["bank"] = 11
    elif case == "boolean-bit":
        raw["presence_condition_flags"][0]["bit"] = True
    elif case == "unsupported-rule":
        raw["presence_condition_flags"] = [{"bank": 1, "bit": 1}]
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(
        ValueError,
        match="RE2 stable presence flags|RE2 conditional pickup presence|RE2 event award presence",
    ):
        Re2Profile.load(path)


@pytest.mark.parametrize(
    "case",
    [
        "missing-flags",
        "changed-flags",
        "boolean-flags",
        "mask-mismatch",
        "unmasked-value",
        "missing-ids",
        "duplicate",
        "unknown-id",
        "boolean-id",
        "required-overlap",
        "conditional-overlap",
        "incomplete",
    ],
)
def test_scenario_exclusion_metadata_is_required_and_bound_to_configuration(
    tmp_path, case
):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    for field in ("room_metadata_path", "floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    document = json.loads(Path(raw["room_metadata_path"]).read_text())
    room = next(room for room in document["rooms"] if room["id"] == "00-0f")
    if case == "missing-flags":
        del document["fixed_scenario_flags"]
    elif case == "changed-flags":
        document["fixed_scenario_flags"][0]["expected"] = 1
    elif case == "boolean-flags":
        document["fixed_scenario_flags"][0]["expected"] = False
    elif case == "mask-mismatch":
        raw["runtime_layout"]["scenario_mask"] = 0x40000000
    elif case == "unmasked-value":
        raw["runtime_layout"]["scenario_value"] = 1
    elif case == "missing-ids":
        del room["scenario_absent_item_ids"]
    elif case == "duplicate":
        room["scenario_absent_item_ids"] = [157, 157]
    elif case == "unknown-id":
        room["scenario_absent_item_ids"] = [255]
    elif case == "boolean-id":
        room["scenario_absent_item_ids"] = [True]
    elif case == "required-overlap":
        other = next(row for row in document["rooms"] if row["id"] == "01-03")
        other["scenario_absent_item_ids"].append(35)
    elif case == "conditional-overlap":
        room["conditional_item_presence"][-1]["presence"] = {"kind": "required"}
    elif case == "incomplete":
        room["candidate_list_complete"] = False
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="RE2.*scenario|RE2 scenario"):
        Re2Profile.load(path)
