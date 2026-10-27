"""Generate numeric RE2 metadata from the pinned owned CUE. No artwork is exported.

Generation needs Unicorn (pip package `unicorn`) to execute the two bounded
native map selectors. The running tracker uses only the generated JSON.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_item_table import _read_file
from extract_psx_file import _find
from list_psx_files import _read_dir, _sector_data
from map_geometry import trace_floor_cells

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.map_layout import Re2MapProjection
from games.re2.room_data import bind_event_awards, collection_presence, decode_room
from games.re2.re2_profile import re2_target
from games.re2.scenario_items import (
    scenario_flags,
    scenario_item_candidates,
    scenario_item_proofs,
    scenario_presence_flags,
    scenario_effect_pool,
)

AREA_NAMES = (
    "City streets west",
    "City streets east",
    "Police station 1F",
    "Police station 2F",
    "Police station 3F",
    "Police station B1",
    "Sewer entrance",
    "Sewers upper level",
    "Sewers lower level",
    "Factory 1F",
    "Factory B1",
    "Factory B2",
    "Factory B3",
    "Laboratory B1",
    "Laboratory B2",
    "Laboratory elevator",
    "Laboratory B3",
    "Laboratory B4",
    "Escape platform",
    "Escape train",
)


def build(cue: Path, profile: dict, names: dict) -> tuple[dict, dict]:
    target = re2_target(profile)
    effect_pool = scenario_effect_pool(profile)
    projection = Re2MapProjection(**profile["map_projection"])
    fixed_flags = scenario_flags(profile)
    condition_flags = frozenset(
        (row["bank"], row["bit"]) for row in profile["presence_condition_flags"]
    )
    counters = presence_counter_indices(profile)
    writes, flag_proof = presence_flag_write_proof(profile)
    from unicorn import UC_ARCH_MIPS, UC_MODE_LITTLE_ENDIAN, UC_MODE_MIPS32, Uc
    from unicorn.mips_const import (
        UC_MIPS_REG_A0,
        UC_MIPS_REG_A1,
        UC_MIPS_REG_PC,
        UC_MIPS_REG_RA,
        UC_MIPS_REG_SP,
        UC_MIPS_REG_V0,
    )

    match = re.search(r'FILE\s+"([^"]+)"', cue.read_text())
    if match is None:
        raise ValueError("CUE lacks its data track")
    with (cue.parent / match[1]).open("rb") as stream:
        pvd = _sector_data(stream, 16)
        if pvd[:7] != b"\x01CD001\x01":
            raise ValueError("data track lacks an ISO9660 primary volume")
        root = struct.unpack_from("<I", pvd, 158)[0]
        root_size = struct.unpack_from("<I", pvd, 166)[0]
        extent, size = _find(stream, root, root_size, target.executable_name)
        executable = _read_file(stream, extent, size)
        identity = (
            target.executable_name + " SHA256 " + hashlib.sha256(executable).hexdigest()
        )
        if identity != profile["executable_identity"]:
            raise ValueError("disc executable does not match the RE2 profile")
        load = struct.unpack_from("<I", executable, 0x18)[0]
        table = int(flag_proof["bank_table_address_ps1"], 0)
        for bank in flag_proof["flag_banks"]:
            offset = 0x800 + table + bank["bank"] * 4 - load
            if not 0x800 <= offset <= len(executable) - 4 or struct.unpack_from(
                "<I", executable, offset
            )[0] != int(bank["address_ps1"], 0):
                raise ValueError("RE2 flag proof disagrees with the native bank table")
        extent, size = _find(stream, root, root_size, "COMMON/DATA/MAPS.PIX")
        pixels = _read_file(stream, extent, size)
        if len(pixels) != 20 * 32768:
            raise ValueError("unsupported RE2 map pixel layout")
        directory, directory_size = root, root_size
        source_directory = f"PL{target.player_index}/RDT"
        for component in source_directory.split("/"):
            row = next(
                (
                    row
                    for row in _read_dir(stream, directory, directory_size)
                    if row[0] == component and row[3]
                ),
                None,
            )
            if row is None:
                raise ValueError(f"disc lacks {target.label} room data")
            directory, directory_size = row[1:3]
        rooms, sources, unsupported = [], {}, []
        for name, extent, size, is_directory in _read_dir(
            stream, directory, directory_size
        ):
            if is_directory:
                continue
            if target.excluded_room_stages and re.fullmatch(
                rf"ROOM[{target.excluded_room_stages}][0-9A-F]{{2}}{target.player_index}\.RDT",
                name,
            ):
                # DualShock has a second room corpus. This profile reads only
                # the numbered sources used by Original mode.
                continue
            match = re.fullmatch(
                rf"ROOM([1-7])([0-9A-F]{{2}}){target.player_index}\.RDT", name
            )
            if match is None:
                raise ValueError(f"unexpected {target.label} room source {name}")
            data = _read_file(stream, extent, size)
            stage, number = int(match[1]) - 1, int(match[2], 16)
            try:
                room = decode_room(
                    data,
                    source_directory + "/" + name,
                    condition_flags,
                    counters,
                    writes,
                )
            except ValueError as error:
                # Keep an unreadable source explicit. Inventing empty item data
                # here would let a later visit incorrectly clear that room.
                unsupported.append(
                    {
                        "id": f"{stage:02d}-{number:02x}",
                        "path": source_directory + "/" + name,
                        "size": len(data),
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "error": str(error),
                    }
                )
                continue
            # Fill this field after the corpus check without reordering JSON keys.
            room["event_awards"] = []
            room.update(stage=int(match[1]) - 1, room=int(match[2], 16))
            room["id"] = f"{room['stage']:02d}-{room['room']:02x}"
            rooms.append(room)
            sources[room["id"]] = data
    if len(rooms) + len(unsupported) != target.room_count:
        raise ValueError(
            f"pinned {target.label} disc must contain {target.room_count} room sources"
        )
    layout = profile["runtime_layout"]
    awards = bind_event_awards(
        rooms,
        sources,
        {
            room["stage"]: layout["item_bank_early"]
            if room["stage"] < layout["item_bank_stage_boundary"]
            else layout["item_bank_late"]
            for room in rooms
        },
        condition_flags,
    )
    for room in rooms:
        room["event_awards"] = awards[room["id"]]
        proof = scenario_item_proofs(
            sources[room["id"]], room, fixed_flags, profile["flag_banks"], effect_pool
        )
        room["fixed_context_preserved"] = proof.fixed_context_preserved
        room["scenario_absent_item_ids"] = proof.absent_item_ids
        room["scenario_item_variants"] = proof.item_variants
        if proof.fixed_context_preserved:
            room["collection_item_ids"], room["conditional_item_presence"] = (
                collection_presence(
                    sources[room["id"]],
                    room,
                    scenario_presence_flags(condition_flags, fixed_flags, True),
                    frozenset(
                        item["offset"] for item in scenario_item_candidates(room)
                    ),
                    fixed_flags=frozenset(
                        (row["bank"], row["bit"], row["expected"])
                        for row in fixed_flags
                    ),
                )
            )
        del room["programs"]
    machine = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
    machine.mem_map(0, 0x200000)
    load = struct.unpack_from("<I", executable, 0x18)[0]
    machine.mem_write(load & 0x1FFFFF, executable[0x800:])
    # The executable starts in A's context even when generating a B profile.
    # Native map selectors read these flags as well as room/floor inputs.
    bank_addresses = {
        row["bank"]: int(row["address_ps1"], 0) for row in profile["flag_banks"]
    }
    for flag in fixed_flags:
        address = (bank_addresses[flag["bank"]] + flag["bit"] // 32 * 4) & 0x1FFFFF
        mask = 0x80000000 >> (flag["bit"] % 32)
        word = int.from_bytes(machine.mem_read(address, 4), "little")
        word = word & ~mask | (mask if flag["expected"] else 0)
        machine.mem_write(address, word.to_bytes(4, "little"))
    layout = profile["metadata_layout"]

    def native(address: int, first: int, second: int) -> int:
        machine.reg_write(UC_MIPS_REG_SP, 0x801FF000)
        machine.reg_write(UC_MIPS_REG_RA, 0x801F0000)
        machine.reg_write(UC_MIPS_REG_A0, first)
        machine.reg_write(UC_MIPS_REG_A1, second)
        machine.emu_start(address, 0x801F0000, count=10000)
        if machine.reg_read(UC_MIPS_REG_PC) != 0x801F0000:
            raise ValueError("native RE2 map selector exceeded its bound")
        return machine.reg_read(UC_MIPS_REG_V0)

    plans = []
    anchors = {}
    for area in range(20):
        table = int(layout["map_info_address_ps1"], 0) - load + 0x800 + area * 8
        address, count, _page, file_number = struct.unpack_from(
            "<IBBH", executable, table
        )
        if not 1 <= count <= 32 or not 0 <= file_number < 20:
            raise ValueError("invalid native RE2 map descriptor")
        plan = {
            "id": f"re2-{area:02d}",
            "name": AREA_NAMES[area],
            "rooms": [],
            "unoutlined_rooms": [],
            "doors": [],
        }
        for region in range(count):
            descriptor = struct.unpack_from(
                "<4B4h4B", executable, address - load + 0x800 + region * 16
            )
            u, v, width, height, x, y, bx, by, *_ = descriptor
            if not width or not height:
                raise ValueError("invalid native RE2 map rectangle")
            cells, interior = set(), set()
            for dy in range(height):
                for dx in range(width):
                    # PS1 texture coordinates wrap at the 256-pixel page edge.
                    index = ((v + dy) % 256) * 256 + (u + dx) % 256
                    value = (
                        pixels[file_number * 32768 + index // 2] >> (4 * (index % 2))
                    ) & 15
                    if value:
                        cells.add((x + dx, y + dy))
                    if value == 2:
                        interior.add((x + dx, y + dy))
            rings, label = trace_floor_cells(cells)
            details = []
            for axis in (0, 1):
                points = sorted(
                    (point[1 - axis], point[axis])
                    for point in interior
                    if all(
                        other in cells
                        for other in (
                            (point[0] - 1, point[1]),
                            (point[0] + 1, point[1]),
                            (point[0], point[1] - 1),
                            (point[0], point[1] + 1),
                        )
                    )
                )
                for fixed, group in itertools.groupby(
                    points, key=lambda point: point[0]
                ):
                    runs = []
                    for _, coordinate in group:
                        if runs and coordinate == runs[-1][-1] + 1:
                            runs[-1].append(coordinate)
                        else:
                            runs.append([coordinate])
                    for run in runs:
                        if len(run) >= 2:
                            segment = [
                                [run[0] + 0.5, fixed + 0.5],
                                [run[-1] + 0.5, fixed + 0.5],
                            ]
                            details.append(
                                segment
                                if axis == 0
                                else [point[::-1] for point in segment]
                            )
            entry = {
                "id": f"{region:02X}",
                "name": "",
                "room_ids": [],
                "rings": [ring for _, ring in rings],
                "ring_roles": [
                    "outer" if signed > 0 else "hole" for signed, _ in rings
                ],
                "label": [value + 0.5 for value in label],
                "detail_segments": details,
                "world_origin": [bx, by],
            }
            plan["rooms"].append(entry)
            anchors[area, region] = (bx, by)
        plans.append(plan)
    locations = []
    area_selector = int(layout["area_selector_ps1"], 0)
    region_selector = int(layout["region_selector_ps1"], 0)
    for room in rooms:
        stage, number = room["stage"], room["room"]
        # These are the data dependencies read by the pinned selector, not a
        # port of its branch logic. Generate each supported alternative natively.
        dependencies = [
            field
            for context in layout["selector_contexts"]
            if room["id"] in context["rooms"]
            for field in context["fields"]
        ]
        for values in itertools.product(*(field["samples"] for field in dependencies)):
            old_tests = []
            for field, (value, expected, negate) in zip(dependencies, values):
                address, mask = int(field["address_ps1"], 0), field["mask"]
                machine.mem_write(
                    address & 0x1FFFFF,
                    value.to_bytes((mask.bit_length() + 7) // 8, "little"),
                )
                old_tests.append([address, mask, expected, negate])
            outcomes = []
            for floor in range(256):
                machine.mem_write(
                    int(layout["floor_address_ps1"], 0) & 0x1FFFFF, bytes([floor])
                )
                area = native(area_selector, stage, number)
                region = native(region_selector, area, number)
                outcomes.append((area, region))
            for (area, region), group in itertools.groupby(
                enumerate(outcomes), key=lambda entry: entry[1]
            ):
                floors = [entry[0] for entry in group]
                if area >= len(plans) or region >= len(plans[area]["rooms"]):
                    # The disc includes unreachable/debug room files. Keep
                    # their missing native outline explicit in the catalog.
                    locations.append(
                        {
                            "room": room["id"],
                            "floor_min": floors[0],
                            "floor_max": floors[-1],
                            "conditions": old_tests,
                            "area": "unmapped",
                            "region": room["id"],
                        }
                    )
                    continue
                locations.append(
                    {
                        "room": room["id"],
                        "floor_min": floors[0],
                        "floor_max": floors[-1],
                        "conditions": old_tests,
                        "area": plans[area]["id"],
                        "region": f"{region:02X}",
                    }
                )
                entry = plans[area]["rooms"][region]
                if room["id"] not in entry["room_ids"]:
                    entry["room_ids"].append(room["id"])
                    if not entry["name"]:
                        entry["name"] = names["rooms"].get(
                            room["id"], "Room " + room["id"]
                        )
    for plan in plans:
        # Extra native shapes can belong exclusively to another character or an unsupported
        # scenario. They stay outside this profile's revealable geometry.
        plan["rooms"] = [entry for entry in plan["rooms"] if entry["room_ids"]]
        for entry in plan["rooms"]:
            for room in rooms:
                if room["id"] not in entry["room_ids"]:
                    continue
                for door in room["doors"]:
                    # The trigger floor belongs to this side of the door. Its
                    # destination floor can select a different outlined region.
                    # Bit 7 bypasses the native floor comparison on every floor.
                    if not door["activation_floor"] & 0x80 and not any(
                        location["room"] == room["id"]
                        and location["area"] == plan["id"]
                        and location["region"] == entry["id"]
                        and location["floor_min"]
                        <= door["activation_floor"]
                        <= location["floor_max"]
                        for location in locations
                    ):
                        continue
                    wx, wz = door["center"]
                    # The native marker maps world X/Z using this translation
                    # and scale (RE2-MAP-001), before adding the room's origin.
                    x, y = projection.project(tuple(entry["world_origin"]), wx, wz)
                    candidates = []
                    for ring in entry["rings"]:
                        for first, last in zip(ring, ring[1:] + ring[:1]):
                            dx, dy = last[0] - first[0], last[1] - first[1]
                            length = (dx * dx + dy * dy) ** 0.5
                            if length < 2:
                                continue
                            along = max(
                                0,
                                min(
                                    length,
                                    ((x - first[0]) * dx + (y - first[1]) * dy)
                                    / length,
                                ),
                            )
                            px, py = (
                                first[0] + along * dx / length,
                                first[1] + along * dy / length,
                            )
                            distance = (px - x) ** 2 + (py - y) ** 2
                            midpoint = max(1, min(length - 1, along))
                            segment = [
                                [
                                    round(
                                        first[0] + (midpoint + shift) * dx / length, 3
                                    ),
                                    round(
                                        first[1] + (midpoint + shift) * dy / length, 3
                                    ),
                                ]
                                for shift in (-1, 1)
                            ]
                            candidates.append((distance, segment))
                    candidates.sort(key=lambda candidate: candidate[0])
                    if not candidates or candidates[0][0] > 64:
                        continue
                    if (
                        len(candidates) > 1
                        and abs(candidates[0][0] - candidates[1][0]) < 1e-8
                        and candidates[0][1] != candidates[1][1]
                    ):
                        # A corner does not establish which wall owns the door.
                        continue
                    observation_id = f"{room['id']}:{door['offset']}"
                    plan["doors"].append(
                        {
                            "id": observation_id + ":" + entry["id"],
                            "observation_id": observation_id,
                            "rooms": [entry["id"]],
                            "segment": candidates[0][1],
                        }
                    )
    header = {
        "schema": 1,
        "profile_id": profile["profile_id"],
        "executable_identity": identity,
        "research_ids": ["RE2-SCD-001", "RE2-MAP-001", "RE2-MAP-002"],
        "validation": "Candidate; runtime coverage is listed in docs/research.md",
    }
    return (
        {
            **header,
            "research_ids": [
                *header["research_ids"],
                "RE2-COLLECT-001",
                "RE2-COLLECT-002",
                "RE2-COLLECT-003",
                "RE2-COLLECT-004",
                "RE2-COLLECT-005",
                "RE2-COLLECT-006",
                "RE2-COLLECT-007",
                "RE2-COLLECT-008",
                "RE2-COLLECT-011",
                "RE2-COLLECT-012",
                "RE2-COLLECT-013",
                "RE2-COLLECT-014",
                "RE2-COLLECT-015",
                "RE2-COLLECT-016",
                "RE2-COLLECT-017",
                "RE2-COLLECT-018",
                "RE2-COLLECT-019",
                "RE2-COLLECT-020",
                "RE2-SOURCE-001",
                "RE2-SCD-002",
            ],
            "fixed_scenario_flags": fixed_flags,
            "scenario_effect_pool": profile["scenario_effect_pool"],
            "unsupported_sources": unsupported,
            "presence_counter_writes": profile["presence_counter_writes"],
            "presence_flag_writes": flag_proof,
            "rooms": rooms,
        },
        {**header, "stage_modulus": 256, "areas": plans, "locations": locations},
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("room_output", type=Path)
    parser.add_argument("map_output", type=Path)
    parser.add_argument(
        "--profile", type=Path, default=ROOT / "profiles/re2_leon_a_slus00421.json"
    )
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text())
        names = json.loads((ROOT / "data/re2_names.json").read_text())
        rooms, maps = build(args.cue, profile, names)
        if rooms["unsupported_sources"]:
            print(
                f"RE2 metadata has {len(rooms['unsupported_sources'])} unsupported room source(s); "
                "their diagnostics are recorded and live tracking will reject them.",
                file=sys.stderr,
            )
        for path, document in ((args.room_output, rooms), (args.map_output, maps)):
            path.write_text(json.dumps(document, indent=2) + "\n")
    except (OSError, ValueError, ImportError, KeyError, struct.error) as error:
        parser.exit(1, f"Cannot generate RE2 metadata: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
