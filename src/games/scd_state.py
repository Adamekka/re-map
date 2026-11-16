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
# Total work for one room's later analysis, across every started or resumed
# task and every restart, checked after each task, so the last task may add
# up to MAX_TOTAL_STEPS more. About 2.5 times the most any owned room needed
# in 20 pseudo-random states (1.55 million steps, RE3 03-0b).
MAX_LATER_STEPS = 4_000_000
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
    # (source offset, tainted) of every direct award run.
    awarded: set[tuple[int, bool]]
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
            set(self.awarded),
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
            frozenset(award if taint else award[:1] for award in self.awarded),
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


_CONDITIONS = ("ck", "cmp", "cond", "has")


# Commands a wait loop may contain for its exit to be analysed exactly: no
# branch can skip one of its predicates.
_STRAIGHT = (
    *_CONDITIONS,
    "set",
    "var",
    "calc",
    "calc2",
    "patch",
    "item",
    "award",
    "door",
    "aot",
    "reset",
    "aot_on",
    "exec",
    "gosub",
)
# Commands whose effect a skipped block would have had.
_EFFECTS = (
    "set",
    "var",
    "calc",
    "calc2",
    "patch",
    "item",
    "award",
    "door",
    "aot",
    "reset",
    "aot_on",
    "exec",
)


@dataclass(frozen=True)
class _Writes:
    """Values scripts can write: flag -> values, bank -> values a Work_copy-
    chosen bit can take, and written variables."""

    flags: dict[tuple[int, int], set[bool]]
    banks: dict[int, set[bool]]
    variables: set[int]
    # Work_copy target offset -> variables it copies there.
    patches: dict[int, set[int]]

    def can_write(
        self, flag: tuple[int, int], values: set[bool], patched: bool
    ) -> bool:
        """Whether one of ``values`` can be written to ``flag``; for a
        Work_copy-chosen bit, any write in its bank counts."""
        bank, bit = flag
        writable = set(self.banks.get(bank, set()))
        if patched:
            for (other, _), written in self.flags.items():
                if other == bank:
                    writable |= written
        else:
            writable |= self.flags.get((bank, bit), set())
        return bool(values & writable)


def _writes(rows, patch_targets: frozenset[int]) -> _Writes:
    """Flags, banks and variables that ``rows`` can write. A Set whose bit a
    Work_copy chooses may write any flag of its bank."""
    flags: dict[tuple[int, int], set[bool]] = {}
    banks: dict[int, set[bool]] = {}
    variables: set[int] = set()
    patches: dict[int, set[int]] = {}
    for row in rows:
        if row[2] == "patch":
            patches.setdefault(row[3], set()).add(row[4])
        elif row[2] == "set":
            values = {True, False} if row[5] == 7 else {bool(row[5])}
            if row[0] + 2 in patch_targets:
                banks.setdefault(row[3], set()).update(values)
            else:
                flags.setdefault((row[3], row[4]), set()).update(values)
        elif row[2] in ("var", "calc", "calc2"):
            variables.add(row[3])
    return _Writes(flags, banks, variables, patches)


def _runnable_procedures(
    program: dict[str, list[list]], roots: tuple[str, ...]
) -> frozenset[str]:
    """Procedures the automatic roots can run, call or start, transitively."""
    pending = [name for name in roots if name in program]
    runnable: set[str] = set()
    while pending:
        name = pending.pop()
        if name in runnable:
            continue
        runnable.add(name)
        for _, _, op, *args in program[name]:
            procedures = (
                [args[0]]
                if op in ("gosub", "exec")
                else [args[3]]
                if op in ("aot", "reset")
                else []
            )
            pending.extend(
                f"main:{procedure}"
                for procedure in procedures
                if procedure >= 0 and f"main:{procedure}" in program
            )
    return frozenset(runnable)


