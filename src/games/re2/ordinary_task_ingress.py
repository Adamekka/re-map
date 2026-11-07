"""Normal ordinary-task ingress, separate from positive and door rights."""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.initializer_control_proof import native_switch_labels
from games.re2.native_control import goto_if_cell, native_bytes, native_nonyielding
from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    NATIVE_IF_FRAME_COUNT,
    NATIVE_LOOP_FRAME_COUNT,
    calls_fit_native_frames,
    programs_digest,
)
from games.re2.startup_entry_selection import (
    EXECUTABLE_SHA256,
    BoundAuxiliaryCorpus,
    VerifiedEntrySelection,
)

INGRESS_AUDIT = "slus00748-normal-ordinary-task-ingress-v1"


def _auxiliary_frames(data: bytes, program: dict) -> bool:
    """Bound shared IF/loop storage while retaining failed-predicate edges."""
    rows = {row["offset"]: row for row in program["commands"]}
    pending, seen = [(program["entry"], (), ())], set()
    try:
        while pending:
            pc, conditions, loops = pending.pop()
            state = pc, conditions, loops
            if state in seen:
                continue
            if len(seen) >= 16384 or pc not in rows:
                return False
            seen.add(state)
            row = rows[pc]
            op, following = row["opcode"], row["next"]
            packet = data[pc:following]
            if op == 1:
                continue
            if op == 6:
                if (
                    len(conditions) >= NATIVE_IF_FRAME_COUNT
                    or row["target"] <= following
                ):
                    return False
                pending.append((following, conditions + (row["target"],), loops))
            elif op == 0x23:
                pending.append((following, conditions, loops))
                if conditions:
                    pending.append((conditions[-1], conditions[:-1], loops))
            elif op in (7, 8):
                if not conditions or following != conditions[-1]:
                    return False
                pending.append(
                    (row["target"] if op == 7 else following, conditions[:-1], loops)
                )
            elif op == 9:
                if packet[1] != 10 or len(loops) >= NATIVE_LOOP_FRAME_COUNT:
                    return False
                pending.append((following, conditions, loops))
            elif op in (0x0D, 0x0F):
                end = following + int.from_bytes(packet[2:4], "little", signed=True)
                if (
                    len(loops) >= NATIVE_LOOP_FRAME_COUNT
                    or end <= following
                    or end not in rows
                ):
                    return False
                body = following
                if op == 0x0F:
                    body += packet[1]
                    cursor = following
                    while cursor < body:
                        if cursor not in rows or rows[cursor]["opcode"] != 0x23:
                            return False
                        cursor = rows[cursor]["next"]
                    if cursor != body or body not in rows:
                        return False
                pending.extend(
                    (
                        (end, conditions, loops),
                        (body, conditions, loops + ((op, pc, body, end, conditions),)),
                    )
                )
            elif op in (0x0E, 0x10):
                if not loops:
                    return False
                kind, header, body, end, saved = loops[-1]
                if (
                    (kind, op) not in ((0x0D, 0x0E), (0x0F, 0x10))
                    or following != end
                    or conditions != saved
                ):
                    return False
                pending.append((following, conditions, loops[:-1]))
                pending.append(
                    (
                        body if op == 0x0E else header,
                        conditions,
                        loops if op == 0x0E else loops[:-1],
                    )
                )
            elif op == 0x13:
                end, labels = native_switch_labels(data, pc, program["limit"])
                if (
                    len(loops) >= NATIVE_LOOP_FRAME_COUNT
                    or end not in rows
                    or any(at not in rows for at in labels)
                ):
                    return False
                frame = (op, pc, labels, end, conditions)
                for at in labels:
                    pending.append(
                        (
                            at if rows[at]["opcode"] == 0x16 else rows[at]["next"],
                            conditions,
                            loops + (frame,),
                        )
                    )
            elif op in (0x14, 0x15, 0x16, 0x1A):
                if not loops or loops[-1][0] != 0x13:
                    return False
                _, _, labels, end, saved = loops[-1]
                if op in (0x16, 0x1A):
                    if conditions != saved:
                        return False
                    pending.append((end, conditions, loops[:-1]))
                else:
                    if pc not in labels:
                        return False
                    pending.append((following, conditions, loops))
            elif op in (0x0A, 0x11, 0x12, 0x17):
                return False
            else:
                pending.append((following, conditions, loops))
        return True
    except (KeyError, ValueError):
        return False


