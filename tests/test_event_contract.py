"""RE1-EVENT-003: synthetic native event-flow and bounds regressions."""

import pytest
from test_cache_metadata import indexed_event, pickup
from test_scan_events import scan, scan_event_commands
from test_tracking_rules import compile_program, evaluate

from games.re1.room_items import RuntimeItemState

pytest_plugins = ("test_tracking_rules",)


UPDATE = bytes((7, 6, 0x13, 5, 4, 0))


def test_timed_wait_advances_into_its_counter_then_reaches_an_update():
    ops, status = scan(bytes((0xF8, 0xF9, 2, 0)) + UPDATE + b"\xff")
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2E, 0x13)]


def test_counter_setup_does_not_skip_an_executable_byte_one():
    # F8 reads two bytes also consumed by the following single-command wrapper.
    # Treating it as width four instead would miss that wrapper at byte one.
    code = bytes((0xF8, 7, 6, 0x13, 5, 4, 0, 0xF7, 0xFF))
    ops, status = scan(code)
    assert status == "clean"
    assert ops == [(0x2B, 0x13, bytes((0x13, 5, 4, 0)))]


@pytest.mark.parametrize("counter", [0, 1, 0xFFFF])
def test_counter_value_changes_duration_but_not_following_command_reachability(counter):
    code = bytes((0xF8, 0xF9)) + counter.to_bytes(2, "little") + UPDATE + b"\xff"
    ops, status = scan(code)
    assert status == "clean"
    assert [op for _, op, _ in ops] == [0x13]


@pytest.mark.parametrize(
    "code,reason",
    [
        (b"\xf7", "wait end has no frame"),
        (bytes((0xF9, 0, 0)), "counter end has no counter frame"),
        (bytes((0xF6, 0xF9, 0, 0)), "counter end has no counter frame"),
        (bytes((0xF8,)), "counter read truncated"),
        (bytes((0xF8, 0xF9)), "counter read truncated"),
        (bytes((0xF8, 0xF9, 0)), "counter read truncated"),
        (bytes((0xF6,)) * 5 + b"\xff", "exceeds bounded analysis"),
        (bytes((0xFA, 0, 1, 0)) * 4 + b"\xf6\xff", "exceeds bounded analysis"),
        (bytes((0xF8, 0xFA, 1, 0, 0, 0xFB, 0xFB)), "loop end has no frame"),
        (bytes((0xFC, 3, 0, 0xF8, 0xFD, 1, 0)), "has no frame"),
        (bytes((0xFC, 0)), "exceeds bounded analysis"),
    ],
)
def test_invalid_shared_depth_or_uninitialized_frame_fields_reject_coverage(
    code, reason
):
    _, status = scan(code)
    assert status != "clean" and reason in status


def test_four_shared_frames_can_pop_waits_and_resume_a_call():
    predicate = bytes((4, 1, 0, 0))
    code = bytes((0xFC, 6)) + predicate + b"\xf6" * 3 + b"\xf7" * 3
    ops, status = scan(code + bytes((0xFE, 0xFD)) + UPDATE + b"\xff")
    assert status == "clean"
    assert [op for _, op, _ in ops] == [4, 0x13]


def test_loop_counter_can_be_consumed_by_a_counter_end():
    ops, status = scan(bytes((0xFA, 0, 2, 0, 0xF9, 0, 0)) + UPDATE + b"\xff")
    assert status == "clean"
    assert [op for _, op, _ in ops] == [0x13]


def test_wait_end_can_pop_a_call_without_reading_its_deferred_fields():
    ops, status = scan(bytes((0xFC, 3, 0, 0xF7)) + UPDATE + b"\xff")
    assert status == "clean"
    assert [op for _, op, _ in ops] == [0x13]


@pytest.mark.parametrize("offset", [1, 2])
def test_native_call_offset_can_overlap_the_deferred_command(offset):
    # Offset one executes the operand 01 as VM state entry; both paths then
    # dispatch the overlapping SCD 00 and leave actor state with 80.
    ops, status = scan(bytes((0xFC, offset, 0, 0xFD, 0x80)) + UPDATE + b"\xff")
    if offset == 2:
        # Offset two remains in state zero; 80 is its native terminator.
        assert status == "clean" and [op for _, op, _ in ops] == [0]
    else:
        assert status == "clean" and [op for _, op, _ in ops] == [0, 0x13]


