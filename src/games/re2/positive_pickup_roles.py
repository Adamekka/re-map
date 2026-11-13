"""RE2-STARTUP-009: bounded ordinary cleanup and owned actor-state roles.

These facts grant neither entry, filtering, registration nor collection rights.
The shared positive factory and prefix compiler remain the only presence path.
"""

from __future__ import annotations

import hashlib
import json
import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.event_presence import flag_write_conflicts
from games.re2.native_control import EFFECT_CLEANUP_NATIVE, native_bytes
from games.re2.normal_engine_binding import (
    NORMAL_ENGINE_BINDING_SHA256,
    OWNED_SOURCE_FIELDS,
    semantic_profile_digest,
    typed_binding_digest,
)
from games.re2.room_data import decode_room
from games.re2.scenario_selection import (
    ScenarioSourceWriteWitnesses,
    scenario_source_write_witnesses,
)
from games.re2.startup_declarations import BoundStartupDeclarations
from games.re2.structured_control import (
    ControlFrames,
    StructuredControl,
    structured_control,
)


class PickupRolesSupport(Enum):
    Existing = "existing low-flag pickup and scalar member domains"


class PickupRolesFailure(Enum):
    Binding = "ordinary pickup native or owned binding mismatch"
    Actor = "actor byte state lacks an owned atomic reinitialization role"


# The shared cleanup fact is neutral. Identity filtering cannot grant presence.
PICKUP_NATIVE_WINDOWS = (
    (
        0x80051884,
        188,
        "69ecd0cf14b326dab9e565efe2baa10d580609d0b41cad3dca30d088e4973ee2",
    ),
    (
        0x80071EB4,
        1592,
        "eb73199d097d0974e0c718af36df8bc6c53d5eb8eb4b67ba392636ca18f7d91a",
    ),
    (
        0x80072500,
        1820,
        "f1a6e634938741ff0f9533a842f46b251cb35e1481393b4bf7d68ac611d225d4",
    ),
    EFFECT_CLEANUP_NATIVE,
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
        0x80055904,
        204,
        "9f08b1193edd13a0362fe5a46ee6324d5903cb8b2f09be702ac7b9d9fc93dd2e",
    ),
    (
        0x8005714C,
        1480,
        "178350b14ecebc82eace0a9a28ccfab8b2c6cac8a27a2fbf72680a5a07a57825",
    ),
    (
        0x8007730C,
        84,
        "b219f7c3e76ab969aee8ac5b7df4a249328aacf2625afda220fe05ec98342039",
    ),
)

# Both physical code pools are selected by the native loader. The complete
# owned archive hash in the existing binder fixes these inspected images too.
ACTOR_STATE_IMAGES = (
    (
        0,
        0x8010D000,
        0,
        53068,
        "bd2c05f70cbf1088404cf583ff970f5f0d5d8b7ee05d32d027cd1c3def88bbdb",
    ),
    (
        1,
        0x80100000,
        26,
        53068,
        "7115c0ad492f63c53ce1e3a0db99081c62b0a0ab3e7f7d51a71ffc99c5e2959c",
    ),
)
ACTOR_BYTE_MEMBERS = ((2, 4), (3, 5), (4, 6), (31, 0x14E))
PICKUP_PROFILE_SHA256 = (
    "d5937ab613d34cf6e25b1accc533ecf219a4ba0f041576e6ec5371567127f145"
)


@dataclass(frozen=True)
class _PickupRoleFacts:
    # program, member command, enemy slot, constructor, acquisition guard
    actor_writes: tuple[tuple[str, int, int, int, int], ...]
    native_windows: tuple[tuple[int, int, str], ...]
    actor_images: tuple[tuple[int, int, int, int, str], ...]


@dataclass(frozen=True)
class _PositivePickupRoles:
    bound: BoundStartupDeclarations
    source_data: bytes
    room_json: str
    profile_json: str
    facts: _PickupRoleFacts

    def __post_init__(self):
        assert type(self.bound) is BoundStartupDeclarations
        assert type(self.source_data) is bytes
        assert type(self.room_json) is str and type(self.profile_json) is str
        assert type(self.facts) is _PickupRoleFacts
        result = _derive_pickup_roles(
            self.source_data,
            json.loads(self.room_json),
            json.loads(self.profile_json),
            self.bound,
        )
        assert type(result) is _PickupRoleFacts
        assert typed_binding_digest(self.facts) == typed_binding_digest(result)


