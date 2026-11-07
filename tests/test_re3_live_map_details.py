"""RE3-MAP-016: explicit current-row detail scope and coherent source state."""

import hashlib
import struct
from dataclasses import FrozenInstanceError, fields, is_dataclass, replace

import pytest
from test_re3_live_map_position import live_map as live_map  # noqa: PLC0414
from test_re3_live_reader import coherent as coherent  # noqa: PLC0414
from test_re3_live_reader import live as live  # noqa: PLC0414
from test_re3_map_binding import context as context  # noqa: PLC0414
from test_re3_map_detail_conditions import details as details  # noqa: PLC0414
from test_re3_map_detail_selection import (
    selected_details as selected_details,  # noqa: PLC0414
)

from emulator.duckstation_gdb import MemRead
from games.bit_flags import msb_flag_location
from games.re3 import live_reader, map_features
from games.re3.live_reader import (
    CurrentMapFeatureObservation,
    CurrentRoomFailure,
    read_current_map_features,
)
from games.re3.map_data import MapPositionContext
from games.re3.map_detail_predicates import (
    DetailSelection,
    NativeMapDetail,
    select_group_one_detail,
)
from games.re3.map_features import (
    CurrentMapFeatureScope,
    MapFeatureLayout,
    NativeCurrentRowDetails,
    NativeCurrentRowFeatures,
    compile_map_feature_layout,
    resolve_current_row_features,
)
from games.re3.room_data import RoomFormatFailure
from tracker.polling import PollStatus

COMBINED = CurrentMapFeatureScope.GroupZeroAndOne


@pytest.fixture
def detail_features(live_map, selected_details, monkeypatch):
    catalog, ram, base, _ = live_map
    source = selected_details
    style, _, admission = source.table_starts[0]
    source.data[style : style + 13] = bytes(
        (1, 0, 255, 255, 1, 0, 31, 0, 1, 0, 32, 1, 255)
    )
    source.data[admission : admission + 9] = bytes((1, 0, 0, 0, 1, 0, 0, 1, 255))

    def compile_source():
        data, executable = bytes(source.data), bytes(source.executable)
        monkeypatch.setattr(
            map_features, "MAP_U_SHA256", hashlib.sha256(data).hexdigest()
        )
        monkeypatch.setattr(
            map_features, "EXECUTABLE_SHA256", hashlib.sha256(executable).hexdigest()
        )
        layout = compile_map_feature_layout(data, executable)
        assert isinstance(layout, MapFeatureLayout), layout
        monkeypatch.setattr(
            live_reader, "MAP_U_SHA256", layout.position_layout.map_sha256
        )
        monkeypatch.setattr(
            live_reader, "EXECUTABLE_SHA256", layout.position_layout.executable_sha256
        )
        return layout

    struct.pack_into("<b", ram, 0xCCBCD, 4)
    return catalog, ram, base, source, compile_source


