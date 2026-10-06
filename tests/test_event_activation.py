"""RE1-EVENT-007: source-bound activation; substitutions are synthetic."""

import json
import struct
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import pytest
from scan_events import scan_event_program
from test_cache_metadata import indexed_event, pickup, source
from test_event_conditions import block
from test_live_items import RamReader, fixture_ram
from test_tracking_rules import REPO, compile_program, door, evaluate, guard
from track import PollStatus, poll_once

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re1.event_state import EventLayout, EventProgram, read_event_snapshot
from games.re1.re1_profile import Re1Profile
from games.re1.room_cache import RoomScriptSource, match_room_source
from tracker.exploration_state import Tracker

pytest_plugins = ("test_tracking_rules",)

BASE = 0x80010000
LAYOUT = EventLayout(0x80002000, 0x80001900, 8, 52, 0, 2, 3, 8, 12, 28)


def indexed(*codes):
    offset = 4 * (len(codes) + 1)
    table = bytearray()
    for code in codes:
        table += struct.pack("<I", offset)
        offset += len(code)
    return bytes(table) + bytes(4) + b"".join(codes)


def setup(rules, init, event):
    from build_cache_metadata import scan_cache_rdt

    data = source(init, b"\0", event)
    row = scan_cache_rdt(data, "PSX/STAGE1/ROOM1091.RDT", rules[1])
    program = compile_program(rules, init, event=event)
    fields = {
        name: row[name]
        for name in (
            "source_rdt",
            "init_offset",
            "init_size",
            "init_sha256",
            "main_offset",
            "main_size",
            "main_sha256",
            "events_offset",
            "events_size",
            "events_sha256",
            "cache_complete",
            "door_cache_complete",
        )
    }
    script = RoomScriptSource(
        room=RoomId(0, 9),
        dependencies=(),
        item_global_ids=tuple(row["item_global_ids"]),
        mutable_fields=(),
        **fields,
    )
    ram = bytearray(2 * 1024 * 1024)
    ram[BASE - 0x80000000 : BASE - 0x80000000 + len(data)] = data
    table = BASE + script.events_offset
    struct.pack_into("<I", ram, LAYOUT.table_pointer_address - 0x80000000, table)
    for index, offset in enumerate(program.event_program.entries):
        struct.pack_into("<I", ram, table - 0x80000000 + 4 * index, BASE + offset)
    return ram, script, program


def activate(ram, point, slot=0):
    offset = LAYOUT.pool_address - 0x80000000 + slot * LAYOUT.stride
    ram[offset], ram[offset + 2], ram[offset + 3] = (
        point.state,
        1,
        255 if point.depth == 0 else point.depth - 1,
    )
    struct.pack_into("<I", ram, offset + 8, BASE + point.offset)
    for index, (kind, repeat, command) in enumerate(point.frames):
        if kind in ("loop", "call"):
            struct.pack_into("<I", ram, offset + 12 + 4 * index, BASE + repeat)
        if kind == "call":
            struct.pack_into("<I", ram, offset + 28 + 4 * index, BASE + command)


def read(ram, script, program, registry=bytes(12)):
    return read_event_snapshot(
        LAYOUT,
        (script,),
        {script.source_rdt: program},
        BASE,
        registry,
        RamReader(ram).read_memory,
    )


def test_shared_native_bytes_keep_every_indexed_owner():
    data = bytes(0x20) + struct.pack("<III", 12, 12, 0) + b"\xfe\xff"
    result = scan_event_program(data, 0x20, len(data))
    assert result.status == "clean"
    assert {(p.entry, p.offset) for p in result.points} == {
        (0, 0x2C),
        (0, 0x2D),
        (1, 0x2C),
        (1, 0x2D),
    }


