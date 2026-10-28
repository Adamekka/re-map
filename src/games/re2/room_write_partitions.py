"""Native room write regions, without entry, relocation freshness or activation proof.

Callers must separately establish which commands can execute and when an embedded
model is freshly loaded. This models retained source and fixed object records;
flags, task/global work and heap allocations remain obligations of other proofs.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.room_data import OPCODE_WIDTHS


@dataclass(frozen=True)
class SourceRange:
    offset: int
    width: int

    def __post_init__(self) -> None:
        assert type(self.offset) is int and self.offset >= 0
        assert type(self.width) is int and self.width > 0


@dataclass(frozen=True)
class RamRange:
    address: int
    width: int

    def __post_init__(self) -> None:
        assert type(self.address) is int and type(self.width) is int
        assert self.width > 0 and 0x80000000 <= self.address
        assert self.address + self.width <= 0x80200000


@dataclass(frozen=True)
class RoomWritePartitionConfig:
    aot_address: int
    aot_capacity: int
    object_address: int
    object_capacity: int
    item_flag_count: int
    interaction_flag_count: int

    def __post_init__(self) -> None:
        assert all(
            type(value) is int and 1 <= value <= 256
            for value in (self.aot_capacity, self.object_capacity)
        )
        assert all(
            type(value) is int and value % 32 == 0 and 32 <= value <= 65536
            for value in (self.item_flag_count, self.interaction_flag_count)
        )
        # Native 2D indexes 0x1F8-byte fixed object records. The room loader
        # places its source at or above 0x8011A000, beyond these fixed arrays.
        fixed = (
            RamRange(self.aot_address, self.aot_capacity * 4),
            RamRange(self.object_address, self.object_capacity * 0x1F8),
        )
        assert all(row.address % 4 == 0 for row in fixed)
        assert all(row.address + row.width <= 0x8011A000 for row in fixed)
        assert (
            fixed[0].address + fixed[0].width <= fixed[1].address
            or fixed[1].address + fixed[1].width <= fixed[0].address
        ), "fixed object records and AOT pointers must not overlap"


class RoomWritePartitionFailure(Enum):
    SourceBinding = "source binding mismatch"
    ScriptLayout = "invalid script layout"
    HeapBoundary = "invalid retained-source boundary"
    SourceOverlap = "native source write overlaps another region"
    ObjectModel = "unsupported embedded model layout"
    Collision = "invalid collision write"
    CameraTrigger = "unsupported camera trigger target or volume"


class ModelResourceState(Enum):
    Absent = "absent"
    NotAccessed = "not accessed"


@dataclass(frozen=True)
class EmbeddedModelResource:
    directory_entry: SourceRange
    asset: SourceRange
    render_objects: int
    writes: tuple[SourceRange, ...]


@dataclass(frozen=True)
class ObjectWritePartition:
    command_offset: int
    slot: int
    record: RamRange
    model: EmbeddedModelResource | ModelResourceState


@dataclass(frozen=True)
class SourceWritePartition:
    command_offset: int
    opcode: int
    writes: tuple[SourceRange, ...]


@dataclass(frozen=True)
class ScaWritePartition:
    asset: SourceRange
    write: SourceRange


@dataclass(frozen=True)
class RoomWritePartitions:
    heap_floor: int
    protected_source: tuple[SourceRange, ...]
    door_creators: tuple[SourceRange, ...]
    objects: tuple[ObjectWritePartition, ...]
    source_writes: tuple[SourceWritePartition, ...]


class _InvalidPartition(Exception):
    def __init__(self, reason: RoomWritePartitionFailure):
        self.reason = reason


def sca_write_partition(
    data: bytes, section_offsets: tuple[int, ...], command_offset: int
) -> ScaWritePartition | RoomWritePartitionFailure:
    """Bound native 37's asset/store; callers supply their own protected domains."""
    assert type(data) is bytes and type(section_offsets) is tuple
    assert len(section_offsets) == 23 and all(
        type(row) is int for row in section_offsets
    )
    assert type(command_offset) is int and command_offset >= 0
    if len(data) < 100 or section_offsets != struct.unpack_from("<23I", data, 8):
        return RoomWritePartitionFailure.SourceBinding
    if command_offset + 4 > len(data) or data[command_offset] != 0x37:
        return RoomWritePartitionFailure.Collision
    collision = section_offsets[6]
    if not collision or collision % 4 or collision + 16 > len(data):
        return RoomWritePartitionFailure.Collision
    count = struct.unpack_from("<I", data, collision + 4)[0]
    limit = min([value for value in section_offsets if value > collision] + [len(data)])
    # Native 37 skips the 16-byte SCA header. Its count includes that header,
    # so count-2 is the final record index and only its flags halfword is stored.
    index = data[command_offset + 1]
    if count < 1 or index >= count - 1 or collision + count * 16 > limit:
        return RoomWritePartitionFailure.Collision
    return ScaWritePartition(
        SourceRange(collision, count * 16),
        SourceRange(collision + (index + 1) * 16 + 8, 2),
    )


