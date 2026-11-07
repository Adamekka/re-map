"""RE3-MAP-015: prospective current-row group-0 observations from owned sources.

This is neither hardware L2 admission nor loaded-MAP cache binding. Native row
visibility and per-quad predicates grant no tracker exploration or ownership.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import NamedTuple

from games.bit_flags import msb_flag_location
from games.re3 import EXECUTABLE_SHA256, MAP_U_SHA256
from games.re3.map_conditions import (
    QuadRequirement,
    decode_map_conditions,
    group_zero_metadata_allows,
    quad_requirements,
)
from games.re3.map_data import (
    MapPositionContext,
    MapPositionLayout,
    NativeMapPosition,
    compile_map_position_layout,
    decode_map_layout,
    native_group_for_record,
    resolve_native_map_position,
)
from games.re3.map_predicate import predicate_flags
from games.re3.map_row_predicates import native_row_flags, native_row_visible
from games.re3.map_shape_predicates import (
    GROUP_ZERO_PREDICATES,
    GROUP_ZERO_SYSTEM_FLAG,
    group_zero_shape_allowed,
)
from games.re3.room_data import RoomFormatFailure


class MapFeatureRecord(NamedTuple):
    group_zero_counts: tuple[int, ...]
    layer_mode: int
    requirements: tuple[QuadRequirement, ...]


@dataclass(frozen=True, slots=True, init=False)
class MapFeatureLayout:
    position_layout: MapPositionLayout
    records: tuple[MapFeatureRecord, ...]
    flag_words: tuple[tuple[int, int], ...]
    _authority: tuple[
        MapPositionLayout,
        tuple[MapFeatureRecord, ...],
        tuple[tuple[int, int], ...],
    ] = field(repr=False, compare=False)

    def __init__(self) -> None:
        # Only the source compiler constructs authority. A replaceable receipt
        # would let callers replace both a derivation and its matching data.
        raise TypeError("Use compile_map_feature_layout with owned source bytes")

    def _assert_compiled(self) -> None:
        assert type(self) is MapFeatureLayout
        assert type(self._authority) is tuple and len(self._authority) == 3
        assert all(
            actual is bound
            for actual, bound in zip(
                (self.position_layout, self.records, self.flag_words), self._authority
            )
        ), "map feature derivations must retain their compiler authority"


@dataclass(frozen=True)
class NativeCurrentRowFeatures:
    map_position: NativeMapPosition
    overlay_u16: int
    actor_floor_i8: int
    native_map_acquired: bool
    native_row_visible: bool
    group_zero_count: int
    group_zero_allowed_indices: tuple[int, ...]
    flag_words: tuple[tuple[int, int], ...]


def compile_map_feature_layout(
    data: bytes, executable: bytes
) -> MapFeatureLayout | RoomFormatFailure:
    """Compile pinned inputs once, keeping no mutable source/decoder aliases."""
    assert type(data) is bytes and type(executable) is bytes
    if (
        hashlib.sha256(data).hexdigest() != MAP_U_SHA256
        or hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256
    ):
        return RoomFormatFailure(
            "map-feature-identity",
            0,
            "Map features require the pinned MAP and executable",
        )
    position = compile_map_position_layout(data, executable)
    if isinstance(position, RoomFormatFailure):
        return position
    layout = decode_map_layout(data, executable)
    if isinstance(layout, RoomFormatFailure):
        return layout
    conditions = decode_map_conditions(data, executable)
    if isinstance(conditions, RoomFormatFailure):
        return conditions
    records = []
    flag_pairs = [GROUP_ZERO_SYSTEM_FLAG]
    for family in GROUP_ZERO_PREDICATES:
        flag_pairs.extend(predicate_flags(family.condition))
    for record, table in zip(layout["records"], conditions["records"], strict=True):
        counts = tuple(len(row["primitive_groups"][0]) for row in record["directory"])
        if len(counts) > 256 or any(count > 256 for count in counts):
            return RoomFormatFailure(
                "map-feature-source",
                record["offset"],
                "Source row or group-0 quad count exceeds native byte arguments",
            )
        requirements = quad_requirements(table["requirements"])
        for entry in requirements:
            if entry.row >= len(counts) or entry.primitive >= counts[entry.row]:
                return RoomFormatFailure(
                    "map-feature-source",
                    table["table_offset"],
                    "Group-0 metadata target is outside its source quads",
                )
            flag_pairs.append((entry.bank, entry.flag_index))
        group = native_group_for_record(record["index"])
        for row in range(len(counts)):
            flag_pairs.extend(native_row_flags(group, row))
        records.append(
            MapFeatureRecord(
                counts, record["layer_metadata"]["raw_prefix"][4], requirements
            )
        )
    words: dict[int, int] = {}
    for bank, index in flag_pairs:
        address, mask = msb_flag_location(bank, index)
        # Visit indices combine a native group 0-6 with a byte-sized row;
        # predicate and metadata indices fit inside the same checked bound.
        if (
            not 0 <= index <= 64 * 6 + 255
            or address % 4
            or not 0x80000000 <= address <= 0x801FFFFC
        ):
            return RoomFormatFailure(
                "map-feature-source", 0, "Flag dependency exceeds physical PS1 RAM"
            )
        words[address] = words[address] | mask if address in words else mask
    result = object.__new__(MapFeatureLayout)
    # All retained values are compiler-created tuples/frozen records. The
    # authority keeps object identity, so equal mutable substitutions cannot pass.
    values = (position, tuple(records), tuple(sorted(words.items())))
    for name, value in zip(
        ("position_layout", "records", "flag_words"), values, strict=True
    ):
        object.__setattr__(result, name, value)
    object.__setattr__(result, "_authority", values)
    result._assert_compiled()
    return result


def resolve_current_row_features(
    layout: MapFeatureLayout,
    context: MapPositionContext,
    actor_floor: int,
    overlay: int,
    words: tuple[tuple[int, int], ...],
) -> NativeCurrentRowFeatures | RoomFormatFailure:
    """Consume a complete, checked flag context after the fresh transaction."""
    layout._assert_compiled()
    if (
        layout.position_layout.map_sha256 != MAP_U_SHA256
        or layout.position_layout.executable_sha256 != EXECUTABLE_SHA256
    ):
        return RoomFormatFailure(
            "map-feature-identity",
            0,
            "Map features require the pinned MAP and executable",
        )
    assert type(actor_floor) is int and -128 <= actor_floor <= 127
    assert type(overlay) is int and 0 <= overlay <= 0xFFFF
    if overlay:
        return RoomFormatFailure(
            "map-feature-context", 0xE0278, "Nonzero map overlay is unsupported"
        )
    assert type(words) is tuple
    assert all(
        type(pair) is tuple and len(pair) == 2 and type(pair[0]) is int
        for pair in words
    )
    assert tuple(address for address, _ in words) == tuple(
        address for address, _ in layout.flag_words
    ), "every compiled dependency must have been read"
    assert all(type(value) is int and 0 <= value <= 0xFFFFFFFF for _, value in words)
    position = resolve_native_map_position(layout.position_layout, context)
    if isinstance(position, RoomFormatFailure):
        return position
    flags = dict(words)
    required_masks = dict(layout.flag_words)

    def flag(bank: int, index: int) -> int:
        address, mask = msb_flag_location(bank, index)
        assert address in flags, "predicate used an undeclared flag word"
        assert required_masks[address] & mask == mask
        return flags[address] & mask

    group, row = position.native_stage_room
    record = layout.records[position.map_record_index]
    acquired = bool(flag(0x800D2124, group))
    count = record.group_zero_counts[row]
    allowed = tuple(
        primitive
        for primitive in range(count)
        if group_zero_metadata_allows(
            record.requirements, row, primitive, acquired, flag
        )
        and group_zero_shape_allowed(
            group, row, primitive, group << 8 | row, actor_floor, overlay, flag
        )
    )
    return NativeCurrentRowFeatures(
        position,
        overlay,
        actor_floor,
        acquired,
        native_row_visible(
            group,
            row,
            group << 8 | row,
            context.stage,
            record.layer_mode,
            position.native_layer_index,
            flag,
        ),
        count,
        allowed,
        words,
    )
