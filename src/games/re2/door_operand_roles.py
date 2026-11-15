"""Bound normal-door numeric operands and non-suspending Copy/IF39 prefixes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from games.re2.event_presence import presence_counter_indices
from games.re2.native_control import native_bytes, native_nonyielding
from games.re2.scenario_selection import (
    SCENARIO_EXECUTABLE_SHA256,
    ScenarioSourceWriteWitnesses,
)


@dataclass(frozen=True)
class DoorOperandRoles:
    copy_predicates: tuple[tuple[str, int, int], ...]
    effect_tails: tuple[tuple[int, int], ...]
    native_windows: tuple[tuple[int, int, str], ...]


def door_operand_roles(
    data: bytes,
    room: dict,
    profile: dict,
    executable: bytes,
    writes: ScenarioSourceWriteWitnesses,
) -> DoorOperandRoles | str:
    # These complete original bodies bind the qualified signed16 arithmetic,
    # original frame pump, Work/Copy handlers and owned Esp_call tail transfer.
    windows = (
        (
            0x800563E8,
            64,
            "b3b33d731b23134452c822e281fadd222dd14f8a661b69822ffe4c712cd8824e",
        ),
        (
            0x80015614,
            136,
            "36d6e214aa0fd185a849f2668774f620417119ea03efcc6d4cb133c9680f8685",
        ),
        (
            0x800154AC,
            172,
            "0c529ccfb152a42eafdddd3e525e00d287f0b8a49d9c04295d3b0b2ed78e5816",
        ),
        (
            0x8008D190,
            212,
            "a021449ebbe667b30cbce22459b6508f7b5a169263df48e8d3552f013a35f9f6",
        ),
        (
            0x800ADB4C,
            48,
            "81270be1526005e5347e7dc972ec5ed38c19ad1fa914885dadcf6a0eca4f9447",
        ),
        (
            0x800542B4,
            92,
            "239bd5e4d665be73ab33d1eac202e55faad6906e97fa0ff839c7b6beda15d513",
        ),
        (
            0x80053924,
            64,
            "ada718623251f9d42c5ad0b83cf0f5e8354af8d587b4be86c40dbc08ed4e38fc",
        ),
        (
            0x80053964,
            60,
            "bd8f9143fbd3a1cc2916f54ba49d4ccac76b537b8645337e30d8b1261776c628",
        ),
        (
            0x800539A0,
            60,
            "69958ee67a62e6d863228e4ce674c5af9b9a4555203ca4293602b2b464142b5a",
        ),
        (
            0x800536C4,
            264,
            "2d6e34c985401d66077e1c1e6fde4f6555179852fcd2462d75b42c2f7456e298",
        ),
        (
            0x80055904,
            204,
            "9f08b1193edd13a0362fe5a46ee6324d5903cb8b2f09be702ac7b9d9fc93dd2e",
        ),
        (
            0x80055E38,
            84,
            "ef575dd86cb50f9e76326ba7e552172b686bc3b3a6776d4d4eba7d155d7ad304",
        ),
        (
            0x800565A4,
            160,
            "3b552695eee9bfe9ba833bf33674075bb38fde25d8b0665a8e212066073444d0",
        ),
        (
            0x8001BF10,
            788,
            "b3904de9b426bfe322efebd19a5ca8a4adc1128fddc738ce08dee738931f3a8a",
        ),
        (
            0x80056A38,
            340,
            "18231aec21200ef09465b2b9c4e5103539b5689b4ce2f41f40e97d5957ab7645",
        ),
    )
    if (
        type(writes) is not ScenarioSourceWriteWitnesses
        or hashlib.sha256(data).hexdigest() != room["sha256"]
        or hashlib.sha256(executable).hexdigest() != SCENARIO_EXECUTABLE_SHA256
        or any(
            hashlib.sha256(native_bytes(executable, at, width)).hexdigest() != digest
            for at, width, digest in windows
        )
    ):
        return "door_operand_native_source_binding"
    # LH inputs give dx,dz in [-65535,65535]. The guarded dx==0 arm skips
    # DIV; dz<<12 cannot be INT_MIN, so dx==-1 cannot reach BREAK6 either.
    # This excludes only those real guards, never generic native trap branches.
    if not (
        -(2**31) < -65535 * 4096 <= 65535 * 4096 < 2**31
        and native_nonyielding(executable, 0x8008D190, {})
        and native_nonyielding(executable, 0x800542B4, {})
    ):
        return "door_angle_native_arithmetic"
    rows = [(key, row) for key, p in room["programs"].items() for row in p["commands"]]
    prefixes, tails = [], []
    counters = presence_counter_indices(profile)
    for key, program in room["programs"].items():
        commands = {r["offset"]: r for r in program["commands"]}
        for header in program["commands"]:
            if header["opcode"] != 6:
                continue
            at, copies = header["next"], []
            while at in commands and commands[at]["opcode"] == 0x1D:
                row = commands[at]
                packet = data[at : row["next"]]
                if len(packet) != 4 or packet[3] != 1 or packet[1] not in counters:
                    break
                copies.append((at, row["next"] + packet[2]))
                at = row["next"]
            if not copies or at not in commands or commands[at]["opcode"] != 0x39:
                continue
            predicate = commands[at]
            if (
                predicate["next"] != at + 8
                or header["target"] not in commands
                or header["target"] < predicate["next"]
                or any(
                    not (at + 2 <= target and target + 2 <= at + 8 and target % 2 == 0)
                    for _, target in copies
                )
            ):
                return "door_angle_prefix_operands"
            interior = {header["offset"], at, *(pos for pos, _ in copies)}
            if any(r.get("target") in interior for _, r in rows):
                return "door_angle_prefix_interior_entry"
            earlier = [r for r in program["commands"] if r["offset"] < header["offset"]]
            work_end = header["offset"]
            if earlier and earlier[-1]["opcode"] == 0:
                nop = earlier.pop()
                work_end = nop["offset"]
                if nop["next"] != header["offset"] or any(
                    r.get("target") == nop["offset"] for _, r in rows
                ):
                    return "door_angle_work_bypass"
            if not earlier:
                return "door_angle_work_provider"
            work = earlier[-1]
            packet = data[work["offset"] : work["next"]]
            if (
                work["next"] != work_end
                or work["opcode"] != 0x2E
                or len(packet) != 3
                or packet[1] not in (1, 2, 3, 4)
                or packet[1] == 3
                and not (packet[2] < 32 or packet[2] in (254, 255))
                or packet[1] == 4
                and packet[2] >= 32
            ):
                return "door_angle_work_provider"
            relied = (
                (header["offset"], predicate["next"]),
                (work["offset"], work["next"]),
            )
            allowed_copies = {(key, pos, target, 2) for pos, target in copies}
            if any(
                c.target_offset < end
                and begin < c.target_offset + c.width
                and (*c.location, c.target_offset, c.width) not in allowed_copies
                for c in writes.copies
                for begin, end in relied
            ) or any(
                r.offset < end and begin < r.offset + r.width
                for r in writes.record_writes
                for begin, end in relied
            ):
                return "door_angle_prefix_mutation"
            prefixes.append((key, header["offset"], at))
    for _, row in rows:
        if (
            row["opcode"] == 0x3A
            and row["next"] == row["offset"] + 16
            and row["offset"] % 2 == 0
        ):
            # Only signed16 tail+14 reaches owned effect+22. Bank, element,
            # reference and destination selectors retain their existing checks.
            if any(
                c.target_offset < row["offset"] + 6
                and row["offset"] < c.target_offset + c.width
                for c in writes.copies
            ):
                return "door_effect_selector_mutation"
            tails.append((row["offset"] + 14, row["next"]))
    return DoorOperandRoles(tuple(prefixes), tuple(tails), windows)
