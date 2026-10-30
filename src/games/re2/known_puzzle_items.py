"""Positive knowledge of declared puzzle pickups, separate from access proof.

A startup declaration and a player callback referring to it establish a known
target even while a puzzle guard blocks delivery. This does not prove that the
guard will change, that a future event finishes, or that other items are absent.
"""

from __future__ import annotations

import itertools
import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.event_presence import flag_write_conflicts
from games.re2.nonchoice_messages import (
    NonchoiceMessageFailure,
    nonchoice_message_proofs,
)
from games.re2.room_entry_contract import VerifiedRoomEntryContract
from games.re2.room_sound_bindings import RoomSoundBindings, room_sound_bindings
from games.re2.room_write_partitions import (
    EmbeddedModelResource,
    RoomWritePartitions,
    SourceRange,
    room_write_partitions,
    static_object_packet,
)
from games.re2.scenario_items import scenario_flags
from games.re2.script_control_limits import NATIVE_CALL_FRAME_COUNT
from games.re2.script_dispatch_items import ScriptItemDispatchConfig


class KnownPuzzleItemFailure(Enum):
    InputBinding = "invalid puzzle-target source inputs"
    NativeContract = "unsupported puzzle-target native contract"
    SourceMutation = "puzzle-target declaration or callback can change identity"
    Prefix = "puzzle-target startup prefix is not bounded"


@dataclass(frozen=True)
class KnownPuzzleItem:
    global_id: int
    item_type: int
    creator_offsets: tuple[int, ...]
    callback_offsets: tuple[int, ...]
    delivery_offsets: tuple[int, ...]
    context_conditions: list[dict]

    def __post_init__(self) -> None:
        assert type(self.global_id) is int and 0 <= self.global_id <= 255
        assert type(self.item_type) is int and 0 <= self.item_type <= 255
        for offsets in (
            self.creator_offsets,
            self.callback_offsets,
            self.delivery_offsets,
        ):
            assert type(offsets) is tuple and offsets
            assert all(type(offset) is int and offset >= 0 for offset in offsets)
            assert tuple(sorted(set(offsets))) == offsets
        assert type(self.context_conditions) is list


class _InvalidTarget(Exception):
    def __init__(self, reason: KnownPuzzleItemFailure):
        self.reason = reason


