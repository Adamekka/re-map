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
from games.re2.actor_part_proofs import (
    ActorPartProofConfig,
    ActorPartSupport,
    actor_part_copy_proof,
    scenario_actor_parts,
)
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


@pytest.fixture
def loop_packet():
    def wrap(kind, body):
        if kind == "for":
            return b"\x0d\0" + struct.pack("<hH", len(body) + 2, 0) + body + b"\x0e\0"
        if kind == "while":
            return (
                b"\x0f\x04"
                + struct.pack("<h", len(body) + 6)
                + bytes([0x21, 4, 7, 1])
                + body
                + b"\x10\0"
            )
        assert kind == "do"
        return (
            b"\x11\0"
            + struct.pack("<h", len(body) + 6)
            + body
            + b"\x12\x04"
            + bytes([0x21, 4, 7, 1])
        )

    return wrap


@pytest.mark.parametrize("outer", ["for", "while", "do"])
@pytest.mark.parametrize("inner", ["for", "while", "do"])
def test_mixed_loop_procedures_retain_fixed_false_creators(loop_packet, outer, inner):
    item = item_command(20, 15, 9)
    guarded = (
        bytes([6, 0])
        + struct.pack("<H", len(item) + 6)
        + bytes([0x21, 1, 1, 1])
        + item
        + b"\x08\0"
    )
    data = synthetic_room(
        b"\x01\0", (loop_packet(outer, loop_packet(inner, guarded)) + b"\x01\0",)
    )
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
    assert proof.absent_item_ids == []
    assert proof.unreachable_creator_offsets == frozenset()


@pytest.mark.parametrize("kind", ["for", "while", "do"])
@pytest.mark.parametrize("case", ["valid", "outside-target", "underflow", "unclosed"])
def test_loop_if_else_frames_stay_inside_the_loop(loop_packet, kind, case):
    first, second = item_command(20, 15, 9), item_command(21, 7, 10)
    guard = (
        bytes([6, 0])
        + struct.pack("<H", len(first) + 8)
        + bytes([0x21, 1, 1, 1])
        + first
        + bytes([7, 0])
        + struct.pack("<H", len(second) + 4)
        + second
    )
    if case == "underflow":
        guard = b"\x08\0" + guard
    elif case == "unclosed":
        guard = (
            bytes([6, 0])
            + struct.pack("<H", len(guard) + 4)
            + bytes([0x21, 1, 1, 1])
            + guard
        )
    script = loop_packet(kind, guard) + b"\x01\0"
    if case == "outside-target":
        script = bytearray(script)
        start = 6 if kind == "for" else 8 if kind == "while" else 4
        # The IF false branch stays valid, but Else would bypass the native
        # loop close. A decoded destination alone cannot establish safety.
        struct.pack_into(
            "<H",
            script,
            start + 8 + len(first) + 2,
            len(second) + 4 + (6 if kind == "do" else 2),
        )
        script = bytes(script)
    data = synthetic_room(b"\x01\0", (script,))
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
    assert proof.fixed_context_preserved is (case == "valid")
    assert proof.absent_item_ids == []


@pytest.mark.parametrize("depth", [4, 5])
@pytest.mark.parametrize("writer", ["none", "unrelated", "fixed"])
def test_mixed_loop_depth_and_write_guards_remain_shared(loop_packet, depth, writer):
    body = (
        bytes([0x22, 1 if writer == "fixed" else 4, 1, 1])
        if writer != "none"
        else b"\0\0"
    )
    for index in range(depth):
        body = loop_packet(("for", "while", "do")[index % 3], body)
    data = synthetic_room(b"\x01\0", (body + b"\x01\0",))
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
    assert proof.fixed_context_preserved is (depth == 4 and writer != "fixed")


@pytest.mark.parametrize("outer", ["for", "while", "do"])
@pytest.mark.parametrize(
    "case", ["mismatched-close", "early-end", "wrong-predicate", "wrong-width"]
)
def test_mixed_loop_malformed_frames_withhold_proof(loop_packet, outer, case):
    inner = bytearray(loop_packet("while", b"\0\0"))
    if case == "mismatched-close":
        inner[-2] = 0x0E
    elif case == "early-end":
        inner[8:10] = b"\x01\0"
    elif case == "wrong-predicate":
        inner[4:8] = bytes([0x22, 4, 7, 1])
    else:
        inner[1] = 6
    data = synthetic_room(b"\x01\0", (loop_packet(outer, bytes(inner)) + b"\x01\0",))
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
    assert not proof.fixed_context_preserved