def _loop_rows(
    program: dict[str, list[list]], proc: str, head: int, last: int
) -> list[list]:
    """Rows of a wait loop, from row ``head`` to row ``last``, and of every
    procedure it calls."""
    found = []
    pending = [program[proc][head : last + 1]]
    called: set[int] = set()
    while pending:
        for row in pending.pop():
            found.append(row)
            if row[2] == "gosub" and row[3] not in called:
                name = f"main:{row[3]}"
                if name not in program:
                    raise _Unsupported(f"missing procedure {name}")
                called.add(row[3])
                pending.append(program[name])
    return found


def _wait_reads(
    program: dict[str, list[list]], proc: str, head: int, last: int
) -> tuple[set[tuple[int, int]], set[int]]:
    """Flags and variables a wait loop and the procedures it calls read."""
    flags: set[tuple[int, int]] = set()
    variables: set[int] = set()
    for _, _, op, *args in _loop_rows(program, proc, head, last):
        if op == "ck":
            flags.add((args[0], args[1]))
        elif op == "set" and args[2] == 7:
            # A toggle reads the flag it writes.
            flags.add((args[0], args[1]))
        elif op == "cmp":
            variables.add(args[0])
        elif op == "switch":
            variables.add(args[1])
        elif op == "var" and args[1] == 1:
            variables.add(args[2])
        elif op == "calc":
            variables.add(args[0])
        elif op == "calc2":
            variables.update((args[0], args[2]))
        elif op == "patch":
            variables.add(args[1])
    return flags, variables


