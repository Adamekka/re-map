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
from games.item_quantity import ItemQuantityState
from games.re1.acquisition_state import AcquisitionLayout, FixedAcquisitionRule


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
    acquisition: AcquisitionLayout

    def __post_init__(self) -> None:
        if (self.acquisition.flags_address, self.acquisition.flags_width) != (
            self.acquisition_flags_address,
            self.acquisition_flags_width,
        ):
            raise ValueError("acquisition rules disagree with the runtime flag block")
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
            *(
                (rule.address, 1)
                for rule in self.acquisition.rules
                if isinstance(rule, FixedAcquisitionRule)
            ),
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
    amount: int | ItemQuantityState
    label: str
    global_id: int
    state: RuntimeItemState
    kind: RuntimeItemKind
    source_address: int
    source_opcode: int

    def __post_init__(self) -> None:
        assert (
            type(self.amount) is int
            and 0 <= self.amount <= 255
            or self.amount is ItemQuantityState.Unreconstructed
        ), "RE1 quantity must be a byte or explicitly unreconstructed"


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
    non_collectible_slots: tuple[int, ...] = ()
    message_door_slots: tuple[int, ...] = ()
    scripted_doors: tuple[tuple[int, bytes, int], ...] = ()
    scripted_collectibles: tuple[tuple[RuntimeRoomItem, int, int], ...] = ()

    def __post_init__(self) -> None:
        assert len(set(self.non_collectible_slots)) == len(self.non_collectible_slots)
        assert all(
            type(slot) is int and 0 <= slot < 128 for slot in self.non_collectible_slots
        )
        assert self.ok or not self.non_collectible_slots
        assert not set(self.non_collectible_slots) & {
            item.aot_id for item in self.items
        }, "a live slot cannot be both collectible and noncollectible"
        assert len(set(self.message_door_slots)) == len(self.message_door_slots)
        assert all(
            type(slot) is int and 0 <= slot < 128 for slot in self.message_door_slots
        )
        assert self.ok or not self.message_door_slots
        assert set(self.message_door_slots) <= {
            slot for slot, _ in self.disabled_doors
        }, "message evidence requires its validated blocked door descriptor"
        assert not set(self.message_door_slots) & {
            slot for slot, _ in self.active_doors
        }, "a message door cannot also allow normal passage"
        assert self.ok or not self.scripted_doors
        scripted_slots = [slot for slot, _, _ in self.scripted_doors]
        assert len(set(scripted_slots)) == len(scripted_slots)
        assert all(
            type(slot) is int
            and 0 <= slot < 24
            and len(opcode) == 26
            and opcode[:2] == bytes((0x0C, slot))
            and type(entry) is int
            and 0 <= entry < 256
            for slot, opcode, entry in self.scripted_doors
        ), "scripted doors require a validated current door source and event index"
        assert not set(scripted_slots) & {
            slot for slot, _ in self.active_doors + self.disabled_doors
        }
        collectible_slots = [item.aot_id for item, _, _ in self.scripted_collectibles]
        assert self.ok or not self.scripted_collectibles
        assert len(set(collectible_slots)) == len(collectible_slots)
        assert not set(collectible_slots) & {item.aot_id for item in self.items}
        assert all(
            0 <= item.aot_id < 24
            and item.source_opcode == 0x18
            and item.source_address > 0
            and type(record) is int
            and 0 <= record < 256
            and type(entry) is int
            and 0 <= entry < 256
            for item, record, entry in self.scripted_collectibles
        ), "scripted collectibles require a validated item source and registered target"


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
    ) + tuple(
        ("separate acquisition flag", address, 1)
        for address in sorted(
            {
                rule.address
                for rule in layout.acquisition.rules
                if isinstance(rule, FixedAcquisitionRule)
                and not layout.acquisition_flags_address
                <= rule.address
                < layout.acquisition_flags_address + layout.acquisition_flags_width
            }
        )
    )
    for label, address, width in fields:
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            detail = result.error if not result.ok else "short read"
            return RuntimeRoomItems(ok=False, error=f"{label}: {detail}")
        values.append(result.data)
    bound, rdt, flags, pending, main = values[:5]
    extra_flags = {
        address: value[0]
        for (_, address, _), value in zip(fields[5:], values[5:], strict=True)
    }
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
    non_collectible_slots: list[int] = []
    message_door_slots: list[int] = []
    scripted_doors: list[tuple[int, bytes, int]] = []
    scripted_collectibles: list[tuple[RuntimeRoomItem, int, int]] = []
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
        if handler == 9 and raw[0] == 0x0C and not selected_pending:
            # A validated descriptor supplies geometry, not access. The
            # source-bound event proof must resolve its registered target.
            scripted_doors.append((slot, raw[:25] + bytes((mode,)), model & 255))
            continue
        if handler in (8, 13, 16) and not selected_pending:
            # RE1-COVER-002/RE1-CLEAR-001: storage, documents and saving do
            # not award room items. Retain validated live evidence because
            # source history can still consider an older pickup handler here.
            # A forced pending award uses its descriptor despite this handler.
            non_collectible_slots.append(slot)
            continue
        if raw[0] == 0x0C and handler in (0, 2) and not selected_pending:
            # RE1-DOORS-003: a retained door source supplies its wall marker,
            # but a disabled/message handler cannot request normal passage.
            # A pending forced award still needs the descriptor checks below.
            disabled_doors.append((slot, raw[:25] + bytes((mode,))))
            if handler == 2:
                message_door_slots.append(slot)
            continue
        if (
            handler not in (0, 1, 3, 4, 15)
            and not (handler == 9 and raw[0] == 0x18)
            and not selected_pending
        ):
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
        try:
            acquisition_flag = layout.acquisition.flag(item_type, global_id)
        except ValueError as error:
            return RuntimeRoomItems(
                ok=False,
                error=f"interaction {slot}: {error}",
            )
        remaining = not layout.acquisition.collected(
            acquisition_flag, flags, extra_flags
        )
        if not remaining:
            state = RuntimeItemState.Taken
        elif handler in (4, 15) or selected_pending:
            # Zero geometry can represent a puzzle/event pickup: the award still reads this registered descriptor.
            state = RuntimeItemState.Available
        else:
            state = RuntimeItemState.Unavailable
        item = RuntimeRoomItem(
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
        if handler == 9 and not selected_pending:
            # Setters replace registry parameters, but the retained source
            # supplies item identity. Its event route still needs a source proof.
            scripted_collectibles.append((item, parameter & 255, model & 255))
        else:
            items.append(item)
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
            (layout.main_flags_address, values[4]),
        )
        + tuple(
            (address, value)
            for (_, address, _), value in zip(fields[5:], values[5:], strict=True)
        )
        # The selected record matters only during a pending pickup. Ordinary
        # doors, storage and saving also change this shared pointer.
        + (
            ((layout.pending_action_pointer_address, values[3]),)
            if pending_item
            else ()
        ),
        non_collectible_slots=tuple(non_collectible_slots),
        message_door_slots=tuple(message_door_slots),
        scripted_doors=tuple(scripted_doors),
        scripted_collectibles=tuple(scripted_collectibles),
    )
