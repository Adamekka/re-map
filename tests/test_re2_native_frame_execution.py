"""RE2-DOOR-011: unchanged owned native handlers on explicit synthetic RAM.

Code-hook store decoding plus full RAM equality avoids Unicorn's corrupting
memory-write hook. These are component executions, never gameplay evidence.
"""

import struct
import sys
from pathlib import Path

import pytest
from test_re2_positive_prefix import owned as owned

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from mips_store_audit import mips_stores
from unicorn import (
    UC_ARCH_MIPS,
    UC_HOOK_CODE,
    UC_HOOK_MEM_READ,
    UC_MODE_LITTLE_ENDIAN,
    UC_MODE_MIPS32,
    Uc,
)
from unicorn import mips_const as m

from games.re2.native_control import (
    TASK_BASE,
    TASK_WIDTH,
    ControlField,
    canonical_if_pointer,
    control_field,
)


@pytest.fixture(scope="module")
def execute(owned):
    exe = owned[2]

    def run(entry, task, depth, packet, initial, expected, *, result=1):
        ram = bytearray(bytes(range(256)) * 8192)
        ram[0x10000 : 0x10000 + len(exe) - 0x800] = exe[0x800:]
        address, ret, stack = 0x80180000, 0x801F0000, 0x801E0000
        current = TASK_BASE + task * TASK_WIDTH
        writes = [(current + 2, depth, 1), (current + 0x1C, address, 4), *initial]
        ram[address & 0x1FFFFF : (address & 0x1FFFFF) + len(packet)] = packet
        for at, value, width in writes:
            ram[at & 0x1FFFFF : (at & 0x1FFFFF) + width] = value.to_bytes(
                width, "little"
            )
        shadow = ram.copy()
        uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        uc.mem_map(0, 0x200000)
        uc.mem_write(0, bytes(ram))
        registers = [getattr(m, f"UC_MIPS_REG_{i}") for i in range(32)]
        for i in range(1, 32):
            uc.reg_write(registers[i], 0x11110000 + i)
        uc.reg_write(m.UC_MIPS_REG_A0, current)
        uc.reg_write(m.UC_MIPS_REG_RA, ret)
        uc.reg_write(m.UC_MIPS_REG_SP, stack)
        preserved = {
            r: uc.reg_read(r)
            for r in [
                m.UC_MIPS_REG_SP,
                *[getattr(m, f"UC_MIPS_REG_S{i}") for i in range(8)],
            ]
        }
        stores, loads, pcs = [], [], []
        allowed = {}
        for at, value, width in expected:
            allowed.setdefault((at, width), set()).add(value)

        def code(vm, pc, size, _):
            pcs.append(pc)
            word = int.from_bytes(vm.mem_read(pc & 0x1FFFFF, 4), "little")
            for store in mips_stores(word, pc, lambda i: vm.reg_read(registers[i])):
                # Every task store is checked independently against the expected
                # contract. The full image also checks stack and unused RAM.
                assert (store.address, store.width) in allowed, (hex(pc), store)
                assert store.value in allowed[store.address, store.width], (
                    hex(pc),
                    store,
                )
                at = store.address & 0x1FFFFF
                shadow[at : at + store.width] = store.value.to_bytes(
                    store.width, "little"
                )
                stores.append(store)

        def read(vm, access, at, width, value, _):
            loads.append((at, width))
            physical = at & 0x1FFFFF
            assert any(
                start <= physical and physical + width <= end
                for start, end in [
                    *(
                        (at & 0x1FFFFF, (at & 0x1FFFFF) + width)
                        for at, _, width in writes
                    ),
                    (TASK_BASE & 0x1FFFFF, (TASK_BASE & 0x1FFFFF) + 18 * TASK_WIDTH),
                    (address & 0x1FFFFF, (address & 0x1FFFFF) + len(packet)),
                    (0xD0000, 0xD7860),
                    (0xD8CBC, 0xD8CC0),
                    (0x170000, 0x170020),
                    (0x10000, 0xB0000),
                    ((stack & 0x1FFFFF) - 0x100, stack & 0x1FFFFF),
                ]
            ), (hex(at), width)

        uc.hook_add(UC_HOOK_CODE, code)
        uc.hook_add(UC_HOOK_MEM_READ, read)
        uc.emu_start(entry, ret, count=4096)
        assert uc.reg_read(m.UC_MIPS_REG_PC) == ret
        assert uc.reg_read(m.UC_MIPS_REG_V0) == result
        assert all(uc.reg_read(r) == value for r, value in preserved.items())
        assert bytes(uc.mem_read(0, 0x200000)) == shadow
        assert {(s.address, s.width) for s in stores} == set(allowed)
        final = {(at, width): value for at, value, width in expected}
        for (at, width), value in final.items():
            assert int.from_bytes(uc.mem_read(at & 0x1FFFFF, width), "little") == value
        assert loads and pcs
        return stores

    return run


