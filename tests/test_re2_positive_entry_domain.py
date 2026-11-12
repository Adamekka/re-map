"""RE2-STARTUP-008: real binding and unsealed source-role negative controls."""

import copy
import json
import sys
from dataclasses import replace

import pytest
from test_re2_positive_prefix import owned as owned  # noqa: PLC0414
from test_re2_tracking import profile as profile  # noqa: PLC0414
from test_re2_tracking import snapshot as snapshot

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.known_puzzle_items import (
    KnownDeclaredItems,
    known_declared_items_from_prefix,
)
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    _numeric_copy_ranges,
    _PositiveEntryDomain,
    _source_entry_roles,
    _SourceEntryRoles,
)
from games.re2.positive_prefix import (
    VerifiedNormalEnginePositivePrefix,
    normal_engine_positive_prefix,
)
from games.re2.room_data import decode_room
from games.re2.scenario_entry_scope import (
    _ScopePolicy,
    _source_scope_facts,
    _SourceScopeFacts,
    scenario_entry_scope,
    scenario_guard_scope,
)
from games.re2.scenario_selection import (
    ScenarioSelectionFailure,
    bind_scenario_context,
    scenario_source_write_witnesses,
)
from games.re2.script_dispatch_items import script_item_dispatch
from games.re2.source_task_control import TaskControlSupport
from games.re2.startup_declarations import (
    BoundStartupDeclarations,
    bind_startup_declaration_resources,
)
from games.re2.structured_control import (
    ControlFrameFailure,
    ControlFrames,
    structured_control,
)


