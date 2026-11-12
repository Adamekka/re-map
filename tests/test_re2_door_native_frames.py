"""RE2-DOOR-011: bounded FF/FF native receiving contract, Candidate."""

import pytest
from test_re2_positive_prefix import owned as owned

from games.re2.door_authority import (
    DoorAuthority,
    compile_door_authority,
    door_access_catalog,
)


@pytest.mark.parametrize(
    "key,offsets",
    [
        ("00-04", (2994,)),
        ("00-08", (6446, 6478)),
        ("00-0a", (6602, 6634, 6666, 6698)),
        ("00-11", (8158, 8190)),
        ("01-06", (5334,)),
        ("01-0f", (5938, 5970, 6002)),
        ("01-12", (1986, 2018)),
        ("01-13", (3714,)),
        ("02-07", (4178, 4210, 4242)),
        ("02-0b", (2902, 2934, 2966, 3030)),
        ("03-08", (10174, 10206)),
        ("05-04", (8112,)),
        ("05-05", (6578,)),
        ("05-15", (11158,)),
    ],
)
def test_owned_public_factory_and_catalog_close_stage_a_rows(owned, key, offsets):
    profile, _, _, _, sources, bound, _, rooms = owned
    authority = compile_door_authority(sources[key], rooms[key], profile, bound)
    assert type(authority) is DoorAuthority
    catalog = door_access_catalog(sources[key], rooms[key], profile, bound)
    assert tuple(at for f in catalog["facts"] for at in f["creator_offsets"]) == offsets


def test_owned_public_factory_keeps_scenario_exclusion_separate(owned):
    profile, _, _, _, sources, bound, _, rooms = owned
    catalog = door_access_catalog(sources["04-05"], rooms["04-05"], profile, bound)
    assert catalog["scenario_excluded_offsets"] == [2996]
    assert catalog["facts"] == []


import copy
import struct

from test_re2_initializer_control import switch
from test_re2_startup_declarations import END, described

from games.re2.door_entry import _task_fields, _TaskFields
from games.re2.native_control import (
    TASK_WIDTH,
    ControlField,
    canonical_if_pointer,
    control_field,
    if_store_cell,
)
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    _foreign_fields_disjoint,
)
from games.re2.structured_control import (
    ControlFrames,
    NativeStructuredControl,
    StructuredControl,
    structured_control,
)


def polling(middle=b"", after=b""):
    block = (
        b"\x06\0"
        + struct.pack("<H", len(middle) + 6 + len(after))
        + middle
        + b"\x21\x02\x07\0"
        + after
        + b"\x08\0"
    )
    return block + b"\x17\xff\xff\0" + struct.pack("<h", -len(block)) + END


@pytest.mark.parametrize(
    "middle,accepted",
    [
        (b"", True),
        (b"\x22\x02\x08\x01", False),
        (b"\x02\0", False),
        (b"\x09\x0a\x01\0", False),
        (b"\x18\x01", False),
        (b"\x3e\0\x0c\x03\0\0", False),
    ],
)
def test_foreign_store_requires_its_own_immediate_nonyielding_predicate(
    middle, accepted
):
    data, room, _ = described(END, (polling(middle), END))
    result = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeDoors
    )
    assert (type(result) is NativeStructuredControl) is accepted


@pytest.mark.parametrize("foreign", [False, True])
@pytest.mark.parametrize("tail", [b"\x18\x01\x21\x02\x08\0", b"\x18\x01\x23\0\0\0\0\0"])
def test_call_return_reconstructs_canonical_pointer_without_inventing_cell_value(
    foreign, tail
):
    body = polling(after=tail)
    if not foreign:
        body = body[:-8] + END
    data, room, _ = described(END, (body, END))
    result = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeDoors
    )
    assert (type(result) is NativeStructuredControl) is not foreign


def test_break_preserves_pointer_and_later_if_stores_in_actual_cell():
    block = switch(b"\0")
    body = block + b"\x06\0\x06\0\x21\x02\x07\0\x08\0"
    body += b"\x17\xff\xff\0" + struct.pack("<h", -len(body)) + END
    data, room, _ = described(END, (body, END))
    frame = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeDoors
    )
    assert type(frame) is NativeStructuredControl
    assert {cell for _, cell, _ in frame.if_stores} == {0xC0, 0x4C0}
    assert any(
        field is ControlField.SavedIf and not write
        for _, field, _, write in frame.accesses
    )


