"""RE2-DOOR-011: sealed bounded native FF/FF door frame and receiver facts.

No positive, Guard, identity-filtering or registration receipt is an input.
The complete owned corpus is mandatory even when its source roles are unsupported.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from enum import Enum

from games.re2.native_entry_fields import (
    NativeTaskPhase,
    _native_entry_witnesses,
    _NativeEntryWitnesses,
    _task_fields,
    _TaskFields,
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
from games.re2.scenario_items import scenario_flags
from games.re2.scenario_selection import (
    ScenarioSelectionFailure,
    ScenarioSourceWriteWitnesses,
    SourceWritePolicy,
    scenario_source_write_witnesses,
)
from games.re2.startup_declarations import BoundStartupDeclarations
from games.re2.structured_control import (
    ControlFrames,
    PredicateOutcome,
)

DOOR_ENTRY_AUDIT = "slus00748-bounded-ff-native-door-entry-v2"
_SEAL = object()


class DoorEntryFailure(Enum):
    Binding = "door_entry_native_source_binding"
    Auxiliary = "door_entry_auxiliary_fields"


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
        native = _native_entry_witnesses(executable)
        if type(native) is not _NativeEntryWitnesses:
            return DoorEntryFailure.Binding
        native_entries, windows = native.entries, native.windows
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
            result = _task_fields(
                aux_data,
                auxiliary["programs"],
                phase=NativeTaskPhase.Auxiliary,
                role=ControlFrames.NativeDoors,
            )
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
                data,
                room["programs"],
                phase=NativeTaskPhase.Ordinary,
                role=ControlFrames.NativeDoors,
                predicates=predicates,
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