class OrdinaryTaskIngressFailure(Enum):
    Binding = "ordinary ingress resource/source binding mismatch"
    Auxiliary = "auxiliary task/control isolation is unproved"
    CopyDomain = "auxiliary source-selected numeric domain is unproved"
    Route = "normal pending-payload route/model domain is unproved"
    NativeClock = "normal ordinary input-clock primitives are unproved"


@dataclass(frozen=True)
class _OrdinaryIngressDerivation:
    audit: str
    executable_sha256: str
    selection: VerifiedEntrySelection
    covered_models: frozenset[int]
    auxiliary_programs: tuple[tuple[int, str], ...]
    preserved_counters: frozenset[int]
    atomic_opcodes: frozenset[int]


@dataclass(frozen=True)
class VerifiedOrdinaryTaskIngress(_OrdinaryIngressDerivation):
    _derivation: _OrdinaryIngressDerivation

    def __post_init__(self) -> None:
        assert isinstance(self._derivation, _OrdinaryIngressDerivation)
        assert self._derivation == _OrdinaryIngressDerivation(
            self.audit,
            self.executable_sha256,
            self.selection,
            self.covered_models,
            self.auxiliary_programs,
            self.preserved_counters,
            self.atomic_opcodes,
        )
        assert self.audit == INGRESS_AUDIT
        assert self.executable_sha256 == EXECUTABLE_SHA256
        assert isinstance(self.selection, VerifiedEntrySelection)
        assert self.selection.executable_sha256 == self.executable_sha256
        assert type(self.covered_models) is frozenset and self.covered_models
        assert type(self.auxiliary_programs) is tuple
        assert {model for model, _ in self.auxiliary_programs} == self.covered_models
        assert all(len(digest) == 64 for _, digest in self.auxiliary_programs)
        assert type(self.preserved_counters) is frozenset
        assert type(self.atomic_opcodes) is frozenset

    def covers(self, data: bytes, room: dict) -> bool:
        models = self.selection.models_for(room["id"])
        # This is a distinct normal pending-payload contract. The legacy
        # selection.stages and its positive/door consumers remain unchanged.
        return (
            type(room["stage"]) is int
            and type(room["room"]) is int
            and 0 <= room["stage"] <= 255
            and 0 <= room["room"] <= 255
            and room["id"] == f"{room['stage']:02x}-{room['room']:02x}"
            and bool(models)
            and set(models) <= self.covered_models
            and any(
                row.room_id == room["id"]
                and row.path == room["source"]
                and row.width == len(data) == room["size"]
                and row.sha256 == room["sha256"] == hashlib.sha256(data).hexdigest()
                for row in self.selection.sources
            )
        )


def _copy_index_domain(data: bytes, program: dict, counter: int) -> bool:
    """Interpret one closed numeric worker, including counted loop iterations."""
    rows = {row["offset"]: row for row in program["commands"]}
    values, copies, loops = {}, {}, []
    position = program["entry"]
    for _ in range(32768):
        row = rows.get(position)
        if row is None:
            return False
        packet = data[position : row["next"]]
        op = row["opcode"]
        following = row["next"]
        if op == 1:
            return not loops
        if op == 0x24:
            values[packet[1]] = int.from_bytes(packet[2:4], "little")
        elif op == 0x25:
            if packet[2] in values:
                values[packet[1]] = values[packet[2]]
            else:
                values.pop(packet[1], None)
        elif op == 0x26:
            target, operation = packet[3], packet[2]
            if target in values and operation in (0, 1):
                operand = int.from_bytes(packet[4:6], "little")
                values[target] = (
                    values[target] + (operand if operation == 0 else -operand)
                ) & 65535
            else:
                values.pop(target, None)
        elif op == 0x1D:
            target = following + packet[2]
            width = 2 if packet[3] else 1
            if packet[1] == counter:
                if counter not in values or not 0 <= values[counter] < 10:
                    return False
                copies[target] = (width, values[counter])
        elif op == 0x2E and position + 2 in copies:
            if copies[position + 2][0] != 1 or packet[1] != 5:
                return False
        elif op == 0x0D:
            count = int.from_bytes(packet[4:6], "little")
            end = following + int.from_bytes(packet[2:4], "little", signed=True)
            if (
                not 1 <= count <= 1024
                or end not in rows
                or len(loops) >= NATIVE_LOOP_FRAME_COUNT
            ):
                return False
            loops.append((following, end, count))
        elif op == 0x0E:
            if not loops or loops[-1][1] != following:
                return False
            body, end, count = loops.pop()
            if count > 1:
                loops.append((body, end, count - 1))
                following = body
        elif op not in (0, 2, 9, 0x2E, 0x34):
            return False
        position = following
    return False