@pytest.mark.parametrize("kind", ["if", "loop"])
def test_ff_goto_may_abandon_frames_at_a_bound_in_program_target(kind):
    if kind == "if":
        body = b"\x06\0\x0a\0\x21\x02\x07\0\x17\xff\xff\0\x06\0" + END
    else:
        body = b"\x0d\0\x08\0\x01\0\x17\xff\xff\0\x08\0\x0e\0" + END
    data, room, _ = described(END, (body, END))
    program = room["programs"]["17:0"]
    assert (
        type(structured_control(data, program, ControlFrames.NativeDoors))
        is NativeStructuredControl
    )
    assert not isinstance(
        structured_control(data, program, ControlFrames.Doors), StructuredControl
    )
    altered = copy.deepcopy(program)
    goto = next(r for r in altered["commands"] if r["opcode"] == 0x17)
    goto["target"] -= 1
    assert not isinstance(
        structured_control(data, altered, ControlFrames.NativeDoors), StructuredControl
    )
    changed = bytearray(data)
    changed[goto["offset"] + 1] = 1
    assert not isinstance(
        structured_control(bytes(changed), program, ControlFrames.NativeDoors),
        StructuredControl,
    )


@pytest.mark.parametrize("count", [0, 1, 0x7FFF, 0x8000, 0xFFFF])
def test_all_for_counts_keep_both_continuations_and_bound_fields(count):
    body = b"\x0d\0\x04\0" + struct.pack("<H", count) + b"\x02\0\x0e\0" + END
    data, room, _ = described(END, (body, END))
    frame = structured_control(
        data, room["programs"]["17:0"], ControlFrames.NativeDoors
    )
    assert type(frame) is NativeStructuredControl
    rows = room["programs"]["17:0"]["commands"]
    header, body = rows[0]["offset"], rows[0]["next"]
    tail = next(r["offset"] for r in rows if r["opcode"] == 0x0E)
    end = rows[-1]["offset"]
    edges = dict(frame.edges)
    assert edges[header] == tuple(sorted((body, end)))
    assert edges[tail] == tuple(sorted((body, end)))
    assert (tail, ControlField.LoopCount, 0, False) in frame.accesses
    assert (header, ControlField.SavedIf, 0, True) in frame.accesses


@pytest.mark.parametrize("depth", range(4))
@pytest.mark.parametrize("loop", range(4))
def test_every_native_frame_receiving_field_uses_its_actual_depth(depth, loop):
    assert control_field(depth, ControlField.LoopStart, loop) == (
        0x20 + depth * 16 + loop * 4,
        4,
    )
    assert control_field(depth, ControlField.LoopEnd, loop) == (
        0x60 + depth * 16 + loop * 4,
        4,
    )
    assert control_field(depth, ControlField.SavedIf, loop) == (
        0x0C + depth * 4 + loop,
        1,
    )
    assert control_field(depth, ControlField.LoopCount, loop) == (
        0xA0 + depth * 8 + loop * 2,
        2,
    )
    assert control_field(depth, ControlField.CallReturn, 0) == (0x144 + depth * 4, 4)
    for level in range(-1, 8):
        pointer = canonical_if_pointer(level)
        assert pointer == 0xC0 + 4 * (level + 1)
        for task in (0, 1, 2, 9, 10, 13):
            assert if_store_cell(task, depth, pointer) == divmod(
                task * TASK_WIDTH + pointer + 32 * depth, TASK_WIDTH
            )


@pytest.mark.parametrize("cell", [0x64, 0x68, 0x6C])
def test_foreign_break_receivers_are_not_numeric_scratch(cell):
    assert _foreign_fields_disjoint(frozenset((cell,)), (0x60,))
    assert not _foreign_fields_disjoint(frozenset((cell,)), (cell,))


@pytest.mark.parametrize("cell", [0x0C, 0x20, 0xA0, 0xA4, 0xC0, 0x140, 0x144])
def test_foreign_stores_cannot_replace_other_frame_fields(cell):
    assert not _foreign_fields_disjoint(frozenset((cell,)), ())


@pytest.mark.parametrize("depth", [0, 1, 2, 3])
def test_eventnext_preserves_task_and_rejects_positive_call_depth(depth):
    main = [bytes((0x18, i + 1)) + END for i in range(depth)]
    main += [b"\x03\0\x18" + bytes((depth + 1,)) + END, END]
    data, room, _ = described(END, tuple(main))
    result = _task_fields(data, room["programs"], auxiliary=False)
    if depth:
        assert result is PositiveEntryFailure.Control
    else:
        assert type(result) is _TaskFields
        assert ("17:1", 1, 0) in result.entries
        assert result.replacements


@pytest.mark.parametrize("key", ["01-0b", "03-0a", "02-04", "05-0c", "04-05"])
def test_new_frame_contract_keeps_independent_unsafe_or_history_paths_unresolved(
    owned, key
):
    p, _, _, _, sources, bound, _, rooms = owned
    catalog = door_access_catalog(sources[key], rooms[key], p, bound)
    assert catalog["facts"] == []
    assert catalog["unsupported"]


