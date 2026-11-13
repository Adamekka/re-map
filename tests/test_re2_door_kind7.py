"""RE2-DOOR-012: bounded numeric Copy, owned factories and synthetic controls."""

import copy
import hashlib
from dataclasses import replace
from types import SimpleNamespace

import pytest
import test_re2_tracking
from test_re2_immutable_open_doors import door
from test_re2_native_frame_execution import execute as execute
from test_re2_persistent_registration import interaction
from test_re2_positive_prefix import owned as owned
from test_re2_startup_declarations import END, contract, described
from test_re2_tracking import profile as profile

from games.game_profile import RoomId
from games.re2.door_authority import (
    DoorAuthority,
    compile_door_access,
    compile_door_authority,
)
from games.re2.door_entry import DoorEntryFailure, compile_door_entry_binding
from games.re2.live_tracking import poll_re2
from games.re2.native_control import TASK_BASE
from games.re2.scenario_entry_scope import (
    DoorSourceFacts,
    DoorSourceFailure,
    _ScopePolicy,
    _source_scope_facts,
)
from games.re2.scenario_selection import ScenarioSelectionFailure, bind_scenario_context
from games.re2.source_task_control import TaskControlSupport
from tracker.exploration_state import DoorUnlockState, Tracker
from tracker.polling import PollStatus

snapshot = test_re2_tracking.snapshot


def test_owned_public_factory_closes_numeric_kind7_copy_without_counter_values(owned):
    profile, _, _, _, sources, bound, _, rooms = owned
    data, room = sources["03-07"], rooms["03-07"]
    assert data[3756:3770] == bytes.fromhex("1d04040146030741000000000000")
    authority = compile_door_authority(data, room, profile, bound)
    assert type(authority) is DoorAuthority
    facts, gaps, excluded = compile_door_access(data, room, profile, authority)
    assert [(f.slot, f.creator_offsets) for f in facts] == [
        (0, (1686,)),
        (1, (1718,)),
        (2, (1750,)),
    ]
    assert not gaps and not excluded
    assert all(f.enabled and f.activation_mask == 0x31 and not f.lock_id for f in facts)


@pytest.mark.parametrize("record", ["ordinary", "four-point", "reset"])
@pytest.mark.parametrize(
    "delta,word,allowed",
    [
        (0, False, True),
        (1, False, True),
        (0, True, True),
        (-1, True, False),
        (1, True, False),
        (2, True, False),
        (4, True, False),
        (-4, False, False),
        (-3, False, False),
        (-2, False, False),
    ],
)
def test_numeric_interval_uses_fresh_record_layout_and_copy_width(
    owned, record, delta, word, allowed
):
    p = owned[0]
    four = record == "four-point"
    target = (
        bytes((0x46, 3, 7, 0x31)) + bytes(6)
        if record == "reset"
        else interaction(slot=3, kind=7, four_point=four)
    )
    payload = 4 if record == "reset" else 22 if four else 14
    packet = bytes((0x1D, 4, payload + delta, word))
    data, room, _ = described(
        door() + interaction(slot=3, kind=7, four_point=four) + END,
        (packet + target + END, END),
    )
    context = bind_scenario_context(p, contract(p, room))
    result = _source_scope_facts(
        data, room, p, context, _ScopePolicy.TrustedDoors, TaskControlSupport.Unaudited
    )
    assert (type(result) is DoorSourceFacts) is allowed
    if not allowed:
        assert result == DoorSourceFailure("copy_changes_unclosed_operand")


@pytest.mark.parametrize("kind", [0, 1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13, 14])
def test_other_kinds_receive_no_numeric_copy_permission(owned, kind):
    p = owned[0]
    target = bytes((0x46, 3, kind, 0x31)) + bytes(6)
    data, room, _ = described(
        door() + interaction(slot=3, kind=7) + END,
        (b"\x1d\x04\x04\x01" + target + END, END),
    )
    context = bind_scenario_context(p, contract(p, room))
    # Kind13 already fails shared camera-write bounds before Copy is inspected.
    assert _source_scope_facts(
        data, room, p, context, _ScopePolicy.TrustedDoors, TaskControlSupport.Unaudited
    ) == DoorSourceFailure(
        "explicit_source_write_footprint"
        if kind == 13
        else "copy_changes_unclosed_operand"
    )


@pytest.mark.parametrize(
    "policy",
    [
        _ScopePolicy.AuditedNativeWork,
        _ScopePolicy.TrustedNormalEngine,
        _ScopePolicy.TrustedPositivePrefix,
        _ScopePolicy.IdentityFiltering,
    ],
)
def test_kind7_numeric_interval_grants_no_other_policy_right(owned, policy):
    p = owned[0]
    data, room, _ = described(
        door() + interaction(slot=3, kind=7) + END,
        (bytes.fromhex("1d04040146030741000000000000") + END, END),
    )
    context = bind_scenario_context(p, contract(p, room))
    assert (
        _source_scope_facts(
            data, room, p, context, policy, TaskControlSupport.Unaudited
        )
        is ScenarioSelectionFailure.EntryScope
    )


