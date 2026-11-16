"""RE3-PLAN-002: synthetic initializer scripts with door creators."""

import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from games.re3.room_data import RoomFormatFailure
from games.re3.script_doors import OPCODE_WIDTHS, door_creators


def procedure(body: bytes) -> tuple[bytes, dict]:
    return body, {"initializer": {"procedures": [{"index": 0, "offset": 0, "size": len(body)}]}}


def test_door_creators_read_both_trigger_shapes_and_stop_at_evt_end():
    rectangle = bytes([0x61, 3, 1, 0, 2, 0]) + struct.pack("<hhHH", -100, 50, 20, 40)
    rectangle += struct.pack("<4h", 7, 0, -9, 1024) + bytes([1, 0x0B, 2, 0, 0, 0, 0, 0x86, 1, 0])
    quad = bytes([0x62, 4, 1, 0, 0x80, 0]) + struct.pack("<8h", 0, 0, 10, 0, 10, 10, 0, 10)
    quad += struct.pack("<4h", 1, 0, 2, 0) + bytes([0, 0x05, 0, 0, 0, 0, 0, 0, 0, 0])
    # Bytes after evt_end are not commands and must not be decoded.
    rdt, room = procedure(bytes([0x00]) + rectangle + quad + bytes([0x01, 0x00, 0x61]))
    doors = door_creators(rdt, room)
    assert [door.offset for door in doors] == [1, 33]
    first, second = doors
    assert first.corners == ((-100, 50), (-80, 50), (-80, 90), (-100, 90))
    assert first.center == (-90, 70)
    assert (first.target_stage, first.target_room, first.floor) == (1, 0x0B, 2)
    assert (first.destination_xz, first.key_id) == ((7, -9), 0x86)
    assert second.corners == ((0, 0), (10, 0), (10, 10), (0, 10))
    assert (second.target_room, second.floor) == (0x05, 0x80)


def test_door_creators_model_unknown_and_unterminated_procedures():
    assert len(OPCODE_WIDTHS) == 0x90
    unknown = door_creators(*procedure(bytes([0x00, 0x90, 0x01, 0x00])))
    assert unknown == RoomFormatFailure("script", 1, "unknown or truncated script command")
    truncated = door_creators(*procedure(bytes([0x00, 0x61, 0x00])))
    assert isinstance(truncated, RoomFormatFailure) and truncated.offset == 1
    unterminated = door_creators(*procedure(bytes([0x00, 0x00])))
    assert unterminated == RoomFormatFailure("script", 2, "procedure ends without evt_end")
