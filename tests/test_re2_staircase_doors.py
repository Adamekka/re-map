"""RE2-MAP-008: source geometry regressions, never gameplay/ownership proof."""

import copy
import hashlib
import json
import os
import re
import struct
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tools")]

from build_re2_metadata import (
    map_door_segments,
    map_door_staircases,
    native_door_geometry,
)

from games.re2.map_layout import Re2MapProjection
from games.re2.re2_profile import Re2Profile
from tracker.map_geometry import MapPath, door_path

FIXTURE = json.loads((ROOT / "tests/fixtures/re2/staircase-openings.json").read_text())


def test_exact_ten_omissions_and_every_legacy_shared_record_are_preserved():
    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00748.json")
    all_markers = [
        {"area": a["id"], **m}
        for a in profile.map_layout.document["areas"]
        for m in a["doors"]
    ]
    added = [m for m in all_markers if "polyline" in m]
    assert len(added) == 10
    assert {m["observation_ids"][0] for m in added} == {
        f"{m['source']}:{m['offset']}" for m in FIXTURE["markers"]
    }
    for expected in FIXTURE["markers"]:
        marker = next(
            m
            for m in added
            if m["observation_ids"] == [f"{expected['source']}:{expected['offset']}"]
        )
        # Traversal direction changes no boundary point or symbol placement.
        assert marker["polyline"] in (expected["polyline"], expected["polyline"][::-1])
        path = door_path(marker)
        assert path.length == 2 and list(path.center) == expected["center"]
        assert len(marker["rooms"]) == 1
    legacy = [m for m in all_markers if "segment" in m]
    assert len(legacy) == 170
    assert (
        hashlib.sha256((json.dumps(legacy, indent=2) + "\n").encode()).hexdigest()
        == FIXTURE["baseline_shared_markers_sha256"]
    )
    assert len({o for m in all_markers for o in m["observation_ids"]}) == 242
    assert not any("05-0c:3922" in m["observation_ids"] for m in all_markers)
    floors = json.loads((ROOT / "data/floor_plans_slus00748.json").read_text())
    for area in floors["areas"]:
        area.pop("doors")
    floors.pop("research_ids")
    assert (
        hashlib.sha256(json.dumps(floors, sort_keys=True).encode()).hexdigest()
        == FIXTURE["non_door_floor_sha256"]
    )
    assert (
        hashlib.sha256((ROOT / "data/rooms_slus00748.json").read_bytes()).hexdigest()
        == "62b79d3a7feb6d9810fd4c7a6d55e3655037b7a87c640345cd23fd3aa168421d"
    )


@pytest.mark.parametrize("shift", range(9))
@pytest.mark.parametrize("reverse", [False, True])
def test_native_contour_corner_run_survives_ring_start_reversal_and_duplicates(
    shift, reverse
):
    # This actual eight-edge interval straddles the ring start in some cases.
    opening = FIXTURE["markers"][6]["native_opening"]
    ring = opening + [[210, 174], [210, 180], [205, 180]]
    cells = {
        (x, y): 1 for x in range(205, 210) for y in range(174, 180) if x + y >= 383
    }
    # Construct the occupied side of every exact native boundary step.
    for a, b in zip(opening, opening[1:]):
        if a[0] == b[0]:
            cells[a[0], min(a[1], b[1])] = 3
        else:
            cells[min(a[0], b[0]), a[1]] = 3
    ring = ring[shift:] + ring[:shift]
    if reverse:
        ring.reverse()
    paths = map_door_staircases(cells, [ring, ring[::-1]])
    assert len(paths) == 1
    expected = MapPath(tuple(map(tuple, opening)))
    assert paths[0].points in (expected.points, expected.points[::-1])


@pytest.mark.parametrize(
    "case", ["interior", "isolated", "l-shape", "nonmonotone", "other-shade"]
)
def test_staircase_rule_rejects_unproven_corner_joins(case):
    ring = [[0, 0], [1, 0], [1, 1], [2, 1], [2, 2], [3, 2], [3, 3], [0, 3]]
    cells = {(x, y): 3 for x in range(3) for y in range(3) if x <= y}
    if case == "interior":
        cells = {(x, y): 3 for x in range(-1, 4) for y in range(-1, 4)}
    elif case == "isolated":
        cells = {(x, y): 3 if (x, y) == (1, 1) else 1 for x, y in cells}
    elif case == "l-shape":
        ring = [[0, 0], [3, 0], [3, 3], [0, 3]]
        cells = {
            (x, y): 3 if y == 0 or x == 2 else 1 for x in range(3) for y in range(3)
        }
    elif case == "nonmonotone":
        ring = [
            [0, 0],
            [1, 0],
            [1, 1],
            [0, 1],
            [0, 2],
            [2, 2],
            [2, 3],
            [-1, 3],
            [-1, 0],
        ]
    else:
        cells = {p: 4 for p in cells}
    assert map_door_staircases(cells, [ring]) == []


