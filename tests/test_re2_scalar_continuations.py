"""Finite scalar entry-to-END summaries remain separate from write coverage."""

import copy
import struct
from dataclasses import FrozenInstanceError, replace

import pytest
from test_re2_actor_write_domains import describe
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    synthetic_room,
)
from test_re2_scenario_reachability import (
    actor_config as actor_config,
    actor_copy_source as actor_copy_source,
    conditional_actor_source as conditional_actor_source,
)

from games.re2.actor_part_proofs import ActorPartSupport, actor_part_copy_proof
from games.re2.room_data import decode_room
from games.re2.script_control_limits import (
    NATIVE_LOOP_FRAME_COUNT,
    SCALAR_PROGRAM_STEP_LIMIT,
)

END = b"\x01\0"
INDEX_COPY = bytes([0x1D, 6, 2, 0, 0x6E, 0, 0, 0, 0, 0])
INCREMENT = bytes([0x26, 0, 0, 6, 1, 0])
INITIALIZE = bytes([0x24, 6, 0, 0])


def loop(body, count):
    return (
        bytes([0x0D, 0]) + struct.pack("<hH", len(body) + 2, count) + body + b"\x0e\0"
    )


@pytest.fixture
def scalar_source(actor_copy_source):
    original = actor_copy_source("valid", 1, 0)
    room = decode_room(
        original, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    root = room["programs"]["17:0"]
    startup = original[root["entry"] : root["limit"]]

    def build(body):
        return synthetic_room(END, (startup, END, body))

    return build


@pytest.mark.parametrize("count", [0, 1, 22])
def test_complete_scalar_loop_records_only_its_entry_to_end(
    scalar_source, actor_config, count
):
    data = scalar_source(INITIALIZE + loop(INDEX_COPY + INCREMENT, count) + END)
    room, proof = describe(data, actor_config(23))
    (summary,) = proof.scalar_continuations
    program = room["programs"]["17:2"]
    assert summary.program == "17:2"
    assert summary.entry == program["entry"]
    assert summary.end == program["commands"][-1]["offset"]
    assert data[summary.end : summary.end + 2] == END
    assert summary.end != program["commands"][-1]["next"]
    assert summary.max_loop_depth == (1 if count else 0)
    assert summary.steps == 3 + 4 * count
    assert summary.matches_source(data, room["programs"])
    assert len(proof.offsets) == (1 if count else 0)
    with pytest.raises(FrozenInstanceError):
        summary.end = summary.entry


@pytest.mark.parametrize("depth", [4, 5])
def test_scalar_loop_nesting_fits_each_native_call_frame(
    scalar_source, actor_config, depth
):
    body = INDEX_COPY
    for _ in range(depth):
        body = loop(body, 1)
    _, proof = describe(scalar_source(INITIALIZE + body + END), actor_config(23))
    assert NATIVE_LOOP_FRAME_COUNT == 4
    assert bool(proof.scalar_continuations) is (depth == 4)
    if depth == 4:
        assert proof.scalar_continuations[0].max_loop_depth == 4


@pytest.mark.parametrize("count", [2729, 2730])
def test_scalar_continuation_keeps_the_existing_dynamic_step_budget(
    scalar_source, actor_config, count
):
    # A fixed valid part index isolates the instruction budget from index bounds.
    body = INITIALIZE + bytes(2) + loop(INDEX_COPY, count) + END
    _, proof = describe(scalar_source(body), actor_config(23))
    assert bool(proof.scalar_continuations) is (count == 2729)
    if count == 2729:
        assert proof.scalar_continuations[0].steps == SCALAR_PROGRAM_STEP_LIMIT


@pytest.mark.parametrize(
    "body",
    [
        INITIALIZE + b"\x0e\0" + INDEX_COPY + END,
        INITIALIZE + loop(INDEX_COPY + END, 1) + END,
        # The FOR limit names END, but NEXT ends before an intervening NOP.
        INITIALIZE
        + bytes([0x0D, 0])
        + struct.pack("<hH", len(INDEX_COPY) + 3, 1)
        + INDEX_COPY
        + b"\x0e\0\0"
        + END,
        END,
    ],
)
def test_unmatched_control_and_nonadvancing_end_have_no_summary(
    scalar_source, actor_config, body
):
    _, proof = describe(scalar_source(body), actor_config(23))
    assert not proof.scalar_continuations


def test_noncanonical_end_withholds_summary_without_changing_write_results(
    scalar_source, actor_config
):
    body = INITIALIZE + loop(INDEX_COPY + INCREMENT, 1)
    _, normal = describe(scalar_source(body + END), actor_config(23))
    _, noncanonical = describe(scalar_source(body + b"\x01\x01"), actor_config(23))
    assert normal.scalar_continuations and not noncanonical.scalar_continuations
    assert replace(normal, scalar_continuations=()) == noncanonical


@pytest.mark.parametrize("operation", [3, 4])
def test_unused_divide_or_modulo_keeps_old_writes_but_no_continuation(
    scalar_source, actor_config, operation
):
    body = INITIALIZE + loop(INDEX_COPY + INCREMENT, 1)
    add = bytes([0x26, 0, 0, 17, 0, 0])
    unsupported = bytes([0x26, 0, operation, 17, 0, 0])
    _, normal = describe(scalar_source(body + add + END), actor_config(23))
    _, rejected = describe(scalar_source(body + unsupported + END), actor_config(23))
    assert normal.scalar_continuations and not rejected.scalar_continuations
    assert normal.offsets and normal.part_writes
    assert replace(normal, scalar_continuations=()) == rejected


@pytest.mark.parametrize(
    "control",
    [
        b"\x02",
        b"\x18\x01",
        bytes([6, 0, 6, 0, 0x21, 1, 1, 0, 8, 0]),
        bytes([7, 0, 4, 0]),
    ],
)
def test_calls_predicates_yields_and_branches_are_not_scalar_summaries(
    scalar_source, actor_config, control
):
    data = scalar_source(control + INITIALIZE + loop(INDEX_COPY, 1) + END)
    _, proof = describe(data, actor_config(23))
    assert not proof.scalar_continuations


@pytest.mark.parametrize(
    "case",
    [
        "selector-copy",
        "wide-index",
        "opcode-copy",
        "invalid-selector",
        "wrong-model",
        "wrong-work",
        "unowned",
        "foreign-entry",
        "loop-work-change",
    ],
)
def test_scalar_summary_cannot_borrow_invalid_copy_or_actor_bounds(
    actor_copy_source, actor_config, case
):
    _, proof = describe(actor_copy_source(case, 22, 0), actor_config(23))
    assert not proof.scalar_continuations


def test_cross_program_selector_mutation_withdraws_scalar_summary(
    scalar_source, actor_config
):
    body = INITIALIZE + loop(INDEX_COPY, 1) + END
    original = scalar_source(body)
    room, _ = describe(original, actor_config(23))
    root = room["programs"]["17:0"]
    caller = original[root["entry"] : root["limit"] - 2] + b"\x1d\0\0\0" + END
    data = bytearray(synthetic_room(END, (caller, END, body)))
    room, _ = describe(bytes(data), actor_config(23))
    mutation = next(
        row for row in room["programs"]["17:0"]["commands"] if row["opcode"] == 0x1D
    )
    part = next(
        row for row in room["programs"]["17:2"]["commands"] if row["opcode"] == 0x6E
    )
    data[mutation["offset"] + 2] = part["offset"] + 3 - mutation["next"]
    _, proof = describe(bytes(data), actor_config(23))
    assert proof.offsets and len(proof.source_writes) == 2
    assert not proof.part_writes and not proof.scalar_continuations


@pytest.mark.parametrize(
    "case,expected",
    [
        ("valid", True),
        ("wrong-birth-guard", False),
        ("unconditional-birth", False),
        ("enemy-clear", False),
        ("enemy-counter-alias", False),
    ],
)
def test_scalar_summary_retains_fresh_actor_context_obligations(
    conditional_actor_source, actor_config, case, expected
):
    data, room, banks = conditional_actor_source(case)
    proof = actor_part_copy_proof(
        data, room, {(1, 1): 0, (1, 6): 0}, banks, actor_config(23)
    )
    assert bool(proof.scalar_continuations) is expected
    if expected:
        assert (
            proof.context_conditions
            == proof.write_context_conditions
            == [
                {
                    "kind": "conditions",
                    "any_of": [[{"bank": 6, "bit": 24, "expected": 0}]],
                }
            ]
        )


def test_scalar_summary_binds_the_entire_source_and_decoded_graph(
    actor_copy_source, actor_config
):
    data = actor_copy_source("valid", 22, 0)
    room, proof = describe(data, actor_config(23))
    (summary,) = proof.scalar_continuations
    changed = bytearray(data)
    changed[-1] ^= 1
    assert not summary.matches_source(bytes(changed), room["programs"])
    programs = copy.deepcopy(room["programs"])
    programs["17:1"]["commands"][0]["kind"] = "changed"
    assert not summary.matches_source(data, programs)
    assert summary.matches_source(data, room["programs"])
    _, unaudited = describe(data, ActorPartSupport.Unaudited)
    assert unaudited.scalar_continuations == ()
