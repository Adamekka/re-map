"""RE2-PLAYER-002: projection/geometry contracts, not new gameplay evidence."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from games.re2.map_layout import Re2MapLayout, Re2MapProjection
from games.re2.re2_profile import Re2Profile
from tracker.player_position import ApproximatePosition, RoomOnlyPosition

POSITION_OBSERVATIONS = json.loads(
    (ROOT / "tests/fixtures/re2/position-observations.json").read_text()
)["observations"]


@pytest.mark.parametrize(
    "observation", POSITION_OBSERVATIONS, ids=lambda row: row["label"]
)
def test_captured_position_references(observation):
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00421.json")
    x, _, z = observation["world_position"]
    result = profile.map_layout.project(
        observation["area"], observation["region"], x, z
    )
    expected = observation["marker"]
    if expected["kind"] == "approximate":
        assert isinstance(result, ApproximatePosition)
        assert (result.x, result.y) == pytest.approx(expected["point"])
    else:
        assert expected["kind"] == "room"
        assert (
            isinstance(result, RoomOnlyPosition) and result.reason == expected["reason"]
        )


@pytest.fixture
def position_document():
    return {
        "schema": 1,
        "profile_id": "position-test",
        "executable_identity": "test",
        "stage_modulus": 256,
        "areas": [
            {
                "id": "a",
                "rooms": [
                    {
                        "id": "r",
                        "name": "Test room",
                        "room_ids": ["00-01"],
                        "rings": [
                            [[0, 0], [10, 0], [10, 10], [0, 10]],
                            [[3, 3], [3, 7], [7, 7], [7, 3]],
                            [[20, 0], [24, 0], [24, 4], [20, 4]],
                        ],
                        "ring_roles": ["outer", "hole", "outer"],
                        "label": [1, 1],
                        "detail_segments": [],
                        "world_origin": [0, 0],
                    }
                ],
                "doors": [],
            }
        ],
        "locations": [
            {
                "room": "00-01",
                "floor_min": 0,
                "floor_max": 255,
                "conditions": [],
                "area": "a",
                "region": "r",
            }
        ],
    }


@pytest.mark.parametrize(
    "x,y,placed",
    [
        (2, 2, True),
        (21, 2, True),
        (5, 5, False),
        (15, 2, False),
        (-1, 2, False),
        (0, 2, False),
        (3, 5, False),
    ],
)
def test_position_respects_holes_islands_and_boundaries(
    tmp_path, position_document, x, y, placed
):
    path = tmp_path / "map.json"
    path.write_text(json.dumps(position_document))
    layout = Re2MapLayout.load(
        path, "position-test", "test", {"00-01": {}}, Re2MapProjection(0, 1)
    )
    result = layout.project("a", "r", x, -y)
    if placed:
        assert result == ApproximatePosition(x, y)
    else:
        assert isinstance(result, RoomOnlyPosition) and result.reason
    assert isinstance(layout.project("unmapped", "00-01", x, -y), RoomOnlyPosition)


@pytest.mark.parametrize(
    "origin", [None, [], [0], [0, 0, 0], [True, 0], [0.5, 0], [32768, 0]]
)
def test_native_origin_is_required_validated_metadata(
    tmp_path, position_document, origin
):
    entry = position_document["areas"][0]["rooms"][0]
    if origin is None:
        del entry["world_origin"]
    else:
        entry["world_origin"] = origin
    path = tmp_path / "map.json"
    path.write_text(json.dumps(position_document))
    with pytest.raises(ValueError, match="native origin"):
        Re2MapLayout.load(
            path, "position-test", "test", {"00-01": {}}, Re2MapProjection(0, 1)
        )


@pytest.mark.parametrize(
    "bias,scale",
    [
        (True, 450),
        ("28000", 450),
        (2**31, 450),
        (28000, False),
        (28000, 0),
        (28000, -1),
    ],
)
def test_projection_rejects_invalid_required_configuration(bias, scale):
    with pytest.raises(ValueError, match="projection"):
        Re2MapProjection(bias, scale)


def test_native_projection_keeps_subpixels_and_signed_coordinates():
    projection = Re2MapProjection(28000, 450)
    assert projection.project((0, 0), -28000, -28000) == (0, 0)
    assert projection.project((0, 0), -28225, -27775) == (-0.5, -0.5)
    assert projection.project((0, 0), -27775.5, -27775.5) == pytest.approx(
        (0.4988888888888889, -0.4988888888888889)
    )
    assert projection.project((118, 169), -13349, 1812) == pytest.approx(
        (150.55777777777777, 102.75111111111111)
    )


@pytest.mark.parametrize("address", ["0x80010000", "0x800C7E35"])
def test_pose_must_fit_the_initial_player_snapshot(tmp_path, address):
    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00421.json").read_text())
    raw["runtime_layout"]["player_position_address_ps1"] = address
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="initial player block"):
        Re2Profile.load(path)
