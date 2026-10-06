"""Compile semantic RE1 interaction rules, without storing game bytecode."""

from __future__ import annotations

import struct
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from scan_events import EventScan
from scan_scd import walk

from games.re1.scd_semantics import (
    CONTINUING_OPCODES,
    LOCAL_FLAG_WRITES,
    UNRESOLVED_PREDICATE_OPCODES,
)
from games.re1.tracking_rules import RoomProgram, RuleCommand, RuleProcedure


def build_tracking_program(
    data: bytes,
    row: dict,
    operations: list,
    source_complete: bool,
    event_scan: EventScan,
) -> dict:
    def command(address: int, op: int, raw: bytes) -> dict:
        kind, args = "unsupported-effect", []
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
        elif op == 7:
            kind, args = (
                "word-test",
                [raw[2], raw[3], struct.unpack_from("<H", raw, 4)[0]],
            )
        elif op in (8, 0x31):
            width = 1 if op == 8 else 2
            kind, args = (
                "variable-write",
                [width, raw[1], int.from_bytes(raw[2 : 2 + width], "little")],
            )
        elif op == 0x1C:
            value = struct.unpack_from("<H", raw, 2)[0]
            kind, args = "variable-write", [1, 8, raw[1], 2, 2, value]
            # A zero counter leaves its previous direction word unchanged.
            if value:
                args += [2, 1, 0x7FFF if value & 0x8000 else 0]
        elif op in (9, 0x0A, 0x23):
            # Camera setters and the camera-control command also update word
            # C3000 bit 20, native flag-bank 5 index 11. Camera predicates stay unresolved.
            operation = 1 if op == 0x0A or op == 0x23 and raw[1] == 0 else 0
            kind, args = (
                ("flag-write", [5, 11, operation])
                if op == 0x23
                else ("camera-change", [operation])
            )
        elif op == 0x4C:
            if raw[1] in (0, 1, 2):
                kind, args = "quantity-transfer", list(raw[1:4])
            else:
                # The native default advances four bytes and returns one
                # without accessing a descriptor or changing a variable.
                kind, args = "constant-test", [1]
        elif op == 0x0F:
            kind, args = "player-control", [raw[1]]
        elif op == 0x1E:
            # Movie setup's helpers change CD/audio state; the caller always
            # sets C3000 bit 17 afterward, including the native default mode.
            kind, args = "flag-write", [5, 14, 0]
        elif op == 0x2C:
            kind, args = "inventory-remove", [raw[1]]
        elif op == 0x29:
            kind, args = "display-request", [raw[1]]
        elif op == 0x48:
            # Clearing the pool zeros its first record's two header bytes.
            # Only those bytes overlap a script flag bank, at C3024/C3025.
            kind, args = "local-flag-clear", [4, 240, 16]
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
        elif op == 0x14:
            kind, args = "event-start", [raw[2], raw[3]]
        elif op in (0x24, 0x2D) and raw[2] in (4, 15):
            kind, args = "award", [raw[1], raw[2], int(op == 0x24)]
        elif op in (0x24, 0x2D) and raw[2] in (1, 5, 6, 7, 9, 13):
            kind, args = "aot-callback", [raw[1], raw[2], int(op == 0x24)]
        elif op in CONTINUING_OPCODES:
            kind, args = "constant-test", [1]
            if op in LOCAL_FLAG_WRITES:
                kind, args = (
                    "local-flag-forget",
                    [field for effect in LOCAL_FLAG_WRITES[op] for field in effect],
                )
        elif op in UNRESOLVED_PREDICATE_OPCODES:
            kind = "uncertain-test"
        return {
            "offset": address,
            "next": address + len(raw),
            "kind": kind,
            "args": args,
        }

    def procedures(cursor: int, end: int) -> tuple[list[dict], bool]:
        result = []
        if not 0 <= cursor < end <= len(data):
            return result, False
        while cursor + 2 <= end:
            length = struct.unpack_from("<H", data, cursor)[0]
            if length == 0:
                return result, True
            if length < 2 or cursor + length > end:
                return result, False
            found, status = walk(
                data[cursor + 2 : cursor + length],
                cursor + 2,
                operand_tail=data[cursor + length : end],
            )
            if status != "clean":
                return result, False
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
        return result, False

    item_slots = set(row["item_aot_ids"])
    # A generic interaction can become a pickup without any item creator in
    # this source. Retain that slot so an unknown payload cannot look cleared.
    item_slots.update(
        raw[1]
        for _, _, op, raw in operations
        if op in (0x12, 0x13) and raw[2] in (3, 4, 15)
    )
    door_slots = {
        raw[1]
        for _, _, op, raw in operations
        if op == 0x0C or op == 0x0D and raw[10] == 1
    }
    door_slots.update(
        raw[1] for _, _, op, raw in operations if op in (0x12, 0x13) and raw[2] == 1
    )
    # RE1-SCD-015: callback 1 and its helpers preserve the AOT/source.
    # Its event-time unlock result comes from fresh flags, not replay.
    changed_slots = set()
    for section, _, op, raw in operations:
        if op == 0x4C and raw[1] in (1, 2):
            # Mode 0 only reads quantity. Modes 1/2 write the AOT source;
            # mode 2 looks up inventory using that source's item type.
            changed_slots.add(raw[2])
    # Unsupported generic pickup creators and awards cannot supply a normal item descriptor.
    unclassified_items = any(
        op == 0x0D
        and raw[10] in (3, 4, 15)
        or op in (0x24, 0x2D)
        and raw[2] in (4, 15)
        and raw[1] not in item_slots
        for _, _, op, raw in operations
    )
    init_procedures, init_complete = procedures(
        row["init_offset"], row["init_offset"] + row["init_size"]
    )
    main_procedures, main_complete = procedures(
        row["main_offset"], row["main_offset"] + row["main_size"]
    )
    event_blocks = []
    block_commands = set()
    event_complete = event_scan.status == "clean"
    for start in event_scan.block_starts:
        blocks, complete = procedures(start, row["events_offset"] + row["events_size"])
        assert complete, "event scanner must validate every embedded procedure list"
        # A flag-only dispatch can enable a later item or door event. Reentry
        # analysis needs its semantics even without a direct interaction update.
        try:
            # Width decoding does not enforce the semantic procedure schema.
            # Invalid blocks cannot authorize pruning or source completeness.
            for block in blocks:
                RuleProcedure(
                    block["start"],
                    block["end"],
                    tuple(
                        RuleCommand(c["offset"], c["next"], c["kind"], tuple(c["args"]))
                        for c in block["commands"]
                    ),
                )
        except ValueError:
            event_complete = False
            continue
        event_blocks.append(blocks)
        block_commands.update(
            c["offset"] for block in blocks for c in block["commands"]
        )
    program = {
        "procedures": init_procedures,
        "main_procedures": main_procedures,
        "event_blocks": event_blocks,
        "event_program": {
            "entries": list(event_scan.entries),
            "points": [asdict(point) for point in event_scan.points],
            "dispatches": [asdict(dispatch) for dispatch in event_scan.dispatches],
            "starts": [asdict(start) for start in event_scan.starts],
            "creators": sorted(
                [address, raw[1] & 127 if op == 0x18 else raw[1]]
                for _, address, op, raw in operations
                if op in (0x0C, 0x0D, 0x18)
            ),
            "registry_writes": sorted(
                [
                    address,
                    raw[1],
                    *struct.unpack_from("<HHH", raw, 12 if op == 0x0D else 4),
                ]
                for _, address, op, raw in operations
                if op in (0x0D, 0x12)
            ),
            "changes": sorted(
                [
                    address,
                    raw[2] if op == 0x4C else raw[1] & 127 if op == 0x18 else raw[1],
                ]
                for _, address, op, raw in operations
                if op in (0x0C, 0x0D, 0x12, 0x13, 0x18)
                or op in (0x24, 0x2D)
                and raw[2] in (1, 4, 15)
                or op == 0x4C
                and raw[1] in (1, 2)
            ),
            "script_starts": sorted(
                [address, raw[2], raw[3]]
                for _, address, op, raw in operations
                if op == 0x14
            ),
        },
        # Single/deferred dispatches have no shared SCD-runner boundary. Their
        # changes remain independent, including commands reached by both forms.
        "event_effects": [
            command(address, op, raw)
            for section, address, op, raw in operations
            if section == "events"
            and (
                op in (0x0C, 0x0D, 0x12, 0x13, 0x18) or op == 0x4C and raw[1] in (1, 2)
            )
            and (
                address not in block_commands
                or address in event_scan.standalone_commands
            )
        ],
        "event_commands": [
            command(address, op, raw)
            for section, address, op, raw in operations
            if section == "events"
            and (
                address not in block_commands
                or address in event_scan.standalone_commands
            )
        ],
        "award_slots": sorted(
            {
                raw[1]
                for _, _, op, raw in operations
                if op in (0x24, 0x2D) and raw[2] in (4, 15)
            }
        ),
        # Clean decoding alone does not validate an indexed event target.
        # Keep the source audit's invalid-target and section failures mandatory.
        # Independently require clean parsing and both sentinels. A caller's
        # source audit cannot authorize a truncated semantic procedure list.
        "coverage_complete": source_complete
        and init_complete
        and main_complete
        and event_complete
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
