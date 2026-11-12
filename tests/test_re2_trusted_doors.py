"""RE2-DOOR-009: actual owned corpus plus synthetic fresh-reader controls.

These are source/synthetic checks. They do not observe gameplay or save loads.
"""

import copy
import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re2_immutable_open_doors import door
from test_re2_metadata import ROOT
from test_re2_positive_prefix import owned as owned
from test_re2_startup_declarations import END, contract, described
from test_re2_tracking import profile as profile
from test_re2_tracking import snapshot as snapshot

from emulator.duckstation_gdb import MemRead
from games.bit_flags import msb_flag_location
from games.game_profile import RoomId
from games.re2.door_access import BoundDoorCatalog, load_door_catalogs
from games.re2.door_authority import (
    DoorAccessFact,
    DoorAuthority,
    DoorFailure,
    compile_door_access,
    compile_door_authority,
    door_access_catalog,
)
from games.re2.immutable_open_doors import immutable_open_doors
from games.re2.live_tracking import poll_re2
from games.re2.positive_prefix import normal_engine_positive_prefix
from games.re2.scenario_entry_scope import (
    DoorSourceFacts,
    DoorSourceFailure,
    _ScopePolicy,
    _source_scope_facts,
    scenario_guard_scope,
)
from games.re2.scenario_selection import bind_scenario_context
from games.re2.source_task_control import TaskControlSupport
from tracker.exploration_state import DoorUnlockState, Tracker
from tracker.polling import PollStatus
from ui.map_view import map_state


def test_complete_owned_corpus_reproduces_every_slot_and_creator(owned):
    profile, config, _, resources, sources, bound, entry, rooms = owned
    committed = {
        r["id"]: r
        for r in json.loads((ROOT / "data/rooms_slus00748.json").read_text())["rooms"]
    }
    assert (
        len(resources),
        len(sources),
        len(bound.entry_resources.corpus.scripts),
    ) == (69, 125, 54)
    slots = creators = accepted = enabled = keyed = later = excluded = (
        accepted_creators
    ) = 0
    for key, room in rooms.items():
        catalog = door_access_catalog(sources[key], room, profile, bound)
        assert catalog == committed[key]["door_access_catalog"], key
        facts = {f["slot"]: f for f in catalog["facts"]}
        gaps = {f["slot"]: f for f in catalog["unsupported"]}
        raw_slots = {d["slot"] for d in room["doors"]}
        assert not facts.keys() & gaps.keys()
        assert facts.keys() | gaps.keys() == raw_slots
        assert not set(catalog["scenario_excluded_offsets"]) & {
            at for f in facts.values() for at in f["creator_offsets"]
        }
        slots += len(raw_slots)
        creators += len(room["doors"])
        accepted += len(facts)
        enabled += sum(f["enabled"] for f in facts.values())
        keyed += sum(bool(f["lock_id"] & 128) for f in facts.values())
        later += sum(room["stage"] >= 2 for _ in facts)
        excluded += len(catalog["scenario_excluded_offsets"])
        accepted_creators += sum(len(f["creator_offsets"]) for f in facts.values())
        # Legacy exports are independently derived and remain available, even
        # where the new policy rejects the source's broader continuation.
        legacy = immutable_open_doors(
            sources[key], room, profile, entry, entry.write_partitions
        )
        if key == "01-01":
            assert [f.slot for f in legacy] == [0, 1]
            assert not facts
        elif isinstance(legacy, tuple):
            assert legacy == ()
    assert (
        slots,
        creators,
        accepted,
        enabled,
        keyed,
        later,
        excluded,
        accepted_creators,
    ) == (279, 321, 114, 110, 13, 55, 11, 124)
    assert creators - excluded - accepted_creators == 186


