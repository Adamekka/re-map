"""Fixed-context item proofs. RE2-COLLECT-007/008/011/014/016/017/019/020."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from games.re2.actor_part_proofs import (
    ActorPartProofConfig,
    ActorPartSupport,
    actor_part_copy_proof,
)
from games.re2.event_presence import (
    FLAG_WRITE_OPERATIONS,
    INITIALIZER_FALLTHROUGH,
    flag_write_conflicts,
)

# The pinned native actor search and shadow selector share this enemy table.
ENEMY_SLOT_COUNT = 32


@dataclass(frozen=True)
class ScenarioItemProof:
    fixed_context_preserved: bool
    absent_item_ids: list[int]
    item_variants: list[dict]
    unreachable_creator_offsets: frozenset[int] = frozenset()
    context_conditions: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        assert type(self.fixed_context_preserved) is bool
        assert type(self.unreachable_creator_offsets) is frozenset
        assert all(
            type(offset) is int and offset >= 0
            for offset in self.unreachable_creator_offsets
        )
        assert self.fixed_context_preserved or (
            not self.absent_item_ids
            and not self.item_variants
            and not self.unreachable_creator_offsets
            and not self.context_conditions
        ), "item proofs require a preserved fixed context"


def scenario_presence_flags(
    condition_flags: frozenset[tuple[int, int]],
    fixed_flags: list[dict[str, int]],
    context_preserved: bool,
) -> frozenset[tuple[int, int]]:
    assert type(context_preserved) is bool
    # A runtime gate alone cannot establish an earlier creator's branch.
    # Admit its predicates only after the whole source preserves that context.
    return condition_flags | frozenset(
        (row["bank"], row["bit"]) for row in fixed_flags if context_preserved
    )


def scenario_flags(profile: dict) -> list[dict[str, int]]:
    layout = profile["runtime_layout"]
    flags = []
    # Generation and loading must bind exclusion proofs to the same native
    # context that polling requires, including the initialized system mode.
    for address, mask, expected in (
        (
            layout["status_flags_address_ps1"],
            layout["scenario_mask"],
            layout["scenario_value"],
        ),
        (
            layout["system_flags_address_ps1"],
            layout.get("system_mode_mask"),
            layout.get("system_mode_value"),
        ),
    ):
        banks = [
            row
            for row in profile["flag_banks"]
            if int(row["address_ps1"], 0) == int(address, 0)
            and type(row["width"]) is int
            and row["width"] == 4
        ]
        if (
            type(mask) is not int
            or not 0 < mask <= 0xFFFFFFFF
            or type(expected) is not int
            or not 0 <= expected <= 0xFFFFFFFF
            or expected & ~mask
            or len(banks) != 1
            or type(banks[0]["bank"]) is not int
            or not 0 <= banks[0]["bank"] <= 255
        ):
            raise ValueError(
                "RE2 scenario and mode require fixed masks and matching flag banks"
            )
        flags.extend(
            {
                "bank": banks[0]["bank"],
                "bit": bit,
                "expected": int(bool(expected & (0x80000000 >> bit))),
            }
            for bit in range(32)
            if mask & (0x80000000 >> bit)
        )
    return flags


def scenario_effect_pool(profile: dict) -> tuple[int, int]:
    pool = profile.get("scenario_effect_pool")
    if type(pool) is not dict or pool.keys() != {"address_ps1", "limit_address_ps1"}:
        raise ValueError("invalid or missing RE2 scenario effect pool")
    try:
        start, limit = (
            int(pool[key], 0) for key in ("address_ps1", "limit_address_ps1")
        )
    except (TypeError, ValueError) as error:
        raise ValueError("invalid RE2 scenario effect pool addresses") from error
    if start % 4 or limit % 4 or not 0x80000000 <= start < limit <= 0x80200000:
        raise ValueError("RE2 scenario effect pool must fit aligned PS1 RAM")
    return start, limit


def scenario_vibration_writes(profile: dict) -> tuple[tuple[int, int], ...]:
    """Bound the opted-in native vibration stores. RE2-DS-003."""
    # An empty proof deliberately leaves vibration commands unsupported on
    # revisions whose handlers have not been audited.
    rows = profile.get("scenario_vibration_writes", [])
    if rows == []:
        return ()
    # The handlers write two four-byte scratch pointers and two queues of
    # 32 ten-byte records. Partial ranges cannot establish write exclusion.
    if (
        type(rows) is not list
        or len(rows) != 3
        or any(
            type(row) is not dict
            or row.keys() != {"address_ps1", "width"}
            or type(row["address_ps1"]) is not str
            or type(row["width"]) is not int
            or row["width"] != width
            for row, width in zip(rows, (8, 320, 320), strict=True)
        )
    ):
        raise ValueError("invalid RE2 vibration write proof")
    try:
        regions = tuple((int(row["address_ps1"], 0), row["width"]) for row in rows)
    except ValueError as error:
        raise ValueError("invalid RE2 vibration write address") from error
    if any(
        address % 4 or not 0x80000000 <= address <= 0x80200000 - width
        for address, width in regions
    ) or any(
        first < second + second_width and second < first + first_width
        for index, (first, first_width) in enumerate(regions)
        for second, second_width in regions[index + 1 :]
    ):
        raise ValueError("RE2 vibration writes must fit disjoint aligned PS1 RAM")
    return regions


def scenario_item_proofs(
    data: bytes,
    room: dict,
    flags: list[dict[str, int]],
    flag_banks: list[dict],
    effect_pool: tuple[int, int],
    vibration_writes: tuple[tuple[int, int], ...] = (),
    actor_parts: ActorPartProofConfig | ActorPartSupport = ActorPartSupport.Unaudited,
) -> ScenarioItemProof:
    """Prove absent acquisition IDs and surviving conflicting creator offsets."""
    fixed = {(row["bank"], row["bit"]): row["expected"] for row in flags}
    assert fixed and len(fixed) == len(flags)
    pool_start, pool_limit = effect_pool
    assert 0x80000000 <= pool_start < pool_limit <= 0x80200000
    assert not vibration_writes or (
        len(vibration_writes) == 3
        and tuple(width for _, width in vibration_writes) == (8, 320, 320)
        and all(
            type(address) is int
            and address % 4 == 0
            and 0x80000000 <= address <= 0x80200000 - width
            for address, width in vibration_writes
        )
    ), "vibration proof must cover both native queues and scratch pointers"
    if not room["candidate_list_complete"]:
        return ScenarioItemProof(False, [], [])
    banks = {
        row["bank"]: (int(row["address_ps1"], 0), row["width"]) for row in flag_banks
    }
    fixed_words, forbidden = flag_write_conflicts(banks, frozenset(fixed))
    # A negative claim needs every creator, including other tasks. Audited
    # event effects may change unrelated state, but cannot introduce an item
    # identity or change the fixed scenario bits. RE2-COLLECT-008.
    programs = room["programs"]
    commands = {
        key: {row["offset"]: row for row in program["commands"]}
        for key, program in programs.items()
    }
    fallthrough = set(INITIALIZER_FALLTHROUGH) - {0x22} | {8}
    fallthrough.update(
        (
            2,
            9,
            10,
            11,
            12,
            0x24,
            0x25,
            0x29,
            0x2A,
            0x2B,
            0x33,
            0x34,
            0x36,
            0x3C,
            0x3F,
            0x40,
            0x41,
            0x42,
            0x43,
            0x47,
            0x48,
            0x51,
            0x53,
            0x57,
            0x58,
            0x59,
            0x5B,
            0x62,
            0x66,
        )
    )
    # RE2-COLLECT-014: the input predicate writes only the task PC. Actor
    # attachment/forced-mode effects above write the selected actor, as do
    # the existing actor effects; none creates a pickup or changes fixed bits.
    predicates = {0x23, 0x3E, 0x50, 0x5E}
    status_writes = {
        0x29: (1, 0x00100100),
        0x2A: (1, 0x00100100),
        0x3C: (1, 0x00000100),
        0x59: (1, 0x00000020),
    }
    opaque_loops = set()
    for key, program in programs.items():
        if not any(
            row["opcode"] in (0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12)
            for row in program["commands"]
        ):
            continue
        # Loops and actor waits retain every decoded creator, including
        # fixed-false branches. Validate their mixed structure before using
        # that conservative set, so a malformed frame cannot hide a creator.
        loops, bodies, conditions = [], [], []
        loop_tests = set()
        for row in program["commands"]:
            opcode = row["opcode"]
            if row["kind"] == "if":
                test = commands[key].get(row["next"])
                if (
                    len(conditions) >= 8
                    or test is None
                    or test["opcode"] not in predicates | {0x21}
                    or row["target"] <= row["next"]
                    or row["target"] not in commands[key]
                ):
                    return ScenarioItemProof(False, [], [])
                conditions.append(row["target"])
            elif opcode in (7, 8):
                if not conditions or row["next"] != conditions.pop():
                    return ScenarioItemProof(False, [], [])
                if opcode == 7 and (
                    row["target"] < row["next"] or row["target"] not in commands[key]
                ):
                    return ScenarioItemProof(False, [], [])
            elif opcode in predicates | {0x21}:
                if row["offset"] not in loop_tests and not conditions:
                    return ScenarioItemProof(False, [], [])
            if opcode in (0x0D, 0x0F, 0x11):
                limit = (
                    row["next"] + struct.unpack_from("<h", data, row["offset"] + 2)[0]
                )
                if (
                    len(loops) >= 4
                    or limit <= row["next"]
                    or limit not in commands[key]
                ):
                    return ScenarioItemProof(False, [], [])
                loops.append((opcode, row["next"], limit, tuple(conditions)))
                if opcode == 0x0F:
                    test = commands[key].get(row["next"])
                    if (
                        test is None
                        or test["opcode"] not in predicates | {0x21}
                        or test["next"] - test["offset"] != data[row["offset"] + 1]
                    ):
                        return ScenarioItemProof(False, [], [])
                    loop_tests.add(test["offset"])
            elif opcode in (0x0E, 0x10, 0x12):
                if not loops:
                    return ScenarioItemProof(False, [], [])
                opening, start, limit, outer_conditions = loops.pop()
                if {0x0E: 0x0D, 0x10: 0x0F, 0x12: 0x11}[opcode] != opening or tuple(
                    conditions
                ) != outer_conditions:
                    return ScenarioItemProof(False, [], [])
                if opcode == 0x12:
                    test = commands[key].get(row["next"])
                    if (
                        test is None
                        or test["opcode"] not in predicates | {0x21}
                        or test["next"] - test["offset"] != data[row["offset"] + 1]
                        or test["next"] != limit
                    ):
                        return ScenarioItemProof(False, [], [])
                    loop_tests.add(test["offset"])
                elif row["next"] != limit:
                    return ScenarioItemProof(False, [], [])
                bodies.append((start, limit))
        if loops or conditions:
            return ScenarioItemProof(False, [], [])
        for start, limit in bodies:
            for row in program["commands"]:
                inside = start <= row["offset"] < limit
                if inside and (row["kind"] == "end" or row["opcode"] == 0x17):
                    return ScenarioItemProof(False, [], [])
                if row["kind"] in ("if", "jump") and inside != (
                    start <= row["target"] < limit
                ):
                    return ScenarioItemProof(False, [], [])
        opaque_loops.add(key)
    # The bounded actor proof assumes the initial fixed context. Every other
    # source write still passes the preservation guards below, so no unproved
    # operation can establish the context used to admit these numeric copies.
    actor_copy = actor_part_copy_proof(data, room, fixed, banks, actor_parts)
    actor_copies = actor_copy.offsets
    reset_ids = set()
    slot_kinds = {}
    for item in room["items"]:
        slot_kinds.setdefault(item["slot"], set()).add(2)
    for door in room["doors"]:
        slot_kinds.setdefault(door["slot"], set()).add(1)
    for program in programs.values():
        for row in program["commands"]:
            if row["kind"] in ("interaction", "reset"):
                slot_kinds.setdefault(row["slot"], set()).add(row["interaction"])
                if row["kind"] == "reset" and row["interaction"] == 2:
                    reset_ids.add(struct.unpack("<3H", bytes(row["data"]))[2])
    for key, program in programs.items():
        for row in program["commands"]:
            kind = row["kind"]
            if kind == "call":
                target = f"17:{row['procedure']}"
                if target not in programs:
                    return ScenarioItemProof(False, [], [])
            elif kind == "flag_write":
                if (
                    row["bank"] not in banks
                    or row["bit"] >= banks[row["bank"]][1] * 8
                    or row["operation"] not in FLAG_WRITE_OPERATIONS
                    or (row["bank"], row["bit"]) in forbidden
                ):
                    return ScenarioItemProof(False, [], [])
            elif kind == "end":
                if row["opcode"] != 1 or data[row["offset"] + 1] != 0:
                    return ScenarioItemProof(False, [], [])
            elif kind == "interaction":
                # Generic AOT creators must not hide an uncatalogued item.
                if row["interaction"] == 2:
                    return ScenarioItemProof(False, [], [])
            elif kind == "item":
                if data[row["offset"] + 2] not in (0, 2):
                    return ScenarioItemProof(False, [], [])
            elif kind == "reset":
                # A reset is another possible creator even without a matching
                # live descriptor. Its identity must never be excluded.
                # RE2-COLLECT-020: native indexing is signed and unchecked.
                # Setting the geometry bit can move subsequent payload reads
                # away from the bytes this reset actually writes.
                if not 0 <= row["slot"] < 32 or data[row["offset"] + 3] & 0x80:
                    return ScenarioItemProof(False, [], [])
                continue
            elif row["opcode"] in (0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12):
                if key not in opaque_loops:
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] == 0x1D:
                if row["offset"] in actor_copies:
                    continue
                width = 2 if data[row["offset"] + 3] else 1
                target = row["next"] + data[row["offset"] + 2]
                destination = next(
                    (
                        command
                        for command in program["commands"]
                        if command["offset"] <= target
                        and target + width <= command["next"]
                    ),
                    None,
                )
                # Native Copy writes a counter into later bytecode. Permit
                # only numeric position/destination operands, never opcodes,
                # identities, predicates, branches, pointers or loop controls.
                if (
                    destination is None
                    or destination["opcode"] not in (0x32, 0x40)
                    or target
                    < destination["offset"]
                    + (2 if destination["opcode"] == 0x32 else 4)
                    or width == 2
                    and target % 2
                ):
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] == 0x3A:
                # RE2-COLLECT-019: reference zero reads a static transform.
                # Allocation writes only the fixed 96-by-124-byte effect pool,
                # apart from task PC/stack. Other reference forms stay opaque;
                # a profile-fixed word must not alias any part of that pool.
                if data[row["offset"] + 4] != 0 or any(
                    address < pool_limit and pool_start < address + 4
                    for address in fixed_words
                ):
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] in (0x8A, 0x8B):
                # RE2-DS-003: these synchronous handlers only enqueue bounded
                # vibration records and update their scratch pointers. Require
                # the revision's complete write proof before preserving bits.
                if not vibration_writes or any(
                    address < start + width and start < address + 4
                    for address in fixed_words
                    for start, width in vibration_writes
                ):
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] == 0x37:
                collision = struct.unpack_from("<I", data, 0x20)[0]
                if not collision or collision % 4 or collision + 16 > len(data):
                    return ScenarioItemProof(False, [], [])
                count = struct.unpack_from("<I", data, collision + 4)[0]
                limit = min(
                    [len(data)]
                    + [
                        offset
                        for offset in room["section_offsets"]
                        if offset > collision
                    ]
                )
                # The native index skips the 16-byte SCA header. Its halfword
                # store must stay in a declared collision record, outside all
                # script bytes, so it cannot rewrite a creator or fixed test.
                if (
                    count < 1
                    or data[row["offset"] + 1] >= count - 1
                    or collision + count * 16 > limit
                    or any(
                        collision < source["limit"]
                        and source["entry"] < collision + count * 16
                        for source in programs.values()
                    )
                ):
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] == 0x60:
                category, index = data[row["offset"] + 1 : row["offset"] + 3]
                # Other selectors leave the native shadow pointer uninitialized;
                # enemy indices are signed and must stay within the actor table.
                if category not in (1, 2, 3) or (
                    category == 3 and index >= ENEMY_SLOT_COUNT
                ):
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] == 4:
                if (
                    data[row["offset"] + 1 : row["offset"] + 3] != b"\xff\x18"
                    or f"17:{data[row['offset'] + 3]}" not in programs
                ):
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] == 0x47:
                kinds = slot_kinds.get(data[row["offset"] + 1], set())
                if not kinds or not kinds <= {0, 1, 2, 5}:
                    return ScenarioItemProof(False, [], [])
                # Item and door dispatch also set native status bits. Binding
                # an allowed interaction kind alone does not preserve them.
                if any(
                    bank not in banks or fixed_words.get(banks[bank][0], 0) & mask
                    for interaction, bank, mask in (
                        (1, 2, 0xFF000000),
                        (2, 1, 0x00008000),
                    )
                    if interaction in kinds
                ):
                    return ScenarioItemProof(False, [], [])
            elif row["opcode"] == 0x2E:
                work, index = data[row["offset"] + 1 : row["offset"] + 3]
                # Work_set reads a signed index without checking bounds. The
                # native actor search covers 32 enemy pointers; object
                # selection uses direct positive-offset structures.
                if (
                    work not in (1, 3, 4)
                    or work == 3
                    and index >= ENEMY_SLOT_COUNT
                    or work == 4
                    and index >= 128
                ):
                    return ScenarioItemProof(False, [], [])
            elif not (
                kind in ("if", "flag_check", "door")
                or row["opcode"] in predicates
                or kind == "award"
                or row["opcode"] == 7
                or row["opcode"] in fallthrough
            ):
                return ScenarioItemProof(False, [], [])
            # These native camera/audio commands write named status bits, even
            # though they preserve ordinary item creation. Reject overlap with
            # any profile-fixed bit instead of assuming this profile's mask.
            if row["opcode"] in status_writes or row["opcode"] == 0x2B:
                bank, mask = (
                    (2, struct.unpack_from("<H", data, row["offset"] + 4)[0] << 16)
                    if row["opcode"] == 0x2B
                    else status_writes[row["opcode"]]
                )
                if bank not in banks or fixed_words.get(banks[bank][0], 0) & mask:
                    return ScenarioItemProof(False, [], [])
    # Also reject raw writer candidates outside decoded paths, within procedure
    # extents. Geometry and texture bytes outside scripts are not commands.
    # False positives withhold proof rather than inventing a fixed assumption.
    if any(
        bytes((0x22, bank, bit)) in data[program["entry"] : program["limit"]]
        for bank, bit in forbidden
        for program in programs.values()
    ):
        return ScenarioItemProof(False, [], [])

    # Loop procedures contribute every decoded creator, independently of any
    # fixed predicate. A wait cannot hide an alternative creator from proof.
    pending = [
        (key, program["entry"], ())
        for key, program in programs.items()
        if key not in opaque_loops
    ]
    seen = set()
    reached = {(key, position) for key in opaque_loops for position in commands[key]}
    steps = len(reached)
    if steps > 4096:
        return ScenarioItemProof(False, [], [])
    while pending:
        key, position, conditions = pending.pop()
        state = key, position, conditions
        if state in seen:
            continue
        steps += 1
        if steps > 4096 or position not in commands[key]:
            return ScenarioItemProof(False, [], [])
        seen.add(state)
        reached.add((key, position))
        row = commands[key][position]
        if row["kind"] == "end":
            continue
        if row["kind"] == "if":
            position = row["next"]
            tests = []
            while (
                position in commands[key]
                and commands[key][position]["kind"] == "flag_check"
            ):
                test = commands[key][position]
                tests.append(test)
                steps += 1
                position = test["next"]
                if steps > 4096:
                    return ScenarioItemProof(False, [], [])
            if not tests:
                if (
                    position not in commands[key]
                    or commands[key][position]["opcode"] not in predicates
                ):
                    return ScenarioItemProof(False, [], [])
                position = commands[key][position]["next"]
            branches = (False, True)
            if (
                len(tests) == 1
                and (tests[0]["bank"], tests[0]["bit"]) in fixed
                and tests[0]["expected"] in (0, 1)
            ):
                test = tests[0]
                branches = (fixed[test["bank"], test["bit"]] == test["expected"],)
            # False checks pop the native IF frame; true checks retain it
            # until Else/Endif. Unknown predicates may take either path.
            if False in branches:
                pending.append((key, row["target"], conditions))
            if True in branches:
                # This source family has five nested actor predicates. Keep
                # an explicit analysis bound while retaining every branch.
                if len(conditions) >= 8:
                    return ScenarioItemProof(False, [], [])
                pending.append((key, position, conditions + (row["target"],)))
        elif row["kind"] == "flag_check" or row["opcode"] in predicates:
            if not conditions:
                return ScenarioItemProof(False, [], [])
            # Opaque predicates can fail after another condition succeeded.
            # Include their false continuation as well as their true one.
            pending.append((key, conditions[-1], conditions[:-1]))
            pending.append((key, row["next"], conditions))
        elif row["opcode"] in (7, 8):
            if not conditions:
                return ScenarioItemProof(False, [], [])
            pending.append(
                (
                    key,
                    row["target"] if row["opcode"] == 7 else row["next"],
                    conditions[:-1],
                )
            )
        else:
            # Calls may return; every callee entry is independently seeded.
            # Ignoring nontermination adds possible paths rather than hiding one.
            pending.append((key, row["next"], conditions))
    targets = {}
    items = {item["offset"]: item for item in room["items"]}
    for key, program in programs.items():
        for row in program["commands"]:
            if row["kind"] == "item":
                targets.setdefault(items[row["item"]]["global_id"], set()).add(
                    (key, row["offset"])
                )
    assert targets.keys() == {item["global_id"] for item in room["items"]}
    absent = sorted(
        gid
        for gid, creators in targets.items()
        if not creators & reached
        and gid not in reset_ids
        and len({item["type"] for item in room["items"] if item["global_id"] == gid})
        == 1
    )
    reachable_resets = [
        (row, struct.unpack("<3H", bytes(row["data"])))
        for key, program in programs.items()
        for row in program["commands"]
        if row["kind"] == "reset" and (key, row["offset"]) in reached
    ]
    variants = []
    for gid, creators in sorted(targets.items()):
        definitions = [item for item in room["items"] if item["global_id"] == gid]
        possible = [items[offset] for _, offset in creators & reached]
        # Reachable resets are independent identity sources. Admit them only
        # when they preserve a selected creator's slot, identity and published
        # quantity set. This proves neither presence nor scenario absence.
        if (
            len({item["type"] for item in definitions}) > 1
            and len({item["type"] for item in possible}) == 1
        ):
            slots = {item["slot"] for item in possible}
            payloads = {
                (item["slot"], item["type"], amount, gid)
                for item in possible
                for amount in item["amounts"]
            }
            if any(
                (row["slot"] in slots or row["interaction"] == 2 and payload[2] == gid)
                and not (
                    row["interaction"] == 0
                    and not any(row["data"])
                    or row["interaction"] == 2
                    and row["slot"] in slots
                    and (row["slot"], *payload) in payloads
                )
                for row, payload in reachable_resets
            ):
                continue
            variants.append(
                {
                    "global_id": gid,
                    "offsets": sorted(item["offset"] for item in possible),
                }
            )
    # Keep creator reachability separate from item-ID exclusion: an impossible
    # generic interaction can conflict with a reachable item's slot too.
    unreachable_creators = frozenset(
        row["offset"]
        for key, program in programs.items()
        for row in program["commands"]
        if row["kind"] in ("item", "interaction", "door", "reset")
        and (key, row["offset"]) not in reached
    )
    return ScenarioItemProof(
        True, absent, variants, unreachable_creators, actor_copy.context_conditions
    )


def scenario_item_candidates(room: dict) -> list[dict]:
    """Apply source-proven variant selection without discarding the raw catalog."""
    selected = {
        row["global_id"]: set(row["offsets"]) for row in room["scenario_item_variants"]
    }
    return [
        item
        for item in room["items"]
        if item["global_id"] not in selected
        or item["offset"] in selected[item["global_id"]]
    ]
