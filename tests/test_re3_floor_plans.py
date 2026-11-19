"""RE3-PLAN-001/002/003: floor-plan builder, committed geometry and names."""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from shapely.geometry import LinearRing, Point, Polygon

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

import build_re3_floor_plans as builder
from disc_cue import read_cue_tracks
from map_geometry import trace_floor_cells

PLANS = ROOT / "data" / "floor_plans_slus00923.json"
NAMES = ROOT / "data" / "re3_names.json"


@pytest.fixture(scope="module")
def plans():
    return json.loads(PLANS.read_text())


@pytest.fixture(scope="module")
def names():
    return json.loads(NAMES.read_text())


def test_cells_round_trip_through_traced_contours_with_holes():
    cells = {(x, y) for x in range(6) for y in range(5)} - {(2, 2), (3, 2)}
    cells |= {(9, 9)}
    rings, _ = trace_floor_cells(cells)
    roles = ["outer" if area > 0 else "hole" for area, _ in rings]
    assert roles.count("hole") == 1
    assert builder.cells_from_rings([ring for _, ring in rings], roles) == cells


def test_door_segment_snaps_to_a_nearby_wall_and_rejects_distant_points():
    ring = [(0, 0), (10, 0), (10, 4), (0, 4)]
    segment = builder.door_segment([ring], (9.6, 2.5))
    assert segment == [[10, 1.5], [10, 3.5]]
    # The two-unit marker stays inside its wall even at a corner.
    assert builder.door_segment([ring], (0.1, 0.2)) in ([[0, 0], [2, 0]], [[0, 0], [0, 2]])
    assert builder.door_segment([ring], (30, 30)) is None


def test_detail_segments_keep_strokes_and_skip_filled_blocks():
    cells = {(x, y) for x in range(12) for y in range(12)}
    stroke = {(x, 2) for x in range(1, 9)}
    block = {(x, y) for x in range(1, 9) for y in range(6, 9)}
    segments = builder.detail_segments(stroke | block, cells)
    assert [[1.5, 2.5], [8.5, 2.5]] in segments
    assert all(not 6 <= y <= 9 for segment in segments for _, y in segment)
    # Short strokes are mostly native map lettering, not room features.
    assert builder.detail_segments({(1, 1), (2, 1)}, cells) == []


def test_decode_text_uses_the_game_character_codes():
    assert builder.decode_text(bytes([0x24, 0x3D, 0x4A, 0x40, 0x00, 0x23, 0x51, 0x4A])) == "Hand Gun"
    logo = bytes([0xEA, 0x24, 0xEA, 0x25, 0xEA, 0x26, 0xEA, 0x27, 0xEA, 0x24])
    assert builder.decode_text(logo + bytes([0x00, 0x1F])) == "S.T.A.R.S. C"
    assert builder.decode_text(bytes([0x0C, 0x01, 0x15, 0x3B, 0x3A])) == "0.9-'"
    with pytest.raises(ValueError):
        builder.decode_text(bytes([0xF7]))


def test_position_bounds_are_inclusive_and_only_constrain_named_axes():
    assert builder.within({}, 10**9, -(10**9))
    assert builder.within({"x": [-8822, 2**31 - 1]}, -8822, 0)
    assert not builder.within({"x": [-8822, 2**31 - 1]}, -8823, 0)
    assert not builder.within({"z": [-(2**31), -11301]}, 0, -11300)


def regions_of(plans):
    return {
        (area["id"], region["id"]): region
        for area in plans["areas"]
        for region in area["rooms"]
    }


def test_committed_plans_match_the_profile_and_stay_small(plans):
    assert PLANS.stat().st_size < 1_000_000
    assert plans["schema"] == 1 and plans["stage_modulus"] == 256
    assert plans["profile_id"] == "re3_jill_hard_slus00923"
    assert plans["executable_identity"] == (
        "SLUS_009.23 SHA256 "
        "2e143418e358b2c99995cdc1a88c387163fb751912c723b755614f38e236bd29"
    )
    assert "RE3-PLAN-001" in plans["research_ids"]
    assert plans["door_placement"] == "projected-wall"
    assert plans["world_units_per_map_unit"] == 450


