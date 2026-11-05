"""Inspect an owned single-track MODE2/2352 disc; emit metadata, never game bytes.

Usage: python3 tools/re3_disc_identity.py /absolute/path/to/owned.cue
The JSON fingerprints the input. It does not certify a known-good dump or a
supported runtime profile. EDC/ECC and gameplay are outside this static check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

from list_psx_files import DATA_LEN, DATA_OFF, SECTOR, _read_dir, _sector_data


class DiscInspectionError(ValueError):
    """The supplied media cannot satisfy the supported static inspection contract."""


def inspect_disc(cue: Path) -> dict:
    cue_bytes = cue.read_bytes()
    cue_match = re.fullmatch(
        r'\s*FILE\s+"([^"\r\n]+)"\s+BINARY\s+'
        r"TRACK\s+01\s+MODE2/2352\s+INDEX\s+01\s+00:00:00\s*",
        cue_bytes.decode("utf-8-sig"),
        re.IGNORECASE,
    )
    if cue_match is None:
        raise DiscInspectionError(
            "Expected one BINARY file, TRACK 01 MODE2/2352, INDEX 01 00:00:00."
        )
    image = cue.parent / cue_match[1]
    with image.open("rb") as stream:
        image_bytes = image.stat().st_size
        if image_bytes < 17 * SECTOR or image_bytes % SECTOR:
            raise DiscInspectionError("Image is too short or has a partial raw sector.")
        image_sectors = image_bytes // SECTOR
        digest = hashlib.sha256()
        forms = {"form1_sectors": 0, "form2_sectors": 0}
        for lba in range(image_sectors):
            raw = stream.read(SECTOR)
            if len(raw) != SECTOR:
                raise DiscInspectionError(f"Short raw sector at LBA {lba}.")
            if raw[:12] != b"\x00" + b"\xff" * 10 + b"\x00" or raw[15] != 2:
                raise DiscInspectionError(f"Invalid Mode 2 sync/header at LBA {lba}.")
            if raw[16:20] != raw[20:24]:
                raise DiscInspectionError(f"Mismatched XA subheaders at LBA {lba}.")
            forms["form2_sectors" if raw[18] & 0x20 else "form1_sectors"] += 1
            digest.update(raw)
        if stream.read(1):
            raise DiscInspectionError("Image size changed during inspection.")

        def read_extent(lba: int, size: int) -> bytes:
            if (
                lba < 0
                or size < 0
                or lba + (size + DATA_LEN - 1) // DATA_LEN > image_sectors
            ):
                raise DiscInspectionError(f"ISO extent exceeds image at LBA {lba}.")
            chunks = []
            for sector in range(lba, lba + (size + DATA_LEN - 1) // DATA_LEN):
                stream.seek(sector * SECTOR + 18)
                submode = stream.read(1)
                if len(submode) != 1:
                    raise DiscInspectionError(f"Short XA subheader at LBA {sector}.")
                if submode[0] & 0x20:
                    # XA media also contains Form 2 audio/video. Reading its first
                    # 2048 bytes as an ISO file would silently change the content.
                    raise DiscInspectionError(f"ISO data uses Form 2 at LBA {sector}.")
                chunk = _sector_data(stream, sector)
                if len(chunk) != DATA_LEN:
                    raise DiscInspectionError(f"Short ISO data at LBA {sector}.")
                chunks.append(chunk)
            return b"".join(chunks)[:size]

        def both_endian(data: bytes, offset: int, width: int) -> int:
            value = int.from_bytes(data[offset : offset + width], "little")
            if value != int.from_bytes(
                data[offset + width : offset + width * 2], "big"
            ):
                raise DiscInspectionError("ISO little/big-endian copies disagree.")
            return value

        pvd = read_extent(16, DATA_LEN)
        if pvd[:7] != b"\x01CD001\x01":
            raise DiscInspectionError("No ISO9660 primary volume at LBA 16.")
        volume_sectors = both_endian(pvd, 80, 4)
        if volume_sectors != image_sectors or both_endian(pvd, 128, 2) != DATA_LEN:
            raise DiscInspectionError(
                "ISO volume size/block size disagrees with image."
            )
        root_lba = both_endian(pvd, 158, 4)
        root_size = both_endian(pvd, 166, 4)
        directory = read_extent(root_lba, root_size)
        if not directory or pvd[156] != 34 or pvd[181] != 2:
            raise DiscInspectionError("Invalid ISO root directory.")
        pos = 0
        while pos < len(directory):
            length = directory[pos]
            if length == 0:
                pos = (pos // DATA_LEN + 1) * DATA_LEN
                continue
            record = directory[pos : pos + length]
            if (
                length < 34
                or len(record) != length
                or pos % DATA_LEN + length > DATA_LEN
                or 33 + record[32] > length
                or record[1] != 0
                or record[25] & 0x80
                or record[26:28] != b"\x00\x00"
            ):
                raise DiscInspectionError(
                    "Malformed or unsupported ISO directory record."
                )
            both_endian(record, 2, 4)
            both_endian(record, 10, 4)
            name = record[33 : 33 + record[32]].decode("ascii")
            if not record[25] & 2 and not name.endswith(";1"):
                # The shared reader strips ISO version suffixes. Require the
                # version selected by SYSTEM.CNF before handing it that record.
                raise DiscInspectionError("Only ISO file version 1 is supported.")
            pos += length

        # Reuse the repository's ISO reader after checking its external-input
        # assumptions. Keep the existing RE1/RE2 extraction behavior unchanged.
        entries = {}
        for name, lba, size, is_dir in _read_dir(stream, root_lba, root_size):
            if name in (".", ".."):
                continue
            if name.upper() in entries:
                raise DiscInspectionError(f"Ambiguous ISO root entry: {name}.")
            entries[name.upper()] = (lba, size, is_dir)

        def root_file(name: str) -> tuple[bytes, dict]:
            if name not in entries or entries[name][2]:
                raise DiscInspectionError(f"Missing root file: {name}.")
            lba, size, _ = entries[name]
            data = read_extent(lba, size)
            return data, {
                "path": name,
                "lba": lba,
                "size_bytes": size,
                "sha256": hashlib.sha256(data).hexdigest(),
            }

        config, config_metadata = root_file("SYSTEM.CNF")
        boots = re.findall(
            r"^\s*BOOT\s*=\s*(.*?)\s*$",
            config.decode("ascii").rstrip("\x00"),
            re.M | re.I,
        )
        if len(boots) != 1:
            raise DiscInspectionError("SYSTEM.CNF must contain exactly one BOOT entry.")
        boot = re.fullmatch(
            r"cdrom:\\([A-Z]{4})_([0-9]{3})\.([0-9]{2});1", boots[0], re.I
        )
        if boot is None:
            raise DiscInspectionError(
                "Expected a root serial-named BOOT executable, version 1."
            )
        executable_name = f"{boot[1]}_{boot[2]}.{boot[3]}".upper()
        executable, executable_metadata = root_file(executable_name)
        if len(executable) < 0x800 or executable[:8] != b"PS-X EXE":
            raise DiscInspectionError("BOOT file lacks a complete PS-X EXE header.")
        fields = dict(
            zip(
                (
                    "initial_pc_ps1_virtual",
                    "initial_gp_ps1_virtual",
                    "load_address_ps1_virtual",
                    "payload_size_bytes",
                    "unknown_20",
                    "unknown_24",
                    "memfill_address_ps1_virtual",
                    "memfill_size_bytes",
                    "initial_sp_base_ps1_virtual",
                    "initial_sp_offset_bytes",
                ),
                struct.unpack_from("<10I", executable, 0x10),
                strict=True,
            )
        )
        if fields["payload_size_bytes"] != len(executable) - 0x800:
            raise DiscInspectionError(
                "PS-X payload size disagrees with executable length."
            )
        load = fields["load_address_ps1_virtual"]
        end = load + fields["payload_size_bytes"]
        if not load <= fields["initial_pc_ps1_virtual"] < end or end > 0x100000000:
            raise DiscInspectionError(
                "PS-X entry point is outside its nonwrapping payload."
            )
        regions = {
            b"North America": "NTSC-U",
            b"Japan": "NTSC-J",
            b"Europe": "PAL",
        }
        matching_regions = [
            region
            for area, region in regions.items()
            if executable[0x4C:].startswith(
                b"Sony Computer Entertainment Inc. for " + area + b" area"
            )
        ]
        if len(matching_regions) != 1:
            raise DiscInspectionError("PS-X region marker is not recognized.")

    return {
        "schema_version": 1,
        "cue_sha256": hashlib.sha256(cue_bytes).hexdigest(),
        "image": {
            "sha256": digest.hexdigest(),
            "size_bytes": image_bytes,
            "raw_sector_bytes": SECTOR,
            "sector_count": image_sectors,
            **forms,
        },
        "iso9660": {
            "system_id": pvd[8:40].decode("ascii").rstrip(),
            "volume_id": pvd[40:72].decode("ascii").rstrip(),
            "logical_block_bytes": DATA_LEN,
            "raw_data_offset_bytes": DATA_OFF,
            "volume_sectors": volume_sectors,
            "root_lba": root_lba,
            "root_size_bytes": root_size,
        },
        "serial": f"{boot[1]}-{boot[2]}{boot[3]}".upper(),
        "region": matching_regions[0],
        "system_cnf": config_metadata,
        "executable": {
            **executable_metadata,
            "payload_file_offset_bytes": 0x800,
            **fields,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cue", type=Path)
    args = parser.parse_args()
    try:
        result = inspect_disc(args.cue)
    except (DiscInspectionError, OSError, UnicodeError) as error:
        print(f"Disc inspection failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
