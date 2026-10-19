"""Sufficient flag conditions for scheduled awards. See RE2-COLLECT-005."""

from __future__ import annotations

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


def event_presence(
    data: bytes, programs: dict, award_program: str, award_offset: int
) -> dict:
    # An empty set means no sufficient condition was proved. The empty
    # conjunction means unconditional reachability, as in ordinary Boolean DNF.
    unconditional = frozenset((frozenset(),))
    unresolved = frozenset()
    commands = {
        key: {row["offset"]: row for row in program["commands"]}
        for key, program in programs.items()
    }

    # A task queued by startup runs later. Reject cancellation/replacement
    # anywhere in the source, including commands after the scheduling point.
    for program in programs.values():
        for row in program["commands"]:
            if row["opcode"] in (3, 5) or (
                row["opcode"] == 4
                and data[row["offset"] + 1 : row["offset"] + 3] != b"\xff\x18"
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
        fallthrough = set(INITIALIZER_FALLTHROUGH) - {0x22} | {8}
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
            if (key, position) == goal:
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
                if (
                    not tests
                    and position in commands[key]
                    and commands[key][position]["opcode"] == 0x3E
                ):
                    # Actor comparisons are opaque here; both outcomes must
                    # still require the award. Never guess their live values.
                    position = commands[key][position]["next"]
                elif not tests or any(test[2] not in (0, 1) for test in tests):
                    active.remove(state)
                    return unresolved
                yes = walk(key, position, returns)
                no = walk(key, row["target"], returns)
                # Only single native flag predicates are interpreted here.
                # Compound condition encodings need their own native proof;
                # requiring both branches is safe without guessing the join.
                if symbolic_flags and len(tests) == 1:
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
    for key, program in programs.items():
        for row in program["commands"]:
            if row["opcode"] != 4:
                continue
            packet = data[row["offset"] : row["next"]]
            target = f"17:{packet[3]}"
            if packet[1:3] != b"\xff\x18" or target not in programs:
                continue
            if (
                required_before((award_program, award_offset), target, False)
                != unconditional
            ):
                continue
            for root in ("16:0", "17:0"):
                conditions = simplify(
                    conditions | required_before((key, row["offset"]), root, True)
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
