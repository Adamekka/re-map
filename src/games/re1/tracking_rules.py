"""Evaluate source-bound RE1 room interactions from fresh game state.

Unknown predicates explore both native IF outcomes. Only interaction states
that agree on every path are published. This is a read-only reconstruction,
not a replay of game side effects or a guess from another room's local bytes.
"""

from __future__ import annotations

import struct
from collections.abc import Callable
from dataclasses import dataclass

from games.game_profile import RoomId
from games.re1.room_items import (
    MemoryResult,
    RuntimeItemKind,
    RuntimeItemState,
    RuntimeRoomItem,
    RuntimeRoomItems,
)


@dataclass(frozen=True)
class RuleCommand:
    offset: int
    next: int
    kind: str
    args: tuple[int, ...]

    def __post_init__(self) -> None:
        counts = {
            "end": 0,
            "if": 1,
            "else": 1,
            "endif": 0,
            "flag-test": 3,
            "flag-write": 3,
            "byte-test": 3,
            "item": 5,
            "door": 10,
            "aot-create": 3,
            "aot-handler": 3,
            "uncertain-test": 0,
        }
        if (
            self.kind not in counts
            or len(self.args) != counts[self.kind]
            or not 0 <= self.offset < self.next
        ):
            raise ValueError("invalid tracking rule command")
        if any(type(value) is not int for value in self.args):
            raise ValueError("tracking rule operands must be integers")
        if self.kind in ("flag-test", "flag-write", "byte-test") and any(
            not 0 <= value <= 255 for value in self.args
        ):
            raise ValueError("tracking rule operand exceeds one byte")
        if (
            self.kind in ("item", "aot-create", "aot-handler", "door")
            and not 0 <= self.args[0] < 24
        ):
            raise ValueError("tracking rule slot exceeds the pinned AOT registry")
        if self.kind == "item" and any(
            not 0 <= value <= 255 for value in self.args[1:]
        ):
            raise ValueError("tracking item fields must fit one byte")
        if self.kind == "door":
            _, x, z, width, depth, animation, lock, target, key, mode = self.args
            if (
                not all(-32768 <= value <= 32767 for value in (x, z))
                or not all(0 <= value <= 65535 for value in (width, depth))
                or not all(
                    0 <= value <= 255 for value in (animation, lock, target, key, mode)
                )
            ):
                raise ValueError("invalid tracking door fields")
        if self.kind in ("aot-create", "aot-handler") and not all(
            0 <= value <= 255 for value in self.args[1:]
        ):
            raise ValueError("invalid tracking handler fields")


@dataclass(frozen=True)
class RuleProcedure:
    start: int
    end: int
    commands: tuple[RuleCommand, ...]

    def __post_init__(self) -> None:
        addresses = {command.offset for command in self.commands}
        if (
            not 0 <= self.start < self.end
            or self.start not in addresses
            or len(addresses) != len(self.commands)
        ):
            raise ValueError("invalid tracking procedure")
        for command in self.commands:
            if not self.start <= command.offset < command.next <= self.end:
                raise ValueError("tracking command outside procedure")
            if command.kind in ("if", "else") and command.args[0] not in addresses | {
                self.end
            }:
                raise ValueError("tracking branch must target a command boundary")
            if command.kind in ("if", "else") and command.args[0] < command.next:
                raise ValueError("tracking branches must advance through the procedure")
            if command.kind not in ("end", "else") and command.next not in addresses | {
                self.end
            }:
                raise ValueError("tracking command has no continuation")


