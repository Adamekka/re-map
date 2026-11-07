"""RE3-MAP-015: immutable prospective source selection and fresh read epochs."""

import hashlib
import struct
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace

import pytest
from test_re3_live_map_position import live_map as live_map  # noqa: PLC0414
from test_re3_live_reader import coherent as coherent  # noqa: PLC0414
from test_re3_live_reader import live as live  # noqa: PLC0414
from test_re3_map_binding import context as context  # noqa: PLC0414
from test_re3_map_conditions import tables as tables  # noqa: PLC0414

from emulator.duckstation_gdb import MemRead
from games.re3 import live_reader, map_features
from games.re3.live_reader import (
    CurrentMapFeatureObservation,
    CurrentMapObservation,
    CurrentRoomFailure,
    read_current_map_features,
    read_current_map_position,
)
from games.re3.map_features import MapFeatureLayout, compile_map_feature_layout
from games.re3.room_data import RoomFormatFailure
from tracker.polling import PollStatus


@pytest.fixture
def features(live_map, tables, monkeypatch):
    catalog, ram, base, _ = live_map
    context, starts = tables
    for record in range(9):
        origin = record * 2048
        section = struct.unpack_from("<I", context.data, origin + 12)[0]
        # Grow original synthetic geometry to four quads; all directory aliases
        # still point at the same bounded source payload, just like the format.
        block = context.data[origin : origin + 2048]
        block[section:section] = bytes(36)
        block = block[:2048]
        for index in (1, 2, 3):
            offset = 4 + 8 * index
            previous = struct.unpack_from("<I", block, offset)[0]
            struct.pack_into("<I", block, offset, previous + 36)
        struct.pack_into("<I", block, 8, section)
        struct.pack_into("<H", block, 44, 4)
        struct.pack_into("<H", block, 52, 3)
        context.data[origin : origin + 2048] = block
    start = starts[0] + 36
    # The unused row-zero requirement also reads the physical word containing
    # a remapping guard, so coherent sampling must cover their shared storage.
    context.data[start : start + 13] = bytes(
        (1, 0, 31, 0, 1, 0, 32, 1, 0, 1, 232, 1, 255)
    )
    data, executable = bytes(context.data), bytes(context.executable)
    monkeypatch.setattr(map_features, "MAP_U_SHA256", hashlib.sha256(data).hexdigest())
    monkeypatch.setattr(
        map_features, "EXECUTABLE_SHA256", hashlib.sha256(executable).hexdigest()
    )
    layout = compile_map_feature_layout(data, executable)
    assert isinstance(layout, MapFeatureLayout), layout
    monkeypatch.setattr(live_reader, "MAP_U_SHA256", layout.position_layout.map_sha256)
    monkeypatch.setattr(
        live_reader, "EXECUTABLE_SHA256", layout.position_layout.executable_sha256
    )
    struct.pack_into("<b", ram, 0xCCBCD, 1)
    struct.pack_into("<I", ram, 0xD20DC, 0xC0000000)
    struct.pack_into("<I", ram, 0xD20CC, 1)
    struct.pack_into("<I", ram, 0xD1FA4, 0x80000000)
    return catalog, ram, base, layout, data, executable


def test_fresh_current_row_keeps_native_row_gate_and_quads_separate(features):
    catalog, ram, _, layout, _, _ = features
    calls = []

    def read(address, size):
        calls.append((address, size))
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + size]), ""
        )

    ram[0xE026A:0xE0278] = b"\xff" * 14
    struct.pack_into("<I", ram, 0xE028C, 0)
    result = read_current_map_features(catalog, layout, read)
    assert isinstance(result, CurrentMapFeatureObservation)
    assert result.features.map_position.native_stage_room == (0, 1)
    assert result.features.map_position.native_layer_index == 0
    assert result.features.group_zero_allowed_indices == (0,)
    assert result.features.native_row_visible
    assert result.features.actor_floor_i8 == result.room.actor_floor == 1
    first = calls.index((0x800CCBCD, 103))
    words = [(address, 4) for address, _ in layout.flag_words]
    assert calls[first - len(words) : first] == words
    assert calls[first + 1 : first + 1 + len(words)] == list(reversed(words))
    assert calls.count((0x800E0278, 2)) == 2
    assert not any(0x800E026A <= address <= 0x800E0277 for address, _ in calls)
    struct.pack_into("<I", ram, 0xD20DC, 0)
    hidden = read_current_map_features(catalog, layout, read)
    assert not hidden.features.native_row_visible
    assert hidden.features.group_zero_allowed_indices == (0,)
    assert not any(
        name in vars(result) for name in ("items", "clearance", "floor_id", "visits")
    )


