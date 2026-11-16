"""Evaluate room scripts against fresh game state. RE2-EVAL-001.

The interpreter runs a game-neutral program model compiled from owned room
scripts. It trusts the unmodified engine to execute those scripts normally,
as approved for RE2 presence and door tracking, and reports what entering a
room would create with the flags and variables that are current now.

A condition the reader cannot evaluate forks into both outcomes. Conditions
that depend only on how the player arrives, such as the entry floor or camera,
produce alternative outcomes that all exist in the room. Other unreadable
conditions taint the values and interactions written under them; outcomes
that differ through tainted writes stay unresolved instead of being guessed.
Unsupported control flow makes the whole evaluation Unsupported.

Instruction rows are lists ``[offset, next, op, *args]``:

- ``loop end count``: count -1 unless a constant For count can skip the body
- ``if end`` / ``else target`` / ``loop_end`` / ``case`` /
  ``break`` / ``goto target`` / ``end`` / ``invalid``
- ``switch end variable [[label, value], ...]`` with value None for Default
- ``ck bank bit expected``
- ``cmp variable operation value`` with ==, >, >=, <, <=, != and bit test
- ``has item``: the player carries an item type
- ``cond approach``: an unreadable condition; approach 1 means it depends only
  on how the player arrives or acts
- ``set bank bit operation`` with 0 clear, 1 set, 7 toggle
- ``var variable kind argument``: kind 0 stores the constant argument, 1
  copies variable ``argument``, 2 stores an unreadable result and 3 an actor
  member, which depends on how the player arrives or acts
- ``calc variable operator value`` / ``calc2 variable operator source``
- ``item slot sat type amount gid`` / ``door slot sat``
- ``aot slot kind sat call`` (``call`` is a procedure number or -1)
- ``reset slot kind sat call type amount gid`` (item fields -1 unless an item)
- ``aot_on slot`` / ``gosub proc`` / ``exec proc`` (-1 when unresolved)
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum

# Interaction kinds shared by the RE2 and RE3 engines.
KIND_DOOR = 1
KIND_ITEM = 2

# Bounds keep a pathological script from stalling the poll loop. Exceeding
# either reports Unsupported, never a partial result.
MAX_TERMINALS = 4096
MAX_STEPS = 200_000
# Total work for one interpreter, across every path.
MAX_TOTAL_STEPS = 2_000_000
# Distinct states one join point keeps exact. Beyond this, arriving paths
# forget every value any path arriving there wrote, which then reads as a
# tainted unknown, so independent unread conditions cannot multiply paths
# without bound.
JOIN_WIDEN = 64
# Loops and backward jumps run at most this many times per path. Their exit is
# assumed to happen eventually, as it does for normal script waits.
LOOP_LIMIT = 2
CALL_DEPTH = 16


@dataclass(frozen=True)
class Item:
    creator: int
    sat: int
    item_type: int
    amount: int
    global_id: int


@dataclass(frozen=True)
class Door:
    creator: int
    sat: int


@dataclass(frozen=True)
class Interaction:
    kind: int
    sat: int
    call: int
    # A door or item replaced in place keeps its creator for marker binding.
    replaced: Door | Item | None


Descriptor = Item | Door | Interaction


class Support(Enum):
    Supported = "supported"
    Unsupported = "unsupported"


FlagReader = Callable[[int, int], bool | None]
VariableReader = Callable[[int], int | None]


@dataclass(frozen=True)
class GameState:
    """Fresh flags and variables as a room would see them on entry.

    Readers return None for values that cannot be read. Approach variables and
    banks hold unreadable values that depend only on how the player arrives or
    acts, such as the entry camera, the previous room or a prompt's answer.
    """

    flag: FlagReader
    variable: VariableReader
    approach_variables: frozenset[int]
    approach_banks: frozenset[int]
    # Whether the player carries an item type, or None when unreadable.
    inventory: Callable[[int], bool | None]


@dataclass(frozen=True)
class EngineTasks:
    """Procedures a game engine runs without a script starting them."""

    # Run once, in order, while the room loads.
    roots: tuple[str, ...]
    # Restarted by the engine while the room runs.
    repeating: frozenset[int]


_COMPARE = (
    lambda a, b: a == b,
    lambda a, b: a > b,
    lambda a, b: a >= b,
    lambda a, b: a < b,
    lambda a, b: a <= b,
    lambda a, b: a != b,
    lambda a, b: a & b != 0,
)


def _calculate(operator: int, current: int | None, operand: int | None) -> int | None:
    """Apply a native Calc operator to signed 16-bit values.

    Division, modulo and the logical right shift differ between revisions for
    negative inputs, and a zero divisor traps, so those cases stay unread.
    """
    if current is None or operand is None:
        return None
    if operator == 0:
        result = current + operand
    elif operator == 1:
        result = current - operand
    elif operator == 2:
        result = current * operand
    elif operator in (3, 4) and current >= 0 and operand > 0:
        result = current // operand if operator == 3 else current % operand
    elif operator == 5:
        result = current | operand
    elif operator == 6:
        result = current & operand
    elif operator == 7:
        result = current ^ operand
    elif operator == 8:
        result = ~current
    elif operator == 9 and 0 <= operand < 32:
        result = current << operand
    elif (
        operator in (10, 11) and 0 <= operand < 32 and (operator == 11 or current >= 0)
    ):
        result = current >> operand
    else:
        return None
    result &= 0xFFFF
    return result - 0x10000 if result & 0x8000 else result


@dataclass
class _Frame:
    proc: str
    index: int
    # (kind, end offset, opening row index, tainted)
    blocks: list[tuple[str, int, int, bool]]
    # A task started under unreadable game state; calls keep their callers'
    # frames, so only task starts need this.
    tainted: bool
    # Loop opener or backward Goto offset -> (iterations, first offset, last
    # offset) of the loop region. A count lasts while execution stays in its
    # region, so a fresh entry or a new call runs the loop again.
    loops: dict[int, tuple[int, int, int]] = field(default_factory=dict)


@dataclass
class _Path:
    frames: list[_Frame]
    # Each written value carries whether an unreadable state condition
    # controlled the write.
    slots: dict[int, tuple[Descriptor, bool]]
    flags: dict[tuple[int, int], tuple[bool | None, bool]]
    variables: dict[int, tuple[int | None, bool]]
    # Tasks to start, with whether unreadable game state started them.
    pending: list[tuple[int, bool]]
    executed: dict[int, int]
    triggers: set[int]
    # (gid, type, amount) for every item a create or Reset wrote.
    created: set[tuple[int, int, int]]
    # (gid, type, amount, tainted) handed over by Aot_on, bypassing
    # activation masks.
    dispatched: set[tuple[int, int, int, bool]]
    # Source offset -> (value, width, tainted) stored by Work_copy.
    patches: dict[int, tuple[int | None, int, bool]]
    # Banks written at a bit no reader can determine.
    unknown_banks: set[int]
    # Written variables whose unread values depend only on how the player
    # arrives or acts, such as a copied actor member.
    arrival: set[int]
    # Tasks waiting on another task, as their call stacks resuming at the wait
    # loop's head.
    suspended: set[Continuation]
    # An unreadable game-state branch could leave this procedure or task
    # early, so everything after it depends on that game state.
    diverged: bool = False
    steps: int = 0

    def fork(self) -> _Path:
        return _Path(
            [
                _Frame(f.proc, f.index, list(f.blocks), f.tainted, dict(f.loops))
                for f in self.frames
            ],
            dict(self.slots),
            dict(self.flags),
            dict(self.variables),
            list(self.pending),
            dict(self.executed),
            set(self.triggers),
            set(self.created),
            set(self.dispatched),
            dict(self.patches),
            set(self.unknown_banks),
            set(self.arrival),
            set(self.suspended),
            self.diverged,
            self.steps,
        )

    def tainted(self) -> bool:
        return self.diverged or any(
            frame.tainted or any(block[3] for block in frame.blocks)
            for frame in self.frames
        )

    def outcome(self, taint: bool) -> tuple:
        """Effects that tell finished paths apart, with or without taint."""

        def values(written: dict) -> tuple:
            return tuple(
                sorted(
                    (key, value if taint else value[:-1])
                    for key, value in written.items()
                )
            )

        return (
            values(self.slots),
            values(self.flags),
            values(self.variables),
            frozenset(self.triggers),
            frozenset(self.created),
            frozenset(item if taint else item[:3] for item in self.dispatched),
            values(self.patches),
            frozenset(self.unknown_banks),
            frozenset(self.arrival),
            frozenset(self.suspended),
            tuple(
                sorted(self.pending if taint else {proc for proc, _ in self.pending})
            ),
            self.diverged and taint,
        )

    def key(self, taint: bool) -> tuple:
        return (
            tuple(
                (
                    f.proc,
                    f.index,
                    tuple(block if taint else block[:3] for block in f.blocks),
                    f.tainted and taint,
                    tuple(sorted(f.loops.items())),
                )
                for f in self.frames
            ),
            tuple(self.pending if taint else [proc for proc, _ in self.pending]),
            tuple(sorted(self.executed.items())),
            self.outcome(taint),
        )


# A join arrival that left a flag, variable or patch as game state.
_UNWRITTEN = object()


def _wait_reads(
    program: dict[str, list[list]], proc: str, head: int
) -> tuple[set[tuple[int, int]], set[int]]:
    """Flags and variables a wait loop and the procedures it calls read.

    The loop runs from row ``head`` to the backward Goto that returns there.
    """
    rows = program[proc]
    offsets = [row[0] for row in rows]
    # A Goto may target an unmodeled command; it resumes at the next row.
    end = next(
        index
        for index in range(head, len(rows))
        if rows[index][2] == "goto" and bisect_left(offsets, rows[index][3]) == head
    )
    flags: set[tuple[int, int]] = set()
    variables: set[int] = set()
    pending = [rows[head : end + 1]]
    called: set[int] = set()
    while pending:
        for _, _, op, *args in pending.pop():
            if op == "ck":
                flags.add((args[0], args[1]))
            elif op == "cmp":
                variables.add(args[0])
            elif op == "switch":
                variables.add(args[1])
            elif op == "gosub" and args[0] not in called:
                called.add(args[0])
                pending.append(program[f"main:{args[0]}"])
    return flags, variables


# A suspended task: its frames as (procedure, row index, blocks, tainted).
Continuation = tuple[tuple[str, int, tuple[tuple[str, int, int, bool], ...], bool], ...]


def _fresh_path(proc: str) -> _Path:
    return _Path(
        [_Frame(proc, 0, [], False)],
        {},
        {},
        {},
        [],
        {},
        set(),
        set(),
        set(),
        {},
        set(),
        set(),
        set(),
    )


class _Unsupported(Exception):
    pass


class _Interpreter:
    def __init__(
        self,
        program: dict[str, list[list]],
        state: GameState,
        entry: bool,
    ) -> None:
        self.program = program
        # Entry runs the room's automatic tasks on a freshly loaded source,
        # which has no Work_copy patches yet, and runs started tasks in order
        # on the same path. Later analysis covers procedures that may run after
        # any patch, so patched fields are unread. It only needs what each task
        # can create or start, so it queues started tasks instead of
        # multiplying every interleaving, and merges paths that differ only in
        # taint, which never changes control flow.
        self.entry = entry
        self.offsets = {
            name: [row[0] for row in rows] for name, rows in program.items()
        }
        self.state = state
        self.patch_targets = frozenset(
            row[3] for rows in program.values() for row in rows if row[2] == "patch"
        )
        self.written: set[tuple[int, int]] = set()
        self.written_variables: set[int] = set()
        self.written_banks: set[int] = set()
        self.total_steps = 0
        # Paths that reach a join point in identical states continue once.
        # Without merging, independent unread conditions multiply outcomes.
        self.joins = {name: self._joins(rows) for name, rows in program.items()}
        self.seen: set[tuple] = set()
        # Join -> arrivals, and every flag, variable and patch target that
        # arriving paths had written.
        self.join_counts: dict[tuple[str, int], int] = {}
        self.join_writes: dict[tuple[str, int], tuple[dict, dict, dict]] = {}
        self.exit_cache: dict[tuple[str, int, int], bool] = {}

    def _joins(self, rows: list[list]) -> frozenset[int]:
        offsets = [row[0] for row in rows]
        targets = set()
        for row in rows:
            if row[2] in ("if", "else", "goto", "loop"):
                targets.add(row[3])
            if row[2] == "loop":
                # Loop_end returns to the body's first row.
                targets.add(row[1])
            elif row[2] == "switch":
                targets.update((row[3], *(label for label, _ in row[5])))
        return frozenset(bisect_left(offsets, target) for target in targets)

    def _index(self, proc: str, offset: int) -> int:
        # The compiler checked that every target is a command boundary and
        # omitted commands without modeled effects, so continue at the next
        # kept row. Running past the last row is reported by the stepper.
        return bisect_left(self.offsets[proc], offset)

    def _flag(self, path: _Path, bank: int, bit: int) -> tuple[bool | None, bool]:
        if (bank, bit) in path.flags:
            return path.flags[bank, bit]
        if bank in path.unknown_banks:
            return None, True
        return self.state.flag(bank, bit), False

    def _operand(
        self, path: _Path, offset: int, signed: bool, original: int
    ) -> tuple[int | None, bool]:
        """Return a source operand after any Work_copy patch, with taint."""
        if offset in path.patches:
            value, width, tainted = path.patches[offset]
            if value is None:
                return None, True
            # Patch the low byte of the operand's 16-bit encoding.
            value = original & 0xFF00 | value & 0xFF if width == 1 else value & 0xFFFF
            if signed and value & 0x8000:
                value -= 0x10000
            return value, tainted
        if offset in self.patch_targets and not self.entry:
            return None, True
        return original, False

    def _variable(self, path: _Path, index: int) -> tuple[int | None, bool]:
        if index in path.variables:
            return path.variables[index]
        return self.state.variable(index), False

    def _arrival(self, path: _Path, index: int) -> bool:
        """Whether the variable's unread value depends only on arrival."""
        if index in path.variables:
            return index in path.arrival
        return index in self.state.approach_variables

    def run(self, start: list[_Path]) -> list[_Path]:
        done, work, finished = [], list(start), set()
        self.seen.clear()
        self.join_counts.clear()
        self.join_writes.clear()
        while work:
            path = work.pop()
            result = self._step_until_done(path, work)
            if result is not None:
                outcome = result.outcome(self.entry)
                if outcome in finished:
                    continue
                finished.add(outcome)
                done.append(result)
                if len(done) > MAX_TERMINALS:
                    raise _Unsupported("too many script outcomes")
        return done

    def _start_task(self, path: _Path, proc: int, tainted: bool) -> bool:
        name = f"main:{proc}"
        if name not in self.program:
            raise _Unsupported(f"missing procedure {name}")
        count = path.executed.get(proc, 0)
        if count >= LOOP_LIMIT:
            return False
        path.executed[proc] = count + 1
        path.frames = [_Frame(name, 0, [], tainted)]
        return True

    def _exits(self, proc: str, first: int, end: int) -> bool:
        """Whether rows from ``first`` up to offset ``end`` can leave early.

        A terminator, a jump out of the region or a Break leaves the code that
        follows the region unexecuted on that branch.
        """
        key = (proc, first, end)
        cached = self.exit_cache.get(key)
        if cached is not None:
            return cached
        rows = self.program[proc]
        begin = rows[first][0] if first < len(rows) else end
        result = False
        for offset, following, op, *args in rows[first:]:
            if offset >= end:
                break
            if op in ("end", "break"):
                result = True
            elif op in ("goto", "else") and not begin <= args[0] <= end:
                # The region's own closing Else lands on its else body.
                result = not (op == "else" and following == end)
            if result:
                break
        self.exit_cache[key] = result
        return result

    def _condition(
        self, path: _Path, offset: int, op: str, args: list
    ) -> tuple[bool | None, bool, bool]:
        """Return (value, approach, tainted) for one predicate row."""
        if op == "ck":
            bit, patch_taint = self._operand(path, offset + 2, False, args[1])
            if bit is None:
                return None, False, True
            flag, tainted = self._flag(path, args[0], bit & 0xFF)
            approach = args[0] in self.state.approach_banks
            return (
                None if flag is None else flag == bool(args[2]),
                approach,
                tainted or patch_taint,
            )
        if op == "cmp":
            index, index_taint = self._operand(path, offset + 2, False, args[0])
            value, value_taint = self._operand(path, offset + 4, True, args[2])
            if index is None or value is None:
                return None, False, True
            current, tainted = self._variable(path, index & 0xFF)
            tainted = tainted or index_taint or value_taint
            approach = self._arrival(path, index & 0xFF)
            if args[1] >= len(_COMPARE):
                # The native handler returns false for other operators.
                return False, approach, tainted
            if current is None:
                return None, approach, tainted
            return _COMPARE[args[1]](current, value), approach, tainted
        if op == "has":
            present = self.state.inventory(args[0])
            return present, False, False
        return None, args[0] == 1, False

    def _step_until_done(self, path: _Path, work: list[_Path]) -> _Path | None:
        while True:
            if not path.frames:
                while self.entry and path.pending:
                    if self._start_task(path, *path.pending.pop(0)):
                        break
                else:
                    return path
            path.steps += 1
            self.total_steps += 1
            if path.steps > MAX_STEPS or self.total_steps > MAX_TOTAL_STEPS:
                raise _Unsupported("script evaluation step limit")
            frame = path.frames[-1]
            rows = self.program[frame.proc]
            if frame.index >= len(rows):
                # Procedures end with an explicit terminator. Running off the
                # decoded range means trailing bytes were not understood.
                raise _Unsupported(f"{frame.proc} ends without a terminator")
            offset, _, op, *args = rows[frame.index]
            while frame.blocks and offset >= frame.blocks[-1][1]:
                frame.blocks.pop()
            if frame.loops:
                # Leaving a loop's region ends its iterations.
                frame.loops = {
                    key: loop
                    for key, loop in frame.loops.items()
                    if loop[1] <= offset <= loop[2]
                }
            if frame.index in self.joins[frame.proc]:
                key = path.key(self.entry)
                if key in self.seen:
                    return None
                join = (frame.proc, frame.index)
                self.join_counts[join] = self.join_counts.get(join, 0) + 1
                observed = self.join_writes.setdefault(join, ({}, {}, {}))
                # A variable's arrival classification is part of its value.
                written = (
                    path.flags,
                    {
                        index: (value, index in path.arrival, taint)
                        for index, (value, taint) in path.variables.items()
                    },
                    path.patches,
                )
                for values, seen in zip(written, observed):
                    for name in values.keys() | seen.keys():
                        # An arrival that did not write it reads game state.
                        seen.setdefault(
                            name,
                            {_UNWRITTEN} if self.join_counts[join] > 1 else set(),
                        ).add(values.get(name, _UNWRITTEN))
                if self.join_counts[join] > JOIN_WIDEN:
                    widened = []
                    for seen in observed:
                        kept = {}
                        for name, values in seen.items():
                            agreed = {value[:-1] for value in values - {_UNWRITTEN}}
                            if _UNWRITTEN not in values and len(agreed) == 1:
                                # Every arriving path wrote this same value.
                                taint = any(value[-1] for value in values)
                                kept[name] = (*next(iter(agreed)), taint)
                            elif self.entry:
                                # Arrivals disagree, so it becomes a tainted
                                # unknown and paths differing in it merge.
                                kept[name] = (None, *next(iter(agreed))[1:], True)
                            # Later analysis treats every value the room writes
                            # as unread, so dropping a disagreed one reads the
                            # same.
                        widened.append(kept)
                    path.flags, variables, path.patches = widened
                    path.variables = {
                        index: (value, taint)
                        for index, (value, _, taint) in variables.items()
                    }
                    path.arrival = {
                        index
                        for index, (value, arrival, _) in variables.items()
                        if arrival and value is None
                    }
                    key = path.key(self.entry)
                    if key in self.seen:
                        return None
                self.seen.add(key)
            nxt = frame.index + 1
            tainted = path.tainted()
            if op == "end":
                path.frames.pop()
                if path.frames:
                    path.frames[-1].index += 1
                continue
            if op == "if":
                frame.blocks.append(("if", args[0], frame.index, False))
            elif op in ("ck", "cmp", "cond", "has"):
                value, approach, read_taint = self._condition(path, offset, op, args)
                if value is None:
                    other = path.fork()
                    # Unreadable game state taints both branches until they
                    # join. Arrival-dependent branches are alternatives. Later
                    # analysis reports only effects, which taint never changes.
                    taint = (read_taint or not approach) and self.entry
                    if taint:
                        self._diverge(path, other)
                    self._fail(other, taint)
                    work.append(other)
                    if taint:
                        self._taint_block(path)
                elif not value:
                    self._fail(path, read_taint and self.entry)
                    continue
                elif read_taint and self.entry:
                    self._taint_block(path)
            elif op == "else":
                if not frame.blocks or frame.blocks[-1][0] != "if":
                    raise _Unsupported("else outside an if block")
                frame.blocks.pop()
                nxt = self._index(frame.proc, args[0])
            elif op == "loop":
                end, count = args
                if count == 0:
                    # The native For handler skips a zero-count body.
                    nxt = self._index(frame.proc, end)
                else:
                    frame.blocks.append(("loop", end, frame.index, False))
            elif op == "loop_end":
                if not frame.blocks or frame.blocks[-1][0] != "loop":
                    raise _Unsupported("loop end outside a loop")
                _, end, start, _ = frame.blocks[-1]
                opener = rows[start][0]
                count = frame.loops.get(opener, (0,))[0] + 1
                if count < LOOP_LIMIT:
                    frame.loops[opener] = (count, opener, end - 1)
                    nxt = start + 1
                else:
                    # Forget the count on exit so later joins can merge.
                    frame.loops.pop(opener, None)
                    frame.blocks.pop()
                    nxt = self._index(frame.proc, end)
            elif op == "switch":
                end, variable, labels = args
                current, read_taint = self._variable(path, variable)
                if current is not None:
                    # The native selector scans labels in order and stops at
                    # the first matching case or at Default.
                    chosen = [
                        next(
                            (
                                label
                                for label, value in labels
                                if value is None or value == current
                            ),
                            end,
                        )
                    ]
                else:
                    chosen = [label for label, _ in labels]
                    if all(value is not None for _, value in labels):
                        chosen.append(end)
                taint = self.entry and (
                    read_taint
                    or (current is None and not self._arrival(path, variable))
                )
                if (
                    taint
                    and len(chosen) > 1
                    and self._exits_besides_breaks(frame.proc, frame.index + 1, end)
                ):
                    # A case can leave early, so code after the switch
                    # depends on the unread selector.
                    path.diverged = True
                for label in chosen[1:]:
                    other = path.fork()
                    other.frames[-1].blocks.append(("switch", end, frame.index, taint))
                    other.frames[-1].index = self._index(frame.proc, label)
                    work.append(other)
                frame.blocks.append(("switch", end, frame.index, taint))
                nxt = self._index(frame.proc, chosen[0])
            elif op == "break":
                while frame.blocks and frame.blocks[-1][0] not in ("switch", "loop"):
                    frame.blocks.pop()
                if not frame.blocks:
                    raise _Unsupported("break outside a loop or switch")
                _, end, start, _ = frame.blocks.pop()
                frame.loops.pop(rows[start][0], None)
                nxt = self._index(frame.proc, end)
            elif op == "goto":
                target = args[0]
                if target <= offset:
                    count = frame.loops.get(offset, (0,))[0] + 1
                    frame.loops[offset] = (count, target, offset)
                    if count >= LOOP_LIMIT:
                        # A repeated backward jump is a wait. Continue as if
                        # the enclosing condition eventually stopped holding.
                        del frame.loops[offset]
                        if not any(
                            block[0] in ("if", "else", "loop") for block in frame.blocks
                        ):
                            # No condition encloses the jump, so the task waits
                            # until another task changes what it waits on, such
                            # as a Switch selector. Later analysis resumes it at
                            # the loop head with every value the room writes
                            # unread; what ran before the wait does not repeat.
                            head = self._index(frame.proc, target)
                            path.suspended.add(
                                (
                                    *(
                                        (f.proc, f.index, tuple(f.blocks), f.tainted)
                                        for f in path.frames[:-1]
                                    ),
                                    (
                                        frame.proc,
                                        head,
                                        # Blocks opened inside the loop close
                                        # before its head.
                                        tuple(b for b in frame.blocks if b[2] < head),
                                        frame.tainted,
                                    ),
                                )
                            )
                            path.frames.clear()
                            continue
                        self._fail(path, False)
                        continue
                nxt = self._index(frame.proc, target)
                # Blocks that open at or after a backward target are entered
                # again from their opening command.
                frame.blocks = [block for block in frame.blocks if block[2] < nxt]
            elif op == "case":
                pass
            elif op == "set":
                bank, bit, operation = args
                bit, patch_taint = self._operand(path, offset + 2, False, bit)
                if bit is None:
                    # A bit no reader can determine may hit any flag of the
                    # bank, so all its unwritten flags become unread.
                    self.written_banks.add(bank)
                    path.unknown_banks.add(bank)
                    path.flags = {
                        key: value
                        for key, value in path.flags.items()
                        if key[0] != bank
                    }
                    frame.index = nxt
                    continue
                bit &= 0xFF
                tainted = tainted or patch_taint
                self.written.add((bank, bit))
                if operation in (0, 1):
                    path.flags[bank, bit] = (operation == 1, tainted)
                elif operation == 7:
                    value, read_taint = self._flag(path, bank, bit)
                    path.flags[bank, bit] = (
                        None if value is None else not value,
                        tainted or read_taint,
                    )
                else:
                    path.flags[bank, bit] = (None, True)
            elif op == "var":
                variable, kind, argument = args
                self.written_variables.add(variable)
                arrival = False
                if kind == 0:
                    path.variables[variable] = (argument, tainted)
                elif kind == 1:
                    value, read_taint = self._variable(path, argument)
                    arrival = value is None and self._arrival(path, argument)
                    path.variables[variable] = (value, tainted or read_taint)
                else:
                    # Comparisons on unread results fork as game state, and on
                    # actor members as alternative arrivals.
                    arrival = kind == 3
                    path.variables[variable] = (None, tainted)
                if arrival:
                    path.arrival.add(variable)
                else:
                    path.arrival.discard(variable)
            elif op in ("calc", "calc2"):
                variable, operator, argument = args
                self.written_variables.add(variable)
                current, read_taint = self._variable(path, variable)
                inputs = [(current, self._arrival(path, variable))]
                if op == "calc":
                    operand, operand_taint = argument, False
                else:
                    operand, operand_taint = self._variable(path, argument)
                    inputs.append((operand, self._arrival(path, argument)))
                result = _calculate(operator, current, operand)
                path.variables[variable] = (
                    result,
                    tainted or read_taint or operand_taint,
                )
                # The result depends only on arrival when every unread input
                # does; a known input the operator rejects is not one.
                unread = [arrival for value, arrival in inputs if value is None]
                if result is None and unread and all(unread):
                    path.arrival.add(variable)
                else:
                    path.arrival.discard(variable)
            elif op == "item":
                slot, sat, item_type, amount, gid = args
                path.slots[slot] = (Item(offset, sat, item_type, amount, gid), tainted)
                path.created.add((gid, item_type, amount))
            elif op == "door":
                path.slots[args[0]] = (Door(offset, args[1]), tainted)
            elif op == "aot":
                slot, kind, sat, call = args
                path.slots[slot] = (Interaction(kind, sat, call, None), tainted)
                if call >= 0:
                    path.triggers.add(call)
            elif op == "reset":
                slot, kind, sat, call, item_type, amount, gid = args
                previous = path.slots.get(slot, (None, False))[0]
                base = (
                    previous.replaced if isinstance(previous, Interaction) else previous
                )
                if kind == KIND_ITEM:
                    creator = base.creator if base is not None else -1
                    descriptor = Item(creator, sat, item_type, amount, gid)
                    path.created.add((gid, item_type, amount))
                elif kind == KIND_DOOR and isinstance(base, Door):
                    descriptor = Door(base.creator, sat)
                else:
                    descriptor = Interaction(kind, sat, call, base)
                path.slots[slot] = (descriptor, tainted)
                if call >= 0:
                    path.triggers.add(call)
            elif op == "aot_on":
                # An interaction written under unreadable game state taints
                # what activating it does.
                current, slot_taint = path.slots.get(args[0], (None, False))
                if isinstance(current, Interaction) and current.call >= 0:
                    path.pending.append((current.call, tainted or slot_taint))
                elif isinstance(current, Item):
                    # Aot_on hands over an item directly, bypassing a zero
                    # activation mask (RE2-DISPATCH-001). A door activation is
                    # a scripted walk through it and changes no interaction.
                    path.dispatched.add(
                        (
                            current.global_id,
                            current.item_type,
                            current.amount,
                            tainted or slot_taint,
                        )
                    )
            elif op == "gosub":
                if len(path.frames) >= CALL_DEPTH:
                    raise _Unsupported("procedure call depth")
                name = f"main:{args[0]}"
                if name not in self.program:
                    raise _Unsupported(f"missing procedure {name}")
                # The caller's frame stays on the stack and keeps its taint.
                path.frames.append(_Frame(name, 0, [], False))
                continue
            elif op == "patch":
                target, variable, width = args
                value, read_taint = self._variable(path, variable)
                path.patches[target] = (value, width, tainted or read_taint)
            elif op == "exec":
                if args[0] < 0:
                    raise _Unsupported("task start without a resolved procedure")
                if self.entry or all(proc != args[0] for proc, _ in path.pending):
                    # Later analysis only queues which procedures start, so a
                    # repeated start would only multiply otherwise equal paths.
                    path.pending.append((args[0], tainted))
            else:
                # Includes "invalid": the compiler could not bound this code.
                raise _Unsupported(f"unsupported model operation {op}")
            frame.index = nxt

    def _exits_besides_breaks(self, proc: str, first: int, end: int) -> bool:
        rows = self.program[proc]
        begin = rows[first][0] if first < len(rows) else end
        return any(
            op == "end" or op == "goto" and not begin <= args[0] <= end
            for offset, _, op, *args in rows[first:]
            if offset < end
        )

    def _diverge(self, taken: _Path, skipped: _Path) -> None:
        """Mark branches whose skipped region could have left early.

        ``taken`` enters the innermost if, else or loop block and ``skipped``
        will jump past it; a true if branch later skips its else body.
        """
        frame = taken.frames[-1]
        block = next(
            (b for b in reversed(frame.blocks) if b[0] in ("if", "else", "loop")),
            None,
        )
        if block is None:
            return
        kind, end, start, _ = block
        if self._exits(frame.proc, start + 1, end):
            skipped.diverged = True
        rows = self.program[frame.proc]
        index = self._index(frame.proc, end)
        if (
            kind == "if"
            and index > 0
            and rows[index - 1][1] == end
            and rows[index - 1][2] == "else"
            and self._exits(frame.proc, index, rows[index - 1][3])
        ):
            taken.diverged = True

    def _taint_block(self, path: _Path) -> None:
        frame = path.frames[-1]
        for index in range(len(frame.blocks) - 1, -1, -1):
            kind, end, start, _ = frame.blocks[index]
            if kind in ("if", "else", "loop"):
                frame.blocks[index] = (kind, end, start, True)
                return
        raise _Unsupported("condition outside an if or loop block")

    def _fail(self, path: _Path, taint: bool) -> None:
        frame = path.frames[-1]
        while frame.blocks and frame.blocks[-1][0] not in ("if", "else", "loop"):
            frame.blocks.pop()
        if not frame.blocks:
            raise _Unsupported("condition outside an if or loop block")
        kind, end, start, _ = frame.blocks.pop()
        frame.loops.pop(self.program[frame.proc][start][0], None)
        index = self._index(frame.proc, end)
        rows = self.program[frame.proc]
        if (
            kind == "if"
            and index > 0
            and rows[index - 1][1] == end
            and rows[index - 1][2] == "else"
        ):
            # A false if enters the else body, whose end is the else target.
            frame.blocks.append(("else", rows[index - 1][3], index - 1, taint))
        frame.index = index