# A suspended task: its frames as (procedure, row index, blocks, tainted,
# loop counts), and the row of the backward Goto that waits.
Continuation = tuple[tuple[tuple, ...], int]


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
        automatic: tuple[str, ...],
        runnable: frozenset[str],
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
        self.patches = tuple(
            row for rows in program.values() for row in rows if row[2] == "patch"
        )
        self.patch_targets = frozenset(row[3] for row in self.patches)
        # ``runnable`` names the procedures the room's automatic tasks can run,
        # call or start. Their writes may release another task's wait.
        self.runnable = runnable
        # The automatic and repeating procedures the engine runs itself.
        self.roots = automatic
        # Waiting call stack -> writes of independently scheduled work.
        self.other_writes: dict[frozenset[str], _Writes] = {}
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
                                # unknown and paths differing in it merge. A
                                # variable depends on arrival only if every
                                # arrival says so; a patch keeps its width.
                                kept[name] = (
                                    None,
                                    *(
                                        (
                                            all(
                                                value[1]
                                                for value in values - {_UNWRITTEN}
                                            ),
                                        )
                                        if seen is observed[1]
                                        else next(iter(agreed))[1:]
                                    ),
                                    True,
                                )
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
                    block = next(
                        (
                            b
                            for b in reversed(frame.blocks)
                            if b[0] in ("if", "else", "loop")
                        ),
                        None,
                    )
                    if (
                        read_taint
                        and self.entry
                        and block is not None
                        and (
                            # Leaving a loop skips its repeats, which may wait.
                            block[0] == "loop"
                            or self._has_effects(
                                rows[frame.index : self._index(frame.proc, block[1])]
                            )
                            or self._exits(frame.proc, frame.index, block[1])
                        )
                    ):
                        # A tainted predicate skipped writes, repeats or an
                        # exit, so what follows depends on unread game state.
                        path.diverged = True
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
                end, count, _ = args
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
                kind = rows[start][5]
                last = frame.index
                holds: bool | None = True
                if kind == "do":
                    # A Do repeats while the predicate after its closing
                    # command holds.
                    last += 1
                    if last >= len(rows) or rows[last][2] not in _CONDITIONS:
                        raise _Unsupported("Do without a following predicate")
                    _, _, predicate, *operands = rows[last]
                    holds, approach, read_taint = self._condition(
                        path, rows[last][0], predicate, operands
                    )
                    # As for an If: unreadable game state taints the repeat,
                    # while arrival-dependent outcomes are alternatives.
                    taint = (
                        read_taint or holds is None and not approach
                    ) and self.entry
                    if holds is None:
                        other = path.fork()
                        exited = other.frames[-1]
                        exited.loops.pop(opener, None)
                        exited.blocks.pop()
                        exited.index = self._index(frame.proc, end)
                        # Leaving early under unread game state makes what
                        # follows depend on it.
                        other.diverged = other.diverged or taint
                        work.append(other)
                    if taint and holds is not False:
                        frame.blocks[-1] = ("loop", end, start, True)
                    elif taint:
                        # A tainted predicate decided to leave.
                        path.diverged = True
                count = frame.loops.get(opener, (0,))[0] + 1
                if holds is not False and count < LOOP_LIMIT:
                    frame.loops[opener] = (count, opener, end - 1)
                    nxt = start + 1
                elif (
                    holds is not False
                    and kind in ("while", "do")
                    and self._waits_on_native(
                        path,
                        start,
                        last,
                        self._loop_shape(rows, start, frame.index, kind == "do"),
                    )
                ):
                    # A While or Do that waits on native state keeps waiting
                    # until that state changes.
                    frame.loops.pop(opener, None)
                    self._suspend(path, start, opener, last)
                    continue
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
                        # A repeated backward jump is a wait. With no enclosing
                        # condition, or a loop that reads native state, the
                        # task waits until another task or native code changes
                        # what it waits on. Otherwise continue as if the
                        # enclosing condition eventually stopped holding.
                        del frame.loops[offset]
                        head = self._index(frame.proc, target)
                        enclosing = next(
                            (
                                block
                                for block in reversed(frame.blocks)
                                if block[0] in ("if", "else", "loop")
                            ),
                            None,
                        )
                        if enclosing is None or self._waits_on_native(
                            path,
                            head,
                            frame.index,
                            self._jump_shape(rows, enclosing, head, frame.index),
                        ):
                            self._suspend(path, head, target, frame.index)
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
            elif op == "award":
                path.awarded.add((offset, tainted))
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

    def _straight(self, rows: list[list], first: int, stop: int) -> bool:
        """Whether rows ``first`` to ``stop`` run in order, every procedure
        they call included, so no branch can skip one of their predicates."""
        pending = [rows[first:stop]]
        called: set[int] = set()
        while pending:
            for row in pending.pop():
                if row[2] not in _STRAIGHT:
                    return False
                if row[2] == "gosub" and row[3] not in called:
                    name = f"main:{row[3]}"
                    if name not in self.program:
                        raise _Unsupported(f"missing procedure {name}")
                    called.add(row[3])
                    body = self.program[name]
                    # A called procedure may end but not branch or test.
                    if any(
                        callee[2] not in (*_STRAIGHT, "end") or callee[2] in _CONDITIONS
                        for callee in body
                    ):
                        return False
                    pending.append([callee for callee in body if callee[2] != "end"])
        return True

    def _has_effects(self, rows: list[list]) -> bool:
        """Whether ``rows`` write anything or start a task, directly or in a
        procedure they call."""
        pending = [rows]
        called: set[int] = set()
        while pending:
            for row in pending.pop():
                if row[2] in _EFFECTS:
                    return True
                if row[2] == "gosub" and row[3] not in called:
                    name = f"main:{row[3]}"
                    if name not in self.program:
                        raise _Unsupported(f"missing procedure {name}")
                    called.add(row[3])
                    pending.append(self.program[name])
        return False

    @staticmethod
    def _predicates(rows: list[list], first: int, stop: int) -> list[int]:
        return [index for index in range(first, stop) if rows[index][2] in _CONDITIONS]

    def _loop_shape(
        self, rows: list[list], start: int, loop_end: int, do: bool
    ) -> tuple | None:
        """How a While or Do at its loop limit decides to repeat.

        It repeats while every predicate in its body holds, and for a Do the
        one after its closing command too. None if its body branches.
        """
        if not self._straight(rows, start + 1, loop_end):
            return None
        return (
            "all",
            self._predicates(rows, start + 1, loop_end)
            + ([loop_end + 1] if do else []),
        )

    def _jump_shape(
        self, rows: list[list], enclosing: tuple, head: int, goto: int
    ) -> tuple | None:
        """How a repeated backward jump at row ``goto`` decides to repeat.

        Every predicate from the loop head to the jump guards it. Inside an
        If or While it repeats while all of them hold. Inside an Else it
        repeats while the guards before the If and the predicates in the
        Else hold and the If's own predicates do not all hold. None unless
        the enclosing block opens inside the loop and nothing branches.
        """
        kind, _, opener, _ = enclosing
        if opener < head:
            return None
        # Jumping back to a While's opener runs its predicate again as a guard.
        first = head + (rows[head][2] == "loop" and rows[head][5] == "while")
        if kind == "if" or kind == "loop" and rows[opener][5] == "while":
            if not (
                self._straight(rows, first, opener)
                and self._straight(rows, opener + 1, goto)
            ):
                return None
            return (
                "all",
                self._predicates(rows, first, opener)
                + self._predicates(rows, opener + 1, goto),
            )
        if kind != "else":
            return None
        # The If jumps past its true branch to the row after this Else.
        matching = next(
            (
                index
                for index in range(opener - 1, head - 1, -1)
                if rows[index][2] == "if" and rows[index][3] == rows[opener][1]
            ),
            None,
        )
        if matching is None or not (
            self._straight(rows, first, matching)
            and self._straight(rows, matching + 1, opener)
            and self._straight(rows, opener + 1, goto)
        ):
            return None
        return (
            "else",
            self._predicates(rows, first, matching)
            + self._predicates(rows, opener + 1, goto),
            self._predicates(rows, matching + 1, opener),
            # A predicate's current value predicts its next test only if no
            # write between the loop head and the If's tests can change it.
            not self._has_effects(rows[first:opener]),
        )

    def _waits_on_native(
        self, path: _Path, head: int, last: int, shape: tuple | None
    ) -> bool:
        """Whether a wait loop waits for native code rather than the room.

        ``shape`` says how the loop decides to repeat (see ``_loop_shape`` and
        ``_jump_shape``), or None when it branches: then every flag and
        variable the loop reads must be writable by a runnable script.
        """
        proc = path.frames[-1].proc
        loop = _loop_rows(self.program, proc, head, last)
        writes = self._releasing_writes(path, loop)
        if shape is None:
            flags, variables = _wait_reads(self.program, proc, head, last)
            return (
                any(not writes.can_write(flag, {True, False}, False) for flag in flags)
                or not variables <= writes.variables
            )
        rows = self.program[proc]

        def room_controlled(variable: int) -> bool:
            """Whether only runnable scripts change this variable, following
            copies inside the loop; an unread or actor value is native."""
            chain, changed = {variable}, True
            while changed:
                changed = False
                for _, _, op, *args in loop:
                    if op in ("var", "calc", "calc2") and args[0] in chain:
                        if op == "var" and args[1] in (2, 3):
                            return False
                        if (op == "var" and args[1] == 1 or op == "calc2") and (
                            args[2] not in chain
                        ):
                            chain.add(args[2])
                            changed = True
            return chain <= writes.variables

        def can_make(index: int, value: bool) -> bool:
            """Whether a runnable script can make predicate row ``index``
            evaluate to ``value``."""
            offset, _, op, *args = rows[index]
            if op == "cond":
                # Arrival predicates are assumed to change; unread game state
                # changes only through native code.
                return args[0] == 1
            if op == "has":
                return False
            # Only a Work_copy that can run while the task waits changes the
            # operand; one that ran before the wait fixed it.
            sources = writes.patches.get(offset + 2, set()) | writes.patches.get(
                offset + 4, set()
            )
            if any(room_controlled(source) for source in sources):
                return True
            if op == "ck":
                return writes.can_write(
                    (args[0], args[1]),
                    {bool(args[2]) == value},
                    offset + 2 in self.patch_targets,
                )
            return offset + 2 not in self.patch_targets and room_controlled(args[0])

        def holds_now(index: int) -> bool:
            offset, _, op, *args = rows[index]
            value, _, taint = self._condition(path, offset, op, args)
            return value is True and not taint

        if shape[0] == "all":
            return not any(can_make(index, False) for index in shape[1])
        _, repeating, leaving, current = shape
        return not (
            any(can_make(index, False) for index in repeating)
            or all(
                current and holds_now(index) or can_make(index, True)
                for index in leaving
            )
        )

    def _releasing_writes(self, path: _Path, loop: list[list]) -> _Writes:
        """Writes that can happen while a task waits in ``loop``.

        Those are the loop's own, including the procedures it calls, and
        those of work the engine schedules independently: the automatic and
        repeating procedures, tasks other scripts start, and what they call.
        Procedures on the waiting task's call stack, and procedures only they
        call outside the loop, cannot run meanwhile.
        """
        stack = frozenset(frame.proc for frame in path.frames)
        if stack not in self.other_writes:
            starts = set(self.roots)
            for name in self.runnable:
                for _, _, op, *args in self.program[name]:
                    started = (
                        args[0]
                        if op == "exec"
                        else args[3]
                        if op in ("aot", "reset")
                        else -1
                    )
                    if started >= 0:
                        starts.add(f"main:{started}")
            independent = _runnable_procedures(
                self.program, tuple(sorted(starts - stack))
            )
            self.other_writes[stack] = _writes(
                (
                    row
                    for name in sorted(independent - stack)
                    for row in self.program[name]
                ),
                self.patch_targets,
            )
        others, own = self.other_writes[stack], _writes(loop, self.patch_targets)
        return _Writes(
            {
                flag: others.flags.get(flag, set()) | own.flags.get(flag, set())
                for flag in others.flags.keys() | own.flags.keys()
            },
            {
                bank: others.banks.get(bank, set()) | own.banks.get(bank, set())
                for bank in others.banks.keys() | own.banks.keys()
            },
            others.variables | own.variables,
            {
                target: others.patches.get(target, set())
                | own.patches.get(target, set())
                for target in others.patches.keys() | own.patches.keys()
            },
        )

    def _suspend(self, path: _Path, head: int, target: int, last: int) -> None:
        """End the task at a wait whose loop runs from row ``head`` to ``last``.

        Later analysis resumes it there with its call stack, so what ran before
        the wait does not repeat.
        """
        frame = path.frames[-1]
        path.suspended.add(
            (
                (
                    *(
                        (
                            f.proc,
                            f.index,
                            tuple(f.blocks),
                            f.tainted,
                            tuple(sorted(f.loops.items())),
                        )
                        for f in path.frames[:-1]
                    ),
                    (
                        frame.proc,
                        head,
                        # Blocks and loops that open inside the wait loop end
                        # before its head.
                        tuple(b for b in frame.blocks if b[2] < head),
                        frame.tainted,
                        tuple(
                            sorted(
                                (key, loop)
                                for key, loop in frame.loops.items()
                                if loop[1] <= target <= loop[2]
                            )
                        ),
                    ),
                ),
                last,
            )
        )
        path.frames.clear()

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
    awarded: frozenset[tuple[int, bool]]
    # Tasks waiting for another task to change what they wait on; they resume
    # with this outcome's interactions.
    suspended: frozenset[Continuation]


