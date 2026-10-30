"""Bounded RE2 SCD decoding for room metadata. See RE2-SCD-001."""

from __future__ import annotations

import hashlib
import struct
from itertools import pairwise

from games.re2.event_presence import (
    FLAG_WRITE_OPERATIONS,
    initializer_fallthrough,
    source_presence,
)
from games.re2.initializer_control_proof import (
    InitializerControlProof,
    InitializerControlSupport,
    native_switch_labels,
)
from games.re2.script_control_limits import NATIVE_CALL_FRAME_COUNT
from games.re2.startup_effects import StartupEffectAuditSupport, StartupEffectReceipt


def bind_event_awards(
    rooms: list[dict],
    sources: dict[str, bytes],
    item_banks: dict[int, int],
    condition_flags: frozenset[tuple[int, int]],
) -> dict[str, list[dict]]:
    """Bind exclusive post-delivery acquisition writes. See RE2-COLLECT-004."""
    assert len({room["id"] for room in rooms}) == len(rooms)
    assert sources.keys() == {room["id"] for room in rooms}, "all sources are required"
    result = {}
    for room in rooms:
        awards = []
        for key, program in room["programs"].items():
            commands = {row["offset"]: row for row in program["commands"]}
            for command in commands.values():
                if command["kind"] != "award":
                    continue
                award = {
                    **command,
                    "collection": {"kind": "unresolved"},
                    "presence": {"kind": "unresolved"},
                }
                following = commands.get(command["next"])
                if (
                    following is not None
                    and following["kind"] == "flag_write"
                    and following["operation"] == 1
                    and following["bank"] == item_banks[room["stage"]]
                    and not any(
                        other["entry"] == following["offset"]
                        or any(
                            row.get("target") == following["offset"]
                            for row in other["commands"]
                        )
                        for other in room["programs"].values()
                    )
                ):
                    bank, bit = following["bank"], following["bit"]
                    # Scan raw sources too: unsupported script paths must not
                    # hide a second writer and manufacture exclusive ownership.
                    needle = bytes((0x22, bank, bit))
                    hits = [
                        (key, offset)
                        for key, data in sources.items()
                        for offset in range(len(data) - 2)
                        if data[offset : offset + 3] == needle
                    ]
                    aliased = any(
                        item_banks[other["stage"]] == bank
                        and (
                            any(item["global_id"] == bit for item in other["items"])
                            or any(
                                row["kind"] == "reset"
                                and row["interaction"] == 2
                                and struct.unpack("<3H", bytes(row["data"]))[2] == bit
                                for program in other["programs"].values()
                                for row in program["commands"]
                            )
                        )
                        for other in rooms
                    )
                    if hits == [(room["id"], following["offset"])] and not aliased:
                        award["collection"] = {"kind": "flag", "bank": bank, "bit": bit}
                        award["presence"] = source_presence(
                            sources[room["id"]],
                            room["programs"],
                            {(key, command["offset"])},
                            "scheduled",
                            condition_flags,
                            fixed_flags=frozenset(),
                        )
                awards.append(award)
        result[room["id"]] = awards
    return result


# The pinned PS1 Endif consumes its padding byte. The PC format's one-byte
# width would turn that byte into an unrelated NOP (RE2-SCD-001).
OPCODE_WIDTHS = (
    1,
    2,
    1,
    4,
    4,
    2,
    4,
    4,
    2,
    4,
    3,
    1,
    1,
    6,
    2,
    4,
    2,
    4,
    2,
    4,
    6,
    2,
    2,
    6,
    2,
    2,
    2,
    6,
    1,
    4,
    1,
    1,
    1,
    4,
    4,
    6,
    4,
    3,
    6,
    4,
    1,
    2,
    1,
    6,
    20,
    38,
    3,
    4,
    1,
    1,
    8,
    8,
    4,
    3,
    12,
    4,
    3,
    8,
    16,
    32,
    2,
    3,
    6,
    4,
    8,
    10,
    1,
    4,
    22,
    5,
    10,
    2,
    16,
    8,
    2,
    3,
    5,
    22,
    22,
    4,
    4,
    6,
    6,
    6,
    22,
    6,
    4,
    8,
    4,
    4,
    2,
    2,
    3,
    2,
    2,
    2,
    14,
    4,
    2,
    1,
    16,
    2,
    1,
    28,
    40,
    30,
    6,
    4,
    1,
    4,
    6,
    2,
    1,
    1,
    16,
    8,
    4,
    22,
    3,
    4,
    6,
    1,
    16,
    16,
    6,
    6,
    6,
    6,
    2,
    3,
    3,
    1,
    2,
    6,
    1,
    1,
    3,
    1,
    6,
    6,
    8,
    24,
    24,
)


