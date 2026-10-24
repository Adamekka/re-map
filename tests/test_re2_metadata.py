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

from map_geometry import trace_floor_cells

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.room_data import bind_event_awards, decode_room

PRESENCE_FLAGS = frozenset({(1, 0), (1, 1), (1, 6), (4, 7)})
PRESENCE_COUNTERS = presence_counter_indices(
    json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
)

PRESENCE_WRITES, FLAG_PROOF = presence_flag_write_proof(
    json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
)


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
        data, room["programs"], {("17:1", award["offset"])}, "scheduled", PRESENCE_FLAGS
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
        data, room["programs"], {("17:1", award["offset"])}, "scheduled", PRESENCE_FLAGS
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
        data, room["programs"], {("17:1", award["offset"])}, "scheduled", PRESENCE_FLAGS
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
        data, room["programs"], {("17:1", award)}, "scheduled", PRESENCE_FLAGS
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
        data, room["programs"], {("17:1", award["offset"])}, "scheduled", PRESENCE_FLAGS
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
        data, room["programs"], {("17:1", award["offset"])}, "scheduled", PRESENCE_FLAGS
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


def test_volatile_startup_checks_never_become_fresh_presence_conditions():
    rooms = json.loads((ROOT / "data/rooms_slus00421.json").read_text())["rooms"]
    room = next(room for room in rooms if room["id"] == "01-02")
    # Bank zero bit 25 changes before normal gameplay, outside these scripts.
    # It cannot authorize either complementary creator using its live value.
    assert not any(
        rule["global_id"] in (115, 116) for rule in room["conditional_item_presence"]
    )
    assert next(
        rule for rule in room["conditional_item_presence"] if rule["global_id"] == 114
    )["presence"] == {"kind": "required"}


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
        data, room, [{"bank": 1, "bit": 1, "expected": 0}], scenario_banks
    )[0] == ([9] if excluded else [])


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
        data, room, [{"bank": 0, "bit": 25, "expected": mode}], banks
    )[0] == ([9] if mode and writer in ("none", "unrelated") else [])


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
        data, room, [{"bank": 1, "bit": 1, "expected": fixed}], scenario_banks
    )[0] == ([9] if excluded else [])


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
    assert scenario_item_proofs(data, room, fixed, scenario_banks)[0] == (
        [9] if excluded else []
    )


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
    absent, variants = scenario_item_proofs(
        data, room, [{"bank": 1, "bit": 1, "expected": fixed}], banks
    )
    assert absent == []
    if case != "valid":
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
        data, room, PRESENCE_FLAGS, frozenset(item["offset"] for item in candidates)
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
    absent, variants = scenario_item_proofs(
        data, room, [{"bank": 1, "bit": 1, "expected": 0}], scenario_banks
    )
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
