"""Coherent bounded Leon A observations. RE2-LIVE-001, RE2-SCD-001.

Collection proofs establish required items independently of activation. A
missing live interaction alone never proves scenario absence or item presence.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Callable

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re2.re2_profile import Re2Profile
from games.runtime_identity import MemoryResult
from tracker.exploration_state import DoorDetail, ItemDetail, Tracker
from tracker.polling import PollResult, PollStatus
from ui.debug_view import render


def poll_re2(
    profile: Re2Profile,
    tracker: Tracker,
    read_memory: Callable[[int, int], MemoryResult],
) -> PollResult:
    identity = profile.verify_runtime(read_memory)
    if not identity.ok:
        return PollResult(PollStatus.ReadFailure, identity.error)
    if not identity.value:
        return PollResult(
            PollStatus.WrongGame,
            f"running game does not match profile {profile.profile_id}",
        )
    if any(key not in profile.rooms for key in tracker.rooms):
        return PollResult(
            PollStatus.ReadFailure,
            "Exploration history contains an unknown RE2 room. Choose another history file or start a new playthrough.",
        )
    layout = profile.runtime_layout
    markers: dict[tuple[int, int], bytes] = {}

    class ReadFailure(Exception):
        pass

    def read(address: int, width: int) -> bytes:
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            raise ReadFailure(
                f"RE2 state read failed at {address:#x}: {result.error or 'short reply'}"
            )
        markers[address, width] = result.data
        return result.data

    try:
        # Bind the initial pose block to the same room used for interpretation,
        # even if a whole transition finishes between the two block reads.
        pose_room = tuple(
            int.from_bytes(read(address, 2), "little")
            for address in (profile.stage_address, profile.room_address)
        )
        blocks = []
        for kind in ("player", "save"):
            address = int(layout[f"{kind}_block_address_ps1"], 0)
            width = layout[f"{kind}_block_width"]
            blocks.append((address, read(address, width)))
            # Timers and animation change during gameplay. Compare only the
            # bytes consumed by interpretation, not these entire read blocks.
            del markers[address, width]

        def value(address: int, width: int) -> int:
            for base, data in blocks:
                offset = address - base
                if 0 <= offset <= len(data) - width:
                    packet = data[offset : offset + width]
                    markers[address, width] = packet
                    return int.from_bytes(packet, "little")
            return int.from_bytes(read(address, width), "little")

        system = value(int(layout["system_flags_address_ps1"], 0), 4)
        status = value(int(layout["status_flags_address_ps1"], 0), 4)
        active = value(int(layout["player_active_address_ps1"], 0), 4)
        if (
            not system & layout["gameplay_mask"]
            or system & (layout["demo_mask"] | layout["game_over_mask"])
            or not active & 1
        ):
            return PollResult(
                PollStatus.NonGameplay, "Title, demo or game over; visits not recorded"
            )
        if status & layout["scenario_mask"] != layout["scenario_value"]:
            return PollResult(PollStatus.WrongGame, "This profile requires Leon A")
        if system & layout["transition_mask"]:
            return PollResult(PollStatus.Retry, "Changing rooms...")
        rid = RoomId(value(profile.stage_address, 2), value(profile.room_address, 2))
        if (rid.stage, rid.room) != pose_room:
            return PollResult(PollStatus.Retry, "Player room changed during pose read")
        key = str(rid)
        if key not in profile.rooms:
            return PollResult(PollStatus.Retry, "Room identity is not yet available")
        room = profile.rooms[key]
        camera = value(profile.camera_address, 2)
        if camera >= room["cameras"]:
            return PollResult(PollStatus.Retry, "Room camera changed during loading")
        base = value(int(layout["loaded_rdt_address_ps1"], 0), 4)
        if not 0x80000000 <= base <= 0x80200000 - room["size"]:
            return PollResult(PollStatus.Retry, "Room source is still loading")
        sections = struct.unpack("<23I", read(base + 8, 92))
        # The loader relocates every nonzero section pointer in place. Camera
        # positions alone are shared by several different RE2 room sources.
        if [pointer - base if pointer else 0 for pointer in sections] != room[
            "section_offsets"
        ]:
            return PollResult(
                PollStatus.Retry, "Loaded room section layout does not match its source"
            )
        for proof in room["proofs"]:
            packet = read(base + proof["offset"], proof["width"])
            if hashlib.sha256(packet).hexdigest() != proof["sha256"]:
                return PollResult(
                    PollStatus.Retry, "Loaded room does not match its source"
                )
        floor = value(int(layout["floor_address_ps1"], 0), 1)
        yaw = value(int(layout["player_facing_address_ps1"], 0), 2)
        position_address = int(layout["player_position_address_ps1"], 0)
        x, _, z = struct.unpack(
            "<3i", value(position_address, 12).to_bytes(12, "little")
        )
        # Position and facing share the initial player block. Requiring them to
        # remain stationary through the final checks would reject normal motion.
        del markers[int(layout["player_facing_address_ps1"], 0), 2]
        del markers[position_address, 12]
        area, region = profile.map_layout.select(key, floor, value)
        position = profile.map_layout.project(area, region, x, z)

        def flag(bank: int, bit: int) -> bool:
            address, width = profile.flag_banks[bank]
            assert 0 <= bit < width * 8, "flag index must fit the pinned bank"
            word = value(address + bit // 32 * 4, 4)
            return bool(word & (0x80000000 >> (bit % 32)))

        registry = read(
            int(layout["aot_table_address_ps1"], 0), layout["aot_capacity"] * 4
        )
        live_items, live_doors = {}, {}
        unresolved_registry = False
        for slot in range(layout["aot_capacity"]):
            pointer = int.from_bytes(registry[slot * 4 : slot * 4 + 4], "little")
            if not pointer:
                continue
            offset = pointer - base - 2
            if not 0 <= offset <= room["size"] - 4:
                return PollResult(
                    PollStatus.Retry, "Room interaction source is unresolved"
                )
            prefix = read(pointer, 2)
            kind = prefix[0]
            if kind not in (0, 1, 2):
                continue
            definitions = (
                room["items"]
                if kind == 2
                else room["doors"]
                if kind == 1
                else room["items"] + room["doors"]
            )
            candidates = [
                row
                for row in definitions
                if row["offset"] == offset and row["slot"] == slot
            ]
            if len(candidates) != 1:
                # Aot_reset can repurpose another interaction. Keep that gap
                # explicit instead of assigning it a nearby source candidate.
                if kind != 0:
                    unresolved_registry = True
                continue
            definition = candidates[0]
            if kind and bool(prefix[1] & 0x80) != definition["four_point"]:
                unresolved_registry = True
                continue
            operand = 20 if definition["four_point"] else 12
            if pointer + operand + (18 if kind == 1 else 6) > base + room["size"]:
                return PollResult(
                    PollStatus.Retry, "Room interaction extends beyond its source"
                )
            packet = read(pointer, operand + (18 if kind == 1 else 6))
            if kind == 2:
                item_type, amount, gid = (
                    int.from_bytes(packet[index : index + 2], "little")
                    for index in range(operand, operand + 6, 2)
                )
                if (item_type, gid) != (definition["type"], definition["global_id"]):
                    unresolved_registry = True
                    continue
                live_items[offset] = ("available", amount)
            elif kind == 0 and definition in room["doors"]:
                live_doors[offset] = {**definition, "inactive": True}
            elif kind == 1:
                # Mutable descriptor payload controls current targets and locks.
                live_doors[offset] = {
                    **definition,
                    "stage": packet[operand + 8],
                    "room": packet[operand + 9],
                    "lock_id": packet[operand + 15],
                    "lock_type": packet[operand + 16],
                }

        evaluations, doors = [], []
        for visited in sorted(set(tracker.rooms) | {key}):
            source = profile.rooms[visited]
            source_id = RoomId(source["stage"], source["room"])
            bank = (
                layout["item_bank_early"]
                if source["stage"] < layout["item_bank_stage_boundary"]
                else layout["item_bank_late"]
            )
            grouped = {}
            for item in source["items"]:
                if item["type"] >= layout["file_type_min"]:
                    continue
                grouped.setdefault(item["global_id"], []).append(item)
            details = []
            for gid, variants in grouped.items():
                available = [
                    item
                    for item in variants
                    if visited == key
                    and item["offset"] in live_items
                    and live_items[item["offset"]][0] == "available"
                ]
                taken = flag(bank, gid)
                if taken and available:
                    return PollResult(
                        PollStatus.Retry, "Pickup changed during room read"
                    )
                types = {item["type"] for item in available or variants}
                item_type = next(iter(types)) if len(types) == 1 else None
                label = profile.names["items"].get(str(item_type), "Collectible")
                if item_type is None:
                    state = "unknown"
                elif taken:
                    state = "taken"
                elif available:
                    state = "available"
                elif gid in source["collection_item_ids"]:
                    state = "uncollected"
                else:
                    state = "unknown"
                amounts = (
                    {live_items[item["offset"]][1] for item in available}
                    if available
                    else {amount for item in variants for amount in item["amounts"]}
                )
                quantity = (
                    next(iter(amounts))
                    if len(amounts) == 1
                    else ItemQuantityState.Unreconstructed
                )
                details.append(ItemDetail(label, state, quantity))
            has_awards = any(
                command["item_type"] < layout["file_type_min"]
                for command in source["event_awards"]
            )
            complete = (
                source["candidate_list_complete"]
                and not has_awards
                and not (visited == key and unresolved_registry)
            )
            # Unbound event deliveries can add collectibles. The current
            # implementation deliberately withholds clearance in those rooms.
            if has_awards:
                details.append(
                    ItemDetail(
                        "Event collectible",
                        "unknown",
                        ItemQuantityState.Unreconstructed,
                    )
                )
            evaluations.append((source_id, tuple(details), complete))
            for definition in source["doors"]:
                observed = (
                    live_doors.get(definition["offset"]) if visited == key else None
                )
                lock = observed or definition
                key_type = lock["lock_type"]
                key_label = (
                    profile.names["items"].get(str(key_type), "")
                    if key_type not in (0, 0xFE, 0xFF)
                    else ""
                )
                unlocked = bool(lock["lock_id"] & 0x80) and flag(
                    layout["key_bank"], lock["lock_id"] & 0x3F
                )
                if unlocked:
                    key_label = ""
                if observed is None:
                    # Unlock knowledge survives leaving a room. Its current
                    # activation can still depend on unresolved room events.
                    state = "UNCHECKED"
                    label = (
                        "Unlocked; access unconfirmed"
                        if unlocked
                        else "Door conditions unresolved"
                    )
                elif observed.get("inactive", False):
                    state = "BLOCKED"
                    label = (
                        "Unlocked; door inactive" if unlocked else "Door is inactive"
                    )
                elif unlocked:
                    state, label = "OPEN", "Unlocked"
                elif not lock["lock_id"] & 0x80:
                    state, label = "OPEN", "Open"
                elif key_type == 0xFE:
                    state, label = "UNLOCKABLE", "Unlock from this side"
                else:
                    state, label = "LOCKED", key_label or "Locked"
                doors.append(
                    DoorDetail(
                        source_id,
                        RoomId(lock["stage"], lock["room"]),
                        state,
                        label,
                        key_label,
                        f"{visited}:{definition['offset']}",
                    )
                )

        # Publish only after all consumed state and source pointers agree.
        # Savestate loads must reverse flags before any cached room is shown.
        masks = {
            (int(layout["system_flags_address_ps1"], 0), 4): layout["gameplay_mask"]
            | layout["demo_mask"]
            | layout["game_over_mask"]
            | layout["transition_mask"],
            (int(layout["status_flags_address_ps1"], 0), 4): layout["scenario_mask"],
            (int(layout["player_active_address_ps1"], 0), 4): 1,
        }
        for (address, width), packet in markers.items():
            result = read_memory(address, width)
            if not result.ok or len(result.data) != width:
                raise ReadFailure(
                    f"RE2 coherence read failed: {result.error or 'short reply'}"
                )
            # Other system/player bits can change during ordinary animation.
            # Only the bits used to admit this snapshot need to remain equal.
            mask = masks.get((address, width), (1 << (8 * width)) - 1)
            if (
                int.from_bytes(result.data, "little") ^ int.from_bytes(packet, "little")
            ) & mask:
                return PollResult(PollStatus.Retry, "Game state changed during read")
    except ReadFailure as error:
        return PollResult(PollStatus.ReadFailure, str(error))
    except ValueError as error:
        return PollResult(PollStatus.Retry, str(error))
    tracker.mark_current(rid)
    tracker.player_position = position
    tracker.player_heading = (
        layout["heading_offset_degrees"]
        + layout["heading_direction"] * (yaw & 0xFFF) * 360 / 4096
    ) % 360
    tracker.current_region = f"{area}:{region}"
    tracker.map_error = (
        "No floor outline is established for this room." if area == "unmapped" else ""
    )
    if area != "unmapped":
        tracker.region_visits[tracker.current_region] = key
    for source_id, details, complete in evaluations:
        remaining = any(item.state in ("available", "uncollected") for item in details)
        unknown = any(item.state == "unknown" for item in details)
        # A source-established reward remains required while its interaction
        # is inactive, including after departure and earlier savestate loads.
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
        record.doors_complete = not (
            str(source_id) == key and unresolved_registry
        ) and all(
            door.state != "UNCHECKED" for door in doors if door.source == source_id
        )
        record.door_reason = (
            "Door conditions are unresolved." if not record.doors_complete else ""
        )
    tracker.doors = tuple(doors)
    return PollResult(
        PollStatus.Display, render(rid, tracker.rooms[key], profile.profile_id)
    )
