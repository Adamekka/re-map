"""SLUS-00421 Leon A identity, bounded memory layout and required metadata."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from games.game_profile import ItemQuery, RoomId, RoomQuery
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.map_layout import Re2MapLayout, Re2MapProjection
from games.re2.scenario_items import scenario_flags
from games.runtime_identity import MemoryResult, RuntimeSignature


@dataclass(frozen=True)
class Re2Profile:
    profile_id: str
    revision: str
    executable_identity: str
    stage_address: int
    room_address: int
    camera_address: int
    runtime_signature: RuntimeSignature
    runtime_layout: dict
    flag_banks: dict[int, tuple[int, int]]
    rooms: dict[str, dict]
    names: dict
    map_layout: Re2MapLayout

    @staticmethod
    def load(path: Path) -> Re2Profile:
        raw = json.loads(path.read_text())
        if (
            raw["profile_id"] != "re2_leon_a_slus00421"
            or raw["serial"] != "SLUS-00421"
            or raw["scenario"] != "leon-a"
            or raw["address_space"] != "PS1 virtual address, little-endian"
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
        if len(rooms) != 125 or len(rooms) != len(document["rooms"]):
            raise ValueError("RE2 metadata needs 125 unique room sources")

        supported = raw["presence_condition_flags"]
        condition_flags = frozenset((row["bank"], row["bit"]) for row in supported)

        def valid_presence(presence):
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
                            and (test["bank"], test["bit"]) in condition_flags
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
                if not valid_presence(presence) or (
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
                            for item in room["items"]
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
                            for item in room["items"]
                            if item["global_id"] == rule["global_id"]
                        }
                    )
                    != 1
                    or not valid_presence(rule["presence"])
                    or rule["presence"]["kind"] == "unresolved"
                    for rule in conditional
                )
                or len({rule["global_id"] for rule in conditional}) != len(conditional)
            ):
                raise ValueError("invalid or missing RE2 conditional pickup presence")
            absent = room.get("scenario_absent_item_ids")
            if (
                type(absent) is not list
                or bool(absent)
                and not room["candidate_list_complete"]
                or any(
                    type(gid) is not int
                    or gid in required
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
            raw["revision"],
            raw["executable_identity"],
            *room_addresses,
            RuntimeSignature(addresses, width, digest),
            layout,
            banks,
            rooms,
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
