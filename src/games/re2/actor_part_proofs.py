"""Bounded source copies into owned actor-part records. RE2-DS-005."""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass
from enum import Enum, auto


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
class ActorPartCopyProof:
    offsets: frozenset[int]
    context_conditions: list[dict]


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
    """Prove nonyielding counted copies and all possible selected actor models."""
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
                if len(stack) >= 4 or limit not in commands[key]:
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
    seen, work_at, models = set(), {}, {}
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
            if target not in programs or depth >= 4:
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
            origin = (index, model, guard, condition)
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

    allowed, applied_origins = set(), set()
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

        used_origins = set()

        def selected_part_count(position: int) -> int | Unknown:
            contexts = work_at.get((key, position), set())
            if not contexts or any(
                context is Unknown.Value
                or any(
                    origin[1] not in counts
                    or not models[origin[0]] <= counts.keys()
                    or origin[3]
                    and not monotonic_guard(origin[2] | {origin[3]})
                    for origin in context
                )
                for context in contexts
            ):
                return Unknown.Value
            used_origins.update(origin for context in contexts for origin in context)
            return min(counts[origin[1]] for context in contexts for origin in context)

        values = [Unknown.Value] * 256
        part_indices = {}
        loops, checked = [], set()
        position, steps, valid = program["entry"], 0, True
        while valid:
            steps += 1
            if steps > 8192 or position not in commands[key]:
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
                if len(loops) >= 4 or limit not in commands[key]:
                    valid = False
                    break
                if count:
                    loops.append((following, limit, count))
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
    conditions = []
    for origin in sorted(
        applied_origins,
        key=lambda item: (item[0], item[1], tuple(sorted(item[2])), item[3]),
    ):
        acquisition = origin[3]
        if not acquisition:
            continue
        bank, bit, expected = acquisition
        # A fresh clear acquisition flag is an entry precondition only while
        # every source writer preserves its monotonic clear-to-set lifetime.
        # The task can set its story guard after queuing, so that guard cannot
        # substitute for the constructor's acquisition check in a fresh poll.
        condition = {
            "kind": "conditions",
            "any_of": [[{"bank": bank, "bit": bit, "expected": expected}]],
        }
        if condition not in conditions:
            conditions.append(condition)
    return ActorPartCopyProof(frozenset(allowed), conditions)
