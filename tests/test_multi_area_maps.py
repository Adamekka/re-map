# Tests need explicit source/tool roots because this repository is not installed.
"""Floor selection, entry-only reveal and explicit missing-map failures."""

import copy
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

from test_live_items import RamReader, fixture_ram
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.map_layout import MapLocation, MapUnavailable, Re1MapLayout
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import DoorDetail, ItemDetail, Tracker
from ui.map_view import map_state


@pytest.fixture
def layout():
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    return Re1MapLayout.load(
        REPO / "data/floor_plans_slus00551.json",
        raw["profile_id"],
        raw["executable_identity"],
    )


@pytest.mark.parametrize(
    "stage,room,camera,area,region",
    [
        (0, 9, 0, "mansion1f", "09"),
        (5, 9, 0, "mansion1f", "09"),
        (0, 7, 2, "mansion1f", "07"),
        (0, 7, 3, "mansion1f", "1D"),
        (0, 7, 6, "mansion1f", "1D"),
        (0, 7, 7, "mansion1f", "07"),
        (0, 15, 3, "mansion1f", "1E"),
        (0, 15, 5, "mansion1f", "0F"),
        (5, 16, 0, "mansionb1", "1E"),
        (5, 16, 1, "mansion1f", "10"),
        (1, 15, 2, "mansion2f", "1D"),
        (6, 15, 5, "mansion2f", "1D"),
        (6, 15, 3, "mansion2f", "0F"),
        (1, 12, 3, "mansion2f", "0C"),
        (6, 12, 4, "mansion1f", "1F"),
        (6, 12, 7, "mansion1f", "1F"),
        (6, 12, 8, "mansion2f", "0C"),
        (6, 26, 0, "mansionb1", "1A"),
        (2, 5, 0, "courtyard1f", "05"),
        (2, 6, 0, "courtyardb1", "06"),
        (2, 11, 4, "courtyardb1", "0B"),
        (2, 11, 5, "courtyardb1", "11"),
        (2, 11, 7, "courtyardb1", "0B"),
        (2, 15, 6, "courtyardb1", "12"),
        (3, 12, 0, "guardhouse1f", "0C"),
        (3, 13, 0, "guardhouseb1", "0D"),
        (4, 1, 0, "laboratoryb1", "01"),
        (4, 2, 0, "laboratoryb2", "02"),
        (4, 5, 0, "laboratoryb3", "05"),
        (4, 7, 3, "laboratoryb3", "16"),
        (4, 7, 4, "laboratoryb3", "07"),
        (4, 19, 0, "laboratoryb4", "13"),
    ],
)
def test_native_area_and_camera_boundaries(layout, stage, room, camera, area, region):
    assert layout.select(RoomId(stage, room), camera) == MapLocation(area, region, True)


def test_all_supported_source_rooms_have_explicit_locations_and_aliases(layout):
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    rooms = {RoomId(row["room_main"], row["room_sub"]) for row in manifest["rooms"]}
    assert len(rooms) == 159
    for room in rooms:
        for camera in range(256):
            selected = layout.select(room, camera)
            assert isinstance(selected, MapLocation)
            plan = next(
                plan for plan in layout.document["areas"] if plan["id"] == selected.area
            )
            entries = plan["rooms"] if selected.outlined else plan["unoutlined_rooms"]
            entry = next(entry for entry in entries if entry["id"] == selected.region)
            assert str(room) in entry["room_ids"]
    assert len(layout.document["areas"]) == 11
    assert sum(len(plan["rooms"]) for plan in layout.document["areas"]) == 118
    assert sum(len(plan["doors"]) for plan in layout.document["areas"]) == 108


def test_undrawn_native_rooms_remain_explicit(layout):
    for main, sub in ((6, 0), (2, 3), (2, 16), (4, 13), (4, 21)):
        selected = layout.select(RoomId(main, sub), 0)
        assert isinstance(selected, MapLocation) and not selected.outlined
    assert isinstance(layout.select(RoomId(0, 255), 0), MapUnavailable)


def test_floor_history_keeps_only_entered_regions_and_retains_item_door_states(layout):
    tracker = Tracker()
    for rid in (RoomId(0, 9), RoomId(1, 3), RoomId(3, 5), RoomId(0, 9)):
        selected = layout.select(rid, 0)
        assert isinstance(selected, MapLocation) and selected.outlined
        tracker.mark_current(rid)
        tracker.update_room_items(rid, 1, 0, True, True, False)
        tracker.rooms[str(rid)].items = (ItemDetail("Ink Ribbon", "available", 3),)
        tracker.current_region = f"{selected.area}:{selected.region}"
        tracker.region_visits[tracker.current_region] = str(rid)
        tracker.doors = (
            DoorDetail(rid, RoomId(rid.stage, 14), "LOCKED", "Requires a key"),
        )
        payload = map_state(tracker)
        assert payload["area"] == selected.area
        assert [entry["id"] for entry in payload["rooms"]] == [selected.region]
        assert payload["rooms"][0]["items"][0]["label"] == "Ink Ribbon"
        assert payload["doors"][0]["source"] == str(rid)
        assert payload["doors"][0]["state"] == "LOCKED"
        assert not payload["doors"][0]["target_visited"]
    assert len(tracker.region_visits) == 3


def test_camera_change_during_snapshot_never_reveals_a_region(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    count = 0

    def read(address, width):
        nonlocal count
        if address == profile.camera_address:
            count += 1
            ram[address - 0x80000000] = count
        return reader.read_memory(address, width)

    tracker = Tracker()
    result = poll_once(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert "camera changed" in result.text
    assert not tracker.rooms and not tracker.region_visits


def test_map_acquisition_never_reveals_other_regions(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    for value in (0, 255, 0):
        ram[0xC871C] = value
        assert (
            poll_once(profile, tracker, RamReader(ram).read_memory).status
            is PollStatus.Display
        )
        assert [row["id"] for row in map_state(tracker)["rooms"]] == ["09"]


@pytest.mark.parametrize(
    "defect",
    [
        "revision",
        "missing-area",
        "overlap",
        "missing-region",
        "coordinate",
        "detail-coordinate",
        "detail-segment",
        "missing-details",
        "empty-bindings",
        "wrong-alias",
    ],
)
def test_invalid_catalog_fails_startup(layout, tmp_path, defect):
    raw = copy.deepcopy(layout.document)
    if defect == "revision":
        raw["profile_id"] = "other"
    elif defect == "missing-area":
        del raw["areas"]
    elif defect == "overlap":
        row = next(row for row in raw["locations"] if row["camera_overrides"])
        row["camera_overrides"].append(row["camera_overrides"][0])
    elif defect == "missing-region":
        raw["locations"][0]["default"]["region"] = "FF"
    elif defect == "coordinate":
        raw["areas"][0]["rooms"][0]["rings"][0][0] = [float("inf"), 0]
    elif defect == "detail-coordinate":
        raw["areas"][0]["rooms"][0]["detail_segments"] = [[[0, 0], [float("inf"), 1]]]
    elif defect == "detail-segment":
        raw["areas"][0]["rooms"][0]["detail_segments"] = [[[0, 0]]]
    elif defect == "missing-details":
        del raw["areas"][0]["rooms"][0]["detail_segments"]
    elif defect == "empty-bindings":
        raw["locations"] = []
    elif defect == "wrong-alias":
        raw["areas"][0]["rooms"][0]["room_ids"] = ["00-ff"]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError):
        Re1MapLayout.load(
            path, layout.document["profile_id"], layout.document["executable_identity"]
        )
