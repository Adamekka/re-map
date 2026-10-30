"""Bound the source reads of one synchronous SLUS-00748 effect call.

RE2-STARTUP-004: this parses resource ownership only. The caller must bind the
native revision, exclude rebinding, protect returned bytes and bound the effect
pool before using it for continuation. GPU setup and deferred effects are not
certified here.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.room_write_partitions import SourceRange


class ImmediateEffectFailure(Enum):
    SourceBinding = "effect resource section binding mismatch"
    Command = "unsupported immediate effect command"
    Layout = "invalid immediate effect resource layout"
    BindingRange = "effect binding exceeds audited native table ranges"


@dataclass(frozen=True)
class ImmediateEffectResource:
    resources: tuple[SourceRange, ...]

    def __post_init__(self) -> None:
        assert type(self.resources) is tuple and len(self.resources) == 3
        assert all(isinstance(row, SourceRange) for row in self.resources)
        assert all(
            first.offset + first.width <= second.offset
            for first, second in zip(self.resources, self.resources[1:])
        )


def immediate_effect_resource(
    data: bytes,
    section_offsets: tuple[int, ...],
    retained_floor: int,
    command_offset: int,
) -> ImmediateEffectResource | ImmediateEffectFailure:
    """Recognize a static-matrix 54 call with one bounded resource element."""
    assert type(data) is bytes and type(section_offsets) is tuple
    assert len(section_offsets) == 23 and all(
        type(offset) is int for offset in section_offsets
    )
    assert type(retained_floor) is int and type(command_offset) is int
    if len(data) < 100 or section_offsets != struct.unpack_from("<23I", data, 8):
        return ImmediateEffectFailure.SourceBinding
    if (
        retained_floor != section_offsets[2]
        or not 100 <= retained_floor <= len(data)
        or retained_floor % 4
        or any(offset and not 100 <= offset <= len(data) for offset in section_offsets)
    ):
        return ImmediateEffectFailure.Layout
    if not 100 <= command_offset <= retained_floor - 22:
        return ImmediateEffectFailure.Command
    packet = data[command_offset : command_offset + 22]
    if packet[0] != 0x54 or packet[4:6] != b"\0\0":
        return ImmediateEffectFailure.Command

    ids, reverse = section_offsets[18:20]
    if not (
        100 <= ids <= retained_floor - 8
        and ids % 4 == 0
        and ids + 8 <= reverse <= retained_floor - 4
        and reverse % 4 == 0
    ):
        return ImmediateEffectFailure.Layout
    id_bytes = data[ids : ids + 8]
    if 0xFF not in id_bytes:
        return ImmediateEffectFailure.Layout
    count = id_bytes.index(0xFF)
    identifiers = id_bytes[:count]
    if not identifiers or len(set(identifiers)) != count:
        return ImmediateEffectFailure.Layout
    if packet[2] not in identifiers:
        return ImmediateEffectFailure.Command

    table_start = reverse - (count - 1) * 4
    if table_start < ids + 8:
        return ImmediateEffectFailure.Layout
    starts = {}
    for index, identifier in enumerate(identifiers):
        # This is an audited write window, not an inferred table capacity.
        # The directory pointer must end before pending sound work at D4F18;
        # the data pointer must not reach the directory table at D4E18.
        if (
            0x800D4CD8 + identifier * 4 + 4 > 0x800D4E18
            or 0x800D4E18 + identifier * 4 + 4 > 0x800D4F18
        ):
            return ImmediateEffectFailure.BindingRange
        start = ids + struct.unpack_from("<I", data, reverse - index * 4)[0]
        if not ids + 8 <= start <= table_start - 8 or start % 4:
            return ImmediateEffectFailure.Layout
        starts[identifier] = start
    if len(set(starts.values())) != count:
        return ImmediateEffectFailure.Layout

    selected = packet[2]
    blocks = {}
    for identifier, start in starts.items():
        end = min([table_start, *(value for value in starts.values() if value > start)])
        low_count, high_count = struct.unpack_from("<2H", data, start)
        directory = start + (2 * low_count + high_count + 2) * 4
        # Native initialization binds every ID, even when this command uses
        # only one. All eight subtype halfwords must fit each owned block.
        if not start + 8 <= directory <= end - 16:
            return ImmediateEffectFailure.Layout
        blocks[identifier] = start, end, directory

    selected_start, selected_end, selected_directory = blocks[selected]
    subtype = packet[3] & 7
    entry = (
        selected_directory
        + 4 * struct.unpack_from("<H", data, selected_directory + subtype * 2)[0]
    )
    if not selected_directory + 16 <= entry <= selected_end - 32:
        return ImmediateEffectFailure.Layout
    if struct.unpack_from("<H", data, entry)[0] != 1:
        return ImmediateEffectFailure.Layout
    # The allocator skips the group's four-byte header and the first record's
    # four-byte header, then copies six words. More elements need another bound.
    return ImmediateEffectResource(
        tuple(
            sorted(
                (
                    SourceRange(ids, 8),
                    SourceRange(table_start, count * 4),
                    SourceRange(selected_start, selected_end - selected_start),
                ),
                key=lambda region: region.offset,
            )
        )
    )
