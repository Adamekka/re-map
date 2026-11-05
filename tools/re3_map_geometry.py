"""Candidate numeric source-texel contours for the owned RE3 map.

RE3-MAP-005 keeps each quad and palette variant separate. Texture coverage
does not establish room ownership, floor labels or tracker visibility.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from map_geometry import trace_floor_cells

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from games.re3.map_data import decode_map_layout
from games.re3.room_data import RoomFormatFailure


def extract_map_contours(data: bytes, executable: bytes) -> dict | RoomFormatFailure:
    """Export palette-dependent coverage after the mandatory executable gate.

    Failure kinds distinguish MAP-file and executable byte offsets.
    Directed or byte-wrapping UVs remain explicitly unresolved. No pixels,
    palette colors, conditional admission or merged room outlines are exported.
    """
    result = decode_map_layout(data, executable)
    if isinstance(result, RoomFormatFailure):
        return result
    for record in result["records"]:

        def read_tim(section_index):
            section = record["sections"][section_index]
            start = record["offset"] + section["offset"]
            end = start + section["size"]
            if end - start < 20 or struct.unpack_from("<II", data, start) != (16, 8):
                return RoomFormatFailure(
                    "map-tim", start, "expected a 4-bit indexed TIM"
                )
            size, x, y, width, height = struct.unpack_from("<I4H", data, start + 8)
            expected_rows = 16 if section_index == 2 else 1
            image = start + 8 + size
            # The loader relocates palette Y but retains X. The renderer's
            # CLUT register addresses word X=304, so another X cannot be inferred.
            if (
                (x, width, height) != (304, 16, expected_rows)
                or size != 12 + width * height * 2
                or image + 12 > end
            ):
                return RoomFormatFailure(
                    "map-tim", start + 8, "unsupported CLUT extent"
                )
            image_size, ix, iy, iw, ih = struct.unpack_from("<I4H", data, image)
            # RE3-MAP-005: uploads occur in order. Main Y is replaced; overlay
            # Y retains its file value plus the texture page's 256-row origin.
            bx, by = (448, 256) if section_index == 2 else (512, 256 + iy)
            if (
                # Keep supported atlas formats bound to this revision's audit.
                (section_index == 2 and (iw not in (64, 128) or ih != 256))
                or (section_index == 3 and (iw, iy, ih) != (64, 216, 40))
                or not 0 < iw <= 1024 - bx
                or not 0 < ih <= 512 - by
                or image_size != 12 + iw * ih * 2
                or image + image_size != end
            ):
                return RoomFormatFailure(
                    "map-tim", image, "invalid loaded image extent"
                )
            palettes = [
                struct.unpack_from("<16H", data, start + 20 + row * 32)
                for row in range(height)
            ]
            if section_index == 2:
                for row, palette in enumerate(palettes):
                    shift = 0 if row < 8 else 2
                    if any(
                        palette[index] != palette[((index >> shift) & 3) << shift]
                        for index in range(16)
                    ):
                        return RoomFormatFailure(
                            "map-tim",
                            start + 20 + row * 32,
                            "CLUT does not preserve its packed two-bit plane",
                        )
            return {
                "source_image_word_rect": [ix, iy, iw, ih],
                "loaded_image_word_rect": [bx, by, iw, ih],
                "source_clut_word_rect": [x, y, width, height],
                "loaded_clut_word_rect": [
                    x,
                    490 if section_index == 2 else 506,
                    width,
                    height,
                ],
                "palettes": palettes,
                "image_offset": image + 12,
            }

        textures = []
        vram = {}
        for section_index in (2, 3):
            texture = read_tim(section_index)
            if isinstance(texture, RoomFormatFailure):
                return texture
            textures.append(texture)
            bx, by, width, height = texture["loaded_image_word_rect"]
            for y in range(height):
                for x in range(width):
                    # Later overlay uploads replace overlapping main-image words.
                    vram[bx + x, by + y] = struct.unpack_from(
                        "<H", data, texture["image_offset"] + 2 * (y * width + x)
                    )[0]
        record["texture_uploads"] = [
            {
                key: texture[key]
                for key in (
                    "source_image_word_rect",
                    "loaded_image_word_rect",
                    "source_clut_word_rect",
                    "loaded_clut_word_rect",
                )
            }
            for texture in textures
        ]
        for row in record["directory"]:
            for group_index, primitives in enumerate(row["primitive_groups"]):
                # Native callers at 0x8007275C and 0x80070530..3C supply only
                # these variants. Their admission conditions remain unresolved.
                variants = (0, 2, 5) if group_index == 0 else (0, 2)
                for primitive in primitives:
                    u0, v0, u1, v1 = primitive["uv_inclusive"]
                    if u1 < u0 or v1 < v0 or u1 == 255 or v1 == 255:
                        # The GPU receives byte-wrapped upper endpoints. Linear
                        # cell sampling would invent interpolation for these cases.
                        primitive["contours"] = {
                            "status": "unresolved-directed-or-wrapping-uv",
                        }
                        continue
                    kind, page_style, _, _ = primitive["style_bytes"]
                    page_x = (((page_style >> 1) + 7) & 15) * 64
                    x0, y0, _, _ = primitive["destination_xyxy"]
                    classes = {
                        (shift, value): set() for shift in (0, 2) for value in range(4)
                    }
                    for v in range(v0, v1 + 1):
                        for u in range(u0, u1 + 1):
                            point = (page_x + u // 4, 256 + v)
                            if point not in vram:
                                return RoomFormatFailure(
                                    "map-contours",
                                    primitive["offset"],
                                    "quad samples outside the loaded TIM images",
                                )
                            index = (vram[point] >> (4 * (u & 3))) & 15
                            destination = (x0 + u - u0, y0 + v - v0)
                            for shift in (0, 2):
                                classes[shift, (index >> shift) & 3].add(destination)

                    def contour(cells):
                        if not cells:
                            # Transparent draws have known empty coverage. This
                            # says nothing about whether their room is empty.
                            return {"cell_count": 0, "rings": [], "ring_roles": []}
                        rings, _ = trace_floor_cells(cells)
                        return {
                            "cell_count": len(cells),
                            "rings": [ring for _, ring in rings],
                            "ring_roles": [
                                "outer" if area > 0 else "hole" for area, _ in rings
                            ],
                        }

                    masks, shades, exported = {}, {}, []
                    for requested in variants:
                        # The native renderer forces kind 7 to variant zero.
                        effective = 0 if kind == 7 else requested
                        clut_row = (page_style & 1) * 8 + kind + effective
                        if clut_row >= 16:
                            return RoomFormatFailure(
                                "map-contours",
                                primitive["offset"] + 8,
                                "quad CLUT is outside the supported main palette",
                            )
                        # Variant addition can cross into the other CLUT half.
                        # Style parity alone would select the wrong packed plane.
                        shift = 0 if clut_row < 8 else 2
                        palette = textures[0]["palettes"][clut_row]
                        visible = tuple(
                            value for value in range(4) if palette[value << shift] != 0
                        )
                        key = shift, visible
                        try:
                            if key not in masks:
                                masks[key] = contour(
                                    set().union(
                                        *(classes[shift, value] for value in visible)
                                    )
                                )
                            for value in visible:
                                if (shift, value) not in shades:
                                    shades[shift, value] = contour(
                                        classes[shift, value]
                                    )
                        except ValueError as exc:
                            return RoomFormatFailure(
                                "map-contours",
                                primitive["offset"],
                                f"cannot trace source coverage: {exc}",
                            )
                        exported.append(
                            {
                                "requested_palette_variant": requested,
                                "effective_palette_variant": effective,
                                "main_clut_row": clut_row,
                                "plane_shift": shift,
                                "visible_classes": list(visible),
                                **masks[key],
                                "shade_contours": [
                                    {"class_index": value, **shades[shift, value]}
                                    for value in visible
                                ],
                            }
                        )
                    primitive["contours"] = {"status": "decoded", "variants": exported}
    return {
        **result,
        "schema": "re3-static-map-contours-v1",
        "geometry_kind": "nontransparent-source-texel-contours",
        "conditional_selection": "unresolved",
        "geometry_ownership": "unresolved",
    }
