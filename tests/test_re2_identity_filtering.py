"""RE2-SCENARIO-009: source/synthetic evidence, never gameplay confirmation."""

import copy
import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re2_metadata import ROOT
from test_re2_positive_prefix import owned as owned
from test_re2_startup_declarations import END, contract, described
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from emulator.duckstation_gdb import MemRead
from games.game_profile import RoomId
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.identity_filtering import (
    _NATIVE_WINDOWS,
    IDENTITY_FILTERING_CATALOG_SHA256,
    IdentityFilteringFailure,
    NormalEngineIdentityFiltering,
    identity_filtering_catalog_digest,
    normal_engine_identity_filtering,
)
from games.re2.known_puzzle_items import known_declared_items_from_prefix
from games.re2.live_tracking import poll_re2
from games.re2.native_control import native_bytes
from games.re2.positive_entry_domain import (
    PositiveEntryFailure,
    SourceEntryPolicy,
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
    scenario_guard_scope,
)
from games.re2.scenario_selection import (
    ScenarioItemVariant,
    ScenarioSelectionFailure,
    ScenarioSourceWriteWitnesses,
    ScopedScenarioItems,
    SourceWritePolicy,
    bind_scenario_context,
    scenario_source_write_witnesses,
    scoped_scenario_items,
)
from games.re2.script_dispatch_items import script_item_dispatch
from games.re2.source_registration import guaranteed_registration
from games.re2.source_task_control import TaskControlSupport
from games.re2.structured_control import (
    ControlFrames,
    StructuredControl,
    structured_control,
)
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


