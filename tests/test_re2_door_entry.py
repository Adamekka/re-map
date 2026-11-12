"""RE2-DOOR-010: the unchanged neutral entry analysis grants only six doors."""

import copy
import dataclasses
import enum
import hashlib
import json
from pathlib import Path

import pytest
from test_re2_positive_prefix import owned as owned

from games.re2.door_authority import (
    DoorAuthority,
    compile_door_access,
    compile_door_authority,
    door_access_catalog,
)
from games.re2.door_entry import (
    DoorEntryFailure,
    _DoorEntryBinding,
    _task_fields,
    _TaskFields,
    compile_door_entry_binding,
)
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    SourceEntryPolicy,
    _source_entry_roles,
    _SourceEntryRoles,
)
from games.re2.scenario_selection import (
    bind_scenario_context,
    scenario_source_write_witnesses,
)
from games.re2.structured_control import ControlFrames, structured_control


@pytest.mark.parametrize(
    "key,offsets,targets",
    [
        ("00-1b", (2282, 2314), ((0, 26, 0), (0, 3, 3))),
        ("01-04", (6366, 6398), ((1, 1, 0), (1, 5, 0))),
        ("02-08", (2450, 2482), ((1, 27, 0), (2, 0, 0))),
    ],
)
def test_owned_public_factory_admits_six_exact_door_rows(owned, key, offsets, targets):
    p, _, _, _, sources, bound, _, rooms = owned
    data, room = sources[key], rooms[key]
    authority = compile_door_authority(data, room, p, bound)
    assert type(authority) is DoorAuthority
    facts, gaps, excluded = compile_door_access(data, room, p, authority)
    assert [(f.slot, f.creator_offsets) for f in facts] == [
        (slot, (offset,)) for slot, offset in enumerate(offsets)
    ]
    assert [(f.stage, f.room, f.floor) for f in facts] == list(targets)
    assert all(
        f.activation_floor == f.lock_id == f.lock_type == 0
        and f.enabled is True
        and f.activation_mask == 49
        for f in facts
    )
    assert excluded == ()
    assert list(gaps) == (
        [
            {
                "slot": 2,
                "creator_offsets": [6430],
                "reasons": ["competing_non_door_origin"],
            }
        ]
        if key == "01-04"
        else []
    )
    assert len(door_access_catalog(data, room, p, bound)["facts"]) == 2


