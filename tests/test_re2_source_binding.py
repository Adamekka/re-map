"""RE2-SOURCE-001: matching bytes cannot authorize an unaligned room base."""

import copy

import pytest
import test_re2_tracking

from games.game_profile import RoomId
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import Tracker
from tracker.polling import PollStatus

# Register the shared fixtures under the names their dependencies request.
profile = test_re2_tracking.profile
snapshot = test_re2_tracking.snapshot


@pytest.mark.parametrize(
    "profile",
    [
        "re2_leon_a_slus00421",
        "re2_claire_b_slus00592",
        "re2_leon_a_slus00748",
        "re2_claire_b_slus00756",
    ],
    indirect=True,
)
@pytest.mark.parametrize("misalignment", [1, 2, 3])
def test_unaligned_room_base_preserves_publication_and_recovers(snapshot, misalignment):
    profile, ram, put, read = snapshot
    room = profile.rooms["00-01"]
    layout = profile.runtime_layout
    original_base = 0x80100000
    source = bytes(ram[0x100000 : 0x100000 + room["size"]])

    def relocate(base):
        # Rebind every pointer so content mismatches cannot mask the missing
        # base-alignment check. Work ownership remains independently aligned.
        start = base & 0x1FFFFF
        ram[start : start + room["size"]] = source
        put(int(layout["loaded_rdt_address_ps1"], 0), base, 4)
        if "scenario_work_address_ps1" in layout:
            put(
                int(layout["scenario_work_address_ps1"], 0),
                (base + room["section_offsets"][2] + 3) & ~3,
                4,
            )
        for index, offset in enumerate(room["section_offsets"]):
            put(base + 8 + index * 4, base + offset if offset else 0, 4)
        for definition in room["items"] + room["doors"]:
            put(
                int(layout["aot_table_address_ps1"], 0) + definition["slot"] * 4,
                base + definition["offset"] + 2,
                4,
            )

    tracker = Tracker()
    tracker.mark_current(RoomId(0, 0))
    before = copy.deepcopy(tracker)
    relocate(original_base + misalignment)
    result = poll_re2(profile, tracker, read)
    assert result.status is PollStatus.Retry
    assert result.text == "Room source is still loading"
    assert tracker == before

    for base in (original_base + 4, original_base):
        relocate(base)
        assert poll_re2(profile, tracker, read).status is PollStatus.Display
        fresh = Tracker()
        fresh.mark_current(RoomId(0, 0))
        assert poll_re2(profile, fresh, read).status is PollStatus.Display
        assert tracker == fresh
        before = copy.deepcopy(tracker)
        relocate(base + misalignment)
        assert poll_re2(profile, tracker, read).status is PollStatus.Retry
        assert tracker == before
