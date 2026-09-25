import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re1.re1_profile import Re1Profile


def test_profile_loads_candidate_addresses():
    p = Re1Profile.load(Path(__file__).resolve().parents[1] / "profiles" / "re1_ntsc_u_slus00170.json")
    assert p.has_room_addresses()
    assert p.stage_address == 0x800C8660
    assert p.room_address == 0x800C8661
    assert p.camera_address == 0x800C8662


def test_profile_without_addresses_refuses():
    p = Re1Profile.load(Path(__file__).resolve().parents[1] / "profiles" / "re1_ntsc_u.json")
    assert not p.has_room_addresses()


def test_bit_test_mansion_save_ink_ribbon():
    # 0x0c86dd Bit1 per user map. Mask 0x02.
    assert Re1Profile.is_bit_set(0x02, 0x02) is True
    assert Re1Profile.is_bit_set(0x00, 0x02) is False
    assert Re1Profile.is_bit_set(0xFF, 0x02) is True
