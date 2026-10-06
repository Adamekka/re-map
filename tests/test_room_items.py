"""Registered item coverage against controlled pickup states and malformed reads."""

import struct
from dataclasses import replace

import pytest
from test_live_items import RamReader, fixture_ram

from games.game_profile import RoomId
from games.re1.room_items import (
    RuntimeItemKind,
    RuntimeItemState,
    RuntimeRoomItems,
    RuntimeRoomLayout,
    observe_room_items,
)


@pytest.fixture
def layout():
    return RuntimeRoomLayout(
        aot_base=0x800B8160,
        aot_bound_address=0x800B7ED8,
        aot_capacity=24,
        loaded_rdt_pointer_address=0x800CAB10,
        acquisition_flags_address=0x800C86DC,
        acquisition_flags_width=32,
        ram_base=0x80000000,
        ram_size=0x200000,
        pending_action_pointer_address=0x800B7DCC,
        main_flags_address=0x800C3000,
        pending_item_mask=0xC00,
        item_labels=(
            (0x44, "Green Herb"),
            (0x26, "Chemical"),
            (0x4E, "Mansion 1F map"),
        ),
    )


@pytest.mark.parametrize(
    "filename,room,item_type,gid,remaining,door_count",
    (
        ("slus00551_green_herb_before.sav", 9, 0x44, 111, True, 5),
        ("slus00551_green_herb_after.sav", 9, 0x44, 111, False, 5),
        ("slus00551_chemical_before.sav", 0x18, 0x26, 13, True, 1),
        ("slus00551_chemical_after.sav", 0x18, 0x26, 13, False, 1),
    ),
)
def test_registered_pickup_states(
    layout, tmp_path, filename, room, item_type, gid, remaining, door_count
):
    ram = fixture_ram(filename, tmp_path)
    result = observe_room_items(layout, RoomId(0, room), RamReader(ram).read_memory)
    assert result.ok, result.error
    assert result.list_complete
    assert len(result.items) == 1
    item = result.items[0]
    assert (item.item_type, item.global_id) == (item_type, gid)
    assert item.state == (
        RuntimeItemState.Available if remaining else RuntimeItemState.Taken
    )
    assert len(result.active_doors) == door_count
    assert all(raw[:2] == bytes((0x0C, slot)) for slot, raw in result.active_doors)