@dataclass(frozen=True)
class RoomProgram:
    procedures: tuple[RuleProcedure, ...]
    coverage_complete: bool
    item_slots: tuple[int, ...]
    door_slots: tuple[int, ...]
    mutable_slots: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.coverage_complete) is not bool:
            raise ValueError("tracking coverage requires an explicit boolean")
        for slots in (self.item_slots, self.door_slots, self.mutable_slots):
            if len(set(slots)) != len(slots) or any(
                type(slot) is not int or not 0 <= slot < 24 for slot in slots
            ):
                raise ValueError("invalid tracking program slots")
        occupied = set()
        last_end = 0
        for procedure in self.procedures:
            if procedure.start < last_end:
                raise ValueError("tracking procedures overlap or run out of order")
            last_end = procedure.end
            for command in procedure.commands:
                if command.offset in occupied:
                    raise ValueError("tracking procedures overlap")
                occupied.add(command.offset)

    @staticmethod
    def load(raw: dict) -> RoomProgram:
        return RoomProgram(
            tuple(
                RuleProcedure(
                    row["start"],
                    row["end"],
                    tuple(
                        RuleCommand(
                            command["offset"],
                            command["next"],
                            command["kind"],
                            tuple(command["args"]),
                        )
                        for command in row["commands"]
                    ),
                )
                for row in raw["procedures"]
            ),
            raw["coverage_complete"],
            tuple(raw["item_slots"]),
            tuple(raw["door_slots"]),
            tuple(raw["mutable_slots"]),
        )


@dataclass(frozen=True)
class TrackingRuleLayout:
    flag_bases: tuple[int, ...]
    persistent_flag_groups: tuple[int, ...]
    persistent_flag_bits: tuple[tuple[int, int], ...]
    character_address: int
    source_selection_masks: tuple[tuple[int, int], ...]
    variant_address: int
    variant_mask: int
    alternate_address: int
    alternate_mask: int

    def __post_init__(self) -> None:
        if len(self.flag_bases) != 10 or any(
            base % 4 or not 0x80000000 <= base <= 0x801FFFE0 for base in self.flag_bases
        ):
            raise ValueError("tracking rules require ten bounded flag banks")
        if len(set(self.persistent_flag_groups)) != len(
            self.persistent_flag_groups
        ) or any(not 0 <= group < 10 for group in self.persistent_flag_groups):
            raise ValueError("invalid persistent flag groups")
        if any(
            not 0 <= group < 10 or not 0 <= index <= 255
            for group, index in self.persistent_flag_bits
        ):
            raise ValueError("invalid persistent flag bits")
        if not 0x80000000 <= self.character_address < 0x80200000:
            raise ValueError("tracking character address is outside PS1 RAM")
        if not self.source_selection_masks or any(
            not 0x80000000 <= address < 0x80200000 or not 0 < mask <= 255
            for address, mask in self.source_selection_masks
        ):
            raise ValueError("tracking source selection requires bounded byte masks")
        if any(
            (address, mask) not in self.source_selection_masks
            for address, mask in (
                (self.variant_address, self.variant_mask),
                (self.alternate_address, self.alternate_mask),
            )
        ):
            raise ValueError("room file selectors must belong to the source context")

    def flag(self, group: int, index: int) -> tuple[int, int]:
        assert 0 <= group < 10 and 0 <= index <= 255
        return self.flag_bases[group] + 4 * (index // 32) + 3 - (
            index % 32
        ) // 8, 128 >> (index % 8)


@dataclass(frozen=True)
class RuleSnapshot:
    values: tuple[tuple[int, int], ...]
    error: str


def read_rule_snapshot(
    layout: TrackingRuleLayout,
    programs: tuple[RoomProgram, ...],
    read_memory: Callable[[int, int], MemoryResult],
) -> RuleSnapshot:
    addresses = {layout.character_address} | {
        address for address, _ in layout.source_selection_masks
    }
    for program in programs:
        for procedure in program.procedures:
            for command in procedure.commands:
                if command.kind in ("flag-test", "flag-write"):
                    group, index, _ = command.args
                    if (
                        group in layout.persistent_flag_groups
                        or (group, index) in layout.persistent_flag_bits
                    ):
                        addresses.add(layout.flag(group, index)[0])
    values = []
    for address in sorted(addresses):
        result = read_memory(address, 1)
        if not result.ok or len(result.data) != 1:
            return RuleSnapshot(
                (), f"room rule state: {result.error or 'short read'} at {address:#x}"
            )
        values.append((address, result.data[0]))
    return RuleSnapshot(tuple(values), "")


