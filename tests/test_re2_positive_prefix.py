"""RE2-STARTUP-007: separate authority, real prefix paths and fresh publication."""

import copy
import hashlib
import json
import os
import re
import struct
import sys
from dataclasses import replace
from pathlib import Path

import pytest
from test_re2_metadata import ROOT
from test_re2_tracking import (
    profile as profile,
)  # noqa: PLC0414
from test_re2_tracking import (
    snapshot as snapshot,
)

from games.game_profile import RoomId
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.known_puzzle_items import (
    KnownDeclaredItemFailure,
    KnownDeclaredItems,
    known_declared_items,
    known_declared_items_from_prefix,
)
from games.re2.live_tracking import poll_re2
from games.re2.positive_prefix import (
    PositivePrefixFailure,
    VerifiedNormalEnginePositivePrefix,
    normal_engine_positive_prefix,
)
from games.re2.room_data import decode_room
from games.re2.room_entry_contract import bind_room_entry_contract, room_entry_contract
from games.re2.scenario_entry_scope import scenario_entry_scope, scenario_guard_scope
from games.re2.scenario_selection import (
    VerifiedScenarioEntryScope,
    bind_scenario_context,
)
from games.re2.script_control_limits import programs_digest
from games.re2.script_dispatch_items import script_item_dispatch
from games.re2.source_task_control import TaskControlSupport
from games.re2.startup_declarations import (
    BoundStartupDeclarations,
    bind_startup_declaration_resources,
    startup_declaration_audit,
    startup_declarations,
)
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.fixture(scope="module")
def owned():
    cue_path = os.environ.get("RE_MAP_RE2_OWNED_CUE")
    if cue_path is None:
        pytest.skip("Set RE_MAP_RE2_OWNED_CUE for the owned-disc factory regressions")
    from build_item_table import _read_file
    from extract_psx_file import _find
    from list_psx_files import _sector_data

    profile = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    config = startup_declaration_audit(profile)
    cue = Path(cue_path)
    match = re.search(r'FILE\s+"([^"]+)"', cue.read_text())
    assert match is not None
    with (cue.parent / match[1]).open("rb") as stream:
        pvd = _sector_data(stream, 16)
        root, size = (
            struct.unpack_from("<I", pvd, 158)[0],
            struct.unpack_from("<I", pvd, 166)[0],
        )

        def read(path):
            return _read_file(stream, *_find(stream, root, size, path))

        executable = read("SLUS_007.48")
        resources = {r.path: read(r.path) for r in config.resources}
        sources = {r.room_id: read(r.path) for r in config.selection.sources}
        entry_config = room_entry_contract(profile)
        entry = bind_room_entry_contract(
            entry_config,
            executable,
            {r.stage: read(r.resource.path) for r in entry_config.stage_entries},
            read(entry_config.actor_archive_path),
            {r.model: read(r.path) for r in entry_config.doors},
        )
    bound = bind_startup_declaration_resources(config, executable, resources, sources)
    assert type(bound) is BoundStartupDeclarations
    rooms = {}
    for spec in config.selection.sources:
        room = decode_room(
            sources[spec.room_id],
            spec.path,
            frozenset(
                (r["bank"], r["bit"]) for r in profile["presence_condition_flags"]
            ),
            presence_counter_indices(profile),
            presence_flag_write_proof(profile)[0],
        )
        stage, number = (int(part, 16) for part in spec.room_id.split("-"))
        room.update(id=spec.room_id, stage=stage, room=number)
        rooms[spec.room_id] = room
    return profile, config, executable, resources, sources, bound, entry, rooms


@pytest.mark.parametrize(
    "key,gid,field",
    [
        ("00-03", 211, "direct_pickups"),
        ("00-09", 13, "puzzle_items"),
        ("01-11", 221, "direct_pickups"),
    ],
)
def test_owned_factory_establishes_required_targets_without_promoting_old_scopes(
    owned, key, gid, field
):
    profile, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources[key], rooms[key]
    prefix = normal_engine_positive_prefix(data, room, profile, bound)
    assert type(prefix) is VerifiedNormalEnginePositivePrefix
    assert not isinstance(prefix, VerifiedScenarioEntryScope)
    result = known_declared_items_from_prefix(
        data, room, profile, entry, script_item_dispatch(profile), prefix
    )
    assert type(result) is KnownDeclaredItems
    target = next(item for item in getattr(result, field) if item.global_id == gid)
    assert target.context_conditions == [
        {
            "kind": "conditions",
            "any_of": [
                [
                    {"bank": 1, "bit": 0, "expected": 0},
                    {"bank": 1, "bit": 1, "expected": 0},
                    {"bank": 1, "bit": 6, "expected": 0},
                    {"bank": 0, "bit": 25, "expected": 1},
                ]
            ],
        }
    ]
    assert not hasattr(target, "amount")
    if key == "00-09":
        assert (
            target.creator_offsets,
            target.callback_offsets,
            target.delivery_offsets,
        ) == ((9024,), (9004,), (11530,))
        assert not any(item.global_id == 205 for item in result.puzzle_items)
    if key == "00-03":
        assert prefix.resources.selection.models_for(key) == (10, 12)
        assert startup_declarations(data, room, profile, bound.declarations) == ()
    assert bound.declarations.selection.stages == frozenset({0})


