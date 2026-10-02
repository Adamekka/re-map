"""RE1-SCD-008: native advances and operand reads have distinct boundaries."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_cache_metadata import scan_cache_rdt
from build_tracking_program import build_tracking_program
from scan_events import scan_event_commands
from scan_scd import walk, walk_linear, walk_procedures
from test_cache_metadata import indexed_event, pickup, source
from test_tracking_rules import compile_program

pytest_plugins = ("test_tracking_rules",)


@pytest.mark.parametrize("opcode,advance", [(0x40, 16), (0x46, 44), (0x47, 14)])
def test_native_advance_preserves_following_items_and_door(opcode, advance):
    setup = bytes((opcode,)) + bytes(advance - 1)
    door = bytes((0x0C, 2)) + bytes(24)
    code = setup + pickup(0, 0x44, 111) + pickup(1, 0x26, 63) + door + b"\0"
    ops, status = walk(code, 0x100)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [
        (0x100, opcode),
        (0x100 + advance, 0x18),
        (0x100 + advance + 26, 0x18),
        (0x100 + advance + 52, 0x0C),
        (0x100 + advance + 78, 0),
    ]
    assert [raw[22] for _, op, raw in ops if op == 0x18] == [111, 63]


def test_branch_can_target_bytes_also_read_by_a_preceding_light_command():
    setup = bytes((0x40,)) + bytes(15)
    code = bytes((1, 16)) + setup + pickup(0, 0x44, 111) + b"\0"
    ops, status = walk(code, 0x100)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [
        (0x100, 1),
        (0x102, 0x40),
        (0x112, 0x18),
        (0x12C, 0),
    ]


@pytest.mark.parametrize("extent", [16, 17])
def test_light_command_requires_its_final_halfword_even_after_pc_advance(extent):
    code = bytes((0x40,)) + bytes(extent - 1)
    assert "truncated operand read" in walk(code, 0x100)[1]
    assert walk_linear(code, 0x100) == []


def test_operand_tail_is_readable_but_is_not_instruction_flow():
    code = bytes((0x40,)) + bytes(15)
    item = pickup(0, 0x44, 111)
    ops, status = walk(code, 0x100, operand_tail=item)
    assert status == "clean"
    assert ops == [(0x100, 0x40, code)]
    assert walk_linear(code, 0x100, operand_tail=item) == ops
    short = bytes((0x47,)) + bytes(11)
    assert "advances outside procedure" in walk(short, 0x100, operand_tail=item)[1]
    assert walk_linear(short, 0x100, operand_tail=item) == []


def test_procedure_sentinel_can_supply_the_light_commands_overlapping_operand():
    command = bytes((0x40,)) + bytes(15)
    span = (18).to_bytes(2, "little") + command + bytes(2)
    assert walk_procedures(span, 0x100) == ([(0x102, 0x40, command)], "clean")
    found, status = walk_procedures(span[:-1], 0x100)
    assert found == []
    assert status != "clean"


def test_semantic_compiler_uses_the_same_bounded_procedure_read_window(rules):
    command = bytes((0x40,)) + bytes(15)
    program = compile_program(rules, command)
    assert program.coverage_complete
    assert len(program.procedures) == 1
    decoded = program.procedures[0].commands
    assert len(decoded) == 1
    assert decoded[0].next - decoded[0].offset == 16


@pytest.mark.parametrize("malformed", [b"\x26", bytes((1, 255)), b"\x47"])
def test_compiler_cannot_trust_a_complete_claim_after_its_own_decoder_failure(
    rules, malformed
):
    data = source(malformed, b"\0", bytes(4))
    row = scan_cache_rdt(data, "PSX/STAGE1/ROOM1091.RDT", rules[1])
    assert not row["tracking_program"]["coverage_complete"]
    assert not build_tracking_program(data, row, [], True)["coverage_complete"]


@pytest.mark.parametrize("header", [bytes((1, 0)), bytes((255, 255)), bytes((3, 0, 0))])
def test_compiler_rejects_invalid_lengths_and_missing_sentinels(rules, header):
    data = source(b"\0", b"\0", bytes(4))
    row = scan_cache_rdt(data, "PSX/STAGE1/ROOM1091.RDT", rules[1])
    start = row["init_offset"]
    short = bytearray(data)
    short[start : start + len(header)] = header
    row["init_size"] = len(header)
    assert not build_tracking_program(short, row, [], True)["coverage_complete"]


@pytest.mark.parametrize("section", ["init", "main"])
def test_compiler_rejects_a_source_section_outside_the_provided_bytes(rules, section):
    data = source(b"\0", b"\0", bytes(4))
    row = scan_cache_rdt(data, "PSX/STAGE1/ROOM1091.RDT", rules[1])
    row[section + "_size"] = len(data)
    assert not build_tracking_program(data, row, [], True)["coverage_complete"]


@pytest.mark.parametrize("source", [4, 29, 127, 255])
def test_native_sound_default_continues_after_header_without_coordinates(source):
    command = bytes((0x17, 0, 0, 0, source, 0))
    ops, status = walk(command + pickup(0, 0x44, 111) + b"\0", 0x100)
    assert status == "clean"
    assert [(address, op) for address, op, _ in ops] == [
        (0x100, 0x17),
        (0x106, 0x18),
        (0x120, 0),
    ]


@pytest.mark.parametrize("source", range(4))
def test_implemented_sound_sources_require_all_ten_bytes(source):
    command = bytes((0x17, 0, 0, 0, source, 0)) + bytes(3)
    assert "truncated opcode 0x17" in walk(command, 0x100)[1]


@pytest.mark.parametrize(
    "command",
    [bytes((opcode, 0)) for opcode in (0x26, 0x2E, 0x4F, 0x50)]
    + [bytes((0x28, 0, 0, selector)) for selector in (4, 7, 11, 255)]
    + [bytes((0x33, selector)) for selector in (2, 11, 255)],
)
def test_nonadvancing_and_null_dispatch_never_expose_following_item(command):
    code = command + pickup(0, 0x44, 111) + b"\0"
    found, status = walk(code, 0x100)
    assert status != "clean"
    assert found == []
    assert walk_linear(code, 0x100) == []
    event = indexed_event(bytes((7, len(command) + 2)) + command + b"\xff")
    # A real event section has a nonzero source offset.
    found, status = scan_event_commands(b"x" + event, 1, len(event) + 1)
    assert status != "clean"
    assert found == []


@pytest.mark.parametrize("opcode,advance", [(0x46, 44), (0x47, 14)])
@pytest.mark.parametrize("deferred", [False, True])
def test_corrected_fixed_widths_work_in_single_and_deferred_events(
    opcode, advance, deferred
):
    command = bytes((opcode,)) + bytes(advance - 1)
    payload = bytes((0xFC if deferred else 7, advance + 2)) + command
    payload += bytes((0xFD, 0xFF)) if deferred else b"\xff"
    event = indexed_event(payload)
    assert scan_event_commands(b"x" + event, 1, len(event) + 1) == (
        [(11, opcode, command)],
        "clean",
    )
    short = bytes((opcode,)) + bytes(advance - 2)
    assert "truncated" in walk(short, 0x100)[1]
    event = indexed_event(bytes((7, len(short) + 2)) + short)
    found, status = scan_event_commands(b"x" + event, 1, len(event) + 1)
    assert found == []
    assert "truncated" in status


def test_embedded_procedure_uses_its_sentinel_for_the_overlapping_operand():
    command = bytes((0x40,)) + bytes(15)
    block = bytes((18, 0)) + command + bytes(2)
    event = indexed_event(bytes((6, len(block) + 2)) + block + b"\xff")
    assert scan_event_commands(b"x" + event, 1, len(event) + 1) == (
        [(13, 0x40, command)],
        "clean",
    )


def test_failed_embedded_procedure_does_not_publish_linear_candidates():
    # Its invalid branch yields linear item candidates in the diagnostic walker.
    code = bytes((1, 255)) + pickup(0, 0x44, 111) + b"\0"
    block = (len(code) + 2).to_bytes(2, "little") + code + bytes(2)
    assert any(op == 0x18 for _, op, _ in walk_procedures(block, 0x100)[0])
    later = bytes((7, 28)) + pickup(1, 0x26, 63)
    event = indexed_event(bytes((6, len(block) + 2)) + block + later + b"\xff")
    found, status = scan_event_commands(b"x" + event, 1, len(event) + 1)
    assert found == []
    assert status != "clean"


def test_single_event_command_can_read_beyond_its_wrapper_but_not_section():
    command = bytes((0x40,)) + bytes(15)
    event = indexed_event(bytes((7, 18)) + command + bytes((0xFF, 0)))
    found, status = scan_event_commands(b"x" + event, 1, len(event) + 1)
    assert status == "clean"
    assert found == [(11, 0x40, command)]
    short = event[:-1]
    assert (
        "truncated operand read"
        in scan_event_commands(b"x" + short, 1, len(short) + 1)[1]
    )


def test_deferred_event_command_keeps_pc_extent_separate_from_operand_read():
    command = bytes((0x40,)) + bytes(15)
    event = indexed_event(bytes((0xFC, 18)) + command + bytes((0xFD, 0xFF)))
    found, status = scan_event_commands(b"x" + event, 1, len(event) + 1)
    assert status == "clean"
    assert found == [(11, 0x40, command)]