@dataclass(frozen=True)
class RuleEvaluation:
    items: RuntimeRoomItems
    doors: tuple[tuple[int, bytes], ...]
    unresolved_item_slots: tuple[int, ...]
    unresolved_door_slots: tuple[int, ...]


def evaluate_room_program(
    program: RoomProgram,
    room: RoomId,
    layout: TrackingRuleLayout,
    snapshot: RuleSnapshot,
    flags: bytes,
    item_labels: tuple[tuple[int, str], ...],
) -> RuleEvaluation:
    assert not snapshot.error, "failed rule reads must not reach interpretation"
    values = dict(snapshot.values)
    # Slots contain semantic creator operands and the latest AOT handler/mode.
    paths = [((), ())]
    bounded = True
    for procedure in program.procedures:
        commands = {command.offset: command for command in procedure.commands}
        pending = [(procedure.start, (), slots, writes) for slots, writes in paths]
        finished = set()
        seen = set()
        while pending:
            pc, stack, slots, writes = pending.pop()
            state = (pc, stack, slots, writes)
            if state in seen:
                continue
            seen.add(state)
            # These are analysis budgets, not claimed native stack capacities.
            # A malformed or branching source must not stall live polling.
            if len(seen) > 4096 or len(stack) > 16:
                bounded = False
                break
            if pc == procedure.end:
                finished.add((slots, writes))
                continue
            command = commands[pc]
            kind, args = command.kind, command.args
            if kind == "end":
                finished.add((slots, writes))
                continue
            if kind == "if":
                pending.append((command.next, stack + (args[0],), slots, writes))
                continue
            if kind in ("else", "endif"):
                if not stack:
                    bounded = False
                    break
                pending.append(
                    (
                        args[0] if kind == "else" else command.next,
                        stack[:-1],
                        slots,
                        writes,
                    )
                )
                continue
            predicate = True
            if kind == "uncertain-test":
                # Unclassified handlers may return zero to the native runner.
                # Explore failure as well as continuation instead of assuming a no-op.
                predicate = None
            elif kind == "flag-test":
                group, index, expected = args
                bit = None
                if group < len(layout.flag_bases):
                    address, mask = layout.flag(group, index)
                    bit = dict(writes).get((address, mask))
                    if (address, mask) not in dict(writes) and (
                        group in layout.persistent_flag_groups
                        or (group, index) in layout.persistent_flag_bits
                    ):
                        bit = bool(values[address] & mask)
                predicate = (
                    bit != bool(expected)
                    if bit is not None and expected in (0, 1)
                    else None
                )
            elif kind == "byte-test":
                index, comparison, expected = args
                actual = {
                    0: room.stage,
                    1: room.room,
                    9: values[layout.character_address],
                }.get(index)
                predicate = (
                    None
                    if actual is None or comparison > 5
                    else (
                        actual == expected,
                        actual > expected,
                        actual >= expected,
                        actual < expected,
                        actual <= expected,
                        actual != expected,
                    )[comparison]
                )
            elif kind == "flag-write":
                group, index, operation = args
                if group >= len(layout.flag_bases):
                    predicate = None
                else:
                    address, mask = layout.flag(group, index)
                    old = dict(writes).get((address, mask))
                    if (address, mask) not in dict(writes) and (
                        group in layout.persistent_flag_groups
                        or (group, index) in layout.persistent_flag_bits
                    ):
                        old = bool(values[address] & mask)
                    changed = dict(writes)
                    # Flag banks overlap in the saved block. Physical bits must
                    # share a shadow value even when accessed through different banks.
                    changed[address, mask] = (
                        True
                        if operation == 0
                        else False
                        if operation == 1
                        else not old
                        if operation == 2 and old is not None
                        else None
                    )
                    writes = tuple(sorted(changed.items()))
            elif kind in ("item", "door", "aot-create", "aot-handler"):
                changed = dict(slots)
                if kind == "item":
                    changed[args[0]] = (
                        kind,
                        args,
                        15 if args[1] >= 0x4E else 4,
                        args[4],
                    )
                elif kind == "door":
                    changed[args[0]] = (kind, args, 1, args[9])
                elif kind == "aot-create":
                    changed[args[0]] = (kind, args, args[1], args[2])
                elif args[0] in changed:
                    creator, fields, _, _ = changed[args[0]]
                    changed[args[0]] = (creator, fields, args[1], args[2])
                slots = tuple(sorted(changed.items()))
            if predicate is not True:
                if stack:
                    pending.append((stack[-1], stack[:-1], slots, writes))
                else:
                    finished.add((slots, writes))
            if predicate is not False:
                pending.append((command.next, stack, slots, writes))
        if not bounded:
            break
        paths = list(finished)
    uncertain_items, uncertain_doors = set(), set()
    items, doors = [], []
    labels = dict(item_labels)
    for slot in sorted(set(program.item_slots) | set(program.door_slots)):
        choices = {dict(slots).get(slot) for slots, _ in paths}
        if (
            not bounded
            or not program.coverage_complete
            or slot in program.mutable_slots
            or len(choices) != 1
        ):
            if slot in program.item_slots:
                uncertain_items.add(slot)
            if slot in program.door_slots:
                uncertain_doors.add(slot)
            continue
        descriptor = choices.pop()
        if descriptor is None:
            continue
        creator, args, handler, mode = descriptor
        if creator == "item":
            _, item_type, amount, gid, _ = args
            if item_type == 0 or item_type >= 0x54:
                continue  # Documents do not count as normal collectibles.
            if item_type == 0x4D or handler not in (0, 3, 4, 15):
                uncertain_items.add(slot)
                continue
            index = 4 * (gid // 32) + 3 - (gid % 32) // 8
            assert index < len(flags), "validated item GlobalId must fit the flag block"
            remaining = bool(flags[index] & (128 >> (gid % 8)))
            state = (
                RuntimeItemState.Taken
                if not remaining
                else RuntimeItemState.Available
                if handler in (4, 15)
                else RuntimeItemState.Unavailable
            )
            items.append(
                # Reconstructed descriptors have no live PS1 source pointer.
                # Zero stays internal; only observed AOTs authorize memory reads.
                RuntimeRoomItem(
                    slot,
                    item_type,
                    amount,
                    labels.get(item_type, ""),
                    gid,
                    state,
                    RuntimeItemKind.Map
                    if item_type >= 0x4E
                    else RuntimeItemKind.Inventory,
                    0,
                    0x18,
                )
            )
        elif creator == "door" and handler == 1:
            _, x, z, width, depth, animation, lock, target, key, _ = args
            raw = bytearray(26)
            raw[:2] = bytes((0x0C, slot))
            struct.pack_into("<hhHH", raw, 2, x, z, width, depth)
            raw[12], raw[14], raw[15], raw[24], raw[25] = (
                animation,
                lock,
                target,
                key,
                mode,
            )
            doors.append((slot, bytes(raw)))
        elif creator == "aot-create" and handler in (1, 3, 4, 15):
            if slot in program.item_slots:
                uncertain_items.add(slot)
            if slot in program.door_slots:
                uncertain_doors.add(slot)
        elif creator == "door":
            # A changed handler can expose another scripted interaction.
            # Its physical access has no implemented door rule yet.
            uncertain_doors.add(slot)
    reason = "" if not uncertain_items else "Some item conditions need a room visit."
    if not bounded or not program.coverage_complete:
        reason = "Room script coverage is incomplete."
    return RuleEvaluation(
        RuntimeRoomItems(
            ok=True,
            items=tuple(items),
            list_complete=not reason,
            coverage_reason=reason,
        ),
        tuple(doors),
        tuple(sorted(uncertain_items)),
        tuple(sorted(uncertain_doors)),
    )
