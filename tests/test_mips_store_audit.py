"""MIPS-AUDIT-001: store auditing must preserve native delay-slot behavior."""

import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from mips_store_audit import MipsStore, UnsupportedMipsStore, mips_stores


@pytest.mark.parametrize(
    ("opcode", "base", "immediate", "width", "address", "value"),
    [
        (0x28, 0x800D4850, 4, 1, 0x800D4854, 0xEF),
        (0x29, 0x800D4880, -6, 2, 0x800D487A, 0xCDEF),
        (0x2B, 0x800D0324, 0x3C, 4, 0x800D0360, 0x89ABCDEF),
        (0x28, 0xFFFFFFFF, 1, 1, 0, 0xEF),
        (0x29, 0xFFFFFFFF, 1, 2, 0, 0xCDEF),
    ],
)
def test_integer_store_uses_signed_displacement_width_and_address_wrap(
    opcode, base, immediate, width, address, value
):
    registers = {4: base, 5: 0x89ABCDEF}
    instruction = opcode << 26 | 4 << 21 | 5 << 16 | (immediate & 0xFFFF)
    assert mips_stores(instruction, 0x80010000, registers.__getitem__) == (
        MipsStore(0x80010000, address, width, value),
    )


def test_zero_register_store_retains_the_real_zero_value():
    assert mips_stores(0xAC004000, 0x1004, lambda index: 0) == (
        MipsStore(0x1004, 0x4000, 4, 0),
    )


@pytest.mark.parametrize("instruction", [0, 0x03E00008, 0x0C000404, 0xC8800000])
def test_non_store_does_not_read_registers(instruction):
    def unexpected_register_read(index):
        pytest.fail(f"Non-store requested register {index}")

    assert mips_stores(instruction, 0x1000, unexpected_register_read) == ()


@pytest.mark.parametrize("opcode", [0x2A, 0x2C, 0x2D, 0x2E, *range(0x38, 0x40)])
def test_unmodeled_store_cannot_disappear_from_the_audit(opcode):
    with pytest.raises(UnsupportedMipsStore, match="Unsupported MIPS store opcode"):
        mips_stores(opcode << 26, 0x1000, lambda index: 0)


@pytest.mark.parametrize(("opcode", "address"), [(0x29, 1), (0x2B, 2)])
def test_unaligned_store_is_an_explicit_failed_audit(opcode, address):
    with pytest.raises(UnsupportedMipsStore, match="Unaligned"):
        mips_stores(opcode << 26 | 4 << 21, 0x1000, {0: 0, 4: address}.__getitem__)


def test_code_hook_audit_preserves_a_jal_with_a_delay_slot_store():
    unicorn = pytest.importorskip("unicorn")
    from unicorn import mips_const

    machine = unicorn.Uc(
        unicorn.UC_ARCH_MIPS, unicorn.UC_MODE_MIPS32 | unicorn.UC_MODE_LITTLE_ENDIAN
    )
    machine.mem_map(0, 0x5000)
    program = (
        0x0C000404,  # JAL 0x1010
        0xAC004000,  # SW zero, 0x4000(zero), in its delay slot
        0x08000800,  # J 0x2000
        0,
        0x27BDFFC0,  # ADDIU sp, sp, -0x40
        0x27BD0040,  # ADDIU sp, sp, 0x40
        0x03E00008,  # JR ra
        0,
    )
    machine.mem_write(0x1000, struct.pack("<8I", *program))
    machine.mem_write(0x4000, b"\xa5" * 4)
    machine.reg_write(mips_const.UC_MIPS_REG_SP, 0x3000)
    before = bytes(machine.mem_read(0, 0x5000))
    register_ids = tuple(
        getattr(mips_const, f"UC_MIPS_REG_{index}") for index in range(32)
    )
    stores = []

    def audit_instruction(cpu, pc, size, context):
        assert size == 4
        instruction = int.from_bytes(cpu.mem_read(pc, 4), "little")
        stores.extend(
            mips_stores(
                instruction, pc, lambda index: cpu.reg_read(register_ids[index])
            )
        )

    # A memory-write hook on this delay-slot SW duplicates the callee's first
    # stack adjustment in Unicorn 2.1.4. Observe the instruction without it.
    machine.hook_add(unicorn.UC_HOOK_CODE, audit_instruction)
    machine.emu_start(0x1000, 0x2000, count=100)
    assert machine.reg_read(mips_const.UC_MIPS_REG_PC) == 0x2000
    assert machine.reg_read(mips_const.UC_MIPS_REG_SP) == 0x3000
    assert stores == [MipsStore(0x1004, 0x4000, 4, 0)]
    expected = bytearray(before)
    expected[0x4000:0x4004] = bytes(4)
    assert bytes(machine.mem_read(0, 0x5000)) == expected