def test_current_detail_kind_style_and_row_visibility_are_separate(detail_features):
    catalog, ram, _, source, compile_source = detail_features
    layout = compile_source()
    calls = []

    def read(address, size):
        calls.append((address, size))
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + size]), ""
        )

    # Stale map-menu caches and absent loaded MAP cannot select a source here.
    ram[0xE026A:0xE0278] = b"\xff" * 14
    struct.pack_into("<I", ram, 0xE028C, 0)
    original = read_current_map_features(catalog, layout, read)
    assert type(original.features) is NativeCurrentRowFeatures
    original_calls = calls[:]
    calls.clear()
    result = read_current_map_features(catalog, layout, read, scope=COMBINED)
    assert type(result.features) is NativeCurrentRowDetails
    f = result.features
    assert f.group_zero.map_position.native_stage_room == (0, 1)
    assert f.group_one_count == 1
    assert f.group_one_allowed == (NativeMapDetail(0, 4, 2, 2),)
    assert not f.group_zero.native_row_visible
    assert (
        replace(f.group_zero, flag_words=original.features.flag_words)
        == original.features
    )
    first = calls.index((0x800CCBCD, 103))
    words = [(address, 4) for address, _ in layout.detail_flag_words]
    assert calls[first - len(words) : first] == words
    assert calls[first + 1 : first + 1 + len(words)] == list(reversed(words))
    assert len(calls) - len(original_calls) == 2 * (
        len(layout.detail_flag_words) - len(layout.flag_words)
    )
    struct.pack_into("<I", ram, 0xD20DC, 0x40000000)
    visible = read_current_map_features(catalog, layout, read, scope=COMBINED)
    assert visible.features.group_zero.native_row_visible
    assert visible.features.group_one_allowed == f.group_one_allowed
    source.data[560] = 7
    kind_seven = read_current_map_features(
        catalog, compile_source(), read, scope=COMBINED
    )
    assert kind_seven.features.group_one_allowed == (NativeMapDetail(0, 7, 2, 0),)
    assert not any(
        key in vars(result)
        for key in ("items", "doors", "clearance", "history", "floor_id")
    )


def test_live_detail_clear_set_clear_and_reconstruction(detail_features):
    catalog, ram, _, source, compile_source = detail_features
    layout = compile_source()

    def observe(compiled):
        return read_current_map_features(
            catalog,
            compiled,
            lambda a, n: MemRead(
                True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), ""
            ),
            scope=COMBINED,
        )

    initial = bytes(ram)
    before = observe(layout)
    for address in (0xD20CC, 0xD1FA0):
        struct.pack_into("<I", ram, address, 0x80000000)
        assert observe(layout).features.group_one_allowed == ()
        ram[:] = initial
        assert observe(compile_source()) == before
    struct.pack_into("<I", ram, 0xD20CC, 1)
    assert observe(layout).features.group_one_allowed[0].requested_palette_variant == 2
    struct.pack_into("<I", ram, 0xD1FA4, 0x80000000)
    assert observe(layout).features.group_one_allowed[0].requested_palette_variant == 0
    ram[:] = initial
    # SB of an acquired supported-group helper mask still has a zero low byte.
    start = source.table_starts[0][2]
    source.data[start : start + 5] = bytes((1, 0, 0, 0x10, 255))
    layout = compile_source()
    struct.pack_into("<I", ram, 0xD2124, 0x80000000)
    acquired = observe(layout).features
    assert acquired.group_zero.native_map_acquired
    assert acquired.native_map_acquisition_byte == 0
    assert acquired.group_one_allowed == ()
    # Raw floor drives the early shape rule independently of lifecycle/mode.
    ram[:] = initial
    source.data[start] = 255
    layout = compile_source()
    for floor, allowed in ((2, False), (3, True), (-1, False), (4, True)):
        struct.pack_into("<b", ram, 0xCCBCD, floor)
        assert bool(observe(layout).features.group_one_allowed) is allowed


@pytest.mark.parametrize("when", ["before-pose", "after-pose"])
def test_all_detail_dependencies_and_same_room_restore_are_atomic(
    detail_features, when
):
    catalog, ram, _, _, compile_source = detail_features
    layout = compile_source()
    initial = bytes(ram)
    for target, mask in (
        *layout.detail_flag_words,
        (0x800CCBCD, 1),
        (0x800E0278, 1),
        (0x800C7961, 1),
    ):
        ram[:] = initial
        changed = False

        def read(address, size):
            nonlocal changed
            at = address - 0x80000000
            packet = bytes(ram[at : at + size])
            if address == 0x800CCBCD and not changed:
                changed = True
                offset = target - 0x80000000
                width = (
                    1
                    if target in (0x800CCBCD, 0x800C7961)
                    else (2 if target == 0x800E0278 else 4)
                )
                value = int.from_bytes(ram[offset : offset + width], "little") ^ (
                    mask & -mask
                )
                ram[offset : offset + width] = value.to_bytes(width, "little")
                struct.pack_into("<3i", ram, 0xCCBF8, 123, 456, 789)
                if when == "before-pose":
                    packet = bytes(ram[at : at + size])
            return MemRead(True, packet, "")

        result = read_current_map_features(catalog, layout, read, scope=COMBINED)
        assert (
            isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry
        ), hex(target)


