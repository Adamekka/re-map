"""Compile door facts only after entry, write and startup-presence proofs."""

import copy
import json
import struct

import pytest
from test_re2_metadata import ROOT, item_command
from test_re2_room_write_partitions import CONFIG, END, md1, source
from test_re2_scenario_reachability import actor_copy_source as actor_copy_source

from games.re2.immutable_open_doors import (
    ImmutableOpenDoorFailure,
    immutable_open_doors,
)
from games.re2.room_entry_contract import (
    RoomEntryContractConfig,
    VerifiedRoomEntryContract,
    room_entry_contract,
)
from games.re2.room_data import decode_room
from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES


@pytest.fixture
def entry_contract(profile):
    # An explicit test receipt exercises the source compiler. Separate binder
    # tests verify the executable/resources required to produce it in use.
    config = room_entry_contract(profile)
    assert isinstance(config, RoomEntryContractConfig)
    return VerifiedRoomEntryContract(
        config=config,
        audit=config.audit,
        executable_sha256=config.executable_sha256,
        minimum_source_address=0x8011A000,
        source_addresses=((0, 0x8011A6A8), (1, 0x8011A65C)),
        stages=frozenset({0, 1}),
        roots=("16:0", "17:0", "17:1"),
        door_models=frozenset({1, 9, 13}),
        non_scheduling_interaction_kinds=frozenset({4, 10, 13}),
        constructor_presets=frozenset({(0x22, 0x4402)}),
        actor_code_images=config.actor_codes,
        write_partitions=CONFIG,
    )


@pytest.fixture
def profile():
    return json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())


def door(slot=0, model=9, lock=0, sat=0x31):
    packet = bytearray(32)
    packet[:4] = bytes([0x3B, slot, 1, sat])
    struct.pack_into("<HH", packet, 10, 100, 100)
    packet[22:24] = bytes([1, 4])
    packet[26] = model
    packet[29] = lock
    return bytes(packet)


def object_command(slot):
    packet = bytearray(38)
    packet[:2] = bytes([0x2D, slot])
    packet[10], packet[12] = 10, 16
    return bytes(packet)


def compiled(init, main, models, profile, entry_contract):
    data, room, _ = source(init, main, models, [0])
    room["stage"] = 1
    return immutable_open_doors(data, room, profile, entry_contract, CONFIG)


def test_partitioned_collision_prefix_proves_both_identical_door_bindings(
    profile, entry_contract
):
    first, second = door(), door(1, 13)
    proofs = compiled(
        b"\x37\0\0\0" + first + second + END,
        (END, END, first + second + END),
        [],
        profile,
        entry_contract,
    )
    assert isinstance(proofs, tuple) and len(proofs) == 2
    assert [proof.slot for proof in proofs] == [0, 1]
    assert all(
        len(proof.creator_offsets) == 2 and not proof.context_conditions
        for proof in proofs
    )


@pytest.mark.parametrize(
    "prefix", [b"\x02\0", b"\x18\x02", bytes([6, 0, 38, 0, 0x21, 4, 7, 0])]
)
def test_reachable_door_does_not_establish_guaranteed_startup_presence(
    profile, entry_contract, prefix
):
    if prefix[0] == 6:
        init = prefix + door() + b"\x08\0" + END
    else:
        init = prefix + door() + END
    proofs = compiled(init, (END, END, END), [], profile, entry_contract)
    assert proofs == ()


@pytest.mark.parametrize(
    "case",
    [
        "different-target",
        "different-model",
        "different-geometry",
        "locked",
        "inactive",
        "reset",
        "other-kind",
    ],
)
def test_every_binding_for_a_slot_must_be_the_same_enabled_unlocked_door(
    profile, entry_contract, case
):
    alternative = bytearray(door())
    if case == "different-target":
        alternative[23] = 5
    elif case == "different-model":
        alternative[26] = 13
    elif case == "different-geometry":
        alternative[6] = 1
    elif case == "locked":
        alternative[29] = 0x80
    elif case == "inactive":
        alternative[3] = 0
    elif case == "reset":
        alternative = bytes([0x46, 0, 0, 0]) + bytes(6)
    else:
        alternative = bytes([0x2C, 0, 4, 0x31]) + bytes(16)
    proofs = compiled(
        door() + END, (END, END, bytes(alternative) + END), [], profile, entry_contract
    )
    assert proofs == ()


