"""Reject incomplete compressed saves before publishing offline RAM captures."""

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

import extract_sav_ram


@pytest.mark.parametrize("existing_capture", [False, True])
def test_truncated_savestate_preserves_capture_and_accepts_valid_retry(
    tmp_path, monkeypatch, capsys, existing_capture
):
    data = (REPO / "tests/fixtures/slus00551_green_herb_after.sav").read_bytes()
    source = tmp_path / "input.sav"
    # zstd emits a complete RAM window before detecting this missing final byte.
    source.write_bytes(data[:-1])
    output = tmp_path / "ram.bin"
    previous = bytes([0xAA]) * extract_sav_ram.RAM_SIZE
    if existing_capture:
        output.write_bytes(previous)
    monkeypatch.setattr(sys, "argv", ["extract_sav_ram.py", str(source), str(output)])

    assert extract_sav_ram.main() == 1
    failure = capsys.readouterr()
    assert failure.out == ""
    assert "RAM not found in any frame" in failure.err
    if existing_capture:
        assert output.read_bytes() == previous
    else:
        assert not output.exists()

    source.write_bytes(data)
    assert extract_sav_ram.main() == 0
    success = capsys.readouterr()
    assert "ram base" in success.out
    assert success.err == ""
    captured = output.read_bytes()
    assert len(captured) == extract_sav_ram.RAM_SIZE
    assert captured != previous