def test_vm_creation_and_reinitialization_keep_distinct_ownership():
    data = bytes(0x20) + indexed(bytes((5, 255, 1, 0, 8, 1)), b"\xfe\xff")
    result = scan_event_program(data, 0x20, len(data))
    assert result.status == "clean"
    assert [(s.entry, s.kind, s.args) for s in result.starts] == [
        (0, "start", (255, 1)),
        (0, "restart", (1,)),
    ]
    target = result.entries[1]
    assert {p.entry for p in result.points if p.offset == target} == {1}


def test_scd_event_starts_keep_their_guard_and_native_return(rules):
    code = guard(bytes((4, 1, 0, 0)), bytes((0x14, 99, 255, 0, 0x13, 0, 0, 0))) + b"\0"
    program = compile_program(
        rules, pickup(0, 0x44, 111) + b"\0", code, indexed_event(b"\xff")
    )
    starts = [
        c
        for p in program.main_procedures
        for c in p.commands
        if c.kind == "event-start"
    ]
    assert [c.args for c in starts] == [(255, 0)]
    ram = bytearray(2 * 1024 * 1024)
    address, mask = rules[0].flag(1, 0)
    ram[address - 0x80000000] = mask
    # The event start's return of one must continue to the handler update.
    assert evaluate(program, rules, ram).items.items[0].state.value == "unavailable"


@pytest.mark.parametrize("op", [0x24, 0x2D])
def test_callback_nine_preserves_the_wrappers_return_contract(rules, op):
    program = compile_program(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        bytes((op, 1, 9, 0, 0x13, 0, 0, 0, 0)),
        indexed_event(b"\xff"),
    )
    result = evaluate(program, rules, bytearray(2 * 1024 * 1024))
    assert result.items.list_complete == (op == 0x24)
    if op == 0x24:
        assert result.items.items[0].state.value == "unavailable"


def test_native_event_positions_bind_items_doors_and_reverse(rules):
    change = bytes((7, 6, 0x13, 0, 0, 0, 7, 6, 0x13, 1, 0, 0, 0xF8, 0xF9, 4, 0, 0xFF))
    ram, script, program = setup(
        rules, pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0", indexed_event(change)
    )
    point = next(p for p in program.event_program.points if p.phase == "waiting")
    activate(ram, point)
    before = read(ram, script, program)
    assert before.ok and before.events[0].phase == "waiting"
    assert before.events[0].owners == ((script.source_rdt, 0),)
    assert before.events[0].item_slots == (0,)
    assert before.events[0].door_slots == (1,)
    ram[LAYOUT.pool_address - 0x80000000 + 2] = 0
    stopped = read(ram, script, program)
    assert stopped.events == () and stopped.positions == ()
    activate(ram, point)
    assert read(ram, script, program) == before


def test_inactive_garbage_and_counter_changes_do_not_change_activation(rules):
    ram, script, program = setup(rules, b"\0", indexed_event(b"\xf8\xf9\x02\x00\xff"))
    before = read(ram, script, program)
    offset = LAYOUT.pool_address - 0x80000000
    ram[offset : offset + 52] = bytes([255]) * 52
    ram[offset + 2] = 0
    assert read(ram, script, program) == before
    activate(ram, next(p for p in program.event_program.points if p.phase == "waiting"))
    active = read(ram, script, program)
    ram[offset + 0x2C] ^= 4
    assert read(ram, script, program) == active


@pytest.mark.parametrize("corruption", ["pc", "state", "depth", "table", "relocation"])
def test_wrong_or_partial_source_never_invents_an_owner(rules, corruption):
    ram, script, program = setup(rules, b"\0", indexed_event(b"\xfe\xff"))
    activate(ram, program.event_program.points[0])
    offset = LAYOUT.pool_address - 0x80000000
    if corruption == "pc":
        struct.pack_into("<I", ram, offset + 8, BASE + script.events_offset + 1)
    elif corruption == "state":
        ram[offset] = 2
    elif corruption == "depth":
        ram[offset + 3] = 4
    elif corruption == "table":
        ram[LAYOUT.table_pointer_address - 0x80000000] ^= 1
    else:
        struct.pack_into(
            "<I",
            ram,
            BASE - 0x80000000 + script.events_offset,
            program.event_program.entries[0] - script.events_offset,
        )
    result = read(ram, script, program)
    assert result.ok and result.events[0].phase == "unbound"
    assert result.events[0].owners == () and result.events[0].reason


