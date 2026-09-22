"""Generic game profile interface.

RE1-specific addresses must live in profiles/*.json and src/games/re1/,
never here. All memory failures are explicit: callers get ok=False
instead of a guessed value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RoomId:
    stage: int
    room: int

    def __str__(self) -> str:
        return f"{self.stage:02d}-{self.room:02x}"


@dataclass(frozen=True)
class RoomItem:
    room: RoomId
    item_id: int
    acquired_flag_address: int | None = None
    acquired_flag_mask: int = 0xFF
    spawn_condition: str = "unknown"
    label: str = ""


@dataclass(frozen=True)
class ItemQuery:
    ok: bool
    value: bool
    error: str = ""


@dataclass(frozen=True)
class RoomQuery:
    ok: bool
    room: RoomId | None = None
    error: str = ""


@dataclass(frozen=True)
class ItemListQuery:
    ok: bool
    items: tuple[RoomItem, ...] = ()
    complete_list_known: bool = False
    error: str = ""


class GameProfile(Protocol):
    profile_id: str

    def detect_game(self) -> ItemQuery:
        """True if attached emulator runs the game this profile targets."""
        ...

    def current_room(self) -> RoomQuery:
        ...

    def enumerate_current_room_items(self, room: RoomId) -> ItemListQuery:
        ...

    def is_item_collected(self, item: RoomItem) -> ItemQuery:
        ...

    def is_item_currently_available(self, item: RoomItem) -> ItemQuery:
        ...
