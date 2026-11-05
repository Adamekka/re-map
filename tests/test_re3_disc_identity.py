"""RE3-ID-001: fingerprint synthetic owned-disc layouts without game assets."""

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import re3_disc_identity as identity


@pytest.fixture
def disc(tmp_path):
    def record(name, lba, size, directory=False):
        data = bytearray(33 + len(name) + (len(name) % 2 == 0))
        data[0] = len(data)
        struct.pack_into("<I", data, 2, lba)
        struct.pack_into(">I", data, 6, lba)
        struct.pack_into("<I", data, 10, size)
        struct.pack_into(">I", data, 14, size)
        data[25] = 2 if directory else 0
        data[28:32] = b"\x01\x00\x00\x01"
        data[32] = len(name)
        data[33 : 33 + len(name)] = name
        return data

    sectors = [bytearray(2048) for _ in range(32)]
    pvd = sectors[16]
    pvd[:7] = b"\x01CD001\x01"
    pvd[8:40] = b"PLAYSTATION".ljust(32)
    pvd[40:72] = b"SYNTHETIC".ljust(32)
    struct.pack_into("<I", pvd, 80, len(sectors))
    struct.pack_into(">I", pvd, 84, len(sectors))
    pvd[128:132] = b"\x00\x08\x08\x00"
    pvd[156:190] = record(b"\x00", 20, 2048, True)
    config = b"BOOT = cdrom:\\SLUS_123.45;1\r\n".ljust(256, b"\n")
    sectors[21][:256] = config
    executable = bytearray(4096)
    executable[:8] = b"PS-X EXE"
    struct.pack_into(
        "<10I",
        executable,
        0x10,
        0x80020080,
        0x80030000,
        0x80020000,
        2048,
        0x123,
        0x456,
        0x80040000,
        0x100,
        0x801FF000,
        0x20,
    )
    marker = b"Sony Computer Entertainment Inc. for North America area"
    executable[0x4C : 0x4C + len(marker)] = marker
    executable[2048:] = bytes(range(256)) * 8
    sectors[22][:] = executable[:2048]
    sectors[23][:] = executable[2048:]
    directory = b"".join(
        [
            record(b"\x00", 20, 2048, True),
            record(b"\x01", 20, 2048, True),
            record(b"SYSTEM.CNF;1", 21, len(config)),
            record(b"SLUS_123.45;1", 22, len(executable)),
        ]
    )
    sectors[20][: len(directory)] = directory
    raw = bytearray()
    for lba, payload in enumerate(sectors):
        sector = bytearray(2352)
        sector[:12] = b"\x00" + b"\xff" * 10 + b"\x00"
        sector[15] = 2
        # A non-ISO Form 2 sector proves the scan accepts mixed XA content.
        sector[18] = sector[22] = 0x20 if lba == 30 else 0
        sector[24:2072] = payload
        raw.extend(sector)
    image = tmp_path / "owned.bin"
    image.write_bytes(raw)
    cue = tmp_path / "owned.cue"
    cue.write_bytes(
        b'FILE "owned.bin" BINARY\r\n  TRACK 01 MODE2/2352\r\n    INDEX 01 00:00:00\r\n'
    )
    return cue, image, bytes(executable), config


def patch(image, offset, value):
    with image.open("r+b") as stream:
        stream.seek(offset)
        stream.write(value)


