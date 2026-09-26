"""Regression test from donated save fixtures. See RE1-PICKUP-003."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "tools"))

from extract_sav_ram import _decompress, _find_frames, _find_ram_base, RAM_SIZE  # noqa: E402


def ram_of(name: str) -> bytes:
    data = (REPO / "tests" / "fixtures" / name).read_bytes()
    assert data[:4] == b"DUCC", "fixture magic"
    for off in sorted(_find_frames(data), reverse=True):
        blob = _decompress(data[off:])
        if blob is None or len(blob) < RAM_SIZE:
            continue
        base = _find_ram_base(blob)
        if base is None:
            continue
        return blob[base : base + RAM_SIZE]
    raise AssertionError("RAM not found in fixture")


def test_chemical_pickup_clears_one_bit():
    before = ram_of("slus00551_chemical_before.sav")
    after = ram_of("slus00551_chemical_after.sav")
    # Same room both sides.
    assert (before[0xC8660], before[0xC8661]) == (0x00, 0x18)
    assert (after[0xC8660], after[0xC8661]) == (0x00, 0x18)
    # Exactly the chemical bit flips 1 -> 0.
    assert before[0xC86DE] == 0xFF
    assert after[0xC86DE] == 0xFB
    # Inventory gains one chemical in slot 6, ink untouched.
    assert after[0xC878E] == 0x26 and after[0xC878F] == 1
    assert before[0xC878E] == 0x00
    assert after[0xC878A] == before[0xC878A] == 0x2F