@dataclass(frozen=True)
class EntryState:
    """Every outcome of entering the room with the current state."""

    support: Support
    reason: str
    terminals: tuple[Outcome, ...]
    # Procedures that player interactions or delayed tasks can still start.
    triggers: frozenset[int]
    written: frozenset[tuple[int, int]]
    written_variables: frozenset[int]
    # Banks written at an undeterminable bit.
    written_banks: frozenset[int]
    # The automatic and repeating procedures, and every procedure they can
    # run, call or start.
    automatic: tuple[str, ...]
    runnable: frozenset[str]
    # Procedures the engine restarts while the room runs.
    repeating: frozenset[int]


@dataclass(frozen=True)
class LaterState:
    """Items that triggered room procedures can still create or hand over."""

    support: Support
    reason: str
    # (gid, type, amount)
    possible: frozenset[tuple[int, int, int]]
    # Source offsets of direct awards they can run.
    awards: frozenset[int]


def evaluate_entry(
    program: dict[str, list[list]], state: GameState, tasks: EngineTasks
) -> EntryState:
    """Run the room's automatic tasks in order, as entering the room would."""
    roots = tasks.roots
    # Only procedures the room has can restart.
    repeating = frozenset(proc for proc in tasks.repeating if f"main:{proc}" in program)
    automatic = (*roots, *(f"main:{proc}" for proc in sorted(repeating)))
    runnable = _runnable_procedures(program, automatic)
    interpreter = _Interpreter(
        program, state, entry=True, automatic=automatic, runnable=runnable
    )
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
            automatic,
            runnable,
            repeating,
        )
    return EntryState(
        Support.Supported,
        "",
        tuple(
            Outcome(
                path.slots,
                frozenset(path.dispatched),
                frozenset(path.awarded),
                frozenset(path.suspended),
            )
            for path in paths
        ),
        frozenset(
            proc
            for path in paths
            for proc in path.triggers | {proc for proc, _ in path.pending}
        ),
        frozenset(interpreter.written),
        frozenset(interpreter.written_variables),
        frozenset(interpreter.written_banks),
        automatic,
        runnable,
        repeating,
    )