@dataclass(frozen=True)
class Outcome:
    # Slot descriptors with whether unreadable game state controlled them.
    slots: dict[int, tuple[Descriptor, bool]]
    dispatched: frozenset[tuple[int, int, int, bool]]


@dataclass(frozen=True)
class EntryState:
    """Every outcome of entering the room with the current state."""

    support: Support
    reason: str
    terminals: tuple[Outcome, ...]
    # Procedures that player interactions or delayed tasks can still start.
    triggers: frozenset[int]
    # Tasks waiting for another task to change what they wait on.
    suspended: frozenset[Continuation]
    written: frozenset[tuple[int, int]]
    written_variables: frozenset[int]
    # Banks written at an undeterminable bit.
    written_banks: frozenset[int]


@dataclass(frozen=True)
class LaterState:
    """Items that triggered room procedures can still create or hand over."""

    support: Support
    reason: str
    # (gid, type, amount)
    possible: frozenset[tuple[int, int, int]]


def evaluate_entry(
    program: dict[str, list[list]], state: GameState, roots: tuple[str, ...]
) -> EntryState:
    """Run the room's automatic tasks in order, as entering the room would."""
    interpreter = _Interpreter(program, state, entry=True)
    try:
        if not roots or any(root not in program for root in roots):
            raise _Unsupported("missing automatic procedure")
        paths = interpreter.run([_fresh_path(roots[0])])
        for root in roots[1:]:
            for path in paths:
                path.frames = [_Frame(root, 0, [], False)]
            paths = interpreter.run(paths)
    except _Unsupported as error:
        return EntryState(
            Support.Unsupported,
            str(error),
            (),
            frozenset(),
            frozenset(),
            frozenset(),
            frozenset(),
            frozenset(),
        )
    return EntryState(
        Support.Supported,
        "",
        tuple(Outcome(path.slots, frozenset(path.dispatched)) for path in paths),
        frozenset(
            proc
            for path in paths
            for proc in path.triggers | {proc for proc, _ in path.pending}
        ),
        frozenset(task for path in paths for task in path.suspended),
        frozenset(interpreter.written),
        frozenset(interpreter.written_variables),
        frozenset(interpreter.written_banks),
    )


