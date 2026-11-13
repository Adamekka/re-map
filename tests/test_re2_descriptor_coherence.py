"""RE2-LIVE-001: overlapping descriptor reads must describe the same header."""

import copy

import pytest
import test_re2_tracking

from emulator.duckstation_gdb import MemRead
from games.re2.live_tracking import poll_re2
from tracker.exploration_state import Tracker
from tracker.polling import PollStatus

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
@pytest.mark.parametrize(
    "snapshot,definitions,four_point",
    [
        ("00-01", "doors", False),
        ("05-08", "doors", True),
        ("00-01", "items", False),
        ("00-08", "items", True),
    ],
    indirect=["snapshot"],
)
@pytest.mark.parametrize("changed_field", ["kind", "geometry", "activation"])
def test_conflicting_descriptor_headers_cannot_publish_or_add_visits(
    snapshot, definitions, four_point, changed_field
):
    profile, _, put, read = snapshot
    source = str(profile.read_current_room(read).room)
    registry = int(profile.runtime_layout["aot_table_address_ps1"], 0)
    room = profile.rooms[source]
    if definitions == "items" and "identity_filtering_items" in room:
        # The generic fixture installs every raw alternative. Keep the baseline
        # compatible with the compiled identity before testing conflicting reads.
        variants = room["identity_filtering_items"]["item_variants"]
        refined_ids = {variant["global_id"] for variant in variants}
        selected_offsets = {at for variant in variants for at in variant["offsets"]}
        for item in room["items"]:
            if item["global_id"] in refined_ids:
                put(registry + item["slot"] * 4, 0, 4)
        for item in room["items"]:
            if item["offset"] in selected_offsets:
                put(registry + item["slot"] * 4, 0x80100000 + item["offset"] + 2, 4)
    definition = next(
        row
        for row in profile.rooms[source][definitions]
        if row["four_point"] is four_point
        and int.from_bytes(read(registry + row["slot"] * 4, 4).data, "little")
        == 0x80100000 + row["offset"] + 2
    )
    pointer = 0x80100000 + definition["offset"] + 2
    tracker = Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    before = copy.deepcopy(tracker)

    def conflicting_read(address, width):
        result = read(address, width)
        if address == pointer and width > 2:
            packet = bytearray(result.data)
            if changed_field == "kind":
                packet[0] = 0
            elif changed_field == "geometry":
                packet[1] ^= 0x80
            else:
                packet[1] = 0
            # Return the same conflicting versions at final rechecks too;
            # independently matching each width cannot establish coherence.
            return MemRead(True, bytes(packet))
        return result

    assert poll_re2(profile, tracker, conflicting_read).status is PollStatus.Retry
    assert tracker == before
    fresh = Tracker()
    assert poll_re2(profile, fresh, conflicting_read).status is PollStatus.Retry
    assert fresh == Tracker()
    assert poll_re2(profile, tracker, read).status is PollStatus.Display
    assert tracker == before
