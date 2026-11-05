"""RE3-NATIVE-001/002/003: synthetic contracts never admit campaign gameplay."""

import hashlib
import json
import struct
import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

import re3_native_contracts as native
from test_re3_room_data import synthetic_ard, synthetic_room

from games.re3.room_data import RoomFormatFailure, decode_ard, decode_room


@pytest.fixture
def coherent(monkeypatch):
    room = bytes(synthetic_room())
    ard = bytes(synthetic_ard(room))
    source = native.RoomSource("CD_DATA/STAGE1/R100.ARD", 1, 0, 24, len(ard), room)
    executable = bytearray(0xA0000)
    for stage in range(7):
        table = 0x8009DE30 + stage * 0x40
        struct.pack_into("<I", executable, 0x800 + 0x9DFD0 - 0x10000 + stage * 4, table)
        struct.pack_into("<H", executable, 0x800 + table - 0x80010000, 0x100 + stage)
        struct.pack_into(
            "<2I",
            executable,
            0x800 + 0x946A4 - 0x10000 + 8 * (0x100 + stage),
            len(ard) | 0xA5000000,
            source.ard_lba + stage | 0xC3000000,
        )
    ram = bytearray(native.RAM_SIZE)
    for index, address in enumerate(native.CODE_WINDOWS):
        window = bytes(range(index * 32, index * 32 + 32))
        offset = 0x800 + address - 0x80010000
        executable[offset : offset + 32] = window
        ram[address - 0x80000000 : address - 0x80000000 + 32] = window
    # The synthetic hash seam runs the real mandatory gate without committing
    # any owned executable bytes or accepting a production fixture fallback.
    monkeypatch.setattr(
        native, "EXECUTABLE_SHA256", hashlib.sha256(executable).hexdigest()
    )
    pointer = 0x80100000
    base = pointer - 0x80000000
    ram[base : base + len(room)] = room
    ram[base] = 100
    decoded = decode_room(room)
    for index, word in enumerate(decoded["section_words"][:21]):
        struct.pack_into(
            "<I",
            ram,
            base + 8 + index * 4,
            (word + pointer) & 0xFFFFFFFF if word else 0,
        )
    for camera in decoded["cameras"]:
        struct.pack_into(
            "<I", ram, base + camera["offset"] + 28, camera["mask_offset"] + pointer
        )
    # Slot 21 is a later runtime work pointer, outside the source witness.
    struct.pack_into("<I", ram, base + 8 + 21 * 4, 0x80180000)
    struct.pack_into("<2I", ram, 0xCC86C, pointer, pointer)
    return SimpleNamespace(
        executable=bytes(executable), ram=ram, source=source, ard=ard, base=base
    )


def test_source_witness_and_native_selector_never_imply_campaign_or_hard(coherent):
    before = bytes(coherent.ram)
    result = native.audit_capture(coherent.executable, before, (coherent.source,))
    assert result["selected_source_paths"] == [coherent.source.path]
    assert result["source_matches"][0]["path"] == coherent.source.path
    assert result["source_matches"][0]["native_file_index"] == 0x100
    assert result["source_matches"][0]["initializer_different_bytes"] == 0
    assert result["rejection_evidence"] == []
    assert result["campaign_admission"] == result["hard_identity"] == "unresolved"
    assert bytes(coherent.ram) == before
    assert not any(key in result for key in ("visited", "items", "doors", "completion"))


@pytest.mark.parametrize("size", [0, native.RAM_SIZE - 1, native.RAM_SIZE + 1])
def test_capture_size_is_required(coherent, size):
    ram = (bytes(coherent.ram) + b"x")[:size] if size else b""
    with pytest.raises(native.ContractError, match="exactly 2 MiB"):
        native.audit_capture(coherent.executable, ram, (coherent.source,))


def test_executable_gate_is_not_replaced_by_matching_sampled_windows(coherent):
    changed = coherent.executable + b"x"
    with pytest.raises(native.ContractError, match="required SLUS"):
        native.audit_capture(changed, coherent.ram, (coherent.source,))


@pytest.mark.parametrize("address", native.CODE_WINDOWS)
def test_each_runtime_code_window_is_mandatory(coherent, address):
    coherent.ram[address - 0x80000000] ^= 1
    with pytest.raises(native.ContractError, match="Capture code window differs"):
        native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))


@pytest.mark.parametrize("pointer", [0, 0xA0100000, 0x801FFFF0, 0x80100001])
def test_bad_loaded_pointer_is_rejection_evidence(coherent, pointer):
    struct.pack_into("<I", coherent.ram, 0xCC86C, pointer)
    result = native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))
    assert "rdt-pointer-outside-cached-main-ram" in result["rejection_evidence"]
    assert result["source_matches"] == []
    assert result["campaign_admission"] == "unresolved"


