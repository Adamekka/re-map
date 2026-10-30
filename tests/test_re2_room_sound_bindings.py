"""RE2-PUZZLE-002: source sound bounds do not certify resource lifetime."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re2.room_sound_bindings import (
    RoomSoundBindingFailure,
    RoomSoundBindings,
    room_sound_bindings,
)
from games.re2.room_write_partitions import SourceRange


@pytest.fixture
def sound_source():
    edt, vab = 100, 292
    floor = vab + 0xE20
    data = bytearray(floor + 16)
    data[edt:vab] = b"\xff" * 192
    data[edt + 10 * 4 : edt + 11 * 4] = b"\0\0\x44\0"
    data[edt + 11 * 4 : edt + 12 * 4] = b"\0\0\x44\0"
    data[edt + 13 * 4 : edt + 14 * 4] = b"\0\0\x73\0"
    data[edt + 14 * 4 : edt + 15 * 4] = b"\0\x01\x20\x36"
    data[vab : vab + 4] = b"pBAV"
    struct.pack_into("<I", data, vab + 4, 7)
    struct.pack_into("<H", data, vab + 18, 2)
    data[vab + 32], data[vab + 48] = 16, 8
    sections = [edt, vab, floor] + [0] * 20
    struct.pack_into("<23I", data, 8, *sections)
    return data, sections, floor


def test_selected_samples_bind_exact_resources_and_unique_tone_flag_bytes(sound_source):
    data, sections, floor = sound_source
    result = room_sound_bindings(
        bytes(data), tuple(sections), floor, frozenset((10, 11, 13, 14))
    )
    assert isinstance(result, RoomSoundBindings)
    assert result.resources == (SourceRange(100, 192), SourceRange(292, 0xE20))
    assert result.tone_writes == tuple(
        SourceRange(292 + 0x821 + program * 0x200 + tone * 0x20, 1)
        for program, tone in ((0, 4), (0, 7), (1, 2), (1, 3))
    )


def test_absent_edt_entry_has_no_native_tone_write(sound_source):
    data, sections, floor = sound_source
    result = room_sound_bindings(bytes(data), tuple(sections), floor, frozenset((47,)))
    assert isinstance(result, RoomSoundBindings) and result.tone_writes == ()


def test_eof_is_the_resource_boundary_when_no_later_section_exists(sound_source):
    data, sections, floor = sound_source
    sections[2] = 0
    struct.pack_into("<23I", data, 8, *sections)
    result = room_sound_bindings(
        bytes(data[:floor]), tuple(sections), floor, frozenset((10,))
    )
    assert isinstance(result, RoomSoundBindings)
    assert result.resources[1] == SourceRange(292, 0xE20)


def test_nonzero_section_22_is_not_a_lifetime_decision_in_the_parser(sound_source):
    data, sections, floor = sound_source
    sections[22] = 100
    struct.pack_into("<23I", data, 8, *sections)
    result = room_sound_bindings(bytes(data), tuple(sections), floor, frozenset((10,)))
    assert isinstance(result, RoomSoundBindings)


@pytest.mark.parametrize("sample", [-1, 48, 255])
def test_sample_index_cannot_read_a_different_source_region(sound_source, sample):
    data, sections, floor = sound_source
    assert (
        room_sound_bindings(bytes(data), tuple(sections), floor, frozenset((sample,)))
        is RoomSoundBindingFailure.Sample
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "short-header",
        "header-mismatch",
        "edt-misaligned",
        "edt-before-header",
        "edt-gap",
        "section-past-eof",
        "next-section-in-header",
        "short-program-storage",
        "floor-before-resource-end",
        "floor-past-eof",
        "magic",
        "version",
        "zero-programs",
        "excess-programs",
    ],
)
def test_malformed_layout_is_a_modeled_failed_binding(sound_source, mutation):
    data, sections, floor = sound_source
    vab = sections[1]
    if mutation == "short-header":
        data = data[:99]
    elif mutation == "header-mismatch":
        data[8] ^= 4
    elif mutation == "edt-misaligned":
        sections[0] += 1
    elif mutation == "edt-before-header":
        sections[0] = 96
    elif mutation == "edt-gap":
        sections[0] -= 4
    elif mutation == "section-past-eof":
        sections[3] = len(data) + 1
    elif mutation == "next-section-in-header":
        sections[3] = vab + 16
    elif mutation == "short-program-storage":
        sections[2] -= 1
    elif mutation == "floor-before-resource-end":
        floor -= 1
    elif mutation == "floor-past-eof":
        floor = len(data) + 1
    elif mutation == "magic":
        data[vab : vab + 4] = b"VABp"
    elif mutation == "version":
        struct.pack_into("<I", data, vab + 4, 8)
    elif mutation == "zero-programs":
        struct.pack_into("<H", data, vab + 18, 0)
    else:
        struct.pack_into("<H", data, vab + 18, 129)
    if mutation not in ("short-header", "header-mismatch"):
        struct.pack_into("<23I", data, 8, *sections)
    result = room_sound_bindings(bytes(data), tuple(sections), floor, frozenset((10,)))
    assert result is (
        RoomSoundBindingFailure.SourceBinding
        if mutation in ("short-header", "header-mismatch")
        else RoomSoundBindingFailure.Layout
    )


@pytest.mark.parametrize(
    "packet,tones",
    [
        (b"\0\x02\0\0", 16),  # Program is outside the declared bank.
        (b"\0\0\xf0\x20", 16),  # Extra tone crosses the sixteen-tone record.
        (b"\0\0\0\x37", 16),  # Extra voice crosses the 24 fixed voices.
        (b"\0\0\x70\0", 7),  # Tone is outside the program's live tone count.
        (b"\0\0\x60\x40", 8),  # Last extra tone is outside that live count.
    ],
)
def test_selected_sound_cannot_escape_its_program_tones_or_voices(
    sound_source, packet, tones
):
    data, sections, floor = sound_source
    data[100 + 10 * 4 : 100 + 11 * 4] = packet
    data[292 + 32] = tones
    assert (
        room_sound_bindings(bytes(data), tuple(sections), floor, frozenset((10,)))
        is RoomSoundBindingFailure.Sample
    )