@pytest.fixture(scope="module")
def target(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    prefix = normal_engine_positive_prefix(sources["01-04"], rooms["01-04"], p, bound)
    assert type(prefix) is VerifiedNormalEnginePositivePrefix
    assert type(prefix.entry_domain) is _PositiveEntryDomain
    return prefix


def test_actual_factory_query_keeps_both_historical_arms_and_independent_item_unknown(
    owned, target
):
    p, _, _, _, sources, bound, entry, rooms = owned
    visits, branch_results = set(), []

    def trace(frame, event, result):
        values = frame.f_locals
        if frame.f_code.co_name == "prefix" and event == "call":
            visits.add((values["key"], values["position"]))
        if (
            frame.f_code.co_name == "branch"
            and event == "return"
            and values["row"]["offset"] == 6714
        ):
            branch_results.append(result)
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        result = known_declared_items_from_prefix(
            sources["01-04"], rooms["01-04"], p, entry, script_item_dispatch(p), target
        )
    finally:
        sys.settrace(previous)
    assert type(result) is KnownDeclaredItems
    assert [
        (i.global_id, i.creator_offsets, i.callback_offsets, i.delivery_offsets)
        for i in result.puzzle_items
    ] == [(3, (6732,), (6776,), (7956,))]
    assert [i.global_id for i in result.direct_pickups] == [46]
    assert {at for paths in branch_results for at, _ in paths} == {6722, 6732}
    assert {("17:0", at) for at in (6726, 6732, 6776, 6836)} <= visits
    assert ("17:6", 7830) not in visits
    assert target.protected_programs == frozenset(rooms["01-04"]["programs"])
    assert len(target.protected_programs) == 27 and len(target.entry_locations) == 21
    assert not any(key == "17:24" for key, _ in target.entry_locations)
    facts = target.entry_domain.facts
    assert {cell % 0x174 for _, _, cell, _ in facts.if_stores if cell >= 0x4C0} == {
        0x64,
        0x68,
    }
    assert len([v for v in facts.if_stores if v[2] >= 0x4C0]) == 5
    assert {cell for _, _, cell in facts.break_reads} == {0x60}
    assert len(facts.auxiliary_break_reads) == 126
    assert not {cell for *_, cell in facts.auxiliary_break_reads} & {0x64, 0x68}
    context = bind_scenario_context(p, bound.declarations)
    assert (
        scenario_entry_scope(sources["01-04"], rooms["01-04"], p, context)
        is ScenarioSelectionFailure.EntryScope
    )
    assert (
        scenario_guard_scope(
            sources["01-04"], rooms["01-04"], p, context, TaskControlSupport.Unaudited
        )
        is ScenarioSelectionFailure.EntryScope
    )
    # The prior positive path still rejects this source without the separate
    # entry authority. Neither old scope nor the new capability proves absence.
    assert isinstance(
        _source_scope_facts(
            sources["01-04"],
            rooms["01-04"],
            p,
            context,
            _ScopePolicy.TrustedPositivePrefix,
            TaskControlSupport.Unaudited,
        ),
        ScenarioSelectionFailure,
    )
    assert not isinstance(target.entry_domain, _SourceScopeFacts)


@pytest.fixture
def source_roles(owned):
    p, config, executable, resources, sources, _, _, rooms = owned

    def compile_changes(changes):
        data = bytearray(sources["01-04"])
        for at, value in changes.items():
            data[at] = value
        data = bytes(data)
        room = decode_room(
            data,
            rooms["01-04"]["source"],
            frozenset((f["bank"], f["bit"]) for f in p["presence_condition_flags"]),
            presence_counter_indices(p),
            presence_flag_write_proof(p)[0],
        )
        room.update(id="01-04", stage=1, room=4)
        # Mutations test generic source roles only. The real complete binder
        # rejects every changed source; no private receipt gains production rights.
        binding = bind_startup_declaration_resources(
            config, executable, resources, sources | {"01-04": data}
        )
        assert (type(binding) is BoundStartupDeclarations) == (data == sources["01-04"])
        return (
            data,
            room,
            _source_entry_roles(
                data, room["programs"], scenario_source_write_witnesses(data, room, p)
            ),
        )

    return compile_changes


@pytest.mark.parametrize("at,value", [(6729, 24), (6793, 24), (6893, 24)])
def test_real_birth_callback_and_gosub_restore_attachment_effect_obligation(
    owned, source_roles, at, value
):
    _, room, result = source_roles({at: value})
    assert type(result) is _SourceEntryRoles
    assert ("17:24", room["programs"]["17:24"]["entry"]) in result.entry_locations
    # It is still an unsafe attachment, not a newly admitted native role.
    assert any(
        row["offset"] == 9380 and row["opcode"] == 0x2D
        for row in room["programs"]["17:24"]["commands"]
    )


@pytest.mark.parametrize(
    "at,value",
    [
        (7957, 6),
        (8063, 0),
        (8063, 1),
        (8063, 10),
        (8063, 255),
        (7483, 0),
        (7483, 1),
        (7483, 10),
        (6893, 10),
        (8229, 0),
        (8230, 0),
        (8984, 148),
    ],
)
def test_entry_changing_source_mutations_reject(source_roles, at, value):
    _, _, result = source_roles({at: value})
    assert isinstance(result, PositiveEntryFailure)


@pytest.mark.parametrize("selector", range(2, 10))
def test_explicit_ordinary_birth_and_kill_selectors_remain_bounded(
    source_roles, selector
):
    _, _, result = source_roles({7483: selector, 8063: selector})
    assert type(result) is _SourceEntryRoles


@pytest.mark.parametrize(
    "at,offset",
    [
        (8982, 8986),
        (9052, 9056),
        (9096, 9104),
        (9100, 9104),
        (9166, 9170),
        (9236, 9240),
        (9280, 9288),
        (9284, 9288),
    ],
)
def test_each_numeric_copy_boundary_and_role(source_roles, at, offset):
    data, room, baseline = source_roles({})
    assert type(baseline) is _SourceEntryRoles
    ranges = [
        span
        for span in _numeric_copy_ranges(data, room["programs"])
        if offset <= span[0] < offset + 22
    ]
    for start, end in ranges:
        for target in (start, end - 2):
            relative = target - at - 4
            if 0 <= relative <= 255:
                _, _, result = source_roles({at + 2: relative})
                assert type(result) is _SourceEntryRoles
        for target in (start - 1, end - 1):
            relative = target - at - 4
            if 0 <= relative <= 255:
                _, _, result = source_roles({at + 2: relative})
                assert isinstance(result, PositiveEntryFailure)
    if data[offset] == 0x36:
        _, _, result = source_roles({offset + 4: 1})
        assert result is PositiveEntryFailure.SourceWrite


@pytest.mark.parametrize("count", [0, 1, 0x7FFF, 0x8000, 0xFFFF])
def test_dynamic_for_count_extremes_preserve_finite_field_roles(source_roles, count):
    _, _, baseline = source_roles({})
    _, _, result = source_roles(
        {8990: count & 255, 8991: count >> 8, 9174: count & 255, 9175: count >> 8}
    )
    assert result == baseline


@pytest.mark.parametrize(
    "field,value",
    [
        ("entry_locations", frozenset()),
        ("gotos", frozenset()),
        ("if_stores", ()),
        ("break_reads", ()),
        ("auxiliary_break_reads", ()),
        ("numeric_ranges", ()),
        ("native_roles", ()),
        ("native_entries", ()),
    ],
)
def test_sealed_capability_recomputes_every_derived_field(target, field, value):
    with pytest.raises(AssertionError):
        replace(
            target.entry_domain,
            facts=replace(target.entry_domain.facts, **{field: value}),
        )


@pytest.mark.parametrize(
    "fault",
    [
        "bytes",
        "profile",
        "room",
        "mutable",
        "corpus",
        "native",
        "subtype",
        "exact-type",
    ],
)
def test_capability_rejects_source_profile_corpus_and_type_substitution(target, fault):
    domain = target.entry_domain
    kwargs = {}
    if fault == "bytes":
        kwargs["source_data"] = domain.source_data[:-1] + b"x"
    elif fault == "mutable":
        kwargs["source_data"] = bytearray(domain.source_data)
    elif fault in ("profile", "room"):
        key = f"{fault}_json"
        value = json.loads(getattr(domain, key))
        if fault == "profile":
            del value["positive_prefix_policy"]
        else:
            value["programs"]["17:0"]["entry"] += 2
        kwargs[key] = json.dumps(value)
    elif fault == "corpus":
        corpus = domain.bound.entry_resources.corpus
        script = corpus.scripts[0]
        altered = replace(
            script,
            programs_json="{}",
            _derivation=replace(script._derivation, programs_json="{}"),
        )
        scripts = (altered, *corpus.scripts[1:])
        changed = replace(
            corpus,
            scripts=scripts,
            _derivation=replace(corpus._derivation, scripts=scripts),
        )
        kwargs["bound"] = replace(
            domain.bound,
            entry_resources=replace(domain.bound.entry_resources, corpus=changed),
        )
    elif fault == "native":
        kwargs["bound"] = replace(
            domain.bound,
            entry_resources=replace(
                domain.bound.entry_resources, executable=b"changed"
            ),
        )
    elif fault == "subtype":

        class Facts(type(domain.facts)):
            pass

        kwargs["facts"] = Facts(**vars(domain.facts))
    else:
        row = domain.facts.if_stores[0]
        kwargs["facts"] = replace(
            domain.facts,
            if_stores=((row[0], row[1], True, row[3]), *domain.facts.if_stores[1:]),
        )
    with pytest.raises(AssertionError):
        replace(domain, **kwargs)


def test_prefix_cannot_swap_entry_domain_for_all_canonical_locations(target):
    from games.re2.scenario_entry_scope import _SourceEffects

    with pytest.raises(AssertionError):
        replace(
            target,
            entry_domain=_SourceEffects.Existing,
            _derivation=replace(
                target._derivation, entry_domain=_SourceEffects.Existing
            ),
        )
    with pytest.raises(AssertionError):
        replace(
            target,
            entry_locations=frozenset(
                (k, p["entry"])
                for k, p in json.loads(target.room_json)["programs"].items()
            ),
            _derivation=replace(
                target._derivation,
                entry_locations=frozenset(
                    (k, p["entry"])
                    for k, p in json.loads(target.room_json)["programs"].items()
                ),
            ),
        )


def test_goto_cannot_accumulate_unclosed_loop_or_if_frames(owned):
    _, _, _, _, sources, _, _, rooms = owned
    data = sources["01-04"]
    program = copy.deepcopy(rooms["01-04"]["programs"]["17:20"])
    # Redirecting a loop tail to the polling Goto abandons its active loop.
    tail = next(r for r in program["commands"] if r["opcode"] == 0x0E)
    tail.update(
        opcode=0x17, target=program["entry"], next=tail["offset"] + 6, kind="goto"
    )
    changed = bytearray(data)
    changed[tail["offset"] : tail["next"]] = b"\x17\xff\xff\0\0\0"
    assert (
        structured_control(bytes(changed), program, ControlFrames.FreshPositive)
        is ControlFrameFailure.Unsupported
    )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-17"], indirect=True)
def test_generated_target_rewinds_without_resolving_item_zero(snapshot):
    from games.game_profile import RoomId
    from games.re2.live_tracking import poll_re2
    from tracker.exploration_state import Tracker
    from tracker.polling import PollStatus

    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(1, 4))
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    states = []
    for acquired in (False, True, False):
        at = bank + 3 // 32 * 4
        value = int.from_bytes(read(at, 4).data, "little")
        mask = 0x80000000 >> (3 % 32)
        put(at, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["01-04"]
        items = {
            definition["global_id"]: state
            for definition, state in zip(
                profile.rooms["01-04"]["items"], record.items, strict=True
            )
        }
        assert items[3].state == ("taken" if acquired else "uncollected")
        assert items[3].quantity == 15 and items[0].state == "unknown"
        fresh = Tracker()
        fresh.mark_current(RoomId(1, 4))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh == tracker
        states.append(copy.deepcopy(record))
    assert states[0] == states[2]


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["01-03"], indirect=True)
@pytest.mark.parametrize("sat", [0, 0x31])
def test_positive_policy_keeps_real_scenario_creator_contradictions_atomic(
    snapshot, sat
):
    from games.re2.live_tracking import poll_re2
    from tracker.exploration_state import Tracker
    from tracker.polling import PollStatus

    profile, _, put, read = snapshot
    source = profile.rooms["01-03"]
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    definition = next(
        row
        for row in source["items"]
        if row["global_id"] in source["scenario_absent_item_ids"]
    )
    pointer = 0x80100000 + definition["offset"] + 2
    put(pointer + 1, sat, 1)
    put(registry + definition["slot"] * 4, pointer, 4)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Pickup disagrees with fixed scenario proof"
    assert tracker == before


