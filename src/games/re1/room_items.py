"""Read RE1's registered room interactions, rather than static spawn guesses.

The pinned executable uses the same AOT descriptor for walking up to an item,
scripted awards, maps, and the pending pickup screen. Addresses remain profile
configuration. RE1-COVER-002 records the checked award paths and their limits.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from games.game_profile import RoomId


class MemoryResult(Protocol):
    ok: bool
    data: bytes
    error: str


class RuntimeItemState(Enum):
    Available = "available"
    Taken = "taken"
    Unavailable = "unavailable"


class RuntimeItemKind(Enum):
    Inventory = "inventory"
    Map = "map"


@dataclass(frozen=True)
class RuntimeRoomLayout:
    aot_base: int
    aot_bound_address: int
    aot_capacity: int
    loaded_rdt_pointer_address: int
    acquisition_flags_address: int
    acquisition_flags_width: int
    ram_base: int
    ram_size: int
    pending_action_pointer_address: int
    main_flags_address: int
    pending_item_mask: int
    item_labels: tuple[tuple[int, str], ...]

    def __post_init__(self) -> None:
        if not 1 <= self.aot_capacity <= 128:
            raise ValueError("AOT capacity must fit the seven-bit item slot index")
        if not 1 <= self.acquisition_flags_width <= 32:
            raise ValueError("acquisition flag block must hold one-byte GlobalIds")
        if self.pending_item_mask == 0:
            raise ValueError("pending item mask must be explicit and nonzero")
        for address, width in (
            (self.aot_base, self.aot_capacity * 12),
            (self.aot_bound_address, 4),
            (self.loaded_rdt_pointer_address, 4),
            (self.acquisition_flags_address, self.acquisition_flags_width),
            (self.pending_action_pointer_address, 4),
            (self.main_flags_address, 4),
        ):
            if (
                not self.ram_base
                <= address
                < address + width
                <= self.ram_base + self.ram_size
            ):
                raise ValueError("runtime room address is outside configured PS1 RAM")
        if len({item_type for item_type, _ in self.item_labels}) != len(
            self.item_labels
        ):
            raise ValueError("item type labels must be unique")
        if any(
            not 0 <= item_type < 0x54 or not label
            for item_type, label in self.item_labels
        ):
            raise ValueError("item labels need supported types and nonempty text")


@dataclass(frozen=True)
class RuntimeRoomItem:
    aot_id: int
    item_type: int
    amount: int
    label: str
    global_id: int
    state: RuntimeItemState
    kind: RuntimeItemKind
    source_address: int
    source_opcode: int


@dataclass(frozen=True)
class RuntimeRoomItems:
    ok: bool
    items: tuple[RuntimeRoomItem, ...] = ()
    list_complete: bool = False
    coverage_reason: str = ""
    active_doors: tuple[tuple[int, bytes], ...] = ()
    disabled_doors: tuple[tuple[int, bytes], ...] = ()
    error: str = ""
    retry: bool = False
    memory_markers: tuple[tuple[int, bytes], ...] = ()


def observe_room_items(
    layout: RuntimeRoomLayout,
    room: RoomId,
    read_memory: Callable[[int, int], MemoryResult],
) -> RuntimeRoomItems:
    """Classify the current registered collectibles with a coherent snapshot.

    Completeness is about currently instantiated room interactions. Dormant
    objects can become available after a story/event change and are reread then.
    Files are not normal collectibles under the project's completion definition.
    The caller must check game identity and room identity around this operation.
    """
    values: list[bytes] = []
    fields = (
        ("AOT bound", layout.aot_bound_address, 4),
        ("loaded room", layout.loaded_rdt_pointer_address, 4),
        (
            "item flags",
            layout.acquisition_flags_address,
            layout.acquisition_flags_width,
        ),
        ("pending interaction", layout.pending_action_pointer_address, 4),
        ("interaction state", layout.main_flags_address, 4),
    )
    for label, address, width in fields:
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            detail = result.error if not result.ok else "short read"
            return RuntimeRoomItems(ok=False, error=f"{label}: {detail}")
        values.append(result.data)
    bound, rdt, flags, pending, main = values
    bound_address = int.from_bytes(bound, "little")
    rdt_address = int.from_bytes(rdt, "little")
    last_slot, remainder = divmod(bound_address - layout.aot_base, 12)
    if remainder or not 0 <= last_slot < layout.aot_capacity:
        return RuntimeRoomItems(
            ok=False, error="AOT bound is outside the registered room range"
        )
    if (
        not layout.ram_base
        <= rdt_address
        < rdt_address + 0x70
        <= layout.ram_base + layout.ram_size
    ):
        return RuntimeRoomItems(
            ok=False, error="loaded room pointer is outside PS1 RAM"
        )
    header = read_memory(rdt_address + 0x60, 16)
    if not header.ok or len(header.data) != 16:
        detail = header.error if not header.ok else "short read"
        return RuntimeRoomItems(ok=False, error=f"room script ranges: {detail}")
    init_start, main_start, event_start, event_end = struct.unpack("<4I", header.data)
    if (
        not rdt_address + 0x94
        <= init_start
        <= main_start
        <= event_start
        <= event_end
        <= layout.ram_base + layout.ram_size
    ):
        return RuntimeRoomItems(
            ok=False, error="loaded room script pointers are not ordered PS1 RAM ranges"
        )
    aot_width = (last_slot + 1) * 12
    records = read_memory(layout.aot_base, aot_width)
    if not records.ok or len(records.data) != aot_width:
        detail = records.error if not records.ok else "short read"
        return RuntimeRoomItems(ok=False, error=f"room interactions: {detail}")
    labels = dict(layout.item_labels)
    pending_address = int.from_bytes(pending, "little")
    pending_item = bool(int.from_bytes(main, "little") & layout.pending_item_mask)
    if pending_item and not (
        layout.aot_base <= pending_address <= bound_address
        and (pending_address - layout.aot_base) % 12 == 0
    ):
        return RuntimeRoomItems(
            ok=False,
            error="pending pickup does not reference a registered room interaction",
        )
    items: list[RuntimeRoomItem] = []
    doors: list[tuple[int, bytes]] = []
    disabled_doors: list[tuple[int, bytes]] = []
    for slot in range(last_slot + 1):
        record = records.data[slot * 12 : (slot + 1) * 12]
        handler, mode, parameter, model, gid, pointer = struct.unpack("<BBHHHI", record)
        if handler > 17:
            return RuntimeRoomItems(
                ok=False, error=f"interaction {slot}: unsupported handler {handler}"
            )
        selected_pending = (
            pending_item and pending_address == layout.aot_base + slot * 12
        )
        source_address = pointer - 2
        if not init_start <= source_address < source_address + 2 <= event_end:
            if handler == 0 and not selected_pending:
                # Reset only clears handler bytes, so dormant slots may retain a prior room pointer.
                continue
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: source descriptor is outside current room scripts",
            )
        source_width = min(26, event_end - source_address)
        source = read_memory(source_address, source_width)
        if not source.ok or len(source.data) != source_width:
            detail = source.error if not source.ok else "short read"
            return RuntimeRoomItems(
                ok=False, error=f"interaction {slot} source: {detail}"
            )
        raw = source.data
        if (
            raw[0] not in (0x0C, 0x0D, 0x18)
            or (raw[1] & 0x7F if raw[0] == 0x18 else raw[1]) != slot
        ):
            if handler == 0 and not selected_pending:
                continue
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: source opcode or slot ID does not match",
            )
        required_width = 18 if raw[0] == 0x0D else 26
        if len(raw) < required_width:
            if handler == 0 and not selected_pending:
                continue
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: source descriptor is truncated",
            )
        if handler == 1 and raw[0] != 0x0C:
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: door handler has an unsupported source descriptor",
            )
        if handler == 13:
            # This handler opens the file screen; reading documents does not block room completion.
            continue
        if raw[0] == 0x0C and handler == 0 and not selected_pending:
            # A validated door pointer survives a scripted handler disable.
            # Preserve the wall marker and show that this passage is unavailable.
            disabled_doors.append((slot, raw[:25] + bytes((mode,))))
            continue
        if handler not in (0, 1, 3, 4, 15) and not selected_pending:
            continue
        if handler in (0, 3) and not selected_pending and raw[0] != 0x18:
            # Generic AOT records have no copied item identity that can distinguish dormant data from stale data.
            continue
        if not source_address + 26 <= event_end:
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: pickup or door descriptor is truncated",
            )
        if handler == 1:
            # Handler setters update the registry mode without rewriting its source.
            doors.append((slot, raw[:25] + bytes((mode,))))
            continue
        if raw[0] not in (0x0D, 0x18):
            if handler == 0 and not selected_pending:
                continue
            return RuntimeRoomItems(
                ok=False, error=f"interaction {slot}: pickup has no item descriptor"
            )
        # Only a full item initializer stores these copied fields. Generic AOT zeros can be stale.
        if (
            handler in (0, 3)
            and not selected_pending
            and (
                raw[0] != 0x18
                or mode != raw[23]
                or parameter != struct.unpack_from("<H", raw, 24)[0]
                or model != raw[12]
                or gid != raw[22]
            )
        ):
            continue
        # Award handlers read these offsets even for a generic 18-byte 0x0D creator.
        # This mirrors the later engine read, not the creator's command boundary.
        item_type, amount, global_id = raw[10], raw[11], raw[22]
        if item_type == 0 or item_type >= 0x54:
            if handler in (4, 15) or selected_pending:
                return RuntimeRoomItems(
                    ok=False,
                    error=f"interaction {slot}: unsupported active item type 0x{item_type:02X}",
                )
            continue
        if item_type == 0x4D:
            if handler not in (4, 15) and not selected_pending:
                continue
            # Radio ownership uses scenario-bank bit 127, bypassing the normal acquisition flag clear.
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: Radio acquisition needs its separate scenario flag",
            )
        if handler == 15 and not 0x4E <= item_type <= 0x53:
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: map handler has a non-map item type",
            )
        if handler == 4 and item_type >= 0x4E:
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: ordinary pickup handler has a map type",
            )
        # The engine indexes MSB-first bits in little-endian 32-bit words, not a linear byte bitfield.
        byte_index = 4 * (global_id // 32) + 3 - (global_id % 32) // 8
        if byte_index >= len(flags):
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: item GlobalId is outside the flag block",
            )
        remaining = bool(flags[byte_index] & (0x80 >> (global_id % 8)))
        if not remaining:
            state = RuntimeItemState.Taken
        elif handler in (4, 15) or selected_pending:
            # Zero geometry can represent a puzzle/event pickup: the award still reads this registered descriptor.
            state = RuntimeItemState.Available
        else:
            state = RuntimeItemState.Unavailable
        items.append(
            RuntimeRoomItem(
                aot_id=slot,
                item_type=item_type,
                amount=amount,
                label=labels.get(item_type, ""),
                global_id=global_id,
                state=state,
                kind=RuntimeItemKind.Map
                if item_type >= 0x4E
                else RuntimeItemKind.Inventory,
                source_address=source_address,
                source_opcode=raw[0],
            )
        )
    # A pickup or script update can happen between reads; never publish counts from two different states.
    for (label, address, width), expected in zip(fields, values, strict=True):
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            detail = result.error if not result.ok else "short read"
            return RuntimeRoomItems(ok=False, error=f"{label}: {detail}")
        if label == "interaction state":
            unchanged = (
                int.from_bytes(result.data, "little") & layout.pending_item_mask
            ) == (int.from_bytes(expected, "little") & layout.pending_item_mask)
        elif label == "pending interaction" and not pending_item:
            # The shared interaction pointer also changes for doors/messages that are not pending pickups.
            unchanged = True
        else:
            unchanged = result.data == expected
        if not unchanged:
            return RuntimeRoomItems(
                ok=False, error="room item state changed during read", retry=True
            )
    final_records = read_memory(layout.aot_base, aot_width)
    if not final_records.ok or len(final_records.data) != aot_width:
        detail = final_records.error if not final_records.ok else "short read"
        return RuntimeRoomItems(ok=False, error=f"room interactions: {detail}")
    if final_records.data != records.data:
        return RuntimeRoomItems(
            ok=False, error="room interactions changed during read", retry=True
        )
    final_header = read_memory(rdt_address + 0x60, 16)
    if not final_header.ok or len(final_header.data) != 16:
        detail = final_header.error if not final_header.ok else "short read"
        return RuntimeRoomItems(ok=False, error=f"room script ranges: {detail}")
    if final_header.data != header.data:
        return RuntimeRoomItems(
            ok=False, error="room script ranges changed during read", retry=True
        )
    return RuntimeRoomItems(
        ok=True,
        items=tuple(items),
        list_complete=True,
        coverage_reason=f"{room}: registered item, map, and pending award descriptors classified",
        active_doors=tuple(doors),
        disabled_doors=tuple(disabled_doors),
        memory_markers=(
            (layout.aot_bound_address, values[0]),
            (layout.aot_base, records.data),
        ),
    )