def test_door_authority_is_separate_and_compiler_owned(owned):
    profile, _, _, _, sources, bound, _, rooms = owned
    key = "00-05"
    data, room = sources[key], rooms[key]
    authority = compile_door_authority(data, room, profile, bound)
    assert type(authority) is DoorAuthority
    facts, _, _ = compile_door_access(data, room, profile, authority)
    assert facts and all(
        type(f) is DoorAccessFact and f.matches(authority) for f in facts
    )
    for value in (authority, *facts):
        with pytest.raises(TypeError):
            type(value)()
        with pytest.raises(TypeError):
            replace(value)
    context = bind_scenario_context(profile, bound.declarations)
    for other in (
        context,
        scenario_guard_scope(
            data, room, profile, context, TaskControlSupport.Unaudited
        ),
        normal_engine_positive_prefix(data, room, profile, bound),
    ):
        with pytest.raises(AssertionError):
            compile_door_access(data, room, profile, other)
    changed = copy.deepcopy(room)
    changed["doors"][0]["lock_id"] ^= 128
    assert not authority.matches(data, changed, profile)
    with pytest.raises(AssertionError):
        compile_door_access(data, changed, profile, authority)


@pytest.mark.parametrize(
    "mutation",
    [
        "opt-out",
        "exe",
        "resource",
        "source",
        "decoded",
        "bank",
        "mode",
        "aot",
        "policy",
        "revision",
    ],
)
def test_public_compiler_rejects_binding_mutations(owned, mutation):
    profile, _, _, _, sources, bound, _, rooms = owned
    profile = copy.deepcopy(profile)
    data, room = sources["00-03"], copy.deepcopy(rooms["00-03"])
    if mutation == "opt-out":
        del profile["trusted_door_policy"]
    elif mutation == "exe":
        bound = replace(
            bound,
            entry_resources=replace(
                bound.entry_resources,
                executable=bound.entry_resources.executable[:-1] + b"!",
            ),
        )
    elif mutation == "resource":
        profile["startup_declaration_audit"]["resources"][0]["sha256"] = "0" * 64
    elif mutation == "source":
        data = data[:-1] + bytes([data[-1] ^ 1])
    elif mutation == "decoded":
        room["programs"]["17:0"]["commands"][0]["opcode"] = 0
    elif mutation == "bank":
        profile["flag_banks"][0]["address_ps1"] = "0x800CFB78"
    elif mutation == "mode":
        profile["runtime_layout"]["system_mode_value"] = 0
    elif mutation == "aot":
        profile["runtime_layout"]["aot_capacity"] = 33
    elif mutation == "policy":
        profile["trusted_door_policy"]["audit"] += "-other"
    else:
        profile["profile_id"] = "re2_claire_b_slus00756"
    assert type(compile_door_authority(data, room, profile, bound)) is DoorFailure


def test_catalog_loader_rejects_changed_facts_and_policy():
    profile = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    document = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    rooms = {r["id"]: r for r in document["rooms"]}
    assert len(load_door_catalogs(profile, rooms, document)) == 56
    original = copy.deepcopy(document)
    for mutation in ("target", "enabled", "excluded", "missing", "profile", "program"):
        document = copy.deepcopy(original)
        source = next(r for r in document["rooms"] if r["id"] == "00-05")
        catalog = source["door_access_catalog"]
        if mutation == "target":
            catalog["facts"][0]["room"] ^= 1
        elif mutation == "enabled":
            catalog["facts"][0]["enabled"] = False
        elif mutation == "excluded":
            catalog["scenario_excluded_offsets"].append(
                catalog["facts"][0]["creator_offsets"][0]
            )
        elif mutation == "missing":
            del source["door_access_catalog"]
        elif mutation == "profile":
            catalog["profile_sha256"] = "0" * 64
        else:
            catalog["programs_sha256"] = "0" * 64
        with pytest.raises(ValueError, match="door catalog"):
            load_door_catalogs(
                profile, {r["id"]: r for r in document["rooms"]}, document
            )
    del profile["trusted_door_policy"]
    with pytest.raises(ValueError, match="explicit opt-in"):
        load_door_catalogs(profile, rooms, original)
    for cls in (BoundDoorCatalog,):
        with pytest.raises(TypeError):
            cls()


def test_source_owned_unsafe_paths_remain_unsupported(owned):
    p, _, _, _, sources, bound, _, rooms = owned
    expected = {
        "00-08": "goto_receiving_frame_consumer",
        "00-01": "copy_changes_unclosed_operand",
        "03-00": "sound_compaction_write_domain",
    }
    for key, reason in expected.items():
        assert compile_door_authority(
            sources[key], rooms[key], p, bound
        ) == DoorFailure(reason)
    for key, slot in [("00-09", 0), ("00-09", 2), ("05-06", 3)]:
        catalog = door_access_catalog(sources[key], rooms[key], p, bound)
        gap = next(g for g in catalog["unsupported"] if g["slot"] == slot)
        assert "history_dependent_kind_reset" in gap["reasons"]


