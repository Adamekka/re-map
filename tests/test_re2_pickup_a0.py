"""RE2-STARTUP-009: owned ordinary A0 presence, separate from acquisition."""

import copy
import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re2_metadata import ROOT
from test_re2_positive_prefix import owned as owned  # noqa: F401
from test_re2_tracking import profile as profile  # noqa: F401
from test_re2_tracking import snapshot as snapshot

from games.bit_flags import msb_flag_location
from games.game_profile import RoomId
from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.known_puzzle_items import (
    KnownDeclaredItems,
    known_declared_items_from_prefix,
)
from games.re2.live_tracking import poll_re2
from games.re2.native_control import native_bytes
from games.re2.normal_engine_binding import OWNED_SOURCE_FIELDS
from games.re2.positive_pickup_roles import (
    ACTOR_STATE_IMAGES,
    PICKUP_NATIVE_WINDOWS,
    PickupRolesFailure,
    PickupRolesSupport,
    _actor_byte_state_roles,
)
from games.re2.positive_prefix import (
    PositivePrefixFailure,
    VerifiedNormalEnginePositivePrefix,
    normal_engine_positive_prefix,
)
from games.re2.room_data import decode_room
from games.re2.room_write_partitions import direct_pickup_packet
from games.re2.scenario_selection import (
    ScenarioSourceWriteWitnesses,
    scenario_source_write_witnesses,
)
from games.re2.script_dispatch_items import script_item_dispatch
from tracker.exploration_state import RoomCompletion, Tracker
from tracker.polling import PollStatus


def test_owned_ordinary_a0_factory_and_public_query(owned):
    profile, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-05"], rooms["00-05"]
    assert data[4616:4638].hex() == "4e020231000096c98ec22003140558000100040000a0"
    prefix = normal_engine_positive_prefix(data, room, profile, bound)
    assert type(prefix) is VerifiedNormalEnginePositivePrefix
    result = known_declared_items_from_prefix(
        data, room, profile, entry, script_item_dispatch(profile), prefix
    )
    assert type(result) is KnownDeclaredItems
    assert result.puzzle_items == ()
    assert len(result.direct_pickups) == 1
    target = result.direct_pickups[0]
    assert (
        target.global_id,
        target.item_type,
        target.slot,
        target.creator_offsets,
    ) == (
        4,
        88,
        2,
        (4616,),
    )
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


def test_generated_ordinary_a0_is_a_required_direct_item():
    catalog = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    room = next(row for row in catalog["rooms"] if row["id"] == "00-05")
    assert [row["global_id"] for row in room["known_direct_pickups"]] == [4]


@pytest.fixture
def actor_check(owned):
    p, _, _, _, sources, _, _, rooms = owned

    def check(edits=()):
        data = bytearray(sources["00-05"])
        for at, value in edits:
            data[at : at + len(value)] = value
        data = bytes(data)
        room = decode_room(
            data,
            rooms["00-05"]["source"],
            frozenset((r["bank"], r["bit"]) for r in p["presence_condition_flags"]),
            presence_counter_indices(p),
            presence_flag_write_proof(p)[0],
        )
        room.update(id="00-05", stage=0, room=5)
        writes = scenario_source_write_witnesses(data, room, p)
        if type(writes) is not ScenarioSourceWriteWitnesses:
            return PickupRolesFailure.Actor
        # Unsealed neutral source controls never construct presence authority.
        # Separate public-factory controls check the complete owned binding.
        return _actor_byte_state_roles(data, room, p, writes)

    return check


def test_owned_guarded_atomic_actor_recipe(actor_check):
    roles = actor_check()
    assert len(roles) == 16
    assert {slot for _, _, slot, _, _ in roles} == {1, 2}
    assert {creator for _, _, _, creator, _ in roles} == {4680, 4702}
    assert {guard for _, _, _, _, guard in roles} == {26, 27}