def test_guard_authority_rejected_by_both_positive_entry_points(owned):
    p, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-09"], rooms["00-09"]
    context = bind_scenario_context(p, bound.declarations)
    guard = scenario_guard_scope(data, room, p, context, TaskControlSupport.Unaudited)
    with pytest.raises(AssertionError):
        known_declared_items_from_prefix(
            data, room, p, entry, script_item_dispatch(p), guard
        )
    with pytest.raises(AssertionError):
        known_declared_items(
            data,
            room,
            p,
            entry,
            script_item_dispatch(p),
            bound.declarations,
            scenario_context=context,
            scenario_entries=guard,
        )
    strict = scenario_entry_scope(data, room, p, context)
    if isinstance(strict, VerifiedScenarioEntryScope):
        old = known_declared_items(
            data,
            room,
            p,
            entry,
            script_item_dispatch(p),
            bound.declarations,
            scenario_context=context,
            scenario_entries=strict,
        )
        assert old is KnownDeclaredItemFailure.Prefix


@pytest.mark.parametrize(
    "fault",
    [
        "source",
        "creator",
        "callback",
        "delivery",
        "guard",
        "root",
        "item-field",
        "list",
        "profile",
        "policy",
    ],
)
def test_actual_authority_rejects_changed_bytes_and_derived_metadata(owned, fault):
    p, _, _, _, sources, bound, entry, rooms = owned
    data, room, profile = (
        sources["00-09"],
        copy.deepcopy(rooms["00-09"]),
        copy.deepcopy(p),
    )
    prefix = normal_engine_positive_prefix(data, room, profile, bound)
    if fault in ("source", "creator", "callback", "delivery", "guard"):
        at = {
            "source": 0,
            "creator": 9024 + 18,
            "callback": 9004 + 17,
            "delivery": 11530 + 1,
            "guard": 8632 + 2,
        }[fault]
        changed = bytearray(data)
        changed[at] ^= 1
        data = bytes(changed)
    elif fault == "root":
        room["programs"]["16:0"]["entry"] += 1
    elif fault == "item-field":
        room["items"][0]["global_id"] ^= 1
    elif fault == "list":
        room["candidate_list_complete"] = False
    elif fault == "profile":
        profile["runtime_layout"]["system_mode_value"] = 0
    else:
        del profile["positive_prefix_policy"]
    assert isinstance(
        normal_engine_positive_prefix(data, room, profile, bound), PositivePrefixFailure
    )
    assert (
        known_declared_items_from_prefix(
            data, room, profile, entry, script_item_dispatch(p), prefix
        )
        is KnownDeclaredItemFailure.InputBinding
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_data", bytearray(b"changed")),
        ("source_sha256", "0" * 64),
        ("programs_sha256", "0" * 64),
        ("roots", (("16:0", 0), ("17:0", 0))),
        ("call_frames", 5),
        ("historical_flags", ((0, 25, 0),)),
        ("protected_programs", frozenset({"16:0"})),
        ("entry_locations", frozenset({("16:0", 0)})),
        ("profile_json", "{}"),
        ("room_json", "{}"),
    ],
)
def test_immutable_derivation_rejects_field_substitution(owned, field, value):
    p, _, _, _, sources, bound, _, rooms = owned
    prefix = normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], p, bound)
    with pytest.raises(AssertionError):
        replace(prefix, **{field: value})
    with pytest.raises((AssertionError, ValueError)):
        replace(
            prefix,
            **{field: value},
            _derivation=replace(prefix._derivation, **{field: value}),
        )