def reset_item_variants(data: bytes, items: list[dict], programs: dict) -> list[dict]:
    """Bind reset-only types to their original ordinary descriptor creators."""
    result = {}
    for program in programs.values():
        for row in program["commands"]:
            if row["opcode"] != 0x46:
                continue
            packet = data[row["offset"] : row["next"]]
            if (
                len(packet) != 10
                or packet[0] != 0x46
                or row["kind"] != "reset"
                or row["slot"] != packet[1]
                or row["interaction"] != packet[2]
                or row["data"] != list(packet[4:])
            ):
                raise ValueError("RE2 reset command does not match its source")
            if packet[2] != 2 or packet[1] >= 32 or packet[3] & 0x80:
                continue
            item_type, amount, gid = struct.unpack_from("<3H", packet, 4)
            creators = [
                item
                for item in items
                if item["slot"] == packet[1]
                and item["global_id"] == gid
                and not item["four_point"]
                and data[item["offset"] : item["offset"] + 3]
                == bytes((0x4E, item["slot"], 2))
                and not data[item["offset"] + 3] & 0x80
            ]
            if not creators or item_type in {item["type"] for item in creators}:
                continue
            for item in creators:
                offset = item["offset"]
                if (
                    not 0 <= offset <= len(data) - 22
                    or data[offset] != 0x4E
                    or data[offset + 1] != item["slot"]
                    or struct.unpack_from("<3H", data, offset + 14)[::2]
                    != (item["type"], gid)
                ):
                    raise ValueError("RE2 reset creator does not match its source")
            # Aliased script tables can decode the same physical reset twice.
            result[row["offset"]] = {
                "offset": row["offset"],
                "creator_offsets": sorted(item["offset"] for item in creators),
                "slot": packet[1],
                "type": item_type,
                "amount": amount,
                "global_id": gid,
                "sat": packet[3],
            }
    return [result[offset] for offset in sorted(result)]


