"""Decode active SLUS-00551 Door_set records; see RE1-DOORS-002."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

from games.game_profile import RoomId


class DoorState(Enum):
    LOCKED = "locked"
    OPEN = "open"
    UNLOCKABLE = "unlockable"
    BLOCKED = "blocked"


@dataclass(frozen=True)
class DoorObservation:
    aot_id: int
    source: RoomId
    target: RoomId
    state: DoorState
    lock_id: int
    lock_type: int
    # Persistent unlock knowledge survives temporary/scripted passage blocking.
    unlocked: bool
    reason: str
    x: int
    z: int
    width: int
    depth: int
    animation: int
    mode: int


def decode_door_target(
    packed_target: int, source_stage: int, stage_remap: bool
) -> RoomId:
    """Decode a Door_set target byte to its runtime room.

    Why: the pinned executable's room transition at 0x8002A6E0..0x8002A73C
    keeps the current stage for encoded zero, otherwise uses encoded minus
    one, then adds five when the stage-remap flag (script flag group 0 index
    0, byte 0x800C8703 mask 0x80) is set and the result is 0 or 1. This maps
    late-game doors targeting 0/1 to returned-Mansion stages 5/6.
    """
    if not 0 <= packed_target <= 0xFF or not 0 <= source_stage <= 0xFF:
        raise ValueError("door target fields must fit one byte")
    if not isinstance(stage_remap, bool):
        # Why ValueError: callers model every door interpretation problem as
        # ValueError so live polling returns a read failure instead of crashing.
        raise ValueError("door stage remap must be an explicit boolean")  # noqa: TRY004
    encoded_stage = packed_target >> 5
    if encoded_stage == 0:
        return RoomId(source_stage, packed_target & 0x1F)
    stage = encoded_stage - 1
    if stage_remap and stage < 2:
        stage += 5
    return RoomId(stage, packed_target & 0x1F)


def stage_remap_flag(rule_layout) -> tuple[int, int]:
    """Return the (address, mask) of the door stage-remap flag.

    Why a helper: the remap coordinate (script flag group 0 index 0) is
    game-specific knowledge owned here, so callers read it through the
    profile layout instead of naming the group and index themselves.
    """
    return rule_layout.flag(0, 0)


def stage_remap_from_window(rule_layout, window: bytes) -> bool:
    """Read the remap flag from a 32-byte window starting at flag_bases[0]."""
    address, mask = stage_remap_flag(rule_layout)
    base = rule_layout.flag_bases[0]
    if not base <= address < base + len(window):
        raise ValueError("door stage remap flag is outside its flag window")
    return bool(window[address - base] & mask)


def parse_door(
    record_id: int,
    opcode: bytes,
    source: RoomId,
    unlock_flags: bytes,
    player_state: int,
    special_flag: int,
    stage_remap: bool,
) -> DoorObservation:
    """Parse one active handler-1 AOT whose pointer the caller has validated.

    ValueError models malformed external data. The caller supplies the pinned
    profile's eight unlock bytes, the two independently read state bytes, and
    the explicit stage-remap flag (script flag group 0 index 0); see
    decode_door_target. There is no default remap because guessing it would
    hide a wrong destination.
    """
    if len(opcode) != 26 or opcode[0] != 0x0C:
        raise ValueError("door requires a complete 26-byte Door_set opcode")
    if not 0 <= record_id <= 0xFF or opcode[1] != record_id:
        raise ValueError("door opcode does not match its active AOT record")
    if len(unlock_flags) != 8:
        raise ValueError("door requires all eight unlock flag bytes")
    if not 0 <= player_state <= 0xFF or not 0 <= special_flag <= 0xFF:
        raise ValueError("door state values must fit one byte")
    if not 0 <= source.stage <= 0xFF or not 0 <= source.room <= 0xFF:
        raise ValueError("door source room values must fit one byte")

    packed_target = opcode[15]
    target = decode_door_target(packed_target, source.stage, stage_remap)
    lock_id, lock_type = opcode[14], opcode[24]
    flag_index = lock_id & 0x3F
    # The executable numbers bits from the high end of little-endian words.
    flag_byte = 4 * (flag_index // 32) + 3 - ((flag_index % 32) // 8)
    flag_mask = 0x80 >> (flag_index % 8)
    unlocked = bool(unlock_flags[flag_byte] & flag_mask)

    # This player-state restriction precedes the persistent unlock test in game.
    if lock_id & 0x40 and player_state & 3 == 3:
        state, reason = DoorState.BLOCKED, "Cannot use this door in the current state"
    elif not lock_id & 0x80:
        state, reason = DoorState.OPEN, "No lock"
    elif unlocked:
        state, reason = DoorState.OPEN, "Unlocked"
    elif lock_type == 0xFE:
        state, reason = DoorState.UNLOCKABLE, "Can unlock from this side"
    elif lock_type == 0xFF:
        state, reason = DoorState.BLOCKED, "Locked from the other side"
    elif lock_type == 0x33 and player_state & 3 == 1:
        # This special path bypasses the ordinary inventory search. Possessing
        # the normal key cannot replace its separate flag in this player state.
        if special_flag & 0x08:
            state, reason = DoorState.UNLOCKABLE, "Can unlock without a key"
        else:
            state, reason = DoorState.LOCKED, "Required unlock ability is unavailable"
    elif lock_type == 0:
        # Zero denotes puzzle/script locks in the disc metadata, not a key name.
        state, reason = DoorState.BLOCKED, "Locked by a puzzle or event"
    else:
        # A carried key can permit an interaction, but does not set the game's
        # unlock bit until that interaction runs. Preserve the actual lock state.
        state, reason = DoorState.LOCKED, "Requires a key"

    x, z, width, depth = struct.unpack_from("<hhHH", opcode, 2)
    return DoorObservation(
        aot_id=record_id,
        source=source,
        target=target,
        state=state,
        lock_id=lock_id,
        lock_type=lock_type,
        unlocked=unlocked,
        reason=reason,
        x=x,
        z=z,
        width=width,
        depth=depth,
        animation=opcode[12],
        mode=opcode[25],
    )
