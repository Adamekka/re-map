"""Candidate positive startup authority under explicit normal-engine trust.

RE2-STARTUP-007. This binds native ingress and neutral source/write facts. It
neither consumes a guard scope nor grants strict entry or whole-source rights.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import Enum

from games.re2.ordinary_task_ingress import VerifiedOrdinaryTaskIngress
from games.re2.scenario_entry_scope import (
    _ScopePolicy,
    _source_scope_facts,
    _SourceScopeFacts,
)
from games.re2.scenario_items import scenario_flags
from games.re2.scenario_selection import (
    SCENARIO_EXECUTABLE_SHA256,
    ScenarioSelectionFailure,
    VerifiedScenarioContext,
    bind_scenario_context,
)
from games.re2.script_control_limits import NATIVE_CALL_FRAME_COUNT, programs_digest
from games.re2.source_task_control import TaskControlSupport
from games.re2.startup_declarations import (
    BoundStartupDeclarations,
    StartupDeclarationAuditConfig,
    VerifiedStartupDeclarationContract,
    startup_declaration_audit,
    startup_flag_banks_match,
)
from games.re2.startup_entry_selection import BoundEntryResources

POSITIVE_PREFIX_AUDIT = "slus00748-trusted-normal-positive-prefix-v1"
# This derived audit identity comes from the complete owned 69-resource,
# 125-source binder, not from a caller-supplied selection or receipt mirror.
_POSITIVE_BINDING_SHA256 = (
    "727c49593f3d756594049140e357d8c4c6f47aefdb215d7fd6d0a0a79ed670a8"
)
_HISTORICAL_FLAGS = ((1, 0, 0), (1, 1, 0), (1, 6, 0), (0, 25, 1))


def _positive_binding_digest(
    resources: BoundEntryResources, declarations: VerifiedStartupDeclarationContract
) -> str:
    def encode(value):
        # Preserve exact types: JSON alone equates tuple/list, and ordinary
        # Python equality equates bool/int in consistently replaced receipts.
        kind = type(value)
        if kind in (str, int, bool):
            return [kind.__name__, value]
        if kind is bytes:
            return ["bytes", len(value), hashlib.sha256(value).hexdigest()]
        if kind is tuple:
            return ["tuple", [encode(part) for part in value]]
        if kind is frozenset:
            return ["frozenset", sorted(encode(part) for part in value)]
        if is_dataclass(value) and not isinstance(value, type):
            return [
                f"{kind.__module__}.{kind.__qualname__}",
                [
                    [field.name, encode(getattr(value, field.name))]
                    for field in fields(value)
                ],
            ]
        raise ValueError("unsupported positive-prefix binding field")

    return hashlib.sha256(
        json.dumps(encode((resources, declarations)), separators=(",", ":")).encode()
    ).hexdigest()


class PositivePrefixFailure(Enum):
    Policy = "positive prefix requires the explicit revision-bound engine policy"
    Binding = "positive prefix native/resource/source binding mismatch"
    Source = "positive prefix source control or writes are unsupported"


class PositivePrefixPolicy(Enum):
    Unaudited = "positive presence unaudited"
    TrustedNormalEngine = "trusted normal initialized engine"


def positive_prefix_policy(profile: dict) -> PositivePrefixPolicy:
    if "positive_prefix_policy" not in profile:
        return PositivePrefixPolicy.Unaudited
    if (
        profile["positive_prefix_policy"]
        != {
            "audit": POSITIVE_PREFIX_AUDIT,
            "executable_sha256": SCENARIO_EXECUTABLE_SHA256,
        }
        or profile["executable_identity"].rpartition(" SHA256 ")[2]
        != SCENARIO_EXECUTABLE_SHA256
        or int(profile["runtime_layout"]["system_flags_address_ps1"], 0) != 0x800CFB74
        or tuple(
            (row["bank"], row["bit"], row["expected"])
            for row in scenario_flags(profile)
        )
        != _HISTORICAL_FLAGS
    ):
        raise ValueError("unsupported RE2 positive-prefix policy")
    return PositivePrefixPolicy.TrustedNormalEngine


@dataclass(frozen=True)
class _PositivePrefixDerivation:
    resources: BoundEntryResources
    context: VerifiedScenarioContext
    source_data: bytes
    source_sha256: str
    programs_sha256: str
    profile_json: str
    room_json: str
    protected_programs: frozenset[str]
    entry_locations: frozenset[tuple[str, int]]
    roots: tuple[tuple[str, int], ...]
    historical_flags: tuple[tuple[int, int, int], ...]
    call_frames: int


@dataclass(frozen=True)
class VerifiedNormalEnginePositivePrefix(_PositivePrefixDerivation):
    _derivation: _PositivePrefixDerivation

    def __post_init__(self) -> None:
        assert type(self._derivation) is _PositivePrefixDerivation
        assert self._derivation == _PositivePrefixDerivation(
            self.resources,
            self.context,
            self.source_data,
            self.source_sha256,
            self.programs_sha256,
            self.profile_json,
            self.room_json,
            self.protected_programs,
            self.entry_locations,
            self.roots,
            self.historical_flags,
            self.call_frames,
        )
        assert type(self.resources) is BoundEntryResources
        assert type(self.resources.executable) is bytes
        assert (
            hashlib.sha256(self.resources.executable).hexdigest()
            == SCENARIO_EXECUTABLE_SHA256
        )
        assert type(self.resources.ordinary_ingress) is VerifiedOrdinaryTaskIngress
        assert (
            self.resources.selection
            == self.resources.corpus.selection
            == self.resources.ordinary_ingress.selection
        )
        assert type(self.context) is VerifiedScenarioContext
        assert self.context.declaration_contract.selection == self.resources.selection
        assert (
            _positive_binding_digest(self.resources, self.context.declaration_contract)
            == _POSITIVE_BINDING_SHA256
        )
        assert all(type(value) is str for value in (self.profile_json, self.room_json))
        assert type(self.roots) is tuple and tuple(k for k, _ in self.roots) == (
            "16:0",
            "17:0",
        )
        assert type(self.historical_flags) is tuple and all(
            type(row) is tuple and len(row) == 3 and all(type(v) is int for v in row)
            for row in self.historical_flags
        )
        assert type(self.protected_programs) is frozenset
        assert type(self.entry_locations) is frozenset
        assert (
            type(self.call_frames) is int
            and self.call_frames == NATIVE_CALL_FRAME_COUNT
        )
        room, profile = json.loads(self.room_json), json.loads(self.profile_json)
        assert type(room) is dict and type(profile) is dict
        assert {
            "id",
            "source",
            "sha256",
            "size",
            "stage",
            "room",
            "programs",
        } <= room.keys()
        config = startup_declaration_audit(profile)
        assert isinstance(config, StartupDeclarationAuditConfig)
        assert self.resources.selection.resources == config.selection.resources
        assert self.resources.selection.sources == config.selection.sources
        assert (
            positive_prefix_policy(profile) is PositivePrefixPolicy.TrustedNormalEngine
        )
        assert startup_flag_banks_match(profile, self.context.declaration_contract)
        assert profile["runtime_layout"]["system_mode_mask"] == 0x40
        assert profile["runtime_layout"]["system_mode_value"] == 0x40
        assert type(self.source_data) is bytes
        assert hashlib.sha256(self.source_data).hexdigest() == self.source_sha256
        assert self.resources.ordinary_ingress.covers(self.source_data, room)
        assert (
            bind_scenario_context(profile, self.context.declaration_contract)
            == self.context
        )
        facts = _source_scope_facts(
            self.source_data,
            room,
            profile,
            self.context,
            _ScopePolicy.TrustedPositivePrefix,
            TaskControlSupport.Unaudited,
        )
        assert type(facts) is _SourceScopeFacts
        assert (
            facts.source_sha256,
            facts.programs_sha256,
            facts.protected_programs,
            facts.entry_locations,
        ) == (
            self.source_sha256,
            self.programs_sha256,
            self.protected_programs,
            self.entry_locations,
        )
        assert self.source_sha256 == room["sha256"]
        assert self.programs_sha256 == programs_digest(room["programs"])
        assert self.protected_programs == frozenset(room["programs"])
        assert self.entry_locations == frozenset(
            (k, p["entry"]) for k, p in room["programs"].items()
        )
        assert self.roots == tuple(
            (k, room["programs"][k]["entry"]) for k in ("16:0", "17:0")
        )
        assert self.historical_flags == tuple(
            (r["bank"], r["bit"], r["expected"]) for r in scenario_flags(profile)
        )

    def matches(
        self,
        data: bytes,
        room: dict,
        profile: dict,
        contract: VerifiedStartupDeclarationContract,
    ) -> bool:
        # Recheck caller-derived metadata, not only its program digest. JSON
        # copies keep later mutable room/profile edits outside the authority.
        return (
            hashlib.sha256(data).hexdigest() == self.source_sha256
            and all(room.get(k) == v for k, v in json.loads(self.room_json).items())
            and profile == json.loads(self.profile_json)
            and contract == self.context.declaration_contract
            and self.resources.ordinary_ingress.covers(data, room)
        )


def normal_engine_positive_prefix(
    data: bytes,
    room: dict,
    profile: dict,
    bound: BoundStartupDeclarations,
) -> VerifiedNormalEnginePositivePrefix | PositivePrefixFailure:
    """Derive positive authority from the complete owned binder's actual result.

    The approved premise supplies initialized unmodified native execution and
    historical mode ownership. It does not infer historical flags from RAM.
    Source-directed writes, identities and prefix paths still need checking.
    """
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert type(bound) is BoundStartupDeclarations
    try:
        if (
            positive_prefix_policy(profile)
            is not PositivePrefixPolicy.TrustedNormalEngine
        ):
            return PositivePrefixFailure.Policy
        resources = bound.entry_resources
        config = startup_declaration_audit(profile)
        context = bind_scenario_context(profile, bound.declarations)
        if not (
            type(resources) is BoundEntryResources
            and type(resources.executable) is bytes
            and hashlib.sha256(resources.executable).hexdigest()
            == SCENARIO_EXECUTABLE_SHA256
            and isinstance(config, StartupDeclarationAuditConfig)
            and resources.selection.resources == config.selection.resources
            and resources.selection.sources == config.selection.sources
            and resources.selection
            == resources.corpus.selection
            == bound.declarations.selection
            and type(resources.ordinary_ingress) is VerifiedOrdinaryTaskIngress
            and resources.ordinary_ingress == bound.ordinary_ingress
            and resources.ordinary_ingress.selection == resources.selection
            and resources.ordinary_ingress.covers(data, room)
            and _positive_binding_digest(resources, bound.declarations)
            == _POSITIVE_BINDING_SHA256
            and type(context) is VerifiedScenarioContext
            and startup_flag_banks_match(profile, bound.declarations)
            and profile["runtime_layout"]["system_mode_mask"] == 0x40
            and profile["runtime_layout"]["system_mode_value"] == 0x40
        ):
            return PositivePrefixFailure.Binding
        facts = _source_scope_facts(
            data,
            room,
            profile,
            context,
            _ScopePolicy.TrustedPositivePrefix,
            TaskControlSupport.Unaudited,
        )
        if isinstance(facts, ScenarioSelectionFailure):
            return PositivePrefixFailure.Source
        assert type(facts) is _SourceScopeFacts
        derivation = _PositivePrefixDerivation(
            resources,
            context,
            data,
            facts.source_sha256,
            facts.programs_sha256,
            json.dumps(profile, sort_keys=True, separators=(",", ":")),
            json.dumps(room, sort_keys=True, separators=(",", ":")),
            facts.protected_programs,
            facts.entry_locations,
            tuple((k, room["programs"][k]["entry"]) for k in ("16:0", "17:0")),
            tuple(
                (r["bank"], r["bit"], r["expected"]) for r in scenario_flags(profile)
            ),
            NATIVE_CALL_FRAME_COUNT,
        )
        return VerifiedNormalEnginePositivePrefix(
            derivation.resources,
            derivation.context,
            derivation.source_data,
            derivation.source_sha256,
            derivation.programs_sha256,
            derivation.profile_json,
            derivation.room_json,
            derivation.protected_programs,
            derivation.entry_locations,
            derivation.roots,
            derivation.historical_flags,
            derivation.call_frames,
            derivation,
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return PositivePrefixFailure.Binding