def test_native_birth_orders_publication_before_fresh_installation(owned):
    from games.re2.native_control import native_bytes, native_nonyielding

    _, _, executable, _, _, _, _, _ = owned
    assert (
        native_bytes(executable, 0x800538BC, 16).hex()
        == "040042241c0082ac4e4c010c21206000"
    )
    assert native_nonyielding(executable, 0x800538A4, {})


@pytest.mark.parametrize("nested", [False, True])
def test_rooftop_style_consuming_receiver_is_derived_and_rejected(owned, nested):
    import struct

    from test_re2_initializer_control import switch
    from test_re2_startup_declarations import END, described

    p = owned[0]
    prefix = b"\x06\0\x08\0\x23\0\x1a\0\0\0\x08\0"
    writer = prefix + b"\x17\xff\xff\0" + struct.pack("<h", -len(prefix))
    receiver = switch(switch(b"\x02") if nested else b"\x02") + END
    data, room, _ = described(
        END, (b"\x04\xff\x18\x02\x04\xff\x18\x03" + END, END, writer, receiver)
    )
    result = _source_entry_roles(
        data, room["programs"], scenario_source_write_witnesses(data, room, p)
    )
    if nested:
        assert result is PositiveEntryFailure.ForeignConsumer
    else:
        assert type(result) is _SourceEntryRoles
        assert result.foreign_fields == frozenset({0x64})
        assert {cell for _, _, cell in result.break_reads} == {0x60}