def test_aliases_remain_ambiguous_and_are_not_selected_by_table_order(rules):
    ram, script, program = setup(
        rules, b"\0", struct.pack("<III", 12, 12, 0) + b"\xfe\xff"
    )
    activate(ram, program.event_program.points[0])
    assert read(ram, script, program).events[0].owners == (
        (script.source_rdt, 0),
        (script.source_rdt, 1),
    )


@pytest.mark.parametrize("kind", ["loop", "call"])
def test_live_stack_pointers_must_match_the_source_flow(rules, kind):
    code = (
        b"\xfa\x00\x02\x00\xfe\xfb\xff"
        if kind == "loop"
        else b"\xfc\x06\x04\x01\x00\x00\xfe\xfd\xff"
    )
    ram, script, program = setup(rules, b"\0", indexed_event(code))
    point = next(
        p for p in program.event_program.points if p.frames and p.frames[-1][0] == kind
    )
    activate(ram, point)
    assert read(ram, script, program).events[0].owners
    offset = LAYOUT.pool_address - 0x80000000
    for field in (12, 28) if kind == "call" else (12,):
        old = ram[offset + field]
        ram[offset + field] ^= 1
        assert read(ram, script, program).events[0].phase == "unbound"
        ram[offset + field] = old
    assert read(ram, script, program).events[0].owners


@pytest.mark.parametrize(
    "command", [b"\x24\x00\x04\x00", b"\x2d\x00\x0f\x00", b"\x4c\x01\x00\x00"]
)
def test_standalone_awards_and_quantity_writes_are_linked_to_items(rules, command):
    ram, script, program = setup(
        rules,
        pickup(0, 0x44, 111) + b"\0",
        indexed_event(b"\x07\x06" + command + b"\xff"),
    )
    activate(ram, program.event_program.points[0])
    assert read(ram, script, program).events[0].item_slots == (0,)


@pytest.mark.parametrize(
    "command,kind,slot",
    [
        (b"\x24\x00\x04\x00", "award", 0),
        (b"\x2d\x00\x0f\x00", "award", 0),
        (b"\x24\x01\x01\x00", "aot-callback", 1),
        (b"\x4c\x01\x00\x00", "quantity-transfer", 0),
        (b"\x4c\x02\x00\x00", "quantity-transfer", 0),
    ],
)
def test_full_dispatch_retains_guards_for_awards_doors_and_quantities(
    rules, command, kind, slot
):
    code = guard(bytes((4, 1, 31, 0)), command) + b"\0"
    ram, script, program = setup(
        rules,
        pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0",
        indexed_event(block(code) + b"\xff"),
    )
    commands = [c for p in program.event_blocks[0] for c in p.commands]
    assert any(c.kind == "flag-test" for c in commands)
    assert any(c.kind == kind for c in commands)
    activate(ram, program.event_program.points[0])
    active = read(ram, script, program).events[0]
    assert slot in active.item_slots + active.door_slots


def test_vm_and_scd_starts_link_transitive_item_and_door_changes(rules):
    event = indexed(
        b"\x05\xff\x01\x00\xfe\xff",
        b"\x07\x06\x14\x00\xff\x02\xff",
        b"\x07\x06\x13\x00\x00\x00\x07\x06\x13\x01\x00\x00\xff",
    )
    ram, script, program = setup(
        rules, pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0", event
    )
    activate(ram, next(p for p in program.event_program.points if p.entry == 0))
    active = read(ram, script, program).events[0]
    assert active.owners == ((script.source_rdt, 0),)
    assert active.item_slots == (0,) and active.door_slots == (1,)


