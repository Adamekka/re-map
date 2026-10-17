"""Numeric contours shared by the owned RE1 and RE2 map generators."""


def trace_floor_cells(
    floor_pixels: set[tuple[int, int]],
) -> tuple[list, tuple[int, int]]:
    if not floor_pixels:
        raise ValueError("floor cells must not be empty")
    edges = set()
    for x, y in floor_pixels:
        for a, b in (
            ((x, y), (x + 1, y)),
            ((x + 1, y), (x + 1, y + 1)),
            ((x + 1, y + 1), (x, y + 1)),
            ((x, y + 1), (x, y)),
        ):
            if (b, a) in edges:
                edges.remove((b, a))
            else:
                edges.add((a, b))
    rings = []
    while edges:
        a, b = min(edges)
        start = a
        ring = [a]
        while True:
            edges.remove((a, b))
            if b == start:
                break
            ring.append(b)
            successors = [end for begin, end in edges if begin == b]
            if not 1 <= len(successors) <= 2:
                raise ValueError("floor cells have an ambiguous contour")
            if len(successors) == 2:
                # Floor regions can touch at one pixel corner. Keep their
                # contours separate by turning right around the occupied cell.
                successors.sort(
                    key=lambda end: (
                        (b[0] - a[0]) * (end[1] - b[1])
                        - (b[1] - a[1]) * (end[0] - b[0])
                    ),
                    reverse=True,
                )
            a, b = b, successors[0]
        # Collapse only collinear cell edges. Smoothing would invent room shape.
        ring = [
            point
            for i, point in enumerate(ring)
            if (point[0] - ring[i - 1][0]) * (ring[(i + 1) % len(ring)][1] - point[1])
            != (point[1] - ring[i - 1][1]) * (ring[(i + 1) % len(ring)][0] - point[0])
        ]
        area = (
            sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(ring, ring[1:] + ring[:1]))
            / 2
        )
        rings.append((area, ring))
    rings.sort(key=lambda entry: abs(entry[0]), reverse=True)
    if sum(area for area, _ in rings) != len(floor_pixels):
        raise ValueError("contour does not preserve floor area")
    center = tuple(
        sum(point[axis] + 0.5 for point in floor_pixels) / len(floor_pixels)
        for axis in (0, 1)
    )
    # Concave-room centroids can land on a wall. Keep labels in the largest
    # interior space, using distance from the centroid only to break ties.
    clearance = {
        (x, y): 0
        for x, y in floor_pixels
        if any(
            point not in floor_pixels
            for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        )
    }
    queue = sorted(clearance)
    for x, y in queue:
        for point in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if point in floor_pixels and point not in clearance:
                clearance[point] = clearance[(x, y)] + 1
                queue.append(point)
    label_pixel = min(
        floor_pixels,
        key=lambda point: (
            -clearance[point],
            sum((point[axis] + 0.5 - center[axis]) ** 2 for axis in (0, 1)),
            point,
        ),
    )
    return rings, label_pixel
