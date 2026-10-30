"""RE2-STARTUP-004: effect reads are bounded without a lifetime capability."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re2.immediate_effect_resource import (
    ImmediateEffectFailure,
    ImmediateEffectResource,
    immediate_effect_resource,
)
from games.re2.room_write_partitions import SourceRange


@pytest.fixture
def effect_source():
    command, ids, first, second, reverse, floor = 100, 128, 136, 376, 636, 640
    data = bytearray(floor + 16)
    data[command] = 0x54
    data[command + 2] = 22
    data[ids : ids + 8] = bytes((22, 9, 255, 255, 255, 255, 255, 255))
    struct.pack_into("<2H", data, first, 1, 2)
    struct.pack_into("<2H", data, second, 2, 2)
    for directory in (first + 24, second + 32):
        struct.pack_into("<8H", data, directory, *([4] * 8))
        struct.pack_into("<2H", data, directory + 16, 1, 0)
        struct.pack_into("<2H", data, directory + 20, 2, 0)
        data[directory + 24 : directory + 48] = bytes(range(24))
    struct.pack_into("<I", data, reverse, first - ids)
    struct.pack_into("<I", data, reverse - 4, second - ids)
    sections = [0] * 23
    sections[2], sections[18], sections[19] = floor, ids, reverse
    struct.pack_into("<23I", data, 8, *sections)
    return data, sections, floor, command


def test_static_call_protects_its_id_list_reverse_table_and_complete_resource(
    effect_source,
):
    data, sections, floor, command = effect_source
    result = immediate_effect_resource(bytes(data), tuple(sections), floor, command)
    assert result == ImmediateEffectResource(
        (SourceRange(128, 8), SourceRange(136, 240), SourceRange(632, 8))
    )
    assert not hasattr(result, "continuation_safe")
    assert not hasattr(result, "lifetime_safe")


@pytest.mark.parametrize("subtype", [1, 7, 8, 255])
def test_native_subtype_uses_only_the_low_three_bits(effect_source, subtype):
    data, sections, floor, command = effect_source
    data[command + 3] = subtype
    assert isinstance(
        immediate_effect_resource(bytes(data), tuple(sections), floor, command),
        ImmediateEffectResource,
    )


def test_last_reverse_binding_selects_its_own_resource(effect_source):
    data, sections, floor, command = effect_source
    data[command + 2] = 9
    assert immediate_effect_resource(bytes(data), tuple(sections), floor, command) == (
        ImmediateEffectResource(
            (SourceRange(128, 8), SourceRange(376, 256), SourceRange(632, 8))
        )
    )


@pytest.mark.parametrize("identifier", [63, 64, 79, 80, 254])
def test_native_pointer_bindings_cannot_reach_sound_or_another_table(
    effect_source, identifier
):
    data, sections, floor, command = effect_source
    data[128] = data[command + 2] = identifier
    result = immediate_effect_resource(bytes(data), tuple(sections), floor, command)
    assert (
        isinstance(result, ImmediateEffectResource)
        if identifier == 63
        else result is ImmediateEffectFailure.BindingRange
    )


@pytest.mark.parametrize("case", ["short-header", "header-drift"])
def test_resource_inputs_must_bind_the_actual_header(effect_source, case):
    data, sections, floor, command = effect_source
    if case == "short-header":
        data = data[:99]
    else:
        sections[18] += 4
    assert (
        immediate_effect_resource(bytes(data), tuple(sections), floor, command)
        is ImmediateEffectFailure.SourceBinding
    )


@pytest.mark.parametrize(
    "case",
    [
        "wrong-opcode",
        "reference-kind",
        "reference-index",
        "before-header",
        "past-floor",
        "unbound-id",
    ],
)
def test_only_the_bound_static_matrix_command_is_admitted(effect_source, case):
    data, sections, floor, command = effect_source
    if case == "wrong-opcode":
        data[command] = 0x3A
    elif case == "reference-kind":
        data[command + 4] = 4
    elif case == "reference-index":
        data[command + 5] = 1
    elif case == "before-header":
        command = 99
    elif case == "past-floor":
        command = floor - 21
    else:
        data[command + 2] = 23
    assert (
        immediate_effect_resource(bytes(data), tuple(sections), floor, command)
        is ImmediateEffectFailure.Command
    )


@pytest.mark.parametrize(
    "case",
    [
        "floor-drift",
        "floor-past-source",
        "unaligned-floor",
        "section-past-source",
        "missing-ids",
        "unaligned-ids",
        "missing-reverse",
        "unaligned-reverse",
        "missing-sentinel",
        "empty-list",
        "duplicate-id",
        "reverse-overlaps-ids",
        "data-overlaps-ids",
        "data-overlaps-reverse",
        "data-past-source",
        "unaligned-data",
        "duplicate-data",
        "selected-directory-past-block",
        "other-directory-past-block",
        "entry-overlaps-directory",
        "entry-past-block",
        "short-record",
        "zero-elements",
        "multiple-elements",
    ],
)
def test_unbounded_source_layouts_return_an_explicit_failure(effect_source, case):
    data, sections, floor, command = effect_source
    if case == "floor-drift":
        floor += 4
    elif case == "floor-past-source":
        floor = sections[2] = len(data) + 4
    elif case == "unaligned-floor":
        floor = sections[2] = floor - 1
    elif case == "section-past-source":
        sections[20] = len(data) + 1
    elif case == "missing-ids":
        sections[18] = 0
    elif case == "unaligned-ids":
        sections[18] += 1
    elif case == "missing-reverse":
        sections[19] = 0
    elif case == "unaligned-reverse":
        sections[19] -= 1
    elif case == "missing-sentinel":
        data[128:136] = bytes(range(8))
    elif case == "empty-list":
        data[128] = 255
    elif case == "duplicate-id":
        data[129] = 22
    elif case == "reverse-overlaps-ids":
        sections[19] = 136
    elif case == "data-overlaps-ids":
        struct.pack_into("<I", data, 636, 4)
    elif case == "data-overlaps-reverse":
        struct.pack_into("<I", data, 636, 632 - 128)
    elif case == "data-past-source":
        struct.pack_into("<I", data, 636, 0xFFFFFFFF)
    elif case == "unaligned-data":
        struct.pack_into("<I", data, 636, 9)
    elif case == "duplicate-data":
        struct.pack_into("<I", data, 632, 8)
    elif case == "selected-directory-past-block":
        struct.pack_into("<H", data, 136, 0xFFFF)
    elif case == "other-directory-past-block":
        struct.pack_into("<H", data, 376, 0xFFFF)
    elif case == "entry-overlaps-directory":
        struct.pack_into("<H", data, 160, 0)
    elif case == "entry-past-block":
        struct.pack_into("<H", data, 160, 0xFFFF)
    elif case == "short-record":
        struct.pack_into("<H", data, 160, (376 - 28 - 160) // 4)
        struct.pack_into("<H", data, 348, 1)
    elif case == "zero-elements":
        struct.pack_into("<H", data, 176, 0)
    else:
        struct.pack_into("<H", data, 176, 2)
    struct.pack_into("<23I", data, 8, *sections)
    assert (
        immediate_effect_resource(bytes(data), tuple(sections), floor, command)
        is ImmediateEffectFailure.Layout
    )