def decode_room(
    data: bytes,
    source: str,
    condition_flags: frozenset[tuple[int, int]],
    presence_counters: frozenset[int],
    presence_writes: frozenset[tuple[int, int]],
) -> dict:
    assert isinstance(presence_counters, frozenset) and all(
        type(index) is int and 0 <= index <= 255 for index in presence_counters
    ), "counter proof indices must be explicit unsigned bytes"
    assert isinstance(presence_writes, frozenset) and all(
        isinstance(pair, tuple)
        and len(pair) == 2
        and all(type(value) is int and 0 <= value <= 255 for value in pair)
        for pair in presence_writes
    ), "flag write proof pairs must be explicit unsigned bytes"
    if len(data) < 100 or data[1] == 0:
        raise ValueError("RE2 room needs a complete header and cameras")
    offsets = struct.unpack_from("<23I", data, 8)
    if any(value and not 100 <= value <= len(data) for value in offsets):
        raise ValueError("RE2 room section outside the source")
    camera = offsets[7]
    if camera + data[1] * 32 > len(data):
        raise ValueError("RE2 camera table outside the source")
    proofs = [
        {
            "offset": camera + index * 32 + 4,
            "width": 24,
            "sha256": hashlib.sha256(
                data[camera + index * 32 + 4 : camera + index * 32 + 28]
            ).hexdigest(),
        }
        for index in range(min(data[1], 3))
    ]
    # RE2-SOURCE-001: the sound bank's program records change after loading.
    # Hash only the complete EDT and the immutable 32-byte VAB header.
    sound_proofs = []
    for index, width in ((0, 192), (1, 32)):
        offset = offsets[index]
        if offset:
            if offset + width > len(data):
                raise ValueError("RE2 sound proof outside the source")
            sound_proofs.append(
                {
                    "section": index,
                    "width": width,
                    "sha256": hashlib.sha256(data[offset : offset + width]).hexdigest(),
                }
            )
    items, doors, programs = {}, {}, {}
    complete = True
    for section in (16, 17):
        begin = offsets[section]
        if not begin:
            raise ValueError("RE2 room lacks required script sections")
        end = min([value for value in offsets if value > begin] + [len(data)])
        first = struct.unpack_from("<H", data, begin)[0]
        if first < 2 or first % 2 or begin + first > end:
            raise ValueError("invalid RE2 procedure table")
        entries = struct.unpack_from(f"<{first // 2}H", data, begin)
        if list(entries) != sorted(set(entries)) or any(
            begin + value >= end for value in entries
        ):
            raise ValueError("invalid RE2 procedure offsets")
        for number, entry in enumerate(entries):
            start = begin + entry
            stop = begin + entries[number + 1] if number + 1 < len(entries) else end
            pending, commands = [start], {}
            switch_labels = set()
            while pending:
                position = pending.pop()
                if position in commands:
                    continue
                if not start <= position < stop:
                    raise ValueError("RE2 script branch outside its procedure")
                opcode = data[position]
                if (
                    opcode >= len(OPCODE_WIDTHS)
                    or position + OPCODE_WIDTHS[opcode] > stop
                ):
                    raise ValueError("unsupported or truncated RE2 script command")
                packet = data[position : position + OPCODE_WIDTHS[opcode]]
                following = position + len(packet)
                command = {
                    "offset": position,
                    "next": following,
                    "kind": "other",
                    "opcode": opcode,
                }
                if opcode in (1, 0x19):
                    command["kind"] = "end"
                elif opcode == 6:
                    command.update(
                        kind="if",
                        target=following + struct.unpack_from("<H", packet, 2)[0],
                    )
                    pending.append(command["target"])
                elif opcode in (7, 0x17):
                    jump = struct.unpack_from(
                        "<H" if opcode == 7 else "<h", packet, 2 if opcode == 7 else 4
                    )[0]
                    command.update(kind="jump", target=position + jump)
                    pending.append(command["target"])
                elif opcode == 0x18:
                    command.update(kind="call", procedure=packet[1])
                elif opcode == 0x21:
                    command.update(
                        kind="flag_check",
                        bank=packet[1],
                        bit=packet[2],
                        expected=packet[3],
                    )
                elif opcode == 0x22:
                    command.update(
                        kind="flag_write",
                        bank=packet[1],
                        bit=packet[2],
                        operation=packet[3],
                        presence_safe=(packet[1], packet[2]) in presence_writes
                        and packet[3] in FLAG_WRITE_OPERATIONS,
                    )
                elif opcode == 0x24:
                    command.update(
                        kind="counter_write",
                        counter=packet[1],
                        presence_safe=packet[1] in presence_counters,
                    )
                elif opcode in (0x4E, 0x69):
                    operand = 14 if opcode == 0x4E else 22
                    item_type, amount, global_id = struct.unpack_from(
                        "<3H", packet, operand
                    )
                    items[position] = {
                        "offset": position,
                        "slot": packet[1],
                        "type": item_type,
                        "amount": amount,
                        "global_id": global_id,
                        "four_point": opcode == 0x69,
                    }
                    command.update(kind="item", item=position)
                elif opcode in (0x3B, 0x68):
                    operand = 22 if opcode == 0x3B else 30
                    doors[position] = {
                        "offset": position,
                        "slot": packet[1],
                        "activation_floor": packet[4],
                        "stage": packet[operand],
                        "room": packet[operand + 1],
                        "floor": packet[operand + 3],
                        "lock_id": packet[operand + 7],
                        "lock_type": packet[operand + 8],
                        "four_point": opcode == 0x68,
                    }
                    doors[position]["center"] = (
                        [
                            sum(
                                struct.unpack_from("<h", packet, 6 + index * 4)[0]
                                for index in range(4)
                            )
                            / 4,
                            sum(
                                struct.unpack_from("<h", packet, 8 + index * 4)[0]
                                for index in range(4)
                            )
                            / 4,
                        ]
                        if opcode == 0x68
                        else [
                            struct.unpack_from("<h", packet, 6)[0]
                            + struct.unpack_from("<H", packet, 10)[0] / 2,
                            struct.unpack_from("<h", packet, 8)[0]
                            + struct.unpack_from("<H", packet, 12)[0] / 2,
                        ]
                    )
                    command.update(kind="door", door=position)
                elif opcode in (0x2C, 0x67):
                    command.update(
                        kind="interaction", slot=packet[1], interaction=packet[2]
                    )
                elif opcode == 0x46:
                    command.update(
                        kind="reset",
                        slot=packet[1],
                        interaction=packet[2],
                        data=list(packet[4:]),
                    )
                elif opcode == 0x76:
                    command.update(kind="award", item_type=packet[1], amount=packet[2])
                elif opcode == 0x13:
                    # RE2-SCD-002: the native selector skips case bodies by
                    # their unsigned relative offsets. Queue every label so
                    # an early return cannot hide a later pickup or award.
                    limit, labels = native_switch_labels(data, position, stop)
                    switch_labels.update(labels)
                    pending.extend(labels)
                    pending.append(limit)
                commands[position] = command
                if command["kind"] not in ("end", "jump"):
                    pending.append(following)
            ordered = sorted(commands.values(), key=lambda row: row["offset"])
            if switch_labels and any(
                left["next"] > right["offset"] for left, right in pairwise(ordered)
            ):
                raise ValueError("overlapping RE2 script commands")
            if any(
                row["opcode"] in (0x14, 0x15, 0x16)
                and row["offset"] not in switch_labels
                for row in ordered
            ):
                # An orphan marker has no validated switch owner, so it
                # cannot establish a complete candidate list.
                complete = False
            programs[f"{section}:{number}"] = {
                "entry": start,
                # Negative proofs also scan unreachable bytes inside this procedure.
                "limit": stop,
                "commands": ordered,
            }

    resets = [
        command
        for program in programs.values()
        for command in program["commands"]
        if command["kind"] == "reset"
    ]
    for item in items.values():
        item["amounts"] = sorted(
            {item["amount"]}
            | {
                struct.unpack("<3H", bytes(command["data"]))[1]
                for command in resets
                if command["interaction"] == 2
                and command["slot"] == item["slot"]
                and struct.unpack("<3H", bytes(command["data"]))[::2]
                == (item["type"], item["global_id"])
            }
        )
    if any(
        command["interaction"] == 2
        and not any(
            item["slot"] == command["slot"]
            and (item["type"], item["global_id"])
            == struct.unpack("<3H", bytes(command["data"]))[::2]
            for item in items.values()
        )
        for command in resets
    ):
        # A reset can introduce an item absent from the creator catalog.
        # Withhold full-list knowledge until that identity is reconstructed.
        complete = False

    room = {
        "source": source,
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "cameras": data[1],
        "section_offsets": list(offsets),
        "proofs": proofs,
        "sound_proofs": sound_proofs,
        "items": list(items.values()),
        "reset_item_variants": reset_item_variants(
            data, list(items.values()), programs
        ),
        "doors": list(doors.values()),
        "programs": programs,
        "candidate_list_complete": complete,
    }
    required, conditional = collection_presence(
        data, room, condition_flags, frozenset(items), fixed_flags=frozenset()
    )
    return {
        **room,
        "collection_item_ids": required,
        "conditional_item_presence": conditional,
    }