def test_disagreeing_allocation_is_not_hidden_by_a_matching_source(coherent):
    struct.pack_into("<I", coherent.ram, 0xCC870, 0x80110000)
    result = native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))
    assert len(result["source_matches"]) == 1
    assert "rdt-pointer-allocation-disagree" in result["rejection_evidence"]


@pytest.mark.parametrize("word", [97, 189, 0xDEADBEEF])
def test_opaque_slot_two_is_relocated_but_never_used_as_a_section_boundary(
    coherent, word
):
    room = bytearray(coherent.source.rdt)
    struct.pack_into("<I", room, 16, word)
    source = replace(coherent.source, rdt=bytes(room))
    pointer = coherent.base + 0x80000000
    struct.pack_into(
        "<I", coherent.ram, coherent.base + 16, (word + pointer) & 0xFFFFFFFF
    )
    result = native.audit_capture(coherent.executable, coherent.ram, (source,))
    assert len(result["source_matches"]) == 1
    struct.pack_into("<I", coherent.ram, coherent.base + 16, 0)
    result = native.audit_capture(coherent.executable, coherent.ram, (source,))
    assert result["source_matches"] == []


@pytest.mark.parametrize("stage,room", [(-1, 0), (0, -1), (1, 0), (0, 255)])
def test_signed_selectors_must_agree_with_the_loaded_source(coherent, stage, room):
    struct.pack_into("<2h", coherent.ram, 0xD1F76, stage, room)
    result = native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))
    assert (result["stage_i16"], result["room_i16"]) == (stage, room)
    assert result["selected_source_paths"] == []
    assert "selectors-disagree-with-loaded-source" in result["rejection_evidence"]


@pytest.mark.parametrize("camera", [-1, 1, 32767])
def test_camera_is_bounded_by_the_source_table(coherent, camera):
    struct.pack_into("<h", coherent.ram, 0xD1F7A, camera)
    result = native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))
    assert result["camera_i16"] == camera
    assert "camera-outside-source-table" in result["rejection_evidence"]


@pytest.mark.parametrize("offset", [1, 8 + 7 * 4, 96, 124, 128])
def test_header_and_independent_geometry_witnesses_are_required(coherent, offset):
    coherent.ram[coherent.base + offset] ^= 1
    result = native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))
    assert result["source_matches"] == []
    assert "no-unique-loaded-source-witness" in result["rejection_evidence"]


def test_script_changes_are_reported_without_becoming_source_identity_or_gameplay(
    coherent,
):
    initial = bytes(coherent.ram)
    before = native.audit_capture(coherent.executable, initial, (coherent.source,))
    coherent.ram[coherent.base + 188] ^= 1
    after = native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))
    assert after["source_matches"][0]["initializer_different_bytes"] == 1
    assert after["campaign_admission"] == after["hard_identity"] == "unresolved"
    assert (
        native.audit_capture(coherent.executable, initial, (coherent.source,)) == before
    )


def test_recorded_input_remains_rejected_with_valid_source_and_pose_independent_fields(
    coherent,
):
    struct.pack_into("<I", coherent.ram, 0xCC858, 0x10000000)
    coherent.ram[0xC79AE] = 2
    struct.pack_into("<I", coherent.ram, 0xC79B0, 123)
    struct.pack_into("<2I", coherent.ram, 0xD1F2C, 0x140, 1)
    result = native.audit_capture(coherent.executable, coherent.ram, (coherent.source,))
    assert result["recorded_input_bit_set"]
    assert result["recorded_input_phase_u8"] == 2
    assert result["recorded_input_index_u32"] == 123
    assert result["saved_status_word_u32"] == 0x140
    assert result["new_game_option_bit_set"]
    assert result["rejection_evidence"] == ["native-recorded-input-path-selected"]
    assert result["campaign_admission"] == result["hard_identity"] == "unresolved"


@pytest.mark.parametrize("change", ["lba", "size", "room", "duplicate", "invalid-rdt"])
def test_sources_must_agree_with_native_file_tables_and_bounded_room_data(
    coherent, change
):
    source = coherent.source
    if change == "lba":
        sources = (replace(source, ard_lba=source.ard_lba + 1),)
    elif change == "size":
        sources = (replace(source, ard_size=source.ard_size + 1),)
    elif change == "room":
        sources = (replace(source, room_number=1),)
    elif change == "duplicate":
        sources = (source, source)
    else:
        sources = (replace(source, rdt=b"invalid"),)
    with pytest.raises(native.ContractError):
        native.audit_capture(coherent.executable, coherent.ram, sources)


