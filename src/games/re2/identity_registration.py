"""RE2-SCENARIO-013: unsealed fixed-context normal identity registration control."""

import json
from dataclasses import dataclass
from enum import Enum

from games.bit_flags import msb_flag_location
from games.re2.event_presence import flag_write_conflicts
from games.re2.native_control import (
    NumericCountPolicy,
    native_bytes,
    native_nonyielding,
)
from games.re2.native_entry_fields import (
    NativeTaskPhase,
    _native_entry_witnesses,
    _NativeEntryWitnesses,
    _task_fields,
    _TaskFields,
)
from games.re2.normal_engine_binding import (
    NORMAL_ENGINE_BINDING_SHA256,
    semantic_profile_digest,
    typed_binding_digest,
)
from games.re2.positive_entry_domain import _NativeIdentityEntryRoles
from games.re2.program_entry_domain import EnteredFrameDomain, entered_frame_domain
from games.re2.scenario_items import scenario_flags
from games.re2.scenario_selection import (
    ScenarioSourceWriteWitnesses,
    VerifiedScenarioContext,
    bind_scenario_context,
)
from games.re2.startup_declarations import BoundStartupDeclarations
from games.re2.structured_control import ControlFrames, PredicateOutcome


class IdentityRegistrationFailure(Enum):
    Binding = "identity registration source/context/native binding mismatch"
    Control = "identity registration native frames or fixed operands are unproved"


@dataclass(frozen=True)
class IdentityRegistrationControl:
    source_roles_sha256: str
    dependencies_sha256: str
    fields: _TaskFields
    fixed_packets: tuple[tuple[str, int, bytes, int, int, int], ...]
    births: tuple[tuple[str, int, str, tuple[int, ...]], ...]
    edges: tuple[tuple[str, int, tuple[int, ...]], ...]
    atomic_opcodes: frozenset[int]


def identity_registration_control(
    data: bytes,
    room: dict,
    profile: dict,
    context: VerifiedScenarioContext,
    source: _NativeIdentityEntryRoles,
    writes: ScenarioSourceWriteWitnesses,
    native: _NativeEntryWitnesses,
    bound: BoundStartupDeclarations,
) -> IdentityRegistrationControl | IdentityRegistrationFailure:
    """Qualify continuations, never infer a registration from an entry inventory."""
    if (
        type(context) is not VerifiedScenarioContext
        or bind_scenario_context(profile, bound.declarations) != context
        or type(source) is not _NativeIdentityEntryRoles
        or type(writes) is not ScenarioSourceWriteWitnesses
        or type(native) is not _NativeEntryWitnesses
        or native != _native_entry_witnesses(bound.entry_resources.executable)
        or not bound.ordinary_ingress.covers(data, room)
        or typed_binding_digest((bound.entry_resources, bound.declarations))
        != NORMAL_ENGINE_BINDING_SHA256
    ):
        return IdentityRegistrationFailure.Binding
    domain = entered_frame_domain(data, room, writes)
    if type(domain) is not EnteredFrameDomain or source.frame_domain != domain:
        return IdentityRegistrationFailure.Control
    programs = room["programs"]
    banks = {
        r["bank"]: (int(r["address_ps1"], 0), r["width"]) for r in profile["flag_banks"]
    }
    fixed = {(r["bank"], r["bit"]): r["expected"] for r in scenario_flags(profile)}
    words, aliases = flag_write_conflicts(banks, frozenset(fixed))
    rows = [(key, r) for key, p in programs.items() for r in p["commands"]]
    if any(
        (r["bank"], r["bit"]) in aliases for _, r in rows if r["kind"] == "flag_write"
    ):
        return IdentityRegistrationFailure.Control
    packets, outcomes = [], []
    for key, program in programs.items():
        predicates = []
        for row in program["commands"]:
            if row["kind"] != "flag_check" or (row["bank"], row["bit"]) not in fixed:
                continue
            at, end = row["offset"], row["next"]
            packet = data[at:end]
            if packet != bytes((0x21, row["bank"], row["bit"], row["expected"])) or any(
                c.target_offset < end and at < c.target_offset + c.width
                for c in writes.copies
            ):
                return IdentityRegistrationFailure.Control
            address, mask = msb_flag_location(banks[row["bank"]][0], row["bit"])
            if address not in words or not words[address] & mask:
                return IdentityRegistrationFailure.Control
            actual = fixed[row["bank"], row["bit"]]
            packets.append((key, at, packet, address, mask, actual))
            predicates.append(
                (
                    at,
                    PredicateOutcome.Matches
                    if actual == row["expected"]
                    else PredicateOutcome.DoesNotMatch,
                )
            )
        if predicates:
            outcomes.append((key, tuple(predicates)))
    executable = bound.entry_resources.executable
    fields = _task_fields(
        data,
        programs,
        phase=NativeTaskPhase.Ordinary,
        role=ControlFrames.NativeIdentityRegistration,
        numeric_counts=NumericCountPolicy.IdentityConservative,
        predicates=tuple(outcomes),
        frame_domain=domain,
    )
    if type(fields) is not _TaskFields:
        return IdentityRegistrationFailure.Control
    atomic = set(bound.ordinary_ingress.atomic_opcodes)
    # Only the separately bound IF/CK/ENDIF graphs gain local atomicity. No
    # global ingress opcode or another policy's registration behavior changes.
    for opcode in (6, 7, 8):
        entry = int.from_bytes(
            native_bytes(executable, 0x800A74C8 + 4 * opcode, 4), "little"
        )
        if entry == {6: 0x80053924, 7: 0x80053964, 8: 0x800539A0}[
            opcode
        ] and native_nonyielding(executable, entry, {}):
            atomic.add(opcode)
    births, blocked = [], set()
    handler = int.from_bytes(native_bytes(executable, 0x800A74D8, 4), "little")
    installer_atomic = handler == 0x800538A4 and native_nonyielding(
        executable, handler, {}
    )
    for key, row in rows:
        if row["opcode"] != 4:
            continue
        at = row["offset"]
        packet = data[at : row["next"]]
        owners = {
            (task, depth) for owner, task, depth in fields.entries if owner == key
        }
        target = f"17:{packet[3]}"
        producer = (key, at, target, tuple(range(2, 10)))
        if (
            installer_atomic
            and len(packet) == 4
            and packet[1:3] == b"\xff\x18"
            and owners
            and all(task in (0, 1) for task, _ in owners)
            and producer in fields.producers
        ):
            # Phase-zero AUTO scans only2..9, ending at9 even if busy. It
            # installs without running the child; caller0/1 keeps its saved PC.
            # The pinned installer clears six Work words and returns without
            # a scheduler call. Child AI and later scheduling gain no contract.
            births.append(producer)
        else:
            blocked.add((key, at))
    if installer_atomic:
        atomic.add(4)
    edges = tuple(
        (key, at, () if (key, at) in blocked else targets)
        for key, frame in fields.frames
        for at, targets in frame.edges
    )
    return IdentityRegistrationControl(
        typed_binding_digest(source),
        typed_binding_digest(
            (
                data,
                json.dumps(room, sort_keys=True),
                semantic_profile_digest(profile),
                context,
                native,
                writes,
                bound.ordinary_ingress,
            )
        ),
        fields,
        tuple(packets),
        tuple(births),
        edges,
        frozenset(atomic),
    )
