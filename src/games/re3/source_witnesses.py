"""Shared RE3-NATIVE-001 source witnesses, separate from gameplay admission."""

from __future__ import annotations

import hashlib
import json
import struct
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from games.re3 import EXECUTABLE_SHA256
from games.re3.capture_data import CODE_WINDOWS, RAM_SIZE
from games.re3.room_data import RoomFormatFailure, decode_room, room_section_end
from games.runtime_identity import RuntimeSignature

# This metadata digest binds the complete owned 169-source corpus. A caller's
# internally consistent subset must not silently become a complete catalog.
_SOURCE_CATALOG_SHA256 = (
    "2e044734044d39327bdfabcb40c81a6f51e4f97f9859f0609e36217ce5fadaba"
)
_CATALOG_BINDING = object()
# The external GDB memory reader limits each reply to 4096 bytes.
_MAX_READ = 4096


@dataclass(frozen=True)
class RoomSource:
    path: str
    stage_digit: int
    room_number: int
    ard_lba: int
    ard_size: int
    rdt: bytes

    def __post_init__(self) -> None:
        assert isinstance(self.path, str) and self.path
        assert type(self.stage_digit) is int and 1 <= self.stage_digit <= 7
        assert type(self.room_number) is int and 0 <= self.room_number <= 255
        assert type(self.ard_lba) is int and self.ard_lba >= 0
        assert type(self.ard_size) is int and self.ard_size > 0
        assert type(self.rdt) is bytes


@dataclass(frozen=True)
class SourceWitness:
    """Unbound immutable source compilation; this grants no runtime admission."""

    source: RoomSource
    rdt_size: int
    camera_count: int
    section_words: tuple[int, ...]
    cameras_offset: int
    cameras: bytes
    zones_offset: int
    zones: bytes
    initializer_offset: int
    initializer_end: int
    normalized_fingerprint: str

    def __post_init__(self) -> None:
        # Value equality also accepts mutable bytes-like buffers and numeric
        # aliases. Neither may survive an immutable compilation/catalog seal.
        assert isinstance(self.source, RoomSource)
        assert all(
            type(value) is int
            for value in (
                self.rdt_size,
                self.camera_count,
                self.cameras_offset,
                self.zones_offset,
                self.initializer_offset,
                self.initializer_end,
            )
        )
        assert type(self.section_words) is tuple
        assert all(type(word) is int for word in self.section_words)
        assert type(self.cameras) is bytes and type(self.zones) is bytes
        assert type(self.normalized_fingerprint) is str

    def ranges(self, base: int) -> tuple[tuple[int, bytes], ...] | RoomFormatFailure:
        """Return relative offsets/expected bytes, each within the read limit."""
        assert type(base) is int
        if base % 4 or not 0x80000000 <= base <= 0x80000000 + RAM_SIZE - self.rdt_size:
            return RoomFormatFailure(
                "source-binding", base, "Loaded RDT cannot contain its owned source"
            )
        # Native relocation includes opaque slot 2. Prefix byte 0 and header
        # slot 21 become runtime work, so neither is an immutable witness.
        header = struct.pack(
            "<21I",
            *((word + base) & 0xFFFFFFFF if word else 0 for word in self.section_words),
        )
        cameras = bytearray(self.cameras)
        for offset in range(28, len(cameras), 32):
            value = struct.unpack_from("<I", cameras, offset)[0]
            # Unlike header words, even a zero camera mask receives the base.
            struct.pack_into("<I", cameras, offset, (value + base) & 0xFFFFFFFF)
        result = []
        for offset, expected in (
            (1, self.source.rdt[1:8]),
            (8, header),
            (self.cameras_offset, bytes(cameras)),
            (self.zones_offset, self.zones),
        ):
            for start in range(0, len(expected), _MAX_READ):
                result.append((offset + start, expected[start : start + _MAX_READ]))
        return tuple(result)


@dataclass(frozen=True)
class BoundSource(SourceWitness):
    """A compiled source whose ARD metadata agrees with the pinned EXE."""

    native_file_index: int

    def __post_init__(self) -> None:
        super().__post_init__()
        assert type(self.native_file_index) is int


@dataclass(frozen=True)
class _CatalogBinding:
    sources: tuple[BoundSource, ...]
    runtime_signature: RuntimeSignature
    seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        assert self.seal is _CATALOG_BINDING


@dataclass(frozen=True)
class SourceCatalog:
    sources: tuple[BoundSource, ...]
    runtime_signature: RuntimeSignature
    _binding: _CatalogBinding = field(repr=False, compare=False)
    _by_selector: Mapping[tuple[int, int], BoundSource] = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        # dataclasses.replace retains private fields. Bind every compiled field
        # and the signature so copying a catalog cannot reuse its old validation
        # after removing sources or weakening a derived camera/header witness.
        assert isinstance(self._binding, _CatalogBinding)
        assert self._binding.seal is _CATALOG_BINDING
        assert type(self.sources) is tuple
        assert self.sources == self._binding.sources
        assert self.runtime_signature == self._binding.runtime_signature
        # Polling selects one source without iterating the complete corpus.
        # The backing dictionary is created here and never exposed for mutation.
        index = {
            (witness.source.stage_digit - 1, witness.source.room_number): witness
            for witness in self.sources
        }
        assert len(index) == len(self.sources)
        object.__setattr__(self, "_by_selector", MappingProxyType(index))

    def lookup(self, stage: int, room: int) -> BoundSource | RoomFormatFailure:
        assert type(stage) is int and type(room) is int
        try:
            return self._by_selector[stage, room]
        except KeyError:
            return RoomFormatFailure(
                "source-selector", 0, "Native stage/room has no supported owned source"
            )