@pytest.fixture(scope="module")
def filtering(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    result = normal_engine_identity_filtering(
        sources["03-08"], rooms["03-08"], p, bound
    )
    assert type(result) is NormalEngineIdentityFiltering
    return result


def test_owned_receipt_with_unaccessed_model_remains_queryable(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    data, room = sources["00-0e"], rooms["00-0e"]
    result = normal_engine_identity_filtering(data, room, p, bound)
    assert type(result) is NormalEngineIdentityFiltering
    assert scoped_scenario_items(data, room, p, result.context, result) == (
        ScopedScenarioItems((), ())
    )


def test_public_factory_query_and_generated_metadata_select_owned_creator(
    owned, filtering
):
    p, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["03-08"], rooms["03-08"]
    assert (
        room["sha256"]
        == "d557b3c7c47c7a9c6a707e3b72c110835aac414da2892c00799f259cac7052cd"
    )
    assert scoped_scenario_items(
        data, room, p, filtering.context, filtering
    ) == ScopedScenarioItems((), (ScenarioItemVariant(185, (10558,)),))
    document = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    generated = next(r for r in document["rooms"] if r["id"] == "03-08")
    assert generated["identity_filtering_items"] == {
        "absent_item_ids": [],
        "item_variants": [{"global_id": 185, "offsets": [10558]}],
    }
    assert [
        (r["offset"], r["type"]) for r in generated["items"] if r["global_id"] == 185
    ] == [(10558, 21), (10584, 25)]
    assert not generated["fixed_context_preserved"]
    assert generated["collection_item_ids"] == []
    assert generated["known_direct_pickups"] == generated["known_puzzle_items"] == []
    assert generated["startup_item_declarations"] == []
    # No stage3 presence contract is added by an identity-only receipt.
    assert {r.stage for r in entry.config.stage_entries} == {0, 1}
    assert (
        type(normal_engine_positive_prefix(data, room, p, bound))
        is not VerifiedNormalEnginePositivePrefix
    )
    with pytest.raises(AssertionError):
        known_declared_items_from_prefix(
            data, room, p, entry, script_item_dispatch(p), filtering
        )
    guard = scenario_guard_scope(
        data, room, p, filtering.context, TaskControlSupport.Unaudited
    )
    assert guard is ScenarioSelectionFailure.EntryScope
    assert filtering.source_roles.foreign_fields == frozenset({0x64})
    assert not filtering.source_roles.break_reads
    assert len(filtering.auxiliary_break_reads) == 126
    assert {read for *_, read in filtering.auxiliary_break_reads} == {0x60}
    assert {(c.target_offset, c.width) for c in filtering.source_writes.copies} == {
        (12398, 2),
        (12428, 2),
    }
    assert 10 in filtering.must_registered


@pytest.mark.parametrize("at,width,digest", _NATIVE_WINDOWS)
def test_every_reviewed_native_window_is_bound_and_mutation_rejected(
    owned, at, width, digest
):
    p, _, executable, _, sources, bound, _, rooms = owned
    assert hashlib.sha256(native_bytes(executable, at, width)).hexdigest() == digest
    for offset in (at, at + width - 1):
        changed = bytearray(executable)
        changed[offset - 0x80010000 + 0x800] ^= 1
        altered = replace(
            bound,
            entry_resources=replace(bound.entry_resources, executable=bytes(changed)),
        )
        assert (
            normal_engine_identity_filtering(
                sources["03-08"], rooms["03-08"], p, altered
            )
            is IdentityFilteringFailure.Binding
        )


@pytest.mark.parametrize(
    "fault",
    ["source", "room", "policy", "mode", "bank", "corpus", "mutable", "authority"],
)
def test_factory_and_query_reject_binding_substitution(owned, filtering, fault):
    p, _, _, _, sources, bound, _, rooms = owned
    p, room, data = copy.deepcopy(p), copy.deepcopy(rooms["03-08"]), sources["03-08"]
    if fault == "source":
        data = data[:10558] + bytes([0]) + data[10559:]
    elif fault == "room":
        room["programs"]["16:0"]["commands"][0]["opcode"] = True
    elif fault == "policy":
        del p["identity_filtering_policy"]
    elif fault == "mode":
        p["runtime_layout"]["system_mode_value"] = 0
    elif fault == "bank":
        p["flag_banks"][0]["address_ps1"] = "0x800CFB78"
    elif fault == "corpus":
        corpus = bound.entry_resources.corpus
        first = corpus.scripts[0]
        altered = replace(
            first,
            programs_json="{}",
            _derivation=replace(first._derivation, programs_json="{}"),
        )
        scripts = (altered, *corpus.scripts[1:])
        bound = replace(
            bound,
            entry_resources=replace(
                bound.entry_resources,
                corpus=replace(
                    corpus,
                    scripts=scripts,
                    _derivation=replace(corpus._derivation, scripts=scripts),
                ),
            ),
        )
    elif fault == "mutable":
        with pytest.raises(AssertionError):
            normal_engine_identity_filtering(bytearray(data), room, p, bound)
        return
    else:
        with pytest.raises(TypeError):
            NormalEngineIdentityFiltering()
        with pytest.raises(AssertionError):
            scoped_scenario_items(
                data,
                room,
                p,
                filtering.context,
                {"source_roles": filtering.source_roles},
            )
        return
    assert (
        type(normal_engine_identity_filtering(data, room, p, bound))
        is IdentityFilteringFailure
    )
    if fault != "corpus":
        assert isinstance(
            scoped_scenario_items(data, room, p, filtering.context, filtering),
            ScenarioSelectionFailure,
        )


@pytest.fixture
def changed_source(owned):
    p, _, _, _, sources, _, _, rooms = owned

    def check(changes):
        data = bytearray(sources["03-08"])
        for at, value in changes.items():
            data[at] = value
        data = bytes(data)
        # This deliberately unsealed source check isolates the selector rules.
        # The actual factory rejects every changed byte through the owned binder.
        try:
            room = decode_room(
                data,
                rooms["03-08"]["source"],
                frozenset((r["bank"], r["bit"]) for r in p["presence_condition_flags"]),
                presence_counter_indices(p),
                presence_flag_write_proof(p)[0],
            )
        except ValueError:
            return ScenarioSelectionFailure.SourceBinding
        room.update(id="00-02", stage=0, room=2)
        context = bind_scenario_context(p, contract(p, room))
        writes = scenario_source_write_witnesses(
            data, room, p, policy=SourceWritePolicy.IdentityFiltering
        )
        if type(writes) is not ScenarioSourceWriteWitnesses:
            return writes
        roles = _source_entry_roles(
            data, room["programs"], writes, policy=SourceEntryPolicy.IdentityFiltering
        )
        if type(roles) is not _SourceEntryRoles:
            return roles
        return _source_scope_facts(
            data,
            room,
            p,
            context,
            _ScopePolicy.IdentityFiltering,
            TaskControlSupport.Unaudited,
            roles,
        )

    return check


def test_unsealed_reference_closes_with_same_protected_light_and_copy_facts(
    changed_source,
):
    assert type(changed_source({})) is _SourceScopeFacts


@pytest.mark.parametrize(
    "at,value",
    [
        (11251, 16),
        (11251, 127),
        (10279, 32),
        (10281, 0xC0),
        (10285, 1),
        (10740, 253),
        (10740, 254),
        (10741, 0x0F),
        (10741, 0x50),
        (13369, 3),
        (13370, 1),
        (13435, 1),
        (12397, 3),
        (12427, 3),
        (12183, 44),
        (12183, 18),
        (11243, 0),
        (11244, 0),
        (11246, 1),
        (13630, 0),
        (13631, 255),
        (10577, 1),
    ],
)
def test_source_native_selector_creator_callback_and_goto_boundaries(
    changed_source, at, value
):
    assert type(changed_source({at: value})) is not _SourceScopeFacts


@pytest.mark.parametrize(
    "copy,target",
    [
        (copy, target)
        for copy in (12392, 12422)
        for target in (
            12396,
            12397,
            12426,
            12427,
            12456,
            12457,
            12458,
            12460,
            12466,
            12467,
        )
        if 0 <= target - copy - 4 < 256
    ],
)
def test_copy_cannot_rewrite_control_selectors_or_an_unentered_work_operand(
    changed_source, copy, target
):
    delta = target - copy - 4
    assert type(changed_source({copy + 2: delta})) is not _SourceScopeFacts


@pytest.mark.parametrize("bank,bit", [(0, 25), (1, 0), (1, 1), (1, 6), (30, 57)])
@pytest.mark.parametrize(
    "at",
    [
        11262,
        11266,
        11284,
        11292,
        11382,
        11390,
        11416,
        11514,
        11522,
        11554,
        11604,
        11612,
        11718,
        11722,
        11729,
        11739,
        11748,
        11994,
        12732,
        12755,
        13048,
        13071,
        13374,
        13440,
        13636,
        13640,
        13644,
        13648,
        13700,
        13704,
        13708,
        13712,
    ],
)
def test_explicit_writers_protect_all_logical_and_physical_historical_aliases(
    changed_source, bank, bit, at
):
    assert type(changed_source({at + 1: bank, at + 2: bit})) is not _SourceScopeFacts


@pytest.mark.parametrize("bank,bit", [(0, 25), (1, 0), (1, 1), (1, 6), (30, 57)])
@pytest.mark.parametrize(
    "at,payload", [(10924, 14), (10944, 14), (10964, 14), (11694, 4), (11704, 4)]
)
def test_every_kind6_creator_and_reset_protects_fixed_aliases(
    changed_source, bank, bit, at, payload
):
    values = dict(
        zip(
            range(at + payload, at + payload + 4),
            struct.pack("<2H", bank, bit),
            strict=True,
        )
    )
    assert type(changed_source(values)) is not _SourceScopeFacts


def test_filtering_predicate86_keeps_both_native_outcomes():
    data, room, _ = described(END, (b"\x06\0\x03\0\x86\x08\0" + END, END))
    result = structured_control(
        data, room["programs"]["17:0"], ControlFrames.IdentityFiltering
    )
    assert type(result) is StructuredControl
    test = room["programs"]["17:0"]["entry"] + 4
    assert dict(result.edges)[test] == (test + 1, test + 3)


def test_legacy_copy_policy_still_rejects_lighting_value_writes(owned):
    p, _, _, _, sources, _, _, rooms = owned
    data, room = sources["03-08"], rooms["03-08"]
    existing = scenario_source_write_witnesses(data, room, p)
    assert (
        _source_entry_roles(data, room["programs"], existing)
        is PositiveEntryFailure.SourceWrite
    )


def test_dispatch_startup_registration_stops_at_yield(owned, filtering):
    _, _, _, _, sources, _, _, rooms = owned
    data, room = sources["03-08"], copy.deepcopy(rooms["03-08"])
    assert 10 in guaranteed_registration(data, room, filtering.source_roles.edges)
    # Stop the synthetic startup graph before the kind12 creator. Merely having
    # its packet elsewhere in the file cannot establish a registered pointer.
    entry = room["programs"]["16:0"]["entry"]
    assert 10 not in guaranteed_registration(
        data,
        room,
        tuple(
            edge for edge in filtering.source_roles.edges if edge[:2] != ("16:0", entry)
        ),
    )


def test_complete_generated_filtering_catalog_keeps_only_compiled_consequences():
    document = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    catalog = {r["id"]: r["identity_filtering_items"] for r in document["rooms"]}
    assert len(catalog) == 125
    assert {key: row for key, row in catalog.items() if any(row.values())} == {
        "00-08": {
            "absent_item_ids": [],
            "item_variants": [{"global_id": 213, "offsets": [6934]}],
        },
        "01-19": {
            "absent_item_ids": [],
            "item_variants": [{"global_id": 117, "offsets": [2762]}],
        },
        "03-08": {
            "absent_item_ids": [],
            "item_variants": [{"global_id": 185, "offsets": [10558]}],
        },
    }
    assert (
        identity_filtering_catalog_digest(document["rooms"])
        == IDENTITY_FILTERING_CATALOG_SHA256
    )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-08", "00-01"], indirect=True)
def test_identity_only_reversals_current_departed_reentry_and_reconstruction(snapshot):
    profile, _, put, read = snapshot
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    tracker = Tracker()
    tracker.mark_current(RoomId(3, 8))
    visits = None
    for acquired in (False, True, False, True):
        for gid in (149, 150, 185, 214):
            at, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(read(at, 4).data, "little")
            put(at, value | mask if acquired else value & ~mask, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        record = tracker.rooms["03-08"]
        assert record.completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Unknown
        )
        assert [i.state for i in record.items] == (
            ["taken"] * 4 if acquired else ["unknown"] * 4
        )
        assert all(i.label != "Collectible" for i in record.items)
        fresh = Tracker()
        fresh.mark_current(RoomId(3, 8))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh == tracker
        if visits is None:
            visits = tracker.region_visits.copy()
        assert tracker.region_visits == visits
        assert set(tracker.rooms) <= {"03-08", "00-01"}


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-08"], indirect=True)
@pytest.mark.parametrize("failure", ["failed", "short", "incoherent"])
def test_new_identity_flags_are_in_atomic_read_transaction(snapshot, failure):
    profile, _, put, read = snapshot
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    # The generic fixture registers both scenario variants. Remove its
    # contradictory alternative before testing read failure atomicity.
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    address = profile.flag_banks[1][0]
    hits = 0

    def broken(at, width):
        nonlocal hits
        result = read(at, width)
        if at <= address < at + width:
            hits += 1
            if failure == "failed":
                return MemRead(False, b"")
            if failure == "short":
                return MemRead(True, result.data[:-1])
            if hits > 1:
                changed = bytearray(result.data)
                changed[address - at + 3] ^= 0x80
                return MemRead(True, bytes(changed))
        return result

    assert poll_re2(profile, tracker, broken).status is not PollStatus.Display
    assert tracker == before


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize(
    "snapshot,target,gids",
    [("03-08", "03-08", (149, 150, 185, 214)), ("01-19", "01-19", (117,))],
    indirect=["snapshot"],
)
@pytest.mark.parametrize("bank,bit", [(1, 0), (1, 1), (1, 6), (0, 25)])
def test_changed_scenario_or_mode_never_publishes_stale_clearance(
    snapshot, target, gids, bank, bit
):
    profile, _, put, read = snapshot
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    acquired_bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0]
    for gid in gids:
        at = acquired_bank + gid // 32 * 4
        put(
            at,
            int.from_bytes(read(at, 4).data, "little") | (0x80000000 >> (gid % 32)),
            4,
        )
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker.rooms[target].completion is RoomCompletion.Cleared
    before = copy.deepcopy(tracker)
    address = profile.flag_banks[bank][0] + bit // 32 * 4
    value = int.from_bytes(read(address, 4).data, "little")
    put(address, value ^ (0x80000000 >> (bit % 32)), 4)
    assert poll_re2(profile, tracker, read).status is not PollStatus.Display
    assert tracker == before
    # Relax only synthetic admission so the separate filtering applicability
    # gate is exercised, rather than the production WrongGame/settings guard.
    layout = profile.runtime_layout | {
        "scenario_mask": 0,
        "system_mode_mask": 0,
        "system_mode_value": 0,
    }
    synthetic = replace(profile, runtime_layout=layout)
    assert poll_re2(synthetic, tracker, read).status is PollStatus.Display
    assert tracker.rooms[target].completion is RoomCompletion.Unknown
    assert sum(i.label == "Collectible" for i in tracker.rooms[target].items) == 1
    put(address, value, 4)
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker == before


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-08"], indirect=True)
@pytest.mark.parametrize("sat", [0, 0x31])
def test_current_excluded_live_creator_retries_even_when_inactive(snapshot, sat):
    profile, _, put, read = snapshot
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    pointer = 0x80100000 + 10584 + 2
    put(pointer, 2, 1)
    put(pointer + 1, sat, 1)
    put(registry + 9 * 4, pointer, 4)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Pickup disagrees with fixed scenario variant"
    assert tracker == before


@pytest.mark.parametrize("fault", ["variant", "missing", "injected", "boolean"])
def test_loader_rejects_uncompiled_identity_metadata(tmp_path, fault):
    from games.re2.re2_profile import Re2Profile

    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    document = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    source = next(r for r in document["rooms"] if r["id"] == "03-08")
    if fault == "variant":
        source["identity_filtering_items"]["item_variants"][0]["offsets"] = [10584]
    elif fault == "missing":
        del source["identity_filtering_items"]
    elif fault == "injected":
        source["identity_filtering_items"]["absent_item_ids"] = [214]
    else:
        source["identity_filtering_items"]["item_variants"][0]["global_id"] = True
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    for field in ("floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(raw))
    diagnostic = {
        "missing": "identity filtering items",
        "boolean": "scenario item variants",
    }.get(fault, "identity filtering catalog")
    with pytest.raises(ValueError, match=diagnostic):
        Re2Profile.load(profile_path)


@pytest.mark.parametrize(
    "key,field,offset,item_type",
    [
        ("03-08", "items", 10558, 22),
        ("03-08", "items", 10558, 104),
        ("03-08", "items", 10584, 22),
        ("01-19", "items", 2762, 21),
        ("01-19", "items", 2762, 104),
        ("01-19", "items", 2826, 21),
        ("00-01", "reset_item_candidates", 9740, 8),
    ],
)
def test_loader_binds_selected_competing_and_reset_descriptor_types(
    tmp_path, key, field, offset, item_type
):
    from games.re2.re2_profile import Re2Profile

    raw = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    document = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    room = next(r for r in document["rooms"] if r["id"] == key)
    next(item for item in room[field] if item["offset"] == offset)["type"] = item_type
    metadata = tmp_path / "rooms.json"
    metadata.write_text(json.dumps(document))
    raw["room_metadata_path"] = str(metadata)
    for field in ("floor_plans_path", "names_path"):
        raw[field] = str((ROOT / "profiles" / raw[field]).resolve())
    profile_path = tmp_path / "profile.json"
    profile_path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="identity filtering catalog"):
        Re2Profile.load(profile_path)


def test_filtering_class_and_owned_fields_cannot_be_substituted(owned, filtering):
    p, _, _, _, sources, _, _, rooms = owned

    class PretendFiltering(NormalEngineIdentityFiltering):
        pass

    changed = copy.copy(filtering)
    object.__setattr__(changed, "must_registered", frozenset())
    with pytest.raises(AssertionError):
        scoped_scenario_items(
            sources["03-08"], rooms["03-08"], p, filtering.context, changed
        )
    subtype = object.__new__(PretendFiltering)
    with pytest.raises(AssertionError):
        scoped_scenario_items(
            sources["03-08"], rooms["03-08"], p, filtering.context, subtype
        )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["03-08"], indirect=True)