@pytest.mark.parametrize("fault", ["odd-record", "whole-payload", "counter"])
def test_unaligned_payload_whole_payload_and_bad_counter_are_rejected(owned, fault):
    p = owned[0]
    target = bytes((0x46, 3, 7, 0x31)) + bytes(6)
    # A native Copy writes only one byte or one word. Three word Copies model
    # an attempted whole-payload rewrite, including the forbidden later words.
    prefix = b"\x00" if fault == "odd-record" else b""
    copies = (
        b"\x1d\x04\x0c\x01\x1d\x04\x0a\x01\x1d\x04\x08\x01"
        if fault == "whole-payload"
        else bytes((0x1D, 255 if fault == "counter" else 4, 4, 1))
    )
    data, room, _ = described(
        door() + interaction(slot=3, kind=7) + END,
        (prefix + copies + target + END, END),
    )
    context = bind_scenario_context(p, contract(p, room))
    result = _source_scope_facts(
        data, room, p, context, _ScopePolicy.TrustedDoors, TaskControlSupport.Unaudited
    )
    assert result == DoorSourceFailure(
        "copy_counter_bounds" if fault == "counter" else "copy_changes_unclosed_operand"
    )


@pytest.mark.parametrize(
    "address",
    [
        0x800A73E0,
        0x800A753C,
        0x800A75E0,
        0x80051A2C,
        0x80051A3C,
        0x80051A44,
        0x800542B4,
        0x8005430C,
        0x80055154,
        0x800551C4,
    ],
)
def test_native_semantic_binding_rejects_changed_tables_and_complete_windows(
    owned, monkeypatch, address
):
    from games.re2 import door_entry

    p, _, _, _, sources, bound, _, rooms = owned
    original = door_entry.native_bytes

    def changed(executable, at, width):
        result = bytearray(original(executable, at, width))
        if at <= address < at + width:
            result[address - at] ^= 1
        return bytes(result)

    monkeypatch.setattr(door_entry, "native_bytes", changed)
    assert (
        compile_door_entry_binding(sources["03-07"], rooms["03-07"], p, bound)
        is DoorEntryFailure.Binding
    )


def test_kind7_authority_keeps_complete_source_corpus_profile_and_receipt_binding(
    owned,
):
    p, _, _, _, sources, bound, _, rooms = owned
    data, room = sources["03-07"], rooms["03-07"]
    authority = compile_door_authority(data, room, p, bound)
    for at in (3756, 3757, 3761, 3762, 3763, 1984, 1990):
        changed = bytearray(data)
        changed[at] ^= 1
        assert (
            type(compile_door_authority(bytes(changed), room, p, bound))
            is not DoorAuthority
        )
    corpus = copy.copy(bound.entry_resources.corpus)
    object.__setattr__(corpus, "scripts", corpus.scripts[:-1])
    altered = replace(
        bound, entry_resources=replace(bound.entry_resources, corpus=corpus)
    )
    assert type(compile_door_authority(data, room, p, altered)) is not DoorAuthority
    changed_profile = copy.deepcopy(p)
    changed_profile["runtime_layout"]["aot_capacity"] += 1
    assert (
        type(compile_door_authority(data, room, changed_profile, bound))
        is not DoorAuthority
    )
    for field, value in (
        ("audit", "slus00748-trusted-normal-door-access-v3"),
        ("entry_audit", "slus00748-bounded-ff-native-door-entry-v2"),
    ):
        changed_profile = copy.deepcopy(p)
        changed_profile["trusted_door_policy"][field] = value
        assert (
            type(compile_door_authority(data, room, changed_profile, bound))
            is not DoorAuthority
        )
    receipt = copy.copy(authority.entry_binding)
    object.__setattr__(receipt, "native_windows", receipt.native_windows[:-1])
    with pytest.raises(AssertionError):
        receipt.matches(data, room, p, bound.declarations)
    assert hashlib.sha256(data).hexdigest() == authority.source_sha256


@pytest.mark.parametrize("value", [0, 1, 0x7FFF, 0x8000, 0xFFFF])
@pytest.mark.parametrize("actor", [0x800C7C30, 0x80170000])
def test_owned_kind7_leaf_has_only_scalar_store_and_preserves_abi(
    execute, value, actor
):
    # Explicit synthetic actor/payload records exercise the complete copied
    # native leaf. No current actor, counter value or gameplay state is assumed.
    execute(
        0x80051A2C,
        0,
        0,
        b"\0\0",
        [(TASK_BASE, value, 2), (0x800CE330, actor, 4)],
        [(actor + 0x10C, value, 2)],
        result=0,
    )


