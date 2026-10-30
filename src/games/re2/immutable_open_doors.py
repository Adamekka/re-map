"""Compile immutable open-door bindings from independent native write proofs."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.actor_part_proofs import actor_part_copy_proof, scenario_actor_parts
from games.re2.clip_effect_proof import clipping_effect_proof
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.nonchoice_messages import (
    NonchoiceMessageFailure,
    nonchoice_message_proofs,
)
from games.re2.room_entry_contract import VerifiedRoomEntryContract
from games.re2.room_sound_bindings import RoomSoundBindingFailure, room_sound_bindings
from games.re2.room_write_partitions import (
    EmbeddedModelResource,
    RoomWritePartitionConfig,
    RoomWritePartitions,
    SourceRange,
    room_write_partitions,
    static_object_packet,
)
from games.re2.scenario_items import (
    scenario_effect_pool,
    scenario_flags,
    scenario_item_proofs,
    scenario_vibration_writes,
)


class ImmutableOpenDoorFailure(Enum):
    InputBinding = "invalid proof inputs"
    EntryContract = "unsupported native entry contract"
    FixedContext = "source does not preserve fixed context"
    Partition = "source write partition is unproved"
    Reachability = "native source entries are not closed"
    WriteEffects = "a reached native write is unsupported"
    MutableControl = "source writes may alter control or ownership operands"
    RepeatedAllocation = "allocation is not a fresh single startup execution"
    CallbackEffects = "native interaction write effects are unproved"
    SoundBinding = "room sound writes are not bound to immutable resources"


@dataclass(frozen=True)
class ImmutableOpenDoor:
    slot: int
    creator_offsets: tuple[int, ...]
    context_conditions: list[dict]

    def __post_init__(self) -> None:
        assert type(self.slot) is int and 0 <= self.slot < 32
        assert type(self.creator_offsets) is tuple and self.creator_offsets
        assert all(
            type(offset) is int and offset >= 0 for offset in self.creator_offsets
        )
        assert tuple(sorted(set(self.creator_offsets))) == self.creator_offsets
        assert type(self.context_conditions) is list


def immutable_open_doors(
    data: bytes,
    room: dict,
    profile: dict,
    entry_contract: VerifiedRoomEntryContract,
    partition_config: RoomWritePartitionConfig,
) -> tuple[ImmutableOpenDoor, ...] | ImmutableOpenDoorFailure:
    """Require whole effect coverage before exporting a departed door fact.

    No observation is cached. The returned constructor conditions must be
    freshly enforced wherever the resulting door bindings are consumed.
    """
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert isinstance(entry_contract, VerifiedRoomEntryContract)
    assert isinstance(partition_config, RoomWritePartitionConfig)
    try:
        layout = profile["runtime_layout"]
        identity = profile.get("executable_identity")
        if (
            type(identity) is not str
            or identity.rpartition(" SHA256 ")[2] != entry_contract.executable_sha256
            or partition_config != entry_contract.write_partitions
        ):
            return ImmutableOpenDoorFailure.EntryContract
        if (
            type(room["stage"]) is not int
            or room["stage"] not in entry_contract.stages
            or (
                int(layout["aot_table_address_ps1"], 0),
                layout["aot_capacity"],
            )
            != (partition_config.aot_address, partition_config.aot_capacity)
        ):
            return ImmutableOpenDoorFailure.EntryContract
        partitions = room_write_partitions(data, room, partition_config)
        if not isinstance(partitions, RoomWritePartitions):
            return ImmutableOpenDoorFailure.Partition
        # Native file/menu graphics start at this fixed upper arena. The
        # exact stage-derived source base, not merely a lower bound, must keep
        # every retained script/model/message/sound byte below that arena.
        if not partitions.retained_before(
            dict(entry_contract.source_addresses)[room["stage"]], 0x80198000
        ):
            return ImmutableOpenDoorFailure.Partition
        fixed_rows = scenario_flags(profile)
        fixed = {(row["bank"], row["bit"]): row["expected"] for row in fixed_rows}
        banks = {
            row["bank"]: (int(row["address_ps1"], 0), row["width"])
            for row in profile["flag_banks"]
        }
        presence_flag_write_proof(profile)
        counters = presence_counter_indices(profile)
        actors = scenario_actor_parts(profile)
        context = scenario_item_proofs(
            data,
            room,
            fixed_rows,
            profile["flag_banks"],
            scenario_effect_pool(profile),
            vibration_writes=scenario_vibration_writes(profile),
            actor_parts=actors,
            clipping=clipping_effect_proof(profile),
        )
        if not context.fixed_context_preserved:
            return ImmutableOpenDoorFailure.FixedContext
        writes = actor_part_copy_proof(data, room, fixed, banks, actors)
        programs = room["programs"]
        commands = {
            key: {row["offset"]: row for row in program["commands"]}
            for key, program in programs.items()
        }
        if any(
            key not in programs
            or (key, programs[key]["entry"]) not in writes.reached_locations
            for key in entry_contract.roots
        ):
            return ImmutableOpenDoorFailure.Reachability
        reached = {
            location: commands[location[0]][location[1]]
            for location in writes.reached_locations
        }
        part_writes = {write.location for write in writes.part_writes}
        actor_writes = {write.location for write in writes.actor_writes}
        source_writes = {write.command_offset for write in partitions.source_writes}
        model_writes = {
            write.command_offset: write
            for write in partitions.objects
            if data[write.command_offset] == 0x2D
        }
        # The scalar interpreter certifies numeric/index self-modification as
        # a unit. Every other script/table/constructor/work operand stays fixed.
        if any(
            write.location[1] not in writes.offsets for write in writes.source_writes
        ):
            return ImmutableOpenDoorFailure.MutableControl
        aot_start, aot_end = (
            partition_config.aot_address,
            partition_config.aot_address + partition_config.aot_capacity * 4,
        )

        def fixed_ram_write(address: int, width: int) -> bool:
            return (
                0x80000000 <= address
                and address + width <= 0x80100000
                and (address + width <= aot_start or aot_end <= address)
            )

        call_edges = {key: [] for key in programs}
        task_roots = {"17:1"}
        native_control = {
            0,
            1,
            2,
            6,
            7,
            8,
            0x0D,
            0x0E,
            0x0F,
            0x10,
            0x11,
            0x12,
            0x21,
            0x23,
        }
        message_resources, required_sounds = [], set()
        for location, row in reached.items():
            key, position = location
            opcode = row["opcode"]
            packet = data[position : row["next"]]
            if row["kind"] == "call":
                call_edges[key].append(f"17:{row['procedure']}")
            elif opcode == 4:
                if packet[1:3] != b"\xff\x18" or f"17:{packet[3]}" not in programs:
                    return ImmutableOpenDoorFailure.Reachability
                task_roots.add(f"17:{packet[3]}")
            elif opcode == 0x1D:
                if position not in writes.offsets:
                    return ImmutableOpenDoorFailure.MutableControl
            elif opcode == 0x6E:
                if location not in part_writes:
                    return ImmutableOpenDoorFailure.WriteEffects
            elif opcode == 0x34:
                if location not in actor_writes:
                    return ImmutableOpenDoorFailure.WriteEffects
            elif opcode == 0x44:
                if not entry_contract.covers_constructor(
                    packet[3], struct.unpack_from("<H", packet, 4)[0]
                ):
                    return ImmutableOpenDoorFailure.EntryContract
            elif opcode == 0x2E:
                if packet[1] != 3 or packet[2] >= 32:
                    return ImmutableOpenDoorFailure.WriteEffects
            elif opcode == 0x2D:
                if position not in model_writes or not static_object_packet(packet):
                    return ImmutableOpenDoorFailure.WriteEffects
            elif opcode == 0x37:
                if position not in source_writes:
                    return ImmutableOpenDoorFailure.WriteEffects
            elif row["kind"] == "flag_write":
                base, width = banks[row["bank"]]
                if not 0 <= row["bit"] < width * 8 or not fixed_ram_write(
                    base + row["bit"] // 32 * 4, 4
                ):
                    return ImmutableOpenDoorFailure.WriteEffects
            elif opcode in (0x24, 0x25, 0x26):
                index = packet[3] if opcode == 0x26 else packet[1]
                if (
                    index not in counters
                    or opcode == 0x26
                    and packet[2] not in (0, 1)
                    or not fixed_ram_write(
                        int(layout["script_counter_address_ps1"], 0) + index * 2, 2
                    )
                ):
                    return ImmutableOpenDoorFailure.WriteEffects
            elif row["kind"] in ("door", "item"):
                if bool(packet[3] & 0x80) != (opcode in (0x68, 0x69)):
                    return ImmutableOpenDoorFailure.WriteEffects
                if (
                    row["kind"] == "door"
                    and packet[26 if opcode == 0x3B else 34]
                    not in entry_contract.door_models
                ):
                    return ImmutableOpenDoorFailure.EntryContract
                if row["kind"] == "item":
                    operand = 14 if opcode == 0x4E else 22
                    item_type, _, global_id = struct.unpack_from("<3H", packet, operand)
                    model = packet[operand + 6]
                    if (
                        packet[2] not in (0, 2)
                        # Native inventory types0..103 and file-table
                        # indices0..24 use the audited bounded UI controllers.
                        or item_type > 0x68 + 24
                        or packet[operand + 7] != 0
                        or global_id >= partition_config.item_flag_count
                        or model != 0xFF
                        and model >= min(data[2], partition_config.object_capacity)
                    ):
                        return ImmutableOpenDoorFailure.WriteEffects
                    if packet[2] == 2:
                        # Grant can disable its own kind byte. Original mode
                        # can also replace type30's two-byte quantity operand;
                        # both are descriptor-local data, never control fields.
                        required_sounds.update((0x14, 0x15))
            elif row["kind"] in ("interaction", "reset"):
                if (
                    row["interaction"]
                    not in entry_contract.non_scheduling_interaction_kinds
                ):
                    return ImmutableOpenDoorFailure.EntryContract
                if row["kind"] == "reset" or bool(packet[3] & 0x80) != (opcode == 0x67):
                    return ImmutableOpenDoorFailure.CallbackEffects
                payload = packet[22 if opcode == 0x67 else 14 :]
                if row["interaction"] == 4:
                    message, flags, stop = struct.unpack("<3H", payload)
                    if message > 255 or flags != 0 or stop != 0xFFFF:
                        return ImmutableOpenDoorFailure.CallbackEffects
                    proofs = nonchoice_message_proofs(
                        data, tuple(room["section_offsets"]), message
                    )
                    if isinstance(proofs, NonchoiceMessageFailure):
                        return ImmutableOpenDoorFailure.CallbackEffects
                    message_resources.extend(
                        SourceRange(proof["offset"], proof["width"]) for proof in proofs
                    )
                elif row["interaction"] == 10:
                    if payload != b"\0\0\x01\0\0\0":
                        return ImmutableOpenDoorFailure.CallbackEffects
                    # The bounded BOX controller changes object zero, fixed UI
                    # and inventory work. Its common menu temporarily binds
                    # header section9, then restores it before ordinary play.
                    # That exact header[44:48] exception is not a script/table,
                    # constructor, sound or selected-door mutation.
                    required_sounds.update((0x14, 0x15))
                else:
                    if position not in source_writes:
                        return ImmutableOpenDoorFailure.CallbackEffects
                    # Kind13's item candidates, fixed object records and RVD
                    # coordinates are bounded by the partition. Native grant
                    # can clear only that selected creator's kind byte; this
                    # disables kind2 and cannot manufacture a script callback.
                    target = struct.unpack_from("<H", payload, 2)[0]
                    if any(
                        data[item["offset"] + 1] == target and item["kind"] != "item"
                        for program in programs.values()
                        for item in program["commands"]
                        if item["kind"] in ("door", "item", "interaction", "reset")
                    ):
                        return ImmutableOpenDoorFailure.CallbackEffects
                    required_sounds.update((0x27, 0x28))
            elif opcode not in native_control:
                return ImmutableOpenDoorFailure.WriteEffects

        def overlaps(first: SourceRange, second: SourceRange) -> bool:
            return (
                first.offset < second.offset + second.width
                and second.offset < first.offset + first.width
            )

        mutable_resources = [
            region for write in partitions.source_writes for region in write.writes
        ]
        mutable_resources.extend(
            SourceRange(write.target_offset, write.width)
            for write in writes.source_writes
        )
        model_assets = [
            write.model.asset
            for write in partitions.objects
            if isinstance(write.model, EmbeddedModelResource)
        ]
        if any(
            resource.offset + resource.width > partitions.heap_floor
            or any(
                overlaps(resource, protected)
                for protected in (
                    *partitions.protected_source,
                    *mutable_resources,
                    *model_assets,
                )
            )
            for resource in message_resources
        ):
            return ImmutableOpenDoorFailure.CallbackEffects
        if required_sounds:
            sections = room["section_offsets"]
            # SOURCE001 compaction is the only later sound-pointer writer.
            # Its native null-section22 path returns without logical writes;
            # source/control immutability preserves that room-lifetime premise.
            if sections[22] or any(row["opcode"] == 0x6C for row in reached.values()):
                return ImmutableOpenDoorFailure.SoundBinding
            sound = room_sound_bindings(
                data, tuple(sections), partitions.heap_floor, frozenset(required_sounds)
            )
            if isinstance(sound, RoomSoundBindingFailure):
                return ImmutableOpenDoorFailure.SoundBinding
            if any(
                overlaps(resource, protected)
                for resource in (*sound.resources, *sound.tone_writes)
                for protected in (
                    *partitions.protected_source,
                    *mutable_resources,
                    *model_assets,
                    *message_resources,
                )
            ):
                return ImmutableOpenDoorFailure.SoundBinding

        def descendants(roots: set[str]) -> set[str]:
            pending, seen = list(roots), set()
            while pending:
                key = pending.pop()
                if key not in seen:
                    seen.add(key)
                    pending.extend(call_edges[key])
            return seen

        model_programs = {key for key, position in reached if position in model_writes}
        constructor_locations = [
            location for location, row in reached.items() if row["opcode"] == 0x44
        ]
        constructor_slots = [
            data[position + 2] for _, position in constructor_locations
        ]
        if len(set(constructor_slots)) != len(constructor_slots):
            return ImmutableOpenDoorFailure.RepeatedAllocation
        allocation_programs = model_programs | {key for key, _ in constructor_locations}
        if allocation_programs & descendants(task_roots):
            return ImmutableOpenDoorFailure.RepeatedAllocation
        model_assets = [
            model_writes[position].model.asset
            for key, position in reached
            if position in model_writes
            and isinstance(model_writes[position].model, EmbeddedModelResource)
        ]
        if len(set(model_assets)) != len(model_assets):
            return ImmutableOpenDoorFailure.RepeatedAllocation
        pending = [(key, frozenset()) for key in entry_contract.roots[:2]]
        visits = {}
        while pending:
            key, active = pending.pop()
            if key in active or sum(visits.values()) >= 1024:
                return ImmutableOpenDoorFailure.RepeatedAllocation
            visits[key] = visits.get(key, 0) + 1
            if allocation_programs & descendants({key}) and any(
                row["opcode"] in range(0x0D, 0x18)
                for location, row in reached.items()
                if location[0] == key
            ):
                return ImmutableOpenDoorFailure.RepeatedAllocation
            pending.extend((child, active | {key}) for child in call_edges[key])
        if any(visits.get(key, 0) != 1 for key in allocation_programs):
            return ImmutableOpenDoorFailure.RepeatedAllocation

        # A deterministic startup prefix proves creation before a later event
        # can suspend. Unknown predicates stop this sufficient proof; graph
        # reachability alone never establishes a current registered door.
        key, position = (
            entry_contract.roots[0],
            programs[entry_contract.roots[0]]["entry"],
        )
        prefix, seen = set(), set()
        while position not in seen and (key, position) in reached:
            seen.add(position)
            row = commands[key][position]
            if row["kind"] == "if":
                following, tests = row["next"], []
                while (
                    following in commands[key]
                    and commands[key][following]["kind"] == "flag_check"
                ):
                    test = commands[key][following]
                    tests.append(test)
                    following = test["next"]
                if not tests or any(
                    (test["bank"], test["bit"]) not in fixed for test in tests
                ):
                    break
                matches = all(
                    fixed[test["bank"], test["bit"]] == test["expected"]
                    for test in tests
                )
                if (
                    matches
                    and following in commands[key]
                    and commands[key][following]["opcode"] in (0x23, 0x3E, 0x50, 0x5E)
                ):
                    break
                position = following if matches else row["target"]
                continue
            if row["opcode"] == 7:
                position = row["target"]
                continue
            if (
                row["kind"] == "end"
                or row["kind"] == "call"
                or row["opcode"] in (2, 4)
                or row["opcode"] in range(0x0D, 0x18)
            ):
                break
            prefix.add(position)
            position = row["next"]

        conditions = list(context.context_conditions)
        conditions.extend(
            condition
            for condition in writes.write_context_conditions
            if condition not in conditions
        )
        bindings = {}
        for program in programs.values():
            for row in program["commands"]:
                if row["kind"] in ("door", "item", "interaction", "reset"):
                    bindings.setdefault(data[row["offset"] + 1], []).append(row)
        result = []
        for slot, creators in sorted(bindings.items()):
            if any(row["kind"] != "door" or row["opcode"] != 0x3B for row in creators):
                continue
            packets = {data[row["offset"] : row["next"]] for row in creators}
            if len(packets) != 1 or not any(
                row["offset"] in prefix for row in creators
            ):
                continue
            packet = next(iter(packets))
            if packet[3] != 0x31 or packet[29:31] != b"\0\0":
                continue
            result.append(
                ImmutableOpenDoor(
                    slot,
                    tuple(sorted(row["offset"] for row in creators)),
                    list(conditions),
                )
            )
        return tuple(result)
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return ImmutableOpenDoorFailure.InputBinding
