"""Bound room EDT/VAB resources and tone writes, without lifetime guarantees.

RE2-PUZZLE-002: callers must separately exclude rebinding/compaction and protect
these bytes from source writes before using them as a native effect bound.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.room_write_partitions import SourceRange


@dataclass(frozen=True)
class InitialSoundLayout:
    source_data: bytes
    section_offsets: tuple[int, ...]
    retained_floor: int


@dataclass(frozen=True)
class CompactedSoundLayout:
    origin: InitialSoundLayout
    mask: int
    retained_indices: tuple[int, ...]
    directory_offset: int
    directory_pairs: tuple[tuple[int, int], ...]
    edt: int
    vab: int
    retained_floor: int
    copy_writes: tuple[SourceRange, ...]


class RoomSoundBindingFailure(Enum):
    SourceBinding = "room sound section binding mismatch"
    Layout = "invalid room sound resource layout"
    Sample = "invalid room sound sample binding"


@dataclass(frozen=True)
class RoomSoundBindings:
    resources: tuple[SourceRange, ...]
    tone_writes: tuple[SourceRange, ...]

    def __post_init__(self) -> None:
        assert type(self.resources) is tuple and len(self.resources) == 2
        assert all(isinstance(row, SourceRange) for row in self.resources)
        edt, vab = self.resources
        assert edt.width == 192 and edt.offset + edt.width == vab.offset
        assert type(self.tone_writes) is tuple and all(
            isinstance(row, SourceRange)
            and row.width == 1
            and vab.offset <= row.offset < vab.offset + vab.width
            for row in self.tone_writes
        )
        offsets = tuple(row.offset for row in self.tone_writes)
        assert tuple(sorted(set(offsets))) == offsets


def room_sound_bindings(
    layout: InitialSoundLayout | CompactedSoundLayout,
    samples: frozenset[int],
) -> RoomSoundBindings | RoomSoundBindingFailure:
    """Parse immutable origin bytes, then validate explicit current coordinates.

    Neither layout grants a lifetime or native/source execution capability.
    """
    assert type(layout) in (InitialSoundLayout, CompactedSoundLayout)
    origin = layout if type(layout) is InitialSoundLayout else layout.origin
    assert type(origin) is InitialSoundLayout
    data, section_offsets, retained_floor = (
        origin.source_data,
        origin.section_offsets,
        origin.retained_floor,
    )
    assert type(data) is bytes and type(section_offsets) is tuple
    assert len(section_offsets) == 23 and all(
        type(offset) is int for offset in section_offsets
    )
    assert type(retained_floor) is int
    assert type(samples) is frozenset and all(type(sample) is int for sample in samples)
    if len(data) < 100 or section_offsets != struct.unpack_from("<23I", data, 8):
        return RoomSoundBindingFailure.SourceBinding
    if not 100 <= retained_floor <= len(data) or any(
        offset > len(data) for offset in section_offsets
    ):
        return RoomSoundBindingFailure.Layout
    if any(not 0 <= sample < 48 for sample in samples):
        return RoomSoundBindingFailure.Sample
    edt, vab = section_offsets[:2]
    # A section ends at the next section or EOF. This does not establish that
    # the native loader keeps that range or leaves its binding unchanged.
    boundary = min([len(data), *(offset for offset in section_offsets if offset > vab)])
    if not (
        100 <= edt
        and edt % 4 == 0
        and vab == edt + 192
        and vab % 4 == 0
        and vab + 32 <= boundary <= retained_floor
    ):
        return RoomSoundBindingFailure.Layout
    programs_count = struct.unpack_from("<H", data, vab + 18)[0]
    if (
        data[vab : vab + 4] != b"pBAV"
        or struct.unpack_from("<I", data, vab + 4)[0] != 7
        or not 1 <= programs_count <= 128
        or vab + 0x820 + programs_count * 0x200 + 0x200 > boundary
    ):
        return RoomSoundBindingFailure.Layout
    writes = set()
    for sample in samples:
        packet = data[edt + sample * 4 : edt + sample * 4 + 4]
        if packet == b"\xff" * 4:
            # Native sound dispatch treats this EDT entry as absent.
            continue
        program, tone, extra, voice = (
            packet[1] & 0x7F,
            packet[2] >> 4,
            packet[3] >> 5,
            packet[3] & 0x1F,
        )
        if (
            program >= programs_count
            or tone + extra >= 16
            or voice + extra >= 24
            or tone + extra >= data[vab + 32 + program * 16]
        ):
            return RoomSoundBindingFailure.Sample
        for index in range(extra + 1):
            offset = vab + 0x821 + program * 0x200 + (tone + index) * 0x20
            if offset >= boundary:
                return RoomSoundBindingFailure.Sample
            writes.add(offset)
    resources = (SourceRange(edt, 192), SourceRange(vab, boundary - vab))
    tones = tuple(SourceRange(offset, 1) for offset in sorted(writes))
    if type(layout) is CompactedSoundLayout:
        # Old header aliases remain immutable file metadata, not live ends.
        # Re-derive every moved field instead of trusting a frozen caller record.
        if compacted_sound_layout(origin, layout.mask) != layout:
            return RoomSoundBindingFailure.Layout
        shift = layout.edt - edt
        resources = tuple(SourceRange(r.offset + shift, r.width) for r in resources)
        tones = tuple(SourceRange(r.offset + shift, r.width) for r in tones)
        if not (
            resources[0].offset == layout.edt
            and resources[1].offset == layout.vab
            and resources[1].offset + resources[1].width == layout.retained_floor
            and all(
                layout.edt <= r.offset < r.offset + r.width <= layout.retained_floor
                for r in (*resources, *tones)
            )
        ):
            return RoomSoundBindingFailure.Layout
    return RoomSoundBindings(resources, tones)


def compacted_sound_layout(
    origin: InitialSoundLayout, mask: int
) -> CompactedSoundLayout | RoomSoundBindingFailure:
    """Bound one native forward-copy pass; repeated compaction is not implied."""
    assert type(origin) is InitialSoundLayout and type(mask) is int
    data, sections, floor = (
        origin.source_data,
        origin.section_offsets,
        origin.retained_floor,
    )
    if (
        len(data) < 100
        or len(sections) != 23
        or sections != struct.unpack_from("<23I", data, 8)
    ):
        return RoomSoundBindingFailure.SourceBinding
    if not 0 <= mask <= 0xFFFFFFFF:
        return RoomSoundBindingFailure.Layout
    section = sections[22]
    if (
        not 100
        <= section
        < sections[0]
        < sections[1]
        < floor
        == sections[2]
        <= len(data)
    ):
        return RoomSoundBindingFailure.Layout
    directory, count = struct.unpack_from("<II", data, section)
    if not (
        1 <= count <= 32
        and section + 8 <= section + directory
        and section + directory + count * 8 == sections[0]
        and section % 4 == directory % 4 == 0
    ):
        return RoomSoundBindingFailure.Layout
    pairs = tuple(
        struct.unpack_from("<II", data, section + directory + 8 * i)
        for i in range(count)
    )
    if not all(
        8 <= first < second < end <= directory
        for (first, second), end in zip(
            pairs, (*[p[0] for p in pairs[1:]], directory), strict=True
        )
    ):
        return RoomSoundBindingFailure.Layout
    kept = tuple(i for i in range(count) if not mask & (0x80000000 >> i))
    if not kept:
        # Native forward copy executes at least once even for length zero.
        # Exclude that unsafe domain instead of treating it as an empty copy.
        return RoomSoundBindingFailure.Layout
    cursor, packed, writes = pairs[0][0], [], []
    for index, (first, second) in enumerate(pairs):
        if index not in kept:
            continue
        if cursor != first:
            # Native copy ends at the next SECOND offset. Cursor advancement
            # below deliberately uses the next FIRST offset instead.
            size = (
                directory - first if index == count - 1 else pairs[index + 1][1] - first
            )
            if not 0 < size or cursor > first or cursor + size > directory:
                return RoomSoundBindingFailure.Layout
            writes.append(SourceRange(section + cursor, size))
            writes.extend(
                (
                    SourceRange(section + directory + len(packed) * 8, 4),
                    SourceRange(section + directory + len(packed) * 8 + 4, 4),
                )
            )
        packed.append((cursor, second - first + cursor))
        cursor += (
            directory - first if index == count - 1 else pairs[index + 1][0] - first
        )
    new_directory = section + cursor
    edt = new_directory + len(packed) * 8
    vab = edt + sections[1] - sections[0]
    current_floor = edt + floor - sections[0]
    if (
        not section + 8 <= new_directory < edt <= sections[0]
        or not edt < vab < current_floor <= floor
    ):
        return RoomSoundBindingFailure.Layout
    writes.extend(
        (
            SourceRange(new_directory, len(packed) * 8),
            SourceRange(section, 4),
            SourceRange(section + 4, 4),
            SourceRange(edt, floor - sections[0]),
            SourceRange(8, 4),
            SourceRange(12, 4),
        )
    )
    if any(
        r.offset not in (8, 12)
        and not section <= r.offset <= floor - r.width
        or r.offset < floor
        and sections[0] < r.offset + r.width
        for r in writes
    ):
        return RoomSoundBindingFailure.Layout
    return CompactedSoundLayout(
        origin,
        mask,
        kept,
        new_directory,
        tuple(packed),
        edt,
        vab,
        current_floor,
        tuple(writes),
    )
