"""Exploration state. Visit history stays separate from completion.

A visited room can have unknown item state. Being current never implies
cleared. When in doubt the tracker reports Unknown.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from games.game_profile import RoomId


class RoomCompletion(Enum):
    Unvisited = "UNVISITED"
    Incomplete = "INCOMPLETE"
    Cleared = "CLEARED"
    Unknown = "UNKNOWN"


@dataclass(frozen=True)
class ItemDetail:
    label: str
    state: str
    quantity: int


@dataclass(frozen=True)
class DoorDetail:
    source: RoomId
    target: RoomId
    state: str
    label: str


@dataclass
class RoomRecord:
    visited: bool = False
    total_items: int = 0
    collected_items: int = 0
    list_complete: bool = False
    completion: RoomCompletion = RoomCompletion.Unvisited
    items: tuple[ItemDetail, ...] = ()
    reason: str = ""


@dataclass
class Tracker:
    rooms: dict[str, RoomRecord] = field(default_factory=dict)
    current: RoomId | None = None
    region_visits: dict[str, str] = field(default_factory=dict)
    current_region: str = ""
    doors: tuple[DoorDetail, ...] = ()

    def _key(self, room: RoomId) -> str:
        return str(room)

    def mark_current(self, room: RoomId) -> None:
        self.current = room
        rec = self.rooms.get(self._key(room))
        if rec is None:
            rec = RoomRecord(visited=True, completion=RoomCompletion.Unknown)
            self.rooms[self._key(room)] = rec
        else:
            rec.visited = True

    def update_room_items(
        self,
        room: RoomId,
        total: int,
        collected: int,
        list_complete: bool,
        any_available_uncollected: bool,
        any_unknown: bool,
    ) -> RoomCompletion:
        """Apply item counts for a visited room and return its completion.

        Rules: one confirmed available uncollected item forces Incomplete.
        Unknown coverage or conditions force Unknown. Cleared needs a
        complete list, zero unknown, and zero remaining.
        """
        key = self._key(room)
        rec = self.rooms.get(key, RoomRecord(visited=True))
        rec.visited = True
        rec.total_items = total
        rec.collected_items = collected
        rec.list_complete = list_complete
        if any_available_uncollected:
            rec.completion = RoomCompletion.Incomplete
        elif any_unknown or not list_complete:
            rec.completion = RoomCompletion.Unknown
        elif total == 0 and list_complete and not any_unknown:
            # No collectibles understood for this room: cleared only when
            # the list is confirmed complete, else Unknown above applies.
            rec.completion = RoomCompletion.Cleared
        elif collected >= total:
            rec.completion = RoomCompletion.Cleared
        else:
            rec.completion = RoomCompletion.Incomplete
        self.rooms[key] = rec
        return rec.completion

    def room_state(self, room: RoomId) -> RoomRecord:
        rec = self.rooms.get(self._key(room))
        if rec is None:
            return RoomRecord()
        return rec
