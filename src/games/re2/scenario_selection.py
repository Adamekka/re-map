"""RE2-SCENARIO-001: scoped identities, separate from presence/global context.

Native scenario provenance and native entry/write isolation are distinct
capabilities. Neither a raw catalog nor a resource hash grants either one.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from games.re2.actor_part_proofs import SourceCopyWrite
from games.re2.event_presence import (
    flag_write_conflicts,
    presence_counter_indices,
    presence_flag_write_proof,
)
from games.re2.room_data import decode_room
from games.re2.room_write_partitions import (
    EmbeddedModelResource,
    RoomWritePartitions,
    ScaWritePartition,
    SourceRange,
    sca_write_partition,
)
from games.re2.scenario_items import scenario_flags
from games.re2.script_control_limits import programs_digest
from games.re2.startup_declarations import VerifiedStartupDeclarationContract

if TYPE_CHECKING:
    from games.re2.persistent_registration import VerifiedPersistentRegistration

SCENARIO_EXECUTABLE_SHA256 = (
    "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
)
SCENARIO_CONTEXT_AUDIT = "slus00748-resident-scenario-v1"
SCENARIO_ENTRY_AUDIT = "slus00748-scenario-entry-v1"
SCENARIO_NATIVE_WORK_AUDIT = "slus00748-initialized-native-work-v1"
SCENARIO_GUARD_AUDIT = "slus00748-scenario-guard-normal-engine-v1"
SCENARIO_TRUSTED_NATIVE_AUDIT = "slus00748-trusted-normal-native-work-v1"


class ScenarioSelectionFailure(Enum):
    NativeContract = "unsupported scenario-selection native contract"
    SourceBinding = "scenario-selection source binding mismatch"
    EntryScope = "scenario-selection native entry scope is unproved"
    SourceMutation = "scenario-selection source can change protected data"
    CameraWrite = "scenario-selection camera write is unbounded"
    Control = "scenario-selection query control is unsupported"


class ScenarioSelectionSupport(Enum):
    Unaudited = "unaudited"


@dataclass(frozen=True)
class ScenarioContextLayout:
    status_address: int
    scenario_mask: int
    fixed_flags: tuple[tuple[int, int, int], ...]
    reset_mask: int
    work_address: int

    def __post_init__(self) -> None:
        assert type(self.status_address) is int and self.status_address == 0x800CFBD8
        assert type(self.scenario_mask) is int and self.scenario_mask == 0xC0000000
        assert type(self.fixed_flags) is tuple and all(
            type(row) is tuple
            and len(row) == 3
            and all(type(value) is int for value in row)
            for row in self.fixed_flags
        )
        assert self.fixed_flags == ((1, 0, 0), (1, 1, 0))
        assert type(self.reset_mask) is int and self.reset_mask == 0x1000
        assert type(self.work_address) is int and self.work_address == 0x800CE32C


@dataclass(frozen=True)
class VerifiedScenarioContext:
    audit: str
    declaration_contract: VerifiedStartupDeclarationContract
    status_address: int
    scenario_mask: int
    fixed_flags: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        assert self.audit == SCENARIO_CONTEXT_AUDIT
        assert isinstance(self.declaration_contract, VerifiedStartupDeclarationContract)
        assert self.declaration_contract.executable_sha256 == SCENARIO_EXECUTABLE_SHA256
        ScenarioContextLayout(
            self.status_address,
            self.scenario_mask,
            self.fixed_flags,
            0x1000,
            0x800CE32C,
        )


@dataclass(frozen=True)
class _ScenarioScopeBinding:
    audit: str
    native_domain_audit: str
    executable_sha256: str
    source_sha256: str
    programs_sha256: str
    protected_programs: frozenset[str]
    entry_locations: frozenset[tuple[str, int]]

    def __post_init__(self) -> None:
        assert self.executable_sha256 == SCENARIO_EXECUTABLE_SHA256
        assert all(
            type(value) is str
            and len(value) == 64
            and all(char in "0123456789abcdef" for char in value)
            for value in (self.source_sha256, self.programs_sha256)
        )
        assert type(self.protected_programs) is frozenset and self.protected_programs
        assert all(type(key) is str for key in self.protected_programs)
        assert type(self.entry_locations) is frozenset and all(
            type(row) is tuple
            and len(row) == 2
            and row[0] in self.protected_programs
            and type(row[1]) is int
            and row[1] >= 0
            for row in self.entry_locations
        )
        assert {key for key, _ in self.entry_locations} == self.protected_programs

    def matches_source(self, data: bytes, programs: dict) -> bool:
        return (
            hashlib.sha256(data).hexdigest() == self.source_sha256
            and programs_digest(programs) == self.programs_sha256
        )


@dataclass(frozen=True)
class VerifiedScenarioEntryScope(_ScenarioScopeBinding):
    def __post_init__(self) -> None:
        super().__post_init__()
        assert self.audit == SCENARIO_ENTRY_AUDIT
        assert self.native_domain_audit == SCENARIO_NATIVE_WORK_AUDIT


@dataclass(frozen=True)
class VerifiedScenarioGuardScope(_ScenarioScopeBinding):
    """Source guard isolation while trusting normal unmodified native execution.

    This is a distinct type because scenario exclusion must not silently grant
    the stricter entry capability consumed by positive-presence compilers.
    """

    def __post_init__(self) -> None:
        super().__post_init__()
        assert self.audit == SCENARIO_GUARD_AUDIT
        assert self.native_domain_audit == SCENARIO_TRUSTED_NATIVE_AUDIT


@dataclass(frozen=True)
class ScenarioItemVariant:
    global_id: int
    offsets: tuple[int, ...]

    def __post_init__(self) -> None:
        assert type(self.global_id) is int and 0 <= self.global_id < 256
        assert (
            type(self.offsets) is tuple
            and self.offsets
            and self.offsets == tuple(sorted(set(self.offsets)))
            and all(type(offset) is int and offset >= 0 for offset in self.offsets)
        )


@dataclass(frozen=True)
class ScopedScenarioItems:
    absent_item_ids: tuple[int, ...]
    item_variants: tuple[ScenarioItemVariant, ...]

    def __post_init__(self) -> None:
        assert type(self.absent_item_ids) is tuple
        assert self.absent_item_ids == tuple(sorted(set(self.absent_item_ids)))
        assert all(type(gid) is int and 0 <= gid < 256 for gid in self.absent_item_ids)
        assert type(self.item_variants) is tuple and all(
            isinstance(variant, ScenarioItemVariant) for variant in self.item_variants
        )
        gids = tuple(variant.global_id for variant in self.item_variants)
        assert gids == tuple(sorted(set(gids)))
        assert not set(gids) & set(self.absent_item_ids)


def scenario_context_layout(
    profile: dict,
) -> ScenarioContextLayout | ScenarioSelectionFailure:
    """Validate profile ABI only; this is not a verified native capability."""
    assert type(profile) is dict
    try:
        layout = profile["runtime_layout"]
        status_banks = [
            row
            for row in profile["flag_banks"]
            if type(row["bank"]) is int and row["bank"] == 1
        ]
        if (
            profile["executable_identity"].rpartition(" SHA256 ")[2]
            != SCENARIO_EXECUTABLE_SHA256
            or int(layout["status_flags_address_ps1"], 0) != 0x800CFBD8
            or len(status_banks) != 1
            or int(status_banks[0]["address_ps1"], 0) != 0x800CFBD8
            or type(status_banks[0]["width"]) is not int
            or status_banks[0]["width"] != 4
            or type(layout["scenario_reset_mask"]) is not int
            or layout["scenario_reset_mask"] != 0x1000
            or int(layout["scenario_work_address_ps1"], 0) != 0x800CE32C
            or type(layout["scenario_mask"]) is not int
            or layout["scenario_mask"] & 0xC0000000 != 0xC0000000
            or type(layout["scenario_value"]) is not int
            or layout["scenario_value"] & 0xC0000000
        ):
            return ScenarioSelectionFailure.NativeContract
        fixed = tuple(
            (row["bank"], row["bit"], row["expected"])
            for row in scenario_flags(profile)
            if row["bank"] == 1 and row["bit"] in (0, 1)
        )
        if fixed != ((1, 0, 0), (1, 1, 0)):
            return ScenarioSelectionFailure.NativeContract
        return ScenarioContextLayout(0x800CFBD8, 0xC0000000, fixed, 0x1000, 0x800CE32C)
    except (KeyError, IndexError, TypeError, ValueError):
        return ScenarioSelectionFailure.NativeContract


def bind_scenario_context(
    profile: dict, declaration_contract: VerifiedStartupDeclarationContract
) -> VerifiedScenarioContext | ScenarioSelectionFailure:
    """Select the inspected native residency recipe, without a source PC proof."""
    assert type(profile) is dict
    assert isinstance(declaration_contract, VerifiedStartupDeclarationContract)
    layout = scenario_context_layout(profile)
    if (
        not isinstance(layout, ScenarioContextLayout)
        or declaration_contract.executable_sha256 != SCENARIO_EXECUTABLE_SHA256
        or declaration_contract.flag_addresses[1] != layout.status_address
    ):
        return ScenarioSelectionFailure.NativeContract
    # Soft reset changes STATUS before clearing active/acquisition state.
    # Runtime admission must enforce this recipe's reset and work-owner guards.
    return VerifiedScenarioContext(
        SCENARIO_CONTEXT_AUDIT,
        declaration_contract,
        layout.status_address,
        layout.scenario_mask,
        layout.fixed_flags,
    )


class _InvalidSelection(Exception):
    def __init__(self, failure: ScenarioSelectionFailure):
        self.failure = failure


@dataclass(frozen=True)
class SourceRecordWriteWitnesses:
    reads: tuple[SourceRange, ...]
    writes: tuple[SourceRange, ...]

    def __post_init__(self) -> None:
        assert all(
            type(regions) is tuple
            and all(isinstance(row, SourceRange) for row in regions)
            for regions in (self.reads, self.writes)
        )


def camera_record_write_witnesses(
    data: bytes, room: dict
) -> SourceRecordWriteWitnesses | ScenarioSelectionFailure:
    """Bound 4B swaps and every possible 61 first match after those swaps."""
    try:
        sections = tuple(room["section_offsets"])
        if (
            len(data) < 100
            or sections != struct.unpack_from("<23I", data, 8)
            or hashlib.sha256(data).hexdigest() != room["sha256"]
        ):
            return ScenarioSelectionFailure.SourceBinding
        commands = [
            row
            for program in room["programs"].values()
            for row in program["commands"]
            if row["opcode"] in (0x4B, 0x61)
        ]
        if not commands:
            return SourceRecordWriteWitnesses((), ())
        start = sections[8]
        end = min((offset for offset in sections if offset > start), default=len(data))
        if not 100 <= start < end <= len(data):
            return ScenarioSelectionFailure.CameraWrite
        records, cursor = [], start
        while cursor + 4 <= end:
            # Native 4B stops before primary camera FF. A bounded 61 must find
            # its camera before this sentinel, even though 61 has no stop test.
            if data[cursor + 2] == 0xFF:
                break
            if cursor + 20 > end:
                return ScenarioSelectionFailure.CameraWrite
            records.append(cursor)
            cursor += 20
        else:
            return ScenarioSelectionFailure.CameraWrite
        identities = {data[at + 2] for at in records}
        components = {identity: {identity} for identity in identities}
        swaps = []
        for row in commands:
            if row["opcode"] != 0x4B:
                continue
            packet = data[row["offset"] : row["next"]]
            if len(packet) != 3 or packet[0] != 0x4B:
                return ScenarioSelectionFailure.SourceBinding
            first, second = packet[1:]
            if (
                first not in identities
                or second not in identities
                or first >= room["cameras"]
                or second >= room["cameras"]
            ):
                return ScenarioSelectionFailure.CameraWrite
            merged = components[first] | components[second]
            for identity in merged:
                components[identity] = merged
            swaps.append(row)
        # Transpositions preserve the label set and sentinel. The optional
        # Cut_chg(second) therefore retains a real first match after any swap.
        writes = [SourceRange(at + 2, 2) for at in records] if swaps else []
        for row in commands:
            if row["opcode"] != 0x61:
                continue
            packet = data[row["offset"] : row["next"]]
            if len(packet) != 4 or packet[0] != 0x61:
                return ScenarioSelectionFailure.SourceBinding
            if packet[1] not in identities:
                return ScenarioSelectionFailure.CameraWrite
            # Every occurrence of one label is renamed together. A possible
            # first match is an original first occurrence in its component.
            matches = {
                next(index for index, at in enumerate(records) if data[at + 2] == label)
                for label in components[packet[1]]
            }
            if any(match + packet[2] >= len(records) for match in matches):
                return ScenarioSelectionFailure.CameraWrite
            writes.extend(
                SourceRange(records[match + packet[2]], 1) for match in sorted(matches)
            )
        return SourceRecordWriteWitnesses(
            tuple(SourceRange(at + 2, 1) for at in (*records, cursor)), tuple(writes)
        )
    except (KeyError, TypeError, ValueError, IndexError, struct.error):
        return ScenarioSelectionFailure.SourceBinding


def floor_flag_write_witnesses(
    data: bytes, room: dict
) -> SourceRecordWriteWitnesses | ScenarioSelectionFailure:
    """Bound native 38's counted floor records and flags halfword."""
    try:
        sections = tuple(room["section_offsets"])
        if (
            len(data) < 100
            or sections != struct.unpack_from("<23I", data, 8)
            or hashlib.sha256(data).hexdigest() != room["sha256"]
        ):
            return ScenarioSelectionFailure.SourceBinding
        commands = [
            row
            for p in room["programs"].values()
            for row in p["commands"]
            if row["opcode"] == 0x38
        ]
        if not commands:
            return SourceRecordWriteWitnesses((), ())
        start = sections[11]
        end = min((offset for offset in sections if offset > start), default=len(data))
        if not 100 <= start <= end - 4 or start % 2:
            return ScenarioSelectionFailure.SourceMutation
        count = struct.unpack_from("<H", data, start)[0]
        if start + 4 + count * 12 > end:
            return ScenarioSelectionFailure.SourceMutation
        writes = []
        for row in commands:
            packet = data[row["offset"] : row["next"]]
            if len(packet) != 3 or packet[0] != 0x38:
                return ScenarioSelectionFailure.SourceBinding
            if packet[1] >= count:
                # Native 38 checks this unsigned index before storing. This
                # exact no-op still advances PC and does not change a flag.
                continue
            writes.append(SourceRange(start + 12 + packet[1] * 12, 2))
        return SourceRecordWriteWitnesses((SourceRange(start, 2),), tuple(writes))
    except (KeyError, TypeError, ValueError, IndexError, struct.error):
        return ScenarioSelectionFailure.SourceBinding


