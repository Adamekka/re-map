"""Bounded RE3 Hard current-room observations, without tracker mutation.

The ordinary native lifecycle and owned-source binding are mandatory. This
reader establishes no item, door, room-clearance or physical map-layer facts.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from games.game_profile import RoomId
from games.re3 import EXECUTABLE_SHA256, MAP_U_SHA256
from games.re3.map_data import (
    MapPositionContext,
    MapPositionLayout,
    NativeMapPosition,
    resolve_native_map_position,
)
from games.re3.room_data import RoomFormatFailure
from games.re3.source_witnesses import SourceCatalog
from games.runtime_identity import MemoryResult
from tracker.polling import PollStatus


@dataclass(frozen=True)
class CurrentRoomObservation:
    room_id: RoomId
    camera: int
    source_path: str
    source_address: int
    position: tuple[int, int, int]
    facing: int
    actor_floor: int


@dataclass(frozen=True)
class CurrentMapObservation:
    room: CurrentRoomObservation
    map_position: NativeMapPosition


class _RoomRead(Enum):
    WithoutMap = "without-map"


@dataclass(frozen=True)
class CurrentRoomFailure:
    status: PollStatus
    detail: str

    def __post_init__(self) -> None:
        assert (
            isinstance(self.status, PollStatus)
            and self.status is not PollStatus.Display
        )
        assert type(self.detail) is str and self.detail


# Read selectors before the pose block. A complete transition can reuse the
# source address between those reads; the final selectors must still agree.
_INITIAL_SPANS = (
    (0x800D1F2C, 0x50),
    (0x800CC830, 0x568),
    (0x800C7960, 0x70),
    (0x800E01E7, 1),
    (0x800D4434, 1),
)

# Compare only native ownership/mode/source fields, rather than animation or
# input bytes that legitimately change while the same room remains current.
# XYZ and facing come from one initial pose block and need not stay stationary.
_GUARD_FIELDS = (
    (0x800CC858, 4, 0x18400780),
    (0x800D1F30, 4, 1),
    (0x800C79CC, 4, 0xFFFFFFFF),
    (0x800C7960, 1, 0xFF),
    (0x800E01E7, 1, 0xFF),
    (0x800D4434, 1, 0xFF),
    (0x800CCBA0, 4, 0x81000000),
    (0x800CCBA4, 4, 0x40000000),
    (0x800CCD94, 4, 0xFFFFFFFF),
    (0x800CCBC8, 1, 0xFF),
    (0x800CCC0A, 2, 0x8000),
    (0x800D1F76, 2, 0xFFFF),
    (0x800D1F78, 2, 0xFFFF),
    (0x800D1F7A, 2, 0xFFFF),
    (0x800CC86C, 4, 0xFFFFFFFF),
    (0x800CC870, 4, 0xFFFFFFFF),
    (0x800CCBCD, 1, 0xFF),
)

# These fresh fields affect native remapping/layers. The UI's cached current
# row can remain stale while gameplay runs, so it cannot supply this context.
_MAP_CONTEXT_SPAN = (0x800D1F7C, 0x48)
_MAP_GUARD_FIELDS = (
    (0x800D1F7C, 2, 0xFFFF),
    (0x800D1FB8, 4, 0x00800000),
    (0x800D1FBC, 4, 0x4000),
    (0x800D1FC0, 4, 1),
)


def read_current_room(
    catalog: SourceCatalog,
    read_memory: Callable[[int, int], MemoryResult],
) -> CurrentRoomObservation | CurrentRoomFailure:
    """Read fresh mode, source and pose; retain no state across polls or loads."""
    result = _read_current_room(catalog, read_memory, _RoomRead.WithoutMap)
    assert isinstance(result, (CurrentRoomObservation, CurrentRoomFailure))
    return result


def read_current_map_position(
    catalog: SourceCatalog,
    layout: MapPositionLayout,
    read_memory: Callable[[int, int], MemoryResult],
) -> CurrentMapObservation | CurrentRoomFailure:
    """Bind a fresh native map position to the same admitted source/pose epoch.

    Numeric native layers do not establish physical floors or room ownership.
    This observation does not reveal rooms or mutate tracker history.
    """
    assert isinstance(layout, MapPositionLayout)
    if (
        layout.map_sha256 != MAP_U_SHA256
        or layout.executable_sha256 != EXECUTABLE_SHA256
    ):
        return CurrentRoomFailure(
            PollStatus.UnsupportedSettings,
            "This reader requires the supported RE3 map resource and revision",
        )
    result = _read_current_room(catalog, read_memory, layout)
    assert isinstance(result, (CurrentMapObservation, CurrentRoomFailure))
    return result


def _read_current_room(
    catalog: SourceCatalog,
    read_memory: Callable[[int, int], MemoryResult],
    layout: MapPositionLayout | _RoomRead,
) -> CurrentRoomObservation | CurrentMapObservation | CurrentRoomFailure:
    assert isinstance(catalog, SourceCatalog)
    assert isinstance(layout, MapPositionLayout) or layout is _RoomRead.WithoutMap
    with_map = isinstance(layout, MapPositionLayout)
    spans = (
        (_INITIAL_SPANS[0], _MAP_CONTEXT_SPAN, *_INITIAL_SPANS[1:])
        if with_map
        else _INITIAL_SPANS
    )
    guard_fields = (*_GUARD_FIELDS, *_MAP_GUARD_FIELDS) if with_map else _GUARD_FIELDS
    identity = catalog.runtime_signature.verify(read_memory)
    if not identity.ok:
        return CurrentRoomFailure(PollStatus.ReadFailure, identity.error)
    if not identity.value:
        return CurrentRoomFailure(
            PollStatus.WrongGame, "This reader requires the supported RE3 revision"
        )

    class ReadFailure(Exception):
        pass

    def read(address: int, width: int) -> bytes:
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            raise ReadFailure(
                f"RE3 state read failed at {address:#x}: {result.error or 'short reply'}"
            )
        return result.data

    def guard_values(blocks: dict[int, bytes]) -> dict[int, int]:
        values = {}
        for address, width, mask in guard_fields:
            for base, packet in blocks.items():
                offset = address - base
                if 0 <= offset <= len(packet) - width:
                    values[address] = (
                        int.from_bytes(packet[offset : offset + width], "little") & mask
                    )
                    break
            else:
                raise AssertionError("Guard field must belong to a required read span")
        return values

    def admission(
        values: dict[int, int],
    ) -> CurrentRoomFailure | Literal[PollStatus.Display]:
        lifecycle = values[0x800CC858]
        if not lifecycle & 0x08000000 or lifecycle & 0x10000000:
            return CurrentRoomFailure(
                PollStatus.NonGameplay, "Ordinary gameplay is not active"
            )
        if lifecycle & 0x80 or values[0x800C79CC]:
            return CurrentRoomFailure(
                PollStatus.UnsupportedSettings, "Unsupported RE3 game mode"
            )
        difficulty, option = bool(lifecycle & 0x100), bool(values[0x800D1F30])
        if difficulty != option:
            return CurrentRoomFailure(
                PollStatus.Retry, "Difficulty is being initialized"
            )
        if difficulty:
            return CurrentRoomFailure(
                PollStatus.UnsupportedSettings, "This reader requires RE3 Hard mode"
            )
        if lifecycle & 0x00400000 or values[0x800C7960]:
            return CurrentRoomFailure(PollStatus.Retry, "Room loading is in progress")
        if values[0x800E01E7] or values[0x800D4434] or values[0x800CCBA0]:
            return CurrentRoomFailure(
                PollStatus.NonGameplay, "Player control is paused or filtered"
            )
        if lifecycle & 0x600 or values[0x800CCBA4]:
            return CurrentRoomFailure(PollStatus.Retry, "Player update is suspended")
        if (
            values[0x800CCD94] != 0x800CCBC4
            or values[0x800CCBC8] != 1
            or values[0x800CCC0A]
        ):
            return CurrentRoomFailure(PollStatus.Retry, "Player ownership is not ready")
        return PollStatus.Display

    try:
        blocks = {address: read(address, width) for address, width in spans}
        before = guard_values(blocks)
        failure = admission(before)
        if isinstance(failure, CurrentRoomFailure):
            return failure
        stage, room, camera = struct.unpack_from("<3h", blocks[0x800D1F2C], 0x4A)
        if not 0 <= stage < 7 or not 0 <= room <= 255 or camera < 0:
            return CurrentRoomFailure(PollStatus.Retry, "Room identity is not ready")
        source = catalog.lookup(stage, room)
        if isinstance(source, RoomFormatFailure):
            return CurrentRoomFailure(PollStatus.UnsupportedRoom, source.detail)
        if camera >= source.camera_count:
            return CurrentRoomFailure(PollStatus.Retry, "Room camera is not ready")
        base = before[0x800CC86C]
        if base != before[0x800CC870]:
            return CurrentRoomFailure(
                PollStatus.Retry, "Room source ownership is changing"
            )
        ranges = source.ranges(base)
        if isinstance(ranges, RoomFormatFailure):
            return CurrentRoomFailure(PollStatus.Retry, ranges.detail)
        observed = []
        for offset, expected in ranges:
            packet = read(base + offset, len(expected))
            if packet != expected:
                return CurrentRoomFailure(
                    PollStatus.Retry, "Loaded room does not match its source"
                )
            observed.append((offset, packet))
        for offset, packet in reversed(observed):
            if read(base + offset, len(packet)) != packet:
                return CurrentRoomFailure(
                    PollStatus.Retry, "Room source changed during read"
                )
        after_blocks = {
            address: read(address, width) for address, width in reversed(spans)
        }
        after = guard_values(after_blocks)
        if before != after:
            return CurrentRoomFailure(
                PollStatus.Retry, "Game state changed during read"
            )
        failure = admission(after)
        if isinstance(failure, CurrentRoomFailure):
            return failure
    except ReadFailure as error:
        return CurrentRoomFailure(PollStatus.ReadFailure, str(error))

    core = blocks[0x800CC830]
    observation = CurrentRoomObservation(
        RoomId(stage, room),
        camera,
        source.source.path,
        base,
        struct.unpack_from("<3i", core, 0x3C8),
        struct.unpack_from("<H", core, 0x402)[0],
        struct.unpack_from("<b", core, 0x39D)[0],
    )
    if isinstance(layout, MapPositionLayout):
        # All additional fields were read before pose and checked in reverse
        # under the same source/lifecycle guards. No later memory read is used.
        context = MapPositionContext(
            stage,
            room,
            observation.position[0],
            observation.position[2],
            observation.facing,
            before[0x800CC858],
            before[0x800D1FB8],
            before[0x800D1FBC],
            before[0x800D1FC0],
            before[0x800D1F7C],
        )
        position = resolve_native_map_position(layout, context)
        if isinstance(position, RoomFormatFailure):
            return CurrentRoomFailure(PollStatus.UnsupportedRoom, position.detail)
        return CurrentMapObservation(observation, position)
    return observation
