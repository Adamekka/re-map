"""SLUS-00421 Leon A identity and room reads. See RE2-IDENTITY-001."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from games.game_profile import ItemQuery, RoomId, RoomQuery
from games.runtime_identity import MemoryResult, RuntimeSignature


@dataclass(frozen=True)
class Re2Profile:
    profile_id: str
    revision: str
    executable_identity: str
    stage_address: int
    room_address: int
    camera_address: int
    runtime_signature: RuntimeSignature

    @staticmethod
    def load(path: Path) -> Re2Profile:
        raw = json.loads(path.read_text())
        if (
            raw["profile_id"] != "re2_leon_a_slus00421"
            or raw["serial"] != "SLUS-00421"
            or raw["scenario"] != "leon-a"
            or raw["address_space"] != "PS1 virtual address, little-endian"
            or raw["room_value_width_bytes"] != 2
        ):
            raise ValueError("unsupported RE2 revision, scenario or address layout")
        signature = raw["runtime_signature"]
        addresses = tuple(int(value, 0) for value in signature["window_addresses_ps1"])
        width = signature["window_width_bytes"]
        digest = signature["concatenated_sha256"]
        room_addresses = tuple(
            int(raw[key], 0)
            for key in ("stage_address_ps1", "room_address_ps1", "camera_address_ps1")
        )
        if (
            not addresses
            or type(width) is not int
            or not 1 <= width <= 4096
            or len(digest) != 64
            or any(value not in "0123456789abcdef" for value in digest)
            or any(
                not 0x80000000 <= address <= 0x80200000 - size
                for address, size in (
                    *((address, width) for address in addresses),
                    *((address, 2) for address in room_addresses),
                )
            )
        ):
            raise ValueError("invalid RE2 runtime identity or room addresses")
        return Re2Profile(
            raw["profile_id"],
            raw["revision"],
            raw["executable_identity"],
            *room_addresses,
            RuntimeSignature(addresses, width, digest),
        )

    def verify_runtime(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> ItemQuery:
        return self.runtime_signature.verify(read_memory)

    def read_current_room(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> RoomQuery:
        values = []
        for address in (self.stage_address, self.room_address):
            result = read_memory(address, 2)
            if not result.ok:
                return RoomQuery(ok=False, error=f"room read failed: {result.error}")
            if len(result.data) != 2:
                return RoomQuery(ok=False, error="room read failed: short reply")
            values.append(int.from_bytes(result.data, "little"))
        if values[0] > 6 or values[1] > 0x2F:
            return RoomQuery(ok=False, error="room identity outside the RE2 room range")
        return RoomQuery(ok=True, room=RoomId(*values))
