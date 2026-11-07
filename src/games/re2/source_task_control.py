"""Finite ordinary task/input frontiers for trusted scenario guards only."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from enum import Enum

from games.bit_flags import msb_flag_location
from games.re2.native_control import goto_if_cell
from games.re2.ordinary_task_ingress import VerifiedOrdinaryTaskIngress
from games.re2.scenario_selection import (
    ScenarioSourceWriteWitnesses,
    VerifiedScenarioContext,
    bind_scenario_context,
    scenario_source_write_witnesses,
)
from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    NATIVE_IF_FRAME_COUNT,
    programs_digest,
)

# Pending UI, delayed pickup animation, selected-record owners and accepted
# pickup clears are separate finite domains. The offline budget includes those
# owners; exhaustion withholds rights rather than dropping a branch.
CONTROL_FRONTIER_LIMIT = 3_000_000


class TaskControlFailure(Enum):
    Binding = "task control source/context/ingress binding mismatch"
    SourceMutation = "task control input or source dependency may change"
    NativeClock = "task control primitive may advance the outer input clock"
    Namespace = "ordinary task birth namespace is unproved"
    InputLease = "ordinary external interaction episodes can overlap"
    TaskAlias = "ordinary allocation can replace a live worker"
    ForeignConsumer = "escaped IF scratch has a possible control consumer"
    StateLimit = "task control frontier exceeds its finite analysis limit"


class TaskControlSupport(Enum):
    Unaudited = "unaudited"


@dataclass(frozen=True)
class _SourceTaskDerivation:
    source_sha256: str
    programs_sha256: str
    ingress: VerifiedOrdinaryTaskIngress
    dispatches: frozenset[tuple[str, int]]
    gotos: frozenset[tuple[str, int]]
    owners: tuple[tuple[int, tuple[str, ...]], ...]
    frontier_count: int


@dataclass(frozen=True)
class VerifiedSourceTaskControl(_SourceTaskDerivation):
    _derivation: _SourceTaskDerivation

    def __post_init__(self) -> None:
        assert isinstance(self._derivation, _SourceTaskDerivation)
        assert self._derivation == _SourceTaskDerivation(
            self.source_sha256,
            self.programs_sha256,
            self.ingress,
            self.dispatches,
            self.gotos,
            self.owners,
            self.frontier_count,
        )
        assert len(self.source_sha256) == len(self.programs_sha256) == 64
        assert isinstance(self.ingress, VerifiedOrdinaryTaskIngress)
        assert type(self.dispatches) is frozenset and type(self.gotos) is frozenset
        assert type(self.owners) is tuple and self.frontier_count > 0

    def matches(
        self, data: bytes, room: dict, context: VerifiedScenarioContext
    ) -> bool:
        return (
            self.source_sha256 == hashlib.sha256(data).hexdigest()
            and self.programs_sha256 == programs_digest(room["programs"])
            and self.ingress.selection == context.declaration_contract.selection
            and self.ingress.covers(data, room)
        )


class _Rejected(Exception):
    def __init__(self, failure: TaskControlFailure):
        self.failure = failure


@dataclass(frozen=True)
class _Task:
    root: str
    key: str
    pc: int
    conditions: tuple[int, ...]
    calls: tuple[tuple[str, int, tuple[int, ...]], ...]
    sleep: int
    external: bool


class _Empty(Enum):
    Task = "inactive task"
    Message = "idle message"
    ItemUI = "idle item UI"
    Binding = "unregistered AOT slot"
    Animation = "no delayed flag1 pickup request"


class _PickupAnimation(Enum):
    Starting = "player routine6 phase0"
    Waiting = "animation before the later UI request"


class _PickupOwner(Enum):
    Unselected = "no current-source pickup request"
    Unobserved = "manual-only record without a Reset or scripted47 consumer"


class _ItemFlags(Enum):
    Unproved = "registered descriptor has no established item flags"


@dataclass(frozen=True)
class _Binding:
    kind: int
    sat: int
    target: str
    item_flags: int | _ItemFlags
    record: int


@dataclass(frozen=True)
class _Message:
    saved7: bool
    fresh: bool


class _UIPhase(Enum):
    Pending = "requested before the native UI gate"
    Active = "ordinary task0 suspended by native item UI"
    Fenced = "postreturn STOP7 mapper before ordinary resumption"


@dataclass(frozen=True)
class _ItemUI:
    saved7: bool
    phase: _UIPhase


@dataclass(frozen=True)
class _Frontier:
    tasks: tuple[_Task | _Empty, ...]
    bindings: tuple[_Binding | _Empty, ...]
    stop6: bool
    stop7: bool
    previous7: bool
    held_action: bool
    message: _Message | _Empty
    item_ui: _ItemUI | _Empty
    records: tuple[_Binding, ...]
    animation: _PickupAnimation | _Empty
    pickup_owner: int | _PickupOwner


def _animation_frontiers(state: _Frontier) -> set[_Frontier]:
    if state.animation is _Empty.Animation or (
        state.item_ui is not _Empty.ItemUI
        and state.item_ui.phase in (_UIPhase.Active, _UIPhase.Fenced)
    ):
        return {state}
    if state.animation is _PickupAnimation.Starting:
        return {state, replace(state, animation=_PickupAnimation.Waiting)}
    assert state.animation is _PickupAnimation.Waiting
    # Native routine6 captures STOP at its later phase2 request, not at the
    # original flag1 AOT. Its nonyielding animation duration stays unknown.
    return {
        state,
        replace(
            state,
            animation=_Empty.Animation,
            item_ui=_ItemUI(state.stop7, _UIPhase.Pending),
        ),
    }


def _ui_completion_frontiers(state: _Frontier) -> set[_Frontier]:
    assert isinstance(state.item_ui, _ItemUI)
    assert state.pickup_owner is not _PickupOwner.Unselected
    if state.item_ui.phase is _UIPhase.Active:
        # Native UI temporarily clears literal STOP but suspends task0. Its
        # return clamps EF and phase5 is a later native0 pass, so a filtered
        # mapper must precede resumption. This is not Message's phase rule.
        fenced = replace(state, item_ui=replace(state.item_ui, phase=_UIPhase.Fenced))
        results = {fenced}
        if type(state.pickup_owner) is int:
            # Accepted UI clears the selected source kind at 72298/72B40.
            # Cancellation retains it. Task0 is suspended during this interval,
            # so both results are published before ordinary SCD can resume.
            def cleared(binding):
                return (
                    replace(binding, kind=0)
                    if isinstance(binding, _Binding)
                    and binding.record == state.pickup_owner
                    else binding
                )

            results.add(
                replace(
                    fenced,
                    records=tuple(cleared(binding) for binding in state.records),
                    bindings=tuple(cleared(binding) for binding in state.bindings),
                )
            )
        return results
    assert state.item_ui.phase is _UIPhase.Fenced
    # Additional owned native STOP ORs can only suppress more admissions.
    # Retaining saved7 is the conservative input-admission projection, with
    # every non-scenario source predicate still retaining both outcomes.
    return {
        state,
        replace(
            state,
            item_ui=_Empty.ItemUI,
            stop6=False,
            stop7=state.item_ui.saved7,
            pickup_owner=(
                _PickupOwner.Unselected
                if state.animation is _Empty.Animation
                else state.pickup_owner
            ),
        ),
    }


def source_task_control_scope(
    data: bytes,
    room: dict,
    profile: dict,
    context: VerifiedScenarioContext,
    ingress: VerifiedOrdinaryTaskIngress,
) -> VerifiedSourceTaskControl | TaskControlFailure:
    """Close source births, input ownership and receiving field consumers.

    Other predicates retain both outcomes. No current RAM value, item identity,
    room name or source offset selects a production permission.
    """
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert isinstance(context, VerifiedScenarioContext)
    assert isinstance(ingress, VerifiedOrdinaryTaskIngress)

    def require(condition, failure):
        if not condition:
            raise _Rejected(failure)

    try:
        require(
            bind_scenario_context(profile, context.declaration_contract) == context
            and ingress.selection == context.declaration_contract.selection
            and ingress.covers(data, room)
            and room["candidate_list_complete"],
            TaskControlFailure.Binding,
        )
        programs = room["programs"]
        fixed_flags = {(bank, bit): value for bank, bit, value in context.fixed_flags}
        rows = {
            key: {r["offset"]: r for r in p["commands"]} for key, p in programs.items()
        }
        all_rows = [(key, row) for key, p in programs.items() for row in p["commands"]]
        writes = scenario_source_write_witnesses(data, room, profile)
        require(
            isinstance(writes, ScenarioSourceWriteWitnesses) and not writes.copies,
            TaskControlFailure.SourceMutation,
        )
        banks = {r["bank"]: int(r["address_ps1"], 0) for r in profile["flag_banks"]}
        for _, row in all_rows:
            packet = data[row["offset"] : row["next"]]
            op = row["opcode"]
            if op == 0x22:
                require(
                    banks[row["bank"]]
                    == context.declaration_contract.flag_addresses[row["bank"]],
                    TaskControlFailure.Binding,
                )
                address, mask = msb_flag_location(banks[row["bank"]], row["bit"])
                # STATUS, SYSTEM, logical input/history and UI snapshots have
                # independent native owners. Only the modeled STOP7 writes may
                # affect an episode; other source aliases cannot inherit trust.
                require(
                    not any(
                        address <= protected < address + 4
                        for protected in (
                            0x800CFBD8,
                            0x800CFB74,
                            0x800CE30C,
                            0x800CE310,
                            0x800DF348,
                            0x800DF38C,
                            0x800C3A88,
                            0x800D76A4,
                            0x800E873C,
                        )
                    )
                    and (
                        address != 0x800CFBDC
                        or mask & 0x03000000 == 0
                        or (row["bank"], row["bit"]) == (2, 7)
                    ),
                    TaskControlFailure.SourceMutation,
                )
                require(
                    all(
                        not (address <= 0x800D47EC + counter * 2 < address + 4)
                        for counter in ingress.preserved_counters
                    ),
                    TaskControlFailure.SourceMutation,
                )
            index = {0x24: 1, 0x25: 1, 0x26: 3, 0x27: 2, 0x3D: 1}.get(op)
            if index is not None:
                require(
                    packet[index] not in ingress.preserved_counters,
                    TaskControlFailure.SourceMutation,
                )
            require(
                op not in (3, 5, 0x19, 0x1B, 0x1C, 0x6C, 0x6E, 0x6F),
                TaskControlFailure.Namespace,
            )
            if op == 4:
                require(
                    packet[1:3] == b"\xff\x18" and f"17:{packet[3]}" in programs,
                    TaskControlFailure.Namespace,
                )
            if op == 0x2B:
                require(
                    packet[1] == packet[4] == 0 and packet[5] & 3 == 3,
                    TaskControlFailure.InputLease,
                )
            if op == 0x26:
                require(packet[2] in (0, 1, 5, 6), TaskControlFailure.NativeClock)
            if op == 0x23:
                require(packet[3] < 7, TaskControlFailure.NativeClock)

        def fresh(key, external):
            require(key in programs, TaskControlFailure.Namespace)
            return _Task(key, key, programs[key]["entry"], (), (), 0, external)

        def allocate(tasks):
            # Native allocation scans 2..8 and uses slot9 unconditionally.
            # Callers must separately reject replacement/non-alias failures.
            return next(
                (index for index in range(2, 9) if tasks[index] is _Empty.Task), 9
            )

        def descriptor(row):
            packet = data[row["offset"] : row["next"]]
            kind = (
                1
                if row["kind"] == "door"
                else 2
                if row["kind"] == "item"
                else packet[2]
            )
            payload = (
                4
                if row["kind"] == "reset"
                else 22
                if row["opcode"] in (0x67, 0x68, 0x69)
                else 14
            )
            require(packet[1] < 32 and kind <= 5, TaskControlFailure.Namespace)
            if kind == 5:
                require(
                    packet[3] == 0x31
                    and packet[payload : payload + 3] == b"\xff\0\x18",
                    TaskControlFailure.Namespace,
                )
                return _Binding(
                    kind,
                    packet[3],
                    f"17:{packet[payload + 3]}",
                    _ItemFlags.Unproved,
                    row["offset"],
                )
            if kind == 4:
                require(
                    packet[3] == 0x31
                    and packet[payload + 2 : payload + 5] == bytes(3)
                    and packet[payload + 5] & 3 == 3,
                    TaskControlFailure.InputLease,
                )
            flags = (
                packet[-1]
                if kind == 2 and row["kind"] == "item"
                else _ItemFlags.Unproved
            )
            return _Binding(kind, packet[3], "", flags, row["offset"])

        # Retain every creator/reset, including alternate historical startup
        # and deferred kind4 Message. Fixed scenario filtering happens later.
        for _, row in all_rows:
            if row["kind"] in ("door", "item", "interaction", "reset"):
                descriptor(row)
        records_by_offset = {
            row["offset"]: descriptor(row)
            for _, row in all_rows
            if row["kind"] in ("door", "item", "interaction")
        }
        record_indices = {
            offset: index for index, offset in enumerate(sorted(records_by_offset))
        }
        observed_slots = {
            data[row["offset"] + 1]
            for _, row in all_rows
            if row["opcode"] in (0x46, 0x47)
        }
        # A manual-only record has no source Reset/47 observer. Its native
        # disable is covered by the existing no-match manual edge; retain an
        # exact owner only where later source control can consume the record.
        pickup_owners = {
            offset: offset
            if data[offset + 1] in observed_slots
            else _PickupOwner.Unobserved
            for offset in records_by_offset
        }

        owners: dict[int, set[str]] = {i: set() for i in range(2, 10)}
        dispatches, gotos = set(), set()
        persistent = {
            key
            for key, p in programs.items()
            if any(r["opcode"] == 0x17 for r in p["commands"])
        }
        require(bool(persistent), TaskControlFailure.Namespace)
        for key in persistent:
            commands = programs[key]["commands"]
            for row in commands:
                op = row["opcode"]
                packet = data[row["offset"] : row["next"]]
                require(
                    row["kind"] not in ("door", "item", "interaction", "reset"),
                    TaskControlFailure.Namespace,
                )
                require(
                    op not in (1, 3, 4, 5, 0x18, 0x22, 0x2B, 0x47),
                    TaskControlFailure.Namespace,
                )
                if op == 0x17:
                    require(
                        packet[1:4] == b"\xff\xff\0" and row["target"] in rows[key],
                        TaskControlFailure.ForeignConsumer,
                    )
                    gotos.add((key, row["offset"]))
                elif op not in (2, 6, 7, 8, 9, 0x11, 0x12, 0x13, 0x14, 0x16, 0x1A):
                    require(
                        op in ingress.atomic_opcodes, TaskControlFailure.NativeClock
                    )
                    require(
                        op != 0x51 or packet[2] in (0, 1),
                        TaskControlFailure.NativeClock,
                    )

        def run(state, slot, startup):
            """Visit once, retaining every finite branch to yield/sleep/end."""
            pending, seen, completed = [state], set(), set()
            while pending:
                state = pending.pop()
                task = state.tasks[slot]
                if task is _Empty.Task:
                    completed.add(state)
                    continue
                require(isinstance(task, _Task), TaskControlFailure.Namespace)
                if task.root in persistent:
                    require(
                        not task.external and not task.calls and slot in (2, 3),
                        TaskControlFailure.Namespace,
                    )
                    owners[slot].add(task.root)
                    completed.add(state)
                    continue
                if state in seen:
                    continue
                seen.add(state)
                require(len(seen) < 16384, TaskControlFailure.StateLimit)
                row = rows[task.key].get(task.pc)
                require(row is not None, TaskControlFailure.Namespace)
                packet = data[task.pc : row["next"]]
                op, following = row["opcode"], row["next"]
                tasks = list(state.tasks)
                next_task = replace(task, pc=following)
                branches = []
                state_branches = []
                suspend = False
                if op == 1:
                    if task.calls:
                        key, pc, conditions = task.calls[-1]
                        next_task = replace(
                            task,
                            key=key,
                            pc=pc,
                            conditions=conditions,
                            calls=task.calls[:-1],
                        )
                    else:
                        next_task = _Empty.Task
                elif op == 0x18:
                    require(
                        startup and len(task.calls) < NATIVE_CALL_FRAME_COUNT - 1,
                        TaskControlFailure.Namespace,
                    )
                    target = f"17:{packet[1]}"
                    require(
                        target in programs and target not in persistent,
                        TaskControlFailure.Namespace,
                    )
                    next_task = replace(
                        task,
                        key=target,
                        pc=programs[target]["entry"],
                        conditions=(),
                        calls=task.calls + ((task.key, following, task.conditions),),
                    )
                elif op == 6:
                    require(
                        len(task.conditions) < NATIVE_IF_FRAME_COUNT
                        and following < row["target"]
                        and row["target"] in rows[task.key],
                        TaskControlFailure.Namespace,
                    )
                    next_task = replace(
                        task,
                        pc=following,
                        conditions=task.conditions + (row["target"],),
                    )
                elif row["kind"] == "flag_check" or op == 0x23:
                    # Outside IF a failed predicate yields. That startup/
                    # episode form has no continuation rule in this compiler.
                    require(bool(task.conditions), TaskControlFailure.Namespace)
                    flag = (
                        (row["bank"], row["bit"]) if row["kind"] == "flag_check" else ()
                    )
                    if flag in fixed_flags:
                        # The same source-wide STATUS writer rejection above
                        # preserves these mandatory native scenario facts.
                        # Historical mode and all other flags stay unknown.
                        if row["expected"] != fixed_flags[flag]:
                            next_task = replace(
                                task,
                                pc=task.conditions[-1],
                                conditions=task.conditions[:-1],
                            )
                    else:
                        branches.append(
                            replace(
                                task,
                                pc=task.conditions[-1],
                                conditions=task.conditions[:-1],
                            )
                        )
                elif op in (7, 8):
                    require(
                        bool(task.conditions) and following == task.conditions[-1],
                        TaskControlFailure.Namespace,
                    )
                    next_task = replace(
                        task,
                        pc=row["target"] if op == 7 else following,
                        conditions=task.conditions[:-1],
                    )
                elif row["kind"] in ("door", "item", "interaction", "reset"):
                    require(
                        startup or op in ingress.atomic_opcodes,
                        TaskControlFailure.NativeClock,
                    )
                    bindings = list(state.bindings)
                    if row["kind"] == "reset":
                        # Native Reset dereferences the existing registry
                        # pointer and changes only kind/SAT/first six payload
                        # bytes. Disabled kind0 remains registered; empty does
                        # not acquire geometry or an item-flags default.
                        previous = bindings[packet[1]]
                        require(
                            isinstance(previous, _Binding), TaskControlFailure.Namespace
                        )
                        # UI keeps this pointer through deferred acceptance.
                        # Rewriting its payload during UI/flag1 animation needs
                        # an independent native resource/control contract.
                        require(
                            previous.record != state.pickup_owner
                            or state.item_ui is _Empty.ItemUI
                            and state.animation is _Empty.Animation,
                            TaskControlFailure.SourceMutation,
                        )
                        binding = replace(
                            descriptor(row),
                            item_flags=previous.item_flags,
                            record=previous.record,
                        )
                        records = list(state.records)
                        records[record_indices[previous.record]] = binding
                        # Reset writes through the registered source pointer.
                        # Reexecution and every alias must see the mutated
                        # record, rather than the original RDT descriptor.
                        bindings = [
                            binding
                            if isinstance(candidate, _Binding)
                            and candidate.record == binding.record
                            else candidate
                            for candidate in bindings
                        ]
                        state = replace(
                            state, bindings=tuple(bindings), records=tuple(records)
                        )
                    else:
                        bindings[packet[1]] = state.records[
                            record_indices[row["offset"]]
                        ]
                        state = replace(state, bindings=tuple(bindings))
                        if row["kind"] == "item" and packet[1] in observed_slots:
                            # Native Item_set registers the source pointer, then
                            # clears its kind if the acquisition flag is set.
                            # Keep both histories without sampling RAM. For
                            # manual-only slots the existing no-match AOT edge
                            # already covers inactive records; Reset/47 can
                            # observe this mutation and therefore require it.
                            cleared = replace(bindings[packet[1]], kind=0)
                            records = list(state.records)
                            records[record_indices[row["offset"]]] = cleared
                            cleared_bindings = tuple(
                                cleared
                                if isinstance(b, _Binding)
                                and b.record == cleared.record
                                else b
                                for b in state.bindings
                            )
                            state_branches.append(
                                replace(
                                    state,
                                    bindings=cleared_bindings,
                                    records=tuple(records),
                                )
                            )
                elif op == 4 or op == 0x47:
                    if op == 4:
                        target, external = f"17:{packet[3]}", False
                    else:
                        binding = state.bindings[packet[1]]
                        require(
                            isinstance(binding, _Binding), TaskControlFailure.Namespace
                        )
                        kind, target, flags = (
                            binding.kind,
                            binding.target,
                            binding.item_flags,
                        )
                        require(kind in (0, 2, 5), TaskControlFailure.Namespace)
                        if kind == 0:
                            # AOT kind0 copies unknown native scalar positions
                            # into counters0/1 and returns0. Every counter
                            # predicate already retains both outcomes; neither
                            # counter is the protected aux index5. Opcode47
                            # ignores the return and advances, without UI/STOP.
                            require(
                                not ingress.preserved_counters & {0, 1},
                                TaskControlFailure.SourceMutation,
                            )
                            target = ""
                        elif kind == 2:
                            require(
                                flags == 0,
                                TaskControlFailure.InputLease,
                            )
                            require(
                                state.item_ui is _Empty.ItemUI
                                or state.item_ui.phase is _UIPhase.Pending,
                                TaskControlFailure.InputLease,
                            )
                            # 51884 captures STOP and requests STATUS8000.
                            # It does not pause this SCD pass or initialize a
                            # Message. The normal UI gate runs after SCD.
                            state = replace(
                                state,
                                item_ui=_ItemUI(state.stop7, _UIPhase.Pending),
                                pickup_owner=pickup_owners[binding.record],
                            )
                            target = ""
                        elif state.stop6:
                            # Native kind5 checks STOP6 for scripted47 as well
                            # as manual dispatch. Opcode47 still advances PC;
                            # assuming a birth here can hide a reentry path.
                            target = ""
                        external = False
                        dispatches.add((task.key, task.pc))
                    if target:
                        allocated = allocate(tasks)
                        # Slot nine is the allocator's unconditional final
                        # replacement case. This certificate requires a free
                        # nonfinal slot as well as caller non-aliasing.
                        require(
                            tasks[allocated] is _Empty.Task
                            and (op != 0x47 or allocated != slot and allocated < 9),
                            TaskControlFailure.TaskAlias,
                        )
                        require(
                            startup or target not in persistent,
                            TaskControlFailure.Namespace,
                        )
                        tasks[allocated] = fresh(target, external)
                        owners[allocated].add(target)
                elif op == 0x22 and (row["bank"], row["bit"]) == (2, 7):
                    require(
                        not startup and packet[3] in (0, 1),
                        TaskControlFailure.InputLease,
                    )
                    state = replace(state, stop7=bool(packet[3]))
                elif op == 0x2B:
                    require(not startup, TaskControlFailure.InputLease)
                    if state.message is _Empty.Message:
                        message = _Message(state.stop7, True)
                    else:
                        message = state.message
                        # 54A8C advances PC before Mess_set. Busy initialization
                        # preserves the old snapshot but still ORs this mask;
                        # it neither retries the instruction nor yields.
                    state = replace(state, stop6=True, stop7=True, message=message)
                elif op == 2:
                    require(not startup, TaskControlFailure.Namespace)
                    suspend = True
                elif op == 9:
                    require(
                        not startup and packet[1] == 10 and not task.calls,
                        TaskControlFailure.Namespace,
                    )
                    remaining = (
                        task.sleep
                        if task.sleep
                        else int.from_bytes(packet[2:4], "little")
                    )
                    require(0 < remaining <= 256, TaskControlFailure.StateLimit)
                    remaining -= 1
                    next_task = replace(
                        task, pc=task.pc if remaining else following, sleep=remaining
                    )
                    suspend = True
                else:
                    # Startup constructors can cooperate with the isolated
                    # aux engine. Ordinary episode paths require call closure
                    # because extra input mappings would expire a release fence.
                    require(
                        op in ingress.atomic_opcodes or startup and op in (0x2D, 0x44),
                        TaskControlFailure.NativeClock,
                    )
                    require(
                        op != 0x51 or packet[2] in (0, 1),
                        TaskControlFailure.NativeClock,
                    )
                for source_state in [state, *state_branches]:
                    for replacement in [next_task, *branches]:
                        current = list(tasks)
                        current[slot] = replacement
                        successor = replace(source_state, tasks=tuple(current))
                        if suspend:
                            completed.add(successor)
                        else:
                            pending.append(successor)
            return completed

        empty_bindings = (_Empty.Binding,) * 32
        initial = _Frontier(
            (fresh("16:0", False), fresh("17:0", False)) + (_Empty.Task,) * 8,
            empty_bindings,
            False,
            False,
            False,
            False,
            _Empty.Message,
            _Empty.ItemUI,
            tuple(records_by_offset[offset] for offset in sorted(records_by_offset)),
            _Empty.Animation,
            _PickupOwner.Unselected,
        )
        # Inherit either STOP6/7 snapshot. Permitting an immediate first input
        # edge over-approximates the native entry fence; no RAM sample supplies
        # a historical owner or a scenario/control permission.
        startup_states = {
            replace(initial, stop6=stop6, stop7=stop7)
            for stop6 in (False, True)
            for stop7 in (False, True)
        }
        for slot in (0, 1):
            startup_states = {
                result for state in startup_states for result in run(state, slot, True)
            }
        require(
            [r["opcode"] for r in programs["17:1"]["commands"]] == [1],
            TaskControlFailure.Namespace,
        )
        pending, seen = list(startup_states), set()
        while pending:
            state = pending.pop()
            if state in seen:
                continue
            seen.add(state)
            require(len(seen) <= CONTROL_FRONTIER_LIMIT, TaskControlFailure.StateLimit)
            # A physical rising edge cannot occur on two consecutive mappings.
            # Source-directed logical input/history writers were rejected above.
            states = {
                replace(state, previous7=state.stop7, held_action=held)
                for held in (False, True)
            }
            states = {
                result
                for candidate in states
                for result in _animation_frontiers(candidate)
            }
            # Phase1 runs before ordinary SCD. Busy Message/fade may defer its
            # STOP clamp for arbitrarily many ordinary passes. Retain that
            # pending path; never substitute the skipped 264CC UI path.
            if (
                state.item_ui is not _Empty.ItemUI
                and state.item_ui.phase is _UIPhase.Pending
                and state.message is _Empty.Message
            ):
                states |= {
                    replace(
                        candidate,
                        stop6=True,
                        stop7=True,
                        item_ui=replace(candidate.item_ui, phase=_UIPhase.Active),
                    )
                    for candidate in tuple(states)
                }
            action_eligible = (
                not state.stop7 and not state.previous7 and not state.held_action
            )
            paused = {candidate for candidate in states if candidate.stop6}
            states -= paused
            for slot in range(2, 10):
                states = {
                    result
                    for candidate in states
                    for result in run(candidate, slot, False)
                }
            states |= paused
            for candidate in states:
                action = action_eligible and candidate.held_action
                ui_gate = candidate.item_ui is not _Empty.ItemUI
                ui_gate = ui_gate and candidate.item_ui.phase in (
                    _UIPhase.Active,
                    _UIPhase.Fenced,
                )
                after_aot = {candidate}
                if action and not ui_gate:
                    for binding in candidate.bindings:
                        if binding is _Empty.Binding:
                            continue
                        assert isinstance(binding, _Binding)
                        kind, sat, target = binding.kind, binding.sat, binding.target
                        if kind not in (2, 4, 5) or sat != 0x31:
                            continue
                        # Model all manual matches, one per pass. Never assume
                        # geometry excludes a source callback or kind4 episode.
                        if kind == 2:
                            require(
                                binding.item_flags in (0, 1),
                                TaskControlFailure.InputLease,
                            )
                            if binding.item_flags == 1:
                                after_aot.add(
                                    replace(
                                        candidate,
                                        animation=_PickupAnimation.Starting,
                                        pickup_owner=pickup_owners[binding.record],
                                    )
                                )
                            else:
                                after_aot.add(
                                    replace(
                                        candidate,
                                        item_ui=_ItemUI(
                                            candidate.stop7, _UIPhase.Pending
                                        ),
                                        pickup_owner=pickup_owners[binding.record],
                                    )
                                )
                            continue
                        if kind == 4:
                            if candidate.message is _Empty.Message:
                                after_aot.add(
                                    replace(
                                        candidate,
                                        message=_Message(candidate.stop7, True),
                                    )
                                )
                            continue
                        if candidate.stop6:
                            # Only kind5's native dispatcher has this STOP6
                            # admission check; manual item/Message callbacks
                            # must not silently inherit it.
                            continue
                        require(
                            not any(
                                isinstance(t, _Task) and t.external and t.root == target
                                for t in candidate.tasks
                            ),
                            TaskControlFailure.InputLease,
                        )
                        # Different manual roots may coexist after a delayed
                        # UI restore. Bound their complete joint allocation
                        # graph; require each external root's release fence to
                        # prevent reentrancy rather than assuming one chain.
                        tasks = list(candidate.tasks)
                        allocated = allocate(tasks)
                        require(
                            tasks[allocated] is _Empty.Task,
                            TaskControlFailure.TaskAlias,
                        )
                        require(target not in persistent, TaskControlFailure.Namespace)
                        tasks[allocated] = fresh(target, True)
                        owners[allocated].add(target)
                        after_aot.add(replace(candidate, tasks=tuple(tasks)))
                after_aot = {
                    result
                    for candidate in after_aot
                    for result in _animation_frontiers(candidate)
                }
                for result in after_aot:
                    if result.item_ui is not _Empty.ItemUI and result.item_ui.phase in (
                        _UIPhase.Active,
                        _UIPhase.Fenced,
                    ):
                        pending.extend(_ui_completion_frontiers(result))
                        continue
                    if result.message is _Empty.Message:
                        pending.append(result)
                    elif result.message.fresh:
                        # Source 2B applies STOP immediately. External kind4
                        # defers it until phase0, after this pass's sole AOT.
                        pending.append(
                            replace(
                                result,
                                message=replace(result.message, fresh=False),
                                stop6=True,
                                stop7=True,
                            )
                        )
                    else:
                        pending.append(result)
                        pending.append(
                            replace(
                                result,
                                message=_Empty.Message,
                                stop6=False,
                                stop7=result.message.saved7,
                            )
                        )

        for key, at in gotos:
            if not any(r["opcode"] == 6 for r in programs[key]["commands"]):
                continue
            slots = {slot for slot, roots in owners.items() if key in roots}
            require(len(slots) == 1, TaskControlFailure.ForeignConsumer)
            receiver, offset = goto_if_cell(next(iter(slots)), 0)
            require(
                receiver < 10 and offset in (0x60, 0x64, 0x68, 0x6C),
                TaskControlFailure.ForeignConsumer,
            )
            for root in owners[receiver]:
                # Sequential Sleep uses +A0 counters. Root END clears activity;
                # calls/structured loops/Break/Goto would consume other fields.
                require(
                    all(
                        r["opcode"] not in (3, 0x0D, 0x0F, 0x11, 0x13, 0x17, 0x18, 0x1A)
                        for r in programs[root]["commands"]
                    ),
                    TaskControlFailure.ForeignConsumer,
                )
            commands = programs[key]["commands"]
            ifs = [r for r in commands if r["opcode"] == 6]
            require(
                len(ifs) == 1
                and rows[key][ifs[0]["next"]]["opcode"] in (0x21, 0x23)
                and all(
                    r["opcode"] in ingress.atomic_opcodes
                    or r["opcode"] in (2, 6, 7, 8, 0x17)
                    for r in commands
                ),
                TaskControlFailure.ForeignConsumer,
            )
        derivation = _SourceTaskDerivation(
            hashlib.sha256(data).hexdigest(),
            programs_digest(programs),
            ingress,
            frozenset(dispatches),
            frozenset(gotos),
            tuple((slot, tuple(sorted(roots))) for slot, roots in owners.items()),
            len(seen),
        )
        return VerifiedSourceTaskControl(
            derivation.source_sha256,
            derivation.programs_sha256,
            derivation.ingress,
            derivation.dispatches,
            derivation.gotos,
            derivation.owners,
            derivation.frontier_count,
            derivation,
        )
    except _Rejected as error:
        return error.failure
    except (KeyError, IndexError, TypeError, ValueError):
        return TaskControlFailure.Binding
