"""RE3-COLLECT-002: singular registration/condition facts, never room clearance."""

import hashlib
import json
import struct
from dataclasses import replace
from types import SimpleNamespace

import pytest
from test_re3_native_contracts import coherent as coherent  # noqa: PLC0414
from test_re3_room_data import synthetic_ard

from emulator.duckstation_gdb import MemRead
from games.re3 import collectibles, live_reader, source_witnesses
from games.re3.collectibles import CollectibleBinding, bind_collectible_source
from games.re3.live_reader import (
    CurrentCollectibleObservation,
    CurrentRoomFailure,
    read_current_collectible,
)
from games.re3.room_data import RoomFormatFailure
from tracker.polling import PollStatus


@pytest.fixture
def item_case(coherent, monkeypatch):
    packet = bytearray(22)
    packet[:4] = bytes((0x67, 13, 2, 0x31))
    struct.pack_into("<3H", packet, 14, 0x73, 1, 2)

    def build(packet, first_size, category, bank):
        end = 188 + first_size + 2
        room = bytearray(end + 6)
        room[:184] = coherent.source.rdt[:184]
        struct.pack_into("<I", room, 8 + 13 * 4, end)
        struct.pack_into("<I", room, 8 + 17 * 4, end + 2)
        struct.pack_into("<2H", room, 184, 4, 4 + first_size)
        room[188 : 188 + len(packet)] = packet
        ard = synthetic_ard(room)
        source = replace(coherent.source, rdt=bytes(room), ard_size=len(ard))
        other = bytearray(room)
        struct.pack_into("<i", other, 100, 700)
        second = replace(
            source,
            path="CD_DATA/STAGE1/R101.ARD",
            room_number=1,
            ard_lba=source.ard_lba + 10,
            rdt=bytes(other),
        )
        sources = (source, second)
        executable = bytearray(coherent.executable)
        table = struct.unpack_from("<I", executable, 0x800 + 0x9DFD0 - 0x10000)[0]
        for index, item in enumerate(sources):
            file_index = 0x100 if index == 0 else 0x107
            struct.pack_into(
                "<H", executable, 0x800 + table - 0x80010000 + index * 2, file_index
            )
            struct.pack_into(
                "<2I",
                executable,
                0x800 + 0x946A4 - 0x10000 + file_index * 8,
                item.ard_size,
                item.ard_lba,
            )
        raw_type = int.from_bytes(packet[14:16], "little")
        # The synthetic native table is explicit test input to the real binder.
        # Unsupported high types still fit this file and must reject by schema.
        executable[0x800 + 0xA0514 - 0x10000 + raw_type * 4] = category
        struct.pack_into("<I", executable, 0x800 + 0x9E414 - 0x10000, bank)
        executable = bytes(executable)
        digest = hashlib.sha256(executable).hexdigest()
        for module in (source_witnesses, collectibles, live_reader):
            monkeypatch.setattr(module, "EXECUTABLE_SHA256", digest)
        manifest = sorted(
            [
                s.path,
                s.stage_digit,
                s.room_number,
                s.ard_lba,
                s.ard_size,
                len(s.rdt),
                hashlib.sha256(s.rdt).hexdigest(),
            ]
            for s in sources
        )
        monkeypatch.setattr(
            source_witnesses,
            "_SOURCE_CATALOG_SHA256",
            hashlib.sha256(
                json.dumps(manifest, separators=(",", ":")).encode()
            ).hexdigest(),
        )
        catalog = source_witnesses.bind_source_catalog(executable, sources)
        assert isinstance(catalog, source_witnesses.SourceCatalog)
        bound = catalog.lookup(0, 0)
        ram = bytearray(coherent.ram)
        ram[coherent.base : coherent.base + len(room)] = room
        for offset, expected in bound.ranges(0x80100000):
            ram[coherent.base + offset : coherent.base + offset + len(expected)] = (
                expected
            )
        struct.pack_into("<I", ram, 0xCC858, 0x08000000)
        struct.pack_into("<I", ram, 0xCCD94, 0x800CCBC4)
        ram[0xCCBC8] = 1
        struct.pack_into("<I", ram, 0xCC890 + 4 * packet[1], 0x80100000 + 190)
        binding = bind_collectible_source(executable, catalog, 0, 0, 0)

        def read(address, width):
            return MemRead(
                True, bytes(ram[address - 0x80000000 : address - 0x80000000 + width])
            )

        return SimpleNamespace(
            executable=executable,
            catalog=catalog,
            ram=ram,
            base=coherent.base,
            binding=binding,
            packet=bytes(packet),
            read=read,
        )

    case = build(packet, 24, 5, 0x800D2008)
    assert isinstance(case.binding, CollectibleBinding)
    case.build = build
    return case