@dataclass(frozen=True)
class ScenarioSourceWriteWitnesses:
    partitions: RoomWritePartitions
    copies: tuple[SourceCopyWrite, ...]
    record_reads: tuple[SourceRange, ...]
    record_writes: tuple[SourceRange, ...]

    def __post_init__(self) -> None:
        assert isinstance(self.partitions, RoomWritePartitions)
        assert type(self.copies) is tuple and all(
            isinstance(row, SourceCopyWrite) for row in self.copies
        )
        assert all(
            type(rows) is tuple and all(isinstance(row, SourceRange) for row in rows)
            for rows in (self.record_reads, self.record_writes)
        )


def scenario_source_write_witnesses(
    data: bytes, room: dict, profile: dict
) -> ScenarioSourceWriteWitnesses | ScenarioSelectionFailure:
    """Share explicit source-directed bounds; grant no native entry authority."""
    from games.re2.room_entry_contract import (
        RoomEntryContractConfig,
        room_entry_contract,
    )
    from games.re2.room_write_partitions import (
        RoomWritePartitionConfig,
        room_write_partitions,
    )

    try:
        recipe = room_entry_contract(profile)
        if not isinstance(recipe, RoomEntryContractConfig):
            return ScenarioSelectionFailure.NativeContract
        layout = recipe.write_partitions
        partitions = room_write_partitions(
            data,
            room,
            RoomWritePartitionConfig(
                int(layout.aot_address_ps1, 0),
                layout.aot_capacity,
                int(layout.object_address_ps1, 0),
                layout.object_capacity,
                layout.item_flag_count,
                layout.interaction_flag_count,
            ),
        )
        if not isinstance(partitions, RoomWritePartitions):
            return ScenarioSelectionFailure.SourceMutation
        camera = camera_record_write_witnesses(data, room)
        if isinstance(camera, ScenarioSelectionFailure):
            return camera
        floor = floor_flag_write_witnesses(data, room)
        if isinstance(floor, ScenarioSelectionFailure):
            return floor
        reads, writes = (*camera.reads, *floor.reads), (*camera.writes, *floor.writes)
        rows = [
            (key, row)
            for key, program in room["programs"].items()
            for row in program["commands"]
        ]
        copies = []
        for key, row in rows:
            if row["opcode"] != 0x1D:
                continue
            packet = data[row["offset"] : row["next"]]
            target, width = row["next"] + packet[2], 2 if packet[3] else 1
            if target + width > partitions.heap_floor or any(
                target < read.offset + read.width and read.offset < target + width
                for read in reads
            ):
                return ScenarioSelectionFailure.SourceMutation
            copies.append(SourceCopyWrite((key, row["offset"]), target, width))
        assets = [
            region
            for model in partitions.objects
            if isinstance(model.model, EmbeddedModelResource)
            for region in (model.model.directory_entry, model.model.asset)
        ]
        for _, row in rows:
            if row["opcode"] == 0x37:
                collision = sca_write_partition(
                    data, tuple(room["section_offsets"]), row["offset"]
                )
                if not isinstance(collision, ScaWritePartition):
                    return ScenarioSelectionFailure.SourceMutation
                assets.append(collision.asset)
        if any(
            write.offset < region.offset + region.width
            and region.offset < write.offset + write.width
            for write in writes
            for region in (*partitions.protected_source, *assets)
        ):
            return ScenarioSelectionFailure.SourceMutation
        if any(
            write.offset < read.offset + read.width
            and read.offset < write.offset + write.width
            for source_write in partitions.source_writes
            for write in source_write.writes
            for read in reads
        ):
            return ScenarioSelectionFailure.SourceMutation
        if any(
            write.offset < read.offset + read.width
            and read.offset < write.offset + write.width
            for writers, readers in (
                (camera.writes, floor.reads),
                (floor.writes, camera.reads),
            )
            for write in writers
            for read in readers
        ):
            return ScenarioSelectionFailure.SourceMutation
        return ScenarioSourceWriteWitnesses(
            partitions, tuple(copies), tuple(reads), tuple(writes)
        )
    except (KeyError, TypeError, ValueError, IndexError, struct.error):
        return ScenarioSelectionFailure.SourceBinding