def known_puzzle_items(
    data: bytes,
    room: dict,
    profile: dict,
    entry_contract: VerifiedRoomEntryContract,
    dispatch: ScriptItemDispatchConfig,
) -> tuple[KnownPuzzleItem, ...] | KnownPuzzleItemFailure:
    """Compile target knowledge; consumers must reread acquisition and context.

    Only the two synchronous startup prefixes establish declarations. An opaque
    later effect stops that path's prefix, without erasing prior knowledge or
    granting permission to prune any creator, variant or future event.
    """
    assert type(data) is bytes and type(room) is dict and type(profile) is dict
    assert isinstance(entry_contract, VerifiedRoomEntryContract)
    assert isinstance(dispatch, ScriptItemDispatchConfig)

    def require(condition: bool, reason=KnownPuzzleItemFailure.InputBinding) -> None:
        if not condition:
            raise _InvalidTarget(reason)

    try:
        layout = profile["runtime_layout"]
        config = entry_contract.write_partitions
        identity = profile["executable_identity"]
        require(
            type(identity) is str
            and identity.rpartition(" SHA256 ")[2] == entry_contract.executable_sha256
            and type(room["stage"]) is int
            and room["stage"] in entry_contract.stages
            and config.aot_address == int(layout["aot_table_address_ps1"], 0)
            and config.aot_capacity == layout["aot_capacity"]
            and layout["transition_mask"] == 0x02000000
            and dispatch.main_table_address
            == int(profile["script_item_dispatch"]["main_table_address_ps1"], 0),
            KnownPuzzleItemFailure.NativeContract,
        )
        partitions = room_write_partitions(data, room, config)
        require(isinstance(partitions, RoomWritePartitions))
        # Native UI/camera work uses the upper graphics arena. An exact source
        # base is required; a lower bound cannot prove the retained bytes fit.
        require(
            partitions.retained_before(
                dict(entry_contract.source_addresses)[room["stage"]], 0x80198000
            ),
            KnownPuzzleItemFailure.NativeContract,
        )
        programs = room["programs"]
        commands = {
            key: {row["offset"]: row for row in program["commands"]}
            for key, program in programs.items()
        }
        banks = {
            row["bank"]: (int(row["address_ps1"], 0), row["width"])
            for row in profile["flag_banks"]
        }

        def physical_flag_key(bank: int, bit: int) -> tuple[int, int]:
            require(bank in banks and 0 <= bit <= 0xFFFF)
            # The native kind6 halfword operand wraps its word index to eight
            # words. Its write may exceed this reader's configured bank width.
            return banks[bank][0] + ((bit // 32) & 7) * 4, 0x80000000 >> (bit % 32)

        def flag_key(bank: int, bit: int) -> tuple[int, int]:
            require(bank in banks and 0 <= bit < banks[bank][1] * 8)
            return physical_flag_key(bank, bit)

        save_base = int(layout["save_block_address_ps1"], 0)
        save_limit = save_base + layout["save_block_width"]

        def saved_flag(target: tuple[int, int]) -> bool:
            return save_base <= target[0] <= save_limit - 4

        fixed_rows = scenario_flags(profile)
        all_fixed = {
            flag_key(row["bank"], row["bit"]): bool(row["expected"])
            for row in fixed_rows
        }
        require(bool(all_fixed))
        _, flag_aliases = flag_write_conflicts(
            banks, frozenset((row["bank"], row["bit"]) for row in fixed_rows)
        )
        all_rows = [row for program in programs.values() for row in program["commands"]]
        for row in all_rows:
            if row["kind"] == "flag_write":
                require(
                    physical_flag_key(row["bank"], row["bit"]) not in all_fixed,
                    KnownPuzzleItemFailure.SourceMutation,
                )
            if row["kind"] in ("interaction", "reset") and row["interaction"] == 6:
                payload = row["offset"] + (
                    4 if row["kind"] == "reset" else 22 if row["opcode"] == 0x67 else 14
                )
                bank, bit, _value = struct.unpack_from("<3H", data, payload)
                require(
                    physical_flag_key(bank, bit) not in all_fixed,
                    KnownPuzzleItemFailure.SourceMutation,
                )
        identities, callbacks, bindings = {}, {}, {}
        protected = [(0, 100)]
        for section in (16, 17):
            table = room["section_offsets"][section]
            protected.append((table, int.from_bytes(data[table : table + 2], "little")))
        # Copy may change later camera values, but cannot create a new writer,
        # redirect a call/branch, or rewrite a declared identity or callback.
        for row in all_rows:
            position, following = row["offset"], row["next"]
            packet = data[position:following]
            if row["kind"] == "call":
                require(packet == bytes((0x18, row["procedure"])))
            elif row["kind"] == "if":
                require(
                    row["target"] == following + int.from_bytes(packet[2:4], "little")
                )
            elif row["opcode"] == 7:
                require(
                    row["target"] == position + int.from_bytes(packet[2:4], "little")
                )
            elif row["kind"] in ("flag_check", "flag_write"):
                operand = (
                    row["expected"] if row["kind"] == "flag_check" else row["operation"]
                )
                require(
                    packet == bytes((row["opcode"], row["bank"], row["bit"], operand))
                )
            protected.append((position, 1))
            if row["opcode"] in (0x21, 0x22) and not any(
                bank == packet[1] for bank, _ in flag_aliases
            ):
                # A copied byte may select any native bit in this bank only
                # when all 256 physical aliases avoid the enforced mode.
                protected.extend(((position, 2), (position + 3, 1)))
            elif row["opcode"] in (1, 3, 4, 5, 6, 7, 8, 0x17, 0x18, 0x1D, 0x21, 0x22):
                protected.append((position, len(packet)))
            if row["kind"] in ("item", "door", "interaction", "reset"):
                protected.append((position, len(packet)))
                bindings.setdefault(packet[1], []).append(row)
            if row["kind"] == "item":
                require(row["opcode"] in (0x4E, 0x69))
                operand = 14 if row["opcode"] == 0x4E else 22
                item_type, amount, gid = struct.unpack_from("<3H", packet, operand)
                require(gid < config.item_flag_count)
                identities[position] = packet[1], item_type, gid, amount
            elif row["kind"] == "interaction" and packet[2:4] == b"\x05\x31":
                if (
                    row["opcode"] == 0x2C
                    and all(struct.unpack_from("<2H", packet, 10))
                    and packet[14:17] == b"\xff\0\x18"
                    and not any(packet[18:])
                ):
                    procedure = f"17:{packet[17]}"
                    require(procedure in programs)
                    callbacks[position] = packet[1], procedure
        catalog_items = {item["offset"]: item for item in room["items"]}
        require(catalog_items.keys() == identities.keys())
        for position, (slot, item_type, gid, amount) in identities.items():
            item = catalog_items[position]
            require(
                (item["slot"], item["type"], item["global_id"], item["amount"])
                == (slot, item_type, gid, amount)
            )
        require(
            not any(
                row["kind"] == "interaction" and row["interaction"] == 2
                for row in all_rows
            ),
            KnownPuzzleItemFailure.SourceMutation,
        )
        rvd = room["section_offsets"][8]
        rvd_end = min(
            (offset for offset in room["section_offsets"] if offset > rvd),
            default=len(data),
        )
        if rvd:
            protected.extend((position, 4) for position in range(rvd, rvd_end - 3, 20))
        for row in all_rows:
            if row["opcode"] != 0x1D:
                continue
            packet = data[row["offset"] : row["next"]]
            target, width = row["next"] + packet[2], 2 if packet[3] else 1
            require(
                target + width <= len(data)
                and not any(
                    target < start + size and start < target + width
                    for start, size in protected
                ),
                KnownPuzzleItemFailure.SourceMutation,
            )

        # Only one leading native mode-return guard may restrict entry settings.
        # All later scenario branches must agree on the same target/callback;
        # fresh mode flags cannot select a historical item alternative.
        fixed = {}
        for root in ("16:0", "17:0"):
            first = commands[root][programs[root]["entry"]]
            if first["kind"] != "if":
                continue
            test = commands[root].get(first["next"])
            terminal = commands[root].get(test["next"]) if test else None
            if (
                test
                and test["kind"] == "flag_check"
                and terminal
                and terminal["kind"] == "end"
            ):
                target = flag_key(test["bank"], test["bit"])
                if target in all_fixed:
                    fixed[target] = all_fixed[target]
                    # Flipping several independent settings together would
                    # omit historical entries where only one setting differed.
                    break
        required_settings = [
            row for row in fixed_rows if flag_key(row["bank"], row["bit"]) in fixed
        ]
        model_writes = {row.command_offset: row for row in partitions.objects}
        # Tokens describe identities rather than one branch's source offset.
        # Alternate declarations can therefore agree without selecting a variant.
        outcomes, steps, prefix_packets, expanded = [], 0, set(), set()
        predicate_packets = set()
        counter_address = int(layout["script_counter_address_ps1"], 0)

        def branch(key, row, frames, values, work, native_predicates):
            if row["opcode"] == 6:
                require(
                    len(frames) < 8 and row["target"] > row["next"],
                    KnownPuzzleItemFailure.Prefix,
                )
                following, matches = row["next"], []
                while following in commands[key]:
                    test = commands[key][following]
                    packet = data[following : test["next"]]
                    if test["kind"] == "flag_check":
                        require(test["expected"] in (0, 1))
                        flag = flag_key(test["bank"], test["bit"])
                        matches.append(
                            values[flag] == bool(test["expected"])
                            if flag in values
                            else "symbolic"
                        )
                    elif native_predicates and (
                        packet[0] == 0x23
                        and packet[1] == 0
                        and save_base
                        <= counter_address + 2 * packet[2]
                        <= save_limit - 2
                        and packet[3] == 0
                        or packet[0] == 0x50
                        and packet[1] in (0, 1)
                        or packet[:4] == b"\x3e\0\x0c\x04"
                        and work[0] == "object"
                    ):
                        # These exact native predicates only read bounded
                        # state. Both boolean outcomes preserve the mode proof.
                        matches.append("symbolic")
                    else:
                        break
                    predicate_packets.add((following, test["next"] - following))
                    following = test["next"]
                require(bool(matches), KnownPuzzleItemFailure.Prefix)
                result = []
                if False not in matches:
                    result.append((following, frames + (row["target"],)))
                if any(value is not True for value in matches):
                    result.append((row["target"], frames))
                return result
            require(
                bool(frames) and frames[-1] == row["next"],
                KnownPuzzleItemFailure.Prefix,
            )
            return [(row["target"] if row["opcode"] == 7 else row["next"], frames[:-1])]

        def bounded_camera(camera, flags):
            # Cut_chg searches without a sentinel bound. Require a real first
            # match and keep its STATUS writes disjoint from proof predicates.
            match = False
            for record in range(rvd, rvd_end - 19, 20) if rvd else ():
                if data[record : record + 2] == b"\xff\xff":
                    break
                if data[record + 2] == camera:
                    match = True
                    break
            return (
                camera < room["cameras"]
                and match
                and not any(
                    address == int(layout["status_flags_address_ps1"], 0)
                    and mask & 0x00100100
                    for address, mask in flags
                )
            )

        opposite_packets, opposite_text, opposite_resources = set(), set(), set()
        required_sounds = set()
        if fixed:
            # If entry skipped the declaration, this smaller source closure
            # must preserve that mode until departure. Normal future effects
            # need no lifetime theorem after a real target is already known.
            opposite = {target: not value for target, value in fixed.items()}
            pending = [
                (
                    root,
                    programs[root]["entry"],
                    (),
                    (),
                    ("unselected", 0),
                    frozenset(),
                    "root",
                    frozenset(),
                )
                for root in entry_contract.roots
            ]
            expanded_opposite = set()
            while pending:
                key, position, returns, frames, work, owners, origin, seen = (
                    pending.pop()
                )
                state = key, position, returns, frames, work, owners, origin
                require(
                    state not in seen and len(seen) < 256,
                    KnownPuzzleItemFailure.NativeContract,
                )
                if state in expanded_opposite:
                    continue
                expanded_opposite.add(state)
                require(
                    len(expanded_opposite) <= 4096 and position in commands[key],
                    KnownPuzzleItemFailure.NativeContract,
                )
                seen = seen | {state}
                row = commands[key][position]
                packet = data[position : row["next"]]
                opposite_packets.add((position, len(packet)))
                opcode = row["opcode"]
                if opcode in (6, 7, 8):
                    pending.extend(
                        (key, target, returns, next_frames, work, owners, origin, seen)
                        for target, next_frames in branch(
                            key, row, frames, opposite, work, True
                        )
                    )
                    continue
                if row["kind"] == "end":
                    require(
                        packet == b"\x01\0" and (not returns or not frames),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    if returns:
                        caller, target, caller_frames = returns[-1]
                        pending.append(
                            (
                                caller,
                                target,
                                returns[:-1],
                                caller_frames,
                                work,
                                owners,
                                origin,
                                seen,
                            )
                        )
                    continue
                if row["kind"] == "call":
                    callee = f"17:{row['procedure']}"
                    require(
                        callee in programs
                        and len(returns) < NATIVE_CALL_FRAME_COUNT - 1,
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    pending.append(
                        (
                            callee,
                            programs[callee]["entry"],
                            returns + ((key, row["next"], frames),),
                            (),
                            work,
                            owners,
                            origin,
                            seen,
                        )
                    )
                    continue
                if opcode in (0, 2):
                    # Yield preserves mode; every independently runnable task
                    # is checked in this same closure before it is accepted.
                    pass
                elif opcode == 4:
                    callee = f"17:{packet[3]}"
                    require(
                        packet[1:3] == b"\xff\x18"
                        and callee in programs
                        and origin == "root",
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    # Automatic slots 2..9 cannot replace startup/frame tasks
                    # 0/1. Workers start at depth zero with inherited Work
                    # unknown, and may not schedule another replacing worker.
                    pending.append(
                        (
                            callee,
                            programs[callee]["entry"],
                            (),
                            (),
                            ("unselected", 0),
                            frozenset(),
                            "worker",
                            frozenset(),
                        )
                    )
                elif row["kind"] == "flag_write":
                    require(
                        packet[3] in (0, 1, 7)
                        and physical_flag_key(packet[1], packet[2]) not in all_fixed,
                        KnownPuzzleItemFailure.NativeContract,
                    )
                elif opcode == 0x29:
                    require(
                        bounded_camera(packet[1] & 0x7F, fixed),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                elif opcode == 0x2A:
                    require(
                        any(
                            commands[prior[0]][prior[1]]["opcode"] == 0x29
                            for prior in seen
                        )
                        and all(
                            bounded_camera(camera, fixed)
                            for camera in range(room["cameras"])
                        ),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    # A validated Cut_chg on this path must first save a live
                    # camera. Every camera it could restore needs a bounded RVD.
                elif opcode == 0x2E:
                    require(
                        packet[1] == 4 and packet[2] < config.object_capacity,
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    work = "object", packet[2]
                elif opcode == 0x2F:
                    require(packet[1] < 12, KnownPuzzleItemFailure.NativeContract)
                elif opcode == 0x31:
                    # Delta update touches only the task's bounded halfwords.
                    pass
                elif opcode in (0x30, 0x34):
                    # Coordinate handlers never dereference a model pointer.
                    # Fixed Work suffices for mode safety before model setup.
                    require(
                        work[0] == "object" and (opcode == 0x30 or packet[1] == 12),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                elif opcode == 9:
                    require(
                        packet[1] == 0x0A
                        and int.from_bytes(packet[2:], "little")
                        and not frames,
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    # The finite 09/0A macro yields on every tick and restores
                    # its task-local loop index before the next source packet.
                elif opcode == 0x0F:
                    # Prove a mode-preserving zero-or-more-iteration block.
                    # Restrict the body so shared IF/loop storage cannot change
                    # across its native backedge. No termination is inferred.
                    condition = row["next"]
                    body = condition + packet[1]
                    end = row["next"] + int.from_bytes(
                        packet[2:], "little", signed=True
                    )
                    require(
                        origin == "worker"
                        and not returns
                        and not frames
                        and packet[1] == 6
                        and work[0] == "object"
                        and data[condition:body][:4] == b"\x3e\0\x0c\x04"
                        and condition in commands[key]
                        and commands[key][condition]["next"] == body
                        and end - 2 in commands[key]
                        and data[end - 2 : end] == b"\x10\0"
                        and commands[key][end - 2]["next"] == end
                        and end in commands[key],
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    opposite_packets.add((condition, 6))
                    cursor = body
                    while cursor < end - 2:
                        require(
                            cursor in commands[key],
                            KnownPuzzleItemFailure.NativeContract,
                        )
                        command = commands[key][cursor]
                        require(
                            command["opcode"] in (0, 2, 0x30, 0x31)
                            and command["next"] <= end - 2,
                            KnownPuzzleItemFailure.NativeContract,
                        )
                        opposite_packets.add((cursor, command["next"] - cursor))
                        cursor = command["next"]
                    require(cursor == end - 2, KnownPuzzleItemFailure.NativeContract)
                    opposite_packets.add((end - 2, 2))
                    pending.append(
                        (key, end, returns, frames, work, owners, origin, seen)
                    )
                    continue
                elif opcode == 0x36:
                    require(
                        packet[1] == 2
                        and packet[3] == 1
                        and packet[4] == 4
                        and packet[5] < config.object_capacity
                        and not any(packet[6:]),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    required_sounds.add(packet[2])
                elif (
                    opcode == 0x2C
                    and packet[2:4] == b"\x04\x31"
                    and packet[16:] == b"\0\0\xff\xff"
                    or opcode == 0x46
                    and packet[2:4] == b"\x04\x31"
                    and packet[6:] == b"\0\0\xff\xff"
                ):
                    if opcode == 0x46:
                        require(
                            any(slot == packet[1] for slot, _ in owners),
                            KnownPuzzleItemFailure.NativeContract,
                        )
                    else:
                        owners = frozenset(
                            (slot, at) for slot, at in owners if slot != packet[1]
                        ) | {(packet[1], position)}
                    require(
                        4 in entry_contract.non_scheduling_interaction_kinds,
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    require(
                        not any(
                            address == int(layout["status_flags_address_ps1"], 0)
                            and mask & 0x40
                            for address, mask in fixed
                        ),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    message_at = 4 if opcode == 0x46 else 14
                    message = int.from_bytes(
                        packet[message_at : message_at + 2], "little"
                    )
                    require(message <= 255, KnownPuzzleItemFailure.NativeContract)
                    proofs = nonchoice_message_proofs(
                        data, tuple(room["section_offsets"]), message
                    )
                    require(
                        not isinstance(proofs, NonchoiceMessageFailure),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    for proof in proofs:
                        require(
                            proof["offset"] + proof["width"] <= partitions.heap_floor,
                            KnownPuzzleItemFailure.NativeContract,
                        )
                        opposite_text.add((proof["offset"], proof["width"]))
                elif (
                    opcode == 0x3B
                    and packet[2:4] == b"\x01\x31"
                    and packet[29:31] == b"\0\0"
                ):
                    require(
                        packet[26] in entry_contract.door_models,
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    require(
                        not any(
                            address == int(layout["status_flags_address_ps1"], 0)
                            and mask & 0x00020000
                            for address, mask in fixed
                        ),
                        KnownPuzzleItemFailure.NativeContract,
                    )
                    # The unlocked callback preserves STATUS. Its loader ORs
                    # STATUS00020000, then sets SYSTEM02000000 before animation;
                    # polling excludes that transition until reinitialization.
                    owners = frozenset(
                        (slot, at) for slot, at in owners if slot != packet[1]
                    ) | {(packet[1], position)}
                else:
                    raise _InvalidTarget(KnownPuzzleItemFailure.NativeContract)
                pending.append(
                    (key, row["next"], returns, frames, work, owners, origin, seen)
                )

        if required_sounds:
            # This opposite-mode closure admits no compaction/rebinding opcode,
            # constructor or arbitrary native entry. Audited incoming auxiliary
            # scripts also have no compactor entry. Section22 need not be null.
            sounds = room_sound_bindings(
                data,
                tuple(room["section_offsets"]),
                partitions.heap_floor,
                frozenset(required_sounds),
            )
            require(
                isinstance(sounds, RoomSoundBindings),
                KnownPuzzleItemFailure.NativeContract,
            )
            other_resources = [
                *partitions.protected_source,
                *(SourceRange(offset, width) for offset, width in opposite_text),
                *(
                    model.model.asset
                    for model in partitions.objects
                    if isinstance(model.model, EmbeddedModelResource)
                ),
                *(
                    region
                    for write in partitions.source_writes
                    for region in write.writes
                ),
            ]
            require(
                not any(
                    sound.offset < other.offset + other.width
                    and other.offset < sound.offset + sound.width
                    for sound in sounds.resources
                    for other in other_resources
                ),
                KnownPuzzleItemFailure.NativeContract,
            )
            opposite_resources.update(
                (region.offset, region.width) for region in sounds.resources
            )

        def prefix(key, position, returns, frames, loaded, work, found, seen):
            nonlocal steps
            state = key, position, returns, frames
            require(
                len(seen) < 256 and state not in seen and position in commands[key],
                KnownPuzzleItemFailure.Prefix,
            )
            analysis_state = state, loaded, work, found
            if analysis_state in expanded:
                return
            # Reconverging scenario branches can have identical knowledge and
            # model ownership. Analyze that complete state once, without
            # merging different identities or dropping an allocation history.
            expanded.add(analysis_state)
            steps += 1
            require(steps <= 4096, KnownPuzzleItemFailure.Prefix)
            seen = seen | {state}
            row = commands[key][position]
            prefix_packets.add((position, row["next"] - position))
            packet = data[position : row["next"]]
            opcode = row["opcode"]
            if opcode in (6, 7, 8):
                for target, next_frames in branch(key, row, frames, fixed, work, False):
                    prefix(key, target, returns, next_frames, loaded, work, found, seen)
                return
            if row["kind"] == "end":
                require(
                    packet == b"\x01\0" and not frames, KnownPuzzleItemFailure.Prefix
                )
                if returns:
                    caller, target, caller_frames = returns[-1]
                    prefix(
                        caller,
                        target,
                        returns[:-1],
                        caller_frames,
                        loaded,
                        work,
                        found,
                        seen,
                    )
                elif key == "16:0":
                    prefix(
                        "17:0",
                        programs["17:0"]["entry"],
                        (),
                        (),
                        loaded,
                        ("unselected", 0),
                        found,
                        seen,
                    )
                else:
                    outcomes.append(found)
                return
            if row["kind"] == "call":
                callee = f"17:{row['procedure']}"
                require(
                    len(returns) < NATIVE_CALL_FRAME_COUNT - 1 and callee in programs,
                    KnownPuzzleItemFailure.Prefix,
                )
                prefix(
                    callee,
                    programs[callee]["entry"],
                    returns + ((key, row["next"], frames),),
                    (),
                    loaded,
                    work,
                    found,
                    seen,
                )
                return
            if opcode == 0:
                pass
            elif row["kind"] == "flag_write":
                target = flag_key(packet[1], packet[2])
                require(
                    packet[3] in (0, 1, 7)
                    and target not in all_fixed
                    and saved_flag(target),
                    KnownPuzzleItemFailure.Prefix,
                )
            elif row["kind"] in ("item", "door", "interaction"):
                if position in identities and opcode == 0x4E and packet[2] == 2:
                    slot, item_type, gid, amount = identities[position]
                    if amount and item_type < layout["file_type_min"]:
                        found = found | {("item", slot, item_type, gid)}
                if position in callbacks:
                    slot, procedure = callbacks[position]
                    found = found | {("callback", slot, procedure)}
            elif opcode == 0x2D:
                model = model_writes[position].model
                if not (
                    static_object_packet(packet)
                    and isinstance(model, EmbeddedModelResource)
                    and ("asset", model.asset.offset) not in loaded
                    and ("slot", packet[1]) not in loaded
                ):
                    outcomes.append(found)
                    return
                loaded = loaded | {("asset", model.asset.offset), ("slot", packet[1])}
            elif opcode == 0x2E and packet[1] == 4 and ("slot", packet[2]) in loaded:
                work = "object", packet[2]
            elif opcode == 0x32 and packet[1] == 0 and work[0] == "object":
                # Native Pos_set changes only coordinates in this already
                # initialized fixed object record, not source or flag words.
                pass
            else:
                outcomes.append(found)
                return
            prefix(key, row["next"], returns, frames, loaded, work, found, seen)

        prefix(
            "16:0",
            programs["16:0"]["entry"],
            (),
            (),
            frozenset(),
            ("unselected", 0),
            frozenset(),
            frozenset(),
        )
        require(bool(outcomes), KnownPuzzleItemFailure.Prefix)
        guaranteed = set.intersection(*(set(outcome) for outcome in outcomes))
        item_bank = (
            layout["item_bank_early"]
            if room["stage"] < layout["item_bank_stage_boundary"]
            else layout["item_bank_late"]
        )
        result = []
        for token in sorted(guaranteed):
            if token[0] != "item":
                continue
            _, slot, item_type, gid = token
            if any(
                other_gid == gid and other_type != item_type
                for _, other_type, other_gid, _ in identities.values()
            ):
                continue
            if any(
                row["kind"] == "reset"
                and data[row["offset"] + 2] == 2
                and struct.unpack_from("<3H", data, row["offset"] + 4)[2] == gid
                and struct.unpack_from("<3H", data, row["offset"] + 4)[0] != item_type
                for row in all_rows
            ):
                continue
            creators = [
                position
                for position, identity in identities.items()
                if identity[:3] == (slot, item_type, gid)
            ]
            if any(
                row["kind"] != "item"
                and not (
                    row["kind"] == "reset"
                    and not data[row["offset"] + 3] & 0x80
                    and (
                        data[row["offset"] + 2] == 0
                        and not any(data[row["offset"] + 4 : row["next"]])
                        or data[row["offset"] + 2] == 2
                        and struct.unpack_from("<3H", data, row["offset"] + 4)[::2]
                        == (item_type, gid)
                    )
                )
                or row["kind"] == "item"
                and identities[row["offset"]][:3] != (slot, item_type, gid)
                for row in bindings[slot]
            ):
                continue
            acquisition = flag_key(item_bank, gid)
            related_callbacks, deliveries = set(), set()
            for callback_offset, (callback_slot, procedure) in callbacks.items():
                if (
                    "callback",
                    callback_slot,
                    procedure,
                ) not in guaranteed or callback_slot == slot:
                    continue
                if any(
                    row["offset"] not in callbacks
                    or callbacks[row["offset"]][1] != procedure
                    for row in bindings[callback_slot]
                ):
                    continue
                if any(
                    row["bank"] not in banks
                    or not 0 <= row["bit"] < banks[row["bank"]][1] * 8
                    for row in programs[procedure]["commands"]
                    if row["kind"] == "flag_check"
                ):
                    continue
                read_flags = {
                    flag_key(row["bank"], row["bit"])
                    for row in programs[procedure]["commands"]
                    if row["kind"] == "flag_check"
                }
                if any(not saved_flag(target) for target in read_flags - fixed.keys()):
                    continue
                if len(read_flags - fixed.keys() - {acquisition}) > 8:
                    continue
                callback_deliveries = set()
                for combination in itertools.product(
                    (False, True), repeat=len(read_flags - fixed.keys() - {acquisition})
                ):
                    values = (
                        fixed
                        | dict(
                            zip(
                                sorted(read_flags - fixed.keys() - {acquisition}),
                                combination,
                                strict=True,
                            )
                        )
                        | {acquisition: False}
                    )
                    position, frames, seen = programs[procedure]["entry"], (), set()
                    for _ in range(256):
                        if position in seen or position not in commands[procedure]:
                            break
                        seen.add(position)
                        row = commands[procedure][position]
                        packet = data[position : row["next"]]
                        opcode = row["opcode"]
                        if opcode in (6, 7, 8):
                            edges = branch(
                                procedure, row, frames, values, ("unselected", 0), False
                            )
                            require(len(edges) == 1, KnownPuzzleItemFailure.Prefix)
                            position, frames = edges[0]
                            continue
                        if opcode == 0x47:
                            if packet[1] == slot:
                                callback_deliveries.add(position)
                            break
                        if opcode == 0:
                            pass
                        elif row["kind"] == "flag_write":
                            target = flag_key(packet[1], packet[2])
                            if (
                                target == acquisition
                                or target in all_fixed
                                or packet[3] not in (0, 1)
                                or not saved_flag(target)
                                and target != flag_key(2, 7)
                            ):
                                break
                            # STOP bit7 pauses player control. The audited
                            # scheduler/Sce_Event gate is bit6, so accepting
                            # arbitrary control-word writes here would be wrong.
                            values[target] = bool(packet[3])
                        elif (
                            opcode == 9
                            and packet[1] == 0x0A
                            and int.from_bytes(packet[2:], "little")
                        ):
                            # The complete 09/0A sleep macro uses a task-local
                            # counter and restores its frame before continuing.
                            pass
                        elif opcode == 0x29:
                            camera = packet[1] & 0x7F
                            if not bounded_camera(
                                camera, read_flags | fixed.keys() | {acquisition}
                            ):
                                break
                        else:
                            # Other branches may display a message or await a
                            # future event. No delivery/progress claim uses them.
                            break
                        position = row["next"]
                if callback_deliveries:
                    related_callbacks.add(callback_offset)
                    deliveries.update(callback_deliveries)
            if deliveries:
                protected_paths = [
                    *prefix_packets,
                    *predicate_packets,
                    *opposite_packets,
                    *opposite_text,
                    *opposite_resources,
                    *(
                        (row["offset"], row["next"] - row["offset"])
                        for callback_offset in related_callbacks
                        for row in programs[callbacks[callback_offset][1]]["commands"]
                    ),
                ]
                # Every operand relied on by the prefix or callback matters.
                # A later numeric Copy must not redirect Aot_on, Cut_chg,
                # object setup or the task-local sleep macro after generation.
                for row in all_rows:
                    if row["opcode"] != 0x1D:
                        continue
                    packet = data[row["offset"] : row["next"]]
                    target, width = row["next"] + packet[2], 2 if packet[3] else 1
                    require(
                        not any(
                            target < start + size and start < target + width
                            for start, size in protected_paths
                        ),
                        KnownPuzzleItemFailure.SourceMutation,
                    )
                result.append(
                    KnownPuzzleItem(
                        gid,
                        item_type,
                        tuple(sorted(creators)),
                        tuple(sorted(related_callbacks)),
                        tuple(sorted(deliveries)),
                        [
                            {
                                "kind": "conditions",
                                "any_of": [[dict(row) for row in required_settings]],
                            }
                        ]
                        if required_settings
                        else [],
                    )
                )
        return tuple(result)
    except _InvalidTarget as error:
        return error.reason
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return KnownPuzzleItemFailure.InputBinding
