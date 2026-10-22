"""Evaluate source-bound RE1 room interactions from fresh game state.

Unknown predicates explore both native IF outcomes. Only interaction states
that agree on every path are published. This is a read-only reconstruction,
not a replay of game side effects or a guess from another room's local bytes.
"""

from __future__ import annotations

import itertools
import struct
from collections.abc import Callable
from dataclasses import dataclass, replace
from enum import Enum
from heapq import heappop, heappush

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re1.acquisition_state import (
    AcquisitionFlag,
    AcquisitionLayout,
    FixedAcquisitionRule,
)
from games.re1.event_state import EventProgram
from games.re1.room_items import (
    MemoryResult,
    RuntimeItemKind,
    RuntimeItemState,
    RuntimeRoomItem,
    RuntimeRoomItems,
)
from games.re1.scripted_collectibles import scripted_collectible_access
from games.re1.scripted_doors import ScriptedDoorAccess, scripted_door_access


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
            "event-start": 2,
            "inventory-remove": 1,
            "display-request": 1,
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
            self.args[1] not in (1, 5, 6, 7, 9, 13) or self.args[2] not in (0, 1)
        ):
            raise ValueError("invalid tracking callback handler")
        if self.kind == "event-start" and any(
            not 0 <= value <= 255 for value in self.args
        ):
            raise ValueError("invalid tracking event start")
        if self.kind == "inventory-remove" and not 0 <= self.args[0] <= 255:
            raise ValueError("invalid inventory removal type")
        if self.kind == "display-request" and not 0 <= self.args[0] <= 255:
            raise ValueError("invalid display request")


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
    event_blocks: tuple[tuple[RuleProcedure, ...], ...]
    event_effects: tuple[RuleCommand, ...]
    award_slots: tuple[int, ...]
    coverage_complete: bool
    reentry_coverage_complete: bool
    item_slots: tuple[int, ...]
    door_slots: tuple[int, ...]
    mutable_slots: tuple[int, ...]
    event_program: EventProgram
    event_commands: tuple[RuleCommand, ...]

    def __post_init__(self) -> None:
        if any(
            type(value) is not bool
            for value in (self.coverage_complete, self.reentry_coverage_complete)
        ):
            raise ValueError("tracking coverage requires an explicit boolean")
        if self.coverage_complete and (
            not self.reentry_coverage_complete or self.event_program.failures
        ):
            raise ValueError(
                "complete current coverage requires complete event decoding"
            )
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
            and not (command.kind == "quantity-transfer" and command.args[0] in (1, 2))
            for command in self.event_effects
        ) or len({command.offset for command in self.event_effects}) != len(
            self.event_effects
        ):
            raise ValueError("invalid tracking event effects")
        # Separate dispatches can reach shared bytes. Validate each list's
        # order; cross-list source order does not establish execution order.
        for block in self.event_blocks:
            last_end = 0
            for procedure in block:
                if procedure.start < last_end or any(
                    command.offset in occupied for command in procedure.commands
                ):
                    raise ValueError(
                        "event block overlaps initialization or runs out of order"
                    )
                last_end = procedure.end
        if len({command.offset for command in self.event_commands}) != len(
            self.event_commands
        ) or any(command.offset in occupied for command in self.event_commands):
            raise ValueError("invalid standalone event commands")
        if self.reentry_coverage_complete:
            semantic_commands = {
                command.offset: command
                for procedure in self.procedures + self.main_procedures
                for command in procedure.commands
            }
            event_commands = {
                command.offset: command for command in self.event_commands
            } | {
                command.offset: command
                for block in self.event_blocks
                for procedure in block
                for command in procedure.commands
            }
            if any(
                offset not in event_commands
                for dispatch in self.event_program.dispatches
                for offset in dispatch.commands
            ):
                raise ValueError("event dispatch lacks semantic commands")
            semantic_commands.update(event_commands)
            if any(
                offset not in semantic_commands
                or semantic_commands[offset].kind not in ("aot-create", "aot-handler")
                or semantic_commands[offset].args[0] != slot
                for offset, slot, _, _, _ in self.event_program.registry_writes
            ):
                raise ValueError("registry parameter writer lacks its semantic slot")
        if self.event_program.door_rules or self.event_program.collectible_rules:
            commands = {
                command.offset: command
                for block in self.event_blocks
                for procedure in block
                for command in procedure.commands
            } | {command.offset: command for command in self.event_commands}
            for rule in self.event_program.door_rules:
                offsets = {
                    offset
                    for dispatch in self.event_program.dispatches
                    if dispatch.entry == rule.entry
                    for offset in dispatch.commands
                }
                if not offsets <= commands.keys():
                    raise ValueError("scripted door rule lacks semantic commands")
                owned = tuple(commands[offset] for offset in sorted(offsets))
                if (
                    tuple(
                        command.args[0]
                        for command in owned
                        if command.kind == "aot-callback"
                    )
                    != rule.door_slots
                    or any(command.kind == "variable-write" for command in owned)
                    != rule.changes_character
                    or any(
                        not (
                            command.kind in ("end", "if", "endif")
                            or command.kind == "byte-test"
                            and command.args in ((5, 0, 0), (5, 2, 128))
                            or command.kind == "variable-write"
                            and len(command.args) == 3
                            and command.args[:2] == (1, 9)
                            or command.kind == "aot-callback"
                            and command.args[1:] == (1, 1)
                            or command.kind == "constant-test"
                            and command.args == (1,)
                            or command.kind == "local-flag-forget"
                            and command.args == (6, 16, 16)
                            or command.kind == "flag-write"
                            and command.args in ((6, 23, 0), (6, 23, 1))
                        )
                        for command in owned
                    )
                ):
                    raise ValueError("scripted door rule disagrees with its effects")
            writes = {row[0]: row[1:] for row in self.event_program.registry_writes}
            for rule in self.event_program.collectible_rules:
                for index, stage in enumerate(rule.stages):
                    offsets = {
                        offset
                        for dispatch in self.event_program.dispatches
                        if dispatch.entry == stage.entry
                        for offset in dispatch.commands
                    }
                    if not offsets <= commands.keys():
                        raise ValueError("scripted collectible lacks semantic commands")
                    owned = tuple(commands[offset] for offset in sorted(offsets))
                    awards = tuple(c.args for c in owned if c.kind == "award")
                    starts = tuple(
                        (c.offset, *c.args) for c in owned if c.kind == "event-start"
                    )
                    if (
                        awards
                        != (
                            ((rule.slot, rule.handler, 1),)
                            if index == len(rule.stages) - 1
                            else ()
                        )
                        or starts != stage.starts
                        or any(
                            not (
                                c.kind in ("end", "if", "endif", "award", "event-start")
                                or c.kind == "aot-handler"
                                and index == len(rule.stages) - 1
                                and c.args == (rule.slot, rule.handler, 129)
                                and writes.get(c.offset) == (rule.slot, 0, 0, 0)
                                or c.kind == "byte-test"
                                and c.args in ((5, 0, 0), (5, 2, 128))
                                or c.kind == "constant-test"
                                and c.args == (1,)
                                or c.kind == "local-flag-forget"
                                and c.args == (6, 16, 16)
                                or c.kind == "flag-write"
                                and c.args in ((6, 23, 0), (6, 23, 1))
                            )
                            for c in owned
                        )
                    ):
                        raise ValueError(
                            "scripted collectible rule disagrees with its effects"
                        )

    @staticmethod
    def load(raw: dict) -> RoomProgram:
        def procedures(rows: list[dict]) -> tuple[RuleProcedure, ...]:
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
                for row in rows
            )

        return RoomProgram(
            procedures(raw["procedures"]),
            procedures(raw["main_procedures"]),
            tuple(procedures(block) for block in raw["event_blocks"]),
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
            raw["reentry_coverage_complete"],
            tuple(raw["item_slots"]),
            tuple(raw["door_slots"]),
            tuple(raw["mutable_slots"]),
            EventProgram.load(raw["event_program"]),
            tuple(
                RuleCommand(c["offset"], c["next"], c["kind"], tuple(c["args"]))
                for c in raw["event_commands"]
            ),
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
    room_entry_flag_clears: tuple[tuple[int, int, int], ...]
    acquisition: AcquisitionLayout

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
        if self.acquisition.flags_address != self.flag_bases[7]:
            raise ValueError("acquisition rules disagree with the script flag bank")
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
        cleared = set()
        for group, first, count in self.room_entry_flag_clears:
            if (
                any(type(value) is not int for value in (group, first, count))
                or group not in (4, 6, 9)
                or not 0 <= first < first + count <= 256
            ):
                raise ValueError("invalid room entry flag clear")
            bits = {self.flag(group, index) for index in range(first, first + count)}
            if bits & cleared:
                raise ValueError("overlapping room entry flag clears")
            cleared.update(bits)
        persistent = {
            self.flag(group, index)
            for group in self.persistent_flag_groups
            for index in range(256)
        } | {self.flag(*bit) for bit in self.persistent_flag_bits}
        if cleared & persistent or any(
            mask & selector_mask
            for address, mask in cleared
            for selector_address, selector_mask in self.source_selection_masks
            if address == selector_address
        ):
            raise ValueError("room entry reset overlaps persistent state")

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
    addresses = (
        {layout.character_address}
        | {address for address, _ in layout.source_selection_masks}
        | {
            rule.address
            for rule in layout.acquisition.rules
            if isinstance(rule, FixedAcquisitionRule)
        }
    )
    for program in programs:
        commands = program.event_commands + tuple(
            command
            for procedure in program.procedures
            + program.main_procedures
            + tuple(p for block in program.event_blocks for p in block)
            for command in procedure.commands
        )
        if any(c.kind == "aot-callback" and c.args[1] == 7 for c in commands):
            for _, _, group, index, _ in program.event_program.registry_writes:
                # Callback 7 uses a fixed word for control/dialog banks. Other
                # banks use the full u16 index; reject unbounded targets later.
                if group in (5, 6):
                    index &= 31
                if (
                    group < 10
                    and index <= 255
                    and (
                        group in layout.persistent_flag_groups
                        or (group, index) in layout.persistent_flag_bits
                    )
                ):
                    addresses.add(layout.flag(group, index)[0])
        for command in commands:
            if (
                command.kind == "aot-callback"
                and command.args[1] == 1
                and 2 in layout.persistent_flag_groups
            ):
                # A source variant can choose any six-bit lock index.
                # Read its eight bytes so a known true unlock survives a
                # conditional native OR and participates in the recheck.
                addresses.update(layout.flag_bases[2] + i for i in range(8))
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
    collection_items: RuntimeRoomItems
    doors: tuple[tuple[int, bytes], ...]
    disabled_doors: tuple[tuple[int, bytes], ...]
    unresolved_item_slots: tuple[int, ...]
    unresolved_collection_slots: tuple[int, ...]
    unresolved_door_slots: tuple[int, ...]
    coverage_complete: bool


@dataclass(frozen=True)
class CachedReentryEvaluation:
    program: RoomProgram
    room: RoomId
    layout: TrackingRuleLayout
    snapshot: RuleSnapshot
    flags: bytes
    item_labels: tuple[tuple[int, str], ...]
    result: RuleEvaluation


class RoomRuleEpoch(Enum):
    Current = "current"
    Reentry = "reentry"


class RegistryParameterState(Enum):
    Unreconstructed = "unreconstructed"


def evaluate_room_program(
    program: RoomProgram,
    room: RoomId,
    layout: TrackingRuleLayout,
    snapshot: RuleSnapshot,
    flags: bytes,
    item_labels: tuple[tuple[int, str], ...],
    epoch: RoomRuleEpoch = RoomRuleEpoch.Current,
) -> RuleEvaluation:
    assert not snapshot.error, "failed rule reads must not reach interpretation"
    assert isinstance(epoch, RoomRuleEpoch)
    values = dict(snapshot.values)
    # Slots contain semantic creator operands and the latest AOT handler/mode.
    paths = [((), ())]
    bounded = True
    reentry = epoch == RoomRuleEpoch.Reentry
    source_complete = (
        program.reentry_coverage_complete if reentry else program.coverage_complete
    )
    failed_entries = {failure.entry for failure in program.event_program.failures}
    started = set()
    registry_parameters = {
        offset: (parameter, model, operation)
        for offset, _, parameter, model, operation in program.event_program.registry_writes
    }
    all_commands = (
        tuple(
            c
            for procedure in program.procedures + program.main_procedures
            for c in procedure.commands
        )
        + tuple(c for block in program.event_blocks for p in block for c in p.commands)
        + program.event_commands
    )
    quantity_slots = {
        command.args[1]
        for command in all_commands
        if command.kind == "quantity-transfer" and command.args[0] in (1, 2)
    }
    descriptor_inputs = tuple(
        sorted(
            {
                command.args[1]
                for command in all_commands
                if command.kind == "quantity-transfer" and command.args[0] == 0
            }
            | {
                command.args[0]
                for command in all_commands
                if command.kind in ("award", "aot-callback")
                and command.args[1] in (1, 7, 15)
            }
        )
    )
    required_shadow_bits = set()
    for command in all_commands:
        if command.kind == "item":
            # RE1-COVER-002: creator activation still uses the GlobalId bit,
            # even when collection is recorded in a separate flag bank.
            required_shadow_bits.add(layout.flag(7, command.args[3]))
        if command.kind == "flag-test":
            group, index, _ = command.args
            if group < len(layout.flag_bases):
                required_shadow_bits.add(layout.flag(group, index))
        elif command.kind in ("byte-test", "word-test") or (
            command.kind == "quantity-transfer" and command.args[0] == 1
        ):
            width = 2 if command.kind == "word-test" else 1
            index = command.args[2 if command.kind == "quantity-transfer" else 0]
            base = (
                layout.word_variables_base if width == 2 else layout.byte_variables_base
            )
            required_shadow_bits.update(
                (base + width * index + bit // 8, 1 << (bit % 8))
                for bit in range(8 * width)
            )
    history_unresolved = set()
    persistent = {
        layout.flag(group, index)
        for group in layout.persistent_flag_groups
        for index in range(256)
    } | {layout.flag(*bit) for bit in layout.persistent_flag_bits}

    def targets_slot(command, slot):
        return command.args[1 if command.kind == "quantity-transfer" else 0] == slot

    init_offsets = {c.offset for p in program.procedures for c in p.commands}
    later_slot_commands = tuple(
        c
        for c in all_commands + program.event_effects
        if c.offset not in init_offsets
        and c.kind
        in (
            "item",
            "door",
            "aot-create",
            "aot-handler",
            "award",
            "aot-callback",
            "quantity-transfer",
        )
    )
    later_collection_slots = {
        slot
        for slot in program.item_slots
        if any(targets_slot(c, slot) for c in later_slot_commands)
    }

    def start_interaction(slot, slots):
        descriptors = dict(slots).get(slot, frozenset({None}))
        targets = set()
        for descriptor in descriptors:
            if (
                descriptor is None
                or descriptor[4] == RegistryParameterState.Unreconstructed
            ):
                return False
            _, model, _ = descriptor[4]
            if model & 255 >= len(program.event_program.entries):
                return False
            targets.add(model & 255)
        started.update(targets)
        return True

    def update_descriptor(
        descriptor, command, quantity=ItemQuantityState.Unreconstructed
    ):
        kind, args = command.kind, command.args
        if kind == "quantity-transfer":
            # 4C writes source+9. Only an item creator gives that byte an
            # audited quantity meaning; a door/generic/stale source can differ.
            if descriptor is None or descriptor[0] != "item":
                history_unresolved.add(args[1])
                return descriptor
            return (*descriptor[:5], quantity, descriptor[6])
        # Generic creators and extended setters provide known u16 parameters.
        # Other creators have no reconstructed parameter contract for callback 9.
        parameters = registry_parameters.get(
            command.offset, RegistryParameterState.Unreconstructed
        )
        if kind == "item":
            # A repeated creator reads a possibly mutated source byte. The
            # disc amount cannot reestablish a quantity after a source writer.
            amount = (
                ItemQuantityState.Unreconstructed
                if args[0] in quantity_slots
                else args[2]
            )
            address, mask = layout.flag(7, args[3])
            index = address - layout.acquisition.flags_address
            assert 0 <= index < len(flags), "creator GlobalId must fit its flag block"
            # Acquisition and activation can use different flags. A creator
            # whose ordinary bit is clear registers handler zero, not a pickup.
            handler = (15 if args[1] >= 0x4E else 4) if flags[index] & mask else 0
            return kind, args, handler, args[4], parameters, amount, False
        if kind == "door":
            return (
                kind,
                args,
                1,
                args[9],
                parameters,
                ItemQuantityState.Unreconstructed,
                False,
            )
        if kind == "aot-create":
            return (
                kind,
                args,
                args[1],
                args[2],
                parameters,
                ItemQuantityState.Unreconstructed,
                False,
            )
        assert kind == "aot-handler"
        if descriptor is None:
            return None  # Setters preserve pointers; no modeled creator supplies one.
        creator, fields, _, _, retained_parameters, retained_quantity, _ = descriptor
        return (
            creator,
            fields,
            args[1],
            args[2],
            parameters
            if command.offset in registry_parameters
            else retained_parameters,
            retained_quantity,
            # A zero creator handler can reflect acquisition or puzzle state.
            # Only an explicit setter proves that initialization disabled it.
            args[1] == 0,
        )

    event_updates = tuple(
        (
            block,
            tuple(
                command
                for procedure in block
                for command in procedure.commands
                if command.kind in ("item", "door", "aot-create", "aot-handler")
                or command.kind == "quantity-transfer"
                and command.args[0] in (1, 2)
            ),
        )
        for block in program.event_blocks
    )
    event_outcomes = {}

    def closure(choices, effects, slot):
        choices = set(choices)
        pending = list(choices)
        while pending:
            descriptor = pending.pop()
            outcomes = {update_descriptor(descriptor, c) for c in effects}
            if not reentry:
                for command in effects:
                    if command.kind == "item" and 1 <= command.args[1] <= 0x53:
                        args = command.args
                        activation = AcquisitionFlag(*layout.flag(7, args[3]), False)
                        if layout.acquisition.flag(args[1], args[3]) != activation:
                            # Separate ownership cannot prove the GlobalId bit
                            # that an earlier optional creator observed.
                            created = update_descriptor(descriptor, command)
                            outcomes.update(
                                (*created[:2], handler, *created[3:])
                                for handler in (0, 15 if args[1] >= 0x4E else 4)
                            )
            for block_index, (block, updates) in enumerate(event_updates):
                relevant = tuple(c for c in updates if targets_slot(c, slot))
                if not relevant:
                    continue
                key = (block_index, slot, descriptor)
                if key not in event_outcomes:
                    # Current-room history has unknown earlier guards. Reentry
                    # instead seeds invariants from its bounded entry analysis.
                    # Each block is optional; its ordered writes/tests retain
                    # their relation without selecting an event schedule.
                    states = [
                        (
                            ((slot, frozenset({descriptor})),),
                            reentry_seed if reentry else (),
                        )
                    ]
                    successful = True
                    for procedure in block:
                        successful, states = run_procedure(
                            procedure, states, not reentry
                        )
                        if not successful:
                            break
                    if successful:
                        event_outcomes[key] = frozenset(
                            d
                            for slots, _ in states
                            for d in dict(slots).get(slot, frozenset({None}))
                        )
                    else:
                        # A callback requiring another descriptor, unsupported
                        # effect or analysis limit cannot authorize pruning.
                        # Retain the old independent-write possibilities.
                        event_outcomes[key] = frozenset(
                            update_descriptor(descriptor, c) for c in relevant
                        )
                outcomes.update(event_outcomes[key])
            for changed in outcomes:
                if changed not in choices:
                    choices.add(changed)
                    pending.append(changed)
            # Event order and repetition are unknown. Bound the per-slot closure
            # instead of selecting a last writer or blocking unrelated slots.
            if len(choices) > 256:
                return frozenset(choices), True
        return frozenset(choices), False

    def run_procedure(procedure, initial, historical):
        successful = True
        commands = {command.offset: command for command in procedure.commands}
        pending, positions = {}, []
        sequence = itertools.count()
        finished = set()
        seen = set()

        def enqueue(pc, stack, slots, writes):
            nonlocal successful
            # Only shadow bits read anywhere in this room can affect a later
            # decision or quantity. Physical keys preserve flag/scalar aliases;
            # whole-room dependencies also preserve later procedures and ticks.
            writes = tuple(
                (key, value) for key, value in writes if key in required_shadow_bits
            )
            # Quantity/registry callbacks can feed later guards. Keep those
            # descriptor inputs separate: joining amounts 1/2 before a >=1
            # test would discard a proof that holds on both original paths.
            descriptors = dict(slots)
            key = (
                pc,
                stack,
                writes,
                tuple(
                    (slot, descriptors.get(slot, frozenset({None})))
                    for slot in descriptor_inputs
                ),
            )
            if key not in pending:
                pending[key] = slots
                # A unique tie breaker avoids comparing unknown shadow values.
                heappush(positions, (pc, next(sequence), key))
            elif pending[key] != slots:
                earlier, later = dict(pending[key]), dict(slots)
                pending[key] = tuple(
                    (
                        slot,
                        earlier.get(slot, frozenset({None}))
                        | later.get(slot, frozenset({None})),
                    )
                    for slot in sorted(earlier.keys() | later.keys())
                )
                # Merging must not bypass the existing descriptor budget.
                if any(len(choices) > 256 for _, choices in pending[key]):
                    successful = False

        for slots, writes in initial:
            enqueue(procedure.start, (), slots, writes)
        while positions and successful:
            # Validated branches advance. Processing PCs in order gathers all
            # predecessors before executing a joined registry. Different IF
            # stacks, shadows or descriptor inputs retain separate histories.
            _, _, key = heappop(positions)
            pc, stack, writes, _ = key
            slots = pending.pop(key)
            state = (pc, stack, slots, writes)
            if state in seen:
                continue
            seen.add(state)
            # These are analysis budgets, not claimed native stack capacities.
            # A malformed or branching source must not stall live polling.
            if len(seen) > 4096 or len(stack) > 16:
                successful = False
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
                enqueue(command.next, stack + (args[0],), slots, writes)
                continue
            if kind in ("else", "endif"):
                if not stack:
                    successful = False
                    break
                enqueue(
                    args[0] if kind == "else" else command.next,
                    stack[:-1],
                    slots,
                    writes,
                )
                continue
            predicate = True
            assumption = None
            if kind == "uncertain-test":
                # Unclassified handlers may return zero to the native runner.
                # Explore failure as well as continuation instead of assuming a no-op.
                predicate = None
            elif kind == "unsupported-effect":
                # A return guess cannot account for unaudited writes or a
                # handler that fails to advance its PC. Reject reconstruction.
                successful = False
                break
            elif kind == "constant-test":
                predicate = bool(args[0])
            elif kind == "event-start":
                # Starting a native event returns one. Its later dispatches
                # remain represented by event rules; never replay scheduling.
                predicate = True
                if reentry:
                    if args[1] >= len(program.event_program.entries):
                        successful = False
                        break
                    started.add(args[1])
            elif kind == "display-request":
                # RE1-REENTRY-002: 29 queues a display, setting C3000 bit 18.
                # The outer display consumer later clears it. Its timing is
                # unavailable, so neither value is an invariant across ticks.
                changed = dict(writes)
                changed[layout.flag(5, 13)] = None
                for index in (6, 7):
                    # The outer display consumer clears C8680/C8682 after
                    # returning. Forget those aliased scalar words now to
                    # cover both pending and consumed requests without timing.
                    for bit in range(16):
                        changed[
                            layout.word_variables_base + 2 * index + bit // 8,
                            1 << (bit % 8),
                        ] = None
                writes = tuple(sorted(changed.items()))
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
                    if (
                        not historical
                        and (address, mask) not in dict(writes)
                        and (
                            group in layout.persistent_flag_groups
                            or (group, index) in layout.persistent_flag_bits
                        )
                    ):
                        bit = bool(values[address] & mask)
                predicate = (
                    bit != bool(expected)
                    if bit is not None and expected in (0, 1)
                    else None
                )
                if (
                    historical
                    and bit is None
                    and group < len(layout.flag_bases)
                    and expected in (0, 1)
                ):
                    # Repeated tests in one synchronous block observe the same
                    # physical bit until a modeled writer changes or forgets it.
                    assumption = (layout.flag(group, index), bool(expected))
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
                elif kind == "byte-test" or index < 16:
                    # A block's written bytes/low scalar words are available.
                    # Higher word indices overlap other saved structures and
                    # room-local data, so do not infer them from a scalar shadow.
                    width = 1 if kind == "byte-test" else 2
                    base = (
                        layout.byte_variables_base
                        if width == 1
                        else layout.word_variables_base
                    )
                    address = base + width * index
                    bits = [
                        shadow.get((address + bit // 8, 1 << (bit % 8)))
                        for bit in range(8 * width)
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
                    successful = False
                    break
                else:
                    address, mask = layout.flag(group, index)
                    old = dict(writes).get((address, mask))
                    if (
                        not historical
                        and (address, mask) not in dict(writes)
                        and (
                            group in layout.persistent_flag_groups
                            or (group, index) in layout.persistent_flag_bits
                        )
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
            elif kind == "quantity-transfer":
                transfer, slot, variable = args
                descriptors = dict(slots).get(slot, frozenset({None}))
                amount = ItemQuantityState.Unreconstructed
                address = layout.byte_variables_base + variable
                if transfer == 0:
                    quantities = {
                        descriptor[5]
                        if descriptor is not None and descriptor[0] == "item"
                        else ItemQuantityState.Unreconstructed
                        for descriptor in descriptors
                    }
                    if len(quantities) == 1:
                        amount = quantities.pop()
                elif transfer == 1:
                    shadow = dict(writes)
                    bits = [shadow.get((address, 1 << bit)) for bit in range(8)]
                    if all(bit is not None for bit in bits):
                        amount = sum(
                            int(value) << bit for bit, value in enumerate(bits)
                        )
                if transfer in (1, 2):
                    if any(d is None or d[0] != "item" for d in descriptors):
                        # Source+9 is not always an item quantity. An unbound
                        # write cannot authorize unrelated room conclusions.
                        successful = False
                        break
                    changed_slots = dict(slots)
                    changed_slots[slot] = frozenset(
                        update_descriptor(d, command, amount) for d in descriptors
                    )
                    slots = tuple(sorted(changed_slots.items()))
                if transfer == 1:
                    # Mode 1 reads the scalar without changing it.
                    enqueue(command.next, stack, slots, writes)
                    continue
                changed = dict(writes)
                for bit in range(8):
                    # Inventory history is unavailable in mode 2, including
                    # its no-match path. Forget the amount and scalar together.
                    changed[address, 1 << bit] = (
                        bool(amount & (1 << bit)) if type(amount) is int else None
                    )
                writes = tuple(sorted(changed.items()))
            elif kind in ("item", "door", "aot-create", "aot-handler"):
                changed = dict(slots)
                if (
                    reentry
                    and kind == "aot-handler"
                    and args[1] != 0
                    and None in changed.get(args[0], frozenset({None}))
                ):
                    # Room setup clears handlers, not retained source pointers.
                    # Disabling needs no source, but enabling without this
                    # entry's creator could resurrect a stale descriptor.
                    successful = False
                    break
                changed[args[0]] = frozenset(
                    update_descriptor(descriptor, command)
                    for descriptor in changed.get(args[0], frozenset({None}))
                )
                if kind == "item":
                    address, mask = layout.flag(7, args[3])
                    shadow = dict(writes)
                    separate_history = (
                        historical
                        and 1 <= args[1] <= 0x53
                        and layout.acquisition.flag(args[1], args[3])
                        != AcquisitionFlag(address, mask, False)
                    )
                    if (address, mask) in shadow or separate_history:
                        enabled = shadow.get((address, mask))
                        handlers = (
                            (0, 15 if args[1] >= 0x4E else 4)
                            if enabled is None
                            else (15 if args[1] >= 0x4E else 4,)
                            if enabled
                            else (0,)
                        )
                        changed[args[0]] = frozenset(
                            (*descriptor[:2], handler, *descriptor[3:])
                            for descriptor in changed[args[0]]
                            for handler in handlers
                        )
                slots = tuple(sorted(changed.items()))
                if (
                    reentry
                    and any(
                        descriptor is not None and descriptor[2] == 9
                        for descriptor in changed[args[0]]
                    )
                    and not start_interaction(args[0], slots)
                ):
                    successful = False
                    break
            elif kind in ("award", "aot-callback"):
                # Read completed acquisition/unlock results from RAM, never
                # grant them by replaying a callback during reconstruction.
                # Opcode 24 returns one, while 2D returns zero to the IF runner.
                predicate = bool(args[2])
                changed = dict(writes)
                if args[1] == 1:
                    # RE1-SCD-015: forced dispatch ignores handler/mode, but
                    # the native callback still reads the preserved source.
                    for descriptor in dict(slots).get(args[0], frozenset({None})):
                        if descriptor is None or descriptor[0] != "door":
                            successful = False
                            break
                        lock = descriptor[1][6]
                        if lock & 0x80 and descriptor[1][8] != 0xFF:
                            # Inventory/player state can prevent unlocking.
                            # A conditional set preserves true, but cannot
                            # retain an earlier false shadow or grant an unlock.
                            # Type FF always takes the missing-key path.
                            address = layout.flag(2, lock & 0x3F)
                            old = changed.get(address)
                            if (
                                not historical
                                and address not in changed
                                and 2 in layout.persistent_flag_groups
                            ):
                                old = bool(values[address[0]] & address[1])
                            changed[address] = True if old is True else None
                    if not successful:
                        break
                    address = layout.flag(5, 6)
                    changed[address] = True if changed.get(address) is True else None
                    # Traversal clears CAB00's halfword; dialog setup can mask
                    # it and copy its old value to CAB02. Forget both aliases
                    # and conditional message/key byte writes, never past-room RAM.
                    for index in range(32):
                        changed[layout.flag(6, index)] = None
                    for index in (5, 6):
                        for bit in range(8):
                            changed[layout.byte_variables_base + index, 1 << bit] = None
                elif args[1] in (5, 6):
                    if any(
                        descriptor is None
                        for descriptor in dict(slots).get(args[0], frozenset({None}))
                    ):
                        # Movement callbacks dereference source geometry even
                        # when forced on a disabled AOT. A stale pointer cannot
                        # establish a supported execution path.
                        successful = False
                        break
                    # The callback queues movement with C3004 bit 22. Native
                    # player consumers clear it later; no tick timing is known.
                    changed[layout.flag(5, 41)] = None
                    address = layout.flag(6, 25)
                    # Orientation can skip the immediate clear, and the
                    # movement consumer later sets this dialog bit again.
                    changed[address] = None
                elif args[1] == 7:
                    targets = set()
                    for descriptor in dict(slots).get(args[0], frozenset({None})):
                        if (
                            descriptor is None
                            or descriptor[4] == RegistryParameterState.Unreconstructed
                        ):
                            successful = False
                            break
                        group, index, operation = descriptor[4]
                        if group in (5, 6):
                            index &= 31
                        if group >= 10 or index > 255:
                            # The native default can write through an unset
                            # register, and larger banks exceed our read bounds.
                            # Neither is a modeled no-op or a safe flag alias.
                            successful = False
                            break
                        targets.add((layout.flag(group, index), bool(operation)))
                    if not successful:
                        break
                    for address in {bit for bit, _ in targets}:
                        old = changed.get(address)
                        if (
                            not historical
                            and address not in changed
                            and address in persistent
                            and address[0] in values
                        ):
                            old = bool(values[address[0]] & address[1])
                        choices = {
                            value if target == address else old
                            for target, value in targets
                        }
                        # Alternative registry writers may target different
                        # bits. Untouched alternatives retain the prior value.
                        changed[address] = choices.pop() if len(choices) == 1 else None
                elif args[1] == 9:
                    # Callback 9 starts a script with registry parameters. Its
                    # activity comes from fresh event RAM, never replay here.
                    if reentry and not start_interaction(args[0], slots):
                        successful = False
                        break
                elif args[1] == 13:
                    # Callback 13 sets C3000 bit 8 only for a zero registry
                    # parameter. That field is not modeled; a prior true bit
                    # remains true, otherwise either result is possible.
                    address = layout.flag(5, 23)
                    changed[address] = True if changed.get(address) is True else None
                elif args[1] == 4:
                    if any(
                        descriptor is None
                        or descriptor[0] != "item"
                        or not 1 <= descriptor[1][1] <= 0x4D
                        for descriptor in dict(slots).get(args[0], frozenset({None}))
                    ):
                        # Forced awards ignore the live handler and dereference
                        # the retained source. A missing creator is not a no-op.
                        successful = False
                        break
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
                            successful = False
                            break
                        _, item_type, _, gid, _ = descriptor[1]
                        # Read actual acquisition/ownership from fresh RAM;
                        # discard older shadows only at the possible targets.
                        changed[layout.flag(7, gid)] = None
                        changed[layout.flag(8, item_type - 0x4E + 124)] = None
                    if not successful:
                        break
                if not predicate:
                    # 2D sets pending bit 10 and toggles bit 11 after dispatch,
                    # even when its zero return skips the surrounding IF body.
                    changed[layout.flag(5, 21)] = True
                    address = layout.flag(5, 20)
                    old = changed.get(address)
                    changed[address] = None if old is None else not old
                writes = tuple(sorted(changed.items()))
            false_writes = true_writes = writes
            if assumption is not None:
                address, expected = assumption
                changed = dict(writes)
                changed[address] = expected
                false_writes = tuple(sorted(changed.items()))
                changed[address] = not expected
                true_writes = tuple(sorted(changed.items()))
            if predicate is not True:
                if stack:
                    enqueue(stack[-1], stack[:-1], slots, false_writes)
                else:
                    finished.add((slots, false_writes))
            if predicate is not False:
                enqueue(command.next, stack, slots, true_writes)
        return successful, list(finished)

    permanently_disabled = set()
    candidates = {
        c.args[0]
        for p in program.procedures
        for c in p.commands
        if c.kind == "aot-handler"
        and c.args[1] == 0
        and c.args[0] in program.item_slots
        and c.args[0] not in later_collection_slots
    }
    if candidates and program.coverage_complete:
        # Fresh story flags describe this entry, not every future entry.
        # Reuse the historical initializer interpreter to cover both outcomes
        # of mutable guards, while retaining the actual room and character.
        earlier_started, earlier_unresolved = started, history_unresolved
        started, history_unresolved = set(), set()
        proof_paths, proof_complete = [((), ())], True
        for procedure in program.procedures:
            proof_complete, proof_paths = run_procedure(procedure, proof_paths, True)
            if not proof_complete:
                break
        if proof_complete and proof_paths:
            for slot in candidates - history_unresolved:
                choices = {
                    d
                    for slots, _ in proof_paths
                    for d in dict(slots).get(slot, frozenset({None}))
                }
                if choices and all(
                    d is not None and d[0] == "item" and d[2] == 0 and d[6]
                    for d in choices
                ):
                    identities = {(d[1][0], d[1][1], d[1][3]) for d in choices}
                    if len(identities) == 1:
                        permanently_disabled.update(identities)
        # Proof-only event starts and uncertainty must not change the actual
        # current/reentry evaluation's scheduling or coverage.
        started, history_unresolved = earlier_started, earlier_unresolved

    if reentry:
        resets = {
            layout.flag(group, index): False
            for group, first, count in layout.room_entry_flag_clears
            for index in range(first, first + count)
        }
        paths = [((), tuple(sorted(resets.items())))]
        for procedure in program.procedures:
            bounded, paths = run_procedure(procedure, paths, False)
            if not bounded:
                break

        def join_paths(states):
            # Reuse each path's maps across all bits. Rebuilding a full shadow
            # dictionary for every bit made heavily branching rooms too slow.
            states = tuple((dict(slots), dict(writes)) for slots, writes in states)
            slots = {slot for descriptors, _ in states for slot in descriptors}
            bits = {bit for _, writes in states for bit in writes}
            joined_slots = tuple(
                (
                    slot,
                    frozenset(
                        descriptor
                        for descriptors, _ in states
                        for descriptor in descriptors.get(slot, frozenset({None}))
                    ),
                )
                for slot in sorted(slots)
            )
            joined_bits = []
            for bit in sorted(bits):
                address, mask = bit
                if address in (
                    layout.byte_variables_base + 18,
                    layout.byte_variables_base + 19,
                ):
                    # RE1-SCD-021: native tick resets and player interactions
                    # can replace these bytes between separate runners. Keep
                    # same-run writes, but never join them into an invariant.
                    joined_bits.append((bit, None))
                    continue
                # A missing local shadow is unknown. A missing saved-bit
                # shadow still has its fresh snapshot value, when read.
                initial = (
                    bool(values[address] & mask)
                    if bit in persistent and address in values
                    else None
                )
                choices = {writes.get(bit, initial) for _, writes in states}
                joined_bits.append(
                    (bit, next(iter(choices)) if len(choices) == 1 else None)
                )
            return joined_slots, tuple(joined_bits)

        blocks = {
            frozenset(c.offset for p in block for c in p.commands): block
            for block in program.event_blocks
        }
        commands = {c.offset: c for c in program.event_commands}

        def events_have_coverage():
            # VM waits and native child starts have no retained SCD guard.
            # Any start belonging to a reachable entry may run later.
            pending_entries = list(started)
            visited_entries = set()
            while pending_entries:
                entry = pending_entries.pop()
                if entry in visited_entries:
                    continue
                visited_entries.add(entry)
                targets = {
                    start.args[-1]
                    for start in program.event_program.starts
                    if start.entry == entry
                }
                started.update(targets)
                pending_entries.extend(targets - visited_entries)
            # Decode failures may conceal any registry/flag write, including
            # slots absent from decoded data. Exclude the entire failed entry.
            return not started & failed_entries

        if bounded and paths:
            paths = [join_paths(paths)]
            # A monotone join covers arbitrary tick counts and dispatch order.
            # The budget limits analysis, never the game's event capacity.
            for _ in range(64):
                before, earlier_starts = paths[0], frozenset(started)
                outcomes = {before}
                main_paths = paths
                for procedure in program.main_procedures:
                    bounded, main_paths = run_procedure(procedure, main_paths, False)
                    if not bounded:
                        break
                if not bounded:
                    break
                # Each SCD runner finishes its whole procedure list before
                # another tick/dispatch. Temporary writes inside that list
                # cannot become the starting state of a separate runner.
                outcomes.update(main_paths)
                if not events_have_coverage():
                    bounded = False
                    break
                for dispatch in program.event_program.dispatches:
                    if dispatch.entry not in started or not dispatch.commands:
                        continue
                    block = blocks.get(frozenset(dispatch.commands))
                    if block is None:
                        if (
                            len(dispatch.commands) != 1
                            or dispatch.commands[0] not in commands
                        ):
                            bounded = False
                            break
                        command = commands[dispatch.commands[0]]
                        try:
                            block = (
                                RuleProcedure(command.offset, command.next, (command,)),
                            )
                        except ValueError:
                            # An isolated branch lacks the runner's IF stack.
                            # Its metadata cannot prove any narrower outcome.
                            bounded = False
                            break
                    event_paths = paths
                    for procedure in block:
                        bounded, event_paths = run_procedure(
                            procedure, event_paths, False
                        )
                        if not bounded:
                            break
                    if not bounded:
                        break
                    outcomes.update(event_paths)
                    if len(outcomes) > 4096:
                        bounded = False
                        break
                if not bounded:
                    break
                paths = [join_paths(outcomes)]
                if any(len(choices) > 256 for _, choices in paths[0][0]):
                    bounded = False
                    break
                if paths[0] == before and frozenset(started) == earlier_starts:
                    break
            else:
                bounded = False
            if bounded:
                invariant_bits = dict(paths[0][1])
                for address, mask in persistent:
                    if address in values and (address, mask) not in invariant_bits:
                        invariant_bits[address, mask] = bool(values[address] & mask)
                reentry_seed = tuple(sorted(invariant_bits.items()))
                # A completed reentry includes a recurring-main pass. Apply
                # its supported last writers after collecting earlier ticks,
                # then retain possible events that can run after that pass.
                for procedure in program.main_procedures:
                    bounded, paths = run_procedure(procedure, paths, False)
                    if not bounded:
                        break
                # The final main pass also participates in the mandatory
                # coverage check before its descriptors can be published.
                bounded = bounded and events_have_coverage()
                event_offsets = {
                    offset
                    for dispatch in program.event_program.dispatches
                    if dispatch.entry in started
                    for offset in dispatch.commands
                }
                event_updates = tuple(
                    (block, updates)
                    for block, updates in event_updates
                    if any(c.offset in event_offsets for p in block for c in p.commands)
                )
                active_effects = tuple(
                    c for c in program.event_effects if c.offset in event_offsets
                )
    else:
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
                    or command.kind == "quantity-transfer"
                    and command.args[0] in (1, 2)
                )
                historical = []
                for slots, _ in paths:
                    changed = dict(slots)
                    for slot in set(program.item_slots) | set(program.door_slots):
                        choices, exceeded = closure(
                            changed.get(slot, frozenset({None})),
                            [
                                command
                                for command in effects
                                if targets_slot(command, slot)
                            ],
                            slot,
                        )
                        changed[slot] = choices
                        if exceeded:
                            history_unresolved.add(slot)
                    historical.append((tuple(sorted(changed.items())), ()))
                paths = historical
            successful, paths = run_procedure(procedure, paths, False)
            if not successful:
                bounded = False
                break
    uncertain_items, uncertain_collection, uncertain_doors = set(), set(), set()
    items, collection_items, doors, disabled_doors = [], [], [], []
    labels = dict(item_labels)

    def interpret_descriptor(descriptor, *, collection: bool):
        if descriptor is None:
            return "absent", None
        creator, args, handler, mode, parameters, quantity, explicitly_disabled = (
            descriptor
        )
        assert type(explicitly_disabled) is bool
        assert not explicitly_disabled or handler == 0
        slot = args[0]
        if creator == "item":
            _, item_type, _, gid, _ = args
            if item_type == 0 or item_type >= 0x54:
                return "absent", None  # Documents are excluded from room completion.
            acquisition_flag = layout.acquisition.flag(item_type, gid)
            remaining = not layout.acquisition.collected(
                acquisition_flag, flags, values
            )
            if handler == 9:
                # RE1-COLLECT-003: fresh acquisition resolves a taken item even
                # when its interaction is unsupported. Access matters only
                # while the source-bound item remains uncollected.
                if remaining and (
                    parameters is RegistryParameterState.Unreconstructed
                    or not scripted_collectible_access(
                        program.event_program,
                        slot,
                        item_type,
                        parameters[0] & 255,
                        parameters[1] & 255,
                    )
                ):
                    if not collection:
                        return "unresolved", None
                    handler = 0
                else:
                    handler = 15 if item_type >= 0x4E else 4
            if (
                handler not in (0, 3, 4, 15)
                or handler == 4
                and item_type >= 0x4E
                or handler == 15
                and item_type < 0x4E
            ):
                return "unresolved", None
            if (
                not collection
                and remaining
                and handler in (0, 3)
                and slot in program.award_slots
            ):
                # A dormant descriptor can still be awarded by an event. Its
                # current availability needs event progress, not just a pickup bit.
                return "unresolved", None
            # RE1-CLEAR-007: a final explicit disable with no later slot writer
            # or forced award proves absence; ordinary puzzle dormancy does not.
            state = (
                RuntimeItemState.Unavailable
                if collection and (slot, item_type, gid) in permanently_disabled
                else RuntimeItemState.Taken
                if not remaining
                else RuntimeItemState.Available
                if handler in (4, 15)
                else RuntimeItemState.Unavailable
                if not collection
                else RuntimeItemState.Uncollected
            )
            return (
                "item",
                # Reconstructed descriptors have no live PS1 source pointer.
                # Zero stays internal; only observed AOTs authorize memory reads.
                RuntimeRoomItem(
                    slot,
                    item_type,
                    quantity,
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
        elif creator == "door" and handler in (0, 1, 2, 9):
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
            if handler == 9:
                if parameters is RegistryParameterState.Unreconstructed:
                    return "unresolved", None
                access = scripted_door_access(
                    program.event_program, slot, parameters[1] & 255, bytes(raw)
                )
                if access is ScriptedDoorAccess.Unresolved:
                    return "unresolved", None
                return (
                    "door"
                    if access is ScriptedDoorAccess.Delegated
                    else "disabled-door",
                    (slot, bytes(raw)),
                )
            # RE1-DOORS-003: handler 2 displays a message, retaining the door
            # source without granting traversal or changing its unlock flag.
            return "door" if handler == 1 else "disabled-door", (slot, bytes(raw))
        elif creator == "aot-create" and handler in (1, 3, 4, 15):
            return "unresolved", None
        elif creator == "door":
            # A changed handler can expose another scripted interaction.
            # Its physical access has no implemented door rule yet.
            return "unresolved", None
        return "absent", None

    def meanings_for(choices, *, collection: bool):
        meanings = {
            interpret_descriptor(descriptor, collection=collection)
            for descriptor in choices
        }
        if meanings and all(kind == "item" for kind, _ in meanings):
            # Collection ignores puzzle activation while native availability
            # keeps that distinction. Both share identity and quantity joining.
            identities = {
                replace(
                    item,
                    amount=ItemQuantityState.Unreconstructed,
                    state=RuntimeItemState.Uncollected
                    if collection and item.state == RuntimeItemState.Available
                    else item.state,
                )
                for _, item in meanings
            }
            if len(identities) == 1:
                amounts = {item.amount for _, item in meanings}
                amount = (
                    amounts.pop()
                    if len(amounts) == 1
                    else ItemQuantityState.Unreconstructed
                )
                item = identities.pop()
                state = (
                    RuntimeItemState.Available
                    if all(
                        item.state == RuntimeItemState.Available for _, item in meanings
                    )
                    else item.state
                )
                meanings = {("item", replace(item, amount=amount, state=state))}
        return meanings

    for slot in sorted(set(program.item_slots) | set(program.door_slots)):
        choices = {
            descriptor
            for slots, _ in paths
            for descriptor in dict(slots).get(slot, frozenset({None}))
        }
        effects = [
            command
            for command in (
                active_effects if reentry and bounded else program.event_effects
            )
            if targets_slot(command, slot)
        ]
        if reentry and not bounded:
            exceeded = False
        else:
            choices, exceeded = closure(choices, effects, slot)
        invalid = (
            not bounded
            or not source_complete
            or slot in program.mutable_slots
            and slot not in quantity_slots
            or exceeded
            or slot in history_unresolved
        )
        if slot in program.item_slots:
            collection_meanings = meanings_for(choices, collection=True)
            if (
                invalid
                or len(collection_meanings) != 1
                or ("unresolved", None) in collection_meanings
            ):
                uncertain_collection.add(slot)
            else:
                kind, value = collection_meanings.pop()
                if kind == "item":
                    collection_items.append(value)
        meanings = meanings_for(choices, collection=False)
        if invalid or len(meanings) != 1 or ("unresolved", None) in meanings:
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

    def item_result(known, unresolved):
        reason = "Some item conditions need a room visit." if unresolved else ""
        if not bounded or not source_complete:
            reason = "Room script coverage is incomplete."
        return RuntimeRoomItems(
            ok=True,
            items=tuple(known),
            list_complete=not reason,
            coverage_reason=reason,
        )

    return RuleEvaluation(
        item_result(items, uncertain_items),
        item_result(collection_items, uncertain_collection),
        tuple(doors),
        tuple(disabled_doors),
        tuple(sorted(uncertain_items)),
        tuple(sorted(uncertain_collection)),
        tuple(sorted(uncertain_doors)),
        bounded and source_complete,
    )
