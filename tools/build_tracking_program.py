"""Compile semantic RE1 interaction rules, without storing game bytecode."""

from __future__ import annotations

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scan_scd import walk

from games.re1.tracking_rules import RoomProgram


def build_tracking_program(data: bytes, row: dict, operations: list) -> dict:
    def command(address: int, op: int, raw: bytes) -> dict:
        kind, args = "uncertain-test", []
        if op == 0:
            kind = "end"
        elif op in (1, 2):
            kind = "if" if op == 1 else "else"
            args = [address + (2 if op == 1 else 0) + raw[1]]
        elif op == 3:
            kind = "endif"
        elif op in (4, 5):
            kind = "flag-test" if op == 4 else "flag-write"
            args = list(raw[1:4])
        elif op == 6:
            kind, args = "byte-test", list(raw[1:4])
        elif op == 0x18:
            kind = "item"
            args = [raw[1] & 127, raw[10], raw[11], raw[22], raw[23]]
        elif op == 0x0C:
            kind = "door"
            args = [
                raw[1],
                *struct.unpack_from("<hhHH", raw, 2),
                raw[12],
                raw[14],
                raw[15],
                raw[24],
                raw[25],
            ]
        elif op in (0x0D, 0x12, 0x13):
            # These setters preserve or replace a descriptor in the shared AOT registry.
            kind = "aot-create" if op == 0x0D else "aot-handler"
            args = [
                raw[1],
                raw[10] if op == 0x0D else raw[2],
                raw[11] if op == 0x0D else raw[3],
            ]
        elif op in (0x24, 0x2D) and raw[2] in (4, 15):
            kind, args = "award", [raw[1], raw[2], int(op == 0x24)]
        return {
            "offset": address,
            "next": address + len(raw),
            "kind": kind,
            "args": args,
        }

    def procedures(section: str) -> list[dict]:
        result = []
        cursor = row[section + "_offset"]
        end = cursor + row[section + "_size"]
        while cursor + 2 <= end:
            length = struct.unpack_from("<H", data, cursor)[0]
            if length == 0 or length < 2 or cursor + length > end:
                break
            found, status = walk(data[cursor + 2 : cursor + length], cursor + 2)
            if status != "clean":
                break
            result.append(
                {
                    "start": cursor + 2,
                    "end": cursor + length,
                    "commands": [
                        command(address, op, raw) for address, op, raw in found
                    ],
                }
            )
            cursor += length
        return result

    item_slots = set(row["item_aot_ids"])
    door_slots = {
        raw[1]
        for _, _, op, raw in operations
        if op == 0x0C or op == 0x0D and raw[10] == 1
    }
    changed_slots = set()
    for section, _, op, raw in operations:
        if op == 0x4C:
            changed_slots.add(raw[2])
        if op in (0x24, 0x2D) and raw[2] == 1:
            # Forced door callbacks have side effects beyond the modeled setters.
            changed_slots.add(raw[1])
    # Unsupported generic pickup creators and awards cannot supply a normal item descriptor.
    unclassified_items = any(
        op == 0x0D
        and raw[10] in (3, 4, 15)
        or op in (0x24, 0x2D)
        and raw[2] in (4, 15)
        and raw[1] not in item_slots
        for _, _, op, raw in operations
    )
    program = {
        "procedures": procedures("init"),
        "main_procedures": procedures("main"),
        # Event activation and historical guards are not reconstructable from
        # current flags. Keep every decoded write as a possible effect instead.
        "event_effects": [
            command(address, op, raw)
            for section, address, op, raw in operations
            if section == "events" and op in (0x0C, 0x0D, 0x12, 0x13, 0x18)
        ],
        "award_slots": sorted(
            {
                raw[1]
                for _, _, op, raw in operations
                if op in (0x24, 0x2D) and raw[2] in (4, 15)
            }
        ),
        "coverage_complete": all(status == "clean" for status in row["stats"].values())
        and not unclassified_items,
        "item_slots": sorted(item_slots),
        "door_slots": sorted(door_slots),
        "mutable_slots": sorted(changed_slots),
    }
    try:
        # Generation and startup enforce the same schema before a profile is written.
        RoomProgram.load(program)
    except ValueError as error:
        raise ValueError(f"{row['source_rdt']}: {error}") from error
    return program