@pytest.mark.parametrize(
    "effect,reason",
    [
        (bytes([0x22, 1, 6, 1]), "scenario_flag_write"),
        (bytes([0x22, 30, 57, 1]), "scenario_flag_write"),
        (bytes([0x44, 0, 253, 0x22]) + bytes(18), "source_control_or_write"),
        (bytes([0x44, 0, 0, 0x56]) + bytes(18), "source_control_or_write"),
        (bytes([0x2E, 4, 255]), "source_control_or_write"),
        (bytes([0x6E, 0, 128, 0, 0, 0]), "part_selector_bounds"),
        (bytes([0x46, 0, 1, 0x80]) + bytes(6), "reset_changes_geometry_selector"),
        (
            bytes([0x46, 0, 2, 0x31]) + struct.pack("<3H", 20, 1, 256),
            "acquisition_flag_bounds",
        ),
        (
            bytes([0x2C, 1, 6, 0x31]) + bytes(10) + struct.pack("<3H", 30, 57, 1),
            "scenario_kind6_write",
        ),
        (bytes([0x29, 127]), "camera_selector_bounds"),
        (bytes([0x52]) + bytes(5), "unmodeled_native_opcode"),
        (bytes([0x6C]), "sound_compaction_write_domain"),
        (bytes([0x1C]), "unmodeled_source_or_control_rewrite"),
    ],
)
def test_neutral_source_checks_reject_unsafe_domains(effect, reason):
    p = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    data, room, _ = described(door() + END, (effect + END, END))
    context = bind_scenario_context(p, contract(p, room))
    result = _source_scope_facts(
        data, room, p, context, _ScopePolicy.TrustedDoors, TaskControlSupport.Unaudited
    )
    assert result == DoorSourceFailure(reason)


@pytest.mark.parametrize("slot", [0, 31, 254, 255])
@pytest.mark.parametrize("model", [0x22, 0x50, 0x51, 0x55])
def test_reserved_native_actor_slots_and_literal_models_are_bounded(slot, model):
    p = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    actor = bytes([0x44, 0, slot, model]) + bytes(18)
    data, room, _ = described(door() + END, (actor + bytes([0x2E, 3, slot]) + END, END))
    context = bind_scenario_context(p, contract(p, room))
    assert (
        type(
            _source_scope_facts(
                data,
                room,
                p,
                context,
                _ScopePolicy.TrustedDoors,
                TaskControlSupport.Unaudited,
            )
        )
        is DoorSourceFacts
    )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-01"], indirect=True)
