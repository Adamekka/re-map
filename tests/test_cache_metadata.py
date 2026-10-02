"""RE1-CACHE-002/003: complete source paths and relevant nested guards are mandatory."""

import hashlib
import struct
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from build_cache_metadata import scan_cache_rdt


def source(init_code: bytes, main_code: bytes, event: bytes) -> bytes:
    init = (len(init_code) + 2).to_bytes(2, "little") + init_code + bytes(2)
    main = (len(main_code) + 2).to_bytes(2, "little") + main_code + bytes(2)
    rdt = bytearray(0x100 + len(init) + len(main) + len(event))
    offsets = [0] * 19
    offsets[6:10] = [0x100, 0x100 + len(init), 0x100 + len(init) + len(main), len(rdt)]
    struct.pack_into("<19I", rdt, 0x48, *offsets)
    rdt[0x100 : offsets[7]] = init
    rdt[offsets[7] : offsets[8]] = main
    rdt[offsets[8] :] = event
    return bytes(rdt)


@pytest.fixture
def profile():
    return {
        "cache_audits": [],
        "script_flag_bases": [hex(0x80001000 + group * 0x100) for group in range(10)],
        "cache_context_dependencies": [
            {"address_ps1": "0x80000100", "width": 4, "mask": "0x00800000"},
            {"address_ps1": "0x80000209", "width": 1, "mask": "0xFF"},
        ],
    }


def pickup(slot: int, item_type: int, gid: int) -> bytes:
    item = bytearray(26)
    item[0:2] = bytes((0x18, slot))
    item[10] = item_type
    item[22] = gid
    return bytes(item)


def indexed_event(code: bytes) -> bytes:
    return bytes((8, 0, 0, 0, 0, 0, 0, 0)) + code


def test_both_item_branches_and_word_boundaries_become_dependencies(profile):
    # Each branch chooses a pickup descriptor. Changing either predicate must invalidate reuse.
    yes = bytes((4, 2, 0, 0, 4, 2, 31, 1)) + pickup(5, 0x15, 111)
    no = bytes((4, 2, 32, 0, 4, 2, 63, 1)) + pickup(5, 0x15, 112)
    code = (
        bytes((1, len(yes) + 2))
        + yes
        + bytes((2, len(no) + 2))
        + no
        + bytes((3, 0, 0, 0))
    )
    row = scan_cache_rdt(
        source(code, bytes((0, 0)), bytes(4)), "PSX/STAGE1/ROOM1091.RDT", profile
    )

    assert row["cache_complete"]
    assert len(row["flag_tests"]) == 4
    assert row["dependencies"] == [
        {"address_ps1": "0x80000102", "width": 1, "mask": 128},
        {"address_ps1": "0x80000209", "width": 1, "mask": 255},
        {"address_ps1": "0x80001200", "width": 1, "mask": 1},
        {"address_ps1": "0x80001203", "width": 1, "mask": 128},
        {"address_ps1": "0x80001204", "width": 1, "mask": 1},
        {"address_ps1": "0x80001207", "width": 1, "mask": 128},
    ]
    assert row["item_global_ids"] == [111, 112]


@pytest.mark.parametrize(
    ("code", "event", "reason"),
    [
        (bytes((0, 0)), bytes((1, 0, 0, 0)), "indexed event scripts"),
        (
            bytes((1, 30, 6, 2, 0, 0)) + pickup(5, 0x15, 111) + bytes((0, 0)),
            bytes(4),
            "room-local comparison",
        ),
        (
            bytes((1, 30, 4, 10, 0, 0)) + pickup(5, 0x15, 111) + bytes((0, 0)),
            bytes(4),
            "unknown flag group 10",
        ),
        (bytes((1, 255, 0, 0)), bytes(4), "branch outside procedure"),
        (
            bytes((0x0D, 0)) + bytes(8) + bytes((4,)) + bytes(9),
            bytes(4),
            "unclassified generic AOT handler 4",
        ),
        (
            bytes((0x0D, 0)) + bytes(8) + bytes((15,)) + bytes(9),
            bytes(4),
            "unclassified generic AOT handler 15",
        ),
        (bytes((0x14, 0, 0, 0, 0, 0)), bytes(4), "event creation index outside table"),
        (
            pickup(5, 0x15, 111) + bytes((0x4C, 3, 5, 0, 0, 0)),
            bytes(4),
            "item quantity transfer",
        ),
    ],
)
def test_unresolved_paths_never_authorize_prior_room_cache(
    profile, code, event, reason
):
    row = scan_cache_rdt(
        source(code, bytes((0, 0)), event), "PSX/STAGE1/ROOM1091.RDT", profile
    )

    assert not row["cache_complete"]
    assert reason in row["reason"]
    assert len(row["init_sha256"]) == len(row["main_sha256"]) == 64


