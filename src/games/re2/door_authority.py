"""RE2-DOOR-009: separate opted-in normal-engine door access authority.

All facts are source/compiler owned. Item presence and scenario guard receipts
cannot authorize them. This is static source analysis, not gameplay evidence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from enum import Enum

from games.re2.normal_engine_binding import (
    NORMAL_ENGINE_BINDING_SHA256,
    semantic_profile_digest,
    typed_binding_digest,
)
from games.re2.scenario_entry_scope import (
    DoorSourceFacts,
    DoorSourceFailure,
    _ScopePolicy,
    _source_scope_facts,
)
from games.re2.scenario_items import scenario_flags
from games.re2.scenario_selection import (
    SCENARIO_EXECUTABLE_SHA256,
    VerifiedScenarioContext,
    bind_scenario_context,
)
from games.re2.script_control_limits import programs_digest
from games.re2.source_registration import RegistrationFailure, guaranteed_registration
from games.re2.source_task_control import TaskControlSupport
from games.re2.startup_declarations import (
    BoundStartupDeclarations,
    StartupDeclarationAuditConfig,
    startup_declaration_audit,
    startup_flag_banks_match,
)

DOOR_AUDIT = "slus00748-trusted-normal-door-access-v1"
# Policy rights belong to this exact semantic profile, independent of packaging paths.
DOOR_PROFILE_SHA256 = "561e1a35af80fabb58887271476861ab9322f2e5c1525c3b52806bc2520b699c"
_HISTORICAL_FLAGS = ((1, 0, 0), (1, 1, 0), (1, 6, 0), (0, 25, 1))
_SEAL = object()


class DoorPolicy(Enum):
    Unaudited = "door access unaudited"
    TrustedNormalEngine = "trusted normal initialized engine"


def door_policy(profile: dict) -> DoorPolicy:
    if "trusted_door_policy" not in profile:
        return DoorPolicy.Unaudited
    if (
        profile["trusted_door_policy"]
        != {
            "audit": DOOR_AUDIT,
            "executable_sha256": SCENARIO_EXECUTABLE_SHA256,
        }
        or profile["profile_id"] != "re2_leon_a_slus00748"
        or profile["executable_identity"].rpartition(" SHA256 ")[2]
        != SCENARIO_EXECUTABLE_SHA256
        or semantic_profile_digest(profile) != DOOR_PROFILE_SHA256
        or tuple((r["bank"], r["bit"], r["expected"]) for r in scenario_flags(profile))
        != _HISTORICAL_FLAGS
    ):
        raise ValueError("unsupported RE2 normal-engine door policy")
    return DoorPolicy.TrustedNormalEngine


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class DoorFailure:
    reason: str


@dataclass(frozen=True, init=False)
class DoorAuthority:
    source_sha256: str
    programs_sha256: str
    profile_sha256: str
    room_json: str
    profile_json: str
    reached: frozenset[tuple[str, int]]
    must_registered: frozenset[int]
    fixed_flags: tuple[tuple[int, int, int], ...]
    _binding: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError("door authority requires the owned-source compiler")

    def matches(self, data: bytes, room: dict, profile: dict) -> bool:
        _assert_owned(self)
        return (
            hashlib.sha256(data).hexdigest() == self.source_sha256
            and programs_digest(room["programs"]) == self.programs_sha256
            and _json(room) == self.room_json
            and _json(profile) == self.profile_json
        )


@dataclass(frozen=True, init=False)
class DoorAccessFact:
    slot: int
    creator_offsets: tuple[int, ...]
    stage: int
    room: int
    floor: int
    activation_floor: int
    lock_id: int
    lock_type: int
    enabled: bool
    activation_mask: int
    authority: DoorAuthority
    _binding: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError("door access facts require door authority")

    def matches(self, authority: DoorAuthority) -> bool:
        _assert_owned(self)
        assert type(authority) is DoorAuthority
        _assert_owned(authority)
        return self.authority is authority


def _assert_owned(value) -> None:
    assert value._binding[0] is _SEAL
    assert all(
        getattr(value, field.name) is part
        for field, part in zip(fields(value)[:-1], value._binding[1:], strict=True)
    )


def _owned(cls, *values):
    result = object.__new__(cls)
    for field, value in zip(fields(cls)[:-1], values, strict=True):
        object.__setattr__(result, field.name, value)
    object.__setattr__(result, "_binding", (_SEAL, *values))
    _assert_owned(result)
    return result


def compile_door_authority(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
) -> DoorAuthority | DoorFailure:
    """Bind actual native/resources/source bytes before checking source effects."""
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert type(bound) is BoundStartupDeclarations
    try:
        if door_policy(profile) is not DoorPolicy.TrustedNormalEngine:
            return DoorFailure("policy_opt_out")
        config = startup_declaration_audit(profile)
        context = bind_scenario_context(profile, bound.declarations)
        resources = bound.entry_resources
        if not (
            type(config) is StartupDeclarationAuditConfig
            and type(context) is VerifiedScenarioContext
            and startup_flag_banks_match(profile, bound.declarations)
            and resources.selection.resources == config.selection.resources
            and resources.selection.sources == config.selection.sources
            and resources.selection
            == resources.corpus.selection
            == bound.declarations.selection
            and resources.ordinary_ingress == bound.ordinary_ingress
            and hashlib.sha256(resources.executable).hexdigest()
            == SCENARIO_EXECUTABLE_SHA256
            and typed_binding_digest((resources, bound.declarations))
            == NORMAL_ENGINE_BINDING_SHA256
            and profile["runtime_layout"]["system_mode_mask"] == 0x40
            and profile["runtime_layout"]["system_mode_value"] == 0x40
        ):
            return DoorFailure("native_resource_binding")
        if not bound.ordinary_ingress.covers(data, room):
            return DoorFailure("native_ingress_binding")
        graph = _source_scope_facts(
            data,
            room,
            profile,
            context,
            _ScopePolicy.TrustedDoors,
            TaskControlSupport.Unaudited,
        )
        if type(graph) is DoorSourceFailure:
            return DoorFailure(graph.reason)
        if type(graph) is not DoorSourceFacts:
            return DoorFailure("source_binding")
        must = guaranteed_registration(data, room, graph.edges)
        if type(must) is RegistrationFailure:
            return DoorFailure(must.reason)
        # Aot_on dereferences even a NULL slot. A kind-five callback can replace
        # its caller and advance the new PC; only the adjacent non-callback
        # Reset recipe closes this source-controlled path.
        rows = {
            (k, r["offset"]): r
            for k, p in room["programs"].items()
            for r in p["commands"]
        }
        edges = {(k, at): targets for k, at, targets in graph.edges}
        kinds = {}
        for key, at in graph.reached:
            row = rows[key, at]
            if row["kind"] in ("door", "item", "interaction", "reset"):
                kinds.setdefault(data[at + 1], set()).add(data[at + 2])
        for key, at in sorted(graph.reached):
            if rows[key, at]["opcode"] != 0x47:
                continue
            slot = data[at + 1]
            if slot not in must:
                return DoorFailure("scripted_null_dispatch")
            if 5 in kinds[slot]:
                prev = rows.get((key, at - 10))
                if not (
                    prev is not None
                    and prev["kind"] == "reset"
                    and prev["slot"] == slot
                    and prev["interaction"] != 5
                    and all(
                        start == at - 10
                        for (pk, start), targets in edges.items()
                        if pk == key and at in targets
                    )
                ):
                    return DoorFailure("callback_self_replacement_risk")
        return _owned(
            DoorAuthority,
            room["sha256"],
            programs_digest(room["programs"]),
            semantic_profile_digest(profile),
            _json(room),
            _json(profile),
            graph.reached,
            must,
            _HISTORICAL_FLAGS,
        )
    except (KeyError, IndexError, ValueError, TypeError):
        return DoorFailure("input_binding")


DOOR_ACCESS_FIELDS = (
    "stage",
    "room",
    "floor",
    "activation_floor",
    "lock_id",
    "lock_type",
)


def compile_door_access(
    data: bytes, room: dict, profile: dict, authority: DoorAuthority
) -> tuple[tuple[DoorAccessFact, ...], tuple[dict, ...], tuple[int, ...]]:
    """Check all competing origins and Reset histories, never just door rows."""
    assert type(authority) is DoorAuthority and authority.matches(data, room, profile)
    rows = [
        r
        for k, p in room["programs"].items()
        for r in p["commands"]
        if (k, r["offset"]) in authority.reached
    ]
    facts, gaps = [], []
    reached_offsets = {r["offset"] for r in rows}
    excluded = tuple(
        sorted(d["offset"] for d in room["doors"] if d["offset"] not in reached_offsets)
    )
    for slot in sorted({d["slot"] for d in room["doors"]}):
        creators = [
            r
            for r in rows
            if r["kind"] in ("door", "item", "interaction")
            and data[r["offset"] + 1] == slot
        ]
        resets = [r for r in rows if r["kind"] == "reset" and r["slot"] == slot]
        reasons = []
        if slot not in authority.must_registered:
            reasons.append("no_guaranteed_startup_registration")
        if not creators:
            reasons.append("no_reached_creator")
        if any(r["kind"] != "door" for r in creators):
            reasons.append("competing_non_door_origin")
        if any(r["interaction"] != 1 for r in resets):
            reasons.append("history_dependent_kind_reset")
        variants = []
        origin_geometry = []
        for row in creators:
            if row["kind"] != "door":
                continue
            door = next(d for d in room["doors"] if d["offset"] == row["offset"])
            sat = data[row["offset"] + 3] | (0x80 if door["four_point"] else 0)
            # Geometry/pose may differ. Native Reset changes only the first six
            # pose bytes, not route/floor/lock; SAT class must remain equal.
            variants.append(
                tuple(door[field] for field in DOOR_ACCESS_FIELDS)
                + (bool(sat), sat & 0x7F)
            )
            origin_geometry.append(0x80 if door["four_point"] else 0)
        signatures = set(variants)
        if len(signatures) != 1:
            reasons.append("different_access_target_or_lock")
        for reset in resets:
            if reset["interaction"] == 1 and variants:
                raw_sat = data[reset["offset"] + 3]
                sat = raw_sat & 0x7F
                if raw_sat & 0x80 and 0 in origin_geometry:
                    reasons.append("reset_changes_geometry_selector")
                # Reset preserves the origin's geometry80. A four-point SAT80
                # remains nonzero even with zero low bits.
                if any(
                    (bool(sat | geometry), sat) != variant[-2:]
                    for geometry, variant in zip(origin_geometry, variants, strict=True)
                ):
                    reasons.append("reset_changes_activation")
        offsets = tuple(sorted(r["offset"] for r in creators if r["kind"] == "door"))
        if reasons:
            gaps.append(
                {
                    "slot": slot,
                    "creator_offsets": list(offsets),
                    "reasons": sorted(set(reasons)),
                }
            )
        else:
            facts.append(
                _owned(
                    DoorAccessFact, slot, offsets, *next(iter(signatures)), authority
                )
            )
    return tuple(facts), tuple(gaps), excluded


def door_access_catalog(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
) -> dict:
    """Serialize only after mandatory source-bound door authority consumption."""
    authority = compile_door_authority(data, room, profile, bound)
    result = {
        "audit": DOOR_AUDIT,
        "source_sha256": room["sha256"],
        "programs_sha256": programs_digest(room["programs"]),
        "profile_sha256": semantic_profile_digest(profile),
        "facts": [],
        "scenario_excluded_offsets": [],
        "unsupported": [],
    }
    if type(authority) is DoorFailure:
        result["unsupported"] = [
            {
                "slot": slot,
                "creator_offsets": sorted(
                    d["offset"] for d in room["doors"] if d["slot"] == slot
                ),
                "reasons": ["source:" + authority.reason],
            }
            for slot in sorted({d["slot"] for d in room["doors"]})
        ]
    else:
        facts, gaps, excluded = compile_door_access(data, room, profile, authority)
        for fact in facts:
            assert fact.matches(authority) and authority.matches(data, room, profile)
            result["facts"].append(
                {
                    f.name: getattr(fact, f.name)
                    for f in fields(fact)
                    if f.name not in ("authority", "_binding")
                }
            )
        result["unsupported"] = list(gaps)
        result["scenario_excluded_offsets"] = list(excluded)
    return json.loads(_json(result))
