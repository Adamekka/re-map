"""Live RE3 Hard tracking. RE3-EVAL-001.

The guarded current-room reader admits ordinary Hard gameplay and binds the
loaded room to its owned source. Every visited room's own scripts are then
evaluated with fresh flags and variables through the shared interpreter, as
for RE2. The current room's live interaction registry takes precedence for
items and doors it shows now.
"""

from __future__ import annotations

import json
import struct
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from games.bit_flags import msb_flag_location
from games.door_access_state import door_access
from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState, parse_unit_count_item_types
from games.player_heading import heading_degrees
from games.re2.map_layout import Re2MapLayout, Re2MapProjection
from games.re3 import EXECUTABLE_SHA256
from games.re3.live_reader import CurrentRoomFailure, read_current_room
from games.re3.script_doors import parse_door
from games.re3.script_model import compile_room_scripts
from games.re3.source_witnesses import RoomSource, SourceCatalog, bind_source_catalog
from games.runtime_identity import MemoryResult, RuntimeSignature
from games.scd_entry import EntryConfig, entry_state, parse_entry_config, pickup_ids
from games.scd_state import (
    RoomScriptState,
    ScriptStateCache,
    Support,
)
from tracker.exploration_state import DoorDetail, DoorUnlockState, ItemDetail, Tracker
from tracker.polling import PollResult, PollStatus
from ui.debug_view import render

# Item and door interaction kinds in the native registry.
_KIND_DOOR = 1
# Handler 0x80051CB0 changes room as soon as the player touches this kind,
# with no action button or lock check.
_KIND_WALK_THROUGH = 13
_KIND_ITEM = 2


@dataclass(frozen=True)
class Re3Target:
    scenario: str
    history_filename: str


# One supported revision and difficulty, with its own exploration history.
RE3_TARGET = Re3Target("jill-hard", "re3-jill-hard-slus00923.json")