def test_exact_eight_unit_gate_ties_and_every_contour_edge():
    path = MapPath(((0, 0), (1, 0), (1, 1), (2, 1), (2, 2)))
    assert native_door_geometry((-8, 0), [], [path]) == {
        "polyline": [[1, 0], [1, 1], [2, 1]]
    }
    assert native_door_geometry((-8.000001, 0), [], [path]) is None
    assert path.distance_squared((2, 2)) == 0
    other = MapPath(((0, -2), (1, -2), (1, -3), (2, -3), (2, -4)))
    assert native_door_geometry((0, -1), [], [path, other]) is None
    # Supplemental paths cannot move an already successful straight marker.
    assert native_door_geometry((2, 2), [[[3, 0], [3, 4]]], [path]) == {
        "segment": [[3, 1], [3, 3]]
    }


@pytest.mark.parametrize(
    "points",
    [
        [],
        [[0, 0]],
        [[0, 0], [0, 0], [1, 0]],
        [[0, 0], [1, 1], [2, 1]],
        [[0, 0], [1, 0], [0.5, 0]],
        [[0, 0], [float("nan"), 0], [1, 1]],
        [[0, 0], [1, float("inf")], [1, 1]],
        [[0, 0], [10**1000, 0], [1, 1]],
        [[0, 0], [1e308, 0], [1e308, 1]],
        [[0, 0], [1e-200, 0], [1e-200, 1]],
    ],
)
def test_malformed_polylines_fail_before_publication(points):
    with pytest.raises(ValueError):
        door_path({"polyline": points})


def test_explicit_geometry_alternatives_and_on_wall_arclength_center():
    with pytest.raises(ValueError):
        door_path({"segment": [[0, 0], [1, 0]], "polyline": [[0, 0], [1, 0], [1, 1]]})
    path = door_path({"polyline": [[206, 176], [207, 176], [207, 175]]})
    assert path.center == (207, 176)
    assert path.center != (206.5, 175.5)
    assert path.on_boundary(
        [[[206, 176], [207, 176], [207, 175], [208, 175], [208, 177], [206, 177]]]
    )
    assert not path.on_boundary([[[206, 176], [207, 175], [208, 177]]])


def test_loader_rejects_off_contour_geometry_without_publishing(tmp_path):
    from games.re2.map_layout import Re2MapLayout

    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00748.json")
    floors = json.loads((ROOT / "data/floor_plans_slus00748.json").read_text())
    marker = next(m for a in floors["areas"] for m in a["doors"] if "polyline" in m)
    marker["polyline"][1][0] += 0.25
    output = tmp_path / "invalid.json"
    output.write_text(json.dumps(floors))
    with pytest.raises(ValueError, match="polyline"):
        Re2MapLayout.load(
            output,
            profile.profile_id,
            floors["executable_identity"],
            profile.rooms,
            profile.map_layout.projection,
        )


@pytest.mark.parametrize("mutation", ["both-kinds", "empty", "nonfinite"])
def test_loader_validates_reverse_geometry_before_pairing_consumes_it(
    tmp_path, mutation
):
    from games.re2.map_layout import Re2MapLayout

    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00748.json")
    floors = json.loads((ROOT / "data/floor_plans_slus00748.json").read_text())
    area_id, shared = next(
        (area["id"], marker)
        for area in profile.map_layout.document["areas"]
        for marker in area["doors"]
        if len(marker["observation_ids"]) == 2
    )
    area = next(area for area in floors["areas"] if area["id"] == area_id)
    raw = [m for m in area["doors"] if m["observation_id"] in shared["observation_ids"]]
    assert len(raw) == 2 and raw[0]["id"] == shared["id"]
    reverse = raw[1]
    if mutation == "both-kinds":
        reverse["polyline"] = [[0, 0], [1, 0], [1, 1]]
    else:
        reverse["segment"] = [] if mutation == "empty" else [[0, 0], [float("nan"), 1]]
    output = tmp_path / "invalid-reverse.json"
    output.write_text(json.dumps(floors))
    with pytest.raises(ValueError, match="map"):
        Re2MapLayout.load(
            output,
            profile.profile_id,
            floors["executable_identity"],
            profile.rooms,
            profile.map_layout.projection,
        )


def test_direct_publication_rejects_off_wall_geometry_and_keeps_input_unchanged():
    from uuid import UUID

    from ui.map_view import map_page

    profile = Re2Profile.load(ROOT / "profiles/re2_leon_a_slus00748.json")
    graph = profile.map_layout.document
    before = copy.deepcopy(graph)
    map_page(graph, UUID(int=1))
    assert graph == before
    marker = next(m for a in graph["areas"] for m in a["doors"] if "polyline" in m)
    marker["polyline"] = [[0, 0], [1, 0], [1, 1]]
    with pytest.raises(ValueError, match="owning contour"):
        map_page(graph, UUID(int=1))


