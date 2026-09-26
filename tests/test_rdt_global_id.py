"""RE1 item opcode field layout regression; see RE1-RDT-002."""

import json
import struct
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))


def test_item_global_id_uses_opcode_byte_22(tmp_path: Path):
    from build_item_table import _scan_rdt

    rdt = bytearray(0x100 + 2 + 26 + 2 + 4)
    offsets = [0] * 19
    offsets[6] = 0x100
    offsets[7] = 0x100 + 2 + 26 + 2
    offsets[8] = offsets[7] + 2
    offsets[9] = len(rdt)
    struct.pack_into("<19I", rdt, 0x48, *offsets)
    struct.pack_into("<H", rdt, 0x100, 28)
    item = memoryview(rdt)[0x102 : 0x102 + 26]
    item[0] = 0x18
    item[1] = 5
    struct.pack_into("<4h", item, 2, 100, 200, 10, 10)
    item[10] = 0x44
    item[11] = 1
    item[16] = 0xA5
    item[22] = 111

    assert _scan_rdt(rdt)["items"][0]["gid"] == 111
    path = tmp_path / "room.rdt"
    path.write_bytes(rdt)
    output = subprocess.run(
        [sys.executable, str(REPO / "tools/scan_scd.py"), str(path)],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    assert "type=0x44 amt=1 gid=111" in output


def test_generated_ids_and_controlled_flag_keys():
    from track_offline import KNOWN_FLAGS

    rooms = json.loads((REPO / "data/item_table_slus00551.json").read_text())["rooms"]
    expected = {
        "ROOM1070.RDT": (131, "0x2f", 39),
        "ROOM1090.RDT": (5, "0x44", 111),
        "ROOM1180.RDT": (1, "0x26", 13),
    }
    for suffix, (item_id, item_type, global_id) in expected.items():
        rows = [
            item
            for room in rooms
            if room["file"].endswith(suffix)
            for item in room["items"]
            if item["id"] == item_id and item["type"] == item_type
        ]
        assert rows
        assert {row["gid"] for row in rows} == {global_id}

    art_items = json.loads((REPO / "data/room_items_slus00551.json").read_text())
    assert art_items["rooms"][0]["items"][0]["global_id"] == 39
    assert set(KNOWN_FLAGS) == {(0, 9, "0x44", 111), (0, 0x18, "0x26", 13)}