def evaluate_later(
    program: dict[str, list[list]],
    state: GameState,
    entry: EntryState,
    repeating: frozenset[int],
    acquisition_flags: frozenset[tuple[int, int]],
) -> LaterState:
    """Find items that procedures started after entry can still create.

    Flags and variables any room procedure writes can change before a trigger
    runs, so they are unreadable here. Others keep their current value.
    ``repeating`` names procedures the engine restarts while the room runs.
    Picking up the room's items sets ``acquisition_flags`` natively, so they
    can change in the room as well.
    """
    assert entry.support is Support.Supported, "later state needs a supported entry"
    written = set(entry.written) | acquisition_flags
    written_variables = set(entry.written_variables)
    written_banks = set(entry.written_banks)
    # Each task to analyze starts a procedure or resumes a waiting one.
    roots = {("start", proc) for proc in entry.triggers | repeating} | {
        ("resume", task) for task in entry.suspended
    }
    possible: set[int] = set()
    seen: set[tuple] = set()
    queue = sorted(roots)
    while queue:
        work = queue.pop()
        if work in seen:
            continue
        seen.add(work)
        kind, task = work
        if kind == "start":
            name = f"main:{task}"
            if name not in program:
                return LaterState(
                    Support.Unsupported, f"missing procedure {name}", frozenset()
                )
            frames = ((name, 0, (), False),)
        else:
            frames = task
            # The wait may end through native code changing what its loop
            # reads, so those values are unread when it resumes.
            reads = _wait_reads(program, frames[-1][0], frames[-1][1])
            flags, variables = reads
            if not (flags <= written and variables <= written_variables):
                written |= flags
                written_variables |= variables
                seen.clear()
                possible.clear()
                queue = sorted(roots)
                continue

        def volatile(bank: int, bit: int) -> bool | None:
            if (bank, bit) in written or bank in written_banks:
                return None
            return state.flag(bank, bit)

        def volatile_variable(index: int) -> int | None:
            return None if index in written_variables else state.variable(index)

        interpreter = _Interpreter(
            program,
            GameState(
                volatile,
                volatile_variable,
                state.approach_variables,
                state.approach_banks,
                # The player can pick up, use or combine items in the room.
                lambda item: None,
            ),
            entry=False,
        )
        # Triggers act on the interactions entry created, such as handing over
        # a parked item, so each one starts from every entry outcome.
        starts = []
        for outcome in entry.terminals:
            path = _fresh_path(frames[0][0])
            path.frames = [
                _Frame(proc, index, list(blocks), tainted)
                for proc, index, blocks, tainted in frames
            ]
            path.slots = dict(outcome.slots)
            starts.append(path)
        try:
            outcomes = interpreter.run(starts)
        except _Unsupported as error:
            return LaterState(Support.Unsupported, str(error), frozenset())
        if not (
            interpreter.written <= written
            and interpreter.written_variables <= written_variables
            and interpreter.written_banks <= written_banks
        ):
            written |= interpreter.written
            written_variables |= interpreter.written_variables
            written_banks |= interpreter.written_banks
            # New writes can open conditions in procedures already checked.
            seen.clear()
            possible.clear()
            queue = sorted(roots)
            continue
        for path in outcomes:
            possible |= path.created | {item[:3] for item in path.dispatched}
            queue.extend(
                ("start", proc)
                for proc in path.triggers | {proc for proc, _ in path.pending}
            )
            queue.extend(("resume", task) for task in path.suspended)
    return LaterState(Support.Supported, "", frozenset(possible))


