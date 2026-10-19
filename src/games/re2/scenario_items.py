"""Fixed-scenario exclusion proofs, separate from presence. RE2-COLLECT-007."""

from __future__ import annotations

from games.re2.event_presence import INITIALIZER_FALLTHROUGH


def scenario_flags(profile: dict) -> list[dict[str, int]]:
    layout = profile["runtime_layout"]
    mask, expected = layout["scenario_mask"], layout["scenario_value"]
    banks = [
        row
        for row in profile["flag_banks"]
        if int(row["address_ps1"], 0) == int(layout["status_flags_address_ps1"], 0)
        and type(row["width"]) is int
        and row["width"] == 4
    ]
    if (
        type(mask) is not int
        or not 0 < mask <= 0xFFFFFFFF
        or type(expected) is not int
        or not 0 <= expected <= 0xFFFFFFFF
        or expected & ~mask
        or len(banks) != 1
        or type(banks[0]["bank"]) is not int
        or not 0 <= banks[0]["bank"] <= 255
    ):
        raise ValueError(
            "RE2 scenario requires a fixed mask and one matching flag bank"
        )
    return [
        {
            "bank": banks[0]["bank"],
            "bit": bit,
            "expected": int(bool(expected & (0x80000000 >> bit))),
        }
        for bit in range(32)
        if mask & (0x80000000 >> bit)
    ]


def scenario_absent_items(
    data: bytes, room: dict, flags: list[dict[str, int]]
) -> list[int]:
    fixed = {(row["bank"], row["bit"]): row["expected"] for row in flags}
    assert fixed and len(fixed) == len(flags)
    if not room["candidate_list_complete"]:
        return []
    # A negative claim needs every possible creator, including other tasks.
    # Restrict the entire source to audited declarations/effects and leaf calls;
    # resets, writes and unsupported commands cannot establish exclusion.
    programs = room["programs"]
    commands = {
        key: {row["offset"]: row for row in program["commands"]}
        for key, program in programs.items()
    }
    fallthrough = set(INITIALIZER_FALLTHROUGH) - {0x22} | {8}
    for program in programs.values():
        for row in program["commands"]:
            kind = row["kind"]
            if kind == "call":
                target = f"17:{row['procedure']}"
                if target not in programs or any(
                    command["kind"] == "call"
                    for command in programs[target]["commands"]
                ):
                    return []
            elif kind == "end":
                if row["opcode"] != 1 or data[row["offset"] + 1] != 0:
                    return []
            elif kind == "interaction":
                # Generic AOT creators must not hide an uncatalogued item.
                if row["interaction"] == 2:
                    return []
            elif kind == "item":
                if data[row["offset"] + 2] not in (0, 2):
                    return []
            elif not (
                kind in ("if", "flag_check", "door")
                or row["opcode"] == 7
                or row["opcode"] in fallthrough
            ):
                return []
    # Also reject raw writer candidates outside decoded paths, within procedure
    # extents. Geometry and texture bytes outside scripts are not commands.
    # False positives withhold proof rather than inventing a fixed assumption.
    if any(
        bytes((0x22, bank, bit)) in data[program["entry"] : program["limit"]]
        for bank, bit in fixed
        for program in programs.values()
    ):
        return []

    pending = [(key, program["entry"], ()) for key, program in programs.items()]
    seen, reached = set(), set()
    steps = 0
    while pending:
        key, position, conditions = pending.pop()
        state = key, position, conditions
        if state in seen:
            continue
        steps += 1
        if steps > 4096 or position not in commands[key]:
            return []
        seen.add(state)
        reached.add((key, position))
        row = commands[key][position]
        if row["kind"] == "end":
            continue
        if row["kind"] == "if":
            position = row["next"]
            tests = []
            while (
                position in commands[key]
                and commands[key][position]["kind"] == "flag_check"
            ):
                test = commands[key][position]
                tests.append(test)
                steps += 1
                position = test["next"]
                if steps > 4096:
                    return []
            if not tests:
                return []
            branches = (False, True)
            if (
                len(tests) == 1
                and (tests[0]["bank"], tests[0]["bit"]) in fixed
                and tests[0]["expected"] in (0, 1)
            ):
                test = tests[0]
                branches = (fixed[test["bank"], test["bit"]] == test["expected"],)
            # False checks leave the native IF frame; true checks retain it
            # until Else/Endif. Unknown predicates may take either path.
            if False in branches:
                pending.append((key, row["target"], conditions))
            if True in branches:
                # Keep deeper conditional stacks outside this negative proof.
                if len(conditions) >= 4:
                    return []
                pending.append((key, position, conditions + (row["target"],)))
        elif row["kind"] == "flag_check":
            return []
        elif row["opcode"] in (7, 8):
            if not conditions:
                return []
            pending.append(
                (
                    key,
                    row["target"] if row["opcode"] == 7 else row["next"],
                    conditions[:-1],
                )
            )
        else:
            # Calls may return; every callee entry is independently seeded.
            # Ignoring nontermination adds possible paths rather than hiding one.
            pending.append((key, row["next"], conditions))
    targets = {}
    items = {item["offset"]: item for item in room["items"]}
    for key, program in programs.items():
        for row in program["commands"]:
            if row["kind"] == "item":
                targets.setdefault(items[row["item"]]["global_id"], set()).add(
                    (key, row["offset"])
                )
    assert targets.keys() == {item["global_id"] for item in room["items"]}
    return sorted(
        gid
        for gid, creators in targets.items()
        if not creators & reached
        and len({item["type"] for item in room["items"] if item["global_id"] == gid})
        == 1
    )