def evaluate_later(
    program: dict[str, list[list]],
    state: GameState,
    entry: EntryState,
    acquisition_flags: frozenset[tuple[int, int]],
) -> LaterState:
    """Find items that procedures started after entry can still create.

    Flags and variables any room procedure writes can change before a trigger
    runs, so they are unreadable here. Others keep their current value.
    Procedures the engine restarts while the room runs come from ``entry``.
    Picking up the room's items sets ``acquisition_flags`` natively, so they
    can change in the room as well.
    """
    assert entry.support is Support.Supported, "later state needs a supported entry"
    written = set(entry.written) | acquisition_flags
    written_variables = set(entry.written_variables)
    written_banks = set(entry.written_banks)

    # Each task to analyze starts a procedure or resumes a waiting one.
    # A resumed task keeps the interactions of the path that suspended it.
    def resumed(task: Continuation, slots: dict) -> tuple:
        # Later analysis never reads taint, so tasks and interactions that
        # differ only in taint resume once.
        frames, last = task
        return (
            "resume",
            (
                tuple(
                    (
                        proc,
                        index,
                        tuple(block[:3] + (False,) for block in blocks),
                        False,
                        loops,
                    )
                    for proc, index, blocks, _, loops in frames
                ),
                last,
            ),
            tuple(
                sorted((slot, descriptor) for slot, (descriptor, _) in slots.items())
            ),
        )

    def ordered(work: set[tuple]) -> list[tuple]:
        # A stable order keeps the reported reason for Unsupported repeatable.
        return sorted(work, key=repr)

    roots = {("start", proc) for proc in entry.triggers | entry.repeating} | {
        resumed(task, outcome.slots)
        for outcome in entry.terminals
        for task in outcome.suspended
    }
    possible: set[int] = set()
    awards: set[int] = set()
    spent = 0
    seen: set[tuple] = set()
    queue = ordered(roots)
    while queue:
        work = queue.pop()
        if work in seen:
            continue
        seen.add(work)
        kind, task, *slots = work
        if kind == "start":
            name = f"main:{task}"
            if name not in program:
                return LaterState(
                    Support.Unsupported,
                    f"missing procedure {name}",
                    frozenset(),
                    frozenset(),
                )
            frames = ((name, 0, (), False, ()),)
        else:
            frames, last = task
            # The wait may end through native code changing what its loop
            # reads, so those values are unread when it resumes.
            try:
                flags, variables = _wait_reads(
                    program, frames[-1][0], frames[-1][1], last
                )
            except _Unsupported as error:
                return LaterState(
                    Support.Unsupported, str(error), frozenset(), frozenset()
                )
            if not (flags <= written and variables <= written_variables):
                written |= flags
                written_variables |= variables
                seen.clear()
                possible.clear()
                awards.clear()
                queue = ordered(roots)
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
            automatic=entry.automatic,
            runnable=entry.runnable,
        )
        # Triggers act on the interactions entry created, such as handing over
        # a parked item, so each one starts from every entry outcome.
        starts = []
        for interactions in (
            [{slot: (descriptor, False) for slot, descriptor in slots[0]}]
            if kind == "resume"
            else [dict(outcome.slots) for outcome in entry.terminals]
        ):
            path = _fresh_path(frames[0][0])
            path.frames = [
                _Frame(proc, index, list(blocks), tainted, dict(loops))
                for proc, index, blocks, tainted, loops in frames
            ]
            path.slots = interactions
            starts.append(path)
        try:
            outcomes = interpreter.run(starts)
        except _Unsupported as error:
            return LaterState(Support.Unsupported, str(error), frozenset(), frozenset())
        spent += interpreter.total_steps
        if spent > MAX_LATER_STEPS:
            return LaterState(
                Support.Unsupported,
                "later script evaluation step limit",
                frozenset(),
                frozenset(),
            )
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
            awards.clear()
            queue = ordered(roots)
            continue
        for path in outcomes:
            possible |= path.created | {item[:3] for item in path.dispatched}
            awards |= {offset for offset, _ in path.awarded}
            queue.extend(
                ("start", proc)
                for proc in path.triggers | {proc for proc, _ in path.pending}
            )
            queue.extend(
                ordered({resumed(task, path.slots) for task in path.suspended})
            )
    return LaterState(Support.Supported, "", frozenset(possible), frozenset(awards))


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
    # Award source offset -> True obtainable now or later, False absent, None
    # unresolved.
    award_presence: dict[int, bool | None] = field(default_factory=dict)


