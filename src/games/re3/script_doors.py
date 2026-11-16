"""Candidate RE3 door creators from the initializer procedures. RE3-PLAN-002.

A creator records where a script would place a door trigger. It does not prove
that the branch runs, that the door is unlocked or that the player used it.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

from games.re3.room_data import RoomFormatFailure
from games.re3.script_model import WIDTHS

# Native command widths; with them every initializer procedure of the owned
# 169 sources decodes up to its first evt_end (0x01); 118 have bytes after it
# that are not commands, so walking must stop there.
OPCODE_WIDTHS = WIDTHS
EVT_END = 0x01
DOOR_AOT_SET = 0x61
DOOR_AOT_SET_4P = 0x62


@dataclass(frozen=True)
class DoorCreator:
    """One door trigger command; offsets are RDT-relative bytes."""

    offset: int
    procedure: int
    floor: int
    # Trigger outline as world X/Z corners, in source order.
    corners: tuple[tuple[int, int], ...]
    target_stage: int
    target_room: int
    target_floor: int
    # Player world X/Z placed in the target room after the transition.
    destination_xz: tuple[int, int]
    key_id: int
    key_type: int

    @property
    def center(self) -> tuple[float, float]:
        return (
            sum(x for x, _ in self.corners) / len(self.corners),
            sum(z for _, z in self.corners) / len(self.corners),
        )


def door_creators(rdt: bytes, room: dict) -> list[DoorCreator] | RoomFormatFailure:
    """Walk each initializer procedure from its start to its first evt_end.

    `room` is the decode_room result for the same bytes. An unknown command or
    a command crossing its procedure envelope is a modeled failure, not an
    empty door list.
    """
    assert len(OPCODE_WIDTHS) == 0x90
    doors = []
    for procedure in room["initializer"]["procedures"]:
        position = procedure["offset"]
        end = position + procedure["size"]
        while True:
            if position >= end:
                return RoomFormatFailure(
                    "script", position, "procedure ends without evt_end"
                )
            opcode = rdt[position]
            if opcode >= len(OPCODE_WIDTHS) or position + OPCODE_WIDTHS[opcode] > end:
                return RoomFormatFailure(
                    "script", position, "unknown or truncated script command"
                )
            if opcode == EVT_END:
                break
            if opcode in (DOOR_AOT_SET, DOOR_AOT_SET_4P):
                doors.append(parse_door(rdt, position, procedure["index"]))
            position += OPCODE_WIDTHS[opcode]
    return doors


def parse_door(rdt: bytes, position: int, procedure: int) -> DoorCreator:
    """Decode one door_aot_set (0x61) or four-point (0x62) command."""
    floor = rdt[position + 4]
    if rdt[position] == DOOR_AOT_SET:
        x, z, width, depth = struct.unpack_from("<hhHH", rdt, position + 6)
        corners = ((x, z), (x + width, z), (x + width, z + depth), (x, z + depth))
        data = position + 14
    else:
        values = struct.unpack_from("<8h", rdt, position + 6)
        corners = tuple((values[i], values[i + 1]) for i in range(0, 8, 2))
        data = position + 22
    # Door data: next X/Y/Z, facing, then stage, room, camera, floor; the key
    # ID and type follow at +15/+16 (handler 0x80050D28).
    next_x, _next_y, next_z = struct.unpack_from("<3h", rdt, data)
    stage, target_room, _camera, target_floor = rdt[data + 8 : data + 12]
    return DoorCreator(
        position,
        procedure,
        floor,
        corners,
        stage,
        target_room,
        target_floor,
        (next_x, next_z),
        rdt[data + 15],
        rdt[data + 16],
    )