@pytest.mark.parametrize(
    "floor,expected", [(1, (0,)), (2, (0,)), (3, (1, 2)), (4, (1, 2)), (-1, (0,))]
)
def test_signed_actor_floor_selects_source_alternatives(features, floor, expected):
    catalog, ram, _, layout, _, _ = features
    struct.pack_into("<b", ram, 0xCCBCD, floor)
    result = read_current_map_features(
        catalog,
        layout,
        lambda a, n: MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), ""),
    )
    assert result.features.group_zero_allowed_indices == expected


def test_acquisition_bypasses_metadata_only_and_restore_reverses_it(features):
    catalog, ram, _, layout, data, executable = features

    def observe(compiled):
        return read_current_map_features(
            catalog,
            compiled,
            lambda a, n: MemRead(
                True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), ""
            ),
        )

    initial = bytes(ram)
    assert observe(layout).features.group_zero_allowed_indices == (0,)
    for offset in (0xD20CC, 0xD1FA4):
        ram[:] = initial
        struct.pack_into("<I", ram, offset, 0)
        assert observe(layout).features.group_zero_allowed_indices == ()
        struct.pack_into("<I", ram, 0xD2124, 0x80000000)
        assert observe(layout).features.group_zero_allowed_indices == (0,)
    struct.pack_into("<b", ram, 0xCCBCD, 4)
    assert observe(layout).features.group_zero_allowed_indices == (1, 2)
    ram[:] = initial
    assert observe(compile_map_feature_layout(data, executable)) == observe(layout)
    assert observe(layout).features.group_zero_allowed_indices == (0,)


@pytest.mark.parametrize(
    "address,size,value,status",
    [
        (0xC7961, 1, 1, PollStatus.NonGameplay),
        (0xD1F2C, 4, 0x100, PollStatus.NonGameplay),
        (0xD1F2C, 4, 0x200, PollStatus.NonGameplay),
        (0xE0278, 2, 1, PollStatus.UnsupportedSettings),
        (0xE0278, 2, 2, PollStatus.UnsupportedSettings),
        (0xE0278, 2, 0x100, PollStatus.UnsupportedSettings),
        (0xE01E7, 1, 1, PollStatus.NonGameplay),
    ],
)
def test_pending_and_overlay_guards_are_explicit(
    features, address, size, value, status
):
    catalog, ram, _, layout, _, _ = features
    ram[address : address + size] = value.to_bytes(size, "little")

    def read(a, n):
        return MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), "")

    result = read_current_map_features(catalog, layout, read)
    assert isinstance(result, CurrentRoomFailure) and result.status is status
    if address != 0xE01E7:
        assert isinstance(
            read_current_map_position(catalog, layout.position_layout, read),
            CurrentMapObservation,
        )


@pytest.mark.parametrize("when", ["before-pose", "after-pose"])
def test_every_dependency_and_guard_change_is_atomic_retry(features, when):
    catalog, ram, _, layout, _, _ = features
    initial = bytes(ram)
    changes = [
        *layout.flag_words,
        (0x800E0278, 1),
        (0x800C7961, 1),
        (0x800D1F2C, 0x100),
        (0x800CCBCD, 1),
    ]
    for target, mask in changes:
        ram[:] = initial
        changed = False

        def read(address, size):
            nonlocal changed
            result = bytes(ram[address - 0x80000000 : address - 0x80000000 + size])
            if address == 0x800CCBCD and not changed:
                changed = True
                offset = target - 0x80000000
                width = (
                    1
                    if target in (0x800C7961, 0x800CCBCD)
                    else (2 if target == 0x800E0278 else 4)
                )
                current = int.from_bytes(ram[offset : offset + width], "little")
                ram[offset : offset + width] = (current ^ (mask & -mask)).to_bytes(
                    width, "little"
                )
                # Simulate same-room restore with unchanged source/ownership but
                # a different pose/floor and predicate epoch.
                struct.pack_into("<3i", ram, 0xCCBF8, 900, 901, 902)
                if when == "before-pose":
                    result = bytes(
                        ram[address - 0x80000000 : address - 0x80000000 + size]
                    )
            return MemRead(True, result, "")

        result = read_current_map_features(catalog, layout, read)
        assert (
            isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry
        ), hex(target)