@pytest.mark.parametrize("fault", ["models", "incoming", "routes", "auxiliary"])
def test_positive_authority_rejects_consistently_replaced_nested_binding(owned, fault):
    p, _, _, _, sources, bound, _, rooms = owned
    resources = bound.entry_resources
    selection, corpus, ingress = (
        resources.selection,
        resources.corpus,
        resources.ordinary_ingress,
    )
    if fault == "models":
        changes = {
            "covered_models": frozenset(range(256)),
            "auxiliary_programs": tuple((i, "0" * 64) for i in range(256)),
        }
        ingress = replace(
            ingress, **changes, _derivation=replace(ingress._derivation, **changes)
        )
    elif fault == "incoming":
        selection = replace(
            selection,
            incoming_models=tuple(
                (key, (0,)) if key == "00-09" else (key, models)
                for key, models in selection.incoming_models
            ),
        )
    elif fault == "routes":
        routes = tuple((key, (), ()) for key, _, _ in corpus.route_witnesses)
        corpus = replace(
            corpus,
            route_witnesses=routes,
            _derivation=replace(corpus._derivation, route_witnesses=routes),
        )
    else:
        script = corpus.scripts[0]
        changes = {"programs_json": "{}"}
        script = replace(
            script, **changes, _derivation=replace(script._derivation, **changes)
        )
        scripts = (script, *corpus.scripts[1:])
        corpus = replace(
            corpus,
            scripts=scripts,
            _derivation=replace(corpus._derivation, scripts=scripts),
        )
    corpus = replace(
        corpus,
        selection=selection,
        _derivation=replace(corpus._derivation, selection=selection),
    )
    ingress = replace(
        ingress,
        selection=selection,
        _derivation=replace(ingress._derivation, selection=selection),
    )
    resources = replace(
        resources, selection=selection, corpus=corpus, ordinary_ingress=ingress
    )
    changed = replace(
        bound,
        entry_resources=resources,
        ordinary_ingress=ingress,
        declarations=replace(bound.declarations, selection=selection),
    )
    assert (
        normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], p, changed)
        is PositivePrefixFailure.Binding
    )
    prefix = normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], p, bound)
    with pytest.raises(AssertionError):
        replace(
            prefix,
            resources=resources,
            _derivation=replace(prefix._derivation, resources=resources),
        )


@pytest.mark.parametrize("mask,value", [(0xC2000001, 1), (0xC6000000, 0)])
def test_positive_policy_cannot_promote_extra_profile_bits_to_historical_facts(
    owned, mask, value
):
    p, _, _, _, sources, bound, _, rooms = owned
    changed = copy.deepcopy(p)
    changed["runtime_layout"].update(scenario_mask=mask, scenario_value=value)
    assert (
        normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], changed, bound)
        is PositivePrefixFailure.Binding
    )


@pytest.mark.parametrize("bank", [0, 3, 4])
def test_positive_authority_binds_logical_flags_to_native_addresses(owned, bank):
    p, _, _, _, sources, bound, _, rooms = owned
    changed = copy.deepcopy(p)
    row = next(row for row in changed["flag_banks"] if row["bank"] == bank)
    row["address_ps1"] = f"0x{int(row['address_ps1'], 0) + 4:08X}"
    if bank == 0:
        changed["runtime_layout"]["system_flags_address_ps1"] = row["address_ps1"]
    assert (
        normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], changed, bound)
        is PositivePrefixFailure.Binding
    )
    prefix = normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], p, bound)
    profile_json = json.dumps(changed, sort_keys=True, separators=(",", ":"))
    with pytest.raises((AssertionError, ValueError)):
        replace(
            prefix,
            profile_json=profile_json,
            _derivation=replace(prefix._derivation, profile_json=profile_json),
        )


def test_positive_authority_rejects_substituted_native_declaration_fields(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    changed = replace(
        bound,
        declarations=replace(
            bound.declarations, actor_parts=bound.declarations.actor_parts + 1
        ),
    )
    assert (
        normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], p, changed)
        is PositivePrefixFailure.Binding
    )


@pytest.mark.parametrize(
    "fault", ["exe", "resource", "resource-missing", "source", "source-missing"]
)
def test_complete_owned_binder_withholds_changed_or_missing_inputs(owned, fault):
    _, config, exe, resources, sources, _, _, _ = owned
    resources, sources = resources.copy(), sources.copy()
    if fault == "exe":
        exe = exe[:-1] + bytes((exe[-1] ^ 1,))
    elif fault.startswith("resource"):
        key = next(iter(resources))
        if fault.endswith("missing"):
            del resources[key]
        else:
            resources[key] = resources[key][:-1] + bytes((resources[key][-1] ^ 1,))
    else:
        if fault.endswith("missing"):
            del sources["00-09"]
        else:
            sources["00-09"] = sources["00-09"][:-1] + bytes(
                (sources["00-09"][-1] ^ 1,)
            )
    assert (
        type(bind_startup_declaration_resources(config, exe, resources, sources))
        is not BoundStartupDeclarations
    )