def actor_banks():
    return {
        row["bank"]: (int(row["address_ps1"], 0), row["width"])
        for row in json.loads(
            (ROOT / "profiles/re2_leon_a_slus00421.json").read_text()
        )["flag_banks"]
    }


@pytest.fixture
def actor_config():
    layout = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())[
        "runtime_layout"
    ]
    return lambda count: ActorPartProofConfig(
        ((0x22, count),),
        int(layout["script_counter_address_ps1"], 0),
        int(layout["system_flags_address_ps1"], 0),
        int(layout["status_flags_address_ps1"], 0),
    )


@pytest.fixture
def actor_copy_source():
    def build(case, count, initial):
        body = bytearray.fromhex(
            "1d0408011d0602006e0000000000"
            "1d0508011d0602006e0000010000"
            "2510060026000010010025061000"
        )
        if case == "selector-copy":
            body[6] = 3
        elif case == "wide-index":
            body[7] = 1
        elif case == "opcode-copy":
            body[6] = 0
        elif case == "invalid-selector":
            body[11] = 7
        elif case == "yield":
            body = bytearray(b"\x02" + body)
        loop = b"\x0d\0" + struct.pack("<hH", len(body) + 2, count) + body + b"\x0e\0"
        target = bytes([0x24, 6]) + struct.pack("<H", initial) + loop + b"\x01\0"
        actor = (
            bytes([0x44, 0, 0, 0x23 if case == "wrong-model" else 0x22])
            + bytes(5)
            + bytes([0xFF])
            + bytes(12)
        )
        work = bytes([0x2E, 4 if case == "wrong-work" else 3, 0, 0])
        if case == "unowned":
            work = bytes(4)
        root = actor + work + b"\x18\x02"
        if case == "foreign-entry":
            root += bytes([4, 0xFF, 0x18, 2])
        if case in ("fixed-alternative", "unknown-alternative"):
            # A one-part replacement is safe to exclude only when its caller
            # guard is false under the same preserved fixed scenario.
            root += bytes(
                [
                    6,
                    0,
                    8,
                    0,
                    0x21,
                    1 if case == "fixed-alternative" else 4,
                    1,
                    1,
                    0x18,
                    3,
                    8,
                    0,
                ]
            )
        if case == "unsafe-writer":
            root += bytes([0x22, 1, 1, 1])
        if case == "loop-work-change":
            changing = b"\x18\x02\x2e\x04\0"
            root = (
                actor
                + work
                + b"\x0d\0"
                + struct.pack("<hH", len(changing) + 2, 2)
                + changing
                + b"\x0e\0"
            )
        # Procedure one is the native frame root. The copied loop is called
        # from procedure zero with explicit enemy work, not entered as a root.
        procedures = (root + b"\x01\0", b"\x01\0", target)
        if case in ("fixed-alternative", "unknown-alternative"):
            procedures += (bytes([0x44, 0, 0, 0x26]) + bytes(18) + b"\x01\0",)
        return synthetic_room(b"\x01\0", procedures)

    return build


@pytest.mark.parametrize(
    "count,part_count,expected",
    [
        (0, 23, False),
        (1, 23, True),
        (22, 23, True),
        (23, 23, True),
        (24, 23, False),
        (128, 128, True),
        (129, 128, False),
    ],
)
def test_actor_copy_indices_fit_the_owned_signed_part_array(
    actor_copy_source, actor_config, count, part_count, expected
):
    data = actor_copy_source("valid", count, 0)
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
        actor_parts=actor_config(part_count),
    )
    assert proof.fixed_context_preserved is expected
    offsets = actor_part_copy_proof(
        data, room, {(1, 1): 0}, actor_banks(), actor_config(part_count)
    ).offsets
    assert len(offsets) == (4 if expected else 0)


@pytest.mark.parametrize(
    "case,initial,expected",
    [
        ("valid", 0, True),
        ("fixed-alternative", 0, True),
        ("unknown-alternative", 0, False),
        ("wrong-model", 0, False),
        ("wrong-work", 0, False),
        ("unowned", 0, False),
        ("foreign-entry", 0, False),
        ("selector-copy", 0, False),
        ("wide-index", 0, False),
        ("opcode-copy", 0, False),
        ("invalid-selector", 0, False),
        ("yield", 0, False),
        ("unsafe-writer", 0, False),
        ("loop-work-change", 0, False),
        ("valid", 128, False),
        ("valid", 0xFFFF, False),
    ],
)
def test_actor_copy_preserves_context_ownership_and_mutation_bounds(
    actor_copy_source, actor_config, case, initial, expected
):
    data = actor_copy_source(case, 22, initial)
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
        actor_parts=actor_config(23),
    )
    assert proof.fixed_context_preserved is expected


