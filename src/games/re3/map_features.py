"""RE3-MAP-015/016: prospective current-row observations from owned sources.

This is neither hardware L2 admission nor loaded-MAP cache binding. Native row
visibility and per-quad predicates grant no tracker exploration or ownership.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import NamedTuple

from games.bit_flags import msb_flag_location
from games.re3 import EXECUTABLE_SHA256, MAP_U_SHA256
from games.re3.map_conditions import (
    DETAIL_STYLE_BANKS,
    DetailRequirement,
    DetailStyleCondition,
    QuadRequirement,
    decode_map_conditions,
    decode_map_detail_conditions,
    detail_metadata,
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
from games.re3.map_detail_predicates import (
    GROUP_ONE_PREDICATES,
    GROUP_ONE_SYSTEM_FLAG,
    DetailSelection,
    NativeMapDetail,
    select_group_one_detail,
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


class MapDetailRecord(NamedTuple):
    native_kinds: tuple[tuple[int, ...], ...]
    requirements: tuple[DetailRequirement, ...]
    styles: tuple[DetailStyleCondition, ...]


class CurrentMapFeatureScope(Enum):
    GroupZero = "group-zero"
    GroupZeroAndOne = "group-zero-and-one"


@dataclass(frozen=True, slots=True, init=False)
class MapFeatureLayout:
    position_layout: MapPositionLayout
    records: tuple[MapFeatureRecord, ...]
    flag_words: tuple[tuple[int, int], ...]
    detail_records: tuple[MapDetailRecord, ...]
    detail_flag_words: tuple[tuple[int, int], ...]
    _authority: tuple[
        MapPositionLayout,
        tuple[MapFeatureRecord, ...],
        tuple[tuple[int, int], ...],
        tuple[MapDetailRecord, ...],
        tuple[tuple[int, int], ...],
    ] = field(repr=False, compare=False)

    def __init__(self) -> None:
        # Only the source compiler constructs authority. A replaceable receipt
        # would let callers replace both a derivation and its matching data.
        raise TypeError("Use compile_map_feature_layout with owned source bytes")

    def _assert_compiled(self) -> None:
        assert type(self) is MapFeatureLayout
        assert type(self._authority) is tuple and len(self._authority) == 5
        assert all(
            actual is bound
            for actual, bound in zip(
                (
                    self.position_layout,
                    self.records,
                    self.flag_words,
                    self.detail_records,
                    self.detail_flag_words,
                ),
                self._authority,
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


@dataclass(frozen=True)
class NativeCurrentRowDetails:
    group_zero: NativeCurrentRowFeatures
    native_map_acquisition_byte: int
    group_one_count: int
    group_one_allowed: tuple[NativeMapDetail, ...]


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
    details = decode_map_detail_conditions(data, executable)
    if isinstance(details, RoomFormatFailure):
        return details
    records = []
    detail_records = []
    flag_pairs = [GROUP_ZERO_SYSTEM_FLAG]
    detail_pairs = [GROUP_ONE_SYSTEM_FLAG]
    for family in GROUP_ONE_PREDICATES:
        detail_pairs.extend(predicate_flags(family.condition))
    for family in GROUP_ZERO_PREDICATES:
        flag_pairs.extend(predicate_flags(family.condition))
    for record, table, detail_table in zip(
        layout["records"], conditions["records"], details["records"], strict=True
    ):
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
        kinds = tuple(
            tuple(quad["style_bytes"][0] for quad in row["primitive_groups"][1])
            for row in record["directory"]
        )
        if any(len(row) > 256 for row in kinds):
            return RoomFormatFailure(
                "map-feature-source",
                record["offset"],
                "Source group-1 quad count exceeds native byte arguments",
            )
        requirements, styles = detail_metadata(detail_table)
        # Native scans ignore unmatched targets. The owned style table itself
        # contains one, so retain it and its dependency rather than repairing it.
        detail_pairs.extend((entry.bank, entry.flag_index) for entry in requirements)
        detail_pairs.extend(
            (DETAIL_STYLE_BANKS[entry.selector], entry.flag_index)
            for entry in styles
            if entry.selector < len(DETAIL_STYLE_BANKS)
        )
        detail_records.append(MapDetailRecord(kinds, requirements, styles))

    def compile_words(
        pairs: list[tuple[int, int]],
    ) -> tuple[tuple[int, int], ...] | RoomFormatFailure:
        words: dict[int, int] = {}
        for bank, index in pairs:
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
        return tuple(sorted(words.items()))

    group_zero_words = compile_words(flag_pairs)
    if isinstance(group_zero_words, RoomFormatFailure):
        return group_zero_words
    detail_words = compile_words(flag_pairs + detail_pairs)
    if isinstance(detail_words, RoomFormatFailure):
        return detail_words
    result = object.__new__(MapFeatureLayout)
    # All retained values are compiler-created tuples/frozen records. The
    # authority keeps object identity, so equal mutable substitutions cannot pass.
    values = (
        position,
        tuple(records),
        group_zero_words,
        tuple(detail_records),
        detail_words,
    )
    for name, value in zip(
        (
            "position_layout",
            "records",
            "flag_words",
            "detail_records",
            "detail_flag_words",
        ),
        values,
        strict=True,
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
    *,
    scope: CurrentMapFeatureScope = CurrentMapFeatureScope.GroupZero,
) -> NativeCurrentRowFeatures | NativeCurrentRowDetails | RoomFormatFailure:
    """Consume a complete, checked flag context after the fresh transaction."""
    layout._assert_compiled()
    assert type(scope) is CurrentMapFeatureScope
    dependencies = (
        layout.flag_words
        if scope is CurrentMapFeatureScope.GroupZero
        else layout.detail_flag_words
    )
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
        address for address, _ in dependencies
    ), "every compiled dependency must have been read"
    assert all(type(value) is int and 0 <= value <= 0xFFFFFFFF for _, value in words)
    position = resolve_native_map_position(layout.position_layout, context)
    if isinstance(position, RoomFormatFailure):
        return position
    flags = dict(words)
    required_masks = dict(dependencies)

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
    features = NativeCurrentRowFeatures(
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
    if scope is CurrentMapFeatureScope.GroupZero:
        return features
    detail_record = layout.detail_records[position.map_record_index]
    # Native SB stores the raw helper mask's low byte, never bool(acquired).
    acquisition_byte = flag(0x800D2124, group) & 0xFF
    details = []
    for index, kind in enumerate(detail_record.native_kinds[row]):
        detail = select_group_one_detail(
            detail_record.requirements,
            detail_record.styles,
            group,
            row,
            index,
            kind,
            group << 8 | row,
            actor_floor,
            context.stage,
            acquisition_byte,
            flag,
        )
        if detail is not DetailSelection.Reject:
            details.append(detail)
    return NativeCurrentRowDetails(
        features, acquisition_byte, len(detail_record.native_kinds[row]), tuple(details)
    )
