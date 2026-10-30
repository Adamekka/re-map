"""Bounded source copies into owned actor-part records. RE2-DS-005."""

from __future__ import annotations

import hashlib
import re
import struct
from dataclasses import dataclass, field
from enum import Enum, auto

from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    NATIVE_LOOP_FRAME_COUNT,
    SCALAR_PROGRAM_STEP_LIMIT,
    programs_digest,
)


class ActorPartSupport(Enum):
    Unaudited = auto()


@dataclass(frozen=True)
class ActorPartProofConfig:
    part_counts: tuple[tuple[int, int], ...]
    counter_address: int
    system_address: int
    status_address: int

    def __post_init__(self) -> None:
        assert type(self.part_counts) is tuple and self.part_counts
        assert all(type(row) is tuple and len(row) == 2 for row in self.part_counts)
        assert len(dict(self.part_counts)) == len(self.part_counts)
        assert all(
            type(model) is int
            and 0x10 <= model < 0x50
            and type(count) is int
            and 1 <= count <= 128
            for model, count in self.part_counts
        )
        assert type(self.counter_address) is int and self.counter_address % 2 == 0
        assert 0x80000000 <= self.counter_address <= 0x801FFE00
        assert all(
            type(address) is int
            and address % 4 == 0
            and 0x80000000 <= address <= 0x801FFFFC
            for address in (self.system_address, self.status_address)
        )


@dataclass(frozen=True)
class ActorOwner:
    enemy_slot: int
    model_type: int
    constructor_offset: int
    part_count: int

    def __post_init__(self) -> None:
        assert all(
            type(value) is int
            for value in (
                self.enemy_slot,
                self.model_type,
                self.constructor_offset,
                self.part_count,
            )
        )
        assert 0 <= self.enemy_slot < 32 and 0x10 <= self.model_type < 0x50
        assert self.constructor_offset >= 0 and 1 <= self.part_count <= 128


@dataclass(frozen=True)
class SourceCopyWrite:
    location: tuple[str, int]
    target_offset: int
    width: int

    def __post_init__(self) -> None:
        assert type(self.location) is tuple and len(self.location) == 2
        assert (
            type(self.location[0]) is str
            and type(self.location[1]) is int
            and self.location[1] >= 0
        )
        assert type(self.target_offset) is int and type(self.width) is int
        assert self.target_offset >= self.location[1] + 4 and self.width in (1, 2)


@dataclass(frozen=True)
class OwnedActorFieldWrite:
    location: tuple[str, int]
    owners: tuple[ActorOwner, ...]
    selector: int
    field_offset: int
    width: int

    def __post_init__(self) -> None:
        assert type(self.owners) is tuple and all(
            isinstance(owner, ActorOwner) for owner in self.owners
        )
        assert all(
            type(value) is int
            for value in (self.selector, self.field_offset, self.width)
        )
        # Other member selectors include pointers and AI state. A bounded
        # record alone does not establish their subsequent native effects.
        assert self.owners and (self.selector, self.field_offset, self.width) == (
            23,
            0x1D4,
            2,
        )


# Native 6E writes only these scalar fields of a 0xAC-byte part record.
PART_FIELD_WRITES = (
    (0x70, 2),
    (0x72, 1),
    (0, 2),
    (2, 2),
    (0x68, 2),
    (0x6A, 2),
    (0x6C, 2),
)


@dataclass(frozen=True)
class OwnedPartFieldWrite:
    location: tuple[str, int]
    owners: tuple[ActorOwner, ...]
    indices: frozenset[int]
    selector: int
    field_offset: int
    width: int
    record_stride: int = 0xAC

    def __post_init__(self) -> None:
        assert type(self.owners) is tuple and all(
            isinstance(owner, ActorOwner) for owner in self.owners
        )
        assert type(self.indices) is frozenset and all(
            type(index) is int for index in self.indices
        )
        assert all(
            type(value) is int
            for value in (
                self.selector,
                self.field_offset,
                self.width,
                self.record_stride,
            )
        )
        assert self.owners and self.indices
        assert all(
            0 <= index < min(owner.part_count, 128)
            for owner in self.owners
            for index in self.indices
        )
        assert 0 <= self.selector < len(PART_FIELD_WRITES)
        assert (self.field_offset, self.width) == PART_FIELD_WRITES[self.selector]
        assert (
            self.record_stride == 0xAC
            and self.field_offset + self.width <= self.record_stride
        )


