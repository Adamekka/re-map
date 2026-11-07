"""Bounded RE3 Hard room and registration observations, without tracker mutation.

The ordinary native lifecycle and owned-source binding are mandatory. This
reader keeps singular acquisition conditions separate from complete item lists,
door state, room clearance and physical map-layer facts.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Literal

from games.game_profile import RoomId
from games.re3 import EXECUTABLE_SHA256, MAP_U_SHA256
from games.re3.collectibles import CollectibleBinding
from games.re3.map_data import (
    MapPositionContext,
    MapPositionLayout,
    NativeMapPosition,
    resolve_native_map_position,
)
from games.re3.map_features import (
    CurrentMapFeatureScope,
    MapFeatureLayout,
    NativeCurrentRowDetails,
    NativeCurrentRowFeatures,
    resolve_current_row_features,
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


@dataclass(frozen=True)
class CurrentMapFeatureObservation:
    room: CurrentRoomObservation
    features: NativeCurrentRowFeatures | NativeCurrentRowDetails


@dataclass(frozen=True)
class _MapFeatureRequest:
    layout: MapFeatureLayout
    scope: CurrentMapFeatureScope


@dataclass(frozen=True)
class CurrentCollectibleObservation:
    room: CurrentRoomObservation
    executable_sha256: str
    source_rdt_sha256: str
    packet_offset: int
    registry_slot: int
    raw_type: int
    source_amount: int
    acquisition_index: int
    acquisition_set: bool


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
# XYZ and facing come from one pose block and need not stay stationary.
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


def read_current_collectible(
    binding: CollectibleBinding,
    read_memory: Callable[[int, int], MemoryResult],
) -> CurrentCollectibleObservation | CurrentRoomFailure:
    """Read one registered packet's native acquisition condition, without caching.

    A set condition does not prove this pickup caused it. This API grants no
    departed presence, complete item list or clearance result.
    """
    assert isinstance(binding, CollectibleBinding)
    result = _read_current_room(binding.catalog, read_memory, binding)
    assert isinstance(result, (CurrentCollectibleObservation, CurrentRoomFailure))
    return result


def read_current_map_features(
    catalog: SourceCatalog,
    layout: MapFeatureLayout,
    read_memory: Callable[[int, int], MemoryResult],
    *,
    scope: CurrentMapFeatureScope = CurrentMapFeatureScope.GroupZero,
) -> CurrentMapFeatureObservation | CurrentRoomFailure:
    """Predict ordinary overlay-zero current-row source selection.

    The explicit combined scope adds per-detail native kinds and palette styles.
    The default retains the group-0 result and its original dependency reads.
    This does not admit a hardware L2 press, guarantee menu opening, bind a
    loaded MAP cache, reveal tracker rooms or establish physical ownership.
    """
    assert type(layout) is MapFeatureLayout
    assert type(scope) is CurrentMapFeatureScope
    layout._assert_compiled()
    if (
        layout.position_layout.map_sha256 != MAP_U_SHA256
        or layout.position_layout.executable_sha256 != EXECUTABLE_SHA256
    ):
        return CurrentRoomFailure(
            PollStatus.UnsupportedSettings,
            "This reader requires the supported RE3 map resource and revision",
        )
    result = _read_current_room(catalog, read_memory, _MapFeatureRequest(layout, scope))
    assert isinstance(result, (CurrentMapFeatureObservation, CurrentRoomFailure))
    return result


def _read_current_room(
    catalog: SourceCatalog,
    read_memory: Callable[[int, int], MemoryResult],
    request: MapPositionLayout | _MapFeatureRequest | CollectibleBinding | _RoomRead,
) -> (
    CurrentRoomObservation
    | CurrentMapObservation
    | CurrentMapFeatureObservation
    | CurrentCollectibleObservation
    | CurrentRoomFailure
):
    assert isinstance(catalog, SourceCatalog)
    assert (
        isinstance(request, (MapPositionLayout, _MapFeatureRequest, CollectibleBinding))
        or request is _RoomRead.WithoutMap
    )
    with_features = isinstance(request, _MapFeatureRequest)
    with_map = isinstance(request, (MapPositionLayout, _MapFeatureRequest))
    spans = (
        (_INITIAL_SPANS[0], _MAP_CONTEXT_SPAN, *_INITIAL_SPANS[1:])
        if with_map
        else _INITIAL_SPANS
    )
    guard_fields = (*_GUARD_FIELDS, *_MAP_GUARD_FIELDS) if with_map else _GUARD_FIELDS
    if with_features:
        # L2 does not clear overlay. Pending source-map requests can also precede
        # menu-active, so neither value can be inferred from a closed menu.
        spans = ((0x800E0278, 2), *spans)
        guard_fields = (
            *guard_fields,
            (0x800E0278, 2, 0xFFFF),
            (0x800C7961, 1, 0xFF),
            (0x800D1F2C, 4, 0x300),
        )
    if isinstance(request, CollectibleBinding):
        # These words already belong to the initial/repeated spans. Pin only
        # the selected registry slot, plus pending and active UI admission.
        registry_address = 0x800CC890 + 4 * request.packet[1]
        guard_fields = (
            *guard_fields,
            (registry_address, 4, 0xFFFFFFFF),
            (0x800C7961, 1, 0xFF),
            (0x800D1F2C, 4, 0x200),
        )
    identity = catalog.runtime_signature.verify(read_memory)
    if not identity.ok:
        return CurrentRoomFailure(
            PollStatus.Retry if with_features else PollStatus.ReadFailure,
            identity.error,
        )
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

    def guard_values(
        blocks: dict[int, bytes], *, require_all: bool = True
    ) -> dict[int, int]:
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
                assert not require_all, (
                    "Guard field must belong to a required read span"
                )
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
        if isinstance(request, CollectibleBinding) and (
            values[0x800C7961] or values[0x800D1F2C]
        ):
            return CurrentRoomFailure(
                PollStatus.NonGameplay, "An interface request is active"
            )
        if with_features:
            if values[0x800C7961] or values[0x800D1F2C]:
                return CurrentRoomFailure(
                    PollStatus.NonGameplay, "A map or interface request is pending"
                )
        if values[0x800E01E7] or values[0x800D4434] or values[0x800CCBA0]:
            return CurrentRoomFailure(
                PollStatus.NonGameplay, "Player control is paused or filtered"
            )
        if with_features and values[0x800E0278]:
            return CurrentRoomFailure(
                PollStatus.UnsupportedSettings,
                "This map observation requires ordinary overlay zero",
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
        pose = blocks[0x800CC830][0x3C8:0x404]
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
        if isinstance(request, CollectibleBinding) and source is not request.source:
            return CurrentRoomFailure(
                PollStatus.UnsupportedRoom, "A different collectible source is current"
            )
        base = before[0x800CC86C]
        if base != before[0x800CC870]:
            return CurrentRoomFailure(
                PollStatus.Retry, "Room source ownership is changing"
            )
        ranges = source.ranges(base)
        if isinstance(ranges, RoomFormatFailure):
            return CurrentRoomFailure(PollStatus.Retry, ranges.detail)
        if isinstance(request, CollectibleBinding) and (
            before[registry_address] != base + request.packet_offset + 2
        ):
            return CurrentRoomFailure(
                PollStatus.Retry, "Collectible registration is not ready"
            )
        observed = []
        for offset, expected in ranges:
            packet = read(base + offset, len(expected))
            if packet != expected:
                return CurrentRoomFailure(
                    PollStatus.Retry, "Loaded room does not match its source"
                )
            observed.append((offset, packet))
        if with_features:
            # The complete dependency set comes from source predicates/metadata,
            # not a guessed flag region. Resample pose only after these words.
            feature_words = tuple(
                (address, int.from_bytes(read(address, 4), "little"))
                for address, _ in (
                    request.layout.flag_words
                    if request.scope is CurrentMapFeatureScope.GroupZero
                    else request.layout.detail_flag_words
                )
            )
            # Mode/remapping words overlap the earlier broad guard blocks.
            # Compare every observed copy before using either context: two
            # matching feature samples cannot hide a conflicting guard sample.
            feature_blocks = {
                address: value.to_bytes(4, "little") for address, value in feature_words
            }
            # Decode explicit copies independently: group 1's request-word
            # address equals a broad span's base, so a dict union would hide it.
            feature_guards = guard_values(feature_blocks, require_all=False)
            if feature_guards != {
                address: before[address] for address in feature_guards
            }:
                return CurrentRoomFailure(
                    PollStatus.Retry, "Map flags disagree with room context"
                )
            # Keep floor, XYZ (+43) and facing (+101) in one actor span so a
            # restore cannot splice a separately sampled floor into this pose.
            actor_pose = read(0x800CCBCD, 103)
            pose = actor_pose[43:]
            if actor_pose[0] != before[0x800CCBCD]:
                return CurrentRoomFailure(
                    PollStatus.Retry, "Actor floor changed during read"
                )
            for address, value in reversed(feature_words):
                if int.from_bytes(read(address, 4), "little") != value:
                    return CurrentRoomFailure(
                        PollStatus.Retry, "Map selection flags changed during read"
                    )
        if isinstance(request, CollectibleBinding):
            address = base + request.packet_offset
            packet = read(address, len(request.packet))
            # Native acceptance/reentry may clear only kind2 to kind0. Keep
            # every other byte exact, rather than normalizing mutable scripts.
            if (
                packet[2] not in (0, 2)
                or packet[:2] != request.packet[:2]
                or packet[3:] != request.packet[3:]
            ):
                return CurrentRoomFailure(
                    PollStatus.Retry, "Collectible packet differs from its source"
                )
            acquisition_set = bool(
                int.from_bytes(read(request.acquisition_address, 4), "little")
                & request.acquisition_mask
            )
            if (packet[2] == 0) != acquisition_set:
                return CurrentRoomFailure(
                    PollStatus.Retry, "Collectible acquisition is not settled"
                )
            # Bracket this pose with the item condition. A same-room restore
            # can change pose and acquisition while every room guard agrees.
            pose = read(0x800CCBF8, 60)
            if (
                bool(
                    int.from_bytes(read(request.acquisition_address, 4), "little")
                    & request.acquisition_mask
                )
                != acquisition_set
                or read(address, len(packet)) != packet
            ):
                return CurrentRoomFailure(
                    PollStatus.Retry, "Collectible changed during read"
                )
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
        return CurrentRoomFailure(
            PollStatus.Retry if with_features else PollStatus.ReadFailure, str(error)
        )

    core = blocks[0x800CC830]
    observation = CurrentRoomObservation(
        RoomId(stage, room),
        camera,
        source.source.path,
        base,
        struct.unpack_from("<3i", pose),
        struct.unpack_from("<H", pose, 0x3A)[0],
        struct.unpack_from("<b", core, 0x39D)[0],
    )
    if isinstance(request, CollectibleBinding):
        return CurrentCollectibleObservation(
            observation,
            EXECUTABLE_SHA256,
            request.source_sha256,
            request.packet_offset,
            request.packet[1],
            request.raw_type,
            request.source_amount,
            request.acquisition_index,
            acquisition_set,
        )
    if with_map:
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
        if with_features:
            features = resolve_current_row_features(
                request.layout,
                context,
                observation.actor_floor,
                before[0x800E0278],
                feature_words,
                scope=request.scope,
            )
            if isinstance(features, RoomFormatFailure):
                return CurrentRoomFailure(PollStatus.UnsupportedRoom, features.detail)
            return CurrentMapFeatureObservation(observation, features)
        position = resolve_native_map_position(request, context)
        if isinstance(position, RoomFormatFailure):
            return CurrentRoomFailure(PollStatus.UnsupportedRoom, position.detail)
        return CurrentMapObservation(observation, position)
    return observation