def test_identity_preserves_spaces_sizes_hashes_and_address_spaces(disc):
    cue, image, executable, config = disc
    renamed = image.with_name("owned disc.bin")
    image.rename(renamed)
    cue.write_bytes(cue.read_bytes().replace(b"owned.bin", b"owned disc.bin"))

    result = identity.inspect_disc(cue)

    assert result == {
        "schema_version": 1,
        "cue_sha256": hashlib.sha256(cue.read_bytes()).hexdigest(),
        "image": {
            "sha256": hashlib.sha256(renamed.read_bytes()).hexdigest(),
            "size_bytes": 32 * 2352,
            "raw_sector_bytes": 2352,
            "sector_count": 32,
            "form1_sectors": 31,
            "form2_sectors": 1,
        },
        "iso9660": {
            "system_id": "PLAYSTATION",
            "volume_id": "SYNTHETIC",
            "logical_block_bytes": 2048,
            "raw_data_offset_bytes": 24,
            "volume_sectors": 32,
            "root_lba": 20,
            "root_size_bytes": 2048,
        },
        "serial": "SLUS-12345",
        "region": "NTSC-U",
        "system_cnf": {
            "path": "SYSTEM.CNF",
            "lba": 21,
            "size_bytes": 256,
            "sha256": hashlib.sha256(config).hexdigest(),
        },
        "executable": {
            "path": "SLUS_123.45",
            "lba": 22,
            "size_bytes": 4096,
            "sha256": hashlib.sha256(executable).hexdigest(),
            "payload_file_offset_bytes": 0x800,
            "initial_pc_ps1_virtual": 0x80020080,
            "initial_gp_ps1_virtual": 0x80030000,
            "load_address_ps1_virtual": 0x80020000,
            "payload_size_bytes": 2048,
            "unknown_20": 0x123,
            "unknown_24": 0x456,
            "memfill_address_ps1_virtual": 0x80040000,
            "memfill_size_bytes": 0x100,
            "initial_sp_base_ps1_virtual": 0x801FF000,
            "initial_sp_offset_bytes": 0x20,
        },
    }


@pytest.mark.parametrize(
    "replacement",
    [
        b"TRACK 01 MODE1/2352",
        b"TRACK 02 MODE2/2352",
        b"TRACK 01 MODE2/2048",
        b"TRACK 01 MODE2/2352\nTRACK 02 AUDIO",
    ],
)
def test_unsupported_cue_does_not_guess_sector_layout(disc, replacement):
    cue, _, _, _ = disc
    cue.write_bytes(cue.read_bytes().replace(b"TRACK 01 MODE2/2352", replacement))
    with pytest.raises(identity.DiscInspectionError, match="Expected one BINARY"):
        identity.inspect_disc(cue)


def test_nonzero_index_does_not_guess_lba_origin(disc):
    cue, _, _, _ = disc
    cue.write_bytes(cue.read_bytes().replace(b"00:00:00", b"00:02:00"))
    with pytest.raises(identity.DiscInspectionError, match="INDEX 01 00:00:00"):
        identity.inspect_disc(cue)


@pytest.mark.parametrize("size", [0, 16 * 2352, 32 * 2352 - 1])
def test_truncated_image_is_a_modeled_failure(disc, size):
    cue, image, _, _ = disc
    image.write_bytes(image.read_bytes()[:size])
    with pytest.raises(identity.DiscInspectionError, match="short or.*partial"):
        identity.inspect_disc(cue)


@pytest.mark.parametrize(
    ("offset", "value", "message"),
    [
        (31 * 2352, b"\x01", "sync/header at LBA 31"),
        (31 * 2352 + 15, b"\x01", "sync/header at LBA 31"),
        (31 * 2352 + 20, b"\x01", "subheaders at LBA 31"),
        (16 * 2352 + 24, b"\x02", "primary volume"),
        (16 * 2352 + 24 + 84, b"\xff", "endian copies"),
        (16 * 2352 + 24 + 128, b"\x00\x04\x04\x00", "volume size/block size"),
        (
            16 * 2352 + 24 + 80,
            b"\x1f\x00\x00\x00\x00\x00\x00\x1f",
            "volume size/block size",
        ),
        (20 * 2352 + 24, b"\x01", "directory record"),
        (20 * 2352 + 24 + 32, b"\xff", "directory record"),
        (20 * 2352 + 24 + 6, b"\xff", "endian copies"),
        (20 * 2352 + 24 + 25, b"\x82", "directory record"),
        (20 * 2352 + 24 + 26, b"\x01", "directory record"),
        (20 * 2352 + 24 + 68 + 33, b"OTHER_.CNF", "Missing root file: SYSTEM.CNF"),
        (20 * 2352 + 24 + 68 + 33 + 11, b"2", "file version 1"),
        (22 * 2352 + 24, b"NO", "PS-X EXE header"),
        (22 * 2352 + 24 + 0x1C, struct.pack("<I", 4096), "payload size"),
        (22 * 2352 + 24 + 0x10, struct.pack("<I", 0x80020800), "entry point"),
        (22 * 2352 + 24 + 0x4C, b"Unrecognized", "region marker"),
    ],
)
def test_corrupt_or_unsupported_inputs_fail_explicitly(disc, offset, value, message):
    cue, image, _, _ = disc
    patch(image, offset, value)
    with pytest.raises(identity.DiscInspectionError, match=message):
        identity.inspect_disc(cue)