@pytest.mark.parametrize("pointer", [0x8000FFFC, 0x80100000, 0x8009DE31])
def test_native_table_pointer_cannot_read_executable_header_or_outside_payload(
    coherent, monkeypatch, pointer
):
    executable = bytearray(coherent.executable)
    struct.pack_into("<I", executable, 0x800 + 0x9DFD0 - 0x10000, pointer)
    monkeypatch.setattr(
        native, "EXECUTABLE_SHA256", hashlib.sha256(executable).hexdigest()
    )
    with pytest.raises(native.ContractError, match="outside the executable payload"):
        native.audit_capture(bytes(executable), coherent.ram, (coherent.source,))


def test_two_independent_source_matches_remain_ambiguous(coherent):
    other = replace(
        coherent.source, path="CD_DATA/STAGE2/R200.ARD", stage_digit=2, ard_lba=25
    )
    result = native.audit_capture(
        coherent.executable, coherent.ram, (coherent.source, other)
    )
    assert len(result["source_matches"]) == 2
    assert "no-unique-loaded-source-witness" in result["rejection_evidence"]
    assert result["campaign_admission"] == "unresolved"


@pytest.fixture
def cli_case(coherent, tmp_path, monkeypatch):
    executable = tmp_path / "synthetic.exe"
    executable.write_bytes(coherent.executable)
    capture = tmp_path / "capture.ram"
    capture.write_bytes(coherent.ram)
    image = tmp_path / "synthetic.bin"
    track = bytearray((24 + len(coherent.ard) // 2048) * 2352)
    for offset in range(0, len(coherent.ard), 2048):
        start = (24 + offset // 2048) * 2352 + 24
        track[start : start + 2048] = coherent.ard[offset : offset + 2048]
    image.write_bytes(track)
    catalog = {
        "rooms": [
            {
                "path": coherent.source.path,
                "source_stage": 1,
                "source_room": 0,
                "lba": 24,
                "size": len(coherent.ard),
                "sha256": hashlib.sha256(coherent.ard).hexdigest(),
                "container": decode_ard(coherent.ard),
            }
        ],
        "unsupported": [],
    }
    # Isolate the already-tested disc catalog boundary. Source-sector reads,
    # hashes, source extraction and capture audits remain real in these CLI tests.
    monkeypatch.setattr(native, "build_catalog", lambda *args: catalog)
    argv = ["audit", str(image), str(executable), str(capture)]
    monkeypatch.setattr(sys, "argv", argv)
    return SimpleNamespace(
        image=image, executable=executable, capture=capture, catalog=catalog, argv=argv
    )


def test_cli_emits_numeric_metadata_without_mutating_inputs(cli_case, capsys):
    before = [
        path.read_bytes()
        for path in (cli_case.image, cli_case.executable, cli_case.capture)
    ]
    assert native.main() == 0
    output = capsys.readouterr()
    assert output.err == ""
    result = json.loads(output.out)
    assert result["native_source_table_rows_checked"] == 1
    assert result["status"] == "candidate-offline-audit"
    assert result["captures"][0]["source_matches"]
    assert result["captures"][0]["campaign_admission"] == "unresolved"
    assert [
        path.read_bytes()
        for path in (cli_case.image, cli_case.executable, cli_case.capture)
    ] == before


@pytest.mark.parametrize(
    "failure",
    [
        "missing-file",
        "unsupported-source",
        "changed-ard",
        "later-bad-capture",
        "catalog-failure",
    ],
)
def test_cli_failure_emits_no_partial_json(
    cli_case, tmp_path, monkeypatch, capsys, failure
):
    if failure == "missing-file":
        cli_case.executable.unlink()
    elif failure == "unsupported-source":
        cli_case.catalog["unsupported"].append({"path": "missing"})
    elif failure == "changed-ard":
        data = bytearray(cli_case.image.read_bytes())
        data[24 * 2352 + 24] ^= 1
        cli_case.image.write_bytes(data)
    elif failure == "later-bad-capture":
        bad = tmp_path / "bad.ram"
        bad.write_bytes(b"incomplete")
        cli_case.argv.append(str(bad))
    else:
        monkeypatch.setattr(
            native,
            "build_catalog",
            lambda *args: RoomFormatFailure("disc", 0, "invalid disc"),
        )
    assert native.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "RE3 native contract audit failed:" in output.err
