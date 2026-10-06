"""Prove bounded RE1 interaction scripts that delegate or only display text.

The proof accepts audited state-0 control flow and dialog completion, not
arbitrary reachable callbacks. See RE1-DOORS-005/006 for scope and evidence.
"""

from scan_events import EventScan


def build_scripted_door_rules(data: bytes, scan: EventScan, blocks: list) -> list[dict]:
    operations = {offset: (op, raw) for offset, op, raw in scan.operations}
    # VM header and first procedure length precede the first SCD command.
    procedures = {block[0]["start"] - 4: block for block in blocks if block}
    failed = {failure.entry for failure in scan.failures}
    result = []

    def inspect_entry(entry, first):
        points = {point.offset for point in scan.points if point.entry == entry}
        dispatches = {d.offset for d in scan.dispatches if d.entry == entry}
        if (
            entry in failed
            or any(p.state != 0 for p in scan.points if p.entry == entry)
            or any(start.entry == entry for start in scan.starts)
        ):
            return
        cursor, seen = first, set()
        visited_dispatches, calls = set(), []
        prompt, completed_prompt = False, False
        changes_character, external_wait, supported = False, False, True

        def inspect_commands(commands):
            nonlocal prompt, completed_prompt, changes_character
            for command in commands:
                offset = command["offset"]
                op, raw = operations[offset]
                if op == 0:
                    continue
                if op == 0x0B:
                    # The message helper sets byte 5's busy bit. Zero is a
                    # selectable/completed result after its audited wait.
                    prompt, completed_prompt = bool(raw[1] & 0x80), False
                elif op == 5 and tuple(raw[1:4]) in ((6, 23, 0), (6, 23, 1)):
                    continue  # This dialog control bit cannot change a door source.
                elif op == 0x17:
                    continue  # Positional audio does not dispatch a door action.
                elif op == 0x24 and raw[2] == 1 and not calls:
                    calls.append(raw[1])
                else:
                    return False
            return True

        while cursor in points and cursor not in seen:
            seen.add(cursor)
            op = data[cursor]
            if op == 0xFF or 10 <= op < 0xF6:
                break  # The state-0 default stops, rather than scanning its tail.
            if op in (0, 0xFE):
                cursor += 1
            elif op in (0xF6, 0xF7):
                external_wait = True
                cursor += 1
            elif op == 0xF8:
                cursor += 1
            elif op == 0xF9:
                cursor += 3  # The native u16 decrement eventually leaves this wait.
            elif op == 0xFC:
                target = cursor + data[cursor + 1]
                command = cursor + 2
                if (
                    not prompt
                    or calls
                    or operations.get(command) != (6, bytes((6, 5, 2, 128)))
                    or target < command + 4
                    or target not in points
                ):
                    supported = False
                    break
                cursor = target
                while cursor in points and data[cursor] == 0xFE:
                    cursor += 1
                if cursor not in points or data[cursor] != 0xFD:
                    supported = False
                    break
                if not any(
                    p.entry == entry
                    and p.offset == cursor
                    and p.frames
                    and p.frames[-1] == ("call", target, command)
                    for p in scan.points
                ):
                    supported = False
                    break
                visited_dispatches.add(cursor)
                # FD repeats while byte 5 >= 0x80. Its exit establishes that
                # the dialog closed; acceptance is still an explicit choice.
                completed_prompt = True
                cursor += 1
            elif op in (6, 7):
                visited_dispatches.add(cursor)
                width = data[cursor + 1]
                if op == 7:
                    operation = operations.get(cursor + 2)
                    if operation is None or width < 2 + len(operation[1]):
                        supported = False
                        break
                    # Native VM07 calls exactly one SCD handler. A larger
                    # jump skips its tail; it does not execute more commands.
                    commands = [{"offset": cursor + 2}]
                    supported = inspect_commands(commands)
                else:
                    block = procedures.get(cursor)
                    if block is None:
                        supported = False
                        break
                    for procedure in block:
                        commands = procedure["commands"]
                        if commands[0]["kind"] != "if":
                            if not inspect_commands(commands):
                                supported = False
                                break
                            continue
                        # The accepted dialog branch has one normal door call.
                        # Story, inventory and unmodeled guards need another rule.
                        body = commands[2:-2]
                        if (
                            not completed_prompt
                            or calls
                            or len(commands) < 5
                            or commands[1]["kind"] != "byte-test"
                            or commands[1]["args"] != [5, 0, 0]
                            or commands[-2]["kind"] != "endif"
                            or commands[-1]["kind"] != "end"
                            or commands[0]["args"] != [commands[-1]["offset"]]
                            or not body
                            or body[-1]["kind"] != "aot-callback"
                            or body[-1]["args"][1:] != [1, 1]
                            or any(
                                c["kind"] != "variable-write"
                                or len(c["args"]) != 3
                                or c["args"][:2] != [1, 9]
                                for c in body[:-1]
                            )
                        ):
                            supported = False
                            break
                        changes_character = bool(body[:-1])
                        calls.append(body[-1]["args"][0])
                if not supported:
                    break
                cursor += width
            else:
                supported = False
                break
        else:
            supported = False
        if (
            supported
            and visited_dispatches == dispatches
            and not (calls and external_wait)
        ):
            result.append(
                {
                    "entry": entry,
                    "dispatches": sorted(dispatches),
                    "door_slots": calls,
                    "changes_character": changes_character,
                }
            )

    for entry, first in enumerate(scan.entries):
        inspect_entry(entry, first)
    return result
