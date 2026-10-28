"""Coherent bounded RE2 observations. RE2-LIVE-001, RE2-SCD-001.

Collection proofs establish required items independently of activation. A
missing live interaction alone never proves scenario absence or item presence.
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Callable

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re2.event_presence import presence_matches
from games.re2.re2_profile import Re2Profile
from games.re2.scenario_items import scenario_item_candidates
from games.re2.script_dispatch_items import ScriptItemDispatchConfig
from games.runtime_identity import MemoryResult
from tracker.exploration_state import DoorDetail, DoorUnlockState, ItemDetail, Tracker
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
    quantity_override = layout["pickup_quantity_override"]
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
            return PollResult(
                PollStatus.WrongGame, f"This profile requires {profile.target.label}"
            )
        if system & layout["transition_mask"]:
            return PollResult(PollStatus.Retry, "Changing rooms...")
        # RE2-COLLECT-011: generated exclusions assume this initialized mode.
        # Reject a mismatch before any absent-item proof can affect clearance.
        if system & layout["system_mode_mask"] != layout["system_mode_value"]:
            return PollResult(
                PollStatus.WrongGame,
                f"Unsupported RE2 game settings. Load a supported {profile.target.label} savestate.",
            )
        rid = RoomId(value(profile.stage_address, 2), value(profile.room_address, 2))
        if (rid.stage, rid.room) != pose_room:
            return PollResult(PollStatus.Retry, "Player room changed during pose read")
        key = str(rid)
        if key in profile.unsupported_sources:
            return PollResult(
                PollStatus.UnsupportedRoom,
                "This room cannot be tracked yet. Visits were not recorded.",
            )
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
        offsets = [pointer - base if pointer else 0 for pointer in sections]
        # RE2-SOURCE-001: native sound pointers can move together inside the
        # loaded source. Camera positions alone cannot identify every room.
        if offsets[2:] != room["section_offsets"][2:]:
            return PollResult(
                PollStatus.Retry, "Loaded room section layout does not match its source"
            )
        if offsets[:2] != room["section_offsets"][:2]:
            if (
                not room["sound_proofs"]
                or offsets[0] - room["section_offsets"][0]
                != offsets[1] - room["section_offsets"][1]
                or any(
                    sections[proof["section"]] % 4
                    or not 100
                    <= offsets[proof["section"]]
                    <= room["size"] - proof["width"]
                    for proof in room["sound_proofs"]
                )
            ):
                return PollResult(
                    PollStatus.Retry,
                    "Loaded room sound section layout does not match its source",
                )
            for proof in room["sound_proofs"]:
                packet = read(sections[proof["section"]], proof["width"])
                if hashlib.sha256(packet).hexdigest() != proof["sha256"]:
                    return PollResult(
                        PollStatus.Retry, "Loaded room sound does not match its source"
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
                # SAT also selects payload geometry. Losing that bit, even
                # with SAT zero, leaves a four-point payload untrusted rather
                # than proving a disabled creator or scenario absence.
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
                # A zero SAT byte skips native activation before geometry or
                # dispatch. Keep the creator for scenario checks, but do not
                # infer presence from it. RE2-COLLECT-022, RE2-CLAIRE-009.
                live_items[offset] = ("available" if packet[1] else "inactive", amount)
            elif kind == 0 and definition in room["doors"]:
                live_doors[offset] = {**definition, "inactive": True}
            elif kind == 1:
                # Mutable descriptor payload controls current targets and locks.
                live_doors[offset] = {
                    **definition,
                    # The shared activation dispatcher skips zero SAT before
                    # door handling, even when the fresh key flag is set.
                    "inactive": not packet[1],
                    "stage": packet[operand + 8],
                    "room": packet[operand + 9],
                    "lock_id": packet[operand + 15],
                    "lock_type": packet[operand + 16],
                }

        if isinstance(profile.script_item_dispatch, ScriptItemDispatchConfig):
            relations = room["script_item_dispatch_relations"]
            if (
                relations
                and value(profile.script_item_dispatch.main_table_address, 4)
                == sections[17]
            ):
                for relation in relations:
                    item_offset = relation["item_offset"]
                    if item_offset not in live_items:
                        continue
                    target = relation["target_slot"] * 4
                    if (
                        int.from_bytes(registry[target : target + 4], "little")
                        != base + item_offset + 2
                    ):
                        continue
                    callback = relation["callback_slot"] * 4
                    pointer = base + relation["callback_offset"] + 2
                    if (
                        int.from_bytes(registry[callback : callback + 4], "little")
                        != pointer
                    ):
                        continue
                    descriptor = read(pointer, relation["callback_proof"]["width"])
                    if (
                        hashlib.sha256(descriptor).hexdigest()
                        != relation["callback_proof"]["sha256"]
                    ):
                        continue
                    if (
                        descriptor[0] != 5
                        or not descriptor[1]
                        or bool(descriptor[1] & 0x80) != relation["callback_four_point"]
                    ):
                        continue
                    payload = descriptor[
                        (20 if relation["callback_four_point"] else 12) :
                    ]
                    if payload != bytes((0xFF, 0, 0x18, relation["procedure"], 0, 0)):
                        continue
                    if any(
                        hashlib.sha256(
                            read(base + proof["offset"], proof["width"])
                        ).hexdigest()
                        != proof["sha256"]
                        for proof in (
                            relation["table_proof"],
                            relation["program_proof"],
                            *relation["message_proofs"],
                        )
                    ):
                        continue
                    # Native Aot_on dispatches directly, bypassing SAT zero and
                    # the parked item's rectangle. The fresh callback, table,
                    # code and item binding prove a player can still collect it.
                    state, amount = live_items[item_offset]
                    if state == "inactive":
                        live_items[item_offset] = ("uncollected", amount)

        evaluations, doors = [], []
        for visited in sorted(set(tracker.rooms) | {key}):
            source = profile.rooms[visited]
            source_id = RoomId(source["stage"], source["room"])
            bank = (
                layout["item_bank_early"]
                if source["stage"] < layout["item_bank_stage_boundary"]
                else layout["item_bank_late"]
            )
            context_valid = all(
                presence_matches(condition, flag)
                for condition in source.get("scenario_context_conditions", [])
            )
            known_puzzle_ids = {
                proof["global_id"]
                for proof in source.get("known_puzzle_items", [])
                if all(
                    presence_matches(condition, flag)
                    for condition in proof["context_conditions"]
                )
            }
            # Resource-dependent script proofs have explicit state requirements.
            # A mismatching load keeps the raw catalog and fresh observations,
            # but cannot retain exclusions, selected variants or clearance.
            candidates = (
                scenario_item_candidates(source) if context_valid else source["items"]
            )
            if (
                context_valid
                and visited == key
                and any(
                    item["offset"] in live_items and item not in candidates
                    for item in source["items"]
                )
            ):
                # A live excluded creator contradicts the fixed-context proof.
                # Retry without publishing instead of hiding the observation.
                return PollResult(
                    PollStatus.Retry, "Pickup disagrees with fixed scenario variant"
                )
            grouped = {}
            for item in candidates:
                if item["type"] >= layout["file_type_min"]:
                    continue
                grouped.setdefault(item["global_id"], []).append(item)
            details = []
            identities_complete = True
            conditional = (
                {
                    rule["global_id"]: rule["presence"]
                    for rule in source["conditional_item_presence"]
                }
                if context_valid
                else {}
            )
            for gid, variants in grouped.items():
                available = [
                    item
                    for item in variants
                    if visited == key
                    and item["offset"] in live_items
                    and live_items[item["offset"]][0] == "available"
                ]
                dispatched = [
                    item
                    for item in variants
                    if visited == key
                    and item["offset"] in live_items
                    and live_items[item["offset"]][0] == "uncollected"
                ]
                if context_valid and gid in source["scenario_absent_item_ids"]:
                    if visited == key and any(
                        item["offset"] in live_items for item in variants
                    ):
                        # Disabling activation does not undo a creator that
                        # contradicts the fixed-scenario absence proof.
                        return PollResult(
                            PollStatus.Retry,
                            "Pickup disagrees with fixed scenario proof",
                        )
                    # The fixed-scenario proof covers every creator. A shared
                    # acquisition bit cannot introduce this forbidden pickup.
                    continue
                taken = flag(bank, gid)
                if taken and available:
                    return PollResult(
                        PollStatus.Retry, "Pickup changed during room read"
                    )
                observed_items = available + dispatched
                types = {item["type"] for item in observed_items or variants}
                item_type = next(iter(types)) if len(types) == 1 else None
                label = profile.names["items"].get(str(item_type), "Collectible")
                if item_type is None:
                    # Collection belongs to the acquisition ID. Its unresolved
                    # identity still prevents a complete room verdict, even
                    # when the fresh flag records collection. RE2-COLLECT-021.
                    identities_complete = False
                if taken:
                    state = "taken"
                elif item_type is None:
                    state = "unknown"
                elif available:
                    state = "available"
                elif (
                    dispatched
                    or gid in known_puzzle_ids
                    or context_valid
                    and (
                        gid in source["collection_item_ids"]
                        or (
                            gid in conditional
                            and presence_matches(conditional[gid], flag)
                        )
                    )
                ):
                    # A known puzzle target remains required before activation;
                    # this does not establish its current access or quantity.
                    state = "uncollected"
                else:
                    state = "unknown"
                amounts = (
                    {live_items[item["offset"]][1] for item in observed_items}
                    if observed_items
                    else {amount for item in variants for amount in item["amounts"]}
                )
                if (
                    item_type == quantity_override["item_type"]
                    and system & quantity_override["system_mask"]
                ):
                    # RE2-QUANTITY-001: the native pickup handler replaces this
                    # amount at prompt entry, so source/live operands are not
                    # yet the award. Reconstruct it from fresh mode flags.
                    amounts = {quantity_override["amount"]}
                # Equal source operands do not prove equal native awards
                # across types, including the mode-specific override above.
                quantity = (
                    next(iter(amounts))
                    if item_type is not None and len(amounts) == 1
                    else ItemQuantityState.Unreconstructed
                )
                details.append(ItemDetail(label, state, quantity))
            for award in source["event_awards"]:
                if award["item_type"] >= layout["file_type_min"]:
                    continue
                collection = award["collection"]
                taken = collection["kind"] == "flag" and flag(
                    collection["bank"], collection["bit"]
                )
                presence = award["presence"]
                required = (
                    context_valid and not taken and presence_matches(presence, flag)
                )
                # Acquisition wins after delivery and use. Presence conditions
                # are sufficient only; a mismatch cannot establish absence.
                details.append(
                    ItemDetail(
                        profile.names["items"].get(
                            str(award["item_type"]), "Collectible"
                        )
                        if taken or required
                        else "Event collectible",
                        "taken" if taken else "uncollected" if required else "unknown",
                        award["amount"]
                        if taken or required
                        else ItemQuantityState.Unreconstructed,
                    )
                )
            complete = (
                source["candidate_list_complete"]
                and context_valid
                and identities_complete
                and not (visited == key and unresolved_registry)
            )
            evaluations.append((source_id, tuple(details), complete))
            departed_open_offsets = {
                offset
                for proof in source.get("immutable_open_doors", [])
                if visited != key
                and context_valid
                and all(
                    presence_matches(condition, flag)
                    for condition in proof["context_conditions"]
                )
                for offset in proof["creator_offsets"]
            }
            for definition in source["doors"]:
                observed = (
                    live_doors.get(definition["offset"]) if visited == key else None
                )
                if (
                    visited == key
                    and observed is None
                    and any(
                        door["slot"] == definition["slot"]
                        for door in live_doors.values()
                    )
                ):
                    # A live slot identifies its current script variant. Other
                    # creators for that slot are not additional current doors.
                    continue
                lock = observed or definition
                key_type = lock["lock_type"]
                key_label = (
                    profile.names["items"].get(str(key_type), "")
                    if key_type not in (0, 0xFE, 0xFF)
                    else ""
                )
                unlock_state = DoorUnlockState.Unknown
                # Current payloads can change targets and locks, so source
                # operands cannot replace a missing live binding. Departed
                # competing creators also cannot identify this side's lock;
                # never cache the last creator through departure or rewind.
                if lock["lock_id"] & 0x80 and (
                    observed is not None
                    or visited != key
                    and sum(
                        creator["slot"] == definition["slot"]
                        for creator in source["doors"] + source["items"]
                    )
                    == 1
                ):
                    unlock_state = (
                        DoorUnlockState.Unlocked
                        if flag(layout["key_bank"], lock["lock_id"] & 0x3F)
                        else DoorUnlockState.Locked
                    )
                unlocked = unlock_state is DoorUnlockState.Unlocked
                if unlocked:
                    key_label = ""
                if observed is None and definition["offset"] in departed_open_offsets:
                    # Source/native write proofs establish this binding for
                    # the room lifetime. Fresh conditions revoke it on rewind.
                    state, label = "OPEN", "Open"
                elif observed is None:
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
                        unlock_state=unlock_state,
                        interaction_id=f"{visited}:{definition['slot']}",
                    )
                )

        # Publish only after all consumed state and source pointers agree.
        # Savestate loads must reverse flags before any cached room is shown.
        masks = {
            (int(layout["system_flags_address_ps1"], 0), 4): layout["gameplay_mask"]
            | layout["demo_mask"]
            | layout["game_over_mask"]
            | layout["transition_mask"]
            | layout["system_mode_mask"]
            | quantity_override["system_mask"],
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
            # Only the bits consumed by this snapshot need to remain equal.
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