@pytest.mark.parametrize("task", [0, 1, 2, 9, 10, 13])
@pytest.mark.parametrize("depth", range(4))
def test_unmodified_ff_goto_abandons_levels_and_installs_foreign_pointer(
    execute, task, depth
):
    base = TASK_BASE + task * TASK_WIDTH
    pc = 0x80180000
    execute(
        0x8005415C,
        task,
        depth,
        b"\x17\xff\xff\0\xfa\xff",
        [],
        [
            (base + 4 + depth, 255, 1),
            (base + 8 + depth, 255, 1),
            (base + 0x140, base + 0x4C0 + 32 * depth, 4),
            (base + 0x1C, pc - 6, 4),
        ],
    )


@pytest.mark.parametrize("task", [0, 1, 9, 10])
@pytest.mark.parametrize("depth", range(4))
@pytest.mark.parametrize("foreign", [False, True])
def test_unmodified_if_stores_the_exit_through_actual_pointer(
    execute, task, depth, foreign
):
    base = TASK_BASE + task * TASK_WIDTH
    pc = 0x80180000
    pointer = base + (0x4C0 if foreign else 0xC0) + 32 * depth
    execute(
        0x80053924,
        task,
        depth,
        b"\x06\0\x08\0",
        [(base + 4 + depth, 255, 1), (base + 0x140, pointer, 4)],
        [
            (base + 0x1C, pc + 4, 4),
            (base + 4 + depth, 0, 1),
            (base + 0x140, pointer + 4, 4),
            (pointer, pc + 12, 4),
        ],
    )


@pytest.mark.parametrize("task", [0, 1, 9, 10])
@pytest.mark.parametrize("depth", [1, 2, 3])
@pytest.mark.parametrize("saved_if", [-1, 0, 7])
@pytest.mark.parametrize("entry", [0x800537FC, 0x80054210])
def test_unmodified_end_and_return_sign_extend_saved_if(
    execute, task, depth, saved_if, entry
):
    base = TASK_BASE + task * TASK_WIDTH
    caller = depth - 1
    continuation = 0x80181234
    execute(
        entry,
        task,
        depth,
        b"\x01\0",
        [
            (base + 4 + caller, saved_if & 255, 1),
            (base + 0x144 + 4 * caller, continuation, 4),
            (base + 0x140, base + 0x4C0 + 32 * depth, 4),
        ],
        [
            (base + 2, caller, 1),
            (base + 0x1C, continuation, 4),
            (base + 0x140, base + 32 * caller + canonical_if_pointer(saved_if), 4),
        ],
    )


