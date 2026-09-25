"""Extract PS1 RAM from a DuckStation .sav without booting anything.

Pure CLI, no emulator window. Handles local header version 83 with
ZstDefault compression as observed on SLUS-00551 saves.

Usage:
  python3 tools/extract_sav_ram.py input.sav output.bin

Method: the state payload holds a zstd frame with all components.
RAM (2MB) sits contiguous inside the decompressed blob. The base is
located by anchoring on the region serial bytes and verifying against
the GDB-observed layout, instead of hardcoding a header offset that
changes with save_state_version.h revisions.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

RAM_SIZE = 0x200000
ZSTD_MAGIC = bytes.fromhex("28b52ffd")
# Region serial observed in RAM at 0x1004c, e.g. b'US-0' for SLUS USA.
SERIAL_OFF = 0x1004C
# Verification offsets from live GDB reads on SLUS-00551, see RE1-USERMAP-001.
# Main Location must be 0x00..0x06, GameState 0x00..0x01. Loose on purpose.
MAIN_OFF = 0xC8660


def _find_frames(data: bytes) -> list[int]:
    idxs: list[int] = []
    i = 0
    while True:
        j = data.find(ZSTD_MAGIC, i)
        if j < 0:
            return idxs
        idxs.append(j)
        i = j + 1


def _decompress(frame: bytes) -> bytes | None:
    with tempfile.NamedTemporaryFile(suffix=".zst", delete=False) as f:
        f.write(frame)
        name = f.name
    try:
        proc = subprocess.run(
            ["zstd", "-d", "-c", name],
            capture_output=True,
        )
        if not proc.stdout:
            return None
        return proc.stdout
    finally:
        Path(name).unlink(missing_ok=True)


def _find_ram_base(blob: bytes) -> int | None:
    # Anchor on plausible serial text near a 2MB window, then verify.
    for anchor_text in (b"US-0", b"ES-0"):
        i = 0
        while True:
            j = blob.find(anchor_text, i)
            if j < 0:
                break
            i = j + 1
            base = j - SERIAL_OFF
            if base < 0 or base + RAM_SIZE > len(blob):
                continue
            main = blob[base + MAIN_OFF]
            if main <= 0x06:
                return base
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("input", type=Path)
    ap.add_argument("output", type=Path)
    args = ap.parse_args()

    data = args.input.read_bytes()
    if data[:4] != b"DUCC":
        print("not a DuckStation savestate (missing DUCC magic)", file=sys.stderr)
        return 2
    frames = _find_frames(data)
    if not frames:
        print("no zstd frames found", file=sys.stderr)
        return 2
    # State payload is the last large frame. Screenshots come first.
    for off in sorted(frames, reverse=True):
        blob = _decompress(data[off:])
        if blob is None or len(blob) < RAM_SIZE:
            continue
        base = _find_ram_base(blob)
        if base is None:
            continue
        args.output.write_bytes(blob[base : base + RAM_SIZE])
        print(f"ram base {base} in decompressed {len(blob)} -> {args.output}")
        return 0
    print("RAM not found in any frame", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