def test_every_failed_or_short_transaction_read_is_retry(features):
    catalog, ram, _, layout, _, _ = features
    calls = []

    def read(a, n):
        calls.append((a, n))
        return MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), "")

    assert isinstance(
        read_current_map_features(catalog, layout, read), CurrentMapFeatureObservation
    )
    for index in range(len(calls)):
        for short in (False, True):
            count = 0

            def failing(a, n):
                nonlocal count
                count += 1
                if count == index + 1:
                    return MemRead(short, b"", "short" if short else "offline")
                return MemRead(
                    True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), ""
                )

            result = read_current_map_features(catalog, layout, failing)
            assert (
                isinstance(result, CurrentRoomFailure)
                and result.status is PollStatus.Retry
            )
            assert count == index + 1


@pytest.mark.parametrize(
    "target,mask",
    [
        (0x800CC858, 0x80),
        (0x800CC858, 0x100),
        (0x800D1FB8, 0x00800000),
        (0x800D1FBC, 0x4000),
        (0x800D1FC0, 1),
    ],
)
def test_dependency_sample_must_agree_with_its_overlapping_room_guard(
    features, target, mask
):
    catalog, ram, _, layout, _, _ = features
    original = bytes(ram)
    samples = 0

    def read(address, size):
        nonlocal samples
        offset = address - 0x80000000
        if (address, size) == (target, 4):
            samples += 1
            if samples == 1:
                value = int.from_bytes(ram[offset : offset + 4], "little")
                ram[offset : offset + 4] = (value ^ mask).to_bytes(4, "little")
        result = bytes(ram[offset : offset + size])
        if (address, size) == (target, 4) and samples == 2:
            # Both explicit word samples can match while the broad guards
            # return to their earlier value. The observed disagreement must
            # still reject mixed mode/remapping and feature contexts.
            ram[offset : offset + 4] = original[offset : offset + 4]
        return MemRead(True, result, "")

    result = read_current_map_features(catalog, layout, read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


def test_compiled_authority_is_deeply_immutable_and_cannot_be_substituted(features):
    _, _, _, layout, _, _ = features

    def check(value):
        assert not isinstance(value, (list, dict, bytearray))
        if is_dataclass(value):
            for item in fields(value):
                check(getattr(value, item.name))
        elif isinstance(value, tuple):
            for item in value:
                check(item)

    check(layout)
    with pytest.raises(FrozenInstanceError):
        layout.records = ()
    with pytest.raises(TypeError):
        MapFeatureLayout()
    for field_name in ("records", "flag_words", "position_layout", "_authority"):
        with pytest.raises(TypeError):
            replace(layout, **{field_name: []})
    # Changing a nested position receipt and derivation together must not create
    # a replacement feature authority with matching but uncompiled contents.
    forged_position = replace(
        layout.position_layout,
        records=(),
        _binding=replace(layout.position_layout._binding, records=()),
    )
    with pytest.raises(TypeError):
        replace(
            layout,
            position_layout=forged_position,
            _authority=(forged_position, layout.records, layout.flag_words),
        )


@pytest.mark.parametrize("source", ["map", "executable"])
def test_both_source_hashes_are_required_at_construction_and_consumption(
    features, monkeypatch, source
):
    catalog, _, _, layout, data, executable = features
    result = compile_map_feature_layout(
        data + (b"changed" if source == "map" else b""),
        executable + (b"changed" if source == "executable" else b""),
    )
    assert (
        isinstance(result, RoomFormatFailure) and result.kind == "map-feature-identity"
    )
    monkeypatch.setattr(
        live_reader,
        "MAP_U_SHA256" if source == "map" else "EXECUTABLE_SHA256",
        "0" * 64,
    )

    def read(a, n):
        raise AssertionError("wrong pinned input must fail before live reads")

    result = read_current_map_features(catalog, layout, read)
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.UnsupportedSettings
    )


def test_active_menu_is_non_gameplay_even_with_a_nonzero_overlay(features):
    catalog, ram, _, layout, _, _ = features
    ram[0xE01E7] = 1
    struct.pack_into("<H", ram, 0xE0278, 2)
    result = read_current_map_features(
        catalog,
        layout,
        lambda a, n: MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), ""),
    )
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.NonGameplay
    )