def test_departure_reentry_and_earlier_synthetic_image_preserve_visits(snapshot):
    from types import SimpleNamespace

    import test_re2_tracking
    from test_live_items import RamReader

    current_profile, current_ram, _, _ = snapshot
    other_profile, other_ram, _, _ = test_re2_tracking.snapshot.__wrapped__(
        SimpleNamespace(param="00-01"), current_profile
    )
    profile = replace(
        current_profile,
        rooms=current_profile.rooms | {"00-01": other_profile.rooms["00-01"]},
    )
    ram = bytearray(current_ram)
    read = RamReader(ram).read_memory
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0) & 0x1FFFFF
    bank = profile.flag_banks[profile.runtime_layout["item_bank_early"]][0] & 0x1FFFFF
    tracker = Tracker()
    for current, acquired in (
        (True, False),
        (False, False),
        (True, False),
        (False, True),
        (True, True),
        (False, False),
        (True, False),
    ):
        ram[:] = current_ram if current else other_ram
        ram[registry : registry + 128] = bytes(128)
        for gid in (149, 150, 185, 214):
            at, mask = bank + gid // 32 * 4, 0x80000000 >> (gid % 32)
            value = int.from_bytes(ram[at : at + 4], "little")
            ram[at : at + 4] = (value | mask if acquired else value & ~mask).to_bytes(
                4, "little"
            )
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        target = tracker.rooms["03-08"]
        assert target.completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Unknown
        )
        assert [i.state for i in target.items] == (
            ["taken"] * 4 if acquired else ["unknown"] * 4
        )
        fresh = Tracker()
        for key in tracker.rooms:
            fresh.mark_current(RoomId(*[int(part, 16) for part in key.split("-")]))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.rooms == tracker.rooms and fresh.doors == tracker.doors
        assert set(tracker.rooms) <= {"03-08", "00-01"}
    assert set(tracker.rooms) == {"03-08", "00-01"}