def test_one_current_registration_reports_raw_condition_without_tracker_rights(
    item_case,
):
    case = item_case
    calls = []

    def read(address, width):
        calls.append((address, width))
        return case.read(address, width)

    result = read_current_collectible(case.binding, read)
    assert isinstance(result, CurrentCollectibleObservation)
    assert (result.room.source_address, result.packet_offset, result.registry_slot) == (
        0x80100000,
        188,
        13,
    )
    assert (result.raw_type, result.source_amount, result.acquisition_index) == (
        0x73,
        1,
        2,
    )
    assert result.acquisition_set is False
    assert result.executable_sha256 == hashlib.sha256(case.executable).hexdigest()
    assert (
        result.source_rdt_sha256
        == hashlib.sha256(case.binding.source.source.rdt).hexdigest()
    )
    assert len(calls) == 27 and max(width for _, width in calls) <= 4096
    assert not any(
        k in vars(result)
        for k in ("items", "complete", "cleared", "visits", "collected")
    )
    assert calls[4:6] == [(0x800D1F2C, 80), (0x800CC830, 1384)]


@pytest.mark.parametrize("slot,index", [(0, 0), (31, 31), (7, 32), (31, 247)])
def test_native_slot_and_flag_boundaries_use_the_selected_packet(
    item_case, slot, index
):
    packet = bytearray(item_case.packet)
    packet[1] = slot
    struct.pack_into("<H", packet, 18, index)
    case = item_case.build(packet, 24, 5, 0x800D2008)
    assert isinstance(case.binding, CollectibleBinding)
    expected_address = 0x800D2008 + 4 * (index // 32)
    expected_mask = 0x80000000 >> (index % 32)
    assert (case.binding.acquisition_address, case.binding.acquisition_mask) == (
        expected_address,
        expected_mask,
    )
    case.ram[case.base + 190] = 0
    struct.pack_into("<I", case.ram, expected_address - 0x80000000, expected_mask)
    result = read_current_collectible(case.binding, case.read)
    assert isinstance(result, CurrentCollectibleObservation) and result.acquisition_set
    assert (result.registry_slot, result.acquisition_index) == (slot, index)


def test_acquisition_and_earlier_restore_are_fresh_without_inventory_dependency(
    item_case,
):
    case = item_case
    earlier = bytes(case.ram)
    before = read_current_collectible(case.binding, case.read)
    case.ram[case.base + 190] = 0
    struct.pack_into("<I", case.ram, 0xD2008, 0x20000000)
    later = bytes(case.ram)
    acquired = read_current_collectible(case.binding, case.read)
    assert (
        isinstance(acquired, CurrentCollectibleObservation) and acquired.acquisition_set
    )
    # Inventory placement is acceptance evidence, not a condition cache. The
    # real native flag remains useful after rearrangement or consumption.
    case.ram[0xD2134:0xD2138] = b"\xff" * 4
    assert read_current_collectible(case.binding, case.read) == acquired
    case.ram[:] = earlier
    assert read_current_collectible(case.binding, case.read) == before
    case.ram[:] = later
    assert read_current_collectible(case.binding, case.read) == acquired


@pytest.mark.parametrize("acquired", [False, True])
@pytest.mark.parametrize("restore_at", ["packet1", "flag1", "pose", "flag2", "packet2"])
def test_same_room_restore_cannot_pair_old_pose_with_new_acquisition(
    item_case, acquired, restore_at
):
    case = item_case

    def restore(acquisition, position, facing):
        case.ram[case.base + 190] = 0 if acquisition else 2
        struct.pack_into("<I", case.ram, 0xD2008, 0x20000000 if acquisition else 0)
        struct.pack_into("<3i", case.ram, 0xCCBF8, *position)
        struct.pack_into("<H", case.ram, 0xCCC32, facing)

    restore(not acquired, (10, 20, 30), 100)
    packet_reads = flag_reads = 0
    restored = False

    def read(at, size):
        nonlocal packet_reads, flag_reads, restored
        point = ""
        if at == 0x80100000 + 188:
            packet_reads += 1
            point = f"packet{packet_reads}"
        elif at == case.binding.acquisition_address:
            flag_reads += 1
            point = f"flag{flag_reads}"
        elif (at, size) == (0x800CCBF8, 60):
            point = "pose"
        if point == restore_at:
            restore(acquired, (1000, 2000, 3000), 200)
            restored = True
        return case.read(at, size)

    result = read_current_collectible(case.binding, read)
    assert restored
    if restore_at == "packet1":
        assert isinstance(result, CurrentCollectibleObservation)
        assert result.acquisition_set is acquired
        assert result.room.position == (1000, 2000, 3000)
        assert result.room.facing == 200
    else:
        assert isinstance(result, CurrentRoomFailure)
        assert result.status is PollStatus.Retry


@pytest.mark.parametrize(
    "kind,word", [(0, 0), (2, 0x20000000), (1, 0), (5, 0x20000000)]
)
def test_kind_alone_cannot_establish_the_acquisition_condition(item_case, kind, word):
    case = item_case
    case.ram[case.base + 190] = kind
    struct.pack_into("<I", case.ram, 0xD2008, word)
    result = read_current_collectible(case.binding, case.read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


@pytest.mark.parametrize("offset", [i for i in range(22) if i != 2])
def test_every_other_packet_byte_must_match_its_owned_source(item_case, offset):
    case = item_case
    case.ram[case.base + 188 + offset] ^= 1
    result = read_current_collectible(case.binding, case.read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


@pytest.mark.parametrize("index", range(1, 28))
@pytest.mark.parametrize("short", [False, True])
def test_each_transport_failure_withholds_the_whole_observation(
    item_case, index, short
):
    case = item_case
    count = 0

    def read(address, width):
        nonlocal count
        count += 1
        if count == index:
            return MemRead(short, b"", "" if short else "disconnected")
        return case.read(address, width)

    result = read_current_collectible(case.binding, read)
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.ReadFailure
    )
    assert count == index


@pytest.mark.parametrize(
    "address,width,value", [(0xC7961, 1, 1), (0xD1F2C, 4, 0x200), (0xE01E7, 1, 1)]
)
def test_pending_and_active_ui_are_excluded_before_item_reads(
    item_case, address, width, value
):
    case = item_case
    case.ram[address : address + width] = value.to_bytes(width, "little")
    calls = []

    def read(at, size):
        calls.append((at, size))
        return case.read(at, size)

    result = read_current_collectible(case.binding, read)
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.NonGameplay
    )
    assert (case.binding.acquisition_address, 4) not in calls


@pytest.mark.parametrize("pointer", [0, 0xDEADBEEF, 0x80100000 + 192])
def test_only_the_exact_current_registry_pointer_qualifies(item_case, pointer):
    case = item_case
    struct.pack_into("<I", case.ram, 0xCC890 + 4 * 13, pointer)
    calls = []

    def read(at, size):
        calls.append((at, size))
        return case.read(at, size)

    result = read_current_collectible(case.binding, read)
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry
    assert (pointer, 22) not in calls


@pytest.mark.parametrize(
    "changed", ["packet", "kind", "flag", "registry", "request", "phase"]
)
def test_every_consumed_dynamic_field_is_checked_in_the_same_transaction(
    item_case, changed
):
    case = item_case
    packet_reads = flag_reads = 0
    mutated = False

    def read(at, size):
        nonlocal packet_reads, flag_reads, mutated
        if at == 0x80100000 + 188:
            packet_reads += 1
        if at == case.binding.acquisition_address:
            flag_reads += 1
        if not mutated and (
            (changed in ("packet", "kind") and packet_reads == 2)
            or (changed == "flag" and flag_reads == 2)
            or (changed in ("registry", "request", "phase") and packet_reads == 1)
        ):
            mutated = True
            if changed == "packet":
                case.ram[case.base + 188 + 16] ^= 1
            elif changed == "kind":
                case.ram[case.base + 190] = 0
            elif changed == "flag":
                struct.pack_into("<I", case.ram, 0xD2008, 0x20000000)
            elif changed == "registry":
                struct.pack_into("<I", case.ram, 0xCC890 + 4 * 13, 0)
            elif changed == "request":
                struct.pack_into("<I", case.ram, 0xD1F2C, 0x200)
            else:
                case.ram[0xC7961] = 1
        return case.read(at, size)

    result = read_current_collectible(case.binding, read)
    assert mutated
    assert isinstance(result, CurrentRoomFailure) and result.status is PollStatus.Retry


def test_unrelated_flags_slots_and_moving_pose_do_not_require_stationary_ram(item_case):
    case = item_case
    count = 0

    def read(at, size):
        nonlocal count
        if at == case.binding.acquisition_address:
            count += 1
            if count == 2:
                struct.pack_into("<I", case.ram, 0xD2008, 1)
                struct.pack_into("<I", case.ram, 0xCC890 + 4 * 14, 0x80180000)
                struct.pack_into("<3i", case.ram, 0xCCBF8, 100, 200, 300)
        return case.read(at, size)

    result = read_current_collectible(case.binding, read)
    assert (
        isinstance(result, CurrentCollectibleObservation) and not result.acquisition_set
    )
    assert result.room.position == (0, 0, 0)


def test_other_source_and_restored_easy_are_rejected_fresh(item_case):
    case = item_case
    earlier = bytes(case.ram)
    struct.pack_into("<h", case.ram, 0xD1F78, 1)
    result = read_current_collectible(case.binding, case.read)
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.UnsupportedRoom
    )
    case.ram[:] = earlier
    struct.pack_into("<I", case.ram, 0xCC858, 0x08000100)
    struct.pack_into("<I", case.ram, 0xD1F30, 1)
    result = read_current_collectible(case.binding, case.read)
    assert (
        isinstance(result, CurrentRoomFailure)
        and result.status is PollStatus.UnsupportedSettings
    )
    case.ram[:] = earlier
    assert isinstance(
        read_current_collectible(case.binding, case.read), CurrentCollectibleObservation
    )


