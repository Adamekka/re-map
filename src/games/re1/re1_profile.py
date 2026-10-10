"""RE1 memory interpretation; addresses come from profiles/*.json."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

from games.game_profile import ItemListQuery, ItemQuery, RoomId, RoomItem, RoomQuery
from games.re1.acquisition_state import AcquisitionLayout
from games.re1.event_state import EventLayout
from games.re1.map_layout import Re1MapLayout
from games.re1.room_cache import (
    CachedRoomObservation,
    RoomDependency,
    RoomMutableField,
    RoomScriptSource,
)
from games.re1.room_items import RuntimeRoomLayout
from games.re1.tracking_rules import (
    CachedReentryEvaluation,
    RoomProgram,
    TrackingRuleLayout,
)


class MemoryResult(Protocol):
    ok: bool
    data: bytes
    error: str


class PilotItemState(Enum):
    UnsupportedState = "unsupported-state"
    Available = "available"
    Taken = "taken"
    AvailabilityUnknown = "availability-unknown"
    ReadFailure = "read-failure"


@dataclass(frozen=True)
class PilotItemObservation:
    state: PilotItemState
    reason: str = ""


@dataclass(frozen=True)
class RuntimeSignature:
    window_addresses: tuple[int, ...]
    window_width: int
    concatenated_sha256: str


@dataclass(frozen=True)
class PilotCondition:
    address: int
    mask: int
    expected: int


@dataclass(frozen=True)
class PilotItem:
    room: RoomId
    character_address: int
    character_value: int
    variant_word_address: int
    variant_mask: int
    conditions: tuple[PilotCondition, ...]
    source_rdt: str
    label: str
    global_id: int
    flag_address: int
    flag_mask: int
    aot_record_address: int
    aot_record_width: int
    active_handler: int
    pointer_offset: int
    expected_opcode_pointer: int


@dataclass(frozen=True)
class DoorStateLayout:
    unlock_flags_address: int
    unlock_flags_width: int
    player_state_address: int
    special_flag_address: int

    def __post_init__(self) -> None:
        if self.unlock_flags_width != 8:
            raise ValueError("door unlock flags require eight bytes")


@dataclass
class Re1Profile:
    profile_id: str
    # PS1 virtual addresses. None means unknown, not zero.
    # The pinned SLUS-00551 profile confirms Main/Sub at these addresses;
    # other revisions keep their own validation status in profile JSON.
    stage_address: int | None = None
    room_address: int | None = None
    camera_address: int | None = None
    lifecycle_address: int | None = None
    map_layout: Re1MapLayout | None = None
    revision: str = "unknown"
    runtime_signature: RuntimeSignature | None = None
    pilot_items: tuple[PilotItem, ...] = ()
    runtime_room_layout: RuntimeRoomLayout | None = None
    door_state_layout: DoorStateLayout | None = None
    room_sources: tuple[RoomScriptSource, ...] = ()
    room_programs: dict[str, RoomProgram] = field(default_factory=dict)
    room_source_choices: dict[tuple[RoomId, int, int], str] = field(
        default_factory=dict
    )
    tracking_rule_layout: TrackingRuleLayout | None = None
    event_layout: EventLayout | None = None
    room_observations: dict[RoomId, CachedRoomObservation] = field(default_factory=dict)
    # Reentry can be expensive for branching sources. Keep one pure result per
    # source in this profile instance; fresh inputs always invalidate it.
    room_reentry_evaluations: dict[str, CachedReentryEvaluation] = field(
        default_factory=dict
    )

    @staticmethod
    def load(path: Path) -> Re1Profile:
        raw = json.loads(path.read_text())

        def _number(v: int | str) -> int:
            if isinstance(v, str):
                if not v.startswith("0x"):
                    raise ValueError(f"profile number must use 0x prefix: {v!r}")
                return int(v, 16)
            return int(v)

        def _addr(key: str) -> int | None:
            v = raw.get(key)
            if v is None:
                return None
            return _number(v)

        def _room_number(v: str) -> int:
            if not isinstance(v, str) or not v.startswith("0x"):
                raise ValueError("pilot room IDs must be 0x-prefixed strings")
            value = _number(v)
            if not 0 <= value <= 0xFF:
                raise ValueError("pilot room IDs must fit one byte")
            return value

        signature_raw = raw.get("runtime_signature")
        signature = None
        if signature_raw is not None:
            signature = RuntimeSignature(
                window_addresses=tuple(
                    _number(v) for v in signature_raw["window_addresses_ps1"]
                ),
                window_width=_number(signature_raw["window_width_bytes"]),
                concatenated_sha256=str(signature_raw["concatenated_sha256"]),
            )
            if (
                not signature.window_addresses
                or not 1 <= signature.window_width <= 4096
            ):
                raise ValueError("runtime signature needs windows with width 1..4096")
            if len(signature.concatenated_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in signature.concatenated_sha256
            ):
                raise ValueError(
                    "runtime signature SHA256 must be 64 lowercase hex digits"
                )

        if "pilot_item" in raw:
            raise ValueError(
                "pilot_item was renamed to pilot_items; update the profile"
            )
        pilots = []
        for pilot_raw in raw.get("pilot_items", []):
            if "conditions" not in pilot_raw:
                raise ValueError("pilot item requires an explicit conditions list")
            conditions = tuple(
                PilotCondition(
                    address=_number(condition["address_ps1"]),
                    mask=_number(condition["mask"]),
                    expected=_number(condition["expected_masked_value"]),
                )
                for condition in pilot_raw["conditions"]
            )
            for condition in conditions:
                if (
                    not 0 < condition.mask <= 0xFF
                    or (condition.expected & ~condition.mask) != 0
                ):
                    raise ValueError(
                        "pilot condition expected value must fit its one-byte mask"
                    )
            pilot = PilotItem(
                room=RoomId(
                    stage=_room_number(pilot_raw["room_main"]),
                    room=_room_number(pilot_raw["room_sub"]),
                ),
                character_address=_number(pilot_raw["character_address_ps1"]),
                character_value=_number(pilot_raw["character_value"]),
                variant_word_address=_number(pilot_raw["variant_word_address_ps1"]),
                variant_mask=_number(pilot_raw["variant_mask"]),
                conditions=conditions,
                source_rdt=str(pilot_raw["source_rdt"]),
                label=str(pilot_raw["label"]),
                global_id=_number(pilot_raw["global_id"]),
                flag_address=_number(pilot_raw["flag_address_ps1"]),
                flag_mask=_number(pilot_raw["flag_mask"]),
                aot_record_address=_number(pilot_raw["aot_record_address_ps1"]),
                aot_record_width=_number(pilot_raw["aot_record_width_bytes"]),
                active_handler=_number(pilot_raw["active_handler"]),
                pointer_offset=_number(pilot_raw["pointer_offset_bytes"]),
                expected_opcode_pointer=_number(
                    pilot_raw["expected_opcode_pointer_ps1"]
                ),
            )
            if not 0 < pilot.flag_mask <= 0xFF:
                raise ValueError("pilot item flag mask must fit one nonzero byte")
            if not 0 <= pilot.pointer_offset or not (
                pilot.pointer_offset + 4 <= pilot.aot_record_width <= 4096
            ):
                raise ValueError("pilot item opcode pointer must fit its AOT record")
            if any(existing.room == pilot.room for existing in pilots):
                raise ValueError(f"duplicate pilot item room: {pilot.room}")
            pilots.append(pilot)

        runtime_raw = raw.get("runtime_room_layout")
        runtime_layout = None
        if runtime_raw is not None:
            runtime_layout = RuntimeRoomLayout(
                acquisition=AcquisitionLayout.load(
                    raw["acquisition_rules"],
                    _number(runtime_raw["acquisition_flags_address"]),
                    _number(runtime_raw["acquisition_flags_width"]),
                ),
                **{
                    key: tuple(
                        (_number(item_type), str(label)) for item_type, label in value
                    )
                    if key == "item_labels"
                    else _number(value)
                    for key, value in runtime_raw.items()
                },
            )
            for key in ("stage_address_ps1", "room_address_ps1", "camera_address_ps1"):
                address = _addr(key)
                if address is None:
                    raise ValueError(f"runtime room profile requires {key}")
                if (
                    not runtime_layout.ram_base
                    <= address
                    < runtime_layout.ram_base + runtime_layout.ram_size
                ):
                    raise ValueError(f"{key} is outside configured PS1 RAM")
        door_raw = raw.get("door_state_layout")
        door_layout = None
        if door_raw is not None:
            door_layout = DoorStateLayout(
                **{key: _number(value) for key, value in door_raw.items()}
            )
            if runtime_layout is None:
                raise ValueError("door layout requires a runtime room layout")
            for address, width in (
                (door_layout.unlock_flags_address, door_layout.unlock_flags_width),
                (door_layout.player_state_address, 1),
                (door_layout.special_flag_address, 1),
            ):
                if (
                    not runtime_layout.ram_base
                    <= address
                    < address + width
                    <= runtime_layout.ram_base + runtime_layout.ram_size
                ):
                    raise ValueError("door state address is outside configured PS1 RAM")

        room_sources = []
        room_programs = {}
        source_choices = {}
        rule_layout = None
        event_layout = None
        if runtime_layout is not None:
            event_layout = EventLayout(
                **{key: _number(value) for key, value in raw["event_layout"].items()}
            )
            rule_raw = raw["tracking_rule_layout"]
            rule_layout = TrackingRuleLayout(
                tuple(_number(value) for value in raw["script_flag_bases"]),
                tuple(rule_raw["persistent_flag_groups"]),
                tuple(tuple(bit) for bit in rule_raw["persistent_flag_bits"]),
                _number(rule_raw["character_address_ps1"]),
                tuple(
                    (_number(mask["address_ps1"]), _number(mask["mask"]))
                    for mask in rule_raw["source_selection_masks"]
                ),
                _number(rule_raw["variant_address_ps1"]),
                _number(rule_raw["variant_mask"]),
                _number(rule_raw["alternate_address_ps1"]),
                _number(rule_raw["alternate_mask"]),
                _number(rule_raw["byte_variables_base_ps1"]),
                _number(rule_raw["word_variables_base_ps1"]),
                tuple(tuple(clear) for clear in rule_raw["room_entry_flag_clears"]),
                runtime_layout.acquisition,
            )
            manifest_path = path.parent / raw["room_manifest_path"]
            manifest = json.loads(manifest_path.read_text())
            if manifest["profile_id"] != raw["profile_id"]:
                raise ValueError("room manifest does not match profile ID")
            if manifest["executable_identity"] != raw["executable_identity"]:
                raise ValueError("room manifest does not match profile executable")
            for row in manifest["rooms"]:
                if (
                    type(row["room_main"]) is not int
                    or type(row["room_sub"]) is not int
                    or not 0 <= row["room_main"] < 7
                    or not 0 <= row["room_sub"] < 32
                ):
                    raise ValueError("invalid tracking source room")
                program = RoomProgram.load(row["tracking_program"])
                events = program.event_program
                event_end = row["events_offset"] + row["events_size"]
                if any(
                    not row["events_offset"] <= offset < event_end
                    for offset in events.entries
                    + tuple(point.offset for point in events.points)
                    + tuple(dispatch.offset for dispatch in events.dispatches)
                    + tuple(start.offset for start in events.starts)
                    + tuple(
                        offset
                        for point in events.points
                        for kind, repeat, command in point.frames
                        for offset in (
                            (repeat, command)
                            if kind == "call"
                            else (repeat,)
                            if kind == "loop"
                            else ()
                        )
                    )
                    + tuple(
                        offset
                        for dispatch in events.dispatches
                        for offset in dispatch.commands
                    )
                ):
                    raise ValueError("event activation metadata outside source events")
                if any(
                    not row["init_offset"] <= record[0] < event_end
                    for record in events.creators
                    + events.registry_writes
                    + events.changes
                    + events.script_starts
                ):
                    raise ValueError("event registry metadata outside source scripts")
                if any(
                    offset < row["events_offset"] + 4 * (len(events.entries) + 1)
                    for offset in events.entries
                ):
                    raise ValueError("event entry overlaps indexed table")
                initial_positions = {
                    (point.entry, point.offset, point.state, point.depth)
                    for point in events.points
                }
                if any(
                    (index, offset, 0, 0) not in initial_positions
                    for index, offset in enumerate(events.entries)
                ):
                    raise ValueError("event entry has no initial VM position")
                if row["source_rdt"] in room_programs:
                    raise ValueError("duplicate tracking source")
                for section, procedures in (
                    ("init", program.procedures),
                    ("main", program.main_procedures),
                    (
                        "events",
                        tuple(p for block in program.event_blocks for p in block),
                    ),
                ):
                    if any(
                        not row[section + "_offset"]
                        <= procedure.start
                        < procedure.end
                        <= row[section + "_offset"] + row[section + "_size"]
                        for procedure in procedures
                    ):
                        raise ValueError("tracking procedure outside source " + section)
                if any(
                    not row["events_offset"]
                    <= command.offset
                    < command.next
                    <= row["events_offset"] + row["events_size"]
                    for command in program.event_effects + program.event_commands
                ):
                    raise ValueError("tracking effect outside source events")
                commands = (
                    tuple(
                        command
                        for procedure in program.procedures + program.main_procedures
                        for command in procedure.commands
                    )
                    + tuple(
                        command
                        for block in program.event_blocks
                        for procedure in block
                        for command in procedure.commands
                    )
                    + program.event_effects
                    + program.event_commands
                )
                if any(
                    command.kind == "item"
                    and command.args[3] >= runtime_layout.acquisition_flags_width * 8
                    for command in commands
                ):
                    raise ValueError("tracking item ID exceeds acquisition flags")
                for command in commands:
                    if command.kind == "item" and 1 <= command.args[1] <= 0x53:
                        runtime_layout.acquisition.flag(
                            command.args[1], command.args[3]
                        )
                room_programs[row["source_rdt"]] = program
                dependencies = tuple(
                    RoomDependency(
                        _number(dep["address_ps1"]),
                        _number(dep["width"]),
                        _number(dep["mask"]),
                    )
                    for dep in row["dependencies"]
                )
                for dep in dependencies:
                    if not (
                        1 <= dep.width <= 4
                        and 0 < dep.mask < (1 << (8 * dep.width))
                        and runtime_layout.ram_base
                        <= dep.address
                        < dep.address + dep.width
                        <= runtime_layout.ram_base + runtime_layout.ram_size
                    ):
                        raise ValueError("invalid room manifest dependency")
                gids = tuple(_number(gid) for gid in row["item_global_ids"])
                if any(
                    not 0 <= gid < runtime_layout.acquisition_flags_width * 8
                    for gid in gids
                ):
                    raise ValueError("room manifest item ID exceeds acquisition flags")
                for section in ("init", "main", "events"):
                    offset, size, digest = (
                        row[section + "_offset"],
                        row[section + "_size"],
                        row[section + "_sha256"],
                    )
                    if not (
                        0x94 <= offset <= offset + size < runtime_layout.ram_size
                        and len(digest) == 64
                        and all(c in "0123456789abcdef" for c in digest)
                    ):
                        raise ValueError("invalid room manifest script range/hash")
                if (
                    type(row["cache_complete"]) is not bool
                    or type(row["door_cache_complete"]) is not bool
                ):
                    raise ValueError("room manifest requires explicit cache policy")
                room_sources.append(
                    RoomScriptSource(
                        room=RoomId(row["room_main"], row["room_sub"]),
                        source_rdt=row["source_rdt"],
                        init_offset=row["init_offset"],
                        init_size=row["init_size"],
                        init_sha256=row["init_sha256"],
                        main_offset=row["main_offset"],
                        main_size=row["main_size"],
                        main_sha256=row["main_sha256"],
                        events_offset=row["events_offset"],
                        events_size=row["events_size"],
                        events_sha256=row["events_sha256"],
                        dependencies=dependencies,
                        item_global_ids=gids,
                        cache_complete=row["cache_complete"],
                        door_cache_complete=row["door_cache_complete"],
                        mutable_fields=tuple(
                            RoomMutableField(
                                section=field["section"],
                                offset=field["offset"],
                                width=field["width"],
                                kind=field["kind"],
                                original=field["original"],
                            )
                            for field in row["mutable_fields"]
                        ),
                    )
                )
            if not room_sources:
                raise ValueError("runtime room manifest must not be empty")
            for choice in manifest["source_choices"]:
                room = RoomId(choice["room_main"], choice["room_sub"])
                variant, alternate = choice["variant"], choice["alternate"]
                key = (room, variant, alternate)
                if (
                    type(variant) is not int
                    or type(alternate) is not int
                    or variant not in (0, 1)
                    or alternate not in (0, 1)
                    or key in source_choices
                ):
                    raise ValueError("invalid or duplicate room source choice")
                if not any(
                    source.room == room and source.source_rdt == choice["source_rdt"]
                    for source in room_sources
                ):
                    raise ValueError("room source choice has no matching program")
                source_choices[key] = choice["source_rdt"]
            expected_choices = {
                (source.room, variant, alternate)
                for source in room_sources
                for variant in (0, 1)
                for alternate in (0, 1)
            }
            if set(source_choices) != expected_choices:
                raise ValueError(
                    "room source choices must cover every supported selector"
                )

        map_layout = None
        if runtime_layout is not None:
            if "floor_plans_path" not in raw:
                raise ValueError("runtime room profile requires floor_plans_path")
            map_layout = Re1MapLayout.load(
                path.parent / raw["floor_plans_path"],
                str(raw["profile_id"]),
                str(raw["executable_identity"]),
            )
            for room in {source.room for source in room_sources}:
                if (
                    room.stage % map_layout.stage_modulus,
                    room.room,
                    0,
                ) not in map_layout.choices:
                    raise ValueError(
                        "floor plans must cover every supported room source"
                    )

        lifecycle_address = _addr("lifecycle_address_ps1")
        if (
            lifecycle_address is not None
            and runtime_layout is not None
            and not (
                runtime_layout.ram_base
                <= lifecycle_address
                < runtime_layout.ram_base + runtime_layout.ram_size
            )
        ):
            raise ValueError("lifecycle address is outside configured PS1 RAM")

        return Re1Profile(
            profile_id=str(raw.get("profile_id", path.stem)),
            stage_address=_addr("stage_address_ps1"),
            room_address=_addr("room_address_ps1"),
            camera_address=_addr("camera_address_ps1"),
            lifecycle_address=lifecycle_address,
            map_layout=map_layout,
            revision=str(raw.get("revision", "unknown")),
            runtime_signature=signature,
            pilot_items=tuple(pilots),
            runtime_room_layout=runtime_layout,
            door_state_layout=door_layout,
            room_sources=tuple(room_sources),
            room_programs=room_programs,
            room_source_choices=source_choices,
            tracking_rule_layout=rule_layout,
            event_layout=event_layout,
        )

    def has_room_addresses(self) -> bool:
        return self.stage_address is not None and self.room_address is not None

    @staticmethod
    def is_bit_set(byte_value: int, mask: int) -> bool:
        # Explicit bit test for Item Collected bytes. Mask must be one byte.
        assert 0 <= byte_value <= 0xFF, "byte_value must be 0..255"
        assert 0x01 <= mask <= 0xFF, "mask must be 1..255"
        return (byte_value & mask) != 0

    def verify_runtime(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> ItemQuery:
        signature = self.runtime_signature
        if signature is None:
            return ItemQuery(
                ok=False,
                value=False,
                error="runtime signature unavailable for this profile",
            )
        windows = []
        for address in signature.window_addresses:
            result = read_memory(address, signature.window_width)
            if not result.ok:
                return ItemQuery(
                    ok=False,
                    value=False,
                    error=f"signature read at {address:#x}: {result.error}",
                )
            if len(result.data) != signature.window_width:
                return ItemQuery(
                    ok=False, value=False, error=f"short signature read at {address:#x}"
                )
            windows.append(result.data)
        digest = hashlib.sha256(b"".join(windows)).hexdigest()
        return ItemQuery(ok=True, value=digest == signature.concatenated_sha256)

    def read_current_room(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> RoomQuery:
        if self.stage_address is None or self.room_address is None:
            return RoomQuery(ok=False, error="room addresses unknown for this revision")
        stage = read_memory(self.stage_address, 1)
        room = read_memory(self.room_address, 1)
        if not stage.ok or not room.ok:
            return RoomQuery(
                ok=False, error=f"room read failed: {stage.error} {room.error}"
            )
        if len(stage.data) != 1 or len(room.data) != 1:
            return RoomQuery(ok=False, error="room read failed: short reply")
        return RoomQuery(ok=True, room=RoomId(stage.data[0], room.data[0]))

    def observe_pilot_item(
        self, pilot: PilotItem, read_memory: Callable[[int, int], MemoryResult]
    ) -> PilotItemObservation:
        reads = (
            ("character", pilot.character_address, 1),
            ("variant", pilot.variant_word_address, 4),
        )
        values = []
        for label, address, width in reads:
            result = read_memory(address, width)
            if not result.ok:
                return PilotItemObservation(
                    PilotItemState.ReadFailure, f"{label}: {result.error}"
                )
            if len(result.data) != width:
                return PilotItemObservation(
                    PilotItemState.ReadFailure, f"{label}: short read"
                )
            values.append(result.data)
        character, variant = values
        if character[0] != pilot.character_value:
            return PilotItemObservation(
                PilotItemState.UnsupportedState, "character not supported in pilot"
            )
        if not int.from_bytes(variant, "little") & pilot.variant_mask:
            return PilotItemObservation(
                PilotItemState.UnsupportedState, "Jill room variant not selected"
            )
        for condition in pilot.conditions:
            result = read_memory(condition.address, 1)
            if not result.ok or len(result.data) != 1:
                reason = result.error if not result.ok else "short read"
                return PilotItemObservation(
                    PilotItemState.ReadFailure, f"branch flag: {reason}"
                )
            if (result.data[0] & condition.mask) != condition.expected:
                return PilotItemObservation(
                    PilotItemState.UnsupportedState,
                    "validated item branch not selected",
                )
        flag_result = read_memory(pilot.flag_address, 1)
        if not flag_result.ok or len(flag_result.data) != 1:
            reason = flag_result.error if not flag_result.ok else "short read"
            return PilotItemObservation(
                PilotItemState.ReadFailure, f"pickup flag: {reason}"
            )
        flag = flag_result.data
        if not self.is_bit_set(flag[0], pilot.flag_mask):
            return PilotItemObservation(PilotItemState.Taken)
        aot_result = read_memory(pilot.aot_record_address, pilot.aot_record_width)
        if not aot_result.ok or len(aot_result.data) != pilot.aot_record_width:
            reason = aot_result.error if not aot_result.ok else "short read"
            return PilotItemObservation(
                PilotItemState.ReadFailure, f"item object: {reason}"
            )
        aot = aot_result.data
        pointer = int.from_bytes(
            aot[pilot.pointer_offset : pilot.pointer_offset + 4], "little"
        )
        if aot[0] == pilot.active_handler and pointer == pilot.expected_opcode_pointer:
            return PilotItemObservation(PilotItemState.Available)
        return PilotItemObservation(
            PilotItemState.AvailabilityUnknown,
            "item object not active at the validated script row",
        )

    def detect_game(self) -> ItemQuery:
        return ItemQuery(
            ok=False, value=False, error="no game identity check implemented"
        )

    def current_room(self) -> RoomQuery:
        if self.stage_address is None or self.room_address is None:
            return RoomQuery(ok=False, error="room addresses unknown for this revision")
        # Real read happens in the tracker loop once addresses validate.
        # This assert marks programmer error if wiring calls us with no reader.
        raise AssertionError(
            "Re1Profile.current_room needs a memory reader; not wired yet"
        )

    def enumerate_current_room_items(self, room: RoomId) -> ItemListQuery:
        return ItemListQuery(ok=True, items=(), complete_list_known=False)

    def is_item_collected(self, item: RoomItem) -> ItemQuery:
        if item.acquired_flag_address is None:
            return ItemQuery(ok=False, value=False, error="acquired flag unknown")
        raise AssertionError(
            "Re1Profile.is_item_collected needs a memory reader; not wired yet"
        )

    def is_item_currently_available(self, item: RoomItem) -> ItemQuery:
        # Unknown until spawn conditions are understood per item.
        return ItemQuery(
            ok=False,
            value=False,
            error=f"spawn condition unresolved: {item.spawn_condition}",
        )
