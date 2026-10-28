"""Relative actor writes, independent of source/AOT partition claims."""

import struct

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    synthetic_room,
)
from test_re2_scenario_reachability import (
    actor_banks,
    actor_config as actor_config,
    actor_copy_source as actor_copy_source,
    conditional_actor_source as conditional_actor_source,
)

from games.re2.actor_part_proofs import (
    ActorPartSupport,
    actor_part_copy_proof,
)
from games.re2.room_data import decode_room


def describe(data, config, banks=None):
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    proof = actor_part_copy_proof(
        data,
        room,
        {(1, 1): 0, (1, 6): 0},
        actor_banks() if banks is None else banks,
        config,
    )
    return room, proof


@pytest.fixture
def actor_source():
    def build(body, case="valid", orphan=b"\x01\0"):
        constructor = bytes([0x44, 0, 0, 0x22]) + bytes(5) + bytes([24]) + bytes(12)
        work = bytes([0x2E, 3, 0])
        if case == "unknown-work":
            work = b""
        elif case == "wrong-slot":
            work = bytes([0x2E, 3, 1])
        elif case == "wrong-model":
            constructor = constructor[:3] + b"\x26" + constructor[4:]
        elif case == "late-constructor":
            constructor = b"\x02\0" + constructor
        elif case == "missing-constructor":
            constructor = b""
        startup = constructor + work + body + b"\x01\0"
        if case == "after-write":
            startup = work + body + constructor + b"\x01\0"
        return synthetic_room(b"\x01\0", (startup, b"\x01\0", orphan))

    return build


@pytest.mark.parametrize(
    "selector,field_offset,width",
    [
        (0, 0x70, 2),
        (1, 0x72, 1),
        (2, 0, 2),
        (3, 2, 2),
        (4, 0x68, 2),
        (5, 0x6A, 2),
        (6, 0x6C, 2),
    ],
)
def test_constant_part_fields_export_owned_indices_and_native_store_width(
    actor_source, actor_config, selector, field_offset, width
):
    data = actor_source(bytes([0x6E, 0, 22, selector, 0xFF, 0xFF]))
    room, proof = describe(data, actor_config(23))
    assert not proof.offsets and not proof.context_conditions
    assert len(proof.part_writes) == 1
    write = proof.part_writes[0]
    assert write.location in proof.reached_locations
    assert write.indices == frozenset({22})
    assert (write.selector, write.field_offset, write.width) == (
        selector,
        field_offset,
        width,
    )
    assert write.record_stride == 0xAC
    assert [
        (owner.enemy_slot, owner.model_type, owner.part_count, owner.constructor_offset)
        for owner in write.owners
    ] == [(0, 0x22, 23, room["programs"]["17:0"]["entry"])]
    assert proof.write_context_conditions == [
        {"kind": "conditions", "any_of": [[{"bank": 6, "bit": 24, "expected": 0}]]}
    ]


@pytest.mark.parametrize(
    "index,selector", [(23, 0), (128, 0), (255, 0), (22, 7), (22, 255)]
)
def test_part_bounds_reject_signed_indices_and_unsupported_selectors(
    actor_source, actor_config, index, selector
):
    _, proof = describe(
        actor_source(bytes([0x6E, 0, index, selector, 0, 0])), actor_config(23)
    )
    assert not proof.part_writes and not proof.write_context_conditions


@pytest.mark.parametrize(
    "case",
    [
        "unknown-work",
        "wrong-slot",
        "wrong-model",
        "late-constructor",
        "missing-constructor",
        "after-write",
    ],
)
@pytest.mark.parametrize(
    "packet", [bytes([0x6E, 0, 22, 2, 0, 0]), bytes([0x34, 23, 1, 0])]
)
def test_relative_writes_need_every_path_to_establish_actor_ownership(
    actor_source, actor_config, case, packet
):
    _, proof = describe(actor_source(packet, case), actor_config(23))
    assert not proof.actor_writes and not proof.part_writes


@pytest.mark.parametrize("selector", [0, 10, 17, 23, 43, 44, 255])
def test_member_certificate_is_only_the_audited_numeric_yaw_step(
    actor_source, actor_config, selector
):
    _, proof = describe(
        actor_source(bytes([0x34, selector]) + struct.pack("<h", -32768)),
        actor_config(23),
    )
    assert bool(proof.actor_writes) is (selector == 23)
    if proof.actor_writes:
        write = proof.actor_writes[0]
        assert (write.selector, write.field_offset, write.width) == (23, 0x1D4, 2)
        assert write.location in proof.reached_locations
        assert write.owners[0].part_count == 23
        assert proof.write_context_conditions


