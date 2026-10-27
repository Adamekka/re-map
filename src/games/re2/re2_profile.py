"""Pinned RE2 identities, bounded memory layouts and required metadata."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from games.game_profile import ItemQuery, RoomId, RoomQuery
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.map_layout import Re2MapLayout, Re2MapProjection
from games.re2.scenario_items import (
    scenario_flags,
    scenario_item_candidates,
    scenario_presence_flags,
    scenario_effect_pool,
    scenario_vibration_writes,
)
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

    @staticmethod
    def load(path: Path) -> Re2Profile:
        raw = json.loads(path.read_text())
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
        if json.dumps(
            document.get("scenario_vibration_writes", []), sort_keys=True
        ) != json.dumps(raw.get("scenario_vibration_writes", []), sort_keys=True):
            raise ValueError("RE2 vibration proof disagrees with its revision layout")
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
        for key, room in rooms.items():
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
