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

- ``if end`` / ``else target`` / ``loop end`` / ``loop_end`` / ``case`` /
  ``break`` / ``goto target`` / ``end`` / ``invalid``
- ``switch end variable [[label, value], ...]`` with value None for Default
- ``ck bank bit expected``
- ``cmp variable operation value`` with ==, >, >=, <, <=, != and bit test
- ``cond approach``: an unreadable condition; approach 1 means it depends only
  on how the player arrives or acts
- ``set bank bit operation`` with 0 clear, 1 set, 7 toggle
- ``var variable kind argument``: kind 0 stores the constant argument, 1
  copies variable ``argument`` and 2 stores an unreadable result
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


@dataclass
class _Frame:
    proc: str
    index: int
    # (kind, end offset, opening row index, tainted)
    blocks: list[tuple[str, int, int, bool]]


@dataclass
class _Path:
    frames: list[_Frame]
    # Each written value carries whether an unreadable state condition
    # controlled the write.
    slots: dict[int, tuple[Descriptor, bool]]
    flags: dict[tuple[int, int], tuple[bool | None, bool]]
    variables: dict[int, tuple[int | None, bool]]
    pending: list[int]
    executed: dict[int, int]
    loops: dict[tuple[str, int], int]
    triggers: set[int]
    # (gid, type, amount) for every item a create or Reset wrote.
    created: set[tuple[int, int, int]]
    # (gid, type, amount) handed over by Aot_on, bypassing activation masks.
    dispatched: set[tuple[int, int, int]]
    # Source offset -> (value, width, tainted) stored by Work_copy.
    patches: dict[int, tuple[int | None, int, bool]]
    # Banks written at a bit no reader can determine.
    unknown_banks: set[int]
    steps: int = 0

    def fork(self) -> _Path:
        return _Path(
            [_Frame(f.proc, f.index, list(f.blocks)) for f in self.frames],
            dict(self.slots),
            dict(self.flags),
            dict(self.variables),
            list(self.pending),
            dict(self.executed),
            dict(self.loops),
            set(self.triggers),
            set(self.created),
            set(self.dispatched),
            dict(self.patches),
            set(self.unknown_banks),
            self.steps,
        )

    def tainted(self) -> bool:
        return any(block[3] for frame in self.frames for block in frame.blocks)

    def outcome(self) -> tuple:
        # Finished paths differ only through their effects.
        return (
            tuple(sorted(self.slots.items())),
            tuple(sorted(self.flags.items())),
            tuple(sorted(self.variables.items())),
            frozenset(self.triggers),
            frozenset(self.created),
            frozenset(self.dispatched),
            tuple(sorted(self.patches.items())),
            frozenset(self.unknown_banks),
        )

    def key(self) -> tuple:
        return (
            tuple((f.proc, f.index, tuple(f.blocks)) for f in self.frames),
            tuple(self.pending),
            tuple(sorted(self.executed.items())),
            tuple(sorted(self.loops.items())),
            self.outcome(),
        )


def _fresh_path(proc: str) -> _Path:
    return _Path(
        [_Frame(proc, 0, [])], {}, {}, {}, [], {}, {}, set(), set(), set(), {}, set()
    )


class _Unsupported(Exception):
    pass


