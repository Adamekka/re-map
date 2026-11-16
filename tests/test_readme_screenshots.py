"""Replay the README screenshot savestate over a synthetic exploration history."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from uuid import UUID

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "src"), str(REPO / "tools")]

from test_live_items import RamReader

from games.re1.re1_profile import Re1Profile
from track import PollStatus, poll_once
from tracker.exploration_state import RoomCompletion, RoomRecord, Tracker
from ui.map_view import map_page, map_state


def replay_readme_screenshots(fixture_path: Path) -> dict:
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1
    manifest = json.loads((REPO / fixture["manifest"]).read_text())
    capture = fixture["capture"]
    entry = next(e for e in manifest["files"] if e["path"] == capture["path"])
    assert entry["kind"] == "duckstation-savestate"
    source = REPO / capture["path"]
    assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
    catalog = json.loads((REPO / fixture["catalog"]).read_text())
    areas = [
        area for area in catalog["areas"] if area["id"] in fixture["explored_areas"]
    ]
    assert [area["id"] for area in areas] == fixture["explored_areas"]
    # A player entering every room of these floors before the capture. Each
    # region records its first-visit room; items and doors come only from the
    # capture's game flags, as after a tracker restart.
    regions = {
        f"{area['id']}:{room['id']}": room["room_ids"][0]
        for area in areas
        for room in area["rooms"]
    }
    tracker = Tracker(
        rooms={
            room: RoomRecord(visited=True, completion=RoomCompletion.Unknown)
            for room in regions.values()
        },
        region_visits=dict(regions),
    )
    profile = Re1Profile.load(REPO / fixture["profile"])
    with tempfile.TemporaryDirectory(prefix="re-map-readme-ram-") as temporary:
        ram_path = Path(temporary) / "ram.bin"
        subprocess.run(
            [
                sys.executable,
                str(REPO / "tools/extract_sav_ram.py"),
                str(source),
                str(ram_path),
            ],
            check=True,
            capture_output=True,
        )
        result = poll_once(
            profile, tracker, RamReader(bytearray(ram_path.read_bytes())).read_memory
        )
    assert result.status is PollStatus.Display, result.text
    assert str(tracker.current) == capture["room"]
    assert tracker.current_region == capture["region"]
    assert tracker.region_visits.keys() == regions.keys()
    assert profile.map_layout is not None
    # The instance ID is fixed only in this offline fixture, so rerenders have
    # identical HTML and response headers without a running map server.
    document = map_page(
        profile.map_layout.document, UUID("1e4c9486-2856-4e99-8524-e9c96367bf3a")
    ).decode()
    return {"document": document, "state": map_state(tracker)}


def test_readme_screenshots_show_capture_state_on_seeded_floors():
    fixture_path = REPO / "tests/fixtures/re1/readme-screenshots.json"
    fixture = json.loads(fixture_path.read_text())
    state = replay_readme_screenshots(fixture_path)["state"]
    assert set(state["explored_areas"]) == set(fixture["explored_areas"])
    visits = [visit for visits in state["explored_areas"].values() for visit in visits]
    # The scene must show both kinds of progress the README describes.
    assert {"CLEARED", "INCOMPLETE"} <= {visit["state"] for visit in visits}
    for shot in fixture["screenshots"]:
        if shot["view"] == "inspect":
            assert shot["room"] in {visit["room"] for visit in visits}


if __name__ == "__main__":
    assert len(sys.argv) == 2, "Pass the README screenshot fixture JSON"
    print(json.dumps(replay_readme_screenshots(Path(sys.argv[1]).resolve())))
