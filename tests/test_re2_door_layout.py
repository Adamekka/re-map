"""RE2-MAP-004: physical doorway geometry; not gameplay access validation."""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from games.re2.map_layout import Re2MapProjection, shared_door_markers
from games.re2.re2_profile import Re2Profile


@pytest.fixture
def adjacent_rooms():
    area = {
        "rooms": [
            {
                "id": "a",
                "room_ids": ["00-00"],
                "world_origin": [0, 0],
                "rings": [[[0, 0], [10, 0], [10, 10], [0, 10]]],
            },
            {
                "id": "b",
                "room_ids": ["00-01"],
                "world_origin": [0, 0],
                "rings": [[[10, 0], [20, 0], [20, 10], [10, 10]]],
            },
        ],
        "doors": [
            {
                "id": "left",
                "observation_id": "00-00:100",
                "rooms": ["a"],
                "segment": [[10, 3], [10, 5]],
            },
            {
                "id": "right",
                "observation_id": "00-01:200",
                "rooms": ["b"],
                "segment": [[10, 5], [10, 7]],
            },
        ],
    }
    rooms = {
        "00-00": {
            "stage": 0,
            "room": 0,
            "doors": [
                {
                    "offset": 100,
                    "stage": 0,
                    "room": 1,
                    "center": [9, -4.5],
                    "activation_floor": 0,
                    "floor": 0,
                }
            ],
        },
        "00-01": {
            "stage": 0,
            "room": 1,
            "doors": [
                {
                    "offset": 200,
                    "stage": 0,
                    "room": 0,
                    "center": [11, -5.5],
                    "activation_floor": 0,
                    "floor": 0,
                }
            ],
        },
    }
    return area, rooms


@pytest.mark.parametrize("sides", ["both", "left", "right", "reversed"])
def test_reciprocal_doors_share_one_wall_even_when_one_side_has_no_marker(
    adjacent_rooms, sides
):
    area, rooms = adjacent_rooms
    if sides == "left":
        area["doors"] = area["doors"][:1]
    elif sides == "right":
        area["doors"] = area["doors"][1:]
    elif sides == "reversed":
        area["doors"].reverse()
    before = copy.deepcopy(area)
    markers = shared_door_markers(area, rooms, Re2MapProjection(0, 1), "projected-wall")
    assert len(markers) == 1
    assert set(markers[0]["observation_ids"]) == {"00-00:100", "00-01:200"}
    assert set(markers[0]["rooms"]) == {"a", "b"}
    assert markers[0]["segment"] == [[10, 4], [10, 6]]
    assert area == before


def test_parallel_doors_between_the_same_rooms_are_not_collapsed(adjacent_rooms):
    area, rooms = adjacent_rooms
    for key, room in rooms.items():
        extra = {**room["doors"][0], "offset": room["doors"][0]["offset"] + 1}
        room["doors"].append(extra)
        original = next(
            marker
            for marker in area["doors"]
            if marker["observation_id"].startswith(key)
        )
        area["doors"].append(
            {
                **original,
                "id": original["id"] + "-second",
                "observation_id": f"{key}:{extra['offset']}",
            }
        )
    markers = shared_door_markers(area, rooms, Re2MapProjection(0, 1), "projected-wall")
    assert len(markers) == 4
    assert all(len(marker["observation_ids"]) == 1 for marker in markers)


@pytest.mark.parametrize(
    "case",
    [
        "gap",
        "corner",
        "short-wall",
        "tie",
        "far",
        "different-floor",
        "one-way",
        "overlap",
    ],
)
def test_ambiguous_or_incompatible_connections_keep_separate_markers(
    adjacent_rooms, case
):
    area, rooms = adjacent_rooms
    if case == "gap":
        area["rooms"][1]["rings"] = [[[11, 0], [20, 0], [20, 10], [11, 10]]]
    elif case == "corner":
        area["rooms"][1]["rings"] = [[[10, 10], [20, 10], [20, 20], [10, 20]]]
    elif case == "short-wall":
        area["rooms"][1]["rings"] = [[[10, 8.5], [20, 8.5], [20, 20], [10, 20]]]
    elif case == "tie":
        area["rooms"][1]["rings"] = [
            [[0, 0], [0, -10], [20, -10], [20, 10], [10, 10], [10, 0]]
        ]
        for room in rooms.values():
            room["doors"][0]["center"] = [10, 0]
    elif case == "far":
        for room in rooms.values():
            room["doors"][0]["center"] = [50, -5]
    elif case == "different-floor":
        rooms["00-01"]["doors"][0]["activation_floor"] = 1
    elif case == "one-way":
        rooms["00-01"]["doors"][0]["room"] = 2
    else:
        area["rooms"][1]["rings"] = copy.deepcopy(area["rooms"][0]["rings"])
    markers = shared_door_markers(area, rooms, Re2MapProjection(0, 1), "projected-wall")
    assert len(markers) == 2
    assert all(len(marker["observation_ids"]) == 1 for marker in markers)
    assert [marker["segment"] for marker in markers] == [
        marker["segment"] for marker in area["doors"]
    ]


