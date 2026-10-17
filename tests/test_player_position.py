"""RE1-PLAYER-003: approximate placement, fresh pose reads and explicit gaps."""

import copy
import json
import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

from build_position_bounds import camera_boundaries
from test_live_items import RamReader, fixture_ram
from track import PollStatus, poll_once

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re1.map_layout import MapLocation
from games.re1.player_position import Re1PositionLayout
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import Tracker
from tracker.player_position import ApproximatePosition, RoomOnlyPosition
from ui.map_view import map_state


@pytest.fixture
def profile():
    return Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")


def test_recorded_walk_turn_and_restore_updates_approximate_position(profile, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    reader = RamReader(ram)
    positions = []
    # Actual RE1-PLAYER-002 observations, not newly performed gameplay.
    for x, z, yaw in (
        (23850, 4649, 1352),
        (23850, 4649, 3624),
        (24543, 5260, 3624),
        (23850, 4649, 1352),
    ):
        struct.pack_into(
            "<3i", ram, profile.player_position_address - 0x80000000, x, 0, z
        )
        struct.pack_into("<H", ram, profile.player_facing_address - 0x80000000, yaw)
        assert (
            poll_once(profile, tracker, reader.read_memory).status is PollStatus.Display
        )
        position = map_state(tracker)["player_position"]
        assert position["kind"] == "approximate"
        positions.append(position["point"])
    assert positions[0] == positions[1] == positions[3]
    assert positions[2][0] > positions[0][0]
    assert positions[2][1] < positions[0][1]
    assert len(tracker.region_visits) == 1


@pytest.mark.parametrize("short", [False, True])
def test_failed_position_read_never_publishes_a_visit(profile, tmp_path, short):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    tracker = Tracker()

    def read(address, width):
        if address == profile.player_position_address:
            return MemRead(
                ok=short, data=bytes(11) if short else b"", error="injected failure"
            )
        return reader.read_memory(address, width)

    result = poll_once(profile, tracker, read)
    assert result.status is PollStatus.ReadFailure
    assert "player position" in result.text
    assert tracker.current is None and not tracker.region_visits
    assert isinstance(tracker.player_position, RoomOnlyPosition)
    assert not profile.room_observations


def test_camera_change_during_position_read_rejects_the_pose(profile, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    tracker = Tracker()

    def read(address, width):
        if address == profile.player_position_address:
            ram[profile.camera_address - 0x80000000] ^= 1
        return reader.read_memory(address, width)

    assert poll_once(profile, tracker, read).status is PollStatus.Retry
    assert tracker.current is None and not tracker.region_visits


def test_projection_keeps_estimates_inside_concave_floor_and_away_from_holes():
    location = MapLocation("floor", "00", True)
    cells = frozenset({(0, 0), (1, 0), (0, 1), (0, 2)})
    layout = Re1PositionLayout(
        {("source", 0): (location, (0, 0, 200, 300))}, {("floor", "00"): cells}
    )
    for x, z in ((100, 200), (190, 20), (-200, 500), (2147483647, -2147483648)):
        point = layout.project(("source",), 0, location, struct.pack("<3i", x, 0, z))
        assert isinstance(point, ApproximatePosition)
        assert (int(point.x), int(point.y)) in cells


def test_projection_does_not_guess_missing_conflicting_or_unoutlined_bindings(profile):
    layout = profile.position_layout
    location = profile.map_layout.select(RoomId(0, 9), 1)
    data = struct.pack("<3i", 23850, 0, 4649)
    assert isinstance(layout.project((), 1, location, data), RoomOnlyPosition)
    assert isinstance(layout.project(("missing",), 1, location, data), RoomOnlyPosition)
    assert isinstance(
        layout.project(("PSX/STAGE1/ROOM1091.RDT",), 255, location, data),
        RoomOnlyPosition,
    )
    assert isinstance(
        layout.project(
            ("PSX/STAGE1/ROOM1091.RDT",), 1, MapLocation("floor", "00", False), data
        ),
        RoomOnlyPosition,
    )
    other = Re1PositionLayout(
        {
            ("a", 0): (location, (0, 0, 100, 100)),
            ("b", 0): (location, (0, 0, 200, 200)),
        },
        layout.floors,
    )
    assert isinstance(other.project(("a", "b"), 0, location, data), RoomOnlyPosition)
    with pytest.raises(ValueError, match="complete"):
        layout.project(("missing",), 1, location, bytes(11))


def test_floor_cells_preserve_every_outline_area_and_hole(profile):
    for area in profile.map_layout.document["areas"]:
        for region in area["rooms"]:
            signed_area = (
                sum(
                    sum(
                        a[0] * b[1] - b[0] * a[1]
                        for a, b in zip(ring, ring[1:] + ring[:1])
                    )
                    for ring in region["rings"]
                )
                / 2
            )
            assert len(profile.position_layout.floors[area["id"], region["id"]]) == abs(
                signed_area
            )


@pytest.mark.parametrize("address", [None, "0x801FFFF5", "0x7FFFFFFF"])
def test_runtime_profile_requires_complete_position_block(tmp_path, address):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    if address is None:
        del raw["player_position_address_ps1"]
    else:
        raw["player_position_address_ps1"] = address
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="player_position_address_ps1"):
        Re1Profile.load(path)


@pytest.mark.parametrize(
    "defect", ["revision", "source", "bounds", "camera", "region", "missing"]
)
def test_position_metadata_must_match_its_source_and_map(profile, tmp_path, defect):
    raw = json.loads((REPO / "data/position_bounds_slus00551.json").read_text())
    raw = copy.deepcopy(raw)
    if defect == "revision":
        raw["executable_identity"] = "other revision"
    elif defect == "source":
        raw["sources"][0]["source_sha256"] = "0" * 64
    elif defect == "bounds":
        raw["sources"][0]["regions"][0]["world_bounds"] = [0, 0, 0, 100]
    elif defect == "camera":
        raw["sources"][0]["regions"][0]["cameras"] *= 2
    elif defect == "region":
        raw["sources"][0]["regions"][0]["region"] = "FF"
    else:
        raw["sources"].pop()
    path = tmp_path / "bounds.json"
    path.write_text(json.dumps(raw))
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    with pytest.raises(ValueError):
        Re1PositionLayout.load(path, manifest, profile.map_layout)


def test_boundary_parser_requires_bounded_terminated_records():
    data = bytearray(0x94 + 24)
    data[1] = 1
    struct.pack_into("<2I", data, 0x48, 0x94, len(data))
    struct.pack_into("<2H8h", data, 0x94, 9, 0, 0, 0, 100, 0, 100, 200, 0, 200)
    struct.pack_into("<2H", data, 0x94 + 20, 0xFFFF, 0xFFFF)
    assert camera_boundaries(data) == (1, {0: [(0, 0), (100, 0), (100, 200), (0, 200)]})
    data[-4:] = bytes(4)
    with pytest.raises(ValueError, match="truncated"):
        camera_boundaries(data)