def test_escaped_writer_rejects_unqualified_call_return_pointer(owned):
    import struct

    from test_re2_startup_declarations import END, described

    p = owned[0]
    prefix = b"\x06\0\x08\0\x23\0\x1a\0\0\0\x08\0\x18\x03"
    writer = prefix + b"\x17\xff\xff\0" + struct.pack("<h", -len(prefix))
    data, room, _ = described(END, (b"\x04\xff\x18\x02" + END, END, writer, END))
    result = _source_entry_roles(
        data, room["programs"], scenario_source_write_witnesses(data, room, p)
    )
    assert result is PositiveEntryFailure.Control


@pytest.mark.parametrize("target", [9358, 9359, 9360, 9361, 9376, 9380, 9383])
def test_numeric_copy_cannot_modify_unentered_creator_or_attachment(
    source_roles, target
):
    # This Copy can reach the excluded procedure, whose complete source still
    # belongs to the capability's protected programs.
    _, _, result = source_roles({9286: target - 9284 - 4})
    assert result is PositiveEntryFailure.SourceWrite


def test_existing_registration_retains_exact_domain_and_private_prefix_facts(owned):
    from games.re2.known_puzzle_items import _DeclaredPrefixFacts, _known_declared_items
    from games.re2.persistent_registration import (
        RegistrationFailure,
        VerifiedPersistentRegistration,
        persistent_registration,
    )
    from games.re2.scenario_selection import (
        ScenarioSelectionSupport,
        ScopedScenarioItems,
        scoped_scenario_items,
    )
    from games.re2.source_task_control import source_task_control_scope

    p, _, _, _, sources, bound, entry, rooms = owned
    dispatch = script_item_dispatch(p)
    for key in ("00-09", "01-04", "01-1b"):
        data, room = sources[key], rooms[key]
        prefix = normal_engine_positive_prefix(data, room, p, bound)
        result = known_declared_items_from_prefix(
            data, room, p, entry, dispatch, prefix
        )
        assert type(result) is KnownDeclaredItems
        facts = _known_declared_items(
            data,
            room,
            p,
            entry,
            dispatch,
            bound.declarations,
            prefix.context,
            ScenarioSelectionSupport.Unaudited,
            prefix,
        )
        assert type(facts) is _DeclaredPrefixFacts and facts.items == result
        registration = persistent_registration(data, room, p, entry, dispatch, prefix)
        if key == "01-04":
            assert registration is RegistrationFailure.Kind
            with pytest.raises(AssertionError):
                scoped_scenario_items(data, room, p, prefix.context, prefix)
            continue
        assert type(registration) is VerifiedPersistentRegistration
        if key == "00-09":
            guard = scenario_guard_scope(
                data,
                room,
                p,
                prefix.context,
                source_task_control_scope(
                    data, room, p, prefix.context, bound.ordinary_ingress
                ),
            )
            assert guard.entry_locations == prefix.entry_locations
            assert guard.protected_programs == prefix.protected_programs
            assert scoped_scenario_items(
                data, room, p, prefix.context, guard, registration=registration
            ) == ScopedScenarioItems((146, 205), ())
        else:
            # This generic secondary consequence has all seven canonical
            # entries. It does not justify a subset rule for absence callers.
            assert prefix.entry_locations == frozenset(
                (k, v["entry"]) for k, v in room["programs"].items()
            )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["01-04"], indirect=True)
