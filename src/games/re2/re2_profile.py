"""Pinned RE2 identities, bounded memory layouts and required metadata."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from games.game_profile import ItemQuery, RoomId, RoomQuery
from games.item_quantity import parse_unit_count_item_types
from games.re2.actor_part_proofs import ActorPartSupport, scenario_actor_parts
from games.re2.clip_effect_proof import ClipEffectSupport, clipping_effect_proof
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.initializer_control_proof import (
    InitializerControlConfig,
    initializer_control_config,
)
from games.re2.map_layout import Re2MapLayout, Re2MapProjection
from games.re2.room_entry_contract import (
    RoomEntryContractConfig,
    RoomEntryContractFailure,
    room_entry_contract,
)
from games.re2.scenario_items import (
    scenario_effect_pool,
    scenario_flags,
    scenario_item_candidates,
    scenario_presence_flags,
    scenario_vibration_writes,
)
from games.re2.script_dispatch_items import (
    ScriptItemDispatchConfig,
    ScriptItemDispatchSupport,
    script_item_dispatch,
)
from games.re2.startup_declarations import (
    StartupDeclarationAuditConfig,
    startup_declaration_audit,
)
from games.re2.startup_effects import StartupEffectAuditConfig, startup_effect_audit
from games.runtime_identity import MemoryResult, RuntimeSignature


@dataclass(frozen=True)
class Re2Target:
    serial: str
    scenario: str
    label: str
    executable_name: str
    player_index: int
    room_count: int
    excluded_room_stages: str
    history_filename: str


RE2_TARGETS = {
    "re2_leon_a_slus00748": Re2Target(
        "SLUS-00748",
        "leon-a",
        "Leon A",
        "SLUS_007.48",
        0,
        125,
        "ABCDEFG",
        "re2-leon-a-slus00748.json",
    ),
    "re2_claire_b_slus00756": Re2Target(
        "SLUS-00756",
        "claire-b",
        "Claire B",
        "SLUS_007.56",
        1,
        125,
        "ABCDEFG",
        "re2-claire-b-slus00756.json",
    ),
    "re2_leon_a_slus00421": Re2Target(
        "SLUS-00421", "leon-a", "Leon A", "SLUS_004.21", 0, 125, "", "re2-leon-a.json"
    ),
    "re2_claire_b_slus00592": Re2Target(
        "SLUS-00592",
        "claire-b",
        "Claire B",
        "SLUS_005.92",
        1,
        127,
        "",
        "re2-claire-b.json",
    ),
}


def re2_target(raw: dict) -> Re2Target:
    target = RE2_TARGETS.get(raw["profile_id"])
    if target is None or (raw["serial"], raw["scenario"]) != (
        target.serial,
        target.scenario,
    ):
        raise ValueError("unsupported RE2 revision or scenario")
    return target


@dataclass(frozen=True)
class Re2Profile:
    profile_id: str
    target: Re2Target
    revision: str
    executable_identity: str
    stage_address: int
    room_address: int
    camera_address: int
    runtime_signature: RuntimeSignature
    runtime_layout: dict
    flag_banks: dict[int, tuple[int, int]]
    rooms: dict[str, dict]
    unsupported_sources: dict[str, dict]
    names: dict
    map_layout: Re2MapLayout
    script_item_dispatch: ScriptItemDispatchConfig | ScriptItemDispatchSupport
    unit_count_item_types: frozenset[int]

    @staticmethod
    def load(path: Path) -> Re2Profile:
        raw = json.loads(path.read_text())
        unit_counts = parse_unit_count_item_types(raw.get("unit_count_item_types"))
        target = re2_target(raw)
        if (
            raw["address_space"] != "PS1 virtual address, little-endian"
            or raw["room_value_width_bytes"] != 2
        ):
            raise ValueError("unsupported RE2 revision, scenario or address layout")
        signature = raw["runtime_signature"]
        addresses = tuple(int(value, 0) for value in signature["window_addresses_ps1"])
        width = signature["window_width_bytes"]
        digest = signature["concatenated_sha256"]
        room_addresses = tuple(
            int(raw[key], 0)
            for key in ("stage_address_ps1", "room_address_ps1", "camera_address_ps1")
        )
        if (
            not addresses
            or type(width) is not int
            or not 1 <= width <= 4096
            or len(digest) != 64
            or any(value not in "0123456789abcdef" for value in digest)
            or any(
                not 0x80000000 <= address <= 0x80200000 - size
                for address, size in (
                    *((address, width) for address in addresses),
                    *((address, 2) for address in room_addresses),
                )
            )
        ):
            raise ValueError("invalid RE2 runtime identity or room addresses")
        layout = raw["runtime_layout"]
        _, flag_proof = presence_flag_write_proof(raw)
        presence_counter_indices(raw)
        scenario_effect_pool(raw)
        scenario_vibration_writes(raw)
        actor_parts = scenario_actor_parts(raw)
        clipping = clipping_effect_proof(raw)
        dispatch = script_item_dispatch(raw)
        startup_audit = startup_effect_audit(raw)
        control_config = initializer_control_config(raw)
        declaration_config = startup_declaration_audit(raw)
        entry_contract = room_entry_contract(raw)
        if isinstance(entry_contract, RoomEntryContractFailure):
            raise ValueError(entry_contract.value)
        if isinstance(control_config, InitializerControlConfig) and not isinstance(
            entry_contract, RoomEntryContractConfig
        ):
            raise ValueError("RE2 initializer control requires a room write layout")
        if isinstance(entry_contract, RoomEntryContractConfig) and (
            raw["executable_identity"]
            != target.executable_name + " SHA256 " + entry_contract.executable_sha256
            or int(layout["aot_table_address_ps1"], 0)
            != int(entry_contract.write_partitions.aot_address_ps1, 0)
            or layout["aot_capacity"] != entry_contract.write_partitions.aot_capacity
        ):
            raise ValueError("RE2 room-entry proof disagrees with its revision layout")
        if isinstance(entry_contract, RoomEntryContractConfig):
            entry_stages = frozenset(row.stage for row in entry_contract.stage_entries)
        if isinstance(declaration_config, StartupDeclarationAuditConfig):
            declaration_sources = {
                row.room_id: row for row in declaration_config.selection.sources
            }
        if layout["aot_capacity"] != 32 or any(
            not 0x80000000 <= int(value, 0) < 0x80200000
            for key, value in layout.items()
            if key.endswith("_address_ps1")
        ):
            raise ValueError("invalid RE2 runtime memory layout")
        quantity_override = layout.get("pickup_quantity_override")
        if (
            type(quantity_override) is not dict
            or quantity_override.keys() != {"system_mask", "item_type", "amount"}
            or any(type(value) is not int for value in quantity_override.values())
            or not 0 < quantity_override["system_mask"] <= 0xFFFFFFFF
            or quantity_override["system_mask"] & (quantity_override["system_mask"] - 1)
            or not 0 <= quantity_override["item_type"] < layout["file_type_min"]
            or not 0 <= quantity_override["amount"] <= 0xFFFF
        ):
            raise ValueError("invalid or missing RE2 pickup quantity override")
        banks = {
            row["bank"]: (int(row["address_ps1"], 0), row["width"])
            for row in raw["flag_banks"]
        }
        blocks = [
            (int(layout[f"{kind}_block_address_ps1"], 0), layout[f"{kind}_block_width"])
            for kind in ("player", "save")
        ]
        player_base, player_width = blocks[0]
        if any(
            not player_base
            <= int(layout[field], 0)
            <= player_base + player_width - size
            for field, size in (
                ("player_position_address_ps1", 12),
                ("player_facing_address_ps1", 2),
            )
        ):
            raise ValueError("RE2 player pose must fit the initial player block")
        if any(
            not 0x80000000 <= address <= 0x80200000 - size or not 1 <= size <= 4096
            for address, size in blocks
        ) or any(
            not any(
                base <= address and address + width <= base + size
                for base, size in blocks
            )
            for address, width in banks.values()
        ):
            raise ValueError("RE2 state banks must fit the bounded read blocks")
        document = json.loads((path.parent / raw["room_metadata_path"]).read_text())
        if (
            document["schema"] != 1
            or document["profile_id"] != raw["profile_id"]
            or document["executable_identity"] != raw["executable_identity"]
        ):
            raise ValueError("RE2 room metadata disagrees with the pinned revision")
        if document.get("presence_counter_writes") != raw["presence_counter_writes"]:
            raise ValueError("RE2 counter proof disagrees with its revision layout")
        if document.get("scenario_effect_pool") != raw["scenario_effect_pool"]:
            raise ValueError("RE2 effect pool proof disagrees with its revision layout")
        if ("startup_declaration_audit" in document) != isinstance(
            declaration_config, StartupDeclarationAuditConfig
        ) or (
            isinstance(declaration_config, StartupDeclarationAuditConfig)
            and json.dumps(document["startup_declaration_audit"], sort_keys=True)
            != json.dumps(raw["startup_declaration_audit"], sort_keys=True)
        ):
            raise ValueError(
                "RE2 startup declaration audit disagrees with its revision"
            )
        if ("initializer_control_audit" in document) != (
            isinstance(control_config, InitializerControlConfig)
        ) or (
            isinstance(control_config, InitializerControlConfig)
            and json.dumps(document["initializer_control_audit"], sort_keys=True)
            != json.dumps(raw["initializer_control_audit"], sort_keys=True)
        ):
            raise ValueError(
                "RE2 initializer control audit disagrees with its revision layout"
            )
        if ("startup_effect_audit" in document) != (
            isinstance(startup_audit, StartupEffectAuditConfig)
        ) or (
            isinstance(startup_audit, StartupEffectAuditConfig)
            and json.dumps(document["startup_effect_audit"], sort_keys=True)
            != json.dumps(raw["startup_effect_audit"], sort_keys=True)
        ):
            raise ValueError(
                "RE2 startup effect audit disagrees with its revision layout"
            )
        if json.dumps(
            document.get("scenario_vibration_writes", []), sort_keys=True
        ) != json.dumps(raw.get("scenario_vibration_writes", []), sort_keys=True):
            raise ValueError("RE2 vibration proof disagrees with its revision layout")
        if json.dumps(
            document.get("scenario_actor_parts", []), sort_keys=True
        ) != json.dumps(raw.get("scenario_actor_parts", []), sort_keys=True) or (
            actor_parts is not ActorPartSupport.Unaudited
            and document.get("actor_part_resource_table_address_ps1")
            != raw["metadata_layout"]["actor_part_resource_table_address_ps1"]
        ):
            raise ValueError("RE2 actor-part proof disagrees with its revision layout")
        if ("scenario_clipping" in document) != (
            clipping is not ClipEffectSupport.Unaudited
        ) or (
            clipping is not ClipEffectSupport.Unaudited
            and json.dumps(document["scenario_clipping"], sort_keys=True)
            != json.dumps(raw["scenario_clipping"], sort_keys=True)
        ):
            raise ValueError("RE2 clipping proof disagrees with its revision layout")
        if ("script_item_dispatch" in document) != (
            dispatch is not ScriptItemDispatchSupport.Unaudited
        ) or (
            dispatch is not ScriptItemDispatchSupport.Unaudited
            and json.dumps(document["script_item_dispatch"], sort_keys=True)
            != json.dumps(raw["script_item_dispatch"], sort_keys=True)
        ):
            raise ValueError(
                "RE2 script item dispatch disagrees with its revision layout"
            )
        if ("room_entry_contract" in document) != (
            isinstance(entry_contract, RoomEntryContractConfig)
        ) or (
            isinstance(entry_contract, RoomEntryContractConfig)
            and json.dumps(document["room_entry_contract"], sort_keys=True)
            != json.dumps(raw["room_entry_contract"], sort_keys=True)
        ):
            raise ValueError("RE2 room-entry proof disagrees with its revision layout")
        # JSON types are part of the proof: Python equality would equate
        # boolean bank/bit operands with integer zero or one.
        if json.dumps(
            document.get("presence_flag_writes"), sort_keys=True
        ) != json.dumps(flag_proof, sort_keys=True):
            raise ValueError("RE2 flag write proof disagrees with its revision layout")
        fixed = document.get("fixed_scenario_flags")
        if (
            type(fixed) is not list
            or any(
                type(test) is not dict
                or test.keys() != {"bank", "bit", "expected"}
                or any(type(test[key]) is not int for key in test)
                for test in fixed
            )
            or fixed != scenario_flags(raw)
        ):
            raise ValueError("RE2 exclusion proof disagrees with fixed scenario flags")
        fixed_values = {(test["bank"], test["bit"]): test["expected"] for test in fixed}
        rooms = {row["id"]: row for row in document["rooms"]}
        unsupported = document.get("unsupported_sources")
        if type(unsupported) is not list or any(
            type(row) is not dict
            or row.keys() != {"id", "path", "size", "sha256", "error"}
            or type(row["id"]) is not str
            or len(row["id"]) != 5
            or row["id"][2] != "-"
            or any(c not in "0123456789abcdef" for c in row["id"][:2] + row["id"][3:])
            or int(row["id"][:2], 16) > 6
            or int(row["id"][3:], 16) > 0x2F
            or type(row["path"]) is not str
            or not row["path"]
            or type(row["size"]) is not int
            or row["size"] <= 0
            or type(row["sha256"]) is not str
            or len(row["sha256"]) != 64
            or any(c not in "0123456789abcdef" for c in row["sha256"])
            or type(row["error"]) is not str
            or not row["error"]
            for row in unsupported
        ):
            raise ValueError("invalid or missing RE2 unsupported source diagnostics")
        unsupported = {row["id"]: row for row in unsupported}
        if (
            len(rooms) + len(unsupported) != target.room_count
            or len(rooms) != len(document["rooms"])
            or len(unsupported) != len(document["unsupported_sources"])
            or rooms.keys() & unsupported.keys()
        ):
            raise ValueError(
                f"RE2 metadata needs {target.room_count} unique room sources"
            )

        supported = raw["presence_condition_flags"]
        condition_flags = frozenset((row["bank"], row["bit"]) for row in supported)

        def valid_presence(presence, allowed_flags):
            if type(presence) is not dict or presence.get("kind") not in (
                "unresolved",
                "required",
                "conditions",
            ):
                return False
            if presence["kind"] in ("unresolved", "required"):
                valid = presence.keys() == {"kind"}
            else:
                clauses = presence.get("any_of")
                valid = (
                    presence.keys() == {"kind", "any_of"}
                    and type(clauses) is list
                    and 1 <= len(clauses) <= 32
                    and all(
                        type(clause) is list
                        and 1 <= len(clause) <= 32
                        and all(
                            type(test) is dict
                            and test.keys() == {"bank", "bit", "expected"}
                            and type(test["bank"]) is int
                            and test["bank"] in banks
                            and type(test["bit"]) is int
                            and 0 <= test["bit"] < banks[test["bank"]][1] * 8
                            and (test["bank"], test["bit"]) in allowed_flags
                            and type(test["expected"]) is int
                            and test["expected"] in (0, 1)
                            for test in clause
                        )
                        and len({(test["bank"], test["bit"]) for test in clause})
                        == len(clause)
                        for clause in clauses
                    )
                )
            return valid

        award_flags, pickup_flags = set(), set()
        context_flags = frozenset(
            (bank, bit)
            for bank, (_, width) in banks.items()
            for bit in range(width * 8)
        )
        for key, room in rooms.items():
            context_conditions = room.get("scenario_context_conditions", [])
            if (
                actor_parts is not ActorPartSupport.Unaudited
                and "scenario_context_conditions" not in room
                or type(context_conditions) is not list
                or any(
                    not valid_presence(condition, context_flags)
                    or condition["kind"] != "conditions"
                    for condition in context_conditions
                )
                or context_conditions
                and not room.get("fixed_context_preserved")
            ):
                raise ValueError("invalid or missing RE2 scenario context conditions")
            declarations = room.get("startup_item_declarations", [])
            declaration_capable = isinstance(
                declaration_config, StartupDeclarationAuditConfig
            )
            if (
                declaration_capable
                and "startup_item_declarations" not in room
                or not declaration_capable
                and "startup_item_declarations" in room
                or type(declarations) is not list
                or len(declarations) > layout["aot_capacity"]
            ):
                raise ValueError("invalid or missing RE2 startup declarations")
            declaration_ids = set()
            for declaration in declarations:
                # This native receipt covers the stage-zero loader only; it
                # cannot authorize declarations in another stage's source arena.
                if (
                    type(declaration) is not dict
                    or declaration.keys()
                    != {"global_id", "item_type", "slot", "creator_offsets"}
                    or type(declaration["global_id"]) is not int
                    or not 0 <= declaration["global_id"] <= 255
                    or declaration["global_id"] in declaration_ids
                    or type(declaration["item_type"]) is not int
                    or not 0 <= declaration["item_type"] < layout["file_type_min"]
                    or type(declaration["slot"]) is not int
                    or not 0 <= declaration["slot"] < layout["aot_capacity"]
                    or type(room.get("stage")) is not int
                    or room["stage"] != 0
                    or type(room.get("size")) is not int
                    or type(room.get("scenario_absent_item_ids")) is not list
                    or declaration["global_id"] in room["scenario_absent_item_ids"]
                    or type(declaration["creator_offsets"]) is not list
                    or not declaration["creator_offsets"]
                    or any(
                        type(offset) is not int or not 0 <= offset <= room["size"] - 22
                        for offset in declaration["creator_offsets"]
                    )
                    or declaration["creator_offsets"]
                    != sorted(set(declaration["creator_offsets"]))
                    or type(room.get("items")) is not list
                    or any(
                        type(item) is not dict
                        or not {"offset", "global_id", "type", "slot"} <= item.keys()
                        or any(
                            type(item[field]) is not int
                            for field in ("offset", "global_id", "type", "slot")
                        )
                        for item in room["items"]
                    )
                ):
                    raise ValueError("invalid RE2 startup declaration")
                creators = [
                    item
                    for item in room["items"]
                    if item["global_id"] == declaration["global_id"]
                ]
                if (
                    not creators
                    or {(item["slot"], item["type"]) for item in creators}
                    != {(declaration["slot"], declaration["item_type"])}
                    or sorted(item["offset"] for item in creators)
                    != declaration["creator_offsets"]
                ):
                    raise ValueError("unbound RE2 startup declaration identity")
                declaration_ids.add(declaration["global_id"])
            puzzle_capable = isinstance(
                entry_contract, RoomEntryContractConfig
            ) and isinstance(dispatch, ScriptItemDispatchConfig)
            reset_variants = room.get("reset_item_variants", [])
            if (
                puzzle_capable
                and "reset_item_variants" not in room
                or not puzzle_capable
                and "reset_item_variants" in room
                or type(reset_variants) is not list
            ):
                raise ValueError("invalid or missing RE2 reset item variants")
            reset_offsets = []
            for variant in reset_variants:
                if (
                    type(variant) is not dict
                    or variant.keys()
                    != {
                        "offset",
                        "creator_offsets",
                        "slot",
                        "type",
                        "amount",
                        "global_id",
                        "sat",
                    }
                    or any(
                        type(variant[field]) is not int
                        for field in (
                            "offset",
                            "slot",
                            "type",
                            "amount",
                            "global_id",
                            "sat",
                        )
                    )
                    or type(room.get("size")) is not int
                    or not 0 <= variant["offset"] <= room["size"] - 10
                    or not 0 <= variant["slot"] < layout["aot_capacity"]
                    or not 0 <= variant["type"] <= 0xFFFF
                    or not 0 <= variant["amount"] <= 0xFFFF
                    or not 0 <= variant["global_id"] < 256
                    or not 0 <= variant["sat"] < 0x80
                    or type(variant["creator_offsets"]) is not list
                    or not variant["creator_offsets"]
                    or any(
                        type(offset) is not int or not 0 <= offset <= room["size"] - 22
                        for offset in variant["creator_offsets"]
                    )
                    or variant["creator_offsets"]
                    != sorted(set(variant["creator_offsets"]))
                    or type(room.get("items")) is not list
                    or any(
                        type(item) is not dict
                        or not {"offset", "slot", "type", "global_id", "four_point"}
                        <= item.keys()
                        or any(
                            type(item[field]) is not int
                            for field in ("offset", "slot", "type", "global_id")
                        )
                        or type(item["four_point"]) is not bool
                        for item in room["items"]
                    )
                ):
                    raise ValueError("invalid RE2 reset item variant")
                creators = [
                    item
                    for item in room["items"]
                    if item["slot"] == variant["slot"]
                    and item["global_id"] == variant["global_id"]
                    and not item["four_point"]
                ]
                if (
                    not creators
                    or sorted(item["offset"] for item in creators)
                    != variant["creator_offsets"]
                    or variant["type"] in {item["type"] for item in creators}
                    or any(
                        offset < variant["offset"] + 10
                        and variant["offset"] < offset + 22
                        for offset in variant["creator_offsets"]
                    )
                ):
                    raise ValueError("unbound RE2 reset item variant")
                reset_offsets.append(variant["offset"])
            if reset_offsets != sorted(set(reset_offsets)) or any(
                first + 10 > second
                for first, second in zip(reset_offsets, reset_offsets[1:])
            ):
                raise ValueError(
                    "duplicate, overlapping or unordered RE2 reset item variants"
                )
            puzzle_items = room.get("known_puzzle_items", [])
            if (
                puzzle_capable
                and "known_puzzle_items" not in room
                or not puzzle_capable
                and "known_puzzle_items" in room
                or type(puzzle_items) is not list
                or len(puzzle_items) > layout["aot_capacity"]
            ):
                raise ValueError("invalid or missing RE2 known puzzle-item proofs")
            puzzle_ids = set()
            for proof in puzzle_items:
                if (
                    type(proof) is not dict
                    or proof.keys()
                    != {
                        "global_id",
                        "item_types",
                        "creator_offsets",
                        "callback_offsets",
                        "delivery_offsets",
                        "context_conditions",
                    }
                    or type(proof["global_id"]) is not int
                    or not 0 <= proof["global_id"] <= 255
                    or proof["global_id"] in puzzle_ids
                    or type(proof["item_types"]) is not list
                    or not proof["item_types"]
                    or any(
                        type(item_type) is not int
                        or not 0 <= item_type < layout["file_type_min"]
                        for item_type in proof["item_types"]
                    )
                    or proof["item_types"] != sorted(set(proof["item_types"]))
                    or type(room.get("stage")) is not int
                    or room["stage"] not in entry_stages
                    or type(room.get("size")) is not int
                    or type(room.get("scenario_absent_item_ids")) is not list
                    or proof["global_id"] in room["scenario_absent_item_ids"]
                    or type(proof["context_conditions"]) is not list
                    or len(proof["context_conditions"]) > 32
                    or any(
                        not valid_presence(condition, context_flags)
                        or condition["kind"] != "conditions"
                        for condition in proof["context_conditions"]
                    )
                    or any(
                        type(proof[field]) is not list
                        or not proof[field]
                        or any(
                            type(offset) is not int
                            or not 0 <= offset <= room["size"] - width
                            for offset in proof[field]
                        )
                        or proof[field] != sorted(set(proof[field]))
                        for field, width in (
                            ("creator_offsets", 22),
                            ("callback_offsets", 20),
                            ("delivery_offsets", 2),
                        )
                    )
                ):
                    raise ValueError("invalid RE2 known puzzle-item proof")
                if type(room.get("items")) is not list or any(
                    type(item) is not dict
                    or not {"offset", "global_id", "type"} <= item.keys()
                    or any(
                        type(item[field]) is not int
                        for field in ("offset", "global_id", "type")
                    )
                    for item in room["items"]
                ):
                    raise ValueError("invalid RE2 known puzzle-item source")
                creators = [
                    item
                    for item in room["items"]
                    if item["global_id"] == proof["global_id"]
                ]
                if (
                    not creators
                    or len({item["type"] for item in creators}) != 1
                    or sorted(
                        {item["type"] for item in creators}
                        | {
                            variant["type"]
                            for variant in reset_variants
                            if variant["global_id"] == proof["global_id"]
                        }
                    )
                    != proof["item_types"]
                    or sorted(item["offset"] for item in creators)
                    != proof["creator_offsets"]
                ):
                    raise ValueError("unbound RE2 known puzzle-item identity")
                puzzle_ids.add(proof["global_id"])
            direct_capable = puzzle_capable and isinstance(
                declaration_config, StartupDeclarationAuditConfig
            )
            direct_pickups = room.get("known_direct_pickups", [])
            if (
                direct_capable
                and "known_direct_pickups" not in room
                or not direct_capable
                and "known_direct_pickups" in room
                or type(direct_pickups) is not list
                or len(direct_pickups) > layout["aot_capacity"]
            ):
                raise ValueError("invalid or missing RE2 known direct-pickup proofs")
            direct_ids = set()
            for proof in direct_pickups:
                if (
                    type(proof) is not dict
                    or proof.keys()
                    != {
                        "global_id",
                        "item_type",
                        "slot",
                        "creator_offsets",
                        "context_conditions",
                    }
                    or type(proof["global_id"]) is not int
                    or not 0 <= proof["global_id"] <= 255
                    or proof["global_id"] in direct_ids | declaration_ids | puzzle_ids
                    or type(proof["item_type"]) is not int
                    or not 0 <= proof["item_type"] < layout["file_type_min"]
                    or type(proof["slot"]) is not int
                    or not 0 <= proof["slot"] < layout["aot_capacity"]
                    or type(room.get("stage")) is not int
                    or room["stage"] != 0
                    or room["stage"] not in entry_stages
                    or type(room.get("size")) is not int
                    or type(room.get("scenario_absent_item_ids")) is not list
                    or proof["global_id"] in room["scenario_absent_item_ids"]
                    or type(proof["creator_offsets"]) is not list
                    or not proof["creator_offsets"]
                    or any(
                        type(offset) is not int or not 0 <= offset <= room["size"] - 22
                        for offset in proof["creator_offsets"]
                    )
                    or proof["creator_offsets"] != sorted(set(proof["creator_offsets"]))
                    or type(proof["context_conditions"]) is not list
                    or len(proof["context_conditions"]) > 32
                    or any(
                        not valid_presence(condition, context_flags)
                        or condition["kind"] != "conditions"
                        for condition in proof["context_conditions"]
                    )
                ):
                    raise ValueError("invalid RE2 known direct-pickup proof")
                # The source/routing receipt qualifies stage zero only. Its
                # exact corpus identity is required even for an empty context.
                if key not in declaration_sources or (
                    room.get("source"),
                    room.get("size"),
                    room.get("sha256"),
                ) != (
                    declaration_sources[key].path,
                    declaration_sources[key].width,
                    declaration_sources[key].sha256,
                ):
                    raise ValueError("unbound RE2 known direct-pickup source")
                if type(room.get("items")) is not list or any(
                    type(item) is not dict
                    or not {"offset", "global_id", "type", "slot", "four_point"}
                    <= item.keys()
                    or any(
                        type(item[field]) is not int
                        for field in ("offset", "global_id", "type", "slot")
                    )
                    or type(item["four_point"]) is not bool
                    for item in room["items"]
                ):
                    raise ValueError("invalid RE2 known direct-pickup source")
                creators = [
                    item
                    for item in room["items"]
                    if item["global_id"] == proof["global_id"]
                ]
                if (
                    not creators
                    or {(item["slot"], item["type"]) for item in creators}
                    != {(proof["slot"], proof["item_type"])}
                    or any(item["four_point"] for item in creators)
                    or sorted(item["offset"] for item in creators)
                    != proof["creator_offsets"]
                ):
                    raise ValueError("unbound RE2 known direct-pickup identity")
                direct_ids.add(proof["global_id"])
            open_doors = room.get("immutable_open_doors", [])
            if (
                isinstance(entry_contract, RoomEntryContractConfig)
                and "immutable_open_doors" not in room
                or not isinstance(entry_contract, RoomEntryContractConfig)
                and "immutable_open_doors" in room
                or type(open_doors) is not list
                or len(open_doors) > layout["aot_capacity"]
            ):
                raise ValueError("invalid or missing RE2 immutable open-door proofs")
            open_slots = set()
            for proof in open_doors:
                if (
                    type(proof) is not dict
                    or proof.keys() != {"slot", "creator_offsets", "context_conditions"}
                    or type(proof["slot"]) is not int
                    or not 0 <= proof["slot"] < layout["aot_capacity"]
                    or proof["slot"] in open_slots
                    or type(proof["creator_offsets"]) is not list
                    or not proof["creator_offsets"]
                    or any(
                        type(offset) is not int for offset in proof["creator_offsets"]
                    )
                    or proof["creator_offsets"] != sorted(set(proof["creator_offsets"]))
                    or type(proof["context_conditions"]) is not list
                    or len(proof["context_conditions"]) > 32
                    or any(
                        not valid_presence(condition, context_flags)
                        or condition["kind"] != "conditions"
                        for condition in proof["context_conditions"]
                    )
                    or not room.get("fixed_context_preserved")
                    or room["stage"] not in entry_stages
                    or any(
                        condition not in proof["context_conditions"]
                        for condition in context_conditions
                    )
                ):
                    raise ValueError("invalid RE2 immutable open-door proof")
                creators = [
                    door for door in room["doors"] if door["slot"] == proof["slot"]
                ]
                if (
                    not creators
                    or sorted(door["offset"] for door in creators)
                    != proof["creator_offsets"]
                    or any(
                        door["lock_id"] != 0
                        or door["lock_type"] != 0
                        or {
                            field: value
                            for field, value in door.items()
                            if field != "offset"
                        }
                        != {
                            field: value
                            for field, value in creators[0].items()
                            if field != "offset"
                        }
                        for door in creators
                    )
                    or any(item["slot"] == proof["slot"] for item in room["items"])
                ):
                    raise ValueError("unbound RE2 immutable open-door proof")
                open_slots.add(proof["slot"])
            relations = room.get("script_item_dispatch_relations", [])
            if (
                dispatch is not ScriptItemDispatchSupport.Unaudited
                and "script_item_dispatch_relations" not in room
                or type(relations) is not list
                or dispatch is ScriptItemDispatchSupport.Unaudited
                and relations
            ):
                raise ValueError(
                    "invalid or missing RE2 script item dispatch relations"
                )
            relation_keys = set()
            for relation in relations:
                if (
                    type(relation) is not dict
                    or relation.keys()
                    != {
                        "item_offset",
                        "callback_offset",
                        "callback_slot",
                        "callback_four_point",
                        "target_slot",
                        "procedure",
                        "table_proof",
                        "program_proof",
                        "message_proofs",
                        "callback_proof",
                    }
                    or any(
                        type(relation[field]) is not int
                        for field in (
                            "item_offset",
                            "callback_offset",
                            "callback_slot",
                            "target_slot",
                            "procedure",
                        )
                    )
                    or type(relation["callback_four_point"]) is not bool
                    or not 0 <= relation["callback_slot"] < layout["aot_capacity"]
                    or not 0 <= relation["target_slot"] < layout["aot_capacity"]
                    or relation["callback_slot"] == relation["target_slot"]
                    or not 0 <= relation["procedure"] <= 255
                    or not 0
                    <= relation["callback_offset"]
                    <= room["size"] - (28 if relation["callback_four_point"] else 20)
                    or not any(
                        item["offset"] == relation["item_offset"]
                        and item["slot"] == relation["target_slot"]
                        for item in room["items"]
                    )
                ):
                    raise ValueError("invalid RE2 script item dispatch relation")
                if (
                    type(relation["message_proofs"]) is not list
                    or len(relation["message_proofs"]) > 64
                ):
                    raise ValueError("invalid RE2 script item dispatch message proofs")
                for proof in (
                    relation["table_proof"],
                    relation["program_proof"],
                    relation["callback_proof"],
                    *relation["message_proofs"],
                ):
                    if (
                        type(proof) is not dict
                        or proof.keys() != {"offset", "width", "sha256"}
                        or type(proof["offset"]) is not int
                        or type(proof["width"]) is not int
                        or not 1 <= proof["width"] <= room["size"]
                        or not 0 <= proof["offset"] <= room["size"] - proof["width"]
                        or type(proof["sha256"]) is not str
                        or len(proof["sha256"]) != 64
                        or any(
                            character not in "0123456789abcdef"
                            for character in proof["sha256"]
                        )
                    ):
                        raise ValueError(
                            "invalid RE2 script item dispatch source proof"
                        )
                if any(
                    proof["width"] > 4096 for proof in relation["message_proofs"]
                ) or len(
                    {
                        (proof["offset"], proof["width"])
                        for proof in relation["message_proofs"]
                    }
                ) != len(relation["message_proofs"]):
                    raise ValueError("invalid RE2 script item dispatch message proofs")
                if (
                    relation["callback_proof"]["offset"]
                    != relation["callback_offset"] + 2
                    or relation["callback_proof"]["width"]
                    != (26 if relation["callback_four_point"] else 18)
                    or relation["table_proof"]["width"] != 2
                    or relation["table_proof"]["offset"]
                    != room["section_offsets"][17] + 2 * relation["procedure"]
                    or relation["program_proof"]["width"] > 4096
                    or relation["program_proof"]["offset"] < room["section_offsets"][17]
                    or not 0
                    <= relation["program_proof"]["offset"] - room["section_offsets"][17]
                    <= 0xFFFF
                    or relation["table_proof"]["sha256"]
                    != hashlib.sha256(
                        (
                            relation["program_proof"]["offset"]
                            - room["section_offsets"][17]
                        ).to_bytes(2, "little")
                    ).hexdigest()
                ):
                    raise ValueError("unbound RE2 script item dispatch source proof")
                identity = relation["item_offset"], relation["callback_offset"]
                if identity in relation_keys:
                    raise ValueError("duplicate RE2 script item dispatch relation")
                relation_keys.add(identity)
            if type(room.get("fixed_context_preserved")) is not bool:
                raise ValueError("invalid or missing RE2 fixed-context presence proof")
            allowed_flags = scenario_presence_flags(
                condition_flags, fixed, room["fixed_context_preserved"]
            )
            bank = (
                layout["item_bank_early"]
                if room["stage"] < layout["item_bank_stage_boundary"]
                else layout["item_bank_late"]
            )
            if (
                "event_awards" not in room
                or "candidate_list_complete" not in room
                or type(room["event_awards"]) is not list
                or type(room["candidate_list_complete"]) is not bool
            ):
                raise ValueError(
                    "RE2 source requires explicit event awards and coverage"
                )
            if any(
                type(award) is not dict
                or not {"offset", "item_type", "amount"} <= award.keys()
                or not all(
                    type(award[field]) is int
                    for field in ("offset", "item_type", "amount")
                )
                or not 0 <= award["offset"] < room["size"]
                or not 0 <= award["item_type"] <= 255
                or not 0 <= award["amount"] <= 255
                for award in room["event_awards"]
            ):
                raise ValueError("invalid RE2 event award metadata")
            if len({award["offset"] for award in room["event_awards"]}) != len(
                room["event_awards"]
            ):
                raise ValueError("duplicate RE2 event award")
            for award in room["event_awards"]:
                collection = award.get("collection")
                if type(collection) is not dict or collection.get("kind") not in (
                    "unresolved",
                    "flag",
                ):
                    raise ValueError(
                        "RE2 event award requires an explicit collection rule"
                    )
                if collection["kind"] == "unresolved":
                    valid = collection == {"kind": "unresolved"}
                else:
                    valid = (
                        collection.keys() == {"kind", "bank", "bit"}
                        and type(collection["bank"]) is int
                        and collection["bank"] == bank
                        and type(collection["bit"]) is int
                        and 0 <= collection["bit"] < banks[bank][1] * 8
                    )
                if not valid:
                    raise ValueError("invalid RE2 event award collection rule")
                if collection["kind"] == "flag":
                    identity = bank, collection["bit"]
                    if identity in award_flags:
                        raise ValueError("aliased RE2 event award collection rule")
                    award_flags.add(identity)
                presence = award.get("presence")
                if not valid_presence(presence, condition_flags) or (
                    presence["kind"] != "unresolved" and collection["kind"] != "flag"
                ):
                    raise ValueError("invalid or unbound RE2 event award presence rule")
            if key != str(RoomId(room["stage"], room["room"])) or not room["proofs"]:
                raise ValueError("invalid RE2 room source identity")
            if (
                not 100 <= room["size"] <= 0x200000
                or len(room["section_offsets"]) != 23
                or any(
                    offset and not 100 <= offset <= room["size"]
                    for offset in room["section_offsets"]
                )
            ):
                raise ValueError("invalid RE2 source section bounds")
            sound = room.get("sound_proofs")
            # Soundless sources require explicit zero pointers and no hashes.
            # They cannot use the paired, hash-checked relocation path.
            if room["section_offsets"][:2] != [0, 0] or sound != []:
                if (
                    type(sound) is not list
                    or len(sound) != 2
                    or any(
                        type(proof) is not dict
                        or proof.keys() != {"section", "width", "sha256"}
                        or type(proof["section"]) is not int
                        or proof["section"] != index
                        or type(proof["width"]) is not int
                        or proof["width"] != width
                        or type(proof["sha256"]) is not str
                        or len(proof["sha256"]) != 64
                        or any(c not in "0123456789abcdef" for c in proof["sha256"])
                        or not 100
                        <= room["section_offsets"][index]
                        <= room["size"] - width
                        for proof, (index, width) in zip(sound, ((0, 192), (1, 32)))
                    )
                    or room["section_offsets"][1] - room["section_offsets"][0] != 192
                ):
                    raise ValueError("invalid or missing RE2 sound source proofs")
            if any(
                not 0 <= item["global_id"] < banks[bank][1] * 8
                for item in room["items"]
            ):
                raise ValueError("RE2 pickup flag outside its bank")
            pickup_flags.update((bank, item["global_id"]) for item in room["items"])
            if "collection_item_ids" not in room:
                raise ValueError(
                    "RE2 source requires explicit collection identity proofs"
                )
            variants = room.get("scenario_item_variants")
            diagnostic = f"RE2 scenario item variants in {key}"
            if type(variants) is not list:
                raise ValueError(f"{diagnostic}: expected a list")
            if variants and not room["candidate_list_complete"]:
                raise ValueError(f"{diagnostic}: source list is incomplete")
            variant_ids = set()
            for rule in variants:
                if (
                    type(rule) is not dict
                    or rule.keys() != {"global_id", "offsets"}
                    or type(rule["global_id"]) is not int
                    or type(rule["offsets"]) is not list
                    or not rule["offsets"]
                    or any(type(offset) is not int for offset in rule["offsets"])
                ):
                    raise ValueError(
                        f"{diagnostic}: expected global_id and nonempty integer offsets"
                    )
                if rule["global_id"] in variant_ids:
                    raise ValueError(f"{diagnostic}: duplicate acquisition ID")
                variant_ids.add(rule["global_id"])
                if rule["offsets"] != sorted(set(rule["offsets"])):
                    raise ValueError(f"{diagnostic}: offsets must be unique and sorted")
                definitions = [
                    item
                    for item in room["items"]
                    if item["global_id"] == rule["global_id"]
                ]
                if len({item["type"] for item in definitions}) <= 1:
                    raise ValueError(
                        f"{diagnostic}: identity must have conflicting catalog types"
                    )
                if not set(rule["offsets"]) <= {item["offset"] for item in definitions}:
                    raise ValueError(
                        f"{diagnostic}: offsets must belong to the acquisition ID"
                    )
                if (
                    len(
                        {
                            item["type"]
                            for item in definitions
                            if item["offset"] in rule["offsets"]
                        }
                    )
                    != 1
                ):
                    raise ValueError(
                        f"{diagnostic}: selected creators must have one type"
                    )
            candidates = scenario_item_candidates(room)
            required = room["collection_item_ids"]
            for item in room["items"]:
                if (
                    "amounts" not in item
                    or type(item["amounts"]) is not list
                    or not item["amounts"]
                    or any(
                        type(amount) is not int or not 0 <= amount <= 0xFFFF
                        for amount in item["amounts"]
                    )
                    or item["amounts"] != sorted(set(item["amounts"]))
                    or item["amount"] not in item["amounts"]
                ):
                    raise ValueError("invalid RE2 source quantity alternatives")
            if (
                type(required) is not list
                or any(type(gid) is not int for gid in required)
                or len(required) != len(set(required))
                or any(
                    len(
                        {
                            item["type"]
                            for item in candidates
                            if item["global_id"] == gid
                        }
                    )
                    != 1
                    for gid in required
                )
            ):
                raise ValueError("invalid RE2 collection identity proof")
            conditional = room.get("conditional_item_presence")
            if (
                type(conditional) is not list
                or any(
                    type(rule) is not dict
                    or rule.keys() != {"global_id", "presence"}
                    or type(rule["global_id"]) is not int
                    or rule["global_id"] in required
                    or len(
                        {
                            item["type"]
                            for item in candidates
                            if item["global_id"] == rule["global_id"]
                        }
                    )
                    != 1
                    or not valid_presence(rule["presence"], allowed_flags)
                    or rule["presence"]["kind"] == "unresolved"
                    for rule in conditional
                )
                or len({rule["global_id"] for rule in conditional}) != len(conditional)
            ):
                raise ValueError("invalid or missing RE2 conditional pickup presence")
            absent = room.get("scenario_absent_item_ids")
            if not room["fixed_context_preserved"] and (absent or variants):
                raise ValueError(
                    "RE2 scenario item proofs require a preserved fixed context"
                )
            if (
                type(absent) is not list
                or bool(absent)
                and not room["candidate_list_complete"]
                or any(
                    type(gid) is not int
                    or gid in required
                    or any(rule["global_id"] == gid for rule in variants)
                    or len(
                        {
                            item["type"]
                            for item in room["items"]
                            if item["global_id"] == gid
                        }
                    )
                    != 1
                    for gid in absent
                )
                or len(set(absent)) != len(absent)
                or any(
                    rule["global_id"] in absent
                    and (
                        rule["presence"]["kind"] == "required"
                        or any(
                            not any(
                                (test["bank"], test["bit"]) in fixed_values
                                and fixed_values[test["bank"], test["bit"]]
                                != test["expected"]
                                for test in clause
                            )
                            for clause in rule["presence"]["any_of"]
                        )
                    )
                    for rule in conditional
                )
            ):
                raise ValueError("invalid or missing RE2 scenario pickup exclusions")
            if room["fixed_context_preserved"] and not room["candidate_list_complete"]:
                raise ValueError(
                    "RE2 fixed-context presence proof needs a complete source"
                )
            if any(
                not 0 <= proof["offset"] <= room["size"] - proof["width"]
                for proof in room["proofs"]
            ):
                raise ValueError("RE2 source proof outside its room")
            if any(
                not 0 <= row["slot"] < layout["aot_capacity"]
                for row in room["items"] + room["doors"]
            ):
                raise ValueError("RE2 interaction outside its registry")
            if any(
                "activation_floor" not in door
                or type(door["activation_floor"]) is not int
                or not 0 <= door["activation_floor"] <= 255
                for door in room["doors"]
            ):
                raise ValueError("invalid RE2 door activation floor")
        if award_flags & pickup_flags:
            raise ValueError("aliased RE2 event award and pickup collection rules")
        return Re2Profile(
            raw["profile_id"],
            target,
            raw["revision"],
            raw["executable_identity"],
            *room_addresses,
            RuntimeSignature(addresses, width, digest),
            layout,
            banks,
            rooms,
            unsupported,
            json.loads((path.parent / raw["names_path"]).read_text()),
            Re2MapLayout.load(
                path.parent / raw["floor_plans_path"],
                raw["profile_id"],
                raw["executable_identity"],
                rooms,
                Re2MapProjection(**raw["map_projection"]),
            ),
            dispatch,
            unit_counts,
        )

    def verify_runtime(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> ItemQuery:
        return self.runtime_signature.verify(read_memory)

    def read_current_room(
        self, read_memory: Callable[[int, int], MemoryResult]
    ) -> RoomQuery:
        values = []
        for address in (self.stage_address, self.room_address):
            result = read_memory(address, 2)
            if not result.ok:
                return RoomQuery(ok=False, error=f"room read failed: {result.error}")
            if len(result.data) != 2:
                return RoomQuery(ok=False, error="room read failed: short reply")
            values.append(int.from_bytes(result.data, "little"))
        if values[0] > 6 or values[1] > 0x2F:
            return RoomQuery(ok=False, error="room identity outside the RE2 room range")
        return RoomQuery(ok=True, room=RoomId(*values))
