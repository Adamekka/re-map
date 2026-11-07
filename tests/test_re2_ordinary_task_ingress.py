"""Native/auxiliary prerequisites are separate, bound scenario-only rights."""

import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re2_startup_declarations import END, described

from games.re2.native_control import goto_if_cell, native_nonyielding
from games.re2.ordinary_task_ingress import (
    OrdinaryTaskIngressFailure,
    auxiliary_isolation,
    ordinary_task_ingress,
)
from games.re2.startup_entry_selection import (
    EXECUTABLE_SHA256,
    BoundAuxiliaryCorpus,
    BoundAuxiliaryScript,
    EntrySelectionResource,
    VerifiedEntrySelection,
    _AuxiliaryCorpusDerivation,
    _AuxiliaryDerivation,
)


def auxiliary(main):
    data, room, _ = described(END, main)
    return {0: (data, room)}


@pytest.mark.parametrize(
    "selector,accepted",
    [
        (0, False),
        (9, False),
        (10, True),
        (11, True),
        (13, True),
        (14, True),
        (255, True),
    ],
)
def test_phase_one_birth_selector_is_explicit_below_fourteen(selector, accepted):
    result = auxiliary_isolation(auxiliary((bytes((4, selector, 0x18, 1)) + END, END)))
    assert (result == frozenset()) is accepted


def poll():
    prefix = b"\x06\0\x0e\0\x23\0\x04\0\x01\0\x02\0"
    return prefix + b"\x17\xff\xff\0" + struct.pack("<h", -len(prefix)) + END


@pytest.mark.parametrize(
    "depth,birth,accepted",
    [(1, False, True), (1, True, False), (2, True, True), (3, True, False)],
)
def test_poll_foreign_cell_needs_numeric_count_or_inactive_receiver(
    depth, birth, accepted
):
    main = []
    for index in range(depth):
        main.append(
            (b"\x04\x0d\x18" + bytes((depth + 1,)) if index == 0 and birth else b"")
            + bytes((0x18, index + 1))
            + END
        )
    main.extend((poll(), END))
    result = auxiliary_isolation(auxiliary(tuple(main)))
    assert (result == frozenset()) is accepted


@pytest.mark.parametrize(
    "fault", ["shift", "fresh_store", "mask", "source_copy", "member", "work", "depth"]
)
def test_unsafe_auxiliary_control_or_write_does_not_get_isolation(fault):
    program = poll()
    start = b"\x18\x01" + END
    if fault == "shift":
        program = (
            program[:-8]
            + b"\x17\xff\xff\0"
            + struct.pack("<h", -len(program) + 10)
            + END
        )
    elif fault == "fresh_store":
        program = program[:4] + b"\x02" + program[4:]
    elif fault == "mask":
        program = b"\x22\x02\x07\x01" + END
    elif fault == "source_copy":
        program = b"\x1d\x05\x01\0\x04\x0d\x18\x02" + END
    elif fault == "member":
        program = b"\x34\x2b\0\0" + END
    elif fault == "work":
        program = b"\x2e\x05\x0a" + END
    else:
        main = (start, b"\x18\x02" + END, b"\x18\x03" + END, b"\x18\x04" + END, END)
        assert (
            auxiliary_isolation(auxiliary(main)) is OrdinaryTaskIngressFailure.Auxiliary
        )
        return
    try:
        sources = auxiliary((start, program, END))
    except ValueError:
        # A malformed stream must fail decoding before any certificate exists.
        return
    assert isinstance(auxiliary_isolation(sources), OrdinaryTaskIngressFailure)


@pytest.fixture
def bound_auxiliary():
    data, room, _ = described(END, (END,))
    resource = EntrySelectionResource(
        "COMMON/DOOR/DOOR00.DO2", 123, hashlib.sha256(b"resource").hexdigest()
    )
    programs = json.dumps(room["programs"], sort_keys=True, separators=(",", ":"))
    descriptor = bytes(12)
    # Explicit synthetic binding isolates constructor invariants. The owned
    # 69-resource/125-source integration uses the actual shared binder.
    script = BoundAuxiliaryScript(
        0,
        resource,
        descriptor,
        data,
        programs,
        _AuxiliaryDerivation(resource, descriptor, data, programs),
    )
    selection = VerifiedEntrySelection(
        EXECUTABLE_SHA256, (resource,), (), frozenset((0,)), ()
    )
    corpus = BoundAuxiliaryCorpus(
        selection, (script,), _AuxiliaryCorpusDerivation(selection, (script,), ()), ()
    )
    return script, corpus, room


def test_decoded_resource_binding_rejects_retained_byte_program_or_corpus_substitution(
    bound_auxiliary,
):
    script, corpus, room = bound_auxiliary
    data, selection = script.data, corpus.selection
    for changes in (
        {"data": b"\x01\0"},
        {"programs_json": "{}"},
        {"descriptor": b"x" * 12},
    ):
        with pytest.raises(AssertionError):
            replace(script, **changes)
    for changes in ({"scripts": ()}, {"selection": replace(selection, resources=())}):
        with pytest.raises(AssertionError):
            replace(corpus, **changes)
    with pytest.raises(AssertionError):
        ordinary_task_ingress(b"exe", {0: (data, room)})


@pytest.mark.parametrize("field", ["data", "descriptor"])
@pytest.mark.parametrize("buffer", [bytearray, memoryview])
def test_equal_mutable_auxiliary_bytes_cannot_retain_a_compiled_receipt(
    bound_auxiliary, field, buffer
):
    script, corpus, _ = bound_auxiliary
    changed = buffer(bytearray(getattr(script, field)))
    assert changed == getattr(script, field)
    # Mutation after an equality-only seal could change packet operands while
    # programs_json and native counter-preservation permissions stayed stale.
    with pytest.raises(AssertionError):
        replace(corpus, scripts=(replace(script, **{field: changed}),))
    with pytest.raises(AssertionError):
        replace(script._derivation, **{field: changed})


def test_bool_model_alias_is_rejected_before_native_resource_formatting(
    bound_auxiliary,
):
    script, _, _ = bound_auxiliary
    assert script.model == 0
    with pytest.raises(AssertionError):
        replace(script, model=False)


def test_foreign_if_cell_formula_uses_native_stride_and_call_depth():
    assert goto_if_cell(2, 0) == (5, 0x64)
    assert goto_if_cell(10, 1) == (13, 0x84)
    assert goto_if_cell(10, 2) == (13, 0xA4)


@pytest.mark.parametrize(
    "fault", ["none", "nested_yield", "indirect", "delay", "outside"]
)
def test_nonyielding_native_closure_follows_callees_and_delay_slots(fault):
    data = bytearray(0x900)
    base = 0x80010000

    def put(offset, word):
        struct.pack_into("<I", data, 0x800 + offset, word)

    put(0, 0x0C000000 | ((base + 32) >> 2 & 0x3FFFFFF))
    put(8, 0x03E00008)
    put(32, 0x03E00008)
    if fault == "nested_yield":
        put(32, 0x0C000000 | (0x80031F94 >> 2 & 0x3FFFFFF))
        put(40, 0x03E00008)
    elif fault == "indirect":
        put(32, 0x0320F809)
    elif fault == "delay":
        put(4, 0x0320F809)
    elif fault == "outside":
        put(0, 0x0C000000 | (0x80100000 >> 2 & 0x3FFFFFF))
    assert native_nonyielding(bytes(data), base, {}) is (fault == "none")
