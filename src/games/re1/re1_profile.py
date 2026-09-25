"""RE1 profile skeleton with user-map candidates.

All numeric addresses must come from a profile JSON listed in profiles/.
None means unknown, never a guess. See docs/research.md RE1-USERMAP-001,
status Candidate, before promoting anything to Confirmed for a revision.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from games.game_profile import ItemListQuery, ItemQuery, RoomId, RoomItem, RoomQuery


@dataclass
class Re1Profile:
    profile_id: str
    # PS1 virtual addresses. None means unknown, not zero.
    # stage is Main Location 0x0c8660, room is SubLocation 0x0c8661
    # per docs/re1_ram_map_user_provided.md, Candidate only.
    stage_address: int | None = None
    room_address: int | None = None
    camera_address: int | None = None
    revision: str = "unknown"

    @staticmethod
    def load(path: Path) -> "Re1Profile":
        raw = json.loads(path.read_text())

        def _addr(key: str) -> int | None:
            v = raw.get(key)
            if v is None:
                return None
            return int(v, 16) if isinstance(v, str) else int(v)

        return Re1Profile(
            profile_id=str(raw.get("profile_id", path.stem)),
            stage_address=_addr("stage_address_ps1"),
            room_address=_addr("room_address_ps1"),
            camera_address=_addr("camera_address_ps1"),
            revision=str(raw.get("revision", "unknown")),
        )

    def has_room_addresses(self) -> bool:
        return self.stage_address is not None and self.room_address is not None

    @staticmethod
    def is_bit_set(byte_value: int, mask: int) -> bool:
        # Explicit bit test for Item Collected bytes. Mask must be one byte.
        assert 0 <= byte_value <= 0xFF, "byte_value must be 0..255"
        assert 0x01 <= mask <= 0xFF, "mask must be 1..255"
        return (byte_value & mask) != 0

    def detect_game(self) -> ItemQuery:
        return ItemQuery(ok=False, value=False, error="no game identity check implemented")

    def current_room(self) -> RoomQuery:
        if self.stage_address is None or self.room_address is None:
            return RoomQuery(ok=False, error="room addresses unknown for this revision")
        # Real read happens in the tracker loop once addresses validate.
        # This assert marks programmer error if wiring calls us with no reader.
        raise AssertionError("Re1Profile.current_room needs a memory reader; not wired yet")

    def enumerate_current_room_items(self, room: RoomId) -> ItemListQuery:
        return ItemListQuery(ok=True, items=(), complete_list_known=False)

    def is_item_collected(self, item: RoomItem) -> ItemQuery:
        if item.acquired_flag_address is None:
            return ItemQuery(ok=False, value=False, error="acquired flag unknown")
        raise AssertionError("Re1Profile.is_item_collected needs a memory reader; not wired yet")

    def is_item_currently_available(self, item: RoomItem) -> ItemQuery:
        # Unknown until spawn conditions are understood per item.
        return ItemQuery(ok=False, value=False, error=f"spawn condition unresolved: {item.spawn_condition}")
