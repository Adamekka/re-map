"""Current-room witnesses for script-dispatched pickups. RE2-DISPATCH-001.

These relations require fresh callback code and both registry bindings. They
establish an uncollected item, not automatic activation or departed presence.
"""

from __future__ import annotations

import hashlib
import itertools
from dataclasses import dataclass
from enum import Enum


class ScriptItemDispatchSupport(Enum):
    Unaudited = "unaudited"


@dataclass(frozen=True)
class ScriptItemDispatchConfig:
    main_table_address: int
    message_preserved_flag_ranges: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        assert (
            type(self.main_table_address) is int
            and self.main_table_address % 4 == 0
            and 0x80000000 <= self.main_table_address <= 0x80200000 - 4
        ), "script item dispatch needs an aligned PS1 RAM table-pointer word"
        assert type(self.message_preserved_flag_ranges) is tuple
        assert 1 <= len(self.message_preserved_flag_ranges) <= 16
        assert all(
            type(row) is tuple
            and len(row) == 2
            and type(row[0]) is int
            and type(row[1]) is int
            and row[0] % 4 == 0
            and row[1] % 4 == 0
            and 4 <= row[1] <= 4096
            and 0x80000000 <= row[0] <= 0x80200000 - row[1]
            for row in self.message_preserved_flag_ranges
        ), "message-preserved flags must use bounded aligned PS1 RAM words"
        assert not any(
            first < second + second_width and second < first + first_width
            for index, (first, first_width) in enumerate(
                self.message_preserved_flag_ranges
            )
            for second, second_width in self.message_preserved_flag_ranges[index + 1 :]
        ), "message-preserved ranges must not overlap"


def script_item_dispatch(
    profile: dict,
) -> ScriptItemDispatchConfig | ScriptItemDispatchSupport:
    if "script_item_dispatch" not in profile:
        return ScriptItemDispatchSupport.Unaudited
    raw = profile["script_item_dispatch"]
    if (
        type(raw) is not dict
        or raw.keys() != {"main_table_address_ps1", "message_preserved_flag_ranges"}
        or type(raw["main_table_address_ps1"]) is not str
    ):
        raise ValueError("invalid RE2 script item dispatch configuration")
    try:
        address = int(raw["main_table_address_ps1"], 0)
    except ValueError as error:
        raise ValueError("invalid RE2 script item dispatch table address") from error
    if address % 4 or not 0x80000000 <= address <= 0x80200000 - 4:
        raise ValueError("invalid RE2 script item dispatch table address")
    ranges = raw["message_preserved_flag_ranges"]
    if type(ranges) is not list or not 1 <= len(ranges) <= 16:
        raise ValueError("invalid RE2 message-preserved flag ranges")
    parsed = []
    for row in ranges:
        if (
            type(row) is not dict
            or row.keys() != {"address_ps1", "width"}
            or type(row["address_ps1"]) is not str
            or type(row["width"]) is not int
        ):
            raise ValueError("invalid RE2 message-preserved flag range")
        try:
            base = int(row["address_ps1"], 0)
        except ValueError as error:
            raise ValueError("invalid RE2 message-preserved flag address") from error
        width = row["width"]
        if (
            base % 4
            or width % 4
            or not 4 <= width <= 4096
            or not 0x80000000 <= base <= 0x80200000 - width
        ):
            raise ValueError("invalid RE2 message-preserved flag bounds")
        if any(base < other + size and other < base + width for other, size in parsed):
            raise ValueError("overlapping RE2 message-preserved flag ranges")
        parsed.append((base, width))
    return ScriptItemDispatchConfig(address, tuple(parsed))


