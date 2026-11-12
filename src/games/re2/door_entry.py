"""RE2-DOOR-010: separately sealed use of unchanged neutral entry facts.

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
    TASK_WIDTH,
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
    _source_entry_roles,
    _SourceEntryRoles,
)
from games.re2.scenario_selection import scenario_source_write_witnesses
from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    calls_fit_native_frames,
)
from games.re2.startup_declarations import BoundStartupDeclarations
from games.re2.structured_control import (
    ControlFrames,
    StructuredControl,
    structured_control,
)

DOOR_ENTRY_AUDIT = "slus00748-existing-neutral-door-entry-v1"
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


def _task_fields(data: bytes, programs: dict, *, auxiliary: bool):
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
    for key, program in programs.items():
        for row in program["commands"]:
            at, op = row["offset"], row["opcode"]
            packet = data[at : row["next"]]
            if row["kind"] == "call":
                calls[key].add(f"17:{packet[1]}")
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
    if not calls_fit_native_frames(calls):
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
        if auxiliary:
            pending.extend(
                (target, slot, 0)
                for owner, _, target, tasks in producers
                if owner == key
                for slot in tasks
            )
    stores, reads = [], []
    for key, program in programs.items():
        roles = [(task, depth) for owner, task, depth in entries if owner == key]
        if not roles:
            continue
        frame = structured_control(data, program, ControlFrames.FreshPositive)
        if type(frame) is not StructuredControl:
            return PositiveEntryFailure.Control
        for task, depth in roles:
            for at, pointer, target in frame.if_stores:
                receiver, offset = if_store_cell(task, depth, pointer)
                if receiver >= 14 or offset + 4 > TASK_WIDTH:
                    return PositiveEntryFailure.ForeignConsumer
                stores.append((key, at, task, depth, receiver, offset, target))
            reads.extend(
                (key, at, task, depth, loop_end_cell(depth, loop))
                for at, loop in frame.break_reads
            )
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
            other == receiver and offset <= cell + 3 and cell <= offset + 3
            for _, _, other, _, cell in reads
        ):
            return PositiveEntryFailure.ForeignConsumer
    return _TaskFields(
        tuple(sorted(producers)),
        tuple(sorted(entries)),
        tuple(sorted(stores)),
        tuple(sorted(reads)),
    )


@dataclass(frozen=True, init=False)
class _DoorEntryBinding:
    bound: BoundStartupDeclarations
    source_data: bytes
    room_json: str
    profile_json: str
    source: _SourceEntryRoles | PositiveEntryFailure
    source_fields: _TaskFields | PositiveEntryFailure
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
        # Existing source roles consume a foreign IF store only through their
        # immediate CMP. Bind its actual switch and both native nonyielding
        # graphs; this adds no predicate or source-opcode permission.
        switches = {
            0x800544C4: struct.unpack("<7I", native_bytes(executable, 0x800111A0, 28))
        }
        if not all(
            native_nonyielding(executable, entry, switches)
            for entry in (0x80053924, 0x80054474)
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
        source_fields = (
            _task_fields(data, room["programs"], auxiliary=False)
            if type(source) is _SourceEntryRoles
            else source
        )
        if type(source) is _SourceEntryRoles and type(source_fields) is not _TaskFields:
            return DoorEntryFailure.Binding
        foreign = (
            source.foreign_fields if type(source) is _SourceEntryRoles else frozenset()
        )
        auxiliary_reads = _auxiliary_break_reads(resources, foreign)
        if type(auxiliary_reads) is not tuple:
            return DoorEntryFailure.Auxiliary
        # Unsupported neutral analysis is explicit and grants no receiving-frame
        # right. The existing door path still enforces its original ban.
        values = (
            bound,
            data,
            json.dumps(room, sort_keys=True, separators=(",", ":")),
            json.dumps(profile, sort_keys=True, separators=(",", ":")),
            source,
            source_fields,
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
