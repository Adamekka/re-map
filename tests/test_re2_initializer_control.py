"""Synchronous initializer receipts do not broaden unknown script effects."""

import copy
import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re2_metadata import (
    PRESENCE_COUNTERS,
    PRESENCE_FLAGS,
    PRESENCE_WRITES,
    ROOT,
    item_command,
)
from test_re2_room_write_partitions import CONFIG, END, source

from games.re2.clip_effect_proof import clipping_effect_proof
from games.re2.event_presence import source_presence
from games.re2.initializer_control_proof import (
    InitializerControlConfig,
    InitializerControlFailure,
    InitializerControlProof,
    InitializerControlSupport,
    initializer_control_config,
    initializer_control_proof,
)
from games.re2.room_data import collection_presence, decode_room
from games.re2.scenario_items import (
    scenario_effect_pool,
    scenario_flags,
    scenario_item_proofs,
    scenario_presence_flags,
)
from games.re2.startup_effects import (
    StartupEffectAuditSupport,
    StartupEffectReceipt,
    startup_effect_audit,
)


@pytest.fixture
def profile():
    result = json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())
    result["initializer_control_audit"] = {
        "audit": "slus00748-initializer-control-v1",
        "executable_sha256": (
            "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
        ),
        "counter_address_ps1": "0x800D47EC",
        "counter_limit_address_ps1": "0x800D4834",
        "task_address_ps1": "0x800D7860",
        "task_capacity": 14,
        "source_addresses": [{"stage": 0, "address_ps1": "0x8011A6A8"}],
        "music_buffers": [
            {"address_ps1": "0x801F2E00", "limit_address_ps1": "0x80200000"},
            {"address_ps1": "0x801ECE00", "limit_address_ps1": "0x80200000"},
        ],
    }
    return result


@pytest.fixture
def config(profile):
    result = initializer_control_config(profile)
    assert isinstance(result, InitializerControlConfig)
    return result


def music(bank=0, mode=0, program=2, volume=50, pan=64):
    return bytes([0x51, bank, mode, program, volume, pan])


def switch(*bodies, counter=26):
    cases = b"".join(
        bytes([0x14, 0]) + struct.pack("<Hh", len(body) + 2, index) + body + b"\x1a\0"
        for index, body in enumerate(bodies)
    )
    return (
        bytes([0x13, counter]) + struct.pack("<H", len(cases) + 2) + cases + b"\x16\0"
    )


def described(body):
    data, _, _ = source(END, (body + END, END), [], [0])
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 0
    return data, room


def initializer_body(selector=1, delta=4, counter=4):
    packet = bytes([0x1D, counter, delta, selector, 0x23, 0, 26, 5, 0, 0])
    body = packet + switch(music(), music(program=3)) + bytes([0x25, 4, 26, 0])
    return bytes([6, 0]) + struct.pack("<H", len(body) + 2) + body + b"\x08\0"


def test_owned_shape_exports_only_bound_copies_and_switch_skip(config):
    data, room = described(initializer_body())
    proof = initializer_control_proof(data, room, config, CONFIG)
    assert isinstance(proof, InitializerControlProof)
    copy_at = next(
        row["offset"]
        for row in room["programs"]["17:0"]["commands"]
        if row["opcode"] == 0x1D
    )
    opening = next(
        row for row in room["programs"]["17:0"]["commands"] if row["opcode"] == 0x13
    )
    assert proof.rhs_copy_offsets == frozenset({copy_at})
    assert proof.predicate_copy_locations == frozenset({("17:0", copy_at)})
    assert proof.source_writes[0].target_offset == copy_at + 8
    assert proof.source_writes[0].width == 2
    assert proof.switch_edges == (
        (
            "17:0",
            opening["offset"],
            opening["next"] + struct.unpack_from("<H", data, opening["offset"] + 2)[0],
        ),
    )
    assert proof.matches_source(data, room["programs"])
    assert proof.preserves_fixed_words({config.flag_ranges[0][0]: 0xFFFFFFFF})
    assert not proof.preserves_fixed_words({config.task_address: 1})
    altered = copy.deepcopy(room["programs"])
    altered["17:0"]["entry"] += 1
    assert not proof.matches_source(data, altered)
    assert not proof.matches_source(data[:-1] + b"\x01", room["programs"])