def test_collinear_wall_fragments_still_allow_one_doorway(adjacent_rooms):
    area, rooms = adjacent_rooms
    area["rooms"][0]["rings"] = [
        [[0, 0], [10, 0], [10, 4], [10, 5], [10, 6], [10, 10], [0, 10]]
    ]
    assert (
        len(shared_door_markers(area, rooms, Re2MapProjection(0, 1), "projected-wall"))
        == 1
    )


@pytest.mark.parametrize("sides", ["both", "left", "right", "reversed"])
def test_native_opening_is_not_moved_by_trigger_projection(adjacent_rooms, sides):
    area, rooms = adjacent_rooms
    for marker in area["doors"]:
        marker["segment"] = [[10, 7], [10, 9]]
    if sides == "left":
        area["doors"] = area["doors"][:1]
    elif sides == "right":
        area["doors"] = area["doors"][1:]
    elif sides == "reversed":
        area["doors"].reverse()
    markers = shared_door_markers(area, rooms, Re2MapProjection(0, 1), "native-doorway")
    assert len(markers) == 1
    assert markers[0]["segment"] == [[10, 7], [10, 9]]


def test_native_opening_on_a_different_wall_cannot_be_pulled_to_shared_wall(
    adjacent_rooms,
):
    area, rooms = adjacent_rooms
    area["doors"] = area["doors"][:1]
    area["doors"][0]["segment"] = [[6, 0], [8, 0]]
    markers = shared_door_markers(area, rooms, Re2MapProjection(0, 1), "native-doorway")
    assert markers[0]["rooms"] == ["a"]
    assert markers[0]["segment"] == [[6, 0], [8, 0]]


@pytest.mark.parametrize("case", ["unknown-source", "wrong-owner", "multiple-owners"])
def test_invalid_source_bindings_raise_a_metadata_diagnostic(adjacent_rooms, case):
    area, rooms = adjacent_rooms
    if case == "unknown-source":
        area["doors"][0]["observation_id"] = "00-00:999"
    elif case == "wrong-owner":
        area["doors"][0]["rooms"] = ["b"]
    else:
        area["doors"][0]["rooms"] = ["a", "b"]
    with pytest.raises(ValueError, match="RE2 door marker"):
        shared_door_markers(area, rooms, Re2MapProjection(0, 1), "projected-wall")


@pytest.mark.parametrize(
    "profile_id,shop_offsets,segments",
    [
        (
            "re2_leon_a_slus00421",
            (6050, 6082),
            {((106, 79), (106, 81)), ((81, 112), (83, 112))},
        ),
        (
            "re2_claire_b_slus00592",
            (6098, 6130),
            {((106, 79), (106, 81)), ((81, 112), (83, 112))},
        ),
        (
            "re2_leon_a_slus00748",
            (6050, 6082),
            {((106, 83), (106, 85)), ((85, 112), (87, 112))},
        ),
        (
            "re2_claire_b_slus00756",
            (6098, 6130),
            {((106, 83), (106, 85)), ((85, 112), (87, 112))},
        ),
    ],
)
def test_shop_has_two_shared_boundary_doors(profile_id, shop_offsets, segments):
    profile = Re2Profile.load(ROOT / "profiles" / (profile_id + ".json"))
    markers = [
        door
        for door in profile.map_layout.document["areas"][0]["doors"]
        if "01" in door["rooms"]
    ]
    assert len(markers) == 2
    assert {frozenset(door["observation_ids"]) for door in markers} == {
        frozenset({"00-00:4246", f"00-01:{shop_offsets[0]}"}),
        frozenset({f"00-01:{shop_offsets[1]}", "00-02:6146"}),
    }
    assert {tuple(map(tuple, door["segment"])) for door in markers} == segments


@pytest.mark.parametrize(
    "profile_id", ["re2_leon_a_slus00748", "re2_claire_b_slus00756"]
)
def test_reported_hall_and_office_doors_use_native_openings(profile_id):
    """RE2-MAP-005: source spans replace the reported arbitrary-wall guesses."""
    profile = Re2Profile.load(ROOT / "profiles" / (profile_id + ".json"))
    area = profile.map_layout.document["areas"][2]
    for region, expected in [
        (
            "00",
            {
                ((154, 174), (156, 174)),
                ((127, 150), (127, 152)),
                ((127, 118), (127, 120)),
                ((183, 166), (183, 168)),
            },
        ),
        ("02", {((127, 118), (127, 120)), ((86, 115), (88, 115))}),
    ]:
        actual = {
            tuple(map(tuple, door["segment"]))
            for door in area["doors"]
            if region in door["rooms"]
        }
        assert actual == expected
    assert not any("01-00:10058" in door["observation_ids"] for door in area["doors"])
