"""Generate numeric RE1 floor plans from the owner's pinned SLUS-00551 disc.

Only outlines, labels, door segments and source metadata leave the parser.
Native selector behavior is recorded in RE1-MAP-004; no texture is exported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from build_floor_plan import DoorMarkerPolicy, extract_floor_plan
from build_item_table import _read_file
from extract_psx_file import _find
from list_psx_files import _sector_data

REPO = Path(__file__).resolve().parents[1]
EXE_SHA256 = "0f589fb426fb4a3e067b3251e8ccd5e34df79322fdcc37ebff75aa670ac7fae6"
# Selector order comes from 0x8008EB80, not alphabetical file order.
AREAS = (
    ("mansion1f", "Mansion · 1F"),
    ("mansion2f", "Mansion · 2F"),
    ("mansionb1", "Mansion · B1"),
    ("courtyard1f", "Courtyard · 1F"),
    ("courtyardb1", "Courtyard · B1"),
    ("guardhouse1f", "Guardhouse · 1F"),
    ("guardhouseb1", "Guardhouse · B1"),
    ("laboratoryb1", "Laboratory · B1"),
    ("laboratoryb2", "Laboratory · B2"),
    ("laboratoryb3", "Laboratory · B3"),
    ("laboratoryb4", "Laboratory · B4"),
)


def native_location(stage: int, room: int, camera: int) -> tuple[int, int]:
    """Transcribe 0x800336EC..0x80033A00, before its unrelated menu helpers."""
    stage %= 5
    if stage == 0:
        if room == 7 and 3 <= camera <= 6:
            return 0, 0x1D
        if room == 0x0F and camera in (3, 4):
            return 0, 0x1E
        if room == 0x10 and camera == 0:
            return 2, 0x1E
        return 0, room
    if stage == 1:
        if room == 0x0F and camera in (2, 5):
            return 1, 0x1D
        if room == 0x0C and 4 <= camera <= 7:
            return 0, 0x1F
        return (1 if room < 0x1A else 2), room
    if stage == 2:
        if room == 0x0B and camera in (5, 6):
            return 4, 0x11
        if room == 0x0F and camera == 6:
            return 4, 0x12
        return (3 if room < 6 else 4), room
    if stage == 3:
        return (5 if room < 0x0D else 6), room
    if room == 7 and camera < 4:
        return 9, 0x16
    return (7 if room < 2 else 8 if room < 5 else 9 if room < 0x13 else 10), room


def build_catalog(cue: Path) -> dict:
    match = re.search(r'FILE\s+"([^"]+)"', cue.read_text())
    if match is None:
        raise ValueError("CUE has no image FILE entry")
    with (cue.parent / match[1]).open("rb") as image:
        pvd = _sector_data(image, 16)
        root_lba = struct.unpack_from("<I", pvd, 158)[0]
        root_size = struct.unpack_from("<I", pvd, 166)[0]
        extent, size = _find(image, root_lba, root_size, "SLUS_005.51")
        executable = _read_file(image, extent, size)
        if hashlib.sha256(executable).hexdigest() != EXE_SHA256:
            raise ValueError("Disc executable does not match pinned SLUS-00551")
        base = struct.unpack_from("<I", executable, 0x18)[0]

        def executable_bytes(address, width):
            return executable[address - base + 0x800 : address - base + 0x800 + width]

        file_ids = struct.unpack("<11H", executable_bytes(0x8008EB80, 22))
        plans = []
        for selector, (area, label) in enumerate(AREAS):
            record = struct.unpack(
                "<3I", executable_bytes(0x80091F68 + 12 * file_ids[selector], 12)
            )
            filename = f"PSX/ITEM_M2/MAP{file_ids[selector] - 219:02X}.TIM"
            extent, size = _find(image, root_lba, root_size, filename)
            if (extent, size) != record[:2] or record[2] != 4096:
                raise ValueError(f"Native map record disagrees with {filename}")
            data = _read_file(image, extent, size)
            plan = extract_floor_plan(data, DoorMarkerPolicy.FullAndBoundaryMarkers)
            plan.update(id=area, name=label, selector=selector, unoutlined_rooms=[])
            plan["source"] = {
                "file": filename,
                "lba": extent,
                "size": size,
                "sha256": hashlib.sha256(data).hexdigest(),
                "file_id": file_ids[selector],
            }
            for region in plan["rooms"]:
                region["room_ids"] = []
            plans.append(plan)

    # Names are user-provided reference labels, not evidence for room identity.
    text = (REPO / "docs/re1_ram_map_user_provided.md").read_text()
    groups = re.findall(
        r"  - (?:Mansion 1F|Mansion 2F|Courtyard/Underground|Guardhouse|Laboratory): (.*?)(?=\n  - |\n- )",
        text,
        re.DOTALL,
    )
    names = {
        (stage, int(sub, 16)): label.strip()
        for stage, group in enumerate(groups)
        for sub, label in re.findall(
            r"0x([0-9A-Fa-f]+) ([^,]+)(?:,|$)", group.replace("\n", " ")
        )
    }
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    source_rooms = sorted(
        {(row["room_main"], row["room_sub"]) for row in manifest["rooms"]}
    )
    locations = []
    normalized = sorted({(stage % 5, room) for stage, room in source_rooms})
    for stage, room in normalized:
        selector, region = native_location(stage, room, 255)
        location = {"area": AREAS[selector][0], "region": f"{region:02X}"}
        overrides = []
        for camera in range(255):
            other_selector, other_region = native_location(stage, room, camera)
            other = {"area": AREAS[other_selector][0], "region": f"{other_region:02X}"}
            if other != location:
                previous = next(
                    (rule for rule in overrides if rule["location"] == other), None
                )
                if previous is None:
                    overrides.append({"cameras": [camera], "location": other})
                else:
                    previous["cameras"].append(camera)
        locations.append(
            {
                "stage": stage,
                "room": room,
                "default": location,
                "camera_overrides": overrides,
            }
        )
        for selected in [location, *(rule["location"] for rule in overrides)]:
            plan = next(plan for plan in plans if plan["id"] == selected["area"])
            matching = next(
                (entry for entry in plan["rooms"] if entry["id"] == selected["region"]),
                None,
            )
            if matching is None:
                # The native map has no colored polygon for elevators/heliport.
                # Retain the selector and describe that omission explicitly.
                matching = next(
                    (
                        entry
                        for entry in plan["unoutlined_rooms"]
                        if entry["id"] == selected["region"]
                    ),
                    None,
                )
                if matching is None:
                    matching = {"id": selected["region"], "room_ids": []}
                    plan["unoutlined_rooms"].append(matching)
            matching["name"] = names.get((stage, room), f"Room {stage:02X}-{room:02X}")
            matching["room_ids"].extend(
                f"{main:02x}-{sub:02x}"
                for main, sub in source_rooms
                if main % 5 == stage and sub == room
            )
    for plan in plans:
        for entry in plan["rooms"] + plan["unoutlined_rooms"]:
            entry["room_ids"] = sorted(set(entry["room_ids"]))
            if "name" not in entry:
                entry["name"] = f"Room {entry['id']}"

    return {
        "schema": 1,
        "profile_id": "re1_directors_cut_slus00551",
        "executable_identity": f"SLUS_005.51 SHA256 {EXE_SHA256}",
        "authored": "2026-10-07; Codex root; Model: GPT-6.1 Sol",
        "research_ids": ["RE1-MAP-002", "RE1-MAP-004", "RE1-MAP-005"],
        "validation": "Candidate; native selector and numeric encoding checked statically; later-area gameplay unvalidated",
        "stage_modulus": 5,
        "locations": locations,
        "areas": plans,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    try:
        catalog = build_catalog(args.cue)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    args.output.write_text(json.dumps(catalog, indent=2) + "\n")
    print(
        f"areas={len(catalog['areas'])} regions={sum(len(plan['rooms']) for plan in catalog['areas'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