@pytest.mark.parametrize(
    "selector,delta,width", [(0, 4, 1), (0, 5, 1), (1, 4, 2), (255, 4, 2)]
)
def test_native_copy_byte_and_nonzero_halfword_forms(config, selector, delta, width):
    data, room = described(initializer_body(selector, delta))
    proof = initializer_control_proof(data, room, config, CONFIG)
    assert isinstance(proof, InitializerControlProof)
    assert proof.source_writes[0].width == width


@pytest.mark.parametrize(
    "selector,delta,counter",
    [(1, 0, 4), (0, 2, 4), (0, 3, 4), (1, 5, 4), (0, 6, 4), (1, 4, 36), (1, 4, 255)],
)
def test_copy_cannot_change_opcode_counter_selector_or_escape_rhs(
    config, selector, delta, counter
):
    data, room = described(initializer_body(selector, delta, counter))
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Copy
    )


def test_every_copy_site_must_have_the_same_safe_numeric_contract(config):
    # The second Copy targets a 32 actor-position operand. Existing actor
    # proofs can handle that class; this receipt deliberately does not inherit it.
    extra = bytes([0x1D, 4, 2, 0, 0x32, 0]) + bytes(6)
    data, room = described(initializer_body() + extra)
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Copy
    )


@pytest.mark.parametrize(
    "bank,mode,program", [(2, 0, 2), (0, 1, 2), (0, 5, 2), (0, 0, 129), (0, 0, 255)]
)
def test_music_cannot_enter_library_control_paths_or_leave_program_table(
    config, bank, mode, program
):
    data, room = described(switch(music(bank, mode, program)))
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Music
    )


@pytest.mark.parametrize("bank,program", [(0, 0), (1, 0), (0, 128), (1, 128)])
def test_music_global_header_and_final_program_are_bounded(config, bank, program):
    data, room = described(
        switch(music(bank=bank, program=program, volume=255, pan=255))
    )
    assert isinstance(
        initializer_control_proof(data, room, config, CONFIG), InitializerControlProof
    )


@pytest.mark.parametrize(
    "fault",
    [
        "case-link",
        "switch-end",
        "break",
        "nested",
        "effect",
        "foreign-target",
        "counter",
    ],
)
def test_switch_is_a_bounded_flat_nonyielding_audio_block(config, fault):
    body = switch(music(), music(program=3))
    if fault in ("case-link", "switch-end"):
        data, room = described(body)
        opening = next(
            row for row in room["programs"]["17:0"]["commands"] if row["opcode"] == 0x13
        )
        data = bytearray(data)
        at = opening["offset"] + (6 if fault == "case-link" else 2)
        struct.pack_into("<H", data, at, 65535)
        data = bytes(data)
        # The normal decoder rejects this first. Rebind its unchanged command
        # spans to also exercise the pure proof boundary on malformed input.
        room["sha256"] = hashlib.sha256(data).hexdigest()
        assert isinstance(
            initializer_control_proof(data, room, config, CONFIG),
            InitializerControlFailure,
        )
        return
    elif fault == "break":
        body = body[:-4] + b"\0\0" + body[-2:]
    elif fault == "nested":
        body = switch(switch(music()))
    elif fault == "effect":
        body = switch(bytes([0x22, 5, 1, 1]))
    elif fault == "foreign-target":
        body = bytes([6, 0, 4, 0]) + body + b"\x08\0"
    else:
        body = switch(music(), counter=36)
    data, room = described(body)
    assert isinstance(
        initializer_control_proof(data, room, config, CONFIG), InitializerControlFailure
    )