def test_unrelated_camera_or_entity_conditions_do_not_invalidate_items(profile):
    code = (
        pickup(5, 0x15, 111)
        + bytes((1, 12, 6, 2, 0, 0, 0x0F))
        + bytes(7)
        + bytes((3, 0, 0, 0))
    )
    event = indexed_event(bytes((1, 0x83, 0x18, 0, 0, 0, 0, 0, 0x80, 0xFF)))
    row = scan_cache_rdt(
        source(code, bytes((0, 0)), event), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["cache_complete"]
    assert row["item_global_ids"] == [111]
    assert len(row["dependencies"]) == 2


@pytest.mark.parametrize("section", ["main", "events"])
def test_closed_nested_camera_branch_does_not_guard_a_later_item_update(
    profile, section
):
    # RE1-CACHE-003: a failed camera test exits only the inner IF, before this update.
    camera = bytes((1, 10, 6, 2, 0, 0, 0x2F, 1, 2, 3, 3, 0))
    body = bytes((4, 1, 0, 1)) + camera + bytes((0x13, 5, 4, 0x81))
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    block = (len(code) + 2).to_bytes(2, "little") + code + bytes(2)
    event = indexed_event(bytes((6, len(block) + 2)) + block + bytes((0xFF,)))
    row = scan_cache_rdt(
        source(
            pickup(5, 0x15, 111) + bytes((0,)),
            code if section == "main" else bytes((0,)),
            event if section == "events" else bytes(4),
        ),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["stats"] == {"init": "clean", "main": "clean", "events": "clean"}
    assert row["cache_complete"]
    assert row["dependencies"] == [
        {"address_ps1": "0x80000102", "width": 1, "mask": 128},
        {"address_ps1": "0x80000209", "width": 1, "mask": 255},
        {"address_ps1": "0x80001103", "width": 1, "mask": 128},
    ]


def test_closed_nested_camera_branch_does_not_guard_a_later_door_initializer(profile):
    camera = bytes((1, 10, 6, 2, 0, 0, 0x2F, 1, 2, 3, 3, 0))
    door = bytes((0x0C, 0)) + bytes(24)
    body = bytes((4, 1, 0, 1)) + camera + door
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    row = scan_cache_rdt(
        source(code, bytes((0,)), bytes(4)), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["cache_complete"] and row["door_cache_complete"]
    assert {"address_ps1": "0x80001103", "width": 1, "mask": 128} in row["dependencies"]


def test_closed_nested_flag_branch_does_not_add_an_unrelated_dependency(profile):
    nested = bytes((1, 10, 4, 2, 40, 1, 0x2F, 1, 2, 3, 3, 0))
    body = bytes((4, 1, 0, 1)) + nested + bytes((0x13, 5, 4, 0x81))
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0,)), code, bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["cache_complete"]
    assert {"address_ps1": "0x80001103", "width": 1, "mask": 128} in row["dependencies"]
    assert {"address_ps1": "0x80001206", "width": 1, "mask": 128} not in row[
        "dependencies"
    ]


def test_item_update_retains_all_active_parent_and_nested_flag_guards(profile):
    camera = bytes((1, 10, 6, 2, 0, 0, 0x2F, 1, 2, 3, 3, 0))
    child_body = bytes((4, 2, 40, 1)) + camera + bytes((0x13, 5, 4, 0x81))
    child = bytes((1, len(child_body) + 2)) + child_body + bytes((3, 0))
    body = bytes((4, 1, 0, 1)) + child
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0,)), code, bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["cache_complete"]
    assert row["dependencies"] == [
        {"address_ps1": "0x80000102", "width": 1, "mask": 128},
        {"address_ps1": "0x80000209", "width": 1, "mask": 255},
        {"address_ps1": "0x80001103", "width": 1, "mask": 128},
        {"address_ps1": "0x80001206", "width": 1, "mask": 128},
    ]


