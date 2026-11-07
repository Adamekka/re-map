"""RE3-COLLECT-002: bind one canonical current collectible, without list rights."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass, field

from games.bit_flags import msb_flag_location
from games.re3 import EXECUTABLE_SHA256
from games.re3.room_data import RoomFormatFailure, decode_room
from games.re3.source_witnesses import BoundSource, SourceCatalog

_COLLECTIBLE_BINDING = object()


@dataclass(frozen=True)
class _CollectibleDerivation:
    catalog: SourceCatalog
    source: BoundSource
    source_sha256: str
    procedure_index: int
    packet_offset: int
    packet: bytes
    raw_type: int
    source_amount: int
    acquisition_index: int
    acquisition_address: int
    acquisition_mask: int
    seal: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        # Equality alone also accepts mutable bytearray packets and bool/int
        # aliases. Require immutable exact field types before comparing receipts.
        assert isinstance(self.catalog, SourceCatalog)
        assert isinstance(self.source, BoundSource)
        assert type(self.source_sha256) is str and len(self.source_sha256) == 64
        assert type(self.packet) is bytes
        assert all(
            type(value) is int
            for value in (
                self.procedure_index,
                self.packet_offset,
                self.raw_type,
                self.source_amount,
                self.acquisition_index,
                self.acquisition_address,
                self.acquisition_mask,
            )
        )
        assert self.seal is _COLLECTIBLE_BINDING


@dataclass(frozen=True)
class CollectibleBinding:
    catalog: SourceCatalog
    source: BoundSource
    source_sha256: str
    procedure_index: int
    packet_offset: int
    packet: bytes
    raw_type: int
    source_amount: int
    acquisition_index: int
    acquisition_address: int
    acquisition_mask: int
    _binding: _CollectibleDerivation = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        # A copied receipt cannot qualify changed packet fields, source,
        # catalog or flag addressing after dataclasses.replace.
        assert isinstance(self._binding, _CollectibleDerivation)
        assert self._binding.seal is _COLLECTIBLE_BINDING
        assert self._binding == _CollectibleDerivation(
            self.catalog,
            self.source,
            self.source_sha256,
            self.procedure_index,
            self.packet_offset,
            self.packet,
            self.raw_type,
            self.source_amount,
            self.acquisition_index,
            self.acquisition_address,
            self.acquisition_mask,
            _COLLECTIBLE_BINDING,
        )


def bind_collectible_source(
    executable: bytes,
    catalog: SourceCatalog,
    stage: int,
    room: int,
    procedure_index: int,
) -> CollectibleBinding | RoomFormatFailure:
    """Qualify an ordinary inventory packet at a native procedure entry.

    Registration, acquisition state and gameplay admission require fresh live
    reads. A canonical entry does not prove its procedure executes.
    """
    assert type(executable) is bytes and isinstance(catalog, SourceCatalog)
    if hashlib.sha256(executable).hexdigest() != EXECUTABLE_SHA256:
        return RoomFormatFailure(
            "executable", 0, "Executable differs from the required SLUS_009.23 SHA256"
        )
    if (
        type(stage) is not int
        or stage != 0
        or type(room) is not int
        or not 0 <= room <= 255
        or type(procedure_index) is not int
        or not 0 <= procedure_index <= 255
    ):
        return RoomFormatFailure(
            "collectible-input",
            0,
            "Collectible binding requires stage 0 and byte selectors",
        )
    source = catalog.lookup(stage, room)
    if isinstance(source, RoomFormatFailure):
        return source
    decoded = decode_room(source.source.rdt)
    assert not isinstance(decoded, RoomFormatFailure)
    procedures = decoded["initializer"]["procedures"]
    if procedure_index >= len(procedures):
        return RoomFormatFailure(
            "collectible-source", source.initializer_offset, "Procedure is absent"
        )
    procedure = procedures[procedure_index]
    offset = procedure["offset"]
    if procedure["size"] < 22:
        return RoomFormatFailure(
            "collectible-source",
            offset,
            "Procedure cannot contain the complete item packet",
        )
    packet = source.source.rdt[offset : offset + 22]
    raw_type, amount, index = struct.unpack_from("<3H", packet, 14)
    # Restrict the first schema to the observed rectangular, immediate UI
    # path. F8+ indices and flag1 use different native event/animation paths.
    if (
        packet[0] != 0x67
        or packet[1] >= 32
        or packet[2:4] != b"\x02\x31"
        or packet[21] & 1
        or raw_type >= 256
        or index >= 0xF8
    ):
        return RoomFormatFailure(
            "collectible-source", offset, "Unsupported ordinary collectible packet"
        )
    category_offset = 0x800 + 0x800A0514 - 0x80010000 + 4 * raw_type
    bank_offset = 0x800 + 0x8009E414 - 0x80010000
    if category_offset + 4 > len(executable) or bank_offset + 4 > len(executable):
        return RoomFormatFailure(
            "executable",
            category_offset,
            "Collectible native tables exceed the executable",
        )
    if executable[category_offset] != 5:
        return RoomFormatFailure(
            "collectible-source", offset + 14, "Unsupported native inventory category"
        )
    bank = struct.unpack_from("<I", executable, bank_offset)[0]
    # Stage0's creator/getter and pickup-success setter share this bank. Later
    # stages select it differently and need their own checked source contract.
    if bank != 0x800D2008:
        return RoomFormatFailure(
            "executable", bank_offset, "Unsupported native collectible flag bank"
        )
    address, mask = msb_flag_location(bank, index)
    derivation = _CollectibleDerivation(
        catalog,
        source,
        decoded["sha256"],
        procedure_index,
        offset,
        packet,
        raw_type,
        amount,
        index,
        address,
        mask,
        _COLLECTIBLE_BINDING,
    )
    return CollectibleBinding(
        catalog,
        source,
        decoded["sha256"],
        procedure_index,
        offset,
        packet,
        raw_type,
        amount,
        index,
        address,
        mask,
        derivation,
    )