def scoped_scenario_items(
    data: bytes,
    room: dict,
    profile: dict,
    context: VerifiedScenarioContext,
    entry_scope: VerifiedScenarioEntryScope | VerifiedScenarioGuardScope,
    *,
    registration: VerifiedPersistentRegistration
    | ScenarioSelectionSupport = ScenarioSelectionSupport.Unaudited,
) -> ScopedScenarioItems | ScenarioSelectionFailure:
    """Select identities after the native context and source guard checks."""
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert isinstance(context, VerifiedScenarioContext)
    assert isinstance(
        entry_scope, (VerifiedScenarioEntryScope, VerifiedScenarioGuardScope)
    )

    def require(condition: bool, failure=ScenarioSelectionFailure.SourceBinding):
        if not condition:
            raise _InvalidSelection(failure)

    try:
        # Import locally because registration consumes the shared positive
        # compiler, which itself uses this module's source-write witnesses.
        from games.re2.persistent_registration import VerifiedPersistentRegistration

        assert (
            registration is ScenarioSelectionSupport.Unaudited
            or type(registration) is VerifiedPersistentRegistration
        )
        refined = type(registration) is VerifiedPersistentRegistration
        if refined:
            require(
                registration.matches(data, room, profile, context.declaration_contract)
            )
            require(
                entry_scope.protected_programs == registration.prefix.protected_programs
                and entry_scope.entry_locations == registration.prefix.entry_locations,
                ScenarioSelectionFailure.EntryScope,
            )
        require(
            bind_scenario_context(profile, context.declaration_contract) == context,
            ScenarioSelectionFailure.NativeContract,
        )
        # The selector's route capability covers stage zero. Its independently
        # hashed source corpus also binds later-stage identities; this grants
        # neither an incoming-door nor native-entry capability for those stages.
        witnesses = context.declaration_contract.selection.sources
        require(
            type(room["stage"]) is int
            and type(room["room"]) is int
            and room["id"] == f"{room['stage']:02x}-{room['room']:02x}"
            and any(
                witness.room_id == room["id"]
                and witness.path == room["source"]
                and witness.width == len(data) == room["size"]
                and witness.sha256 == room["sha256"]
                and hashlib.sha256(data).hexdigest() == witness.sha256
                for witness in witnesses
            )
        )
        programs = room["programs"]
        require(entry_scope.matches_source(data, programs))
        decoded = decode_room(
            data,
            room["source"],
            frozenset(
                (row["bank"], row["bit"]) for row in profile["presence_condition_flags"]
            ),
            presence_counter_indices(profile),
            presence_flag_write_proof(profile)[0],
        )
        require(
            all(
                decoded[field] == room[field]
                for field in (
                    "sha256",
                    "size",
                    "cameras",
                    "section_offsets",
                    "items",
                    "doors",
                    "reset_item_variants",
                    "candidate_list_complete",
                    "programs",
                )
            )
        )
        if not room["candidate_list_complete"]:
            return ScopedScenarioItems((), ())
        require(
            entry_scope.protected_programs <= programs.keys(),
            ScenarioSelectionFailure.EntryScope,
        )
        commands = {
            key: {row["offset"]: row for row in program["commands"]}
            for key, program in programs.items()
        }
        require(
            all(at in commands[key] for key, at in entry_scope.entry_locations),
            ScenarioSelectionFailure.EntryScope,
        )
        banks = {
            row["bank"]: (int(row["address_ps1"], 0), row["width"])
            for row in profile["flag_banks"]
        }
        require(
            all(
                0 <= bank < len(context.declaration_contract.flag_addresses)
                and address == context.declaration_contract.flag_addresses[bank]
                for bank, (address, _) in banks.items()
            ),
            ScenarioSelectionFailure.NativeContract,
        )
        fixed = {}
        for bank, bit, expected in context.fixed_flags:
            _, aliases = flag_write_conflicts(banks, frozenset(((bank, bit),)))
            for alias in aliases:
                require(alias not in fixed or fixed[alias] == bool(expected))
                fixed[alias] = bool(expected)
        all_rows = [(key, row) for key, p in programs.items() for row in p["commands"]]
        protected = [SourceRange(0, 100)]
        for section in (16, 17):
            table = room["section_offsets"][section]
            protected.append(
                SourceRange(table, int.from_bytes(data[table : table + 2], "little"))
            )
        targets = {}
        ordinary_origins = {
            (key, row["offset"]): data[row["offset"] + 1]
            for key, row in all_rows
            if row["kind"] in ("item", "door", "interaction")
        }
        for key, row in all_rows:
            at, op = row["offset"], row["opcode"]
            packet = data[at : row["next"]]
            protected.append(SourceRange(at, 1))
            if op in (
                1,
                3,
                4,
                5,
                6,
                7,
                8,
                0x17,
                0x18,
                0x1D,
                0x21,
                0x22,
                0x38,
                0x4B,
                0x61,
            ) or row["kind"] in ("item", "door", "interaction", "reset"):
                protected.append(SourceRange(at, len(packet)))
            if row["kind"] == "flag_write":
                require(
                    row["bank"] in banks and (row["bank"], row["bit"]) not in fixed,
                    ScenarioSelectionFailure.SourceMutation,
                )
            if row["kind"] in ("interaction", "reset") and row["interaction"] == 6:
                operand = 4 if row["kind"] == "reset" else 22 if op == 0x67 else 14
                bank, bit, _ = struct.unpack_from("<3H", packet, operand)
                require(
                    bank in banks and (bank, bit % 256) not in fixed,
                    ScenarioSelectionFailure.SourceMutation,
                )
            require(
                row["kind"] != "interaction" or row["interaction"] != 2,
                ScenarioSelectionFailure.SourceMutation,
            )
            if row["kind"] == "item":
                operand = 22 if op == 0x69 else 14
                item_type, _, gid = struct.unpack_from("<3H", packet, operand)
                require(gid < 256 and packet[1] < 32)
                targets.setdefault(gid, {})[key, at] = ("creator", item_type)
            elif row["kind"] == "reset" and row["interaction"] == 2:
                item_type, _, gid = struct.unpack_from("<3H", packet, 4)
                require(
                    gid < 256 and packet[1] < 32 and not packet[3] & 0x80,
                    ScenarioSelectionFailure.SourceMutation,
                )
                targets.setdefault(gid, {})[key, at] = ("reset", item_type)
        source_writes = scenario_source_write_witnesses(data, room, profile)
        if isinstance(source_writes, ScenarioSelectionFailure):
            return source_writes
        copy_protected = (*protected, *source_writes.record_reads)
        for copy in source_writes.copies:
            require(
                not any(
                    copy.target_offset < region.offset + region.width
                    and region.offset < copy.target_offset + copy.width
                    for region in copy_protected
                ),
                ScenarioSelectionFailure.SourceMutation,
            )
        absent, variants = [], []
        for gid, creators in sorted(targets.items()):
            scopes = {key for key, _ in creators}
            if refined:
                reset_slots = {
                    data[at + 1]
                    for (_, at), (kind, _) in creators.items()
                    if kind == "reset"
                }
                # Every ordinary/four-point origin for each Reset slot must
                # join the same all-canonical-entry walk, regardless of kind,
                # item identity, acquisition or whether startup registered it.
                scopes |= {
                    key
                    for (key, _), slot in ordinary_origins.items()
                    if slot in reset_slots
                }
            if not scopes <= entry_scope.protected_programs:
                continue
            if any(
                row["opcode"] in range(0x0D, 0x1B)
                and row["opcode"] != 0x18
                or row["opcode"] in (3, 5)
                or row["kind"] in ("if", "jump")
                and row["target"] < row["next"]
                for key in scopes
                for row in programs[key]["commands"]
            ):
                continue
            pending = [
                (key, at, ())
                for key, at in entry_scope.entry_locations
                if key in scopes
            ]
            seen, reached = set(), set()
            supported = True
            while pending and supported:
                key, at, frames = pending.pop()
                state = key, at, frames
                if state in seen:
                    continue
                seen.add(state)
                if len(seen) > 4096 or at not in commands[key]:
                    supported = False
                    break
                row = commands[key][at]
                reached.add((key, at))
                if row["kind"] == "end":
                    supported = data[at : row["next"]] == b"\x01\0"
                    continue
                if row["kind"] == "if":
                    if (
                        len(frames) >= 8
                        or row["target"] <= row["next"]
                        or row["target"] not in commands[key]
                    ):
                        supported = False
                        break
                    cursor, answers = row["next"], []
                    while cursor in commands[key]:
                        test = commands[key][cursor]
                        packet = data[cursor : test["next"]]
                        if test["kind"] == "flag_check":
                            if (
                                test["expected"] not in (0, 1)
                                or test["bank"] not in banks
                            ):
                                supported = False
                                break
                            identity = test["bank"], test["bit"]
                            answers.append(
                                fixed[identity] == bool(test["expected"])
                                if identity in fixed
                                else None
                            )
                        elif (
                            test["opcode"] == 0x23 and packet[1] == 0 and packet[3] < 7
                        ):
                            # This read-only numeric test can take either path;
                            # the query needs no invented runtime counter value.
                            answers.append(None)
                        else:
                            break
                        cursor = test["next"]
                    if not supported or not answers:
                        supported = False
                        break
                    if not any(answer is False for answer in answers):
                        pending.append((key, cursor, frames + (row["target"],)))
                    if any(answer is not True for answer in answers):
                        pending.append((key, row["target"], frames))
                elif row["opcode"] in (7, 8):
                    if not frames or row["next"] != frames[-1]:
                        supported = False
                        break
                    pending.append(
                        (
                            key,
                            row["target"] if row["opcode"] == 7 else row["next"],
                            frames[:-1],
                        )
                    )
                elif row["kind"] == "flag_check" or row["opcode"] in (
                    0x23,
                    0x3E,
                    0x50,
                    0x5E,
                    0x85,
                ):
                    # Native predicate failure consumes an owned IF target.
                    # Treating a standalone predicate as fallthrough could
                    # bypass the very guard needed to select this identity.
                    supported = False
                else:
                    packet = data[at : row["next"]]
                    if (
                        row["opcode"] == 4
                        and (
                            packet[1:3] != b"\xff\x18"
                            or f"17:{packet[3]}" not in programs
                        )
                        or row["kind"] == "call"
                        and f"17:{row['procedure']}" not in programs
                    ):
                        supported = False
                        break
                    # The entry receipt owns native PC effects. Event_exec may
                    # replace a caller, so allowing its old continuation only
                    # adds possibilities; it cannot prove event completion.
                    pending.append((key, row["next"], frames))
            if not supported:
                continue
            possible = {
                loc: value
                for loc, value in creators.items()
                if loc in reached
                and (
                    not refined
                    or value[0] == "creator"
                    or any(
                        origin in reached and slot == data[loc[1] + 1]
                        for origin, slot in ordinary_origins.items()
                    )
                )
            }
            if not possible:
                absent.append(gid)
                continue
            possible_types = {value[1] for value in possible.values()}
            if len(possible_types) != 1 or len({v[1] for v in creators.values()}) <= 1:
                continue
            offsets = tuple(
                sorted(
                    at for (key, at), (kind, _) in possible.items() if kind == "creator"
                )
            )
            if offsets:
                variants.append(ScenarioItemVariant(gid, offsets))
        return ScopedScenarioItems(tuple(absent), tuple(variants))
    except _InvalidSelection as error:
        return error.failure
    except (KeyError, TypeError, ValueError, IndexError, struct.error):
        return ScenarioSelectionFailure.SourceBinding