@pytest.mark.parametrize("depth", [1, 4])
def test_switch_does_not_inherit_unmodeled_shared_loop_depth(config, depth):
    body = switch(music())
    for _ in range(depth):
        body = b"\x0d\0" + struct.pack("<hH", len(body) + 2, 1) + body + b"\x0e\0"
    data, room = described(body)
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Switch
    )


@pytest.mark.parametrize("depth", [1, 3, 4])
def test_switch_cannot_execute_in_an_unallocated_call_frame(config, depth):
    programs = [bytes([0x18, 2]) + END, END]
    programs.extend(
        bytes([0x18, procedure + 1]) + END
        if procedure < depth + 1
        else switch(music()) + END
        for procedure in range(2, depth + 2)
    )
    data, room, _ = source(END, tuple(programs), [], [0])
    room["stage"] = 0
    proof = initializer_control_proof(data, room, config, CONFIG)
    if depth == 4:
        assert proof is InitializerControlFailure.CallDepth
    else:
        assert isinstance(proof, InitializerControlProof)


@pytest.mark.parametrize(
    "destination,source_index", [(24, 4), (25, 4), (26, 4), (255, 4), (4, 36)]
)
def test_counter_copy_preserves_room_identity_and_uses_bounded_source(
    config, destination, source_index
):
    data, room = described(bytes([0x25, destination, source_index, 0]))
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Counter
    )


@pytest.mark.parametrize("stage", [False, True, "0", None])
def test_source_stage_must_be_an_explicit_integer(config, stage):
    data, room = described(initializer_body())
    room["stage"] = stage
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Stage
    )


def test_source_stage_upper_arena_and_flag_domains_are_explicit(config):
    data, room = described(switch(music()))
    room["stage"] = 1
    assert (
        initializer_control_proof(data, room, config, CONFIG)
        is InitializerControlFailure.Stage
    )
    room["stage"] = 0
    near_music = replace(config, source_addresses=((0, config.music_buffers[1][0]),))
    assert (
        initializer_control_proof(data, room, near_music, CONFIG)
        is InitializerControlFailure.Partition
    )
    alias = replace(
        config,
        flag_ranges=((config.music_buffers[0][0], config.music_buffers[0][0] + 4),),
    )
    assert (
        initializer_control_proof(data, room, alias, CONFIG)
        is InitializerControlFailure.FlagAlias
    )


def test_absent_optin_is_explicitly_unaudited():
    assert initializer_control_config({}) is InitializerControlSupport.Unaudited
    data, room = described(END)
    assert (
        initializer_control_proof(
            data, room, InitializerControlSupport.Unaudited, CONFIG
        )
        is InitializerControlSupport.Unaudited
    )


@pytest.mark.parametrize(
    "fault",
    [
        "null",
        "native-hash",
        "task-capacity",
        "stage-address",
        "counter-origin",
        "counter-window",
        "profile-revision",
    ],
)
def test_audit_drift_fails_startup_instead_of_selecting_a_fallback(profile, fault):
    raw = profile["initializer_control_audit"]
    if fault == "null":
        profile["initializer_control_audit"] = None
    elif fault == "native-hash":
        raw["executable_sha256"] = "0" * 64
    elif fault == "task-capacity":
        raw["task_capacity"] = True
    elif fault == "stage-address":
        raw["source_addresses"][0]["address_ps1"] = "0x8011A000"
    elif fault == "counter-origin":
        profile["runtime_layout"]["script_counter_address_ps1"] = "0x800D47EE"
    elif fault == "counter-window":
        profile["presence_counter_writes"]["limit_address_ps1"] = "0x800D4836"
    else:
        profile["executable_identity"] = "another SHA256 " + "0" * 64
    with pytest.raises(ValueError, match="initializer control"):
        initializer_control_config(profile)


