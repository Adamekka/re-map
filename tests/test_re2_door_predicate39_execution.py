"""RE2-DOOR-013: unchanged original native components, explicit synthetic ABI."""

import struct

from test_re2_native_frame_execution import execute as execute
from test_re2_positive_prefix import owned as owned

from games.re2.native_control import TASK_BASE, TASK_WIDTH, native_bytes


def test_original_angle39_extremes_copies_and_if_handlers(owned, execute):
    exe, source = owned[2], owned[4]["00-01"]

    def i32(value):
        value &= 0xFFFFFFFF
        return value - 0x100000000 if value & 0x80000000 else value

    def angle(current_x, current_z, target_x, target_z, table):
        assert all(
            -32768 <= value <= 32767
            for value in (current_x, current_z, target_x, target_z)
        )
        assert len(table) == 12
        dx, dz = target_x - current_x, target_z - current_z
        if dx == 0:
            return {
                "path": "cardinal",
                "angle": 0xC00 if dz > 0 else 0x400,
                "states": [],
            }
        numerator = dz * 4096
        quotient = abs(numerator) // abs(dx)
        if (numerator < 0) != (dx < 0):
            quotient = -quotient
        x, y, theta = 4096, quotient, 0
        states = [(x, y, theta)]
        for index, increment in enumerate(table):
            if y < 0:
                x, y, theta = (
                    i32(x - (y >> index)),
                    i32(y + (x >> index)),
                    i32(theta - increment),
                )
            else:
                x, y, theta = (
                    i32(x + (y >> index)),
                    i32(y - (x >> index)),
                    i32(theta + increment),
                )
            states.append((x, y, theta))
        signed_theta = ((theta & 65535) ^ 32768) - 32768
        value = ((0x1000 if dx >= 0 else 0x800) - signed_theta) & 0xFFF
        return {
            "path": "cordic",
            "angle": value,
            "quotient": quotient,
            "states": states,
        }

    def predicate_result(angle_value, yaw_u16, tolerance_i16):
        assert 0 <= yaw_u16 <= 65535 and -32768 <= tolerance_i16 <= 32767
        wrapped = (angle_value - yaw_u16 + tolerance_i16) & 0xFFF
        quantity = (
            0
            if wrapped < tolerance_i16 * 2
            else tolerance_i16
            if wrapped < 0x801
            else -tolerance_i16
        )
        return int(quantity == 0)

    table = struct.unpack("<12I", native_bytes(exe, 0x800ADB4C, 48))
    run = execute
    task, depth = 9, 0
    base = TASK_BASE + task * TASK_WIDTH
    pc, stack, ret, work = 0x80180000, 0x801E0000, 0x801F0000, 0x800D0324
    records = []
    coordinates = [
        (0, 0, 0, 0),
        (0, -1, 0, 1),
        (0, 1, 0, -1),
        (0, 0, 1, 0),
        (0, 0, -1, 0),
        (-32768, -32768, 32767, 32767),
        (32767, 32767, -32768, -32768),
        (-1, -32768, 0, 32767),
        (0, 32767, -1, -32768),
        (0, -32768, -1, 32767),
        (-32768, 32767, -32767, -32768),
        (32767, -32768, 32766, 32767),
        (32767, 0, -32768, 1),
        (-32768, 0, 32767, -1),
    ]
    cases = []
    for coords in coordinates:
        model = angle(*coords, table)
        yaw = model["angle"]
        cases.extend(
            (coords, (yaw + offset) & 0xFFF, 350)
            for offset in (0, 349, 350, -350, 2048)
        )
        cases.append((coords, 65535, 350))
    for tolerance in (-32768, -1, 0, 1, 32767):
        cases.extend(((0, 0, 1, 1), yaw, tolerance) for yaw in (0, 4095))

    for coords, yaw, tolerance in cases:
        model = angle(*coords, table)
        packet = bytes((0x39, 0)) + struct.pack("<hhh", coords[2], coords[3], tolerance)
        expected = [
            (base + 0x1C, pc + 8, 4),
            (stack - 8, ret, 4),
            (stack - 0x28, 0x11110010, 4),
            (stack - 0x24, 0x11110011, 4),
            (stack - 0x20, 0x80056418, 4),
            (stack - 0x40, work, 4),
            (stack - 0x3C, 0x80015648, 4),
        ]
        if model["path"] == "cordic":
            for index, (x, y, theta) in enumerate(model["states"]):
                frame = stack - 0xF8
                expected.extend(
                    (
                        (frame + index * 4, x & 0xFFFFFFFF, 4),
                        (frame + 0x38 + index * 4, y & 0xFFFFFFFF, 4),
                        (frame + 0x70 + index * 4, theta & 0xFFFFFFFF, 4),
                    )
                )
        answer = predicate_result(model["angle"], yaw, tolerance)
        # Nonzero upper coordinate halves check the native LH narrowing rather
        # than silently assuming whole actor coordinates are signed16 values.
        initial = [
            (base + 0x154, work, 4),
            (work + 0x38, 0xA5A50000 | (coords[0] & 65535), 4),
            (work + 0x40, 0x5A5A0000 | (coords[1] & 65535), 4),
            (work + 0x76, yaw, 2),
            (base + 4, 1, 1),
            (base + 0x140, base + 0x4C8, 4),
            (base + 0x4C4, pc + 24, 4),
        ]
        stores = run(0x800563E8, task, depth, packet, initial, expected, result=answer)
        records.append(
            {
                "component": "39",
                "coordinates_i16": coords,
                "yaw_u16": yaw,
                "tolerance_i16": tolerance,
                "model_path": model["path"],
                "expected_Boolean": answer,
                "original_return_matches": True,
                "stores": len(stores),
                "IF_and_Work_fields_preserved": True,
            }
        )

    for value in (0, 0x7FFF, 0x8000, 0xFFFF):
        for copy, counter, target in ((8636, 5, 12), (8640, 4, 6)):
            packet = source[copy:8652]
            stores = run(
                0x800542B4,
                task,
                depth,
                packet,
                [(0x800D47EC + counter * 2, value, 2)],
                [(base + 0x1C, pc + 4, 4), (pc + target, value, 2)],
            )
            records.append(
                {
                    "component": "Copy",
                    "source_offset": copy,
                    "counter_u16": value,
                    "numeric_target_delta": target,
                    "stores": len(stores),
                }
            )

    for depth in (0, 3):
        pointer = base + 0x4C4 + 32 * depth
        stores = run(
            0x80053924,
            task,
            depth,
            source[8632:8656],
            [(base + 4 + depth, 0, 1), (base + 0x140, pointer, 4)],
            [
                (base + 4 + depth, 1, 1),
                (base + 0x140, pointer + 4, 4),
                (base + 0x1C, pc + 4, 4),
                (pointer, pc + 24, 4),
            ],
        )
        records.append(
            {
                "component": "IF",
                "depth": depth,
                "fresh_foreign_target_ps1": hex(pointer),
                "target": hex(pc + 24),
                "stores": len(stores),
            }
        )
        stores = run(
            0x80053964,
            task,
            depth,
            bytes.fromhex("07001c00"),
            [(base + 4 + depth, 1, 1), (base + 0x140, pointer + 4, 4)],
            [
                (base + 4 + depth, 0, 1),
                (base + 0x140, pointer, 4),
                (base + 0x1C, pc + 28, 4),
            ],
        )
        records.append({"component": "ELSE", "depth": depth, "stores": len(stores)})
        stores = run(
            0x800539A0,
            task,
            depth,
            bytes.fromhex("0800"),
            [(base + 4 + depth, 0, 1), (base + 0x140, pointer, 4)],
            [
                (base + 4 + depth, 255, 1),
                (base + 0x140, pointer - 4, 4),
                (base + 0x1C, pc + 2, 4),
            ],
        )
        records.append({"component": "ENDIF", "depth": depth, "stores": len(stores)})

    assert len(records) == 108
    assert {r["expected_Boolean"] for r in records if r["component"] == "39"} == {0, 1}