def test_fixed_false_predicate_can_skip_an_unentered_unsupported_constructor(
    profile, entry_contract
):
    unsupported = bytes([0x44, 0, 0, 0x26]) + bytes(18)
    init = bytes([6, 0, 28, 0, 0x21, 1, 6, 1]) + unsupported + b"\x08\0" + door() + END
    proofs = compiled(init, (END, END), [], profile, entry_contract)
    assert isinstance(proofs, tuple) and len(proofs) == 1


def test_compound_fixed_and_opaque_predicate_is_not_guaranteed_creation(
    profile, entry_contract
):
    checks = bytes([0x21, 1, 6, 0, 0x23, 0, 1, 0, 0, 0])
    init = (
        bytes([6, 0])
        + struct.pack("<H", len(checks) + 34)
        + checks
        + door()
        + b"\x08\0"
        + END
    )
    assert compiled(init, (END, END), [], profile, entry_contract) == ()


@pytest.mark.parametrize("case", ["frame", "repeated-call", "loop", "same-asset"])
def test_models_require_fresh_single_startup_execution(profile, entry_contract, case):
    obj = object_command(0)
    init, main = door() + END, (obj + END, END)
    if case == "frame":
        main = (END, obj + END)
    elif case == "repeated-call":
        init = door() + bytes([0x18, 2, 0x18, 2]) + END
        main = (END, END, obj + END)
    elif case == "loop":
        init = (
            door()
            + b"\x0d\0"
            + struct.pack("<HH", len(obj) + 2, 2)
            + obj
            + b"\x0e\0"
            + END
        )
        main = (END, END)
    else:
        init = door() + obj + obj + END
        main = (END, END)
    assert (
        compiled(init, main, [md1(1, 1)], profile, entry_contract)
        is ImmutableOpenDoorFailure.RepeatedAllocation
    )


def test_unknown_callback_namespace_is_not_an_entry_proof(profile, entry_contract):
    callback = bytes([0x2C, 3, 5, 0x31]) + bytes(10) + bytes([0xFF, 0, 0x18, 2, 0, 0])
    assert (
        compiled(door() + callback + END, (END, END, END), [], profile, entry_contract)
        is ImmutableOpenDoorFailure.EntryContract
    )


@pytest.mark.parametrize("kind", [4, 10])
def test_non_scheduling_callback_alone_does_not_certify_its_writes(
    profile, entry_contract, kind
):
    callback = bytes([0x2C, 3, kind, 0x31]) + bytes(16)
    assert (
        compiled(door() + callback + END, (END, END), [], profile, entry_contract)
        is ImmutableOpenDoorFailure.CallbackEffects
    )


def test_source_or_counter_mutations_cannot_borrow_an_actor_domain(
    profile, entry_contract
):
    mutated = bytes([0x1D, 0, 0, 0]) + door() + END
    assert (
        compiled(mutated, (END, END), [], profile, entry_contract)
        is ImmutableOpenDoorFailure.FixedContext
    )
    altered = copy.deepcopy(profile)
    altered["runtime_layout"]["script_counter_address_ps1"] = "0x800CE558"
    assert (
        compiled(door() + END, (END, END), [], altered, entry_contract)
        is ImmutableOpenDoorFailure.InputBinding
    )


