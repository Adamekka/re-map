"""Fixed-scenario exclusion proofs, separate from presence. RE2-COLLECT-007/008."""

from __future__ import annotations

import struct

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
    data: bytes, room: dict, flags: list[dict[str, int]], flag_banks: list[dict]
) -> list[int]:
    fixed = {(row["bank"], row["bit"]): row["expected"] for row in flags}
    assert fixed and len(fixed) == len(flags)
    if not room["candidate_list_complete"]:
        return []
    banks = {
        row["bank"]: (int(row["address_ps1"], 0), row["width"]) for row in flag_banks
    }
    fixed_words = {}
    for bank, bit in fixed:
        address = banks[bank][0] + bit // 32 * 4
        fixed_words[address] = fixed_words.get(address, 0) | (0x80000000 >> (bit % 32))
    # Native banks can alias. Compare the PS1 virtual word and mask, not just the
    # script bank number, before treating any flag write as unrelated.
    forbidden = {
        (bank, bit)
        for bank, (address, _) in banks.items()
        for bit in range(256)
        if fixed_words.get(address + bit // 32 * 4, 0) & (0x80000000 >> (bit % 32))
    }
    # A negative claim needs every creator, including other tasks. Audited
    # event effects may change unrelated state, but cannot introduce an item
    # identity or change the fixed scenario bits. RE2-COLLECT-008.
    programs = room["programs"]
    commands = {
        key: {row["offset"]: row for row in program["commands"]}
        for key, program in programs.items()
    }
    fallthrough = set(INITIALIZER_FALLTHROUGH) - {0x22} | {8}
    fallthrough.update(
        (
            2,
            9,
            10,
            11,
            12,
            0x24,
            0x25,
            0x29,
            0x2A,
            0x2B,
            0x33,
            0x34,
            0x36,
            0x3C,
            0x3F,
            0x40,
            0x41,
            0x42,
            0x43,
            0x47,
            0x51,
            0x53,
            0x57,
            0x58,
            0x59,
            0x5B,
            0x62,
        )
    )
    predicates = {0x23, 0x3E, 0x5E}
    status_writes = {
        0x29: (1, 0x00100100),
        0x2A: (1, 0x00100100),
        0x3C: (1, 0x00000100),
        0x59: (1, 0x00000020),
    }
    opaque_loops = set()
    for key, program in programs.items():
        if not any(row["opcode"] in (0x11, 0x12) for row in program["commands"]):
            continue
        # Do/while actor waits need no reachability guess: every command in
        # their procedure is possible. Require paired local bounds and one
        # read-only predicate, so hidden condition bytecode cannot be a creator.
        loops = []
        for row in program["commands"]:
            if row["opcode"] in (6, 7, 8, 0x17):
                return []
            if row["opcode"] == 0x11:
                if len(loops) >= 4:
                    return []
                loops.append(
                    row["next"] + struct.unpack_from("<h", data, row["offset"] + 2)[0]
                )
            elif row["opcode"] == 0x12:
                test = commands[key].get(row["next"])
                if (
                    not loops
                    or test is None
                    or test["opcode"] not in predicates | {0x21}
                    or test["next"] - test["offset"] != data[row["offset"] + 1]
                    or test["next"] != loops.pop()
                    or test["next"] not in commands[key]
                ):
                    return []
        if loops:
            return []
        opaque_loops.add(key)
    reset_ids = set()
    slot_kinds = {}
    for item in room["items"]:
        slot_kinds.setdefault(item["slot"], set()).add(2)
    for door in room["doors"]:
        slot_kinds.setdefault(door["slot"], set()).add(1)
    for program in programs.values():
        for row in program["commands"]:
            if row["kind"] in ("interaction", "reset"):
                slot_kinds.setdefault(row["slot"], set()).add(row["interaction"])
                if row["kind"] == "reset" and row["interaction"] == 2:
                    reset_ids.add(struct.unpack("<3H", bytes(row["data"]))[2])
    for key, program in programs.items():
        for row in program["commands"]:
            kind = row["kind"]
            if kind == "call":
                target = f"17:{row['procedure']}"
                if target not in programs:
                    return []
            elif kind == "flag_write":
                if (
                    row["bank"] not in banks
                    or row["bit"] >= banks[row["bank"]][1] * 8
                    or row["operation"] not in (0, 1, 7)
                    or (row["bank"], row["bit"]) in forbidden
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
            elif kind == "reset":
                # A reset is another possible creator even without a matching
                # live descriptor. Its identity must never be excluded.
                continue
            elif row["opcode"] in (0x11, 0x12):
                if key not in opaque_loops:
                    return []
            elif row["opcode"] == 4:
                if (
                    data[row["offset"] + 1 : row["offset"] + 3] != b"\xff\x18"
                    or f"17:{data[row['offset'] + 3]}" not in programs
                ):
                    return []
            elif row["opcode"] == 0x47:
                kinds = slot_kinds.get(data[row["offset"] + 1], set())
                if not kinds or not kinds <= {0, 1, 2, 5}:
                    return []
                # Item and door dispatch also set native status bits. Binding
                # an allowed interaction kind alone does not preserve them.
                if any(
                    bank not in banks or fixed_words.get(banks[bank][0], 0) & mask
                    for interaction, bank, mask in (
                        (1, 2, 0xFF000000),
                        (2, 1, 0x00008000),
                    )
                    if interaction in kinds
                ):
                    return []
            elif row["opcode"] == 0x2E:
                work, index = data[row["offset"] + 1 : row["offset"] + 3]
                # Work_set reads a signed index without checking bounds. The
                # native actor search covers 32 enemy pointers; object
                # selection uses direct positive-offset structures.
                if (
                    work not in (1, 3, 4)
                    or work == 3
                    and index >= 32
                    or work == 4
                    and index >= 128
                ):
                    return []
            elif not (
                kind in ("if", "flag_check", "door")
                or row["opcode"] in predicates
                or kind == "award"
                or row["opcode"] == 7
                or row["opcode"] in fallthrough
            ):
                return []
            # These native camera/audio commands write named status bits, even
            # though they preserve ordinary item creation. Reject overlap with
            # any profile-fixed bit instead of assuming this profile's mask.
            if row["opcode"] in status_writes or row["opcode"] == 0x2B:
                bank, mask = (
                    (2, struct.unpack_from("<H", data, row["offset"] + 4)[0] << 16)
                    if row["opcode"] == 0x2B
                    else status_writes[row["opcode"]]
                )
                if bank not in banks or fixed_words.get(banks[bank][0], 0) & mask:
                    return []
    # Also reject raw writer candidates outside decoded paths, within procedure
    # extents. Geometry and texture bytes outside scripts are not commands.
    # False positives withhold proof rather than inventing a fixed assumption.
    if any(
        bytes((0x22, bank, bit)) in data[program["entry"] : program["limit"]]
        for bank, bit in forbidden
        for program in programs.values()
    ):
        return []

    # Loop procedures contribute every decoded creator, independently of any
    # fixed predicate. A wait cannot hide an alternative creator from proof.
    pending = [
        (key, program["entry"], ())
        for key, program in programs.items()
        if key not in opaque_loops
    ]
    seen = set()
    reached = {(key, position) for key in opaque_loops for position in commands[key]}
    steps = len(reached)
    if steps > 4096:
        return []
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
                if (
                    position not in commands[key]
                    or commands[key][position]["opcode"] not in predicates
                ):
                    return []
                position = commands[key][position]["next"]
            branches = (False, True)
            if (
                len(tests) == 1
                and (tests[0]["bank"], tests[0]["bit"]) in fixed
                and tests[0]["expected"] in (0, 1)
            ):
                test = tests[0]
                branches = (fixed[test["bank"], test["bit"]] == test["expected"],)
            # False checks pop the native IF frame; true checks retain it
            # until Else/Endif. Unknown predicates may take either path.
            if False in branches:
                pending.append((key, row["target"], conditions))
            if True in branches:
                # Keep deeper conditional stacks outside this negative proof.
                if len(conditions) >= 4:
                    return []
                pending.append((key, position, conditions + (row["target"],)))
        elif row["kind"] == "flag_check" or row["opcode"] in predicates:
            if not conditions:
                return []
            # Opaque predicates can fail after another condition succeeded.
            # Include their false continuation as well as their true one.
            pending.append((key, conditions[-1], conditions[:-1]))
            pending.append((key, row["next"], conditions))
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
        and gid not in reset_ids
        and len({item["type"] for item in room["items"] if item["global_id"] == gid})
        == 1
    )
