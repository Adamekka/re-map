"""Audited positive startup declarations, without quantity or absence claims."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from games.re2.startup_entry_selection import (
        EntrySelectionConfig,
        EntrySelectionResource,
        VerifiedEntrySelection,
    )


class StartupDeclarationSupport(Enum):
    Unaudited = "unaudited"


class StartupDeclarationFailure(Enum):
    NativeContract = "startup declaration native contract is unproved"
    SourceBinding = "startup declaration source binding mismatch"
    SourceMutation = "startup declaration source may mutate control or identity"
    Prefix = "startup declaration prefix is unsupported"


@dataclass(frozen=True)
class StartupDeclarationReceipt:
    source_sha256: str
    programs_sha256: str
    locations: frozenset[tuple[str, int]]

    def __post_init__(self) -> None:
        assert all(
            type(value) is str
            and len(value) == 64
            and all(char in "0123456789abcdef" for char in value)
            for value in (self.source_sha256, self.programs_sha256)
        )
        assert type(self.locations) is frozenset and all(
            type(key) is str and type(offset) is int and offset >= 0
            for key, offset in self.locations
        )

    def matches_source(self, data: bytes, programs: dict) -> bool:
        return (
            hashlib.sha256(data).hexdigest() == self.source_sha256
            and hashlib.sha256(
                json.dumps(programs, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            == self.programs_sha256
        )


@dataclass(frozen=True)
class StartupDeclaration:
    global_id: int
    item_type: int
    slot: int
    creator_offsets: tuple[int, ...]

    def __post_init__(self) -> None:
        assert type(self.global_id) is int and 0 <= self.global_id < 256
        assert type(self.item_type) is int and 0 <= self.item_type < 104
        assert type(self.slot) is int and 0 <= self.slot < 32
        assert (
            type(self.creator_offsets) is tuple
            and self.creator_offsets
            and tuple(sorted(set(self.creator_offsets))) == self.creator_offsets
        )


@dataclass(frozen=True)
class VerifiedStartupDeclarationContract:
    executable_sha256: str
    source_address: int
    source_stage: int
    selection: VerifiedEntrySelection
    flag_addresses: tuple[int, ...]
    actor_model: int
    constructor_flags: frozenset[int]
    actor_parts: int
    actor_mesh_width: int
    actor_shadow_width: int
    actor_resource_width: int
    model_uv_address: int

    def __post_init__(self) -> None:
        assert type(self.executable_sha256) is str and len(self.executable_sha256) == 64
        assert (
            type(self.source_address) is int
            and 0x8011A000 <= self.source_address < 0x80198000
        )
        assert type(self.source_stage) is int and 0 <= self.source_stage <= 255
        assert self.selection.executable_sha256 == self.executable_sha256
        assert (
            type(self.flag_addresses) is tuple
            and self.flag_addresses
            and all(type(value) is int for value in self.flag_addresses)
        )
        assert type(self.actor_model) is int and 0 <= self.actor_model <= 255
        assert (
            type(self.constructor_flags) is frozenset
            and self.constructor_flags
            and all(
                type(value) is int and 0 <= value <= 65535
                for value in self.constructor_flags
            )
        )
        assert type(self.actor_parts) is int and 1 <= self.actor_parts <= 127
        assert all(
            type(value) is int and value >= 0
            for value in (
                self.actor_mesh_width,
                self.actor_shadow_width,
                self.actor_resource_width,
            )
        )
        assert (
            type(self.model_uv_address) is int
            and 0x8011A000 < self.model_uv_address < 0x801A1000
        )


def startup_declarations(
    data: bytes,
    room: dict,
    profile: dict,
    contract: VerifiedStartupDeclarationContract | StartupDeclarationSupport,
) -> tuple[StartupDeclaration, ...] | StartupDeclarationFailure:
    """Prove unconditional first declarations, without selecting a quantity."""
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert contract is StartupDeclarationSupport.Unaudited or isinstance(
        contract, VerifiedStartupDeclarationContract
    )
    if contract is StartupDeclarationSupport.Unaudited:
        return ()
    import struct

    from games.re2.event_presence import source_presence
    from games.re2.room_data import OPCODE_WIDTHS, decode_room
    from games.re2.room_write_partitions import (
        EmbeddedModelResource,
        ScaWritePartition,
        embedded_model_resource,
        sca_write_partition,
        static_object_packet,
    )

    class Invalid(Exception):
        def __init__(self, reason):
            self.reason = reason

    def require(value, reason=StartupDeclarationFailure.SourceBinding):
        if not value:
            raise Invalid(reason)

    try:
        require(
            profile["executable_identity"].rpartition(" SHA256 ")[2]
            == contract.executable_sha256,
            StartupDeclarationFailure.NativeContract,
        )
        require(
            hashlib.sha256(data).hexdigest() == room["sha256"]
            and len(data) == room["size"]
        )
        room_id = f"{room['stage']:02x}-{room['room']:02x}"
        if (
            not contract.selection.covers_source(data, room)
            or room["stage"] != contract.source_stage
            or not contract.selection.models_for(room_id)
            or not set(contract.selection.models_for(room_id)) <= {2, 0x0A}
        ):
            return ()
        sections = tuple(room["section_offsets"])
        require(len(data) >= 100 and sections == struct.unpack_from("<23I", data, 8))
        floor = sections[2]
        require(100 <= floor <= len(data) and floor % 4 == 0)
        programs = room["programs"]
        # Re-decode the exact bytes instead of trusting caller-supplied command,
        # branch, procedure and item fields. Presence-safe tags grant no rights here.
        safe_writes = frozenset(
            (r["bank"], r["bit"])
            for p in programs.values()
            for r in p["commands"]
            if r["kind"] == "flag_write" and r["presence_safe"]
        )
        safe_counters = frozenset(
            r["counter"]
            for p in programs.values()
            for r in p["commands"]
            if r["kind"] == "counter_write" and r["presence_safe"]
        )
        decoded = decode_room(
            data, room["source"], frozenset(), safe_counters, safe_writes
        )
        require(
            decoded["programs"] == programs
            and decoded["items"] == room["items"]
            and decoded["candidate_list_complete"]
        )
        rows = [(key, r) for key, p in programs.items() for r in p["commands"]]
        require(
            all(r["opcode"] != 0x1D for _, r in rows),
            StartupDeclarationFailure.SourceMutation,
        )
        spans = sorted(set((r["offset"], r["next"]) for _, r in rows))
        require(all(a[1] <= b[0] for a, b in zip(spans, spans[1:])))
        require(
            all(
                0 <= r["opcode"] < len(OPCODE_WIDTHS)
                and r["next"] - r["offset"] == OPCODE_WIDTHS[r["opcode"]]
                for _, r in rows
            )
        )
        protected = [(0, 100)] + spans
        for section in (16, 17):
            at = sections[section]
            require(100 <= at < floor and at + 2 <= floor)
            width = int.from_bytes(data[at : at + 2], "little")
            require(width >= 2 and width % 2 == 0 and at + width <= floor)
            protected.append((at, at + width))
        require(all(stop <= floor for _, stop in protected))
        directory = sections[10]
        if data[2]:
            require(
                100 <= directory <= floor - data[2] * 8
                and directory % 4 == 0
                and not any(
                    directory < stop and begin < directory + data[2] * 8
                    for begin, stop in protected
                )
            )
            protected.append((directory, directory + data[2] * 8))

        def disjoint(start, width):
            return not any(
                start < stop and begin < start + width for begin, stop in protected
            )

        banks = {
            r["bank"]: (int(r["address_ps1"], 0), r["width"])
            for r in profile["flag_banks"]
        }
        require(
            all(
                bank < len(contract.flag_addresses)
                and address == contract.flag_addresses[bank]
                for bank, (address, _width) in banks.items()
            ),
            StartupDeclarationFailure.NativeContract,
        )
        require(
            all(
                row["bank"] in banks and 0 <= row["bit"] < banks[row["bank"]][1] * 8
                for _, row in rows
                if row["kind"] == "flag_check"
            )
        )
        runtime = profile["runtime_layout"]
        require(
            runtime["save_block_address_ps1"] == "0x800D46D4"
            and runtime["save_block_width"] == 1792
            and runtime["aot_table_address_ps1"] == "0x800CE558"
            and runtime["aot_capacity"] == 32
            and runtime["script_counter_address_ps1"] == "0x800D47EC"
            and runtime["file_type_min"] == 104,
            StartupDeclarationFailure.NativeContract,
        )
        save = int(runtime["save_block_address_ps1"], 0)
        save_end = save + runtime["save_block_width"]
        locations, models, model_commands, model_assets, constructors = (
            set(),
            {},
            {},
            set(),
            [],
        )
        bindings = {}
        for key, row in rows:
            at, stop, op = row["offset"], row["next"], row["opcode"]
            packet = data[at:stop]
            loc = key, at
            if row["kind"] in ("item", "door", "interaction", "reset"):
                bindings.setdefault(packet[1], []).append((key, row))
            if op == 0:
                locations.add(loc)
            elif row["kind"] == "flag_write":
                bank, bit, operation = packet[1:]
                if (
                    bank in banks
                    and bit < banks[bank][1] * 8
                    and operation in (0, 1, 7)
                ):
                    address = banks[bank][0] + bit // 32 * 4
                    if save <= address <= save_end - 4:
                        locations.add(loc)
            elif (
                op == 4 and packet[1:3] == b"\xff\x18" and f"17:{packet[3]}" in programs
            ):
                # The native phase-zero allocator searches only tasks2..9.
                # Queued tasks cannot run while the current root continues.
                locations.add(loc)
            elif row["kind"] in ("item", "door", "interaction"):
                if packet[1] < 32 and (
                    row["kind"] != "interaction" or packet[2] in (0, 3, 5, 6)
                ):
                    locations.add(loc)
            elif op == 0x2D and static_object_packet(
                packet, render_flags=frozenset((0, 0x10, 0x30))
            ):
                slot = packet[1]
                entry = sections[10] + slot * 8
                if slot < min(data[2], 32) and 100 <= entry <= floor - 8:
                    model = embedded_model_resource(data, entry, floor)
                    if isinstance(model, EmbeddedModelResource) and disjoint(
                        model.asset.offset, model.asset.width
                    ):
                        require(
                            slot not in models
                            and model.asset.offset not in model_assets,
                            StartupDeclarationFailure.Prefix,
                        )
                        require(
                            not any(
                                model.asset.offset
                                < other.asset.offset + other.asset.width
                                and other.asset.offset
                                < model.asset.offset + model.asset.width
                                for other in models.values()
                            ),
                            StartupDeclarationFailure.Prefix,
                        )
                        models[slot] = model
                        model_commands[slot] = loc
                        model_assets.add(model.asset.offset)
                        locations.add(loc)
            elif (
                op == 0x44
                and packet[3] == contract.actor_model
                and packet[2] < 32
                and int.from_bytes(packet[4:6], "little") in contract.constructor_flags
                and packet[6] == 0
                and packet[8] <= 2
            ):
                constructors.append(packet[2])
                locations.add(loc)
            elif op == 0x37:
                collision = sca_write_partition(data, sections, at)
                if (
                    isinstance(collision, ScaWritePartition)
                    and disjoint(collision.asset.offset, collision.asset.width)
                    and collision.asset.offset + collision.asset.width <= floor
                ):
                    locations.add(loc)

        for key, row in rows:
            if row["opcode"] == 0x37 and (key, row["offset"]) in locations:
                collision = sca_write_partition(data, sections, row["offset"])
                assert isinstance(collision, ScaWritePartition)
                if any(
                    collision.asset.offset < model.asset.offset + model.asset.width
                    and model.asset.offset
                    < collision.asset.offset + collision.asset.width
                    for model in models.values()
                ):
                    locations.remove((key, row["offset"]))

        def called_from(root):
            reached, pending = set(), [root]
            while pending:
                key = pending.pop()
                if key in reached:
                    continue
                reached.add(key)
                pending.extend(
                    f"17:{r['procedure']}"
                    for r in programs[key]["commands"]
                    if r["kind"] == "call" and f"17:{r['procedure']}" in programs
                )
            return reached

        shared = called_from("16:0") & called_from("17:0")
        # Separate root walks cannot inherit a freshly relocated model from
        # one another. Reject a shared allocation procedure until setup history
        # is explicitly threaded across both native roots.
        require(
            not any(
                key in shared and row["opcode"] in (0x2D, 0x44) for key, row in rows
            ),
            StartupDeclarationFailure.Prefix,
        )
        require(
            len(constructors) <= 4 and len(set(constructors)) == len(constructors),
            StartupDeclarationFailure.Prefix,
        )
        model_heap = sum(
            sum(
                int.from_bytes(
                    data[
                        m.asset.offset + 12 + i * 28 + 20 : m.asset.offset
                        + 12
                        + i * 28
                        + 24
                    ],
                    "little",
                )
                * (80 if i % 2 == 0 else 104)
                for i in range(m.render_objects)
            )
            for m in models.values()
        )
        # All live actors may allocate both ordinary and shadow packets. The
        # shared model/UV and incoming Door arenas must remain separate even
        # when every constructor's acquisition guard permits allocation.
        heap_end = (
            contract.source_address
            + floor
            + model_heap
            + (contract.actor_resource_width if constructors else 0)
            + len(constructors)
            * (
                0x248
                + contract.actor_parts * 0xAC
                + contract.actor_mesh_width
                + contract.actor_shadow_width
            )
        )
        require(
            heap_end <= contract.model_uv_address < 0x801A1000,
            StartupDeclarationFailure.Prefix,
        )
        program_hash = hashlib.sha256(
            json.dumps(programs, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

        def receipt():
            return StartupDeclarationReceipt(
                room["sha256"], program_hash, frozenset(locations)
            )

        def guaranteed(targets):
            return source_presence(
                data,
                programs,
                targets,
                "declaration",
                frozenset(),
                frozenset(),
                declaration_effects=receipt(),
            ) == {"kind": "required"}

        # Reset writes through the existing registry pointer. Establish a
        # bounded root16 owner before granting that write in root17.
        initialized = {
            slot
            for slot, (key, offset) in model_commands.items()
            if key == "16:0" and guaranteed({(key, offset)})
        }
        for key, row in rows:
            at = row["offset"]
            packet = data[at : row["next"]]
            if (
                row["kind"] == "reset"
                and packet[1] < 32
                and packet[2] in (0, 1, 3, 5, 6)
            ):
                owners = [
                    (k, r) for k, r in bindings[packet[1]] if r["kind"] != "reset"
                ]
                if (
                    owners
                    and all(
                        k == "16:0" and (k, r["offset"]) in locations for k, r in owners
                    )
                    and guaranteed({(k, r["offset"]) for k, r in owners})
                ):
                    locations.add((key, at))
            if row["opcode"] == 0x2E and packet[1] == 4 and packet[2] in initialized:
                locations.add((key, at))
            if row["opcode"] == 0x34 and packet[1] == 15:
                previous = [r for r in programs[key]["commands"] if r["next"] <= at]
                while previous and previous[-1]["opcode"] == 0:
                    previous.pop()
                if previous:
                    work = previous[-1]
                    wp = data[work["offset"] : work["next"]]
                    if (
                        work["opcode"] == 0x2E
                        and wp[1] == 4
                        and wp[2] in initialized
                        and not any(
                            r.get("target", -1) in range(work["next"], at + 1)
                            for _, r in rows
                        )
                    ):
                        locations.add((key, at))
        result = []
        for gid in sorted({r["global_id"] for r in room["items"]}):
            items = [r for r in room["items"] if r["global_id"] == gid]
            identities = {(r["slot"], r["type"]) for r in items}
            if len(identities) != 1 or gid >= 256:
                continue
            slot, item_type = next(iter(identities))
            if slot >= 32 or not 0 <= item_type < runtime["file_type_min"]:
                continue
            offsets = {r["offset"] for r in items}
            if not all(
                r["kind"] == "item" and r["offset"] in offsets
                for _, r in bindings[slot]
            ):
                continue
            targets = set()
            for key, row in rows:
                if row["offset"] not in offsets:
                    continue
                packet = data[row["offset"] : row["next"]]
                if (
                    row["opcode"] != 0x4E
                    or packet[2:4] != b"\x02\x31"
                    or not all(struct.unpack_from("<2H", packet, 10))
                    or not int.from_bytes(packet[16:18], "little")
                    or packet[21] != 0
                ):
                    targets.clear()
                    break
                targets.add((key, row["offset"]))
            if targets and guaranteed(targets):
                result.append(
                    StartupDeclaration(gid, item_type, slot, tuple(sorted(offsets)))
                )
        return tuple(result)
    except Invalid as error:
        return error.reason
    except (KeyError, TypeError, ValueError, IndexError, struct.error):
        return StartupDeclarationFailure.SourceBinding


AUDITED_STARTUP_DECLARATION_SHA256 = (
    "e5b9f72f3603713364cc183ca9e4461302c0606dfaa9e620738ee3acbca73526"
)


@dataclass(frozen=True)
class StartupDeclarationAuditConfig:
    audit: str
    executable_sha256: str
    resources: tuple[EntrySelectionResource, ...]
    selection: EntrySelectionConfig

    def __post_init__(self) -> None:
        from games.re2.startup_entry_selection import (
            EntrySelectionConfig,
            EntrySelectionResource,
        )

        assert self.audit == "slus00748-startup-declarations-v1"
        assert (
            self.executable_sha256
            == "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
        )
        assert (
            type(self.resources) is tuple
            and self.resources
            and all(isinstance(row, EntrySelectionResource) for row in self.resources)
        )
        assert isinstance(self.selection, EntrySelectionConfig)
        # The generator loads this resource list before the selector binds it.
        # Keep both views identical even for directly constructed configs.
        assert self.resources == self.selection.resources
        assert self.executable_sha256 == self.selection.executable_sha256


def startup_declaration_audit(
    profile: dict,
) -> StartupDeclarationAuditConfig | StartupDeclarationSupport:
    """Require the exact native/resource/corpus audit before enabling inference."""
    if "startup_declaration_audit" not in profile:
        return StartupDeclarationSupport.Unaudited
    from games.re2.startup_entry_selection import (
        EntrySelectionConfig,
        EntrySelectionResource,
        entry_selection_config,
    )

    raw = profile["startup_declaration_audit"]
    try:
        digest = hashlib.sha256(
            json.dumps(
                raw, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        if (
            digest != AUDITED_STARTUP_DECLARATION_SHA256
            or profile["executable_identity"].rpartition(" SHA256 ")[2]
            != raw["executable_sha256"]
        ):
            raise ValueError("unsupported native startup declaration audit")
        resources = tuple(EntrySelectionResource(**row) for row in raw["resources"])
        selection = entry_selection_config(
            raw["selection"], resources, raw["executable_sha256"]
        )
        if not isinstance(selection, EntrySelectionConfig):
            raise ValueError("unsupported startup entry selection audit")
        return StartupDeclarationAuditConfig(
            raw["audit"], raw["executable_sha256"], resources, selection
        )
    except (KeyError, TypeError, ValueError, AssertionError, AttributeError) as error:
        raise ValueError("invalid RE2 startup declaration audit") from error


def bind_startup_declaration_audit(
    config: StartupDeclarationAuditConfig,
    executable: bytes,
    native_resources: dict[str, bytes],
    sources: dict[str, bytes],
) -> VerifiedStartupDeclarationContract | StartupDeclarationFailure:
    """Bind audited native entry, resource lookup and allocation dimensions."""
    assert isinstance(config, StartupDeclarationAuditConfig)
    assert (
        type(executable) is bytes
        and type(native_resources) is dict
        and type(sources) is dict
    )
    import struct

    from games.re2.startup_entry_selection import (
        VerifiedEntrySelection,
        bind_entry_selection,
    )

    selection = bind_entry_selection(
        config.selection, executable, native_resources, sources
    )
    if not isinstance(selection, VerifiedEntrySelection):
        return StartupDeclarationFailure.NativeContract
    try:

        def native(address, width):
            offset = 0x800 + address - 0x80010000
            if not 0 <= offset <= len(executable) - width:
                raise ValueError("native resource lookup is out of bounds")
            return executable[offset : offset + width]

        stage = native_resources["COMMON/BIN/STAGE1.BIN"]
        # Room_load retains the stage binary, aligned to four bytes, before
        # the RDT. Bind the loader's actual recipe and directory, not just size.
        recipe = struct.unpack("<3I", native(0x800A20B8 + 8 * 12, 12))
        directory = native(0x800988A4 + 7 * 8, 8)
        if (
            recipe != (7, 0x8011A004, 0x80010810)
            or int.from_bytes(native(0x80010810, 4), "little") != 0x8011A000
            or int.from_bytes(directory[:4], "little") != len(stage)
        ):
            return StartupDeclarationFailure.NativeContract
        source_address = 0x8011A000 + (len(stage) + 3) // 4 * 4
        archive = native_resources["PL0/PLD/CDEMD0.EMS"]

        def resource(index):
            sector, width = struct.unpack("<2I", native(0x8009ADF4 + index * 8, 8))
            start = sector * 2048
            if width < 4 or start + width > len(archive):
                raise ValueError("actor resource exceeds archive")
            return archive[start : start + width]

        for index in (0, 1, 62):
            resource(index)
        model = resource(63)
        table = int.from_bytes(model[:4], "little")
        offsets = struct.unpack_from("<8I", model, table)
        tmd = offsets[7]
        body, flags, count = struct.unpack_from("<3I", model, tmd)
        if flags or count != 34 or tmd + body > len(model):
            return StartupDeclarationFailure.NativeContract
        objects = [
            struct.unpack_from("<7I", model, tmd + 12 + i * 28) for i in range(count)
        ]
        mesh = sum(
            row[5] * (80 if i % 2 == 0 else 104) for i, row in enumerate(objects)
        )
        uv_width = sum(
            row[5] * (12 if i % 2 == 0 else 16) for i, row in enumerate(objects)
        )
        parts = count // 2
        shadow = parts * 0xAC + objects[0][0] + body - (objects[0][4] + 12) + mesh
        if not 0 <= objects[0][4] + 12 <= body or tmd + body + uv_width > len(model):
            return StartupDeclarationFailure.NativeContract
        return VerifiedStartupDeclarationContract(
            executable_sha256=config.executable_sha256,
            source_address=source_address,
            source_stage=0,
            selection=selection,
            flag_addresses=struct.unpack("<40I", native(0x800A78C8, 40 * 4)),
            actor_model=0x1F,
            constructor_flags=frozenset((0x46, 0x8046, 0x8040)),
            actor_parts=parts,
            actor_mesh_width=mesh,
            actor_shadow_width=shadow,
            actor_resource_width=tmd + body,
            model_uv_address=0x8018FFF0 - uv_width,
        )
    except (KeyError, TypeError, ValueError, IndexError, struct.error):
        return StartupDeclarationFailure.NativeContract