def test_stale_cleared_pointer_does_not_create_a_pickup(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    # Prior room pointers survive reset. A cleared slot is meaningful only when its copied item fields match.
    struct.pack_into("<I", ram, 0xB819C + 8, 0x80121E94)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete
    assert result.items == ()
    ram[0xB819C] = 4
    invalid = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not invalid.ok
    assert "outside current room scripts" in invalid.error


def test_dormant_object_with_set_flag_is_unavailable(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 0
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete
    assert result.items[0].state == RuntimeItemState.Unavailable


def test_pending_award_preserves_remaining_item_until_flag_clear(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 0
    struct.pack_into("<I", ram, 0xB7DCC, 0x800B819C)
    flags = struct.unpack_from("<I", ram, 0xC3000)[0]
    struct.pack_into("<I", ram, 0xC3000, flags | 0x400)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete
    assert result.items[0].state == RuntimeItemState.Available
    ram[0xC86EA] &= ~1
    taken = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert taken.ok and taken.items[0].state == RuntimeItemState.Taken


def test_zero_geometry_scripted_map_remains_a_collectible(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer : pointer + 8] = bytes(8)
    ram[pointer + 8] = 0x4E
    ram[pointer + 21] = 0
    ram[0xB819C] = 15
    ram[0xB819C + 1] = 0
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete
    assert result.items[0].kind == RuntimeItemKind.Map
    assert result.items[0].state == RuntimeItemState.Available


def test_files_do_not_block_normal_room_completion(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer + 8] = 0x54
    ram[0xB819C] = 13
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete and result.items == ()
    assert result.non_collectible_slots == (5,)


@pytest.mark.parametrize("handler", (8, 13, 16))
@pytest.mark.parametrize("opcode", (0x0D, 0x18))
def test_audited_noncollectible_interactions_preserve_live_slot_evidence(
    layout, tmp_path, handler, opcode
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer - 2] = opcode
    ram[0xB819C] = handler
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete and result.items == ()
    assert result.non_collectible_slots == (5,)


@pytest.mark.parametrize("handler", (8, 13, 16))
@pytest.mark.parametrize("pending_mask", (0x400, 0x800))
def test_pending_award_overrides_a_noncollectible_handler(
    layout, tmp_path, handler, pending_mask
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = handler
    struct.pack_into("<I", ram, 0xB7DCC, 0x800B819C)
    flags = struct.unpack_from("<I", ram, 0xC3000)[0]
    struct.pack_into("<I", ram, 0xC3000, flags | pending_mask)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.items[0].state == RuntimeItemState.Available
    assert result.non_collectible_slots == ()


@pytest.mark.parametrize("change", ("pointer", "slot", "opcode", "truncated"))
def test_invalid_noncollectible_sources_supply_no_live_evidence(
    layout, tmp_path, change
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 16
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    if change == "pointer":
        struct.pack_into("<I", ram, 0xB819C + 8, 0x80121E94)
    elif change == "slot":
        ram[pointer - 1] = 4
    elif change == "opcode":
        ram[pointer - 2] = 0x13
    else:
        end = struct.unpack_from("<I", ram, 0x121C00 + 0x6C)[0]
        source = end - 18
        ram[source - 0x80000000 : end - 0x80000000] = bytes((0x18, 5)) + bytes(16)
        struct.pack_into("<I", ram, 0xB819C + 8, source + 2)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not result.ok and result.non_collectible_slots == ()


@pytest.mark.parametrize("handler", (0, 2, 3, 9))
def test_dormant_and_unaudited_handlers_supply_no_absence_evidence(
    layout, tmp_path, handler
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = handler
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.non_collectible_slots == ()


def test_noncollectible_registry_changes_discard_evidence(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    ram[0xB819C] = 16
    reads = 0

    def changing_reader(address, length):
        nonlocal reads
        if address == layout.aot_base:
            reads += 1
            if reads == 2:
                ram[0xB819C] = 4
        return RamReader(ram).read_memory(address, length)

    result = observe_room_items(layout, RoomId(0, 9), changing_reader)
    assert not result.ok and result.retry and result.non_collectible_slots == ()


def test_noncollectible_evidence_cannot_conflict_with_a_live_item(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    with pytest.raises(AssertionError, match="both collectible and noncollectible"):
        replace(result, non_collectible_slots=(5,))
    with pytest.raises(AssertionError):
        RuntimeRoomItems(ok=True, non_collectible_slots=(5, 5))


def test_generic_descriptor_uses_actual_pickup_fields(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer - 2] = 0x0D
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete
    assert result.items[0].source_opcode == 0x0D
    assert result.items[0].global_id == 111
    ram[0xB819C] = 0
    dormant = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert dormant.ok and dormant.items == ()


@pytest.mark.parametrize("handler,pending", ((4, False), (15, False), (0, True)))
def test_unsupported_active_item_type_is_a_failure(layout, tmp_path, handler, pending):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer + 8] = 0xFF
    ram[0xB819C] = handler
    if pending:
        struct.pack_into("<I", ram, 0xB7DCC, 0x800B819C)
        flags = struct.unpack_from("<I", ram, 0xC3000)[0]
        struct.pack_into("<I", ram, 0xC3000, flags | 0x400)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not result.ok and not result.list_complete
    assert "unsupported active item type" in result.error


def test_generic_nonpickup_needs_only_its_eighteen_byte_descriptor(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    end = struct.unpack_from("<I", ram, 0x121C00 + 0x6C)[0]
    source = end - 18
    ram[source - 0x80000000 : end - 0x80000000] = bytes((0x0D, 5)) + bytes(16)
    ram[0xB819C] = 2
    struct.pack_into("<I", ram, 0xB819C + 8, source + 2)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert result.ok and result.list_complete and result.items == ()
    ram[0xB819C] = 4
    truncated = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not truncated.ok and "descriptor is truncated" in truncated.error


def test_generic_door_and_radio_need_explicit_supported_semantics(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer - 2] = 0x0D
    ram[0xB819C] = 1
    door = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not door.ok and "unsupported source descriptor" in door.error
    ram[pointer - 2] = 0x18
    ram[pointer + 8] = 0x4D
    ram[0xB819C] = 4
    radio = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not radio.ok and "separate scenario flag" in radio.error


@pytest.mark.parametrize(
    "address,value,expected",
    (
        (0xB7ED8, 0x800B8161, "AOT bound"),
        (0xB7ED8, 0x800B8160 + 24 * 12, "AOT bound"),
        (0xCAB10, 0x7FFFFFFF, "loaded room pointer"),
        (0x121C00 + 0x68, 0x7FFFFFFF, "script pointers"),
        (0xB819C + 8, 0x801FFFF0, "outside current room scripts"),
    ),
)
def test_malformed_runtime_pointers_fail_explicitly(
    layout, tmp_path, address, value, expected
):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    struct.pack_into("<I", ram, address, value)
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not result.ok and not result.list_complete
    assert expected in result.error


def test_source_self_id_and_unsupported_handlers_fail(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    pointer = struct.unpack_from("<I", ram, 0xB819C + 8)[0] - 0x80000000
    ram[pointer - 1] = 4
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not result.ok and "slot ID" in result.error
    ram[pointer - 1] = 5
    ram[0xB819C] = 18
    result = observe_room_items(layout, RoomId(0, 9), RamReader(ram).read_memory)
    assert not result.ok and "unsupported handler" in result.error


def test_runtime_read_failure_and_state_change_are_not_clear(layout, tmp_path):
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    reader = RamReader(ram)
    reader.fail_address = layout.acquisition_flags_address
    failed = observe_room_items(layout, RoomId(0, 9), reader.read_memory)
    assert not failed.ok and not failed.list_complete
    assert "injected read failure" in failed.error
    reads = 0

    def changing_reader(address, length):
        nonlocal reads
        if address == layout.acquisition_flags_address:
            reads += 1
            if reads == 2:
                ram[0xC86EA] &= ~1
        return RamReader(ram).read_memory(address, length)

    changed = observe_room_items(layout, RoomId(0, 9), changing_reader)
    assert not changed.ok and changed.retry and not changed.list_complete


def test_layout_configuration_requires_valid_explicit_ranges(layout):
    with pytest.raises(ValueError, match="AOT capacity"):
        replace(layout, aot_capacity=0)
    with pytest.raises(ValueError, match="outside configured"):
        replace(layout, aot_base=0x90000000)
    with pytest.raises(ValueError, match="unique"):
        replace(layout, item_labels=((0x44, "Herb"), (0x44, "Different herb")))
