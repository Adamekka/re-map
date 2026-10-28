"""RE2-SCD-001 / RE2-MAP-001 / RE2-COLLECT-001: source contracts, not gameplay.

RE2-COLLECT-002 covers independent presence proofs for unrelated slots.
"""

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from build_re2_metadata import map_detail_segments, map_door_segments
from map_geometry import trace_floor_cells

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.room_data import bind_event_awards, decode_room
from games.re2.scenario_items import scenario_effect_pool

SCENARIO_EFFECT_POOL = scenario_effect_pool(
    json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
)

PRESENCE_FLAGS = frozenset({(1, 0), (1, 1), (1, 6), (4, 7)})
PRESENCE_COUNTERS = presence_counter_indices(
    json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
)

PRESENCE_WRITES, FLAG_PROOF = presence_flag_write_proof(
    json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
)


@pytest.mark.parametrize("offset", [0, 24, 96 * 124 - 4])
def test_dualshock_effect_pool_rejects_native_fixed_word_aliases(offset):
    """RE2-DS-003: sign-extended ADDIU selects D8CF0, not E8CF0."""
    from games.re2.scenario_items import scenario_item_proofs

    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    pool = scenario_effect_pool(raw)
    # Both native allocators add signed -0x7310 to LUI 0x800E. Their
    # 96 records occupy this full interval, including the last pointer word.
    assert pool == (0x800D8CF0, 0x800DBB70)
    data = synthetic_room(b"\x01\0", (bytes([0x3A]) + bytes(15) + b"\x01\0",))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    flags = [{"bank": 99, "bit": 0, "expected": 0}]
    banks = [
        *raw["flag_banks"],
        {"bank": 99, "address_ps1": f"0x{0x800D8CF0 + offset:08X}", "width": 4},
    ]
    assert not scenario_item_proofs(
        data, room, flags, banks, pool
    ).fixed_context_preserved
    # The prior interval incorrectly admitted these aliases. Retain the
    # counterexample so another unsigned-immediate transcription is caught.
    assert scenario_item_proofs(
        data, room, flags, banks, (0x800E8CF0, 0x800EBB70)
    ).fixed_context_preserved


