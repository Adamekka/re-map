"""Room-entry game state for script evaluation. RE2-EVAL-001, RE3-EVAL-001.

RE2 and RE3 share the shape of their loader: before a room's scripts run it
clears some flags, resets some variables and exposes the room's own stage and
room numbers. Each revision supplies these facts in its profile.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from games.scd_state import EngineTasks, FlagReader, GameState

_FIELDS = frozenset(
    {
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
)


@dataclass(frozen=True)
class EntryConfig:
    """Revision facts the evaluator needs to see a room as entry does."""

    tasks: EngineTasks
    variables_address: int
    variable_count: int
    # Flag bits the room loader clears before scripts run.
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


def parse_entry_config(raw: dict, extra_fields: frozenset[str]) -> EntryConfig:
    """Validate a profile's ``script_evaluation`` block.

    ``extra_fields`` names the game-specific keys the caller reads itself.
    """
    if type(raw) is not dict or raw.keys() != _FIELDS | extra_fields:
        raise ValueError("invalid script evaluation configuration")
    address = int(raw["variables_address_ps1"], 0)
    count = raw["variable_count"]
    if (
        type(count) is not int
        or not 0 < count <= 256
        or address % 2
        or not 0x80000000 <= address <= 0x80200000 - 2 * count
    ):
        raise ValueError("invalid script variable array")
    cleared = set()
    for row in raw["entry_cleared_flags"]:
        if row.keys() != {"bank", "first_bit", "last_bit"} or not (
            0 <= row["first_bit"] <= row["last_bit"] < 256
        ):
            raise ValueError("invalid entry-cleared flag range")
        cleared.update(
            (row["bank"], bit) for bit in range(row["first_bit"], row["last_bit"] + 1)
        )
    entry_variables = {}
    for row in raw["entry_variables"]:
        if row.keys() != {"variable", "value"} or not 0 <= row["variable"] < count:
            raise ValueError("invalid entry variable")
        entry_variables[row["variable"]] = row["value"]
    variables = (
        raw["stage_variable"],
        raw["room_variable"],
        *raw["unread_variables"],
        *raw["approach_variables"],
    )
    if any(type(value) is not int or not 0 <= value < count for value in variables):
        raise ValueError("invalid script variable index")
    roots = tuple(raw["roots"])
    if not roots or any(type(root) is not str for root in roots):
        raise ValueError("script evaluation needs its automatic procedures")
    return EntryConfig(
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
    )


def entry_state(
    config: EntryConfig,
    flag: FlagReader,
    halfword: Callable[[int], int | None],
    inventory: Callable[[int], bool | None],
    stage: int,
    room: int,
) -> GameState:
    """Fresh state as the room's scripts would see it on entry.

    ``flag`` returns None for flags it cannot read, ``halfword`` reads an
    unsigned halfword at a PS1 address, or None when it cannot, and
    ``inventory`` says whether the player carries an item type.
    """

    def entry_flag(bank: int, bit: int) -> bool | None:
        if (bank, bit) in config.entry_cleared_flags:
            # The room loader clears these before its scripts run.
            return False
        return flag(bank, bit)

    def entry_variable(index: int) -> int | None:
        if index in config.entry_variables:
            return config.entry_variables[index]
        if index == config.stage_variable:
            return stage
        if index == config.room_variable:
            return room
        if (
            index >= config.variable_count
            or index in config.unread_variables
            or index in config.approach_variables
        ):
            return None
        raw = halfword(config.variables_address + 2 * index)
        return None if raw is None else raw - 0x10000 if raw & 0x8000 else raw

    return GameState(
        entry_flag,
        entry_variable,
        config.approach_variables,
        config.approach_banks,
        inventory,
    )


def pickup_ids(program: dict[str, list[list]], file_type_min: int) -> frozenset[int]:
    """Acquisition IDs of ordinary pickups a room's scripts create or reset."""
    return frozenset(
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