def compile_source_witness(source: RoomSource) -> SourceWitness | RoomFormatFailure:
    """Compile owned bytes only; native revision/catalog binding is separate."""
    decoded = decode_room(source.rdt)
    if isinstance(decoded, RoomFormatFailure):
        return RoomFormatFailure(
            "source-witness",
            decoded.offset,
            f"Invalid room source {source.path}: {decoded.detail}",
        )
    words = tuple(decoded["section_words"][:21])
    cameras_offset = words[7]
    camera_count = len(decoded["cameras"])
    cameras = source.rdt[cameras_offset : cameras_offset + camera_count * 32]
    zones_offset = words[8]
    zones_end = room_section_end(decoded["section_words"], 8, len(source.rdt))
    zones = source.rdt[zones_offset:zones_end]
    # Prefix/header/cameras fix their own extents. Excluding zones from this
    # conservative ambiguity key avoids mistaking different zone lengths for
    # uniqueness when one source's bounded witness is a prefix of another's.
    # Opaque word 2 is still checked by ranges(), but cannot distinguish this
    # key: its unrestricted nonzero value can wrap to a relocated zero.
    fingerprint_words = words[:2] + (0,) + words[3:]
    fingerprint = hashlib.sha256(
        source.rdt[1:8] + struct.pack("<21I", *fingerprint_words) + cameras
    ).hexdigest()
    return SourceWitness(
        source,
        len(source.rdt),
        camera_count,
        words,
        cameras_offset,
        cameras,
        zones_offset,
        zones,
        decoded["initializer"]["offset"],
        decoded["initializer"]["end"],
        fingerprint,
    )


def bind_diagnostic_sources(
    executable: bytes, sources: tuple[RoomSource, ...]
) -> tuple[BoundSource, ...] | RoomFormatFailure:
    """Bind possibly partial offline sources, never a complete live context."""
    assert type(sources) is tuple
    if hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256:
        return RoomFormatFailure(
            "executable", 0, "Executable differs from the required SLUS_009.23 SHA256"
        )

    def word(address: int, width: int) -> int | RoomFormatFailure:
        offset = 0x800 + address - 0x80010000
        if address % width or not 0x800 <= offset <= len(executable) - width:
            return RoomFormatFailure(
                "executable",
                offset,
                "Native room/file table points outside the executable payload",
            )
        return int.from_bytes(executable[offset : offset + width], "little")

    identifiers = set()
    bound = []
    for source in sources:
        identifier = source.stage_digit, source.room_number
        if identifier in identifiers:
            return RoomFormatFailure(
                "source-catalog", 0, "Duplicate source stage/room identifier"
            )
        identifiers.add(identifier)
        witness = compile_source_witness(source)
        if isinstance(witness, RoomFormatFailure):
            return witness
        table = word(0x8009DFD0 + 4 * (source.stage_digit - 1), 4)
        if isinstance(table, RoomFormatFailure):
            return table
        file_index = word(table + 2 * source.room_number, 2)
        if isinstance(file_index, RoomFormatFailure):
            return file_index
        record = 0x800946A4 + 8 * file_index
        size, lba = word(record, 4), word(record + 4, 4)
        if isinstance(size, RoomFormatFailure):
            return size
        if isinstance(lba, RoomFormatFailure):
            return lba
        # High metadata bytes are native tags, not part of size or sector LBA.
        if (size & 0xFFFFFF, lba & 0xFFFFFF) != (source.ard_size, source.ard_lba):
            return RoomFormatFailure(
                "source-catalog",
                0,
                f"Native selector table disagrees with owned ARD {source.path}",
            )
        bound.append(BoundSource(**vars(witness), native_file_index=file_index))
    return tuple(bound)


def bind_source_catalog(
    executable: bytes, sources: tuple[RoomSource, ...]
) -> SourceCatalog | RoomFormatFailure:
    """Bind the complete revision corpus before a live reader can use it."""
    bound = bind_diagnostic_sources(executable, sources)
    if isinstance(bound, RoomFormatFailure):
        return bound
    manifest = sorted(
        [
            source.path,
            source.stage_digit,
            source.room_number,
            source.ard_lba,
            source.ard_size,
            len(source.rdt),
            hashlib.sha256(source.rdt).hexdigest(),
        ]
        for source in sources
    )
    digest = hashlib.sha256(
        json.dumps(manifest, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != _SOURCE_CATALOG_SHA256:
        return RoomFormatFailure(
            "source-catalog",
            0,
            "Owned source catalog differs from the complete revision corpus",
        )
    paths, fingerprints = set(), set()
    for witness in bound:
        if (
            witness.source.path in paths
            or witness.normalized_fingerprint in fingerprints
        ):
            return RoomFormatFailure(
                "source-catalog",
                0,
                "Owned source catalog has duplicate paths or ambiguous witnesses",
            )
        paths.add(witness.source.path)
        fingerprints.add(witness.normalized_fingerprint)
    windows = b"".join(
        executable[0x800 + address - 0x80010000 : 0x800 + address - 0x80010000 + 32]
        for address in CODE_WINDOWS
    )
    signature = RuntimeSignature(CODE_WINDOWS, 32, hashlib.sha256(windows).hexdigest())
    return SourceCatalog(
        bound, signature, _CatalogBinding(bound, signature, _CATALOG_BINDING)
    )
