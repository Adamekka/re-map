"""Extract one file from a MODE2/2352 PS1 image to /tmp.

Local reverse-engineering helper only. Never point the output at the repo:
extracted game bytes stay out of git.

Usage:
  python3 tools/extract_psx_file.py CUE IMAGE_PATH OUTPUT
  example: python3 tools/extract_psx_file.py cue.bin "PSX/STAGE1/ROOM1070.RDT" /tmp/room1070.rdt
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_psx_files import _read_dir, _sector_data  # noqa: E402


def _find(f, root_lba: int, root_len: int, want: str) -> tuple[int, int]:
    parts = want.upper().split("/")
    queue: list[tuple[str, int, int]] = [("", root_lba, root_len)]
    dirs: dict[str, tuple[int, int]] = {"": (root_lba, root_len)}
    # Walk level by level.
    prefix = ""
    for depth, part in enumerate(parts):
        plba, plen = dirs[prefix]
        found = None
        for name, extent, size, is_dir in _read_dir(f, plba, plen):
            if name in (".", ".."):
                continue
            if name.upper() == part:
                found = (extent, size, is_dir)
                break
            if is_dir:
                key = f"{prefix}/{name}" if prefix else name
                dirs[key] = (extent, size)
        if found is None:
            # Expand one level and retry.
            expanded = False
            for key, (dlba, dlen) in list(dirs.items()):
                if key.count("/") != depth:
                    continue
                for name, extent, size, is_dir in _read_dir(f, dlba, dlen):
                    if name in (".", ".."):
                        continue
                    key2 = f"{key}/{name}" if key else name
                    if is_dir and key2 not in dirs:
                        dirs[key2] = (extent, size)
                        expanded = True
            if expanded:
                plba, plen = dirs.get(prefix, (root_lba, root_len))
                for name, extent, size, is_dir in _read_dir(f, plba, plen):
                    if name in (".", ".."):
                        continue
                    if name.upper() == part:
                        found = (extent, size, is_dir)
                        break
            if found is None:
                raise FileNotFoundError(part)
        extent, size, is_dir = found
        if depth < len(parts) - 1:
            if not is_dir:
                raise NotADirectoryError(part)
            prefix = f"{prefix}/{part}" if prefix else part
            dirs[prefix] = (extent, size)
        else:
            if is_dir:
                raise IsADirectoryError(part)
            return extent, size
    raise FileNotFoundError(want)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cue", type=Path)
    ap.add_argument("image_path")
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    cue_text = args.cue.read_text(errors="replace")
    m = re.search(r'FILE\s+"([^"]+)"', cue_text)
    if not m:
        print("no FILE line in cue", file=sys.stderr)
        return 2
    img = args.cue.parent / m.group(1)
    with open(img, "rb") as f:
        pvd = _sector_data(f, 16)
        root_lba = struct.unpack_from("<I", pvd, 158)[0]
        root_len = struct.unpack_from("<I", pvd, 166)[0]
        extent, size = _find(f, root_lba, root_len, args.image_path)
        # Extent LBAs are 2048-block units. Image sectors are 2352 bytes.
        nsect = (size + 2048 - 1) // 2048
        out = bytearray()
        for i in range(nsect):
            f.seek((extent + i) * 2352 + 24)
            out.extend(f.read(2048))
        args.output.write_bytes(bytes(out[:size]))
        print(f"wrote {size} bytes to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
