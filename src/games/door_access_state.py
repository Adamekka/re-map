"""Door access wording shared by RE2 and RE3 descriptor readers."""

from __future__ import annotations


def door_access(
    enabled: bool, unlocked: bool, lock_id: int, key_type: int, key_label: str
) -> tuple[str, str]:
    """Return (state, label) for a door whose activation is established.

    Lock ID bit 7 marks a keyed lock. Key type 0xFE unlocks from this side.
    """
    if not enabled:
        return "BLOCKED", "Unlocked; door inactive" if unlocked else "Door is inactive"
    if unlocked:
        return "OPEN", "Unlocked"
    if not lock_id & 0x80:
        return "OPEN", "Open"
    if key_type == 0xFE:
        return "UNLOCKABLE", "Unlock from this side"
    return "LOCKED", key_label or "Locked"
