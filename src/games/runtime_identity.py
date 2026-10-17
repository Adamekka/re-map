"""Revision checks shared by the game profiles."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from games.game_profile import ItemQuery


class MemoryResult(Protocol):
    ok: bool
    data: bytes
    error: str


@dataclass(frozen=True)
class RuntimeSignature:
    window_addresses: tuple[int, ...]
    window_width: int
    concatenated_sha256: str

    def verify(self, read_memory: Callable[[int, int], MemoryResult]) -> ItemQuery:
        windows = []
        for address in self.window_addresses:
            result = read_memory(address, self.window_width)
            if not result.ok:
                return ItemQuery(
                    ok=False,
                    value=False,
                    error=f"signature read at {address:#x}: {result.error}",
                )
            if len(result.data) != self.window_width:
                return ItemQuery(
                    ok=False, value=False, error=f"short signature read at {address:#x}"
                )
            windows.append(result.data)
        digest = hashlib.sha256(b"".join(windows)).hexdigest()
        return ItemQuery(ok=True, value=digest == self.concatenated_sha256)