@dataclass(frozen=True)
class ScalarProgramContinuation:
    program: str
    entry: int
    end: int
    source_sha256: str
    programs_sha256: str
    max_loop_depth: int
    steps: int

    def __post_init__(self) -> None:
        assert type(self.program) is str and self.program
        assert type(self.entry) is int and type(self.end) is int
        assert 0 <= self.entry < self.end
        assert all(
            type(digest) is str and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            for digest in (self.source_sha256, self.programs_sha256)
        )
        assert (
            type(self.max_loop_depth) is int
            and 0 <= self.max_loop_depth <= NATIVE_LOOP_FRAME_COUNT
        )
        assert type(self.steps) is int and 1 <= self.steps <= SCALAR_PROGRAM_STEP_LIMIT

    def matches_source(self, data: bytes, programs: dict) -> bool:
        return (
            hashlib.sha256(data).hexdigest() == self.source_sha256
            and programs_digest(programs) == self.programs_sha256
        )


@dataclass(frozen=True)
class ActorPartCopyProof:
    offsets: frozenset[int]
    context_conditions: list[dict]
    reached_locations: frozenset[tuple[str, int]] = frozenset()
    source_writes: tuple[SourceCopyWrite, ...] = ()
    actor_writes: tuple[OwnedActorFieldWrite, ...] = ()
    part_writes: tuple[OwnedPartFieldWrite, ...] = ()
    write_context_conditions: list[dict] = field(default_factory=list)
    scalar_continuations: tuple[ScalarProgramContinuation, ...] = ()

    def __post_init__(self) -> None:
        assert type(self.scalar_continuations) is tuple and all(
            isinstance(continuation, ScalarProgramContinuation)
            for continuation in self.scalar_continuations
        )
        assert len({row.program for row in self.scalar_continuations}) == len(
            self.scalar_continuations
        )


def scenario_actor_parts(profile: dict) -> ActorPartProofConfig | ActorPartSupport:
    """Read revision opt-ins whose owned resource bytes generation verifies."""
    rows = profile.get("scenario_actor_parts", [])
    if rows == []:
        return ActorPartSupport.Unaudited
    layout = profile.get("metadata_layout")
    if (
        type(layout) is not dict
        or type(layout.get("actor_part_resource_table_address_ps1")) is not str
    ):
        raise ValueError("RE2 actor-part proof requires its native resource table")
    try:
        table = int(layout["actor_part_resource_table_address_ps1"], 0)
    except ValueError as error:
        raise ValueError("invalid RE2 actor-part resource table") from error
    if table % 4 or not 0x80000000 <= table <= 0x801FFFF8:
        raise ValueError("RE2 actor-part resource table must be aligned in PS1 RAM")
    keys = {
        "model_type",
        "part_count",
        "resource_sha256",
        "archive_path",
        "resource_sector",
        "resource_width",
    }
    if (
        type(rows) is not list
        or any(
            type(row) is not dict
            or row.keys() != keys
            or type(row["model_type"]) is not int
            or not 0x10 <= row["model_type"] < 0x50
            or type(row["part_count"]) is not int
            or not 1 <= row["part_count"] <= 128
            or type(row["resource_sha256"]) is not str
            or re.fullmatch(r"[0-9a-f]{64}", row["resource_sha256"]) is None
            or row["archive_path"] != "PL0/PLD/CDEMD0.EMS"
            or type(row["resource_sector"]) is not int
            or row["resource_sector"] < 0
            or type(row["resource_width"]) is not int
            or not 44 <= row["resource_width"] <= 0x200000
            for row in rows
        )
        or len({row["model_type"] for row in rows}) != len(rows)
    ):
        raise ValueError("invalid RE2 actor-part resource proof")
    runtime = profile.get("runtime_layout")
    if type(runtime) is not dict or any(
        type(runtime.get(key)) is not str
        for key in (
            "script_counter_address_ps1",
            "system_flags_address_ps1",
            "status_flags_address_ps1",
        )
    ):
        raise ValueError("RE2 actor-part proof requires native game-state addresses")
    try:
        counter, system, status = (
            int(runtime[key], 0)
            for key in (
                "script_counter_address_ps1",
                "system_flags_address_ps1",
                "status_flags_address_ps1",
            )
        )
    except ValueError as error:
        raise ValueError("invalid RE2 actor-part game-state addresses") from error
    if (
        counter % 2
        or not 0x80000000 <= counter <= 0x801FFE00
        or any(
            address % 4 or not 0x80000000 <= address <= 0x801FFFFC
            for address in (system, status)
        )
    ):
        raise ValueError("RE2 actor-part game-state addresses must fit aligned PS1 RAM")
    return ActorPartProofConfig(
        tuple((row["model_type"], row["part_count"]) for row in rows),
        counter,
        system,
        status,
    )


