"""Regression tests for alignment of SLUS-00551 room scripts."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from scan_scd import walk, walk_linear, walk_procedures


def test_opcodes_20_and_21_leave_following_item_aligned():
    item = bytearray(26)
    item[0] = 0x18
    item[22] = 111
    for opcode in (0x20, 0x21):
        code = bytes([opcode]) + bytes(13) + item
        ops, status = walk(code, 0x100)
        assert status == "clean"
        assert [(addr, op) for addr, op, _ in ops] == [(0x100, opcode), (0x10E, 0x18)]
        assert ops[1][2][22] == 111


def test_unconditional_end_excludes_trailing_item():
    item = bytes([0x18]) + bytes(25)
    code = bytes([0x00, 0xFF]) + item
    span = (len(code) + 2).to_bytes(2, "little") + code + bytes(2)
    ops, status = walk_procedures(span, 0x100)
    assert status == "clean"
    assert [(addr, op) for addr, op, _ in ops] == [(0x102, 0x00)]


def test_if_exit_keeps_item_after_terminator():
    item = bytes([0x18]) + bytes(25)
    code = bytes([0x01, 0x02, 0x00, 0xFF]) + item + bytes([0x00, 0xFF])
    ops, status = walk(code, 0x100)
    assert status == "clean"
    assert (0x104, 0x18) in [(addr, op) for addr, op, _ in ops]


def test_else_jumps_over_unreachable_item():
    item = bytes([0x18]) + bytes(25)
    code = bytes([0x02, 0x1C]) + item + bytes([0x00, 0xFF])
    ops, status = walk(code, 0x100)
    assert status == "clean"
    assert [(addr, op) for addr, op, _ in ops] == [(0x100, 0x02), (0x11C, 0x00)]


def test_if_else_preserves_both_candidate_items():
    item = bytes([0x18]) + bytes(25)
    code = bytes([0x01, 0x1C]) + item + bytes([0x02, 0x1E])
    code += item + bytes([0x03, 0xFF, 0x00, 0xFF])
    span = (len(code) + 2).to_bytes(2, "little") + code + bytes(2)
    ops, status = walk_procedures(span, 0x100)
    assert status == "clean"
    assert [(addr, op) for addr, op, _ in ops if op == 0x18] == [
        (0x104, 0x18),
        (0x120, 0x18),
    ]


def test_bad_branch_keeps_linear_candidates_with_partial_status():
    item = bytes([0x18]) + bytes(25)
    code = bytes([0x01, 0xFF]) + item + bytes([0x00, 0xFF])
    span = (len(code) + 2).to_bytes(2, "little") + code + bytes(2)
    ops, status = walk_procedures(span, 0x100)
    assert status.startswith("partial:")
    assert (0x104, 0x18) in [(addr, op) for addr, op, _ in ops]


def test_overlapping_branch_target_retains_only_linear_candidates():
    item = bytes([0x18]) + bytes(25)
    code = bytes([0x01, 0x01]) + item + bytes([0x00, 0xFF])
    span = (len(code) + 2).to_bytes(2, "little") + code + bytes(2)
    ops, status = walk_procedures(span, 0x100)
    assert status.startswith("partial: overlapping branch target")
    assert [(addr, op) for addr, op, _ in ops] == [
        (0x102, 0x01),
        (0x104, 0x18),
        (0x11E, 0x00),
    ]


def test_else_target_inside_its_own_opcode_is_partial():
    span = bytes([0x06, 0x00, 0x02, 0x01, 0x00, 0xFF, 0x00, 0x00])
    ops, status = walk_procedures(span, 0x100)
    assert status.startswith("partial: ELSE target inside opcode")
    assert [(addr, op) for addr, op, _ in ops] == [(0x102, 0x02), (0x104, 0x00)]


def test_next_procedure_still_scanned_after_termination():
    item = bytes([0x18]) + bytes(25)
    first = bytes([0x04, 0x00, 0xFF, 0xFF])
    second = item + bytes([0x00, 0xFF])
    span = (len(first) + 2).to_bytes(2, "little") + first
    span += (len(second) + 2).to_bytes(2, "little") + second + bytes(2)
    ops, status = walk_procedures(span, 0x100)
    assert status == "clean"
    assert (0x108, 0x18) in [(addr, op) for addr, op, _ in ops]


def test_malformed_procedure_bounds_are_partial():
    assert walk_procedures(bytes([0x01, 0x00]), 0x100) == (
        [],
        "partial: bad procedure length at +0",
    )
    assert walk_procedures(bytes([0x04, 0x00, 0x00, 0xFF]), 0x100) == (
        [(0x102, 0x00, bytes([0x00, 0xFF]))],
        "partial: missing procedure sentinel at +4",
    )


def test_raw_candidates_continue_past_first_terminator():
    item = bytes([0x18]) + bytes(25)
    ops = walk_linear(bytes([0x00, 0xFF]) + item, 0x100)
    assert [(addr, op) for addr, op, _ in ops] == [(0x100, 0x00), (0x102, 0x18)]


def test_generated_table_excludes_dead_tails_but_keeps_branch_reachable_items():
    table = Path(__file__).resolve().parents[1] / "data/item_table_slus00551.json"
    rooms = {
        Path(row["file"]).name: row for row in json.loads(table.read_text())["rooms"]
    }
    assert {item["gid"] for item in rooms["ROOM1091.RDT"]["items"]} == {111}
    assert 120 not in {item["gid"] for item in rooms["ROOM40A0.RDT"]["items"]}
    assert {item["addr"] for item in rooms["ROOM10E0.RDT"]["items"]} >= {
        "0x22b74",
        "0x22b98",
    }
