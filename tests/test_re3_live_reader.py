"""RE3-LIVE-001: lifecycle, source freshness and moving-pose regressions."""

import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re3_native_contracts import coherent as coherent  # noqa: PLC0414

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re3 import source_witnesses
from games.re3.capture_data import CODE_WINDOWS
from games.re3.live_reader import (
    CurrentRoomFailure,
    CurrentRoomObservation,
    read_current_room,
)
from games.re3.room_data import decode_room
from tracker.polling import PollStatus


@pytest.fixture
def live(coherent, monkeypatch):
    first = coherent.source
    other = bytearray(first.rdt)
    decoded = decode_room(first.rdt)
    struct.pack_into("<i", other, decoded["section_words"][7] + 4, 700)
    second = replace(
        first,
        path="CD_DATA/STAGE1/R101.ARD",
        room_number=1,
        ard_lba=first.ard_lba + 10,
        rdt=bytes(other),
    )
    executable = bytearray(coherent.executable)
    table = struct.unpack_from("<I", executable, 0x800 + 0x9DFD0 - 0x10000)[0]
    struct.pack_into("<H", executable, 0x800 + table - 0x80010000 + 2, 0x107)
    struct.pack_into(
        "<2I",
        executable,
        0x800 + 0x946A4 - 0x10000 + 8 * 0x107,
        second.ard_size | 0xA5000000,
        second.ard_lba | 0xC3000000,
    )
    # Synthetic identity seams exercise the real mandatory native/catalog
    # binders without storing owned executable or RDT assets in the repository.
    monkeypatch.setattr(
        source_witnesses, "EXECUTABLE_SHA256", hashlib.sha256(executable).hexdigest()
    )
    sources = (first, second)
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
    monkeypatch.setattr(
        source_witnesses,
        "_SOURCE_CATALOG_SHA256",
        hashlib.sha256(
            json.dumps(manifest, separators=(",", ":")).encode()
        ).hexdigest(),
    )
    catalog = source_witnesses.bind_source_catalog(bytes(executable), sources)
    assert isinstance(catalog, source_witnesses.SourceCatalog)
    ram = coherent.ram
    struct.pack_into("<I", ram, 0xCC858, 0x08000000)
    struct.pack_into("<I", ram, 0xCCD94, 0x800CCBC4)
    ram[0xCCBC8] = 1
    struct.pack_into("<3i", ram, 0xCCBF8, -123456789, 0, 64032)
    struct.pack_into("<H", ram, 0xCCC32, 4095)
    struct.pack_into("<b", ram, 0xCCBCD, -2)
    return catalog, ram, coherent.base


def test_current_room_observation_has_raw_pose_and_no_tracker_facts(live):
    catalog, ram, _ = live
    calls = []

    def read(address, width):
        calls.append((address, width))
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        )

    result = read_current_room(catalog, read)
    assert result == CurrentRoomObservation(
        RoomId(0, 0),
        0,
        "CD_DATA/STAGE1/R100.ARD",
        0x80100000,
        (-123456789, 0, 64032),
        4095,
        -2,
    )
    assert calls[4:6] == [(0x800D1F2C, 80), (0x800CC830, 1384)]
    assert len(calls) == 22 and max(width for _, width in calls) <= 4096
    assert not any(
        name in vars(result) for name in ("items", "doors", "completion", "visits")
    )


@pytest.mark.parametrize("index", range(1, 23))
@pytest.mark.parametrize("short", [False, True])
def test_every_transport_read_failure_is_modeled(live, index, short):
    catalog, ram, _ = live
    count = 0

    def read(address, width):
        nonlocal count
        count += 1
        if count == index:
            return MemRead(short, b"", "" if short else "disconnected")
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        )

    result = read_current_room(catalog, read)
    assert isinstance(result, CurrentRoomFailure)
    assert result.status is PollStatus.ReadFailure
    assert count == index


@pytest.mark.parametrize("address", CODE_WINDOWS)
def test_revision_windows_are_checked_on_each_poll(live, address):
    catalog, ram, _ = live
    ram[address - 0x80000000] ^= 1
    result = read_current_room(
        catalog,
        lambda at, width: MemRead(
            True, bytes(ram[at - 0x80000000 : at - 0x80000000 + width]), ""
        ),
    )
    assert isinstance(result, CurrentRoomFailure)
    assert result.status is PollStatus.WrongGame


@pytest.mark.parametrize(
    "address,width,value,status",
    [
        (0xCC858, 4, 0, PollStatus.NonGameplay),
        (0xCC858, 4, 0x18000000, PollStatus.NonGameplay),
        (0xCC858, 4, 0x08000080, PollStatus.UnsupportedSettings),
        (0xC79CC, 4, 1, PollStatus.UnsupportedSettings),
        (0xCC858, 4, 0x08400000, PollStatus.Retry),
        (0xC7960, 1, 1, PollStatus.Retry),
        (0xCC858, 4, 0x08000100, PollStatus.Retry),
        (0xD1F30, 4, 1, PollStatus.Retry),
        (0xE01E7, 1, 1, PollStatus.NonGameplay),
        (0xD4434, 1, 1, PollStatus.NonGameplay),
        (0xCCBA0, 4, 0x01000000, PollStatus.NonGameplay),
        (0xCCBA0, 4, 0x80000000, PollStatus.NonGameplay),
        (0xCC858, 4, 0x08000200, PollStatus.Retry),
        (0xCC858, 4, 0x08000400, PollStatus.Retry),
        (0xCCBA4, 4, 0x40000000, PollStatus.Retry),
        (0xCCD94, 4, 0, PollStatus.Retry),
        (0xCCBC8, 1, 0, PollStatus.Retry),
        (0xCCC0A, 2, 0x8000, PollStatus.Retry),
        (0xD1F76, 2, 0xFFFF, PollStatus.Retry),
        (0xD1F78, 2, 0xFFFF, PollStatus.Retry),
        (0xD1F7A, 2, 0xFFFF, PollStatus.Retry),
        (0xD1F7A, 2, 255, PollStatus.Retry),
        (0xCC870, 4, 0x80110000, PollStatus.Retry),
        (0xCC86C, 4, 0x80100001, PollStatus.Retry),
        (0xD1F78, 2, 2, PollStatus.UnsupportedRoom),
    ],
)
def test_native_lifecycle_and_source_gates(live, address, width, value, status):
    catalog, ram, _ = live
    ram[address : address + width] = value.to_bytes(width, "little")
    result = read_current_room(
        catalog,
        lambda at, size: MemRead(
            True, bytes(ram[at - 0x80000000 : at - 0x80000000 + size]), ""
        ),
    )
    assert isinstance(result, CurrentRoomFailure)
    assert result.status is status


