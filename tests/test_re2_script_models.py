"""Committed RE2 script models and their fresh-game evaluation. RE2-EVAL-001.

These are source and synthetic-state checks, not gameplay confirmation.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from games.re2.re2_profile import Re2Profile  # noqa: E402
from games.re2.script_model import ScriptEvaluationConfig  # noqa: E402
from games.scd_entry import entry_state  # noqa: E402
from games.scd_state import GameState, Support, room_script_state  # noqa: E402

PROFILES = {
    "re2_leon_a_slus00748": ("RE_MAP_RE2_OWNED_CUE", set()),
    # Claire B sets the Claire and second-scenario status bits.
    "re2_claire_b_slus00756": ("RE_MAP_RE2_CLAIRE_OWNED_CUE", {(1, 0), (1, 1)}),
}


def fresh_game(profile: Re2Profile, room: dict, scenario: set) -> GameState:
    def flag(bank: int, bit: int) -> bool | None:
        if bank not in profile.flag_banks:
            return None
        return (bank, bit) in scenario

    # Every script variable starts at zero in a new game.
    return entry_state(
        profile.script_evaluation.entry,
        flag,
        lambda address: 0,
        # A new game starts with an empty inventory.
        lambda item: False,
        room["stage"],
        room["room"],
    )


@pytest.mark.parametrize("profile_id", sorted(PROFILES))
def test_every_source_resolves_from_a_fresh_game(profile_id, script_evaluation):
    profile = Re2Profile.load(ROOT / "profiles" / f"{profile_id}.json")
    evaluation = profile.script_evaluation
    assert isinstance(evaluation, ScriptEvaluationConfig)
    layout = profile.runtime_layout
    unresolved = []
    for key, room in profile.rooms.items():
        bank = (
            layout["item_bank_early"]
            if room["stage"] < layout["item_bank_stage_boundary"]
            else layout["item_bank_late"]
        )
        result = room_script_state(
            evaluation.models[key],
            fresh_game(profile, room, PROFILES[profile_id][1]),
            evaluation.entry.tasks,
            {gid: (bank, gid) for gid in evaluation.item_ids[key]},
        )
        if result.support is not Support.Supported:
            unresolved.append((key, result.reason))
            continue
        unresolved.extend(
            (key, "item", gid)
            for gid, present in result.item_presence.items()
            if present is None
        )
        unresolved.extend(
            (key, "door", creator)
            for creator, verdict in result.doors.items()
            if verdict.sat is None
        )
        unresolved.extend(
            (key, "award", offset)
            for offset, present in result.award_presence.items()
            if present is None
        )
    assert unresolved == []


@pytest.mark.parametrize(
    ("profile_id", "offset", "present"),
    [
        # Entry starts the award's event while bank 1 bit 1 and bank 4 bit 7
        # are clear; Claire B's second-scenario bit is bank 1 bit 1.
        ("re2_leon_a_slus00748", 8944, True),
        ("re2_claire_b_slus00756", 9066, False),
    ],
)
def test_fresh_game_award_follows_its_event_conditions(
    profile_id, offset, present, script_evaluation
):
    profile = Re2Profile.load(ROOT / "profiles" / f"{profile_id}.json")
    evaluation = profile.script_evaluation
    room = profile.rooms["01-02"]
    assert [award["offset"] for award in room["event_awards"]] == [offset]
    result = room_script_state(
        evaluation.models["01-02"],
        fresh_game(profile, room, PROFILES[profile_id][1]),
        evaluation.entry.tasks,
        {gid: (8, gid) for gid in evaluation.item_ids["01-02"]},
    )
    assert result.award_presence == {offset: present}


@pytest.mark.parametrize("profile_id", sorted(PROFILES))
def test_committed_models_match_the_owned_disc(profile_id, tmp_path):
    cue = os.environ.get(PROFILES[profile_id][0])
    if not cue:
        pytest.skip(f"Set {PROFILES[profile_id][0]} to regenerate script models")
    profile_path = ROOT / "profiles" / f"{profile_id}.json"
    output = tmp_path / "models.json"
    subprocess.run(
        [
            sys.executable,
            ROOT / "tools/build_script_models.py",
            cue,
            profile_path,
            output,
        ],
        check=True,
    )
    committed = json.loads(profile_path.read_text())["script_evaluation"]["models_path"]
    assert output.read_bytes() == (profile_path.parent / committed).read_bytes()


def test_loading_rejects_a_catalog_award_without_a_model_row():
    from games.re2.script_model import script_evaluation

    path = ROOT / "profiles" / "re2_claire_b_slus00756.json"
    rooms = Re2Profile.load(path).rooms
    [award] = rooms["01-02"]["event_awards"]
    moved = {
        **rooms,
        "01-02": {
            **rooms["01-02"],
            "event_awards": [{**award, "offset": award["next"]}],
        },
    }
    raw = json.loads(path.read_text())
    assert script_evaluation(raw, path, rooms) is not None
    with pytest.raises(ValueError, match="omit a catalog award"):
        script_evaluation(raw, path, moved)
