"""RE2-MAP-006: source geometry contracts, not native wall confirmation."""

import copy
import json
import math
import struct
import sys
from pathlib import Path

import pytest
from shapely import LineString, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tools"))

from re2_map_interiors import add_collision_interiors, collision_detail_segments

from games.re2.map_layout import Re2MapProjection


def sca_source(*records):
    data = bytearray(100)
    struct.pack_into("<I", data, 8 + 6 * 4, 100)
    struct.pack_into("<I", data, 8 + 11 * 4, 116 + len(records) * 16)
    data.extend(struct.pack("<hhIiI", 0, 0, len(records) + 1, -1800, 0))
    for record in records:
        data.extend(struct.pack("<hhHHHHI", *record))
    return bytes(data)


@pytest.fixture
def entry():
    return {
        "rings": [[[0, 0], [40, 0], [40, 40], [0, 40]]],
        "ring_roles": ["outer"],
        "world_origin": [0, 0],
    }


PROJECTION = Re2MapProjection(world_bias=0, units_per_pixel=1)


def test_overlapping_boxes_have_no_invented_internal_partition(entry):
    details = collision_detail_segments(
        sca_source((10, -30, 10, 10, 0, 0x9000, 1), (15, -30, 10, 10, 0, 0x9000, 1)),
        entry,
        PROJECTION,
    )
    assert details
    for segment in details:
        first, last = segment
        assert first[1] == last[1] in (20, 30) or first[0] == last[0] in (10, 25)
    assert sum(LineString(segment).length for segment in details) == 50


def test_circle_is_not_its_collision_bounding_box(entry):
    details = collision_detail_segments(
        sca_source((10, -30, 10, 10, 6, 0x9000, 1)), entry, PROJECTION
    )
    assert len(details) == 32
    for point in {tuple(p) for segment in details for p in segment}:
        assert math.dist(point, (15, 25)) == pytest.approx(5, abs=0.001)
    assert [[10, 20], [20, 20]] not in details


@pytest.mark.parametrize("shape,width,depth", [(7, 20, 10), (8, 10, 20)])
def test_capsules_keep_straight_sides_and_rounded_ends(entry, shape, width, depth):
    details = collision_detail_segments(
        sca_source((10, -30, width, depth, shape, 0x9000, 1)), entry, PROJECTION
    )
    points = [p for segment in details for p in segment]
    assert min(p[0] for p in points) == 10
    assert max(p[0] for p in points) == 10 + width
    assert min(p[1] for p in points) == 30 - depth
    assert max(p[1] for p in points) == 30
    straight = [[15, 20], [25, 20]] if shape == 7 else [[10, 15], [10, 25]]
    assert straight in details
    assert len(details) == 34


@pytest.mark.parametrize("shape", [11, 12])
def test_ramp_or_step_clipping_keeps_source_edges_without_closing_the_clip(
    entry, shape
):
    assert collision_detail_segments(
        sca_source((-5, -20, 20, 10, shape, 0x9000, 3)), entry, PROJECTION
    ) == [
        [[0.75, 10.0], [15.0, 10.0]],
        [[0.75, 20.0], [15.0, 20.0]],
        [[15.0, 10.0], [15.0, 20.0]],
    ]


@pytest.mark.parametrize(
    "record",
    [
        (10, -30, 10, 10, 0, 0x9000, 2),
        (10, -30, 10, 10, 3, 0x9000, 1),
        (-10, -30, 25, 10, 0, 0x9000, 1),
        (-100, -100, 200, 200, 0, 0x9000, 1),
        (0, -30, 10, 10, 0, 0x9000, 1),
    ],
)
def test_other_floors_unknown_shapes_and_perimeter_blockers_are_omitted(entry, record):
    assert collision_detail_segments(sca_source(record), entry, PROJECTION) == []


def test_holes_reject_solids_and_split_routes_without_inventing_hole_edges(entry):
    entry["rings"].append([[15, 15], [25, 15], [25, 25], [15, 25]])
    entry["ring_roles"].append("hole")
    assert (
        collision_detail_segments(
            sca_source((10, -30, 20, 20, 0, 0x9000, 1)), entry, PROJECTION
        )
        == []
    )
    details = collision_detail_segments(
        sca_source((10, -20, 20, 10, 11, 0x9000, 1)), entry, PROJECTION
    )
    assert [[10.0, 20.0], [14.25, 20.0]] in details
    assert [[25.75, 20.0], [30.0, 20.0]] in details
    assert not any(a[0] == b[0] in (14.25, 25.75) for a, b in details)


def test_disconnected_floor_islands_cannot_be_connected_by_clipping(entry):
    entry["rings"] = [
        [[0, 0], [15, 0], [15, 40], [0, 40]],
        [[25, 0], [40, 0], [40, 40], [25, 40]],
    ]
    entry["ring_roles"] = ["outer", "outer"]
    details = collision_detail_segments(
        sca_source((10, -20, 20, 10, 11, 0x9000, 1)), entry, PROJECTION
    )
    assert all(max(a[0], b[0]) <= 14.25 or min(a[0], b[0]) >= 25.75 for a, b in details)


