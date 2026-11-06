"""RE3-MAP-012: numeric source cases with original synthetic flag RAM."""

import struct

import pytest

from games.bit_flags import msb_flag_location
from games.re3.map_layer import native_map_layer
from games.re3.map_row_predicates import native_row_visible


@pytest.fixture
def flag_ram():
    ram = bytearray(2 * 1024 * 1024)

    def read(bank, index):
        address, mask = msb_flag_location(bank, index)
        return struct.unpack_from("<I", ram, address - 0x80000000)[0] & mask

    return ram, read


def write_flag(ram, bank, index, enabled):
    address, mask = msb_flag_location(bank, index)
    offset = address - 0x80000000
    word = struct.unpack_from("<I", ram, offset)[0]
    struct.pack_into("<I", ram, offset, word | mask if enabled else word & ~mask)


@pytest.mark.parametrize(
    "group,row,expected",
    [
        (0, 0, 0),
        (0, 255, 0),
        (1, 0, 0),
        (1, 255, 0),
        (3, 0, 0),
        (3, 255, 0),
        (2, 9, 0),
        (2, 10, 1),
        (2, 11, 1),
        (2, 12, 2),
        (2, 13, 1),
        (2, 255, 1),
        (4, 0, 1),
        (4, 3, 1),
        (4, 4, 0),
        (4, 6, 0),
        (4, 7, 0),
        (4, 8, 1),
        (4, 10, 1),
        (4, 11, 0),
        (4, 17, 0),
        (4, 18, 0),
        (4, 255, 0),
        (5, 7, 0),
        (5, 8, 1),
        (5, 255, 1),
        (6, 4, 1),
        (6, 5, 2),
        (6, 8, 2),
        (6, 9, 0),
        (6, 255, 0),
    ],
)
def test_native_layer_source_boundaries(group, row, expected):
    assert native_map_layer(group, row) == expected


@pytest.mark.parametrize("group", range(7))
def test_full_acquisition_mask_reveals_rows_with_zero_low_byte(flag_ram, group):
    ram, flag = flag_ram
    write_flag(ram, 0x800D2124, group, True)
    assert flag(0x800D2124, group) != 0
    assert flag(0x800D2124, group) & 0xFF == 0
    # High rows are pure function-domain cases when outside the chosen source
    # directory. They do not establish room ownership or a supported MAP row.
    assert native_row_visible(group, 64, 0x6FF, 0, 0, 0, flag)


@pytest.mark.parametrize("row", [47, 48, 63, 64, 77, 255])
def test_unacquired_cutoff_happens_before_visit_read(flag_ram, row):
    ram, flag = flag_ram
    write_flag(ram, 0x800D20DC, 128 + row, True)
    calls = []

    def observed_flag(bank, index):
        calls.append((bank, index))
        return flag(bank, index)

    assert native_row_visible(2, row, 0x6FF, 0, 0, 0, observed_flag) is (row == 47)
    assert calls == (
        [(0x800D2124, 2), (0x800D20DC, 175)] if row == 47 else [(0x800D2124, 2)]
    )


def test_native_visit_rejection_precedes_structural_flags_and_layer(flag_ram):
    ram, flag = flag_ram
    write_flag(ram, 0x800D1FA0, 58, True)
    calls = []

    def observed_flag(bank, index):
        calls.append((bank, index))
        return flag(bank, index)

    assert not native_row_visible(1, 0, 0x10C, 2, 1, -128, observed_flag)
    assert calls == [(0x800D2124, 1), (0x800D20DC, 64)]


@pytest.mark.parametrize("row", range(10, 17))
@pytest.mark.parametrize("visited", [False, True])
def test_acquired_group_four_still_requires_visits_for_rows_eleven_to_fifteen(
    flag_ram, row, visited
):
    ram, flag = flag_ram
    write_flag(ram, 0x800D2124, 4, True)
    write_flag(ram, 0x800D20DC, 256 + row, visited)
    assert native_row_visible(4, row, 0x6FF, 0, 0, 0, flag) is (
        visited or row in (10, 16)
    )