@pytest.mark.parametrize("lba", [16, 20, 21, 22, 23])
def test_iso_reads_reject_form2_in_metadata_or_payload(disc, lba):
    cue, image, _, _ = disc
    patch(image, lba * 2352 + 18, b"\x20")
    patch(image, lba * 2352 + 22, b"\x20")
    with pytest.raises(identity.DiscInspectionError, match=f"Form 2 at LBA {lba}"):
        identity.inspect_disc(cue)


def test_out_of_image_extent_is_rejected_before_read(disc):
    cue, image, _, _ = disc
    patch(
        image, 20 * 2352 + 24 + 114 + 2, struct.pack("<I", 32) + struct.pack(">I", 32)
    )
    with pytest.raises(identity.DiscInspectionError, match="extent exceeds image"):
        identity.inspect_disc(cue)


def test_duplicate_root_files_are_ambiguous(disc):
    cue, image, _, _ = disc
    start = 20 * 2352 + 24
    patch(image, start + 160, image.read_bytes()[start + 68 : start + 114])
    with pytest.raises(identity.DiscInspectionError, match="Ambiguous ISO root entry"):
        identity.inspect_disc(cue)


@pytest.mark.parametrize(
    "config",
    [
        b"STACK = 0X801FFF00\r\n",
        b"BOOT = cdrom:\\SLUS_123.45;1\nBOOT = cdrom:\\SLUS_123.45;1\n",
        b"BOOT = cdrom:\\SLUS_123.45;2\n",
        b"BOOT = cdrom:\\DIR\\SLUS_123.45;1\n",
        b"BOOT = cdrom:\\SLUS_009.23;1\n",
    ],
)
def test_boot_must_resolve_without_a_default_executable(disc, config):
    cue, image, _, _ = disc
    patch(image, 21 * 2352 + 24, config.ljust(256, b"\n"))
    with pytest.raises(identity.DiscInspectionError):
        identity.inspect_disc(cue)


def test_cli_publishes_only_complete_metadata(disc, monkeypatch, capsys):
    cue, _, _, _ = disc
    monkeypatch.setattr(sys, "argv", ["re3_disc_identity.py", str(cue)])
    assert identity.main() == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out) == identity.inspect_disc(cue)
    assert str(cue.parent) not in output.out
    assert "PS-X EXE" not in output.out


@pytest.mark.parametrize("failure", ["missing_image", "invalid_cue", "invalid_utf8"])
def test_cli_failure_has_no_partial_json_or_traceback(
    disc, monkeypatch, capsys, failure
):
    cue, image, _, _ = disc
    if failure == "missing_image":
        image.unlink()
    elif failure == "invalid_utf8":
        cue.write_bytes(b"\xff")
    else:
        cue.write_bytes(b"unsupported")
    monkeypatch.setattr(sys, "argv", ["re3_disc_identity.py", str(cue)])
    assert identity.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.startswith("Disc inspection failed: ")
    assert "Traceback" not in output.err