def test_bounded_scalar_copies_export_exact_part_index_domains(
    actor_copy_source, actor_config
):
    data = actor_copy_source("valid", 22, 0)
    room, proof = describe(data, actor_config(23))
    assert len(proof.offsets) == 4 and len(proof.source_writes) == 4
    assert len(proof.part_writes) == 2
    for write in proof.source_writes:
        key, position = write.location
        assert position in proof.offsets
        assert write.target_offset == position + 4 + data[position + 2]
        assert write.width == (2 if data[position + 3] else 1)
        assert write.location in proof.reached_locations
        assert (
            room["programs"][key]["entry"] <= position < room["programs"][key]["limit"]
        )
    assert {write.indices for write in proof.part_writes} == {frozenset(range(22))}
    assert {
        (write.selector, write.field_offset, write.width) for write in proof.part_writes
    } == {(0, 0x70, 2), (1, 0x72, 1)}


@pytest.mark.parametrize("field", [0, 2, 3])
def test_mutated_part_opcode_index_or_selector_cannot_reuse_literal_bounds(
    actor_source, actor_config, field
):
    # Counter zero is deliberately uninitialized. A source write range is
    # still reportable, but its unknown value cannot establish a part bound.
    data = actor_source(bytes([0x1D, 0, field, 0, 0x6E, 0, 22, 2, 0, 0]))
    _, proof = describe(data, actor_config(23))
    assert len(proof.source_writes) == 1
    assert not proof.part_writes


def test_orphan_positions_are_unvisited_but_not_an_entry_closure_claim(
    actor_source, actor_config
):
    data = actor_source(
        bytes([0x34, 23, 1, 0]), orphan=bytes([0x6E, 0, 22, 2, 0, 0, 1, 0])
    )
    room, proof = describe(data, actor_config(23))
    assert not any(key == "17:2" for key, _ in proof.reached_locations)
    assert not proof.part_writes and len(proof.actor_writes) == 1
    assert ("17:2", room["programs"]["17:2"]["entry"]) not in proof.reached_locations


@pytest.mark.parametrize(
    "case,expected",
    [
        ("valid", True),
        ("wrong-birth-guard", False),
        ("unconditional-birth", False),
        ("enemy-clear", False),
        ("enemy-toggle", False),
        ("enemy-counter-alias", False),
    ],
)
def test_domain_conditions_keep_constructor_skip_and_alias_guards(
    conditional_actor_source, actor_config, case, expected
):
    data, room, banks = conditional_actor_source(case)
    proof = actor_part_copy_proof(
        data, room, {(1, 1): 0, (1, 6): 0}, banks, actor_config(23)
    )
    assert bool(proof.part_writes) is expected
    assert proof.write_context_conditions == (
        proof.context_conditions if expected else []
    )
    if expected:
        predicates = {
            (key, row["offset"])
            for key, program in room["programs"].items()
            for row in program["commands"]
            if row["kind"] == "flag_check"
        }
        assert predicates & proof.reached_locations


def test_unaudited_actor_support_has_no_domain_facts(actor_source):
    _, proof = describe(
        actor_source(bytes([0x34, 23, 1, 0])), ActorPartSupport.Unaudited
    )
    assert not proof.reached_locations and not proof.source_writes
    assert (
        not proof.actor_writes
        and not proof.part_writes
        and not proof.write_context_conditions
    )


def test_unchecked_signed_enemy_slot_does_not_construct_an_invalid_owner(
    actor_source, actor_config
):
    original = actor_source(bytes([0x34, 23, 1, 0, 0x6E, 0, 0, 2, 0, 0]))
    data = bytearray(original)
    decoded, _ = describe(original, actor_config(23))
    for row in decoded["programs"]["17:0"]["commands"]:
        if row["opcode"] in (0x44, 0x2E):
            data[row["offset"] + 2] = 0xFF
    _, proof = describe(bytes(data), actor_config(23))
    assert not proof.offsets and not proof.actor_writes and not proof.part_writes