def test_nested_procedure_end_keeps_its_condition_for_a_later_item_update(profile):
    # True ends the whole procedure; false pops only the inner IF and reaches the update.
    nested = bytes((1, 6, 4, 2, 40, 1, 0, 0))
    body = bytes((4, 1, 0, 1)) + nested + bytes((0x13, 5, 4, 0x81))
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0,)), code, bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["stats"] == {"init": "clean", "main": "clean", "events": "clean"}
    assert row["cache_complete"]
    assert {"address_ps1": "0x80001206", "width": 1, "mask": 128} in row["dependencies"]


@pytest.mark.parametrize("alternate", [False, True])
def test_nested_camera_condition_still_blocks_items_in_either_arm(profile, alternate):
    update = bytes((0x13, 5, 4, 0x81))
    yes = bytes((6, 2, 0, 0)) + (bytes((0x2F, 1, 2, 3)) if alternate else update)
    no = update if alternate else bytes((0x2F, 1, 2, 3))
    nested = bytes((1, len(yes) + 2)) + yes + bytes((2, len(no) + 2)) + no
    body = bytes((4, 1, 0, 1)) + nested
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0,)), code, bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert not row["cache_complete"]
    assert "room-local comparison field 2" in row["reason"]


def test_condition_in_nested_else_keeps_the_parent_skip_target(profile):
    # ELSE/failing THEN pops the inner IF. A failing test in ELSE exits the parent IF.
    yes = bytes((4, 2, 40, 1, 0x2F, 1, 2, 3))
    no = bytes((6, 2, 0, 0, 0x2F, 1, 2, 3))
    nested = bytes((1, len(yes) + 2)) + yes + bytes((2, len(no) + 2)) + no
    body = bytes((4, 1, 0, 1)) + nested + bytes((0x13, 5, 4, 0x81))
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0,)), code, bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert not row["cache_complete"]
    assert "room-local comparison field 2" in row["reason"]
    assert {"address_ps1": "0x80001206", "width": 1, "mask": 128} in row["dependencies"]