@pytest.mark.parametrize(
    "offset,expected", [(4808, 1), (4812, 13), (4816, 0), (4840, 0)]
)
@pytest.mark.parametrize("value", [0, 1, 13, 31, 255, 256, 65535])
def test_arbitrary_byte_state_literals_reject(actor_check, offset, expected, value):
    result = actor_check(((offset + 2, struct.pack("<H", value)),))
    assert (type(result) is tuple) == (value == expected)


@pytest.mark.parametrize(
    "edits",
    [
        ((4801, b"\x01"),),
        ((4801, b"\x02"),),
        ((4801, b"\x04"),),
        ((4802, b"\x00"),),
        ((4802, b"\xff"),),
        ((4683, b"\x11"),),
        ((4684, b"\x01\0"),),
        ((4684, b"\xff\xff"),),
        ((4682, b"\x02"),),
        ((4689, b"\xff"),),
        ((4689, b"\x1b"),),
        ((4797, b"\x07"),),
        ((4798, b"\x1b"),),
        ((4799, b"\x01"),),
        ((4805, b"\x03"),),
        ((4806, b"\x01\0"),),
        ((4825, b"\x01"),),
        ((4833, b"\x01"),),
        ((4794, struct.pack("<h", 4812 - 4796)),),
        ((4788, b"\x1d\0\x06\0"),),
        ((4808, b"\x35\x02\0\0"),),
        ((4808, b"\x3d\0\x02\0"),),
        ((5110, b"\x04\xff\x18\x01"),),
        ((5110, b"\x24\x48\0\0"),),
        ((4640, b"\x06"),),
        ((4640, b"\x05"), (4652, b"\xff\0\x18\x01\0\0")),
    ],
)
def test_ownership_control_copy_and_callback_boundaries(actor_check, edits):
    assert actor_check(edits) is PickupRolesFailure.Actor


def test_numeric_pose_copy_is_still_numeric(actor_check):
    # Only an already admitted position operand changes. Control stays fixed.
    assert type(actor_check(((4612, b"\x1d\0\xd2\x01"),))) is tuple


@pytest.mark.parametrize("field", ["actor_writes", "native_windows", "actor_images"])
def test_pickup_roles_recompute_their_complete_derivation(owned, field):
    p, _, _, _, sources, bound, _, rooms = owned
    prefix = normal_engine_positive_prefix(sources["00-05"], rooms["00-05"], p, bound)
    roles = prefix.pickup_roles
    changed = replace(roles.facts, **{field: getattr(roles.facts, field)[:-1]})
    with pytest.raises(AssertionError):
        replace(roles, facts=changed)
    with pytest.raises(AssertionError):
        replace(
            prefix,
            pickup_roles=PickupRolesSupport.Existing,
            _derivation=replace(
                prefix._derivation, pickup_roles=PickupRolesSupport.Existing
            ),
        )


@pytest.mark.parametrize(
    "at",
    [4616 + n for n in (1, 2, 3, 10, 12, 14, 16, 18, 20, 21)]
    + [4802, 4808, 4814, 4842, 5074, 5110],
)
def test_real_factory_and_query_reject_source_mutations(owned, at):
    from games.re2.known_puzzle_items import KnownDeclaredItemFailure

    p, _, _, _, sources, bound, entry, rooms = owned
    data, room = sources["00-05"], rooms["00-05"]
    prefix = normal_engine_positive_prefix(data, room, p, bound)
    changed = bytearray(data)
    changed[at] ^= 1
    changed = bytes(changed)
    assert isinstance(
        normal_engine_positive_prefix(changed, room, p, bound), PositivePrefixFailure
    )
    assert (
        known_declared_items_from_prefix(
            changed, room, p, entry, script_item_dispatch(p), prefix
        )
        is KnownDeclaredItemFailure.InputBinding
    )
    altered_room = copy.deepcopy(room)
    altered_room["sha256"] = hashlib.sha256(changed).hexdigest()
    assert isinstance(
        normal_engine_positive_prefix(changed, altered_room, p, bound),
        PositivePrefixFailure,
    )