@dataclass(frozen=True)
class DoorVerdict:
    creator: int
    # None means outcomes disagree through game state, so access is unresolved.
    sat: int | None
    replaced: bool


@dataclass(frozen=True)
class RoomScriptState:
    support: Support
    reason: str
    # gid -> True obtainable now or later, False absent, None unresolved.
    item_presence: dict[int, bool | None] = field(default_factory=dict)
    # Item IDs that are absent at entry but triggered procedures can create.
    later_items: frozenset[int] = frozenset()
    # Type and amount of each obtainable item where every outcome agrees.
    item_identity: dict[int, tuple[int, int]] = field(default_factory=dict)
    doors: dict[int, DoorVerdict] = field(default_factory=dict)


def room_script_state(
    program: dict[str, list[list]],
    state: GameState,
    tasks: EngineTasks,
    acquisition_flags: dict[int, tuple[int, int]],
) -> RoomScriptState:
    """Evaluate one room. ``acquisition_flags`` maps each pickup ID the room's
    scripts can create to its acquisition flag."""
    roots = tuple(root for root in tasks.roots if root in program)
    entry = evaluate_entry(program, state, roots)
    if entry.support is Support.Unsupported:
        return RoomScriptState(Support.Unsupported, entry.reason)
    later = evaluate_later(
        program,
        state,
        entry,
        frozenset(proc for proc in tasks.repeating if f"main:{proc}" in program),
        frozenset(acquisition_flags.values()),
    )
    if later.support is Support.Unsupported:
        return RoomScriptState(Support.Unsupported, later.reason)
    presence: dict[int, bool | None] = {}
    identity: dict[int, tuple[int, int]] = {}
    later_items = set()
    later_gids = {row[0] for row in later.possible}
    for gid in acquisition_flags:
        # Per outcome: (active, controlled by unreadable state).
        rows = []
        kinds = {
            (item_type, amount) for g, item_type, amount in later.possible if g == gid
        }

        def holds(descriptor: Descriptor) -> bool:
            if isinstance(descriptor, Interaction):
                descriptor = descriptor.replaced
            return isinstance(descriptor, Item) and descriptor.global_id == gid

        # Any slot that holds this item in some outcome. A write to it under
        # unreadable game state, including one that replaces the item with
        # something else, makes the item's presence state-dependent.
        holding = {
            slot
            for outcome in entry.terminals
            for slot, (descriptor, _) in outcome.slots.items()
            if holds(descriptor)
        }
        for outcome in entry.terminals:
            handed = {(t, a) for g, t, a, _ in outcome.dispatched if g == gid}
            kinds |= handed
            active = bool(handed)
            dispatch_taint = any(
                taint for g, _, _, taint in outcome.dispatched if g == gid
            )
            for descriptor, _ in outcome.slots.values():
                # SAT bit 7 selects four-point geometry, not activation.
                if (
                    isinstance(descriptor, Item)
                    and descriptor.global_id == gid
                    and descriptor.sat & 0x7F
                ):
                    active = True
                    kinds.add((descriptor.item_type, descriptor.amount))
            tainted = dispatch_taint or any(
                outcome.slots[slot][1] for slot in holding if slot in outcome.slots
            )
            rows.append((active, tainted))
        if rows and all(active for active, _ in rows):
            presence[gid] = True
        elif gid in later_gids:
            # Triggered procedures can still create it, such as a puzzle
            # reward, so it remains obtainable in this room.
            presence[gid] = True
            later_items.add(gid)
        elif not any(active for active, _ in rows):
            # Never created, or replaced or hidden in every outcome.
            presence[gid] = False
        elif not any(tainted for _, tainted in rows):
            # Outcomes differ only by arrival, such as the floor entered
            # from; each arrival's items exist in the room.
            presence[gid] = True
        else:
            presence[gid] = None
        if len(kinds) == 1:
            # The one item this acquisition can hand over, which also names
            # an item already collected.
            identity[gid] = next(iter(kinds))
    doors: dict[int, DoorVerdict] = {}
    slots = {slot for outcome in entry.terminals for slot in outcome.slots}
    for slot in slots:
        found = set()
        missing = False
        tainted = False
        for outcome in entry.terminals:
            descriptor, write_taint = outcome.slots.get(slot, (None, False))
            tainted = tainted or write_taint
            if isinstance(descriptor, Door):
                found.add((descriptor.creator, descriptor.sat, False))
            elif isinstance(descriptor, Interaction) and isinstance(
                descriptor.replaced, Door
            ):
                found.add((descriptor.replaced.creator, 0, True))
            else:
                missing = True
        if not found:
            continue
        if len(found) == 1 and not missing:
            creator, sat, replaced = next(iter(found))
            doors[creator] = DoorVerdict(creator, sat, replaced)
        elif not tainted:
            # Each arrival exposes its own door. Keep every creator at the
            # most usable state any arrival gives it.
            for creator in {row[0] for row in found}:
                options = sorted(
                    (not (row[1] & 0x7F and not row[2]), row)
                    for row in found
                    if row[0] == creator
                )
                _, (_, sat, replaced) = options[0]
                doors[creator] = DoorVerdict(creator, sat, replaced)
        else:
            for creator in {row[0] for row in found}:
                doors[creator] = DoorVerdict(creator, None, False)
    return RoomScriptState(
        Support.Supported, "", presence, frozenset(later_items), identity, doors
    )


