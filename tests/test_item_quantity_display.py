"""RE1-QUANTITY-003 / RE2-QUANTITY-002: raw amounts need explicit units."""

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from games.game_profile import RoomId
from games.item_quantity import ItemQuantityState
from games.re1.re1_profile import Re1Profile
from games.re2.re2_profile import Re2Profile
from tracker.exploration_state import ItemDetail, Tracker
from ui.map_view import map_state


@pytest.mark.parametrize(
    "profile_id,expected",
    [
        ("re1_directors_cut_slus00551", {11, 12, 13, 14, 16, 17, 18, 47}),
        ("re1_ntsc_u", set()),
        ("re1_ntsc_u_slus00170", set()),
        ("re2_leon_a_slus00748", {20, 21, 22, 24, 25, 26, 29, 30, 31}),
        ("re2_claire_b_slus00756", {20, 21, 22, 24, 25, 26, 29, 30, 31}),
        ("re2_leon_a_slus00421", set()),
        ("re2_claire_b_slus00592", set()),
    ],
)
def test_count_types_are_bound_to_independently_audited_revisions(profile_id, expected):
    profile_class = Re1Profile if profile_id.startswith("re1_") else Re2Profile
    profile = profile_class.load(ROOT / "profiles" / (profile_id + ".json"))
    assert profile.unit_count_item_types == expected
    assert isinstance(profile.unit_count_item_types, frozenset)


@pytest.mark.parametrize("profile_class", [Re1Profile, Re2Profile])
@pytest.mark.parametrize(
    "document",
    [
        {},
        {"unit_count_item_types": None},
        {"unit_count_item_types": "20"},
        {"unit_count_item_types": [True]},
        {"unit_count_item_types": [20, 20]},
        {"unit_count_item_types": [-1]},
        {"unit_count_item_types": [256]},
        {"unit_count_item_types": [20.0]},
        {"unit_count_item_types": ["20"]},
        {"unit_count_item_types": [[20]]},
    ],
)
def test_profiles_require_explicit_valid_count_units(tmp_path, profile_class, document):
    path = tmp_path / "profile.json"
    path.write_text(json.dumps(document))
    with pytest.raises(ValueError, match="unit_count_item_types"):
        profile_class.load(path)


@pytest.mark.parametrize("units", [None, 0, 1, "count"])
def test_quantity_units_cannot_silently_default(units):
    with pytest.raises(AssertionError, match="units"):
        ItemDetail("Collectible", "available", 2, units)


@pytest.mark.parametrize("state", ["available", "uncollected", "unknown", "taken"])
@pytest.mark.parametrize("quantity", [0, 1, 2, ItemQuantityState.Unreconstructed])
@pytest.mark.parametrize("unit_count", [False, True])
def test_map_preserves_raw_amount_and_units_in_every_room_view(
    state, quantity, unit_count
):
    tracker = Tracker(player_heading=90)
    room = RoomId(0, 1)
    tracker.mark_current(room)
    tracker.current_region = "test:01"
    tracker.region_visits[tracker.current_region] = str(room)
    tracker.rooms[str(room)].items = (
        ItemDetail("Collectible", state, quantity, unit_count),
    )
    payload = map_state(tracker)
    for detail in (
        payload["current_detail"],
        payload["rooms"][0],
        payload["explored_areas"]["test"][0],
    ):
        assert detail["items"] == [
            {
                "label": "Collectible",
                "state": state,
                "quantity": quantity,
                "quantity_is_unit_count": unit_count,
            }
        ]
