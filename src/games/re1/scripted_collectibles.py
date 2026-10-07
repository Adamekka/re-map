"""Source-bound award access, never simulated acquisition. RE1-COLLECT-002."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from games.re1.event_state import EventProgram


def scripted_collectible_access(
    program: EventProgram, slot: int, item_type: int, record: int, entry: int
) -> bool:
    # Automatic allocation can pick an already-active final record when full.
    # Only an exact root record can prove a child will not overwrite its parent.
    if not 0 <= record < 8:
        return False
    for rule in program.collectible_rules:
        if rule.stages[0].entry != entry:
            continue
        return (
            rule.slot == slot
            and (
                1 <= item_type < 0x4E
                if rule.handler == 4
                else 0x4E <= item_type <= 0x53
            )
            and all(record != row[1] for stage in rule.stages for row in stage.starts)
        )
    return False
