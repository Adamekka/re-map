"""RE1-CLEAR-006: player-placed replacements are not room rewards."""

import json
from dataclasses import replace

import pytest
from test_live_items import REPO, RamReader, fixture_ram
from track import PollStatus, poll_once

from games.game_profile import RoomId
from games.re1.re1_profile import Re1Profile
from tracker.exploration_state import RoomCompletion, Tracker

pytest_plugins = ("test_puzzle_items",)


@pytest.mark.parametrize("stage", [0, 5])
@pytest.mark.parametrize("drop_cache", [False, True])
def test_pinned_exchanges_clear_and_original_pickups_rewind(
    tmp_path, stage, drop_cache
):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    bar, living, dining = RoomId(stage, 0x0F), RoomId(stage, 0x16), RoomId(stage, 5)
    tracker.mark_current(bar)
    tracker.mark_current(living)
    tracker.mark_current(dining)
    # These substitutions replay acquisition states through the actual room
    # programs. They do not claim a newly performed in-game exchange.
    for collected, placed in (
        (False, False),
        (True, True),
        (True, False),
        (False, True),
    ):
        for item_type, gid in (
            (3, 0),
            (35, 7),
            (32, 21),
            (45, 31),
            (53, 33),
            (31, 42),
            (33, 44),
        ):
            flag = profile.runtime_room_layout.acquisition.flag(item_type, gid)
            offset = flag.address - 0x80000000
            ram[offset] = (
                ram[offset] & ~flag.mask if collected else ram[offset] | flag.mask
            )
        for item_type, gid in ((28, 1), (31, 20), (32, 43)):
            flag = profile.runtime_room_layout.acquisition.flag(item_type, gid)
            offset = flag.address - 0x80000000
            ram[offset] = (
                ram[offset] | flag.mask if placed else ram[offset] & ~flag.mask
            )
        if drop_cache:
            profile.room_observations.clear()
            profile.room_reentry_evaluations.clear()
        result = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert result.status is PollStatus.Display, result.text
        for room, labels in (
            (bar, ["Gold Emblem", "Music Notes"]),
            (living, ["Shotgun"]),
        ):
            record = tracker.room_state(room)
            assert record.list_complete
            assert record.completion is (
                RoomCompletion.Cleared if collected else RoomCompletion.Incomplete
            )
            assert [item.label for item in record.items] == labels
        record = tracker.room_state(dining)
        assert record.list_complete
        assert record.completion is (
            RoomCompletion.Cleared if collected else RoomCompletion.Incomplete
        )
        assert not any(item.label == "Gold Emblem" for item in record.items)
        assert set(tracker.rooms) == {str(bar), str(living), str(dining), "00-09"}


def test_live_player_placed_policy_keeps_observed_acquisition(dormant_room):
    profile, ram = dormant_room
    # Classify this fixture's Herb explicitly to check the shared policy with
    # an unrelated identity, without changing production revision metadata.
    profile.player_placed_items = frozenset({(0x44, 111)})
    tracker = Tracker()
    room = RoomId(0, 9)
    for handler, remaining in ((0, True), (4, True), (0, False), (4, True)):
        ram[0xB819C] = handler
        ram[0xC86EA] = ram[0xC86EA] | 1 if remaining else ram[0xC86EA] & ~1
        before = bytes(ram)
        result = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert result.status is PollStatus.Display, result.text
        record = tracker.room_state(room)
        assert record.completion is RoomCompletion.Cleared
        assert record.items == ()
        assert bytes(ram) == before
        observed = profile.room_observations[room].observation.items
        if remaining:
            assert len(observed) == 1
            assert observed[0].state.value == (
                "available" if handler == 4 else "uncollected"
            )
        else:
            assert all(item.state.value == "taken" for item in observed)


def test_placed_items_do_not_hide_unresolved_source_coverage(dormant_room):
    profile, ram = dormant_room
    profile.player_placed_items = frozenset({(0x44, 111)})
    name = "PSX/STAGE1/ROOM1091.RDT"
    profile.room_programs[name] = replace(
        profile.room_programs[name], coverage_complete=False
    )
    tracker = Tracker()
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status is PollStatus.Display, result.text
    assert tracker.room_state(RoomId(0, 9)).completion is RoomCompletion.Unknown


