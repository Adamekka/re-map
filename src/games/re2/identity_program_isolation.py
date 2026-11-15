"""Unsealed identity program isolation, conditional on entered operative checks."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from games.re2.event_presence import presence_counter_indices
from games.re2.native_control import TASK_BASE, TASK_WIDTH
from games.re2.native_entry_fields import (
    _native_entry_witnesses,
    _NativeEntryWitnesses,
    _TaskFields,
)
from games.re2.normal_engine_binding import (
    NORMAL_ENGINE_BINDING_SHA256,
    typed_binding_digest,
)
from games.re2.positive_entry_domain import _NativeIdentityEntryRoles
from games.re2.script_control_limits import programs_digest

if TYPE_CHECKING:
    from games.re2.identity_filtering import IdentityFilteringPolicy, _IdentityDispatch
    from games.re2.scenario_selection import ScenarioSourceWriteWitnesses
    from games.re2.startup_declarations import BoundStartupDeclarations


class IdentityIsolationSupport(Enum):
    WholeSource = "original whole-source operative checks required"
    Binding = "program isolation source/native/owner binding is unproved"
    Entries = "program isolation canonical producer or frame is unproved"
    Metadata = "program isolation metadata preservation is unproved"
    Effects = "program isolation source effect or dispatch is unproved"


@dataclass(frozen=True)
class IdentityProgramIsolation:
    source_sha256: str
    programs_sha256: str
    source_roles_sha256: str
    entered_programs: frozenset[str]
    entry_locations: frozenset[tuple[str, int]]
    protected_source: tuple[tuple[int, int], ...]
    dependencies_sha256: str


def identity_program_isolation(
    data: bytes,
    room: dict,
    profile: dict,
    bound: BoundStartupDeclarations,
    native: _NativeEntryWitnesses,
    source: _NativeIdentityEntryRoles,
    writes: ScenarioSourceWriteWitnesses,
    auxiliary_fields: tuple[tuple[int, _TaskFields], ...],
    auxiliary_reads: tuple,
    registered: frozenset[int],
    dispatches: tuple[_IdentityDispatch, ...],
    owner: IdentityFilteringPolicy,
) -> IdentityProgramIsolation | IdentityIsolationSupport:
    """Preserve canonical entries without interpreting another SCD control flow.

    Success permits no store: the consumer must still validate every entered
    instruction with these same dependencies before its own authority seal.
    """
    from games.re2.identity_filtering import IdentityFilteringPolicy, _IdentityDispatch
    from games.re2.ordinary_task_ingress import auxiliary_isolation
    from games.re2.scenario_selection import ScenarioSourceWriteWitnesses

    assert type(data) is bytes and type(auxiliary_fields) is tuple
    assert type(auxiliary_reads) is tuple and type(dispatches) is tuple
    if (
        owner is not IdentityFilteringPolicy.TrustedNormalEngine
        or type(native) is not _NativeEntryWitnesses
        or type(source) is not _NativeIdentityEntryRoles
        or type(writes) is not ScenarioSourceWriteWitnesses
        or hashlib.sha256(data).hexdigest() != room["sha256"]
        or typed_binding_digest(native)
        != typed_binding_digest(
            _native_entry_witnesses(bound.entry_resources.executable)
        )
        or typed_binding_digest((bound.entry_resources, bound.declarations))
        != NORMAL_ENGINE_BINDING_SHA256
        or not bound.ordinary_ingress.covers(data, room)
    ):
        return IdentityIsolationSupport.Binding
    auxiliary = {
        s.model: (s.data, {"programs": json.loads(s.programs_json)})
        for s in bound.entry_resources.corpus.scripts
    }
    if (
        tuple(model for model, _ in auxiliary_fields) != tuple(sorted(auxiliary))
        or any(type(fields) is not _TaskFields for _, fields in auxiliary_fields)
        or auxiliary_isolation(auxiliary) != bound.ordinary_ingress.preserved_counters
    ):
        return IdentityIsolationSupport.Binding
    programs = room["programs"]
    fields = source.native_fields
    entered = frozenset(key for key, _, _ in fields.entries)
    frames = dict(fields.frames)
    if not entered or not entered <= programs.keys() or set(frames) != programs.keys():
        return IdentityIsolationSupport.Entries
    # The genuine shared inventory seeds every textual event/descriptor
    # alternative, even from an unentered owner. Calls/replacements then close
    # those actual roots. Missing knowledge never becomes an empty entry set.
    if (
        any(target not in entered for _, _, target, _ in fields.producers)
        or any(
            owner in entered and target not in entered for owner, target in fields.calls
        )
        or any(
            owner in entered and target not in entered
            for owner, _, target in fields.replacements
        )
        or source.entry_locations
        != frozenset((key, programs[key]["entry"]) for key in entered)
    ):
        return IdentityIsolationSupport.Entries
    for key in entered:
        offsets = {r["offset"] for r in programs[key]["commands"]}
        if programs[key]["entry"] not in offsets or any(
            at not in offsets or any(target not in offsets for target in targets)
            for at, targets in frames[key].edges
        ):
            return IdentityIsolationSupport.Entries
    sections = room["section_offsets"]
    protected = [(8 + 4 * section, 4) for section in (16, 17)]
    for section in (16, 17):
        extents = [
            r
            for r in writes.partitions.protected_source
            if r.offset == sections[section]
        ]
        if len(extents) != 1:
            return IdentityIsolationSupport.Metadata
        protected.append((extents[0].offset, extents[0].width))
    explicit_writes = [
        (r.offset, r.width)
        for effect in writes.partitions.source_writes
        for r in effect.writes
    ]
    explicit_writes.extend((r.offset, r.width) for r in writes.record_writes)
    explicit_writes.extend((r.target_offset, r.width) for r in writes.copies)
    explicit_writes.extend(
        (r.offset, r.width)
        for fact in source.compactions
        for r in (*fact.layout.copy_writes, *fact.rebind_writes)
    )
    if any(
        at < start + width and start < at + size
        for at, size in explicit_writes
        for start, width in protected
    ):
        return IdentityIsolationSupport.Metadata
    if any(
        fact.layout.retained_floor < program["limit"]
        for fact in source.compactions
        for program in programs.values()
    ):
        return IdentityIsolationSupport.Metadata
    layout = profile["runtime_layout"]
    control_ram = [
        (TASK_BASE, 14 * TASK_WIDTH),
        (0x800D8CBC, 4),
        (0x800D8CC8, 1),
        (0x800CE32C, 4),
    ]
    control_ram.extend(
        (
            int(layout[name], 0),
            layout["aot_capacity"] * 4 if name == "aot_table_address_ps1" else 4,
        )
        for name in ("loaded_rdt_address_ps1", "aot_table_address_ps1")
    )
    # Check complete configured numeric domains, not only this source's observed
    # writes. Every actual selector still needs the entered operative preflight.
    numeric = [(int(r["address_ps1"], 0), r["width"]) for r in profile["flag_banks"]]
    counter_base = int(layout["script_counter_address_ps1"], 0)
    numeric.extend(
        (counter_base + 2 * index, 2) for index in presence_counter_indices(profile)
    )
    numeric.extend(
        (o.record.address, o.record.width) for o in writes.partitions.objects
    )
    if any(
        at < start + width and start < at + size
        for at, size in numeric
        for start, width in control_ram
    ):
        return IdentityIsolationSupport.Metadata
    rows = [
        (key, r, data[r["offset"] : r["next"]])
        for key, p in programs.items()
        for r in p["commands"]
    ]
    if (
        any(
            (key, r["offset"])
            not in {(f.program, f.offset) for f in source.compactions}
            for key, r, _ in rows
            if r["opcode"] == 0x6C
        )
        or any(
            (key, r["offset"])
            not in {(f.program, f.offset) for f in source.primitive_reservations}
            for key, r, _ in rows
            if r["opcode"] == 0x5D
        )
        or type(registered) is not frozenset
        or any(type(fact) is not _IdentityDispatch for fact in dispatches)
        or {fact.slot for fact in dispatches}
        != {packet[1] for _, r, packet in rows if r["opcode"] == 0x47}
    ):
        return IdentityIsolationSupport.Effects
    for _, row, packet in rows:
        if row["kind"] not in ("door", "item", "interaction", "reset"):
            continue
        kind = 1 if row["kind"] == "door" else 2 if row["kind"] == "item" else packet[2]
        if (
            packet[1] >= 32
            or kind > 14
            or row["kind"] == "reset"
            and row["interaction"] not in (0, 4)
        ):
            return IdentityIsolationSupport.Effects
        # Kind5's complete creator/reset projection already participates in the
        # shared producer inventory. Keep all alternatives, including unentered
        # origins; pickup/Reset numeric operands need not all stay immutable.
        if kind == 5:
            operand = (
                4 if row["kind"] == "reset" else 22 if row["opcode"] == 0x67 else 14
            )
            if (
                packet[operand : operand + 3] != b"\xff\0\x18"
                or f"17:{packet[operand + 3]}" not in entered
            ):
                return IdentityIsolationSupport.Effects
    return IdentityProgramIsolation(
        room["sha256"],
        programs_digest(programs),
        typed_binding_digest(source),
        entered,
        source.entry_locations,
        tuple(protected),
        typed_binding_digest(
            (native, writes, auxiliary_fields, auxiliary_reads, registered, dispatches)
        ),
    )