def test_all125_catalogs_and_unchanged_neutral_and_frame_domains(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    baseline = json.loads(
        (Path(__file__).parent / "fixtures/re2/door-entry-baseline.json").read_text()
    )

    def encode(v):
        if isinstance(v, enum.Enum):
            return {"enum": type(v).__name__, "value": v.value}
        if dataclasses.is_dataclass(v):
            return {f.name: encode(getattr(v, f.name)) for f in dataclasses.fields(v)}
        if isinstance(v, dict):
            return {str(k): encode(part) for k, part in v.items()}
        if isinstance(v, (set, frozenset)):
            return sorted(encode(part) for part in v)
        if isinstance(v, (tuple, list)):
            return [encode(part) for part in v]
        return v

    neutral, walks = {}, {}
    totals = [0, 0, 0, 0]
    for key, room in rooms.items():
        data = sources[key]
        catalog = door_access_catalog(data, room, p, bound)
        if key in ("00-1b", "01-04", "02-08"):
            old = baseline["targets"][key]
            assert old["facts"] == []
            assert (
                catalog["scenario_excluded_offsets"] == old["scenario_excluded_offsets"]
            )
            assert [f["slot"] for f in catalog["facts"]] == [0, 1]
            assert catalog["unsupported"] == (
                [
                    {
                        "slot": 2,
                        "creator_offsets": [6430],
                        "reasons": ["competing_non_door_origin"],
                    }
                ]
                if key == "01-04"
                else []
            )
        else:
            actual = {
                field: catalog[field]
                for field in ("facts", "scenario_excluded_offsets", "unsupported")
            }
            assert (
                hashlib.sha256(
                    json.dumps(actual, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
                == baseline["catalog_sha256"][key]
            ), key
        totals[0] += len(catalog["facts"])
        totals[1] += sum(len(f["creator_offsets"]) for f in catalog["facts"])
        totals[2] += len(catalog["scenario_excluded_offsets"])
        totals[3] += len(catalog["unsupported"])
        neutral[key] = encode(
            _source_entry_roles(
                data,
                room["programs"],
                scenario_source_write_witnesses(data, room, p),
                policy=SourceEntryPolicy.Existing,
            )
        )
        for pk, program in room["programs"].items():
            for role in ControlFrames:
                walks[key + "/" + pk + "/" + role.name] = encode(
                    structured_control(data, program, role)
                )
    assert len(rooms) == 125 and totals == [120, 130, 11, 159]
    assert len(walks) == baseline["walks"] == 7844
    for name, value in (("neutral", neutral), ("walks", walks)):
        assert (
            hashlib.sha256(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            == baseline[name + "_sha256"]
        )


@pytest.fixture(scope="module")
def binding(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    result = compile_door_entry_binding(sources["01-04"], rooms["01-04"], p, bound)
    assert type(result) is _DoorEntryBinding
    assert type(result.source) is _SourceEntryRoles
    assert type(result.source_fields) is _TaskFields
    return result


def test_binding_seals_actual_tasks_receivers_and_complete_auxiliary_corpus(
    owned, binding
):
    p, _, _, _, sources, bound, _, rooms = owned
    assert binding.matches(sources["01-04"], rooms["01-04"], p, bound.declarations)
    tasks = binding.source_fields
    assert {task for _, task, _ in tasks.entries} <= set(range(10))
    assert ("16:0", 0, 0) in tasks.entries
    assert ("17:0", 1, 0) in tasks.entries
    assert ("17:1", 0, 0) in tasks.entries
    assert (
        "17:24",
        rooms["01-04"]["programs"]["17:24"]["entry"],
    ) not in binding.source.entry_locations
    assert {
        cell for _, _, task, _, receiver, cell, _ in tasks.stores if task != receiver
    } == {0x64, 0x68}
    assert len(binding.auxiliary_fields) == 54
    escaped = [
        (model, row)
        for model, facts in binding.auxiliary_fields
        for row in facts.stores
        if row[2] != row[4]
    ]
    assert len(escaped) == 51
    assert all(row[2] == 10 and row[4] == 13 for _, row in escaped)
    assert sum(row[3] == 2 and row[5] == 0xA4 for _, row in escaped) == 47
    inactive = [(model, row) for model, row in escaped if row[5] == 0x84]
    assert len(inactive) == 4 and all(row[3] == 1 for _, row in inactive)
    assert all(
        all(task != 13 for _, task, _ in dict(binding.auxiliary_fields)[model].entries)
        for model, _ in inactive
    )
    assert len(binding.auxiliary_reads) == 126
    assert {cell for *_, cell in binding.auxiliary_reads} == {0x60}
    assert len(binding.native_entries) == 8
    # Static source/native evidence remains Candidate; task metadata grants no
    # item or clearance capability and contains no sampled application state.
    assert not hasattr(binding, "item_presence")


@pytest.mark.parametrize(
    "field",
    [f.name for f in dataclasses.fields(_DoorEntryBinding) if f.name != "_binding"],
)
def test_binding_cannot_be_constructed_or_replaced_even_with_receipt_mirrors(
    binding, field
):
    with pytest.raises(TypeError):
        _DoorEntryBinding(**{field: getattr(binding, field)})
    with pytest.raises(TypeError):
        dataclasses.replace(binding, **{field: getattr(binding, field)})
    forged = copy.copy(binding)
    object.__setattr__(forged, field, object())
    with pytest.raises(AssertionError):
        forged.matches(
            binding.source_data,
            json.loads(binding.room_json),
            json.loads(binding.profile_json),
            binding.bound.declarations,
        )


@pytest.mark.parametrize(
    "fault",
    [
        "native",
        "corpus",
        "auxiliary",
        "source",
        "unentered",
        "copy",
        "profile",
        "json-type",
        "policy",
        "legacy-policy",
        "ingress",
    ],
)
def test_public_factory_rejects_complete_binding_mutations_atomically(owned, fault):
    p, _, _, _, sources, bound, _, rooms = owned
    p, room = copy.deepcopy(p), copy.deepcopy(rooms["01-04"])
    data = sources["01-04"]
    if fault == "native":
        bound = dataclasses.replace(
            bound,
            entry_resources=dataclasses.replace(
                bound.entry_resources,
                executable=bound.entry_resources.executable[:-1] + b"!",
            ),
        )
    elif fault in ("corpus", "auxiliary"):
        corpus = bound.entry_resources.corpus
        script = corpus.scripts[0]
        args = (
            {"data": script.data[:-1] + b"!"}
            if fault == "corpus"
            else {"programs_json": "{}"}
        )
        script = dataclasses.replace(
            script, **args, _derivation=dataclasses.replace(script._derivation, **args)
        )
        scripts = (script, *corpus.scripts[1:])
        corpus = dataclasses.replace(
            corpus,
            scripts=scripts,
            _derivation=dataclasses.replace(corpus._derivation, scripts=scripts),
        )
        bound = dataclasses.replace(
            bound,
            entry_resources=dataclasses.replace(bound.entry_resources, corpus=corpus),
        )
    elif fault == "ingress":
        ingress = bound.ordinary_ingress
        args = {"preserved_counters": frozenset()}
        ingress = dataclasses.replace(
            ingress,
            **args,
            _derivation=dataclasses.replace(ingress._derivation, **args),
        )
        bound = dataclasses.replace(
            bound,
            ordinary_ingress=ingress,
            entry_resources=dataclasses.replace(
                bound.entry_resources, ordinary_ingress=ingress
            ),
        )
    elif fault in ("source", "unentered", "copy"):
        at = (
            len(data) - 1
            if fault == "source"
            else 9380
            if fault == "unentered"
            else 8984
        )
        altered = bytearray(data)
        altered[at] ^= 1
        data = bytes(altered)
    elif fault == "profile":
        p["runtime_layout"]["aot_capacity"] = 33
    elif fault == "json-type":
        room["programs"]["16:0"]["commands"][0]["opcode"] = True
    elif fault == "policy":
        del p["trusted_door_policy"]["entry_audit"]
    else:
        p["trusted_door_policy"]["audit"] = "slus00748-trusted-normal-door-access-v1"
    assert compile_door_entry_binding(data, room, p, bound) is DoorEntryFailure.Binding
    from games.re2.door_authority import DoorFailure

    assert type(compile_door_authority(data, room, p, bound)) is DoorFailure
    catalog = door_access_catalog(data, room, p, bound)
    assert catalog["facts"] == catalog["scenario_excluded_offsets"] == []
    assert [row["slot"] for row in catalog["unsupported"]] == [0, 1, 2]


def test_door_binding_has_no_cross_domain_conversion(owned, binding):
    from games.re2.identity_filtering import normal_engine_identity_filtering
    from games.re2.positive_prefix import normal_engine_positive_prefix
    from games.re2.scenario_entry_scope import (
        _ScopePolicy,
        _source_scope_facts,
        scenario_guard_scope,
    )
    from games.re2.scenario_selection import ScenarioSelectionFailure
    from games.re2.source_task_control import TaskControlSupport

    p, _, _, _, sources, bound, _, rooms = owned
    data, room = sources["01-04"], rooms["01-04"]
    context = bind_scenario_context(p, bound.declarations)
    for receipt in (
        context,
        normal_engine_positive_prefix(data, room, p, bound),
        normal_engine_identity_filtering(data, room, p, bound),
        scenario_guard_scope(data, room, p, context, TaskControlSupport.Unaudited),
        binding.source,
        json.loads(binding.room_json),
    ):
        with pytest.raises(AssertionError):
            compile_door_entry_binding(data, room, p, receipt)
    for policy in _ScopePolicy:
        if policy is _ScopePolicy.TrustedDoors:
            continue
        assert isinstance(
            _source_scope_facts(
                data, room, p, context, policy, TaskControlSupport.Unaudited, binding
            ),
            ScenarioSelectionFailure,
        )

    # A different exact subclass cannot inherit the compiler's seal or rights.
    class OtherBinding(_DoorEntryBinding):
        pass

    fake = object.__new__(OtherBinding)
    for f in dataclasses.fields(binding):
        object.__setattr__(fake, f.name, getattr(binding, f.name))
    from games.re2.scenario_entry_scope import DoorSourceFailure

    assert (
        type(
            _source_scope_facts(
                data,
                room,
                p,
                context,
                _ScopePolicy.TrustedDoors,
                TaskControlSupport.Unaudited,
                fake,
            )
        )
        is DoorSourceFailure
    )


@pytest.mark.parametrize("selector", [0, 1, 2, 9, 10, 13, 14, 255])
def test_neutral_task_attachment_keeps_phase_zero_allocator_boundary(owned, selector):
    from test_re2_startup_declarations import END, described

    data, room, _ = described(END, (bytes((4, selector, 0x18, 2)) + END, END, END))
    result = _task_fields(data, room["programs"], auxiliary=False)
    assert type(result) is _TaskFields
    assert {
        task for key, task, depth in result.entries if key == "17:2" and depth == 0
    } == ({selector} if selector < 10 else set(range(2, 10)))
    # This task calculation adds no selector permission to Existing source roles.
    if selector not in (2, 9, 255):
        assert isinstance(
            _source_entry_roles(
                data,
                room["programs"],
                scenario_source_write_witnesses(data, room, owned[0]),
            ),
            PositiveEntryFailure,
        )


@pytest.mark.parametrize("at,depth", [(6729, 0), (6793, 0), (6893, 1)])
def test_actual_unentered_program_gains_every_producer_and_call_depth(owned, at, depth):
    p, _, _, _, sources, _, _, rooms = owned
    from games.re2.event_presence import (
        presence_counter_indices,
        presence_flag_write_proof,
    )
    from games.re2.room_data import decode_room

    data = bytearray(sources["01-04"])
    data[at] = 24
    data = bytes(data)
    room = decode_room(
        data,
        rooms["01-04"]["source"],
        frozenset((f["bank"], f["bit"]) for f in p["presence_condition_flags"]),
        presence_counter_indices(p),
        presence_flag_write_proof(p)[0],
    )
    result = _task_fields(data, room["programs"], auxiliary=False)
    assert type(result) is _TaskFields
    assert {(task, d) for key, task, d in result.entries if key == "17:24"} == (
        {(task, 0) for task in range(2, 10)} if depth == 0 else {(1, 1)}
    )


@pytest.mark.parametrize(
    "depth,birth,accepted",
    [(1, False, True), (1, True, False), (2, True, True), (3, True, False)],
)
def test_auxiliary_inactive_receiver_cannot_be_replaced_by_assumed_flags(
    depth, birth, accepted
):
    from test_re2_ordinary_task_ingress import poll
    from test_re2_startup_declarations import END, described

    main = []
    for index in range(depth):
        main.append(
            (bytes((4, 13, 0x18, depth + 1)) if index == 0 and birth else b"")
            + bytes((0x18, index + 1))
            + END
        )
    main.extend((poll(), END))
    data, room, _ = described(END, tuple(main))
    result = _task_fields(data, room["programs"], auxiliary=True)
    assert (type(result) is _TaskFields) is accepted
    if not accepted:
        assert result is PositiveEntryFailure.ForeignConsumer


def test_public_factory_requires_full_auxiliary_obligations_on_every_source(
    owned, monkeypatch
):
    from games.re2.door_authority import DoorFailure
    from games.re2.ordinary_task_ingress import OrdinaryTaskIngressFailure

    p, _, _, _, sources, bound, _, rooms = owned
    calls = []

    def reject(auxiliaries):
        calls.append(set(auxiliaries))
        return OrdinaryTaskIngressFailure.Auxiliary

    monkeypatch.setattr("games.re2.door_entry.auxiliary_isolation", reject)
    for key in ("00-05", "01-04"):
        assert compile_door_authority(
            sources[key], rooms[key], p, bound
        ) == DoorFailure(DoorEntryFailure.Auxiliary.value)
    assert len(calls) == 2 and all(len(models) == 54 for models in calls)
