"""RE2-SCENARIO-009: source-bound normal-engine identity filtering only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from enum import Enum

from games.re2.native_control import native_bytes
from games.re2.normal_engine_binding import (
    NORMAL_ENGINE_BINDING_SHA256,
    semantic_profile_digest,
    typed_binding_digest,
)
from games.re2.positive_entry_domain import (
    SourceEntryPolicy,
    _auxiliary_break_reads,
    _source_entry_roles,
    _SourceEntryRoles,
)
from games.re2.scenario_entry_scope import (
    _ScopePolicy,
    _source_scope_facts,
    _SourceScopeFacts,
)
from games.re2.scenario_items import scenario_flags
from games.re2.scenario_selection import (
    SCENARIO_EXECUTABLE_SHA256,
    ScenarioSourceWriteWitnesses,
    SourceWritePolicy,
    VerifiedScenarioContext,
    bind_scenario_context,
    scenario_source_write_witnesses,
)
from games.re2.source_registration import guaranteed_registration
from games.re2.source_task_control import TaskControlSupport
from games.re2.startup_declarations import (
    BoundStartupDeclarations,
    StartupDeclarationAuditConfig,
    startup_declaration_audit,
    startup_flag_banks_match,
)

IDENTITY_FILTERING_AUDIT = "slus00748-trusted-normal-identity-filtering-v1"
IDENTITY_FILTERING_PROFILE_SHA256 = (
    "561e1a35af80fabb58887271476861ab9322f2e5c1525c3b52806bc2520b699c"
)
IDENTITY_FILTERING_CATALOG_SHA256 = (
    "11fd9074594ed0e455417a05d93d610bb6c59ef49a81208be3fa9f764b4b4a9f"
)
HISTORICAL_FLAGS = ((1, 0, 0), (1, 1, 0), (1, 6, 0), (0, 25, 1))
_SEAL = object()


class IdentityFilteringPolicy(Enum):
    Unaudited = "identity filtering unaudited"
    TrustedNormalEngine = "trusted normal initialized engine"


class IdentityFilteringFailure(Enum):
    Binding = "identity filtering native, resource or source binding mismatch"
    Source = "identity filtering source effect or selector is unsupported"
    Control = "identity filtering source or auxiliary frame is unsupported"
    Dispatch = "identity filtering dispatch lacks guaranteed non-replacing registration"
    OptOut = "identity filtering requires explicit revision opt-in"


def identity_filtering_policy(profile: dict) -> IdentityFilteringPolicy:
    if "identity_filtering_policy" not in profile:
        return IdentityFilteringPolicy.Unaudited
    if (
        profile["identity_filtering_policy"]
        != {
            "audit": IDENTITY_FILTERING_AUDIT,
            "executable_sha256": SCENARIO_EXECUTABLE_SHA256,
        }
        or semantic_profile_digest(profile) != IDENTITY_FILTERING_PROFILE_SHA256
        or profile["profile_id"] != "re2_leon_a_slus00748"
        or profile["executable_identity"].rpartition(" SHA256 ")[2]
        != SCENARIO_EXECUTABLE_SHA256
        or tuple((r["bank"], r["bit"], r["expected"]) for r in scenario_flags(profile))
        != HISTORICAL_FLAGS
    ):
        raise ValueError("unsupported RE2 normal-engine identity filtering policy")
    return IdentityFilteringPolicy.TrustedNormalEngine


@dataclass(frozen=True, init=False)
class NormalEngineIdentityFiltering:
    source_data: bytes
    room_json: str
    profile_json: str
    context: VerifiedScenarioContext
    protected_programs: frozenset[str]
    entry_locations: frozenset[tuple[str, int]]
    source_writes: ScenarioSourceWriteWitnesses
    source_roles: _SourceEntryRoles
    auxiliary_break_reads: tuple[tuple[int, str, int, int], ...]
    must_registered: frozenset[int]
    _binding: tuple

    def __init__(self, *args, **kwargs):
        raise TypeError("identity filtering requires the owned-source compiler")

    def matches(
        self, data: bytes, room: dict, profile: dict, context: VerifiedScenarioContext
    ) -> bool:
        assert self._binding[0] is _SEAL
        assert all(
            getattr(self, field.name) is part
            for field, part in zip(fields(self)[:-1], self._binding[1:], strict=True)
        )
        return (
            data == self.source_data
            and _json(room) == self.room_json
            and _json(profile) == self.profile_json
            and typed_binding_digest(context) == typed_binding_digest(self.context)
        )


def _json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def identity_filtering_catalog_digest(rooms: list[dict]) -> str:
    # A creator offset alone does not bind its item identity. Include competing
    # AOT origins and Reset inputs so metadata drift cannot turn an unresolved
    # ordinary pickup into a file or silently remove it from completion.
    source_fields = (
        "id",
        "stage",
        "room",
        "source",
        "size",
        "sha256",
        "items",
        "doors",
        "reset_item_variants",
        "reset_item_candidates",
        "reset_candidate_descriptors",
        "reset_candidate_source_failure",
        "candidate_list_complete",
        "identity_filtering_items",
    )
    if any(
        type(room) is not dict or not set(source_fields) <= room.keys()
        for room in rooms
    ):
        raise ValueError("RE2 identity filtering catalog lacks source descriptors")
    return hashlib.sha256(
        _json(
            {
                room["id"]: {field: room[field] for field in source_fields}
                for room in rooms
            }
        ).encode()
    ).hexdigest()


# These are independently inspected filtering roles. The exact full binder also
# protects native producers, auxiliary scripts and resources outside the windows.
_NATIVE_WINDOWS = (
    (
        0x8005478C,
        520,
        "6bc83d7cf4e99ad0d9f5192c3e4cb4d7f3d8dc95a8c291a0ca31ee166227af05",
    ),
    (
        0x80055260,
        684,
        "aead22d7fb008abcb03651512058cccbc7365dc4f3ac48de9e1ce5340a7f45a6",
    ),
    (
        0x8005714C,
        1480,
        "178350b14ecebc82eace0a9a28ccfab8b2c6cac8a27a2fbf72680a5a07a57825",
    ),
    (
        0x80055C00,
        568,
        "4eef77dab709eefdde25ae6c09d736894d2c54826f88ddff66a055191958d682",
    ),
    (
        0x80011228,
        176,
        "c308b5c63e4c18d09953af98d2880be8ec33f92e3b1af4dd8828de7b24c16889",
    ),
    (
        0x80058A8C,
        76,
        "fe54141bea92d23adcd259dae31d3ad373a38d84d5167ea84fc0a3d46e2cf332",
    ),
    (
        0x80051980,
        64,
        "4d547670ea6a7fd2b14c3c708584d33379addfb2b351179d6753d7b1c9270271",
    ),
    (
        0x80053138,
        264,
        "bb949e6d6055312ab19d81876c29bd1dcc2b136716d35cc97c9022f0f95f3907",
    ),
    (
        0x800538A4,
        128,
        "e7b522273320dbfc0cc4ce549a58a3d14d17bdce1c2f6e69033807e880e68371",
    ),
    (
        0x80054020,
        664,
        "360ff21e546ef91d16f938422756a3344db7fa70c70c41122c584a2f72065b75",
    ),
    (
        0x800A73C4,
        60,
        "bd5f3053faab22c27a3926da9d199b7af16fe18e20f9b82c325f740427b8ba0f",
    ),
    (
        0x80011470,
        20,
        "e5ce74886012117323ee44e58408747af2cadac527984761d52f763b2ff44843",
    ),
    (
        0x80056884,
        0x64,
        "811437a9044307fc679c1da437a95b434bd724de91bf1f707554152bf8111a2c",
    ),
    (
        0x80056A38,
        0x1A0,
        "41b5ef3b54bb7541d8fb6880233c0dd550bf8782166e9b8a48a6a3d69a1b51cc",
    ),
    (
        0x8001CEFC,
        192,
        "4bf9ba0e9b571f695041a93ca1726c8e89781d62797956b69570da95d43cc437",
    ),
    (
        0x800592F8,
        0x20,
        "8f213d5bc91873fbea0888fd2244664d744d29ea427392172e066b24b8e698a7",
    ),
    (
        0x80059318,
        0x30,
        "2ca4da930797be95c99fa308af4054895cb2f43c7013aaf4fb6448039bfc3036",
    ),
    (
        0x80052004,
        256,
        "31fe55d98ae041f256d49a1f766a9e2496351e46ff50628dd17f88f53f7c9299",
    ),
)


def normal_engine_identity_filtering(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
) -> NormalEngineIdentityFiltering | IdentityFilteringFailure:
    """Check full owned binding, neutral facts and this policy's closed effects."""
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert type(bound) is BoundStartupDeclarations
    try:
        if identity_filtering_policy(profile) is IdentityFilteringPolicy.Unaudited:
            return IdentityFilteringFailure.OptOut
        config = startup_declaration_audit(profile)
        resources = bound.entry_resources
        context = bind_scenario_context(profile, bound.declarations)
        if not (
            type(config) is StartupDeclarationAuditConfig
            and type(context) is VerifiedScenarioContext
            and startup_flag_banks_match(profile, bound.declarations)
            and resources.selection.resources == config.selection.resources
            and resources.selection.sources == config.selection.sources
            and resources.selection
            == resources.corpus.selection
            == bound.declarations.selection
            and typed_binding_digest(bound.ordinary_ingress)
            == typed_binding_digest(resources.ordinary_ingress)
            and typed_binding_digest((resources, bound.declarations))
            == NORMAL_ENGINE_BINDING_SHA256
            and hashlib.sha256(resources.executable).hexdigest()
            == SCENARIO_EXECUTABLE_SHA256
            and profile["runtime_layout"]["system_mode_mask"] == 0x40
            and profile["runtime_layout"]["system_mode_value"] == 0x40
            and bound.ordinary_ingress.covers(data, room)
            and all(
                hashlib.sha256(
                    native_bytes(resources.executable, at, width)
                ).hexdigest()
                == digest
                for at, width, digest in _NATIVE_WINDOWS
            )
            and int.from_bytes(
                native_bytes(resources.executable, 0x800A73F4, 4), "little"
            )
            == 0x80052004
        ):
            return IdentityFilteringFailure.Binding
        writes = scenario_source_write_witnesses(
            data, room, profile, policy=SourceWritePolicy.IdentityFiltering
        )
        if type(writes) is not ScenarioSourceWriteWitnesses:
            return IdentityFilteringFailure.Source
        source = _source_entry_roles(
            data, room["programs"], writes, policy=SourceEntryPolicy.IdentityFiltering
        )
        if type(source) is not _SourceEntryRoles:
            return IdentityFilteringFailure.Control
        auxiliary = _auxiliary_break_reads(resources, source.foreign_fields)
        if type(auxiliary) is not tuple:
            return IdentityFilteringFailure.Control
        scope = _source_scope_facts(
            data,
            room,
            profile,
            context,
            _ScopePolicy.IdentityFiltering,
            TaskControlSupport.Unaudited,
            source,
        )
        if type(scope) is not _SourceScopeFacts:
            return IdentityFilteringFailure.Source
        must = guaranteed_registration(
            data,
            room,
            source.edges,
            atomic_opcodes=resources.ordinary_ingress.atomic_opcodes,
        )
        if type(must) is not frozenset:
            return IdentityFilteringFailure.Dispatch
        rows = [r for p in room["programs"].values() for r in p["commands"]]
        kinds = {}
        for row in rows:
            if row["kind"] in ("door", "item", "interaction", "reset"):
                kinds.setdefault(data[row["offset"] + 1], set()).add(
                    data[row["offset"] + 2]
                )
        for row in rows:
            if row["opcode"] == 0x47:
                slot = data[row["offset"] + 1]
                # A NULL slot dereferences memory; kind5 can replace its caller.
                # Only the reviewed fixed-store kind12 leaf is admitted here.
                if slot not in must or kinds.get(slot) != {12}:
                    return IdentityFilteringFailure.Dispatch
        values = (
            data,
            _json(room),
            _json(profile),
            context,
            scope.protected_programs,
            scope.entry_locations,
            writes,
            source,
            auxiliary,
            must,
        )
        result = object.__new__(NormalEngineIdentityFiltering)
        for field, value in zip(fields(result)[:-1], values, strict=True):
            object.__setattr__(result, field.name, value)
        object.__setattr__(result, "_binding", (_SEAL, *values))
        assert result.matches(data, room, profile, context)
        return result
    except (KeyError, IndexError, TypeError, ValueError):
        return IdentityFilteringFailure.Binding
