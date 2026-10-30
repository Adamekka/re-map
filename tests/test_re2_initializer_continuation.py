"""RE2-CONTROL-002: finite receipts retain ownership, predicates and applicability."""

import copy
from dataclasses import replace

import pytest
from test_re2_immutable_open_doors import (
    entry_contract as entry_contract,
    profile as profile,
)
from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES
from test_re2_room_write_partitions import CONFIG, END, source
from test_re2_scenario_reachability import actor_copy_source as actor_copy_source

import games.re2.room_lifetime_proof as lifetime_module
from games.re2.initializer_control_proof import (
    InitializerContinuationFailure,
    InitializerContinuationProof,
    InitializerContinuationSupport,
    initializer_control_config,
)
from games.re2.room_data import decode_room
from games.re2.room_lifetime_proof import (
    RoomLifetimeFailure,
    RoomLifetimeProof,
    initializer_continuation_proof,
    room_lifetime_proof,
)
from games.re2.scenario_items import scenario_flags

GUARD = {"kind": "conditions", "any_of": [[{"bank": 6, "bit": 24, "expected": 0}]]}


@pytest.fixture
def continuation_source(actor_copy_source):
    def build(case="valid"):
        original = actor_copy_source("valid", 22, 0)
        decoded = decode_room(
            original, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
        )
        leaf = decoded["programs"]["17:2"]
        body = bytearray(original[leaf["entry"] : leaf["limit"]])
        if case == "no-copy":
            body = bytearray(END)
        elif case == "yield":
            body[:0] = b"\x02\0"
        elif case == "non-end":
            body[-1] = 1
        elif case == "unsafe-calc":
            at = next(
                row["offset"] - leaf["entry"]
                for row in leaf["commands"]
                if row["opcode"] == 0x26
            )
            body[at + 2] = 9
        elif case == "unsafe-copy":
            at = next(
                row["offset"] - leaf["entry"]
                for row in leaf["commands"]
                if row["opcode"] == 0x1D
            )
            body[at + 2] = 0
        constructor = bytes([0x44, 0, 0, 0x22, 2, 0x44, 0, 0, 0, 24]) + bytes(12)
        work = bytes([0x2E, 3, 1 if case == "unowned" else 0, 0])
        startup = constructor + work + b"\x18\x02" + END
        data, room, _ = source(END, (startup, END, bytes(body)), [], [0])
        room.update(
            stage=1,
            fixed_context_preserved=True,
            scenario_context_conditions=[copy.deepcopy(GUARD)],
        )
        return data, room

    return build


def compile_receipt(data, room, profile, entry_contract):
    return initializer_continuation_proof(data, room, profile, entry_contract, CONFIG)


def fixed_flags(profile):
    return frozenset(
        (row["bank"], row["bit"], row["expected"]) for row in scenario_flags(profile)
    )


def condition_flags(profile):
    return frozenset(
        (row["bank"], row["bit"]) for row in profile["presence_condition_flags"]
    )


def test_whole_program_receipt_retains_exact_source_context_and_predicates(
    profile, entry_contract, continuation_source
):
    data, room = continuation_source()
    proof = compile_receipt(data, room, profile, entry_contract)
    assert isinstance(proof, InitializerContinuationProof)
    assert proof.context_conditions == (GUARD,)
    assert proof.fixed_flags == fixed_flags(profile)
    assert proof.predicate_flags == condition_flags(profile) | {
        (bank, bit) for bank, bit, _ in proof.fixed_flags
    } | {(6, 24)}
    assert len(proof.scalar_continuations) == 1
    summary = proof.scalar_continuations[0]
    assert summary.program == "17:2"
    assert summary.entry == room["programs"]["17:2"]["entry"]
    assert data[summary.end : summary.end + 2] == END
    assert summary.entry < summary.end and summary.max_loop_depth == 1
    assert (
        proof.for_predicates(
            data, room["programs"], condition_flags(profile), proof.fixed_flags
        )
        is proof
    )
    assert (
        proof.for_predicates(
            data,
            room["programs"],
            condition_flags(profile) | {(7, 9)},
            proof.fixed_flags,
        )
        is InitializerContinuationSupport.Unaudited
    )