def guarded_pickup_source(profile):
    fixed = scenario_flags(profile)
    guard = fixed[-1]
    item = item_command(20, 15, 9)
    init = (
        bytes([6, 0])
        + struct.pack("<H", len(item) + 6)
        + bytes([0x21, guard["bank"], guard["bit"], guard["expected"]])
        + item
        + b"\x08\0"
        + END
    )
    # Both startup roots must finish. The pickup is in the first root, while
    # SCA and the copied opaque comparison are reached by the second root.
    setup = bytes([0x37, 0, 0x80, 0, 0x24, 4, 0, 0, 0x18, 2]) + END
    data, room, _ = source(init, (setup, END, initializer_body() + END), [], [0])
    room["stage"] = 0
    return data, room, fixed


@pytest.mark.parametrize(
    "control_enabled,startup_enabled",
    [(False, False), (True, False), (False, True), (True, True)],
)
def test_presence_requires_both_shared_setup_and_control_receipts(
    profile, config, control_enabled, startup_enabled
):
    data, room, fixed = guarded_pickup_source(profile)
    control = initializer_control_proof(data, room, config, CONFIG)
    assert isinstance(control, InitializerControlProof)
    proof = scenario_item_proofs(
        data,
        room,
        fixed,
        profile["flag_banks"],
        scenario_effect_pool(profile),
        clipping=clipping_effect_proof(profile),
        startup_audit=startup_effect_audit(profile)
        if startup_enabled
        else StartupEffectAuditSupport.Unaudited,
        initializer_control=control
        if control_enabled
        else InitializerControlSupport.Unaudited,
    )
    assert proof.fixed_context_preserved is control_enabled
    room["fixed_context_preserved"] = proof.fixed_context_preserved
    if not control_enabled:
        assert proof.initializer_control is InitializerControlSupport.Unaudited
        assert proof.startup_effects is StartupEffectAuditSupport.Unaudited
    elif startup_enabled:
        assert isinstance(proof.startup_effects, StartupEffectReceipt)
        assert proof.initializer_control is control
    conditions = scenario_presence_flags(
        PRESENCE_FLAGS, fixed, proof.fixed_context_preserved
    )
    fixed_flags = (
        frozenset((row["bank"], row["bit"], row["expected"]) for row in fixed)
        if proof.fixed_context_preserved
        else frozenset()
    )
    required, conditional = collection_presence(
        data,
        room,
        conditions,
        frozenset(item["offset"] for item in room["items"]),
        fixed_flags,
        startup_effects=proof.startup_effects,
        initializer_control=proof.initializer_control,
    )
    if control_enabled and startup_enabled:
        assert 9 in required or conditional == [
            {"global_id": 9, "presence": {"kind": "required"}}
        ]
    else:
        assert (required, conditional) == ([], [])


def test_query_binding_and_fixed_word_preservation_are_mandatory(profile, config):
    data, room, fixed = guarded_pickup_source(profile)
    control = initializer_control_proof(data, room, config, CONFIG)
    assert isinstance(control, InitializerControlProof)
    altered = replace(
        control, ram_writes=((int(profile["flag_banks"][0]["address_ps1"], 0), 1),)
    )
    proof = scenario_item_proofs(
        data,
        room,
        fixed,
        profile["flag_banks"],
        scenario_effect_pool(profile),
        initializer_control=altered,
    )
    assert not proof.fixed_context_preserved
    target = frozenset({("16:0", room["items"][0]["offset"])})
    with pytest.raises(AssertionError, match="another source"):
        source_presence(
            data + b"\0",
            room["programs"],
            target,
            "startup",
            PRESENCE_FLAGS,
            frozenset(),
            initializer_control=control,
        )
    assert (
        control.for_predicates(
            data, room["programs"], frozenset({(255, 0)}), frozenset()
        )
        is InitializerControlSupport.Unaudited
    )
