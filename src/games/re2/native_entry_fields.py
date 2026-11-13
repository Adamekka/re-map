"""Shared unsealed native task/frame facts; policy compilers own authority."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.native_control import (
    TASK_BASE,
    TASK_WIDTH,
    ControlField,
    canonical_if_pointer,
    control_field,
    if_store_cell,
    loop_end_cell,
    native_bytes,
    native_nonyielding,
)
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    _foreign_fields_disjoint,
)
from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    calls_fit_native_frames,
)
from games.re2.structured_control import (
    ControlFrames,
    NativeStructuredControl,
    PredicateOutcome,
    structured_control,
)


class NativeTaskPhase(Enum):
    Ordinary = "ordinary tasks 0..9"
    Auxiliary = "door auxiliary tasks 10..13"


@dataclass(frozen=True)
class _TaskFields:
    producers: tuple[tuple[str, int, str, tuple[int, ...]], ...]
    entries: tuple[tuple[str, int, int], ...]
    stores: tuple[tuple[str, int, int, int, int, int, int], ...]
    reads: tuple[tuple[str, int, int, int, int], ...]
    control: tuple[tuple[str, int, int, int, ControlField, int, int, bool], ...]
    frames: tuple[tuple[str, NativeStructuredControl], ...]
    replacements: tuple[tuple[str, int, str], ...]
    calls: tuple[tuple[str, str], ...]
    initializations: tuple[tuple[str, int, int, ControlField, int, int, int], ...]
    loop_reads: tuple[tuple[str, int, int, int, int, bool], ...]


def _task_fields(
    data: bytes,
    programs: dict,
    *,
    phase: NativeTaskPhase,
    role: ControlFrames,
    predicates: tuple[tuple[str, tuple[tuple[int, PredicateOutcome], ...]], ...] = (),
) -> _TaskFields | PositiveEntryFailure:
    """Attach actual native task/depth roots to the existing shared frame walk."""
    assert type(phase) is NativeTaskPhase
    assert role in (ControlFrames.NativeDoors, ControlFrames.NativeIdentityFiltering)
    auxiliary = phase is NativeTaskPhase.Auxiliary
    # Native roots have no source offset. Their distinct owner marks the zero
    # placeholders; the actual native call sites are bound separately below.
    producers = (
        [("native", 0, "17:0", (10,))]
        if auxiliary
        else [
            ("native", 0, "16:0", (0,)),
            ("native", 0, "17:0", (1,)),
            ("native", 0, "17:1", (0,)),
        ]
    )
    calls = {key: set() for key in programs}
    replacements = []
    for key, program in programs.items():
        for row in program["commands"]:
            at, op = row["offset"], row["opcode"]
            packet = data[at : row["next"]]
            if row["kind"] == "call":
                calls[key].add(f"17:{packet[1]}")
            elif op == 3:
                if auxiliary or packet[1:3] != b"\0\x18":
                    return PositiveEntryFailure.Control
                replacements.append((key, at, f"17:{packet[3]}"))
            elif op == 4:
                # The phase-zero installer maps every selector>=10 to AUTO2..9.
                # Auxiliary phase has its separate explicit10..13/AUTO contract.
                start, limit = (10, 14) if auxiliary else (2, 10)
                tasks = (
                    (packet[1],) if packet[1] < limit else tuple(range(start, limit))
                )
                if packet[2] != 0x18 or auxiliary and packet[1] < 10:
                    return PositiveEntryFailure.Control
                producers.append((key, at, f"17:{packet[3]}", tasks))
            elif not auxiliary and row["kind"] in ("interaction", "reset"):
                if packet[2] != 5:
                    continue
                payload = 4 if row["kind"] == "reset" else 22 if op == 0x67 else 14
                if packet[payload : payload + 3] != b"\xff\0\x18":
                    return PositiveEntryFailure.Control
                producers.append(
                    (key, at, f"17:{packet[payload + 3]}", tuple(range(2, 10)))
                )
    if any(
        not targets <= programs.keys() for targets in calls.values()
    ) or not calls_fit_native_frames(calls):
        return PositiveEntryFailure.Control
    # Include every producer, including an unentered procedure's writers and
    # every Reset alternative. No sampled inactive task can remove a root.
    pending = [
        (target, task, 0)
        for owner, _, target, tasks in producers
        if not auxiliary or owner == "native"
        for task in tasks
    ]
    entries = set()
    while pending:
        key, task, depth = pending.pop()
        if (key, task, depth) in entries:
            continue
        if key not in programs or depth >= NATIVE_CALL_FRAME_COUNT:
            return PositiveEntryFailure.Control
        entries.add((key, task, depth))
        pending.extend((target, task, depth + 1) for target in calls[key])
        for owner, at, target in replacements:
            if owner == key:
                if depth != 0:
                    return PositiveEntryFailure.Control
                pending.append((target, task, depth))
        if auxiliary:
            pending.extend(
                (target, slot, 0)
                for owner, _, target, tasks in producers
                if owner == key
                for slot in tasks
            )
    stores, reads, control, frames, loop_reads, initializations = [], [], [], [], [], []
    outcomes = dict(predicates)
    for key, program in programs.items():
        roles = [(task, depth) for owner, task, depth in entries if owner == key]
        # Walk every program for control/source protection, but attach a native
        # receiving field only when an actual producer supplies task and depth.
        frame = structured_control(
            data, program, role, predicates=outcomes.get(key, ())
        )
        if type(frame) is not NativeStructuredControl:
            return PositiveEntryFailure.Control
        frames.append((key, frame))
        for task, depth in roles:
            # Installers and Gosub initialize levels/pointer, not IF target
            # cells. No unknown target or count is initialized by this proof.
            for field, value in (
                (ControlField.IfLevel, 255),
                (ControlField.LoopLevel, 255),
                (
                    ControlField.IfPointer,
                    TASK_BASE
                    + task * TASK_WIDTH
                    + control_field(
                        depth, ControlField.IfTarget, canonical_if_pointer(-1)
                    )[0],
                ),
            ):
                cell, width = control_field(depth, field, 0)
                initializations.append((key, task, depth, field, cell, width, value))
            for row in program["commands"]:
                if row["kind"] != "end" or row["offset"] not in frame.reached:
                    continue
                at = row["offset"]
                if depth == 0:
                    cell, width = control_field(depth, ControlField.Active, 0)
                    control.append(
                        (
                            key,
                            at,
                            task,
                            depth,
                            ControlField.Active,
                            task * TASK_WIDTH + cell,
                            width,
                            True,
                        )
                    )
                else:
                    for field, field_depth, write in (
                        (ControlField.CallDepth, depth, True),
                        (ControlField.CallReturn, depth - 1, False),
                        (ControlField.ProgramCounter, depth, True),
                        (ControlField.IfLevel, depth - 1, False),
                        (ControlField.IfPointer, depth - 1, True),
                    ):
                        cell, width = control_field(field_depth, field, 0)
                        control.append(
                            (
                                key,
                                at,
                                task,
                                depth,
                                field,
                                task * TASK_WIDTH + cell,
                                width,
                                write,
                            )
                        )
            loop_reads.extend(
                (key, at, task, depth, loop_end_cell(depth, loop), atomic)
                for at, loop, atomic in frame.loop_reads
            )
            for at, field, index, write in frame.accesses:
                cell, width = control_field(depth, field, index)
                receiver, offset = divmod(task * TASK_WIDTH + cell, TASK_WIDTH)
                if receiver >= 14 or offset + width > TASK_WIDTH:
                    return PositiveEntryFailure.ForeignConsumer
                control.append(
                    (
                        key,
                        at,
                        task,
                        depth,
                        field,
                        receiver * TASK_WIDTH + offset,
                        width,
                        write,
                    )
                )
            for at, pointer, target in frame.if_stores:
                receiver, offset = if_store_cell(task, depth, pointer)
                if receiver >= 14 or offset + 4 > TASK_WIDTH:
                    return PositiveEntryFailure.ForeignConsumer
                stores.append((key, at, task, depth, receiver, offset, target))
            reads.extend(
                (key, at, task, depth, loop_end_cell(depth, loop))
                for at, loop in frame.break_reads
            )
    foreign = frozenset(
        offset for _, _, task, _, receiver, offset, _ in stores if receiver != task
    )
    if not auxiliary and not _foreign_fields_disjoint(
        foreign, tuple(cell for *_, cell in reads)
    ):
        return PositiveEntryFailure.ForeignConsumer
    for _, _, task, depth, receiver, offset, _ in stores:
        if auxiliary and receiver != task:
            # These are the existing full auxiliary writer obligations. A4 is
            # numeric FOR count storage; 84 is safe only with no task13 entry.
            if not (
                receiver == 13
                and (
                    offset == 0xA4
                    or offset == 0x84
                    and all(t != 13 for _, t, _ in entries)
                )
            ):
                return PositiveEntryFailure.ForeignConsumer
        if receiver != task and any(
            other == receiver
            and offset <= cell + 3
            and cell <= offset + 3
            and not atomic
            for _, _, other, _, cell, atomic in loop_reads
        ):
            return PositiveEntryFailure.ForeignConsumer
        if receiver != task and any(
            other == receiver and offset <= cell + 3 and cell <= offset + 3
            for _, _, other, _, cell in reads
        ):
            return PositiveEntryFailure.ForeignConsumer
    return _TaskFields(
        tuple(sorted(producers)),
        tuple(sorted(entries)),
        tuple(sorted(stores)),
        tuple(sorted(reads)),
        tuple(
            sorted(
                control,
                key=lambda r: (r[0], r[1], r[2], r[3], r[4].value, r[5], r[6], r[7]),
            )
        ),
        tuple(sorted(frames)),
        tuple(sorted(replacements)),
        tuple(
            sorted(
                (key, target) for key, targets in calls.items() for target in targets
            )
        ),
        tuple(sorted(initializations, key=lambda r: (r[0], r[1], r[2], r[3].value))),
        tuple(sorted(loop_reads)),
    )


class NativeEntryFailure(Enum):
    Binding = "native entry handlers or installer binding mismatch"


@dataclass(frozen=True)
class _NativeEntryWitnesses:
    entries: tuple[tuple[int, int], ...]
    windows: tuple[tuple[int, int, str], ...]


def _native_entry_witnesses(
    executable: bytes,
) -> _NativeEntryWitnesses | NativeEntryFailure:
    """Check the shared native producers and atomic field-consumption graphs."""
    assert type(executable) is bytes
    try:
        windows = (
            (
                0x800530EC,
                428,
                "219bb5f2d377be2d79ca559e4f1e94d18361449d488c5b0a3985f7a5c5d3ce31",
            ),
            (
                0x80053528,
                400,
                "5a023ab6025298e578547e9b5aa3638a0319e7ced2a6087346852b23a2569605",
            ),
            (
                0x80051980,
                72,
                "b8d749d65bf13706baa4318d6a129548c129b3b06cf8fc26c1a70738598df3f2",
            ),
            (
                0x80053924,
                184,
                "0242027b221cd5f14c187b3bb3254fcd67f52304e4ba0ea3bbb9c601bd159aed",
            ),
            (
                0x80054354,
                96,
                "cc4ed0df629c94415d3769f3891487433ad205cef0136f31c17e4ee4123c17ed",
            ),
            (
                0x80053B1C,
                1600,
                "875fe6f1854934b2e83227930ccc5aa644317af097b5a34cb4658376b8188e07",
            ),
            (
                0x800537FC,
                296,
                "c13c9ed8e4bcee5afa3e84efa7a7a0104d0648dd9d63c6d5526b05b09e983ce4",
            ),
            (
                0x800111A0,
                28,
                "2ebc07d8ba0694afc8290590d9a63ac0338ebdc126a51229ec3d7b5af5e2e543",
            ),
            (
                0x80054474,
                192,
                "e3827d2183df46362af3744f448ce65afa61299af8a07fba12c35c4f6eb70cef",
            ),
            (
                0x8005415C,
                344,
                "76c315b1c78fcdc7a7d3b435ed9ce3c85a4b094d59dee39127da2b49a6090009",
            ),
            (
                0x800536C4,
                264,
                "2d6e34c985401d66077e1c1e6fde4f6555179852fcd2462d75b42c2f7456e298",
            ),
        )
        if any(
            hashlib.sha256(native_bytes(executable, at, width)).hexdigest() != digest
            for at, width, digest in windows
        ):
            return NativeEntryFailure.Binding
        expected_entries = (
            (0x80013E28, 0x800530EC),
            (0x800519A8, 0x80053138),
            (0x8005322C, 0x800530EC),
            (0x800535E0, 0x80053138),
            (0x80053600, 0x80053138),
            (0x800536A4, 0x80053138),
            (0x8005388C, 0x800530EC),
            (0x800538C4, 0x80053138),
        )
        installers = {
            0x0C000000 | ((target >> 2) & 0x3FFFFFF): target
            for target in (0x800530EC, 0x80053138)
        }
        native_entries = tuple(
            (0x80010000 + at * 4, installers[word])
            for at, (word,) in enumerate(struct.iter_unpack("<I", executable[0x800:]))
            if word in installers
        )
        if native_entries != expected_entries:
            return NativeEntryFailure.Binding
        # The bounded role consumes a foreign IF store only through its own
        # immediate CK/CMP. Bind the exact native switch and nonyielding
        # graphs. This grants no general atomic-token or actor-predicate right.
        switches = {
            0x800544C4: struct.unpack("<7I", native_bytes(executable, 0x800111A0, 28))
        }
        if not all(
            native_nonyielding(executable, entry, switches)
            for entry in (0x80053924, 0x80054354, 0x80054474)
        ):
            return NativeEntryFailure.Binding
        return _NativeEntryWitnesses(native_entries, windows)
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return NativeEntryFailure.Binding