def test_polling_never_recompiles_sources(features, monkeypatch):
    catalog, ram, _, layout, _, _ = features

    def decode(*args):
        raise AssertionError("Source compilation belongs outside polling")

    for name in (
        "compile_map_position_layout",
        "decode_map_layout",
        "decode_map_conditions",
    ):
        monkeypatch.setattr(map_features, name, decode)
    for _ in range(2):
        result = read_current_map_features(
            catalog,
            layout,
            lambda a, n: MemRead(
                True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), ""
            ),
        )
        assert isinstance(result, CurrentMapFeatureObservation)


def test_compiler_rejects_mutable_source_aliases(features):
    _, _, _, _, data, executable = features
    for source, exe in ((bytearray(data), executable), (data, bytearray(executable))):
        with pytest.raises(AssertionError):
            compile_map_feature_layout(source, exe)


@pytest.mark.parametrize("bad", ["metadata", "count", "rows", "flag-span"])
def test_compiler_bounds_native_arguments_metadata_targets_and_flag_spans(
    features, monkeypatch, bad
):
    _, _, _, _, data, executable = features
    decoded = map_features.decode_map_layout(data, executable)
    if bad == "metadata":
        condition = map_features.decode_map_conditions(data, executable)
        condition["records"][0]["requirements"][0]["primitive_index"] = 255
        monkeypatch.setattr(
            map_features, "decode_map_conditions", lambda *args: condition
        )
    elif bad == "flag-span":
        # The pinned rules cannot contain this location; the compiler still
        # checks its mandatory derived spans before any transport can consume it.
        monkeypatch.setattr(map_features, "GROUP_ZERO_SYSTEM_FLAG", (0x801FFFFC, 32))
    else:
        rows = decoded["records"][0]["directory"]
        if bad == "count":
            rows[0]["primitive_groups"][0] *= 65
        else:
            rows *= 5
        monkeypatch.setattr(map_features, "decode_map_layout", lambda *args: decoded)
    result = compile_map_feature_layout(data, executable)
    assert isinstance(result, RoomFormatFailure) and result.kind == "map-feature-source"


def test_complete_context_rejects_missing_or_mutable_flag_fields(features):
    from games.re3.map_data import MapPositionContext
    from games.re3.map_features import resolve_current_row_features

    _, _, _, layout, _, _ = features
    context = MapPositionContext(0, 1, 0, 0, 0, 0, 0, 0, 0, 0)
    words = tuple((address, 0) for address, _ in layout.flag_words)
    for incomplete in (
        words[:-1],
        (*words, words[0]),
        tuple(list(pair) for pair in words),
    ):
        with pytest.raises(AssertionError):
            resolve_current_row_features(layout, context, 1, 0, incomplete)


def test_shared_predicate_word_changes_feature_and_reconstruction_repeats_it(
    features, context, monkeypatch
):
    catalog, ram, _, _, data, executable = features
    changed = bytearray(data)
    struct.pack_into("<H", changed, 44 + 47 * 8, 2)
    exe = bytearray(executable)
    exe[context.table : context.table + 8] = bytes((0, 1, 0, 47, 255, 255, 255, 255))
    import games.re3.map_data as map_data

    monkeypatch.setattr(map_data, "EXECUTABLE_SHA256", hashlib.sha256(exe).hexdigest())
    monkeypatch.setattr(
        map_features, "EXECUTABLE_SHA256", hashlib.sha256(exe).hexdigest()
    )
    monkeypatch.setattr(
        map_features, "MAP_U_SHA256", hashlib.sha256(changed).hexdigest()
    )
    layout = compile_map_feature_layout(bytes(changed), bytes(exe))
    assert isinstance(layout, MapFeatureLayout)
    monkeypatch.setattr(live_reader, "MAP_U_SHA256", layout.position_layout.map_sha256)
    monkeypatch.setattr(
        live_reader, "EXECUTABLE_SHA256", layout.position_layout.executable_sha256
    )

    def read(a, n):
        return MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), "")

    struct.pack_into("<I", ram, 0xD1FB0, 0)
    before = read_current_map_features(catalog, layout, read)
    assert before.features.map_position.native_stage_room == (0, 47)
    assert before.features.group_zero_allowed_indices == (0,)
    struct.pack_into("<I", ram, 0xD1FB0, 0x40000)
    after = read_current_map_features(catalog, layout, read)
    assert after.features.group_zero_allowed_indices == (1,)
    rebuilt = compile_map_feature_layout(bytes(changed), bytes(exe))
    assert read_current_map_features(catalog, rebuilt, read) == after
    struct.pack_into("<I", ram, 0xD1FB0, 0)
    assert read_current_map_features(catalog, rebuilt, read) == before
