"""Source entries and scenario guards under separate native execution contracts.

Normal-engine trust applies only to scenario filtering. Both policies retain
source-directed control and write checks; neither claims arbitrary-pointer or
DMA safety.
"""

from __future__ import annotations

import hashlib
import struct
from enum import Enum

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.initializer_control_proof import native_switch_labels
from games.re2.room_data import decode_room
from games.re2.scenario_selection import (
    SCENARIO_ENTRY_AUDIT,
    SCENARIO_EXECUTABLE_SHA256,
    SCENARIO_GUARD_AUDIT,
    SCENARIO_NATIVE_WORK_AUDIT,
    SCENARIO_TRUSTED_NATIVE_AUDIT,
    ScenarioSelectionFailure,
    ScenarioSourceWriteWitnesses,
    VerifiedScenarioContext,
    VerifiedScenarioEntryScope,
    VerifiedScenarioGuardScope,
    bind_scenario_context,
    scenario_source_write_witnesses,
)
from games.re2.script_control_limits import (
    NATIVE_LOOP_FRAME_COUNT,
    calls_fit_native_frames,
    programs_digest,
)


class _UnprovedEntry(Exception):
    pass


class _ScopePolicy(Enum):
    AuditedNativeWork = "audited native work"
    TrustedNormalEngine = "trusted normal engine"


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


def scenario_entry_scope(
    data: bytes, room: dict, profile: dict, context: VerifiedScenarioContext
) -> VerifiedScenarioEntryScope | ScenarioSelectionFailure:
    """Qualify entries under the audited initialized-native-work recipe."""
    result = _scenario_scope(
        data, room, profile, context, _ScopePolicy.AuditedNativeWork
    )
    assert isinstance(result, (VerifiedScenarioEntryScope, ScenarioSelectionFailure))
    return result


def scenario_guard_scope(
    data: bytes, room: dict, profile: dict, context: VerifiedScenarioContext
) -> VerifiedScenarioGuardScope | ScenarioSelectionFailure:
    """Qualify scenario guards while trusting normal native engine execution."""
    result = _scenario_scope(
        data, room, profile, context, _ScopePolicy.TrustedNormalEngine
    )
    assert isinstance(result, (VerifiedScenarioGuardScope, ScenarioSelectionFailure))
    return result


