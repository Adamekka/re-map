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
    NumericCountPolicy,
    canonical_if_pointer,
    control_field,
    if_store_cell,
    loop_end_cell,
    native_bytes,
    native_nonyielding,
)
from games.re2.native_entry_inventory import (
    NativeEntryInventory,
    NativeTaskPhase,
    native_entry_inventory,
)
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    _foreign_fields_disjoint,
)
from games.re2.program_entry_domain import EnteredFrameDomain, FrameDomain
from games.re2.structured_control import (
    ControlFrames,
    NativeStructuredControl,
    PredicateOutcome,
    structured_control,
)


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
    numeric_counts: NumericCountPolicy = NumericCountPolicy.Existing,
    predicates: tuple[tuple[str, tuple[tuple[int, PredicateOutcome], ...]], ...] = (),
    frame_domain: EnteredFrameDomain | FrameDomain = FrameDomain.WholeSource,
    copy_predicates: tuple[tuple[str, int, int], ...] = (),
) -> _TaskFields | PositiveEntryFailure:
    """Attach actual native task/depth roots to the existing shared frame walk."""
    assert type(phase) is NativeTaskPhase
    assert role in (
        ControlFrames.NativeDoors,
        ControlFrames.NativeIdentityFiltering,
        ControlFrames.NativeIdentityRegistration,
    )
    assert type(numeric_counts) is NumericCountPolicy
    assert numeric_counts is NumericCountPolicy.Existing or role in (
        ControlFrames.NativeIdentityFiltering,
        ControlFrames.NativeIdentityRegistration,
    )
    assert not copy_predicates or role is ControlFrames.NativeDoors
    inventory = native_entry_inventory(data, programs, phase)
    if type(inventory) is not NativeEntryInventory:
        return inventory
    auxiliary = phase is NativeTaskPhase.Auxiliary
    producers, entries = inventory.producers, inventory.entries
    replacements, calls = inventory.replacements, inventory.calls
    if type(frame_domain) is EnteredFrameDomain:
        if not frame_domain.matches(data, programs, inventory):
            return PositiveEntryFailure.Binding
        frame_programs = frame_domain.entered_programs
    else:
        assert type(frame_domain) is FrameDomain
        frame_programs = frozenset(programs)
    stores, reads, control, frames, loop_reads, initializations = [], [], [], [], [], []
    outcomes = dict(predicates)
    for key, program in programs.items():
        if key not in frame_programs:
            continue
        roles = [(task, depth) for owner, task, depth in entries if owner == key]
        # Missing isolation keeps all original frames. A validated domain keeps
        # raw source protection separate and requires each entered frame here;
        # only actual producers supply receiving task/depth fields.
        frame = structured_control(
            data,
            program,
            role,
            predicates=outcomes.get(key, ()),
            copy_predicates=tuple(
                (header, predicate)
                for owner, header, predicate in copy_predicates
                if owner == key
            ),
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
        foreign, tuple(cell for *_, cell in reads), numeric_counts=numeric_counts
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
        if (
            role
            in (
                ControlFrames.NativeIdentityFiltering,
                ControlFrames.NativeIdentityRegistration,
            )
            and receiver != task
        ):
            # A suspended wait keeps its incremented LoopLevel. Foreign IF
            # stores must not corrupt that byte before its completing retry.
            if any(
                field is ControlField.LoopLevel
                and receiver * TASK_WIDTH + offset < cell + width
                and cell < receiver * TASK_WIDTH + offset + 4
                for _, _, _, _, field, cell, width, _ in control
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
        tuple(calls),
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
