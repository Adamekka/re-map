"""Explicit observed-source RE2 publication, independent of private RAM files."""

import hashlib
import json
import sys
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from games.re2.re2_profile import Re2Profile
from ui.map_view import map_page


def readme_publication(path: Path) -> dict:
    fixture = json.loads(path.read_text())
    assert fixture["schema"] == 1
    assert fixture["profile"] == "profiles/re2_leon_a_slus00748.json"
    state = fixture["state"]
    assert (
        hashlib.sha256(
            json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        == fixture["publication_sha256"]
    )
    assert (
        set(fixture["visits"]["rooms"])
        == {row["observed_current"] for row in fixture["inputs"]}
        == {"03-08", "03-0a"}
    )
    assert {
        area + ":" + visit["id"]: visit["room"]
        for area, visits in state["explored_areas"].items()
        for visit in visits
    } == fixture["visits"]["regions"]
    profile = Re2Profile.load(ROOT / fixture["profile"])
    for area, visits in state["explored_areas"].items():
        for visit in visits:
            assert (
                visit["room"]
                in profile.map_layout.regions[area, visit["id"]]["room_ids"]
            )
    return {
        "document": map_page(
            profile.map_layout.document, UUID("8bca9147-e543-455f-95ae-fbb38aca75d2")
        ).decode(),
        **fixture,
    }


def test_readme_publication_contains_only_observed_visits():
    readme_publication(ROOT / "tests/fixtures/re2/readme-map.json")


if __name__ == "__main__":
    assert len(sys.argv) == 2, "Pass the explicit RE2 publication fixture JSON"
    print(json.dumps(readme_publication(Path(sys.argv[1]).resolve())))
