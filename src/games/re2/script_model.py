"""Compile RE2 room scripts into the shared evaluation model. RE2-EVAL-001.

The model keeps only operations that affect control flow, flags or room
interactions. Offsets stay source-relative so creators keep the identities
used by the room catalog and map door markers.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from games.re2.room_data import OPCODE_WIDTHS
from games.scd_compile import OpcodeSet, compile_section
from games.scd_state import EngineTasks

RE2_OPCODES = OpcodeSet(
    widths=OPCODE_WIDTHS,
    ends=frozenset({0x01, 0x19}),
    if_=0x06,
    else_=0x07,
    goto=0x17,
    # For, While, Do and For2.
    loops=frozenset({0x0D, 0x0F, 0x11, 0x1B}),
    loop_ends=frozenset({0x0E, 0x10, 0x12}),
    # Switch handler 0x80054020 compares signed case values in label order.
    switch=0x13,
    case=0x14,
    default=0x15,
    end_switch=0x16,
    break_=0x1A,
    ck=0x21,
    # Cmp handler 0x80054474, operator table 0x800111A0.
    cmp=0x23,
    set_=0x22,
    # Actor members such as the entry floor, facing, enemy position and
    # button/trigger checks.
    approach_conditions=frozenset({0x39, 0x3E, 0x4F, 0x50, 0x85}),
    # Inventory and poison checks.
    state_conditions=frozenset({0x5E, 0x81, 0x86}),
    # Save, Copy, Calc, Calc2 and Member_copy.
    variable_writes={
        0x24: (0, 1, 2),
        0x25: (1, 1, 2),
        0x26: (2, 3, 0),
        0x27: (2, 2, 0),
        0x3D: (2, 1, 0),
    },
    # Sce_rnd stores a random value in variable 29 (0x80052CA0).
    fixed_variable_writes={0x28: 29},
    items={0x4E: 14, 0x69: 22},
    doors=frozenset({0x3B, 0x68}),
    interactions=frozenset({0x2C, 0x67}),
    reset=0x46,
    aot_on=0x47,
    gosub=0x18,
    exec_=0x04,
    # Handler 0x800542B4.
    work_copy=0x1D,
)


def compile_room_scripts(data: bytes) -> dict[str, list[list]]:
    return {
        **compile_section(RE2_OPCODES, data, 16, "init"),
        **compile_section(RE2_OPCODES, data, 17, "main"),
    }


class ScriptEvaluationSupport(Enum):
    Unaudited = "unaudited"


@dataclass(frozen=True)
class ScriptEvaluationConfig:
    """Revision facts the evaluator needs to see a room as entry does."""

    tasks: EngineTasks
    variables_address: int
    variable_count: int
    # Flag bits the room loader clears before scripts run (0x80052E20).
    entry_cleared_flags: frozenset[tuple[int, int]]
    # Variables the room loader sets before scripts run.
    entry_variables: dict[int, int]
    stage_variable: int
    room_variable: int
    # Natively written values with no stable meaning at room entry.
    unread_variables: frozenset[int]
    approach_variables: frozenset[int]
    # Flag banks that hold answers to prompts and other interaction results.
    approach_banks: frozenset[int]
    models: dict[str, dict[str, list[list]]]
    # Ordinary pickup IDs each source's scripts can create or reset.
    item_ids: dict[str, frozenset[int]]


def script_evaluation(
    profile: dict, path: Path, rooms: dict[str, dict]
) -> ScriptEvaluationConfig | ScriptEvaluationSupport:
    if "script_evaluation" not in profile:
        return ScriptEvaluationSupport.Unaudited
    raw = profile["script_evaluation"]
    fields = {
        "models_path",
        "roots",
        "repeating_procedures",
        "variables_address_ps1",
        "variable_count",
        "entry_cleared_flags",
        "entry_variables",
        "stage_variable",
        "room_variable",
        "unread_variables",
        "approach_variables",
        "approach_banks",
    }
    if type(raw) is not dict or raw.keys() != fields:
        raise ValueError("invalid RE2 script evaluation configuration")
    address = int(raw["variables_address_ps1"], 0)
    count = raw["variable_count"]
    if (
        type(count) is not int
        or not 0 < count <= 256
        or address % 2
        or not 0x80000000 <= address <= 0x80200000 - 2 * count
    ):
        raise ValueError("invalid RE2 script variable array")
    cleared = set()
    for row in raw["entry_cleared_flags"]:
        if row.keys() != {"bank", "first_bit", "last_bit"} or not (
            0 <= row["first_bit"] <= row["last_bit"] < 256
        ):
            raise ValueError("invalid RE2 entry-cleared flag range")
        cleared.update(
            (row["bank"], bit) for bit in range(row["first_bit"], row["last_bit"] + 1)
        )
    entry_variables = {}
    for row in raw["entry_variables"]:
        if row.keys() != {"variable", "value"} or not 0 <= row["variable"] < count:
            raise ValueError("invalid RE2 entry variable")
        entry_variables[row["variable"]] = row["value"]
    variables = (
        raw["stage_variable"],
        raw["room_variable"],
        *raw["unread_variables"],
        *raw["approach_variables"],
    )
    if any(type(value) is not int or not 0 <= value < count for value in variables):
        raise ValueError("invalid RE2 script variable index")
    roots = tuple(raw["roots"])
    if (
        not roots
        or roots[0] != "init:0"
        or any(type(root) is not str for root in roots)
    ):
        raise ValueError("RE2 script evaluation must start with the initializer")
    document = json.loads((path.parent / raw["models_path"]).read_text())
    if (
        document.get("schema") != 1
        or document.get("profile_id") != profile["profile_id"]
        or document.get("executable_identity") != profile["executable_identity"]
        or document["sources"].keys() != rooms.keys()
        or any(
            document["sources"][key]["sha256"] != room["sha256"]
            for key, room in rooms.items()
        )
    ):
        raise ValueError("RE2 script models disagree with the room catalog")
    file_type_min = profile["runtime_layout"]["file_type_min"]
    models = {key: row["program"] for key, row in document["sources"].items()}
    item_ids = {
        key: frozenset(
            gid
            for rows in program.values()
            for _, _, op, *args in rows
            for item_type, gid in (
                [(args[2], args[4])]
                if op == "item"
                else [(args[4], args[6])]
                if op == "reset" and args[1] == 2
                else []
            )
            # Files are documents, not room pickups.
            if 0 <= item_type < file_type_min
        )
        for key, program in models.items()
    }
    return ScriptEvaluationConfig(
        EngineTasks(roots, frozenset(raw["repeating_procedures"])),
        address,
        count,
        frozenset(cleared),
        entry_variables,
        raw["stage_variable"],
        raw["room_variable"],
        frozenset(raw["unread_variables"]),
        frozenset(raw["approach_variables"]),
        frozenset(raw["approach_banks"]),
        models,
        item_ids,
    )