def test_actor_copy_support_is_explicit_and_cannot_authorize_other_copy_targets(
    actor_copy_source,
):
    data = actor_copy_source("valid", 22, 0)
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert (
        actor_part_copy_proof(
            data, room, {(1, 1): 0}, actor_banks(), ActorPartSupport.Unaudited
        ).offsets
        == frozenset()
    )
    assert not scenario_item_proofs(
        data,
        room,
        [{"bank": 1, "bit": 1, "expected": 0}],
        json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())[
            "flag_banks"
        ],
        SCENARIO_EFFECT_POOL,
    ).fixed_context_preserved


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "empty",
        "missing-table",
        "unaligned-table",
        "bad-table",
        "duplicate",
        "model",
        "parts",
        "hash",
        "archive",
        "sector",
        "width",
        "extra",
    ],
)
def test_actor_part_resource_contract_is_revision_opted_in(case):
    row = {
        "model_type": 34,
        "part_count": 23,
        "resource_sha256": "ab" * 32,
        "archive_path": "PL0/PLD/CDEMD0.EMS",
        "resource_sector": 1426,
        "resource_width": 174964,
    }
    profile = {
        "runtime_layout": json.loads(
            (ROOT / "profiles/re2_leon_a_slus00421.json").read_text()
        )["runtime_layout"],
        "metadata_layout": {"actor_part_resource_table_address_ps1": "0x8009ADF4"},
        "scenario_actor_parts": [row],
    }
    if case == "empty":
        assert scenario_actor_parts({}) is ActorPartSupport.Unaudited
        return
    if case == "missing-table":
        del profile["metadata_layout"]
    elif case == "unaligned-table":
        profile["metadata_layout"]["actor_part_resource_table_address_ps1"] = (
            "0x8009ADF5"
        )
    elif case == "bad-table":
        profile["metadata_layout"]["actor_part_resource_table_address_ps1"] = (
            "not-address"
        )
    elif case == "duplicate":
        profile["scenario_actor_parts"].append(dict(row))
    elif case == "model":
        row["model_type"] = 0x50
    elif case == "parts":
        row["part_count"] = 129
    elif case == "hash":
        row["resource_sha256"] = "not-hash"
    elif case == "archive":
        row["archive_path"] = "another.EMS"
    elif case == "sector":
        row["resource_sector"] = -1
    elif case == "width":
        row["resource_width"] = 0
    elif case == "extra":
        row["anything"] = 1
    if case == "valid":
        assert scenario_actor_parts(profile).part_counts == ((34, 23),)
    else:
        with pytest.raises(ValueError, match="actor-part"):
            scenario_actor_parts(profile)


@pytest.fixture
def conditional_actor_source(actor_copy_source, actor_config):
    def build(case):
        original = actor_copy_source("valid", 22, 0)
        decoded = decode_room(
            original, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
        )
        target = decoded["programs"]["17:2"]
        body = original[target["entry"] : target["limit"]]
        actor = bytes([0x44, 0, 0, 0x22]) + bytes(5) + bytes([24]) + bytes(12)
        direct = actor + bytes([0x2E, 3, 0, 0, 0x18, 2])
        if case == "constructor-after-copy":
            direct = bytes([0x2E, 3, 0, 0, 0x18, 2]) + actor
        elif case == "late-constructor":
            direct = b"\x02\0" + direct
        startup = (
            bytes([6, 0])
            + struct.pack("<H", len(direct) + 6)
            + bytes([0x21, 4, 5, 0])
            + direct
            + b"\x08\0\x01\0"
        )
        # The opaque counter predicate can prevent a task launch. If it does
        # launch, its subsequent flag check still establishes the birth guard.
        birth = bytes(
            [0x23, 0, 26, 0, 4, 0, 0x21, 4, 6 if case == "wrong-birth-guard" else 5, 0]
        )
        activation = bytes([4, 0xFF, 0x18, 3, 0x22, 4, 5, 1])
        frame = (
            bytes([6, 0])
            + struct.pack("<H", len(birth) + len(activation) + 2)
            + birth
            + activation
            + b"\x08\0\x01\0"
        )
        if case == "unconditional-birth":
            frame = activation + b"\x01\0"
        task = bytes([0x2E, 3, 0, 0, 0x18, 2, 1, 0])
        extra = b"\x01\0"
        banks = actor_banks()
        if case in ("clear-alias", "toggle", "enemy-clear", "enemy-toggle"):
            enemy = case.startswith("enemy-")
            banks[99] = banks[6 if enemy else 4]
            extra = bytes(
                [
                    0x22,
                    99,
                    24 if enemy else 5,
                    0 if case in ("clear-alias", "enemy-clear") else 7,
                    1,
                    0,
                ]
            )
        elif case in ("counter-alias", "enemy-counter-alias"):
            address = banks[6][0] if case == "enemy-counter-alias" else banks[4][0] + 2
            index = (address - actor_config(23).counter_address) // 2
            assert 0 <= index <= 255
            extra = bytes([0x24, index, 0, 0, 1, 0])
        data = synthetic_room(b"\x01\0", (startup, frame, body, task, extra))
        room = decode_room(
            data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
        )
        room["stage"] = 1
        return data, room, banks

    return build


