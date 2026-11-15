"""Unsealed source-bound entry domain; each policy still checks entered effects."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from games.re2.native_entry_inventory import (
    NativeEntryInventory,
    NativeTaskPhase,
    native_entry_inventory,
)
from games.re2.normal_engine_binding import typed_binding_digest
from games.re2.positive_entry_domain import FrameDomain
from games.re2.scenario_selection import ScenarioSourceWriteWitnesses
from games.re2.script_control_limits import programs_digest


@dataclass(frozen=True)
class EnteredFrameDomain:
    source_sha256: str
    programs_sha256: str
    inventory: NativeEntryInventory
    entered_programs: frozenset[str]
    protected_source: tuple[tuple[int, int], ...]
    inert_operands: tuple[tuple[int, int], ...]
    writes_sha256: str

    def matches(
        self, data: bytes, programs: dict, inventory: NativeEntryInventory
    ) -> bool:
        return (
            self.source_sha256 == hashlib.sha256(data).hexdigest()
            and self.programs_sha256 == programs_digest(programs)
            and typed_binding_digest(self.inventory) == typed_binding_digest(inventory)
            and self.entered_programs
            == frozenset(key for key, _, _ in inventory.entries)
            and bool(self.entered_programs)
        )


def entered_frame_domain(
    data: bytes, room: dict, writes: ScenarioSourceWriteWitnesses
) -> EnteredFrameDomain | FrameDomain:
    """Derive raw closure before frames, preserving every textual producer.

    This supplies no native/owner/policy right. The mandatory policy compiler
    binds those premises and checks all entered instructions before its seal.
    """
    if (
        type(writes) is not ScenarioSourceWriteWitnesses
        or hashlib.sha256(data).hexdigest() != room["sha256"]
    ):
        return FrameDomain.Unproved
    programs = room["programs"]
    inventory = native_entry_inventory(data, programs, NativeTaskPhase.Ordinary)
    if type(inventory) is not NativeEntryInventory:
        return FrameDomain.Unproved
    entered = frozenset(key for key, _, _ in inventory.entries)
    if not entered or not entered <= programs.keys():
        return FrameDomain.Unproved
    blocks, protected, inert = [], [], []
    for section in (16, 17):
        start = room["section_offsets"][section]
        members = [p for k, p in programs.items() if k.startswith(f"{section}:")]
        if not members:
            return FrameDomain.Unproved
        end = max(p["limit"] for p in members)
        blocks.extend(((8 + 4 * section, 4), (start, end - start)))
        protected.extend(
            ((8 + 4 * section, 4), (start, min(p["entry"] for p in members) - start))
        )
    for key, program in programs.items():
        for row in program["commands"]:
            at, end, op = row["offset"], row["next"], row["opcode"]
            protected.append((at, 1))
            if row["kind"] in (
                "call",
                "if",
                "end",
                "door",
                "item",
                "interaction",
                "reset",
            ) or op in (
                3,
                4,
                5,
                7,
                8,
                9,
                0x0A,
                0x0B,
                0x0C,
                0x0F,
                0x10,
                0x11,
                0x12,
                0x13,
                0x14,
                0x15,
                0x16,
                0x17,
                0x19,
                0x1A,
                0x1B,
                0x1C,
                0x1D,
                0x47,
                0x5D,
                0x6C,
                0x8D,
            ):
                protected.append((at, end - at))
            elif op == 0x0D:
                protected.append((at, 4))
            elif key not in entered:
                # An excluded instruction cannot consume these operands. Its
                # opcode and every producer/control/write projection stay fixed.
                inert.append((at + 1, end))
    explicit = [(r.offset, r.width) for r in writes.record_writes]
    explicit.extend(
        (r.offset, r.width)
        for effect in writes.partitions.source_writes
        for r in effect.writes
    )
    if any(
        at < start + width and start < at + size
        for at, size in explicit
        for start, width in blocks
    ) or any(
        c.target_offset < start + width and start < c.target_offset + c.width
        for c in writes.copies
        for start, width in protected
    ):
        return FrameDomain.Unproved
    return EnteredFrameDomain(
        room["sha256"],
        programs_digest(programs),
        inventory,
        entered,
        tuple(protected),
        tuple(inert),
        typed_binding_digest(writes),
    )