@pytest.mark.parametrize("change", ["drop", "opposite", "extra"])
def test_query_requires_exact_fixed_assignments(
    profile, entry_contract, continuation_source, change
):
    data, room = continuation_source()
    proof = compile_receipt(data, room, profile, entry_contract)
    assert isinstance(proof, InitializerContinuationProof)
    fixed = set(proof.fixed_flags)
    bank, bit, expected = min(fixed)
    if change == "extra":
        fixed.add((4, 7, 0))
    else:
        fixed.remove((bank, bit, expected))
        if change == "opposite":
            fixed.add((bank, bit, 1 - expected))
    assert (
        proof.for_predicates(
            data, room["programs"], condition_flags(profile), frozenset(fixed)
        )
        is InitializerContinuationSupport.Unaudited
    )


@pytest.mark.parametrize("change", ["source", "programs"])
def test_query_cannot_reuse_a_receipt_after_source_or_decoding_changes(
    profile, entry_contract, continuation_source, change
):
    data, room = continuation_source()
    proof = compile_receipt(data, room, profile, entry_contract)
    assert isinstance(proof, InitializerContinuationProof)
    programs = copy.deepcopy(room["programs"])
    if change == "source":
        data = data[:-1] + bytes([data[-1] ^ 1])
    else:
        programs["17:2"]["commands"][0]["kind"] = "changed"
    assert not proof.matches_source(data, programs)
    with pytest.raises(AssertionError, match="belongs to another source"):
        proof.for_predicates(
            data, programs, condition_flags(profile), proof.fixed_flags
        )


def test_guard_predicates_must_remain_physically_preserved_at_query_time(
    profile, entry_contract, continuation_source
):
    data, room = continuation_source()
    proof = compile_receipt(data, room, profile, entry_contract)
    assert isinstance(proof, InitializerContinuationProof)
    proof = replace(proof, predicate_flags=proof.predicate_flags - {(6, 24)})
    assert (
        proof.for_predicates(
            data, room["programs"], condition_flags(profile), proof.fixed_flags
        )
        is InitializerContinuationSupport.Unaudited
    )


@pytest.mark.parametrize("change", ["missing", "opposite", "malformed", "not-fixed"])
def test_factory_requires_validated_room_applicability(
    profile, entry_contract, continuation_source, change
):
    data, room = continuation_source()
    expected = InitializerContinuationFailure.Context
    if change == "missing":
        room["scenario_context_conditions"] = []
    elif change == "opposite":
        room["scenario_context_conditions"][0]["any_of"][0][0]["expected"] = 1
    elif change == "malformed":
        room["scenario_context_conditions"] = [{"kind": "required"}]
    else:
        room["fixed_context_preserved"] = False
        expected = InitializerContinuationFailure.FixedContext
    assert compile_receipt(data, room, profile, entry_contract) is expected


@pytest.mark.parametrize("field", ["context_conditions", "write_context_conditions"])
def test_both_actor_applicability_lists_must_be_covered(
    profile, entry_contract, continuation_source, monkeypatch, field
):
    data, room = continuation_source()
    lifetime = room_lifetime_proof(data, room, profile, entry_contract, CONFIG)
    assert isinstance(lifetime, RoomLifetimeProof)
    additional = {
        "kind": "conditions",
        "any_of": [[{"bank": 4, "bit": 7, "expected": 0}]],
    }
    actor = replace(lifetime.actor_write_proof, **{field: [GUARD, additional]})
    monkeypatch.setattr(
        lifetime_module,
        "room_lifetime_proof",
        lambda *args: replace(lifetime, actor_write_proof=actor),
    )
    assert (
        compile_receipt(data, room, profile, entry_contract)
        is InitializerContinuationFailure.Context
    )