def room_script_state(
    program: dict[str, list[list]],
    state: GameState,
    tasks: EngineTasks,
    acquisition_flags: dict[int, tuple[int, int]],
) -> RoomScriptState:
    """Evaluate one room. ``acquisition_flags`` maps each pickup ID the room's
    scripts can create to its acquisition flag."""
    roots = tuple(root for root in tasks.roots if root in program)
    entry = evaluate_entry(program, state, EngineTasks(roots, tasks.repeating))
    if entry.support is Support.Unsupported:
        return RoomScriptState(Support.Unsupported, entry.reason)
    later = evaluate_later(program, state, entry, frozenset(acquisition_flags.values()))
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
    awards: dict[int, bool | None] = {}
    for offset in sorted(
        row[0] for rows in program.values() for row in rows if row[2] == "award"
    ):
        ran = [
            any(award == offset for award, _ in outcome.awarded)
            for outcome in entry.terminals
        ]
        if offset in later.awards or ran and all(ran):
            # Entering runs it, or a triggered procedure still can, such as a
            # puzzle reward.
            awards[offset] = True
        elif not any(ran):
            awards[offset] = False
        else:
            # An outcome without the award records no reason, so arrival and
            # unreadable state cannot be told apart.
            awards[offset] = None
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
        Support.Supported, "", presence, frozenset(later_items), identity, doors, awards
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
