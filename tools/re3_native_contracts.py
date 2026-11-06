"""Audit Candidate RE3 native contracts against private RAM and owned media.

RE3-NATIVE-001/002/003/004/005: offline source witnesses and rejection evidence only.
No emulator access, gameplay admission, history updates or game-byte output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_item_table import _read_file
from re3_room_catalog import build_catalog

from games.re3 import EXECUTABLE_SHA256

# Retained private capture scripts import these constants from the audit tool.
from games.re3.capture_data import CODE_WINDOWS as CODE_WINDOWS
from games.re3.capture_data import RAM_SIZE as RAM_SIZE
from games.re3.capture_data import capture_failure
from games.re3.room_data import RoomFormatFailure, decode_room, room_section_end


class ContractError(ValueError):
    """The inputs cannot support this bounded offline audit."""


@dataclass(frozen=True)
class RoomSource:
    path: str
    stage_digit: int
    room_number: int
    ard_lba: int
    ard_size: int
    rdt: bytes

    def __post_init__(self) -> None:
        assert 1 <= self.stage_digit <= 7
        assert 0 <= self.room_number <= 255
        assert self.ard_lba >= 0 and self.ard_size > 0


def verify_executable(executable: bytes) -> None:
    if hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256:
        raise ContractError("Executable differs from the required SLUS_009.23 SHA256")


def audit_capture(
    executable: bytes, ram: bytes, sources: tuple[RoomSource, ...]
) -> dict:
    verify_executable(executable)
    failure = capture_failure(executable, ram)
    if failure is not None:
        raise ContractError(failure.detail)

    def executable_word(address: int, width: int) -> int:
        offset = 0x800 + address - 0x80010000
        if address % width or not 0x800 <= offset <= len(executable) - width:
            raise ContractError(
                "Native room/file table points outside the executable payload"
            )
        return int.from_bytes(executable[offset : offset + width], "little")

    # RE3-NATIVE-001: these are signed selectors, not filename stage digits.
    stage, room, camera = struct.unpack_from("<3h", ram, 0xD1F76)
    pointer, allocation = struct.unpack_from("<2I", ram, 0xCC86C)
    flags = struct.unpack_from("<I", ram, 0xCC858)[0]
    result = {
        "capture_sha256": hashlib.sha256(ram).hexdigest(),
        "stage_i16": stage,
        "room_i16": room,
        "camera_i16": camera,
        "rdt_pointer_virtual": pointer,
        "rdt_allocation_virtual": allocation,
        "lifecycle_word_u32": flags,
        "recorded_input_bit_set": bool(flags & 0x10000000),
        "recorded_input_phase_u8": ram[0xC79AE],
        "recorded_input_index_u32": struct.unpack_from("<I", ram, 0xC79B0)[0],
        "saved_status_word_u32": struct.unpack_from("<I", ram, 0xD1F2C)[0],
        "new_game_option_word_u32": struct.unpack_from("<I", ram, 0xD1F30)[0],
        "new_game_option_bit_set": bool(ram[0xD1F30] & 1),
        "native_menu_active_u8": ram[0xE01E7],
        "native_menu_view_u8": ram[0xE01D0],
        "native_pause_u8": ram[0xD4434],
        "native_control_word_u32": struct.unpack_from("<I", ram, 0xCCBA0)[0],
        "raw_held_input_u32": struct.unpack_from("<I", ram, 0xCC830)[0],
        "logical_held_input_u32": struct.unpack_from("<I", ram, 0xCC83C)[0],
        "source_matches": [],
        "selected_source_paths": [],
        "rejection_evidence": [],
        # Static contracts and negative examples cannot authorize a campaign
        # visit, even when every source witness matches and no reject bit is set.
        "campaign_admission": "unresolved",
        "hard_identity": "unresolved",
    }
    if flags & 0x10000000:
        result["rejection_evidence"].append("native-recorded-input-path-selected")
    # RE3-NATIVE-004: native interface loops and Start pause preserve plausible
    # player/source fields. Source agreement cannot cancel these update gates.
    if result["native_menu_active_u8"]:
        result["rejection_evidence"].append("native-menu-loop-active")
    if result["native_pause_u8"]:
        result["rejection_evidence"].append("native-world-update-paused")
    # RE3-NATIVE-005: this native filter retains held bits 0x3000 while
    # removing movement input even at the player's normal handler.
    if result["native_control_word_u32"] & 0x01000000:
        result["rejection_evidence"].append("native-logical-movement-input-filtered")
    if pointer != allocation:
        result["rejection_evidence"].append("rdt-pointer-allocation-disagree")
    if not 0x80000000 <= pointer <= 0x80000000 + RAM_SIZE - 96 or pointer % 4:
        result["rejection_evidence"].append("rdt-pointer-outside-cached-main-ram")
        base = -1
    else:
        base = pointer - 0x80000000

    identifiers = set()
    for source in sources:
        identifier = source.stage_digit, source.room_number
        if identifier in identifiers:
            raise ContractError("Duplicate source stage/room identifier")
        identifiers.add(identifier)
        decoded = decode_room(source.rdt)
        if isinstance(decoded, RoomFormatFailure):
            raise ContractError(f"Invalid room source {source.path}: {decoded.detail}")
        table = executable_word(0x8009DFD0 + 4 * (source.stage_digit - 1), 4)
        file_index = executable_word(table + 2 * source.room_number, 2)
        record = 0x800946A4 + 8 * file_index
        size = executable_word(record, 4) & 0xFFFFFF
        lba = executable_word(record + 4, 4) & 0xFFFFFF
        if (size, lba) != (source.ard_size, source.ard_lba):
            raise ContractError(
                f"Native selector table disagrees with owned ARD {source.path}"
            )
        # The native selector indexes seven tables from zero; source filenames
        # number their stages from one. All 169 file-table rows agree.
        if (stage, room) == (source.stage_digit - 1, source.room_number):
            result["selected_source_paths"].append(source.path)
        if base < 0 or base + len(source.rdt) > len(ram):
            continue
        if ram[base + 1 : base + 8] != source.rdt[1:8]:
            continue
        live_words = struct.unpack_from("<22I", ram, base + 8)
        words = decoded["section_words"]
        # Native initialization relocates every nonzero word, including opaque
        # slot 2. Slot 21 and prefix byte 0 are later runtime work fields.
        if any(
            live_words[index] != ((word + pointer) & 0xFFFFFFFF if word else 0)
            for index, word in enumerate(words[:21])
        ):
            continue
        cameras_start = words[7]
        cameras_end = cameras_start + len(decoded["cameras"]) * 32
        cameras = bytearray(source.rdt[cameras_start:cameras_end])
        for offset in range(28, len(cameras), 32):
            # The native camera loop adds the base even to a zero mask offset.
            value = struct.unpack_from("<I", cameras, offset)[0]
            struct.pack_into("<I", cameras, offset, (value + pointer) & 0xFFFFFFFF)
        zones_start = words[8]
        zones_end = room_section_end(words, 8, len(source.rdt))
        if ram[base + cameras_start : base + cameras_end] != cameras:
            continue
        zones = source.rdt[zones_start:zones_end]
        if ram[base + zones_start : base + zones_end] != zones:
            continue
        start, end = decoded["initializer"]["offset"], decoded["initializer"]["end"]
        # Script operands can change in the retained captures. Report differences
        # without masking them or treating script-byte identity as mandatory.
        differences = sum(
            a != b
            for a, b in zip(source.rdt[start:end], ram[base + start : base + end])
        )
        result["source_matches"].append(
            {
                "path": source.path,
                "native_file_index": file_index,
                "rdt_sha256": decoded["sha256"],
                "camera_count": len(decoded["cameras"]),
                "camera_in_range": 0 <= camera < len(decoded["cameras"]),
                "relocated_cameras_sha256": hashlib.sha256(cameras).hexdigest(),
                "camera_zones_sha256": hashlib.sha256(zones).hexdigest(),
                "initializer_different_bytes": differences,
                "initializer_size": end - start,
            }
        )
    matches = result["source_matches"]
    if len(matches) != 1:
        result["rejection_evidence"].append("no-unique-loaded-source-witness")
    else:
        if result["selected_source_paths"] != [matches[0]["path"]]:
            result["rejection_evidence"].append("selectors-disagree-with-loaded-source")
        if not matches[0]["camera_in_range"]:
            result["rejection_evidence"].append("camera-outside-source-table")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("executable", type=Path)
    parser.add_argument("captures", type=Path, nargs="+")
    args = parser.parse_args()
    try:
        executable = args.executable.read_bytes()
        verify_executable(executable)
        catalog = build_catalog(args.image, "SLUS_009.23", EXECUTABLE_SHA256)
        if isinstance(catalog, RoomFormatFailure):
            raise ContractError(catalog.detail)
        if catalog["unsupported"]:
            raise ContractError(
                "Owned media has unsupported sources; audit would be incomplete"
            )
        sources = []
        with args.image.open("rb") as stream:
            for row in catalog["rooms"]:
                ard = _read_file(stream, row["lba"], row["size"])
                if hashlib.sha256(ard).hexdigest() != row["sha256"]:
                    raise ContractError("ARD changed after catalog inspection")
                obj = row["container"]["objects"][8]
                rdt = ard[obj["offset"] : obj["offset"] + obj["size"]]
                sources.append(
                    RoomSource(
                        row["path"],
                        row["source_stage"],
                        row["source_room"],
                        row["lba"],
                        row["size"],
                        rdt,
                    )
                )
        captures = [
            {
                "file": str(path),
                **audit_capture(executable, path.read_bytes(), tuple(sources)),
            }
            for path in args.captures
        ]
    except (OSError, ValueError, struct.error) as error:
        print(f"RE3 native contract audit failed: {error}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "schema": "re3-native-contracts-v1",
                "status": "candidate-offline-audit",
                "executable_sha256": EXECUTABLE_SHA256,
                "native_source_table_rows_checked": len(sources),
                "captures": captures,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