class ScriptStateCache:
    """Reuse room evaluations until a flag or variable they read changes.

    Readers must be pure functions of fresh game memory. The cache records
    every value an evaluation read and revalidates them on each lookup, so a
    savestate load or story change re-evaluates the affected rooms.
    """

    def __init__(self) -> None:
        self._entries: dict[str, tuple[dict[tuple, object], RoomScriptState]] = {}

    def get(
        self,
        key: str,
        program: dict[str, list[list]],
        state: GameState,
        tasks: EngineTasks,
        acquisition_flags: dict[int, tuple[int, int]],
    ) -> RoomScriptState:
        readers = {
            "flag": state.flag,
            "variable": state.variable,
            "inventory": state.inventory,
        }
        cached = self._entries.get(key)
        if cached is not None and all(
            readers[read[0]](*read[1:]) == value for read, value in cached[0].items()
        ):
            return cached[1]
        reads: dict[tuple, object] = {}

        def flag(bank: int, bit: int) -> bool | None:
            value = state.flag(bank, bit)
            reads["flag", bank, bit] = value
            return value

        def variable(index: int) -> int | None:
            value = state.variable(index)
            reads["variable", index] = value
            return value

        def inventory(item: int) -> bool | None:
            value = state.inventory(item)
            reads["inventory", item] = value
            return value

        result = room_script_state(
            program,
            GameState(
                flag,
                variable,
                state.approach_variables,
                state.approach_banks,
                inventory,
            ),
            tasks,
            acquisition_flags,
        )
        self._entries[key] = (reads, result)
        return result