@pytest.mark.parametrize("door", [False, True])
def test_top_level_else_condition_can_block_a_later_initializer(profile, door):
    yes = bytes((4, 1, 0, 1, 0x2F, 1, 2, 3))
    no = bytes((6, 2, 0, 0, 0x2F, 1, 2, 3))
    branch = bytes((1, len(yes) + 2)) + yes + bytes((2, len(no) + 2)) + no
    initializer = bytes((0x0C, 0)) + bytes(24) if door else pickup(5, 0x15, 111)
    row = scan_cache_rdt(
        source(branch + initializer + bytes((0,)), bytes((0,)), bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["stats"] == {"init": "clean", "main": "clean", "events": "clean"}
    assert not row["door_cache_complete" if door else "cache_complete"]
    assert "room-local" in row["door_cache_reason" if door else "reason"]
    assert {"address_ps1": "0x80001103", "width": 1, "mask": 128} in row["dependencies"]


@pytest.mark.parametrize("door", [False, True])
def test_else_condition_keeps_an_initializer_in_its_own_arm_unresolved(profile, door):
    yes = bytes((4, 1, 0, 1, 0x2F, 1, 2, 3))
    initializer = bytes((0x0C, 0)) + bytes(24) if door else pickup(5, 0x15, 111)
    no = bytes((6, 2, 0, 0)) + initializer
    branch = bytes((1, len(yes) + 2)) + yes + bytes((2, len(no) + 2)) + no
    row = scan_cache_rdt(
        source(branch + bytes((0,)), bytes((0,)), bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["stats"] == {"init": "clean", "main": "clean", "events": "clean"}
    assert not row["door_cache_complete" if door else "cache_complete"]
    assert "room-local" in row["door_cache_reason" if door else "reason"]


def test_nested_else_test_can_select_the_parent_else_item_update(profile):
    nested_yes = bytes((4, 2, 40, 1, 0x2F, 1, 2, 3))
    nested_no = bytes((6, 2, 0, 0, 0x2F, 1, 2, 3))
    nested = (
        bytes((1, len(nested_yes) + 2))
        + nested_yes
        + bytes((2, len(nested_no) + 2))
        + nested_no
    )
    yes = bytes((4, 1, 0, 1)) + nested
    no = bytes((0x13, 5, 4, 0x81))
    code = bytes((1, len(yes) + 2)) + yes + bytes((2, len(no) + 2)) + no + bytes((0,))
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0,)), code, bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["stats"] == {"init": "clean", "main": "clean", "events": "clean"}
    assert not row["cache_complete"]
    assert "room-local comparison field 2" in row["reason"]
    assert {"address_ps1": "0x80001103", "width": 1, "mask": 128} in row["dependencies"]
    assert {"address_ps1": "0x80001206", "width": 1, "mask": 128} in row["dependencies"]


def test_closed_nested_condition_does_not_disguise_an_unguarded_item_update(profile):
    camera = bytes((1, 10, 6, 2, 0, 0, 0x2F, 1, 2, 3, 3, 0))
    body = camera + bytes((0x13, 5, 4, 0x81))
    code = bytes((1, len(body) + 2)) + body + bytes((3, 0, 0))
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0,)), code, bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert not row["cache_complete"]
    assert "unguarded item interaction update" in row["reason"]
    assert "room-local comparison" not in row["reason"]


