"""RE2-STARTUP-008: internal positive-only entry and operand capabilities.

The exact owned binder supplies the normal native producer/namespace contract.
This compiler closes source entries and escaped control fields, not VM safety.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from games.re2.native_control import (
    GOTO_FF_IF_BASE,
    IF_FRAME_BASE,
    IF_FRAME_WIDTH,
    TASK_WIDTH,
    loop_end_cell,
    native_bytes,
)
from games.re2.scenario_selection import (
    ScenarioSourceWriteWitnesses,
    scenario_source_write_witnesses,
)
from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    calls_fit_native_frames,
)
from games.re2.startup_declarations import (
    BoundStartupDeclarations,
    startup_flag_banks_match,
)
from games.re2.structured_control import (
    ControlFrames,
    StructuredControl,
    structured_control,
)


class PositiveEntryFailure(Enum):
    Binding = "positive entry native or source binding mismatch"
    Control = "positive entry source control is unsupported"
    ForeignConsumer = "escaped source IF store has a control consumer"
    SourceWrite = "source Copy can change a protected operand"


@dataclass(frozen=True)
class _EntryFacts:
    entry_locations: frozenset[tuple[str, int]]
    gotos: frozenset[tuple[str, int]]
    if_stores: tuple[tuple[str, int, int, int], ...]
    break_reads: tuple[tuple[str, int, int], ...]
    auxiliary_break_reads: tuple[tuple[int, str, int, int], ...]
    numeric_ranges: tuple[tuple[int, int], ...]
    native_roles: tuple[tuple[int, int, str], ...]
    native_entries: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class _PositiveEntryDomain:
    bound: BoundStartupDeclarations
    source_data: bytes
    room_json: str
    profile_json: str
    facts: _EntryFacts

    def __post_init__(self):
        # Recompute rather than accepting a matching hand-made derivation. The
        # bound tuple digest also rejects mutable aliases and bool/int equality.
        assert type(self.bound) is BoundStartupDeclarations
        assert type(self.source_data) is bytes
        assert type(self.room_json) is str and type(self.profile_json) is str
        assert type(self.facts) is _EntryFacts
        result = _derive_entry_domain(
            self.source_data,
            json.loads(self.room_json),
            json.loads(self.profile_json),
            self.bound,
        )
        assert type(result) is _EntryFacts
        from games.re2.positive_prefix import _positive_binding_digest

        assert _positive_binding_digest(self.facts, ()) == _positive_binding_digest(
            result, ()
        )


def _numeric_copy_ranges(data: bytes, programs: dict) -> tuple[tuple[int, int], ...]:
    ranges = []
    for program in programs.values():
        for row in program["commands"]:
            at, opcode = row["offset"], row["opcode"]
            if opcode == 0x0D:
                ranges.append((at + 4, at + 6))
            elif opcode == 0x36 and data[at + 4] == 0:
                ranges.append((at + 6, at + 12))
            elif opcode == 0x54:
                ranges.extend(((at + 8, at + 14), (at + 14, at + 20)))
    return tuple(sorted(ranges))


def _call_depths(programs: dict, roots: set[str], calls: dict[str, set[str]]):
    depths = {key: set() for key in programs}
    pending = [(key, 0) for key in roots]
    while pending:
        key, depth = pending.pop()
        if depth in depths[key]:
            continue
        depths[key].add(depth)
        pending.extend((target, depth + 1) for target in calls[key])
    return depths


@dataclass(frozen=True)
class _SourceEntryRoles:
    entry_locations: frozenset[tuple[str, int]]
    gotos: frozenset[tuple[str, int]]
    if_stores: tuple[tuple[str, int, int, int], ...]
    break_reads: tuple[tuple[str, int, int], ...]
    foreign_fields: frozenset[int]
    numeric_ranges: tuple[tuple[int, int], ...]


def _source_entry_roles(
    data: bytes, programs: dict, writes: ScenarioSourceWriteWitnesses
) -> _SourceEntryRoles | PositiveEntryFailure:
    """Unsealed source analysis, never sufficient positive/native authority."""

    def require(condition, reason=PositiveEntryFailure.Control):
        if not condition:
            raise _Unsupported(reason)

    try:
        roots = {"16:0", "17:0", "17:1"}
        require(roots <= programs.keys())
        calls = {key: set() for key in programs}
        bindings, gotos, controls = {}, set(), []
        require(
            type(writes) is ScenarioSourceWriteWitnesses,
            PositiveEntryFailure.SourceWrite,
        )
        numeric = _numeric_copy_ranges(data, programs)
        for key, program in programs.items():
            for row in program["commands"]:
                at, opcode = row["offset"], row["opcode"]
                packet = data[at : row["next"]]
                controls.append((at, at + 1))
                require(opcode not in (3, 0x19, 0x1B, 0x1C, 0x6C, 0x6E, 0x8D))
                if opcode in (
                    1,
                    4,
                    5,
                    6,
                    7,
                    8,
                    0x0F,
                    0x11,
                    0x12,
                    0x13,
                    0x14,
                    0x15,
                    0x16,
                    0x17,
                    0x18,
                    0x1A,
                ) or row["kind"] in ("item", "door", "interaction", "reset"):
                    controls.append((at, row["next"]))
                elif opcode == 0x0D:
                    controls.append((at, at + 4))
                if row["kind"] == "call":
                    target = f"17:{packet[1]}"
                    require(target in programs)
                    calls[key].add(target)
                elif opcode == 4:
                    require(
                        packet[2] == 0x18 and (2 <= packet[1] < 10 or packet[1] == 0xFF)
                    )
                    target = f"17:{packet[3]}"
                    require(target in programs)
                    roots.add(target)
                elif opcode == 5:
                    require(2 <= packet[1] < 10)
                elif opcode == 0x17:
                    require(
                        packet[1:4] == b"\xff\xff\0"
                        and row["target"] == program["entry"]
                    )
                    gotos.add((key, at))
                if row["kind"] in ("item", "door", "interaction", "reset"):
                    kind = (
                        2
                        if row["kind"] == "item"
                        else 1
                        if row["kind"] == "door"
                        else packet[2]
                    )
                    require(packet[1] < 32 and kind <= 14)
                    bindings.setdefault(packet[1], set()).add(kind)
                    if kind == 5:
                        offset = (
                            4
                            if row["kind"] == "reset"
                            else 22
                            if opcode == 0x67
                            else 14
                        )
                        require(packet[offset : offset + 3] == b"\xff\0\x18")
                        target = f"17:{packet[offset + 3]}"
                        require(target in programs)
                        # Every creator/reset alternative contributes, even
                        # in a procedure not yet known to have an incoming edge.
                        roots.add(target)
        for program in programs.values():
            for row in program["commands"]:
                if row["opcode"] == 0x47:
                    kinds = bindings.get(data[row["offset"] + 1], set())
                    require(bool(kinds) and 5 not in kinds)
        require(calls_fit_native_frames(calls))
        require(
            not any(key in targets for key, _ in gotos for targets in calls.values())
        )
        # Return reconstructs a canonical IF pointer rather than the escaped
        # pointer. A writer with Gosub needs a separate return-field role;
        # treating that call as neutral would invent its later store targets.
        require(all(not calls[key] for key, _ in gotos))
        allowed = (
            *numeric,
            *(
                (r["offset"] + (4 if r["opcode"] == 0x23 else 2), r["next"])
                for p in programs.values()
                for r in p["commands"]
                if r["opcode"] in (0x23, 0x32, 0x6D)
            ),
        )
        require(
            all(
                any(
                    start <= copy.target_offset
                    and copy.target_offset + copy.width <= end
                    for start, end in allowed
                )
                for copy in writes.copies
            ),
            PositiveEntryFailure.SourceWrite,
        )
        # Excluding a native effect never excludes its source from protection.
        # This rejects control writes even in unentered procedures.
        require(
            not any(
                copy.target_offset < end and start < copy.target_offset + copy.width
                for copy in writes.copies
                for start, end in controls
            ),
            PositiveEntryFailure.SourceWrite,
        )
        depths = _call_depths(programs, roots, calls)
        frames = {}
        for key in programs:
            if depths[key]:
                result = structured_control(
                    data, programs[key], ControlFrames.FreshPositive
                )
                require(type(result) is StructuredControl)
                frames[key] = result
        if_stores, break_reads = [], []
        foreign = set()
        for key, result in frames.items():
            for at, pointer, target in result.if_stores:
                for depth in depths[key]:
                    cell = pointer + depth * IF_FRAME_WIDTH
                    if_stores.append((key, at, cell, target))
                    if pointer >= GOTO_FF_IF_BASE:
                        require(depth == 0, PositiveEntryFailure.ForeignConsumer)
                        delta, offset = divmod(cell, TASK_WIDTH)
                        require(
                            delta > 0 and delta + 9 < 14,
                            PositiveEntryFailure.ForeignConsumer,
                        )
                        foreign.add(offset)
            break_reads.extend(
                (key, at, loop_end_cell(depth, loop))
                for at, loop in result.break_reads
                for depth in depths[key]
            )
        require(
            _foreign_fields_disjoint(
                frozenset(foreign), tuple(read for _, _, read in break_reads)
            ),
            PositiveEntryFailure.ForeignConsumer,
        )
        return _SourceEntryRoles(
            frozenset((key, programs[key]["entry"]) for key in frames),
            frozenset(gotos),
            tuple(sorted(if_stores)),
            tuple(sorted(break_reads)),
            frozenset(foreign),
            numeric,
        )
    except _Unsupported as error:
        return error.reason
    except (KeyError, IndexError, TypeError, ValueError):
        return PositiveEntryFailure.Control


def _foreign_fields_disjoint(foreign: frozenset[int], reads: tuple[int, ...]) -> bool:
    # WHILE writes its own end before atomic predicate consumption. Break
    # retains the end pointer across arbitrary source effects and must be
    # checked separately against every possible ordinary/auxiliary consumer.
    other_fields = set(range(0x140, 0x154))
    for depth in range(NATIVE_CALL_FRAME_COUNT):
        other_fields.update(range(0x20 + 16 * depth, 0x30 + 16 * depth))
        other_fields.update(range(0xA0 + 8 * depth, 0xA8 + 8 * depth))
        other_fields.update(
            range(
                IF_FRAME_BASE + IF_FRAME_WIDTH * depth,
                IF_FRAME_BASE + IF_FRAME_WIDTH * (depth + 1),
            )
        )
        other_fields.update(range(0x0C + 4 * depth, 0x10 + 4 * depth))
    return not any(
        any(cell <= byte < cell + 4 for byte in other_fields) for cell in foreign
    ) and not any(
        cell <= read + 3 and read <= cell + 3 for cell in foreign for read in reads
    )


def _derive_entry_domain(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
) -> _EntryFacts | PositiveEntryFailure:
    from games.re2.event_presence import (
        presence_counter_indices,
        presence_flag_write_proof,
    )
    from games.re2.positive_prefix import (
        _POSITIVE_BINDING_SHA256,
        PositivePrefixPolicy,
        _positive_binding_digest,
        positive_prefix_policy,
    )
    from games.re2.room_data import decode_room
    from games.re2.scenario_selection import SCENARIO_EXECUTABLE_SHA256

    def require(condition, reason=PositiveEntryFailure.Control):
        if not condition:
            raise _Unsupported(reason)

    try:
        require(
            type(bound) is BoundStartupDeclarations and type(data) is bytes,
            PositiveEntryFailure.Binding,
        )
        require(
            positive_prefix_policy(profile) is PositivePrefixPolicy.TrustedNormalEngine,
            PositiveEntryFailure.Binding,
        )
        require(
            startup_flag_banks_match(profile, bound.declarations)
            and profile["runtime_layout"]["system_mode_mask"] == 0x40
            and profile["runtime_layout"]["system_mode_value"] == 0x40,
            PositiveEntryFailure.Binding,
        )
        resources = bound.entry_resources
        require(
            type(bound.ordinary_ingress) is type(resources.ordinary_ingress)
            and _positive_binding_digest(bound.ordinary_ingress, ())
            == _positive_binding_digest(resources.ordinary_ingress, ()),
            PositiveEntryFailure.Binding,
        )
        require(
            _positive_binding_digest(resources, bound.declarations)
            == _POSITIVE_BINDING_SHA256,
            PositiveEntryFailure.Binding,
        )
        executable = resources.executable
        # Full identity is mandatory before any native instruction interpretation.
        require(
            type(executable) is bytes
            and hashlib.sha256(executable).hexdigest() == SCENARIO_EXECUTABLE_SHA256,
            PositiveEntryFailure.Binding,
        )
        require(
            resources.ordinary_ingress.covers(data, room), PositiveEntryFailure.Binding
        )
        decoded = decode_room(
            data,
            room["source"],
            frozenset(
                (r["bank"], r["bit"]) for r in profile["presence_condition_flags"]
            ),
            presence_counter_indices(profile),
            presence_flag_write_proof(profile)[0],
        )
        require(
            all(
                json.dumps(decoded[k], sort_keys=True)
                == json.dumps(room[k], sort_keys=True)
                for k in decoded
            ),
            PositiveEntryFailure.Binding,
        )
        # These audited windows identify producer argument order, fresh roots,
        # descriptor ownership and the two newly used native scalar effects.
        # No extra resource is implied: all code is in the pinned executable;
        # source/auxiliary bytes come from the actual complete bound corpus.
        windows = (
            (
                0x800538A4,
                0x80,
                "e7b522273320dbfc0cc4ce549a58a3d14d17bdce1c2f6e69033807e880e68371",
            ),
            (
                0x80054020,
                0x298,
                "360ff21e546ef91d16f938422756a3344db7fa70c70c41122c584a2f72065b75",
            ),
            (
                0x80054760,
                44,
                "efec9417d7979e8fb3415501c3e8762bef8184f64d6e85f09d87f86e61707412",
            ),
            (
                0x80052CA0,
                116,
                "4abb0c573c555b6dba5410ffdcd5b891d384785fe9d73062fcb818af07fdc5a3",
            ),
            (
                0x80015FE8,
                64,
                "a4e0ed85f10c3fbd7407b675ae13e878afb357cdcc02a2fb1bd161ca1b0c955f",
            ),
        )
        require(
            all(
                hashlib.sha256(native_bytes(executable, at, width)).hexdigest()
                == digest
                for at, width, digest in windows
            ),
            PositiveEntryFailure.Binding,
        )
        require(
            int.from_bytes(native_bytes(executable, 0x800A73D8, 4), "little")
            == 0x80051980,
            PositiveEntryFailure.Binding,
        )
        native_entries = (
            (0x80013E28, 0x800530EC),  # auxiliary reset/root
            (0x800519A8, 0x80053138),  # registered kind5 payload
            (0x8005322C, 0x800530EC),  # fresh installer forwarding
            (0x800535E0, 0x80053138),  # initialization16:0
            (0x80053600, 0x80053138),  # initialization17:0
            (0x800536A4, 0x80053138),  # refresh17:1
            (0x8005388C, 0x800530EC),  # EventNext, rejected in source
            (0x800538C4, 0x80053138),  # EventExec source payload
        )
        require(
            all(
                int.from_bytes(native_bytes(executable, at, 4), "little")
                == 0x0C000000 | ((target >> 2) & 0x3FFFFFF)
                for at, target in native_entries
            ),
            PositiveEntryFailure.Binding,
        )
        # DEFAULT advances only PC+2. Operandless Rand publishes PC+1 before
        # updating its fixed RNG state and counter29; neither dispatches SCD.
        require(
            all(
                int.from_bytes(
                    native_bytes(executable, 0x800A74C8 + op * 4, 4), "little"
                )
                == handler
                for op, handler in (
                    (4, 0x800538A4),
                    (5, 0x800538DC),
                    (0x15, 0x80054110),
                    (0x28, 0x80054760),
                )
            ),
            PositiveEntryFailure.Binding,
        )
        writes = scenario_source_write_witnesses(data, room, profile)
        source = _source_entry_roles(data, room["programs"], writes)
        if type(source) is not _SourceEntryRoles:
            return source
        foreign = source.foreign_fields
        auxiliary_reads = []
        for script in resources.corpus.scripts:
            auxiliary = json.loads(script.programs_json)
            aux_calls = {key: set() for key in auxiliary}
            aux_roots = {"17:0"}
            for key, program in auxiliary.items():
                for row in program["commands"]:
                    packet = script.data[row["offset"] : row["next"]]
                    require(
                        row["opcode"]
                        not in (
                            3,
                            0x19,
                            0x1B,
                            0x1C,
                            0x2C,
                            0x3B,
                            0x46,
                            0x47,
                            0x4E,
                            0x67,
                            0x68,
                            0x69,
                            0x6C,
                            0x6E,
                            0x8D,
                        )
                    )
                    if row["kind"] == "call":
                        aux_calls[key].add(f"17:{packet[1]}")
                    elif row["opcode"] == 4:
                        require(packet[1] >= 10 and packet[2] == 0x18)
                        aux_roots.add(f"17:{packet[3]}")
            require(calls_fit_native_frames(aux_calls))
            aux_depths = _call_depths(auxiliary, aux_roots, aux_calls)
            for key, program in auxiliary.items():
                if not aux_depths[key]:
                    continue
                result = structured_control(
                    script.data, program, ControlFrames.FreshPositive
                )
                require(type(result) is StructuredControl)
                # The actual ingress binder retains its separate auxiliary
                # poll roles. Here every reachable Break contributes its read
                # cell, regardless of which ordinary slot might write it.
                auxiliary_reads.extend(
                    (script.model, key, at, loop_end_cell(depth, loop))
                    for at, loop in result.break_reads
                    for depth in aux_depths[key]
                )
        require(
            _foreign_fields_disjoint(
                foreign, tuple(read for *_, read in auxiliary_reads)
            ),
            PositiveEntryFailure.ForeignConsumer,
        )
        return _EntryFacts(
            source.entry_locations,
            source.gotos,
            source.if_stores,
            source.break_reads,
            tuple(sorted(auxiliary_reads)),
            source.numeric_ranges,
            windows,
            native_entries,
        )
    except _Unsupported as error:
        return error.reason
    except (KeyError, IndexError, TypeError, ValueError):
        return PositiveEntryFailure.Binding


class _Unsupported(Exception):
    def __init__(self, reason):
        self.reason = reason


def _positive_entry_domain(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
) -> _PositiveEntryDomain | PositiveEntryFailure:
    result = _derive_entry_domain(data, room, profile, bound)
    if type(result) is not _EntryFacts:
        return result
    return _PositiveEntryDomain(
        bound,
        data,
        json.dumps(room, sort_keys=True, separators=(",", ":")),
        json.dumps(profile, sort_keys=True, separators=(",", ":")),
        result,
    )
