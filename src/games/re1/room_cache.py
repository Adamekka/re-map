"""Bind live room scripts and refresh only source-audited past observations."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Callable
from dataclasses import dataclass, replace

from games.game_profile import RoomId
from games.re1.room_items import (
    MemoryResult,
    RuntimeItemState,
    RuntimeRoomItems,
    RuntimeRoomLayout,
)


@dataclass(frozen=True)
class RoomDependency:
    address: int
    width: int
    mask: int


@dataclass(frozen=True)
class RoomMutableField:
    section: str
    offset: int
    width: int
    kind: str
    original: int

    def __post_init__(self) -> None:
        if (
            self.section not in ("init", "main")
            or (self.kind, self.width)
            not in (("item-parameter-mask", 2), ("item-quantity", 1))
            or self.offset < 0
            or not 0 <= self.original < 1 << (8 * self.width)
        ):
            raise ValueError("invalid room manifest mutable field")


@dataclass(frozen=True)
class RoomScriptSource:
    room: RoomId
    source_rdt: str
    init_offset: int
    init_size: int
    init_sha256: str
    main_offset: int
    main_size: int
    main_sha256: str
    dependencies: tuple[RoomDependency, ...]
    item_global_ids: tuple[int, ...]
    cache_complete: bool
    door_cache_complete: bool
    mutable_fields: tuple[RoomMutableField, ...]

    def __post_init__(self) -> None:
        occupied = set()
        for field in self.mutable_fields:
            size = self.init_size if field.section == "init" else self.main_size
            if field.offset + field.width > size:
                raise ValueError("room manifest mutable field exceeds its script")
            for offset in range(field.offset, field.offset + field.width):
                key = (field.section, offset)
                if key in occupied:
                    raise ValueError("room manifest mutable fields overlap")
                occupied.add(key)


@dataclass(frozen=True)
class RoomSourceQuery:
    ok: bool
    sources: tuple[RoomScriptSource, ...] = ()
    error: str = ""
    retry: bool = False


def match_room_source(
    layout: RuntimeRoomLayout,
    sources: tuple[RoomScriptSource, ...],
    room: RoomId,
    read_memory: Callable[[int, int], MemoryResult],
) -> RoomSourceQuery:
    candidates = tuple(source for source in sources if source.room == room)
    if not candidates:
        # Other areas retain room-ID tracking; this manifest covers Mansion 1F.
        return RoomSourceQuery(ok=True)
    pointer = read_memory(layout.loaded_rdt_pointer_address, 4)
    if not pointer.ok or len(pointer.data) != 4:
        return RoomSourceQuery(
            ok=False, error=f"loaded room read: {pointer.error or 'short read'}"
        )
    base = int.from_bytes(pointer.data, "little")
    if not layout.ram_base <= base < base + 0x70 <= layout.ram_base + layout.ram_size:
        return RoomSourceQuery(ok=False, error="loaded room pointer is outside PS1 RAM")
    header = read_memory(base + 0x60, 16)
    if not header.ok or len(header.data) != 16:
        return RoomSourceQuery(
            ok=False, error=f"room script header: {header.error or 'short read'}"
        )
    init, main, events, _ = struct.unpack("<4I", header.data)
    if not base + 0x94 <= init <= main <= events <= layout.ram_base + layout.ram_size:
        return RoomSourceQuery(ok=False, error="room script ranges are outside PS1 RAM")
    matching_ranges = tuple(
        source
        for source in candidates
        if (source.init_offset, source.init_size, source.main_offset, source.main_size)
        == (init - base, main - init, main - base, events - main)
    )
    if not matching_ranges:
        return RoomSourceQuery(
            ok=False, retry=True, error="room ID and loaded script ranges disagree"
        )
    scripts = []
    for start, end in ((init, main), (main, events)):
        script = bytearray()
        for address in range(start, end, 4096):
            width = min(4096, end - address)
            result = read_memory(address, width)
            if not result.ok or len(result.data) != width:
                return RoomSourceQuery(
                    ok=False, error=f"room script read: {result.error or 'short read'}"
                )
            script.extend(result.data)
        scripts.append(script)
    matches = []
    for source in matching_ranges:
        normalized = [bytearray(script) for script in scripts]
        valid = True
        for field in source.mutable_fields:
            script = normalized[0 if field.section == "init" else 1]
            value = int.from_bytes(
                script[field.offset : field.offset + field.width], "little"
            )
            if field.kind == "item-parameter-mask" and value not in (
                field.original,
                field.original & 1,
            ):
                valid = False
                break
            # The engine masks opcode 18's parameter in place and transfers
            # quantities through source+9. Restore only those audited bytes
            # for identity hashing; every other byte must still match the disc.
            script[field.offset : field.offset + field.width] = field.original.to_bytes(
                field.width, "little"
            )
        if valid and tuple(
            hashlib.sha256(script).hexdigest() for script in normalized
        ) == (
            source.init_sha256,
            source.main_sha256,
        ):
            matches.append(source)
    if not matches:
        return RoomSourceQuery(
            ok=False, retry=True, error="room ID and loaded script identity disagree"
        )
    final_pointer = read_memory(layout.loaded_rdt_pointer_address, 4)
    final_header = read_memory(base + 0x60, 16)
    if not final_pointer.ok or not final_header.ok:
        return RoomSourceQuery(ok=False, error="room source recheck failed")
    if final_pointer.data != pointer.data or final_header.data != header.data:
        return RoomSourceQuery(
            ok=False, retry=True, error="room source changed during read"
        )
    # Variants may have identical item programs. Preserve every matching source,
    # so caching requires agreement rather than choosing an arbitrary variant.
    return RoomSourceQuery(ok=True, sources=tuple(matches))


@dataclass(frozen=True)
class CachedRoomObservation:
    observation: RuntimeRoomItems
    sources: tuple[RoomScriptSource, ...]
    context: tuple[int, ...]
    absent_flags: tuple[tuple[int, bool], ...]


def read_cache_context(
    sources: tuple[RoomScriptSource, ...],
    read_memory: Callable[[int, int], MemoryResult],
) -> tuple[tuple[int, ...], str]:
    values = []
    for source in sources:
        for dependency in source.dependencies:
            result = read_memory(dependency.address, dependency.width)
            if not result.ok or len(result.data) != dependency.width:
                return (), f"cached room condition: {result.error or 'short read'}"
            values.append(int.from_bytes(result.data, "little") & dependency.mask)
    return tuple(values), ""


def refresh_cached_items(
    cached: CachedRoomObservation,
    context: tuple[int, ...],
    acquisition_flags: bytes,
) -> RuntimeRoomItems:
    def remaining(global_id: int) -> bool:
        index = 4 * (global_id // 32) + 3 - (global_id % 32) // 8
        assert 0 <= index < len(acquisition_flags), (
            "validated manifest GlobalId must fit the acquisition block"
        )
        return bool(acquisition_flags[index] & (0x80 >> (global_id % 8)))

    if (
        not cached.sources
        or not all(source.cache_complete for source in cached.sources)
        or any(
            item.state == RuntimeItemState.Unavailable
            for item in cached.observation.items
        )
        or context != cached.context
        or any(
            remaining(gid) != was_remaining
            for gid, was_remaining in cached.absent_flags
        )
    ):
        return RuntimeRoomItems(
            ok=True,
            list_complete=False,
            coverage_reason="Re-enter this room to refresh its items.",
        )
    items = tuple(
        replace(
            item,
            state=RuntimeItemState.Available
            if remaining(item.global_id)
            else RuntimeItemState.Taken,
        )
        if item.state != RuntimeItemState.Unavailable
        else item
        for item in cached.observation.items
    )
    return replace(cached.observation, items=items)
