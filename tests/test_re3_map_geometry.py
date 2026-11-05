"""RE3-MAP-005 original packed textures; no owned game artwork or code."""

import struct
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

import re3_map_geometry
from test_re3_map_binding import context as context
from test_re3_map_binding import synthetic_layout

from games.re3.room_data import RoomFormatFailure, aligned_block_size


def quad(uv=(0, 0, 7, 7), destination=(-9, 10), style=(0, 0, 0, 0)):
    return struct.pack("<4B2h4B", *uv, *destination, *style)


def packed_tim(width, height, cells, rows, image_y):
    palette = []
    for row in range(rows):
        shift = 0 if row < 8 else 2
        colors = [0, 1, 0 if row in (5, 13) else 0x8000, 2]
        palette.extend(colors[(index >> shift) & 3] for index in range(16))
    pixels = bytearray(width * height * 2)
    for (x, y), value in cells.items():
        pixels[y * width * 2 + x // 2] |= value << (4 * (x & 1))
    return (
        struct.pack("<II", 16, 8)
        + struct.pack("<I4H", 12 + len(palette) * 2, 304, 0, 16, rows)
        + struct.pack(f"<{len(palette)}H", *palette)
        + struct.pack("<I4H", 12 + len(pixels), 0, image_y, width, height)
        + pixels
    )


def map_bytes(group0, group1=(), *, cells=(), overlay=(), main_width=128):
    template = synthetic_layout(records=1, rows=1, anchors=1)
    offset, size = struct.unpack_from("<II", template, 12)
    projection = template[offset : offset + size]
    main = packed_tim(main_width, 256, dict(cells), 16, 0)
    extra = packed_tim(64, 40, dict(overlay), 1, 216)
    result = bytearray()
    for record in range(9):
        first, second = (group0, group1) if record == 0 else ((), ())
        directory = struct.pack("<IIHH", 1, 12, len(first), len(second)) + b"".join(
            (*first, *second)
        )
        sections = (directory, projection, main, extra)
        header, start = bytearray(36), 36
        struct.pack_into("<I", header, 0, 4)
        for index, section in enumerate(sections):
            struct.pack_into("<II", header, 4 + index * 8, start, len(section))
            start += len(section)
        raw = header + b"".join(sections)
        result.extend(raw + bytes(aligned_block_size(len(raw)) - len(raw)))
    return result


def first_contours(result, group=0):
    assert not isinstance(result, RoomFormatFailure), result
    return result["records"][0]["directory"][0]["primitive_groups"][group][0][
        "contours"
    ]


def test_nonrectangular_coverage_keeps_holes_components_and_signed_origin(context):
    cells = {
        (x, y): 2 for x in range(5) for y in range(5) if x in (0, 4) or y in (0, 4)
    }
    cells[7, 7] = 3
    result = re3_map_geometry.extract_map_contours(
        map_bytes([quad()], cells=cells), context.executable
    )
    variant = first_contours(result)["variants"][0]
    assert variant["cell_count"] == 17
    assert variant["ring_roles"] == ["outer", "hole", "outer"]
    assert set(variant["rings"][0]) == {(-9, 10), (-4, 10), (-4, 15), (-9, 15)}
    assert set(variant["rings"][1]) == {(-8, 11), (-5, 11), (-5, 14), (-8, 14)}
    assert (
        result["conditional_selection"] == result["geometry_ownership"] == "unresolved"
    )
    assert result["geometry_kind"] == "nontransparent-source-texel-contours"
    assert all(key not in result for key in ("rooms", "doors", "completion", "visited"))


def test_palette_word_8000_is_covered_and_variant5_retains_only_its_visible_classes(
    context,
):
    data = map_bytes(
        [quad(uv=(0, 0, 3, 0))], cells={(0, 0): 4, (1, 0): 2, (2, 0): 8, (3, 0): 3}
    )
    variants = first_contours(
        re3_map_geometry.extract_map_contours(data, context.executable)
    )["variants"]
    assert [variant["requested_palette_variant"] for variant in variants] == [0, 2, 5]
    assert [variant["cell_count"] for variant in variants] == [2, 2, 1]
    assert variants[0]["visible_classes"] == [1, 2, 3]
    assert variants[2]["visible_classes"] == [1, 3]
    assert [shade["cell_count"] for shade in variants[0]["shade_contours"]] == [0, 1, 1]


def test_effective_palette_row_selects_the_plane_after_variant_addition(context):
    data = map_bytes(
        [quad(uv=(0, 0, 2, 0), style=(4, 0, 0, 0))],
        cells={(0, 0): 1, (1, 0): 4, (2, 0): 8},
    )
    variants = first_contours(
        re3_map_geometry.extract_map_contours(data, context.executable)
    )["variants"]
    assert [variant["main_clut_row"] for variant in variants] == [4, 6, 9]
    assert [variant["plane_shift"] for variant in variants] == [0, 0, 2]
    assert [variant["cell_count"] for variant in variants] == [1, 1, 2]


def test_style7_preserves_requested_variants_but_forces_effective_zero(context):
    data = map_bytes([quad(style=(7, 1, 0, 0))], cells={(0, 0): 8})
    variants = first_contours(
        re3_map_geometry.extract_map_contours(data, context.executable)
    )["variants"]
    assert [variant["requested_palette_variant"] for variant in variants] == [0, 2, 5]
    assert {variant["effective_palette_variant"] for variant in variants} == {0}
    assert {variant["main_clut_row"] for variant in variants} == {15}
    assert {variant["cell_count"] for variant in variants} == {1}


def test_second_drawing_group_stays_separate_and_has_only_two_variants(context):
    data = map_bytes([], [quad(style=(4, 0, 0, 0))], cells={(0, 0): 1})
    result = re3_map_geometry.extract_map_contours(data, context.executable)
    assert result["records"][0]["directory"][0]["primitive_groups"][0] == []
    variants = first_contours(result, 1)["variants"]
    assert [variant["requested_palette_variant"] for variant in variants] == [0, 2]


def test_shade_contours_keep_detail_inside_the_unchanged_coverage(context):
    cells = {(x, y): 2 for x in range(4) for y in range(4)}
    cells.update({(1, 1): 1, (1, 2): 1})
    data = map_bytes([quad(uv=(0, 0, 3, 3))], cells=cells)
    variant = first_contours(
        re3_map_geometry.extract_map_contours(data, context.executable)
    )["variants"][0]
    assert variant["cell_count"] == 16 and len(variant["rings"][0]) == 4
    detail = variant["shade_contours"][0]
    assert detail["class_index"] == 1 and detail["cell_count"] == 2
    assert set(detail["rings"][0]) == {(-8, 11), (-7, 11), (-7, 13), (-8, 13)}


def test_later_overlay_upload_replaces_the_main_image_words(context):
    data = map_bytes(
        [quad(uv=(0, 216, 0, 216), style=(0, 2, 0, 0))],
        cells={(256, 216): 1},
        overlay={(0, 0): 2},
    )
    variants = first_contours(
        re3_map_geometry.extract_map_contours(data, context.executable)
    )["variants"]
    assert variants[0]["cell_count"] == 1
    assert variants[2]["cell_count"] == 0
    assert variants[2]["rings"] == []


def test_unloaded_texture_words_are_a_failure_instead_of_transparent_coverage(context):
    data = map_bytes([quad(style=(0, 2, 0, 0))], main_width=64)
    result = re3_map_geometry.extract_map_contours(data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert "outside the loaded TIM" in result.detail


@pytest.mark.parametrize(
    "uv", [(8, 0, 3, 0), (0, 8, 0, 3), (0, 0, 255, 0), (0, 0, 0, 255)]
)
def test_directed_and_byte_wrapping_uvs_remain_explicitly_unresolved(context, uv):
    result = re3_map_geometry.extract_map_contours(
        map_bytes([quad(uv=uv)]), context.executable
    )
    assert first_contours(result) == {"status": "unresolved-directed-or-wrapping-uv"}


@pytest.mark.parametrize(
    "section,offset,value,fmt",
    [
        (2, 0, 0, "I"),
        (2, 4, 9, "I"),
        (2, 8, 1, "I"),
        (2, 12, 0, "H"),
        (2, 16, 15, "H"),
        (2, 18, 15, "H"),
        (2, 532, 12, "I"),
        (2, 540, 0, "H"),
        (3, 4, 0, "I"),
        (3, 58, 215, "H"),
    ],
)
def test_tim_contract_failures_are_modeled_before_sampling(
    context, section, offset, value, fmt
):
    data = map_bytes([quad()])
    start = struct.unpack_from("<I", data, 4 + section * 8)[0]
    struct.pack_into("<" + fmt, data, start + offset, value)
    result = re3_map_geometry.extract_map_contours(data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-tim"


def test_full_palette_words_must_repeat_for_the_selected_two_bit_plane(context):
    data = map_bytes([quad()])
    start = struct.unpack_from("<I", data, 20)[0]
    struct.pack_into("<H", data, start + 20 + 4 * 2, 0x8000)
    result = re3_map_geometry.extract_map_contours(data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert "packed two-bit plane" in result.detail


def test_nontransparent_class_zero_is_computed_from_the_supplied_palette(context):
    data = map_bytes([quad(uv=(0, 0, 0, 0))])
    start = struct.unpack_from("<I", data, 20)[0]
    for index in (0, 4, 8, 12):
        struct.pack_into("<H", data, start + 20 + 2 * index, 0x8000)
    variant = first_contours(
        re3_map_geometry.extract_map_contours(data, context.executable)
    )["variants"][0]
    assert 0 in variant["visible_classes"] and variant["cell_count"] == 1
    assert variant["shade_contours"][0]["class_index"] == 0


def test_unsupported_palette_address_cannot_produce_partial_contours(context):
    data = map_bytes([quad(), quad(style=(255, 0, 0, 0))])
    result = re3_map_geometry.extract_map_contours(data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert "outside the supported main palette" in result.detail


def test_executable_identity_is_checked_before_any_texture_interpretation(context):
    result = re3_map_geometry.extract_map_contours(b"", context.executable + b"changed")
    assert isinstance(result, RoomFormatFailure)
    assert result.kind == "map-identity"


def test_failure_in_the_last_record_does_not_return_an_earlier_partial_export(context):
    data = map_bytes([quad()], cells={(0, 0): 2})
    record_size = len(data) // 9
    start = struct.unpack_from("<I", data, 8 * record_size + 20)[0]
    struct.pack_into("<I", data, 8 * record_size + start, 0)
    result = re3_map_geometry.extract_map_contours(data, context.executable)
    assert isinstance(result, RoomFormatFailure)
    assert result.offset == 8 * record_size + start