def auxiliary_isolation(
    auxiliaries: dict[int, tuple[bytes, dict]],
) -> frozenset[int] | OrdinaryTaskIngressFailure:
    """Derive phase-one births, foreign IF scratch and Copy requirements."""
    preserved = set()
    try:
        for data, room in auxiliaries.values():
            programs = room["programs"]
            edges = {key: set() for key in programs}
            rows = [(key, row) for key, p in programs.items() for row in p["commands"]]
            births, copy_counters = [], {}
            for key, row in rows:
                op, at = row["opcode"], row["offset"]
                packet = data[at : row["next"]]
                if op not in (
                    0,
                    1,
                    2,
                    4,
                    6,
                    7,
                    8,
                    9,
                    0x0D,
                    0x0E,
                    0x0F,
                    0x10,
                    0x13,
                    0x14,
                    0x15,
                    0x16,
                    0x17,
                    0x18,
                    0x1A,
                    0x1D,
                    0x23,
                    0x24,
                    0x25,
                    0x26,
                    0x2E,
                    0x2F,
                    0x30,
                    0x31,
                    0x34,
                    0x35,
                    0x36,
                    0x3D,
                    0x4D,
                    0x53,
                    0x74,
                    0x8A,
                    0x8B,
                    0x8C,
                ):
                    return OrdinaryTaskIngressFailure.Auxiliary
                if op in (
                    3,
                    5,
                    0x19,
                    0x1B,
                    0x1C,
                    0x22,
                    0x2B,
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
                ):
                    return OrdinaryTaskIngressFailure.Auxiliary
                if row["kind"] == "call":
                    edges[key].add(f"17:{packet[1]}")
                if op == 4:
                    # Phase one treats every value below 14 as explicit,
                    # including unsafe ordinary slots. 0E is already AUTO.
                    if packet[2] != 0x18 or packet[1] < 10:
                        return OrdinaryTaskIngressFailure.Auxiliary
                    births.append((key, packet[1], f"17:{packet[3]}"))
                if op == 0x2E and (packet[1] != 5 or packet[2] >= 10):
                    return OrdinaryTaskIngressFailure.Auxiliary
                if op == 0x4D and packet[1] >= 10 or op == 0x2F and packet[1] >= 12:
                    return OrdinaryTaskIngressFailure.Auxiliary
                if op in (0x34, 0x35) and packet[1] not in (11, 12, 13):
                    return OrdinaryTaskIngressFailure.Auxiliary
                if op == 0x3D and packet[2] not in (11, 12, 13):
                    return OrdinaryTaskIngressFailure.Auxiliary
                if op == 0x1D:
                    target, width = row["next"] + packet[2], 2 if packet[3] else 1
                    owners = [
                        r
                        for _, r in rows
                        if r["offset"] <= target and target + width <= r["next"]
                    ]
                    if len(owners) != 1:
                        return OrdinaryTaskIngressFailure.CopyDomain
                    owner = owners[0]
                    if (
                        owner["opcode"] == 0x2E
                        and target == owner["offset"] + 2
                        and width == 1
                    ):
                        copy_counters.setdefault(key, set()).add(packet[1])
                    elif not (
                        owner["opcode"] == 0x34
                        and target == owner["offset"] + 2
                        and width == 2
                    ):
                        return OrdinaryTaskIngressFailure.CopyDomain
            if any(
                not targets <= programs.keys() for targets in edges.values()
            ) or not calls_fit_native_frames(edges):
                return OrdinaryTaskIngressFailure.Auxiliary
            pending, reached = [(10, 0, "17:0")], set()
            while pending:
                task, depth, key = pending.pop()
                if (task, depth, key) in reached:
                    continue
                if key not in programs or depth >= NATIVE_CALL_FRAME_COUNT:
                    return OrdinaryTaskIngressFailure.Auxiliary
                reached.add((task, depth, key))
                pending.extend((task, depth + 1, target) for target in edges[key])
                for owner, selector, target in births:
                    if owner == key:
                        slots = (selector,) if selector < 14 else range(10, 14)
                        pending.extend((slot, 0, target) for slot in slots)
            for key, row in rows:
                if row["opcode"] != 0x17:
                    continue
                commands = programs[key]["commands"]
                packet = data[row["offset"] : row["next"]]
                # A new IF stores before its immediate predicate can consume
                # the escaped pointer. Yield is only on the true arm, followed
                # by Goto and a fresh store before the next own read.
                if (
                    [r["opcode"] for r in commands] != [6, 0x23, 2, 0, 0x17, 1]
                    or packet[1:4] != b"\xff\xff\0"
                    or row["target"] != programs[key]["entry"]
                    or commands[0]["target"] != commands[-1]["offset"]
                ):
                    return OrdinaryTaskIngressFailure.Auxiliary
                roles = {
                    (task, depth) for task, depth, owner in reached if owner == key
                }
                if not roles:
                    return OrdinaryTaskIngressFailure.Auxiliary
                for task, depth in roles:
                    receiver, offset = goto_if_cell(task, depth)
                    numeric_counts = receiver == 13 and offset == 0xA4
                    inactive = (
                        receiver == 13
                        and offset == 0x84
                        and all(task != receiver for task, _, _ in reached)
                    )
                    if not (numeric_counts or inactive):
                        return OrdinaryTaskIngressFailure.Auxiliary
            for program in programs.values():
                if not any(
                    r["opcode"] == 0x17 for r in program["commands"]
                ) and not _auxiliary_frames(data, program):
                    return OrdinaryTaskIngressFailure.Auxiliary
            for key, counters in copy_counters.items():
                # A concurrent writer would invalidate an affine index range.
                # Preserve these counters in the main source too, since aux
                # tasks survive ordinary reset and constructor yields.
                for counter in counters:
                    if not _copy_index_domain(data, programs[key], counter):
                        return OrdinaryTaskIngressFailure.CopyDomain
                    owners = set()
                    for owner, row in rows:
                        packet = data[row["offset"] : row["next"]]
                        index = {0x24: 1, 0x25: 1, 0x26: 3, 0x27: 2, 0x3D: 1}.get(
                            row["opcode"]
                        )
                        if index is not None and packet[index] == counter:
                            owners.add(owner)
                    roles = {
                        (task, depth) for task, depth, owner in reached if owner == key
                    }
                    if owners != {key} or len(roles) != 1 or next(iter(roles))[1] != 0:
                        return OrdinaryTaskIngressFailure.CopyDomain
                    preserved.add(counter)
        return frozenset(preserved)
    except (KeyError, IndexError, TypeError, ValueError):
        return OrdinaryTaskIngressFailure.Auxiliary