def actor_part_copy_proof(
    data: bytes,
    room: dict,
    fixed: dict[tuple[int, int], int],
    banks: dict[int, tuple[int, int]],
    config: ActorPartProofConfig | ActorPartSupport,
) -> ActorPartCopyProof:
    """Describe bounded writes under the source's analyzed actor ownership.

    Reached locations are not a complete native entry closure. Consumers must
    separately establish that closure, source operand stability and allocator
    partitions before these relative domains imply source/AOT preservation.
    Existing copy applicability stays separate from write-domain conditions.
    """
    assert config is ActorPartSupport.Unaudited or isinstance(
        config, ActorPartProofConfig
    )
    if config is ActorPartSupport.Unaudited:
        return ActorPartCopyProof(frozenset(), [])
    counts = dict(config.part_counts)
    if (
        any(
            bank not in banks
            or banks[bank][0] + bit // 32 * 4
            not in (config.system_address, config.status_address)
            for bank, bit in fixed
        )
        or banks.get(0) != (config.system_address, 4)
        or banks.get(1) != (config.status_address, 4)
    ):
        return ActorPartCopyProof(frozenset(), [])
    programs = room["programs"]
    commands = {
        key: {row["offset"]: row for row in program["commands"]}
        for key, program in programs.items()
    }
    # These operations can replace a task or enter code with restored frames.
    # Their existing native audits do not establish this analysis's entry state.
    if any(
        row["opcode"] in (3, 5, 0x13, 0x17, 0x47)
        for program in programs.values()
        for row in program["commands"]
    ):
        return ActorPartCopyProof(frozenset(), [])

    class Unknown(Enum):
        Value = auto()

    loop_edges = {}
    for key, program in programs.items():
        stack = []
        for row in program["commands"]:
            opcode = row["opcode"]
            if opcode in (0x0D, 0x0F, 0x11):
                limit = (
                    row["next"] + struct.unpack_from("<h", data, row["offset"] + 2)[0]
                )
                if len(stack) >= NATIVE_LOOP_FRAME_COUNT or limit not in commands[key]:
                    return ActorPartCopyProof(frozenset(), [])
                stack.append((opcode, row["next"], limit))
                if opcode != 0x11:
                    loop_edges[key, row["offset"]] = (row["next"], limit)
            elif opcode in (0x0E, 0x10, 0x12):
                if not stack:
                    return ActorPartCopyProof(frozenset(), [])
                opening, start, limit = stack.pop()
                if {0x0E: 0x0D, 0x10: 0x0F, 0x12: 0x11}[opcode] != opening:
                    return ActorPartCopyProof(frozenset(), [])
                loop_edges[key, row["offset"]] = (start, limit)
        if stack:
            return ActorPartCopyProof(frozenset(), [])

    def preserves_work(key: str, active: frozenset[str]) -> bool:
        if key in active or key not in programs:
            return False
        return all(
            row["opcode"] != 0x2E
            and (
                row["kind"] != "call"
                or preserves_work(f"17:{row['procedure']}", active | {key})
            )
            for row in programs[key]["commands"]
        )

    def flag_location(bank: int, bit: int) -> tuple[int, int] | Unknown:
        if bank not in banks or not 0 <= bit < banks[bank][1] * 8:
            return Unknown.Value
        return banks[bank][0] + bit // 32 * 4, 0x80000000 >> (bit % 32)

    fixed_locations = {
        flag_location(bank, bit): value for (bank, bit), value in fixed.items()
    }

    def monotonic_guard(guard: frozenset[tuple[int, int, int]]) -> bool:
        if not guard:
            return True
        protected = {
            flag_location(bank, bit): expected for bank, bit, expected in guard
        }
        if Unknown.Value in protected:
            return False
        for source in programs.values():
            for command in source["commands"]:
                if command["kind"] == "flag_write":
                    location = flag_location(command["bank"], command["bit"])
                    if location is Unknown.Value:
                        return False
                    if (
                        location in protected
                        and command["operation"] != 1 - protected[location]
                    ):
                        return False
                elif command["opcode"] in (0x24, 0x25, 0x26, 0x27):
                    operand = (
                        3
                        if command["opcode"] == 0x26
                        else 2
                        if command["opcode"] == 0x27
                        else 1
                    )
                    address = (
                        config.counter_address + data[command["offset"] + operand] * 2
                    )
                    for word, mask in protected:
                        if word <= address <= word + 2 and mask & (
                            0xFFFF << ((address - word) * 8)
                        ):
                            return False
        return True

    # An origin records a startup constructor and the flag branch needed to
    # reach it. A later task inherits it only when its birth guard implies that
    # branch and source writes cannot make the branch newly true after startup.
    constructors = set()
    pending = [
        (
            key,
            programs[key]["entry"],
            Unknown.Value,
            0,
            frozenset(),
            True,
            frozenset(),
            "startup",
        )
        for key in ("16:0", "17:0")
        if key in programs
    ]
    deferred = []
    seen, work_at, models, reached = set(), {}, {}, set()
    frame_started = False
    while pending or not frame_started:
        if not pending:
            frame_started = True
            if "17:1" in programs:
                pending.append(
                    (
                        "17:1",
                        programs["17:1"]["entry"],
                        Unknown.Value,
                        0,
                        frozenset(),
                        True,
                        frozenset(),
                        "frame",
                    )
                )
            pending.extend(deferred)
            if not pending:
                break
        key, position, work, depth, guard, certain, owned, phase = pending.pop()
        state = key, position, work, depth, guard, certain, owned, phase
        if state in seen:
            continue
        if len(seen) >= 16384 or len(guard) > 32 or position not in commands[key]:
            return ActorPartCopyProof(frozenset(), [])
        seen.add(state)
        reached.add((key, position))
        row = commands[key][position]
        opcode = row["opcode"]
        contexts = work_at.setdefault((key, position), set())
        origins = frozenset(
            origin
            for origin in owned
            if work is not Unknown.Value and work == (3, origin[0])
        )
        contexts.add(origins if origins else Unknown.Value)
        if row["kind"] == "end":
            continue
        if (key, position) in loop_edges:
            pending.extend(
                (key, target, work, depth, guard, False, owned, phase)
                for target in loop_edges[key, position]
            )
            continue
        if row["kind"] == "if":
            following, tests, opaque = row["next"], [], False
            while following in commands[key] and commands[key][following]["opcode"] in (
                0x21,
                0x23,
                0x3E,
                0x50,
                0x5E,
            ):
                test = commands[key][following]
                reached.add((key, following))
                if test["kind"] == "flag_check" and test["expected"] in (0, 1):
                    tests.append((test["bank"], test["bit"], test["expected"]))
                else:
                    opaque = True
                following = test["next"]
            yes, no = True, True
            yes_guard, no_guard = set(guard), set(guard)
            for bank, bit, expected in tests:
                location = flag_location(bank, bit)
                if location is Unknown.Value:
                    return ActorPartCopyProof(frozenset(), [])
                if location in fixed_locations:
                    if fixed_locations[location] != expected:
                        yes = False
                else:
                    yes_guard.add((bank, bit, expected))
            if len(tests) == 1 and not opaque:
                bank, bit, expected = tests[0]
                location = flag_location(bank, bit)
                if location in fixed_locations:
                    no = fixed_locations[location] != expected
                else:
                    no_guard.add((bank, bit, 1 - expected))
            for target, clause, possible in (
                (following, yes_guard, yes),
                (row["target"], no_guard, no),
            ):
                by_location = {}
                for bank, bit, expected in clause:
                    location = flag_location(bank, bit)
                    if location in by_location and by_location[location] != expected:
                        possible = False
                    by_location[location] = expected
                if possible:
                    pending.append(
                        (
                            key,
                            target,
                            work,
                            depth,
                            frozenset(clause),
                            certain and not opaque,
                            owned,
                            phase,
                        )
                    )
            continue
        if opcode == 7:
            pending.append(
                (key, row["target"], work, depth, guard, certain, owned, phase)
            )
            continue
        if row["kind"] == "call":
            target = f"17:{row['procedure']}"
            if target not in programs or depth >= NATIVE_CALL_FRAME_COUNT - 1:
                return ActorPartCopyProof(frozenset(), [])
            pending.append(
                (
                    target,
                    programs[target]["entry"],
                    work,
                    depth + 1,
                    guard,
                    certain,
                    owned,
                    phase,
                )
            )
            if not preserves_work(target, frozenset()):
                work = Unknown.Value
            # The caller continuation does not assume any side effects from a
            # callee. Copies reached inside that callee retain their real path.
            certain = False
        elif (
            opcode == 4
            or row["kind"] in ("interaction", "reset")
            and row["interaction"] == 5
        ):
            if opcode == 4:
                packet = data[position : row["next"]]
                if packet[1:3] != b"\xff\x18":
                    return ActorPartCopyProof(frozenset(), [])
                target = f"17:{packet[3]}"
            else:
                payload = (
                    bytes(row["data"])
                    if row["kind"] == "reset"
                    else data[position + (22 if opcode == 0x67 else 14) : row["next"]]
                )
                if payload[:3] != b"\xff\0\x18" or any(payload[4:]):
                    return ActorPartCopyProof(frozenset(), [])
                target = f"17:{payload[3]}"
            if target not in programs:
                return ActorPartCopyProof(frozenset(), [])
            implied = {
                flag_location(bank, bit): expected for bank, bit, expected in guard
            }
            inherited = frozenset(
                origin
                for origin in constructors
                if monotonic_guard(origin[2])
                and all(
                    implied.get(flag_location(bank, bit)) == expected
                    for bank, bit, expected in origin[2]
                )
            )
            child = (
                target,
                programs[target]["entry"],
                Unknown.Value,
                0,
                frozenset(),
                True,
                inherited,
                "task",
            )
            if phase == "startup":
                deferred.append(child)
            else:
                pending.append(child)
            certain = False
        elif opcode == 0x2E:
            work = (data[position + 1], data[position + 2])
        elif opcode == 0x44:
            index, model = data[position + 2 : position + 4]
            models.setdefault(index, set()).add(model)
            acquired = data[position + 9]
            condition = ()
            if acquired != 0xFF:
                stage = room.get("stage")
                if type(stage) is not int or stage < 3 and (1, 6) not in fixed:
                    return ActorPartCopyProof(frozenset(), [])
                bank = 6 if stage < 3 and fixed[1, 6] == 0 else 7
                if flag_location(bank, acquired) is Unknown.Value:
                    return ActorPartCopyProof(frozenset(), [])
                condition = (bank, acquired, 0)
            origin = (index, model, guard, condition, position)
            # Constructors after opaque/yielding paths cannot establish a
            # startup promise for independently scheduled room tasks.
            if certain:
                owned = frozenset(item for item in owned if item[0] != index) | {origin}
                if phase == "startup":
                    constructors.add(origin)
            else:
                owned = frozenset(item for item in owned if item[0] != index)
        elif row["kind"] == "flag_write":
            location = flag_location(row["bank"], row["bit"])
            guard = frozenset(
                item for item in guard if flag_location(item[0], item[1]) != location
            )
            certain = False
        elif opcode in (2, 9, 10, 11, 12):
            certain = False
        pending.append((key, row["next"], work, depth, guard, certain, owned, phase))

    def selected_origins(key: str, position: int) -> frozenset | Unknown:
        contexts = work_at.get((key, position), set())
        if not contexts or any(
            context is Unknown.Value
            or any(
                not 0 <= origin[0] < 32
                or origin[1] not in counts
                or not models[origin[0]] <= counts.keys()
                or origin[3]
                and not monotonic_guard(origin[2] | {origin[3]})
                for origin in context
            )
            for context in contexts
        ):
            return Unknown.Value
        return frozenset(origin for context in contexts for origin in context)

    allowed, applied_origins, scalar_indices = set(), set(), {}
    scalar_programs = []
    for key, program in programs.items():
        candidates = []
        for row in program["commands"]:
            if row["opcode"] != 0x1D:
                continue
            width = 2 if data[row["offset"] + 3] else 1
            target = row["next"] + data[row["offset"] + 2]
            destination = next(
                (
                    command
                    for command in program["commands"]
                    if command["offset"] <= target and target + width <= command["next"]
                ),
                None,
            )
            if destination is not None and destination["opcode"] == 0x6E:
                candidates.append((row, destination, target, width))
        if not candidates:
            continue
        # Keeping this interpreter synchronous makes a known counter local to
        # this invocation: another room task cannot interleave a write at yield.
        if any(
            row["opcode"] not in (0, 1, 0x0D, 0x0E, 0x1D, 0x24, 0x25, 0x26, 0x6E)
            for row in program["commands"]
        ):
            continue
        by_copy = {
            row["offset"]: (destination, target, width)
            for row, destination, target, width in candidates
        }
        # Other Calc operations can trap even when their result is unused.
        # Preserve their old write analysis without certifying continuation.
        summary_eligible = all(
            row["opcode"] != 0x26 or data[row["offset"] + 2] in (0, 1)
            for row in program["commands"]
        )

        used_origins = set()

        def selected_part_count(position: int) -> int | Unknown:
            origins = selected_origins(key, position)
            if origins is Unknown.Value:
                return Unknown.Value
            used_origins.update(origins)
            return min(counts[origin[1]] for origin in origins)

        values = [Unknown.Value] * 256
        part_indices = {}
        loops, checked, indices = [], set(), {}
        max_loop_depth = 0
        position, steps, valid = program["entry"], 0, True
        while valid:
            steps += 1
            if steps > SCALAR_PROGRAM_STEP_LIMIT or position not in commands[key]:
                valid = False
                break
            row = commands[key][position]
            opcode, following = row["opcode"], row["next"]
            if opcode == 1:
                valid = not loops
                break
            if opcode == 0x24:
                values[data[position + 1]] = struct.unpack_from(
                    "<H", data, position + 2
                )[0]
            elif opcode == 0x25:
                values[data[position + 1]] = values[data[position + 2]]
            elif opcode == 0x26:
                operation, index = data[position + 2 : position + 4]
                operand = struct.unpack_from("<h", data, position + 4)[0]
                value = values[index]
                values[index] = (
                    (value + operand if operation == 0 else value - operand) & 0xFFFF
                    if type(value) is int and operation in (0, 1)
                    else Unknown.Value
                )
            elif opcode == 0x0D:
                count = struct.unpack_from("<H", data, position + 4)[0]
                limit = following + struct.unpack_from("<h", data, position + 2)[0]
                if len(loops) >= NATIVE_LOOP_FRAME_COUNT or limit not in commands[key]:
                    valid = False
                    break
                if count:
                    loops.append((following, limit, count))
                    max_loop_depth = max(max_loop_depth, len(loops))
                else:
                    following = limit
            elif opcode == 0x0E:
                if not loops or following != loops[-1][1]:
                    valid = False
                    break
                start, limit, remaining = loops.pop()
                if remaining > 1:
                    loops.append((start, limit, remaining - 1))
                    following = start
            elif opcode == 0x6E:
                count = selected_part_count(position)
                index = part_indices.get(position, data[position + 2])
                if (
                    count is Unknown.Value
                    or index >= min(count, 128)
                    or data[position + 3] > 6
                ):
                    valid = False
                    break
                indices.setdefault(position, set()).add(index)
            elif opcode == 0x1D:
                if position not in by_copy:
                    valid = False
                    break
                destination, target, width = by_copy[position]
                field = target - destination["offset"]
                count = selected_part_count(destination["offset"])
                if count is Unknown.Value:
                    valid = False
                    break
                selector = data[destination["offset"] + 3]
                value = values[data[position + 1]]
                if selector > 6 or not (
                    field == 2
                    and width == 1
                    and type(value) is int
                    and value < min(count, 128)
                    or field >= 4
                    and field + width <= 6
                    and (width == 1 or target % 2 == 0)
                ):
                    valid = False
                    break
                if field == 2:
                    part_indices[destination["offset"]] = value
                checked.add(position)
            position = following
        if valid:
            allowed.update(checked)
            applied_origins.update(used_origins)
            scalar_indices.update(
                {
                    (key, position): frozenset(values)
                    for position, values in indices.items()
                }
            )
            if (
                summary_eligible
                and program["entry"] < position
                and data[position : row["next"]] == b"\x01\0"
            ):
                scalar_programs.append(
                    (
                        key,
                        program["entry"],
                        position,
                        max_loop_depth,
                        steps,
                        frozenset(checked),
                        frozenset(indices),
                    )
                )

    source_writes = tuple(
        SourceCopyWrite(
            (key, position),
            row["next"] + data[position + 2],
            2 if data[position + 3] else 1,
        )
        for key, position in sorted(work_at)
        if (row := commands[key][position])["opcode"] == 0x1D
    )
    actor_writes, part_writes, write_origins = [], [], set()
    for key, position in sorted(work_at):
        row = commands[key][position]
        if row["opcode"] not in (0x34, 0x6E):
            continue
        origins = selected_origins(key, position)
        if origins is Unknown.Value:
            continue
        owners = tuple(
            sorted(
                {
                    ActorOwner(origin[0], origin[1], origin[4], counts[origin[1]])
                    for origin in origins
                },
                key=lambda owner: (
                    owner.enemy_slot,
                    owner.model_type,
                    owner.constructor_offset,
                    owner.part_count,
                ),
            )
        )
        if row["opcode"] == 0x34:
            if data[position + 1] != 23 or any(
                write.target_offset < position + 2
                and position < write.target_offset + write.width
                for write in source_writes
            ):
                continue
            actor_writes.append(
                OwnedActorFieldWrite((key, position), owners, 23, 0x1D4, 2)
            )
        else:
            selector = data[position + 3]
            if selector >= len(PART_FIELD_WRITES) or any(
                write.target_offset < position + 1
                and position < write.target_offset + write.width
                or write.target_offset < position + 4
                and position + 3 < write.target_offset + write.width
                for write in source_writes
            ):
                continue
            if (key, position) in scalar_indices:
                if any(
                    write.target_offset < position + 3
                    and position + 2 < write.target_offset + write.width
                    and (write.location[0] != key or write.location[1] not in allowed)
                    for write in source_writes
                ):
                    continue
                indices = scalar_indices[key, position]
            elif any(
                write.target_offset < position + 3
                and position + 2 < write.target_offset + write.width
                for write in source_writes
            ):
                continue
            else:
                indices = frozenset({data[position + 2]})
            if any(
                index >= min(owner.part_count, 128)
                for owner in owners
                for index in indices
            ):
                continue
            field_offset, width = PART_FIELD_WRITES[selector]
            part_writes.append(
                OwnedPartFieldWrite(
                    (key, position), owners, indices, selector, field_offset, width
                )
            )
        write_origins.update(origins)

    owned_parts = {write.location for write in part_writes}
    checked_copies = {
        write.location for write in source_writes if write.location[1] in allowed
    }
    # Later cross-program mutation checks can withdraw an owned part bound.
    # A continuation cannot retain effects that the complete write proof lost.
    scalar_programs = [
        (key, entry, end, depth, steps)
        for key, entry, end, depth, steps, copies, parts in scalar_programs
        if {(key, position) for position in copies} <= checked_copies
        and {(key, position) for position in parts} <= owned_parts
    ]
    scalar_continuations = ()
    if scalar_programs:
        source_sha256 = hashlib.sha256(data).hexdigest()
        programs_sha256 = programs_digest(programs)
        scalar_continuations = tuple(
            ScalarProgramContinuation(
                key, entry, end, source_sha256, programs_sha256, depth, steps
            )
            for key, entry, end, depth, steps in scalar_programs
        )

    def context_conditions(origins: set) -> list[dict]:
        conditions = []
        for origin in sorted(
            origins,
            key=lambda item: (
                item[0],
                item[1],
                tuple(sorted(item[2])),
                item[3],
                item[4],
            ),
        ):
            acquisition = origin[3]
            if not acquisition:
                continue
            bank, bit, expected = acquisition
            # A fresh clear flag is an entry requirement only while all source
            # writers preserve its monotonic clear-to-set lifetime. The story
            # guard cannot substitute after a skipped constructor queues work.
            condition = {
                "kind": "conditions",
                "any_of": [[{"bank": bank, "bit": bit, "expected": expected}]],
            }
            if condition not in conditions:
                conditions.append(condition)
        return conditions

    return ActorPartCopyProof(
        frozenset(allowed),
        context_conditions(applied_origins),
        frozenset(reached),
        source_writes,
        tuple(actor_writes),
        tuple(part_writes),
        context_conditions(write_origins),
        scalar_continuations,
    )
