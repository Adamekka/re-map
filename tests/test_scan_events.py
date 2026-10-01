"""Synthetic interpreter regressions, not runtime confirmation of room behavior."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from scan_events import scan_event_commands


def scan(code: bytes):
    data = bytes(0x20) + bytes((8, 0, 0, 0, 0, 0, 0, 0)) + code
    return scan_event_commands(data, 0x20, len(data))


def test_fc_fd_defers_the_source_command_and_covers_repeat_and_exit():
    item = bytes((0x18, 5)) + bytes(24)
    code = bytes((0xFC, 28)) + item + bytes((0xFE, 0xFD, 7, 6, 0x13, 5, 4, 0, 0xFF))
    ops, status = scan(code)
    assert status == "clean"
    assert [(address, opcode) for address, opcode, _ in ops] == [
        (0x2A, 0x18),
        (0x48, 0x13),
    ]


def test_fa_fb_loop_keeps_command_and_command_after_the_loop():
    code = bytes((0xFA, 0, 2, 0, 7, 6, 0x13, 5, 0, 0, 0xFB, 7, 6, 0x13, 5, 4, 0, 0xFF))
    ops, status = scan(code)
    assert status == "clean"
    assert [(address, opcode) for address, opcode, _ in ops] == [
        (0x2E, 0x13),
        (0x35, 0x13),
    ]


def test_animation_payload_is_not_misread_as_item_initializer():
    ops, status = scan(bytes((1, 0x83, 0x18, 0, 0, 0, 0, 0, 0x80, 0xFF)))
    assert status == "clean"
    assert ops == []


def test_single_dispatch_reads_operands_beyond_vm_advance_width():
    # The engine reads all ten AOT-reset bytes although this wrapper advances only six.
    code = bytes((7, 6, 0x12, 5, 4, 0, 0, 0, 0, 0, 0, 0, 0xFF))
    ops, status = scan(code)
    assert status == "clean"
    assert ops == [(0x2A, 0x12, code[2:12])]


def test_single_dispatch_end_does_not_consume_the_following_vm_terminator():
    ops, status = scan(bytes((7, 3, 0, 0xFF)))
    assert status == "clean"
    assert ops == [(0x2A, 0, bytes(1))]


def test_odd_block_width_keeps_zero_sentinel_in_following_vm_noop():
    # The wrapper excludes one sentinel byte, which the runner reads from the following VM no-op.
    block = bytes((3, 0, 0, 0, 0))
    code = bytes((6, 6)) + block + bytes((0xFF,))
    ops, status = scan(code)
    assert status == "clean"
    assert ops == [(0x2C, 0, bytes((0,)))]


@pytest.mark.parametrize(("camera", "flag"), [(1, 2), (2, 4)])
def test_dining_room_camera_branch_can_end_at_either_adjacent_zero(camera, flag):
    # RE1-SCD-006: both Dining Room event branches land on the second zero.
    # Each zero is operand-free; their length-prefixed procedure still has a two-byte sentinel.
    procedure = bytes((1, 11, 6, 2, 0, camera, 5, 4, flag, 0, 3, 0, 0, 0))
    block = (len(procedure) + 2).to_bytes(2, "little") + procedure + bytes(2)
    ops, status = scan(bytes((6, 19)) + block + bytes((0xFF,)))
    assert status == "clean"
    assert [(address, opcode) for address, opcode, _ in ops] == [
        (0x2C, 1),
        (0x2E, 6),
        (0x32, 5),
        (0x36, 3),
        (0x38, 0),
        (0x39, 0),
    ]
    assert [raw for _, opcode, raw in ops if opcode == 0] == [bytes(1), bytes(1)]


def test_reinitialization_follows_table_entry_without_duplicate_commands():
    ops, status = scan(bytes((7, 6, 0x13, 5, 4, 0, 8, 0)))
    assert status == "clean"
    assert len(ops) == 1


@pytest.mark.parametrize(
    ("code", "reason"),
    [
        (bytes((0xFD, 0xFF)), "has no frame"),
        (bytes((0xFB, 0xFF)), "has no frame"),
        (bytes((0xFC, 2, 0xFF)), "invalid extent"),
        (bytes((0xFC, 255, 0)), "leaves section"),
        (bytes((7, 28, 0x18, 5, 0)), "extent invalid"),
        (bytes((6, 6, 5, 0, 0, 0)), "length mismatch"),
        (bytes((1, 0x07, 0xFF)), "unsupported event state 1"),
        (bytes((5, 0, 1, 0, 0xFF)), "creation index outside table"),
        (bytes((8, 1)), "reinitialization index outside table"),
        (bytes((7, 6, 0x14, 0, 0, 1, 0xFF)), "SCD event creation index outside table"),
    ],
)
def test_malformed_or_unsupported_paths_are_explicit_failures(code, reason):
    _, status = scan(code)
    assert status != "clean" and reason in status


def test_nested_loop_exceeding_native_record_capacity_is_not_complete():
    _, status = scan(bytes((0xFA, 0, 1, 0)) * 5 + bytes((0xFF,)))
    assert "exceeds bounded analysis" in status


@pytest.mark.parametrize(
    "table",
    [bytes((1, 0, 0, 0, 0, 0, 0, 0)), bytes((255, 0, 0, 0)), bytes((4, 0, 0, 0))],
)
def test_bad_index_tables_do_not_authorize_coverage(table):
    data = bytes(0x20) + table
    _, status = scan_event_commands(data, 0x20, len(data))
    assert status != "clean"