def test_original_effect_tail_and_signed_work3_extremes(owned, execute):
    source = owned[4]["00-01"]
    run = execute
    task = 9
    base = TASK_BASE + task * TASK_WIDTH
    pc = 0x80180000
    stack = 0x801E0000
    ret = 0x801F0000
    records = []
    for value in (0, 1, 32767, 32768, 65535):
        packet = source[10020:10040]
        stores = run(
            0x800542B4,
            task,
            0,
            packet,
            [(0x800D47F4, value, 2)],
            [(base + 0x1C, pc + 4, 4), (pc + 18, value, 2)],
        )
        records.append(
            {"component": "Copy10020", "counter4_u16": value, "stores": len(stores)}
        )
    for tail in (0, 1, 32767, 32768, 65535):
        packet = bytearray(source[10024:10040])
        struct.pack_into("<H", packet, 14, tail)
        bank, header, matrix, actor = 0x80110000, 0x80111000, 0x80170000, 0x800D0324
        slot = 0x800D8CF0 + 95 * 124
        matrix_values = [0x10203000 + x for x in range(8)]
        resource_values = [0x90000000 + x for x in range(6)]
        # The vector padding and resource base-angle share final bytes +32/+33.
        # Match them so the unchanged fixture can assert every overlapping store
        # against its final RAM value without weakening that fixture.
        initial = [
            (slot + 0x78, 0, 4),
            (0x800D4E20, bank, 4),
            (0x800D4CE0, header, 4),
            (bank + 4, 4, 2),
            (bank + 16, 1, 2),
            (header, 0, 2),
            (header + 4, 0xA5A5, 2),
            (header + 6, 0x200, 2),
            (header + 10, 0x30, 1),
            (0x800CFE1C, actor, 4),
            (actor + 0x198, matrix - 0x7AC, 4),
            (stack - 0x1A, 0xA5A5, 2),
        ]
        initial.extend(
            (0x800D8CF0 + x * 124 + 0x18, int(x != 95), 2) for x in range(96)
        )
        initial.extend((matrix + 4 * x, v, 4) for x, v in enumerate(matrix_values))
        initial.extend((bank + 24 + 4 * x, v, 4) for x, v in enumerate(resource_values))
        expected = [
            (stack - 8, 0x11110012, 4),
            (stack - 4, ret, 4),
            (stack - 12, 0x11110011, 4),
            (stack - 16, 0x11110010, 4),
            (stack - 0x20, 0xB8, 2),
            (stack - 0x1E, 0x22E, 2),
            (stack - 0x1C, 0xFFB0, 2),
            (slot + 0x18, 0xA003, 2),
            (slot + 0x1A, 0, 1),
            (slot + 0x1B, 0, 1),
            (slot + 0x1C, 0x00020002, 4),
            (slot + 0x22, tail, 2),
            (slot + 0x24, 0, 4),
            (slot + 0x20, 0x30, 2),
            (slot + 0x28, 0x02000000, 4),
            (slot + 0x2C, 0x022E00B8, 4),
            (slot + 0x30, 0xA5A5FFB0, 4),
            (slot + 0x38, 0x09000000, 4),
            (slot + 0x40, 0x10000, 4),
            (slot + 0x34, 0, 4),
            (slot + 0x3C, 0, 4),
            (slot + 0x44, 0, 4),
            (slot + 0x48, 0, 4),
            (slot + 0x32, 0xA5A5, 2),
            (slot + 0x70, header + 8, 4),
            (slot + 0x74, header + 8, 4),
            (slot + 0x6C, matrix, 4),
            (slot + 0x78, bank + 24, 4),
            (base + 0x1C, pc + 16, 4),
        ]
        expected.extend(
            (slot + 0x4C + 4 * x, v, 4) for x, v in enumerate(matrix_values)
        )
        expected.extend((slot + 4 * x, v, 4) for x, v in enumerate(resource_values))
        stores = run(0x800565A4, task, 0, bytes(packet), initial, expected)
        records.append(
            {
                "component": "original3A_full_Esp_call_one_element",
                "tail_u16": tail,
                "tail_i16": tail if tail < 32768 else tail - 65536,
                "stores": len(stores),
                "only_tail_dependent_destination": hex(slot + 0x22),
                "scope": "Synthetic original component resource/actor/ABI, not gameplay or owned source lifetime.",
            }
        )
    for counter in (0, 1, 31, 32, 127, 128, 254, 255, 65535):
        stores = run(
            0x800542B4,
            task,
            0,
            source[10210:10218],
            [(0x800D47F4, counter, 2)],
            [(base + 0x1C, pc + 4, 4), (pc + 6, counter & 255, 1)],
        )
        records.append(
            {
                "component": "Copy10210",
                "counter4_u16": counter,
                "selected_byte": counter & 255,
                "stores": len(stores),
            }
        )
    for index in (0, 1, 31, 32, 127, 128, 254, 255):
        signed = index if index < 128 else index - 256
        at = 0x800CFE1C + 4 * signed
        pointer = 0x80170000
        expected = [(base + x, 0, 4) for x in range(0x158, 0x170, 4)] + [
            (base + 0x1C, pc + 3, 4),
            (base + 0x154, pointer, 4),
        ]
        stores = run(
            0x80055904, task, 0, bytes((0x2E, 3, index)), [(at, pointer, 4)], expected
        )
        records.append(
            {
                "component": "Work3_signed_index",
                "encoded_index": index,
                "signed_index": signed,
                "read_slot_ps1": hex(at),
                "stores": len(stores),
                "scope": "Proves the original signed selector arithmetic only; out-of-domain synthetic pointers do not establish normal actor ownership.",
            }
        )
    assert len(records) == 27
