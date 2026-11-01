"""A local finite music receipt still checks every source Copy."""

import pytest
from test_re2_initializer_control import config as config
from test_re2_initializer_control import initializer_body, music
from test_re2_initializer_control import profile as profile
from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES
from test_re2_room_write_partitions import CONFIG, END, source

from games.re2.initializer_control_proof import (
    InitializerControlFailure,
    InitializerControlProof,
    initializer_control_proof,
)
from games.re2.room_data import decode_room
from games.re2.scenario_items import (
    scenario_effect_pool,
    scenario_flags,
    scenario_item_proofs,
)


def test_scoped_music_does_not_authorize_an_unrelated_music_bank(config, profile):
    data, _, _ = source(
        END,
        (initializer_body() + END, initializer_body() + music(mode=2) + END),
        [],
        [0],
    )
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 0
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Music
    )
    proof = initializer_control_proof(
        data, room, config, CONFIG, program_scope=frozenset({"17:0"})
    )
    assert isinstance(proof, InitializerControlProof)
    assert proof.program_scope == frozenset({"17:0"})
    assert {key for key, _ in proof.fallthrough_locations} == {"17:0"}
    assert {key for key, _ in proof.predicate_copy_locations} == {"17:0"}
    assert {key for key, _, _ in proof.switch_edges} == {"17:0"}
    assert {write.location[0] for write in proof.source_writes} == {"17:0"}
    assert proof.matches_source(data, room["programs"])
    assert not scenario_item_proofs(
        data,
        room,
        scenario_flags(profile),
        profile["flag_banks"],
        scenario_effect_pool(profile),
        initializer_control=proof,
    ).fixed_context_preserved


def test_foreign_procedure_copy_cannot_hide_behind_program_scope(config):
    data, _, _ = source(END, (initializer_body() + END, b"\x1d\0\0\0" + END), [], [0])
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 0
    assert (
        initializer_control_proof(
            data, room, config, CONFIG, program_scope=frozenset({"17:0"})
        )
        is InitializerControlFailure.Copy
    )


@pytest.mark.parametrize("scope", [frozenset(), frozenset({"17:99"}), "17:0"])
def test_invalid_program_scope_is_an_explicit_failed_receipt(config, scope):
    data, _, _ = source(END, (initializer_body() + END, END), [], [0])
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 0
    assert (
        initializer_control_proof(data, room, config, CONFIG, program_scope=scope)
        is InitializerControlFailure.SourceBinding
    )
