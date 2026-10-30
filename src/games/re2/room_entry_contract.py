"""Bind an audited native entry contract to exact revision and resource bytes.

This receipt does not determine which room commands execute. A source compiler
must still prove its control flow and that reachable writes preserve entries,
procedure tables and task state. The hashes select inspected native semantics;
absence of a byte reference is not treated as an entry-closure proof.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import asdict, dataclass
from enum import Enum

from games.re2.room_write_partitions import RoomWritePartitionConfig

# The profile owns revision data. This digest selects the inspected recipe;
# changing a resource hash must not silently grant its native capabilities.
AUDITED_ROOM_ENTRY_MANIFEST_SHA256 = (
    "4884802bc04ea26380f4f8846ea3ba7193d30e6292fc3594135b917786bf2f7b"
)


def _manifest_digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class RoomEntryContractSupport(Enum):
    Unaudited = "unaudited"


class RoomEntryContractFailure(Enum):
    Manifest = "unsupported or invalid room-entry manifest"
    Executable = "room-entry executable identity mismatch"
    NativeLayout = "room-entry native layout mismatch"
    StageResource = "room-entry stage resource mismatch"
    ActorResource = "room-entry actor code resource mismatch"
    DoorResource = "room-entry door resource mismatch"


@dataclass(frozen=True)
class StageEntryResource:
    path: str
    width: int
    sha256: str

    def __post_init__(self) -> None:
        assert type(self.path) is str and self.path
        assert type(self.width) is int and self.width > 0
        assert type(self.sha256) is str and re.fullmatch(r"[0-9a-f]{64}", self.sha256)


@dataclass(frozen=True)
class StageEntryLoad:
    recipe_table_address_ps1: str
    recipe_index: int
    file_index: int
    entry_address_ps1: str
    destination_pointer_address_ps1: str
    destination_address_ps1: str
    file_lba: int
    file_flags: int
    source_alignment: int


@dataclass(frozen=True)
class StageEntry:
    stage: int
    resource: StageEntryResource
    load: StageEntryLoad

    def __post_init__(self) -> None:
        assert type(self.stage) is int and 0 <= self.stage <= 255
        assert isinstance(self.resource, StageEntryResource)
        assert isinstance(self.load, StageEntryLoad)


@dataclass(frozen=True)
class ActorEntryResource:
    resource_index: int
    sector: int
    width: int
    load_address_ps1: str
    sha256: str

    def __post_init__(self) -> None:
        assert type(self.resource_index) is int and 0 <= self.resource_index < 256
        assert type(self.sector) is int and self.sector >= 0
        assert type(self.width) is int and 4 <= self.width <= 0x200000
        assert type(self.load_address_ps1) is str and re.fullmatch(
            r"0x80[0-9A-F]{6}", self.load_address_ps1
        )
        assert type(self.sha256) is str and re.fullmatch(r"[0-9a-f]{64}", self.sha256)


@dataclass(frozen=True)
class DoorEntryResource:
    model: int
    path: str
    width: int
    sha256: str
    file_index: int
    lba: int
    payload_sector: int
    payload_width: int
    script_width: int
    script_sha256: str

    def __post_init__(self) -> None:
        assert type(self.model) is int and 0 <= self.model <= 255
        assert type(self.path) is str and self.path
        assert all(
            type(value) is int and value > 0
            for value in (
                self.width,
                self.file_index,
                self.lba,
                self.payload_sector,
                self.payload_width,
                self.script_width,
            )
        )
        assert 2 <= self.script_width <= self.payload_width - 8
        assert all(
            type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value)
            for value in (self.sha256, self.script_sha256)
        )


@dataclass(frozen=True)
class NativeEntryDispatch:
    address_ps1: str
    handler_address_ps1: str


@dataclass(frozen=True)
class NativeEntryLayout:
    executable_entry_address_ps1: str
    executable_global_pointer_ps1: str
    executable_load_address_ps1: str
    executable_text_width: int
    executable_file_width: int
    dispatch: tuple[NativeEntryDispatch, ...]
    actor_resource_table_address_ps1: str
    actor_model_origin: int
    actor_resources_per_model: int
    actor_primary_code_variant: int
    actor_code_pool_address_ps1: str
    actor_code_pool_stride: int
    actor_code_pool_count: int
    door_model_table_address_ps1: str
    door_model_record_width: int
    door_file_index_table_address_ps1: str
    file_table_address_ps1: str
    file_table_record_width: int
    sector_width: int


@dataclass(frozen=True)
class RoomEntryWriteLayout:
    aot_address_ps1: str
    aot_capacity: int
    object_address_ps1: str
    object_capacity: int
    item_flag_count: int
    interaction_flag_count: int


def _write_partitions(layout: RoomEntryWriteLayout) -> RoomWritePartitionConfig:
    return RoomWritePartitionConfig(
        int(layout.aot_address_ps1, 0),
        layout.aot_capacity,
        int(layout.object_address_ps1, 0),
        layout.object_capacity,
        layout.item_flag_count,
        layout.interaction_flag_count,
    )


@dataclass(frozen=True)
class RoomEntryContractConfig:
    audit: str
    executable_sha256: str
    stage_entries: tuple[StageEntry, ...]
    actor_archive_path: str
    constructor_presets: tuple[tuple[int, int], ...]
    actor_codes: tuple[ActorEntryResource, ...]
    doors: tuple[DoorEntryResource, ...]
    minimum_source_address_ps1: str
    roots: tuple[str, ...]
    non_scheduling_interaction_kinds: tuple[int, ...]
    native_layout: NativeEntryLayout
    write_partitions: RoomEntryWriteLayout

    def __post_init__(self) -> None:
        assert type(self.audit) is str and type(self.executable_sha256) is str
        assert type(self.stage_entries) is tuple and self.stage_entries
        assert all(isinstance(row, StageEntry) for row in self.stage_entries)
        assert len({row.stage for row in self.stage_entries}) == len(self.stage_entries)
        assert type(self.actor_archive_path) is str
        assert type(self.constructor_presets) is tuple and all(
            type(row) is tuple
            and len(row) == 2
            and type(row[0]) is int
            and 0 <= row[0] <= 255
            and type(row[1]) is int
            and 0 <= row[1] <= 0xFFFF
            for row in self.constructor_presets
        )
        assert type(self.actor_codes) is tuple and all(
            isinstance(row, ActorEntryResource) for row in self.actor_codes
        )
        assert type(self.doors) is tuple and all(
            isinstance(row, DoorEntryResource) for row in self.doors
        )
        assert type(self.minimum_source_address_ps1) is str
        assert type(self.roots) is tuple and all(type(key) is str for key in self.roots)
        assert type(self.non_scheduling_interaction_kinds) is tuple and all(
            type(kind) is int for kind in self.non_scheduling_interaction_kinds
        )
        assert isinstance(self.native_layout, NativeEntryLayout)
        assert isinstance(self.write_partitions, RoomEntryWriteLayout)
        assert _manifest_digest(asdict(self)) == AUDITED_ROOM_ENTRY_MANIFEST_SHA256


def _source_address(stage: StageEntry) -> int:
    load = stage.load
    # The room loader retains the stage binary before the RDT and rounds its
    # byte count up to this audited alignment before selecting the RDT base.
    return int(load.destination_address_ps1, 0) + (
        (stage.resource.width + load.source_alignment - 1) & -load.source_alignment
    )


@dataclass(frozen=True)
class VerifiedRoomEntryContract:
    config: RoomEntryContractConfig
    audit: str
    executable_sha256: str
    minimum_source_address: int
    source_addresses: tuple[tuple[int, int], ...]
    stages: frozenset[int]
    roots: tuple[str, ...]
    door_models: frozenset[int]
    non_scheduling_interaction_kinds: frozenset[int]
    constructor_presets: frozenset[tuple[int, int]]
    actor_code_images: tuple[ActorEntryResource, ...]
    write_partitions: RoomWritePartitionConfig

    def __post_init__(self) -> None:
        assert isinstance(self.config, RoomEntryContractConfig)
        assert (
            _manifest_digest(asdict(self.config)) == AUDITED_ROOM_ENTRY_MANIFEST_SHA256
        )
        assert type(self.audit) is str
        assert type(self.executable_sha256) is str
        assert type(self.minimum_source_address) is int
        assert type(self.source_addresses) is tuple and all(
            type(row) is tuple
            and len(row) == 2
            and all(type(value) is int for value in row)
            for row in self.source_addresses
        )
        assert all(
            type(values) is frozenset and all(type(value) is int for value in values)
            for values in (
                self.stages,
                self.door_models,
                self.non_scheduling_interaction_kinds,
            )
        )
        assert type(self.roots) is tuple
        assert type(self.constructor_presets) is frozenset and all(
            type(row) is tuple
            and len(row) == 2
            and all(type(value) is int for value in row)
            for row in self.constructor_presets
        )
        assert type(self.actor_code_images) is tuple
        assert self.audit == self.config.audit
        assert self.executable_sha256 == self.config.executable_sha256
        assert self.minimum_source_address == int(
            self.config.minimum_source_address_ps1, 0
        )
        assert self.source_addresses == tuple(
            (row.stage, _source_address(row)) for row in self.config.stage_entries
        )
        assert all(
            address >= self.minimum_source_address
            for _, address in self.source_addresses
        )
        assert self.stages == frozenset(row.stage for row in self.config.stage_entries)
        assert self.roots == self.config.roots
        assert self.door_models == frozenset(door.model for door in self.config.doors)
        assert self.non_scheduling_interaction_kinds == frozenset(
            self.config.non_scheduling_interaction_kinds
        )
        assert self.constructor_presets == frozenset(self.config.constructor_presets)
        assert self.actor_code_images == self.config.actor_codes
        assert self.write_partitions == _write_partitions(self.config.write_partitions)

    def covers_constructor(self, model_type: int, flag_word: int) -> bool:
        assert type(model_type) is int and 0 <= model_type <= 255
        assert type(flag_word) is int and 0 <= flag_word <= 0xFFFF
        return (model_type, flag_word) in self.constructor_presets


def room_entry_contract(
    profile: dict,
) -> RoomEntryContractConfig | RoomEntryContractSupport | RoomEntryContractFailure:
    if type(profile) is not dict:
        return RoomEntryContractFailure.Manifest
    if "room_entry_contract" not in profile:
        return RoomEntryContractSupport.Unaudited
    try:
        # JSON types are part of the contract. Python equality would equate
        # booleans and integers, while omitted code variants weaken the audit.
        raw = profile["room_entry_contract"]
        if _manifest_digest(raw) != AUDITED_ROOM_ENTRY_MANIFEST_SHA256:
            return RoomEntryContractFailure.Manifest
        layout = raw["native_layout"]
        return RoomEntryContractConfig(
            audit=raw["audit"],
            executable_sha256=raw["executable_sha256"],
            stage_entries=tuple(
                StageEntry(
                    stage=row["stage"],
                    resource=StageEntryResource(**row["resource"]),
                    load=StageEntryLoad(**row["load"]),
                )
                for row in raw["stage_entries"]
            ),
            actor_archive_path=raw["actor_archive_path"],
            constructor_presets=tuple(tuple(row) for row in raw["constructor_presets"]),
            actor_codes=tuple(ActorEntryResource(**row) for row in raw["actor_codes"]),
            doors=tuple(DoorEntryResource(**row) for row in raw["doors"]),
            minimum_source_address_ps1=raw["minimum_source_address_ps1"],
            roots=tuple(raw["roots"]),
            non_scheduling_interaction_kinds=tuple(
                raw["non_scheduling_interaction_kinds"]
            ),
            native_layout=NativeEntryLayout(
                **layout
                | {
                    "dispatch": tuple(
                        NativeEntryDispatch(**row) for row in layout["dispatch"]
                    )
                }
            ),
            write_partitions=RoomEntryWriteLayout(**raw["write_partitions"]),
        )
    except (AssertionError, KeyError, TypeError, ValueError):
        return RoomEntryContractFailure.Manifest


class _InvalidContract(Exception):
    def __init__(self, reason: RoomEntryContractFailure):
        self.reason = reason


def bind_room_entry_contract(
    config: RoomEntryContractConfig,
    executable: bytes,
    stage_resources: dict[int, bytes],
    actor_code_archive: bytes,
    door_resources: dict[int, bytes],
) -> VerifiedRoomEntryContract | RoomEntryContractFailure:
    """Verify required bytes; no source reachability or activation is inferred."""
    assert isinstance(config, RoomEntryContractConfig)
    assert all(type(value) is bytes for value in (executable, actor_code_archive))
    assert type(stage_resources) is dict and all(
        type(stage) is int and type(value) is bytes
        for stage, value in stage_resources.items()
    )
    assert type(door_resources) is dict and all(
        type(model) is int and type(value) is bytes
        for model, value in door_resources.items()
    )
    layout = config.native_layout
    load_address = int(layout.executable_load_address_ps1, 0)
    minimum_source_address = int(config.minimum_source_address_ps1, 0)

    def require(condition: bool, reason: RoomEntryContractFailure) -> None:
        if not condition:
            raise _InvalidContract(reason)

    def native(address: int, width: int) -> bytes:
        offset = 0x800 + address - load_address
        require(
            0x800 <= offset <= len(executable) - width,
            RoomEntryContractFailure.NativeLayout,
        )
        return executable[offset : offset + width]

    try:
        require(
            _manifest_digest(asdict(config)) == AUDITED_ROOM_ENTRY_MANIFEST_SHA256,
            RoomEntryContractFailure.Manifest,
        )
        require(
            hashlib.sha256(executable).hexdigest() == config.executable_sha256,
            RoomEntryContractFailure.Executable,
        )
        require(
            len(executable) == layout.executable_file_width
            and len(executable) >= 0x20
            and executable[:8] == b"PS-X EXE"
            and struct.unpack_from("<4I", executable, 0x10)
            == (
                int(layout.executable_entry_address_ps1, 0),
                int(layout.executable_global_pointer_ps1, 0),
                load_address,
                layout.executable_text_width,
            ),
            RoomEntryContractFailure.NativeLayout,
        )
        # The full executable hash binds the audited handlers. These table
        # checks additionally bind their native dispatch and resource layouts.
        for row in layout.dispatch:
            require(
                int.from_bytes(native(int(row.address_ps1, 0), 4), "little")
                == int(row.handler_address_ps1, 0),
                RoomEntryContractFailure.NativeLayout,
            )
        require(
            stage_resources.keys() == {row.stage for row in config.stage_entries},
            RoomEntryContractFailure.StageResource,
        )
        for stage in config.stage_entries:
            stage_resource = stage_resources[stage.stage]
            require(
                len(stage_resource) == stage.resource.width
                and hashlib.sha256(stage_resource).hexdigest() == stage.resource.sha256,
                RoomEntryContractFailure.StageResource,
            )
            stage_load = stage.load
            require(
                struct.unpack(
                    "<3I",
                    native(
                        int(stage_load.recipe_table_address_ps1, 0)
                        + stage_load.recipe_index * 12,
                        12,
                    ),
                )
                == (
                    stage_load.file_index,
                    int(stage_load.entry_address_ps1, 0),
                    int(stage_load.destination_pointer_address_ps1, 0),
                )
                and int.from_bytes(
                    native(int(stage_load.destination_pointer_address_ps1, 0), 4),
                    "little",
                )
                == int(stage_load.destination_address_ps1, 0),
                RoomEntryContractFailure.StageResource,
            )
            stage_record = native(
                int(layout.file_table_address_ps1, 0)
                + stage_load.file_index * layout.file_table_record_width,
                layout.file_table_record_width,
            )
            require(
                int.from_bytes(stage_record[:4], "little") == stage.resource.width
                and int.from_bytes(stage_record[4:7], "little") == stage_load.file_lba
                and stage_record[7] == stage_load.file_flags,
                RoomEntryContractFailure.StageResource,
            )
        model_types = {model for model, _ in config.constructor_presets}
        require(len(model_types) == 1, RoomEntryContractFailure.ActorResource)
        model_type = next(iter(model_types))
        for code in config.actor_codes:
            # The loader chooses the two inspected code images by physical
            # pool, not by the constructor's part-count/model-data resource.
            pool = (
                (model_type - layout.actor_model_origin)
                * layout.actor_resources_per_model
                + layout.actor_primary_code_variant
                - code.resource_index
            )
            require(
                0 <= pool < layout.actor_code_pool_count
                and int(code.load_address_ps1, 0)
                == int(layout.actor_code_pool_address_ps1, 0)
                + pool * layout.actor_code_pool_stride
                and int(code.load_address_ps1, 0) + code.width
                <= minimum_source_address,
                RoomEntryContractFailure.ActorResource,
            )
            require(
                struct.unpack(
                    "<II",
                    native(
                        int(layout.actor_resource_table_address_ps1, 0)
                        + code.resource_index * 8,
                        8,
                    ),
                )
                == (code.sector, code.width),
                RoomEntryContractFailure.ActorResource,
            )
            start = code.sector * layout.sector_width
            require(
                0 <= start <= len(actor_code_archive) - code.width,
                RoomEntryContractFailure.ActorResource,
            )
            require(
                hashlib.sha256(
                    actor_code_archive[start : start + code.width]
                ).hexdigest()
                == code.sha256,
                RoomEntryContractFailure.ActorResource,
            )
        require(
            door_resources.keys() == {door.model for door in config.doors},
            RoomEntryContractFailure.DoorResource,
        )
        for door in config.doors:
            data = door_resources[door.model]
            require(
                len(data) == door.width
                and hashlib.sha256(data).hexdigest() == door.sha256,
                RoomEntryContractFailure.DoorResource,
            )
            require(
                int.from_bytes(
                    native(
                        int(layout.door_file_index_table_address_ps1, 0)
                        + door.model * 2,
                        2,
                    ),
                    "little",
                )
                == door.file_index,
                RoomEntryContractFailure.DoorResource,
            )
            record = native(
                int(layout.file_table_address_ps1, 0)
                + door.file_index * layout.file_table_record_width,
                layout.file_table_record_width,
            )
            require(
                int.from_bytes(record[:4], "little") == door.width
                and int.from_bytes(record[4:7], "little") == door.lba,
                RoomEntryContractFailure.DoorResource,
            )
            descriptor = native(
                int(layout.door_model_table_address_ps1, 0)
                + door.model * layout.door_model_record_width,
                layout.door_model_record_width,
            )
            require(
                int.from_bytes(descriptor[2:4], "little") == door.payload_width
                and int.from_bytes(descriptor[4:8], "little") == door.payload_sector,
                RoomEntryContractFailure.DoorResource,
            )
            start = door.payload_sector * layout.sector_width
            require(
                0 <= start <= len(data) - door.payload_width,
                RoomEntryContractFailure.DoorResource,
            )
            payload = data[start : start + door.payload_width]
            require(
                len(payload) >= 10
                and int.from_bytes(payload[:4], "little") == 8 + door.script_width
                and hashlib.sha256(payload[8 : 8 + door.script_width]).hexdigest()
                == door.script_sha256,
                RoomEntryContractFailure.DoorResource,
            )
    except _InvalidContract as error:
        return error.reason
    return VerifiedRoomEntryContract(
        config=config,
        audit=config.audit,
        executable_sha256=config.executable_sha256,
        minimum_source_address=minimum_source_address,
        source_addresses=tuple(
            (row.stage, _source_address(row)) for row in config.stage_entries
        ),
        stages=frozenset(row.stage for row in config.stage_entries),
        roots=config.roots,
        door_models=frozenset(door.model for door in config.doors),
        non_scheduling_interaction_kinds=frozenset(
            config.non_scheduling_interaction_kinds
        ),
        constructor_presets=frozenset(config.constructor_presets),
        actor_code_images=config.actor_codes,
        write_partitions=_write_partitions(config.write_partitions),
    )
