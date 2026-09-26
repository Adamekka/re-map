"""Debug view for milestone 1. No map yet.

Prints the exact lines from AGENTS.md plus whether the item list is known.
"""
from __future__ import annotations

from games.game_profile import RoomId
from tracker.exploration_state import RoomRecord


def render(
    room: RoomId | None,
    record: RoomRecord | None,
    profile_id: str = "unknown",
) -> str:
    if room is None:
        return "\n".join(
            [
                f"Profile: {profile_id}",
                "Current room: ??",
                "Visited: no",
                "Items: unknown",
                "Collected: unknown",
                "State: UNKNOWN",
                "List complete: no",
            ]
        )
    assert record is not None, "render needs a RoomRecord when room is known"
    visited = "yes" if record.visited else "no"
    # Zero with an incomplete list means no item coverage, not an empty room.
    items_known = record.total_items > 0 or record.list_complete
    items = str(record.total_items) if items_known else "unknown"
    collected = str(record.collected_items) if items_known else "unknown"
    return "\n".join(
        [
            f"Profile: {profile_id}",
            f"Current room: {room}",
            f"Visited: {visited}",
            f"Items: {items}",
            f"Collected: {collected}",
            f"State: {record.completion.value}",
            f"List complete: {'yes' if record.list_complete else 'no'}",
        ]
    )
