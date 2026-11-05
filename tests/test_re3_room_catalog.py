"""RE3-ROOM-004: synthetic MAP directories and an owned-byte-free ISO track."""

import hashlib
import json
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from games.re3.room_data import RoomFormatFailure, decode_map
from re3_room_catalog import build_catalog, main
from test_re3_room_data import synthetic_ard, synthetic_room


def synthetic_map():
    data = bytearray(2048)
    struct.pack_into("<I", data, 0, 4)
    # Section 0 has three entries, two sharing a payload offset. The other
    # payloads intentionally carry no TIM data, since image decoding is outside
    # this directory contract and game artwork must not enter fixtures.
    for index, (offset, size) in enumerate(((36, 52), (88, 4), (92, 4), (96, 4))):
        struct.pack_into("<II", data, 4 + 8 * index, offset, size)
    struct.pack_into("<I", data, 36, 3)
    for index, (offset, attribute0, attribute1) in enumerate(((28, 0, 0), (28, 7, 2), (40, 1, 0))):
        struct.pack_into("<IHH", data, 40 + index * 8, offset, attribute0, attribute1)
    return data


def synthetic_disc(tmp_path, *, room_bytes):
    payloads = {
        "SLUS_009.23": b"PS-X EXE" + bytes(2040),
        "CD_DATA/STAGE1/R100.ARD": room_bytes,
        "CD_DATA/ETC/MAP_U.MAP": bytes(synthetic_map()),
    }
    directories = {"": 20, "CD_DATA": 21, "CD_DATA/STAGE1": 22, "CD_DATA/ETC": 23}
    files, sector = {}, 24
    for path, data in payloads.items():
        files[path] = (sector, len(data))
        sector += (len(data) + 2047) // 2048
    image = bytearray(sector * 2352)

    def write_payload(lba, data):
        for index in range((len(data) + 2047) // 2048):
            part = data[index * 2048 : (index + 1) * 2048]
            start = (lba + index) * 2352 + 24
            image[start : start + len(part)] = part

    pvd = bytearray(2048)
    pvd[:7] = b"\x01CD001\x01"
    struct.pack_into("<I", pvd, 158, 20)
    struct.pack_into("<I", pvd, 166, 2048)
    write_payload(16, pvd)
    for directory, lba in directories.items():
        records = bytearray()
        for path, (extent, size) in {
            **{key: (value, 2048) for key, value in directories.items() if key},
            **files,
        }.items():
            parent, _, name = path.rpartition("/")
            if parent != directory:
                continue
            is_directory = path in directories
            encoded = (name if is_directory else name + ";1").encode("ascii")
            record = bytearray((33 + len(encoded) + 1) & ~1)
            record[0] = len(record)
            struct.pack_into("<I", record, 2, extent)
            struct.pack_into(">I", record, 6, extent)
            struct.pack_into("<I", record, 10, size)
            struct.pack_into(">I", record, 14, size)
            record[25] = 2 if is_directory else 0
            record[32] = len(encoded)
            record[33 : 33 + len(encoded)] = encoded
            records.extend(record)
        write_payload(lba, records)
    for path, data in payloads.items():
        write_payload(files[path][0], data)
    path = tmp_path / "synthetic.bin"
    path.write_bytes(image)
    return path, hashlib.sha256(payloads["SLUS_009.23"]).hexdigest()


def test_map_bounds_aliases_and_successive_aligned_records_without_artwork():
    result = decode_map(bytes(synthetic_map()) * 2)
    assert not isinstance(result, RoomFormatFailure)
    assert result["spatial_semantics"] == "unresolved"
    assert [r["offset"] for r in result["records"]] == [0, 2048]
    assert result["records"][0]["directory"] == [
        {"index": 0, "offset": 28, "attributes": [0, 0], "bounded_size": 12},
        {"index": 1, "offset": 28, "attributes": [7, 2], "bounded_size": 12},
        {"index": 2, "offset": 40, "attributes": [1, 0], "bounded_size": 12},
    ]
    assert all("payload" not in s for r in result["records"] for s in r["sections"])


@pytest.mark.parametrize("offset,value", [
    (0, 0), (0, 5), (4, 35), (8, 0), (8, 2048), (12, 87),
    (36, 0), (36, 0xFFFFFFFF), (40, 27), (40, 53),
])
def test_map_corrupt_counts_overlaps_and_out_of_section_entries_are_failures(offset, value):
    data = synthetic_map()
    struct.pack_into("<I", data, offset, value)
    assert isinstance(decode_map(data), RoomFormatFailure)


def test_map_partial_blocks_and_corrupt_later_record_are_failures():
    data = synthetic_map()
    assert isinstance(decode_map(b""), RoomFormatFailure)
    assert isinstance(decode_map(data[:-1]), RoomFormatFailure)
    assert isinstance(decode_map(data + bytes(2048)), RoomFormatFailure)


def test_map_directory_order_is_not_a_spatial_or_script_order():
    data = synthetic_map()
    struct.pack_into("<I", data, 40, 40)
    result = decode_map(data)
    assert not isinstance(result, RoomFormatFailure)
    assert [r["offset"] for r in result["records"][0]["directory"]] == [40, 28, 40]


def test_catalog_reuses_iso_reads_and_keeps_static_success_explicit(tmp_path):
    image, digest = synthetic_disc(tmp_path, room_bytes=synthetic_ard(synthetic_room()))
    result = build_catalog(image, "SLUS_009.23", digest)
    assert not isinstance(result, RoomFormatFailure)
    assert result["iso_file_count"] == 3
    assert result["unsupported"] == []
    assert result["evidence_kind"] == "offline-only"
    assert result["runtime_support"] == "unresolved"
    assert result["rooms"][0]["source_stage"] == 1
    assert result["rooms"][0]["source_room"] == 0
    assert result["rooms"][0]["room"]["completion"] == "unknown"
    assert result["map"]["status"] == "bounded"


def test_catalog_retains_corrupt_room_as_failure_instead_of_empty_items(tmp_path):
    data = synthetic_ard(synthetic_room())
    struct.pack_into("<I", data, 4, 9)
    image, digest = synthetic_disc(tmp_path, room_bytes=data)
    result = build_catalog(image, "SLUS_009.23", digest)
    assert not isinstance(result, RoomFormatFailure)
    assert result["rooms"] == []
    assert len(result["unsupported"]) == 1
    assert result["unsupported"][0]["path"] == "CD_DATA/STAGE1/R100.ARD"
    assert result["unsupported"][0]["failure"]["kind"] == "ard"


def test_catalog_retains_nested_room_and_map_failures(tmp_path):
    room = synthetic_room()
    struct.pack_into("<H", room, 184, 3)
    image, digest = synthetic_disc(tmp_path, room_bytes=synthetic_ard(room))
    data = bytearray(image.read_bytes())
    # MAP_U is the final sector in this synthetic image.
    struct.pack_into("<I", data, len(data) - 2352 + 24, 0)
    image.write_bytes(data)
    result = build_catalog(image, "SLUS_009.23", digest)
    assert not isinstance(result, RoomFormatFailure)
    assert [r["failure"]["kind"] for r in result["unsupported"]] == ["rdt", "map"]
    assert result["map"] == {"path": "CD_DATA/ETC/MAP_U.MAP", "status": "unsupported"}


def test_missing_image_is_an_explicit_failure(tmp_path):
    result = build_catalog(tmp_path / "absent.bin", "SLUS_009.23", "0" * 64)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "disc"


@pytest.mark.parametrize("failure", ["identity", "bad-hash", "missing-executable", "truncated", "pvd", "extent", "cycle"])
def test_catalog_external_disc_failures_are_modeled(tmp_path, failure):
    image, digest = synthetic_disc(tmp_path, room_bytes=synthetic_ard(synthetic_room()))
    executable_path = "SLUS_009.23"
    data = bytearray(image.read_bytes())
    if failure == "identity":
        digest = "0" * 64
    elif failure == "bad-hash":
        digest = "abc"
    elif failure == "missing-executable":
        executable_path = "OTHER.EXE"
    elif failure == "truncated":
        data.pop()
    elif failure == "pvd":
        data[16 * 2352 + 24] = 0
    elif failure == "extent":
        struct.pack_into("<I", data, 16 * 2352 + 24 + 166, 0xFFFFFFFF)
    else:
        struct.pack_into("<I", data, 20 * 2352 + 24 + 2, 20)
    image.write_bytes(data)
    assert isinstance(build_catalog(image, executable_path, digest), RoomFormatFailure)


def test_catalog_cli_writes_numeric_json_and_reports_output_failures(tmp_path, monkeypatch, capsys):
    image, digest = synthetic_disc(tmp_path, room_bytes=synthetic_ard(synthetic_room()))
    output = tmp_path / "catalog.json"
    args = ["catalog", str(image), str(output), "--executable", "SLUS_009.23", "--expected-executable-sha256", digest]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 0
    assert json.loads(output.read_text())["runtime_support"] == "unresolved"
    assert capsys.readouterr().out == "rooms=1 unsupported=0\n"
    args[2] = str(tmp_path / "missing" / "catalog.json")
    assert main() == 2
    assert "Cannot write RE3 catalog" in capsys.readouterr().err


def test_catalog_cli_distinguishes_partial_metadata_from_success(tmp_path, monkeypatch, capsys):
    data = synthetic_ard(synthetic_room())
    struct.pack_into("<I", data, 4, 9)
    image, digest = synthetic_disc(tmp_path, room_bytes=data)
    output = tmp_path / "partial.json"
    args = ["catalog", str(image), str(output), "--executable", "SLUS_009.23", "--expected-executable-sha256", digest]
    monkeypatch.setattr(sys, "argv", args)
    assert main() == 1
    assert len(json.loads(output.read_text())["unsupported"]) == 1
    assert capsys.readouterr().out == "rooms=0 unsupported=1\n"
    args[-1] = "0" * 64
    assert main() == 2
    assert "does not match" in capsys.readouterr().err


@pytest.mark.parametrize("alias", ["same-path", "symlink", "hardlink"])
def test_catalog_output_cannot_replace_owned_input_bytes(tmp_path, monkeypatch, capsys, alias):
    image, digest = synthetic_disc(tmp_path, room_bytes=synthetic_ard(synthetic_room()))
    original = image.read_bytes()
    output = image if alias == "same-path" else tmp_path / "alias.json"
    if alias == "symlink":
        output.symlink_to(image)
    elif alias == "hardlink":
        output.hardlink_to(image)
    monkeypatch.setattr(sys, "argv", [
        "catalog", str(image), str(output), "--executable", "SLUS_009.23",
        "--expected-executable-sha256", digest,
    ])
    assert main() == 2
    assert "must differ" in capsys.readouterr().err
    assert image.read_bytes() == original