@pytest.mark.parametrize("change", ["executable", "counter", "audit", "flag-alias"])
def test_native_profile_or_predicate_alias_changes_reject_receipts(
    profile, entry_contract, continuation_source, change
):
    data, room = continuation_source()
    altered = copy.deepcopy(profile)
    if change == "executable":
        altered["executable_identity"] = "SLUS_007.48 SHA256 " + "0" * 64
    elif change == "counter":
        altered["runtime_layout"]["script_counter_address_ps1"] = "0x800D487C"
    elif change == "audit":
        altered["initializer_control_audit"]["task_capacity"] = 13
    else:
        next(row for row in altered["flag_banks"] if row["bank"] == 6)[
            "address_ps1"
        ] = "0x800D47F4"
    result = compile_receipt(data, room, altered, entry_contract)
    assert isinstance(result, (InitializerContinuationFailure, RoomLifetimeFailure))


@pytest.mark.parametrize(
    "case", ["no-copy", "yield", "non-end", "unsafe-calc", "unsafe-copy", "unowned"]
)
def test_no_partial_or_unproved_program_becomes_a_continuation(
    profile, entry_contract, continuation_source, case
):
    data, room = continuation_source(case)
    result = compile_receipt(data, room, profile, entry_contract)
    assert not isinstance(result, InitializerContinuationProof)
    assert isinstance(
        result,
        (
            InitializerContinuationSupport,
            InitializerContinuationFailure,
            RoomLifetimeFailure,
        ),
    )


@pytest.mark.parametrize("change", ["source", "programs", "entry", "end"])
def test_factory_rejects_foreign_or_misbound_whole_program_summaries(
    profile, entry_contract, continuation_source, monkeypatch, change
):
    data, room = continuation_source()
    lifetime = room_lifetime_proof(data, room, profile, entry_contract, CONFIG)
    assert isinstance(lifetime, RoomLifetimeProof)
    summary = lifetime.actor_write_proof.scalar_continuations[0]
    if change == "source":
        summary = replace(summary, source_sha256="0" * 64)
    elif change == "programs":
        summary = replace(summary, programs_sha256="0" * 64)
    elif change == "entry":
        summary = replace(summary, entry=summary.entry + 4)
    else:
        summary = replace(summary, end=summary.end - 2)
    actor = replace(lifetime.actor_write_proof, scalar_continuations=(summary,))
    monkeypatch.setattr(
        lifetime_module,
        "room_lifetime_proof",
        lambda *args: replace(lifetime, actor_write_proof=actor),
    )
    expected = (
        InitializerContinuationFailure.SourceBinding
        if change in ("source", "programs")
        else InitializerContinuationFailure.Summary
    )
    assert compile_receipt(data, room, profile, entry_contract) is expected


def test_task_writes_cannot_alias_an_applicability_word(
    profile, entry_contract, continuation_source, monkeypatch
):
    data, room = continuation_source()
    config = replace(initializer_control_config(profile), task_address=0x800D487C)
    monkeypatch.setattr(
        lifetime_module, "initializer_control_config", lambda *args: config
    )
    assert (
        compile_receipt(data, room, profile, entry_contract)
        is InitializerContinuationFailure.FlagAlias
    )


@pytest.mark.parametrize("case", ["cycle", "five-frames"])
def test_receipt_requires_native_call_frame_bounds(
    profile, entry_contract, continuation_source, monkeypatch, case
):
    data, room = continuation_source()
    lifetime = room_lifetime_proof(data, room, profile, entry_contract, CONFIG)
    assert isinstance(lifetime, RoomLifetimeProof)
    edges = dict(lifetime.call_edges)
    if case == "cycle":
        edges["17:2"] = ("17:0",)
    else:
        edges["17:2"] = ("auxiliary-one",)
        edges["auxiliary-one"] = ("auxiliary-two",)
        edges["auxiliary-two"] = ("auxiliary-three",)
        edges["auxiliary-three"] = ()
    altered = replace(lifetime, call_edges=tuple(edges.items()))
    monkeypatch.setattr(lifetime_module, "room_lifetime_proof", lambda *args: altered)
    assert (
        compile_receipt(data, room, profile, entry_contract)
        is InitializerContinuationFailure.CallDepth
    )