@pytest.mark.parametrize(
    "at",
    [
        0x800518CC,
        0x800518D4,
        0x80072388,
        0x80072390,
        0x80072398,
        0x80072BB4,
        0x80072BBC,
        0x80072BC8,
    ],
)
def test_all_flag_consumer_bytes_bind_the_actual_executable(owned, at):
    p, _, exe, _, sources, bound, _, rooms = owned
    changed = bytearray(exe)
    changed[at - 0x80010000 + 0x800] ^= 1
    substituted = replace(
        bound, entry_resources=replace(bound.entry_resources, executable=bytes(changed))
    )
    assert (
        normal_engine_positive_prefix(sources["00-05"], rooms["00-05"], p, substituted)
        is PositivePrefixFailure.Binding
    )


def test_native_windows_and_both_owned_actor_code_pools(owned):
    _, _, exe, resources, _, _, _, _ = owned
    for at, width, digest in PICKUP_NATIVE_WINDOWS:
        assert hashlib.sha256(native_bytes(exe, at, width)).hexdigest() == digest
    for at, word in [
        (0x800518CC, 0x90820007),
        (0x800518D4, 0x30420001),
        (0x80072388, 0x92030007),
        (0x80072390, 0x30620080),
        (0x80072398, 0x30620060),
        (0x80072BB4, 0x92230007),
        (0x80072BBC, 0x30620080),
        (0x80072BC8, 0x30650060),
    ]:
        assert int.from_bytes(native_bytes(exe, at, 4), "little") == word
    archive = resources["PL0/PLD/CDEMD0.EMS"]
    for index, base, sector, width, digest in ACTOR_STATE_IMAGES:
        assert struct.unpack("<2I", native_bytes(exe, 0x8009ADF4 + index * 8, 8)) == (
            sector,
            width,
        )
        code = archive[sector * 2048 : sector * 2048 + width]
        assert hashlib.sha256(code).hexdigest() == digest
        for table, selector, offset in [
            (0xC830, 1, 0x114C),
            (0xC854, 0, 0x118C),
            (0xC88C, 13, 0x4920),
            (0xC8CC, 13, 0x4928),
        ]:
            assert (
                struct.unpack_from("<I", code, table + selector * 4)[0] == base + offset
            )
        assert code[0x4920:0x4928] == bytes.fromhex("0800e00300000000")
        assert int.from_bytes(code[0x4988:0x498C], "little") == 0xAE300004


@pytest.mark.parametrize("flag", [0, 1, 0xA0, 0xA1, 0x80, 2])
def test_packet_predicate_defaults_and_old_explicit_flags_stay_narrow(owned, flag):
    packet = bytearray(owned[4]["00-05"][4616:4638])
    packet[21] = flag
    assert direct_pickup_packet(bytes(packet)) is (flag == 0)
    assert direct_pickup_packet(bytes(packet), pickup_flags=frozenset((0, 1))) is (
        flag in (0, 1)
    )
    assert direct_pickup_packet(
        bytes(packet), pickup_flags=frozenset((0, 1, 0xA0))
    ) is (flag in (0, 1, 0xA0))


@pytest.mark.parametrize(
    "fault", ["length", "width", "height", "amount", "kind", "sat", "four-point"]
)
def test_a0_retains_every_other_packet_requirement(owned, fault):
    packet = bytearray(owned[4]["00-05"][4616:4638])
    if fault == "length":
        del packet[-1]
    else:
        at, value = {
            "width": (10, b"\0\0"),
            "height": (12, b"\0\0"),
            "amount": (16, b"\0\0"),
            "kind": (2, b"\x05"),
            "sat": (3, b"\0"),
            "four-point": (3, b"\xb1"),
        }[fault]
        packet[at : at + len(value)] = value
    assert not direct_pickup_packet(bytes(packet), pickup_flags=frozenset((0, 1, 0xA0)))