@pytest.mark.parametrize(
    "case,expected",
    [
        ("valid", True),
        ("wrong-birth-guard", False),
        ("unconditional-birth", False),
        ("constructor-after-copy", False),
        ("late-constructor", False),
        ("clear-alias", False),
        ("toggle", False),
        ("counter-alias", False),
        ("enemy-clear", False),
        ("enemy-toggle", False),
        ("enemy-counter-alias", False),
    ],
)
def test_actor_constructor_dominates_direct_and_guarded_task_copies(
    conditional_actor_source, actor_config, case, expected
):
    data, room, banks = conditional_actor_source(case)
    proof = actor_part_copy_proof(
        data, room, {(1, 1): 0, (1, 6): 0}, banks, actor_config(23)
    )
    assert len(proof.offsets) == (4 if expected else 0)
    assert proof.context_conditions == (
        [
            {
                "kind": "conditions",
                "any_of": [
                    [{"bank": 6, "bit": 24, "expected": 0}],
                ],
            }
        ]
        if expected
        else []
    )


@pytest.mark.parametrize(
    "guard,acquired", [(False, False), (False, True), (True, False), (True, True)]
)
def test_actor_context_condition_models_constructor_skip_explicitly(
    conditional_actor_source, actor_config, guard, acquired
):
    from games.re2.event_presence import presence_matches

    data, room, banks = conditional_actor_source("valid")
    proof = actor_part_copy_proof(
        data, room, {(1, 1): 0, (1, 6): 0}, banks, actor_config(23)
    )
    flags = {(4, 5): guard, (6, 24): acquired}
    assert all(
        presence_matches(condition, lambda bank, bit: flags[bank, bit])
        for condition in proof.context_conditions
    ) is (not acquired)


@pytest.mark.parametrize("depth,expected", [(4, True), (5, False)])
def test_actor_copy_callers_fit_the_native_call_stack(
    actor_copy_source, actor_config, depth, expected
):
    original = actor_copy_source("valid", 22, 0)
    decoded = decode_room(
        original, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    target = decoded["programs"]["17:2"]
    actor = bytes([0x44, 0, 0, 0x22]) + bytes(5) + bytes([0xFF]) + bytes(12)
    startup = actor + bytes([0x2E, 3, 0, 0, 0x18, 3, 1, 0])
    wrappers = tuple(
        bytes([0x18, number + 1 if number < depth + 1 else 2, 1, 0])
        for number in range(3, depth + 2)
    )
    data = synthetic_room(
        b"\x01\0",
        (startup, b"\x01\0", original[target["entry"] : target["limit"]], *wrappers),
    )
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    proof = actor_part_copy_proof(
        data, room, {(1, 1): 0}, actor_banks(), actor_config(23)
    )
    assert bool(proof.offsets) is expected


def test_actor_copy_rejects_unproved_fixed_words_in_the_model_heap(
    actor_copy_source, actor_config
):
    data = actor_copy_source("valid", 22, 0)
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    banks = {**actor_banks(), 99: (0x80110000, 4)}
    proof = actor_part_copy_proof(data, room, {(99, 0): 0}, banks, actor_config(23))
    assert not proof.offsets and not proof.context_conditions
