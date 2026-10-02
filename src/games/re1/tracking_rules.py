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
            "word-test": 3,
            "constant-test": 1,
            "unsupported-effect": 0,
            "quantity-transfer": 3,
            "camera-change": 1,
            "player-control": 1,
            "item": 5,
            "door": 10,
            "aot-create": 3,
            "aot-handler": 3,
            "award": 3,
            "aot-callback": 3,
            "inventory-remove": 1,
            "uncertain-test": 0,
        }
        if (
            self.kind not in counts
            and self.kind
            not in ("variable-write", "local-flag-forget", "local-flag-clear")
            or self.kind in counts
            and len(self.args) != counts[self.kind]
            or not 0 <= self.offset < self.next
        ):
            raise ValueError("invalid tracking rule command")
        if any(type(value) is not int for value in self.args):
            raise ValueError("tracking rule operands must be integers")
        if self.kind in ("flag-test", "flag-write", "byte-test") and any(
            not 0 <= value <= 255 for value in self.args
        ):
            raise ValueError("tracking rule operand exceeds one byte")
        if self.kind == "constant-test" and self.args[0] not in (0, 1):
            raise ValueError("invalid constant command result")
        if self.kind == "camera-change" and self.args[0] not in (0, 1):
            raise ValueError("invalid camera change")
        if self.kind == "player-control" and not 0 <= self.args[0] <= 255:
            raise ValueError("invalid player control")
        if self.kind == "word-test" and (
            not all(0 <= value <= 255 for value in self.args[:2])
            or not 0 <= self.args[2] <= 65535
        ):
            raise ValueError("invalid word predicate")
        if self.kind == "variable-write" and (
            not self.args
            or len(self.args) % 3
            or any(
                width not in (1, 2)
                or not 0 <= index <= 255
                or not 0 <= value < 1 << (8 * width)
                for width, index, value in zip(
                    self.args[::3], self.args[1::3], self.args[2::3]
                )
            )
        ):
            raise ValueError("invalid variable writes")
        if self.kind in ("local-flag-forget", "local-flag-clear") and (
            not self.args
            or len(self.args) % 3
            or any(
                group not in (4, 6, 9) or not 0 <= first < first + count <= 256
                for group, first, count in zip(
                    self.args[::3], self.args[1::3], self.args[2::3]
                )
            )
        ):
            raise ValueError("invalid local flag effects")
        if self.kind == "quantity-transfer" and (
            any(not 0 <= value <= 255 for value in self.args)
            or self.args[0] not in (0, 1, 2)
            or self.args[1] >= 24
        ):
            raise ValueError("invalid quantity transfer")
        if (
            self.kind
            in ("item", "aot-create", "aot-handler", "door", "award", "aot-callback")
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
        if self.kind == "award" and (
            self.args[1] not in (4, 15) or self.args[2] not in (0, 1)
        ):
            raise ValueError("invalid tracking award handler")
        if self.kind == "aot-callback" and (
            self.args[1] != 13 or self.args[2] not in (0, 1)
        ):
            raise ValueError("invalid tracking callback handler")
        if self.kind == "inventory-remove" and not 0 <= self.args[0] <= 255:
            raise ValueError("invalid inventory removal type")


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
    main_procedures: tuple[RuleProcedure, ...]
    event_effects: tuple[RuleCommand, ...]
    award_slots: tuple[int, ...]
    coverage_complete: bool
    item_slots: tuple[int, ...]
    door_slots: tuple[int, ...]
    mutable_slots: tuple[int, ...]

    def __post_init__(self) -> None:
        if type(self.coverage_complete) is not bool:
            raise ValueError("tracking coverage requires an explicit boolean")
        for slots in (
            self.item_slots,
            self.door_slots,
            self.mutable_slots,
            self.award_slots,
        ):
            if len(set(slots)) != len(slots) or any(
                type(slot) is not int or not 0 <= slot < 24 for slot in slots
            ):
                raise ValueError("invalid tracking program slots")
        occupied = set()
        last_end = 0
        for procedure in self.procedures + self.main_procedures:
            if procedure.start < last_end:
                raise ValueError("tracking procedures overlap or run out of order")
            last_end = procedure.end
            for command in procedure.commands:
                if command.offset in occupied:
                    raise ValueError("tracking procedures overlap")
                occupied.add(command.offset)
        if any(
            command.kind not in ("item", "door", "aot-create", "aot-handler")
            for command in self.event_effects
        ) or len({command.offset for command in self.event_effects}) != len(
            self.event_effects
        ):
            raise ValueError("invalid tracking event effects")

    @staticmethod
    def load(raw: dict) -> RoomProgram:
        def procedures(section: str) -> tuple[RuleProcedure, ...]:
            return tuple(
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
                for row in raw[section]
            )

        return RoomProgram(
            procedures("procedures"),
            procedures("main_procedures"),
            tuple(
                RuleCommand(
                    command["offset"],
                    command["next"],
                    command["kind"],
                    tuple(command["args"]),
                )
                for command in raw["event_effects"]
            ),
            tuple(raw["award_slots"]),
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
    byte_variables_base: int
    word_variables_base: int

    def __post_init__(self) -> None:
        if (
            not 0x80000000 <= self.byte_variables_base <= 0x801FFF00
            or not 0x80000000 <= self.word_variables_base <= 0x801FFE00
            or self.word_variables_base % 2
            or self.character_address != self.byte_variables_base + 9
        ):
            raise ValueError(
                "tracking variables require bounded PS1 banks and character offset"
            )
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
        for procedure in program.procedures + program.main_procedures:
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
    disabled_doors: tuple[tuple[int, bytes], ...]
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

    def update_descriptor(descriptor, kind, args):
        if kind == "item":
            return kind, args, 15 if args[1] >= 0x4E else 4, args[4]
        if kind == "door":
            return kind, args, 1, args[9]
        if kind == "aot-create":
            return kind, args, args[1], args[2]
        assert kind == "aot-handler"
        if descriptor is None:
            return None  # Setters preserve pointers and cannot create an absent descriptor.
        creator, fields, _, _ = descriptor
        return creator, fields, args[1], args[2]

    def closure(choices, effects):
        choices = set(choices)
        pending = list(choices)
        while pending:
            descriptor = pending.pop()
            for command in effects:
                changed = update_descriptor(descriptor, command.kind, command.args)
                if changed not in choices:
                    choices.add(changed)
                    pending.append(changed)
            # Event order and repetition are unknown. Bound the per-slot closure
            # instead of selecting a last writer or blocking unrelated slots.
            if len(choices) > 256:
                return frozenset(choices), True
        return frozenset(choices), False

    history_unresolved = set()
    for index, procedure in enumerate(program.procedures + program.main_procedures):
        if index == len(program.procedures):
            # Current RAM already reflects completed initialization. Main tests
            # must use that snapshot rather than repeat init's shadow flag writes.
            # Scalar variables can also change during prior main/event ticks;
            # their initializer shadows are not proof of their current values.
            # Main setters can retain an earlier effect after its guard becomes
            # false. Include those histories before applying current main rules.
            effects = program.event_effects + tuple(
                command
                for block in program.main_procedures
                for command in block.commands
                if command.kind in ("item", "door", "aot-create", "aot-handler")
            )
            historical = []
            for slots, _ in paths:
                changed = dict(slots)
                for slot in set(program.item_slots) | set(program.door_slots):
                    choices, exceeded = closure(
                        changed.get(slot, frozenset({None})),
                        [command for command in effects if command.args[0] == slot],
                    )
                    changed[slot] = choices
                    if exceeded:
                        history_unresolved.add(slot)
                historical.append((tuple(sorted(changed.items())), ()))
            paths = historical
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
            elif kind == "unsupported-effect":
                # A return guess cannot account for unaudited writes or a
                # handler that fails to advance its PC. Reject reconstruction.
                bounded = False
                break
            elif kind == "constant-test":
                predicate = bool(args[0])
            elif kind in ("local-flag-forget", "local-flag-clear"):
                changed = dict(writes)
                for group, first, count in zip(
                    args[::3], args[1::3], args[2::3], strict=True
                ):
                    for index in range(first, first + count):
                        # Forget unresolved native values even after a shadow
                        # write; a proven clear instead establishes false.
                        changed[layout.flag(group, index)] = (
                            False if kind == "local-flag-clear" else None
                        )
                writes = tuple(sorted(changed.items()))
            elif kind == "inventory-remove":
                # A prior room's inventory is unavailable. Native removal
                # returns zero if absent and one if found, then compacts it.
                # Compaction can change count byte 7 and selection byte 41.
                # Forgetting both on either outcome conservatively covers that
                # conditional write without inventing past inventory contents.
                predicate = None
                changed = dict(writes)
                for index in (7, 41):
                    for bit in range(8):
                        changed[layout.byte_variables_base + index, 1 << bit] = None
                writes = tuple(sorted(changed.items()))
            elif kind == "player-control":
                changed = dict(writes)
                for bit in range(8):
                    # The native control setter clears low bits 0/1, then ORs
                    # its byte operand into C3000. Preserve untouched higher bits.
                    if bit < 2 or args[0] & (1 << bit):
                        changed[layout.flag(5, 31 - bit)] = bool(args[0] & (1 << bit))
                for index in range(160, 256):
                    # Model copying/allocation changes CAB14/CAB1C pointers.
                    # Their local flag aliases cannot retain an earlier shadow.
                    changed[layout.flag(6, index)] = None
                writes = tuple(sorted(changed.items()))
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
            elif kind in ("byte-test", "word-test"):
                index, comparison, expected = args
                actual = None
                shadow = dict(writes)
                if kind == "byte-test" and index in (0, 1, 9):
                    actual = {
                        0: room.stage,
                        1: room.room,
                        9: values[layout.character_address],
                    }[index]
                    address = layout.byte_variables_base + index
                    for bit in range(8):
                        if (address, 1 << bit) in shadow:
                            value = shadow[address, 1 << bit]
                            if value is None:
                                actual = None
                                break
                            actual = actual & ~(1 << bit) | int(value) << bit
                elif kind == "word-test" and index < 16:
                    # Only fully written scalar words can be reconstructed.
                    # Higher indices overlap other saved structures and room-local data.
                    address = layout.word_variables_base + 2 * index
                    bits = [
                        shadow.get((address + bit // 8, 1 << (bit % 8)))
                        for bit in range(16)
                    ]
                    if all(bit is not None for bit in bits):
                        actual = sum(
                            int(value) << bit for bit, value in enumerate(bits)
                        )
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
            elif kind in ("flag-write", "camera-change"):
                group, index, operation = (
                    (5, 11, args[0]) if kind == "camera-change" else args
                )
                if group >= len(layout.flag_bases):
                    # An undefined bank can write outside the modeled flag state.
                    # It is an unsupported side effect, not a conditional failure.
                    bounded = False
                    break
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
                if kind == "camera-change":
                    # The camera rebuild calls local scene helpers. Their local
                    # flag results are not reconstructed, so discard older shadows.
                    changed = dict(writes)
                    for local_group in (4, 6, 9):
                        for local_index in range(256):
                            changed[layout.flag(local_group, local_index)] = None
                    writes = tuple(sorted(changed.items()))
            elif kind == "variable-write":
                changed = dict(writes)
                for width, index, value in zip(
                    args[::3], args[1::3], args[2::3], strict=True
                ):
                    base = (
                        layout.byte_variables_base
                        if width == 1
                        else layout.word_variables_base
                    )
                    address = base + width * index
                    for bit in range(8 * width):
                        # Use physical bits so variable writes and overlapping
                        # flag-bank writes share one shadow state. Never write RAM.
                        changed[address + bit // 8, 1 << (bit % 8)] = bool(
                            value & (1 << bit)
                        )
                writes = tuple(sorted(changed.items()))
            elif kind == "quantity-transfer" and args[0] in (0, 2):
                changed = dict(writes)
                address = layout.byte_variables_base + args[2]
                for bit in range(8):
                    # These copies read live source/inventory quantities that
                    # cannot be reconstructed. Forget a preceding scalar write.
                    changed[address, 1 << bit] = None
                writes = tuple(sorted(changed.items()))
            elif kind in ("item", "door", "aot-create", "aot-handler"):
                changed = dict(slots)
                changed[args[0]] = frozenset(
                    update_descriptor(descriptor, kind, args)
                    for descriptor in changed.get(args[0], frozenset({None}))
                )
                slots = tuple(sorted(changed.items()))
            elif kind in ("award", "aot-callback"):
                # Completed inventory/map awards clear the acquisition bit.
                # Read the completed result from RAM; do not grant an item by replaying a script.
                # Opcode 24 returns one, while 2D returns zero to the IF runner.
                predicate = bool(args[2])
                changed = dict(writes)
                if args[1] == 13:
                    # Callback 13 sets C3000 bit 8 only for a zero registry
                    # parameter. That field is not modeled; a prior true bit
                    # remains true, otherwise either result is possible.
                    address = layout.flag(5, 23)
                    changed[address] = True if changed.get(address) is True else None
                elif args[1] == 4:
                    # The pending bit depends on the registry parameter, which
                    # setters can change independently of mode. A conditional
                    # OR cannot erase an already established true bit.
                    address = layout.flag(5, 20)
                    changed[address] = True if changed.get(address) is True else None
                else:
                    assert args[1] == 15
                    # The immediate map callback changes byte variable 19.
                    # Its acquisition result still comes from the fresh flags.
                    for bit in range(8):
                        changed[layout.byte_variables_base + 19, 1 << bit] = None
                    # The forced callback uses its source even if the current
                    # handler is disabled. Require supported map descriptors
                    # before interpreting any source-dependent writes.
                    for descriptor in dict(slots).get(args[0], frozenset({None})):
                        if (
                            descriptor is None
                            or descriptor[0] != "item"
                            or not 0x4E <= descriptor[1][1] < 0x54
                        ):
                            bounded = False
                            break
                        _, item_type, _, gid, _ = descriptor[1]
                        # Read actual acquisition/ownership from fresh RAM;
                        # discard older shadows only at the possible targets.
                        changed[layout.flag(7, gid)] = None
                        changed[layout.flag(8, item_type - 0x4E + 124)] = None
                    if not bounded:
                        break
                if not predicate:
                    # 2D sets pending bit 10 and toggles bit 11 after dispatch,
                    # even when its zero return skips the surrounding IF body.
                    changed[layout.flag(5, 21)] = True
                    address = layout.flag(5, 20)
                    old = changed.get(address)
                    changed[address] = None if old is None else not old
                writes = tuple(sorted(changed.items()))
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
    items, doors, disabled_doors = [], [], []
    labels = dict(item_labels)

    def interpret_descriptor(descriptor):
        if descriptor is None:
            return "absent", None
        creator, args, handler, mode = descriptor
        slot = args[0]
        if creator == "item":
            _, item_type, amount, gid, _ = args
            if item_type == 0 or item_type >= 0x54:
                return "absent", None  # Documents are excluded from room completion.
            if (
                item_type == 0x4D
                or handler not in (0, 3, 4, 15)
                or handler == 4
                and item_type >= 0x4E
                or handler == 15
                and item_type < 0x4E
            ):
                return "unresolved", None
            index = 4 * (gid // 32) + 3 - (gid % 32) // 8
            assert index < len(flags), "validated item GlobalId must fit the flag block"
            remaining = bool(flags[index] & (128 >> (gid % 8)))
            if remaining and handler in (0, 3) and slot in program.award_slots:
                # A dormant descriptor can still be awarded by an event. Its
                # current availability needs event progress, not just a pickup bit.
                return "unresolved", None
            state = (
                RuntimeItemState.Taken
                if not remaining
                else RuntimeItemState.Available
                if handler in (4, 15)
                else RuntimeItemState.Unavailable
            )
            return (
                "item",
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
                ),
            )
        elif creator == "door" and handler in (0, 1):
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
            return "door" if handler == 1 else "disabled-door", (slot, bytes(raw))
        elif creator == "aot-create" and handler in (1, 3, 4, 15):
            return "unresolved", None
        elif creator == "door":
            # A changed handler can expose another scripted interaction.
            # Its physical access has no implemented door rule yet.
            return "unresolved", None
        return "absent", None

    for slot in sorted(set(program.item_slots) | set(program.door_slots)):
        choices = {
            descriptor
            for slots, _ in paths
            for descriptor in dict(slots).get(slot, frozenset({None}))
        }
        effects = [
            command for command in program.event_effects if command.args[0] == slot
        ]
        choices, exceeded = closure(choices, effects)
        meanings = {interpret_descriptor(descriptor) for descriptor in choices}
        if (
            not bounded
            or not program.coverage_complete
            or slot in program.mutable_slots
            or exceeded
            or slot in history_unresolved
            or len(meanings) != 1
            or ("unresolved", None) in meanings
        ):
            if slot in program.item_slots:
                uncertain_items.add(slot)
            if slot in program.door_slots:
                uncertain_doors.add(slot)
            continue
        kind, value = meanings.pop()
        if kind == "item":
            items.append(value)
        elif kind == "door":
            doors.append(value)
        elif kind == "disabled-door":
            disabled_doors.append(value)
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
        tuple(disabled_doors),
        tuple(sorted(uncertain_items)),
        tuple(sorted(uncertain_doors)),
    )