@pytest.mark.parametrize(
    "group,row,key,bits,expected",
    [
        (0, 16, 0x6FF, (), True),
        (0, 17, 0x6FF, (), False),
        (0, 26, 0x6FF, (), False),
        (0, 27, 0x6FF, (), True),
        (1, 0, 0x10B, ((0x800D1FA0, 58),), True),
        (1, 0, 0x10C, (), True),
        (1, 0, 0x10C, ((0x800D1FA0, 58),), False),
        (1, 0, 0x115, ((0x800D1FA0, 58),), False),
        (1, 12, 0x10C, ((0x800D1FA0, 58),), True),
        (1, 12, 0x115, ((0x800D1FA0, 58),), True),
        (1, 15, 0x10E, (), False),
        (1, 16, 0x10E, (), True),
        (1, 15, 0x10F, (), True),
        (1, 16, 0x10F, (), False),
        (1, 17, 0x111, (), True),
        (1, 18, 0x111, (), False),
        (1, 17, 0x112, (), False),
        (1, 18, 0x112, (), True),
        (3, 17, 0x6FF, (), True),
        (3, 21, 0x6FF, (), False),
        (3, 17, 0x6FF, ((0x800D1FA0, 196),), False),
        (3, 21, 0x6FF, ((0x800D1FA0, 196),), True),
        (3, 13, 0x30F, (), True),
        (3, 16, 0x30F, (), False),
        (3, 13, 0x310, (), False),
        (3, 16, 0x310, (), True),
        (3, 17, 0x310, (), False),
        (3, 21, 0x310, ((0x800D1FA0, 196),), False),
    ],
)
def test_structural_source_branches_after_acquisition(
    flag_ram, group, row, key, bits, expected
):
    ram, flag = flag_ram
    write_flag(ram, 0x800D2124, group, True)
    for bank, index in bits:
        write_flag(ram, bank, index, True)
    assert native_row_visible(group, row, key, 0, 0, 0, flag) is expected


@pytest.mark.parametrize("raw_stage", [0, 1, 2, 3, 4, 5, 0x8002, 0xFFFE, 0xFFFF])
def test_raw_stage_row_twelve_uses_exact_unsigned_membership(flag_ram, raw_stage):
    ram, flag = flag_ram
    write_flag(ram, 0x800D2124, 1, True)
    write_flag(ram, 0x800D1FA0, 58, True)
    assert native_row_visible(1, 12, 0x10C, raw_stage, 0, 0, flag) is (
        raw_stage not in (2, 3, 4)
    )


@pytest.mark.parametrize("raw_layer", range(256))
@pytest.mark.parametrize("layer_mode", [0, 1, 255])
def test_all_selected_layer_byte_encodings_preserve_signedness_and_mode(
    flag_ram, raw_layer, layer_mode
):
    ram, flag = flag_ram
    write_flag(ram, 0x800D2124, 2, True)
    layer = raw_layer if raw_layer < 128 else raw_layer - 256
    assert native_row_visible(2, 12, 0x6FF, 0, layer_mode, layer, flag) is (
        layer_mode == 0 or layer == 2
    )


def test_visit_index_over_thirty_one_aliases_the_same_physical_flag_word(flag_ram):
    ram, flag = flag_ram
    assert msb_flag_location(0x800D20DC, 65) == msb_flag_location(0x800D20CC, 193)
    write_flag(ram, 0x800D20CC, 193, True)
    assert flag(0x800D20DC, 65) == 0x40000000
    assert native_row_visible(1, 1, 0x6FF, 0, 0, 0, flag)
    write_flag(ram, 0x800D20DC, 65, False)
    assert flag(0x800D20CC, 193) == 0
    assert not native_row_visible(1, 1, 0x6FF, 0, 0, 0, flag)


def test_generated_high_row_visit_alias_can_change_the_acquisition_bit(flag_ram):
    ram, flag = flag_ram
    # Row 198 is outside owned group-6 sources. This proves physical aliasing
    # in the pure u8 domain, not the existence of a visited gameplay row.
    assert msb_flag_location(0x800D20DC, 582) == msb_flag_location(0x800D2124, 6)
    write_flag(ram, 0x800D20DC, 582, True)
    assert flag(0x800D2124, 6) == 0x02000000
    assert native_row_visible(6, 198, 0x6FF, 0, 0, 0, flag)
    write_flag(ram, 0x800D2124, 6, False)
    assert flag(0x800D20DC, 582) == 0
    assert not native_row_visible(6, 198, 0x6FF, 0, 0, 0, flag)


@pytest.mark.parametrize(
    "position,value",
    [
        (0, -1),
        (0, 7),
        (0, 255),
        (1, -1),
        (1, 256),
        (2, -1),
        (2, 0x10000),
        (3, -1),
        (3, 0x10000),
        (4, -1),
        (4, 256),
        (5, -129),
        (5, 128),
        *[(position, True) for position in range(6)],
    ],
)
def test_row_helper_decoded_scalar_widths_are_programmer_invariants(
    flag_ram, position, value
):
    _, flag = flag_ram
    arguments = [0, 0, 0, 0, 0, 0]
    arguments[position] = value
    with pytest.raises(AssertionError):
        native_row_visible(*arguments, flag)


@pytest.mark.parametrize(
    "group,row", [(-1, 0), (7, 0), (True, 0), (0, -1), (0, 256), (0, True)]
)
def test_layer_helper_accepts_only_supported_groups_and_decoded_rows(group, row):
    with pytest.raises(AssertionError):
        native_map_layer(group, row)