def _actor_byte_state_roles(
    data: bytes, room: dict, profile: dict, writes: ScenarioSourceWriteWitnesses
):
    """Recognize one atomic controller reset; arbitrary literal bytes reject.

    The existing structured-frame compiler supplies all control edges. This
    performs no second entry or positive-prefix traversal.
    """
    programs = room["programs"]
    all_rows = [(key, r) for key, p in programs.items() for r in p["commands"]]
    members = dict(ACTOR_BYTE_MEMBERS)
    requested = {
        (key, r["offset"])
        for key, r in all_rows
        if r["opcode"] == 0x34 and data[r["offset"] + 1] in members
    }
    if not requested:
        return ()
    # This role does not borrow task roots, inherited Work, dynamic member
    # values or callback timing from the broader normal-engine premise.
    if (
        room["stage"] not in (0, 1)
        or any(key != "17:1" for key, _ in requested)
        or any(r["kind"] == "call" for r in programs["16:0"]["commands"])
        or any(
            r["opcode"]
            in (
                3,
                4,
                5,
                0x17,
                0x24,
                0x25,
                0x26,
                0x27,
                0x35,
                0x3D,
                0x47,
                0x6C,
            )
            or r["kind"] in ("interaction", "reset")
            and r["interaction"] in (5, 6)
            for _, r in all_rows
        )
    ):
        return PickupRolesFailure.Actor
    constructors = {}
    # Only the leading unconditional startup sequence owns these actors.
    # Canonical frame work begins after native initialization completes.
    for r in programs["17:0"]["commands"]:
        if r["kind"] in ("end", "if", "call", "jump") or r["opcode"] in (
            0x0D,
            0x0F,
            0x11,
            0x13,
            0x19,
            0x1A,
        ):
            break
        if r["opcode"] == 0x44:
            packet = data[r["offset"] : r["next"]]
            slot = packet[2]
            if slot in constructors:
                return PickupRolesFailure.Actor
            constructors[slot] = (r["offset"], packet)
    accepted = []
    guards = set()
    covered_members, covered_work = set(), set()
    for key, program in programs.items():
        needed = {at for k, at in requested if k == key}
        if not needed:
            continue
        frames = structured_control(data, program, ControlFrames.Strict)
        if type(frames) is not StructuredControl:
            return PickupRolesFailure.Actor
        rows = program["commands"]
        edges = dict(frames.edges)
        for index, r in enumerate(rows):
            if r["kind"] != "if" or index + 12 >= len(rows):
                continue
            test, work = rows[index + 1 : index + 3]
            if not (
                test["kind"] == "flag_check"
                and (test["bank"], test["expected"]) == (6, 0)
                and work["opcode"] == 0x2E
            ):
                continue
            slot_packet = data[work["offset"] : work["next"]]
            if len(slot_packet) != 3 or slot_packet[1] != 3:
                continue
            slot = slot_packet[2]
            origin = constructors.get(slot)
            if origin is None:
                continue
            creator, packet = origin
            if not (
                slot < 32
                and packet[1] == 0
                and packet[3] == 0x10
                # Preset6 initializes state0101; preset0 initializes0001.
                # Both use the even controller table, then this atomic recipe
                # installs its own complete state and clears the old preset.
                and int.from_bytes(packet[4:6], "little") in (0, 6)
                and packet[9] == test["bit"] != 0xFF
                and sum(
                    row["opcode"] == 0x44 and data[row["offset"] + 2] == slot
                    for _, row in all_rows
                )
                == 1
            ):
                continue
            start = index + 3
            if rows[start]["opcode"] == 0:
                start += 1
            recipe = rows[start : start + 8]
            suffix = rows[start + 8]
            if not (
                [data[t["offset"] : t["next"]] for t in recipe[:5]]
                == [
                    bytes((0x34, m, v, 0))
                    for m, v in ((7, 0), (2, 1), (3, 13), (4, 0), (5, 0))
                ]
                and [t["opcode"] for t in recipe[5:]] == [0x32, 0x33, 0x34]
                and data[recipe[5]["offset"] + 1] == 0
                and data[recipe[6]["offset"] + 1] == 0
                and data[recipe[7]["offset"] : recipe[7]["next"]] == b"\x34\x1f\0\0"
                and suffix["opcode"] == 8
                and r["target"] == suffix["next"]
            ):
                continue
            # Every incoming edge must pass the acquisition guard and Work
            # selection. No Goto, IF failure, alternate entry or call can enter
            # the middle of this uninterrupted native scalar sequence.
            block = rows[index : start + 9]
            if any(
                program["entry"] == t["offset"]
                or any(
                    source != previous["offset"]
                    for source, targets in edges.items()
                    if t["offset"] in targets
                )
                for previous, t in zip(block, block[1:])
            ):
                continue
            if any(
                copy.target_offset < test["next"]
                and test["offset"] < copy.target_offset + copy.width
                for copy in writes.copies
            ):
                # The existing positive Copy role permits numeric flag-test
                # operands. This ownership guard must keep its exact enemy ID.
                continue
            guards.add((6, test["bit"]))
            covered_members.update(
                (key, t["offset"]) for t in recipe if t["opcode"] == 0x34
            )
            covered_work.add((key, work["offset"]))
            accepted.extend(
                (key, t["offset"], slot, creator, test["bit"])
                for t in recipe
                if t["opcode"] == 0x34 and data[t["offset"] + 1] in members
            )
    if {(key, at) for key, at, *_ in accepted} != requested:
        return PickupRolesFailure.Actor
    if any(
        row["opcode"] == 0x34
        and (key, row["offset"]) not in covered_members
        or row["opcode"] == 0x2E
        and (key, row["offset"]) not in covered_work
        or row["opcode"] in (0x2F, 0x30, 0x31)
        for key, row in all_rows
    ):
        return PickupRolesFailure.Actor
    banks = {
        r["bank"]: (int(r["address_ps1"], 0), r["width"]) for r in profile["flag_banks"]
    }
    _, aliases = flag_write_conflicts(banks, frozenset(guards))
    # Counter/member and kind6 writers are outside this bounded source role.
    # Rejecting them above avoids inferring a guard history or a counter value.
    for _, row in all_rows:
        if row["kind"] == "flag_write" and (row["bank"], row["bit"]) in aliases:
            return PickupRolesFailure.Actor
    return tuple(sorted(accepted))


