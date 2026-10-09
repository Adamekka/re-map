"""Coherent observations for event experiments, separate from tracker history."""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Callable
from dataclasses import asdict, dataclass

from games.game_profile import RoomId
from games.re1.door_state import (
    DoorObservation,
    parse_door,
    stage_remap_from_window,
)
from games.re1.event_state import EventSnapshot, read_event_snapshot
from games.re1.re1_profile import MemoryResult, Re1Profile
from games.re1.room_cache import RoomScriptSource, match_room_source
from games.re1.room_items import RuntimeRoomItems, observe_room_items


@dataclass(frozen=True)
class CaptureFailure:
    status: str
    error: str


@dataclass(frozen=True)
class EventWatch:
    positions: tuple[tuple[int, ...], ...]
    fields: tuple[tuple[str, int, bytes], ...]
    trigger_fields: tuple[tuple[str, int, bytes], ...]


@dataclass(frozen=True)
class EventCapture:
    watch: EventWatch
    room: RoomId
    sources: tuple[RoomScriptSource, ...]
    events: EventSnapshot
    observation: RuntimeRoomItems
    doors: tuple[tuple[DoorObservation, bool], ...]

    def record(self) -> dict:
        return {
            "room": str(self.room),
            "sources": [asdict(source) for source in self.sources],
            "positions": self.watch.positions,
            "events": [asdict(event) for event in self.events.events],
            "interactions": [asdict(event) for event in self.events.interactions],
            "items": [
                {**asdict(item), "state": item.state.value, "kind": item.kind.value}
                for item in self.observation.items
            ],
            # This is the live registry's coverage, not a room-clear verdict.
            "registry_items_complete": self.observation.list_complete,
            "registry_items_reason": self.observation.coverage_reason,
            "doors": [
                {**asdict(door), "state": door.state.value, "disabled": disabled}
                for door, disabled in self.doors
            ],
            "reads": [
                {
                    "name": name,
                    "address_ps1": f"0x{address:08X}",
                    "width": len(data),
                    # Source fingerprints detect in-place quantity changes.
                    # Never put the descriptor's game bytecode into the log.
                    **(
                        {"sha256": hashlib.sha256(data).hexdigest()}
                        if name.startswith("source-")
                        else {"hex": data.hex()}
                    ),
                }
                for name, address, data in self.watch.fields
            ],
        }