def test_outlines_are_closed_simple_rings_with_consistent_roles(plans, names):
    for area in plans["areas"]:
        assert area["name"] == names["areas"][area["id"]]
        assert len({region["id"] for region in area["rooms"]}) == len(area["rooms"])
        for region in area["rooms"]:
            assert region["name"] and region["room_ids"] == sorted(set(region["room_ids"]))
            assert len(region["rings"]) == len(region["ring_roles"]) >= 1
            outers = []
            for ring, role in zip(region["rings"], region["ring_roles"]):
                assert len(ring) >= 4 and len({tuple(p) for p in ring}) == len(ring)
                assert all(type(v) is int for point in ring for v in point)
                # Unit-cell contours keep only axis-aligned edges.
                assert all(
                    (a[0] == b[0]) != (a[1] == b[1]) for a, b in zip(ring, ring[1:] + ring[:1])
                )
                shape = LinearRing(ring)
                assert shape.is_valid and shape.is_simple
                # Positive shoelace area marks an outer ring, as in trace_floor_cells.
                assert (role == "outer") == shape.is_ccw
                if role == "outer":
                    outers.append(Polygon(ring))
            label = Point(region["label"])
            assert any(polygon.contains(label) for polygon in outers)
            assert all(
                any(polygon.covers(Point(point)) for polygon in outers)
                for segment in region["detail_segments"]
                for point in segment
            )
            assert all(
                type(v) is int and -32768 <= v <= 32767 for v in region["world_origin"]
            )


def test_every_located_room_is_outlined_or_explicitly_unoutlined(plans, names):
    regions = regions_of(plans)
    unoutlined = {
        room for area in plans["areas"] for room in area["unoutlined_rooms"]
    }
    located = set()
    for location in plans["locations"]:
        located.add(location["room"])
        assert 0 <= location["floor_min"] <= location["floor_max"] <= 255
        if location["area"] == "unmapped":
            assert location["room"] in unoutlined
        else:
            region = regions[location["area"], location["region"]]
            assert location["room"] in region["room_ids"]
        for axis, (low, high) in location["position_bounds"].items():
            assert axis in ("x", "z") and -(2**31) <= low <= high <= 2**31 - 1
    outlined = {room for region in regions.values() for room in region["room_ids"]}
    assert outlined | unoutlined == located
    assert set(names["rooms"]) >= located


def test_door_markers_lie_on_their_owning_outline(plans):
    regions = regions_of(plans)
    for area in plans["areas"]:
        assert len({door["id"] for door in area["doors"]}) == len(area["doors"])
        for door in area["doors"]:
            (owner,) = door["rooms"]
            region = regions[area["id"], owner]
            source = door["observation_id"].split(":")[0]
            assert source in region["room_ids"] and door["target"] != source
            (a, b) = door["segment"]
            assert abs(a[0] - b[0]) + abs(a[1] - b[1]) == pytest.approx(2)
            boundary = [LinearRing(ring) for ring in region["rings"]]
            assert all(
                any(ring.distance(Point(point)) < 1e-9 for ring in boundary)
                for point in (a, b)
            )


def test_names_cover_items_without_unreleased_placeholders(names):
    assert names["items"]["1"] == "Knife"
    assert "0" not in names["items"]
    assert all(name and name != "BOTU" for name in names["items"].values())


@pytest.fixture(scope="module")
def owned_cue():
    cue = os.environ.get("RE_MAP_RE3_OWNED_CUE")
    if cue is None:
        pytest.skip("Set RE_MAP_RE3_OWNED_CUE for the owned-disc floor-plan checks")
    return Path(cue)


def test_owned_disc_regenerates_the_committed_plans(
    owned_cue, plans, tmp_path, monkeypatch
):
    output = tmp_path / "plans.json"
    monkeypatch.setattr(
        sys, "argv", ["build_re3_floor_plans.py", str(owned_cue), str(output)]
    )
    assert builder.main() == 0
    assert json.loads(output.read_text()) == plans


def test_owned_disc_item_names_match_the_executable_table(owned_cue, names):
    executable, _, sources = builder.read_disc(read_cue_tracks(owned_cue)[0])
    assert builder.item_names(executable) == names["items"]
    located = {location["room"] for location in json.loads(PLANS.read_text())["locations"]}
    assert located == set(sources)