def test_real_prefix_visits_both_story_arms_all_switch_cases_and_native_end_frames(
    owned,
):
    p, _, _, _, sources, bound, entry, rooms = owned
    prefix = normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], p, bound)
    visits, depths = set(), []

    def trace(frame, event, _arg):
        if frame.f_code.co_name == "prefix" and event == "call":
            values = frame.f_locals
            key, at = values["key"], values["position"]
            visits.add((key, at))
            depths.append(1 + len(values["returns"]))
        return trace

    previous = sys.gettrace()
    try:
        sys.settrace(trace)
        result = known_declared_items_from_prefix(
            sources["00-09"], rooms["00-09"], p, entry, script_item_dispatch(p), prefix
        )
    finally:
        sys.settrace(previous)
    assert result.puzzle_items[0].global_id == 13
    assert max(depths) == 4
    assert any(key == "17:9" for key, _ in visits)
    assert any(key == "17:10" for key, _ in visits)
    switch = rooms["00-09"]["programs"]["17:6"]
    labels = [r for r in switch["commands"] if r["opcode"] == 0x14]
    assert len(labels) == 10
    assert all(("17:6", r["next"]) in visits for r in labels)
    assert any(
        ("17:6", r["offset"]) in visits
        for r in switch["commands"]
        if r["opcode"] == 0x16
    )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-17"], indirect=True)
