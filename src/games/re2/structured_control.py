"""Shared finite structured-frame walk, without a loop-progress assumption."""

from dataclasses import dataclass
from enum import Enum

from games.re2.initializer_control_proof import native_switch_labels
from games.re2.native_control import (
    GOTO_FF_IF_BASE,
    IF_FRAME_BASE,
    ControlField,
    canonical_if_pointer,
)
from games.re2.script_control_limits import (
    NATIVE_IF_FRAME_COUNT,
    NATIVE_LOOP_FRAME_COUNT,
)


class ControlFrames(Enum):
    Strict = "existing entry frames"
    FreshPositive = "fresh positive-entry frames"
    Doors = "trusted normal door frames"
    NativeDoors = "bounded FF/FF native door frames"
    IdentityFiltering = "normal-engine identity filtering frames"
    NativeIdentityFiltering = "bounded native identity filtering frames"


class PredicateOutcome(Enum):
    Both = "both predicate outcomes"
    Matches = "predicate matches"
    DoesNotMatch = "predicate does not match"


class ControlFrameFailure(Enum):
    Unsupported = "source control frame or escaped pointer is unsupported"
    DoorControl = "source_control_or_write"
    DoorGotoDepth = "goto_depth_escape"
    DoorSwitchFrame = "switch_frame_missing"


@dataclass(frozen=True)
class StructuredControl:
    edges: tuple[tuple[int, tuple[int, ...]], ...]
    if_stores: tuple[tuple[int, int, int], ...]
    # Fields are relative to a root-depth task; callers add the actual call
    # depth using the same native formulas below, never a sampled task slot.
    break_reads: tuple[tuple[int, int], ...]
    states: int
    reached: frozenset[int]


@dataclass(frozen=True)
class NativeStructuredControl(StructuredControl):
    # Source offsets and field selectors are attached to actual task/depth
    # producers by native_entry_fields. This walk does not infer task ownership.
    accesses: tuple[tuple[int, ControlField, int, bool], ...]
    loop_reads: tuple[tuple[int, int, bool], ...]


