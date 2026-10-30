"""Decode PS1 MIPS stores for code-hook audits without altering execution.

MIPS-AUDIT-001: Unicorn memory-write hooks can corrupt delay-slot execution.
Call this from a code hook, then compare the completed run's full RAM image.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


class UnsupportedMipsStore(RuntimeError):
    """The instruction's memory effect cannot be audited by this decoder."""


@dataclass(frozen=True)
class MipsStore:
    instruction_address: int
    address: int
    width: Literal[1, 2, 4]
    value: int

    def __post_init__(self) -> None:
        assert type(self.instruction_address) is int
        assert 0 <= self.instruction_address <= 0xFFFFFFFF
        assert self.instruction_address % 4 == 0
        assert type(self.address) is int and 0 <= self.address <= 0xFFFFFFFF
        assert type(self.width) is int and self.width in (1, 2, 4)
        assert type(self.value) is int and 0 <= self.value < 1 << (8 * self.width)


def mips_stores(
    instruction: int,
    instruction_address: int,
    read_register: Callable[[int], int],
) -> tuple[MipsStore, ...]:
    """Predict ordinary integer stores from pre-instruction register values.

    Non-store instructions return an empty tuple. Unsupported store families
    fail explicitly, so a partial audit cannot silently omit their writes.
    Addresses remain MIPS virtual addresses; values use the stored low bytes.
    """
    assert type(instruction) is int and 0 <= instruction <= 0xFFFFFFFF
    assert type(instruction_address) is int
    assert 0 <= instruction_address <= 0xFFFFFFFF and instruction_address % 4 == 0
    opcode = instruction >> 26
    widths: dict[int, Literal[1, 2, 4]] = {0x28: 1, 0x29: 2, 0x2B: 4}
    if opcode not in widths:
        if opcode in {0x2A, 0x2C, 0x2D, 0x2E, *range(0x38, 0x40)}:
            raise UnsupportedMipsStore(
                f"Unsupported MIPS store opcode 0x{opcode:02X} "
                f"at 0x{instruction_address:08X}"
            )
        return ()
    base_index = (instruction >> 21) & 31
    value_index = (instruction >> 16) & 31
    base, value = read_register(base_index), read_register(value_index)
    assert type(base) is int and 0 <= base <= 0xFFFFFFFF
    assert type(value) is int and 0 <= value <= 0xFFFFFFFF
    assert base_index != 0 or base == 0, "MIPS register zero must read as zero"
    assert value_index != 0 or value == 0, "MIPS register zero must read as zero"
    immediate = instruction & 0xFFFF
    if immediate & 0x8000:
        immediate -= 0x10000
    # MIPS address arithmetic wraps at 32 bits even on a wider host.
    address = (base + immediate) & 0xFFFFFFFF
    width = widths[opcode]
    if address % width:
        raise UnsupportedMipsStore(
            f"Unaligned {width}-byte MIPS store at 0x{instruction_address:08X}: "
            f"0x{address:08X}"
        )
    return (
        MipsStore(
            instruction_address, address, width, value & ((1 << (width * 8)) - 1)
        ),
    )
