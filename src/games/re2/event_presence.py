"""Sufficient source conditions for pickups and awards. RE2-COLLECT-005/006."""

from __future__ import annotations

import struct
from collections.abc import Callable
from typing import Literal

from games.re2.startup_effects import StartupEffectAuditSupport, StartupEffectReceipt

# Audited initializer effects shared with ordinary collection proofs. These
# commands neither declare pickups nor yield the synchronous startup task.
INITIALIZER_FALLTHROUGH = (
    0,
    0x22,
    0x26,
    0x2D,
    0x2E,
    0x32,
    0x35,
    0x3D,
    0x44,
    0x4B,
    0x6E,
)

# RE2-COLLECT-013: native clear, set and toggle. Other operand values are not
# admitted to presence proofs even though this revision treats them as no-ops.
FLAG_WRITE_OPERATIONS = (0, 1, 7)


def flag_write_conflicts(
    banks: dict[int, tuple[int, int]], flags: frozenset[tuple[int, int]]
) -> tuple[dict[int, int], frozenset[tuple[int, int]]]:
    words = {}
    for bank, bit in flags:
        address = banks[bank][0] + bit // 32 * 4
        words[address] = words.get(address, 0) | (0x80000000 >> (bit % 32))
    # Native bank numbers can alias, including through an out-of-range bit.
    # Compare the actual PS1 word/mask before applying each proof's bounds.
    aliases = frozenset(
        (bank, bit)
        for bank, (address, _) in banks.items()
        for bit in range(256)
        if words.get(address + bit // 32 * 4, 0) & (0x80000000 >> (bit % 32))
    )
    return words, aliases


def presence_flag_write_proof(
    profile: dict,
) -> tuple[frozenset[tuple[int, int]], dict]:
    """Validate bounded, predicate-disjoint writes and their metadata contract."""
    try:
        layout = profile["runtime_layout"]
        rows = profile["flag_banks"]
        supported = profile.get("presence_condition_flags")
        blocks = [
            (int(layout[f"{kind}_block_address_ps1"], 0), layout[f"{kind}_block_width"])
            for kind in ("player", "save")
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid or missing RE2 presence flag write layout") from error
    if type(layout.get("script_flag_table_address_ps1")) is not str:
        raise ValueError("invalid or missing RE2 presence flag table address")
    try:
        table = int(layout["script_flag_table_address_ps1"], 0)
    except ValueError as error:
        raise ValueError("invalid RE2 presence flag table address") from error
    # An unsigned byte bank indexes a four-byte native pointer table.
    if table % 4 or not 0x80000000 <= table <= 0x80200000 - 256 * 4:
        raise ValueError(
            "RE2 presence flag table address must be aligned within PS1 RAM"
        )
    if (
        type(rows) is not list
        or not rows
        or any(
            type(width) is not int
            or not 1 <= width <= 4096
            or not 0x80000000 <= base <= 0x80200000 - width
            for base, width in blocks
        )
    ):
        raise ValueError("invalid RE2 presence flag write layout")
    banks = {}
    for row in rows:
        if (
            type(row) is not dict
            or row.keys() != {"bank", "address_ps1", "width"}
            or type(row["bank"]) is not int
            or not 0 <= row["bank"] <= 255
            or row["bank"] in banks
            or type(row["address_ps1"]) is not str
            or type(row["width"]) is not int
            or not 4 <= row["width"] <= 32
            or row["width"] % 4
        ):
            raise ValueError("invalid RE2 presence flag write bank")
        try:
            address = int(row["address_ps1"], 0)
        except ValueError as error:
            raise ValueError("invalid RE2 presence flag write bank address") from error
        if address % 4 or not any(
            base <= address and address + row["width"] <= base + width
            for base, width in blocks
        ):
            raise ValueError("RE2 presence flag write bank exceeds bounded state")
        banks[row["bank"]] = address, row["width"]
    if (
        type(supported) is not list
        or not supported
        or any(
            type(row) is not dict
            or row.keys() != {"bank", "bit"}
            or type(row["bank"]) is not int
            or row["bank"] not in banks
            or type(row["bit"]) is not int
            or not 0 <= row["bit"] < banks[row["bank"]][1] * 8
            for row in supported
        )
        or len({(row["bank"], row["bit"]) for row in supported}) != len(supported)
    ):
        raise ValueError("invalid or missing RE2 stable presence flags")
    flags = frozenset((row["bank"], row["bit"]) for row in supported)
    _, forbidden = flag_write_conflicts(banks, flags)
    allowed = frozenset(
        (bank, bit)
        for bank, (_, width) in banks.items()
        for bit in range(width * 8)
        if (bank, bit) not in forbidden
    )
    return allowed, {
        "bank_table_address_ps1": f"0x{table:08X}",
        "operations": list(FLAG_WRITE_OPERATIONS),
        "flag_banks": [
            {"bank": bank, "address_ps1": f"0x{address:08X}", "width": width}
            for bank, (address, width) in sorted(banks.items())
        ],
        "condition_flags": [{"bank": bank, "bit": bit} for bank, bit in sorted(flags)],
    }


def presence_counter_indices(profile: dict) -> frozenset[int]:
    """Validate the revision's bounded counter-write proof. RE2-COLLECT-012."""
    region = profile.get("presence_counter_writes")
    if (
        type(region) is not dict
        or region.keys() != {"address_ps1", "limit_address_ps1"}
        or any(type(value) is not str for value in region.values())
    ):
        raise ValueError("invalid or missing RE2 presence counter write range")
    try:
        base = int(region["address_ps1"], 0)
        limit = int(region["limit_address_ps1"], 0)
    except ValueError as error:
        raise ValueError("invalid RE2 presence counter write addresses") from error
    try:
        layout = profile["runtime_layout"]
        native_base = int(layout["script_counter_address_ps1"], 0)
        save_base = int(layout["save_block_address_ps1"], 0)
        save_width = layout["save_block_width"]
        identities = [
            int(profile[field], 0)
            for field in ("stage_address_ps1", "room_address_ps1", "camera_address_ps1")
        ]
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            "invalid or missing RE2 counter layout or identity addresses"
        ) from error
    # Packet indices are relative to the native origin, not the chosen proof
    # window. A shifted window would otherwise approve the wrong RAM writes.
    if base != native_base:
        raise ValueError(
            "RE2 presence counter range must start at the native counter base"
        )
    # Save accepts any byte index. The bounded work region also contains
    # room identity, so those halfwords must be excluded individually below.
    if (
        base % 2
        or limit % 2
        or not 0x80000000 <= base < limit <= 0x80200000
        or not 2 <= limit - base <= 512
        or type(save_width) is not int
        or not 1 <= save_width <= 4096
        or not save_base <= base < limit <= save_base + save_width
        or any(
            base < int(bank["address_ps1"], 0) + bank["width"]
            and int(bank["address_ps1"], 0) < limit
            for bank in profile["flag_banks"]
        )
    ):
        raise ValueError("RE2 presence counter writes overlap unproved state")
    return frozenset(
        index
        for index in range((limit - base) // 2)
        if all(
            not (base + 2 * index < address + 2 and address < base + 2 * index + 2)
            for address in identities
        )
    )


def initializer_fallthrough(command: dict) -> bool:
    # A counter opcode alone is insufficient: decoding must bind its write to
    # the profile's audited, flag-disjoint range before either proof accepts it.
    return command["opcode"] in INITIALIZER_FALLTHROUGH or (
        command["kind"] == "counter_write" and command["presence_safe"]
    )


def source_presence(
    data: bytes,
    programs: dict,
    targets: set[tuple[str, int]],
    mode: Literal["startup", "scheduled"],
    condition_flags: frozenset[tuple[int, int]],
    fixed_flags: frozenset[tuple[int, int, int]],
    *,
    startup_effects: StartupEffectReceipt
    | StartupEffectAuditSupport = StartupEffectAuditSupport.Unaudited,
) -> dict:
    assert mode in ("startup", "scheduled")
    assert targets and all(key in programs for key, _ in targets)
    assert isinstance(fixed_flags, frozenset) and all(
        (bank, bit) in condition_flags and type(value) is int and value in (0, 1)
        for bank, bit, value in fixed_flags
    ), "fixed startup flags must be supported predicates with explicit values"
    fixed = {(bank, bit): value for bank, bit, value in fixed_flags}
    assert len(fixed) == len(fixed_flags), "fixed startup flags must not conflict"
    assert startup_effects is StartupEffectAuditSupport.Unaudited or isinstance(
        startup_effects, StartupEffectReceipt
    )
    setup_locations = (
        startup_effects.locations_for(data, programs, condition_flags, fixed_flags)
        if isinstance(startup_effects, StartupEffectReceipt)
        else frozenset()
    )
    # An empty set means no sufficient condition was proved. The empty
    # conjunction means unconditional reachability, as in ordinary Boolean DNF.
    unconditional = frozenset((frozenset(),))
    unresolved = frozenset()
    commands = {
        key: {row["offset"]: row for row in program["commands"]}
        for key, program in programs.items()
    }
    groups = {}
    for key, position in sorted(targets):
        row = commands[key].get(position)
        if (
            row is not None
            and row["kind"] == "item"
            and row["opcode"] in (0x4E, 0x69)
            and row["next"] - position == (22 if row["opcode"] == 0x4E else 30)
        ):
            operand = position + (14 if row["opcode"] == 0x4E else 22)
            item_type, _, global_id = struct.unpack_from("<3H", data, operand)
            identity = "item", global_id, item_type
        else:
            identity = "single", key, position
        groups.setdefault(identity, set()).add((key, position))
    # Either creator of one acquisition identity can satisfy the goal before
    # opaque branch outcomes are intersected. Unrelated items/awards retain
    # separate goals; their individual guarantees cannot be combined here.
    target_groups = tuple(frozenset(group) for group in groups.values())

    # Later counter aliases can invalidate fresh presence predicates. Reject
    # them anywhere in the source, as with task cancellation/replacement.
    for program in programs.values():
        for row in program["commands"]:
            if (
                row["kind"] == "counter_write"
                and not initializer_fallthrough(row)
                or row["opcode"] in (3, 5)
                or (
                    row["opcode"] == 4
                    and data[row["offset"] + 1 : row["offset"] + 3] != b"\xff\x18"
                )
            ):
                return {"kind": "unresolved"}

    def simplify(clauses):
        # Bound formula growth before exporting it; exceeding the bound must
        # withhold the proof rather than truncate conditions into a false claim.
        if len(clauses) > 32 or any(len(clause) > 32 for clause in clauses):
            return unresolved
        clauses = set(clauses)
        while True:
            combined = set(clauses)
            for first in clauses:
                for second in clauses:
                    difference = first ^ second
                    if len(difference) == 2:
                        left, right = tuple(difference)
                        if left[:2] == right[:2] and left[2] != right[2]:
                            combined.add(first & second)
            reduced = {x for x in combined if not any(y < x for y in combined)}
            if reduced == clauses:
                return frozenset(reduced)
            clauses = reduced

    def conjunction(first, second):
        clauses = set()
        for left in first:
            for right in second:
                clause = left | right
                if not any(
                    (bank, bit, 1 - value) in clause for bank, bit, value in clause
                ):
                    clauses.add(clause)
                    if len(clauses) > 32:
                        return unresolved
        return simplify(clauses)

    def required_before(goal, root, symbolic_flags):
        active, cache = set(), {}
        steps = 0
        fallthrough = {8}
        if not symbolic_flags:
            # Audited delivery waits, camera, message, actor and audio commands
            # preserve the executing task's continuation past the command.
            fallthrough.update(
                (
                    2,
                    9,
                    10,
                    11,
                    12,
                    0x22,
                    0x29,
                    0x2B,
                    0x36,
                    0x3F,
                    0x40,
                    0x41,
                    0x43,
                    0x51,
                    0x57,
                    0x59,
                    0x5B,
                )
            )

        def walk(key, position, returns):
            nonlocal steps
            if goal != "startup-end" and (key, position) in goal:
                return unconditional
            state = key, position, returns
            steps += 1
            # Bound both work and Python call depth for malformed/deep sources.
            if (
                steps > 4096
                or len(active) >= 256
                or state in active
                or position not in commands[key]
            ):
                return unresolved
            if state in cache:
                return cache[state]
            active.add(state)
            row = commands[key][position]
            kind, opcode = row["kind"], row["opcode"]
            if kind == "end":
                if opcode == 1 and data[row["offset"] + 1] != 0:
                    result = unresolved
                elif returns:
                    result = walk(*returns[-1], returns[:-1])
                else:
                    result = (
                        unconditional
                        if goal == "startup-end" and opcode == 1
                        else unresolved
                    )
            elif kind == "call":
                target = f"17:{row['procedure']}"
                if target not in programs or len(returns) >= 4:
                    result = unresolved
                else:
                    callee = programs[target]
                    body = callee["commands"]
                    waiting = (
                        [x["opcode"] for x in body] == [0x11, 2, 0, 0x12, 0x21, 1]
                        and data[callee["entry"] + 2 : callee["entry"] + 4] == b"\x08\0"
                        and data[body[3]["offset"] + 1] == 4
                        and body[4]["expected"] in (0, 1)
                        and data[body[5]["offset"] + 1] == 0
                    )
                    # This do/wait/check loop can suspend for user input. Its
                    # only exit returns without changing flags or skipping the
                    # caller's later award, so suspension does not erase it.
                    result = (
                        walk(key, row["next"], returns)
                        if waiting and not symbolic_flags
                        else walk(
                            target, callee["entry"], returns + ((key, row["next"]),)
                        )
                    )
            elif kind == "if":
                position = row["next"]
                tests = []
                while (
                    position in commands[key]
                    and commands[key][position]["kind"] == "flag_check"
                ):
                    test = commands[key][position]
                    tests.append((test["bank"], test["bit"], test["expected"]))
                    position = test["next"]
                predicate = commands[key].get(position)
                if (
                    not tests
                    and predicate is not None
                    and (
                        predicate["opcode"] == 0x3E
                        or predicate["opcode"] == 0x23
                        and data[predicate["offset"] + 3] < 7
                    )
                ):
                    # RE2-COLLECT-015: the seven native counter comparisons,
                    # like actor comparisons, only advance the task PC. Require
                    # both outcomes; fresh counter values cannot prove presence.
                    position = predicate["next"]
                elif not tests or any(test[2] not in (0, 1) for test in tests):
                    active.remove(state)
                    return unresolved
                # RE2-COLLECT-019: only a whole-source context proof permits
                # fixed-value pruning. Polling enforces that same context;
                # other fresh predicates remain symbolic below.
                # A false first check exits even a compound IF. A true first
                # check cannot establish its later opaque predicates.
                if (
                    tests
                    and tests[0][:2] in fixed
                    and (len(tests) == 1 or fixed[tests[0][:2]] != tests[0][2])
                ):
                    result = walk(
                        key,
                        position
                        if fixed[tests[0][:2]] == tests[0][2]
                        else row["target"],
                        returns,
                    )
                    active.remove(state)
                    cache[state] = result
                    return result
                yes = walk(key, position, returns)
                no = walk(key, row["target"], returns)
                # Only explicitly supported stable flags become predicates.
                # Lifecycle/input flags can change outside the source during
                # room initialization, so their fresh values prove neither path.
                # Only single native flag predicates are interpreted here.
                # Compound condition encodings need their own native proof;
                # requiring both branches is safe without guessing the join.
                if (
                    symbolic_flags
                    and len(tests) == 1
                    and tests[0][:2] in condition_flags
                ):
                    success = frozenset((frozenset(tests),))
                    failure = frozenset(
                        frozenset(((b, i, 1 - v),)) for b, i, v in tests
                    )
                    result = simplify(
                        conjunction(success, yes) | conjunction(failure, no)
                    )
                else:
                    result = conjunction(yes, no)
            elif opcode == 7:
                result = walk(key, row["target"], returns)
            elif (
                opcode == 4
                and goal == "startup-end"
                or (
                    kind in ("item", "door", "interaction", "reset")
                    or opcode in fallthrough
                    or (key, row["offset"]) in setup_locations
                    or (
                        # Fresh predicates must survive startup. Decoding binds
                        # unrelated writes to canonical, alias-checked bits.
                        (opcode != 0x22 or row["presence_safe"])
                        and initializer_fallthrough(row)
                    )
                )
            ):
                result = walk(key, row["next"], returns)
            else:
                # Startup writes, task control, loops and unsupported effects
                # cannot authorize a condition evaluated from fresh flags.
                result = unresolved
            active.remove(state)
            cache[state] = result
            return result

        return walk(root, programs[root]["entry"], ())

    # Queuing is insufficient if startup later transitions, loops or changes
    # flags before the task can run. Require both synchronous roots to finish
    # using only the audited initializer effects, including after the fork.
    for root in ("16:0", "17:0"):
        if required_before("startup-end", root, True) != unconditional:
            return {"kind": "unresolved"}

    conditions = unresolved
    if mode == "startup":
        for target in target_groups:
            for root in ("16:0", "17:0"):
                conditions = simplify(conditions | required_before(target, root, True))
    else:
        for key, program in programs.items():
            for row in program["commands"]:
                if row["opcode"] != 4:
                    continue
                packet = data[row["offset"] : row["next"]]
                target = f"17:{packet[3]}"
                if packet[1:3] != b"\xff\x18" or target not in programs:
                    continue
                if not any(
                    required_before(goal, target, False) == unconditional
                    for goal in target_groups
                ):
                    continue
                for root in ("16:0", "17:0"):
                    conditions = simplify(
                        conditions
                        | required_before(frozenset({(key, row["offset"])}), root, True)
                    )
    if conditions == unconditional:
        return {"kind": "required"}
    if not conditions:
        return {"kind": "unresolved"}
    return {
        "kind": "conditions",
        "any_of": [
            [
                {"bank": bank, "bit": bit, "expected": value}
                for bank, bit, value in sorted(clause)
            ]
            for clause in sorted(conditions, key=lambda clause: sorted(clause))
        ],
    }


def presence_matches(presence: dict, flag: Callable[[int, int], bool]) -> bool:
    assert presence["kind"] in ("unresolved", "required", "conditions")
    # Conditions are sufficient only. A mismatch withholds presence; it does
    # not prove absence or override an independently observed acquisition.
    return (
        presence["kind"] == "required"
        or presence["kind"] == "conditions"
        and any(
            all(flag(test["bank"], test["bit"]) == test["expected"] for test in clause)
            for clause in presence["any_of"]
        )
    )