def test_every_departed_creator_and_keyed_variant_rebuilds_with_fresh_flags(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    legacy = Tracker()
    old_profile = replace(profile, door_catalogs={})
    for key, source in profile.rooms.items():
        room = RoomId(source["stage"], source["room"])
        tracker.mark_current(room)
        legacy.mark_current(room)
    initial_visits = set(tracker.rooms)
    for unlocked in (False, True, False):
        for word in range(2):
            put(
                profile.flag_banks[profile.runtime_layout["key_bank"]][0] + 4 * word,
                0xFFFFFFFF if unlocked else 0,
                4,
            )
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        assert poll_re2(old_profile, legacy, read).status is PollStatus.Display
        assert set(tracker.rooms) == initial_visits
        observed = {d.observation_id: d for d in tracker.doors}
        old = {d.observation_id: d for d in legacy.doors}
        covered = set()
        excluded = set()
        for key, source in profile.rooms.items():
            catalog = source["door_access_catalog"]
            if key == "00-01":
                continue
            excluded.update(
                f"{key}:{at}" for at in catalog["scenario_excluded_offsets"]
            )
            for fact in catalog["facts"]:
                expected = (
                    "BLOCKED"
                    if not fact["enabled"]
                    else "OPEN"
                    if not fact["lock_id"] & 128 or unlocked
                    else "UNLOCKABLE"
                    if fact["lock_type"] == 0xFE
                    else "LOCKED"
                )
                for at in fact["creator_offsets"]:
                    identity = f"{key}:{at}"
                    covered.add(identity)
                    actual = observed[identity]
                    assert actual.state == expected, (identity, actual)
                    assert actual.target == RoomId(fact["stage"], fact["room"])
                    if fact["lock_id"] & 128:
                        assert actual.unlock_state is (
                            DoorUnlockState.Unlocked
                            if unlocked
                            else DoorUnlockState.Locked
                        )
            # Only derived door summaries may change on each room record.
            assert tracker.rooms[key].items == legacy.rooms[key].items
            assert tracker.rooms[key].completion == legacy.rooms[key].completion
        assert len(covered) == 124
        assert len(excluded) == 11
        assert not excluded & observed.keys()
        for identity, actual in observed.items():
            if identity not in covered:
                assert actual == old[identity], identity
        fresh = Tracker()
        for key in initial_visits:
            source = profile.rooms[key]
            fresh.mark_current(RoomId(source["stage"], source["room"]))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert fresh.doors == tracker.doors
        for field in ("player_position", "player_heading", "current", "region_visits"):
            assert getattr(tracker, field) == getattr(legacy, field)


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
def test_hidden_sources_stay_hidden_and_flags_remain_transaction_guards(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert set(tracker.rooms) == {"00-01"}
    assert all(str(d.source) == "00-01" for d in tracker.doors)
    tracker.mark_current(RoomId(0, 3))
    key_fact = next(
        (key, fact)
        for key, catalog in profile.door_catalogs.items()
        for fact in catalog.facts
        if fact.lock_id & 128
    )
    key, fact = key_fact
    source = profile.rooms[key]
    tracker.mark_current(RoomId(source["stage"], source["room"]))
    address, mask = msb_flag_location(
        profile.flag_banks[profile.runtime_layout["key_bank"]][0], fact.lock_id & 63
    )
    put(address, 0, 4)
    calls = 0
    before = copy.deepcopy(tracker)

    def torn(address_read, width):
        nonlocal calls
        result = read(address_read, width)
        if address_read == address and width == 4:
            calls += 1
            if calls == 1:
                return MemRead(
                    True,
                    (int.from_bytes(result.data, "little") ^ mask).to_bytes(
                        4, "little"
                    ),
                )
        return result

    assert poll_re2(profile, tracker, torn).status is PollStatus.Retry
    assert tracker == before
    assert calls == 1
    assert map_state(tracker) == map_state(before)


def test_unchanged_native_reset_leaf_preserves_route_but_not_kind_history(owned):
    from itertools import product

    from unicorn import UC_ARCH_MIPS, UC_MODE_LITTLE_ENDIAN, UC_MODE_MIPS32, Uc
    from unicorn.mips_const import (
        UC_MIPS_REG_A0,
        UC_MIPS_REG_PC,
        UC_MIPS_REG_RA,
        UC_MIPS_REG_V0,
    )

    _, _, executable, _, _, _, _, _ = owned
    start, end = 0x80055154, 0x800551C8
    code = executable[0x800 + start - 0x80010000 : 0x800 + end - 0x80010000]
    assert (
        hashlib.sha256(code).hexdigest()
        == "3ac89bd618207ddc7c84953e22b53de29436d99cf95566b48ba2ad5cac9b3b05"
    )
    for four, kind, sat, slot in product(
        (False, True), (0, 1, 5), (0, 0x31, 0x51, 0x80, 0xB1), (0, 7, 31)
    ):
        ram = bytearray(0x200000)
        ram[start & 0x1FFFFF : (start & 0x1FFFFF) + len(code)] = code
        task, table, packet, descriptor, ret = (
            0x800D7860,
            0x800CE558,
            0x80100000,
            0x80110000,
            0x801F0000,
        )

        def put(address, value, width):
            offset = address & 0x1FFFFF
            ram[offset : offset + width] = value.to_bytes(width, "little")

        old = bytearray(range(38 if four else 30))
        old[:2] = bytes((1, 0xB1 if four else 0x31))
        offset = descriptor & 0x1FFFFF
        ram[offset : offset + len(old)] = old
        reset = bytes((0x46, slot, kind, sat)) + bytes.fromhex("34127856bc9a")
        ram[packet & 0x1FFFFF : (packet & 0x1FFFFF) + 10] = reset
        put(task + 0x1C, packet, 4)
        put(table + 4 * slot, descriptor, 4)
        expected = ram.copy()
        expected[offset : offset + 2] = bytes((kind, sat | (old[1] & 0x80)))
        payload = offset + (20 if four else 12)
        expected[payload : payload + 6] = reset[4:10]
        pc = (task + 0x1C) & 0x1FFFFF
        expected[pc : pc + 4] = (packet + 10).to_bytes(4, "little")
        uc = Uc(UC_ARCH_MIPS, UC_MODE_MIPS32 | UC_MODE_LITTLE_ENDIAN)
        uc.mem_map(0, 0x200000)
        uc.mem_write(0, bytes(ram))
        uc.reg_write(UC_MIPS_REG_A0, task)
        uc.reg_write(UC_MIPS_REG_RA, ret)
        uc.emu_start(start, ret, count=100)
        assert uc.reg_read(UC_MIPS_REG_PC) == ret
        assert uc.reg_read(UC_MIPS_REG_V0) == 1
        actual = bytes(uc.mem_read(0, 0x200000))
        assert actual == expected
        # Physical route/lock fields remain equal even in kind-changing cases.
        # Such histories still have no door fact; equal bytes alone grant none.
        for field in (8, 9, 11, 15, 16):
            assert actual[payload + field] == ram[payload + field]


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-05"], indirect=True)
@pytest.mark.parametrize("binding", ["missing", "inactive", "contradictory"])
def test_source_facts_never_override_current_missing_inactive_or_contradictory(
    snapshot, binding
):
    profile, _, put, read = snapshot
    source = profile.rooms["00-05"]
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    definition = source["doors"][0]
    if binding != "missing":
        pointer = 0x80100000 + definition["offset"] + 2
        put(registry + definition["slot"] * 4, pointer, 4)
        if binding == "inactive":
            put(pointer + 1, 0, 1)
        else:
            operand = 20 if definition["four_point"] else 12
            put(pointer + operand + 8, 255, 1)
    tracker = Tracker()
    if binding == "contradictory":
        before = copy.deepcopy(tracker)
        assert poll_re2(profile, tracker, read).status is PollStatus.Retry
        assert tracker == before
    else:
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        actual = next(
            d
            for d in tracker.doors
            if d.observation_id == f"00-05:{definition['offset']}"
        )
        assert actual.state == ("UNCHECKED" if binding == "missing" else "BLOCKED")


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-17"], indirect=True)
def test_acquisition_reversal_leaves_doors_independent(snapshot):
    profile, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 3))
    tracker.mark_current(RoomId(0, 5))
    address, mask = msb_flag_location(
        profile.flag_banks[profile.runtime_layout["item_bank_early"]][0], 211
    )
    doors = None
    for acquired in (False, True, False):
        put(address, mask if acquired else 0, 4)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        item = next(
            i
            for i in tracker.rooms["00-03"].items
            if i.label == profile.names["items"]["38"]
        )
        assert item.state == ("taken" if acquired else "uncollected")
        if doors is None:
            doors = tracker.doors
        assert tracker.doors == doors
        assert set(tracker.rooms) == {"00-03", "00-05", "00-17"}


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "short",
        "after-heap",
        "script",
        "vector-index",
        "component",
        "strength-index",
        "copy-value",
        "copy-selector",
    ],
)
def test_camera_light_records_have_full_bounded_disjoint_footprints(mutation):
    from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES
    from test_re2_room_write_partitions import source

    from games.re2.room_data import decode_room
    from games.re2.scenario_selection import (
        ScenarioSelectionFailure,
        ScenarioSourceWriteWitnesses,
        SourceWritePolicy,
        scenario_source_write_witnesses,
    )

    p = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    vector = bytearray([0x6A, 0, 2, 13, 0x34, 0x12])
    strength = bytearray([0x6B, 2, 0x78, 0x56])
    if mutation == "vector-index":
        vector[2] = 3
    elif mutation == "component":
        vector[3] = 14
    elif mutation == "strength-index":
        strength[1] = 3
    prefix = (
        bytes([0x1D, 4, 4 if mutation == "copy-value" else 2, 1])
        if mutation.startswith("copy-")
        else b""
    )
    raw, _, sections = source(
        door() + END, (prefix + vector + strength + END, END), [], [0]
    )
    data = bytearray(raw)
    at = sections["floor"]
    width = 7 * 40 - (2 if mutation == "short" else 0)
    data[at:at] = bytes(width)
    struct.pack_into(
        "<I", data, 8 + 2 * 4, at if mutation == "after-heap" else at + width
    )
    struct.pack_into("<I", data, 8 + 9 * 4, at)
    if mutation == "script":
        struct.pack_into(
            "<I", data, 8 + 9 * 4, struct.unpack_from("<I", data, 8 + 17 * 4)[0]
        )
    data = bytes(data)
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    receipt = scenario_source_write_witnesses(
        data, room, p, policy=SourceWritePolicy.NormalDoors
    )
    if mutation in ("none", "copy-value", "copy-selector"):
        assert type(receipt) is ScenarioSourceWriteWitnesses
        assert any(
            region.offset == at and region.width == 280
            for region in receipt.record_reads
        )
        assert len(receipt.record_writes) == 14
        assert all(at <= r.offset <= at + 280 - r.width for r in receipt.record_writes)
        room.update(id="00-02", stage=0, room=2)
        context = bind_scenario_context(p, contract(p, room))
        graph = _source_scope_facts(
            data,
            room,
            p,
            context,
            _ScopePolicy.TrustedDoors,
            TaskControlSupport.Unaudited,
        )
        if mutation == "copy-selector":
            assert graph == DoorSourceFailure("copy_changes_unclosed_operand")
        else:
            assert type(graph) is DoorSourceFacts
    else:
        assert isinstance(receipt, ScenarioSelectionFailure)


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-05"], indirect=True)
def test_synthetic_departure_reentry_and_earlier_state_rebuild_without_access_cache(
    snapshot,
):
    from types import SimpleNamespace

    from test_re2_tracking import snapshot as synthetic_snapshot

    first, first_ram, put, first_read = snapshot
    registry = int(first.runtime_layout["aot_table_address_ps1"], 0)
    for slot in range(32):
        put(registry + slot * 4, 0, 4)
    earlier = bytes(first_ram)
    profile, _, _, departed_read = synthetic_snapshot.__wrapped__(
        SimpleNamespace(param="00-17"), first
    )
    tracker = Tracker()
    definition = next(
        d for d in first.rooms["00-05"]["doors"] if not d["lock_id"] & 128
    )
    identity = f"00-05:{definition['offset']}"
    for read, expected in (
        (first_read, "UNCHECKED"),
        (departed_read, "OPEN"),
        (first_read, "UNCHECKED"),
    ):
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        assert (
            next(d for d in tracker.doors if d.observation_id == identity).state
            == expected
        )
        before = copy.deepcopy(tracker)
        assert (
            poll_re2(replace(profile, door_catalogs={}), before, read).status
            is PollStatus.Display
        )
        assert before.player_heading == tracker.player_heading
        assert before.player_position == tracker.player_position
        assert all(
            before.rooms[key].items == room.items
            and before.rooms[key].completion == room.completion
            for key, room in tracker.rooms.items()
        )
    pointer = 0x80100000 + definition["offset"] + 2
    put(registry + definition["slot"] * 4, pointer, 4)
    assert poll_re2(profile, tracker, first_read).status is PollStatus.Display
    assert (
        next(d for d in tracker.doors if d.observation_id == identity).state == "OPEN"
    )
    # Restore the complete synthetic earlier RAM, including missing registration.
    # Visits accumulate; access is freshly derived and loses the current binding.
    first_ram[:] = earlier
    assert poll_re2(profile, tracker, first_read).status is PollStatus.Display
    assert (
        next(d for d in tracker.doors if d.observation_id == identity).state
        == "UNCHECKED"
    )
    assert set(tracker.rooms) == {"00-05", "00-17"}
    fresh = Tracker()
    for key in tracker.rooms:
        source = profile.rooms[key]
        fresh.mark_current(RoomId(source["stage"], source["room"]))
    assert poll_re2(profile, fresh, first_read).status is PollStatus.Display
    assert fresh.doors == tracker.doors
    assert fresh.rooms == tracker.rooms