@pytest.mark.parametrize("relative,word", [(4, True), (4, False), (5, False)])
@pytest.mark.parametrize("value", [0, 0x7FFF, 0x8000, 0xFFFF])
def test_owned_copy_stores_exact_word_or_byte_and_advances_pc(
    execute, relative, word, value
):
    pc = 0x80180000
    execute(
        0x800542B4,
        0,
        0,
        bytes((0x1D, 4, relative, word)) + bytes(10),
        [(0x800D47F4, value, 2)],
        [
            (TASK_BASE + 0x1C, pc + 4, 4),
            (pc + 4 + relative, value if word else value & 255, 2 if word else 1),
        ],
    )


@pytest.mark.parametrize("four", [False, True])
@pytest.mark.parametrize("value", [0, 0x7FFF, 0x8000, 0xFFFF])
def test_owned_reset_installs_kind7_and_only_six_payload_bytes(execute, four, value):
    descriptor, pc = 0x80170000, 0x80180000
    payload = descriptor + (20 if four else 12)
    execute(
        0x80055154,
        0,
        0,
        bytes((0x46, 3, 7, 0x41))
        + value.to_bytes(2, "little")
        + bytes.fromhex("7856bc9a"),
        [(0x800CE564, descriptor, 4), (descriptor + 1, 0xB1 if four else 0x31, 1)],
        [
            (descriptor, 7, 1),
            (descriptor + 1, 0xC1 if four else 0x41, 1),
            (payload, value, 2),
            (payload + 2, 0x5678, 2),
            (payload + 4, 0x9ABC, 2),
            (TASK_BASE + 0x1C, pc + 10, 4),
        ],
    )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-07"], indirect=True)
def test_kind7_departure_reentry_reconstruction_and_opt_out(snapshot):
    p, _, _, _ = snapshot
    departed = test_re2_tracking.snapshot.__wrapped__(SimpleNamespace(param="00-01"), p)
    tracker = Tracker()
    for used_profile, _, _, read in (snapshot, departed, snapshot, departed):
        old = copy.deepcopy(tracker)
        without = replace(
            used_profile,
            door_catalogs={
                key: catalog
                for key, catalog in used_profile.door_catalogs.items()
                if key != "03-07"
            },
        )
        assert poll_re2(used_profile, tracker, read).status is PollStatus.Display
        assert poll_re2(without, old, read).status is PollStatus.Display
        affected = [d for d in tracker.doors if str(d.source) == "03-07"]
        assert len(affected) == 3
        assert all(d.state == "OPEN" for d in affected)
        if str(tracker.current) == "00-01":
            # Open access on a door without a native lock flag does not invent
            # a separate observed unlock event or its padlock marker.
            assert all(d.unlock_state is DoorUnlockState.Unknown for d in affected)
            assert all(
                d.state == "UNCHECKED" for d in old.doors if str(d.source) == "03-07"
            )
        for key in tracker.rooms:
            assert tracker.rooms[key].items == old.rooms[key].items
            assert tracker.rooms[key].completion == old.rooms[key].completion
        fresh = Tracker()
        for key in tracker.rooms:
            stage, room = (int(part, 16) for part in key.split("-"))
            fresh.mark_current(RoomId(stage, room))
        assert poll_re2(used_profile, fresh, read).status is PollStatus.Display
        assert fresh.doors == tracker.doors
    assert set(tracker.rooms) == {"00-01", "03-07"}


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-07"], indirect=True)
@pytest.mark.parametrize("fault", ["missing", "inactive", "contradictory"])
def test_kind7_current_descriptor_and_atomic_retry_remain_mandatory(snapshot, fault):
    p, _, put, read = snapshot
    definition = p.rooms["03-07"]["doors"][0]
    pointer = 0x80100000 + definition["offset"] + 2
    if fault == "missing":
        put(int(p.runtime_layout["aot_table_address_ps1"], 0), 0, 4)
    elif fault == "inactive":
        put(pointer + 1, 0, 1)
    else:
        put(pointer + 12 + 8, 255, 1)
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 1))
    before = copy.deepcopy(tracker)
    result = poll_re2(p, tracker, read)
    if fault == "contradictory":
        assert result.status is PollStatus.Retry
        assert tracker == before
    else:
        assert result.status is PollStatus.Display
        actual = next(d for d in tracker.doors if d.observation_id == "03-07:1686")
        assert actual.state == ("UNCHECKED" if fault == "missing" else "BLOCKED")