def test_all_bounded_actor_writes_contribute_fresh_constructor_conditions(
    profile, entry_contract, actor_copy_source
):
    original = actor_copy_source("valid", 22, 0)
    decoded = decode_room(
        original, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    procedure = decoded["programs"]["17:2"]
    copied = original[procedure["entry"] : procedure["limit"]]
    constructor = bytes([0x44, 0, 0, 0x22, 2, 0x44, 0, 0, 0, 24]) + bytes(12)
    startup = (
        constructor
        + bytes([0x2E, 3, 0, 0, 0x18, 2, 0x6E, 0, 22, 2, 0, 0, 0x34, 23, 1, 0])
        + END
    )
    proofs = compiled(door() + END, (startup, END, copied), [], profile, entry_contract)
    assert isinstance(proofs, tuple) and len(proofs) == 1
    assert proofs[0].context_conditions == [
        {"kind": "conditions", "any_of": [[{"bank": 6, "bit": 24, "expected": 0}]]}
    ]


@pytest.mark.parametrize(
    "field,value", [(2, 1), (3, 1), (6, 2), (7, 1), (8, 1), (10, 0), (12, 32), (26, 1)]
)
def test_embedded_model_packets_cannot_hide_attach_or_effect_writes(
    profile, entry_contract, field, value
):
    packet = bytearray(object_command(0))
    packet[field] = value
    assert (
        compiled(
            door() + bytes(packet) + END,
            (END, END),
            [md1(1, 1)],
            profile,
            entry_contract,
        )
        is ImmutableOpenDoorFailure.WriteEffects
    )


@pytest.mark.parametrize("case", ["loop", "frame", "repeated-slot"])
def test_constructors_cannot_grow_the_heap_by_reentry(profile, entry_contract, case):
    constructor = bytes([0x44, 0, 0, 0x22, 2, 0x44, 0, 0, 0, 0xFF]) + bytes(12)
    if case == "loop":
        body = (
            b"\x0d\0"
            + struct.pack("<HH", len(constructor) + 2, 2)
            + constructor
            + b"\x0e\0"
            + END
        )
        main = (body, END)
    elif case == "frame":
        main = (END, constructor + END)
    else:
        main = (constructor + constructor + END, END)
    assert (
        compiled(door() + END, main, [], profile, entry_contract)
        is ImmutableOpenDoorFailure.RepeatedAllocation
    )


def callback_source(callback, item_type=20):
    init = (
        door()
        + object_command(0)
        + item_command(item_type, 15, 9, slot=9)
        + callback
        + END
    )
    original, _, layout = source(init, (END, END), [md1(1, 1)], [0])
    data = bytearray(original[: layout["floor"]])
    sections = list(struct.unpack_from("<23I", data, 8))
    for section in (13, 14):
        sections[section] = len(data)
        data.extend(struct.pack("<2H", 4, 6) + b"\xfe\0\xfa\x02\xfd\0\xfe\0")
    data.extend(bytes((-len(data)) % 4))
    edt = sections[0] = len(data)
    data.extend(bytes(192))
    for index, packet in (
        (0x14, b"\0\0\x93\x16"),
        (0x15, b"\0\0\xa5\x16"),
        (0x27, b"\0\0\x74\x16"),
        (0x28, b"\0\0\x84\x17"),
    ):
        data[edt + index * 4 : edt + index * 4 + 4] = packet
    vab = sections[1] = len(data)
    data.extend(bytes(0xC20))
    data[vab : vab + 4] = b"pBAV"
    struct.pack_into("<I", data, vab + 4, 7)
    struct.pack_into("<H", data, vab + 18, 1)
    data[vab + 32] = 11
    sections[2] = len(data)
    data.extend(bytes(32))
    struct.pack_into("<23I", data, 8, *sections)
    return data, {"edt": edt, "vab": vab, "sections": sections}


def compile_data(data, profile, entry_contract):
    data = bytes(data)
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    return immutable_open_doors(data, room, profile, entry_contract, CONFIG)


@pytest.mark.parametrize("item_type", [0, 20, 21, 30, 103, 104, 107, 128])
@pytest.mark.parametrize("kind", [4, 10, 13])
def test_bounded_native_callbacks_preserve_door_control_and_bindings(
    profile, entry_contract, kind, item_type
):
    payload = {
        4: struct.pack("<3H", 1, 0, 0xFFFF),
        10: b"\0\0\x01\0\0\0",
        13: struct.pack("<3H", 0, 9, 0),
    }[kind]
    callback = bytes([0x2C, 8, kind, 0x31]) + bytes(10) + payload
    data, _ = callback_source(callback, item_type)
    proofs = compile_data(data, profile, entry_contract)
    assert isinstance(proofs, tuple) and len(proofs) == 1 and proofs[0].slot == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "relocation",
        "geometry",
        "effect",
        "file-outside",
        "edt-gap",
        "vab-version",
        "program-count",
        "program",
        "tone",
        "voice",
        "extra",
        "graphics-overlap",
        "selected-door",
    ],
)
def test_callback_resource_or_binding_changes_withhold_open(
    profile, entry_contract, mutation
):
    callback = bytes([0x2C, 8, 13, 0x31]) + bytes(10) + struct.pack("<3H", 0, 9, 0)
    data, layout = callback_source(callback)
    decoded = decode_room(
        bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    item = next(
        row for row in decoded["programs"]["16:0"]["commands"] if row["kind"] == "item"
    )
    if mutation == "relocation":
        struct.pack_into("<I", data, 8 + 22 * 4, layout["sections"][2])
    elif mutation == "geometry":
        data[item["offset"] + 3] = 0xB1
    elif mutation == "effect":
        data[item["offset"] + 21] = 0x80
    elif mutation == "file-outside":
        struct.pack_into("<H", data, item["offset"] + 14, 129)
    elif mutation == "edt-gap":
        struct.pack_into("<I", data, 8, layout["edt"] - 4)
    elif mutation == "vab-version":
        struct.pack_into("<I", data, layout["vab"] + 4, 8)
    elif mutation == "program-count":
        struct.pack_into("<H", data, layout["vab"] + 18, 128)
    elif mutation in ("program", "tone", "voice", "extra"):
        offset, value = {
            "program": (1, 127),
            "tone": (2, 0xF0),
            "voice": (3, 31),
            "extra": (3, 0xFF),
        }[mutation]
        data[layout["edt"] + 0x27 * 4 + offset] = value
    elif mutation == "graphics-overlap":
        floor = 0x80000
        data.extend(bytes(floor + 32 - len(data)))
        struct.pack_into("<I", data, 8 + 2 * 4, floor)
    else:
        camera = next(
            row
            for row in decoded["programs"]["16:0"]["commands"]
            if row["kind"] == "interaction"
        )
        struct.pack_into("<H", data, camera["offset"] + 16, 0)
    assert isinstance(
        compile_data(data, profile, entry_contract), ImmutableOpenDoorFailure
    )


def test_owned_source_artifact_contains_two_applicable_immutable_doors():
    document = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    room = next(room for room in document["rooms"] if room["id"] == "01-01")
    assert (
        room["sha256"]
        == "48360046aa7758cb7a0df5a1306b8ecd2902374218fe330c57ccd786f4f26f37"
    )
    condition = [
        {"kind": "conditions", "any_of": [[{"bank": 6, "bit": 24, "expected": 0}]]}
    ]
    assert room["immutable_open_doors"] == [
        {"slot": 0, "creator_offsets": [3018, 4232], "context_conditions": condition},
        {"slot": 1, "creator_offsets": [3050, 4264], "context_conditions": condition},
    ]


def test_native_contract_cannot_be_reused_with_another_layout_or_revision(
    profile, entry_contract
):
    from dataclasses import replace

    data, _ = callback_source(
        bytes([0x2C, 8, 10, 0x31]) + bytes(10) + b"\0\0\x01\0\0\0"
    )
    room = decode_room(
        bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    assert (
        immutable_open_doors(
            bytes(data), room, profile, entry_contract, replace(CONFIG, aot_capacity=64)
        )
        is ImmutableOpenDoorFailure.EntryContract
    )
    other = copy.deepcopy(profile)
    other["executable_identity"] = "SLUS_004.21 SHA256 " + "0" * 64
    assert (
        immutable_open_doors(bytes(data), room, other, entry_contract, CONFIG)
        is ImmutableOpenDoorFailure.EntryContract
    )
