"""RE2-DOOR-011: sealed bounded native FF/FF door frame and receiver facts.

No positive, Guard, identity-filtering or registration receipt is an input.
The complete owned corpus is mandatory even when its source roles are unsupported.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass, fields
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
from games.re2.normal_engine_binding import (
    NORMAL_ENGINE_BINDING_SHA256,
    semantic_profile_digest,
    typed_binding_digest,
)
from games.re2.ordinary_task_ingress import auxiliary_isolation
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    SourceEntryPolicy,
    _auxiliary_break_reads,
    _foreign_fields_disjoint,
    _source_entry_roles,
    _SourceEntryRoles,
)
from games.re2.scenario_items import scenario_flags
from games.re2.scenario_selection import (
    ScenarioSelectionFailure,
    ScenarioSourceWriteWitnesses,
    SourceWritePolicy,
    scenario_source_write_witnesses,
)
from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    calls_fit_native_frames,
)
from games.re2.startup_declarations import BoundStartupDeclarations
from games.re2.structured_control import (
    ControlFrames,
    NativeStructuredControl,
    PredicateOutcome,
    structured_control,
)

DOOR_ENTRY_AUDIT = "slus00748-bounded-ff-native-door-entry-v2"
_SEAL = object()


class DoorEntryFailure(Enum):
    Binding = "door_entry_native_source_binding"
    Auxiliary = "door_entry_auxiliary_fields"


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
    auxiliary: bool,
    predicates: tuple[tuple[str, tuple[tuple[int, PredicateOutcome], ...]], ...] = (),
):
    """Attach actual native task/depth roots to the existing shared frame walk."""
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
            data, program, ControlFrames.NativeDoors, predicates=outcomes.get(key, ())
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


@dataclass(frozen=True, init=False)
class _DoorEntryBinding:
    bound: BoundStartupDeclarations
    source_data: bytes
    room_json: str
    profile_json: str
    source: _SourceEntryRoles | PositiveEntryFailure
    source_fields: _TaskFields | PositiveEntryFailure
    source_writes: ScenarioSourceWriteWitnesses | ScenarioSelectionFailure
    auxiliary_fields: tuple[tuple[int, _TaskFields], ...]
    auxiliary_reads: tuple[tuple[int, str, int, int], ...]
    native_entries: tuple[tuple[int, int], ...]
    native_windows: tuple[tuple[int, int, str], ...]
    _binding: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError("door entry binding requires the owned-source compiler")

    def matches(self, data: bytes, room: dict, profile: dict, declarations) -> bool:
        assert type(self) is _DoorEntryBinding
        assert self._binding[0] is _SEAL
        assert all(
            getattr(self, f.name) is part
            for f, part in zip(fields(self)[:-1], self._binding[1:], strict=True)
        )
        return (
            type(data) is bytes
            and data == self.source_data
            and json.dumps(room, sort_keys=True, separators=(",", ":"))
            == self.room_json
            and json.dumps(profile, sort_keys=True, separators=(",", ":"))
            == self.profile_json
            and typed_binding_digest(declarations)
            == typed_binding_digest(self.bound.declarations)
        )


def compile_door_entry_binding(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
) -> _DoorEntryBinding | DoorEntryFailure:
    # Policy validation stays with the public authority, which also imports this
    # compiler. Delay this import to avoid a module-initialization cycle.
    from games.re2.door_authority import DOOR_PROFILE_SHA256, DoorPolicy, door_policy
    from games.re2.event_presence import (
        presence_counter_indices,
        presence_flag_write_proof,
    )
    from games.re2.room_data import decode_room
    from games.re2.scenario_selection import SCENARIO_EXECUTABLE_SHA256

    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert type(bound) is BoundStartupDeclarations
    try:
        resources = bound.entry_resources
        if not (
            door_policy(profile) is DoorPolicy.TrustedNormalEngine
            and semantic_profile_digest(profile) == DOOR_PROFILE_SHA256
            and typed_binding_digest((resources, bound.declarations))
            == NORMAL_ENGINE_BINDING_SHA256
            and typed_binding_digest(bound.ordinary_ingress)
            == typed_binding_digest(resources.ordinary_ingress)
            and bound.ordinary_ingress.covers(data, room)
            and hashlib.sha256(resources.executable).hexdigest()
            == SCENARIO_EXECUTABLE_SHA256
        ):
            return DoorEntryFailure.Binding
        decoded = decode_room(
            data,
            room["source"],
            frozenset(
                (r["bank"], r["bit"]) for r in profile["presence_condition_flags"]
            ),
            presence_counter_indices(profile),
            presence_flag_write_proof(profile)[0],
        )
        if any(
            json.dumps(value, sort_keys=True) != json.dumps(room[key], sort_keys=True)
            for key, value in decoded.items()
        ):
            return DoorEntryFailure.Binding
        executable = resources.executable
        # Bind the installer phases, kind-five dispatch and native frame/read
        # operations used by these existing neutral roles, before sealing them.
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
            return DoorEntryFailure.Binding
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
            return DoorEntryFailure.Binding
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
            return DoorEntryFailure.Binding
        auxiliaries = {
            script.model: (script.data, {"programs": json.loads(script.programs_json)})
            for script in resources.corpus.scripts
        }
        # Re-run the complete existing Copy/writer/phase proof. A matching
        # receipt mirror or an assumed inactive flag cannot replace this pass.
        if (
            auxiliary_isolation(auxiliaries)
            != resources.ordinary_ingress.preserved_counters
        ):
            return DoorEntryFailure.Auxiliary
        auxiliary_fields = []
        for model, (aux_data, auxiliary) in sorted(auxiliaries.items()):
            result = _task_fields(aux_data, auxiliary["programs"], auxiliary=True)
            if type(result) is not _TaskFields:
                return DoorEntryFailure.Auxiliary
            auxiliary_fields.append((model, result))
        writes = scenario_source_write_witnesses(data, room, profile)
        source = _source_entry_roles(
            data, room["programs"], writes, policy=SourceEntryPolicy.Existing
        )
        native_writes = scenario_source_write_witnesses(
            data, room, profile, policy=SourceWritePolicy.NormalDoors
        )
        source_fields = PositiveEntryFailure.SourceWrite
        if type(native_writes) is ScenarioSourceWriteWitnesses:
            fixed = {
                (r["bank"], r["bit"]): r["expected"] for r in scenario_flags(profile)
            }
            predicates = tuple(
                (
                    key,
                    tuple(
                        (
                            r["offset"],
                            PredicateOutcome.Matches
                            if fixed[r["bank"], r["bit"]] == r["expected"]
                            else PredicateOutcome.DoesNotMatch,
                        )
                        for r in p["commands"]
                        if r["kind"] == "flag_check"
                        and (r["bank"], r["bit"]) in fixed
                        and not any(
                            c.target_offset < r["next"]
                            and r["offset"] < c.target_offset + c.width
                            for c in native_writes.copies
                        )
                    ),
                )
                for key, p in room["programs"].items()
            )
            source_fields = _task_fields(
                data, room["programs"], auxiliary=False, predicates=predicates
            )
        foreign = (
            frozenset(
                offset
                for _, _, task, _, receiver, offset, _ in source_fields.stores
                if task != receiver
            )
            if type(source_fields) is _TaskFields
            else frozenset()
        )
        auxiliary_reads = _auxiliary_break_reads(resources, foreign)
        if type(auxiliary_reads) is not tuple:
            return DoorEntryFailure.Auxiliary
        # Unsupported native field analysis is explicit and grants no receiving-frame
        # right. The existing door path still enforces its original ban.
        values = (
            bound,
            data,
            json.dumps(room, sort_keys=True, separators=(",", ":")),
            json.dumps(profile, sort_keys=True, separators=(",", ":")),
            source,
            source_fields,
            native_writes,
            tuple(auxiliary_fields),
            auxiliary_reads,
            native_entries,
            windows,
        )
        result = object.__new__(_DoorEntryBinding)
        for f, value in zip(fields(result)[:-1], values, strict=True):
            object.__setattr__(result, f.name, value)
        object.__setattr__(result, "_binding", (_SEAL, *values))
        assert result.matches(data, room, profile, bound.declarations)
        return result
    except (KeyError, IndexError, TypeError, ValueError):
        return DoorEntryFailure.Binding
