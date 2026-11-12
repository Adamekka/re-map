"""RE2-SCENARIO-008: registration origins under initialized engine execution.

Reset writes through an existing pointer, including NULL. Absence can use
ordinary registration origins only when no consumer can dispatch that NULL
descriptor. This capability grants no positive, entry, door or whole-source
rights and is valid only for the prefix's exact loaded-source binding.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from enum import Enum

from games.re2.known_puzzle_items import _DeclaredPrefixFacts, _known_declared_items
from games.re2.positive_prefix import VerifiedNormalEnginePositivePrefix
from games.re2.room_entry_contract import VerifiedRoomEntryContract
from games.re2.scenario_selection import ScenarioSelectionSupport
from games.re2.script_dispatch_items import ScriptItemDispatchConfig
from games.re2.startup_declarations import VerifiedStartupDeclarationContract


class RegistrationFailure(Enum):
    Binding = "registration prefix binding mismatch"
    Prefix = "registration startup prefix is unsupported"
    Kind = "registration consumer kind is unsupported"
    Dispatch = "scripted dispatch can consume an unregistered descriptor"


@dataclass(frozen=True, init=False)
class VerifiedPersistentRegistration:
    prefix: VerifiedNormalEnginePositivePrefix
    registered_slots: frozenset[int]
    dispatches: tuple[tuple[str, int, int], ...]
    source_kinds: frozenset[int]
    _authority: tuple

    def __init__(self):
        # Only the compiler may bind companion facts to its actual traversal;
        # dataclass replacement must not mint coordinated field/receipt edits.
        raise TypeError("persistent registration requires the source compiler")

    def matches(
        self,
        data: bytes,
        room: dict,
        profile: dict,
        contract: VerifiedStartupDeclarationContract,
    ) -> bool:
        assert all(
            getattr(self, field.name) is value
            for field, value in zip(fields(self)[:-1], self._authority, strict=True)
        )
        return self.prefix.matches(data, room, profile, contract)


def persistent_registration(
    data: bytes,
    room: dict,
    profile: dict,
    entry: VerifiedRoomEntryContract,
    dispatch: ScriptItemDispatchConfig,
    prefix: VerifiedNormalEnginePositivePrefix,
) -> VerifiedPersistentRegistration | RegistrationFailure:
    assert type(entry) is VerifiedRoomEntryContract
    assert type(dispatch) is ScriptItemDispatchConfig
    assert type(prefix) is VerifiedNormalEnginePositivePrefix
    if not prefix.matches(data, room, profile, prefix.context.declaration_contract):
        return RegistrationFailure.Binding
    rows = [(key, row) for key, p in room["programs"].items() for row in p["commands"]]
    kinds = frozenset(
        data[row["offset"] + 2]
        for _, row in rows
        if row["kind"] in ("item", "door", "interaction", "reset")
    )
    # These inspected native classes preserve registry pointers. Other kinds,
    # including kind13's cross-slot reads, have no consumer-isolation right.
    if not kinds <= {0, 1, 2, 4, 5}:
        return RegistrationFailure.Kind
    facts = _known_declared_items(
        data,
        room,
        profile,
        entry,
        dispatch,
        prefix.context.declaration_contract,
        prefix.context,
        ScenarioSelectionSupport.Unaudited,
        prefix,
    )
    if not isinstance(facts, _DeclaredPrefixFacts):
        return RegistrationFailure.Prefix
    dispatches = tuple(
        (key, row["offset"], data[row["offset"] + 1])
        for key, row in rows
        if row["opcode"] == 0x47
    )
    # All empty slots alias physical zero. A Reset there is observable through
    # any other empty scripted47 slot. Manual scanning alone skips NULL.
    if any(slot not in facts.registered_slots for _, _, slot in dispatches):
        return RegistrationFailure.Dispatch
    values = prefix, facts.registered_slots, dispatches, kinds
    result = object.__new__(VerifiedPersistentRegistration)
    for field, value in zip(fields(result)[:-1], values, strict=True):
        object.__setattr__(result, field.name, value)
    object.__setattr__(result, "_authority", values)
    assert result.matches(data, room, profile, prefix.context.declaration_contract)
    return result