def structured_control(
    data: bytes,
    program: dict,
    role: ControlFrames,
    *,
    predicates: tuple[tuple[int, PredicateOutcome], ...] = (),
) -> StructuredControl | ControlFrameFailure:
    assert type(role) is ControlFrames
    assert type(predicates) is tuple and all(
        type(row) is tuple
        and len(row) == 2
        and type(row[0]) is int
        and type(row[1]) is PredicateOutcome
        for row in predicates
    )
    assert not predicates or role in (ControlFrames.Doors, ControlFrames.NativeDoors)
    native = role in (ControlFrames.NativeDoors, ControlFrames.NativeIdentityFiltering)
    door = role in (ControlFrames.Doors, ControlFrames.NativeDoors)
    accesses, loop_reads = set(), set()
    outcomes = dict(predicates)
    assert len(outcomes) == len(predicates)
    rows = {row["offset"]: row for row in program["commands"]}
    pending, seen = [(program["entry"], (), (), IF_FRAME_BASE, -1)], set()
    edges, stores, breaks = {}, set(), set()

    def require(condition, failure=ControlFrameFailure.Unsupported):
        if not condition:
            raise ValueError(failure)

    def predicate_end(start, width):
        cursor, end = start, start + width
        require(width > 0)
        while cursor < end:
            require(cursor in rows)
            row = rows[cursor]
            packet = data[cursor : row["next"]]
            require(
                door
                and row["opcode"] in (0x21, 0x23, 0x3E, 0x50, 0x5E, 0x85)
                or row["kind"] == "flag_check"
                or row["opcode"] == 0x23
                and packet[1] == 0
                and packet[3] < 7
            )
            cursor = row["next"]
        require(cursor == end)
        return end

    try:
        while pending:
            position, conditions, loops, pointer, previous = pending.pop()
            state = (
                position,
                conditions,
                loops,
                pointer,
                previous
                if role
                in (
                    ControlFrames.FreshPositive,
                    ControlFrames.IdentityFiltering,
                    ControlFrames.NativeDoors,
                    ControlFrames.NativeIdentityFiltering,
                )
                else -1,
            )
            if state in seen:
                continue
            require(len(seen) < 16384 and position in rows)
            seen.add(state)
            edge_start = len(pending)
            row = rows[position]
            opcode, following = row["opcode"], row["next"]
            packet = data[position:following]

            def access(field, index=0, *, write):
                if native:
                    accesses.add((position, field, index, write))

            if native:
                access(ControlField.CallDepth, write=False)
                if row["kind"] != "end":
                    access(ControlField.ProgramCounter, write=False)
                    access(ControlField.ProgramCounter, write=True)
            if row["kind"] == "end":
                require(packet == b"\x01\0")
                continue
            if opcode == 3:
                access(ControlField.IfLevel, write=True)
                access(ControlField.LoopLevel, write=True)
                access(ControlField.IfPointer, write=True)
                require(
                    role
                    in (
                        ControlFrames.Strict,
                        ControlFrames.Doors,
                        ControlFrames.NativeDoors,
                    )
                )
                continue
            if opcode == 0x17:
                if native:
                    require(packet[1:4] == b"\xff\xff\0" and row["target"] in rows)
                    access(ControlField.IfLevel, write=True)
                    access(ControlField.LoopLevel, write=True)
                    access(ControlField.IfPointer, write=True)
                else:
                    require(not loops, ControlFrameFailure.DoorGotoDepth)
                    if role in (ControlFrames.Strict, ControlFrames.Doors):
                        require(not conditions, ControlFrameFailure.DoorGotoDepth)
                    else:
                        require(
                            packet[1:4] == b"\xff\xff\0"
                            and row["target"] == program["entry"]
                        )
                # FF resets the IF level and computes an absolute frame-relative
                # pointer. Repeating a Goto cannot accumulate pointer growth.
                pending.append((row["target"], (), (), GOTO_FF_IF_BASE))
            elif row["kind"] == "if":
                require(
                    len(conditions) < NATIVE_IF_FRAME_COUNT
                    and row["target"] > following
                )
                stores.add((position, pointer, row["target"]))
                access(ControlField.IfLevel, write=False)
                access(ControlField.IfLevel, write=True)
                access(ControlField.IfPointer, write=False)
                access(ControlField.IfPointer, write=True)
                access(ControlField.IfTarget, pointer, write=True)
                if native and pointer >= GOTO_FF_IF_BASE:
                    # Only this immediately following CK/CMP can consume the
                    # foreign store. SET, calls, yields and actor predicates
                    # deliberately do not preserve an atomic-store token.
                    test = rows[following]
                    test_packet = data[following : test["next"]]
                    require(test["opcode"] in (0x21, 0x23))
                    require(test["opcode"] != 0x21 or test_packet[3] in (0, 1))
                    require(
                        test["opcode"] != 0x23
                        or test_packet[1] == 0
                        and test_packet[3] < 7
                    )
                if (
                    role
                    in (ControlFrames.FreshPositive, ControlFrames.IdentityFiltering)
                    and pointer >= GOTO_FF_IF_BASE
                ):
                    # Escaped IF failures must consume their fresh store in the
                    # immediately following atomic CMP, before any task yield.
                    test = rows[following]
                    test_packet = data[following : test["next"]]
                    require(
                        test["opcode"] == 0x23
                        and test_packet[1] == 0
                        and test_packet[3] < 7
                    )
                if not door:
                    pending.append((row["target"], conditions, loops, pointer))
                # Door exclusion follows the predicate's actual continuations.
                # The older roles retain their conservative synthetic skip.
                pending.append(
                    (
                        following,
                        conditions
                        + (((row["target"], pointer),) if native else (row["target"],)),
                        loops,
                        pointer + 4,
                    )
                )
            elif (
                row["kind"] == "flag_check"
                or (
                    role
                    in (
                        ControlFrames.IdentityFiltering,
                        ControlFrames.NativeIdentityFiltering,
                    )
                    and opcode == 0x86
                )
                or opcode
                in (
                    0x23,
                    0x3E,
                    0x50,
                    0x5E,
                    0x85,
                )
            ):
                if (
                    role
                    in (ControlFrames.FreshPositive, ControlFrames.IdentityFiltering)
                    and pointer > GOTO_FF_IF_BASE
                    and conditions
                ):
                    # The failed predicate reads foreign scratch only on the
                    # same uninterrupted edge as its own preceding IF store.
                    require(previous == position - 4 and rows[previous]["opcode"] == 6)
                if native and conditions:
                    access(ControlField.IfLevel, write=False)
                    access(ControlField.IfPointer, write=False)
                # Missing knowledge retains both paths; only the source-bound
                # door caller may provide an immutable fixed-scenario result.
                outcome = outcomes.get(position, PredicateOutcome.Both)
                if outcome is not PredicateOutcome.DoesNotMatch:
                    pending.append((following, conditions, loops, pointer))
                if conditions and outcome is not PredicateOutcome.Matches:
                    if native:
                        # Return reconstructs canonical storage. A logical
                        # target alone cannot justify that cell's value.
                        require(conditions[-1][1] == pointer - 4)
                        if pointer > GOTO_FF_IF_BASE:
                            require(
                                previous == position - 4
                                and rows[previous]["opcode"] == 6
                            )
                            require(opcode in (0x21, 0x23))
                        access(ControlField.IfTarget, pointer - 4, write=False)
                        access(ControlField.IfPointer, write=True)
                        access(ControlField.IfLevel, write=True)
                    pending.append(
                        (
                            conditions[-1][0] if native else conditions[-1],
                            conditions[:-1],
                            loops,
                            pointer - 4,
                        )
                    )
            elif opcode in (7, 8):
                require(
                    bool(conditions)
                    and following == (conditions[-1][0] if native else conditions[-1])
                )
                access(ControlField.IfLevel, write=False)
                access(ControlField.IfLevel, write=True)
                access(ControlField.IfPointer, write=False)
                access(ControlField.IfPointer, write=True)
                target = row["target"] if opcode == 7 else following
                require(target >= following)
                pending.append((target, conditions[:-1], loops, pointer - 4))
            elif opcode == 9:
                require(packet[1] == 0x0A and len(loops) < NATIVE_LOOP_FRAME_COUNT)
                pending.append((following, conditions, loops, pointer))
            elif opcode in (0x0D, 0x0F, 0x11):
                require(len(loops) < NATIVE_LOOP_FRAME_COUNT)
                limit = following + int.from_bytes(packet[2:4], "little", signed=True)
                require(following < limit and limit in rows)
                body = (
                    predicate_end(following, packet[1]) if opcode == 0x0F else following
                )
                require(body in rows and body <= limit)
                for field in (ControlField.LoopLevel, ControlField.IfLevel):
                    access(field, write=False)
                access(ControlField.LoopLevel, write=True)
                for field in (
                    ControlField.LoopStart,
                    ControlField.LoopEnd,
                    ControlField.SavedIf,
                ):
                    access(field, len(loops), write=True)
                if opcode == 0x0D:
                    access(ControlField.LoopCount, len(loops), write=True)
                if native and opcode == 0x0F:
                    # An overlapping writer requires the native nested
                    # predicate to consume this fresh end without yielding.
                    # The task attachment checks that overlap separately.
                    loop_reads.add(
                        (
                            position,
                            len(loops),
                            all(
                                rows[at]["opcode"] in (0x21, 0x23)
                                for at in rows
                                if following <= at < body
                            ),
                        )
                    )
                    access(ControlField.LoopEnd, len(loops), write=False)
                loop = opcode, position, body, limit, conditions, pointer
                # All count values, including zero and FFFF, retain both skip
                # and repeat edges. Numeric Copy grants no termination fact.
                if opcode != 0x11:
                    pending.append((limit, conditions, loops, pointer))
                pending.append((body, conditions, loops + (loop,), pointer))
            elif opcode in (0x0E, 0x10, 0x12):
                require(bool(loops))
                kind, header, body, limit, saved_conditions, saved_pointer = loops[-1]
                require(
                    (kind, opcode) in ((0x0D, 0x0E), (0x0F, 0x10), (0x11, 0x12))
                    and conditions == saved_conditions
                    and pointer == saved_pointer
                )
                access(ControlField.LoopLevel, write=False)
                access(ControlField.LoopLevel, write=True)
                access(ControlField.LoopStart, len(loops) - 1, write=False)
                if opcode == 0x0E:
                    access(ControlField.LoopCount, len(loops) - 1, write=False)
                    access(ControlField.LoopCount, len(loops) - 1, write=True)
                if opcode == 0x12:
                    after = predicate_end(following, packet[1])
                    require(after == limit)
                    pending.extend(
                        (
                            (after, conditions, loops[:-1], pointer),
                            (body, conditions, loops, pointer),
                        )
                    )
                elif opcode == 0x10:
                    require(following == limit)
                    pending.append((header, conditions, loops[:-1], pointer))
                else:
                    require(following == limit)
                    pending.extend(
                        (
                            (following, conditions, loops[:-1], pointer),
                            (body, conditions, loops, pointer),
                        )
                    )
            elif opcode == 0x18 and native:
                access(ControlField.CallReturn, write=True)
                access(ControlField.CallDepth, write=True)
                access(ControlField.IfPointer, write=True)
                # The separately attached callee has fresh IF/loop levels at
                # depth+1. Its END/Return rebuilds this canonical caller pointer.
                pending.append(
                    (
                        following,
                        conditions,
                        loops,
                        canonical_if_pointer(len(conditions) - 1),
                    )
                )
            elif opcode == 0x19 and native:
                # Explicit early Return needs its own interprocedural edges;
                # the bounded source contract does not invent a continuation.
                raise ValueError("explicit return entry domain")
            elif opcode == 0x13:
                require(len(loops) < NATIVE_LOOP_FRAME_COUNT)
                end, labels = native_switch_labels(data, position, program["limit"])
                require(end in rows and all(at in rows for at in labels))
                require(
                    all(
                        rows[at]["opcode"]
                        in (
                            (0x14, 0x15)
                            if role
                            in (
                                ControlFrames.FreshPositive,
                                ControlFrames.IdentityFiltering,
                                ControlFrames.Doors,
                                ControlFrames.NativeDoors,
                                ControlFrames.NativeIdentityFiltering,
                            )
                            else (0x14,)
                        )
                        for at in labels[:-1]
                    )
                )
                require(rows[labels[-1]]["opcode"] == 0x16)
                access(ControlField.LoopLevel, write=False)
                access(ControlField.IfLevel, write=False)
                access(ControlField.LoopLevel, write=True)
                access(ControlField.LoopEnd, len(loops), write=True)
                access(ControlField.SavedIf, len(loops), write=True)
                loop = opcode, position, labels, end, conditions, pointer
                pending.append((labels[-1], conditions, loops + (loop,), pointer))
                pending.extend(
                    (rows[at]["next"], conditions, loops + (loop,), pointer)
                    for at in labels[:-1]
                )
            elif (
                opcode == 0x14
                or opcode == 0x15
                and role
                in (
                    ControlFrames.FreshPositive,
                    ControlFrames.IdentityFiltering,
                    ControlFrames.Doors,
                    ControlFrames.NativeDoors,
                    ControlFrames.NativeIdentityFiltering,
                )
            ):
                require(
                    bool(loops) and loops[-1][0] == 0x13,
                    ControlFrameFailure.DoorSwitchFrame,
                )
                require(position in loops[-1][2])
                pending.append((following, conditions, loops, pointer))
            elif opcode in (0x16, 0x1A):
                require(
                    bool(loops) and loops[-1][0] == 0x13,
                    ControlFrameFailure.DoorSwitchFrame,
                )
                _, _, labels, end, saved_conditions, saved_pointer = loops[-1]
                require(conditions == saved_conditions and pointer == saved_pointer)
                require(opcode != 0x16 or position == labels[-1])
                access(ControlField.LoopLevel, write=False)
                access(ControlField.LoopLevel, write=True)
                if opcode == 0x1A:
                    access(ControlField.SavedIf, len(loops) - 1, write=False)
                    access(ControlField.IfLevel, write=True)
                    access(ControlField.LoopEnd, len(loops) - 1, write=False)
                    breaks.add((position, len(loops) - 1))
                # Break restores only the saved IF byte. Unlike Return it
                # leaves the current IF pointer unchanged in the native code.
                pending.append((end, conditions, loops[:-1], pointer))
            elif opcode in (0x0A, 0x15):
                raise ValueError("standalone control tail")
            else:
                pending.append((following, conditions, loops, pointer))
            for index in range(edge_start, len(pending)):
                pending[index] = (*pending[index], position)
            edges.setdefault(position, set()).update(s[0] for s in pending[edge_start:])
        values = (
            tuple(
                (at, tuple(sorted(targets))) for at, targets in sorted(edges.items())
            ),
            tuple(sorted(stores)),
            tuple(sorted(breaks)),
            len(seen),
            frozenset(state[0] for state in seen),
        )
        if native:
            return NativeStructuredControl(
                *values,
                tuple(sorted(accesses, key=lambda r: (r[0], r[1].value, r[2], r[3]))),
                tuple(sorted(loop_reads)),
            )
        return StructuredControl(*values)
    except ValueError as error:
        if door:
            if error.args and error.args[0] in (
                ControlFrameFailure.DoorGotoDepth,
                ControlFrameFailure.DoorSwitchFrame,
            ):
                return error.args[0]
            return ControlFrameFailure.DoorControl
        return ControlFrameFailure.Unsupported
    except (KeyError, IndexError, TypeError):
        if door:
            return ControlFrameFailure.DoorControl
        return ControlFrameFailure.Unsupported