@dataclass(frozen=True)
class Re3Profile:
    profile_id: str
    revision: str
    executable_identity: str
    target: Re3Target
    runtime_signature: RuntimeSignature
    catalog: SourceCatalog
    layout: dict
    # Flag bank -> PS1 address of its first word (native table 0x8009E3F8).
    flag_banks: dict[int, int]
    # Room key -> source path, stage, room, program, doors and item IDs.
    rooms: dict[str, dict]
    names: dict
    map_layout: Re2MapLayout
    evaluation: EntryConfig
    script_cache: ScriptStateCache = field(
        default_factory=ScriptStateCache, compare=False
    )

    @staticmethod
    def load(
        path: Path, executable: bytes, sources: tuple[RoomSource, ...]
    ) -> Re3Profile:
        raw = json.loads(path.read_text())
        if raw.get("executable_identity") != f"SLUS_009.23 SHA256 {EXECUTABLE_SHA256}":
            raise ValueError("executable_identity must match the pinned RE3 revision")
        if raw["profile_id"] != "re3_jill_hard_slus00923":
            raise ValueError("RE3 profile targets another revision")
        catalog = bind_source_catalog(executable, sources)
        if not isinstance(catalog, SourceCatalog):
            raise ValueError(f"Owned RE3 disc rejected: {catalog.detail}")
        layout = raw["runtime_layout"]
        layout["unit_count_item_types"] = parse_unit_count_item_types(
            layout.get("unit_count_item_types")
        )
        blocks = [(int(address, 0), width) for address, width in layout["state_blocks"]]

        def in_blocks(address: int, width: int) -> bool:
            return any(
                base <= address and address + width <= base + size
                for base, size in blocks
            )

        if layout["aot_capacity"] != 32 or not in_blocks(
            int(layout["aot_table_address_ps1"], 0), 4 * layout["aot_capacity"]
        ):
            raise ValueError("RE3 interaction registry must be 32 slots in the reads")
        evaluation = parse_entry_config(raw["script_evaluation"], frozenset())
        if not in_blocks(evaluation.variables_address, 2 * evaluation.variable_count):
            raise ValueError("RE3 script variables must fit the state reads")
        if not in_blocks(int(layout["inventory_pointer_address_ps1"], 0), 4):
            raise ValueError("RE3 inventory pointer must fit the state reads")
        rooms = {}
        for bound in catalog.sources:
            source = bound.source
            stage, number = source.stage_digit - 1, source.room_number
            program = compile_room_scripts(source.rdt)
            rooms[f"{stage:02d}-{number:02x}"] = {
                "id": f"{stage:02d}-{number:02x}",
                "source": source.path,
                "stage": stage,
                "room": number,
                "program": program,
                "doors": _door_definitions(source.rdt, program),
                "item_ids": pickup_ids(program, layout["file_type_min"]),
            }
        map_layout = Re2MapLayout.load(
            path.parent / raw["floor_plans_path"],
            raw["profile_id"],
            raw["executable_identity"],
            rooms,
            Re2MapProjection(**raw["map_projection"]),
        )
        if any(
            not in_blocks(address, (mask.bit_length() + 7) // 8)
            for rows in map_layout.locations.values()
            for row in rows
            for address, mask, _, _ in row["conditions"]
        ):
            raise ValueError("RE3 map conditions must fit the state reads")
        return Re3Profile(
            raw["profile_id"],
            raw["revision"],
            raw["executable_identity"],
            RE3_TARGET,
            catalog.runtime_signature,
            catalog,
            layout,
            {
                int(bank): int(address, 0)
                for bank, address in raw["flag_bank_addresses_ps1"].items()
            },
            rooms,
            json.loads((path.parent / raw["names_path"]).read_text()),
            map_layout,
            evaluation,
        )


def _door_definitions(rdt: bytes, program: dict[str, list[list]]) -> list[dict]:
    doors = {}
    for rows in program.values():
        for offset, following, _, slot, _ in (row for row in rows if row[2] == "door"):
            door = parse_door(rdt, offset, -1)
            walk_through = rdt[offset + 2] == _KIND_WALK_THROUGH
            doors[offset] = {
                "offset": offset,
                "slot": slot,
                "activation_floor": door.floor,
                "stage": door.target_stage,
                "room": door.target_room,
                "floor": door.target_floor,
                "kind": _KIND_WALK_THROUGH if walk_through else _KIND_DOOR,
                # A walk-through exit has no lock.
                "lock_id": 0 if walk_through else door.key_id,
                "lock_type": 0 if walk_through else door.key_type,
                "four_point": following - offset == 40,
                "center": list(door.center),
            }
    walk_through = {
        door["slot"] for door in doors.values() if door["kind"] == _KIND_WALK_THROUGH
    }
    if any(
        row[2] == "reset" and row[3] in walk_through
        for rows in program.values()
        for row in rows
    ):
        # The evaluator keeps a reset slot's door identity only for kind 1.
        raise ValueError("RE3 resets of walk-through exits are not modeled")
    return [doors[offset] for offset in sorted(doors)]


def live_door(definition: dict, kind: int, sat: int, data: bytes) -> dict | None:
    """Decode a current door slot that still points at its creator.

    SAT bit 7 selects the payload layout. A door whose bit disagrees with its
    creator stays unresolved (None); a slot a script replaced in place with
    another interaction kind is inactive.
    """
    door = kind == definition["kind"]
    if door and bool(sat & 0x80) != definition["four_point"]:
        return None
    operand = 20 if definition["four_point"] else 12
    walk_through = definition["kind"] == _KIND_WALK_THROUGH
    return {
        **definition,
        "enabled": door and bool(sat & 0x7F),
        "stage": data[operand + 8],
        "room": data[operand + 9],
        "lock_id": 0 if walk_through else data[operand + 15],
        "lock_type": 0 if walk_through else data[operand + 16],
    }


def poll_re3(
    profile: Re3Profile,
    tracker: Tracker,
    read_memory: Callable[[int, int], MemoryResult],
) -> PollResult:
    first = read_current_room(profile.catalog, read_memory)
    if isinstance(first, CurrentRoomFailure):
        return PollResult(first.status, first.detail)
    layout = profile.layout
    key = str(first.room_id)
    if key not in profile.rooms:
        return PollResult(
            PollStatus.UnsupportedRoom,
            "This room cannot be tracked yet. Visits were not recorded.",
        )
    if any(visited not in profile.rooms for visited in tracker.rooms):
        return PollResult(
            PollStatus.ReadFailure,
            "Exploration history contains an unknown RE3 room. Choose another history file or start a new playthrough.",
        )

    inventory_pointer = int(layout["inventory_pointer_address_ps1"], 0)
    # The slot count byte follows the four-byte slots.
    inventory_width = layout["inventory_count_offset"] + 1

    def read_blocks(inventory: int | None) -> list[tuple[int, bytes]] | PollResult:
        """Read the state blocks, then the inventory at the given base.

        The first read passes None to take the base from its own blocks.
        """
        result_blocks = []
        for address, width in layout["state_blocks"]:
            result = read_memory(int(address, 0), width)
            if not result.ok or len(result.data) != width:
                return PollResult(
                    PollStatus.ReadFailure,
                    f"RE3 state read failed at {address}: {result.error or 'short reply'}",
                )
            result_blocks.append((int(address, 0), result.data))
        if inventory is None:
            start, data = next(
                (start, data)
                for start, data in result_blocks
                if start <= inventory_pointer <= start + len(data) - 4
            )
            offset = inventory_pointer - start
            inventory = int.from_bytes(data[offset : offset + 4], "little")
        if not 0x80000000 <= inventory <= 0x80200000 - inventory_width:
            return PollResult(PollStatus.Retry, "Inventory is not yet readable")
        result = read_memory(inventory, inventory_width)
        if not result.ok or len(result.data) != inventory_width:
            return PollResult(
                PollStatus.ReadFailure,
                f"RE3 inventory read failed: {result.error or 'short reply'}",
            )
        result_blocks.append((inventory, result.data))
        return result_blocks

    blocks = read_blocks(None)
    if isinstance(blocks, PollResult):
        return blocks
    # Every value interpretation consumes, rechecked after all reads.
    consumed: dict[tuple[int, int], int] = {}

    def value(address: int, width: int) -> int | None:
        for base, data in blocks:
            if base <= address and address + width <= base + len(data):
                result = int.from_bytes(
                    data[address - base : address - base + width], "little"
                )
                consumed[address, width] = result
                return result
        return None

    def flag(bank: int, bit: int) -> bool | None:
        if bank not in profile.flag_banks:
            return None
        address, mask = msb_flag_location(profile.flag_banks[bank], bit)
        word = value(address, 4)
        return None if word is None else bool(word & mask)

    evaluation = profile.evaluation
    inventory_base = value(inventory_pointer, 4)

    def carries(item_type: int) -> bool | None:
        count = value(inventory_base + layout["inventory_count_offset"], 1)
        if 4 * count > layout["inventory_count_offset"]:
            # The search would run past the slots into the count byte.
            return None
        return any(
            value(inventory_base + 4 * slot, 1) == item_type for slot in range(count)
        )

    def acquisition_bank(room: dict) -> int:
        return (
            layout["item_bank_early"]
            if room["stage"] < layout["item_bank_stage_boundary"]
            else layout["item_bank_late"]
        )

    def script_state(room: dict) -> RoomScriptState:
        bank = acquisition_bank(room)
        return profile.script_cache.get(
            room["id"],
            room["program"],
            entry_state(
                evaluation,
                flag,
                lambda address: value(address, 2),
                carries,
                room["stage"],
                room["room"],
            ),
            evaluation.tasks,
            {gid: (bank, gid) for gid in room["item_ids"]},
            file_type_min=layout["file_type_min"],
        )

    # The current room's live registry shows what exists now.
    base = first.source_address
    live: dict[int, tuple[int, int, int, bytes]] = {}
    registry = int(layout["aot_table_address_ps1"], 0)
    size = len(
        profile.catalog.lookup(first.room_id.stage, first.room_id.room).source.rdt
    )
    for slot in range(layout["aot_capacity"]):
        pointer = value(registry + 4 * slot, 4)
        offset = pointer - base - 2
        if not pointer or not 0 <= offset <= size - 40:
            # Native interactions outside the room source, such as enemy or
            # system areas, are not room creators.
            continue
        # Item and door payloads follow a 12-byte header, or 20 bytes for
        # four-point geometry; read the largest door payload.
        result = read_memory(pointer, 38)
        if not result.ok or len(result.data) != 38:
            return PollResult(PollStatus.ReadFailure, "RE3 interaction read failed")
        live[slot] = (offset, result.data[0], result.data[1], result.data)

    names = profile.names.get("items", {})
    doors: list[DoorDetail] = []
    absent_doors: set[str] = set()
    evaluations = []
    for visited in sorted(set(tracker.rooms) | {key}):
        room = profile.rooms[visited]
        scripted = script_state(room)
        bank = acquisition_bank(room)
        details = []
        supported = scripted.support is Support.Supported
        identities_complete = True
        current = visited == key
        live_items = {}
        if current:
            for offset, kind, sat, data in live.values():
                if kind == _KIND_ITEM:
                    operand = 20 if sat & 0x80 else 12
                    item_type, amount, gid = struct.unpack_from("<3H", data, operand)
                    if item_type < layout["file_type_min"]:
                        live_items[gid] = (item_type, amount, bool(sat & 0x7F))
        for gid in sorted(room["item_ids"]):
            taken = flag(bank, gid)
            if taken is None:
                return PollResult(PollStatus.ReadFailure, "RE3 item flags are unread")
            identity = (
                live_items[gid][:2]
                if gid in live_items
                else scripted.item_identity.get(gid)
                if supported
                else None
            )
            if taken:
                state = "taken"
            elif current and gid in live_items and live_items[gid][2]:
                state = "available"
            elif not supported:
                state = "unknown"
            else:
                presence = scripted.item_presence.get(gid)
                if presence is False:
                    continue
                state = "uncollected" if presence else "unknown"
            if identity is None:
                # An unresolved identity keeps the list incomplete even when
                # the acquisition flag records collection.
                identities_complete = False
            details.append(
                ItemDetail(
                    names.get(str(identity[0]), "Collectible")
                    if identity is not None
                    else "Collectible",
                    state,
                    identity[1]
                    if identity is not None
                    else ItemQuantityState.Unreconstructed,
                    identity is not None
                    and identity[0] in layout["unit_count_item_types"],
                )
            )
        complete = supported and identities_complete
        evaluations.append(
            (RoomId(room["stage"], room["room"]), tuple(details), complete)
        )
        key_bank = layout["key_bank"]
        for definition in room["doors"]:
            observed = None
            if current:
                slot = live.get(definition["slot"])
                if slot is None or slot[0] != definition["offset"]:
                    # The slot is empty or holds another interaction.
                    absent_doors.add(f"{visited}:{definition['offset']}")
                    continue
                _, kind, sat, data = slot
                observed = live_door(definition, kind, sat, data)
            elif supported:
                verdict = scripted.doors.get(definition["offset"])
                if verdict is None:
                    # Fresh scripts run another creator for this slot, or none.
                    absent_doors.add(f"{visited}:{definition['offset']}")
                    continue
                if verdict.sat is not None:
                    observed = {
                        **definition,
                        "enabled": bool(verdict.sat & 0x7F) and not verdict.replaced,
                    }
            lock = observed or definition
            key_type = lock["lock_type"]
            unlock_state = DoorUnlockState.Unknown
            if lock["lock_id"] & 0x80:
                unlocked = flag(key_bank, lock["lock_id"] & 0x3F)
                if unlocked is not None:
                    unlock_state = (
                        DoorUnlockState.Unlocked if unlocked else DoorUnlockState.Locked
                    )
            key_label = (
                names.get(str(key_type), "")
                if key_type not in (0, 0xFE, 0xFF)
                and unlock_state is not DoorUnlockState.Unlocked
                else ""
            )
            if observed is None:
                state, label = "UNCHECKED", "Door conditions unresolved"
            else:
                state, label = door_access(
                    observed["enabled"],
                    unlock_state is DoorUnlockState.Unlocked,
                    lock["lock_id"],
                    key_type,
                    key_label,
                )
            doors.append(
                DoorDetail(
                    RoomId(room["stage"], room["room"]),
                    RoomId(lock["stage"], lock["room"]),
                    state,
                    label,
                    key_label,
                    f"{visited}:{definition['offset']}",
                    unlock_state=unlock_state,
                    interaction_id=f"{visited}:{definition['slot']}",
                )
            )

    rid = first.room_id

    def condition_value(address: int, width: int) -> int:
        result = value(address, width)
        # Map conditions name words inside the state blocks; the profile
        # loader checks this, so a miss is a programming error.
        assert result is not None, "map condition outside the RE3 state blocks"
        return result

    x, _, z = first.position
    try:
        area, region, origin = profile.map_layout.select_at(
            key, first.actor_floor & 0xFF, condition_value, x, z
        )
    except ValueError as error:
        return PollResult(PollStatus.Retry, str(error))
    # Publish only if every consumed value, interaction packet and the room
    # itself still agree, so a savestate load between reads cannot mix states.
    later = read_blocks(inventory_base)
    if isinstance(later, PollResult):
        return later
    for (address, width), expected in consumed.items():
        current = next(
            int.from_bytes(data[address - start : address - start + width], "little")
            for start, data in later
            if start <= address and address + width <= start + len(data)
        )
        if current != expected:
            return PollResult(PollStatus.Retry, "Game state changed during read")
    for offset, _, _, data in live.values():
        result = read_memory(base + offset + 2, len(data))
        if not result.ok or result.data != data:
            return PollResult(PollStatus.Retry, "Room interaction changed during read")
    final = read_current_room(profile.catalog, read_memory)
    if isinstance(final, CurrentRoomFailure):
        return PollResult(final.status, final.detail)
    if (final.room_id, final.source_address) != (first.room_id, first.source_address):
        return PollResult(PollStatus.Retry, "Changing rooms...")
    tracker.mark_current(rid)
    tracker.player_position = (
        profile.map_layout.project_from(origin, area, region, x, z)
        if area != "unmapped"
        else profile.map_layout.project(area, region, x, z)
    )
    tracker.player_heading = heading_degrees(
        first.facing, layout["heading_offset_degrees"], layout["heading_direction"]
    )
    tracker.current_region = f"{area}:{region}"
    tracker.map_error = (
        "No floor outline is established for this room." if area == "unmapped" else ""
    )
    if area != "unmapped":
        tracker.region_visits[tracker.current_region] = key
    for source_id, details, complete in evaluations:
        remaining = any(item.state in ("available", "uncollected") for item in details)
        unknown = any(item.state == "unknown" for item in details)
        tracker.update_room_items(
            source_id,
            len(details),
            sum(item.state == "taken" for item in details),
            complete,
            remaining,
            unknown,
        )
        record = tracker.rooms[str(source_id)]
        record.items = details
        record.reason = (
            "Item conditions are unresolved." if unknown or not complete else ""
        )
        record.doors_complete = all(
            door.state != "UNCHECKED" for door in doors if door.source == source_id
        )
        record.door_reason = (
            "Door conditions are unresolved." if not record.doors_complete else ""
        )
    tracker.doors = tuple(doors)
    tracker.absent_doors = frozenset(absent_doors)
    return PollResult(
        PollStatus.Display, render(rid, tracker.rooms[key], profile.profile_id)
    )
