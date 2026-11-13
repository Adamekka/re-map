"""Source entries and scenario guards under separate native execution contracts.

Separate normal-engine policies cover guards and positive prefixes. All retain
source-directed control and write checks; neither claims arbitrary-pointer or
DMA safety.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from enum import Enum

from games.bit_flags import msb_flag_location
from games.re2.door_entry import _DoorEntryBinding
from games.re2.event_presence import (
    FLAG_WRITE_OPERATIONS,
    flag_write_conflicts,
    presence_counter_indices,
    presence_flag_write_proof,
)
from games.re2.native_entry_fields import _TaskFields
from games.re2.normal_engine_binding import OWNED_SOURCE_FIELDS
from games.re2.positive_entry_domain import (
    _NativeIdentityEntryRoles,
    _PositiveEntryDomain,
    _SourceEntryRoles,
)
from games.re2.positive_pickup_roles import PickupRolesSupport, _PositivePickupRoles
from games.re2.room_data import decode_room
from games.re2.scenario_items import scenario_flags
from games.re2.scenario_selection import (
    SCENARIO_ENTRY_AUDIT,
    SCENARIO_EXECUTABLE_SHA256,
    SCENARIO_GUARD_AUDIT,
    SCENARIO_NATIVE_WORK_AUDIT,
    SCENARIO_TRUSTED_NATIVE_AUDIT,
    ScenarioSelectionFailure,
    ScenarioSourceWriteWitnesses,
    SourceWritePolicy,
    VerifiedScenarioContext,
    VerifiedScenarioEntryScope,
    VerifiedScenarioGuardScope,
    bind_scenario_context,
    scenario_source_write_witnesses,
)
from games.re2.script_control_limits import (
    calls_fit_native_frames,
    programs_digest,
)
from games.re2.source_task_control import (
    TaskControlFailure,
    TaskControlSupport,
    VerifiedSourceTaskControl,
)
from games.re2.structured_control import (
    ControlFrames,
    PredicateOutcome,
    StructuredControl,
    structured_control,
)


class _UnprovedEntry(Exception):
    def __init__(self, reason: str):
        self.reason = reason


@dataclass(frozen=True)
class DoorSourceFailure:
    reason: str


@dataclass(frozen=True)
class DoorSourceFacts:
    reached: frozenset[tuple[str, int]]
    edges: tuple[tuple[str, int, tuple[int, ...]], ...]


class _SourceEffects(Enum):
    Existing = "all existing source effects checked"


class _ScopePolicy(Enum):
    AuditedNativeWork = "audited native work"
    TrustedNormalEngine = "trusted normal engine"
    TrustedPositivePrefix = "trusted normal positive prefix"
    TrustedDoors = "trusted normal door access"
    IdentityFiltering = "trusted normal identity filtering"
    NativeIdentityFiltering = "trusted bounded native identity filtering"


@dataclass(frozen=True)
class _SourceScopeFacts:
    source_sha256: str
    programs_sha256: str
    protected_programs: frozenset[str]
    entry_locations: frozenset[tuple[str, int]]


# RE2-SCENARIO-006: these additional selectors write Work+0/2 u16, +7 u8,
# +10E u16 and +3C u32. Normal owned records permit scalar state changes;
# this grants no pointer-field permission or stricter positive-entry right.
_TRUSTED_SCALAR_MEMBERS = frozenset((0, 1, 5, 7, 12))


# These handlers have inspected initialized-native-work roles: scalar state,
# actors, camera/audio/render work and registered interactions. Their source
# writes (Copy, model, collision and camera records) are additionally bounded
# by the mandatory selection compiler. Unlisted effects receive no entry right.
_ENTRY_PRESERVING_NATIVE_EFFECTS = frozenset(
    (
        0,
        1,
        2,
        3,
        4,
        6,
        7,
        8,
        9,
        0x0A,
        0x0D,
        0x0E,
        0x0F,
        0x10,
        0x11,
        0x12,
        0x13,
        0x14,
        0x16,
        0x17,
        0x18,
        0x1A,
        0x1D,
        0x21,
        0x22,
        0x23,
        0x24,
        0x25,
        0x26,
        0x27,
        0x29,
        0x2B,
        0x2C,
        0x2D,
        0x2E,
        0x2F,
        0x30,
        0x31,
        0x32,
        0x33,
        0x34,
        0x35,
        0x36,
        0x37,
        0x38,
        0x3A,
        0x3B,
        0x3C,
        0x3D,
        0x3E,
        0x3F,
        0x40,
        0x41,
        0x42,
        0x43,
        0x44,
        0x46,
        0x47,
        0x4B,
        0x4E,
        0x51,
        0x53,
        0x54,
        0x57,
        0x58,
        0x5B,
        0x5E,
        0x61,
        0x62,
        0x66,
        0x67,
        0x68,
        0x69,
        0x6D,
        0x6F,
        0x74,
        0x8A,
        0x8B,
        0x8C,
    )
)


# Closed opcode set for this exact native executable, not every future decoded
# effect. These ordinary actor/audio/inventory/render effects use the approved
# engine premise. Source writers still pass the shared partitions, Copy domains
# and frame checks below. 1B/1C/6C are listed only to report their explicit gap.
_DOOR_NATIVE_EFFECTS = frozenset(
    (
        0x0,
        0x1,
        0x2,
        0x3,
        0x4,
        0x5,
        0x6,
        0x7,
        0x8,
        0x9,
        0xA,
        0xB,
        0xC,
        0xD,
        0xE,
        0xF,
        0x10,
        0x11,
        0x12,
        0x13,
        0x14,
        0x15,
        0x16,
        0x17,
        0x18,
        0x19,
        0x1A,
        0x1B,
        0x1C,
        0x1D,
        0x21,
        0x22,
        0x23,
        0x24,
        0x25,
        0x26,
        0x27,
        0x28,
        0x29,
        0x2A,
        0x2B,
        0x2C,
        0x2D,
        0x2E,
        0x2F,
        0x30,
        0x31,
        0x32,
        0x33,
        0x34,
        0x35,
        0x36,
        0x37,
        0x38,
        0x39,
        0x3A,
        0x3B,
        0x3C,
        0x3D,
        0x3E,
        0x3F,
        0x40,
        0x41,
        0x42,
        0x43,
        0x44,
        0x46,
        0x47,
        0x48,
        0x49,
        0x4B,
        0x4C,
        0x4E,
        0x4F,
        0x50,
        0x51,
        0x53,
        0x54,
        0x57,
        0x58,
        0x59,
        0x5A,
        0x5B,
        0x5C,
        0x5D,
        0x5E,
        0x5F,
        0x60,
        0x61,
        0x62,
        0x64,
        0x65,
        0x66,
        0x67,
        0x68,
        0x69,
        0x6A,
        0x6B,
        0x6C,
        0x6D,
        0x6E,
        0x6F,
        0x70,
        0x71,
        0x72,
        0x73,
        0x74,
        0x75,
        0x76,
        0x77,
        0x78,
        0x79,
        0x7A,
        0x7B,
        0x7D,
        0x7E,
        0x7F,
        0x80,
        0x81,
        0x82,
        0x83,
        0x84,
        0x85,
        0x86,
        0x87,
        0x88,
        0x89,
        0x8A,
        0x8B,
        0x8C,
    )
)


def scenario_entry_scope(
    data: bytes, room: dict, profile: dict, context: VerifiedScenarioContext
) -> VerifiedScenarioEntryScope | ScenarioSelectionFailure:
    """Qualify entries under the audited initialized-native-work recipe."""
    result = _source_scope_facts(
        data,
        room,
        profile,
        context,
        _ScopePolicy.AuditedNativeWork,
        TaskControlSupport.Unaudited,
    )
    if isinstance(result, ScenarioSelectionFailure):
        return result
    return VerifiedScenarioEntryScope(
        SCENARIO_ENTRY_AUDIT,
        SCENARIO_NATIVE_WORK_AUDIT,
        SCENARIO_EXECUTABLE_SHA256,
        result.source_sha256,
        result.programs_sha256,
        result.protected_programs,
        result.entry_locations,
    )


def scenario_guard_scope(
    data: bytes,
    room: dict,
    profile: dict,
    context: VerifiedScenarioContext,
    control: VerifiedSourceTaskControl | TaskControlFailure | TaskControlSupport,
) -> VerifiedScenarioGuardScope | ScenarioSelectionFailure:
    """Qualify scenario guards while trusting normal native engine execution."""
    result = _source_scope_facts(
        data, room, profile, context, _ScopePolicy.TrustedNormalEngine, control
    )
    if isinstance(result, ScenarioSelectionFailure):
        return result
    return VerifiedScenarioGuardScope(
        SCENARIO_GUARD_AUDIT,
        SCENARIO_TRUSTED_NATIVE_AUDIT,
        SCENARIO_EXECUTABLE_SHA256,
        result.source_sha256,
        result.programs_sha256,
        result.protected_programs,
        result.entry_locations,
    )


def _source_scope_facts(
    data: bytes,
    room: dict,
    profile: dict,
    context: VerifiedScenarioContext,
    policy: _ScopePolicy,
    control: VerifiedSourceTaskControl | TaskControlFailure | TaskControlSupport,
    entry_domain: _PositiveEntryDomain
    | _DoorEntryBinding
    | _SourceEntryRoles
    | _NativeIdentityEntryRoles
    | _SourceEffects = _SourceEffects.Existing,
    *,
    pickup_roles: _PositivePickupRoles
    | PickupRolesSupport = PickupRolesSupport.Existing,
) -> _SourceScopeFacts | DoorSourceFacts | DoorSourceFailure | ScenarioSelectionFailure:
    """Close ordinary source entries without assuming opaque tasks terminate.

    Source/record writers are checked against all protected packets by the
    selection compiler, which must consume this exact source-bound receipt.
    """
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert isinstance(context, VerifiedScenarioContext)
    assert isinstance(policy, _ScopePolicy)
    assert isinstance(
        control, (VerifiedSourceTaskControl, TaskControlFailure, TaskControlSupport)
    )

    door_policy = policy is _ScopePolicy.TrustedDoors
    identity_policy = policy in (
        _ScopePolicy.IdentityFiltering,
        _ScopePolicy.NativeIdentityFiltering,
    )
    native_identity = policy is _ScopePolicy.NativeIdentityFiltering

    def require(condition: bool, reason: str = "source_control_or_write") -> None:
        if not condition:
            raise _UnprovedEntry(reason)

    try:
        actor_byte_writes = frozenset()
        if type(pickup_roles) is _PositivePickupRoles:
            require(policy is _ScopePolicy.TrustedPositivePrefix)
            require(
                pickup_roles.source_data == data
                and json.loads(pickup_roles.room_json) == room
                and json.loads(pickup_roles.profile_json) == profile
                and pickup_roles.bound.declarations == context.declaration_contract
            )
            actor_byte_writes = frozenset(
                (key, at) for key, at, *_ in pickup_roles.facts.actor_writes
            )
        else:
            require(pickup_roles is PickupRolesSupport.Existing)
        require(bind_scenario_context(profile, context.declaration_contract) == context)
        if isinstance(control, VerifiedSourceTaskControl):
            require(
                policy is not _ScopePolicy.AuditedNativeWork
                and control.matches(data, room, context)
            )
        closed_entries = type(entry_domain) is _PositiveEntryDomain
        door_entries = type(entry_domain) is _DoorEntryBinding
        if door_entries:
            require(
                door_policy
                and entry_domain.matches(
                    data, room, profile, context.declaration_contract
                )
            )
        elif closed_entries:
            require(policy is _ScopePolicy.TrustedPositivePrefix)
            require(
                entry_domain.source_data == data
                and json.loads(entry_domain.room_json) == room
                and json.loads(entry_domain.profile_json) == profile
                and entry_domain.bound.declarations == context.declaration_contract
            )
        elif identity_policy:
            require(
                type(entry_domain)
                is (_NativeIdentityEntryRoles if native_identity else _SourceEntryRoles)
            )
        else:
            require(entry_domain is _SourceEffects.Existing)
        source_entries = entry_domain.facts if closed_entries else entry_domain
        layout = profile["runtime_layout"]
        require(
            layout["scenario_work_address_ps1"] == "0x800CE32C"
            and type(layout["scenario_reset_mask"]) is int
            and layout["scenario_reset_mask"] == 0x1000
            and context.declaration_contract.executable_sha256
            == SCENARIO_EXECUTABLE_SHA256
        )
        # The corpus binds later-stage bytes too. Its stage-zero route rights
        # do not become an incoming-door capability for another stage.
        require(
            any(
                witness.room_id == room["id"]
                and witness.path == room["source"]
                and witness.width == room["size"] == len(data)
                and witness.sha256 == room["sha256"] == hashlib.sha256(data).hexdigest()
                for witness in context.declaration_contract.selection.sources
            )
        )
        counters = presence_counter_indices(profile)
        decoded = decode_room(
            data,
            room["source"],
            frozenset(
                (row["bank"], row["bit"]) for row in profile["presence_condition_flags"]
            ),
            counters,
            presence_flag_write_proof(profile)[0],
        )
        require(all(decoded[field] == room[field] for field in OWNED_SOURCE_FIELDS))
        if policy in (
            _ScopePolicy.TrustedPositivePrefix,
            _ScopePolicy.TrustedDoors,
            _ScopePolicy.IdentityFiltering,
            _ScopePolicy.NativeIdentityFiltering,
        ):
            # Exact JSON types matter: Python equality alone equates True/1
            # and can otherwise accept substituted decoded operands.
            require(
                all(
                    json.dumps(decoded[field], sort_keys=True)
                    == json.dumps(room[field], sort_keys=True)
                    for field in (
                        "items",
                        "doors",
                        "reset_item_variants",
                        "programs",
                        "candidate_list_complete",
                    )
                )
            )
        # Door reachability closes its own fixed-scenario frames below. The
        # independent collectible completeness flag can include unreachable
        # orphan markers and grants no door right in either direction.
        programs = room["programs"]
        require(all(key in programs for key in ("16:0", "17:0", "17:1")))
        commands = {
            key: {row["offset"]: row for row in program["commands"]}
            for key, program in programs.items()
        }
        calls = {key: set() for key in programs}
        replacement_sources = set()
        render_initializers = {}
        dispatch_resets = {}
        slot_kinds: dict[int, set[int]] = {}
        bindings = []
        rows = [(key, row) for key, p in programs.items() for row in p["commands"]]
        has_render_updates = any(row["opcode"] == 0x74 for _, row in rows)
        writes = scenario_source_write_witnesses(
            data,
            room,
            profile,
            policy=SourceWritePolicy.NormalDoors
            if door_policy
            else SourceWritePolicy.IdentityFiltering
            if identity_policy
            else SourceWritePolicy.Existing,
        )
        require(
            isinstance(writes, ScenarioSourceWriteWitnesses),
            "explicit_source_write_footprint",
        )
        fixed = {(r["bank"], r["bit"]): r["expected"] for r in scenario_flags(profile)}
        banks = {
            r["bank"]: (int(r["address_ps1"], 0), r["width"])
            for r in profile["flag_banks"]
        }
        fixed_words, aliases = flag_write_conflicts(banks, frozenset(fixed))
        # The shared footprint receipt keeps model/SCA/camera/floor writes out
        # of scripts and their source dependencies. Copy has a narrower right:
        # only these numeric values can change without invalidating an inspected
        # selector, entry, task frame or resource-write destination.
        scalar_immediates = [
            (row["offset"] + (4 if row["opcode"] == 0x23 else 2), row["next"])
            for _, row in rows
            if row["opcode"] in (0x23, 0x32, 0x6D)
        ]
        if policy is _ScopePolicy.TrustedPositivePrefix:
            scalar_immediates.extend(
                (r["offset"] + 2, r["offset"] + 3)
                for _, r in rows
                if r["kind"] == "flag_check"
                and not any(bank == r["bank"] for bank, _ in aliases)
            )
        if closed_entries or identity_policy:
            scalar_immediates.extend(source_entries.numeric_ranges)
        if door_policy:
            # Copy may change values, never source selectors, PC/frame targets,
            # access identity or fixed scenario bits. Each extra domain belongs
            # only to the explicitly opted-in door policy.
            for _, row in rows:
                at, op = row["offset"], row["opcode"]
                if op == 0x0D:
                    scalar_immediates.append((at + 4, row["next"]))
                if row["kind"] in ("flag_check", "flag_write") and not any(
                    bank == row["bank"] for bank, _ in aliases
                ):
                    scalar_immediates.append((at + 2, at + 3))
                for opcode, begin, end in (
                    (0x40, 4, row["next"] - at),
                    (0x6A, 4, 6),
                    (0x6B, 2, 4),
                    (0x60, 6, 14),
                    (0x33, 2, row["next"] - at),
                    (0x39, 2, row["next"] - at),
                    (0x36, 6, row["next"] - at),
                    (0x3A, 6, 14),
                    (0x54, 8, 20),
                ):
                    if op == opcode:
                        scalar_immediates.append((at + begin, at + end))
                if op == 0x6E and data[at + 2] < 128 and data[at + 3] < 7:
                    scalar_immediates.append((at + 4, at + 6))
                if row["kind"] in ("interaction", "reset") and row["interaction"] == 7:
                    # RE2-DOOR-012: the bound native leaf stores any u16 only
                    # into the ordinary actor's numeric +10C field. This grants
                    # no selector, callback, SAT or later-payload Copy domain.
                    payload = 4 if row["kind"] == "reset" else 22 if op == 0x67 else 14
                    # The mandatory fresh reader requires a word-aligned RDT
                    # base. An aligned two-byte interval also forces word Copy
                    # to start at its beginning; either byte remains writable.
                    if (at + payload) % 2 == 0:
                        scalar_immediates.append((at + payload, at + payload + 2))
        mutated_checks = {
            row["offset"]
            for _, row in rows
            if row["kind"] == "flag_check"
            and any(
                copy.target_offset < row["next"]
                and row["offset"] < copy.target_offset + copy.width
                for copy in writes.copies
            )
        }
        require(
            all(
                any(
                    begin <= copy.target_offset
                    and copy.target_offset + copy.width <= end
                    for begin, end in scalar_immediates
                )
                for copy in writes.copies
            ),
            "copy_changes_unclosed_operand",
        )
        for key, row in rows:
            packet = data[row["offset"] : row["next"]]
            opcode = row["opcode"]
            # Camera_back 2A has no operands. Its STATUS set/clear masks
            # 00100000/00000100 are disjoint from fixed scenario bits.
            require(
                opcode in _DOOR_NATIVE_EFFECTS
                if door_policy
                else (
                    opcode in _ENTRY_PRESERVING_NATIVE_EFFECTS
                    or policy is not _ScopePolicy.AuditedNativeWork
                    and opcode in (0x2A, 0x64, 0x65, 0x85)
                    or (closed_entries or identity_policy)
                    and opcode in (5, 0x15, 0x28)
                    or identity_policy
                    and opcode in (0x4C, 0x6A, 0x6B, 0x86, 0x87)
                    or native_identity
                    and opcode in (0x0B, 0x0C, 0x59, 0x5F, 0x60)
                ),
                "unmodeled_native_opcode",
            )
            if native_identity and opcode == 0x59:
                # Mode0 uses ordinary engine music ownership; other native
                # modes do not inherit it. Its LHU needs an even RDT offset.
                require(
                    len(packet) == 4 and packet[1] == 0 and row["offset"] % 2 == 0,
                    "music_request59_bounds",
                )
            if native_identity and opcode == 0x5F:
                # The leaf writes only a fixed audio scalar. Unused high-byte
                # no-store cases remain unsupported, with no implicit default.
                require(
                    len(packet) == 2 and packet[1] < 128,
                    "fixed_audio_scalar5F_bounds",
                )
            if native_identity and opcode == 0x60:
                # Category3 reloads the owned actor table, then actor+16C's
                # render pointer, independently of task Work. Signed indices
                # and stale-destination default categories stay rejected.
                # LHU/SH use even offsets on the required aligned RDT base.
                require(
                    len(packet) == 14
                    and packet[1] == 3
                    and packet[2] < 32
                    and row["offset"] % 2 == 0,
                    "owned_actor_render60_bounds",
                )
            if door_policy or identity_policy:
                if row["kind"] == "flag_write":
                    require(
                        row["bank"] in banks
                        and 0 <= row["bit"] < 256
                        and row["operation"] in FLAG_WRITE_OPERATIONS
                        and (row["bank"], row["bit"]) not in aliases,
                        "scenario_flag_write",
                    )
                if row["kind"] == "reset" and packet[3] & 0x80:
                    origins = [
                        r
                        for _, r in rows
                        if r["kind"] in ("door", "item", "interaction")
                        and data[r["offset"] + 1] == packet[1]
                    ]
                    # Reset preserves old80 and stores six bytes using the old
                    # geometry. Promoting an ordinary origin would redirect a
                    # subsequent Reset/dispatch beyond its original payload.
                    require(
                        bool(origins)
                        and all(r["opcode"] in (0x67, 0x68, 0x69) for r in origins),
                        "reset_changes_geometry_selector",
                    )
                if (
                    row["kind"] == "item"
                    or row["kind"] == "reset"
                    and row["interaction"] == 2
                ):
                    payload = (
                        4 if row["kind"] == "reset" else 22 if opcode == 0x69 else 14
                    )
                    require(
                        struct.unpack_from("<H", packet, payload + 4)[0] < 256,
                        "acquisition_flag_bounds",
                    )
                if row["kind"] in ("interaction", "reset") and row["interaction"] == 6:
                    payload = (
                        4 if row["kind"] == "reset" else 22 if opcode == 0x67 else 14
                    )
                    bank, bit, _ = struct.unpack_from("<3H", packet, payload)
                    require(bank in banks, "scenario_kind6_write")
                    address, mask = msb_flag_location(banks[bank][0], bit & 255)
                    require(
                        not fixed_words.get(address, 0) & mask, "scenario_kind6_write"
                    )
            if row["kind"] == "call":
                target = f"17:{packet[1]}"
                require(target in programs)
                calls[key].add(target)
            elif opcode == 3:
                # This replacement recipe covers main-procedure entries.
                # Auxiliary table borrowing does not grant initializer rights.
                require(door_policy or key.startswith("17:"))
                require(packet[1:3] == b"\0\x18")
                require(f"17:{packet[3]}" in programs)
                replacement_sources.add(key)
            elif opcode == 4:
                # Automatic native allocation cannot replace startup task zero.
                # Its PC advance precedes replacement, unlike Aot_on below.
                require(
                    packet[2] == 0x18
                    and (
                        packet[1] == 0xFF
                        or door_policy
                        and packet[1] < 14
                        or (closed_entries or identity_policy)
                        and 2 <= packet[1] < 10
                    ),
                    "explicit_task_slot",
                )
                target = f"17:{packet[3]}"
                require(target in programs)
            elif opcode == 0x2D:
                # Attachment registration appends to an unbounded native
                # queue that can reach task storage. This work contract covers
                # only model setup without that additional queue ownership.
                if identity_policy:
                    # The fixed reference matrix avoids native parent-pointer
                    # selectors. Attachment queue ownership is the explicit
                    # normal-engine premise, not an unbounded safety theorem.
                    require(packet[7] == 0)
                require(
                    door_policy
                    or identity_policy
                    and packet[3] == 0x82
                    or packet[3] & 0xC0 == 0
                    or closed_entries
                    and (key, programs[key]["entry"])
                    not in entry_domain.facts.entry_locations
                )
            elif opcode == 0x17:
                require(
                    policy is not _ScopePolicy.AuditedNativeWork
                    and (door_policy or key.startswith("17:"))
                    and packet[1:4] == b"\xff\xff\0"
                    and (
                        door_policy
                        or policy
                        in (
                            _ScopePolicy.TrustedPositivePrefix,
                            _ScopePolicy.IdentityFiltering,
                            _ScopePolicy.NativeIdentityFiltering,
                        )
                        and row["target"] in commands[key]
                        or isinstance(control, VerifiedSourceTaskControl)
                        and (key, row["offset"]) in control.gotos
                        or row["target"] == programs[key]["entry"]
                        and all(
                            c["opcode"] not in (1, 3, 6, 7, 8, 0x18)
                            for c in programs[key]["commands"]
                        )
                    ),
                    "goto_depth_escape",
                )
            elif opcode == 5 and (closed_entries or identity_policy):
                require(2 <= packet[1] < 10)
            elif (
                opcode in (0x1B, 0x1C, 0x6C)
                or not door_policy
                and opcode in (5, 0x19, 0x6E)
            ):
                raise _UnprovedEntry(
                    "sound_compaction_write_domain"
                    if opcode == 0x6C
                    else "unmodeled_source_or_control_rewrite"
                )
            elif opcode == 0x64:
                # Scenario filtering trusts the normal renderer, but a source
                # selected Work pointer still needs its own bounded role.
                require(door_policy or packet[4:6] == b"\0\0")
            elif opcode == 0x53 and has_render_updates and not door_policy:
                # Another procedure may initialize a record while this recipe
                # sleeps. Every such initializer must retain the same four
                # owned records, valid blend mode and RGB-mask domain.
                require(packet[1] < 4 and packet[2] < 4 and packet[3] <= 7)
            elif opcode == 0x74 and native_identity:
                # This helper writes one fixed76-byte record, not a sampled
                # pointer. Native buffer/record ownership is the approved premise;
                # selectors and every explicit source write stay independently bound.
                require(len(packet) == 4 and packet[1] < 4, "render_record_bounds")
            elif opcode == 0x74 and not door_policy:
                # Both 53 and 74 call native 8002C2B0. Only this uninterrupted
                # initialized-record recipe reuses 53's existing renderer/OT
                # ownership; a pointer sampled from RAM grants no such right.
                at, record = row["offset"], packet[1]
                # Six-byte 53, four-byte Sleep and six-byte FOR precede 74;
                # the fixed suffix excludes other writers before loop repeat.
                start = at - 16
                require(all(pos in commands[key] for pos in (start, at - 10, at - 6)))
                initializer = data[start : at - 10]
                require(
                    initializer[:2] == bytes((0x53, record))
                    and record < 4
                    and initializer[2] < 4
                    and initializer[3] <= 7
                    and data[at - 10 : at - 8] == b"\x09\x0a"
                    and data[at - 6 : at - 2] == b"\x0d\0\x08\0"
                    and data[row["next"] : at + 8] == b"\x02\0\x0e\0"
                )
                render_initializers.setdefault(key, {})[at] = start
            elif opcode == 0x1D and door_policy:
                require(packet[1] in counters, "copy_counter_bounds")
            elif opcode == 0x29 and (door_policy or identity_policy):
                # Cut_chg masks its high mode bit before selecting camera work.
                require(packet[1] & 0x7F < room["cameras"], "camera_selector_bounds")
            elif opcode == 0x2E:
                category, index = packet[1:3]
                require(category in (1, 2, 3, 4))
                require(
                    category != 3 or index < 32 or door_policy and index in (254, 255),
                    "work_selector_bounds",
                )
                require(category != 4 or index < 32)
            elif opcode == 0x2F:
                # The six native reset words at task+158..170 contain these
                # halfwords. Larger selectors can change another task record.
                require(packet[1] < 12)
            elif opcode in (0x24, 0x25, 0x26, 0x27):
                # Counter arithmetic/copy still uses a source-selected RAM
                # destination. Keep its halfword inside the audited save region.
                index = (
                    packet[3]
                    if opcode == 0x26
                    else packet[2]
                    if opcode == 0x27
                    else packet[1]
                )
                require(index in counters)
            elif opcode == 0x34:
                # These audited member selectors are numeric actor fields,
                # including the animation semaphore, not pointer selectors.
                require(
                    door_policy
                    and packet[1] < 44
                    # Byte state is control data. Only the separately bound
                    # owned atomic actor recipe grants these exact locations.
                    or (key, row["offset"]) in actor_byte_writes
                    or packet[1] in (15, 16, 23, 29)
                    or policy is not _ScopePolicy.AuditedNativeWork
                    and packet[1] in _TRUSTED_SCALAR_MEMBERS
                    # Native 80055D94 stores only Work+1D6 u16. Its normal
                    # actor ownership belongs to the new positive premise;
                    # guard and strict entry selector domains stay unchanged.
                    or policy
                    in (
                        _ScopePolicy.TrustedPositivePrefix,
                        _ScopePolicy.IdentityFiltering,
                        _ScopePolicy.NativeIdentityFiltering,
                    )
                    and packet[1] == 24
                    # Native members11/13 store the owned Work's numeric X/Z
                    # coordinates. The new bound entry role grants no pointer
                    # selector or guard/strict-entry permission.
                    or (closed_entries or identity_policy)
                    and packet[1] in (11, 13)
                    # Member14 stores only the owned Work rotation halfword.
                    or identity_policy
                    and packet[1] == 14
                )
            elif opcode == 0x44:
                # The audited model's presets select states0/17/18. Their
                # owned code and numeric actor fields have no room-PC entry;
                # other presets cannot inherit this initialized-work role.
                require(
                    packet[1] == 0
                    and (
                        packet[2] < 32
                        or door_policy
                        and packet[2] in (254, 255)
                        or identity_policy
                        and packet[2] == 255
                    )
                    and (
                        door_policy
                        and (
                            0x10 <= packet[3] < 0x50 or packet[3] in (0x50, 0x51, 0x55)
                        )
                        or
                        # The trusted engine owns normal loading/AI lifetimes.
                        # Signed actor slots and model selectors still cannot
                        # direct construction outside the native tables.
                        policy is not _ScopePolicy.AuditedNativeWork
                        and 0x10 <= packet[3] < 0x50
                        or packet[3] == 0x22
                        and int.from_bytes(packet[4:6], "little")
                        in (0x0010, 0x4011, 0x4402)
                    )
                )
            elif opcode in (0x35, 0x3D):
                # Member_set reads counter byte2 into member byte1; Member_copy
                # writes counter byte1 from member byte2. The latter sign-extends
                # its counter, so both stay inside the audited positive domain.
                selector = packet[1] if opcode == 0x35 else packet[2]
                counter = packet[2] if opcode == 0x35 else packet[1]
                require(
                    door_policy
                    and selector < 44
                    or selector in (11, 12, 13, 14, 15, 16, 23)
                    or policy is not _ScopePolicy.AuditedNativeWork
                    and selector in _TRUSTED_SCALAR_MEMBERS
                )
                require(counter in counters and counter < 128)
            elif opcode == 0x6E and door_policy:
                # Both part index and field selector are signed native bytes.
                # Ownership is ordinary engine work; negative indices are not.
                require(packet[2] < 128 and packet[3] < 7, "part_selector_bounds")
            elif opcode == 0x4C and identity_policy:
                # Category0 selects a fixed native position. Effect bytes are
                # comparison filters over 96 owned records, never array indices.
                require(packet[3:5] == b"\0\0")
            elif opcode == 0x85:
                # The position predicate indexes player/partner plus 32 enemy
                # pointers. Its truth stays unknown, including the IF-pop edge.
                require(packet[1] < 34 and packet[2] < 34)
            if row["kind"] in ("door", "item", "interaction", "reset"):
                require(packet[1] < 32)
                kind = (
                    1
                    if row["kind"] == "door"
                    else 2
                    if row["kind"] == "item"
                    else packet[2]
                )
                require(kind <= 14)
                slot_kinds.setdefault(packet[1], set()).add(kind)
                bindings.append((key, row, packet, kind))
        for _, row, packet, kind in bindings:
            if kind == 5:
                payload = (
                    4 if row["kind"] == "reset" else 22 if row["opcode"] == 0x67 else 14
                )
                require(packet[payload : payload + 3] == b"\xff\0\x18")
                target = f"17:{packet[payload + 3]}"
                require(target in programs)
        if policy in (
            _ScopePolicy.TrustedPositivePrefix,
            _ScopePolicy.IdentityFiltering,
            _ScopePolicy.NativeIdentityFiltering,
        ):
            require(
                decoded["candidate_list_complete"] and calls_fit_native_frames(calls)
            )
            # Later FF/FF Gotos grant no prefix continuation. The positive
            # walker stops there; normal native field ownership is the approved
            # premise, rather than the old exhaustive task-memory theorem.
            return _SourceScopeFacts(
                room["sha256"],
                programs_digest(programs),
                frozenset(programs),
                source_entries.entry_locations
                if closed_entries or identity_policy
                else frozenset((key, p["entry"]) for key, p in programs.items()),
            )
        for key, row in rows:
            if row["opcode"] == 0x47 and not door_policy:
                at = row["offset"]
                slot = data[at + 1]
                kinds = slot_kinds.get(slot, set())
                # A kind-five dispatch can replace its own final worker and
                # then add two to the new PC. Ordinary entries are insufficient.
                require(bool(kinds))
                if 5 in kinds:
                    require(policy is not _ScopePolicy.AuditedNativeWork)
                    if (
                        isinstance(control, VerifiedSourceTaskControl)
                        and (key, at) in control.dispatches
                    ):
                        # The joint source/input frontier proves allocation
                        # cannot replace this caller. It grants no shifted PC.
                        continue
                    reset = commands[key].get(at - 10)
                    # Door Reset returns one without yielding or calling SCD.
                    # Adjacency plus the control checks below ensure no other
                    # source can change the descriptor before this dispatch.
                    require(
                        reset is not None
                        and reset["next"] == at
                        and reset["kind"] == "reset"
                        and data[at - 10 : at - 7] == bytes((0x46, slot, 1))
                    )
                    dispatch_resets.setdefault(key, {})[at] = at - 10
        require(calls_fit_native_frames(calls))
        # EventNext resets the root IF/loop cells but preserves call depth.
        # Reject the first replacement in every positive-depth chain rather
        # than assuming a replacement target repairs a caller's stale frame.
        # Every procedure's edges are present, so this union already includes
        # callees of callees without a second traversal of the same graph.
        callees = {target for targets in calls.values() for target in targets}
        require(not replacement_sources & callees)

        # Each policy keeps its own frame contract within the shared walk.
        reached_locations, all_edges = set(), []
        for key, program in programs.items():
            predicates = (
                tuple(
                    (
                        row["offset"],
                        PredicateOutcome.Matches
                        if fixed[row["bank"], row["bit"]] == row["expected"]
                        else PredicateOutcome.DoesNotMatch,
                    )
                    for row in program["commands"]
                    if row["kind"] == "flag_check"
                    and (row["bank"], row["bit"]) in fixed
                    and row["offset"] not in mutated_checks
                )
                if door_policy
                else ()
            )
            native_frames = (
                door_entries and type(entry_domain.source_fields) is _TaskFields
            )
            frames = (
                dict(entry_domain.source_fields.frames)[key]
                if native_frames
                else structured_control(
                    data,
                    program,
                    ControlFrames.Doors if door_policy else ControlFrames.Strict,
                    predicates=predicates,
                )
            )
            if not isinstance(frames, StructuredControl):
                raise _UnprovedEntry(frames.value)
            reached_locations.update((key, at) for at in frames.reached)
            edges = dict(frames.edges)
            if door_policy:
                for at in frames.reached:
                    if commands[key][at]["opcode"] != 0x17:
                        continue
                    if native_frames:
                        # Only the separately sealed native producer/field closure
                        # closes these receivers. Door source effects,
                        # creators, Reset and registration retain their checks.
                        continue
                    # FF Goto computes an escaped IF pointer. This door recipe
                    # permits no subsequent consumer of that pointer, unlike
                    # the separate fresh-positive foreign-field capability.
                    scan, visited = [commands[key][at]["target"]], set()
                    while scan:
                        cursor = scan.pop()
                        if cursor in visited:
                            continue
                        require(cursor in commands[key], "goto_target")
                        visited.add(cursor)
                        target_row = commands[key][cursor]
                        if target_row["opcode"] in (1, 3):
                            continue
                        require(
                            target_row["opcode"]
                            not in (
                                6,
                                7,
                                8,
                                9,
                                0x0A,
                                0x0D,
                                0x0E,
                                0x0F,
                                0x10,
                                0x11,
                                0x12,
                                0x13,
                                0x14,
                                0x15,
                                0x16,
                                0x18,
                                0x19,
                                0x1A,
                            ),
                            "goto_receiving_frame_consumer",
                        )
                        scan.append(
                            target_row["target"]
                            if target_row["opcode"] == 0x17
                            else target_row["next"]
                        )
            all_edges.extend(
                (key, start, tuple(sorted(targets)))
                for start, targets in sorted(edges.items())
            )
            for dispatch, reset in dispatch_resets.get(key, {}).items():
                # An IF-failure, loop or switch edge may bypass a lexically
                # adjacent Reset even when its own control frames are legal.
                require(
                    all(
                        start == reset
                        for start, targets in edges.items()
                        if dispatch in targets
                    )
                )
            for update, initializer in (
                render_initializers.get(key, {}) | dispatch_resets.get(key, {})
            ).items():
                # Lexical adjacency alone does not exclude a branch into the
                # recipe. Retain every admitted control edge and its initializer
                # on every path, including loop repeats and failed predicates.
                reached, pending_positions = set(), [program["entry"]]
                while pending_positions:
                    position = pending_positions.pop()
                    if position in reached or position == initializer:
                        continue
                    reached.add(position)
                    pending_positions.extend(edges.get(position, ()))
                require(update not in reached)

        if door_policy:
            return DoorSourceFacts(frozenset(reached_locations), tuple(all_edges))
        # Identity/exclusion uses immutable scenario bits, so a later canonical
        # entry does not need startup exclusivity. Both native and explicit
        # entries still had to establish bounded fresh procedure frames above.
        protected = set(programs)
        return _SourceScopeFacts(
            room["sha256"],
            programs_digest(programs),
            frozenset(protected),
            frozenset((key, programs[key]["entry"]) for key in protected),
        )
    except _UnprovedEntry as error:
        return (
            DoorSourceFailure(error.reason)
            if door_policy
            else ScenarioSelectionFailure.EntryScope
        )
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return ScenarioSelectionFailure.SourceBinding
