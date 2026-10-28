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

from games.re2.initializer_control_proof import NATIVE_CALL_FRAME_COUNT
from games.re2.nonchoice_messages import (
    NonchoiceMessageFailure,
    nonchoice_message_proofs,
)
from games.re2.room_entry_contract import VerifiedRoomEntryContract
from games.re2.room_write_partitions import (
    EmbeddedModelResource,
    RoomWritePartitions,
    room_write_partitions,
    static_object_packet,
)
from games.re2.scenario_items import scenario_flags
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
            partitions.retained_before(entry_contract.source_address, 0x80198000),
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
            if row["opcode"] in (1, 3, 4, 5, 6, 7, 8, 0x17, 0x18, 0x1D, 0x21, 0x22):
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

        # Only a leading native mode-return guard may restrict entry settings.
        # All later scenario branches must agree on the same target/callback;
        # fresh mode flags cannot select a historical item alternative.
        fixed = {}
        first = commands["16:0"][programs["16:0"]["entry"]]
        if first["kind"] == "if":
            test = commands["16:0"].get(first["next"])
            terminal = commands["16:0"].get(test["next"]) if test else None
            if (
                test
                and test["kind"] == "flag_check"
                and terminal
                and terminal["kind"] == "end"
            ):
                target = flag_key(test["bank"], test["bit"])
                if target in all_fixed:
                    fixed[target] = all_fixed[target]
        required_settings = [
            row for row in fixed_rows if flag_key(row["bank"], row["bit"]) in fixed
        ]
        model_writes = {row.command_offset: row for row in partitions.objects}
        # Tokens describe identities rather than one branch's source offset.
        # Alternate declarations can therefore agree without selecting a variant.
        outcomes, steps, prefix_packets, expanded = [], 0, set(), set()

        def branch(key, row, frames, values):
            if row["opcode"] == 6:
                require(
                    len(frames) < 8 and row["target"] > row["next"],
                    KnownPuzzleItemFailure.Prefix,
                )
                following, predicates = row["next"], []
                while (
                    following in commands[key]
                    and commands[key][following]["kind"] == "flag_check"
                ):
                    test = commands[key][following]
                    require(test["expected"] in (0, 1))
                    predicates.append(
                        (flag_key(test["bank"], test["bit"]), bool(test["expected"]))
                    )
                    following = test["next"]
                require(bool(predicates), KnownPuzzleItemFailure.Prefix)
                matches = [
                    values.get(flag, "symbolic") == expected
                    if flag in values
                    else "symbolic"
                    for flag, expected in predicates
                ]
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

        opposite_packets, opposite_text = set(), set()
        if fixed:
            # If entry skipped the declaration, this smaller source closure
            # must preserve that mode until departure. Normal future effects
            # need no lifetime theorem after a real target is already known.
            opposite = {target: not value for target, value in fixed.items()}
            pending = [
                (root, programs[root]["entry"], (), (), frozenset())
                for root in entry_contract.roots
            ]
            expanded_opposite = set()
            while pending:
                key, position, returns, frames, seen = pending.pop()
                state = key, position, returns, frames
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
                        (key, target, returns, next_frames, seen)
                        for target, next_frames in branch(key, row, frames, opposite)
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
                            (caller, target, returns[:-1], caller_frames, seen)
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
                            seen,
                        )
                    )
                    continue
                if opcode == 0:
                    pass
                elif (
                    opcode == 0x2C
                    and packet[2:4] == b"\x04\x31"
                    and packet[16:] == b"\0\0\xff\xff"
                ):
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
                    message = int.from_bytes(packet[14:16], "little")
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
                else:
                    raise _InvalidTarget(KnownPuzzleItemFailure.NativeContract)
                pending.append((key, row["next"], returns, frames, seen))

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
                for target, next_frames in branch(key, row, frames, fixed):
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
                            edges = branch(procedure, row, frames, values)
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
                            # Cut_chg's search has no sentinel check. A valid
                            # camera number alone cannot bound that native read.
                            match = False
                            for record in range(rvd, rvd_end - 19, 20) if rvd else ():
                                if data[record : record + 2] == b"\xff\xff":
                                    break
                                if data[record + 2] == camera:
                                    match = True
                                    break
                            status_address = int(layout["status_flags_address_ps1"], 0)
                            if (
                                camera >= room["cameras"]
                                or not match
                                or any(
                                    address == status_address and mask & 0x00100100
                                    for address, mask in read_flags
                                    | fixed.keys()
                                    | {acquisition}
                                )
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
                    *opposite_packets,
                    *opposite_text,
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
