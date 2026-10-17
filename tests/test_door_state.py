"""Door decoding from existing pickup fixtures and synthetic unlock changes.

RE1-DOORS-002 records the executable evidence. Synthetic flag changes below
exercise decoding and save reversal; they are not gameplay unlock experiments.
"""

import struct
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from games.game_profile import RoomId
from games.re1.door_state import DoorState, parse_door


def door_opcode(lock_id: int, lock_type: int, target: int) -> bytes:
    opcode = bytearray(26)
    opcode[0:2] = bytes((0x0C, 2))
    struct.pack_into("<hhHH", opcode, 2, -1200, 900, 1400, 1500)
    opcode[12] = 6
    opcode[14:16] = bytes((lock_id, target))
    opcode[24:26] = bytes((lock_type, 0x81))
    return bytes(opcode)


@pytest.mark.parametrize("after", [False, True])
@pytest.mark.parametrize("pickup", ["green_herb", "chemical"])
def test_active_fixture_doors(pickup: str, after: bool, tmp_path: Path):
    state = "after" if after else "before"
    output = tmp_path / "ram.bin"
    subprocess.run(
        [
            sys.executable,
            str(REPO / "tools/extract_sav_ram.py"),
            str(REPO / "tests/fixtures" / f"slus00551_{pickup}_{state}.sav"),
            str(output),
        ],
        check=True,
        capture_output=True,
    )
    ram = output.read_bytes()
    source = RoomId(ram[0xC8660], ram[0xC8661])
    bound = struct.unpack_from("<I", ram, 0xB7ED8)[0]
    observations = []
    for record_id in range((bound - 0x800B8160) // 12 + 1):
        record = ram[0xB8160 + record_id * 12 : 0xB8160 + (record_id + 1) * 12]
        if record[0] != 1:
            continue
        pointer = struct.unpack_from("<I", record, 8)[0]
        opcode = ram[pointer - 0x80000000 - 2 : pointer - 0x80000000 + 24]
        observation = parse_door(
            record_id,
            opcode,
            source,
            ram[0xC86B4:0xC86BC],
            ram[0xC5125],
            ram[0xC870C],
            bool(ram[0xC8703] & 0x80),
        )
        assert observation.mode == record[1] == 0x81
        observations.append(observation)

    if pickup == "green_herb":
        assert source == RoomId(0, 9)
        assert [(d.aot_id, d.target.room, d.state) for d in observations] == [
            (0, 8, DoorState.OPEN),
            (1, 0x14, DoorState.LOCKED),
            (2, 0x13, DoorState.OPEN),
            (3, 0x15, DoorState.OPEN),
            (4, 0x0A, DoorState.OPEN),
        ]
        armor_door = observations[1]
        assert (armor_door.lock_id, armor_door.lock_type) == (0xC4, 0x34)
        assert (armor_door.x, armor_door.z, armor_door.width, armor_door.depth) == (
            25000,
            6800,
            2000,
            2300,
        )
    else:
        assert source == RoomId(0, 0x18)
        assert [(d.aot_id, d.target, d.state) for d in observations] == [
            (0, RoomId(0, 0x0B), DoorState.OPEN)
        ]


@pytest.mark.parametrize(
    ("index", "byte", "mask"),
    [(0, 3, 0x80), (4, 3, 0x08), (31, 0, 0x01), (32, 7, 0x80), (63, 4, 0x01)],
)
def test_unlock_bits_use_word_order_and_reverse_on_load(
    index: int, byte: int, mask: int
):
    opcode = door_opcode(0x80 | index, 0x34, 0x14)
    flags = bytearray(8)
    before = parse_door(2, opcode, RoomId(0, 9), bytes(flags), 1, 8, False)
    assert before.state == DoorState.LOCKED
    assert not before.unlocked

    flags[byte] = mask
    unlocked = parse_door(2, opcode, RoomId(0, 9), bytes(flags), 1, 8, False)
    assert unlocked.state == DoorState.OPEN
    assert unlocked.reason == "Unlocked"
    assert unlocked.unlocked

    restored = parse_door(2, opcode, RoomId(0, 9), bytes(8), 1, 8, False)
    assert restored.state == DoorState.LOCKED


def test_reciprocal_unlock_sides_share_the_bit():
    from_this_side = door_opcode(0x92, 0xFE, 4)
    from_other_side = door_opcode(0x92, 0xFF, 3)
    assert parse_door(2, from_this_side, RoomId(0, 3), bytes(8), 1, 8, False).state == (
        DoorState.UNLOCKABLE
    )
    other = parse_door(2, from_other_side, RoomId(0, 4), bytes(8), 1, 8, False)
    assert other.state == DoorState.BLOCKED
    assert other.reason == "Locked from the other side"

    flags = bytearray(8)
    flags[1] = 0x20
    for opcode, source in (
        (from_this_side, RoomId(0, 3)),
        (from_other_side, RoomId(0, 4)),
    ):
        assert (
            parse_door(2, opcode, source, bytes(flags), 1, 8, False).state
            == DoorState.OPEN
        )


@pytest.mark.parametrize("lock_id", [0x40, 0xC4])
def test_player_gate_precedes_even_an_unlocked_flag(lock_id: int):
    opcode = door_opcode(lock_id, 0x34, 0x14)
    blocked = parse_door(2, opcode, RoomId(0, 9), b"\xff" * 8, 3, 8, False)
    assert blocked.state == DoorState.BLOCKED
    assert blocked.reason == "Cannot use this door in the current state"


@pytest.mark.parametrize(
    ("player", "special", "expected"),
    [(1, 8, DoorState.UNLOCKABLE), (1, 0, DoorState.LOCKED), (0, 8, DoorState.LOCKED)],
)
def test_special_sword_path_is_not_an_inventory_inference(
    player: int, special: int, expected: DoorState
):
    opcode = door_opcode(0x89, 0x33, 8)
    assert (
        parse_door(2, opcode, RoomId(0, 7), bytes(8), player, special, False).state
        == expected
    )


def test_puzzle_lock_has_no_required_key():
    observation = parse_door(
        2, door_opcode(0x80, 0, 9), RoomId(0, 0x15), bytes(8), 1, 8, False
    )
    assert observation.state == DoorState.BLOCKED
    assert observation.lock_type == 0
    assert observation.reason == "Locked by a puzzle or event"


def test_target_stage_zero_preserves_main_and_other_stages_decode():
    source = RoomId(3, 2)
    same_stage = parse_door(2, door_opcode(0, 0, 7), source, bytes(8), 1, 8, False)
    assert same_stage.target == RoomId(3, 7)
    other_stage = parse_door(2, door_opcode(0, 0, 0x46), source, bytes(8), 1, 8, False)
    assert other_stage.target == RoomId(1, 6)
    assert (same_stage.x, same_stage.z) == (-1200, 900)


def test_returned_mansion_remap_adds_five_to_stage_zero_and_one():
    # RE1-DOORS-009: the pinned transition at 0x8002A6E0 remaps 0/1 to 5/6
    # when script flag group 0 index 0 is set; other stages are unchanged.
    kitchen = RoomId(6, 0x1C)
    stairway = RoomId(5, 0x10)
    assert parse_door(
        2, door_opcode(0, 0, 0x30), kitchen, bytes(8), 1, 8, False
    ).target == RoomId(0, 0x10)
    assert parse_door(
        2, door_opcode(0, 0, 0x30), kitchen, bytes(8), 1, 8, True
    ).target == RoomId(5, 0x10)
    assert parse_door(
        2, door_opcode(0, 0, 0x5C), stairway, bytes(8), 1, 8, False
    ).target == RoomId(1, 0x1C)
    assert parse_door(
        2, door_opcode(0, 0, 0x5C), stairway, bytes(8), 1, 8, True
    ).target == RoomId(6, 0x1C)
    # Encoded zero keeps the source stage even when the remap flag is set,
    # and encoded stages yielding 2+ never gain five.
    assert parse_door(
        2, door_opcode(0, 0, 7), kitchen, bytes(8), 1, 8, True
    ).target == RoomId(6, 7)
    assert parse_door(
        2, door_opcode(0, 0, 0x66), RoomId(3, 2), bytes(8), 1, 8, True
    ).target == RoomId(2, 6)


@pytest.mark.parametrize(
    ("record_id", "opcode", "flags", "player", "special", "remap", "message"),
    [
        (2, b"", bytes(8), 1, 8, False, "26-byte"),
        (2, bytes(26), bytes(8), 1, 8, False, "26-byte"),
        (1, door_opcode(0, 0, 7), bytes(8), 1, 8, False, "active AOT"),
        (2, door_opcode(0, 0, 7), bytes(7), 1, 8, False, "eight unlock"),
        (2, door_opcode(0, 0, 7), bytes(8), 256, 8, False, "one byte"),
        (2, door_opcode(0, 0, 7), bytes(8), 1, -1, False, "one byte"),
        (2, door_opcode(0, 0, 7), bytes(8), 1, 8, 0, "explicit boolean"),
    ],
)
def test_invalid_reads_are_explicit_failures(
    record_id, opcode, flags, player, special, remap, message
):
    with pytest.raises(ValueError, match=message):
        parse_door(record_id, opcode, RoomId(0, 9), flags, player, special, remap)
