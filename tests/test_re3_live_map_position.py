"""RE3-LIVE-002: fresh native projection without cached map-screen state."""

import hashlib
import struct
from dataclasses import replace

import pytest
from test_re3_live_reader import coherent as coherent  # noqa: PLC0414
from test_re3_live_reader import live as live  # noqa: PLC0414
from test_re3_map_binding import context as context  # noqa: PLC0414
from test_re3_map_binding import synthetic_layout

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re3 import live_reader, map_data
from games.re3.live_reader import (
    CurrentMapObservation,
    CurrentRoomFailure,
    read_current_map_position,
)
from tracker.polling import PollStatus


@pytest.fixture
def live_map(live, context, monkeypatch):
    catalog, ram, base = live
    layout = map_data.compile_map_position_layout(context.data, context.executable)
    assert isinstance(layout, map_data.MapPositionLayout)
    # Original synthetic resources replace only the mandatory identity hashes.
    # Neither the live reader nor the compiler accepts fixture defaults.
    monkeypatch.setattr(live_reader, "MAP_U_SHA256", layout.map_sha256)
    monkeypatch.setattr(live_reader, "EXECUTABLE_SHA256", layout.executable_sha256)
    source = catalog.lookup(0, 1)
    ram[base : base + source.rdt_size] = source.source.rdt
    for offset, expected in source.ranges(0x80100000):
        ram[base + offset : base + offset + len(expected)] = expected
    struct.pack_into("<h", ram, 0xD1F78, 1)
    struct.pack_into("<3i", ram, 0xCCBF8, -549, 42, 1549)
    struct.pack_into("<H", ram, 0xCCC32, 1024)
    return catalog, ram, base, layout


def test_fresh_source_projects_even_when_map_screen_caches_are_stale(live_map):
    catalog, ram, _, layout = live_map
    ram[0xE026A:0xE026D] = b"\xff\xff\xff"
    calls = []

    def read(address, width):
        calls.append((address, width))
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        )

    result = read_current_map_position(catalog, layout, read)
    assert isinstance(result, CurrentMapObservation)
    assert result.room.room_id == RoomId(0, 1)
    assert result.room.position == (-549, 42, 1549)
    assert result.map_position.native_stage_room == (0, 1)
    assert result.map_position.native_map_xy == (102, -100)
    assert result.map_position.native_layer_index == 0
    assert result.room.actor_floor == -2
    assert result.map_position.player_heading_degrees == 180
    assert result.map_position.native_arrow_sector == 2
    assert result.map_position.map_sha256 == layout.map_sha256
    assert calls[4:7] == [(0x800D1F2C, 80), (0x800D1F7C, 72), (0x800CC830, 1384)]
    assert len(calls) == 24 and max(width for _, width in calls) <= 4096
    assert not any(
        name in vars(result)
        for name in ("visits", "items", "doors", "completion", "floor_id")
    )


@pytest.mark.parametrize("index", range(1, 25))
@pytest.mark.parametrize("short", [False, True])
def test_map_read_failures_do_not_publish_partial_observations(live_map, index, short):
    catalog, ram, _, layout = live_map
    count = 0

    def read(address, width):
        nonlocal count
        count += 1
        if count == index:
            return MemRead(short, b"", "" if short else "disconnected")
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        )

    result = read_current_map_position(catalog, layout, read)
    assert isinstance(result, CurrentRoomFailure)
    assert result.status is PollStatus.ReadFailure and count == index


@pytest.mark.parametrize(
    "address,width,mask",
    [
        (0xD1F7C, 2, 0x503),
        (0xD1FB8, 4, 0x00800000),
        (0xD1FBC, 4, 0x4000),
        (0xD1FC0, 4, 1),
    ],
)
@pytest.mark.parametrize("relevant", [True, False])
def test_map_context_is_rechecked_with_its_source(
    live_map, address, width, mask, relevant
):
    catalog, ram, base, layout = live_map
    changed = False

    def read(at, size):
        nonlocal changed
        if at == 0x80000000 + base + 1 and not changed:
            changed = True
            initial = int.from_bytes(ram[address : address + width], "little")
            # The previous identifier is fully masked, so only its unchanged
            # value can pass. The flag words also have unrelated bits to test.
            value = initial ^ (mask if relevant else (0 if width == 2 else 2))
            ram[address : address + width] = value.to_bytes(width, "little")
        return MemRead(True, bytes(ram[at - 0x80000000 : at - 0x80000000 + size]), "")

    result = read_current_map_position(catalog, layout, read)
    if relevant:
        assert (
            isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry
        )
    else:
        assert isinstance(result, CurrentMapObservation)


