"""Invalid dump requests must not overwrite an existing capture."""

import sys
from pathlib import Path
from unittest.mock import Mock, call

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import dump_ram
from emulator.duckstation_gdb import MemRead


@pytest.mark.parametrize(
    "arguments,diagnostic",
    [
        (["--length", "0"], "--length must be positive"),
        (["--length", "-1"], "--length must be positive"),
        (["--chunk", "0"], "--chunk must be between 1 and 4096"),
        (["--chunk", "-1"], "--chunk must be between 1 and 4096"),
        (["--chunk", "4097"], "--chunk must be between 1 and 4096"),
        (["--address", "broken"], "--address must be hexadecimal"),
        (["--address", "-1"], "address range must fit 32 bits"),
        (["--address", "100000000"], "address range must fit 32 bits"),
        (["--address", "ffffffff", "--length", "2"], "address range must fit 32 bits"),
    ],
)
def test_invalid_request_preserves_capture_without_connecting(
    tmp_path, monkeypatch, capsys, arguments, diagnostic
):
    output = tmp_path / "capture.bin"
    output.write_bytes(b"existing capture")
    gdb = Mock()
    monkeypatch.setattr(dump_ram, "DuckStationGdb", gdb)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dump_ram.py",
            "--address",
            "80000000",
            "--length",
            "4",
            "--out",
            str(output),
            *arguments,
        ],
    )
    with pytest.raises(SystemExit) as exc:
        dump_ram.main()
    assert exc.value.code == 2
    assert diagnostic in capsys.readouterr().err
    assert output.read_bytes() == b"existing capture"
    gdb.assert_not_called()


@pytest.mark.parametrize(
    "address,length,chunk,requests",
    [
        (0x80000000, 5, 2, [(0x80000000, 2), (0x80000002, 2), (0x80000004, 1)]),
        (0xFFFFFFFE, 2, 4096, [(0xFFFFFFFE, 2)]),
    ],
)
def test_dump_preserves_exact_bytes_with_partial_chunks_and_boundary_addresses(
    tmp_path, monkeypatch, capsys, address, length, chunk, requests
):
    output = tmp_path / "capture.bin"
    data = bytes(range(length))
    gdb = Mock(spec=dump_ram.DuckStationGdb)
    gdb.connect.return_value = ""
    gdb.read_memory.side_effect = lambda start, width: MemRead(
        True, data[start - address : start - address + width]
    )
    monkeypatch.setattr(dump_ram, "DuckStationGdb", Mock(return_value=gdb))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dump_ram.py",
            "--address",
            f"{address:x}",
            "--length",
            str(length),
            "--chunk",
            str(chunk),
            "--out",
            str(output),
        ],
    )
    assert dump_ram.main() == 0
    assert output.read_bytes() == data
    assert gdb.read_memory.call_args_list == [call(*request) for request in requests]
    gdb.close.assert_called_once()
    assert f"wrote {length} bytes" in capsys.readouterr().out


def test_failed_read_preserves_capture_and_closes_connection(
    tmp_path, monkeypatch, capsys
):
    output = tmp_path / "capture.bin"
    output.write_bytes(b"existing capture")
    gdb = Mock(spec=dump_ram.DuckStationGdb)
    gdb.connect.return_value = ""
    gdb.read_memory.side_effect = [
        MemRead(True, b"\x01\x02"),
        MemRead(False, b"", "injected read failure"),
    ]
    monkeypatch.setattr(dump_ram, "DuckStationGdb", Mock(return_value=gdb))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "dump_ram.py",
            "--address",
            "80000000",
            "--length",
            "5",
            "--chunk",
            "2",
            "--out",
            str(output),
        ],
    )
    assert dump_ram.main() == 1
    assert output.read_bytes() == b"existing capture"
    gdb.close.assert_called_once()
    assert "read failed at 0x80000002: injected read failure" in capsys.readouterr().err