@pytest.mark.parametrize("loop", [False, True])
@pytest.mark.parametrize("advance", [1, 2, 3])
def test_parent_start_position_keeps_ownership_and_frame_checks(rules, loop, advance):
    parent = (
        (b"\xfa\x00\x02\x00" if loop else b"")
        + b"\x05\x18\x01\x00"
        + (b"\xfb" if loop else b"")
        + b"\xff"
    )
    child = b"\x07\x06\x13\x00\x00\x00\x07\x06\x13\x01\x00\x00\xff"
    ram, script, program = setup(
        rules, pickup(0, 0x44, 111) + door(1, 8, 0x34) + b"\0", indexed(parent, child)
    )
    start = program.event_program.starts[0]
    point = next(
        point for point in program.event_program.points if point.offset == start.offset
    )
    # The native helper stores parent PC+1 while initializing a child. These
    # substitutions exercise that captured position, not real CPU execution.
    activate(ram, replace(point, offset=start.offset + advance), slot=7)
    active = read(ram, script, program).events[0]
    if advance == 1:
        assert active.phase == "active" and active.owners == ((script.source_rdt, 0),)
        assert active.item_slots == (0,) and active.door_slots == (1,)
        if loop:
            ram[LAYOUT.pool_address - 0x80000000 + 7 * LAYOUT.stride + 12] ^= 1
            assert read(ram, script, program).events[0].phase == "unbound"
    else:
        assert active.phase == "unbound" and active.owners == ()
    # A readable in-flight PC is not another VM entry into its operand bytes.
    assert not any(
        point.offset in (start.offset + 2, start.offset + 3)
        for point in program.event_program.points
    )


def test_restart_cycles_are_bounded_without_inventing_execution(rules):
    ram, script, program = setup(rules, b"\0", indexed(b"\x08\x01", b"\x08\x00"))
    activate(ram, program.event_program.points[0])
    active = read(ram, script, program).events[0]
    assert active.owners and active.item_slots == () and active.door_slots == ()


def test_registered_interaction_uses_current_parameter_bytes_and_reverses(rules):
    creator = bytearray(18)
    creator[0], creator[1], creator[10], creator[11] = 0x0D, 2, 9, 0x81
    struct.pack_into("<HH", creator, 12, 0xA0FF, 0xB000)
    change = bytes((7, 6, 0x13, 0, 0, 0, 0xFF))
    ram, script, program = setup(
        rules, pickup(0, 0x44, 111) + bytes(creator) + b"\0", indexed_event(change)
    )
    assert program.event_program.registry_writes[0][1:] == (2, 0xA0FF, 0xB000, 0)
    offset = next(
        offset for offset, slot in program.event_program.creators if slot == 2
    )
    registry = bytearray(36)
    struct.pack_into(
        "<BBHHHI", registry, 24, 9, 0x81, 0xA0FF, 0xB000, 0, BASE + offset + 2
    )
    before = read(ram, script, program, bytes(registry))
    assert before.interactions[0].requested_slot == 255
    assert before.interactions[0].entry == 0 and before.interactions[0].item_slots == (
        0,
    )
    registry[24 + 4] = 1
    assert read(ram, script, program, bytes(registry)).interactions[0].reason
    registry[24 + 4] = 0
    assert read(ram, script, program, bytes(registry)) == before


@pytest.mark.parametrize("short", [False, True])
def test_failed_pool_or_table_reads_are_explicit(rules, short):
    ram, script, program = setup(rules, b"\0", indexed_event(b"\xfe\xff"))
    for failure in (
        LAYOUT.pool_address,
        LAYOUT.table_pointer_address,
        BASE + script.events_offset,
    ):

        def reader(address, width, failed_address=failure):
            if address == failed_address:
                return MemRead(
                    short,
                    bytes(max(0, width - 1)) if short else b"",
                    "" if short else "disconnected",
                )
            return RamReader(ram).read_memory(address, width)

        result = read_event_snapshot(
            LAYOUT, (script,), {script.source_rdt: program}, BASE, bytes(12), reader
        )
        assert not result.ok and result.error and not result.events


