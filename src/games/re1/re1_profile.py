"""RE1 memory interpretation; addresses come from profiles/*.json."""
from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol

from games.game_profile import ItemListQuery, ItemQuery, RoomId, RoomItem, RoomQuery


class MemoryResult(Protocol):
    ok: bool
    data: bytes
    error: str


class PilotItemState(Enum):
    OutsideRoom = "outside-room"
    UnsupportedVariant = "unsupported-variant"
    Available = "available"
    Taken = "taken"
    AvailabilityUnknown = "availability-unknown"
    ReadFailure = "read-failure"


@dataclass(frozen=True)
class PilotItemObservation:
    state: PilotItemState
    reason: str = ""


@dataclass(frozen=True)
class RuntimeSignature:
    window_addresses: tuple[int, ...]
    window_width: int
    concatenated_sha256: str


@dataclass(frozen=True)
class PilotItem:
    room: RoomId
    character_address: int
    character_value: int
    variant_word_address: int
    variant_mask: int
    source_rdt: str
    label: str
    global_id: int
    flag_address: int
    flag_mask: int
    aot_record_address: int
    aot_record_width: int
    active_handler: int
    pointer_offset: int
    expected_opcode_pointer: int


@dataclass
class Re1Profile:
    profile_id: str
    # PS1 virtual addresses. None means unknown, not zero.
    # The pinned SLUS-00551 profile confirms Main/Sub at these addresses;
    # other revisions keep their own validation status in profile JSON.
    stage_address: int | None = None
    room_address: int | None = None
    camera_address: int | None = None
    revision: str = "unknown"
    runtime_signature: RuntimeSignature | None = None
    pilot_item: PilotItem | None = None

    @staticmethod
    def load(path: Path) -> Re1Profile:
        raw = json.loads(path.read_text())

        def _number(v: int | str) -> int:
            if isinstance(v, str):
                if not v.startswith("0x"):
                    raise ValueError(f"profile number must use 0x prefix: {v!r}")
                return int(v, 16)
            return int(v)

        def _addr(key: str) -> int | None:
            v = raw.get(key)
            if v is None:
                return None
            return _number(v)

        signature_raw = raw.get("runtime_signature")
        signature = None
        if signature_raw is not None:
            signature = RuntimeSignature(
                window_addresses=tuple(
                    _number(v) for v in signature_raw["window_addresses_ps1"]
                ),
                window_width=_number(signature_raw["window_width_bytes"]),
                concatenated_sha256=str(signature_raw["concatenated_sha256"]),
            )
            if not signature.window_addresses or not 1 <= signature.window_width <= 4096:
                raise ValueError("runtime signature needs windows with width 1..4096")
            if len(signature.concatenated_sha256) != 64 or any(
                c not in "0123456789abcdef" for c in signature.concatenated_sha256
            ):
                raise ValueError("runtime signature SHA256 must be 64 lowercase hex digits")

        pilot_raw = raw.get("pilot_item")
        pilot = None
        if pilot_raw is not None:
            pilot = PilotItem(
                room=RoomId(
                    stage=_number(pilot_raw["room_main"]),
                    room=_number(pilot_raw["room_sub"]),
                ),
                character_address=_number(pilot_raw["character_address_ps1"]),
                character_value=_number(pilot_raw["character_value"]),
                variant_word_address=_number(pilot_raw["variant_word_address_ps1"]),
                variant_mask=_number(pilot_raw["variant_mask"]),
                source_rdt=str(pilot_raw["source_rdt"]),
                label=str(pilot_raw["label"]),
                global_id=_number(pilot_raw["global_id"]),
                flag_address=_number(pilot_raw["flag_address_ps1"]),
                flag_mask=_number(pilot_raw["flag_mask"]),
                aot_record_address=_number(pilot_raw["aot_record_address_ps1"]),
                aot_record_width=_number(pilot_raw["aot_record_width_bytes"]),
                active_handler=_number(pilot_raw["active_handler"]),
                pointer_offset=_number(pilot_raw["pointer_offset_bytes"]),
                expected_opcode_pointer=_number(
                    pilot_raw["expected_opcode_pointer_ps1"]
                ),
            )
            if not 0 < pilot.flag_mask <= 0xFF:
                raise ValueError("pilot item flag mask must fit one nonzero byte")
            if not 0 <= pilot.pointer_offset or not (
                pilot.pointer_offset + 4 <= pilot.aot_record_width <= 4096
            ):
                raise ValueError("pilot item opcode pointer must fit its AOT record")

        return Re1Profile(
            profile_id=str(raw.get("profile_id", path.stem)),
            stage_address=_addr("stage_address_ps1"),
            room_address=_addr("room_address_ps1"),
            camera_address=_addr("camera_address_ps1"),
            revision=str(raw.get("revision", "unknown")),
            runtime_signature=signature,
            pilot_item=pilot,
        )

    def has_room_addresses(self) -> bool:
        return self.stage_address is not None and self.room_address is not None

    @staticmethod
    def is_bit_set(byte_value: int, mask: int) -> bool:
        # Explicit bit test for Item Collected bytes. Mask must be one byte.
        assert 0 <= byte_value <= 0xFF, "byte_value must be 0..255"
        assert 0x01 <= mask <= 0xFF, "mask must be 1..255"
        return (byte_value & mask) != 0

    def verify_runtime(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> ItemQuery:
        signature = self.runtime_signature
        if signature is None:
            return ItemQuery(
                ok=False,
                value=False,
                error="runtime signature unavailable for this profile",
            )
        windows = []
        for address in signature.window_addresses:
            result = read_memory(address, signature.window_width)
            if not result.ok:
                return ItemQuery(
                    ok=False,
                    value=False,
                    error=f"signature read at {address:#x}: {result.error}",
                )
            if len(result.data) != signature.window_width:
                return ItemQuery(
                    ok=False, value=False, error=f"short signature read at {address:#x}"
                )
            windows.append(result.data)
        digest = hashlib.sha256(b"".join(windows)).hexdigest()
        return ItemQuery(ok=True, value=digest == signature.concatenated_sha256)

    def read_current_room(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> RoomQuery:
        if self.stage_address is None or self.room_address is None:
            return RoomQuery(ok=False, error="room addresses unknown for this revision")
        stage = read_memory(self.stage_address, 1)
        room = read_memory(self.room_address, 1)
        if not stage.ok or not room.ok:
            return RoomQuery(ok=False, error=f"room read failed: {stage.error} {room.error}")
        if len(stage.data) != 1 or len(room.data) != 1:
            return RoomQuery(ok=False, error="room read failed: short reply")
        return RoomQuery(ok=True, room=RoomId(stage.data[0], room.data[0]))

    def observe_pilot_item(
        self, room: RoomId, read_memory: Callable[[int, int], MemoryResult]
    ) -> PilotItemObservation:
        pilot = self.pilot_item
        if pilot is None or room != pilot.room:
            return PilotItemObservation(PilotItemState.OutsideRoom)

        reads = (
            ("character", pilot.character_address, 1),
            ("variant", pilot.variant_word_address, 4),
        )
        values = []
        for label, address, width in reads:
            result = read_memory(address, width)
            if not result.ok:
                return PilotItemObservation(
                    PilotItemState.ReadFailure, f"{label}: {result.error}"
                )
            if len(result.data) != width:
                return PilotItemObservation(
                    PilotItemState.ReadFailure, f"{label}: short read"
                )
            values.append(result.data)
        character, variant = values
        if character[0] != pilot.character_value:
            return PilotItemObservation(
                PilotItemState.UnsupportedVariant, "character not supported in pilot"
            )
        if not int.from_bytes(variant, "little") & pilot.variant_mask:
            return PilotItemObservation(
                PilotItemState.UnsupportedVariant, "Jill room variant not selected"
            )
        flag_result = read_memory(pilot.flag_address, 1)
        if not flag_result.ok or len(flag_result.data) != 1:
            reason = flag_result.error if not flag_result.ok else "short read"
            return PilotItemObservation(PilotItemState.ReadFailure, f"pickup flag: {reason}")
        flag = flag_result.data
        if not self.is_bit_set(flag[0], pilot.flag_mask):
            return PilotItemObservation(PilotItemState.Taken)
        aot_result = read_memory(pilot.aot_record_address, pilot.aot_record_width)
        if not aot_result.ok or len(aot_result.data) != pilot.aot_record_width:
            reason = aot_result.error if not aot_result.ok else "short read"
            return PilotItemObservation(PilotItemState.ReadFailure, f"item object: {reason}")
        aot = aot_result.data
        pointer = int.from_bytes(
            aot[pilot.pointer_offset : pilot.pointer_offset + 4], "little"
        )
        if aot[0] == pilot.active_handler and pointer == pilot.expected_opcode_pointer:
            return PilotItemObservation(PilotItemState.Available)
        return PilotItemObservation(
            PilotItemState.AvailabilityUnknown,
            "item object not active at the validated script row",
        )

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