def test_original_emblem_and_broken_shotgun_still_count(tmp_path):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    # Select the source-established Broken Shotgun alternative in the Storeroom.
    # The branch change is synthetic and does not establish Chris support.
    ram[0xC3006] |= 2
    tracker = Tracker()
    dining, storeroom = RoomId(0, 5), RoomId(0, 0x18)
    tracker.mark_current(dining)
    tracker.mark_current(storeroom)
    for item_type, gid in ((31, 42), (28, 48)):
        flag = profile.runtime_room_layout.acquisition.flag(item_type, gid)
        ram[flag.address - 0x80000000] |= flag.mask
    result = poll_once(profile, tracker, RamReader(ram).read_memory)
    assert result.status is PollStatus.Display, result.text
    for room, label in ((dining, "Wood Emblem"), (storeroom, "Broken Shotgun")):
        record = tracker.room_state(room)
        assert record.completion is RoomCompletion.Incomplete
        assert any(
            item.label == label and item.state in ("available", "uncollected")
            for item in record.items
        )


@pytest.mark.parametrize("drop_cache", [False, True])
def test_placed_red_book_keeps_original_and_ribbon_required(tmp_path, drop_cache):
    profile = Re1Profile.load(REPO / "profiles/re1_directors_cut_slus00551.json")
    ram = fixture_ram("slus00551_green_herb_before.sav", tmp_path)
    tracker = Tracker()
    rec_room, room003 = RoomId(3, 1), RoomId(3, 0x0A)
    tracker.mark_current(rec_room)
    tracker.mark_current(room003)
    # Replay independent acquisition reversals through the pinned programs.
    # The placed book's flag must never replace the original pickup or ribbon.
    for original_taken, ribbon_taken, placed_remaining in (
        (False, True, True),
        (True, False, True),
        (True, True, True),
        (True, True, False),
        (False, True, False),
    ):
        for item_type, gid, collected in (
            (62, 99, original_taken),
            (12, 165, True),
            (47, 120, ribbon_taken),
            (62, 255, not placed_remaining),
        ):
            flag = profile.runtime_room_layout.acquisition.flag(item_type, gid)
            offset = flag.address - 0x80000000
            ram[offset] = (
                ram[offset] & ~flag.mask if collected else ram[offset] | flag.mask
            )
        if drop_cache:
            profile.room_observations.clear()
            profile.room_reentry_evaluations.clear()
        before = bytes(ram)
        result = poll_once(profile, tracker, RamReader(ram).read_memory)
        assert result.status is PollStatus.Display, result.text
        assert bytes(ram) == before
        record = tracker.room_state(room003)
        assert record.list_complete
        assert [item.label for item in record.items] == ["Ink Ribbon"]
        assert record.completion is (
            RoomCompletion.Cleared if ribbon_taken else RoomCompletion.Incomplete
        )
        original = tracker.room_state(rec_room)
        assert original.list_complete
        assert original.items[0].label == "Red Book"
        assert (original.items[0].state == "taken") is original_taken
        assert original.completion is (
            RoomCompletion.Cleared if original_taken else RoomCompletion.Incomplete
        )
        assert set(tracker.rooms) == {"03-01", "03-0a", "00-09"}


@pytest.mark.parametrize(
    "value", [None, [[28]], [[True, 1]], [[28, 256]], [[28, 1], [28, 1]]]
)
def test_profile_rejects_invalid_placed_item_metadata(tmp_path, value):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    raw["player_placed_items"] = value
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="player-placed"):
        Re1Profile.load(path)


def test_runtime_profile_requires_explicit_placed_item_policy(tmp_path):
    raw = json.loads((REPO / "profiles/re1_directors_cut_slus00551.json").read_text())
    del raw["player_placed_items"]
    path = tmp_path / "missing.json"
    path.write_text(json.dumps(raw))
    with pytest.raises(KeyError, match="player_placed_items"):
        Re1Profile.load(path)
