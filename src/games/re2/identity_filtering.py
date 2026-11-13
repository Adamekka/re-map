"""RE2-SCENARIO-010: source-bound native identity filtering only."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, fields
from enum import Enum

from games.re2.native_control import (
    EFFECT_CLEANUP_NATIVE,
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
from games.re2.ordinary_task_ingress import auxiliary_isolation
from games.re2.positive_entry_domain import (
    SourceEntryPolicy,
    _auxiliary_break_reads,
    _NativeIdentityEntryRoles,
    _source_entry_roles,
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
from games.re2.structured_control import ControlFrames

IDENTITY_FILTERING_AUDIT = "slus00748-trusted-normal-identity-filtering-v2"
IDENTITY_FILTERING_PROFILE_SHA256 = (
    "c9afde348a1f7651e33e961443b7fa3c24e208a377587b05edd816c59df11e58"
)
IDENTITY_FILTERING_CATALOG_SHA256 = (
    "70387e94440aef491be72b765f1d55cc87977dd653d5981b70bdcab2dc122407"
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


class _IdentityDispatchKind(Enum):
    FixedFlag = "kind12 fixed flag callback"
    PendingDoor = "kind1 immutable unlocked pending request"


@dataclass(frozen=True)
class _IdentityDispatch:
    slot: int
    kind: _IdentityDispatchKind
    creator_offsets: tuple[int, ...]


def _identity_dispatch(
    data: bytes,
    room: dict,
    slot: int,
    registered: frozenset[int],
    writes: ScenarioSourceWriteWitnesses,
    covered_models: frozenset[int],
) -> _IdentityDispatch | IdentityFilteringFailure:
    """Derive a local callback footprint; this unsealed fact grants no authority."""
    assert type(data) is bytes and type(slot) is int
    assert type(registered) is frozenset and type(covered_models) is frozenset
    assert type(writes) is ScenarioSourceWriteWitnesses
    origins = [
        row
        for program in room["programs"].values()
        for row in program["commands"]
        if row["kind"] in ("door", "item", "interaction", "reset")
        and data[row["offset"] + 1] == slot
    ]
    kinds = {data[row["offset"] + 2] for row in origins}
    if slot not in registered:
        return IdentityFilteringFailure.Dispatch
    offsets = tuple(sorted(row["offset"] for row in origins))
    if kinds == {12}:
        return _IdentityDispatch(slot, _IdentityDispatchKind.FixedFlag, offsets)
    if kinds != {1}:
        return IdentityFilteringFailure.Dispatch
    # The mandatory policy check fixes STATUS1:0=0. This excludes the callback's
    # special helper path; the ordinary busy word remains unknown on both paths.
    assert (1, 0, 0) in HISTORICAL_FLAGS
    for row in origins:
        at = row["offset"]
        packet = data[at : row["next"]]
        if row["kind"] != "door" or row["opcode"] not in (0x3B, 0x68):
            return IdentityFilteringFailure.Dispatch
        four = row["opcode"] == 0x68
        payload = 22 if four else 14
        # Native68 installs the geometry bit itself. A rectangular record with
        # that bit already set would select a payload outside its physical shape.
        if len(packet) != (40 if four else 32) or not four and packet[3] & 0x80:
            return IdentityFilteringFailure.Dispatch
        if (
            packet[payload + 15] & 0x80
            or packet[payload + 12] not in covered_models
            or any(
                copy.target_offset < row["next"]
                and at < copy.target_offset + copy.width
                for copy in writes.copies
            )
        ):
            return IdentityFilteringFailure.Dispatch
    return _IdentityDispatch(slot, _IdentityDispatchKind.PendingDoor, offsets)


@dataclass(frozen=True, init=False)
class NormalEngineIdentityFiltering:
    source_data: bytes
    room_json: str
    profile_json: str
    context: VerifiedScenarioContext
    protected_programs: frozenset[str]
    entry_locations: frozenset[tuple[str, int]]
    source_writes: ScenarioSourceWriteWitnesses
    source_roles: _NativeIdentityEntryRoles
    native_entries: _NativeEntryWitnesses
    auxiliary_fields: tuple[tuple[int, _TaskFields], ...]
    dispatches: tuple[_IdentityDispatch, ...]
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
    EFFECT_CLEANUP_NATIVE,
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


# Full callback/renderer/world windows accompany the common native entry proof.
# Whole owned resource/ingress binding remains required; these are not standalone
# capabilities or a general renderer/heap/DMA safety theorem.
_NATIVE_IDENTITY_WINDOWS = (
    (
        0x80057EF0,
        232,
        "62ce8f46d6caa0339ae6b47ce2c8b238ce7af55ae9ab1c8433c76c235ad7a28e",
    ),
    (
        0x80057FD8,
        80,
        "0a243cd1dc1687bd2110cf5ccdf5fc57d2d8fc62475bc0e97475c04c5fe763db",
    ),
    (
        0x8002C2B0,
        116,
        "16b5fa5f892d7dd9ba38268ddc760387ff67ea44aa00b6691d0a7c9b0be130f3",
    ),
    (
        0x80051514,
        516,
        "3aa961a1519d1d75499e0768bfae4465cd751daab64823f9aa4672ad3c81eeb8",
    ),
    (
        0x800551C8,
        152,
        "75b63c9e98d72d170818720da3e2dfd3dc8ece23d0b6d92f68a4f12cacbacf50",
    ),
    (
        0x80026B7C,
        860,
        "7a7600311bb0bad9dadfff3aaa13b5303a74ba161a5a78f61a0875297baf88eb",
    ),
    (
        0x80013C1C,
        664,
        "917af35745938e01b1ee80ab5b81a4f2816de776d45201732cdc5f7e2c97c1fe",
    ),
    (
        0x80013EB4,
        420,
        "eb490c58f1ac9e9007bc8554538b29c869c53f678b9333e65d56d85229a31a6e",
    ),
    (
        0x80049E48,
        1400,
        "abb25ef30698ec834d7bc8661e0b408b7253d1cb7ac5bdf177ac1786475e8e62",
    ),
    (
        0x80054BE4,
        240,
        "cdc298087b3776be7355f2fe25727b0e0aa38ef137eb2ebea8bd649ade213738",
    ),
    (
        0x80055154,
        116,
        "3ac89bd618207ddc7c84953e22b53de29436d99cf95566b48ba2ad5cac9b3b05",
    ),
    (
        0x8002C1A0,
        272,
        "9dee818177fc291cfc63fe8437971a39edf8d034fc2c792dd450dc7a37585074",
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
                for at, width, digest in (*_NATIVE_WINDOWS, *_NATIVE_IDENTITY_WINDOWS)
            )
            and int.from_bytes(
                native_bytes(resources.executable, 0x800A73F4, 4), "little"
            )
            == 0x80052004
        ):
            return IdentityFilteringFailure.Binding
        native = _native_entry_witnesses(resources.executable)
        if type(native) is not _NativeEntryWitnesses:
            return IdentityFilteringFailure.Binding
        if (
            int.from_bytes(native_bytes(resources.executable, 0x800A73C8, 4), "little")
            != 0x80051514
            or int.from_bytes(
                native_bytes(resources.executable, 0x800109C4, 4), "little"
            )
            != 0x80025970
            or not all(
                native_nonyielding(resources.executable, at, {})
                for at in (0x80057FD8, 0x8002C2B0)
            )
        ):
            return IdentityFilteringFailure.Binding
        auxiliaries = {
            script.model: (script.data, {"programs": json.loads(script.programs_json)})
            for script in resources.corpus.scripts
        }
        if (
            auxiliary_isolation(auxiliaries)
            != bound.ordinary_ingress.preserved_counters
        ):
            return IdentityFilteringFailure.Control
        auxiliary_fields = []
        for model, (aux_data, auxiliary_room) in sorted(auxiliaries.items()):
            result = _task_fields(
                aux_data,
                auxiliary_room["programs"],
                phase=NativeTaskPhase.Auxiliary,
                role=ControlFrames.NativeIdentityFiltering,
            )
            if type(result) is not _TaskFields:
                return IdentityFilteringFailure.Control
            auxiliary_fields.append((model, result))
        writes = scenario_source_write_witnesses(
            data, room, profile, policy=SourceWritePolicy.IdentityFiltering
        )
        if type(writes) is not ScenarioSourceWriteWitnesses:
            return IdentityFilteringFailure.Source
        source = _source_entry_roles(
            data,
            room["programs"],
            writes,
            policy=SourceEntryPolicy.NativeIdentityFiltering,
        )
        if type(source) is not _NativeIdentityEntryRoles:
            return IdentityFilteringFailure.Control
        auxiliary = _auxiliary_break_reads(resources, source.foreign_fields)
        if type(auxiliary) is not tuple:
            return IdentityFilteringFailure.Control
        scope = _source_scope_facts(
            data,
            room,
            profile,
            context,
            _ScopePolicy.NativeIdentityFiltering,
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
        dispatches = []
        for slot in sorted(
            {data[row["offset"] + 1] for row in rows if row["opcode"] == 0x47}
        ):
            dispatch = _identity_dispatch(
                data,
                room,
                slot,
                must,
                writes,
                resources.ordinary_ingress.covered_models,
            )
            if type(dispatch) is not _IdentityDispatch:
                return IdentityFilteringFailure.Dispatch
            dispatches.append(dispatch)
        values = (
            data,
            _json(room),
            _json(profile),
            context,
            scope.protected_programs,
            scope.entry_locations,
            writes,
            source,
            native,
            tuple(auxiliary_fields),
            tuple(dispatches),
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