def test_live_poll_rechecks_activity_and_does_not_retain_a_stopped_owner(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    reader = RamReader(ram)
    room = RoomId(0, 9)
    sources = match_room_source(
        profile.runtime_room_layout, profile.room_sources, room, reader.read_memory
    ).sources
    base = int.from_bytes(ram[0xCAB10:0xCAB14], "little")
    point = next(
        p
        for p in profile.room_programs[sources[0].source_rdt].event_program.points
        if p.state == 0 and p.depth == 0
    )
    offset = profile.event_layout.pool_address - 0x80000000
    ram[offset], ram[offset + 2], ram[offset + 3] = point.state, 1, 255
    struct.pack_into("<I", ram, offset + 8, base + point.offset)
    tracker = Tracker()
    active = poll_once(profile, tracker, reader.read_memory)
    assert active.status == PollStatus.Display and "Active events: 1" in active.text
    ram[offset + 2] = 0
    stopped = poll_once(profile, tracker, reader.read_memory)
    assert stopped.status == PollStatus.Display and "Active events: 0" in stopped.text
    assert "Event slot 0:" not in stopped.text
    ram[offset + 2] = 1
    assert poll_once(profile, tracker, reader.read_memory).text == active.text

    def changing(address, width):
        result = reader.read_memory(address, width)
        if address == profile.event_layout.pool_address:
            ram[offset + 2] ^= 1
        return result

    unchanged = deepcopy(tracker)
    assert poll_once(profile, tracker, changing).status == PollStatus.Retry
    assert tracker == unchanged


def test_unbound_active_event_prevents_false_clearance(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_after.sav", tmp_path)
    offset = profile.event_layout.pool_address - 0x80000000
    ram[offset + 2] = 1
    struct.pack_into("<I", ram, offset + 8, 0x80010000)
    tracker = Tracker()
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status == PollStatus.Display and "State: UNKNOWN" in result.text
    assert not tracker.room_state(RoomId(0, 9)).doors_complete


def test_activation_schema_and_pinned_layout_are_mandatory(rules):
    program = compile_program(rules, b"\0", event=indexed_event(b"\xfe\xff"))
    raw = {
        "entries": [1],
        "points": [],
        "dispatches": [{"entry": 0, "offset": 2, "commands": [3]}],
        "starts": [],
        "failures": [],
        "door_rules": [],
        "creators": [],
        "registry_writes": [],
        "changes": [],
        "script_starts": [],
    }
    with pytest.raises(ValueError, match="dispatch"):
        EventProgram.load(raw)
    with pytest.raises(ValueError, match="ownership"):
        replace(
            program.event_program,
            points=(replace(program.event_program.points[0], entry=2),),
        )
    with pytest.raises(ValueError, match="layout"):
        replace(LAYOUT, capacity=9)


@pytest.mark.parametrize("corruption", ["frame", "initial"])
def test_profile_rejects_unbounded_frames_and_missing_entry_positions(
    tmp_path, corruption
):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    manifest = json.loads((REPO / "data/room_manifest_slus00551.json").read_text())
    row = next(
        row
        for row in manifest["rooms"]
        if any(
            frame[0] in ("loop", "call")
            for point in row["tracking_program"]["event_program"]["points"]
            for frame in point["frames"]
        )
    )
    events = row["tracking_program"]["event_program"]
    if corruption == "frame":
        frame = next(
            frame
            for point in events["points"]
            for frame in point["frames"]
            if frame[0] in ("loop", "call")
        )
        frame[1] = row["events_offset"] + row["events_size"]
    else:
        for point in events["points"]:
            if (point["entry"], point["offset"], point["state"], point["depth"]) == (
                0,
                events["entries"][0],
                0,
                0,
            ):
                point["state"] = 1
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest))
    raw["room_manifest_path"] = str(manifest_path)
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(
        ValueError,
        match="outside source events"
        if corruption == "frame"
        else "initial VM position",
    ):
        Re1Profile.load(profile_path)
