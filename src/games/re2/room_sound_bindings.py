"""Bound room EDT/VAB resources and tone writes, without lifetime guarantees.

RE2-PUZZLE-002: callers must separately exclude rebinding/compaction and protect
these bytes from source writes before using them as a native effect bound.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import Enum

from games.re2.room_write_partitions import SourceRange


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
    data: bytes,
    section_offsets: tuple[int, ...],
    retained_floor: int,
    samples: frozenset[int],
) -> RoomSoundBindings | RoomSoundBindingFailure:
    """Parse source ranges only; section 22 does not grant a lifetime proof."""
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
    return RoomSoundBindings(
        (SourceRange(edt, 192), SourceRange(vab, boundary - vab)),
        tuple(SourceRange(offset, 1) for offset in sorted(writes)),
    )