def test_entry_domain_departure_reentry_restart_and_earlier_snapshot(
    snapshot, tmp_path
):
    from types import SimpleNamespace

    import test_re2_tracking

    from games.re2.live_tracking import poll_re2
    from tracker.exploration_state import RoomCompletion, Tracker
    from tracker.polling import PollStatus
    from tracker.visit_history import HistoryIdentity, VisitHistory

    current_profile, current_ram, _, _ = snapshot
    other_profile, other_ram, _, _ = test_re2_tracking.snapshot.__wrapped__(
        SimpleNamespace(param="00-17"), current_profile
    )
    profile = replace(
        current_profile,
        rooms=current_profile.rooms | {"00-17": other_profile.rooms["00-17"]},
    )
    ram = bytearray(current_ram)
    from test_live_items import RamReader

    read = RamReader(ram).read_memory
    regions = {
        f"{area['id']}:{room['id']}": set(room["room_ids"])
        for area in profile.map_layout.document["areas"]
        for room in area["rooms"]
    }
    identity = HistoryIdentity(
        profile.profile_id, profile.runtime_signature.concatenated_sha256, "leon-a"
    )
    history_path = tmp_path / "isolated-positive-entry-visits.json"
    tracker = Tracker()
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    offset = bank & 0x1FFFFF
    mask = 0x80000000 >> 3
    earlier = None
    for current, acquired in (
        (True, False),
        (False, False),
        (True, False),
        (False, True),
        (True, True),
        (False, False),
    ):
        ram[:] = current_ram if current else other_ram
        value = int.from_bytes(ram[offset : offset + 4], "little")
        ram[offset : offset + 4] = (
            value | mask if acquired else value & ~mask
        ).to_bytes(4, "little")
        if current and acquired:
            # A collected pickup no longer has an active live descriptor;
            # leaving it enabled deliberately triggers the reader's torn-state check.
            registry = (
                int(profile.runtime_layout["aot_table_address_ps1"], 0) & 0x1FFFFF
            )
            ram[registry + 4 * 4 : registry + 5 * 4] = bytes(4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        if not current and not acquired and earlier is None:
            earlier = bytes(ram)
        target = tracker.rooms["01-04"]
        indexed = {
            definition["global_id"]: item
            for definition, item in zip(
                profile.rooms["01-04"]["items"], target.items, strict=True
            )
        }
        assert indexed[3].state == (
            "taken" if acquired else "available" if current else "uncollected"
        )
        assert indexed[3].quantity == 15 and indexed[0].state == "unknown"
        # Independent pickup46 remains uncollected throughout these controls.
        assert target.completion is RoomCompletion.Incomplete
        assert set(tracker.rooms) == (
            {"01-04"} if current and earlier is None else {"01-04", "00-17"}
        )
        history = VisitHistory(history_path, identity, regions, False)
        history.save(tracker)
        history.close()
        history = VisitHistory(history_path, identity, regions, False)
        restarted = history.restore()
        history.close()
        assert not restarted.doors and all(
            not record.items for record in restarted.rooms.values()
        )
        assert poll_re2(profile, restarted, read).status is PollStatus.Display
        assert restarted == tracker
    # Replacing the complete synthetic memory image models an earlier load;
    # this is not execution of DuckStation's savestate restoration machinery.
    before_restore = copy.deepcopy(tracker)
    ram[:] = earlier
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker == before_restore


def test_complete_owned_corpus_preserves_prior_public_outputs(owned):
    """Full source census against 83bd4c7, with no sampled/retained task state."""
    import dataclasses
    import hashlib
    from enum import Enum
    from pathlib import Path

    from games.re2.known_puzzle_items import known_declared_items
    from games.re2.persistent_registration import (
        VerifiedPersistentRegistration,
        persistent_registration,
    )
    from games.re2.scenario_selection import VerifiedScenarioEntryScope

    def encode(value):
        if isinstance(value, Enum):
            return {"failure": type(value).__name__ + "." + value.name}
        if dataclasses.is_dataclass(value):
            return encode(dataclasses.asdict(value))
        if isinstance(value, dict):
            return {str(k): encode(v) for k, v in value.items()}
        if isinstance(value, (set, frozenset)):
            return sorted(encode(v) for v in value)
        if isinstance(value, (tuple, list)):
            return [encode(v) for v in value]
        return value

    baseline = json.loads(
        (
            Path(__file__).parent / "fixtures/re2/positive-entry-baseline.json"
        ).read_text()
    )
    p, _, _, _, sources, bound, entry, rooms = owned
    context = bind_scenario_context(p, bound.declarations)
    dispatch = script_item_dispatch(p)
    results = {field: {} for field in baseline["output_sha256"]}
    for key, room in rooms.items():
        data = sources[key]
        strict = scenario_entry_scope(data, room, p, context)
        guard = scenario_guard_scope(
            data, room, p, context, TaskControlSupport.Unaudited
        )
        for field, scope in (("strict", strict), ("guard", guard)):
            results[field][key] = (
                encode(scope)
                if isinstance(scope, Enum)
                else {
                    "entries": encode(scope.entry_locations),
                    "programs": encode(scope.protected_programs),
                }
            )
        results["default"][key] = encode(
            known_declared_items(data, room, p, entry, dispatch, bound.declarations)
        )
        results["strict_query"][key] = (
            encode(
                known_declared_items(
                    data,
                    room,
                    p,
                    entry,
                    dispatch,
                    bound.declarations,
                    scenario_context=context,
                    scenario_entries=strict,
                )
            )
            if isinstance(strict, VerifiedScenarioEntryScope)
            else None
        )
        if key not in baseline["original_positive_sources"]:
            continue
        prefix = normal_engine_positive_prefix(data, room, p, bound)
        assert type(prefix) is VerifiedNormalEnginePositivePrefix
        results["positive_query"][key] = encode(
            known_declared_items_from_prefix(data, room, p, entry, dispatch, prefix)
        )
        registration = persistent_registration(data, room, p, entry, dispatch, prefix)
        results["registration"][key] = (
            {
                "registered_slots": encode(registration.registered_slots),
                "dispatches": encode(registration.dispatches),
                "kinds": encode(registration.source_kinds),
            }
            if type(registration) is VerifiedPersistentRegistration
            else encode(registration)
        )
    assert len(sources) == len(rooms) == 125
    for field, expected in baseline["output_sha256"].items():
        actual = hashlib.sha256(
            json.dumps(results[field], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        assert actual == expected, field