def ordinary_task_ingress(
    executable: bytes,
    corpus: BoundAuxiliaryCorpus,
) -> VerifiedOrdinaryTaskIngress | OrdinaryTaskIngressFailure:
    assert type(executable) is bytes and isinstance(corpus, BoundAuxiliaryCorpus)
    selection = corpus.selection
    auxiliaries = {
        row.model: (row.data, {"programs": json.loads(row.programs_json)})
        for row in corpus.scripts
    }
    if hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256:
        return OrdinaryTaskIngressFailure.Binding
    expected = {
        int(row.path[-6:-4], 16) for row in selection.resources if "/DOOR/" in row.path
    }
    if set(auxiliaries) != expected or not expected:
        return OrdinaryTaskIngressFailure.Binding
    if any(
        read_start < write_end and write_start < read_end
        for _, readers, writers in corpus.route_witnesses
        for read_start, read_end in readers
        for write_start, write_end in writers
    ):
        return OrdinaryTaskIngressFailure.Route
    preservation = auxiliary_isolation(auxiliaries)
    if isinstance(preservation, OrdinaryTaskIngressFailure):
        return preservation
    try:
        # These are normal lifecycle/control contracts on the exact executable,
        # not a claim about arbitrary heap, renderer or AI memory safety.
        # Room_load unconditionally enters the common initializer. It resets
        # 0..9, queues header16/task0 and header17/task1, clears auxiliary phase,
        # then schedules. Later ordinary passes seed main1/task0 separately.
        calls = {
            0x8002B264: 0x8002C610,
            0x8004A334: 0x80053528,
            0x800535B8: 0x80052F3C,
            0x800535E0: 0x80053138,
            0x80053600: 0x80053138,
            0x80053608: 0x800536C4,
            0x800536A4: 0x80053138,
        }
        if any(
            int.from_bytes(native_bytes(executable, at, 4), "little")
            != 0x0C000000 | ((target >> 2) & 0x3FFFFFF)
            for at, target in calls.items()
        ):
            return OrdinaryTaskIngressFailure.Binding
        # Normal new-game setup calls the global reset before source entry;
        # it explicitly clears Message busy. Every later normal door passes
        # the shared busy80 gate before its suspended RoomChange continuation.
        # Aux isolation forbids a Message initializer during constructor yields.
        # Thus clean Message ingress is historical native provenance, never a
        # sampled busy0 premise. The normal driver must finish its SYSTEM10000
        # clear wait before another ordinary SCD/AOT pass can run.
        if (
            native_bytes(executable, 0x8002C688, 8) != bytes.fromhex("0f80013c3c8720a0")
            or hashlib.sha256(native_bytes(executable, 0x80025970, 24)).hexdigest()
            != "3dd611a83d8a01be3f24916c1b5188a64b90e2a2db7ecd416b0c9007cd1f5bea"
        ):
            return OrdinaryTaskIngressFailure.NativeClock
        # The source-corpus pass checks every pending descriptor producer and
        # route writer. The normal setter 26C9C reloads that pending payload
        # after auxiliary completion, takes room+9 and stage+8 modulo9 for all
        # stages. Model+12 selects the DO2 before that same transition. Thus
        # only covered model sets get ingress; cross-kind model71 stays out.
        # This does not expand VerifiedEntrySelection.stages or its consumers.
        if native_bytes(executable, 0x80026D7C, 4) != bytes.fromhex("0900a290"):
            return OrdinaryTaskIngressFailure.Route
        # Bound native switches for initialized scalar Work, arithmetic,
        # member and sound handlers. All callees must also close without a
        # cooperative yield, including earlier persistent workers.
        specs = (
            (0x80055954, 0x800111F0, 5),
            (0x80055CCC, 0x80011228, 44),
            (0x80055F70, 0x800112F8, 44),
            (0x800544C4, 0x800111A0, 7),
            (0x80054650, 0x800111C0, 12),
            (0x8005B7A8, 0x80011608, 2),
            (0x80056470, 0x80011458, 5),
        )
        switches = {
            at: struct.unpack(f"<{count}I", native_bytes(executable, table, count * 4))
            for at, table, count in specs
        }
        # The source analyzer enforces these arithmetic and sound domains.
        # Unused division/error and sound modes get no atomicity permission.
        switches[0x80054650] = tuple(switches[0x80054650][i] for i in (0, 1, 5, 6))
        candidates = (
            0,
            0x21,
            0x22,
            0x23,
            0x26,
            0x29,
            0x2C,
            0x2E,
            0x2F,
            0x30,
            0x32,
            0x34,
            0x35,
            0x36,
            0x3B,
            0x3C,
            0x3D,
            0x46,
            0x4E,
            0x51,
            0x53,
            0x67,
            0x68,
            0x69,
        )
        atomic = frozenset(
            op
            for op in candidates
            if native_nonyielding(
                executable,
                int.from_bytes(
                    native_bytes(executable, 0x800A74C8 + op * 4, 4), "little"
                ),
                switches,
            )
        )
        # Flag1 starts player routine6, then captures STOP at its later phase2
        # UI request. Bind that native dispatch and the whole phase worker,
        # including its animation callee, before admitting delayed requests.
        player_dispatch = {
            0x800A4034: 0x8003C57C,
            0x800A406C: 0x8003E1D4,
            0x800A409C: 0x8003E1DC,
        }
        if any(
            int.from_bytes(native_bytes(executable, at, 4), "little") != target
            for at, target in player_dispatch.items()
        ):
            return OrdinaryTaskIngressFailure.NativeClock
        animation_switch = struct.unpack(
            "<7I", native_bytes(executable, 0x80010EF8, 28)
        )
        if not native_nonyielding(
            executable, 0x8003E1DC, {0x8003E210: animation_switch}
        ):
            return OrdinaryTaskIngressFailure.NativeClock
        # Acquired item constructors clear the registered source kind. Aot_on
        # still calls kind0, whose complete leaf writes counters0/1 and returns
        # zero. Bind that scalar-only dispatch before projecting its numeric
        # results as unknown predicates in the source interpreter.
        if int.from_bytes(
            native_bytes(executable, 0x800A73C4, 4), "little"
        ) != 0x800514EC or not native_nonyielding(executable, 0x800514EC, {}):
            return OrdinaryTaskIngressFailure.NativeClock
        derivation = _OrdinaryIngressDerivation(
            INGRESS_AUDIT,
            EXECUTABLE_SHA256,
            selection,
            frozenset(auxiliaries),
            tuple(
                (model, programs_digest(room["programs"]))
                for model, (_, room) in sorted(auxiliaries.items())
            ),
            preservation,
            atomic,
        )
        return VerifiedOrdinaryTaskIngress(
            derivation.audit,
            derivation.executable_sha256,
            derivation.selection,
            derivation.covered_models,
            derivation.auxiliary_programs,
            derivation.preserved_counters,
            derivation.atomic_opcodes,
            derivation,
        )
    except (ValueError, struct.error):
        return OrdinaryTaskIngressFailure.Binding