@pytest.mark.parametrize("code", [bytes((7, 1, 0, 0x80, 0xFF)), bytes((7, 2, 0, 0xFF))])
def test_single_wrapper_can_jump_into_its_header_or_source(code):
    ops, status = scan(code)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2A, 0)]


def test_short_block_wrapper_can_read_a_procedure_beyond_its_vm_jump():
    code = bytes((6, 2, 3, 0, 0, 0, 0, 1, 0xFF))
    ops, status = scan(code)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2C, 0)]


def test_block_reader_follows_a_second_procedure_and_sentinel_outside_its_wrapper():
    code = bytes((6, 6, 3, 0, 0, 3, 0, 0, 0, 0, 0xFF))
    ops, status = scan(code)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2C, 0), (0x2F, 0)]


def test_short_block_wrapper_can_dispatch_an_empty_procedure_list():
    ops, status = scan(bytes((6, 2, 0, 0, 0xFF)))
    assert status == "clean" and ops == []


@pytest.mark.parametrize(
    "code",
    [
        bytes((6, 2)),
        bytes((6, 2, 0)),
        bytes((6, 2, 3, 0, 0)),
        bytes((6, 2, 3, 0, 0, 0)),
        bytes((6, 2, 7, 0, 0)),
        bytes((7, 2)),
        bytes((6, 0, 0, 0)),
        bytes((7, 0, 0)),
    ],
)
def test_short_embedded_dispatch_still_requires_bounded_reads_and_progress(code):
    ops, status = scan(code)
    assert status != "clean" and ops == []


def test_zero_result_does_not_repeat_an_incompatible_vm_state():
    code = bytes((0xFC, 3, 0, 1, 0, 0xFD, 0x80)) + UPDATE + b"\xff"
    ops, status = scan(code)
    assert status == "clean"
    assert [op for _, op, _ in ops] == [0, 0x13]


@pytest.mark.parametrize(
    "opcode,width",
    [(5, 4), (8, 4), (0x0C, 26), (0x13, 4), (0x18, 26), (0x40, 16), (0x46, 44)],
)
def test_nonzero_deferred_command_does_not_expose_an_exit_update(opcode, width):
    command = bytes((opcode,)) + bytes(width - 1)
    # The overlapping FE/FD bytes also satisfy command 40's two-byte operand peek.
    code = bytes((0xFC, width + 2)) + command + bytes((0xFE, 0xFD)) + UPDATE + b"\xff"
    ops, status = scan(code)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2A, opcode)]


def test_flag_setter_default_result_two_also_repeats_without_exiting():
    code = bytes((0xFC, 6, 5, 1, 0, 255, 0xFE, 0xFD)) + UPDATE + b"\xff"
    ops, status = scan(code)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2A, 5)]


@pytest.mark.parametrize("opcode", [10, 0x17, 0x48, 0x80, 0xF5])
def test_state_zero_default_terminates_without_exposing_a_later_update(opcode):
    ops, status = scan(bytes((opcode,)) + UPDATE)
    assert status == "clean" and ops == []


def test_a_native_stop_does_not_skip_an_independent_indexed_entry():
    table = (12).to_bytes(4, "little") + (14).to_bytes(4, "little") + bytes(4)
    data = bytes(0x20) + table + bytes((0x17, 0x18)) + UPDATE + b"\xff"
    ops, status = scan_event_commands(data, 0x20, len(data))
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x30, 0x13)]


@pytest.mark.parametrize(
    "prefix",
    [b"\xf6", b"\xf8", bytes((0xFA, 0, 1, 0)), bytes((0xFC, 3, 0))],
)
@pytest.mark.parametrize("terminator", [0x0A, 0xFF])
def test_native_termination_can_discard_outstanding_frames(prefix, terminator):
    # F8's two-byte counter read is satisfied even when byte one terminates.
    ops, status = scan(prefix + bytes((terminator, 0, 0)) + UPDATE)
    assert status == "clean" and ops == []


