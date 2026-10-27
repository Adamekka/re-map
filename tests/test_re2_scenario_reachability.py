"""Shared creator reachability used by source presence proofs, RE2-DS-003."""

import json
import struct

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    ROOT,
    SCENARIO_EFFECT_POOL,
    item_command,
    synthetic_room,
)

from games.re2.room_data import decode_room
from games.re2.scenario_items import ScenarioItemProof, scenario_item_proofs


@pytest.mark.parametrize("kind", ["item", "interaction", "door", "reset"])
@pytest.mark.parametrize("context", ["false", "true", "unknown", "failed"])
def test_only_whole_source_proofs_export_unreachable_creators(kind, context):
    packet = {
        "item": item_command(20, 15, 9),
        "interaction": bytes([0x2C, 8, 5, 0x31]) + bytes(16),
        "door": bytes([0x3B, 8, 1, 0x31]) + bytes(28),
        "reset": bytes([0x46, 8, 0, 0x31]) + bytes(6),
    }[kind]
    branch = (
        bytes([6, 0])
        + struct.pack("<H", len(packet) + 6)
        + bytes([0x21, 1 if context != "unknown" else 4, 1, 1])
        + packet
        + b"\x08\0"
    )
    data = synthetic_room(
        branch + packet + (b"\x20" if context == "failed" else b"") + b"\x01\0"
    )
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["candidate_list_complete"]
    creators = [
        row["offset"]
        for row in room["programs"]["16:0"]["commands"]
        if row["kind"] == kind
    ]
    assert len(creators) == 2
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": int(context == "true")}],
        json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())[
            "flag_banks"
        ],
        SCENARIO_EFFECT_POOL,
    )
    assert proof.fixed_context_preserved == (context != "failed")
    assert proof.unreachable_creator_offsets == (
        frozenset({creators[0]}) if context == "false" else frozenset()
    )


def test_opaque_loop_creators_are_never_exported_as_unreachable():
    packet = bytes([0x2C, 8, 5, 0x31]) + bytes(16)
    branch = bytes([6, 0, 26, 0, 0x21, 1, 1, 1]) + packet + b"\x08\0"
    # Zero-count FOR bodies remain possible in the conservative source proof.
    loop = b"\x0d\0" + struct.pack("<HH", len(branch) + 2, 0) + branch + b"\x0e\0"
    data = synthetic_room(loop + b"\x01\0")
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())[
            "flag_banks"
        ],
        SCENARIO_EFFECT_POOL,
    )
    assert proof.fixed_context_preserved
    assert proof.unreachable_creator_offsets == frozenset()


def test_failed_proof_cannot_carry_unreachable_creators():
    assert ScenarioItemProof(False, [], []).unreachable_creator_offsets == frozenset()
    with pytest.raises(AssertionError, match="preserved fixed context"):
        ScenarioItemProof(False, [], [], frozenset({134}))