@pytest.mark.parametrize("short", [False, True])
def test_every_detail_transaction_failure_rejects_atomically(detail_features, short):
    catalog, ram, _, _, compile_source = detail_features
    layout = compile_source()
    calls = []

    def read(a, n):
        calls.append((a, n))
        return MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), "")

    assert isinstance(
        read_current_map_features(catalog, layout, read, scope=COMBINED),
        CurrentMapFeatureObservation,
    )
    for index in range(len(calls)):
        count = 0

        def failing(a, n):
            nonlocal count
            count += 1
            if count == index + 1:
                return MemRead(short, b"", "short" if short else "offline")
            return MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), "")

        result = read_current_map_features(catalog, layout, failing, scope=COMBINED)
        assert (
            isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry
        )
        assert count == index + 1


@pytest.mark.parametrize(
    "target,mask",
    [
        (0x800CC858, 0x80),
        (0x800CC858, 0x100),
        (0x800D1FB8, 0x800000),
        (0x800D1FBC, 0x4000),
        (0x800D1FC0, 1),
        (0x800D1F2C, 0x100),
        (0x800D1F2C, 0x200),
    ],
)
def test_detail_explicit_samples_cannot_disagree_with_broad_guards(
    detail_features, target, mask
):
    catalog, ram, _, _, compile_source = detail_features
    layout = compile_source()

    def read(address, size):
        packet = bytes(ram[address - 0x80000000 : address - 0x80000000 + size])
        if (address, size) == (target, 4):
            packet = (int.from_bytes(packet, "little") ^ mask).to_bytes(4, "little")
        return MemRead(True, packet, "")

    result = read_current_map_features(catalog, layout, read, scope=COMBINED)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


@pytest.mark.parametrize(
    "address,width,value,status",
    [
        (0xC7961, 1, 1, PollStatus.NonGameplay),
        (0xD1F2C, 4, 0x100, PollStatus.NonGameplay),
        (0xD1F2C, 4, 0x200, PollStatus.NonGameplay),
        (0xE0278, 2, 0x100, PollStatus.UnsupportedSettings),
        (0xE01E7, 1, 1, PollStatus.NonGameplay),
    ],
)
def test_detail_pending_active_and_full_overlay_rejection(
    detail_features, address, width, value, status
):
    catalog, ram, _, _, compile_source = detail_features
    ram[address : address + width] = value.to_bytes(width, "little")
    result = read_current_map_features(
        catalog,
        compile_source(),
        lambda a, n: MemRead(True, bytes(ram[a - 0x80000000 : a - 0x80000000 + n]), ""),
        scope=COMBINED,
    )
    assert isinstance(result, CurrentRoomFailure) and result.status is status