def test_moving_pose_uses_initial_contiguous_position_and_facing(live_map):
    catalog, ram, _, layout = live_map
    count = 0

    def read(address, width):
        nonlocal count
        if address == 0x800CC830:
            count += 1
            if count == 2:
                struct.pack_into("<3i", ram, 0xCCBF8, 123456, 50, -123456)
                struct.pack_into("<H", ram, 0xCCC32, 0)
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        )

    result = read_current_map_position(catalog, layout, read)
    assert isinstance(result, CurrentMapObservation)
    assert result.room.position == (-549, 42, 1549)
    assert result.map_position.native_map_xy == (102, -100)
    assert result.map_position.raw_facing_u16 == result.room.facing == 1024


def test_earlier_restore_reverses_projection_and_easy_never_latches_hard(live_map):
    catalog, ram, _, layout = live_map
    initial = bytes(ram)

    def read(address, width):
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        )

    before = read_current_map_position(catalog, layout, read)
    assert isinstance(before, CurrentMapObservation)
    struct.pack_into("<i", ram, 0xCCBF8, 351)
    assert read_current_map_position(
        catalog, layout, read
    ).map_position.native_map_xy == (104, -100)
    struct.pack_into("<I", ram, 0xCC858, 0x08000100)
    struct.pack_into("<I", ram, 0xD1F30, 1)
    easy = read_current_map_position(catalog, layout, read)
    assert (
        isinstance(easy, CurrentRoomFailure)
        and easy.status is PollStatus.UnsupportedSettings
    )
    ram[:] = initial
    assert read_current_map_position(catalog, layout, read) == before


@pytest.mark.parametrize("field", ["MAP_U_SHA256", "EXECUTABLE_SHA256"])
def test_live_map_requires_both_pinned_resources(live_map, monkeypatch, field):
    catalog, _, _, layout = live_map
    monkeypatch.setattr(
        live_reader, field, hashlib.sha256(b"wrong resource").hexdigest()
    )

    def read(address, width):
        raise AssertionError("Unsupported static layout must fail before polling")

    result = read_current_map_position(catalog, layout, read)
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.UnsupportedSettings
    )


def test_missing_native_projection_row_is_an_explicit_failure(
    live_map, context, monkeypatch
):
    catalog, ram, _, _ = live_map
    layout = map_data.compile_map_position_layout(
        synthetic_layout(rows=1, anchors=1), context.executable
    )
    monkeypatch.setattr(live_reader, "MAP_U_SHA256", layout.map_sha256)
    result = read_current_map_position(
        catalog,
        layout,
        lambda address, width: MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        ),
    )
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.UnsupportedRoom
    )


def test_polling_reuses_compiled_layout(live_map, monkeypatch):
    catalog, ram, _, layout = live_map

    def decode(*args):
        raise AssertionError("Static source must not be decoded on every poll")

    monkeypatch.setattr(map_data, "decode_map_layout", decode)
    for _ in range(2):
        result = read_current_map_position(
            catalog,
            layout,
            lambda address, width: MemRead(
                True,
                bytes(ram[address - 0x80000000 : address - 0x80000000 + width]),
                "",
            ),
        )
        assert isinstance(result, CurrentMapObservation)


@pytest.mark.parametrize(
    "field", ["records", "remaps", "map_sha256", "executable_sha256"]
)
def test_copied_layout_cannot_change_derived_projection_or_identity(live_map, field):
    _, _, _, layout = live_map
    value = () if field in ("records", "remaps") else "0" * 64
    if field == "remaps":
        value = ((0, 1, 2, 3),)
    with pytest.raises(AssertionError):
        replace(layout, **{field: value})
    record = replace(layout.records[0], anchors=())
    with pytest.raises(AssertionError):
        replace(layout, records=(record, *layout.records[1:]))
    assert replace(layout) == layout