@pytest.mark.parametrize(
    "key,gids",
    [
        ("00-0f", {139, 38}),
        ("00-18", {161}),
        ("01-03", {35}),
        ("01-07", {148, 167}),
        ("01-0a", {33}),
        ("01-0c", {170}),
    ],
)
def test_generator_rebinding_accepts_derived_fields_and_preserves_raw_inputs(
    owned, key, gids
):
    p, _, _, _, sources, bound, entry, raw_rooms = owned
    catalog = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    generated = next(r for r in catalog["rooms"] if r["id"] == key)
    # Final catalogs omit executable programs. Restore actual owned decoder
    # inputs and retain the generated fields used between compiler passes.
    room = copy.deepcopy(raw_rooms[key])
    room.update({k: v for k, v in generated.items() if k not in OWNED_SOURCE_FIELDS})
    prefix = normal_engine_positive_prefix(sources[key], room, p, bound)
    assert type(prefix) is VerifiedNormalEnginePositivePrefix
    result = known_declared_items_from_prefix(
        sources[key], room, p, entry, script_item_dispatch(p), prefix
    )
    assert {r.global_id for r in result.direct_pickups} == gids
    # The raw semantic lists remain bound even after generated-field changes.
    changed = copy.deepcopy(room)
    changed["items"][0]["global_id"] ^= 1
    assert isinstance(
        normal_engine_positive_prefix(sources[key], changed, p, bound),
        PositivePrefixFailure,
    )


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-05"], indirect=True)
def test_current_departed_reentry_and_complete_earlier_image_restore(
    snapshot, tmp_path
):
    from types import SimpleNamespace

    import test_re2_tracking
    from test_live_items import RamReader

    from tracker.visit_history import HistoryIdentity, VisitHistory

    p, current_ram, _, _ = snapshot
    departed, departed_ram, _, _ = test_re2_tracking.snapshot.__wrapped__(
        SimpleNamespace(param="00-17"), p
    )
    p = replace(p, rooms=departed.rooms)
    ram = bytearray(current_ram)
    read = RamReader(ram).read_memory
    bank = p.flag_banks[p.runtime_layout["item_bank_early"]][0]
    address, mask = msb_flag_location(bank, 4)
    offset = address & 0x1FFFFF
    registry = int(p.runtime_layout["aot_table_address_ps1"], 0) & 0x1FFFFF
    source = p.rooms["00-05"]
    definition = source["items"][0]
    assert definition["global_id"] == 4
    pointer = 0x80100000 + definition["offset"] + 2
    tracker = Tracker()
    regions = {
        f"{a['id']}:{r['id']}": set(r["room_ids"])
        for a in p.map_layout.document["areas"]
        for r in a["rooms"]
    }
    history_id = HistoryIdentity(
        p.profile_id, p.runtime_signature.concatenated_sha256, "synthetic-a0"
    )
    earlier = None
    for current, acquired, enabled in [
        (True, False, False),
        (False, False, False),
        (True, False, True),
        (False, True, False),
        (True, True, False),
        (False, False, False),
    ]:
        ram[:] = current_ram if current else departed_ram
        word = int.from_bytes(ram[offset : offset + 4], "little")
        ram[offset : offset + 4] = (word | mask if acquired else word & ~mask).to_bytes(
            4, "little"
        )
        if current:
            if acquired:
                ram[registry + 8 : registry + 12] = bytes(4)
            else:
                ram[(pointer & 0x1FFFFF) + 1] = 0x31 if enabled else 0
                ram[(pointer & 0x1FFFFF) + 19] = 0xA0
        if not current and not acquired and earlier is None:
            earlier = bytes(ram)
        assert poll_re2(p, tracker, read).status is PollStatus.Display
        record = tracker.rooms["00-05"]
        assert record.items[0].state == (
            "taken"
            if acquired
            else "available"
            if current and enabled
            else "uncollected"
        )
        assert record.completion is (
            RoomCompletion.Cleared if acquired else RoomCompletion.Incomplete
        )
        assert set(tracker.rooms) == (
            {"00-05"} if earlier is None else {"00-05", "00-17"}
        )
        history = VisitHistory(tmp_path / "a0.json", history_id, regions, False)
        history.save(tracker)
        history.close()
        history = VisitHistory(tmp_path / "a0.json", history_id, regions, False)
        fresh = history.restore()
        history.close()
        assert all(not r.items for r in fresh.rooms.values()) and not fresh.doors
        assert poll_re2(p, fresh, read).status is PollStatus.Display
        assert fresh == tracker
    before = copy.deepcopy(tracker)
    ram[:] = earlier
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker == before


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-17"], indirect=True)
@pytest.mark.parametrize("bank,bit", [(1, 0), (1, 1), (1, 6), (0, 25)])
def test_all_historical_context_contradictions_withhold_a0_presence(
    snapshot, bank, bit
):
    p, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 5))
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker.rooms["00-05"].items[0].state == "uncollected"
    address, mask = msb_flag_location(p.flag_banks[bank][0], bit)
    original = int.from_bytes(read(address, 4).data, "little")
    put(address, original ^ mask, 4)
    before = copy.deepcopy(tracker)
    assert poll_re2(p, tracker, read).status is (
        PollStatus.UnsupportedSettings if bank == 0 else PollStatus.WrongGame
    )
    assert tracker == before
    put(address, original, 4)
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    assert tracker == before


