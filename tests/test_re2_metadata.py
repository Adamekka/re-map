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

from games.re2.room_data import bind_event_awards, decode_room


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
    first = {**decode_room(data, "synthetic"), "id": "01-02", "stage": 1}
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
    other = {**decode_room(other_data, "synthetic"), "id": "00-01", "stage": 0}
    result = bind_event_awards(
        [first, other], {"01-02": data, "00-01": other_data}, {0: 8, 1: 8}
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
    result = decode_room(data, "synthetic")
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
    assert decode_room(data, "synthetic")["collection_item_ids"] == [9]


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
        decode_room(synthetic_room(script), "synthetic")["collection_item_ids"]
        == expected
    )


def test_optional_creator_and_uncalled_procedure_do_not_establish_presence():
    optional = (
        bytes([6, 0, 28, 0, 0x21, 4, 0, 1])
        + item_command(20, 15, 9)
        + bytes([8, 0, 1, 0])
    )
    assert (
        decode_room(synthetic_room(optional), "synthetic")["collection_item_ids"] == []
    )
    data = synthetic_room(
        bytes([1, 0]), (bytes([1, 0]), item_command(20, 15, 9) + bytes([1, 0]))
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_init_gosub_uses_main_table_and_returns_to_its_caller():
    data = synthetic_room(
        bytes([0x18, 1]) + item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), item_command(30, 1, 10, slot=9) + bytes([0x19, 0])),
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == [9, 10]


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
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_recursive_calls_and_missing_callees_cannot_establish_presence():
    for procedure in (0, 255):
        data = synthetic_room(
            bytes([1, 0]),
            (item_command(20, 15, 9) + bytes([0x18, procedure, 1, 0]),),
        )
        assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_replaced_item_slot_does_not_turn_both_initializers_into_required_items():
    data = synthetic_room(
        item_command(20, 15, 9) + item_command(30, 1, 10) + bytes([1, 0])
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


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
    result = decode_room(synthetic_room(script + bytes([1, 0])), "synthetic")
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
    assert decode_room(synthetic_room(script), "synthetic")["collection_item_ids"] == [
        11
    ]


def test_conflicting_acquisition_identity_across_slots_stays_unproven():
    script = (
        item_command(20, 15, 9)
        + item_command(30, 1, 9, slot=9)
        + item_command(38, 1, 11, slot=10)
        + bytes([1, 0])
    )
    assert decode_room(synthetic_room(script), "synthetic")["collection_item_ids"] == [
        11
    ]


def test_uncalled_conflict_does_not_create_an_item_or_erase_unrelated_proof():
    data = synthetic_room(
        item_command(20, 15, 9) + item_command(38, 1, 11, slot=9) + bytes([1, 0]),
        (bytes([1, 0]), item_command(30, 1, 10) + bytes([1, 0])),
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == [11]


def test_unsupported_control_flow_still_discards_independent_item_proofs():
    script = (
        item_command(38, 1, 11, slot=9)
        + item_command(20, 15, 9)
        + item_command(30, 1, 10)
        + bytes([2, 1, 0])
    )
    assert decode_room(synthetic_room(script), "synthetic")["collection_item_ids"] == []


def test_item_initializer_with_an_unresolved_interaction_is_not_a_presence_proof():
    item = bytearray(item_command(20, 15, 9))
    item[2] = 5
    assert (
        decode_room(synthetic_room(item + bytes([1, 0])), "synthetic")[
            "collection_item_ids"
        ]
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
    result = decode_room(data, "synthetic")
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
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_automatic_task_does_not_make_its_items_mandatory():
    data = synthetic_room(
        bytes([4, 255, 0x18, 1]) + item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), item_command(30, 1, 10, slot=9) + bytes([1, 0])),
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == [9]


def test_reset_without_a_matching_creator_leaves_coverage_unresolved():
    data = synthetic_room(
        item_command(20, 15, 9) + bytes([1, 0]),
        (bytes([1, 0]), bytes([0x46, 9, 2, 0, 30, 0, 1, 0, 10, 0, 1, 0])),
    )
    result = decode_room(data, "synthetic")
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
    assert decode_room(data, "synthetic")["collection_item_ids"] == [10]


@pytest.mark.parametrize("task,procedure", [(0, 1), (1, 1), (9, 1), (255, 255)])
def test_explicit_or_missing_tasks_do_not_prove_startup_execution(task, procedure):
    data = synthetic_room(
        bytes([4, task, 0x18, procedure]) + item_command(20, 15, 9) + bytes([1, 0])
    )
    assert decode_room(data, "synthetic")["collection_item_ids"] == []


def test_audited_actor_setup_does_not_block_later_reward_declaration():
    setup = bytes.fromhex(
        "2e0300 3d1000 260005100400 350010 3200bec1000089c6 4b0007 6e000b020000"
    )
    data = synthetic_room(setup + item_command(20, 15, 9) + bytes([1, 0]))
    assert decode_room(data, "synthetic")["collection_item_ids"] == [9]


def test_truncated_script_and_branch_outside_procedure_are_rejected():
    with pytest.raises(ValueError, match="truncated"):
        decode_room(synthetic_room(bytes([0x4E, 0])), "synthetic")
    with pytest.raises(ValueError, match="outside its procedure"):
        decode_room(synthetic_room(bytes([6, 0, 255, 0, 1, 0])), "synthetic")


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
            tuple(room["section_offsets"]),
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
    door = decode_room(synthetic_room(packet + b"\x01\0"), "synthetic")["doors"][0]
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
    from games.re2.event_presence import event_presence

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
    room = decode_room(data, "synthetic")
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    result = event_presence(data, room["programs"], "17:1", award["offset"])
    assert result == (
        {"kind": "conditions", "any_of": [[{"bank": 4, "bit": 7, "expected": 0}]]}
        if case == "guarded"
        else {"kind": "required"}
        if case == "unconditional"
        else {"kind": "unresolved"}
    )


def test_event_presence_joins_both_scheduling_branches_without_an_unrelated_gate():
    from games.re2.event_presence import event_presence

    schedule = bytes([4, 255, 0x18, 1])
    startup = (
        bytes([6, 0, 12, 0, 0x21, 4, 7, 0])
        + schedule
        + bytes([7, 0, 10, 0])
        + schedule
        + bytes([0, 0, 1, 0])
    )
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(data, "synthetic")
    award = room["programs"]["17:1"]["entry"]
    assert event_presence(data, room["programs"], "17:1", award) == {"kind": "required"}


@pytest.mark.parametrize("wait_change", [False, True])
def test_event_presence_preserves_a_waiting_award_but_rejects_changed_wait_effects(
    wait_change,
):
    from games.re2.event_presence import event_presence

    startup = bytes([4, 255, 0x18, 1, 1, 0])
    delivery = bytes([0x18, 2, 0x76, 53, 1, 1, 0])
    wait = bytes([0x11, 0, 8, 0, 2, 0, 0x12, 4, 0x21, 5, 33, 0, 1, 0])
    if wait_change:
        wait = bytes([5, 0, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, delivery, wait))
    room = decode_room(data, "synthetic")
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    assert event_presence(data, room["programs"], "17:1", award["offset"]) == (
        {"kind": "unresolved"} if wait_change else {"kind": "required"}
    )


def test_event_presence_rejects_a_delivery_path_that_can_finish_without_awarding():
    from games.re2.event_presence import event_presence

    startup = bytes([4, 255, 0x18, 1, 1, 0])
    delivery = bytes([6, 0, 7, 0, 0x21, 4, 7, 0, 0x76, 53, 1, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, delivery))
    room = decode_room(data, "synthetic")
    award = next(
        c for c in room["programs"]["17:1"]["commands"] if c["kind"] == "award"
    )
    assert event_presence(data, room["programs"], "17:1", award["offset"]) == {
        "kind": "unresolved"
    }


def test_startup_write_cannot_make_an_unexecuted_branch_look_required():
    from games.re2.event_presence import event_presence

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
    room = decode_room(data, "synthetic")
    assert event_presence(
        data, room["programs"], "17:1", room["programs"]["17:1"]["entry"]
    ) == {"kind": "unresolved"}


def test_compound_predicates_need_a_native_join_proof_before_exporting_conditions():
    from games.re2.event_presence import event_presence

    startup = bytes(
        [6, 0, 14, 0, 0x21, 4, 7, 0, 0x21, 6, 28, 0, 4, 255, 0x18, 1, 8, 0, 1, 0]
    )
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(data, "synthetic")
    assert event_presence(
        data, room["programs"], "17:1", room["programs"]["17:1"]["entry"]
    ) == {"kind": "unresolved"}


def test_later_task_cancellation_invalidates_an_earlier_scheduling_proof():
    from games.re2.event_presence import event_presence

    startup = bytes([4, 255, 0x18, 1, 5, 10, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(data, "synthetic")
    assert event_presence(
        data, room["programs"], "17:1", room["programs"]["17:1"]["entry"]
    ) == {"kind": "unresolved"}


def test_startup_must_finish_after_queuing_the_award_task():
    from games.re2.event_presence import event_presence

    # Aot_on can transition away before queued tasks run. It is deliberately
    # outside the synchronous initializer proof even after the fork succeeds.
    startup = bytes([4, 255, 0x18, 1, 0x47, 0, 1, 0])
    data = synthetic_room(bytes([1, 0]), (startup, bytes([0x76, 53, 1, 1, 0])))
    room = decode_room(data, "synthetic")
    assert event_presence(
        data, room["programs"], "17:1", room["programs"]["17:1"]["entry"]
    ) == {"kind": "unresolved"}
