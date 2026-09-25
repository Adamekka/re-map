"""List files on a MODE2/2352 PS1 .bin/.cue without extracting anything.

Pure CLI metadata: path, LBA, size. No copyrighted bytes are read out,
only directory layout for finding RDT room files.

Usage:
  python3 tools/list_psx_files.py "/path/to/game.cue" [--filter RDT]
"""
from __future__ import annotations

import argparse
import re
import struct
import sys
from pathlib import Path

SECTOR = 2352
DATA_OFF = 24
DATA_LEN = 2048


def _sector_data(f, lba: int) -> bytes:
    f.seek(lba * SECTOR + DATA_OFF)
    return f.read(DATA_LEN)


def _read_dir(f, lba: int, length: int) -> list[tuple[str, int, int, bool]]:
    # Returns (name, extent_lba, size, is_dir) for entries in an ISO9660
    # directory, following the path-table-free extent chain.
    out: list[tuple[str, int, int, bool]] = []
    remaining = length
    cur = lba
    buf = b""
    while remaining > 0:
        chunk = _sector_data(f, cur)
        take = min(remaining, DATA_LEN)
        buf += chunk[:take]
        remaining -= take
        cur += 1
    pos = 0
    while pos + 33 <= len(buf):
        rec_len = buf[pos]
        if rec_len == 0:
            # Pad to next sector boundary within the buffer.
            nxt = ((pos // DATA_LEN) + 1) * DATA_LEN
            pos = nxt
            continue
        flags = buf[pos + 25]
        extent = struct.unpack_from("<I", buf, pos + 2)[0]
        size = struct.unpack_from("<I", buf, pos + 10)[0]
        name_len = buf[pos + 32]
        name_raw = buf[pos + 33 : pos + 33 + name_len]
        if name_raw in (b"\x00", b"\x01"):
            name = "." if name_raw == b"\x00" else ".."
        else:
            name = name_raw.decode("ascii", errors="replace").split(";")[0]
        out.append((name, extent, size, bool(flags & 2)))
        pos += rec_len
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cue", type=Path)
    ap.add_argument("--filter", default="")
    args = ap.parse_args()

    cue_text = args.cue.read_text(errors="replace")
    m = re.search(r'FILE\s+"([^"]+)"', cue_text)
    if not m:
        print("no FILE line in cue", file=sys.stderr)
        return 2
    img = args.cue.parent / m.group(1)
    filt = args.filter.upper()

    with open(img, "rb") as f:
        pvd = _sector_data(f, 16)
        if pvd[0] != 1 or pvd[1:6] != b"CD001":
            print("not an ISO9660 PVD at sector 16", file=sys.stderr)
            return 2
        root_lba = struct.unpack_from("<I", pvd, 158)[0]
        root_len = struct.unpack_from("<I", pvd, 166)[0]

        # Walk directories breadth-first.
        queue: list[tuple[str, int, int]] = [("", root_lba, root_len)]
        count = 0
        while queue:
            prefix, lba, length = queue.pop(0)
            for name, extent, size, is_dir in _read_dir(f, lba, length):
                if name in (".", ".."):
                    continue
                path = f"{prefix}/{name}" if prefix else name
                if is_dir:
                    queue.append((path, extent, size))
                else:
                    if filt and filt not in path.upper():
                        continue
                    print(f"{path} lba={extent} size={size}")
                    count += 1
        print(f"listed={count}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