def collection_presence(
    data: bytes,
    room: dict,
    condition_flags: frozenset[tuple[int, int]],
    offsets: frozenset[int],
    fixed_flags: frozenset[tuple[int, int, int]],
    *,
    unreachable_creator_offsets: frozenset[int] = frozenset(),
    startup_effects: StartupEffectReceipt
    | StartupEffectAuditSupport = StartupEffectAuditSupport.Unaudited,
    initializer_control: InitializerControlProof
    | InitializerControlSupport = InitializerControlSupport.Unaudited,
) -> tuple[list[int], list[dict]]:
    """Prove collection presence for an explicit set of source candidates."""
    assert isinstance(fixed_flags, frozenset), "fixed startup flags must be explicit"
    assert not fixed_flags or room.get("fixed_context_preserved") is True, (
        "fixed startup flags require the whole-source context proof"
    )
    items = {item["offset"]: item for item in room["items"]}
    eligible = {offset: item for offset, item in items.items() if offset in offsets}
    programs = room["programs"]
    assert startup_effects is StartupEffectAuditSupport.Unaudited or isinstance(
        startup_effects, StartupEffectReceipt
    )
    setup_locations = (
        startup_effects.locations_for(data, programs, condition_flags, fixed_flags)
        if isinstance(startup_effects, StartupEffectReceipt)
        else frozenset()
    )
    assert initializer_control is InitializerControlSupport.Unaudited or isinstance(
        initializer_control, InitializerControlProof
    )
    if isinstance(initializer_control, InitializerControlProof):
        initializer_control = initializer_control.for_predicates(
            data, programs, condition_flags, fixed_flags
        )
    control_locations = (
        initializer_control.fallthrough_locations
        if isinstance(initializer_control, InitializerControlProof)
        else frozenset()
    )
    control_edges = (
        {(key, start): end for key, start, end in initializer_control.switch_edges}
        if isinstance(initializer_control, InitializerControlProof)
        else {}
    )
    assert isinstance(unreachable_creator_offsets, frozenset)
    assert not unreachable_creator_offsets or fixed_flags, (
        "creator lifetime exclusions require the preserved fixed context"
    )
    assert unreachable_creator_offsets <= {
        command["offset"]
        for program in programs.values()
        for command in program["commands"]
        if command["kind"] in ("item", "door", "interaction", "reset")
    }, "creator lifetime exclusions must belong to the decoded source"
    doors = {door["offset"]: door for door in room["doors"]}
    complete = room["candidate_list_complete"]
    assert offsets <= items.keys(), "presence candidates must belong to the source"
    resets = [
        command
        for program in programs.values()
        for command in program["commands"]
        if command["kind"] == "reset"
    ]
    # A later Copy can rewrite a callback binding or its entry command.
    # The script-restoration proof requires bytecode that stays unchanged.
    self_modifying = any(
        command["opcode"] == 0x1D
        for program in programs.values()
        for command in program["commands"]
    )
    ambiguous_slots = {
        slot
        for slot in {item["slot"] for item in eligible.values()}
        if len(
            {
                (item["global_id"], item["type"])
                for item in eligible.values()
                if item["slot"] == slot
                # RE2-COLLECT-023: the whole-source proof already excluded this creator.
                and item["offset"] not in unreachable_creator_offsets
            }
        )
        > 1
    }
    # An event can reuse the registry slot after startup. Only the shared
    # whole-source context walk can exclude a generic creator; an uncalled
    # procedure or a fresh mutable predicate cannot prove its unreachability.
    # Doors and resets retain their existing conservative lifetime checks.
    ambiguous_slots.update(
        doors[command["door"]]["slot"] if command["kind"] == "door" else command["slot"]
        for program in programs.values()
        for command in program["commands"]
        if command["kind"] in ("door", "interaction")
        and not (
            command["kind"] == "interaction"
            and command["offset"] in unreachable_creator_offsets
        )
    )
    for command in resets:
        identities = {
            (item["type"], item["global_id"])
            for item in eligible.values()
            if item["slot"] == command["slot"]
        }
        if not identities:
            continue
        payload = bytes(command["data"])
        if command["interaction"] == 0 and not any(payload):
            continue
        if (
            command["interaction"] == 5
            and not self_modifying
            and payload[:3] == b"\xff\0\x18"
            and payload[4:] == b"\0\0"
        ):
            callback = programs.get(f"17:{payload[3]}")
            if callback is not None:
                entry = next(
                    row
                    for row in callback["commands"]
                    if row["offset"] == callback["entry"]
                )
                # RE2-COLLECT-018: a canonical automatic script interaction
                # preserves the declared item only when it restores that exact
                # slot and identity before executing any other command.
                if (
                    entry["kind"] == "reset"
                    and entry["slot"] == command["slot"]
                    and entry["interaction"] == 2
                    and identities == {struct.unpack("<3H", bytes(entry["data"]))[::2]}
                ):
                    continue
        item_type, _amount, gid = struct.unpack("<3H", payload)
        # RE2-COLLECT-003: a later reset can change identity even when
        # its event is not part of startup. Quantity is not identity.
        if command["interaction"] != 2 or identities != {(item_type, gid)}:
            ambiguous_slots.add(command["slot"])

    def collection_items() -> list[int]:
        # RE2-COLLECT-001: prove presence independently of activation. A catalog
        # entry alone may belong to a conditional or never-started procedure.
        # Later unsafe counter writes can alias item flags or room identity.
        if not complete or any(
            row["kind"] == "counter_write" and not initializer_fallthrough(row)
            for program in programs.values()
            for row in program["commands"]
        ):
            return []
        commands = {
            key: {command["offset"]: command for command in program["commands"]}
            for key, program in programs.items()
        }
        outcomes = []
        steps = 0
        for root in ("16:0", "17:0"):
            pending = [
                (root, programs[root]["entry"], (), (), frozenset(), frozenset())
            ]
            finished = []
            while pending:
                key, position, returns, conditions, found, seen = pending.pop()
                state = (key, position, returns, conditions)
                steps += 1
                # Unsupported paths and nontermination cannot prove that a
                # later initializer runs. Discard the whole presence proof.
                if steps > 4096 or state in seen or position not in commands[key]:
                    return []
                seen = seen | {state}
                command = commands[key][position]
                opcode, kind = command["opcode"], command["kind"]
                if (key, position) in control_edges:
                    position = control_edges[key, position]
                elif kind == "end":
                    if returns:
                        key, position, conditions = returns[-1]
                        returns = returns[:-1]
                    elif opcode == 1:
                        finished.append(found)
                        continue
                    else:
                        return []
                elif kind == "call":
                    # Native Gosub uses the main procedure table even when the
                    # caller is the separately scheduled init task.
                    target = f"17:{command['procedure']}"
                    if (
                        target not in programs
                        or len(returns) >= NATIVE_CALL_FRAME_COUNT - 1
                    ):
                        return []
                    returns = returns + ((key, command["next"], conditions),)
                    key, position, conditions = target, programs[target]["entry"], ()
                elif kind == "if":
                    pending.append(
                        (key, command["target"], returns, conditions, found, seen)
                    )
                    position = command["next"]
                    conditions = conditions + (command["target"],)
                elif opcode == 7:
                    if not conditions:
                        return []
                    position, conditions = command["target"], conditions[:-1]
                elif opcode == 8:
                    if not conditions:
                        return []
                    position, conditions = command["next"], conditions[:-1]
                elif kind == "flag_check":
                    if not conditions:
                        return []
                    position = command["next"]
                elif kind == "item":
                    item = items[command["item"]]
                    if data[item["offset"] + 2] not in (0, 2):
                        return []
                    # RE2-COLLECT-002: conflicting slot identities need their
                    # own history proof; they cannot erase unrelated items.
                    if (
                        item["offset"] in eligible
                        and item["slot"] not in ambiguous_slots
                    ):
                        found = found | {(item["global_id"], item["type"])}
                    position = command["next"]
                elif kind == "reset":
                    # Reset writes only its registered slot. The room-wide
                    # check above excludes identities that it can replace.
                    position = command["next"]
                elif opcode == 4:
                    # Automatic tasks run after the two startup tasks. Do not
                    # count their conditional declarations as startup proof.
                    packet = data[position : command["next"]]
                    if packet[1] < 10 or f"17:{packet[3]}" not in programs:
                        return []
                    position = command["next"]
                elif kind in ("door", "interaction"):
                    # These creators' slots were excluded above, including
                    # creators reached only by an asynchronous event.
                    position = command["next"]
                elif (
                    initializer_fallthrough(command)
                    or (key, command["offset"]) in setup_locations
                    or (key, command["offset"]) in control_locations
                ):
                    # Audited fall-through commands: padding, flag writes,
                    # scalar/actor setup and camera replacement do not declare
                    # collectibles or yield the executing startup task.
                    position = command["next"]
                else:
                    return []
                pending.append((key, position, returns, conditions, found, seen))
            if not finished:
                return []
            outcomes.append(set.intersection(*(set(result) for result in finished)))
        required = outcomes[0] | outcomes[1]
        return sorted(
            gid
            for gid, item_type in required
            if {item["type"] for item in eligible.values() if item["global_id"] == gid}
            == {item_type}
        )

    required = collection_items()
    conditional = []
    for gid in sorted(
        {item["global_id"] for item in eligible.values()} - set(required)
    ):
        variants = [item for item in eligible.values() if item["global_id"] == gid]
        if (
            not complete
            or len({item["type"] for item in variants}) != 1
            or any(
                item["slot"] in ambiguous_slots
                or data[item["offset"] + 2] not in (0, 2)
                for item in variants
            )
        ):
            continue
        # Reuse the award proof's guarded startup paths. Identity/lifetime
        # exclusions still apply even if one creator can be reached reliably.
        presence = source_presence(
            data,
            programs,
            {
                (key, command["offset"])
                for key, program in programs.items()
                for command in program["commands"]
                if command["kind"] == "item"
                and command["item"] in eligible
                and items[command["item"]]["global_id"] == gid
            },
            "startup",
            condition_flags,
            fixed_flags,
            startup_effects=startup_effects,
            initializer_control=initializer_control,
        )
        if presence["kind"] != "unresolved":
            conditional.append({"global_id": gid, "presence": presence})

    return required, conditional
