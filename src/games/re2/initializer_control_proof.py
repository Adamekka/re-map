"""Bound synchronous comparison copies and flat music-only switch blocks.

The named revision audit covers initialized native music buffers. This receipt
proves only the listed effects; callers still reject every other unsupported
source effect and enforce their own startup and scenario requirements.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from games.re2.actor_part_proofs import SourceCopyWrite

if TYPE_CHECKING:
    from games.re2.room_write_partitions import RoomWritePartitionConfig

# Native depth-indexed IF/loop fields have four call frames, including root.
NATIVE_CALL_FRAME_COUNT = 4

AUDITED_INITIALIZER_CONTROL_SHA256 = (
    "dfd9d7f331c2d2a0cff02c2d599478057b2e81bd9148179a33b3544149c2f295"
)
# The revision's VM allocates this many bytes per task, including its native
# call, IF and switch frame storage. Control effects never leave that record.
NATIVE_TASK_WIDTH = 0x174


class InitializerControlSupport(Enum):
    Unaudited = "unaudited"


class InitializerControlFailure(Enum):
    SourceBinding = "initializer control source binding mismatch"
    Partition = "initializer control storage partition is unproved"
    Stage = "initializer control source placement is unaudited"
    Copy = "initializer copy may change a protected operand"
    Counter = "initializer counter copy is outside its native work region"
    Switch = "unsupported native switch structure"
    CallDepth = "initializer exceeds audited native call frames"
    Music = "unsupported native music control form"
    FlagAlias = "initializer writes may change a fresh flag predicate"


def native_switch_labels(
    data: bytes, start: int, stop: int
) -> tuple[int, tuple[int, ...]]:
    """Follow the native unsigned case links, including the closing marker."""
    following = start + 4
    end = following + struct.unpack_from("<H", data, start + 2)[0]
    if not following < end < stop or data[end - 2] != 0x16:
        raise ValueError("invalid RE2 switch bounds")
    label, labels = following, []
    while True:
        if not following <= label <= end - 2:
            raise ValueError("RE2 switch case outside its bounds")
        marker = data[label]
        labels.append(label)
        if marker == 0x14 and label + 6 <= end - 2:
            label += 6 + struct.unpack_from("<H", data, label + 2)[0]
        elif marker == 0x15 and label < end - 2:
            # Default stops the native search. Its body and the closing
            # marker still need independent decoder visits.
            labels.append(end - 2)
            break
        elif marker == 0x16 and label == end - 2:
            break
        else:
            raise ValueError("invalid RE2 switch label chain")
    return end, tuple(labels)


@dataclass(frozen=True)
class InitializerControlConfig:
    audit: str
    executable_sha256: str
    counter_address: int
    counter_limit: int
    writable_counters: frozenset[int]
    flag_ranges: tuple[tuple[int, int], ...]
    predicate_flags: frozenset[tuple[int, int]]
    task_address: int
    task_capacity: int
    source_addresses: tuple[tuple[int, int], ...]
    music_buffers: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        assert type(self.audit) is str and self.audit
        assert type(self.executable_sha256) is str and len(self.executable_sha256) == 64
        assert type(self.counter_address) is int and self.counter_address % 2 == 0
        assert type(self.counter_limit) is int and self.counter_limit % 2 == 0
        assert 0x80000000 <= self.counter_address < self.counter_limit <= 0x80200000
        assert (self.counter_limit - self.counter_address) // 2 <= 256
        assert type(self.writable_counters) is frozenset and all(
            type(index) is int
            and 0 <= index < (self.counter_limit - self.counter_address) // 2
            for index in self.writable_counters
        )
        assert type(self.task_address) is int and self.task_address % 4 == 0
        assert type(self.task_capacity) is int and 1 <= self.task_capacity <= 256
        assert 0x80000000 <= self.task_address
        assert self.task_address + self.task_capacity * NATIVE_TASK_WIDTH <= 0x80200000
        assert type(self.source_addresses) is tuple and self.source_addresses
        assert len(dict(self.source_addresses)) == len(self.source_addresses)
        assert all(
            type(stage) is int
            and 0 <= stage <= 255
            and type(address) is int
            and address % 4 == 0
            and 0x80000000 <= address < 0x80200000
            for stage, address in self.source_addresses
        )
        assert type(self.music_buffers) is tuple and len(self.music_buffers) == 2
        assert type(self.flag_ranges) is tuple and self.flag_ranges
        assert type(self.predicate_flags) is frozenset and all(
            type(bank) is int
            and type(bit) is int
            and 0 <= bank <= 255
            and 0 <= bit <= 255
            for bank, bit in self.predicate_flags
        )
        assert all(
            type(start) is int
            and type(end) is int
            and 0x80000000 <= start < end <= 0x80200000
            for start, end in (*self.music_buffers, *self.flag_ranges)
        )


@dataclass(frozen=True)
class InitializerControlProof:
    source_sha256: str
    programs_sha256: str
    rhs_copy_offsets: frozenset[int]
    predicate_copy_locations: frozenset[tuple[str, int]]
    switch_edges: tuple[tuple[str, int, int], ...]
    fallthrough_locations: frozenset[tuple[str, int]]
    source_writes: tuple[SourceCopyWrite, ...]
    ram_writes: tuple[tuple[int, int], ...]
    predicate_flags: frozenset[tuple[int, int]]

    def matches_source(self, data: bytes, programs: dict) -> bool:
        return (
            hashlib.sha256(data).hexdigest() == self.source_sha256
            and hashlib.sha256(
                json.dumps(programs, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            == self.programs_sha256
        )

    def preserves_fixed_words(self, words: dict[int, int]) -> bool:
        return all(
            address + width <= word or word + 4 <= address
            for address, width in self.ram_writes
            for word in words
        )

    def supports_predicates(
        self,
        condition_flags: frozenset[tuple[int, int]],
        fixed_flags: frozenset[tuple[int, int, int]],
    ) -> bool:
        return (
            condition_flags | frozenset((bank, bit) for bank, bit, _ in fixed_flags)
            <= self.predicate_flags
        )

    def for_predicates(
        self,
        data: bytes,
        programs: dict,
        condition_flags: frozenset[tuple[int, int]],
        fixed_flags: frozenset[tuple[int, int, int]],
    ) -> InitializerControlProof | InitializerControlSupport:
        assert self.matches_source(data, programs), (
            "initializer receipt belongs to another source"
        )
        # A new query cannot inherit preservation for flags outside the native
        # banks whose complete physical ranges this receipt checked.
        return (
            self
            if self.supports_predicates(condition_flags, fixed_flags)
            else InitializerControlSupport.Unaudited
        )


def initializer_control_config(
    profile: dict,
) -> InitializerControlConfig | InitializerControlSupport:
    """Select the audited native semantics through explicit revision data."""
    if "initializer_control_audit" not in profile:
        return InitializerControlSupport.Unaudited
    raw = profile["initializer_control_audit"]
    try:
        digest = hashlib.sha256(
            json.dumps(
                raw, sort_keys=True, separators=(",", ":"), allow_nan=False
            ).encode()
        ).hexdigest()
        if digest != AUDITED_INITIALIZER_CONTROL_SHA256:
            raise ValueError("unsupported RE2 initializer control audit")
        from games.re2.event_presence import presence_counter_indices

        runtime = profile["runtime_layout"]
        if (
            profile["executable_identity"].rpartition(" SHA256 ")[2]
            != raw["executable_sha256"]
            or raw["counter_address_ps1"] != runtime["script_counter_address_ps1"]
            or profile["presence_counter_writes"]
            != {
                "address_ps1": raw["counter_address_ps1"],
                "limit_address_ps1": raw["counter_limit_address_ps1"],
            }
        ):
            raise ValueError(
                "RE2 initializer control disagrees with its revision layout"
            )
        return InitializerControlConfig(
            audit=raw["audit"],
            executable_sha256=raw["executable_sha256"],
            counter_address=int(raw["counter_address_ps1"], 0),
            counter_limit=int(raw["counter_limit_address_ps1"], 0),
            writable_counters=presence_counter_indices(profile),
            flag_ranges=tuple(
                (
                    int(bank["address_ps1"], 0),
                    int(bank["address_ps1"], 0) + bank["width"],
                )
                for bank in profile["flag_banks"]
            ),
            predicate_flags=frozenset(
                (bank["bank"], bit)
                for bank in profile["flag_banks"]
                for bit in range(bank["width"] * 8)
            ),
            task_address=int(raw["task_address_ps1"], 0),
            task_capacity=raw["task_capacity"],
            source_addresses=tuple(
                (row["stage"], int(row["address_ps1"], 0))
                for row in raw["source_addresses"]
            ),
            music_buffers=tuple(
                (int(row["address_ps1"], 0), int(row["limit_address_ps1"], 0))
                for row in raw["music_buffers"]
            ),
        )
    except (KeyError, TypeError, AttributeError, AssertionError, ValueError) as error:
        raise ValueError("invalid RE2 initializer control audit") from error


class _InvalidControl(Exception):
    def __init__(self, reason: InitializerControlFailure):
        self.reason = reason


def initializer_control_proof(
    data: bytes,
    room: dict,
    config: InitializerControlConfig | InitializerControlSupport,
    partition_config: RoomWritePartitionConfig,
) -> InitializerControlProof | InitializerControlFailure | InitializerControlSupport:
    """Validate every source Copy before granting the new control receipts."""
    assert type(data) is bytes and type(room) is dict
    assert config is InitializerControlSupport.Unaudited or isinstance(
        config, InitializerControlConfig
    )
    if config is InitializerControlSupport.Unaudited:
        return config
    # room_data owns the opcode table and imports the presence interpreter.
    # Defer this shared validator import until those modules finish loading.
    from games.re2.room_write_partitions import (
        RoomWritePartitionConfig,
        RoomWritePartitions,
        room_write_partitions,
    )

    assert isinstance(partition_config, RoomWritePartitionConfig)

    def require(condition: bool, failure: InitializerControlFailure) -> None:
        if not condition:
            raise _InvalidControl(failure)

    try:
        partitions = room_write_partitions(data, room, partition_config)
        require(
            isinstance(partitions, RoomWritePartitions),
            InitializerControlFailure.Partition,
        )
        require(type(room.get("stage")) is int, InitializerControlFailure.Stage)
        source = dict(config.source_addresses).get(room["stage"])
        require(source is not None, InitializerControlFailure.Stage)
        assert source is not None
        # The music loaders place all 114 owned lookup resources in these
        # fixed upper arenas. Their VAB offset is nonnegative and their fixed
        # 128-program table remains inside the copied initialized resource.
        require(
            source + partitions.heap_floor
            <= min(start for start, _ in config.music_buffers),
            InitializerControlFailure.Partition,
        )
        programs = room["programs"]
        commands = {
            key: {row["offset"]: row for row in program["commands"]}
            for key, program in programs.items()
        }
        locations = {
            (key, position): row
            for key, rows in commands.items()
            for position, row in rows.items()
        }
        call_edges = {key: set() for key in programs}
        for (key, position), row in locations.items():
            if row["opcode"] == 0x18:
                target = f"17:{data[position + 1]}"
                require(
                    row["kind"] == "call"
                    and row["procedure"] == data[position + 1]
                    and target in programs,
                    InitializerControlFailure.SourceBinding,
                )
                call_edges[key].add(target)
        pending = [(key, (key,)) for key in programs]
        while pending:
            key, active = pending.pop()
            # Native Gosub has no bound check. Call depths 0..3 own separate
            # frames; depth 4 aliases the root loop byte and IF-pointer field.
            require(
                len(active) <= NATIVE_CALL_FRAME_COUNT,
                InitializerControlFailure.CallDepth,
            )
            for target in call_edges[key]:
                require(target not in active, InitializerControlFailure.CallDepth)
                pending.append((target, active + (target,)))
        count = (config.counter_limit - config.counter_address) // 2
        copies, predicate_copies, fallthrough, edges = [], set(), set(), []
        ram_writes = [(config.task_address, config.task_capacity * NATIVE_TASK_WIDTH)]
        music_seen = False
        for (key, position), row in locations.items():
            opcode = row["opcode"]
            packet = data[position : row["next"]]
            if opcode == 0x1D:
                width = 1 if packet[3] == 0 else 2
                target = row["next"] + packet[2]
                destination = next(
                    (
                        candidate
                        for candidate in programs[key]["commands"]
                        if candidate["offset"] <= target
                        and target + width <= candidate["next"]
                    ),
                    None,
                )
                require(
                    packet[1] < count
                    and destination is not None
                    and destination["opcode"] == 0x23
                    and destination["offset"] + 4 <= target
                    and target + width <= destination["offset"] + 6
                    and (width == 1 or target % 2 == 0)
                    and data[destination["offset"] + 2] < count
                    and data[destination["offset"] + 3] < 7,
                    InitializerControlFailure.Copy,
                )
                copies.append(SourceCopyWrite((key, position), target, width))
                predicate_copies.add((key, position))
                fallthrough.add((key, position))
                ram_writes.append((source + target, width))
            elif opcode == 0x25:
                require(
                    packet[1] in config.writable_counters and packet[2] < count,
                    InitializerControlFailure.Counter,
                )
                fallthrough.add((key, position))
                ram_writes.append((config.counter_address + packet[1] * 2, 2))
            elif opcode == 0x51:
                # Mode zero bypasses every sound-library call. Program zero
                # writes VH header volume/pan; 1..128 writes one of its fixed
                # 128 sixteen-byte program records. This is global music VH,
                # not the relocatable room sound bank or its tone records.
                require(
                    packet[1] in (0, 1) and packet[2] == 0 and packet[3] <= 128,
                    InitializerControlFailure.Music,
                )
                music_seen = True
                fallthrough.add((key, position))
        if music_seen:
            ram_writes.extend(
                (start, end - start) for start, end in config.music_buffers
            )

        covered = set()
        for (key, start), opening in locations.items():
            if opening["opcode"] != 0x13:
                continue
            # SWITCH shares native depth/storage with FOR/WHILE/DO. This
            # receipt skips the block, so it cannot hide a fifth shared frame
            # from the caller's loop validator or inherit Goto-adjusted depth.
            require(
                not any(
                    0x0D <= row["opcode"] <= 0x12 or row["opcode"] == 0x17
                    for row in programs[key]["commands"]
                ),
                InitializerControlFailure.Switch,
            )
            require(data[start + 1] < count, InitializerControlFailure.Counter)
            end, labels = native_switch_labels(data, start, programs[key]["limit"])
            require(
                start < end <= programs[key]["limit"]
                and end - 2 in commands[key]
                and commands[key][end - 2]["opcode"] == 0x16
                and data[end - 1] == 0,
                InitializerControlFailure.Switch,
            )
            cases = len(labels) - 1
            require(0 < cases <= 256, InitializerControlFailure.Switch)
            for cursor, following in zip(labels, labels[1:]):
                require(
                    cursor in commands[key] and commands[key][cursor]["opcode"] == 0x14,
                    InitializerControlFailure.Switch,
                )
                case = commands[key][cursor]
                require(
                    case["next"] + 2 <= following <= end - 2,
                    InitializerControlFailure.Switch,
                )
                body = case["next"]
                covered.add((key, cursor))
                while body < following - 2:
                    require(
                        body in commands[key] and commands[key][body]["opcode"] == 0x51,
                        InitializerControlFailure.Switch,
                    )
                    covered.add((key, body))
                    body = commands[key][body]["next"]
                require(
                    body == following - 2
                    and body in commands[key]
                    and commands[key][body]["opcode"] == 0x1A
                    and data[body + 1] == 0,
                    InitializerControlFailure.Switch,
                )
                covered.add((key, body))
            covered.update(((key, start), (key, end - 2)))
            # A foreign IF/Goto target inside a case would bypass native
            # switch-frame initialization or execute an unmatched Break.
            require(
                not any(
                    start < row.get("target", start) < end
                    for row in programs[key]["commands"]
                ),
                InitializerControlFailure.Switch,
            )
            edges.append((key, start, end))
        require(
            all(
                location in covered
                for location, row in locations.items()
                if row["opcode"] in (0x13, 0x14, 0x15, 0x16, 0x1A)
            ),
            InitializerControlFailure.Switch,
        )
        require(
            all(
                address + width <= flag_start or flag_end <= address
                for address, width in ram_writes
                for flag_start, flag_end in config.flag_ranges
            ),
            InitializerControlFailure.FlagAlias,
        )
        return InitializerControlProof(
            source_sha256=hashlib.sha256(data).hexdigest(),
            programs_sha256=hashlib.sha256(
                json.dumps(programs, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest(),
            rhs_copy_offsets=frozenset(write.location[1] for write in copies),
            predicate_copy_locations=frozenset(predicate_copies),
            switch_edges=tuple(sorted(edges)),
            fallthrough_locations=frozenset(fallthrough),
            source_writes=tuple(sorted(copies, key=lambda write: write.location)),
            ram_writes=tuple(sorted(set(ram_writes))),
            predicate_flags=config.predicate_flags,
        )
    except _InvalidControl as error:
        return error.reason
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return InitializerControlFailure.SourceBinding
