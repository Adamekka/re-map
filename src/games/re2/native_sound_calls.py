"""RE2-SCENARIO-012: exact cached-reader callsite facts, no global helper right."""

from __future__ import annotations

import hashlib
import struct
from enum import Enum

from games.re2.native_control import NativeScalarCall, native_bytes, native_nonyielding


class SoundReaderFailure(Enum):
    Binding = "cached sound reader native callsite binding mismatch"


_SOUND_WINDOWS = (
    (
        0x8005C040,
        1444,
        "c624b90054a3a4f184362de9a84b8963e59987ebab169d8216ba3870e9008717",
    ),
    (
        0x800528E8,
        204,
        "a1ba5a876705c13fe6a79e057bcb708267c3f24ef5726bc669c8ac9c100deeb6",
    ),
    (
        0x8002C904,
        72,
        "10a8a6e04c6cb4e52829a9235b2fb78ff1f8d556fb3e4b9a170d1cae728e0114",
    ),
    (
        0x8001BF10,
        788,
        "b3904de9b426bfe322efebd19a5ca8a4adc1128fddc738ce08dee738931f3a8a",
    ),
    (
        0x8005C92C,
        68,
        "d09bce8968ba0b1bcf804a856af27b2a82e0392c62c569ee44296fe1cef60b5c",
    ),
    (
        0x80015FE8,
        64,
        "a4e0ed85f10c3fbd7407b675ae13e878afb357cdcc02a2fb1bd161ca1b0c955f",
    ),
    (
        0x800395B8,
        220,
        "2c55652d10fe774da97268f570f3fc34699f8ff263601f9e07c6a11f26d84221",
    ),
    (
        0x800397B8,
        44,
        "728e04372e096d039ca37cf493082a85c6831d13ea4f72da358c86b9e1fe7ae0",
    ),
    (
        0x800397E4,
        52,
        "a04eed9ac36f838658e74ac7f50c1544ae6e4169f33d34ce6550be4ade733ef7",
    ),
)
_SOUND_CALLS = (
    (0x8005C1B4, 0x800395B8, (1, 130, 100, 0)),
    (0x8005C1C8, 0x800395B8, (9, 85, 10, 1)),
    (0x8005C1E0, 0x800395B8, (3, 50, 100, 0)),
    (0x8005C1F4, 0x800395B8, (5, 85, 0, 3)),
    (0x8005C308, 0x800395B8, (1, 130, 100, 0)),
    (0x8005C31C, 0x800395B8, (9, 85, 10, 1)),
    (0x8005C33C, 0x800395B8, (3, 50, 100, 0)),
    (0x8005C350, 0x800395B8, (5, 85, 10, 3)),
)


def sound_reader_scalar_calls(
    executable: bytes,
) -> tuple[NativeScalarCall, ...] | SoundReaderFailure:
    """Bind literal dominance and the complete guarded helper/leaf bodies."""
    assert type(executable) is bytes
    try:
        if any(
            hashlib.sha256(native_bytes(executable, at, width)).hexdigest() != digest
            for at, width, digest in _SOUND_WINDOWS
        ):
            return SoundReaderFailure.Binding
        incoming = {0x8005C040}
        sites = []
        for at in range(0x8005C040, 0x8005C5E4, 4):
            word = int.from_bytes(native_bytes(executable, at, 4), "little")
            op = word >> 26
            if op in (1, 4, 5, 6, 7):
                distance = struct.unpack("<h", (word & 65535).to_bytes(2, "little"))[0]
                incoming.add(at + 4 + distance * 4)
            elif op in (2, 3):
                target = (at + 4) & 0xF0000000 | (word & 0x3FFFFFF) << 2
                if op == 2:
                    incoming.add(target)
                else:
                    incoming.add(at + 8)
                    if target == 0x800395B8:
                        sites.append(at)
        if sites != [at for at, _, _ in _SOUND_CALLS]:
            return SoundReaderFailure.Binding
        for at, target, arguments in _SOUND_CALLS:
            if any(at - 12 < dest <= at + 4 for dest in incoming):
                return SoundReaderFailure.Binding
            for pos, reg, value in zip(
                (at - 12, at - 8, at - 4, at + 4), range(4, 8), arguments, strict=True
            ):
                word = int.from_bytes(native_bytes(executable, pos, 4), "little")
                # Zero is encoded either as addiu or the native move from zero.
                if word != (0x24000000 | reg << 16 | value) and not (
                    value == 0 and word == (reg << 11 | 0x21)
                ):
                    return SoundReaderFailure.Binding
            if arguments[0] not in (1, 9, 3, 5):
                return SoundReaderFailure.Binding

        # The complete helper saves A0 in S0 before both leaf calls. Its only
        # other S0 write restores the caller's register at return. Positive S0
        # excludes both break7 and break6 for every possible numerator.
        def writes_s0(word):
            op, function = word >> 26, word & 63
            return (
                op == 0 and function not in (8, 9, 12, 13) and word >> 11 & 31 == 16
            ) or (
                op in (8, 9, 10, 11, 12, 13, 14, 15, 32, 33, 35, 36, 37)
                and word >> 16 & 31 == 16
            )

        if native_bytes(executable, 0x800395C0, 4) != bytes.fromhex("21808000") or [
            at
            for at in range(0x800395B8, 0x80039694, 4)
            if writes_s0(int.from_bytes(native_bytes(executable, at, 4), "little"))
        ] != [0x800395C0, 0x80039684]:
            return SoundReaderFailure.Binding
        for entry, end in ((0x800397B8, 0x800397E4), (0x800397E4, 0x80039818)):
            if any(
                writes_s0(int.from_bytes(native_bytes(executable, at, 4), "little"))
                for at in range(entry, end, 4)
            ) or not native_nonyielding(executable, entry, {}):
                return SoundReaderFailure.Binding
        return tuple(
            NativeScalarCall(at, target, arguments)
            for at, target, arguments in _SOUND_CALLS
        )
    except (ValueError, struct.error):
        return SoundReaderFailure.Binding