def test_event_manifest_guard_and_creation_guard_are_dependencies(profile):
    embedded = bytes((1, 8, 4, 1, 40, 1, 0x13, 5, 4, 0, 3, 0, 0, 0))
    block = (len(embedded) + 2).to_bytes(2, "little") + embedded + bytes(2)
    event = indexed_event(bytes((6, len(block) + 2)) + block + bytes((0xFF,)))
    init = pickup(5, 0x15, 111) + bytes((1, 8, 4, 2, 20, 1, 0x14, 0, 0, 0, 3, 0, 0, 0))
    row = scan_cache_rdt(
        source(init, bytes((0, 0)), event), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["cache_complete"]
    assert {entry["address_ps1"] for entry in row["dependencies"]} >= {
        "0x80001106",
        "0x80001201",
    }


@pytest.mark.parametrize("initialized", [True, False])
def test_event_award_requires_a_source_item_descriptor(profile, initialized):
    init = pickup(5, 0x15, 111) + bytes((0, 0)) if initialized else bytes((0, 0))
    event = indexed_event(bytes((7, 6, 0x2D, 5, 4, 0, 0xFF)))
    row = scan_cache_rdt(
        source(init, bytes((0, 0)), event), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["cache_complete"] is initialized
    if not initialized:
        assert "award has no item initializer" in row["reason"]


@pytest.mark.parametrize("opcode", [0x12, 0x13])
def test_unguarded_main_item_update_never_reuses_a_captured_manifest(profile, opcode):
    update = bytes((opcode, 5, 0, 0))
    if opcode == 0x12:
        update += bytes(6)
    row = scan_cache_rdt(
        source(pickup(5, 0x15, 111) + bytes((0, 0)), update + bytes((0, 0)), bytes(4)),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert not row["cache_complete"]
    assert "unguarded item interaction update" in row["reason"]


def test_collected_absent_normal_items_remain_in_manifest_but_documents_do_not(profile):
    init = pickup(5, 0x15, 111) + pickup(6, 0x54, 112) + bytes((0, 0))
    row = scan_cache_rdt(
        source(init, bytes((0, 0)), bytes(4)), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["cache_complete"]
    assert row["item_global_ids"] == [111]
    assert row["item_aot_ids"] == [5]


def test_event_door_update_does_not_authorize_cached_raw_doors(profile):
    door = bytes((0x0C, 0)) + bytes(24)
    event = indexed_event(bytes((7, 6, 0x13, 0, 0, 0, 0xFF)))
    row = scan_cache_rdt(
        source(door + bytes((0, 0)), bytes((0, 0)), event),
        "PSX/STAGE1/ROOM1091.RDT",
        profile,
    )
    assert row["cache_complete"]
    assert not row["door_cache_complete"]
    assert "door interaction update outside init" in row["door_cache_reason"]


def test_initial_door_branch_records_global_dependencies(profile):
    door = bytes((0x0C, 0)) + bytes(24)
    init = bytes((1, 30, 4, 2, 40, 0)) + door + bytes((3, 0, 0, 0))
    row = scan_cache_rdt(
        source(init, bytes((0, 0)), bytes(4)), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["cache_complete"] and row["door_cache_complete"]
    assert {"address_ps1": "0x80001206", "width": 1, "mask": 128} in row["dependencies"]


def test_unknown_event_path_disables_items_and_doors(profile):
    # State 0's default is a proven stop. State 1's default does not advance,
    # so it still provides the unsupported flow this coverage test requires.
    event = indexed_event(bytes((1, 0x0F, 0xFF)))
    row = scan_cache_rdt(
        source(bytes((0, 0)), bytes((0, 0)), event), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert not row["cache_complete"] and not row["door_cache_complete"]


def test_required_profile_dependency_config_is_not_defaulted():
    with pytest.raises(KeyError, match="script_flag_bases"):
        scan_cache_rdt(bytes(0x100), "PSX/STAGE1/ROOM1091.RDT", {})


def test_only_proven_source_mutations_are_identified(profile):
    item = bytearray(pickup(5, 0x15, 111))
    item[24:26] = bytes((1, 0x84))
    init = bytes(item) + bytes((0x4C, 1, 5, 12, 0, 0))
    row = scan_cache_rdt(
        source(init, bytes((0, 0)), bytes(4)), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["mutable_fields"] == [
        {
            "section": "init",
            "offset": 26,
            "width": 2,
            "kind": "item-parameter-mask",
            "original": 0x8401,
        },
        {
            "section": "init",
            "offset": 13,
            "width": 1,
            "kind": "item-quantity",
            "original": 0,
        },
    ]
    assert not row["cache_complete"]


def test_parameter_fields_already_masked_are_still_declared(profile):
    init = pickup(5, 0x15, 111) + pickup(6, 0x15, 112) + bytes((0, 0))
    row = scan_cache_rdt(
        source(init, bytes((0, 0)), bytes(4)), "PSX/STAGE1/ROOM1091.RDT", profile
    )
    assert row["mutable_fields"] == [
        {
            "section": "init",
            "offset": 26,
            "width": 2,
            "kind": "item-parameter-mask",
            "original": 0,
        },
        {
            "section": "init",
            "offset": 52,
            "width": 2,
            "kind": "item-parameter-mask",
            "original": 0,
        },
    ]


@pytest.mark.parametrize("valid_hash", [True, False])
def test_manual_item_audit_is_bound_to_source_and_never_overrides_door_failure(
    profile, valid_hash
):
    rdt = source(bytes((0, 0)), bytes((0, 0)), bytes((1, 0, 0, 0)))
    profile["cache_audits"] = [
        {
            "source_rdt": "PSX/STAGE1/ROOM1091.RDT",
            "source_sha256": hashlib.sha256(rdt).hexdigest()
            if valid_hash
            else "0" * 64,
            "research_ids": ["SYNTHETIC-TEST"],
            "reason": "Explicit test-only audit",
        }
    ]
    if not valid_hash:
        with pytest.raises(ValueError, match="source hash mismatch"):
            scan_cache_rdt(rdt, "PSX/STAGE1/ROOM1091.RDT", profile)
    else:
        row = scan_cache_rdt(rdt, "PSX/STAGE1/ROOM1091.RDT", profile)
        assert row["cache_complete"]
        assert not row["door_cache_complete"]
        assert row["cache_audit_references"] == ["SYNTHETIC-TEST"]
