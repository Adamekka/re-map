"""Catalog numeric RE3 PS1 room and MAP_U bounds from an owned MODE2/2352 image.

The caller supplies the expected boot fingerprint explicitly. This tool does
not register a runtime profile, decode scripts or export any image payloads.
See docs/research/re3/room-format.md for claims and reproduction.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from build_item_table import _read_file
from list_psx_files import _read_dir, _sector_data
from output_safety import aliases_input

from games.re3.room_data import (
    RoomFormatFailure,
    aligned_block_size,
    decode_ard,
    decode_map,
    decode_room,
)


def build_catalog(image: Path, executable_path: str, expected_sha256: str) -> dict | RoomFormatFailure:
    if re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        return RoomFormatFailure("disc", 0, "expected executable SHA256 must be 64 lowercase hex digits")
    try:
        with image.open("rb") as stream:
            image_size = stream.seek(0, 2)
            if image_size % 2352:
                raise ValueError("image is not a complete MODE2/2352 track")

            def check_extent(lba: int, size: int) -> None:
                if size <= 0 or (lba + aligned_block_size(size) // 2048) * 2352 > image_size:
                    raise ValueError(f"ISO extent outside image: LBA {lba}, size {size}")

            check_extent(16, 2048)
            pvd = _sector_data(stream, 16)
            if pvd[:7] != b"\x01CD001\x01":
                raise ValueError("image lacks its ISO9660 primary volume")
            root = struct.unpack_from("<I", pvd, 158)[0]
            root_size = struct.unpack_from("<I", pvd, 166)[0]
            queue, visited, files = [("", root, root_size)], set(), {}
            while queue:
                prefix, lba, size = queue.pop(0)
                check_extent(lba, size)
                if lba in visited:
                    raise ValueError("repeated ISO directory extent")
                visited.add(lba)
                for name, extent, length, is_directory in _read_dir(stream, lba, size):
                    if name in (".", ".."):
                        continue
                    path = f"{prefix}/{name}" if prefix else name
                    if is_directory:
                        queue.append((path, extent, length))
                    elif path in files:
                        raise ValueError(f"duplicate ISO file: {path}")
                    else:
                        files[path] = (extent, length)

            def read_file(path: str) -> bytes:
                if path not in files:
                    raise ValueError(f"required source missing: {path}")
                lba, size = files[path]
                check_extent(lba, size)
                data = _read_file(stream, lba, size)
                if len(data) != size:
                    raise ValueError(f"incomplete source read: {path}")
                return data

            executable = read_file(executable_path)
            digest = hashlib.sha256(executable).hexdigest()
            if digest != expected_sha256:
                raise ValueError("disc executable does not match the supplied SHA256")
            rooms, unsupported = [], []
            for path, (lba, size) in sorted(files.items()):
                if not path.endswith(".ARD"):
                    continue
                match = re.fullmatch(r"CD_DATA/STAGE([1-7])/R\1([0-9A-F]{2})\.ARD", path)
                if match is None:
                    raise ValueError(f"unsupported room source path: {path}")
                data = read_file(path)
                source = {
                    "path": path, "lba": lba, "size": size,
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "source_stage": int(match[1]), "source_room": int(match[2], 16),
                }
                container = decode_ard(data)
                if isinstance(container, RoomFormatFailure):
                    unsupported.append({**source, "failure": asdict(container)})
                    continue
                obj = container["objects"][8]
                room = decode_room(data[obj["offset"] : obj["offset"] + obj["size"]])
                if isinstance(room, RoomFormatFailure):
                    unsupported.append({**source, "container": container, "failure": asdict(room)})
                    continue
                rooms.append({**source, "container": container, "room": room})
            if not rooms and not unsupported:
                raise ValueError("disc contains no RE3 ARD sources")
            map_path = "CD_DATA/ETC/MAP_U.MAP"
            map_data = decode_map(read_file(map_path))
            if isinstance(map_data, RoomFormatFailure):
                unsupported.append({"path": map_path, "failure": asdict(map_data)})
                map_result = {"path": map_path, "status": "unsupported"}
            else:
                map_result = {"path": map_path, "status": "bounded", **map_data}
            return {
                "schema": "re3-static-room-catalog-v1", "evidence_kind": "offline-only",
                "executable": {"path": executable_path, "size": len(executable), "sha256": digest},
                "iso_file_count": len(files), "rooms": rooms, "map": map_result,
                "unsupported": unsupported,
                "runtime_support": "unresolved",
            }
    except (OSError, ValueError, struct.error) as error:
        return RoomFormatFailure("disc", 0, str(error))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--executable", required=True)
    parser.add_argument("--expected-executable-sha256", required=True)
    args = parser.parse_args()
    result = build_catalog(args.image, args.executable, args.expected_executable_sha256)
    if isinstance(result, RoomFormatFailure):
        print(f"RE3 catalog failed: {result.detail}", file=sys.stderr)
        return 2
    try:
        # The output is metadata, and must never replace owned input bytes,
        # including when a symlink or hard link names the same image.
        if aliases_input(args.image, args.output):
            print("Catalog output must differ from the input image", file=sys.stderr)
            return 2
        args.output.write_text(json.dumps(result, indent=2) + "\n")
    except OSError as error:
        print(f"Cannot write RE3 catalog: {error}", file=sys.stderr)
        return 2
    print(f"rooms={len(result['rooms'])} unsupported={len(result['unsupported'])}")
    return 1 if result["unsupported"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