@pytest.mark.parametrize("offset", [1, 2, 255])
def test_call_at_section_end_cannot_hide_a_missing_deferred_command(offset):
    _, status = scan(bytes((0xFC, offset)))
    assert "leaves section" in status


@pytest.mark.parametrize(
    "packet", [bytes((4, 0, 0x18)), bytes((5, 0, 0, 0x18)), bytes((9, 0))]
)
def test_state_zero_packet_extents_preserve_following_updates(packet):
    ops, status = scan(packet + UPDATE + b"\xff")
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2A + len(packet), 0x13)]
    _, truncated = scan(packet[:-1])
    assert truncated != "clean"


@pytest.mark.parametrize("end", [0x80, 0x8B])
def test_both_actor_end_commands_resume_state_zero(end):
    ops, status = scan(bytes((1, end)) + UPDATE + b"\xff")
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2C, 0x13)]


def test_native_event_stop_preserves_last_item_clearance_and_acquisition_rewind(rules):
    hidden_item = bytes((7, 28)) + pickup(1, 0x26, 63)
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        event=indexed_event(b"\x17" + hidden_item),
    )
    assert program.coverage_complete and program.item_slots == (0,)
    flags = bytearray([255] * 32)
    ram = bytearray(2 * 1024 * 1024)
    for taken in (False, True, False):
        flags[14] = 254 if taken else 255
        items = evaluate(program, rules, ram, bytes(flags)).items
        assert items.list_complete and len(items.items) == 1
        assert items.items[0].state == (
            RuntimeItemState.Taken if taken else RuntimeItemState.Available
        )


@pytest.mark.parametrize("code", [bytes((1, 7)), bytes((2, 12))])
def test_other_state_defaults_do_not_gain_an_invented_advance(code):
    _, status = scan(code + UPDATE + b"\xff")
    assert status.startswith("unsupported event state")


@pytest.mark.parametrize(
    "packet",
    [
        bytes((0,)),
        bytes((0x81, 0)),
        bytes((0x81, 1)) + bytes((0x18,)) * 8,
        bytes((0x82,)),
        bytes((0x83,)) + bytes((0x18,)) * 6,
        bytes((0x84,)) + bytes((0x18,)) * 3,
        bytes((0x85,)) + bytes((0x18,)) * 3,
        bytes((0x86,)),
        bytes((0x87,)) + bytes((0x18,)) * 3,
        bytes((0x88,)) + bytes((0x18,)) * 3,
        bytes((0x89, 0x18)),
        bytes((0x8A, 0x18)),
    ],
)
def test_actor_state_packet_extents_preserve_the_following_vm_boundary(packet):
    ops, status = scan(b"\x01" + packet + b"\x80" + UPDATE + b"\xff")
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2C + len(packet), 0x13)]
    _, truncated = scan(b"\x01" + packet[:-1])
    assert truncated != "clean"


@pytest.mark.parametrize(
    "packet",
    [
        bytes((0,)),
        bytes((2,)),
        bytes((3,)),
        bytes((4,)),
        bytes((5,)) + bytes((0x18,)) * 3,
        bytes((6,)) + bytes((0x18,)) * 3,
        bytes((7,)) + bytes((0x18,)) * 7,
        bytes((8,)) + bytes((0x18,)) * 2,
        bytes((9, 0x18)),
        bytes((10, 0)) + bytes((0x18,)) * 2,
        bytes((11,)) + bytes((0x18,)) * 7,
    ],
)
@pytest.mark.parametrize("entry", [2, 3])
def test_motion_state_packet_extents_preserve_the_following_vm_boundary(entry, packet):
    ops, status = scan(bytes((entry,)) + packet + b"\x01" + UPDATE + b"\xff")
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [(0x2C + len(packet), 0x13)]
    _, truncated = scan(bytes((entry,)) + packet[:-1])
    assert truncated != "clean"
