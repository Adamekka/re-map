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
from games.scd_entry import EntryConfig, parse_entry_config, pickup_ids

RE2_OPCODES = OpcodeSet(
    widths=OPCODE_WIDTHS,
    ends=frozenset({0x01, 0x19}),
    if_=0x06,
    else_=0x07,
    goto=0x17,
    # For, While, Do and For2.
    loops=frozenset({0x0D, 0x0F, 0x11, 0x1B}),
    for_loop=0x0D,
    while_loop=0x0F,
    do_loop=0x11,
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
    # Inventory search 0x800696CC over slots at 0x800D4A3C.
    has_item=0x5E,
    # Player state tests: bit 0x80 of byte 0x800D5BF8 (0x80058528) and the
    # halfword at 0x800CFE10 (0x800592F8).
    state_conditions=frozenset({0x81, 0x86}),
    # Save, Copy and Member_copy.
    variable_writes={
        0x24: (0, 1, 2),
        0x25: (1, 1, 2),
        0x3D: (3, 1, 0),
    },
    # Sce_rnd stores a random value in variable 29 (0x80052CA0).
    fixed_variable_writes={0x28: 29},
    # Operator table 0x800111C0 (handler 0x80054634).
    calc=0x26,
    calc2=0x27,
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
    entry: EntryConfig
    models: dict[str, dict[str, list[list]]]
    # Ordinary pickup IDs each source's scripts can create or reset.
    item_ids: dict[str, frozenset[int]]
    # Four-byte inventory slots, item type first, and their count byte.
    inventory_slots_address: int
    inventory_count_address: int


def script_evaluation(
    profile: dict, path: Path, rooms: dict[str, dict]
) -> ScriptEvaluationConfig | ScriptEvaluationSupport:
    if "script_evaluation" not in profile:
        return ScriptEvaluationSupport.Unaudited
    raw = profile["script_evaluation"]
    entry = parse_entry_config(
        raw,
        frozenset(
            {
                "models_path",
                "inventory_slots_address_ps1",
                "inventory_count_address_ps1",
            }
        ),
    )
    if entry.tasks.roots[0] != "init:0":
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
    return ScriptEvaluationConfig(
        entry,
        models,
        {key: pickup_ids(program, file_type_min) for key, program in models.items()},
        int(raw["inventory_slots_address_ps1"], 0),
        int(raw["inventory_count_address_ps1"], 0),
    )