@pytest.mark.parametrize("source", ["cue", "data", "audio", "names"])
@pytest.mark.parametrize("alias", ["direct", "symlink", "hardlink"])
def test_floor_plan_output_preserves_inputs(
    tmp_path, monkeypatch, capsys, source, alias
):
    cue = tmp_path / "test.cue"
    data = tmp_path / "data track.bin"
    audio = tmp_path / "audio.bin"
    names = tmp_path / "names.json"
    cue.write_text(f'FILE "{data.name}" BINARY\nFILE {audio.name} BINARY\n')
    data.write_bytes(b"test data track")
    audio.write_bytes(b"test audio track")
    names.write_text("{}")
    media = {"cue": cue, "data": data, "audio": audio, "names": names}[source]
    before = media.read_bytes()
    output = tmp_path / "out.json"
    if alias == "direct":
        output = media
    elif alias == "symlink":
        output.symlink_to(media)
    else:
        output.hardlink_to(media)
    build = Mock()
    monkeypatch.setattr(builder, "build", build)
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_re3_floor_plans.py", str(cue), str(output), "--names", str(names)],
    )
    assert builder.main() == 2
    assert "Choose another output path" in capsys.readouterr().err
    assert media.read_bytes() == before
    build.assert_not_called()


@pytest.mark.parametrize("fault", ["new-alias", "partial-write", "retargeted-symlink"])
def test_floor_plan_export_checks_again_before_replacing_output(
    tmp_path, monkeypatch, capsys, fault
):
    cue = tmp_path / "test.cue"
    image = tmp_path / "track.bin"
    output = tmp_path / "out.json"
    cue.write_text(f'FILE "{image.name}" BINARY\n')
    image.write_bytes(b"test data track")
    output.write_text('{"previous": true}\n')
    requested = output
    if fault == "retargeted-symlink":
        requested = tmp_path / "requested.json"
        requested.symlink_to(output)

    def build(path, names):
        assert path == image
        if fault == "new-alias":
            output.unlink()
            output.hardlink_to(image)
        elif fault == "retargeted-symlink":
            requested.unlink()
            requested.symlink_to(image)
        return {"updated": True}

    original_write = Path.write_text

    def partial_write(path, data):
        original_write(path, data[:3])
        raise OSError("simulated short write")

    monkeypatch.setattr(builder, "build", build)
    if fault == "partial-write":
        monkeypatch.setattr(Path, "write_text", partial_write)
    monkeypatch.setattr(
        sys,
        "argv",
        ["build_re3_floor_plans.py", str(cue), str(requested)],
    )
    assert builder.main() == 2
    assert image.read_bytes() == b"test data track"
    error = capsys.readouterr().err
    if fault == "new-alias":
        assert "Choose another output path" in error
        assert output.samefile(image)
    else:
        assert output.read_text() == '{"previous": true}\n'
        if fault == "retargeted-symlink":
            assert "Output path changed" in error
            assert requested.samefile(image)
        else:
            assert "simulated short write" in error
    assert not list(tmp_path.glob(".re-map-export-*"))


def test_re2_layout_consumer_accepts_the_geometry_and_native_witnesses(plans, tmp_path):
    from games.re2.map_layout import Re2MapLayout, Re2MapProjection

    document = json.loads(json.dumps(plans))
    # The RE2 loader pairs doors through its own room catalog; this checks the
    # shared geometry and selection contract with a doorless catalog.
    for area in document["areas"]:
        area["doors"] = []
    path = tmp_path / "plans.json"
    path.write_text(json.dumps(document))
    rooms = {location["room"]: {"doors": []} for location in document["locations"]}
    layout = Re2MapLayout.load(
        path,
        document["profile_id"],
        document["executable_identity"],
        rooms,
        Re2MapProjection(0, 450),
    )
    # RE3-MAP-004 observed the native marker at these map positions. Native
    # truncation and the rounded integer origin each move it under one unit.
    for room, world, native in (
        ("00-0d", (13209, -14515), (612, 246)),
        ("00-01", (-4842, -11028), (515, 331)),
    ):
        area, region = layout.select(room, 0, lambda address, width: 0)
        position = layout.project(area, region, *world)
        assert abs(position.x - native[0]) < 1.5 and abs(position.y - native[1]) < 1.5
