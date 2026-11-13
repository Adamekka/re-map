"""Validate generated door facts at the mandatory fresh-reader boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from games.re2.door_authority import (
    DOOR_ACCESS_FIELDS,
    DOOR_AUDIT,
    DoorPolicy,
    _json,
    door_policy,
)
from games.re2.normal_engine_binding import semantic_profile_digest
from games.re2.scenario_items import scenario_flags
from games.re2.startup_declarations import (
    StartupDeclarationAuditConfig,
    startup_declaration_audit,
)

# Pinned outputs of the owned-source compiler under this audit. This prevents
# edited numeric metadata from manufacturing rights without the compiler inputs.
DOOR_CATALOG_SHA256 = "aab4d3a03b2573d33c60e29410b94ec31725b7d9afaa5c2fb5eadcca566c1a00"
_SEAL = object()


@dataclass(frozen=True)
class DepartedDoorAccess:
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


def _source_binding(room: dict) -> str:
    return _json(
        {
            k: room[k]
            for k in (
                "id",
                "stage",
                "room",
                "source",
                "size",
                "sha256",
                "doors",
                "door_access_catalog",
            )
        }
    )


@dataclass(frozen=True, init=False)
class BoundDoorCatalog:
    facts: tuple[DepartedDoorAccess, ...]
    scenario_excluded_offsets: frozenset[int]
    source_json: str
    applicability: tuple[tuple[int, int, int], ...]
    _binding: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError("door catalogs require validated generated metadata")

    def matches(self, room: dict) -> bool:
        assert self._binding[0] is _SEAL
        assert self.facts is self._binding[1]
        assert self.scenario_excluded_offsets is self._binding[2]
        assert self.source_json is self._binding[3]
        assert self.applicability is self._binding[4]
        return self.source_json == _source_binding(room)


def load_door_catalogs(
    profile: dict, rooms: dict[str, dict], document: dict
) -> dict[str, BoundDoorCatalog]:
    """Opt-out profiles get no door right, even with injected metadata."""
    policy = door_policy(profile)
    if policy is DoorPolicy.Unaudited:
        if "trusted_door_policy" in document or any(
            "door_access_catalog" in r for r in rooms.values()
        ):
            raise ValueError("RE2 normal-engine door facts require explicit opt-in")
        return {}
    config = startup_declaration_audit(profile)
    if (
        type(config) is not StartupDeclarationAuditConfig
        or document.get("trusted_door_policy") != profile["trusted_door_policy"]
    ):
        raise ValueError("RE2 door policy disagrees with its native corpus")
    specs = {s.room_id: s for s in config.selection.sources}
    # Bind the whole corpus, including residuals and scenario exclusions.
    # Missing facts cannot silently become a second, less strict contract.
    catalog = {
        key: room.get("door_access_catalog") for key, room in sorted(rooms.items())
    }
    if hashlib.sha256(_json(catalog).encode()).hexdigest() != DOOR_CATALOG_SHA256:
        raise ValueError("RE2 door catalog differs from the audited compiler output")
    result = {}
    for key, room in rooms.items():
        spec = specs[key]
        raw = catalog[key]
        if (room["source"], room["size"], room["sha256"]) != (
            spec.path,
            spec.width,
            spec.sha256,
        ) or (
            raw["audit"] != DOOR_AUDIT
            or raw["source_sha256"] != spec.sha256
            or raw["profile_sha256"] != semantic_profile_digest(profile)
        ):
            raise ValueError("RE2 door facts are not bound to their source/profile")
        facts = tuple(
            DepartedDoorAccess(**{**f, "creator_offsets": tuple(f["creator_offsets"])})
            for f in raw["facts"]
        )
        excluded = frozenset(raw["scenario_excluded_offsets"])
        for fact in facts:
            creators = [
                d
                for d in room["doors"]
                if d["slot"] == fact.slot and d["offset"] not in excluded
            ]
            if (
                tuple(sorted(d["offset"] for d in creators)) != fact.creator_offsets
                or any(
                    any(
                        d[field] != getattr(fact, field) for field in DOOR_ACCESS_FIELDS
                    )
                    for d in creators
                )
                or set(fact.creator_offsets) & excluded
            ):
                raise ValueError("RE2 door fact has an unbound creator")
        if not facts and not excluded:
            # Residual diagnostics grant no runtime right. Keeping them out of
            # the reader also leaves strict legacy/current paths independent.
            continue
        bound = object.__new__(BoundDoorCatalog)
        source_json = _source_binding(room)
        applicability = tuple(
            (r["bank"], r["bit"], r["expected"]) for r in scenario_flags(profile)
        )
        for name, value in (
            ("applicability", applicability),
            ("facts", facts),
            ("scenario_excluded_offsets", excluded),
            ("source_json", source_json),
            ("_binding", (_SEAL, facts, excluded, source_json, applicability)),
        ):
            object.__setattr__(bound, name, value)
        assert bound.matches(room)
        result[key] = bound
    return result