@pytest.mark.parametrize("profile", ["re2_leon_a_slus00748"], indirect=True)
@pytest.mark.parametrize("snapshot", ["00-17"], indirect=True)
@pytest.mark.parametrize("fault", ["failed", "short", "incoherent"])
def test_a0_failed_or_incoherent_reads_never_partially_publish(snapshot, fault):
    from emulator.duckstation_gdb import MemRead

    p, _, put, read = snapshot
    tracker = Tracker()
    tracker.mark_current(RoomId(0, 5))
    assert poll_re2(p, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)
    address, mask = msb_flag_location(
        p.flag_banks[p.runtime_layout["item_bank_early"]][0], 4
    )
    changed = False

    def broken(at, width):
        nonlocal changed
        value = read(at, width)
        if at <= address < at + width:
            if fault == "failed":
                return MemRead(False, b"", "test disconnect")
            if fault == "short":
                return MemRead(True, value.data[:-1])
            if not changed:
                original = int.from_bytes(read(address, 4).data, "little")
                put(address, original ^ mask, 4)
                changed = True
        return value

    result = poll_re2(p, tracker, broken)
    assert result.status is (
        PollStatus.Retry if fault == "incoherent" else PollStatus.ReadFailure
    )
    assert tracker == before


def test_all_125_owned_factory_and_public_query_outcomes(owned):
    from dataclasses import asdict
    from enum import Enum

    p, _, _, _, sources, bound, entry, rooms = owned
    pin = json.loads((ROOT / "tests/fixtures/re2/pickup-a0-census.json").read_text())
    results = {}
    accepted = 0
    for key, room in rooms.items():
        prefix = normal_engine_positive_prefix(sources[key], room, p, bound)
        if isinstance(prefix, Enum):
            factory, query = (
                {"failure": type(prefix).__name__ + "." + prefix.name},
                None,
            )
        else:
            accepted += 1
            factory = {
                "entries": sorted(prefix.entry_locations),
                "programs": sorted(prefix.protected_programs),
            }
            query = known_declared_items_from_prefix(
                sources[key], room, p, entry, script_item_dispatch(p), prefix
            )
            query = (
                {"failure": type(query).__name__ + "." + query.name}
                if isinstance(query, Enum)
                else asdict(query)
            )
        results[key] = {"factory": factory, "query": query}
    assert len(results) == pin["sources"] == 125
    assert accepted == pin["accepted_factories"] == 35
    assert (
        hashlib.sha256(
            json.dumps(results, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == pin["factory_query_sha256"]
    )