@pytest.mark.parametrize("depth", range(4))
@pytest.mark.parametrize("loop", range(4))
@pytest.mark.parametrize("count", [0, 1, 0x7FFF, 0x8000, 0xFFFF])
def test_unmodified_for_and_next_use_unsigned_counts_without_progress_assumption(
    execute, depth, loop, count
):
    base = TASK_BASE
    pc = 0x80180000
    count_cell = base + control_field(depth, ControlField.LoopCount, loop)[0]
    start = base + control_field(depth, ControlField.LoopStart, loop)[0]
    end = base + control_field(depth, ControlField.LoopEnd, loop)[0]
    saved = base + control_field(depth, ControlField.SavedIf, loop)[0]
    expected = [(base + 0x1C, pc + 6 + (8 if count == 0 else 0), 4)]
    if count:
        expected += [
            (base + 8 + depth, loop, 1),
            (count_cell, count, 2),
            (start, pc + 6, 4),
            (end, pc + 14, 4),
            (saved, 255, 1),
        ]
    execute(
        0x80053B1C,
        0,
        depth,
        b"\x0d\0\x08\0" + struct.pack("<H", count),
        [(base + 8 + depth, (loop - 1) & 255, 1), (base + 4 + depth, 255, 1)],
        expected,
    )
    # NEXT decrements modulo16 even for a deliberately supplied zero counter;
    # zero is not initialized by the source analysis or used to prove progress.
    remaining = (count - 1) & 65535
    expected = [
        (count_cell, remaining, 2),
        (base + 0x1C, pc + 2 if remaining == 0 else pc + 40, 4),
    ]
    if remaining == 0:
        expected.append((base + 8 + depth, (loop - 1) & 255, 1))
    execute(
        0x80053CBC,
        0,
        depth,
        b"\x0e\0",
        [(base + 8 + depth, loop, 1), (count_cell, count, 2), (start, pc + 40, 4)],
        expected,
    )


@pytest.mark.parametrize("depth", range(4))
@pytest.mark.parametrize("loop", range(4))
@pytest.mark.parametrize("saved_if", [-1, 0, 7])
def test_unmodified_break_reads_saved_if_and_its_actual_end_cell(
    execute, depth, loop, saved_if
):
    base = TASK_BASE
    target = 0x80181234
    end = base + control_field(depth, ControlField.LoopEnd, loop)[0]
    saved = base + control_field(depth, ControlField.SavedIf, loop)[0]
    execute(
        0x80054268,
        0,
        depth,
        b"\x1a\0",
        [(base + 8 + depth, loop, 1), (saved, saved_if & 255, 1), (end, target, 4)],
        [
            (base + 4 + depth, saved_if & 255, 1),
            (base + 8 + depth, (loop - 1) & 255, 1),
            (base + 0x1C, target, 4),
        ],
    )


@pytest.mark.parametrize("task", [0, 1, 9, 10])
@pytest.mark.parametrize("depth", [0, 1, 2])
def test_unmodified_gosub_initializes_only_the_actual_callee_frame(
    execute, task, depth
):
    base = TASK_BASE + task * TASK_WIDTH
    table, pc = 0x80170000, 0x80180000
    execute(
        0x800541A8,
        task,
        depth,
        b"\x18\x02",
        [(0x800D8CBC, table, 4), (table + 4, 0x100, 2)],
        [
            (base + 0x144 + depth * 4, pc + 2, 4),
            (base + 4 + depth + 1, 255, 1),
            (base + 8 + depth + 1, 255, 1),
            (base + 0x140, base + 0xC0 + 32 * (depth + 1), 4),
            (base + 2, depth + 1, 1),
            (base + 0x1C, table + 0x100, 4),
        ],
    )


@pytest.mark.parametrize("depth", range(4))
@pytest.mark.parametrize("loop", range(4))
def test_unmodified_do_nextwhile_and_endswitch_fields(execute, depth, loop):
    base, pc = TASK_BASE, 0x80180000
    start = base + control_field(depth, ControlField.LoopStart, loop)[0]
    end = base + control_field(depth, ControlField.LoopEnd, loop)[0]
    saved = base + control_field(depth, ControlField.SavedIf, loop)[0]
    execute(
        0x80053E50,
        0,
        depth,
        b"\x11\0\x0c\0",
        [(base + 8 + depth, (loop - 1) & 255, 1), (base + 4 + depth, 7, 1)],
        [
            (base + 8 + depth, loop, 1),
            (start, pc + 4, 4),
            (end, pc + 16, 4),
            (saved, 7, 1),
            (base + 0x1C, pc + 4, 4),
        ],
    )
    execute(
        0x80053E0C,
        0,
        depth,
        b"\x10\0",
        [(base + 8 + depth, loop, 1), (start, pc + 40, 4)],
        [
            (base + 8 + depth, (loop - 1) & 255, 1),
            (base + 0x1C, pc + 40, 4),
        ],
    )
    execute(
        0x80054128,
        0,
        depth,
        b"\x16\0",
        [(base + 8 + depth, loop, 1)],
        [
            (base + 8 + depth, (loop - 1) & 255, 1),
            (base + 0x1C, pc + 2, 4),
        ],
    )