def test_restored_easy_and_hard_are_reread_without_a_mode_latch(live):
    catalog, ram, _ = live

    def read(at, size):
        return MemRead(True, bytes(ram[at - 0x80000000 : at - 0x80000000 + size]), "")

    assert isinstance(read_current_room(catalog, read), CurrentRoomObservation)
    struct.pack_into("<I", ram, 0xCC858, 0x08000100)
    struct.pack_into("<I", ram, 0xD1F30, 1)
    result = read_current_room(catalog, read)
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.UnsupportedSettings
    )
    struct.pack_into("<I", ram, 0xCC858, 0x08000000)
    struct.pack_into("<I", ram, 0xD1F30, 0)
    struct.pack_into("<i", ram, 0xCCBF8, 900)
    assert read_current_room(catalog, read).position == (900, 0, 64032)


def test_normal_movement_does_not_require_stationary_pose(live):
    catalog, ram, _ = live
    pose_reads = 0

    def read(address, width):
        nonlocal pose_reads
        if address == 0x800CC830:
            pose_reads += 1
            if pose_reads == 2:
                struct.pack_into("<3i", ram, 0xCCBF8, 500, 100, -500)
                struct.pack_into("<H", ram, 0xCCC32, 10)
        return MemRead(
            True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width]), ""
        )

    result = read_current_room(catalog, read)
    assert isinstance(result, CurrentRoomObservation)
    assert result.position == (-123456789, 0, 64032) and result.facing == 4095


def test_transition_after_pose_cannot_pair_old_pose_with_reused_base(live):
    catalog, ram, base = live
    transitioned = False

    def read(address, width):
        nonlocal transitioned
        result = bytes(ram[address - 0x80000000 : address - 0x80000000 + width])
        if address == 0x800CC830 and not transitioned:
            transitioned = True
            other = catalog.lookup(0, 1)
            ram[base : base + other.rdt_size] = other.source.rdt
            for offset, expected in other.ranges(0x80100000):
                ram[base + offset : base + offset + len(expected)] = expected
            struct.pack_into("<h", ram, 0xD1F78, 1)
            struct.pack_into("<i", ram, 0xCCBF8, 900)
        return MemRead(True, result, "")

    result = read_current_room(catalog, read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


def test_source_witness_is_rechecked_between_polls(live):
    catalog, ram, base = live
    witness = catalog.lookup(0, 0)

    def read(at, size):
        return MemRead(True, bytes(ram[at - 0x80000000 : at - 0x80000000 + size]), "")

    assert isinstance(read_current_room(catalog, read), CurrentRoomObservation)
    ram[base + witness.cameras_offset + 4] ^= 1
    result = read_current_room(catalog, read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


def test_source_witness_is_rechecked_within_one_poll(live):
    catalog, ram, base = live
    changed = False

    def read(address, width):
        nonlocal changed
        packet = bytes(ram[address - 0x80000000 : address - 0x80000000 + width])
        if address == 0x80000000 + base + 1 and not changed:
            changed = True
            ram[base + 1] ^= 1
        return MemRead(True, packet, "")

    result = read_current_room(catalog, read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry
    assert result.detail == "Room source changed during read"


@pytest.mark.parametrize(
    "address,width,value",
    [
        (0xC7960, 1, 1),
        (0xCC858, 4, 0x08400000),
        (0xCC858, 4, 0x08000100),
        (0xD1F30, 4, 1),
        (0xCC870, 4, 0x80110000),
        (0xCC86C, 4, 0x80110000),
        (0xD1F78, 2, 1),
        (0xCCBCD, 1, 0),
        (0xCCD94, 4, 0),
        (0xCCBC8, 1, 2),
    ],
)
def test_guard_change_during_source_reads_retries(live, address, width, value):
    catalog, ram, base = live
    changed = False

    def read(at, size):
        nonlocal changed
        if at == 0x80000000 + base + 1 and not changed:
            changed = True
            ram[address : address + width] = value.to_bytes(width, "little")
        return MemRead(True, bytes(ram[at - 0x80000000 : at - 0x80000000 + size]), "")

    result = read_current_room(catalog, read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


def test_unrelated_animation_and_mutable_source_work_do_not_block_pose(live):
    catalog, ram, base = live
    ram[base] ^= 1
    struct.pack_into("<I", ram, base + 92, 0x80190000)
    struct.pack_into("<I", ram, 0xCC878, 0x80190000)
    struct.pack_into("<I", ram, 0xCC858, 0x28001000)
    result = read_current_room(
        catalog,
        lambda at, size: MemRead(
            True, bytes(ram[at - 0x80000000 : at - 0x80000000 + size]), ""
        ),
    )
    assert isinstance(result, CurrentRoomObservation)