def script_dispatch_relations(
    data: bytes,
    room: dict,
    item_bank: int,
    flag_banks: dict[int, tuple[int, int]],
    registry_capacity: int,
    config: ScriptItemDispatchConfig,
) -> list[dict]:
    assert type(registry_capacity) is int and 1 <= registry_capacity <= 256
    assert item_bank in flag_banks
    assert isinstance(config, ScriptItemDispatchConfig)
    programs = room["programs"]
    result = []
    proven_pairs = set()

    def flag_key(bank: int, bit: int) -> tuple[int, int]:
        assert bank in flag_banks and 0 <= bit < flag_banks[bank][1] * 8
        return flag_banks[bank][0] + bit // 32 * 4, 0x80000000 >> (bit % 32)

    for source in programs.values():
        for callback in source["commands"]:
            if callback["kind"] != "interaction" or callback["interaction"] != 5:
                continue
            opcode = callback["opcode"]
            if (
                opcode not in (0x2C, 0x67)
                or not 0 <= callback["slot"] < registry_capacity
            ):
                continue
            four_point = opcode == 0x67
            descriptor = data[callback["offset"] + 2 : callback["next"]]
            if not descriptor[1] or bool(descriptor[1] & 0x80) != four_point:
                continue
            payload = data[
                callback["offset"] + (22 if four_point else 14) : callback["next"]
            ]
            if len(payload) != 6 or payload[:3] != b"\xff\0\x18" or any(payload[4:]):
                continue
            procedure = payload[3]
            program = programs.get(f"17:{procedure}")
            if program is None:
                continue
            table = room["section_offsets"][17]
            entry = table + procedure * 2
            table_width = int.from_bytes(data[table : table + 2], "little")
            if (
                procedure * 2 + 2 > table_width
                or entry + 2 > len(data)
                or table + int.from_bytes(data[entry : entry + 2], "little")
                != program["entry"]
            ):
                continue
            commands = {row["offset"]: row for row in program["commands"]}
            ordered = program["commands"]
            if (
                not ordered
                or ordered[0]["offset"] != program["entry"]
                or any(
                    first["next"] != second["offset"]
                    for first, second in itertools.pairwise(ordered)
                )
            ):
                continue
            # The entire hashed procedure is required at runtime. Supporting
            # only this closed command set avoids assuming a callback's calls,
            # source mutation or task replacement will eventually return here.
            if any(
                row["opcode"] not in (0, 1, 6, 7, 8, 0x21, 0x22, 0x2B, 0x47)
                for row in ordered
            ):
                continue
            # The audited nonchoice UI path preserves saved flags for this
            # mode/STOP mask. Bind both language resources because later Copy
            # commands can change text even when callback code stays intact.
            message_proofs = {}
            valid_messages = True
            for row in ordered:
                if row["opcode"] != 0x2B:
                    continue
                packet = data[row["offset"] : row["next"]]
                if (
                    len(packet) != 6
                    or packet[:2] != b"\x2b\0"
                    or packet[3:] != b"\0\xff\xff"
                ):
                    valid_messages = False
                    break
                for section in (13, 14):
                    table = room["section_offsets"][section]
                    boundary = min(
                        (
                            offset
                            for offset in room["section_offsets"]
                            if offset > table
                        ),
                        default=len(data),
                    )
                    if not 0 < table <= boundary - 2:
                        valid_messages = False
                        break
                    table_width = int.from_bytes(data[table : table + 2], "little")
                    if (
                        table_width % 2
                        or not 2 <= table_width <= 512
                        or table + table_width > boundary
                        or packet[2] + 1 >= table_width // 2
                    ):
                        valid_messages = False
                        break
                    entries = [
                        int.from_bytes(data[position : position + 2], "little")
                        for position in range(table, table + table_width, 2)
                    ]
                    if any(
                        not table_width <= entry <= boundary - table
                        for entry in entries
                    ) or any(
                        first > second for first, second in itertools.pairwise(entries)
                    ):
                        valid_messages = False
                        break
                    start, end = (
                        table + entries[index] for index in (packet[2], packet[2] + 1)
                    )
                    if not 2 <= end - start <= 4096:
                        valid_messages = False
                        break
                    position, terminated = start, False
                    while position < end:
                        command = data[position]
                        position += 1
                        if command <= 0xED or command == 0xFC:
                            continue
                        if (
                            command not in (0xEE, 0xEF, 0xF0, 0xF9, 0xFA, 0xFD, 0xFE)
                            or position == end
                            or command == 0xFA
                            and data[position] == 0
                        ):
                            break
                        position += 1
                        if command == 0xFE:
                            terminated = not any(data[position:end])
                            break
                    if not terminated:
                        valid_messages = False
                        break
                    for offset, width in (
                        (table + packet[2] * 2, 4),
                        (start, end - start),
                    ):
                        message_proofs[offset, width] = {
                            "offset": offset,
                            "width": width,
                            "sha256": hashlib.sha256(
                                data[offset : offset + width]
                            ).hexdigest(),
                        }
                if not valid_messages:
                    break
            if not valid_messages or len(message_proofs) > 64:
                continue
            dispatches = {
                data[row["offset"] + 1] for row in ordered if row["opcode"] == 0x47
            }
            if len(dispatches) != 1:
                continue
            target_slot = next(iter(dispatches))
            if target_slot >= registry_capacity or target_slot == callback["slot"]:
                continue
            valid, flags = True, set()
            for row in ordered:
                position, opcode = row["offset"], row["opcode"]
                if row["kind"] in ("flag_check", "flag_write"):
                    bank, bit = row["bank"], row["bit"]
                    if bank not in flag_banks or not 0 <= bit < flag_banks[bank][1] * 8:
                        valid = False
                        break
                    if row["kind"] == "flag_check" and row["expected"] not in (0, 1):
                        valid = False
                        break
                    if row["kind"] == "flag_write" and row["operation"] not in (
                        0,
                        1,
                        7,
                    ):
                        valid = False
                        break
                    flags.add(flag_key(bank, bit))
                elif opcode in (1, 8) and data[position + 1] != 0:
                    valid = False
                    break
                elif opcode in (6, 7):
                    target = row["target"]
                    if target <= row["next"] or target not in commands:
                        valid = False
                        break
            if not valid or len(flags) > 8:
                continue
            if any(
                not any(
                    base <= address <= base + width - 4
                    for base, width in config.message_preserved_flag_ranges
                )
                for address, _ in flags
            ):
                # Control words can stop script scheduling even without a
                # message. Restrict the entire VM to audited saved flag words,
                # whose writes also survive the native message/UI handlers.
                continue

            # Validate both outcomes without a fixed game context. A malformed
            # branch cannot enter a body with the native IF frame missing.
            pending, seen, frame_at = [(program["entry"], ())], set(), {}
            while pending and valid:
                position, frames = pending.pop()
                if (position, frames) in seen:
                    continue
                if len(seen) >= 1024 or position not in commands:
                    valid = False
                    break
                if position in frame_at and frame_at[position] != frames:
                    valid = False
                    break
                frame_at[position] = frames
                seen.add((position, frames))
                row = commands[position]
                opcode = row["opcode"]
                if opcode == 1:
                    valid = not frames
                elif opcode == 6:
                    predicate = commands.get(row["next"])
                    if (
                        len(frames) >= 8
                        or predicate is None
                        or predicate["kind"] != "flag_check"
                    ):
                        valid = False
                        break
                    pending.extend(
                        (
                            (predicate["next"], frames + (row["target"],)),
                            (row["target"], frames),
                        )
                    )
                elif opcode in (7, 8):
                    if not frames or frames[-1] != row["next"]:
                        valid = False
                        break
                    pending.append(
                        (row["target"] if opcode == 7 else row["next"], frames[:-1])
                    )
                elif opcode == 0x21:
                    valid = False
                else:
                    pending.append((row["next"], frames))
            if not valid:
                continue

            for item in room["items"]:
                identity = item["offset"], callback["offset"]
                if identity in proven_pairs:
                    continue
                if (
                    item["slot"] != target_slot
                    or not 0 <= item["global_id"] < flag_banks[item_bank][1] * 8
                ):
                    continue
                acquisition = flag_key(item_bank, item["global_id"])
                if not any(
                    base <= acquisition[0] <= base + width - 4
                    for base, width in config.message_preserved_flag_ranges
                ):
                    continue
                # Collection belongs to the native pickup handler. A callback
                # cannot manufacture the acquisition before delivering it.
                if any(
                    row["kind"] == "flag_write"
                    and flag_key(row["bank"], row["bit"]) == acquisition
                    for row in ordered
                ):
                    continue
                free_flags = sorted(flags - {acquisition})
                proven = True
                for initial in itertools.product((False, True), repeat=len(free_flags)):
                    values = dict(zip(free_flags, initial, strict=True)) | {
                        acquisition: False
                    }
                    prior_states, dispatched = set(), False
                    # A first interaction may only set an inspection guard and
                    # display a message. Retrying is allowed after it finishes;
                    # repeating a state without dispatch withholds the proof.
                    for _ in range(16):
                        state = tuple(sorted(values.items()))
                        if state in prior_states:
                            break
                        prior_states.add(state)
                        position = program["entry"]
                        for _ in range(256):
                            row = commands[position]
                            opcode = row["opcode"]
                            if opcode == 1:
                                break
                            if opcode == 6:
                                predicate = commands[row["next"]]
                                matches = values[
                                    flag_key(predicate["bank"], predicate["bit"])
                                ] == bool(predicate["expected"])
                                position = (
                                    predicate["next"] if matches else row["target"]
                                )
                            elif opcode == 7:
                                position = row["target"]
                            elif opcode == 0x22:
                                key = flag_key(row["bank"], row["bit"])
                                operation = row["operation"]
                                values[key] = (
                                    not values[key]
                                    if operation == 7
                                    else bool(operation)
                                )
                                position = row["next"]
                            elif opcode == 0x47:
                                dispatched = True
                                break
                            else:
                                position = row["next"]
                        else:
                            break
                        if dispatched:
                            break
                    if not dispatched:
                        proven = False
                        break
                if proven:
                    start, width = program["entry"], program["limit"] - program["entry"]
                    if not 1 <= width <= 4096:
                        continue
                    proven_pairs.add(identity)
                    result.append(
                        {
                            "item_offset": item["offset"],
                            "callback_offset": callback["offset"],
                            "callback_slot": callback["slot"],
                            "callback_four_point": four_point,
                            "target_slot": target_slot,
                            "procedure": procedure,
                            "callback_proof": {
                                "offset": callback["offset"] + 2,
                                "width": len(descriptor),
                                "sha256": hashlib.sha256(descriptor).hexdigest(),
                            },
                            "message_proofs": [
                                message_proofs[key] for key in sorted(message_proofs)
                            ],
                            "table_proof": {
                                "offset": entry,
                                "width": 2,
                                "sha256": hashlib.sha256(
                                    data[entry : entry + 2]
                                ).hexdigest(),
                            },
                            "program_proof": {
                                "offset": start,
                                "width": width,
                                "sha256": hashlib.sha256(
                                    data[start : start + width]
                                ).hexdigest(),
                            },
                        }
                    )
    return result