@pytest.mark.parametrize("producer", ["callback", "four-point", "reset", "exec"])
@pytest.mark.parametrize("entered", [False, True])
def test_every_callback_reset_and_unentered_producer_alternative_contributes(
    producer, entered
):
    from test_re2_source_task_control import callback, reset

    packet = (
        callback(3, 3)
        if producer in ("callback", "four-point")
        else reset(3, 3)
        if producer == "reset"
        else b"\x04\x0a\x18\x03"
    )
    if producer == "four-point":
        packet = bytes((0x67,)) + packet[1:6] + bytes(16) + packet[14:]
    data, room, _ = described(
        END, ((b"\x18\x02" if entered else b"") + END, END, packet + END, END)
    )
    result = _task_fields(data, room["programs"], auxiliary=False)
    assert type(result) is _TaskFields
    assert {task for key, task, depth in result.entries if key == "17:3"} == set(
        range(2, 10)
    )
    assert any(
        owner == "17:2" and target == "17:3" for owner, _, target, _ in result.producers
    )
    changed = bytearray(data)
    at = room["programs"]["17:2"]["entry"]
    changed[
        at
        + (
            3
            if producer == "exec"
            else 7
            if producer == "reset"
            else 25
            if producer == "four-point"
            else 17
        )
    ] = 255
    from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES

    from games.re2.room_data import decode_room

    altered = decode_room(
        bytes(changed), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    assert (
        _task_fields(bytes(changed), altered["programs"], auxiliary=False)
        is PositiveEntryFailure.Control
    )


@pytest.mark.parametrize("nesting", [1, 2, 3, 4])
def test_receiver_break_overlap_uses_all_actual_tasks_and_depths(nesting):
    receiver = b"\0"
    for _ in range(nesting):
        receiver = switch(receiver)
    data, room, _ = described(
        END, (b"\x04\xff\x18\x02\x04\xff\x18\x03" + END, END, polling(), receiver + END)
    )
    result = _task_fields(data, room["programs"], auxiliary=False)
    assert (type(result) is _TaskFields) is (nesting == 1)
    if nesting > 1:
        assert result is PositiveEntryFailure.ForeignConsumer


def test_no_producer_does_not_invent_an_entry_or_native_store():
    data, room, _ = described(END, (END, END, polling()))
    result = _task_fields(data, room["programs"], auxiliary=False)
    assert type(result) is _TaskFields
    assert all(key != "17:2" for key, _, _ in result.entries)
    assert all(key != "17:2" for key, *_ in result.stores)
    # The hypothetical frame is still parsed for source/control protection.
    assert "17:2" in dict(result.frames)


@pytest.mark.parametrize("atomic", [False, True])
def test_overlapping_while_receiver_requires_an_uninterrupted_bound_predicate(atomic):
    check = b"\x21\x02\x07\0" if atomic else b"\x3e\0\x0c\x03\0\0"
    # Two nested WHILE frames place the second end at receiver+64, where
    # another task's escaped IF may write. No counter value is sampled.
    inner = (
        b"\x0f"
        + bytes((len(check),))
        + struct.pack("<h", len(check) + 3)
        + check
        + b"\0\x10\0"
    )
    outer = (
        b"\x0f\x04"
        + struct.pack("<h", 4 + len(inner) + 2)
        + b"\x21\x02\x07\0"
        + inner
        + b"\x10\0"
        + END
    )
    data, room, _ = described(
        END, (b"\x04\xff\x18\x02\x04\xff\x18\x03" + END, END, polling(), outer)
    )
    result = _task_fields(data, room["programs"], auxiliary=False)
    assert (type(result) is _TaskFields) is atomic
    if not atomic:
        assert result is PositiveEntryFailure.ForeignConsumer


from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import Tracker
from tracker.polling import PollStatus


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-08"], indirect=True)
@pytest.mark.parametrize("binding", ["missing", "inactive", "contradictory"])
def test_observed_source_facts_never_override_current_descriptor_or_reveal_on_retry(
    snapshot, binding
):
    profile, _, put, read = snapshot
    source = profile.rooms["03-08"]
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    definition = source["doors"][0]
    if binding != "missing":
        pointer = 0x80100000 + definition["offset"] + 2
        put(registry + definition["slot"] * 4, pointer, 4)
        put(
            pointer + (1 if binding == "inactive" else 20),
            0 if binding == "inactive" else 255,
            1,
        )
    tracker = Tracker()
    tracker.mark_current(RoomId(3, 10))
    before = copy.deepcopy(tracker)
    result = poll_re2(profile, tracker, read)
    if binding == "contradictory":
        assert result.status is PollStatus.Retry
        assert tracker == before
        assert "03-08" not in tracker.rooms
    else:
        assert result.status is PollStatus.Display
        actual = next(
            d
            for d in tracker.doors
            if d.observation_id == f"03-08:{definition['offset']}"
        )
        assert actual.state == ("UNCHECKED" if binding == "missing" else "BLOCKED")
