"""Build source signatures, tracking rules and loader choices for SLUS-00551.

Usage: python3 tools/build_cache_metadata.py CUE OUT.JSON PROFILE.JSON
Only semantic operands, hashes, offsets, flag masks and diagnostics are written.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
from pathlib import Path

from build_item_table import _iter_files, _read_file
from build_source_choices import build_source_choices
from build_tracking_program import build_tracking_program
from list_psx_files import _sector_data
from scan_events import scan_event_program
from scan_scd import walk_procedures


def scan_cache_rdt(data: bytes, source_rdt: str, profile: dict) -> dict:
    """Capture item-manifest guards and audit door reuse separately."""
    bases = [int(value, 0) for value in profile["script_flag_bases"]]
    if len(bases) != 10 or any(base % 4 for base in bases):
        raise ValueError("script_flag_bases must contain ten aligned PS1 addresses")
    match = re.fullmatch(
        r"ROOM([1-9A-E])([0-9A-F]{2})([01])\.RDT", Path(source_rdt).name
    )
    if match is None:
        raise ValueError(f"not a RE1 RDT filename: {source_rdt}")
    offsets = struct.unpack_from("<19I", data, 0x48)
    row = {
        # RE1-STAGE-001: sparse STAGE8-E files overlay the corresponding base Main.
        "room_main": (int(match[1], 16) - 1) % 7,
        "room_sub": int(match[2], 16),
        "source_rdt": source_rdt,
        "variant": int(match[3]),
        "source_sha256": hashlib.sha256(data).hexdigest(),
    }
    dependencies: dict[int, int] = {}
    for dependency in profile["cache_context_dependencies"]:
        address = int(dependency["address_ps1"], 0)
        width = dependency["width"]
        mask = int(dependency["mask"], 0)
        if width not in (1, 2, 4) or not 0 < mask < 1 << (8 * width):
            raise ValueError("cache context dependency has invalid width or mask")
        for index in range(width):
            byte_mask = (mask >> (8 * index)) & 255
            if byte_mask:
                dependencies[address + index] = (
                    dependencies.get(address + index, 0) | byte_mask
                )

    operations = []
    issues = []
    source_issues = []
    stats = {}
    flag_tests = []
    for index, section in ((6, "init"), (7, "main")):
        start, end = offsets[index : index + 2]
        if not 0 < start < end <= len(data):
            source_issues.append(f"{section}: bad range")
            stats[section] = "bad-range"
            continue
        span = data[start:end]
        row.update(
            {
                section + "_offset": start,
                section + "_size": len(span),
                section + "_sha256": hashlib.sha256(span).hexdigest(),
            }
        )
        found, status = walk_procedures(span, start)
        operations.extend((section, address, op, raw) for address, op, raw in found)
        stats[section] = status
        if status != "clean":
            source_issues.append(f"{section}: {status}")

    event_start, event_end = offsets[8:10]
    if 0 < event_start < event_end <= len(data):
        row.update(
            events_offset=event_start,
            events_size=event_end - event_start,
            events_sha256=hashlib.sha256(data[event_start:event_end]).hexdigest(),
        )
    event_scan = scan_event_program(data, event_start, event_end)
    found, status = event_scan.operations, event_scan.status
    operations.extend(("events", address, op, raw) for address, op, raw in found)
    stats["events"] = status
    if status != "clean":
        source_issues.append(f"indexed event scripts: {status}")
    event_count = 0
    if 0 < event_start < event_end <= len(data):
        for address in range(event_start, event_end - 3, 4):
            if struct.unpack_from("<I", data, address)[0] == 0:
                break
            event_count += 1
    for _, address, op, raw in operations:
        if op == 0x14 and raw[3] >= event_count:
            source_issues.append(f"event creation index outside table at 0x{address:x}")
    issues.extend(source_issues)
    door_issues = list(source_issues)
    item_ids = {
        raw[1] & 127
        for _, _, op, raw in operations
        if op == 0x18 and 0 < raw[10] < 0x54
    }
    writers = [
        (section, address)
        for section, address, op, raw in operations
        if op == 0x18
        and raw[1] & 127 in item_ids
        or op in (0x0C, 0x0D, 0x12, 0x13)
        and raw[1] in item_ids
    ]
    direct_writers = tuple(writers)
    door_ids = {
        raw[1]
        for _, _, op, raw in operations
        if op == 0x0C or op == 0x0D and raw[10] == 1
    }
    door_writers = [
        (section, address)
        for section, address, op, raw in operations
        if op in (0x0C, 0x0D, 0x12, 0x13)
        and raw[1] in door_ids
        or op in (0x24, 0x2D)
        and raw[1] in door_ids
        or op == 0x4C
        and raw[2] in door_ids
    ]
    if any(section == "events" for section, _ in writers):
        # Starting an event can enable a later manifest write. Its creation guard belongs to the dependency set too.
        writers.extend(
            (section, address) for section, address, op, _ in operations if op == 0x14
        )
    for section, address in door_writers:
        if section != "init":
            door_issues.append(f"door interaction update outside init at 0x{address:x}")
    predicates = {4, 6, 7, 0x10, 0x11, 0x1A, 0x1D, 0x22, 0x36, 0x38, 0x3C, 0x3F, 0x50}
    guarded = set()
    door_guarded = set()
    guarded_writes = set()
    # Room-local tests only invalidate item knowledge when they guard an item manifest writer.
    # Other tests can animate a camera, NPC, or door without changing an observed item list.
    by_address = {address: (op, raw) for _, address, op, raw in operations}
    branches = []
    for section, begin, op, raw in operations:
        if op != 1:
            continue
        false_target = begin + 2 + raw[1]
        finish = false_target
        alternate = by_address.get(false_target - 2)
        if alternate is not None and alternate[0] == 2:
            finish = false_target - 2 + alternate[1][1]
        branches.append((section, begin, false_target, finish))

    predicate_limits = {}
    unbounded_predicates = set()
    for section, address, op, _ in operations:
        if op not in predicates:
            continue
        active = [
            (begin, finish)
            for branch_section, begin, false_target, finish in branches
            if branch_section == section and begin < address < false_target
        ]
        if active:
            # RE1-CACHE-003: failure pops the innermost IF. Its condition can select either
            # arm, but cannot skip a later sibling after both arms have ended.
            # ELSE has already popped that IF, so its tests use the parent.
            begin, finish = max(active)
            if not any(
                operation_section == section
                and begin < operation_address < finish
                and operation == 0
                for operation_section, operation_address, operation, _ in operations
            ):
                predicate_limits[address] = finish
            else:
                unbounded_predicates.add(address)
            # A reachable procedure end prevents reconvergence. Its branch
            # conditions can still decide whether a later sibling runs.
        elif any(
            branch_section == section and false_target <= address < finish
            for branch_section, _, false_target, finish in branches
        ):
            # An ELSE test without a parent IF ends the procedure on failure.
            # Keep it relevant to later source writes; flat event output does
            # not prove which procedure bounds would safely narrow that extent.
            unbounded_predicates.add(address)
        # Without an active IF, retain the conservative existing branch audit;
        # no captured stack owner proves a narrower predicate extent.

    for targets, destination in ((writers, guarded), (door_writers, door_guarded)):
        pending = list(targets)
        inspected = set()
        while pending:
            section, target = pending.pop()
            if (section, target) in inspected:
                continue
            inspected.add((section, target))
            containing = [
                begin
                for branch_section, begin, _, finish in branches
                if branch_section == section and begin < target < finish
            ]
            for predicate_section, address, op, _ in operations:
                if (
                    predicate_section != section
                    or op not in predicates
                    or address >= target
                    or address not in unbounded_predicates
                    and not any(begin < address for begin in containing)
                    or address in predicate_limits
                    and target >= predicate_limits[address]
                ):
                    continue
                if (
                    destination is guarded
                    and (section, target) in direct_writers
                    and any(begin < address for begin in containing)
                ):
                    # A conservative lifetime alone does not prove that an
                    # asynchronous item write has a captured initialization guard.
                    guarded_writes.add((section, target))
                destination.add(address)
                # A nested condition can choose whether another relevant
                # condition runs, including an ELSE test that exits its parent.
                pending.append((section, address))
    for section, address in direct_writers:
        # A mutation without a captured guard could change a departed room's manifest while context stayed equal.
        if section != "init" and (section, address) not in guarded_writes:
            issues.append(
                f"unguarded item interaction update outside init at 0x{address:x}"
            )

    for section, address, op, raw in operations:
        if op == 4:
            group, index, expected = raw[1:]
            test = {
                "section": section,
                "offset": address,
                "group": group,
                "index": index,
                "expected": expected,
            }
            if group < len(bases):
                # RE1 numbers bits from each little-endian word's MSB.
                byte = bases[group] + 4 * (index // 32) + 3 - (index % 32) // 8
                mask = 128 >> (index % 8)
                if address in guarded or address in door_guarded:
                    dependencies[byte] = dependencies.get(byte, 0) | mask
                test.update(address_ps1=hex(byte), width=1, mask=mask)
            else:
                if address in guarded:
                    issues.append(f"unknown flag group {group} at 0x{address:x}")
                if address in door_guarded:
                    door_issues.append(f"unknown flag group {group} at 0x{address:x}")
            if expected not in (0, 1):
                if address in guarded:
                    issues.append(f"unclassified flag comparison at 0x{address:x}")
                if address in door_guarded:
                    door_issues.append(f"unclassified flag comparison at 0x{address:x}")
            flag_tests.append(test)
        if op == 6 and address in guarded:
            index, comparison, _ = raw[1:]
            # Stage/room can be reconstructed and character is captured.
            # Camera and interaction bytes belong to the active room only.
            if index not in (0, 1, 9):
                issues.append(f"room-local comparison field {index} at 0x{address:x}")
            if comparison > 5:
                issues.append(f"unclassified byte comparison at 0x{address:x}")
        if op == 6 and address in door_guarded:
            index, comparison, _ = raw[1:]
            if index not in (0, 1, 9):
                door_issues.append(
                    f"room-local door comparison field {index} at 0x{address:x}"
                )
            if comparison > 5:
                door_issues.append(
                    f"unclassified door byte comparison at 0x{address:x}"
                )
        if op in predicates - {4, 6} and address in guarded:
            issues.append(f"non-bit comparison 0x{op:02x} at 0x{address:x}")
        if op in predicates - {4, 6} and address in door_guarded:
            door_issues.append(f"non-bit door comparison 0x{op:02x} at 0x{address:x}")
    # Item initialization also tests its acquisition bit implicitly. A room
    # entered after pickup may have no active descriptor for that item; a
    # later rewind must still invalidate that cached empty manifest.
    item_global_ids = sorted(
        {raw[22] for _, _, op, raw in operations if op == 0x18 and 0 < raw[10] < 0x54}
    )
    quantity_slots = {
        raw[2] for _, _, op, raw in operations if op == 0x4C and raw[1] in (1, 2)
    }
    mutable_fields = []
    if "events_offset" in row:
        for index in range(event_count):
            mutable_fields.append(
                {
                    "section": "events",
                    "offset": 4 * index,
                    "width": 4,
                    "kind": "event-pointer",
                    "original": struct.unpack_from("<I", data, event_start + 4 * index)[
                        0
                    ],
                }
            )
    for section, address, op, raw in operations:
        section_offset = row[section + "_offset"]
        if op == 0x18:
            # The item initializer clears every flag except bit zero in its own source packet.
            mutable_fields.append(
                {
                    "section": section,
                    "offset": address + 24 - section_offset,
                    "width": 2,
                    "kind": "item-parameter-mask",
                    "original": struct.unpack_from("<H", raw, 24)[0],
                }
            )
        if op in (0x0C, 0x0D, 0x18) and raw[1] & 127 in quantity_slots:
            # Transfer modes 1/2 write through AOT source+9, i.e. this initializer's byte 11.
            mutable_fields.append(
                {
                    "section": section,
                    "offset": address + 11 - section_offset,
                    "width": 1,
                    "kind": "item-quantity",
                    "original": raw[11],
                }
            )
    for section, address, op, raw in operations:
        if op == 0x0D and raw[10] in (3, 4, 15):
            issues.append(
                f"unclassified generic AOT handler {raw[10]} at 0x{address:x}"
            )
        if op in (0x24, 0x2D) and raw[2] in (4, 15) and raw[1] not in item_ids:
            issues.append(f"award has no item initializer at 0x{address:x}")
        if op == 0x4C and raw[2] in item_ids:
            issues.append(
                f"item quantity transfer requires live refresh at 0x{address:x}"
            )

    row.update(
        dependencies=[
            {"address_ps1": hex(address), "width": 1, "mask": mask}
            for address, mask in sorted(dependencies.items())
        ],
        cache_complete=not issues,
        door_cache_complete=not door_issues,
        door_cache_reason="; ".join(door_issues)
        if door_issues
        else "door definitions initialized only; source and initialization guards covered",
        reason="; ".join(issues)
        if issues
        else "init/main/indexed events covered; item manifest guards captured",
        stats=stats,
        flag_tests=flag_tests,
        item_aot_ids=sorted(item_ids),
        item_global_ids=item_global_ids,
        mutable_fields=mutable_fields,
    )
    if all(section + "_offset" in row for section in ("init", "main", "events")):
        row["tracking_program"] = build_tracking_program(
            data, row, operations, not source_issues, event_scan
        )
    for audit in profile["cache_audits"]:
        if audit["source_rdt"] != source_rdt:
            continue
        # A hand-audited event program can close a conservative scanner gap,
        # but its authorization must be bound to the exact owned source bytes.
        if audit["source_sha256"] != row["source_sha256"]:
            raise ValueError("cache audit source hash mismatch")
        if not audit["research_ids"] or not audit["reason"]:
            raise ValueError("cache audit requires evidence references and a reason")
        row["cache_complete"] = True
        row["reason"] = audit["reason"]
        row["cache_audit_references"] = audit["research_ids"]
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    parser.add_argument("out", type=Path)
    parser.add_argument("profile", type=Path)
    arguments = parser.parse_args()
    try:
        profile = json.loads(arguments.profile.read_text())
        if profile["serial"] != "SLUS-00551":
            raise ValueError(
                "cache inspection supports only the pinned SLUS-00551 profile"
            )
        expected_identity = profile["executable_identity"]
        cue = arguments.cue.read_text()
        image_match = re.search(r'FILE\s+"([^"]+)"', cue)
        if image_match is None:
            raise ValueError("CUE has no quoted FILE entry")
        image = arguments.cue.parent / image_match[1]
        rooms = []
        excluded = []
        executable_identity = ""
        executable = b""
        catalog = []
        with image.open("rb") as file:
            descriptor = _sector_data(file, 16)
            root, root_size = (
                struct.unpack_from("<I", descriptor, 158)[0],
                struct.unpack_from("<I", descriptor, 166)[0],
            )
            for name, extent, size in _iter_files(file, root, root_size):
                catalog.append(name)
                if Path(name).name == "SLUS_005.51":
                    executable = _read_file(file, extent, size)
                    digest = hashlib.sha256(executable).hexdigest()
                    executable_identity = "SLUS_005.51 SHA256 " + digest
                if name.endswith(".RDT"):
                    row = scan_cache_rdt(_read_file(file, extent, size), name, profile)
                    if "tracking_program" in row:
                        rooms.append(row)
                    else:
                        excluded.append({"source_rdt": name, "reason": row["reason"]})
        if executable_identity != expected_identity:
            raise ValueError(
                "disc executable does not match the required profile identity"
            )
        if not rooms:
            raise ValueError("disc contains no RE1 RDT files with bounded scripts")
        arguments.out.write_text(
            json.dumps(
                {
                    "profile_id": profile["profile_id"],
                    "executable_identity": executable_identity,
                    "research_ids": [
                        "RE1-CACHE-001",
                        "RE1-CACHE-002",
                        "RE1-CACHE-003",
                        "RE1-ENGINE-001",
                        "RE1-ENGINE-002",
                        "RE1-SCD-007",
                        "RE1-SCD-008",
                        "RE1-SCD-009",
                        "RE1-SCD-010",
                        "RE1-SCD-011",
                        "RE1-SCD-012",
                        "RE1-SCD-013",
                        "RE1-SCD-014",
                        "RE1-SCD-015",
                        "RE1-SCD-016",
                        "RE1-SCD-017",
                        "RE1-NATIVE-001",
                        "RE1-EVENT-001",
                        "RE1-EVENT-003",
                        "RE1-EVENT-004",
                        "RE1-EVENT-005",
                        "RE1-EVENT-006",
                        "RE1-EVENT-007",
                        "RE1-EVENT-014",
                        "RE1-EVENT-016",
                        "RE1-EVENT-017",
                        "RE1-REENTRY-004",
                        "RE1-REENTRY-002",
                        "RE1-QUANTITY-001",
                        "RE1-QUANTITY-002",
                        "RE1-VARS-001",
                        "RE1-SOURCE-002",
                        "RE1-SELECT-001",
                    ],
                    "validation": "Candidate: pinned executable and static source inspection",
                    "rooms": rooms,
                    "excluded_sources": excluded,
                    "source_choices": build_source_choices(
                        executable, catalog, rooms, profile
                    ),
                },
                indent=2,
            )
        )
    except (KeyError, OSError, TypeError, ValueError, struct.error) as error:
        parser.error(str(error))
    print(
        f"rooms={len(rooms)} cache_candidates={sum(row['cache_complete'] for row in rooms)} -> {arguments.out}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
