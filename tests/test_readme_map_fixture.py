"""Replay the README's explicit Jill captures without an emulator or user history."""

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
from tracker.exploration_state import Tracker
from ui.map_view import map_page, map_state


def replay_readme_map(fixture_path: Path) -> dict:
    fixture = json.loads(fixture_path.read_text())
    assert fixture["schema"] == 1
    manifest_path = REPO / fixture["manifest"]
    manifest = json.loads(manifest_path.read_text())
    sources = {entry["path"]: entry for entry in manifest["files"]}
    profile_path = REPO / fixture["profile"]
    catalog_path = REPO / fixture["catalog"]
    inputs = {fixture_path, manifest_path, profile_path, catalog_path}
    for capture in fixture["captures"]:
        entry = sources[capture["path"]]
        assert entry["kind"] == "duckstation-savestate"
        assert "Training Jill" in entry["description"], entry["path"]
        source = REPO / entry["path"]
        assert source.stat().st_size == entry["bytes"], entry["path"]
        assert hashlib.sha256(source.read_bytes()).hexdigest() == entry["sha256"]
        inputs.add(source)
    before = {str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs}
    tracker = Tracker()
    observed = {}
    with tempfile.TemporaryDirectory(prefix="re-map-readme-ram-") as temporary:
        ram_path = Path(temporary) / "ram.bin"
        for capture in fixture["captures"]:
            subprocess.run(
                [
                    sys.executable,
                    str(REPO / "tools/extract_sav_ram.py"),
                    str(REPO / capture["path"]),
                    str(ram_path),
                ],
                check=True,
                capture_output=True,
            )
            # A new profile discards prior runtime observations. Every room's
            # item/door verdict must come from this capture's fresh game flags.
            profile = Re1Profile.load(profile_path)
            result = poll_once(
                profile, tracker, RamReader(bytearray(ram_path.read_bytes())).read_memory
            )
            assert result.status is PollStatus.Display, result.text
            assert str(tracker.current) == capture["room"]
            assert tracker.current_region == capture["region"]
            observed[capture["region"]] = capture["room"]
            assert tracker.region_visits == observed
            assert set(tracker.rooms) == set(observed.values())
    visits = {"rooms": sorted(tracker.rooms), "regions": dict(sorted(observed.items()))}
    assert visits == fixture["visits"]
    state = map_state(tracker)
    publication_sha256 = hashlib.sha256(
        json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    assert publication_sha256 == fixture["publication_sha256"], publication_sha256
    assert profile.map_layout is not None
    catalog = profile.map_layout.document
    assert catalog == json.loads(catalog_path.read_text())
    assert catalog["executable_identity"] == (
        "SLUS_005.51 SHA256 " + manifest["game"]["executable_sha256"]
    )
    # The instance ID is fixed only in this offline fixture, so rerenders have
    # identical HTML and response headers without a running map server.
    document = map_page(catalog, UUID("1e4c9486-2856-4e99-8524-e9c96367bf3a")).decode()
    assert map_state(tracker) == state
    assert tracker.region_visits == visits["regions"]
    assert sorted(tracker.rooms) == visits["rooms"]
    assert before == {
        str(path): hashlib.sha256(path.read_bytes()).hexdigest() for path in inputs
    }
    return {
        "document": document,
        "state": state,
        "visits": visits,
        "publication_sha256": publication_sha256,
        "inputs_sha256": before,
    }


def test_readme_replay_reverses_pickups_without_inventing_visits():
    result = replay_readme_map(REPO / "tests/fixtures/re1/readme-map.json")
    rooms = {
        visit["room"]: visit
        for visits in result["state"]["explored_areas"].values()
        for visit in visits
    }
    # These captures first observe collection, then restore an earlier state.
    # Visits remain, but no earlier Collected verdict may survive that restore.
    assert set(rooms) == set(result["visits"]["rooms"])
    assert all(visit["items_complete"] for visit in rooms.values())
    assert all(
        item["state"] == "available"
        for visit in rooms.values()
        for item in visit["items"]
    )


if __name__ == "__main__":
    assert len(sys.argv) == 2, "Pass the explicit README render fixture JSON"
    print(json.dumps(replay_readme_map(Path(sys.argv[1]).resolve())))