def test_all_owned_sources_and_356_native_contexts_reproduce_only_ten_additions():
    cue_text = os.environ.get("RE_MAP_RE2_OWNED_CUE")
    if cue_text is None:
        pytest.skip("Set RE_MAP_RE2_OWNED_CUE for the source-wide staircase census")
    from build_item_table import _read_file
    from extract_psx_file import _find
    from list_psx_files import _sector_data

    catalog = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    floors = json.loads((ROOT / "data/floor_plans_slus00748.json").read_text())
    profile = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    projection = Re2MapProjection(**profile["map_projection"])
    cue = Path(cue_text)
    match = re.search(r'FILE\s+"([^"]+)"', cue.read_text())
    assert match
    with (cue.parent / match[1]).open("rb") as stream:
        pvd = _sector_data(stream, 16)
        root, size = (
            struct.unpack_from("<I", pvd, 158)[0],
            struct.unpack_from("<I", pvd, 166)[0],
        )

        def read(path):
            return _read_file(stream, *_find(stream, root, size, path))

        exe, pixels = read("SLUS_007.48"), read("COMMON/DATA/MAPS.PIX")
        assert (
            hashlib.sha256(exe).hexdigest()
            == "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
        )
        assert (
            hashlib.sha256(pixels).hexdigest()
            == "d5b71306319d64bb0569562549463b338920a124383ea77e23758610c1fac439"
        )
        for room in catalog["rooms"]:
            data = read(room["source"])
            assert (
                len(data) == room["size"]
                and hashlib.sha256(data).hexdigest() == room["sha256"]
            )
            for door in room["doors"]:
                packet = data[door["offset"] :]
                four = packet[0] == 0x68
                geometry = struct.unpack_from("<8h" if four else "<2h2H", packet, 6)
                center = (
                    [sum(geometry[::2]) / 4, sum(geometry[1::2]) / 4]
                    if four
                    else [geometry[0] + geometry[2] / 2, geometry[1] + geometry[3] / 2]
                )
                assert center == door["center"] and four == door["four_point"]
                assert (
                    packet[1] == door["slot"] and packet[4] == door["activation_floor"]
                )
                payload = 30 if four else 22
                assert [packet[payload + i] for i in (0, 1, 3, 7, 8)] == [
                    door[k] for k in ("stage", "room", "floor", "lock_id", "lock_type")
                ]
    load = struct.unpack_from("<I", exe, 0x18)[0]
    contexts, additions, staircase_count = 0, [], 0
    generated = copy.deepcopy(floors)
    for area in generated["areas"]:
        area["doors"] = []
        table = (
            int(profile["metadata_layout"]["map_info_address_ps1"], 0)
            - load
            + 0x800
            + int(area["id"][4:]) * 8
        )
        address, _, _, page = struct.unpack_from("<IBBH", exe, table)
        for entry in area["rooms"]:
            u, v, w, h, x, y, bx, by, *_ = struct.unpack_from(
                "<4B4h4B", exe, address - load + 0x800 + int(entry["id"], 16) * 16
            )
            assert entry["world_origin"] == [bx, by]
            cells = {}
            for dy in range(h):
                for dx in range(w):
                    index = ((v + dy) % 256) * 256 + (u + dx) % 256
                    shade = (
                        pixels[page * 32768 + index // 2] >> (4 * (index % 2))
                    ) & 15
                    if shade:
                        cells[x + dx, y + dy] = shade
            segments = map_door_segments(cells, entry["rings"])
            staircases = map_door_staircases(cells, entry["rings"])
            staircase_count += len(staircases)
            for source in catalog["rooms"]:
                if source["id"] not in entry["room_ids"]:
                    continue
                for door in source["doors"]:
                    contexts += 1
                    eligible = bool(door["activation_floor"] & 0x80) or any(
                        r["room"] == source["id"]
                        and r["area"] == area["id"]
                        and r["region"] == entry["id"]
                        and r["floor_min"] <= door["activation_floor"] <= r["floor_max"]
                        for r in floors["locations"]
                    )
                    point = projection.project((bx, by), *door["center"])
                    geometry = native_door_geometry(point, segments, staircases)
                    if geometry is None or not eligible:
                        continue
                    identity = f"{source['id']}:{door['offset']}"
                    if "polyline" in geometry:
                        additions.append(identity)
                    area["doors"].append(
                        {
                            "id": identity + ":" + entry["id"],
                            "observation_id": identity,
                            "rooms": [entry["id"]],
                            **geometry,
                        }
                    )
        assert area["doors"] == next(
            a["doors"] for a in floors["areas"] if a["id"] == area["id"]
        )
    assert sum(len(r["doors"]) for r in catalog["rooms"]) == 321
    assert contexts == 356 and staircase_count == 6
    assert len(additions) == 10
    assert set(additions) == {
        f"{m['source']}:{m['offset']}" for m in FIXTURE["markers"]
    }