def _derive_pickup_roles(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
):
    from games.re2.event_presence import (
        presence_counter_indices,
        presence_flag_write_proof,
    )

    # The prefix compiler imports these roles and owns the policy. Defer that
    # import until both modules are initialized to avoid a module cycle.
    from games.re2.positive_prefix import PositivePrefixPolicy, positive_prefix_policy

    if (
        type(bound) is not BoundStartupDeclarations
        or type(data) is not bytes
        or positive_prefix_policy(profile)
        is not PositivePrefixPolicy.TrustedNormalEngine
        or semantic_profile_digest(profile) != PICKUP_PROFILE_SHA256
        or typed_binding_digest((bound.entry_resources, bound.declarations))
        != NORMAL_ENGINE_BINDING_SHA256
        or type(bound.ordinary_ingress)
        is not type(bound.entry_resources.ordinary_ingress)
        or typed_binding_digest(bound.ordinary_ingress)
        != typed_binding_digest(bound.entry_resources.ordinary_ingress)
        or not bound.ordinary_ingress.covers(data, room)
        or room["id"] != f"{room['stage']:02x}-{room['room']:02x}"
    ):
        return PickupRolesFailure.Binding
    decoded = decode_room(
        data,
        room["source"],
        frozenset((r["bank"], r["bit"]) for r in profile["presence_condition_flags"]),
        presence_counter_indices(profile),
        presence_flag_write_proof(profile)[0],
    )
    if any(
        json.dumps(decoded[key], sort_keys=True)
        != json.dumps(room[key], sort_keys=True)
        for key in OWNED_SOURCE_FIELDS
    ):
        return PickupRolesFailure.Binding
    executable = bound.entry_resources.executable
    if any(
        hashlib.sha256(native_bytes(executable, a, w)).hexdigest() != digest
        for a, w, digest in PICKUP_NATIVE_WINDOWS
    ):
        return PickupRolesFailure.Binding
    if any(
        struct.unpack("<2I", native_bytes(executable, 0x8009ADF4 + index * 8, 8))
        != (sector, width)
        for index, _, sector, width, _ in ACTOR_STATE_IMAGES
    ):
        return PickupRolesFailure.Binding
    source_writes = scenario_source_write_witnesses(data, room, profile)
    if type(source_writes) is not ScenarioSourceWriteWitnesses:
        return PickupRolesFailure.Actor
    actor_writes = _actor_byte_state_roles(data, room, profile, source_writes)
    if isinstance(actor_writes, PickupRolesFailure):
        return actor_writes
    return _PickupRoleFacts(actor_writes, PICKUP_NATIVE_WINDOWS, ACTOR_STATE_IMAGES)


def positive_pickup_roles(
    data: bytes, room: dict, profile: dict, bound: BoundStartupDeclarations
):
    result = _derive_pickup_roles(data, room, profile, bound)
    if isinstance(result, PickupRolesFailure):
        return result
    return _PositivePickupRoles(
        bound,
        data,
        json.dumps(room, sort_keys=True, separators=(",", ":")),
        json.dumps(profile, sort_keys=True, separators=(",", ":")),
        result,
    )