def test_detail_authority_nested_substitution_and_complete_dependencies(
    detail_features, monkeypatch
):
    _, _, _, source, compile_source = detail_features
    layout = compile_source()

    def immutable(value):
        assert not isinstance(value, (dict, list, bytearray))
        if is_dataclass(value):
            for item in fields(value):
                immutable(getattr(value, item.name))
        elif isinstance(value, tuple):
            for child in value:
                immutable(child)

    immutable(layout)
    for name in ("detail_records", "detail_flag_words"):
        with pytest.raises(FrozenInstanceError):
            setattr(layout, name, ())
        with pytest.raises(TypeError):
            replace(layout, **{name: ()})
    forged = layout.detail_records[0]._replace(native_kinds=())
    records = (forged, *layout.detail_records[1:])
    with pytest.raises(TypeError):
        replace(
            layout,
            detail_records=records,
            _authority=(*layout._authority[:3], records, layout.detail_flag_words),
        )
    context = MapPositionContext(0, 1, 0, 0, 0, 0, 0, 0, 0, 0)
    words = tuple((address, 0) for address, _ in layout.detail_flag_words)
    for bad in (words[:-1], (*words, words[0]), tuple(list(pair) for pair in words)):
        with pytest.raises(AssertionError):
            resolve_current_row_features(layout, context, 4, 0, bad, scope=COMBINED)
    # Caller-owned source mutations after compilation cannot change authority.
    data, executable = bytes(source.data), bytes(source.executable)
    source.data[560] = 7
    assert layout.detail_records[0].native_kinds[1] == (4,)
    decoded = map_features.decode_map_layout(data, executable)
    decoded["records"][0]["directory"][0]["primitive_groups"][1] *= 257
    monkeypatch.setattr(map_features, "decode_map_layout", lambda *args: decoded)
    failure = compile_map_feature_layout(data, executable)
    assert (
        isinstance(failure, RoomFormatFailure) and failure.kind == "map-feature-source"
    )


def test_group_one_admission_order_early_late_system_and_raw_byte():
    from games.re3.map_conditions import DetailRequirement, DetailStyleCondition

    requirement = (DetailRequirement(40, 0, 0x800D20CC, 0, True),)
    calls = []
    system = False

    def flag(bank, index):
        calls.append((bank, index))
        return 0x80 if (bank, index) == (0x800CC858, 24) and system else 0

    def select(group, row, acquisition):
        return select_group_one_detail(
            requirement,
            (DetailStyleCondition(row, 0, 0, 255),),
            group,
            row,
            0,
            4,
            0,
            4,
            0,
            acquisition,
            flag,
        )

    assert select(2, 40, 0) is DetailSelection.Reject
    assert (0x800D20CC, 0) not in calls
    calls.clear()
    assert select(2, 40, 1) == NativeMapDetail(0, 4, 0, 0)
    assert (0x800D20CC, 0) in calls
    system = True
    calls.clear()
    assert select(2, 40, 1) is DetailSelection.Reject
    assert (0x800D20CC, 0) not in calls
    assert select(2, 41, 0) == NativeMapDetail(0, 4, 0, 0)
    assert select(0, 40, 0) == NativeMapDetail(0, 4, 0, 0)
    assert select(0, 12, 0) == NativeMapDetail(0, 4, 2, 2)


@pytest.mark.parametrize("kind", [0, 1, 4, 6, 7, 8, 255])
@pytest.mark.parametrize("selector", range(4))
def test_exact_native_kind_palette_and_style_banks(kind, selector):
    from games.re3.map_conditions import DETAIL_STYLE_BANKS, DetailStyleCondition

    reads = []

    def flag(bank, index):
        reads.append((bank, index))
        return 0

    result = select_group_one_detail(
        (),
        (DetailStyleCondition(40, 0, 255, selector),),
        5,
        40,
        0,
        kind,
        0,
        4,
        0,
        0,
        flag,
    )
    assert result == NativeMapDetail(0, kind, 2, 0 if kind == 7 else 2)
    assert (DETAIL_STYLE_BANKS[selector], 255) in reads


def test_declared_detail_masks_cover_all_metadata_even_skipped_targets(detail_features):
    _, _, _, source, compile_source = detail_features
    style = source.table_starts[0][0]
    source.data[style : style + 9] = bytes((255 - 1, 255, 255, 2, 1, 0, 255, 255, 255))
    layout = compile_source()
    assert layout.detail_records[0].styles[0].row == 254
    words = dict(layout.detail_flag_words)
    address, mask = msb_flag_location(0x800D1FC8, 255)
    assert words[address] & mask
    assert layout.detail_records[0].styles[1].selector == 255
    for record in layout.detail_records:
        for entry in record.requirements:
            address, mask = msb_flag_location(entry.bank, entry.flag_index)
            assert words[address] & mask