def test_generated_positive_rows_rewind_independently_with_fresh_acquisition(snapshot):
    profile, _, put, read = snapshot
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    for key in ("00-03", "00-09", "01-11"):
        tracker.mark_current(RoomId(*(int(part, 16) for part in key.split("-"))))
    for taken in (False, True, False):
        for gid in (211, 13, 221):
            at, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(read(at, 4).data, "little")
            put(at, value | mask if taken else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        for key, gid in (("00-03", 211), ("00-09", 13), ("01-11", 221)):
            record = tracker.rooms[key]
            index = next(
                index
                for index, i in enumerate(profile.rooms[key]["items"])
                if i["global_id"] == gid
            )
            item = record.items[index]
            assert item.state == ("taken" if taken else "uncollected")
            if not taken:
                assert record.completion is RoomCompletion.Incomplete


@pytest.fixture
def prefix_inputs(owned):
    from games.re2.positive_prefix import _PositivePrefixDerivation
    from games.re2.startup_entry_selection import EntrySelectionSource

    p, _, _, _, sources, bound, entry, rooms = owned
    original = normal_engine_positive_prefix(sources["00-09"], rooms["00-09"], p, bound)

    def compile_source(init, main):
        from test_re2_startup_declarations import described

        data, room, _ = described(init, main)
        # Explicit source-only test receipts isolate interpreter semantics.
        # The production factory rejects this altered pinned source corpus;
        # owned factory/binder tests above exercise the mandatory real binding.
        selection = replace(
            bound.entry_resources.selection,
            sources=tuple(
                EntrySelectionSource(
                    r.room_id,
                    room["source"],
                    len(data),
                    hashlib.sha256(data).hexdigest(),
                )
                if r.room_id == room["id"]
                else r
                for r in bound.entry_resources.selection.sources
            ),
        )
        ingress = bound.ordinary_ingress
        ingress = replace(
            ingress,
            selection=selection,
            _derivation=replace(ingress._derivation, selection=selection),
        )
        corpus = bound.entry_resources.corpus
        corpus = replace(
            corpus,
            selection=selection,
            _derivation=replace(corpus._derivation, selection=selection),
        )
        resources = replace(
            bound.entry_resources,
            selection=selection,
            corpus=corpus,
            ordinary_ingress=ingress,
        )
        context = bind_scenario_context(
            p, replace(bound.declarations, selection=selection)
        )
        derivation = _PositivePrefixDerivation(
            resources,
            context,
            data,
            room["sha256"],
            programs_digest(room["programs"]),
            original.profile_json,
            json.dumps(room, sort_keys=True, separators=(",", ":")),
            frozenset(room["programs"]),
            frozenset((k, pr["entry"]) for k, pr in room["programs"].items()),
            tuple((k, room["programs"][k]["entry"]) for k in ("16:0", "17:0")),
            original.historical_flags,
            4,
        )
        # Bypass construction only in this source-interpreter unit fixture.
        # A real capability must pass the constructor's pinned corpus checks.
        prefix = object.__new__(VerifiedNormalEnginePositivePrefix)
        for field, value in (vars(derivation) | {"_derivation": derivation}).items():
            object.__setattr__(prefix, field, value)
        assert isinstance(
            normal_engine_positive_prefix(
                data,
                room,
                p,
                replace(
                    bound,
                    entry_resources=resources,
                    declarations=context.declaration_contract,
                    ordinary_ingress=ingress,
                ),
            ),
            PositivePrefixFailure,
        )
        return data, room, p, entry, script_item_dispatch(p), prefix

    return compile_source


@pytest.fixture
def source_prefix(prefix_inputs):
    return lambda init, main: known_declared_items_from_prefix(
        *prefix_inputs(init, main)
    )


def test_native_callee_end_discards_only_its_if_frame(source_prefix):
    from test_re2_known_puzzle_items import callback, conditional, delivery, item
    from test_re2_startup_declarations import END

    result = source_prefix(
        b"\x18\x03" + item() + END,
        (callback() + END, END, delivery(), conditional(4, 72, 1, END) + END),
    )
    assert isinstance(result, KnownDeclaredItems)
    assert [r.global_id for r in result.puzzle_items] == [93]


@pytest.mark.parametrize("depth", [3, 4])
def test_positive_prefix_enforces_four_total_native_frames(source_prefix, depth):
    from test_re2_known_puzzle_items import callback, delivery, item
    from test_re2_startup_declarations import END

    chain = tuple(bytes((0x18, i + 1)) + END for i in range(3, 3 + depth - 1))
    result = source_prefix(
        b"\x18\x03" + item() + END, (callback() + END, END, delivery(), *chain, END)
    )
    if depth == 3:
        assert [r.global_id for r in result.puzzle_items] == [93]
    else:
        assert result is KnownDeclaredItemFailure.Prefix


@pytest.mark.parametrize("same_target", [True, False])
def test_saved_story_paths_intersect_identities_instead_of_selecting_fresh_flags(
    source_prefix, same_target
):
    from test_re2_known_puzzle_items import callback, conditional, delivery, item
    from test_re2_startup_declarations import END

    result = source_prefix(
        END,
        (
            callback()
            + conditional(4, 72, 1, item() + END)
            + item(gid=93 if same_target else 92)
            + END,
            END,
            delivery(),
        ),
    )
    assert isinstance(result, KnownDeclaredItems)
    assert bool(result.puzzle_items) is same_target


def test_switch_no_match_cannot_borrow_a_case_declaration(source_prefix):
    from test_re2_initializer_control import switch
    from test_re2_known_puzzle_items import callback, delivery, item
    from test_re2_startup_declarations import END

    result = source_prefix(
        END,
        (
            callback() + switch(item(), item()) + END,
            END,
            delivery(),
        ),
    )
    assert isinstance(result, KnownDeclaredItems) and result.puzzle_items == ()


@pytest.mark.parametrize("alias", ["creator", "reset", "callback", "write"])
def test_new_positive_caller_retains_shared_target_alias_and_write_checks(
    source_prefix, alias
):
    from test_re2_known_puzzle_items import callback, delivery, item
    from test_re2_startup_declarations import END

    later = {
        "creator": item(gid=92),
        "reset": b"\x46\x09\x02\x31" + struct.pack("<3H", 20, 1, 92),
        "callback": callback(3),
        "write": b"\x22\x00\x19\x00",
    }[alias]
    result = source_prefix(
        item() + END, (callback() + END, later + END, delivery(), END)
    )
    assert isinstance(result, KnownDeclaredItemFailure) or result.puzzle_items == ()


def test_profile_policy_is_explicit_and_revision_bound():
    from games.re2.positive_prefix import PositivePrefixPolicy, positive_prefix_policy

    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    assert positive_prefix_policy(raw) is PositivePrefixPolicy.TrustedNormalEngine
    missing = copy.deepcopy(raw)
    del missing["positive_prefix_policy"]
    assert positive_prefix_policy(missing) is PositivePrefixPolicy.Unaudited
    wrong = copy.deepcopy(raw)
    wrong["positive_prefix_policy"]["audit"] = "another policy"
    with pytest.raises(ValueError, match="positive-prefix"):
        positive_prefix_policy(wrong)
    wrong = copy.deepcopy(raw)
    wrong["executable_identity"] = "different revision SHA256 " + "0" * 64
    with pytest.raises(ValueError, match="positive-prefix"):
        positive_prefix_policy(wrong)


def test_generation_rejects_misconfigured_positive_policy_before_opening_media(
    tmp_path,
):
    from build_re2_metadata import build

    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    raw["positive_prefix_policy"]["audit"] = "another policy"
    with pytest.raises(ValueError, match="positive-prefix"):
        build(tmp_path / "not-opened.cue", raw, {})