@pytest.mark.parametrize("depth", range(4))
@pytest.mark.parametrize("matches", [False, True])
def test_unmodified_while_consumes_its_fresh_end_after_complete_ck(
    execute, owned, depth, matches
):
    from games.re2.native_control import native_bytes

    base, pc, stack, ret = TASK_BASE, 0x80180000, 0x801E0000, 0x801F0000
    start = base + control_field(depth, ControlField.LoopStart, 0)[0]
    end = base + control_field(depth, ControlField.LoopEnd, 0)[0]
    saved = base + control_field(depth, ControlField.SavedIf, 0)[0]
    flag = int.from_bytes(native_bytes(owned[2], 0x800A78D0, 4), "little")
    expected = [
        (stack - 0x10, 0x11110010, 4),
        (stack - 4, ret, 4),
        (stack - 8, 0x11110012, 4),
        (stack - 0x0C, 0x11110011, 4),
        (base + 8 + depth, 0, 1),
        (start, pc, 4),
        (end, pc + 16, 4),
        (base + 0x1C, pc + 4, 4),
        (saved, 255, 1),
        (stack - 0x30, end, 4),
        (stack - 0x24, 0x80053DCC, 4),
        (stack - 0x28, 0x11110014, 4),
        (stack - 0x2C, 0x11110013, 4),
        (stack - 0x34, base + depth, 4),
        (stack - 0x38, base, 4),
        (base + 0x1C, pc + 8, 4),
    ]
    if not matches:
        expected += [(base + 0x1C, pc + 16, 4), (base + 8 + depth, 255, 1)]
    execute(
        0x80053D3C,
        0,
        depth,
        b"\x0f\x04\x0c\0\x21\x02\x07\x01",
        [
            (base + 8 + depth, 255, 1),
            (base + 4 + depth, 255, 1),
            (flag, 0x01000000 if matches else 0, 4),
        ],
        expected,
    )


@pytest.mark.parametrize("value", [0, 1, 0x7FFF, 0x8000, 0xFFFF])
@pytest.mark.parametrize("operation", range(7))
def test_unmodified_cmp_returns_the_bound_native_switch_result(
    execute, value, operation
):
    signed = value if value < 0x8000 else value - 0x10000
    immediate = -1
    outcome = (
        signed == immediate,
        signed > immediate,
        signed >= immediate,
        signed < immediate,
        signed <= immediate,
        signed != immediate,
        bool(signed & immediate),
    )[operation]
    execute(
        0x80054474,
        0,
        0,
        bytes((0x23, 0, 26, operation)) + struct.pack("<h", immediate),
        [(0x800D47EC + 52, value, 2)],
        [(TASK_BASE + 0x1C, 0x80180006, 4)],
        result=int(outcome),
    )


@pytest.mark.parametrize("depth", range(4))
@pytest.mark.parametrize("matches", [False, True])
def test_unmodified_switch_sets_end_and_saved_if_without_changing_if_pointer(
    execute, depth, matches
):
    from test_re2_initializer_control import switch

    packet = switch(b"\0")
    base, pc = TASK_BASE, 0x80180000
    end = base + control_field(depth, ControlField.LoopEnd, 0)[0]
    saved = base + control_field(depth, ControlField.SavedIf, 0)[0]
    expected = [(base + 8 + depth, 0, 1), (end, pc + len(packet), 4), (saved, 7, 1)]
    if matches:
        expected += [(base + 0x1C, pc + 10, 4)]
    else:
        expected += [(base + 8 + depth, 255, 1), (base + 0x1C, pc + len(packet), 4)]
    execute(
        0x80054020,
        0,
        depth,
        packet,
        [
            (base + 8 + depth, 255, 1),
            (base + 4 + depth, 7, 1),
            (0x800D47EC + 52, 0 if matches else 1, 2),
        ],
        expected,
    )
