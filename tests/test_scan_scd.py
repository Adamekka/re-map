"""Regression tests for alignment of SLUS-00551 room scripts."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from scan_scd import walk


def test_opcodes_20_and_21_leave_following_item_aligned():
    item = bytearray(26)
    item[0] = 0x18
    item[22] = 111
    for opcode in (0x20, 0x21):
        code = bytes([opcode]) + bytes(13) + item
        ops, status = walk(code, 0x100)
        assert status == "clean"
        assert [(addr, op) for addr, op, _ in ops] == [(0x100, opcode), (0x10E, 0x18)]
        assert ops[1][2][22] == 111