@pytest.mark.parametrize(
    "field,value", [(0, 0x68), (1, 32), (2, 0), (3, 0xB1), (21, 1)]
)
def test_unsupported_packet_roles_do_not_mint_a_binding(item_case, field, value):
    packet = bytearray(item_case.packet)
    packet[field] = value
    result = item_case.build(packet, 24, 5, 0x800D2008).binding
    assert isinstance(result, RoomFormatFailure) and result.kind == "collectible-source"


@pytest.mark.parametrize("field,value", [(14, 256), (18, 0xF8), (18, 0x100)])
def test_native_width_and_index_paths_are_explicit(item_case, field, value):
    packet = bytearray(item_case.packet)
    struct.pack_into("<H", packet, field, value)
    assert isinstance(
        item_case.build(packet, 24, 5, 0x800D2008).binding, RoomFormatFailure
    )


def test_false_opcode_byte_and_cross_procedure_packet_do_not_qualify(item_case):
    packet = bytearray(item_case.packet)
    packet[:2] = b"\x00\x67"
    assert isinstance(
        item_case.build(packet, 24, 5, 0x800D2008).binding, RoomFormatFailure
    )
    assert isinstance(
        item_case.build(item_case.packet, 20, 5, 0x800D2008).binding, RoomFormatFailure
    )


