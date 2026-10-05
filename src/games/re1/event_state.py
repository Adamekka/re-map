"""Source-bound event activation for SLUS-00551. See RE1-EVENT-005/006/007.

Activity is transient evidence, never an acquisition or execution-history flag.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from games.re1.room_cache import RoomScriptSource
from games.re1.room_items import MemoryResult

if TYPE_CHECKING:
    from games.re1.tracking_rules import RoomProgram


@dataclass(frozen=True, order=True)
class EventPoint:
    entry: int
    offset: int
    state: int
    depth: int
    phase: str
    frames: tuple[tuple[str, int, int], ...]

    def __post_init__(self) -> None:
        if (
            any(
                type(value) is not int
                for value in (self.entry, self.offset, self.state, self.depth)
            )
            or not 0 <= self.entry < 256
            or self.offset < 0
            or not 0 <= self.state <= 3
            or not 0 <= self.depth <= 4
            or self.phase not in ("active", "waiting", "ending")
            or len(self.frames) != self.depth
            or any(
                kind not in ("wait", "counter", "loop", "call")
                or type(repeat) is not int
                or type(command) is not int
                or repeat < 0
                or command < 0
                or kind in ("wait", "counter")
                and (repeat != 0 or command != 0)
                or kind == "loop"
                and (repeat == 0 or command != 0)
                or kind == "call"
                and (repeat == 0 or command == 0)
                for kind, repeat, command in self.frames
            )
        ):
            raise ValueError("invalid indexed event position")


@dataclass(frozen=True, order=True)
class EventDispatch:
    entry: int
    offset: int
    commands: tuple[int, ...]


@dataclass(frozen=True, order=True)
class EventStart:
    entry: int
    offset: int
    kind: str
    args: tuple[int, ...]


@dataclass(frozen=True)
class EventProgram:
    entries: tuple[int, ...]
    points: tuple[EventPoint, ...]
    dispatches: tuple[EventDispatch, ...]
    starts: tuple[EventStart, ...]
    # Creator offsets bind retained registry pointers. Parameter writers retain
    # both u16 values: callback 9 consumes their low bytes, not handler/mode.
    creators: tuple[tuple[int, int], ...]
    registry_writes: tuple[tuple[int, int, int, int], ...]
    changes: tuple[tuple[int, int], ...]
    script_starts: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        if len(self.entries) > 256 or any(
            type(offset) is not int or offset < 0 for offset in self.entries
        ):
            raise ValueError("invalid indexed event table")
        for collection in (self.points, self.dispatches, self.starts):
            if len(set(collection)) != len(collection) or any(
                type(row.entry) is not int
                or type(row.offset) is not int
                or not 0 <= row.entry < len(self.entries)
                or row.offset < 0
                for row in collection
            ):
                raise ValueError("invalid event ownership")
        positions = {(p.entry, p.offset) for p in self.points}
        for dispatch in self.dispatches:
            if (
                (dispatch.entry, dispatch.offset) not in positions
                or len(set(dispatch.commands)) != len(dispatch.commands)
                or any(
                    type(offset) is not int or offset < 0
                    for offset in dispatch.commands
                )
            ):
                raise ValueError("invalid event dispatch")
        for start in self.starts:
            if (
                (start.entry, start.offset) not in positions
                or start.kind not in ("start", "restart")
                or len(start.args) != (2 if start.kind == "start" else 1)
                or any(
                    type(value) is not int or not 0 <= value <= 255
                    for value in start.args
                )
                or start.args[-1] >= len(self.entries)
            ):
                raise ValueError("invalid event activation target")
        for rows, width, capacity, maximum in (
            (self.creators, 2, 24, 65535),
            (self.registry_writes, 4, 24, 65535),
            (self.changes, 2, 24, 65535),
            (self.script_starts, 3, 256, 255),
        ):
            if any(
                len(row) != width
                or any(type(value) is not int for value in row)
                or row[0] < 0
                or not 0 <= row[1] < capacity
                or any(not 0 <= value <= maximum for value in row[2:])
                for row in rows
            ) or len({row[0] for row in rows}) != len(rows):
                raise ValueError("invalid event registry metadata")

    @staticmethod
    def load(raw: dict) -> EventProgram:
        return EventProgram(
            tuple(raw["entries"]),
            tuple(
                EventPoint(
                    **{**row, "frames": tuple(tuple(frame) for frame in row["frames"])}
                )
                for row in raw["points"]
            ),
            tuple(
                EventDispatch(row["entry"], row["offset"], tuple(row["commands"]))
                for row in raw["dispatches"]
            ),
            tuple(
                EventStart(row["entry"], row["offset"], row["kind"], tuple(row["args"]))
                for row in raw["starts"]
            ),
            tuple(tuple(row) for row in raw["creators"]),
            tuple(tuple(row) for row in raw["registry_writes"]),
            tuple(tuple(row) for row in raw["changes"]),
            tuple(tuple(row) for row in raw["script_starts"]),
        )


@dataclass(frozen=True)
class EventInitializer:
    address: int
    activity_write_address: int
    commit_address: int
    sha256: str

    def __post_init__(self) -> None:
        # The completion loop assumes the pinned straight-line initializer,
        # ending with a return and its script-pointer store in the delay slot.
        if (
            not 0x80000000 <= self.address < self.commit_address + 4 <= 0x80200000
            or self.address % 4
            or self.activity_write_address != self.address + 4
            or self.commit_address != self.address + 56
            or len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError("invalid pinned event initializer")

    def verify(self, read_memory: Callable[[int, int], MemoryResult]) -> str:
        width = self.commit_address + 4 - self.address
        result = read_memory(self.address, width)
        if not result.ok or len(result.data) != width:
            return f"Event initializer: {result.error or 'short read'}"
        if hashlib.sha256(result.data).hexdigest() != self.sha256:
            return "Event initializer does not match the pinned executable."
        return ""


@dataclass(frozen=True)
class EventLayout:
    pool_address: int
    table_pointer_address: int
    capacity: int
    stride: int
    state_offset: int
    active_offset: int
    depth_offset: int
    pc_offset: int
    repeat_offset: int
    deferred_offset: int

    def __post_init__(self) -> None:
        # Native allocation and shared frame storage fix these widths. Treat a
        # different layout as another revision, not a tunable read length.
        if (
            (self.capacity, self.stride) != (8, 0x34)
            or (
                self.state_offset,
                self.active_offset,
                self.depth_offset,
                self.pc_offset,
            )
            != (0, 2, 3, 8)
            or (self.repeat_offset, self.deferred_offset) != (0x0C, 0x1C)
            or any(
                address % 4 or not 0x80000000 <= address < address + width <= 0x80200000
                for address, width in (
                    (self.pool_address, self.capacity * self.stride),
                    (self.table_pointer_address, 4),
                )
            )
        ):
            raise ValueError("invalid pinned event layout")

    def positions(self, pool: bytes) -> tuple[tuple[int, ...], ...]:
        assert len(pool) == self.capacity * self.stride, "validated event pool width"
        # Counters and entity/frame scratch change without changing the current
        # event position. Inactive fields are stale and irrelevant to coherence.
        return tuple(
            (
                slot,
                pool[start + self.active_offset],
                pool[start + self.state_offset],
                pool[start + self.depth_offset],
                int.from_bytes(
                    pool[start + self.pc_offset : start + self.pc_offset + 4], "little"
                ),
                *(
                    int.from_bytes(
                        pool[start + first + 4 * frame : start + first + 4 * frame + 4],
                        "little",
                    )
                    for frame in range(
                        min(4, pool[start + self.depth_offset] + 1)
                        if pool[start + self.depth_offset] != 255
                        else 0
                    )
                    for first in (self.repeat_offset, self.deferred_offset)
                ),
            )
            for slot in range(self.capacity)
            if pool[(start := slot * self.stride) + self.active_offset]
        )


@dataclass(frozen=True)
class ActiveEvent:
    slot: int
    phase: str
    owners: tuple[tuple[str, int], ...]
    item_slots: tuple[int, ...]
    door_slots: tuple[int, ...]
    reason: str


@dataclass(frozen=True)
class EventInteraction:
    slot: int
    requested_slot: int
    entry: int
    owners: tuple[str, ...]
    item_slots: tuple[int, ...]
    door_slots: tuple[int, ...]
    reason: str


@dataclass(frozen=True)
class EventSnapshot:
    ok: bool
    events: tuple[ActiveEvent, ...]
    interactions: tuple[EventInteraction, ...]
    positions: tuple[tuple[int, ...], ...]
    memory_markers: tuple[tuple[int, bytes], ...]
    error: str


def read_event_snapshot(
    layout: EventLayout,
    sources: tuple[RoomScriptSource, ...],
    programs: dict[str, RoomProgram],
    base: int,
    registry: bytes,
    read_memory: Callable[[int, int], MemoryResult],
) -> EventSnapshot:
    values = []
    markers = []
    for address, width in (
        (layout.pool_address, layout.capacity * layout.stride),
        (layout.table_pointer_address, 4),
    ):
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            return EventSnapshot(
                False,
                (),
                (),
                (),
                (),
                f"event state: {result.error or 'short read'} at {address:#x}",
            )
        values.append(result.data)
        if address == layout.table_pointer_address:
            markers.append((address, result.data))
    pool, pointer = values
    table = int.from_bytes(pointer, "little")
    bound_sources = []
    for source in sources:
        event_program = programs[source.source_rdt].event_program
        if table != base + source.events_offset:
            continue
        width = 4 * (len(event_program.entries) + 1)
        if not 0x80000000 <= table < table + width <= 0x80200000:
            continue
        result = read_memory(table, width)
        if not result.ok or len(result.data) != width:
            return EventSnapshot(
                False, (), (), (), (), f"event table: {result.error or 'short read'}"
            )
        markers.append((table, result.data))
        expected = b"".join(
            (base + offset).to_bytes(4, "little") for offset in event_program.entries
        ) + bytes(4)
        if result.data == expected:
            bound_sources.append(source)

    def affected(source, entries):
        program = programs[source.source_rdt]
        event_program = program.event_program
        # Follow possible starts/restarts, including cycles, without treating
        # reachability as evidence that a trigger or a later command ran.
        reachable, pending = set(entries), list(entries)
        offsets = set()
        while pending:
            entry = pending.pop()
            commands = {
                offset
                for dispatch in event_program.dispatches
                if dispatch.entry == entry
                for offset in dispatch.commands
            }
            offsets.update(commands)
            targets = {
                start.args[-1] for start in event_program.starts if start.entry == entry
            } | {
                target
                for offset, _, target in event_program.script_starts
                if offset in commands and target < len(event_program.entries)
            }
            for target in targets - reachable:
                reachable.add(target)
                pending.append(target)
        # These are potential changes in the owning event, not evidence that
        # any particular command ran or that a collectible is available.
        slots = {slot for offset, slot in event_program.changes if offset in offsets}
        return slots & set(program.item_slots), slots & set(program.door_slots)

    events = []
    for slot in range(layout.capacity):
        record = pool[slot * layout.stride : (slot + 1) * layout.stride]
        if not record[layout.active_offset]:
            # Termination retains old pointers/state/depth. Ignore all of them;
            # an inactive slot establishes no execution history or room owner.
            continue
        pc = int.from_bytes(record[layout.pc_offset : layout.pc_offset + 4], "little")
        depth = record[layout.depth_offset]
        depth = 0 if depth == 255 else depth + 1
        owners, phases, item_slots, door_slots = set(), set(), set(), set()
        for source in bound_sources:
            points = tuple(
                p
                for p in programs[source.source_rdt].event_program.points
                if (p.offset, p.state, p.depth)
                == (pc - base, record[layout.state_offset], depth)
                and all(
                    kind not in ("loop", "call")
                    or int.from_bytes(
                        record[
                            layout.repeat_offset + 4 * index : layout.repeat_offset
                            + 4 * index
                            + 4
                        ],
                        "little",
                    )
                    == base + repeat
                    and (
                        kind != "call"
                        or int.from_bytes(
                            record[
                                layout.deferred_offset
                                + 4 * index : layout.deferred_offset + 4 * index + 4
                            ],
                            "little",
                        )
                        == base + command
                    )
                    for index, (kind, repeat, command) in enumerate(p.frames)
                )
            )
            entries = {p.entry for p in points}
            owners.update((source.source_rdt, entry) for entry in entries)
            phases.update(p.phase for p in points)
            items, doors = affected(source, entries)
            item_slots.update(items)
            door_slots.update(doors)
        events.append(
            ActiveEvent(
                slot,
                next(iter(phases))
                if len(phases) == 1
                else "active"
                if phases
                else "unbound",
                tuple(sorted(owners)),
                tuple(sorted(item_slots)),
                tuple(sorted(door_slots)),
                ""
                if owners
                else "Active event does not match the current room source.",
            )
        )
    assert len(registry) % 12 == 0, "validated registry must contain whole records"
    interactions = []
    for slot in range(len(registry) // 12):
        handler, _, parameter, model, _, pc = struct.unpack_from(
            "<BBHHHI", registry, 12 * slot
        )
        if handler != 9:
            continue
        owners, item_slots, door_slots = [], set(), set()
        entry = model & 255
        for source in bound_sources:
            program = programs[source.source_rdt]
            if (
                pc - base - 2,
                slot,
            ) not in program.event_program.creators or entry >= len(
                program.event_program.entries
            ):
                continue
            owners.append(source.source_rdt)
            items, doors = affected(source, {entry})
            item_slots.update(items)
            door_slots.update(doors)
        interactions.append(
            EventInteraction(
                slot,
                parameter & 255,
                entry,
                tuple(sorted(owners)),
                tuple(sorted(item_slots)),
                tuple(sorted(door_slots)),
                ""
                if owners
                else "Event interaction does not match the current room source.",
            )
        )
    return EventSnapshot(
        True,
        tuple(events),
        tuple(interactions),
        layout.positions(pool),
        tuple(markers),
        "",
    )