def _scenario_scope(
    data: bytes,
    room: dict,
    profile: dict,
    context: VerifiedScenarioContext,
    policy: _ScopePolicy,
) -> VerifiedScenarioEntryScope | VerifiedScenarioGuardScope | ScenarioSelectionFailure:
    """Close ordinary source entries without assuming opaque tasks terminate.

    Source/record writers are checked against all protected packets by the
    selection compiler, which must consume this exact source-bound receipt.
    """
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert isinstance(context, VerifiedScenarioContext)
    assert isinstance(policy, _ScopePolicy)

    def require(condition: bool) -> None:
        if not condition:
            raise _UnprovedEntry

    try:
        require(bind_scenario_context(profile, context.declaration_contract) == context)
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
        require(
            all(
                decoded[field] == room[field]
                for field in (
                    "sha256",
                    "size",
                    "cameras",
                    "section_offsets",
                    "items",
                    "doors",
                    "reset_item_variants",
                    "candidate_list_complete",
                    "programs",
                )
            )
        )
        programs = room["programs"]
        require(all(key in programs for key in ("16:0", "17:0", "17:1")))
        commands = {
            key: {row["offset"]: row for row in program["commands"]}
            for key, program in programs.items()
        }
        calls = {key: set() for key in programs}
        replacement_sources = set()
        sealed_goto_programs = set()
        render_initializers = {}
        slot_kinds: dict[int, set[int]] = {}
        bindings = []
        rows = [(key, row) for key, p in programs.items() for row in p["commands"]]
        has_render_updates = any(row["opcode"] == 0x74 for _, row in rows)
        writes = scenario_source_write_witnesses(data, room, profile)
        require(isinstance(writes, ScenarioSourceWriteWitnesses))
        # The shared footprint receipt keeps model/SCA/camera/floor writes out
        # of scripts and their source dependencies. Copy has a narrower right:
        # only these numeric values can change without invalidating an inspected
        # selector, entry, task frame or resource-write destination.
        scalar_immediates = [
            (row["offset"] + (4 if row["opcode"] == 0x23 else 2), row["next"])
            for _, row in rows
            if row["opcode"] in (0x23, 0x32, 0x6D)
        ]
        require(
            all(
                any(
                    begin <= copy.target_offset
                    and copy.target_offset + copy.width <= end
                    for begin, end in scalar_immediates
                )
                for copy in writes.copies
            )
        )
        for key, row in rows:
            packet = data[row["offset"] : row["next"]]
            opcode = row["opcode"]
            require(
                opcode in _ENTRY_PRESERVING_NATIVE_EFFECTS
                or policy is _ScopePolicy.TrustedNormalEngine
                and opcode in (0x64, 0x65)
            )
            if row["kind"] == "call":
                target = f"17:{packet[1]}"
                require(target in programs)
                calls[key].add(target)
            elif opcode == 3:
                # This replacement recipe covers main-procedure entries.
                # Auxiliary table borrowing does not grant initializer rights.
                require(key.startswith("17:"))
                require(packet[1:3] == b"\0\x18")
                require(f"17:{packet[3]}" in programs)
                replacement_sources.add(key)
            elif opcode == 4:
                # Automatic native allocation cannot replace startup task zero.
                # Its PC advance precedes replacement, unlike Aot_on below.
                require(packet[1:3] == b"\xff\x18")
                target = f"17:{packet[3]}"
                require(target in programs)
            elif opcode == 0x2D:
                # Attachment registration appends to an unbounded native
                # queue that can reach task storage. This work contract covers
                # only model setup without that additional queue ownership.
                require(packet[3] & 0xC0 == 0)
            elif opcode == 0x17:
                # FF depths poison +140 without dereferencing it. A sealed
                # cycle cannot read that IF pointer or return to its caller;
                # native predicate failure merely suspends this worker at FF.
                require(
                    policy is _ScopePolicy.TrustedNormalEngine
                    and key.startswith("17:")
                    and packet[1:4] == b"\xff\xff\0"
                    and row["target"] == programs[key]["entry"]
                    and all(
                        command["opcode"] not in (1, 3, 6, 7, 8, 0x18)
                        for command in programs[key]["commands"]
                    )
                )
                sealed_goto_programs.add(key)
            elif opcode in (5, 0x19, 0x1B, 0x1C, 0x6C, 0x6E):
                # These task/source effects retain their independent entry
                # obligations even when their targets decode locally.
                raise _UnprovedEntry
            elif opcode == 0x64:
                # Scenario filtering trusts the normal renderer, but a source
                # selected Work pointer still needs its own bounded role.
                require(packet[4:6] == b"\0\0")
            elif opcode == 0x53 and has_render_updates:
                # Another procedure may initialize a record while this recipe
                # sleeps. Every such initializer must retain the same four
                # owned records, valid blend mode and RGB-mask domain.
                require(packet[1] < 4 and packet[2] < 4 and packet[3] <= 7)
            elif opcode == 0x74:
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
            elif opcode == 0x2E:
                category, index = packet[1:3]
                require(category in (1, 2, 3, 4))
                require(category != 3 or index < 32)
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
                require(packet[1] in (15, 16, 23, 29))
            elif opcode == 0x44:
                # The audited model's presets select states0/17/18. Their
                # owned code and numeric actor fields have no room-PC entry;
                # other presets cannot inherit this initialized-work role.
                require(
                    packet[1] == 0
                    and packet[2] < 32
                    and packet[3] == 0x22
                    and int.from_bytes(packet[4:6], "little")
                    in (0x0010, 0x4011, 0x4402)
                )
            elif opcode in (0x35, 0x3D):
                # Member_set reads counter byte2 into member byte1; Member_copy
                # writes counter byte1 from member byte2. The latter sign-extends
                # its counter, so both stay inside the audited positive domain.
                selector = packet[1] if opcode == 0x35 else packet[2]
                counter = packet[2] if opcode == 0x35 else packet[1]
                require(selector in (11, 12, 13, 14, 15, 16, 23))
                require(counter in counters and counter < 128)
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
        for _, row in rows:
            if row["opcode"] == 0x47:
                kinds = slot_kinds.get(data[row["offset"] + 1], set())
                # A kind-five dispatch can replace its own final worker and
                # then add two to the new PC. Ordinary entries are insufficient.
                require(bool(kinds) and 5 not in kinds)
        require(calls_fit_native_frames(calls))
        # EventNext resets the root IF/loop cells but preserves call depth.
        # Reject the first replacement in every positive-depth chain rather
        # than assuming a replacement target repairs a caller's stale frame.
        # Every procedure's edges are present, so this union already includes
        # callees of callees without a second traversal of the same graph.
        callees = {target for targets in calls.values() for target in targets}
        require(not replacement_sources & callees)

        def predicate_end(key, start, width):
            end, cursor = start + width, start
            require(width > 0)
            while cursor < end:
                require(cursor in commands[key])
                condition = commands[key][cursor]
                packet = data[cursor : condition["next"]]
                require(
                    condition["kind"] == "flag_check"
                    or condition["opcode"] == 0x23
                    and packet[1] == 0
                    and packet[3] < 7
                )
                cursor = condition["next"]
            require(cursor == end)
            return end

        # Each procedure starts with a native call frame. Unknown predicates
        # retain both continuations; loops can repeat without proving progress.
        for key, program in programs.items():
            pending = [(program["entry"], (), ())]
            seen = set()
            edges = {}
            while pending:
                position, conditions, loops = pending.pop()
                state = position, conditions, loops
                if state in seen:
                    continue
                require(len(seen) < 16384 and position in commands[key])
                seen.add(state)
                edge_start = len(pending)
                row = commands[key][position]
                opcode, following = row["opcode"], row["next"]
                packet = data[position:following]
                if row["kind"] == "end":
                    require(packet == b"\x01\0")
                    continue
                if opcode == 3:
                    # The old procedure is abandoned, with no caller advance.
                    # Its canonical target is independently audited above as
                    # a fresh root, including its synchronous call capacity.
                    continue
                if opcode == 0x17:
                    require(
                        key in sealed_goto_programs and not conditions and not loops
                    )
                    pending.append((row["target"], (), ()))
                elif row["kind"] == "if":
                    require(len(conditions) < 8 and row["target"] > following)
                    pending.append((row["target"], conditions, loops))
                    pending.append((following, conditions + (row["target"],), loops))
                elif row["kind"] == "flag_check" or opcode in (0x23, 0x3E, 0x50, 0x5E):
                    pending.append((following, conditions, loops))
                    if conditions:
                        # A failed predicate pops the IF frame, not an enclosing
                        # loop. Testing inside a loop can therefore abandon its
                        # body with the native loop slot still occupied.
                        pending.append((conditions[-1], conditions[:-1], loops))
                elif opcode in (7, 8):
                    require(bool(conditions) and following == conditions[-1])
                    target = row["target"] if opcode == 7 else following
                    require(target >= following)
                    pending.append((target, conditions[:-1], loops))
                elif opcode == 9:
                    require(packet[1] == 0x0A and len(loops) < NATIVE_LOOP_FRAME_COUNT)
                    pending.append((following, conditions, loops))
                elif opcode in (0x0D, 0x0F, 0x11):
                    require(len(loops) < NATIVE_LOOP_FRAME_COUNT)
                    limit = following + struct.unpack_from("<h", packet, 2)[0]
                    require(following < limit and limit in commands[key])
                    body = following
                    if opcode == 0x0F:
                        body = predicate_end(key, following, packet[1])
                        require(body in commands[key] and body <= limit)
                    loop = opcode, position, body, limit, conditions
                    if opcode != 0x11:
                        pending.append((limit, conditions, loops))
                    pending.append((body, conditions, loops + (loop,)))
                elif opcode in (0x0E, 0x10, 0x12):
                    require(bool(loops))
                    kind, header, body, limit, saved_conditions = loops[-1]
                    require(
                        (kind, opcode) in ((0x0D, 0x0E), (0x0F, 0x10), (0x11, 0x12))
                        and conditions == saved_conditions
                    )
                    if opcode == 0x12:
                        after = predicate_end(key, following, packet[1])
                        require(after == limit)
                        pending.append((after, conditions, loops[:-1]))
                        pending.append((body, conditions, loops))
                    elif opcode == 0x10:
                        require(following == limit)
                        pending.append((header, conditions, loops[:-1]))
                    else:
                        require(following == limit)
                        pending.append((following, conditions, loops[:-1]))
                        pending.append((body, conditions, loops))
                elif opcode == 0x13:
                    require(len(loops) < NATIVE_LOOP_FRAME_COUNT)
                    end, labels = native_switch_labels(data, position, program["limit"])
                    require(end in commands[key])
                    require(all(at in commands[key] for at in labels))
                    require(
                        all(commands[key][at]["opcode"] == 0x14 for at in labels[:-1])
                    )
                    require(commands[key][labels[-1]]["opcode"] == 0x16)
                    loop = opcode, position, labels, end, conditions
                    # No-match and each case are possible. Retaining them all
                    # grants no case-based item exclusion or counter knowledge.
                    pending.append((labels[-1], conditions, loops + (loop,)))
                    for at in labels[:-1]:
                        pending.append(
                            (commands[key][at]["next"], conditions, loops + (loop,))
                        )
                elif opcode == 0x14:
                    require(bool(loops) and loops[-1][0] == 0x13)
                    require(position in loops[-1][2])
                    pending.append((following, conditions, loops))
                elif opcode in (0x16, 0x1A):
                    require(bool(loops) and loops[-1][0] == 0x13)
                    _, _, labels, end, saved_conditions = loops[-1]
                    require(conditions == saved_conditions)
                    require(opcode != 0x16 or position == labels[-1])
                    pending.append((end, conditions, loops[:-1]))
                elif opcode in (0x0A, 0x15):
                    # A standalone sleep tail or unsupported default cannot
                    # inherit another instruction's native control frame.
                    raise _UnprovedEntry
                else:
                    pending.append((following, conditions, loops))
                edges.setdefault(position, set()).update(
                    next_state[0] for next_state in pending[edge_start:]
                )

            for update, initializer in render_initializers.get(key, {}).items():
                # Lexical adjacency alone does not exclude a branch into the
                # recipe. Retain every admitted control edge and require 53
                # on every path, including loop repeats and failed predicates.
                reached, pending_positions = set(), [program["entry"]]
                while pending_positions:
                    position = pending_positions.pop()
                    if position in reached or position == initializer:
                        continue
                    reached.add(position)
                    pending_positions.extend(edges.get(position, ()))
                require(update not in reached)

        # Identity/exclusion uses immutable scenario bits, so a later canonical
        # entry does not need startup exclusivity. Both native and explicit
        # entries still had to establish bounded fresh procedure frames above.
        protected = set(programs)
        if policy is _ScopePolicy.TrustedNormalEngine:
            # This receipt authorizes scenario filtering only. Positive
            # declarations retain the independent audited native-work scope.
            return VerifiedScenarioGuardScope(
                SCENARIO_GUARD_AUDIT,
                SCENARIO_TRUSTED_NATIVE_AUDIT,
                SCENARIO_EXECUTABLE_SHA256,
                room["sha256"],
                programs_digest(programs),
                frozenset(protected),
                frozenset((key, programs[key]["entry"]) for key in protected),
            )
        return VerifiedScenarioEntryScope(
            SCENARIO_ENTRY_AUDIT,
            SCENARIO_NATIVE_WORK_AUDIT,
            SCENARIO_EXECUTABLE_SHA256,
            room["sha256"],
            programs_digest(programs),
            frozenset(protected),
            frozenset((key, programs[key]["entry"]) for key in protected),
        )
    except _UnprovedEntry:
        return ScenarioSelectionFailure.EntryScope
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return ScenarioSelectionFailure.SourceBinding
