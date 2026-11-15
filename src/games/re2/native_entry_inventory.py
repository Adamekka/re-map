"""Complete raw native entry closure, separate from operative frame checks."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from games.re2.positive_entry_domain import PositiveEntryFailure
from games.re2.script_control_limits import (
    NATIVE_CALL_FRAME_COUNT,
    calls_fit_native_frames,
    programs_digest,
)


class NativeTaskPhase(Enum):
    Ordinary = "ordinary tasks 0..9"
    Auxiliary = "door auxiliary tasks 10..13"


@dataclass(frozen=True)
class NativeEntryInventory:
    source_sha256: str
    programs_sha256: str
    phase: NativeTaskPhase
    producers: tuple[tuple[str, int, str, tuple[int, ...]], ...]
    entries: tuple[tuple[str, int, int], ...]
    replacements: tuple[tuple[str, int, str], ...]
    calls: tuple[tuple[str, str], ...]


def native_entry_inventory(
    data: bytes, programs: dict, phase: NativeTaskPhase
) -> NativeEntryInventory | PositiveEntryFailure:
    assert type(phase) is NativeTaskPhase
    auxiliary = phase is NativeTaskPhase.Auxiliary
    # Native roots have no source offset. Their distinct owner marks the zero
    # placeholders; the actual native call sites are bound separately below.
    producers = (
        [("native", 0, "17:0", (10,))]
        if auxiliary
        else [
            ("native", 0, "16:0", (0,)),
            ("native", 0, "17:0", (1,)),
            ("native", 0, "17:1", (0,)),
        ]
    )
    calls = {key: set() for key in programs}
    replacements = []
    for key, program in programs.items():
        for row in program["commands"]:
            at, op = row["offset"], row["opcode"]
            packet = data[at : row["next"]]
            if row["kind"] == "call":
                calls[key].add(f"17:{packet[1]}")
            elif op == 3:
                if auxiliary or packet[1:3] != b"\0\x18":
                    return PositiveEntryFailure.Control
                replacements.append((key, at, f"17:{packet[3]}"))
            elif op == 4:
                # The phase-zero installer maps every selector>=10 to AUTO2..9.
                # Auxiliary phase has its separate explicit10..13/AUTO contract.
                start, limit = (10, 14) if auxiliary else (2, 10)
                tasks = (
                    (packet[1],) if packet[1] < limit else tuple(range(start, limit))
                )
                if packet[2] != 0x18 or auxiliary and packet[1] < 10:
                    return PositiveEntryFailure.Control
                producers.append((key, at, f"17:{packet[3]}", tasks))
            elif not auxiliary and row["kind"] in ("interaction", "reset"):
                if packet[2] != 5:
                    continue
                payload = 4 if row["kind"] == "reset" else 22 if op == 0x67 else 14
                if packet[payload : payload + 3] != b"\xff\0\x18":
                    return PositiveEntryFailure.Control
                producers.append(
                    (key, at, f"17:{packet[payload + 3]}", tuple(range(2, 10)))
                )
    if any(
        not targets <= programs.keys() for targets in calls.values()
    ) or not calls_fit_native_frames(calls):
        return PositiveEntryFailure.Control
    # Include every producer, including an unentered procedure's writers and
    # every Reset alternative. No sampled inactive task can remove a root.
    pending = [
        (target, task, 0)
        for owner, _, target, tasks in producers
        if not auxiliary or owner == "native"
        for task in tasks
    ]
    entries = set()
    while pending:
        key, task, depth = pending.pop()
        if (key, task, depth) in entries:
            continue
        if key not in programs or depth >= NATIVE_CALL_FRAME_COUNT:
            return PositiveEntryFailure.Control
        entries.add((key, task, depth))
        pending.extend((target, task, depth + 1) for target in calls[key])
        for owner, at, target in replacements:
            if owner == key:
                if depth != 0:
                    return PositiveEntryFailure.Control
                pending.append((target, task, depth))
        if auxiliary:
            pending.extend(
                (target, slot, 0)
                for owner, _, target, tasks in producers
                if owner == key
                for slot in tasks
            )
    return NativeEntryInventory(
        hashlib.sha256(data).hexdigest(),
        programs_digest(programs),
        phase,
        tuple(sorted(producers)),
        tuple(sorted(entries)),
        tuple(sorted(replacements)),
        tuple(
            sorted(
                (key, target) for key, targets in calls.items() for target in targets
            )
        ),
    )
