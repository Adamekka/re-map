"""RE2-MAP-006: conservative, offline SCA footprints for two DualShock rooms.

Requires Shapely 2.1 for generation only. These collision contours do not prove
visible walls. Unknown shapes and misplaced perimeter blockers stay omitted.
"""

from __future__ import annotations

import hashlib
import struct

from games.re2.map_layout import Re2MapProjection


def _collision_section(data: bytes) -> bytes:
    if len(data) < 100:
        raise ValueError("RE2 collision source lacks its section table")
    sections = struct.unpack_from("<23I", data, 8)
    start = sections[6]
    if start < 100 or start % 4 or start + 16 > len(data):
        raise ValueError("RE2 collision section is outside its source")
    end = min((offset for offset in sections if offset > start), default=len(data))
    count = struct.unpack_from("<I", data, start + 4)[0]
    # Native Sca_search advances past the header before its first record and
    # stops at start + Num * 16. Num therefore includes the header, not a shape.
    if count < 1 or start + count * 16 != end or end > len(data):
        raise ValueError("RE2 collision count disagrees with its section boundary")
    return data[start:end]


def collision_detail_segments(
    data: bytes, entry: dict, projection: Re2MapProjection
) -> list:
    from shapely import GeometryCollection, LineString, Point, Polygon, box, union_all

    section = _collision_section(data)

    floor = union_all(
        [
            Polygon(ring)
            for ring, role in zip(entry["rings"], entry["ring_roles"], strict=True)
            if role == "outer"
        ]
    ).difference(
        union_all(
            [
                Polygon(ring)
                for ring, role in zip(entry["rings"], entry["ring_roles"], strict=True)
                if role == "hole"
            ]
        )
    )
    if floor.is_empty or not floor.is_valid:
        raise ValueError("RE2 collision details require a valid mapped floor")
    # The existing detail outline is 1.4 map units wide. Leave room for its
    # half-width and coordinate rounding without redrawing the room perimeter.
    inset = floor.buffer(-0.75, join_style="mitre")
    origin = tuple(entry["world_origin"])
    solids, routes = [], []
    for offset in range(16, len(section), 16):
        x, z, width, depth, identity, _kind, floors = struct.unpack_from(
            "<hhHHHHI", section, offset
        )
        if not width or not depth or not floors:
            raise ValueError("RE2 collision record has an empty extent or floor mask")
        # Floor bit zero covers native Y=0. This is deliberately limited to the
        # two 1F rooms; the player trigger-floor byte is a different quantity.
        if not floors & 1:
            continue
        shape = identity & 0xF
        if shape in (0, 11, 12):
            left, bottom = projection.project(origin, x, z)
            right, top = projection.project(origin, x + width, z + depth)
            footprint = box(left, top, right, bottom)
        elif shape == 6:
            if width != depth:
                raise ValueError("RE2 circular collision has unequal diameters")
            radius = width // 2
            footprint = Point(
                projection.project(origin, x + radius, z + radius)
            ).buffer(radius / projection.units_per_pixel, quad_segs=8)
        elif shape in (7, 8):
            if (shape == 7 and width < depth) or (shape == 8 and depth < width):
                raise ValueError("RE2 capsule collision has a reversed long axis")
            radius = (depth if shape == 7 else width) // 2
            centers = (
                ((x + radius, z + radius), (x + width - radius, z + radius))
                if shape == 7
                else ((x + radius, z + radius), (x + radius, z + depth - radius))
            )
            footprint = LineString(
                [projection.project(origin, *point) for point in centers]
            ).buffer(radius / projection.units_per_pixel, quad_segs=8)
        else:
            # Diagonals, diamonds and curved slopes need their own verified
            # interpretation. Their bounding rectangles are not map walls.
            continue
        if shape in (11, 12):
            # Slopes and steps describe a traversable footprint. Retain only
            # source edges inside the map, never a new edge along the clip or
            # invented treads from the collision height/animation calculation.
            routes.append(footprint.boundary.intersection(inset))
        elif inset.covers(footprint):
            # Large off-outline blockers constrain movement but do not prove
            # visible partitions across the distorted native room sprite.
            solids.append(footprint)

    paths = [*routes]
    if solids:
        # Overlapping collider primitives describe one blocked footprint. Their
        # internal seams would invent partitions through that same obstacle.
        paths.append(union_all(solids).boundary)
    segments = set()

    def collect(geometry) -> None:
        if geometry.is_empty or geometry.geom_type == "Point":
            # Tangent clipping contacts have no drawable length.
            return
        if geometry.geom_type in ("LineString", "LinearRing"):
            points = [tuple(round(value, 3) for value in p) for p in geometry.coords]
            for first, last in zip(points, points[1:]):
                if first != last:
                    segments.add(tuple(sorted((first, last))))
        else:
            assert isinstance(geometry, GeometryCollection) or geometry.geom_type in (
                "MultiLineString",
                "MultiPoint",
            ), "collision boundaries must contain only lines and clipping contacts"
            for part in geometry.geoms:
                collect(part)

    for path in paths:
        collect(path)
    return [[list(first), list(last)] for first, last in sorted(segments)]


def add_collision_interiors(
    profile_id: str,
    sources: dict[str, bytes],
    plans: list,
    projection: Re2MapProjection,
) -> None:
    if profile_id not in ("re2_leon_a_slus00748", "re2_claire_b_slus00756"):
        # The original-release collision corpus has not received this check.
        return
    for room_id, digest in (
        ("01-00", "f47e4f6e32511becd4f815d49d15477c63431a352a670017d82e81eef5fafb19"),
        ("01-0b", "c88f56746e72a753a814362f92c0e0b9603f96951142b1ea6aa2a39ffc416d9e"),
    ):
        data = sources[room_id]
        if hashlib.sha256(_collision_section(data)).hexdigest() != digest:
            raise ValueError(f"{room_id} collision source differs from RE2-MAP-006")
        entries = [
            entry
            for plan in plans
            if plan["id"] == "re2-02"
            for entry in plan["rooms"]
            if room_id in entry["room_ids"]
        ]
        if len(entries) != 1 or entries[0]["room_ids"] != [room_id]:
            raise ValueError(f"{room_id} requires its own unique 1F map region")
        entry = entries[0]
        for segment in collision_detail_segments(data, entry, projection):
            if segment not in entry["detail_segments"]:
                entry["detail_segments"].append(segment)
