"""Access proofs for source-bound scripted doors, scoped in RE1-DOORS-006."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from games.re1.event_state import EventProgram


class ScriptedDoorAccess(Enum):
    Delegated = "delegated"
    Blocked = "blocked"
    Unresolved = "unresolved"


def scripted_door_access(
    program: EventProgram, slot: int, entry: int, opcode: bytes
) -> ScriptedDoorAccess:
    assert len(opcode) == 26 and opcode[:2] == bytes((0x0C, slot))
    for rule in program.door_rules:
        if rule.entry != entry:
            continue
        if not rule.door_slots:
            return ScriptedDoorAccess.Blocked
        if rule.door_slots != (slot,):
            return ScriptedDoorAccess.Unresolved
        if rule.changes_character and (
            opcode[14] & 0x40 or opcode[14] & 0x80 and opcode[24] == 0x33
        ):
            # These lock paths depend on the player state at dispatch. A
            # script changing it cannot reuse the caller's current state.
            return ScriptedDoorAccess.Unresolved
        return ScriptedDoorAccess.Delegated
    return ScriptedDoorAccess.Unresolved
