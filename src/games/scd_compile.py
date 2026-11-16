"""Compile room scripts into the shared evaluation model. RE2-EVAL-001.

RE2 and RE3 scripts share their structure but number their commands
differently. Each game supplies an ``OpcodeSet``; this module keeps one
implementation of control flow, switch chains and interaction operands.
The model keeps only operations that affect control flow, flags, variables
or room interactions, with source-relative offsets so creators keep the
identities used by room catalogs and map door markers.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class OpcodeSet:
    widths: tuple[int, ...]
    ends: frozenset[int]
    if_: int
    else_: int
    goto: int
    # Loop openers store their block length after the opcode and one operand
    # byte; Do's predicate follows its closing command.
    loops: frozenset[int]
    loop_ends: frozenset[int]
    switch: int
    case: int
    default: int
    end_switch: int
    break_: int
    ck: int
    cmp: int
    set_: int
    # Unreadable predicates. Approach predicates depend only on how the player
    # arrives or acts; state predicates read persistent game state.
    approach_conditions: frozenset[int]
    state_conditions: frozenset[int]
    # opcode -> (kind, destination operand index, source operand index):
    # kind 0 stores the signed 16-bit value at the source index, 1 copies the
    # variable named by the source byte, 2 stores an unreadable result.
    variable_writes: dict[int, tuple[int, int, int]]
    # Commands that store an unreadable result in one fixed variable.
    fixed_variable_writes: dict[int, int]
    # opcode -> offset of the type/amount/ID triple.
    items: dict[int, int]
    doors: frozenset[int]
    interactions: frozenset[int]
    reset: int
    aot_on: int
    gosub: int
    exec_: int
    # Work_copy stores a variable into a later command's bytes: operand 1 is
    # the variable, 2 the target offset after this command, 3 nonzero for a
    # halfword. Patched operands then follow the variable.
    work_copy: int


def _embedded_call(opcodes: OpcodeSet, kind: int, data: bytes) -> int:
    # Event interactions store "ff 00 <Gosub> nn", like task starts.
    if kind == 5 and data[2] == opcodes.gosub:
        return data[3]
    return -1


def switch_labels(
    data: bytes, start: int, stop: int, case: int, default: int, end_switch: int
) -> tuple[int, tuple[int, ...]]:
    """Follow the native unsigned case links, including the closing marker."""
    following = start + 4
    end = following + struct.unpack_from("<H", data, start + 2)[0]
    if not following < end < stop or data[end - 2] != end_switch:
        raise ValueError("invalid switch bounds")
    label, labels = following, []
    while True:
        if not following <= label <= end - 2:
            raise ValueError("switch case outside its bounds")
        marker = data[label]
        labels.append(label)
        if marker == case and label + 6 <= end - 2:
            label += 6 + struct.unpack_from("<H", data, label + 2)[0]
        elif marker == default and label < end - 2:
            # Default stops the native search. Its body and the closing
            # marker still need independent decoder visits.
            labels.append(end - 2)
            break
        elif marker == end_switch and label == end - 2:
            break
        else:
            raise ValueError("invalid switch label chain")
    return end, tuple(labels)


def compile_procedure(
    opcodes: OpcodeSet, data: bytes, start: int, stop: int
) -> list[list]:
    # Decode only commands control flow reaches. Procedures can embed data
    # that a Goto skips, and padding follows their last terminator.
    rows: list[list] = []
    decoded: dict[int, int] = {}
    patches = []
    pending = [start]
    widths = opcodes.widths
    while pending:
        position = pending.pop()
        if position in decoded or position == stop:
            # A block may end at the procedure's end; running there is
            # reported by the interpreter if a path reaches it.
            continue
        if not start <= position < stop:
            return [[start, start, "invalid"]]
        opcode = data[position]
        if opcode >= len(widths) or position + widths[opcode] > stop:
            return [[start, start, "invalid"]]
        packet = data[position : position + widths[opcode]]
        following = position + len(packet)
        decoded[position] = following
        row: list | None = None
        if opcode in opcodes.ends:
            row = ["end"]
        elif opcode == opcodes.if_:
            row = ["if", following + struct.unpack_from("<H", packet, 2)[0]]
        elif opcode == opcodes.else_:
            row = ["else", position + struct.unpack_from("<H", packet, 2)[0]]
        elif opcode == opcodes.goto:
            row = ["goto", position + struct.unpack_from("<h", packet, 4)[0]]
        elif opcode in opcodes.loops:
            row = ["loop", following + struct.unpack_from("<H", packet, 2)[0]]
        elif opcode in opcodes.loop_ends:
            row = ["loop_end"]
        elif opcode == opcodes.switch:
            try:
                end, labels = switch_labels(
                    data,
                    position,
                    stop,
                    opcodes.case,
                    opcodes.default,
                    opcodes.end_switch,
                )
            except ValueError:
                # A reachable selector without a native case chain.
                return [[start, start, "invalid"]]
            row = [
                "switch",
                end,
                packet[1],
                # Case values are signed; None marks Default, which stops the
                # native scan where it appears.
                [
                    [label, struct.unpack_from("<h", data, label + 4)[0]]
                    if data[label] == opcodes.case
                    else [label, None]
                    for label in labels
                    if label != end - 2
                ],
            ]
        elif opcode in (opcodes.case, opcodes.default, opcodes.end_switch):
            row = ["case"]
        elif opcode == opcodes.break_:
            row = ["break"]
        elif opcode == opcodes.ck:
            row = ["ck", packet[1], packet[2], packet[3]]
        elif opcode == opcodes.cmp:
            row = ["cmp", packet[2], packet[3], struct.unpack_from("<h", packet, 4)[0]]
        elif opcode in opcodes.approach_conditions:
            row = ["cond", 1]
        elif opcode in opcodes.state_conditions:
            row = ["cond", 0]
        elif opcode in opcodes.variable_writes:
            kind, destination, source = opcodes.variable_writes[opcode]
            argument = (
                struct.unpack_from("<h", packet, source)[0]
                if kind == 0
                else packet[source]
                if kind == 1
                else -1
            )
            row = ["var", packet[destination], kind, argument]
        elif opcode in opcodes.fixed_variable_writes:
            row = ["var", opcodes.fixed_variable_writes[opcode], 2, -1]
        elif opcode == opcodes.set_:
            row = ["set", packet[1], packet[2], packet[3]]
        elif opcode in opcodes.items:
            row = [
                "item",
                packet[1],
                packet[3],
                *struct.unpack_from("<3H", packet, opcodes.items[opcode]),
            ]
        elif opcode in opcodes.doors:
            row = ["door", packet[1], packet[3]]
        elif opcode in opcodes.interactions:
            row = [
                "aot",
                packet[1],
                packet[2],
                packet[3],
                _embedded_call(opcodes, packet[2], packet[-6:]),
            ]
        elif opcode == opcodes.reset:
            payload = packet[4:]
            item = (
                list(struct.unpack_from("<3H", payload, 0))
                if packet[2] == 2
                else [-1, -1, -1]
            )
            row = [
                "reset",
                packet[1],
                packet[2],
                packet[3],
                _embedded_call(opcodes, packet[2], payload),
                *item,
            ]
        elif opcode == opcodes.aot_on:
            row = ["aot_on", packet[1]]
        elif opcode == opcodes.gosub:
            row = ["gosub", packet[1]]
        elif opcode == opcodes.exec_:
            row = ["exec", packet[3] if packet[2] == opcodes.gosub else -1]
        elif opcode == opcodes.work_copy:
            row = ["patch", following + packet[2], packet[1], 2 if packet[3] else 1]
            patches.append(row[1])
        kind = row[0] if row is not None else ""
        if kind in ("if", "loop"):
            pending.extend((following, row[1]))
        elif kind in ("else", "goto"):
            pending.append(row[1])
        elif kind == "switch":
            pending.extend((row[1], *(label for label, _ in row[3])))
        elif kind not in ("end", "break"):
            # Break continues at its enclosing block's end, which the opener
            # already queued.
            pending.append(following)
        if row is not None:
            rows.append([position, following, *row])
    ordered = sorted(decoded.items())
    if any(end > begin for (_, end), (begin, _) in zip(ordered, ordered[1:])):
        # Two control paths decode overlapping commands.
        return [[start, start, "invalid"]]
    rows.sort()
    # Patches may change a predicate or flag write's bit, variable or value,
    # which the interpreter follows. Unreadable predicates, loop counts and a
    # non-item Reset's data do not affect the model. Any other patched modeled
    # operand would silently keep its source value, so the procedure is not
    # modeled.
    relevant = set()
    for target in patches:
        owner = max((row for row in rows if row[0] <= target), default=None)
        if owner is None or owner[1] <= target:
            if not start <= target < stop:
                return [[start, start, "invalid"]]
            continue
        field = target - owner[0]
        op = owner[2]
        if op in ("ck", "set") and field == 2 or op == "cmp" and field in (2, 4):
            relevant.add(target)
        elif not (
            op == "cond"
            or op == "loop"
            and field >= 4
            # Reset operands: slot, kind, SAT, then data; events keep their
            # procedure in data bytes 2-3.
            or op == "reset"
            and field >= 4
            and owner[4] != 2
            and not (owner[4] == 5 and field in (6, 7))
        ):
            return [[start, start, "invalid"]]
    # Other patches change nothing the model reads; keeping them would only
    # split otherwise identical evaluation paths.
    return [row for row in rows if row[2] != "patch" or row[3] in relevant]


def compile_section(
    opcodes: OpcodeSet, data: bytes, section: int, name: str
) -> dict[str, list[list]]:
    """Compile one RDT procedure directory into ``name:N`` procedures."""
    offsets = struct.unpack_from("<23I", data, 8)
    begin = offsets[section]
    end = min([value for value in offsets if value > begin] + [len(data)])
    first = struct.unpack_from("<H", data, begin)[0]
    entries = struct.unpack_from(f"<{first // 2}H", data, begin)
    program = {}
    for number, entry in enumerate(entries):
        stop = begin + entries[number + 1] if number + 1 < len(entries) else end
        program[f"{name}:{number}"] = compile_procedure(
            opcodes, data, begin + entry, stop
        )
    return program