def test_signed_origins_unsigned_extents_and_native_projection(entry):
    entry["world_origin"] = [0, 40]
    details = collision_detail_segments(
        sca_source((-30000, -30000, 60000, 60000, 0, 0x9000, 1)),
        entry,
        Re2MapProjection(world_bias=50000, units_per_pixel=2500),
    )
    assert details == [
        [[8.0, 8.0], [8.0, 32.0]],
        [[8.0, 8.0], [32.0, 8.0]],
        [[8.0, 32.0], [32.0, 32.0]],
        [[32.0, 8.0], [32.0, 32.0]],
    ]


@pytest.mark.parametrize(
    "mutation", ["header", "pointer", "alignment", "count", "next", "truncated"]
)
def test_malformed_collision_sections_fail_explicitly(entry, mutation):
    data = bytearray(sca_source((10, -30, 10, 10, 0, 0x9000, 1)))
    if mutation == "header":
        data = data[:99]
    elif mutation == "pointer":
        struct.pack_into("<I", data, 32, len(data))
    elif mutation == "alignment":
        struct.pack_into("<I", data, 32, 101)
    elif mutation == "count":
        struct.pack_into("<I", data, 104, 1)
    elif mutation == "next":
        struct.pack_into("<I", data, 52, len(data) + 4)
    else:
        data = data[:-1]
    with pytest.raises(ValueError, match="collision"):
        collision_detail_segments(bytes(data), entry, PROJECTION)


@pytest.mark.parametrize(
    "record",
    [
        (10, -30, 0, 10, 0, 0x9000, 1),
        (10, -30, 10, 0, 0, 0x9000, 1),
        (10, -30, 10, 10, 0, 0x9000, 0),
        (10, -30, 10, 20, 6, 0x9000, 1),
        (10, -30, 10, 20, 7, 0x9000, 1),
        (10, -30, 20, 10, 8, 0x9000, 1),
    ],
)
def test_invalid_supported_shapes_fail_explicitly(entry, record):
    with pytest.raises(ValueError, match="collision"):
        collision_detail_segments(sca_source(record), entry, PROJECTION)


def test_original_release_profiles_do_not_gain_unverified_geometry():
    plans = [{"id": "re2-02", "rooms": [], "doors": [{"retained": True}]}]
    before = copy.deepcopy(plans)
    add_collision_interiors("re2_leon_a_slus00421", {}, plans, PROJECTION)
    add_collision_interiors("re2_claire_b_slus00592", {}, plans, PROJECTION)
    assert plans == before


def test_changed_collision_source_cannot_reuse_the_pinned_room_interpretation():
    with pytest.raises(ValueError, match="differs from RE2-MAP-006"):
        add_collision_interiors(
            "re2_leon_a_slus00748",
            {"01-00": sca_source((10, -30, 10, 10, 0, 0x9000, 1))},
            [],
            PROJECTION,
        )


@pytest.mark.parametrize("serial", ["00748", "00756"])
def test_generated_interiors_are_nonempty_inset_and_revision_scoped(serial):
    current = json.loads((ROOT / f"data/floor_plans_slus{serial}.json").read_text())
    original = json.loads((ROOT / "data/floor_plans_slus00421.json").read_text())
    for room_id in ("00", "0B"):
        room = next(
            r
            for a in current["areas"]
            if a["id"] == "re2-02"
            for r in a["rooms"]
            if r["id"] == room_id
        )
        old = next(
            r
            for a in original["areas"]
            if a["id"] == "re2-02"
            for r in a["rooms"]
            if r["id"] == room_id
        )
        assert old["detail_segments"] == []
        assert room["detail_segments"]
        assert room["rings"] == old["rings"]
        assert room["world_origin"] == old["world_origin"]
        floor = Polygon(room["rings"][0]).buffer(-0.7, join_style="mitre")
        assert all(
            floor.covers(LineString(segment)) for segment in room["detail_segments"]
        )
        assert len(
            {tuple(map(tuple, segment)) for segment in room["detail_segments"]}
        ) == len(room["detail_segments"])
        if room_id == "00":
            # SCA records 3 and 43 are the two ramp footprints. The left
            # footprint crosses the sprite edge and must not be moved to fit.
            assert [[127.75, 116.2], [137.169, 116.2]] in room["detail_segments"]
            assert [[131.75, 131.333], [137.169, 131.333]] in room["detail_segments"]
            assert [[162.991, 116.2], [173.591, 116.2]] in room["detail_segments"]
        else:
            # SCA record 3 supplies the desk-sized box. This source-backed
            # edge must survive union with its overlapping round colliders.
            assert [[195.827, 151.644], [195.827, 160.004]] in room["detail_segments"]