@pytest.mark.parametrize("opcode", [0x8A, 0x8B, 0x8C])
@pytest.mark.parametrize(
    "proof", ["missing", "disjoint", "scratch", "queue0", "queue1"]
)
def test_vibration_context_requires_all_writes_disjoint_from_fixed_words(
    opcode, proof, scenario_banks
):
    """RE2-DS-003: a vibration command cannot authorize another revision."""
    from games.re2.scenario_items import scenario_item_proofs, scenario_vibration_writes

    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    regions = scenario_vibration_writes(raw)
    if proof == "missing":
        regions = ()
    elif proof != "disjoint":
        index = {"scratch": 0, "queue0": 1, "queue1": 2}[proof]
        # An offset alias reaches the fixed word from another bank. Check the
        # last aligned word in each permitted write range, not just its base.
        start, width = regions[index]
        scenario_banks = [
            *scenario_banks,
            {"bank": 99, "address_ps1": f"0x{start + width - 8:08X}", "width": 8},
        ]
    flags = [
        {"bank": 99, "bit": 32, "expected": 0}
        if proof in ("scratch", "queue0", "queue1")
        else {"bank": 1, "bit": 1, "expected": 0}
    ]
    guarded = (
        bytes([6, 0, 28, 0, 0x21, 1, 1, 1])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    command = bytes([opcode, 255, 10, 0, 2, 0])
    if opcode == 0x8C:
        command += bytes(2)
    data = synthetic_room(bytes([1, 0]), (guarded, command + bytes([1, 0])))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    result = scenario_item_proofs(
        data,
        room,
        flags,
        scenario_banks,
        SCENARIO_EFFECT_POOL,
        vibration_writes=regions,
    )
    accepted = proof == "disjoint" and opcode in (0x8A, 0x8B)
    assert result.fixed_context_preserved is accepted
    assert result.absent_item_ids == ([9] if accepted else [])


@pytest.mark.parametrize("operation", [0, 1, 7, 2, 255])
@pytest.mark.parametrize(
    "bank,bit,safe",
    [(4, 6, True), (4, 7, False), (1, 32, False), (2, 224, False), (11, 0, False)],
)
def test_startup_flag_writes_must_preserve_presence_inputs(operation, bank, bit, safe):
    """RE2-COLLECT-013: neither a bank number nor a no-op proves safety."""
    guarded = (
        bytes([6, 0, 28, 0, 0x21, 4, 7, 0])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    data = synthetic_room(bytes([0x22, bank, bit, operation, 1, 0]), (guarded,))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["conditional_item_presence"] == (
        [
            {
                "global_id": 9,
                "presence": {
                    "kind": "conditions",
                    "any_of": [[{"bank": 4, "bit": 7, "expected": 0}]],
                },
            }
        ]
        if safe and operation in (0, 1, 7)
        else []
    )


def test_flag_write_guard_catches_aliases_and_keeps_other_bits_in_the_word():
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    # This explicit synthetic bank aliases the preceding word and the stable
    # input word. It is not a new native profile bank.
    raw["flag_banks"].append({"bank": 99, "address_ps1": "0x800CC97C", "width": 8})
    allowed, _ = presence_flag_write_proof(raw)
    assert (99, 39) not in allowed and (99, 38) in allowed
    assert (4, 7) not in allowed and (4, 6) in allowed
    guarded = (
        bytes([6, 0, 28, 0, 0x21, 4, 7, 0])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    for bit, present in [(39, False), (38, True)]:
        room = decode_room(
            synthetic_room(bytes([0x22, 99, bit, 1, 1, 0]), (guarded,)),
            "synthetic",
            PRESENCE_FLAGS,
            PRESENCE_COUNTERS,
            allowed,
        )
        assert bool(room["conditional_item_presence"]) is present


@pytest.mark.parametrize("safe", [False, True])
def test_scheduled_presence_uses_the_same_flag_write_guard_after_queuing(safe):
    from games.re2.event_presence import source_presence

    startup = bytes([4, 255, 0x18, 1, 0x22, 4, 6 if safe else 7, 1, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    award = next(
        row for row in room["programs"]["17:1"]["commands"] if row["kind"] == "award"
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", award["offset"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "required" if safe else "unresolved"}


def test_startup_flag_write_without_explicit_proof_is_unresolved():
    guarded = (
        bytes([6, 0, 28, 0, 0x21, 4, 7, 0])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    data = synthetic_room(bytes([0x22, 4, 6, 1, 1, 0]), (guarded,))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, frozenset()
    )
    assert room["conditional_item_presence"] == []


@pytest.mark.parametrize(
    "field", ["runtime_layout", "stage_address_ps1", "camera_address_ps1"]
)
def test_counter_proof_rejects_missing_dependencies_with_a_diagnostic(field):
    profile = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    del profile[field]
    with pytest.raises(ValueError, match="RE2 counter layout or identity"):
        presence_counter_indices(profile)


@pytest.mark.parametrize("counter", [0, 7, 23, 24, 25, 26, 32, 35, 36, 52, 104, 255])
@pytest.mark.parametrize("value", [0, 51, 65535])
def test_counter_setup_requires_a_flag_and_identity_disjoint_write(counter, value):
    """RE2-COLLECT-012: a Save opcode is not an unconditional fall-through."""
    safe = counter in {0, 7, 23, 32, 35}
    save = bytes([0x24, counter]) + struct.pack("<H", value)
    data = synthetic_room(save + item_command(20, 15, 9) + b"\x01\0")
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert room["candidate_list_complete"]
    assert room["collection_item_ids"] == ([9] if safe else [])
    assert room["conditional_item_presence"] == []


@pytest.mark.parametrize("counter", [7, 24, 36, 53, 120])
@pytest.mark.parametrize("after_startup", [False, True])
def test_counter_aliases_cannot_authorize_fresh_conditional_presence(
    counter, after_startup
):
    save = bytes([0x24, counter, 0, 0])
    pickup = item_command(20, 15, 9)
    guarded = bytes([6, 0, 28, 0, 0x21, 4, 7, 0]) + pickup + bytes([8, 0, 1, 0])
    data = synthetic_room(
        bytes([1, 0]),
        (guarded, save + bytes([1, 0])) if after_startup else (save + guarded,),
    )
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert room["collection_item_ids"] == []
    assert room["conditional_item_presence"] == (
        [
            {
                "global_id": 9,
                "presence": {
                    "kind": "conditions",
                    "any_of": [[{"bank": 4, "bit": 7, "expected": 0}]],
                },
            }
        ]
        if counter == 7
        else []
    )


@pytest.mark.parametrize("counter", [7, 32, 36, 104])
def test_scheduled_delivery_reuses_the_counter_write_guard(counter):
    from games.re2.event_presence import source_presence

    save = bytes([0x24, counter, 51, 0])
    data = synthetic_room(
        bytes([1, 0]),
        (save + bytes([4, 255, 0x18, 1, 1, 0]), save + bytes([0x76, 53, 1, 1, 0])),
    )
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", award["offset"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "required" if counter in (7, 32) else "unresolved"}


def test_counter_setup_without_an_explicit_proof_stays_unresolved():
    data = synthetic_room(bytes([0x24, 7, 0, 0]) + item_command(20, 15, 9) + b"\x01\0")
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, frozenset(), presence_writes=PRESENCE_WRITES
    )
    assert not room["collection_item_ids"] and not room["conditional_item_presence"]


def synthetic_room(init, main_procedures=(b"\x01\0",)):
    data = bytearray(132)
    data[1] = 1
    struct.pack_into("<I", data, 8 + 7 * 4, 100)
    struct.pack_into("<I", data, 8 + 16 * 4, 132)
    data.extend(b"\x02\0" + init)
    struct.pack_into("<I", data, 8 + 17 * 4, len(data))
    offset = 2 * len(main_procedures)
    for procedure in main_procedures:
        data.extend(struct.pack("<H", offset))
        offset += len(procedure)
    data.extend(b"".join(main_procedures))
    return bytes(data)


def switch_command(case_bodies, tail):
    body = (
        b"".join(
            bytes([0x14, 0]) + struct.pack("<HH", len(commands), value) + commands
            for value, commands in enumerate(case_bodies)
        )
        + tail
        + bytes([0x16, 0])
    )
    return bytes([0x13, 0]) + struct.pack("<H", len(body)) + body


@pytest.mark.parametrize("default", [False, True])
def test_switch_catalog_includes_cases_after_returns_and_the_post_switch_path(default):
    """RE2-SCD-002: source coverage includes all choices, not one live selector."""
    tail = bytes([0x15, 0, 0x76, 53, 1, 1, 0]) if default else b""
    script = (
        switch_command((bytes([1, 0]), item_command(20, 15, 9) + bytes([1, 0])), tail)
        + item_command(30, 1, 10, slot=9)
        + bytes([1, 0])
    )
    room = decode_room(
        synthetic_room(script),
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        PRESENCE_WRITES,
    )
    assert room["candidate_list_complete"]
    assert {item["global_id"] for item in room["items"]} == {9, 10}
    assert sum(
        command["kind"] == "award"
        for program in room["programs"].values()
        for command in program["commands"]
    ) == int(default)
    # Cataloging every branch does not establish mandatory startup delivery.
    assert room["collection_item_ids"] == []
    assert room["conditional_item_presence"] == []


def test_nested_switches_and_default_preserve_every_candidate():
    inner = switch_command((bytes([1, 0]), item_command(20, 15, 9)), b"")
    outer = switch_command(
        (inner + bytes([1, 0]),),
        bytes([0x15, 0]) + item_command(30, 1, 10, slot=9) + bytes([1, 0]),
    )
    room = decode_room(
        synthetic_room(outer + bytes([1, 0])),
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        PRESENCE_WRITES,
    )
    assert room["candidate_list_complete"]
    assert {item["global_id"] for item in room["items"]} == {9, 10}
    assert room["collection_item_ids"] == []


@pytest.mark.parametrize("bodies", [(), (b"", b""), (bytes([0x1A, 0]), bytes([1, 0]))])
def test_item_free_switches_have_complete_empty_lists(bodies):
    room = decode_room(
        synthetic_room(switch_command(bodies, b"") + bytes([1, 0])),
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        PRESENCE_WRITES,
    )
    assert room["candidate_list_complete"]
    assert room["items"] == []


@pytest.mark.parametrize(
    "mutation", ["exit", "closing", "case_target", "case_body", "overlap"]
)
def test_malformed_switches_cannot_establish_coverage(mutation):
    script = bytearray(switch_command((item_command(20, 15, 9),), b"") + bytes([1, 0]))
    if mutation == "exit":
        struct.pack_into("<H", script, 2, len(script))
    elif mutation == "closing":
        script[-4] = 0
    elif mutation == "case_target":
        struct.pack_into("<H", script, 6, len(script))
    elif mutation == "case_body":
        struct.pack_into("<H", script, 6, 1)
    else:
        # A valid-looking end marker inside an item's operand is not a
        # command boundary and cannot authorize a negative item-list proof.
        struct.pack_into("<H", script, 2, 20)
        struct.pack_into("<H", script, 6, 12)
        script[22:24] = bytes([0x16, 0])
    with pytest.raises(ValueError, match="switch|overlapping"):
        decode_room(
            synthetic_room(bytes(script)),
            "synthetic",
            PRESENCE_FLAGS,
            PRESENCE_COUNTERS,
            PRESENCE_WRITES,
        )


@pytest.mark.parametrize("marker", [0x14, 0x15, 0x16])
def test_orphan_switch_markers_leave_candidate_coverage_unresolved(marker):
    packet = bytes([marker, 0]) + (bytes(4) if marker == 0x14 else b"")
    room = decode_room(
        synthetic_room(packet + bytes([1, 0])),
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        PRESENCE_WRITES,
    )
    assert not room["candidate_list_complete"]


@pytest.mark.parametrize("truncated", [False, True])
def test_sound_proofs_hash_only_the_stable_source_bytes(truncated):
    data = bytearray(synthetic_room(b"\x01\0"))
    offset = len(data)
    struct.pack_into("<2I", data, 8, offset, offset + 192)
    edt, header = bytes(range(192)), bytes(range(32))
    data.extend(edt + header)
    if truncated:
        with pytest.raises(ValueError, match="sound proof outside"):
            decode_room(
                bytes(data[:-1]),
                "synthetic",
                PRESENCE_FLAGS,
                PRESENCE_COUNTERS,
                PRESENCE_WRITES,
            )
    else:
        data.extend(b"mutable program records")
        room = decode_room(
            bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
        )
        assert room["sound_proofs"] == [
            {
                "section": index,
                "width": len(packet),
                "sha256": hashlib.sha256(packet).hexdigest(),
            }
            for index, packet in enumerate((edt, header))
        ]


def item_command(item_type, amount, gid, slot=8):
    item = bytearray(22)
    item[0:4] = bytes([0x4E, slot, 2, 0x31])
    struct.pack_into("<3H", item, 14, item_type, amount, gid)
    return bytes(item)


@pytest.mark.parametrize(
    "case,bound",
    [
        ("exclusive", True),
        ("clear", False),
        ("toggle", False),
        ("story-bank", False),
        ("not-adjacent", False),
        ("ordinary-alias", False),
        ("reset-alias", False),
        ("other-source-writer", False),
        ("undecoded-writer", False),
        ("branch-bypass", False),
    ],
)
def test_event_award_requires_an_exclusive_post_delivery_item_flag(case, bound):
    write = bytes(
        [
            0x22,
            4 if case == "story-bank" else 8,
            5,
            0 if case == "clear" else 2 if case == "toggle" else 1,
        ]
    )
    delivery = (
        bytes([0x76, 53, 1]) + (bytes([0]) if case == "not-adjacent" else b"") + write
    )
    if case == "branch-bypass":
        # The false branch enters the flag write without delivering anything.
        delivery = bytes([6, 0, 7, 0, 0x21, 4, 7, 0]) + delivery
    data = synthetic_room(bytes([1, 0]), (delivery + bytes([1, 0]),))
    first = {
        **decode_room(
            data,
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        ),
        "id": "01-02",
        "stage": 1,
    }
    other_data = synthetic_room(
        item_command(20, 15, 5) + bytes([1, 0])
        if case == "ordinary-alias"
        else bytes([0x46, 9, 2, 0, 20, 0, 1, 0, 5, 0, 1, 0])
        if case == "reset-alias"
        else bytes([0x22, 8, 5, 1, 1, 0])
        if case == "other-source-writer"
        else bytes([1, 0])
    )
    if case == "undecoded-writer":
        # Conservatively reject a writer even beyond an early script return.
        other_data += bytes([0x22, 8, 5, 2])
    other = {
        **decode_room(
            other_data,
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        ),
        "id": "00-01",
        "stage": 0,
    }
    result = bind_event_awards(
        [first, other],
        {"01-02": data, "00-01": other_data},
        {0: 8, 1: 8},
        PRESENCE_FLAGS,
    )
    assert result["00-01"] == []
    assert result["01-02"][0]["collection"] == (
        {"kind": "flag", "bank": 8, "bit": 5} if bound else {"kind": "unresolved"}
    )


def test_generated_event_award_has_collection_and_conditional_presence_proofs():
    rooms = json.loads((ROOT / "data/rooms_slus00421.json").read_text())["rooms"]
    awards = [(room["id"], award) for room in rooms for award in room["event_awards"]]
    assert len(awards) == 1
    source, award = awards[0]
    assert source == "01-02"
    assert (award["offset"], award["item_type"], award["amount"]) == (8944, 53, 1)
    assert award["collection"] == {"kind": "flag", "bank": 8, "bit": 5}
    assert award["presence"] == {
        "kind": "conditions",
        "any_of": [
            [{"bank": 1, "bit": 1, "expected": 0}, {"bank": 4, "bit": 7, "expected": 0}]
        ],
    }


def test_conditional_return_does_not_hide_later_pickup():
    item = bytearray(22)
    item[0:4] = bytes([0x4E, 8, 2, 0x31])
    struct.pack_into("<3H", item, 14, 20, 15, 9)
    data = synthetic_room(
        bytes([6, 0, 8, 0, 0x21, 4, 0, 1, 1, 0, 0, 0]) + item + bytes([1, 0])
    )
    result = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert result["items"] == [
        {
            "offset": 146,
            "slot": 8,
            "type": 20,
            "amount": 15,
            "amounts": [15],
            "global_id": 9,
            "four_point": False,
        }
    ]
    assert result["proofs"][0]["sha256"] == hashlib.sha256(bytes(24)).hexdigest()
    assert result["collection_item_ids"] == []


def test_inactive_reward_keeps_its_initializer_collection_identity():
    data = synthetic_room(
        item_command(20, 15, 9) + bytes([0x46, 8, 0, 0, 0, 0, 0, 0, 0, 0, 1, 0])
    )
    assert decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [9]


@pytest.mark.parametrize("second_type,expected", [(20, [9]), (21, [])])
def test_presence_joins_branches_only_when_every_path_has_the_same_identity(
    second_type, expected
):
    # Both branches create ID 9; differing amounts do not change identity.
    script = (
        bytes([6, 0, 30, 0, 0x21, 4, 0, 1])
        + item_command(20, 15, 9)
        + bytes([7, 0, 28, 0])
        + item_command(second_type, 30, 9)
        + bytes([0, 0, 1, 0])
    )
    assert (
        decode_room(
            synthetic_room(script),
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == expected
    )


def test_optional_creator_and_uncalled_procedure_do_not_establish_presence():
    optional = (
        bytes([6, 0, 28, 0, 0x21, 4, 0, 1])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    assert (
        decode_room(
            synthetic_room(optional),
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )
    data = synthetic_room(
        bytes([1, 0]), (bytes([1, 0]), item_command(20, 15, 9) + bytes([1, 0]))
    )
    assert (
        decode_room(
            data,
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )


def test_init_gosub_uses_main_table_and_returns_to_its_caller():
    data = synthetic_room(
        bytes([0x18, 1]) + item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), item_command(30, 1, 10, slot=9) + bytes([0x19, 0])),
    )
    assert decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [
        9,
        10,
    ]


@pytest.mark.parametrize(
    "prefix,suffix",
    [
        (bytes([2]), b""),  # Unsupported task control.
        (bytes([0x21, 4, 0, 1]), b""),  # Predicate outside a supported if.
        (b"", bytes([0x46, 8, 2, 0, 21, 0, 15, 0, 9, 0])),  # Identity reset.
        (b"", bytes([0x2C, 8, 0, 0]) + bytes(16)),  # Slot repurposed.
    ],
)
def test_unsupported_effects_cannot_authorize_an_item(prefix, suffix):
    data = synthetic_room(prefix + item_command(20, 15, 9) + suffix + bytes([1, 0]))
    assert (
        decode_room(
            data,
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )


def test_recursive_calls_and_missing_callees_cannot_establish_presence():
    for procedure in (0, 255):
        data = synthetic_room(
            bytes([1, 0]),
            (item_command(20, 15, 9) + bytes([0x18, procedure, 1, 0]),),
        )
        assert (
            decode_room(
                data,
                "synthetic",
                PRESENCE_FLAGS,
                presence_counters=PRESENCE_COUNTERS,
                presence_writes=PRESENCE_WRITES,
            )["collection_item_ids"]
            == []
        )


def test_replaced_item_slot_does_not_turn_both_initializers_into_required_items():
    data = synthetic_room(
        item_command(20, 15, 9) + item_command(30, 1, 10) + bytes([1, 0])
    )
    assert (
        decode_room(
            data,
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )


@pytest.mark.parametrize("unrelated_first", [False, True])
@pytest.mark.parametrize("replacement_type,replacement_gid", [(20, 10), (30, 9)])
def test_conflicting_slot_does_not_discard_an_unrelated_item(
    unrelated_first, replacement_type, replacement_gid
):
    conflict = item_command(20, 15, 9) + item_command(
        replacement_type, 1, replacement_gid
    )
    unrelated = item_command(38, 1, 11, slot=9)
    script = unrelated + conflict if unrelated_first else conflict + unrelated
    result = decode_room(
        synthetic_room(script + bytes([1, 0])),
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert result["collection_item_ids"] == [11]


def test_branch_conflicts_leave_an_unconditional_item_proven():
    script = (
        bytes([6, 0, 30, 0, 0x21, 4, 0, 1])
        + item_command(20, 15, 9)
        + bytes([7, 0, 28, 0])
        + item_command(30, 1, 10)
        + bytes([0, 0])
        + item_command(38, 1, 11, slot=9)
        + bytes([1, 0])
    )
    assert decode_room(
        synthetic_room(script),
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [11]


def test_conflicting_acquisition_identity_across_slots_stays_unproven():
    script = (
        item_command(20, 15, 9)
        + item_command(30, 1, 9, slot=9)
        + item_command(38, 1, 11, slot=10)
        + bytes([1, 0])
    )
    assert decode_room(
        synthetic_room(script),
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [11]


def test_uncalled_conflict_does_not_create_an_item_or_erase_unrelated_proof():
    data = synthetic_room(
        item_command(20, 15, 9) + item_command(38, 1, 11, slot=9) + bytes([1, 0]),
        (bytes([1, 0]), item_command(30, 1, 10) + bytes([1, 0])),
    )
    assert decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [11]


def test_unsupported_control_flow_still_discards_independent_item_proofs():
    script = (
        item_command(38, 1, 11, slot=9)
        + item_command(20, 15, 9)
        + item_command(30, 1, 10)
        + bytes([2, 1, 0])
    )
    assert (
        decode_room(
            synthetic_room(script),
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )


def test_item_initializer_with_an_unresolved_interaction_is_not_a_presence_proof():
    item = bytearray(item_command(20, 15, 9))
    item[2] = 5
    assert (
        decode_room(
            synthetic_room(item + bytes([1, 0])),
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )


def test_unrelated_resets_and_matching_reward_activation_preserve_identity():
    script = (
        bytes([0x46, 0, 5, 0x31, 255, 0, 24, 1, 0, 0])
        + item_command(20, 15, 9)
        + bytes([0x46, 8, 0, 0, 0, 0, 0, 0, 0, 0])
        + bytes([1, 0])
    )
    activation = bytes([0x46, 8, 2, 0x31, 20, 0, 4, 0, 9, 0, 1, 0])
    data = synthetic_room(script, (bytes([1, 0]), activation))
    result = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert result["collection_item_ids"] == [9]
    assert result["items"][0]["amounts"] == [4, 15]


@pytest.mark.parametrize(
    "interaction,item_type,gid", [(2, 21, 9), (2, 20, 10), (5, 20, 9)]
)
def test_later_identity_reset_cannot_authorize_an_earlier_reward(
    interaction, item_type, gid
):
    reset = bytes([0x46, 8, interaction, 0]) + struct.pack("<3H", item_type, 1, gid)
    data = synthetic_room(
        item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), reset + bytes([1, 0])),
    )
    assert (
        decode_room(
            data,
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )


@pytest.mark.parametrize(
    "case,preserved",
    [
        ("matching", True),
        ("changed-amount", True),
        ("fixed-task", False),
        ("task-high-byte", False),
        ("dispatch-marker", False),
        ("reserved-payload", False),
        ("missing-procedure", False),
        ("empty-procedure", False),
        ("padding-before-reset", False),
        ("call-before-reset", False),
        ("conditional-reset", False),
        ("wrong-slot", False),
        ("wrong-type", False),
        ("wrong-acquisition", False),
        ("wrong-kind", False),
        ("later-foreign-reset", False),
        ("conflicting-creator", False),
        ("incomplete-catalog", False),
    ],
)
def test_script_interaction_requires_an_immediate_matching_item_restore(
    case, preserved
):
    """RE2-COLLECT-018: scripted activation cannot replace collection identity."""
    park = bytearray([0x46, 8, 5, 0x31, 255, 0, 24, 1, 0, 0])
    restore = bytearray([0x46, 8, 2, 0, 20, 0, 4, 0, 9, 0])
    prefix, suffix, extra = b"", b"", b""
    if case == "changed-amount":
        restore[6] = 7
    elif case in (
        "fixed-task",
        "task-high-byte",
        "dispatch-marker",
        "reserved-payload",
    ):
        index, value = {
            "fixed-task": (4, 10),
            "task-high-byte": (5, 1),
            "dispatch-marker": (6, 0),
            "reserved-payload": (8, 1),
        }[case]
        park[index] = value
    elif case == "missing-procedure":
        park[7] = 2
    elif case == "empty-procedure":
        restore = b""
    elif case == "padding-before-reset":
        prefix = bytes([0, 0])
    elif case == "call-before-reset":
        prefix = bytes([0x18, 1])
    elif case == "conditional-reset":
        prefix = bytes([6, 0, 16, 0, 0x21, 4, 7, 1])
        suffix = bytes([8, 0])
    elif case in ("wrong-slot", "wrong-type", "wrong-acquisition", "wrong-kind"):
        index, value = {
            "wrong-slot": (1, 9),
            "wrong-type": (4, 21),
            "wrong-acquisition": (8, 10),
            "wrong-kind": (2, 0),
        }[case]
        restore[index] = value
    elif case == "later-foreign-reset":
        suffix = bytes([0x46, 8, 2, 0, 21, 0, 4, 0, 9, 0])
    elif case == "conflicting-creator":
        extra = item_command(21, 4, 10)
    elif case == "incomplete-catalog":
        extra = bytes([0x46, 9, 2, 0, 21, 0, 4, 0, 10, 0])
    data = synthetic_room(
        item_command(20, 15, 9) + park + extra + bytes([1, 0]),
        (bytes([1, 0]), prefix + restore + suffix + bytes([1, 0])),
    )
    result = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert (9 in result["collection_item_ids"]) is preserved
    assert result["conditional_item_presence"] == []
    if preserved:
        assert result["items"][0]["amounts"] == [
            7 if case == "changed-amount" else 4,
            15,
        ]


@pytest.mark.parametrize("creator", ["conditional", "uncalled"])
def test_matching_script_callback_does_not_establish_creator_reachability(creator):
    park = bytes([0x46, 8, 5, 0x31, 255, 0, 24, 1, 0, 0])
    restore = bytes([0x46, 8, 2, 0x31, 20, 0, 15, 0, 9, 0, 1, 0])
    declaration = item_command(20, 15, 9) + park
    data = (
        synthetic_room(
            bytes([6, 0, 38, 0, 0x21, 4, 7, 1]) + declaration + bytes([8, 0, 1, 0]),
            (bytes([1, 0]), restore),
        )
        if creator == "conditional"
        else synthetic_room(
            bytes([1, 0]), (bytes([1, 0]), restore, declaration + bytes([1, 0]))
        )
    )
    result = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert result["collection_item_ids"] == []
    assert result["conditional_item_presence"] == (
        [
            {
                "global_id": 9,
                "presence": {
                    "kind": "conditions",
                    "any_of": [[{"bank": 4, "bit": 7, "expected": 1}]],
                },
            }
        ]
        if creator == "conditional"
        else []
    )


@pytest.mark.parametrize("target_delta", [4, 8])
def test_scheduled_copy_withholds_script_restore_proof_but_keeps_unrelated_items(
    target_delta,
):
    # The scheduled child can overwrite the later callback's kind or amount
    # after startup. A raw entry reset alone cannot prove that lifetime.
    park = bytes([0x46, 8, 5, 0x31, 255, 0, 24, 2, 0, 0])
    restore = bytes([0x46, 8, 2, 0x31, 20, 0, 15, 0, 9, 0, 1, 0])
    data = synthetic_room(
        bytes([0x24, 0, 5, 0])
        + item_command(20, 15, 9)
        + park
        + item_command(30, 1, 10, slot=9)
        + bytes([1, 0]),
        (
            bytes([4, 255, 24, 1, 1, 0]),
            bytes([0x1D, 0, target_delta, 0, 1, 0]),
            restore,
        ),
    )
    result = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert result["collection_item_ids"] == [10]
    assert result["conditional_item_presence"] == []


def test_automatic_task_does_not_make_its_items_mandatory():
    data = synthetic_room(
        bytes([4, 255, 0x18, 1]) + item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), item_command(30, 1, 10, slot=9) + bytes([1, 0])),
    )
    assert decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [9]


def test_reset_without_a_matching_creator_leaves_coverage_unresolved():
    data = synthetic_room(
        item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), bytes([0x46, 9, 2, 0, 30, 0, 1, 0, 10, 0, 1, 0])),
    )
    result = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert not result["candidate_list_complete"]
    assert result["collection_item_ids"] == []


def test_event_slot_replacement_does_not_erase_unrelated_item_proof():
    data = synthetic_room(
        bytes([4, 255, 0x18, 1])
        + item_command(20, 15, 9)
        + item_command(30, 1, 10, slot=9)
        + bytes([1, 0]),
        (bytes([1, 0]), bytes([0x2C, 8, 5, 0]) + bytes(16) + bytes([1, 0])),
    )
    assert decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [10]


@pytest.mark.parametrize("task,procedure", [(0, 1), (1, 1), (9, 1), (255, 255)])
def test_explicit_or_missing_tasks_do_not_prove_startup_execution(task, procedure):
    data = synthetic_room(
        bytes([4, task, 0x18, procedure]) + item_command(20, 15, 9) + bytes([1, 0])
    )
    assert (
        decode_room(
            data,
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )["collection_item_ids"]
        == []
    )


def test_audited_actor_setup_does_not_block_later_reward_declaration():
    setup = bytes.fromhex(
        "2e0300 3d1000 260005100400 350010 3200bec1000089c6 4b0007 6e000b020000"
    )
    data = synthetic_room(setup + item_command(20, 15, 9) + bytes([1, 0]))
    assert decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["collection_item_ids"] == [9]


def test_truncated_script_and_branch_outside_procedure_are_rejected():
    with pytest.raises(ValueError, match="truncated"):
        decode_room(
            synthetic_room(bytes([0x4E, 0])),
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )
    with pytest.raises(ValueError, match="outside its procedure"):
        decode_room(
            synthetic_room(bytes([6, 0, 255, 0, 1, 0])),
            "synthetic",
            PRESENCE_FLAGS,
            presence_counters=PRESENCE_COUNTERS,
            presence_writes=PRESENCE_WRITES,
        )


def test_diagonal_floor_contacts_preserve_both_disconnected_cells():
    rings, label = trace_floor_cells({(0, 0), (1, 1)})
    assert len(rings) == 2
    assert sum(area for area, _ in rings) == 2
    assert label in {(0, 0), (1, 1)}


@pytest.mark.parametrize("transpose", [False, True])
def test_native_door_openings_keep_their_boundary_span(transpose):
    cells = {(x, y): 1 for x in range(10) for y in range(12)}
    # Include a doorway on each side, plus an interior mark that cannot
    # establish a wall opening and a single-pixel edge mark to reject.
    for x, y in [
        (0, 3),
        (0, 4),
        (9, 7),
        (9, 8),
        (4, 0),
        (5, 0),
        (6, 11),
        (7, 11),
        (5, 5),
        (0, 9),
    ]:
        cells[x, y] = 3
    expected = [
        [[4, 0], [6, 0]],
        [[10, 7], [10, 9]],
        [[6, 12], [8, 12]],
        [[0, 3], [0, 5]],
    ]
    if transpose:
        cells = {point[::-1]: shade for point, shade in cells.items()}
        expected = [[point[::-1] for point in segment] for segment in expected]
    rings, _ = trace_floor_cells(set(cells))
    actual = map_door_segments(cells, [ring for _, ring in rings])
    assert {frozenset(map(tuple, segment)) for segment in actual} == {
        frozenset(map(tuple, segment)) for segment in expected
    }


def test_native_door_openings_do_not_invent_doors_from_other_map_shades():
    rings = [[[0, 0], [6, 0], [6, 6], [0, 6]]]
    for shade in (1, 2, 4):
        cells = {(x, y): shade for x in range(6) for y in range(6)}
        assert map_door_segments(cells, rings) == []


@pytest.mark.parametrize("transpose", [False, True])
def test_interior_wall_is_retained_without_redrawing_the_perimeter(transpose):
    """RE2-MAP-003: a wall connects the border to an open passage."""
    cells = {
        (x, y): 4 if x < 2 or x >= 8 or y < 2 or y >= 6 else 1
        for x in range(10)
        for y in range(8)
    }
    cells.update({(x, y): 4 for x in range(6) for y in (3, 4)})
    expected = [[[x + 0.5, 3.5], [x + 0.5, 4.5]] for x in range(2, 6)]
    if transpose:
        cells = {point[::-1]: value for point, value in cells.items()}
        expected = [[point[::-1] for point in segment] for segment in expected]
    assert map_detail_segments(cells) == expected


@pytest.mark.parametrize("end_shade", [0, 1, 3])
def test_wall_runs_need_floor_on_both_sides(end_shade):
    cells = {(x, y): 1 for x in range(5) for y in range(5)}
    cells.update({(1, 2): 4, (2, 2): 4})
    if end_shade:
        cells[3, 2] = end_shade
    else:
        del cells[3, 2]
    assert map_detail_segments(cells) == (
        [[[1.5, 2.5], [2.5, 2.5]]] if end_shade == 1 else []
    )


def test_existing_interior_rails_keep_their_segments():
    cells = {(x, y): 1 for x in range(5) for y in range(5)}
    cells.update({(x, 2): 2 for x in range(1, 4)})
    cells.update({(x, 0): 2 for x in range(1, 4)})
    assert map_detail_segments(cells) == [[[1.5, 2.5], [3.5, 2.5]]]


@pytest.mark.parametrize("serial", ["00748", "00756"])
def test_basketball_court_retains_its_upper_alley_partition(serial):
    """RE2-MAP-003: native tile wall, distinct from the vertical rail."""
    maps = json.loads((ROOT / f"data/floor_plans_slus{serial}.json").read_text())
    court = next(room for room in maps["areas"][0]["rooms"] if room["id"] == "02")
    # The native wall's leftmost column extends one cell farther into the court.
    for x in range(84, 111):
        assert [[x + 0.5, 117.5], [x + 0.5, 120.5 + (x == 84)]] in court[
            "detail_segments"
        ]
    assert [[111.5, 121.5], [111.5, 138.5]] in court["detail_segments"]


def test_generated_catalog_has_unique_room_proofs_and_only_numeric_map_data():
    rooms = json.loads((ROOT / "data/rooms_slus00421.json").read_text())
    maps = json.loads((ROOT / "data/floor_plans_slus00421.json").read_text())
    assert rooms["executable_identity"] == maps["executable_identity"]
    assert len(rooms["rooms"]) == 125
    signatures = {
        (
            # RE2-SOURCE-001: sound relocation must not collapse room identity.
            tuple(room["section_offsets"][2:]),
            tuple(proof["sha256"] for proof in room["proofs"]),
        )
        for room in rooms["rooms"]
    }
    assert len(signatures) == 125
    assert sum(len(room["items"]) for room in rooms["rooms"]) == 281
    assert sum(len(room["doors"]) for room in rooms["rooms"]) == 321
    assert len(maps["areas"]) == 20
    assert not any("programs" in room for room in rooms["rooms"])
    assert all(
        set(door) == {"id", "observation_id", "rooms", "segment"}
        for area in maps["areas"]
        for door in area["doors"]
    )


@pytest.mark.parametrize("opcode,size,operand", [(0x3B, 32, 22), (0x68, 40, 30)])
@pytest.mark.parametrize("activation_floor", [4, 0x84])
def test_door_trigger_floor_is_separate_from_destination(
    opcode, size, operand, activation_floor
):
    packet = bytearray(size)
    packet[:6] = bytes([opcode, 0, 1, 0x31, activation_floor, 0])
    packet[operand + 3] = 1
    door = decode_room(
        synthetic_room(packet + b"\x01\0"),
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )["doors"][0]
    assert door["activation_floor"] == activation_floor
    assert door["floor"] == 1


def test_native_split_room_door_markers_belong_to_their_trigger_floor():
    """RE2-MAP-002: both source sides have captured native crossings."""
    maps = json.loads((ROOT / "data/floor_plans_slus00421.json").read_text())
    markers = {
        (area["id"], door["id"]): door
        for area in maps["areas"]
        for door in area["doors"]
    }
    assert ("re2-03", "00-16:2522:0D") not in markers
    for area, marker, segment in (
        ("re2-03", "00-09:8432:01", [[240, 159.756], [240, 157.756]]),
        ("re2-03", "00-16:2554:0D", [[248, 159.524], [248, 157.524]]),
        ("re2-02", "00-16:2522:11", [[251, 164.598], [251, 162.598]]),
        ("re2-02", "01-0b:12160:0B", [[251, 161.913], [251, 163.913]]),
    ):
        assert markers[area, marker]["segment"] == segment


@pytest.mark.parametrize(
    "case",
    [
        "direct",
        "guarded",
        "unconditional",
        "opaque-bypass",
        "startup-write",
        "abort-delivery",
        "recursive",
        "deep",
    ],
)
def test_event_presence_proves_scheduling_and_every_supported_delivery_path(case):
    from games.re2.event_presence import source_presence

    schedule = bytes([4, 255, 0x18, 1])
    startup = schedule + bytes([1, 0])
    if case == "guarded":
        startup = bytes([6, 0, 10, 0, 0x21, 4, 7, 0]) + schedule + bytes([8, 0, 1, 0])
    elif case == "opaque-bypass":
        startup = (
            bytes([6, 0, 12, 0, 0x3E, 0, 0, 0, 0, 0]) + schedule + bytes([8, 0, 1, 0])
        )
    elif case == "startup-write":
        startup = bytes([0x22, 4, 7, 0]) + startup
    elif case == "direct":
        startup = bytes([1, 0])
    elif case == "deep":
        startup = bytes(300) + startup
    delivery = bytes([0x76, 53, 1, 0x22, 8, 5, 1, 1, 0])
    if case == "abort-delivery":
        delivery = bytes([5, 0]) + delivery
    elif case == "recursive":
        delivery = bytes([0x18, 1]) + delivery
    data = synthetic_room(bytes([1, 0]), (startup, delivery))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    result = source_presence(
        data,
        room["programs"],
        {("17:1", award["offset"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    )
    assert result == (
        {"kind": "conditions", "any_of": [[{"bank": 4, "bit": 7, "expected": 0}]]}
        if case == "guarded"
        else {"kind": "required"}
        if case == "unconditional"
        else {"kind": "unresolved"}
    )


def test_event_presence_joins_both_scheduling_branches_without_an_unrelated_gate():
    from games.re2.event_presence import source_presence

    schedule = bytes([4, 255, 0x18, 1])
    startup = (
        bytes([6, 0, 12, 0, 0x21, 4, 7, 0])
        + schedule
        + bytes([7, 0, 10, 0])
        + schedule
        + bytes([0, 0, 1, 0])
    )
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    award = room["programs"]["17:1"]["entry"]
    assert source_presence(
        data,
        room["programs"],
        {("17:1", award)},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "required"}


@pytest.mark.parametrize("wait_change", [False, True])
def test_event_presence_preserves_a_waiting_award_but_rejects_changed_wait_effects(
    wait_change,
):
    from games.re2.event_presence import source_presence

    startup = bytes([4, 255, 0x18, 1, 1, 0])
    delivery = bytes([0x18, 2, 0x76, 53, 1, 1, 0])
    wait = bytes([0x11, 0, 8, 0, 2, 0, 0x12, 4, 0x21, 5, 33, 0, 1, 0])
    if wait_change:
        wait = bytes([5, 0, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, delivery, wait))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", award["offset"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == ({"kind": "unresolved"} if wait_change else {"kind": "required"})


def test_event_presence_rejects_a_delivery_path_that_can_finish_without_awarding():
    from games.re2.event_presence import source_presence

    startup = bytes([4, 255, 0x18, 1, 1, 0])
    delivery = bytes([6, 0, 7, 0, 0x21, 4, 7, 0, 0x76, 53, 1, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, delivery))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", award["offset"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "unresolved"}


def test_startup_write_cannot_make_an_unexecuted_branch_look_required():
    from games.re2.event_presence import source_presence

    # If the clear branch sets its own guard and skips scheduling, the final
    # set bit cannot prove that the scheduling branch ran.
    startup = bytes(
        [
            6,
            0,
            12,
            0,
            0x21,
            4,
            7,
            0,
            0x22,
            4,
            7,
            1,
            7,
            0,
            10,
            0,
            4,
            255,
            0x18,
            1,
            0,
            0,
            1,
            0,
        ]
    )
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", room["programs"]["17:1"]["entry"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "unresolved"}


def test_compound_predicates_need_a_native_join_proof_before_exporting_conditions():
    from games.re2.event_presence import source_presence

    startup = bytes(
        [6, 0, 14, 0, 0x21, 4, 7, 0, 0x21, 6, 28, 0, 4, 255, 0x18, 1, 8, 0, 1, 0]
    )
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", room["programs"]["17:1"]["entry"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "unresolved"}


def test_later_task_cancellation_invalidates_an_earlier_scheduling_proof():
    from games.re2.event_presence import source_presence

    startup = bytes([4, 255, 0x18, 1, 5, 10, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", room["programs"]["17:1"]["entry"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "unresolved"}


def test_startup_must_finish_after_queuing_the_award_task():
    from games.re2.event_presence import source_presence

    # Aot_on can transition away before queued tasks run. It is deliberately
    # outside the synchronous initializer proof even after the fork succeeds.
    startup = bytes([4, 255, 0x18, 1, 0x47, 0, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", room["programs"]["17:1"]["entry"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "unresolved"}


@pytest.mark.parametrize(
    "case,expected",
    [
        ("guarded", "conditions"),
        ("unconditional", "required"),
        ("same-identity-alternatives", "required"),
        ("startup-write", None),
        ("post-creator-transition", None),
        ("scheduled-only", None),
        ("slot-replacement", None),
        ("reset-replacement", None),
        ("different-type-alternatives", None),
    ],
)
def test_conditional_pickup_proof_preserves_identity_and_startup_conditions(
    case, expected
):
    pickup = item_command(20, 15, 9)
    # Each branch is conditional to the old proof, while their common pickup
    # identity can still be necessary under the shared source proof.
    guarded = bytes([6, 0, 28, 0, 0x21, 4, 7, 0]) + pickup + bytes([8, 0])
    startup = guarded + bytes([1, 0])
    procedures = ()
    if case == "unconditional":
        # An unrelated opaque actor test previously discarded every item proof.
        startup = (
            bytes([6, 0, 8, 0, 0x3E, 0, 0, 0, 0, 0, 8, 0]) + pickup + bytes([1, 0])
        )
    elif case in ("same-identity-alternatives", "different-type-alternatives"):
        other = item_command(21 if case == "different-type-alternatives" else 20, 15, 9)
        startup = (
            bytes([6, 0, 30, 0, 0x21, 4, 7, 0])
            + pickup
            + bytes([7, 0, 26, 0])
            + other
            + bytes([0, 0, 1, 0])
        )
        startup = bytes([6, 0, 8, 0, 0x3E, 0, 0, 0, 0, 0, 8, 0]) + startup
    elif case == "startup-write":
        startup = bytes([0x22, 4, 7, 0]) + startup
    elif case == "post-creator-transition":
        startup = guarded + bytes([0x47, 0, 1, 0])
    elif case == "scheduled-only":
        procedures = (pickup + bytes([1, 0]),)
        startup = bytes([4, 255, 0x18, 1, 1, 0])
    elif case == "slot-replacement":
        replacement = bytes([0x2C, 8, 4]) + bytes(17)
        procedures = (replacement + bytes([1, 0]),)
    elif case == "reset-replacement":
        procedures = (bytes([0x46, 8, 2, 0, 21, 0, 15, 0, 9, 0, 1, 0]),)
    room = decode_room(
        synthetic_room(bytes([1, 0]), (startup, *procedures)),
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert room["collection_item_ids"] == []
    assert room["conditional_item_presence"] == (
        []
        if expected is None
        else [
            {
                "global_id": 9,
                "presence": {
                    "kind": expected,
                    **(
                        {"any_of": [[{"bank": 4, "bit": 7, "expected": 0}]]}
                        if expected == "conditions"
                        else {}
                    ),
                },
            }
        ]
    )


def test_fixed_context_does_not_expand_the_general_stable_flag_whitelist():
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    assert {"bank": 0, "bit": 25} not in raw["presence_condition_flags"]
    rooms = json.loads((ROOT / "data/rooms_slus00421.json").read_text())["rooms"]
    room = next(room for room in rooms if room["id"] == "01-02")
    # RE2-COLLECT-019 binds the mode only after whole-source validation.
    # Its impossible presence branch cannot override the existing exclusion.
    assert room["fixed_context_preserved"]
    assert 116 in room["scenario_absent_item_ids"]
    assert all(rule["global_id"] != 116 for rule in room["conditional_item_presence"])
    assert next(
        rule for rule in room["conditional_item_presence"] if rule["global_id"] == 114
    )["presence"] == {"kind": "required"}


@pytest.mark.parametrize("operation", range(9))
@pytest.mark.parametrize("counter", [0, 27, 255])
def test_counter_comparisons_require_common_pickup_reachability(operation, counter):
    """RE2-COLLECT-015: no live counter value is exported as a condition."""
    comparison = bytes([0x23, 0, counter, operation, 2, 5])
    startup = bytes([6, 0, 8, 0]) + comparison + bytes([8, 0])
    startup += item_command(20, 15, 9) + bytes([1, 0])
    room = decode_room(
        synthetic_room(bytes([1, 0]), (startup,)),
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        PRESENCE_WRITES,
    )
    assert room["conditional_item_presence"] == (
        [{"global_id": 9, "presence": {"kind": "required"}}] if operation < 7 else []
    )


@pytest.mark.parametrize(
    "case,proved",
    [
        ("common", True),
        ("callee-return", True),
        ("one-sided", False),
        ("inline-return", False),
        ("transition", False),
        ("flag-write", False),
        ("counter-write", False),
        ("compound", False),
        ("standalone", False),
        ("unsupported-operator", False),
    ],
)
def test_counter_comparisons_preserve_branch_and_startup_guards(case, proved):
    comparison = bytes([0x23, 0, 27, 0, 2, 5])
    body = bytes([0, 0])
    if case in ("callee-return", "inline-return"):
        body = bytes([1, 0])
    elif case == "transition":
        body = bytes([0x47, 0, 1, 0])
    elif case == "flag-write":
        body = bytes([0x22, 4, 7, 1])
    elif case == "counter-write":
        body = bytes([0x24, 24, 0, 0])
    elif case == "compound":
        comparison += bytes([0x21, 4, 7, 0])
    elif case == "unsupported-operator":
        comparison = bytes([0x23, 0, 27, 255, 2, 5])
    pickup = item_command(20, 15, 9)
    if case == "one-sided":
        body = pickup
    branch = (
        bytes([6, 0])
        + struct.pack("<H", len(comparison) + len(body))
        + comparison
        + body
        + bytes([8, 0])
    )
    extra = ()
    if case == "callee-return":
        startup = bytes([0x18, 1]) + pickup + bytes([1, 0])
        extra = (branch + bytes([1, 0]),)
    elif case == "standalone":
        startup = comparison + pickup + bytes([1, 0])
    else:
        startup = branch + (b"" if case == "one-sided" else pickup) + bytes([1, 0])
    room = decode_room(
        synthetic_room(bytes([1, 0]), (startup, *extra)),
        "synthetic",
        PRESENCE_FLAGS,
        PRESENCE_COUNTERS,
        PRESENCE_WRITES,
    )
    assert room["conditional_item_presence"] == (
        [{"global_id": 9, "presence": {"kind": "required"}}] if proved else []
    )


@pytest.mark.parametrize("transition", [False, True])
def test_scheduled_award_requires_startup_to_finish_after_counter_comparison(
    transition,
):
    from games.re2.event_presence import source_presence

    branch = bytes([6, 0, 8, 0, 0x23, 0, 27, 0, 2, 5, 8, 0])
    startup = bytes([4, 255, 0x18, 1]) + branch
    startup += bytes([0x47, 0, 1, 0]) if transition else bytes([1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    assert source_presence(
        data,
        room["programs"],
        {("17:1", award["offset"])},
        "scheduled",
        PRESENCE_FLAGS,
        fixed_flags=frozenset(),
    ) == {"kind": "unresolved" if transition else "required"}


def test_counter_comparison_must_have_a_complete_native_packet():
    with pytest.raises(ValueError, match="truncated"):
        decode_room(
            synthetic_room(bytes([1, 0]), (bytes([0x23, 0, 27, 0, 2]),)),
            "synthetic",
            PRESENCE_FLAGS,
            PRESENCE_COUNTERS,
            PRESENCE_WRITES,
        )


@pytest.mark.parametrize("bank,bit", [(0, 25), (2, 7), (10, 0)])
def test_unapproved_flag_checks_are_opaque_to_pickup_presence(bank, bit):
    item = item_command(20, 15, 9)
    startup = bytes([6, 0, 28, 0, 0x21, bank, bit, 0]) + item + bytes([8, 0, 1, 0])
    room = decode_room(
        synthetic_room(bytes([1, 0]), (startup,)),
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert room["collection_item_ids"] == []
    assert room["conditional_item_presence"] == []


@pytest.fixture
def scenario_banks():
    return json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())[
        "flag_banks"
    ]


@pytest.mark.parametrize(
    "case,excluded",
    [
        ("fixed-false", True),
        ("fixed-true", False),
        ("story", False),
        ("lifecycle", False),
        ("compound", False),
        ("uncalled-creator", False),
        ("second-variant", False),
        ("type-alias", False),
        ("write", False),
        ("reset", False),
        ("generic-item", False),
        ("unsupported", False),
        ("spawn", True),
        ("non-leaf-call", True),
        ("goto-bypass", False),
        ("raw-writer", False),
        ("geometry-pattern", True),
        ("incomplete", False),
        ("budget", False),
        ("cycle", False),
        ("endif-underflow", False),
        ("conditional-depth", False),
    ],
)
def test_scenario_exclusion_proves_every_creator_impossible(
    case, excluded, scenario_banks
):
    from games.re2.scenario_items import scenario_item_proofs

    pickup = item_command(20, 15, 9)
    checks = bytes([0x21, 1, 1, 0 if case == "fixed-true" else 1])
    if case == "story":
        checks = bytes([0x21, 4, 7, 1])
    elif case == "lifecycle":
        checks = bytes([0x21, 0, 25, 1])
    elif case == "compound":
        checks += bytes([0x21, 4, 7, 1])
    guarded = (
        bytes([6, 0, len(checks) + len(pickup) + 2, 0])
        + checks
        + pickup
        + bytes([8, 0])
    )
    startup = guarded + bytes([1, 0])
    extra = ()
    if case == "uncalled-creator":
        extra = (pickup + bytes([1, 0]),)
    elif case == "second-variant":
        startup = guarded + item_command(20, 15, 9, slot=9) + bytes([1, 0])
    elif case == "type-alias":
        startup = (
            guarded
            + bytes([6, 0, 28, 0, 0x21, 1, 1, 1])
            + item_command(30, 1, 9, slot=9)
            + bytes([8, 0, 1, 0])
        )
    elif case == "write":
        startup = bytes([0x22, 1, 1, 1]) + startup
    elif case == "reset":
        extra = (bytes([0x46, 8, 2, 0, 20, 0, 15, 0, 9, 0, 1, 0]),)
    elif case == "generic-item":
        extra = (bytes([0x2C, 9, 2, 0]) + bytes(16) + bytes([1, 0]),)
    elif case == "unsupported":
        extra = (bytes([0x47, 30, 1, 0]),)
    elif case == "spawn":
        startup = bytes([4, 255, 0x18, 1]) + startup
        extra = (bytes([1, 0]),)
    elif case == "non-leaf-call":
        extra = (bytes([0x18, 2, 1, 0]), bytes([1, 0]))
        startup = bytes([0x18, 1]) + startup
    elif case == "goto-bypass":
        startup = bytes([7, 0, 12, 0]) + startup
    elif case == "raw-writer":
        startup += bytes([0x22, 1, 1, 1])
    elif case == "budget":
        startup = bytes(4096) + startup
    elif case == "cycle":
        extra = (bytes([7, 0, 0, 0]),)
    elif case == "endif-underflow":
        extra = (bytes([8, 0, 1, 0]),)
    elif case == "conditional-depth":
        # Unknown predicates explore true paths too. Exceeding the stack bound
        # in another procedure withholds the entire source's negative proof.
        nested = bytes([1, 0])
        for _ in range(9):
            nested = (
                bytes([6, 0, len(nested) + 6, 0, 0x21, 4, 7, 1])
                + nested
                + bytes([8, 0, 1, 0])
            )
        extra = (nested,)
    data = synthetic_room(bytes([1, 0]), (startup, *extra))
    if case == "geometry-pattern":
        # These bytes lie in the camera section, outside every SCD procedure.
        data = data[:108] + bytes([0x22, 1, 1]) + data[111:]
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    if case == "incomplete":
        room["candidate_list_complete"] = False
    assert scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    ).absent_item_ids == ([9] if excluded else [])


@pytest.mark.parametrize("mode", [0, 1])
@pytest.mark.parametrize("writer", ["none", "mode", "alias", "unrelated"])
def test_mode_exclusion_withholds_proof_for_direct_and_aliased_writers(
    mode, writer, scenario_banks
):
    from games.re2.scenario_items import scenario_item_proofs

    pickup = item_command(20, 15, 9)
    startup = bytes([6, 0, 28, 0, 0x21, 0, 25, 0]) + pickup + bytes([8, 0, 1, 0])
    extra = (
        bytes([1, 0])
        if writer == "none"
        else bytes(
            [
                0x22,
                99 if writer == "alias" else 0,
                24 if writer == "unrelated" else 25,
                1,
                1,
                0,
            ]
        )
    )
    data = synthetic_room(bytes([1, 0]), (startup, extra))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    # The native bank table can alias the system word. A different bank number
    # must not hide a writer to the pinned mode bit.
    banks = [*scenario_banks, {"bank": 99, "address_ps1": "0x800C7CE4", "width": 4}]
    assert scenario_item_proofs(
        data,
        room,
        [{"bank": 0, "bit": 25, "expected": mode}],
        banks,
        SCENARIO_EFFECT_POOL,
    ).absent_item_ids == ([9] if mode and writer in ("none", "unrelated") else [])


@pytest.mark.parametrize("fixed,excluded", [(0, True), (1, False)])
def test_scenario_exclusion_tracks_nested_else_frames(fixed, excluded, scenario_banks):
    from games.re2.scenario_items import scenario_item_proofs

    # An opaque nested condition takes either path. Its Else must pop only
    # that frame, leaving the outer fixed guard intact until the outer Else.
    nested = bytes([6, 0, 9, 0, 0x21, 4, 7, 1, 0, 7, 0, 6, 0, 0, 0])
    pickup = item_command(20, 15, 9)
    guarded = (
        bytes([6, 0, len(nested) + 8, 0, 0x21, 1, 1, 0])
        + nested
        + bytes([7, 0, len(pickup) + 4, 0])
        + pickup
        + bytes([1, 0])
    )
    data = synthetic_room(bytes([1, 0]), (guarded,))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": fixed}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    ).absent_item_ids == ([9] if excluded else [])


@pytest.mark.parametrize(
    "case,excluded",
    [
        ("unrelated-write", True),
        ("same-bank-other-bit", True),
        ("aliased-bank-write", False),
        ("unknown-bank-write", False),
        ("out-of-bank-write", False),
        ("unknown-operation", False),
        ("unrelated-reset", True),
        ("reset-alias", False),
        ("bound-item-call", True),
        ("bound-item-status-write", False),
        ("bound-door-status-write", False),
        ("unbound-call", False),
        ("unsupported-dispatch", False),
        ("camera-unrelated", True),
        ("camera-fixed-bit", False),
        ("audio-fixed-bit", False),
        ("message-fixed-bit", False),
        ("opaque-check", True),
        ("opaque-creator", False),
        ("wait", True),
        ("actor-wait", True),
        ("wait-creator", False),
        ("wait-bound", False),
        ("wait-predicate-width", False),
        ("wait-hidden-creator", False),
        ("wait-conditional", False),
        ("unsupported-work", False),
        ("last-actor", True),
        ("out-of-table-actor", False),
        ("negative-actor", False),
        ("negative-object", False),
        ("unresolved-effect", False),
    ],
)
def test_scripted_scenario_exclusion_audits_mutations_and_all_creators(
    scenario_banks, case, excluded
):
    from games.re2.scenario_items import scenario_item_proofs

    pickup = item_command(20, 15, 9)
    guarded = bytes([6, 0, 28, 0, 0x21, 1, 1, 1]) + pickup + bytes([8, 0, 1, 0])
    extra = bytes([1, 0])
    fixed = [{"bank": 1, "bit": 1, "expected": 0}]
    if case in ("unrelated-write", "aliased-bank-write"):
        extra = bytes([0x22, 5, 1, 1, 1, 0])
        if case == "aliased-bank-write":
            next(row for row in scenario_banks if row["bank"] == 5)["address_ps1"] = (
                "0x800C7D04"
            )
    elif case == "same-bank-other-bit":
        extra = bytes([0x22, 1, 27, 1, 1, 0])
    elif case == "unknown-bank-write":
        extra = bytes([0x22, 255, 0, 1, 1, 0])
    elif case == "out-of-bank-write":
        extra = bytes([0x22, 1, 32, 1, 1, 0])
    elif case == "unknown-operation":
        extra = bytes([0x22, 5, 1, 2, 1, 0])
    elif case in ("unrelated-reset", "reset-alias"):
        extra = (
            b"" if case == "reset-alias" else item_command(20, 15, 10, slot=9)
        ) + bytes(
            [
                0x46,
                8 if case == "reset-alias" else 9,
                2,
                0,
                20,
                0,
                15,
                0,
                9 if case == "reset-alias" else 10,
                0,
                1,
                0,
            ]
        )
    elif case in ("bound-item-call", "bound-item-status-write"):
        extra = bytes([0x47, 8, 1, 0])
        if case == "bound-item-status-write":
            fixed.append({"bank": 1, "bit": 16, "expected": 0})
    elif case == "bound-door-status-write":
        extra = bytes([0x3B, 9, 1, 0]) + bytes(28) + bytes([0x47, 9, 1, 0])
        fixed.append({"bank": 2, "bit": 0, "expected": 0})
    elif case == "unbound-call":
        extra = bytes([0x47, 30, 1, 0])
    elif case == "unsupported-dispatch":
        extra = bytes([0x2C, 9, 6, 0]) + bytes(16) + bytes([0x47, 9, 1, 0])
    elif case.startswith("camera"):
        extra = bytes([0x3C, 0, 1, 0])
        if case == "camera-fixed-bit":
            fixed.append({"bank": 1, "bit": 23, "expected": 0})
    elif case == "audio-fixed-bit":
        extra = bytes([0x59, 0, 0, 0, 1, 0])
        fixed.append({"bank": 1, "bit": 26, "expected": 0})
    elif case == "message-fixed-bit":
        extra = bytes([0x2B, 0, 0, 0, 0, 1, 1, 0])
        fixed.append({"bank": 2, "bit": 7, "expected": 0})
    elif case in ("opaque-check", "opaque-creator"):
        extra = (
            bytes([6, 0, 30, 0, 0x23, 0, 0, 0, 0, 0])
            + (pickup if case == "opaque-creator" else item_command(30, 1, 10))
            + bytes([8, 0, 1, 0])
        )
    elif case.startswith("wait") or case == "actor-wait":
        predicate = (
            bytes([0x3E, 0, 0, 0, 0, 0])
            if case == "actor-wait"
            else bytes([0x21, 5, 1, 0])
        )
        body = pickup if case == "wait-creator" else bytes([2, 0])
        if case == "wait-hidden-creator":
            predicate = pickup
        end = len(body) + 2 + len(predicate)
        extra = (
            bytes([0x11, 0, end, 0])
            + body
            + bytes([0x12, len(predicate)])
            + predicate
            + bytes([1, 0])
        )
        if case == "wait-bound":
            extra = extra[:2] + bytes([end - 1, 0]) + extra[4:]
        elif case == "wait-predicate-width":
            position = 4 + len(body) + 1
            extra = (
                extra[:position] + bytes([len(predicate) + 2]) + extra[position + 1 :]
            )
        elif case == "wait-conditional":
            extra = guarded[:-2] + extra + bytes([1, 0])
    elif case == "unsupported-work":
        extra = bytes([0x2E, 6, 0, 1, 0])
    elif case in (
        "last-actor",
        "out-of-table-actor",
        "negative-actor",
        "negative-object",
    ):
        extra = bytes(
            [
                0x2E,
                4 if case == "negative-object" else 3,
                31
                if case == "last-actor"
                else 32
                if case == "out-of-table-actor"
                else 255,
                1,
                0,
            ]
        )
    elif case == "unresolved-effect":
        extra = bytes([0x58, 0, 0, 0, 0x17, 0, 0, 0, 0, 0, 1, 0])
    data = synthetic_room(bytes([1, 0]), (guarded, extra))
    room = decode_room(
        data,
        "synthetic",
        PRESENCE_FLAGS,
        presence_counters=PRESENCE_COUNTERS,
        presence_writes=PRESENCE_WRITES,
    )
    assert scenario_item_proofs(
        data, room, fixed, scenario_banks, SCENARIO_EFFECT_POOL
    ).absent_item_ids == ([9] if excluded else [])


def test_scenario_exclusions_require_independent_creator_proofs():
    rooms = {
        room["id"]: room
        for room in json.loads((ROOT / "data/rooms_slus00421.json").read_text())[
            "rooms"
        ]
    }
    assert rooms["00-0f"]["scenario_absent_item_ids"] == [157]
    assert rooms["01-03"]["scenario_absent_item_ids"] == [36]
    assert rooms["01-02"]["scenario_absent_item_ids"] == [116, 249]
    assert rooms["01-08"]["scenario_absent_item_ids"] == [158]
    assert rooms["01-09"]["scenario_absent_item_ids"] == [70]
    # RE2-COLLECT-011 adds only a pinned mode predicate. It does not turn
    # opaque activation paths in other sources into absence proofs.
    assert 159 not in rooms["01-08"]["scenario_absent_item_ids"]


@pytest.mark.parametrize("fixed", [0, 1])
@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "unknown-condition",
        "other-creator",
        "reset",
        "writer",
        "alias",
        "unsupported",
        "incomplete",
    ],
)
def test_scenario_variant_proof_requires_every_possible_creator(
    fixed, case, scenario_banks
):
    """RE2-COLLECT-014: a sufficient presence path cannot prove unique identity."""
    from games.re2.room_data import collection_presence
    from games.re2.scenario_items import scenario_item_candidates, scenario_item_proofs

    first = item_command(20, 15, 9)
    second = item_command(21, 30, 9)
    branch = (
        bytes(
            [
                6,
                0,
                30,
                0,
                0x21,
                4 if case == "unknown-condition" else 1,
                7 if case == "unknown-condition" else 1,
                0,
            ]
        )
        + first
        + bytes([7, 0, 28, 0])
        + second
        + bytes([0, 0, 1, 0])
    )
    extra = bytes([1, 0])
    if case == "other-creator":
        extra = (second if fixed == 0 else first) + extra
    elif case == "reset":
        extra = bytes([0x46, 8, 2, 0]) + struct.pack("<3H", 21, 30, 9) + extra
    elif case in ("writer", "alias"):
        extra = bytes([0x22, 99 if case == "alias" else 1, 1, 1]) + extra
    elif case == "unsupported":
        extra = bytes([0x4A, 0, 1, 0])
    data = synthetic_room(bytes([1, 0]), (branch, extra))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    if case == "incomplete":
        room["candidate_list_complete"] = False
    banks = [*scenario_banks, {"bank": 99, "address_ps1": "0x800C7D04", "width": 4}]
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": fixed}],
        banks,
        SCENARIO_EFFECT_POOL,
    )
    absent, variants = proof.absent_item_ids, proof.item_variants
    assert absent == []
    if case != "valid" and not (case == "reset" and fixed == 1):
        assert variants == []
        return
    selected = next(
        item for item in room["items"] if item["type"] == (20 if fixed == 0 else 21)
    )
    assert variants == [{"global_id": 9, "offsets": [selected["offset"]]}]
    room["scenario_item_variants"] = variants
    candidates = scenario_item_candidates(room)
    assert candidates == [selected]
    assert collection_presence(
        data,
        room,
        PRESENCE_FLAGS,
        frozenset(item["offset"] for item in candidates),
        fixed_flags=frozenset(),
    ) == (
        [],
        [
            {
                "global_id": 9,
                "presence": {
                    "kind": "conditions",
                    "any_of": [[{"bank": 1, "bit": 1, "expected": fixed}]],
                },
            }
        ],
    )


@pytest.mark.parametrize(
    "case,selected",
    [
        ("matching", True),
        ("unreachable-alternative", True),
        ("unknown-alternative", False),
        ("uncalled-alternative", False),
        ("opaque-loop-alternative", False),
        ("changed-type", False),
        ("changed-amount", True),
        ("foreign-slot", False),
        ("foreign-id-on-slot", False),
        ("script-on-slot", False),
        ("inactive-zero", True),
        ("inactive-payload", False),
        ("geometry-change", False),
        ("past-registry", False),
        ("negative-slot", False),
        ("copy-reset", False),
        ("incomplete", False),
        ("quantity-set", True),
        ("no-reachable-creator", False),
    ],
)
def test_scenario_variant_includes_every_reachable_reset(
    case, selected, scenario_banks
):
    """RE2-COLLECT-020: reset reachability cannot replace identity/quantity proof."""
    from games.re2.scenario_items import scenario_item_candidates, scenario_item_proofs

    first, second = item_command(20, 15, 9), item_command(21, 30, 9)
    branch = (
        bytes([6, 0, 30, 0, 0x21, 1, 1, 0])
        + first
        + bytes([7, 0, 28, 0])
        + second
        + b"\0\0\x01\0"
    )
    matching = bytes([0x46, 8, 2, 0x31]) + struct.pack("<3H", 20, 15, 9)
    other = bytes([0x46, 8, 2, 0x31]) + struct.pack("<3H", 21, 30, 9)
    extra = matching + b"\x01\0"
    additional = ()
    if case in ("unreachable-alternative", "unknown-alternative"):
        extra = (
            matching
            + bytes(
                [
                    6,
                    0,
                    16,
                    0,
                    0x21,
                    1 if case == "unreachable-alternative" else 4,
                    1 if case == "unreachable-alternative" else 7,
                    1,
                ]
            )
            + other
            + b"\x08\0\x01\0"
        )
    elif case == "uncalled-alternative":
        additional = (other + b"\x01\0",)
    elif case == "opaque-loop-alternative":
        # A zero-count loop is deliberately opaque in the negative analysis.
        extra = matching + bytes([0x0D, 0, 12, 0, 0, 0]) + other + b"\x0e\0\x01\0"
    elif case == "changed-type":
        extra = other + b"\x01\0"
    elif case == "changed-amount":
        extra = matching[:6] + struct.pack("<H", 16) + matching[8:] + b"\x01\0"
    elif case == "foreign-slot":
        extra = bytes([0x46, 9]) + matching[2:] + b"\x01\0"
        additional = (
            bytes([6, 0, 28, 0, 0x21, 1, 1, 1])
            + item_command(20, 15, 9, slot=9)
            + b"\x08\0\x01\0",
        )
    elif case == "foreign-id-on-slot":
        extra = matching[:8] + struct.pack("<H", 10) + b"\x01\0"
        additional = (
            bytes([6, 0, 28, 0, 0x21, 1, 1, 1])
            + item_command(20, 15, 10)
            + b"\x08\0\x01\0",
        )
    elif case == "script-on-slot":
        extra = bytes([0x46, 8, 5, 0x31, 255, 0, 24, 2, 0, 0, 1, 0])
    elif case in ("inactive-zero", "inactive-payload"):
        extra = (
            matching
            + bytes([0x46, 8, 0, 0])
            + bytes(5)
            + bytes([case == "inactive-payload"])
            + b"\x01\0"
        )
    elif case == "geometry-change":
        extra = matching[:3] + b"\x80" + matching[4:] + b"\x01\0"
    elif case in ("past-registry", "negative-slot"):
        extra = (
            bytes([0x46, 32 if case == "past-registry" else 255])
            + matching[2:]
            + b"\x01\0"
        )
    elif case == "copy-reset":
        extra = bytes([0x1D, 0, 4, 0]) + matching + b"\x01\0"
    elif case == "quantity-set":
        extra = (
            item_command(20, 16, 9)
            + matching[:6]
            + struct.pack("<H", 16)
            + matching[8:]
            + b"\x01\0"
        )
    elif case == "no-reachable-creator":
        body = first + second
        branch = bytes([6, 0, 50, 0, 0x21, 1, 1, 1]) + body + b"\x08\0\x01\0"
    data = synthetic_room(b"\x01\0", (branch, extra, *additional))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    if case == "incomplete":
        room["candidate_list_complete"] = False
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    assert proof.absent_item_ids == []
    if not selected:
        assert proof.item_variants == []
        return
    room["scenario_item_variants"] = proof.item_variants
    candidates = scenario_item_candidates(room)
    assert {item["type"] for item in candidates} == {20}
    assert {amount for item in candidates for amount in item["amounts"]} == (
        {15, 16} if case in ("quantity-set", "changed-amount") else {15}
    )


@pytest.mark.parametrize("opening,closing", [(0x0F, 0x10), (0x11, 0x12)])
@pytest.mark.parametrize("malformed", [False, True])
@pytest.mark.parametrize("loop_gid", [9, 10])
def test_scenario_loops_keep_every_creator_possible(
    opening, closing, malformed, loop_gid, scenario_banks
):
    from games.re2.scenario_items import scenario_item_proofs

    # A valid wait may execute zero times. Treat all its creators as possible,
    # rather than pruning an alternative using the enclosing loop predicate.
    test = bytes([0x50, 0, 0, 0x80])
    body = item_command(21, 30, loop_gid)
    if opening == 0x0F:
        loop = (
            bytes([opening, 4, len(test) + len(body) + 2, 0])
            + test
            + body
            + bytes([closing, 0])
        )
    else:
        loop = bytes([opening, 0, len(body) + 6, 0]) + body + bytes([closing, 4]) + test
    if malformed:
        loop = (
            loop[:2]
            + (int.from_bytes(loop[2:4], "little") + 1).to_bytes(2, "little")
            + loop[4:]
        )
    data = synthetic_room(
        bytes([1, 0]),
        (
            bytes([6, 0, 28, 0, 0x21, 1, 1, 1])
            + item_command(20, 15, 9)
            + bytes([8, 0, 1, 0]),
            loop + bytes([1, 0]),
        ),
    )
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    absent, variants = proof.absent_item_ids, proof.item_variants
    assert absent == ([9] if not malformed and loop_gid != 9 else [])
    assert variants == (
        [
            {
                "global_id": 9,
                "offsets": [
                    next(item["offset"] for item in room["items"] if item["type"] == 21)
                ],
            }
        ]
        if not malformed and loop_gid == 9
        else []
    )


@pytest.fixture
def incompatible_item():
    return (
        bytes([6, 0, 28, 0, 0x21, 1, 1, 1])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )


@pytest.mark.parametrize(
    "category,index,safe",
    [
        (1, 0, True),
        (1, 255, True),
        (2, 255, True),
        (3, 0, True),
        (3, 31, True),
        (0, 0, False),
        (4, 0, False),
        (255, 0, False),
        (3, 32, False),
        (3, 127, False),
        (3, 128, False),
        (3, 255, False),
    ],
)
def test_scenario_shadow_selector_bounds(
    category, index, safe, incompatible_item, scenario_banks
):
    from games.re2.scenario_items import scenario_item_proofs

    packet = bytes([0x60, category, index]) + bytes(11)
    data = synthetic_room(b"\x01\0", (incompatible_item, packet + b"\x01\0"))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["candidate_list_complete"]
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    assert (proof.absent_item_ids, proof.item_variants) == ([9] if safe else [], [])


@pytest.mark.parametrize(
    "reference,index,safe",
    [(0, 0, True), (0, 255, True)]
    + [(reference, 0, False) for reference in (1, 2, 3, 4, 5, 127, 128, 160, 192, 255)],
)
def test_scenario_effect_static_reference_preserves_context(
    reference, index, safe, incompatible_item, scenario_banks
):
    from games.re2.scenario_items import scenario_item_proofs

    packet = bytes([0x3A, 0, 47, 0, reference, index]) + bytes(10)
    data = synthetic_room(b"\x01\0", (incompatible_item, packet + b"\x01\0"))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    assert proof.fixed_context_preserved is safe
    assert proof.absent_item_ids == ([9] if safe else [])


@pytest.mark.parametrize(
    "checks,fixed,proven",
    [
        ([(1, 1, 1)], frozenset(), False),
        ([(1, 1, 1)], frozenset({(1, 1, 0)}), True),
        ([(1, 1, 1)], frozenset({(1, 1, 1)}), False),
        ([(1, 1, 1), (4, 7, 1)], frozenset({(1, 1, 0)}), True),
        ([(1, 1, 1), (4, 7, 1)], frozenset({(1, 1, 1)}), False),
        ([(4, 7, 1), (1, 1, 1)], frozenset({(1, 1, 0)}), False),
    ],
)
def test_fixed_context_skips_only_proven_startup_branches(checks, fixed, proven):
    from games.re2.event_presence import source_presence

    # The opaque message command is on an alternate startup path. Its
    # continuation cannot be assumed when that path has not been excluded.
    body = b"\x51\0\x01\0\0\0"
    tests = b"".join(bytes([0x21, *check]) for check in checks)
    startup = (
        bytes([6, 0])
        + struct.pack("<H", len(tests) + len(body) + 2)
        + tests
        + body
        + b"\x08\0"
        + item_command(39, 1, 9)
        + b"\x01\0"
    )
    data = synthetic_room(b"\x01\0", (startup,))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    creator = room["items"][0]["offset"]
    result = source_presence(
        data, room["programs"], {("17:0", creator)}, "startup", PRESENCE_FLAGS, fixed
    )
    assert result == {"kind": "required" if proven else "unresolved"}


@pytest.mark.parametrize(
    "fixed",
    [frozenset({(1, 1, 0), (1, 1, 1)}), frozenset({(4, 6, 0)})],
)
def test_fixed_startup_context_rejects_conflicting_or_unsupported_inputs(fixed):
    from games.re2.event_presence import source_presence

    data = synthetic_room(b"\x01\0", (item_command(39, 1, 9) + b"\x01\0",))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    with pytest.raises(AssertionError):
        source_presence(
            data,
            room["programs"],
            {("17:0", room["items"][0]["offset"])},
            "startup",
            PRESENCE_FLAGS,
            fixed,
        )


def test_fixed_collection_context_requires_whole_source_proof():
    from games.re2.room_data import collection_presence

    data = synthetic_room(b"\x01\0", (item_command(39, 1, 9) + b"\x01\0",))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    with pytest.raises(AssertionError, match="whole-source"):
        collection_presence(
            data,
            room,
            PRESENCE_FLAGS,
            frozenset(i["offset"] for i in room["items"]),
            frozenset({(1, 1, 0)}),
        )


@pytest.mark.parametrize(
    "address,bit,safe",
    [
        (0x800D0D64, 0, True),
        (0x800D0D64, 32, False),
        (0x800D0D68, 0, False),
        (0x800D3BE4, 31, False),
        (0x800D3BE8, 0, True),
    ],
)
@pytest.mark.parametrize("pool_shift", [0, -0x238])
def test_scenario_effect_pool_must_not_alias_fixed_context(
    address, bit, safe, scenario_banks, pool_shift
):
    address += pool_shift
    from games.re2.scenario_items import scenario_item_proofs

    packet = bytes([0x3A, 0, 47, 0, 0, 255]) + bytes(10)
    data = synthetic_room(b"\x01\0", (packet + b"\x01\0",))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    banks = [*scenario_banks, {"bank": 99, "address_ps1": hex(address), "width": 8}]
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 99, "bit": bit, "expected": 0}],
        banks,
        tuple(value + pool_shift for value in SCENARIO_EFFECT_POOL),
    )
    assert proof.fixed_context_preserved is safe


@pytest.mark.parametrize(
    "opcode,field,width,safe",
    [
        (0x32, 2, 1, True),
        (0x32, 3, 1, True),
        (0x32, 6, 2, True),
        (0x40, 4, 1, True),
        (0x40, 6, 2, True),
        (0x32, 0, 1, False),
        (0x32, 1, 1, False),
        (0x32, 3, 2, False),
        (0x32, 7, 2, False),
        (0x40, 2, 1, False),
        (0x40, 3, 1, False),
        (0x4E, 1, 1, False),
        (0x4E, 14, 2, False),
        (0x4E, 16, 2, False),
        (0x4E, 18, 2, False),
        (0x21, 1, 1, False),
        (0x18, 1, 1, False),
        (0x1D, 1, 1, False),
        (0x01, 0, 1, False),
    ],
)
def test_scenario_copy_can_only_patch_numeric_actor_operands(
    opcode, field, width, safe, incompatible_item, scenario_banks
):
    from games.re2.room_data import OPCODE_WIDTHS
    from games.re2.scenario_items import scenario_item_proofs

    destination = bytearray(OPCODE_WIDTHS[opcode])
    destination[0] = opcode
    if opcode == 0x4E:
        destination = bytearray(item_command(20, 1, 10))
    elif opcode == 0x21:
        destination[:] = bytes([0x21, 4, 7, 1])
    elif opcode == 0x18:
        destination[1] = 0
    elif opcode == 0x1D:
        destination[:] = bytes([0x1D, 0, 2, 1])
    # Counter values remain unknown. Safety comes from the destination's role,
    # including byte/halfword boundaries, rather than a convenient test value.
    packet = bytes([0x1D, 255, field, width - 1])
    data = synthetic_room(
        b"\x01\0", (incompatible_item, packet + destination + b"\x01\0")
    )
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["candidate_list_complete"]
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    assert (proof.absent_item_ids, proof.item_variants) == ([9] if safe else [], [])


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "last",
        "zero-count",
        "header-only",
        "outside-index",
        "overrun",
        "script-overlap",
        "unaligned",
    ],
)
def test_scenario_collision_store_stays_in_its_section(
    case, incompatible_item, scenario_banks
):
    from games.re2.scenario_items import scenario_item_proofs

    index = 1 if case == "last" else 2 if case == "outside-index" else 0
    data = bytearray(
        synthetic_room(
            b"\x01\0", (incompatible_item, bytes([0x37, index, 0, 0xFC, 1, 0]))
        )
    )
    data.extend(bytes(-len(data) % 4))
    collision = len(data)
    data.extend(bytes(48))
    count = (
        0
        if case == "zero-count"
        else 1
        if case == "header-only"
        else 4
        if case == "overrun"
        else 3
    )
    if case == "script-overlap":
        collision = 132
    elif case == "unaligned":
        collision += 1
    struct.pack_into("<I", data, 0x20, collision)
    if case != "script-overlap":
        struct.pack_into("<I", data, collision + 4, count)
    room = decode_room(
        bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["candidate_list_complete"]
    proof = scenario_item_proofs(
        bytes(data),
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    assert (proof.absent_item_ids, proof.item_variants) == (
        [9] if case in ("valid", "last") else [],
        [],
    )


@pytest.mark.parametrize("count", [0, 1, 65535])
@pytest.mark.parametrize("body_gid", [9, 10])
def test_scenario_for_procedure_never_prunes_a_creator(
    count, body_gid, incompatible_item, scenario_banks
):
    from games.re2.scenario_items import scenario_item_proofs

    body = (
        bytes([6, 0, 28, 0, 0x21, 1, 1, 1])
        + item_command(21, 7, body_gid)
        + bytes([8, 0])
    )
    loop = (
        bytes([0x0D, 0])
        + struct.pack("<HH", len(body) + 2, count)
        + body
        + b"\x0e\0\x01\0"
    )
    data = synthetic_room(b"\x01\0", (incompatible_item, loop))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["candidate_list_complete"]
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    absent, variants = proof.absent_item_ids, proof.item_variants
    assert absent == ([9] if body_gid == 10 else [])
    assert variants == (
        [{"global_id": 9, "offsets": [room["items"][-1]["offset"]]}]
        if body_gid == 9
        else []
    )


@pytest.mark.parametrize(
    "case",
    [
        "balanced",
        "unmatched-open",
        "unmatched-close",
        "wrong-limit",
        "depth-five",
        "mixed-while",
        "early-end",
        "early-return",
        "jump-out",
        "jump-in",
        "endif-underflow",
        "unclosed-if",
        "if-depth-nine",
        "unframed-test",
        "unsupported-test",
        "wrong-endif",
    ],
)
def test_scenario_for_control_flow_bounds(case, incompatible_item, scenario_banks):
    from games.re2.scenario_items import scenario_item_proofs

    body = b"\0\0"
    if case == "mixed-while":
        body = bytes([0x0F, 4, 6, 0, 0x50, 0, 0, 0x80, 0x10, 0])
    elif case in ("early-end", "early-return"):
        body = bytes([1 if case == "early-end" else 0x17, 0])
    elif case == "jump-out":
        body = bytes([7, 0, 6, 0])
    loop = bytes([0x0D, 0]) + struct.pack("<HH", len(body) + 2, 1) + body + b"\x0e\0"
    if case == "unmatched-open":
        loop = loop[:-2]
    elif case == "unmatched-close":
        loop = loop[6:]
    elif case == "wrong-limit":
        loop = loop[:2] + struct.pack("<H", len(body)) + loop[4:]
    elif case == "depth-five":
        for _ in range(4):
            loop = (
                bytes([0x0D, 0])
                + struct.pack("<HH", len(loop) + 2, 1)
                + loop
                + b"\x0e\0"
            )
    elif case == "jump-in":
        loop = bytes([7, 0, 10, 0]) + loop
    elif case == "endif-underflow":
        loop += b"\x08\0"
    elif case == "unclosed-if":
        loop += bytes([6, 0, 4, 0, 0x21, 1, 1, 1])
    elif case == "if-depth-nine":
        for _ in range(9):
            loop = (
                bytes([6, 0])
                + struct.pack("<H", len(loop) + 6)
                + bytes([0x21, 1, 1, 1])
                + loop
                + b"\x08\0"
            )
    elif case == "unframed-test":
        loop += bytes([0x21, 1, 1, 1])
    elif case in ("unsupported-test", "wrong-endif"):
        loop += (
            bytes([6, 0, 4, 0])
            + (bytes([0x21, 1, 1, 1]) if case == "wrong-endif" else b"\0\0")
            + b"\x08\0"
        )
    data = synthetic_room(b"\x01\0", (incompatible_item, loop + b"\x01\0"))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert room["candidate_list_complete"]
    proof = scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        scenario_banks,
        SCENARIO_EFFECT_POOL,
    )
    assert (proof.absent_item_ids, proof.item_variants) == (
        [9] if case in ("balanced", "mixed-while") else [],
        [],
    )


@pytest.mark.parametrize(
    "writer",
    ["none", "unrelated", "direct", "alias", "raw", "unsupported", "incomplete"],
)
def test_fixed_context_presence_requires_a_whole_source_proof(writer, scenario_banks):
    from games.re2.scenario_items import scenario_item_proofs, scenario_presence_flags

    startup = (
        bytes([6, 0, 28, 0, 0x21, 0, 25, 1])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    extra = bytes([1, 0])
    if writer in ("direct", "alias", "unrelated"):
        extra = bytes(
            [
                0x22,
                99 if writer == "alias" else 0,
                24 if writer == "unrelated" else 25,
                1,
                1,
                0,
            ]
        )
    elif writer == "raw":
        extra += bytes([0x22, 0, 25, 1])
    elif writer == "unsupported":
        extra = bytes([0x4A, 0, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, extra))
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    if writer == "incomplete":
        room["candidate_list_complete"] = False
    banks = [*scenario_banks, {"bank": 99, "address_ps1": "0x800C7CE4", "width": 4}]
    fixed = [{"bank": 0, "bit": 25, "expected": 1}]
    proof = scenario_item_proofs(data, room, fixed, banks, SCENARIO_EFFECT_POOL)
    assert not proof.absent_item_ids and not proof.item_variants
    assert proof.fixed_context_preserved is (writer in ("none", "unrelated"))
    flags = scenario_presence_flags(
        PRESENCE_FLAGS, fixed, proof.fixed_context_preserved
    )
    from games.re2.room_data import collection_presence

    required, conditional = collection_presence(
        data,
        room,
        flags,
        frozenset(i["offset"] for i in room["items"]),
        fixed_flags=frozenset(),
    )
    assert required == []
    assert conditional == (
        [
            {
                "global_id": 9,
                "presence": {
                    "kind": "conditions",
                    "any_of": [[{"bank": 0, "bit": 25, "expected": 1}]],
                },
            }
        ]
        if proof.fixed_context_preserved
        else []
    )
