"""RE1-CACHE-002: pinned variable-width handlers leave following pickups aligned."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from scan_scd import walk


@pytest.mark.parametrize(
    ("opcode", "subtype", "width"),
    [(0x17, subtype, 10) for subtype in range(4)]
    + [
        (0x28, subtype, width)
        for subtype, width in {
            0: 6,
            1: 8,
            2: 6,
            3: 6,
            5: 6,
            6: 4,
            8: 4,
            9: 6,
            10: 6,
        }.items()
    ]
    + [
        (0x33, subtype, width)
        for subtype, width in {
            0: 2,
            1: 4,
            3: 4,
            4: 2,
            5: 4,
            6: 2,
            7: 2,
            8: 4,
            9: 4,
            10: 4,
        }.items()
    ],
)
def test_variable_width_command_does_not_consume_or_hide_the_following_item(
    opcode, subtype, width
):
    command = bytearray(width)
    command[0] = opcode
    command[{0x17: 4, 0x28: 3, 0x33: 1}[opcode]] = subtype
    item = bytes((0x18, 5)) + bytes(24)
    ops, status = walk(bytes(command) + item, 0x100)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [
        (0x100, opcode),
        (0x100 + width, 0x18),
    ]


@pytest.mark.parametrize(
    ("opcode", "subtype"), [(0x17, 4), (0x28, 4), (0x28, 7), (0x33, 2), (0x33, 11)]
)
def test_unsupported_subcommand_never_uses_an_invented_width(opcode, subtype):
    command = bytearray(10)
    command[0] = opcode
    command[{0x17: 4, 0x28: 3, 0x33: 1}[opcode]] = subtype
    _, status = walk(bytes(command), 0x100)
    assert "unsupported" in status
