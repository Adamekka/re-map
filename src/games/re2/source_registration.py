"""Neutral guaranteed registrations before the first scheduling boundary."""

from dataclasses import dataclass
from enum import Enum


class RegistrationFlow(Enum):
    Existing = "existing synchronous startup boundaries"


@dataclass(frozen=True)
class RegistrationFailure:
    reason: str


def guaranteed_registration(
    data: bytes,
    room: dict,
    source_edges: tuple[tuple[str, int, tuple[int, ...]], ...],
    *,
    atomic_opcodes: frozenset[int] | RegistrationFlow = RegistrationFlow.Existing,
) -> frozenset[int] | RegistrationFailure:
    """Intersect registrations on every finite synchronous startup outcome."""
    assert (
        atomic_opcodes is RegistrationFlow.Existing or type(atomic_opcodes) is frozenset
    )
    programs = room["programs"]
    rows = {k: {r["offset"]: r for r in p["commands"]} for k, p in programs.items()}
    edges = {(k, at): targets for k, at, targets in source_edges}
    outcomes = []
    pending = [("16:0", programs["16:0"]["entry"], (), frozenset(), frozenset())]
    seen = set()
    while pending:
        key, at, stack, registered, path = pending.pop()
        state = key, at, stack, registered
        if state in seen:
            continue
        if len(seen) >= 20000 or at not in rows[key]:
            return RegistrationFailure("startup_bounds")
        seen.add(state)
        if (key, at) in path:
            outcomes.append(registered)
            continue
        path = path | {(key, at)}
        row = rows[key][at]
        opcode, following = row["opcode"], row["next"]
        if (
            type(atomic_opcodes) is frozenset
            and opcode not in atomic_opcodes
            and row["kind"] not in ("end", "call")
        ):
            # A constructor that might yield before publishing cannot prove
            # registration. The identity compiler needs only pinned atomic births.
            outcomes.append(registered)
            continue
        if row["kind"] in ("door", "item", "interaction"):
            registered = registered | {data[at + 1]}
        if row["kind"] == "end":
            if stack:
                key, at, stack = stack[-1][0], stack[-1][1], stack[:-1]
            elif key == "16:0":
                key, at = "17:0", programs["17:0"]["entry"]
            else:
                outcomes.append(registered)
                continue
            pending.append((key, at, stack, registered, path))
        elif row["kind"] == "call":
            target = f"17:{row['procedure']}"
            pending.append(
                (
                    target,
                    programs[target]["entry"],
                    stack + ((key, following),),
                    registered,
                    path,
                )
            )
        elif (
            opcode in (2, 3, 5, 9, 0x0A, 0x0D, 0x0F, 0x11, 0x17, 0x19, 0x47)
            or opcode == 4
            and data[at + 1] in (0, 1)
        ):
            # Waiting, cycles, replacement or dispatch cannot prove progress.
            outcomes.append(registered)
        elif not edges.get((key, at)):
            outcomes.append(registered)
        else:
            pending.extend(
                (key, target, stack, registered, path) for target in edges[key, at]
            )
    if not outcomes:
        return RegistrationFailure("startup_no_outcome")
    return frozenset.intersection(*outcomes)