class _Interpreter:
    def __init__(
        self, program: dict[str, list[list]], state: GameState, fresh_source: bool
    ) -> None:
        self.program = program
        self.offsets = {
            name: [row[0] for row in rows] for name, rows in program.items()
        }
        self.state = state
        # A freshly loaded source has no Work_copy patches yet. Procedures
        # started later may run after any patch, so patched fields are unread.
        self.fresh_source = fresh_source
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

    def _joins(self, rows: list[list]) -> frozenset[int]:
        offsets = [row[0] for row in rows]
        targets = set()
        for row in rows:
            if row[2] in ("if", "else", "goto", "loop"):
                targets.add(row[3])
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
            value = original & ~0xFF | value & 0xFF if width == 1 else value & 0xFFFF
            if signed and value & 0x8000:
                value -= 0x10000
            return value, tainted
        if offset in self.patch_targets and not self.fresh_source:
            return None, True
        return original, False

    def _variable(self, path: _Path, index: int) -> tuple[int | None, bool]:
        if index in path.variables:
            return path.variables[index]
        return self.state.variable(index), False

    def run(self, start: list[_Path]) -> list[_Path]:
        done, work, finished = [], list(start), set()
        self.seen.clear()
        while work:
            path = work.pop()
            result = self._step_until_done(path, work)
            if result is not None and result.outcome() not in finished:
                finished.add(result.outcome())
                done.append(result)
                if len(done) > MAX_TERMINALS:
                    raise _Unsupported("too many script outcomes")
        return done

    def _start_task(self, path: _Path, proc: int) -> bool:
        name = f"main:{proc}"
        if name not in self.program:
            raise _Unsupported(f"missing procedure {name}")
        count = path.executed.get(proc, 0)
        if count >= LOOP_LIMIT:
            return False
        path.executed[proc] = count + 1
        path.frames = [_Frame(name, 0, [])]
        return True

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
            approach = index in self.state.approach_variables
            if args[1] >= len(_COMPARE):
                # The native handler returns false for other operators.
                return False, approach, tainted
            if current is None:
                return None, approach, tainted
            return _COMPARE[args[1]](current, value), approach, tainted
        return None, args[0] == 1, False

    def _step_until_done(self, path: _Path, work: list[_Path]) -> _Path | None:
        while True:
            if not path.frames:
                while path.pending:
                    if self._start_task(path, path.pending.pop(0)):
                        break
                else:
                    return path
            path.steps += 1
            self.total_steps += 1
            if path.steps > MAX_STEPS or self.total_steps > MAX_TOTAL_STEPS:
                raise _Unsupported("script evaluation step limit")
            frame = path.frames[-1]
            rows = self.program[frame.proc]
            if frame.index in self.joins[frame.proc]:
                key = path.key()
                if key in self.seen:
                    return None
                self.seen.add(key)
            if frame.index >= len(rows):
                # Procedures end with an explicit terminator. Running off the
                # decoded range means trailing bytes were not understood.
                raise _Unsupported(f"{frame.proc} ends without a terminator")
            offset, _, op, *args = rows[frame.index]
            while frame.blocks and offset >= frame.blocks[-1][1]:
                frame.blocks.pop()
            nxt = frame.index + 1
            tainted = path.tainted()
            if op == "end":
                path.frames.pop()
                if path.frames:
                    path.frames[-1].index += 1
                continue
            if op == "if":
                frame.blocks.append(("if", args[0], frame.index, False))
            elif op in ("ck", "cmp", "cond"):
                value, approach, read_taint = self._condition(path, offset, op, args)
                if value is None:
                    other = path.fork()
                    # Unreadable game state taints both branches until they
                    # join. Arrival-dependent branches are alternatives.
                    taint = read_taint or not approach
                    self._fail(other, taint)
                    work.append(other)
                    if taint:
                        self._taint_block(path)
                elif not value:
                    self._fail(path, read_taint)
                    continue
                elif read_taint:
                    self._taint_block(path)
            elif op == "else":
                if not frame.blocks or frame.blocks[-1][0] != "if":
                    raise _Unsupported("else outside an if block")
                frame.blocks.pop()
                nxt = self._index(frame.proc, args[0])
            elif op == "loop":
                frame.blocks.append(("loop", args[0], frame.index, False))
            elif op == "loop_end":
                if not frame.blocks or frame.blocks[-1][0] != "loop":
                    raise _Unsupported("loop end outside a loop")
                _, end, start, _ = frame.blocks[-1]
                key = (frame.proc, start)
                path.loops[key] = path.loops.get(key, 0) + 1
                if path.loops[key] < LOOP_LIMIT:
                    nxt = start + 1
                else:
                    # Forget the count on exit so later joins can merge.
                    del path.loops[key]
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
                taint = read_taint or (
                    current is None and variable not in self.state.approach_variables
                )
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
                path.loops.pop((frame.proc, start), None)
                nxt = self._index(frame.proc, end)
            elif op == "goto":
                target = args[0]
                if target <= offset:
                    key = (frame.proc, offset)
                    path.loops[key] = path.loops.get(key, 0) + 1
                    if path.loops[key] >= LOOP_LIMIT:
                        # A repeated backward jump is a wait. Continue as if
                        # the enclosing condition eventually stopped holding.
                        del path.loops[key]
                        if not frame.blocks:
                            path.frames.pop()
                            if path.frames:
                                path.frames[-1].index += 1
                            continue
                        self._fail(path, False)
                        continue
                nxt = self._index(frame.proc, target)
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
                if kind == 0:
                    path.variables[variable] = (argument, tainted)
                elif kind == 1:
                    value, read_taint = self._variable(path, argument)
                    path.variables[variable] = (value, tainted or read_taint)
                else:
                    # Unread arithmetic or actor values. Comparisons on them
                    # fork as game state.
                    path.variables[variable] = (None, tainted)
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
                current = path.slots.get(args[0], (None, False))[0]
                if isinstance(current, Interaction) and current.call >= 0:
                    path.pending.append(current.call)
                elif isinstance(current, Item):
                    # Aot_on hands over an item directly, bypassing a zero
                    # activation mask (RE2-DISPATCH-001). A door activation is
                    # a scripted walk through it and changes no interaction.
                    path.dispatched.add(
                        (current.global_id, current.item_type, current.amount)
                    )
            elif op == "gosub":
                if len(path.frames) >= CALL_DEPTH:
                    raise _Unsupported("procedure call depth")
                name = f"main:{args[0]}"
                if name not in self.program:
                    raise _Unsupported(f"missing procedure {name}")
                # A call made under tainted control inherits that taint.
                path.frames.append(
                    _Frame(name, 0, [("call", 1 << 62, -1, True)] if tainted else [])
                )
                continue
            elif op == "patch":
                target, variable, width = args
                value, read_taint = self._variable(path, variable)
                path.patches[target] = (value, width, tainted or read_taint)
            elif op == "exec":
                if args[0] < 0:
                    raise _Unsupported("task start without a resolved procedure")
                path.pending.append(args[0])
            else:
                # Includes "invalid": the compiler could not bound this code.
                raise _Unsupported(f"unsupported model operation {op}")
            frame.index = nxt

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
        path.loops.pop((frame.proc, start), None)
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
    dispatched: frozenset[tuple[int, int, int]]


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
    interpreter = _Interpreter(program, state, fresh_source=True)
    try:
        if not roots or any(root not in program for root in roots):
            raise _Unsupported("missing automatic procedure")
        paths = interpreter.run([_fresh_path(roots[0])])
        for root in roots[1:]:
            for path in paths:
                path.frames = [_Frame(root, 0, [])]
                path.loops.clear()
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
        )
    return EntryState(
        Support.Supported,
        "",
        tuple(Outcome(path.slots, frozenset(path.dispatched)) for path in paths),
        frozenset(proc for path in paths for proc in path.triggers | set(path.pending)),
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
    roots = entry.triggers | repeating
    possible: set[int] = set()
    seen: set[int] = set()
    queue = sorted(roots)
    while queue:
        proc = queue.pop()
        if proc in seen:
            continue
        seen.add(proc)
        name = f"main:{proc}"
        if name not in program:
            return LaterState(
                Support.Unsupported, f"missing procedure {name}", frozenset()
            )

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
            ),
            fresh_source=False,
        )
        # Triggers act on the interactions entry created, such as handing over
        # a parked item, so each one starts from every entry outcome.
        starts = []
        for outcome in entry.terminals:
            path = _fresh_path(name)
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
            possible |= path.created | path.dispatched
            queue.extend(path.triggers | set(path.pending))
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
        for outcome in entry.terminals:
            handed = {(t, a) for g, t, a in outcome.dispatched if g == gid}
            kinds |= handed
            active, tainted = bool(handed), False
            for descriptor, write_taint in outcome.slots.values():
                if isinstance(descriptor, Item) and descriptor.global_id == gid:
                    # SAT bit 7 selects four-point geometry, not activation.
                    if descriptor.sat & 0x7F:
                        active = True
                        kinds.add((descriptor.item_type, descriptor.amount))
                    tainted = tainted or write_taint
                elif (
                    isinstance(descriptor, Interaction)
                    and isinstance(descriptor.replaced, Item)
                    and descriptor.replaced.global_id == gid
                ):
                    tainted = tainted or write_taint
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
        cached = self._entries.get(key)
        if cached is not None and all(
            (state.flag(*read[1:]) if read[0] == "flag" else state.variable(read[1]))
            == value
            for read, value in cached[0].items()
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

        result = room_script_state(
            program,
            GameState(flag, variable, state.approach_variables, state.approach_banks),
            tasks,
            acquisition_flags,
        )
        self._entries[key] = (reads, result)
        return result