def read_event_watch(
    profile: Re1Profile, read_memory: Callable[[int, int], MemoryResult]
) -> EventWatch | CaptureFailure:
    layout = profile.runtime_room_layout
    event_layout = profile.event_layout
    door_layout = profile.door_state_layout
    rules = profile.tracking_rule_layout
    if (
        layout is None
        or event_layout is None
        or door_layout is None
        or rules is None
        or profile.stage_address is None
        or profile.room_address is None
        or profile.camera_address is None
    ):
        return CaptureFailure("configuration", "Profile lacks event capture addresses.")
    identity = profile.verify_runtime(read_memory)
    if not identity.ok:
        return CaptureFailure("read-failure", f"Game identity: {identity.error}")
    if not identity.value:
        return CaptureFailure("wrong-game", "Running game does not match the profile.")
    fields = []
    for name, address, width in (
        ("stage", profile.stage_address, 1),
        ("room", profile.room_address, 1),
        ("camera", profile.camera_address, 1),
        ("loaded-room", layout.loaded_rdt_pointer_address, 4),
        ("registry-bound", layout.aot_bound_address, 4),
        ("pending-interaction", layout.pending_action_pointer_address, 4),
        ("interaction-flags", layout.main_flags_address, 4),
        (
            "acquisition",
            layout.acquisition_flags_address,
            layout.acquisition_flags_width,
        ),
        ("unlock", door_layout.unlock_flags_address, door_layout.unlock_flags_width),
        ("player-state", door_layout.player_state_address, 1),
        ("special-flag", door_layout.special_flag_address, 1),
        ("character", rules.character_address, 1),
        *(
            (f"script-flags-{group}", base, 32)
            for group, base in enumerate(rules.flag_bases)
        ),
    ):
        result = read_memory(address, width)
        if not result.ok or len(result.data) != width:
            return CaptureFailure(
                "read-failure",
                f"{name} at {address:#x}: {result.error or 'short read'}",
            )
        fields.append((name, address, result.data))
    values = {name: data for name, _, data in fields}
    bound = int.from_bytes(values["registry-bound"], "little")
    if not (
        layout.aot_base <= bound < layout.aot_base + layout.aot_capacity * 12
        and (bound - layout.aot_base) % 12 == 0
    ):
        return CaptureFailure(
            "registry-unavailable", "Registry bound is outside the supported range."
        )
    # The bound points at the last registered record, not past it. Reading
    # beyond it would mistake retained prior-room records for live triggers.
    width = bound - layout.aot_base + 12
    result = read_memory(layout.aot_base, width)
    if not result.ok or len(result.data) != width:
        return CaptureFailure(
            "read-failure", f"Registry: {result.error or 'short read'}"
        )
    fields.append(("registry", layout.aot_base, result.data))
    values["registry"] = result.data
    base = int.from_bytes(values["loaded-room"], "little")
    if layout.ram_base <= base < base + 0x70 <= layout.ram_base + layout.ram_size:
        # The loaded RDT stores its four script pointers at +0x60. These
        # watch reads are change hints; source validation happens at capture.
        result = read_memory(base + 0x60, 16)
        if not result.ok or len(result.data) != 16:
            return CaptureFailure(
                "read-failure", f"Script header: {result.error or 'short read'}"
            )
        fields.append(("script-header", base + 0x60, result.data))
        init, main, events, end = struct.unpack("<4I", result.data)
        if (
            base + 0x94
            <= init
            < main
            < events
            < end
            <= layout.ram_base + layout.ram_size
        ):
            for slot in range(len(values["registry"]) // 12):
                pointer = struct.unpack_from("<I", values["registry"], 12 * slot + 8)[0]
                address = pointer - 2
                if not init <= address < end:
                    # Stale registry pointers are not safe source reads.
                    # Capture reports any unsupported live interpretation.
                    continue
                width = min(26, end - address)
                result = read_memory(address, width)
                if not result.ok or len(result.data) != width:
                    return CaptureFailure(
                        "read-failure",
                        f"Source slot {slot}: {result.error or 'short read'}",
                    )
                fields.append((f"source-{slot}", address, result.data))
    pool = read_memory(
        event_layout.pool_address, event_layout.capacity * event_layout.stride
    )
    if not pool.ok or len(pool.data) != event_layout.capacity * event_layout.stride:
        return CaptureFailure(
            "read-failure", f"Event pool: {pool.error or 'short read'}"
        )
    masks = {}
    for group in rules.persistent_flag_groups:
        for offset in range(32):
            masks[rules.flag_bases[group] + offset] = 255
    for group, index in rules.persistent_flag_bits:
        address, mask = rules.flag(group, index)
        masks[address] = masks.get(address, 0) | mask
    room = RoomId(values["stage"][0], values["room"][0])
    for source in profile.room_sources:
        if source.room != room:
            continue
        for dependency in source.dependencies:
            for offset in range(dependency.width):
                address = dependency.address + offset
                masks[address] = masks.get(address, 0) | (
                    dependency.mask >> (8 * offset) & 255
                )
        program = profile.room_programs[source.source_rdt]
        for procedure in (
            program.procedures
            + program.main_procedures
            + tuple(procedure for block in program.event_blocks for procedure in block)
        ):
            for command in procedure.commands:
                if command.kind in ("flag-test", "flag-write"):
                    address, mask = rules.flag(command.args[0], command.args[1])
                    masks[address] = masks.get(address, 0) | mask
    # Snapshot all flag bytes, but pause only for persistent or source-declared
    # conditions. Unrelated animation scratch changes on nearly every frame.
    triggers = tuple(
        (
            name,
            address,
            bytes(
                value & masks.get(address + offset, 0)
                for offset, value in enumerate(data)
            ),
        )
        if name.startswith("script-flags-")
        else (name, address, data)
        for name, address, data in fields
    )
    return EventWatch(event_layout.positions(pool.data), tuple(fields), triggers)


def read_event_capture(
    profile: Re1Profile, read_memory: Callable[[int, int], MemoryResult]
) -> EventCapture | CaptureFailure:
    watch = read_event_watch(profile, read_memory)
    if isinstance(watch, CaptureFailure):
        return watch
    layout = profile.runtime_room_layout
    event_layout = profile.event_layout
    assert layout is not None and event_layout is not None, (
        "validated capture configuration"
    )
    values = {name: data for name, _, data in watch.fields}
    room = RoomId(values["stage"][0], values["room"][0])
    query = match_room_source(layout, profile.room_sources, room, read_memory)
    if not query.ok or not query.sources:
        return CaptureFailure(
            "source-unavailable", query.error or "Room source is not supported."
        )
    observation = observe_room_items(layout, room, read_memory)
    if not observation.ok:
        return CaptureFailure(
            "changed" if observation.retry else "registry-unavailable",
            observation.error,
        )
    base = int.from_bytes(values["loaded-room"], "little")
    snapshot = read_event_snapshot(
        event_layout,
        query.sources,
        profile.room_programs,
        base,
        values["registry"],
        read_memory,
    )
    if not snapshot.ok:
        return CaptureFailure("read-failure", snapshot.error)
    if snapshot.positions != watch.positions:
        return CaptureFailure("changed", "Event position changed during capture.")
    rule_layout = profile.tracking_rule_layout
    if rule_layout is None:
        return CaptureFailure("configuration", "Profile lacks tracking rules.")
    # Door targets remap stage 0/1 to 5/6 when this story flag is set; see
    # door_state.decode_door_target and the pinned transition at 0x8002A6E0.
    remap_bytes = values.get("script-flags-0")
    if remap_bytes is None:
        return CaptureFailure("read-failure", "Door stage remap flag is missing.")
    try:
        stage_remap = stage_remap_from_window(rule_layout, remap_bytes)
    except ValueError as error:
        return CaptureFailure("read-failure", str(error))
    doors = []
    try:
        for disabled, records in (
            (False, observation.active_doors),
            (True, observation.disabled_doors),
        ):
            for slot, raw in records:
                doors.append(
                    (
                        parse_door(
                            slot,
                            raw,
                            room,
                            values["unlock"],
                            values["player-state"][0],
                            values["special-flag"][0],
                            stage_remap,
                        ),
                        disabled,
                    )
                )
    except ValueError as error:
        return CaptureFailure("door-unavailable", str(error))
    for address, expected in (
        query.memory_markers + observation.memory_markers + snapshot.memory_markers
    ):
        result = read_memory(address, len(expected))
        if not result.ok or len(result.data) != len(expected):
            return CaptureFailure(
                "read-failure", f"Snapshot recheck: {result.error or 'short read'}"
            )
        if result.data != expected:
            return CaptureFailure(
                "changed", "Source, registry or flags changed during capture."
            )
    again = read_event_watch(profile, read_memory)
    if isinstance(again, CaptureFailure):
        return again
    if again != watch:
        return CaptureFailure("changed", "Watched state changed during capture.")
    return EventCapture(watch, room, query.sources, snapshot, observation, tuple(doors))


def observed_changes(before: EventCapture, after: EventCapture) -> list[dict]:
    if before.room != after.room or before.sources != after.sources:
        # An address reused by another room is not continuation of an event.
        return [{"kind": "room-source-changed"}]
    old = {row[0]: row for row in before.watch.positions}
    new = {row[0]: row for row in after.watch.positions}
    changes = [
        {
            "kind": "became-active"
            if slot not in old
            else "became-inactive"
            if slot not in new
            else "position-changed",
            "slot": slot,
        }
        for slot in sorted(old.keys() | new.keys())
        if old.get(slot) != new.get(slot)
    ]
    old_fields = {name: (address, data) for name, address, data in before.watch.fields}
    new_fields = {name: (address, data) for name, address, data in after.watch.fields}
    changes.extend(
        {"kind": "read-changed", "name": name}
        for name in sorted(old_fields.keys() | new_fields.keys())
        if old_fields.get(name) != new_fields.get(name)
    )
    return changes