def room_write_partitions(
    data: bytes, room: dict, config: RoomWritePartitionConfig
) -> RoomWritePartitions | RoomWritePartitionFailure:
    """Validate the audited write classes in the supplied decoded source.

    No command is declared reachable, an AOT active or a model safe to relocate
    twice. In particular, an unchanged embedded-model pointer is not freshness.
    """
    assert type(data) is bytes and type(room) is dict
    assert isinstance(config, RoomWritePartitionConfig)

    def require(condition: bool, reason: RoomWritePartitionFailure) -> None:
        if not condition:
            raise _InvalidPartition(reason)

    def overlaps(first: SourceRange, second: SourceRange) -> bool:
        return (
            first.offset < second.offset + second.width
            and second.offset < first.offset + first.width
        )

    try:
        require(
            len(data) >= 100
            and type(room["programs"]) is dict
            and room["size"] == len(data)
            and room["sha256"] == hashlib.sha256(data).hexdigest(),
            RoomWritePartitionFailure.SourceBinding,
        )
        sections = struct.unpack_from("<23I", data, 8)
        require(
            list(sections) == room["section_offsets"]
            and all(not offset or 100 <= offset <= len(data) for offset in sections),
            RoomWritePartitionFailure.SourceBinding,
        )
        # 4A30C..4A324 resets GFreeWork to relocated RDT+0x10, section 2.
        # The rest of the disc file can be reclaimed; file size is not its floor.
        floor = sections[2]
        require(
            floor >= 100 and floor % 4 == 0 and floor <= len(data),
            RoomWritePartitionFailure.HeapBoundary,
        )

        def limit(offset: int) -> int:
            return min([value for value in sections if value > offset] + [len(data)])

        protected = [SourceRange(0, 100)]
        commands = []
        expected_programs = set()
        for section in (16, 17):
            begin = sections[section]
            require(
                100 <= begin < floor and begin + 2 <= len(data),
                RoomWritePartitionFailure.ScriptLayout,
            )
            end = limit(begin)
            table_width = struct.unpack_from("<H", data, begin)[0]
            require(
                end <= floor
                and table_width >= 2
                and table_width % 2 == 0
                and begin + table_width < end,
                RoomWritePartitionFailure.ScriptLayout,
            )
            entries = struct.unpack_from(f"<{table_width // 2}H", data, begin)
            require(
                entries[0] == table_width
                and list(entries) == sorted(set(entries))
                and all(begin + entry < end for entry in entries),
                RoomWritePartitionFailure.ScriptLayout,
            )
            protected.append(SourceRange(begin, end - begin))
            for index, entry in enumerate(entries):
                key = f"{section}:{index}"
                expected_programs.add(key)
                program = room["programs"][key]
                start = begin + entry
                stop = begin + entries[index + 1] if index + 1 < len(entries) else end
                require(
                    program["entry"] == start and program["limit"] == stop,
                    RoomWritePartitionFailure.ScriptLayout,
                )
                seen = set()
                spans = []
                for row in program["commands"]:
                    position, following, opcode = (
                        row["offset"],
                        row["next"],
                        row["opcode"],
                    )
                    require(
                        type(position) is int
                        and type(following) is int
                        and type(opcode) is int
                        and start <= position < following <= stop
                        and 0 <= opcode < len(OPCODE_WIDTHS)
                        and following - position == OPCODE_WIDTHS[opcode]
                        and data[position] == opcode
                        and position not in seen,
                        RoomWritePartitionFailure.ScriptLayout,
                    )
                    seen.add(position)
                    spans.append((position, following))
                    commands.append(row)
                require(start in seen, RoomWritePartitionFailure.ScriptLayout)
                spans.sort()
                # Pickup can change its own kind/quantity operands. A branch
                # into those bytes would turn that data write into new code.
                require(
                    all(
                        first[1] <= second[0] for first, second in zip(spans, spans[1:])
                    ),
                    RoomWritePartitionFailure.ScriptLayout,
                )
        require(
            room["programs"].keys() == expected_programs,
            RoomWritePartitionFailure.ScriptLayout,
        )

        doors = []
        native_aot_kinds = {
            0x3B: "door",
            0x68: "door",
            0x4E: "item",
            0x69: "item",
            0x2C: "interaction",
            0x67: "interaction",
            0x46: "reset",
        }
        for row in commands:
            if row["opcode"] in native_aot_kinds:
                require(
                    row["kind"] == native_aot_kinds[row["opcode"]],
                    RoomWritePartitionFailure.ScriptLayout,
                )
            else:
                require(
                    row["kind"] not in ("door", "item", "interaction", "reset"),
                    RoomWritePartitionFailure.ScriptLayout,
                )
            if row["kind"] not in ("door", "item", "interaction", "reset"):
                continue
            packet = data[row["offset"] : row["next"]]
            require(
                packet[1] < config.aot_capacity, RoomWritePartitionFailure.ScriptLayout
            )
            if row["kind"] in ("interaction", "reset"):
                require(
                    row["interaction"] == packet[2],
                    RoomWritePartitionFailure.ScriptLayout,
                )
            if row["kind"] == "door":
                require(
                    row["opcode"] in (0x3B, 0x68)
                    and packet[2] == 1
                    and bool(packet[3] & 0x80) == (row["opcode"] == 0x68),
                    RoomWritePartitionFailure.ScriptLayout,
                )
                doors.append(SourceRange(row["offset"], len(packet)))
        require(
            {row.offset for row in doors} == {row["offset"] for row in room["doors"]},
            RoomWritePartitionFailure.ScriptLayout,
        )
        protected.extend(doors)
        object_commands = [row for row in commands if row["opcode"] == 0x2D]
        if object_commands:
            directory = sections[10]
            require(
                directory >= 100
                and directory % 4 == 0
                and directory + data[2] * 8 <= min(floor, limit(directory))
                and data[2] > 0,
                RoomWritePartitionFailure.ObjectModel,
            )
            directory_region = SourceRange(directory, data[2] * 8)
            require(
                not any(overlaps(directory_region, region) for region in protected),
                RoomWritePartitionFailure.SourceOverlap,
            )
            protected.append(directory_region)

        resources: list[tuple[str, SourceRange]] = []

        def reserve(kind: str, region: SourceRange) -> None:
            require(
                region.offset >= 100 and region.offset + region.width <= floor,
                RoomWritePartitionFailure.SourceOverlap,
            )
            require(
                not any(overlaps(region, other) for other in protected)
                and not any(
                    overlaps(region, other) and (kind != other_kind or region != other)
                    for other_kind, other in resources
                ),
                RoomWritePartitionFailure.SourceOverlap,
            )
            resources.append((kind, region))

        objects, source_writes = [], []
        for row in object_commands:
            position = row["offset"]
            slot = data[position + 1]
            require(
                slot < min(data[2], config.object_capacity),
                RoomWritePartitionFailure.ObjectModel,
            )
            entry = sections[10] + slot * 8
            texture, model = struct.unpack_from("<II", data, entry)
            require(texture < len(data), RoomWritePartitionFailure.ObjectModel)
            record = RamRange(config.object_address + slot * 0x1F8, 0x1F8)
            if model == 0:
                # The relocated null field equals the RDT base; native 2D
                # disables the object and skips its model-loader branch.
                objects.append(
                    ObjectWritePartition(
                        position, slot, record, ModelResourceState.Absent
                    )
                )
                continue
            require(
                model >= 100 and model % 4 == 0 and model + 12 <= floor,
                RoomWritePartitionFailure.ObjectModel,
            )
            body_width, flags, count = struct.unpack_from("<III", data, model)
            require(
                flags == 0
                and count >= 2
                and count % 2 == 0
                and 12 + count * 28 <= body_width
                and body_width % 4 == 0
                and model + body_width <= floor,
                RoomWritePartitionFailure.ObjectModel,
            )
            writes, uv_width = [], 0
            # MD1 offsets are relative to the first object record, not its
            # 12-byte header. Header word 0 excludes the appended UV records.
            for index in range(count):
                at = model + 12 + index * 28
                vertex, vertices, normal, normals, primitive, primitives, uv = (
                    struct.unpack_from("<7I", data, at)
                )
                stride = 12 if index % 2 == 0 else 16
                for pointer, width in (
                    (vertex, vertices * 8),
                    (normal, normals * 8),
                    (primitive, primitives * stride),
                ):
                    require(
                        pointer % 4 == 0
                        and pointer >= count * 28
                        and 12 + pointer + width <= body_width,
                        RoomWritePartitionFailure.ObjectModel,
                    )
                require(
                    12 + uv == body_width + uv_width
                    and model + body_width + uv_width + primitives * stride <= floor,
                    RoomWritePartitionFailure.ObjectModel,
                )
                # 2CFD8 relocates four pointers. Both mesh allocators can
                # subsequently replace the fourth with a tagged packet cache.
                writes.extend(SourceRange(at + field, 4) for field in (0, 8, 16, 24))
                for primitive_index in range(primitives):
                    start = model + 12 + uv + primitive_index * stride
                    writes.extend((SourceRange(start, 4), SourceRange(start + 4, 4)))
                uv_width += primitives * stride
            asset = SourceRange(model, body_width + uv_width)
            reserve("model", asset)
            resource = EmbeddedModelResource(
                SourceRange(entry, 8), asset, count, tuple(writes)
            )
            objects.append(ObjectWritePartition(position, slot, record, resource))
            source_writes.append(SourceWritePartition(position, 0x2D, resource.writes))

        for row in commands:
            position, opcode = row["offset"], row["opcode"]
            packet = data[position : row["next"]]
            if opcode == 0x37:
                collision = sca_write_partition(data, sections, position)
                require(
                    isinstance(collision, ScaWritePartition),
                    RoomWritePartitionFailure.Collision,
                )
                reserve("collision", collision.asset)
                source_writes.append(
                    SourceWritePartition(position, opcode, (collision.write,))
                )
            if row["kind"] not in ("interaction", "reset") or row["interaction"] != 13:
                continue
            require(
                opcode in (0x2C, 0x67, 0x46)
                and not (opcode == 0x46 and packet[3] & 0x80)
                and bool(packet[3] & 0x80) == (opcode == 0x67),
                RoomWritePartitionFailure.CameraTrigger,
            )
            payload = (
                packet[4:]
                if opcode == 0x46
                else packet[22:]
                if opcode == 0x67
                else packet[14:]
            )
            require(len(payload) == 6, RoomWritePartitionFailure.CameraTrigger)
            flag, target, camera = struct.unpack("<3H", payload)
            require(
                flag < config.interaction_flag_count
                and target < config.aot_capacity
                and camera < data[1],
                RoomWritePartitionFailure.CameraTrigger,
            )
            candidates = [
                command
                for command in commands
                if command["kind"] in ("door", "item", "interaction", "reset")
                and data[command["offset"] + 1] == target
            ]
            require(bool(candidates), RoomWritePartitionFailure.CameraTrigger)
            target_models = set()
            for candidate in candidates:
                value = data[candidate["offset"] : candidate["next"]]
                if candidate["kind"] == "reset":
                    require(
                        value[2] == 2
                        and not value[3] & 0x80
                        and struct.unpack_from("<H", value, 8)[0]
                        < config.item_flag_count,
                        RoomWritePartitionFailure.CameraTrigger,
                    )
                    continue
                require(
                    candidate["opcode"] == 0x4E
                    and value[2] == 2
                    and not value[3] & 0x80
                    and struct.unpack_from("<H", value, 18)[0] < config.item_flag_count
                    and value[20] < min(data[2], config.object_capacity),
                    RoomWritePartitionFailure.CameraTrigger,
                )
                target_models.add(value[20])
            require(bool(target_models), RoomWritePartitionFailure.CameraTrigger)

            rvd = sections[8]
            require(
                rvd >= 100 and rvd % 4 == 0, RoomWritePartitionFailure.CameraTrigger
            )
            cursor, volume = rvd, -1
            while cursor + 4 <= min(floor, limit(rvd)):
                if data[cursor : cursor + 4] == b"\xff" * 4:
                    break
                require(
                    cursor + 20 <= min(floor, limit(rvd)),
                    RoomWritePartitionFailure.CameraTrigger,
                )
                # 2C7DC searches byte 2 and returns the first match. Camera
                # numbers are not record indices and can occur more than once.
                if volume == -1 and data[cursor + 2] == camera:
                    volume = cursor
                cursor += 20
            else:
                raise _InvalidPartition(RoomWritePartitionFailure.CameraTrigger)
            require(volume != -1, RoomWritePartitionFailure.CameraTrigger)
            reserve("camera", SourceRange(rvd, cursor + 4 - rvd))
            source_writes.append(
                SourceWritePartition(
                    position,
                    opcode,
                    tuple(SourceRange(volume + field, 2) for field in range(4, 20, 2)),
                )
            )
            # Kind 13 also toggles the target item's fixed model record. Its
            # UI, inventory, flags and eventual pickup remain separate effects.
            objects.extend(
                ObjectWritePartition(
                    position,
                    slot,
                    RamRange(config.object_address + slot * 0x1F8, 0x1F8),
                    ModelResourceState.NotAccessed,
                )
                for slot in sorted(target_models)
            )
        return RoomWritePartitions(
            floor, tuple(protected), tuple(doors), tuple(objects), tuple(source_writes)
        )
    except _InvalidPartition as error:
        return error.reason
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return RoomWritePartitionFailure.SourceBinding
