"""Build a room item table from all RDTs on the disc, metadata only.

Reads each RDT by LBA, walks init and main script chunks, collects 0x18
entries with the biorand RE1 field split. Output is integers and labels,
no game bytes, safe to commit.

Usage:
  python3 tools/build_item_table.py CUE OUT.JSON [--stage STAGE1] [--limit 0]
"""
from __future__ import annotations

import argparse
import json
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from list_psx_files import _read_dir, _sector_data  # noqa: E402
from scan_scd import SIZES, walk  # noqa: E402

import re


def _iter_files(f, root_lba: int, root_len: int):
    queue = [("", root_lba, root_len)]
    while queue:
        prefix, lba, length = queue.pop(0)
        for name, extent, size, is_dir in _read_dir(f, lba, length):
            if name in (".", ".."):
                continue
            path = f"{prefix}/{name}" if prefix else name
            if is_dir:
                queue.append((path, extent, size))
            else:
                yield path, extent, size


def _read_file(f, extent: int, size: int) -> bytes:
    nsect = (size + 2048 - 1) // 2048
    out = bytearray()
    for i in range(nsect):
        f.seek((extent + i) * 2352 + 24)
        out.extend(f.read(2048))
    return bytes(out[:size])


def _scan_rdt(d: bytes) -> dict:
    offs = struct.unpack_from("<19I", d, 0x48)
    header = {
        "head8": d[:8].hex(),
        "offsets": [hex(o) for o in offs],
    }
    items = []
    stats = {}
    for idx, name in ((6, "init"), (7, "main")):
        start, end = offs[idx], offs[idx + 1]
        if end <= start or end > len(d):
            stats[name] = "bad-range"
            continue
        span = d[start:end]
        (length,) = struct.unpack_from("<H", span, 0)
        code = span[2 : 2 + length] if length + 2 <= len(span) else span
        ops, status = walk(code, start + 2)
        stats[name] = f"{status}/{len(ops)}"
        for addr, op, raw in ops:
            if op != 0x18:
                continue
            _id = raw[1]
            x, y, w, h = struct.unpack_from("<4h", raw, 2)
            items.append({
                "scd": name, "addr": hex(addr), "id": _id,
                "x": x, "y": y, "w": w, "h": h,
                "type": f"0x{raw[10]:02x}", "amount": raw[11],
                "gid": raw[16],
            })
    return {"header": header, "stats": stats, "items": items}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cue", type=Path)
    ap.add_argument("out", type=Path)
    ap.add_argument("--stage", default="")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    cue_text = args.cue.read_text(errors="replace")
    img = args.cue.parent / re.search(r'FILE\s+"([^"]+)"', cue_text).group(1)
    stage_f = args.stage.upper()
    table = []
    with open(img, "rb") as f:
        pvd = _sector_data(f, 16)
        root_lba = struct.unpack_from("<I", pvd, 158)[0]
        root_len = struct.unpack_from("<I", pvd, 166)[0]
        n = 0
        for path, extent, size in _iter_files(f, root_lba, root_len):
            up = path.upper()
            if ".RDT" not in up:
                continue
            if stage_f and stage_f not in up:
                continue
            d = _read_file(f, extent, size)
            row = {"file": path, "lba": extent, "size": size}
            try:
                row.update(_scan_rdt(d))
            except struct.error as exc:
                row["error"] = str(exc)
            table.append(row)
            n += 1
            if args.limit and n >= args.limit:
                break
    args.out.write_text(json.dumps({"rooms": table}, indent=1))
    total_items = sum(len(r.get("items", [])) for r in table)
    print(f"rooms={len(table)} item_entries={total_items} -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