@pytest.mark.parametrize(
    "category,bank", [(4, 0x800D2008), (6, 0x800D2008), (5, 0x800D2028)]
)
def test_unproven_categories_and_banks_are_modeled_failures(item_case, category, bank):
    assert isinstance(
        item_case.build(item_case.packet, 24, category, bank).binding, RoomFormatFailure
    )


@pytest.mark.parametrize(
    "stage,room,procedure",
    [
        (1, 0, 0),
        (True, 0, 0),
        (0, True, 0),
        (0, 0, True),
        (0, 0, -1),
        (0, 0, 256),
        (0, 0, 2),
        (0, 255, 0),
    ],
)
def test_unsupported_selectors_fail_explicitly(item_case, stage, room, procedure):
    assert isinstance(
        bind_collectible_source(
            item_case.executable, item_case.catalog, stage, room, procedure
        ),
        RoomFormatFailure,
    )


def test_full_executable_identity_is_required_even_with_matching_sampled_code(
    item_case,
):
    result = bind_collectible_source(
        item_case.executable + b"x", item_case.catalog, 0, 0, 0
    )
    assert isinstance(result, RoomFormatFailure) and result.kind == "executable"


@pytest.mark.parametrize(
    "field",
    [
        "catalog",
        "source",
        "source_sha256",
        "procedure_index",
        "packet_offset",
        "packet",
        "raw_type",
        "source_amount",
        "acquisition_index",
        "acquisition_address",
        "acquisition_mask",
    ],
)
def test_retaining_a_binding_cannot_replace_its_compiled_fields(item_case, field):
    binding = item_case.binding
    value = getattr(binding, field)
    changed = value + 1 if type(value) is int else object()
    with pytest.raises(AssertionError):
        replace(binding, **{field: changed})


@pytest.mark.parametrize("buffer", [bytearray, memoryview])
def test_equal_mutable_packets_cannot_reuse_the_immutable_receipt(item_case, buffer):
    # These buffers compare equal to bytes but can be changed after validation.
    # The copied reader must never retain a mutable packet with a stale index.
    packet = buffer(bytearray(item_case.packet))
    assert packet == item_case.binding.packet
    with pytest.raises(AssertionError):
        replace(item_case.binding, packet=packet)
    with pytest.raises(AssertionError):
        replace(item_case.binding._binding, packet=packet)


def test_bool_int_equality_cannot_change_a_compiled_field_type(item_case):
    assert item_case.binding.source_amount == 1
    with pytest.raises(AssertionError):
        replace(item_case.binding, source_amount=True)
    with pytest.raises(AssertionError):
        replace(item_case.binding._binding, source_amount=True)
