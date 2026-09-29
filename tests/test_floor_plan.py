"""Numeric map extraction invariants; fixtures contain no game assets."""

import json
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))

from build_floor_plan import extract_floor_plan


def tim(width, height, cells):
    palette = struct.pack("<I4H", 524, 0, 480, 256, 1) + bytes(512)
    pixels = bytearray(width * height)
    for (x, y), index in cells.items():
        pixels[y * width + x] = index
    image = struct.pack("<I4H", 12 + len(pixels), 0, 0, width // 2, height)
    return struct.pack("<II", 16, 9) + palette + image + pixels


def test_floor_contour_preserves_a_hole_and_places_label_on_floor():
    cells = {
        (x, y): 16
        for y in range(1, 6)
        for x in range(1, 6)
        if x in (1, 5) or y in (1, 5)
    }
    plan = extract_floor_plan(tim(8, 8, cells))
    assert plan["bounds"] == [1, 1, 5, 5]
    assert len(plan["rooms"]) == 1
    room = plan["rooms"][0]
    assert room["ring_roles"] == ["outer", "hole"]
    assert {tuple(point) for point in room["rings"][0]} == {
        (1, 1),
        (6, 1),
        (6, 6),
        (1, 6),
    }
    assert {tuple(point) for point in room["rings"][1]} == {
        (2, 2),
        (5, 2),
        (5, 5),
        (2, 5),
    }
    assert (int(room["label"][0]), int(room["label"][1])) in cells


def test_door_pairs_preserve_room_ownership_and_wall_orientation():
    cells = {(x, y): 16 for y in range(1, 6) for x in range(1, 4)}
    cells.update({(x, y): 22 for y in range(1, 6) for x in range(7, 10)})
    cells.update({(4, 3): 13, (5, 3): 13, (6, 3): 19})
    plan = extract_floor_plan(tim(12, 8, cells))
    assert len(plan["doors"]) == 1
    door = plan["doors"][0]
    assert door["id"] == "00-01"
    assert door["rooms"] == ["00", "01"]
    assert door["segment"] == [[5.75, 3], [5.75, 4]]
    assert door["sides"] == [
        {"room": "00", "point": [5.0, 3.5]},
        {"room": "01", "point": [6.5, 3.5]},
    ]


def test_unpaired_door_is_an_explicit_failure():
    data = tim(8, 8, {(2, 2): 16, (3, 2): 13})
    with pytest.raises(ValueError, match="unpaired door marker"):
        extract_floor_plan(data)


def test_door_with_no_owned_floor_is_an_explicit_failure():
    data = tim(8, 8, {(2, 2): 16, (3, 2): 19})
    with pytest.raises(ValueError, match="doors without a floor"):
        extract_floor_plan(data)


@pytest.mark.parametrize("data", [b"", bytes(20), tim(8, 8, {(1, 1): 16})[:-1]])
def test_invalid_tim_is_an_explicit_failure(data):
    with pytest.raises(ValueError):
        extract_floor_plan(data)


def test_pinned_floor_plan_and_rdt_links_agree():
    plan = json.loads((REPO / "data/mansion1f_floor_plan.json").read_text())
    table = json.loads((REPO / "data/item_table_slus00551.json").read_text())
    assert plan["bounds"] == [1, 1, 157, 92]
    assert len(plan["rooms"]) == 32
    assert len(plan["doors"]) == 28
    rooms = {room["id"]: room for room in plan["rooms"]}
    # These distinct architectural positions distinguish an actual floor plan
    # from the old topology layout without keeping a reference game image.
    assert rooms["06"]["label"][0] < rooms["07"]["label"][0]
    assert rooms["07"]["label"][1] > rooms["09"]["label"][1]
    assert rooms["18"]["label"][0] > rooms["0B"]["label"][0]
    physical_links = {
        (source, target)
        for door in plan["doors"]
        for source, target in (door["rooms"], reversed(door["rooms"]))
    }
    rdt_links = {
        (room["file"][-7:-5], f"{door['next_room']:02X}")
        for room in table["rooms"]
        if room["file"].startswith("PSX/STAGE1/")
        for door in room.get("doors", [])
        if door["next_stage"] == 0
    }
    assert len(rdt_links) == 54
    assert rdt_links <= physical_links
    assert physical_links - rdt_links == {("10", "04"), ("19", "0A")}
    for door in plan["doors"]:
        assert set(door["rooms"]) <= rooms.keys()
        assert {half["room"] for half in door["sides"]} == set(door["rooms"])
        for direction in door["directions"]:
            assert bool(direction["rdt_sites"]) == (
                (direction["from"], direction["to"]) in rdt_links
            )
