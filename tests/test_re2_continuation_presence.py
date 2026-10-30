"""RE2-CONTROL-002: guarded whole-program receipts grant no general opcode permission."""

import copy
import hashlib
import struct
from dataclasses import replace

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    item_command,
    synthetic_room,
)

from games.re2.actor_part_proofs import ScalarProgramContinuation
from games.re2.event_presence import presence_matches, source_presence
from games.re2.initializer_control_proof import InitializerContinuationProof
from games.re2.room_data import collection_presence, decode_room
from games.re2.script_control_limits import programs_digest


@pytest.fixture
def source():
    def build(*, init=b"\x01\0", tail=b"", nested=0):
        leaf = b"\x0d\0" + struct.pack("<hH", 3, 1) + b"\0\x0e\0\x01\0"
        entry = item_command(20, 15, 9) + bytes([0x18, 1]) + tail + b"\x01\0"
        procedures = [entry]
        for index in range(nested):
            procedures.append(bytes([0x18, index + 2, 1, 0]))
        procedures.append(leaf)
        data = synthetic_room(init, tuple(procedures))
        room = decode_room(
            data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
        )
        room["fixed_context_preserved"] = True
        key = f"17:{len(procedures) - 1}"
        program = room["programs"][key]
        summary = ScalarProgramContinuation(
            key,
            program["entry"],
            program["commands"][-1]["offset"],
            hashlib.sha256(data).hexdigest(),
            programs_digest(room["programs"]),
            1,
            4,
        )
        guard = {
            "kind": "conditions",
            "any_of": [[{"bank": 6, "bit": 24, "expected": 0}]],
        }
        # These tests supply a trusted receipt to isolate its consumer. Native
        # ownership, scalar execution and factory rejection have separate tests.
        receipt = InitializerContinuationProof(
            summary.source_sha256,
            summary.programs_sha256,
            (summary,),
            PRESENCE_FLAGS | {(6, 24)},
            frozenset(),
            (guard,),
        )
        return data, room, receipt

    return build


def query(data, room, receipt, **kwargs):
    item = room["items"][0]
    target = next(
        (key, row["offset"])
        for key, program in room["programs"].items()
        for row in program["commands"]
        if row["kind"] == "item" and row["item"] == item["offset"]
    )
    return source_presence(
        data,
        room["programs"],
        {target},
        "startup",
        PRESENCE_FLAGS,
        frozenset(),
        initializer_continuations=receipt,
        **kwargs,
    )


def test_finite_leaf_only_adds_guarded_conditional_presence(source):
    data, room, receipt = source()
    offsets = frozenset(item["offset"] for item in room["items"])
    assert collection_presence(data, room, PRESENCE_FLAGS, offsets, frozenset()) == (
        [],
        [],
    )
    assert query(data, room, receipt) == receipt.context_conditions[0]
    assert collection_presence(
        data,
        room,
        PRESENCE_FLAGS,
        offsets,
        frozenset(),
        initializer_continuations=receipt,
    ) == ([], [{"global_id": 9, "presence": receipt.context_conditions[0]}])
    result = query(data, room, receipt)
    assert presence_matches(result, lambda bank, bit: False)
    assert not presence_matches(result, lambda bank, bit: (bank, bit) == (6, 24))


@pytest.mark.parametrize("extra", [b"\x02\0", b"\x34" + bytes(7)])
def test_leaf_receipt_does_not_approve_other_effects(source, extra):
    data, room, receipt = source(tail=extra)
    assert query(data, room, receipt) == {"kind": "unresolved"}


def test_both_roots_still_have_to_finish(source):
    data, room, receipt = source(init=b"\x02\0\x01\0")
    assert query(data, room, receipt) == {"kind": "unresolved"}


@pytest.mark.parametrize("nested,expected", [(2, "conditions"), (3, "unresolved")])
def test_leaf_substitution_retains_native_call_limit(source, nested, expected):
    data, room, receipt = source(nested=nested)
    assert query(data, room, receipt)["kind"] == expected


@pytest.mark.parametrize("changed", ["source", "program"])
def test_receipt_source_binding_is_mandatory(source, changed):
    data, room, receipt = source()
    if changed == "source":
        data += b"\0"
    else:
        room = copy.deepcopy(room)
        room["programs"]["17:1"]["entry"] += 1
    with pytest.raises(AssertionError, match="another source"):
        query(data, room, receipt)


def test_unpreserved_guard_withholds_continuation(source):
    data, room, receipt = source()
    receipt = replace(receipt, predicate_flags=PRESENCE_FLAGS)
    assert query(data, room, receipt) == {"kind": "unresolved"}


def test_all_context_formulas_are_conjoined(source):
    data, room, receipt = source()
    additional = {
        "kind": "conditions",
        "any_of": [
            [{"bank": 4, "bit": 7, "expected": 0}],
            [{"bank": 1, "bit": 6, "expected": 1}],
        ],
    }
    result = query(
        data,
        room,
        replace(receipt, context_conditions=(*receipt.context_conditions, additional)),
    )
    for guard in (False, True):
        for first in (False, True):
            for second in (False, True):
                values = {(6, 24): guard, (4, 7): first, (1, 6): second}
                assert presence_matches(
                    result, lambda bank, bit: values[bank, bit]
                ) == (not guard and (not first or second))


def test_conflicting_context_withholds_presence(source):
    data, room, receipt = source()
    opposite = {
        "kind": "conditions",
        "any_of": [[{"bank": 6, "bit": 24, "expected": 1}]],
    }
    assert query(
        data,
        room,
        replace(receipt, context_conditions=(*receipt.context_conditions, opposite)),
    ) == {"kind": "unresolved"}
