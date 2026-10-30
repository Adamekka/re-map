"""Positive puzzle-target knowledge must not become access or absence proof."""

import copy
import json
import struct
from pathlib import Path

import pytest
from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES
from test_re2_room_write_partitions import END, md1, source

from games.re2.known_puzzle_items import (
    KnownDeclaredItemFailure,
    KnownDeclaredItems,
    known_declared_items,
)
from games.re2.room_data import decode_room
from games.re2.room_entry_contract import (
    RoomEntryContractConfig,
    VerifiedRoomEntryContract,
    room_entry_contract,
)
from games.re2.room_write_partitions import RoomWritePartitionConfig
from games.re2.script_dispatch_items import script_item_dispatch
from games.re2.startup_declarations import StartupDeclarationSupport


def puzzle_items(data, room, profile, receipt, dispatch):
    # These tests isolate the puzzle projection. Direct pickup selection has
    # separate tests with an explicitly bound routing/declaration receipt.
    compiled = known_declared_items(
        data, room, profile, receipt, dispatch, StartupDeclarationSupport.Unaudited
    )
    return (
        compiled.puzzle_items if isinstance(compiled, KnownDeclaredItems) else compiled
    )


@pytest.fixture
def profile():
    return json.loads(
        (
            Path(__file__).resolve().parents[1] / "profiles/re2_leon_a_slus00748.json"
        ).read_text()
    )


@pytest.fixture
def receipt(profile):
    # This explicit test receipt exercises source reasoning. The separate
    # resource-binder suite verifies every byte needed to obtain one in use.
    config = room_entry_contract(profile)
    assert isinstance(config, RoomEntryContractConfig)
    return VerifiedRoomEntryContract(
        config=config,
        audit=config.audit,
        executable_sha256=config.executable_sha256,
        minimum_source_address=0x8011A000,
        source_addresses=((0, 0x8011A6A8), (1, 0x8011A65C)),
        stages=frozenset({0, 1}),
        roots=config.roots,
        door_models=frozenset(door.model for door in config.doors),
        non_scheduling_interaction_kinds=frozenset(
            config.non_scheduling_interaction_kinds
        ),
        constructor_presets=frozenset(config.constructor_presets),
        actor_code_images=config.actor_codes,
        write_partitions=RoomWritePartitionConfig(
            0x800CE558, 32, 0x800D0324, 32, 256, 64
        ),
    )


def item(slot=9, item_type=89, gid=93, amount=2):
    packet = bytearray(22)
    packet[:4] = bytes((0x4E, slot, 2, 0x31))
    struct.pack_into("<4H", packet, 6, 15948, 9485, 1, 1)
    struct.pack_into("<3H", packet, 14, item_type, amount, gid)
    packet[20] = 255
    return bytes(packet)


def callback(procedure=2, sat=0x31):
    packet = bytearray(20)
    packet[:4] = bytes((0x2C, 10, 5, sat))
    struct.pack_into("<2H", packet, 10, 1000, 1000)
    packet[14:] = bytes((255, 0, 0x18, procedure, 0, 0))
    return bytes(packet)


def conditional(bank, bit, expected, body):
    return (
        bytes((6, 0))
        + struct.pack("<H", 4 + len(body) + 2)
        + bytes((0x21, bank, bit, expected))
        + body
        + b"\x08\0"
    )


def delivery(prefix=b"", slot=9):
    return (
        prefix + conditional(4, 72, 1, conditional(8, 93, 0, bytes((0x47, slot)))) + END
    )


def compile_source(profile, receipt, init, main, models=(), cameras=(0,)):
    data, room, _ = source(init, main, models, cameras)
    room["stage"] = 1
    return puzzle_items(data, room, profile, receipt, script_item_dispatch(profile))


def test_declared_player_callback_target_is_known_before_its_puzzle_guard(
    profile, receipt
):
    opaque_tail = bytes((0x54,)) + bytes(21) + END
    result = compile_source(
        profile, receipt, item() + END, (callback() + opaque_tail, END, delivery())
    )
    assert isinstance(result, tuple) and len(result) == 1
    proof = result[0]
    assert (proof.global_id, proof.item_type) == (93, 89)
    assert (
        len(proof.creator_offsets)
        == len(proof.callback_offsets)
        == len(proof.delivery_offsets)
        == 1
    )
    assert proof.context_conditions == []
    assert not hasattr(proof, "amount")
    assert not hasattr(proof, "cleared")


def test_declaration_cannot_use_a_fifth_native_call_frame(profile, receipt):
    # A native depth-four IF aliases its own pointer field. Both symbolic
    # branches containing an item cannot establish an actual startup fact.
    leaf = conditional(4, 72, 1, item()) + item() + END
    result = compile_source(
        profile,
        receipt,
        bytes((0x18, 3)) + END,
        (
            callback() + END,
            END,
            delivery(),
            bytes((0x18, 4)) + END,
            bytes((0x18, 5)) + END,
            bytes((0x18, 6)) + END,
            leaf,
        ),
    )
    assert result is KnownDeclaredItemFailure.Prefix


def test_only_a_leading_mode_return_guard_is_a_historical_entry_requirement(
    profile, receipt
):
    init = conditional(1, 6, 1, END) + item() + END
    proof = compile_source(
        profile,
        receipt,
        init,
        (conditional(1, 6, 1, END) + callback() + END, END, delivery()),
    )[0]
    assert proof.context_conditions == [
        {"kind": "conditions", "any_of": [[{"bank": 1, "bit": 6, "expected": 0}]]}
    ]


@pytest.mark.parametrize(
    "effect",
    [
        b"\x04\xff\x18\x02",
        b"\x6f\x05",
        bytes((0x54,)) + bytes(21),
        bytes((0x44,)) + bytes(21),
    ],
)
def test_opposite_entry_mode_must_have_a_closed_native_effect_set(
    profile, receipt, effect
):
    init = conditional(1, 6, 1, END) + item() + END
    main = (conditional(1, 6, 1, effect + END) + callback() + END, END, delivery())
    assert (
        compile_source(profile, receipt, init, main)
        is KnownDeclaredItemFailure.NativeContract
    )


@pytest.mark.parametrize("model,lock", [(13, 0), (8, 0), (13, 0x80)])
def test_opposite_entry_door_stops_at_the_audited_transition_boundary(
    profile, receipt, model, lock
):
    door = bytearray(32)
    door[:4] = bytes((0x3B, 1, 1, 0x31))
    door[26], door[29] = model, lock
    init = conditional(1, 6, 1, END) + item() + END
    main = (conditional(1, 6, 1, bytes(door) + END) + callback() + END, END, delivery())
    result = compile_source(profile, receipt, init, main)
    assert (
        len(result) == 1
        if (model, lock) == (13, 0)
        else result is KnownDeclaredItemFailure.NativeContract
    )


@pytest.mark.parametrize(
    "case", ["both-languages", "first-choice", "second-choice", "missing-second"]
)
def test_opposite_mode_nonchoice_message_binds_both_owned_language_resources(
    profile, receipt, case
):
    message = bytes((0x2C, 11, 4, 0x31)) + bytes(10) + struct.pack("<3H", 0, 0, 0xFFFF)
    init = conditional(1, 6, 1, END) + item() + END
    main = (conditional(1, 6, 1, message + END) + callback() + END, END, delivery())
    data, room, layout = source(init, main, (), (0,))
    data = bytearray(data)
    floor = layout["floor"]
    text = b"\x02\0A\xfe\0\0\0\0"
    data[floor:floor] = text * 2
    struct.pack_into("<I", data, 8 + 2 * 4, floor + 16)
    struct.pack_into("<I", data, 8 + 13 * 4, floor)
    struct.pack_into(
        "<I", data, 8 + 14 * 4, 0 if case == "missing-second" else floor + 8
    )
    if case == "first-choice":
        data[floor + 2] = 0xF7
    elif case == "second-choice":
        data[floor + 10] = 0xF8
    room = decode_room(
        bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    result = puzzle_items(
        bytes(data), room, profile, receipt, script_item_dispatch(profile)
    )
    assert (
        len(result) == 1
        if case == "both-languages"
        else result is KnownDeclaredItemFailure.NativeContract
    )


def test_alternate_quantity_declarations_share_knowledge_without_variant_selection(
    profile, receipt
):
    init = conditional(4, 7, 1, item(amount=1)) + item(amount=2) + END
    result = compile_source(profile, receipt, init, (callback() + END, END, delivery()))
    assert len(result) == 1 and len(result[0].creator_offsets) == 2


@pytest.mark.parametrize(
    "case",
    [
        "orphan-item",
        "orphan-callback",
        "other-scenario",
        "yield-before-callback",
        "unsupported-before-callback",
        "wrong-target",
        "inactive-callback",
        "empty-callback-rectangle",
        "mutable-guard",
        "unfinished-first-root",
    ],
)
def test_catalog_or_opaque_reference_alone_does_not_establish_knowledge(
    profile, receipt, case
):
    init, main = item() + END, [callback() + END, END, delivery()]
    if case == "orphan-item":
        init = END
        main.append(item() + END)
    elif case == "orphan-callback":
        main[0] = END
        main.append(callback() + END)
    elif case == "other-scenario":
        main[0] = conditional(1, 1, 1, callback()) + END
    elif case == "yield-before-callback":
        main[0] = b"\x02" + main[0]
    elif case == "unsupported-before-callback":
        main[0] = bytes((0x54,)) + bytes(21) + main[0]
    elif case == "wrong-target":
        main[2] = delivery(slot=8)
    elif case == "inactive-callback":
        main[0] = callback(sat=0) + END
    elif case == "empty-callback-rectangle":
        main[0] = callback()[:10] + bytes(4) + callback()[14:] + END
    elif case == "mutable-guard":
        main[0] = conditional(4, 7, 1, callback()) + END
    else:
        init = item() + bytes((0x54,)) + bytes(21) + END
    assert compile_source(profile, receipt, init, main) == ()


@pytest.mark.parametrize(
    "case",
    [
        "different-type",
        "different-id",
        "other-slot-type",
        "door",
        "generic",
        "reset-type",
        "other-slot-reset-type",
        "reset-geometry",
    ],
)
def test_target_identity_and_binding_aliases_withhold_knowledge(profile, receipt, case):
    if case == "different-type":
        alias = item(item_type=90)
    elif case == "different-id":
        alias = item(gid=94)
    elif case == "other-slot-type":
        alias = item(slot=8, item_type=90)
    elif case == "door":
        alias = bytes((0x3B, 9, 1, 0x31)) + bytes(28)
    elif case == "generic":
        alias = bytes((0x2C, 9, 4, 0x31)) + bytes(16)
    elif case == "reset-type":
        alias = bytes((0x46, 9, 2, 0x31)) + struct.pack("<3H", 90, 2, 93)
    elif case == "other-slot-reset-type":
        alias = bytes((0x46, 8, 2, 0x31)) + struct.pack("<3H", 90, 2, 93)
    else:
        alias = bytes((0x46, 9, 2, 0xB1)) + struct.pack("<3H", 89, 2, 93)
    assert (
        compile_source(
            profile,
            receipt,
            item() + END,
            (callback() + END, END, delivery(), alias + END),
        )
        == ()
    )


def test_same_identity_reset_is_a_puzzle_activation_relationship(profile, receipt):
    reset = bytes((0x46, 9, 2, 0x31)) + struct.pack("<3H", 89, 1, 93)
    result = compile_source(
        profile, receipt, item() + END, (callback() + END, END, delivery(), reset + END)
    )
    assert len(result) == 1


def test_prefix_flags_may_not_rewrite_enforced_entry_settings(profile, receipt):
    result = compile_source(
        profile,
        receipt,
        b"\x22\x01\x01\0" + item() + END,
        (callback() + END, END, delivery()),
    )
    assert result is KnownDeclaredItemFailure.SourceMutation


@pytest.mark.parametrize(
    "kind", ["flag", "flag-alias", "interaction", "wrapped-interaction"]
)
def test_later_fixed_mode_writers_cannot_authorize_a_skipped_historical_declaration(
    profile, receipt, kind
):
    profile = copy.deepcopy(profile)
    if kind == "flag-alias":
        profile["flag_banks"].append(
            {
                "bank": 99,
                "address_ps1": f"0x{int(profile['flag_banks'][1]['address_ps1'], 0) - 4:08X}",
                "width": 8,
            }
        )
        writer = bytes((0x22, 99, 33, 0))
    elif kind in ("interaction", "wrapped-interaction"):
        writer = (
            bytes((0x2C, 11, 6, 0x31))
            + bytes(10)
            + struct.pack("<3H", 1, 257 if kind == "wrapped-interaction" else 1, 0)
        )
    else:
        writer = bytes((0x22, 1, 1, 0))
    init = conditional(1, 1, 0, item()) + END
    result = compile_source(
        profile, receipt, init, (callback() + END, writer + END, delivery())
    )
    assert result is KnownDeclaredItemFailure.SourceMutation


def test_native_flag_setter_outside_reader_bank_width_is_checked_by_physical_mask(
    profile, receipt
):
    # This is the Main Hall setter's bank/index. Its native word lies beyond
    # the bounded reader's bank10 width, but is disjoint from the mode words.
    writer = bytes((0x2C, 11, 6, 0x31)) + bytes(10) + struct.pack("<3H", 10, 71, 1)
    result = compile_source(
        profile, receipt, writer + item() + END, (callback() + END, END, delivery())
    )
    assert len(result) == 1


@pytest.mark.parametrize(
    "case", ["fresh", "repeated-slot", "work-uninitialized", "position-before-work"]
)
def test_prefix_object_effects_require_fresh_owned_records(profile, receipt, case):
    obj = bytearray(38)
    obj[:2] = bytes((0x2D, 0))
    obj[10], obj[12] = 10, 16
    work, position = b"\x2e\x04\0", b"\x32\0" + bytes(6)
    extra = bytes(obj)
    if case == "repeated-slot":
        extra += bytes(obj)
    elif case == "work-uninitialized":
        work = b"\x2e\x04\x01"
    elif case == "position-before-work":
        work = b""
    result = compile_source(
        profile,
        receipt,
        item() + extra + END,
        (work + position + callback() + END, END, delivery()),
        (md1(1, 1),),
    )
    assert bool(result) if case == "fresh" else result == ()


@pytest.mark.parametrize(
    "case",
    [
        "camera-match",
        "camera-number-only",
        "saved-stop-write",
        "scheduler-stop-write",
        "system-write",
        "acquisition-write",
        "native-sleep",
        "malformed-sleep",
    ],
)
def test_callback_effects_are_bounded_before_the_delivery_reference(
    profile, receipt, case
):
    prefixes = {
        "camera-match": b"\x29\x03",
        "camera-number-only": b"\x29\x03",
        "saved-stop-write": b"\x22\x02\x07\x01",
        "scheduler-stop-write": b"\x22\x02\x06\x01",
        "system-write": b"\x22\x00\x16\x01",
        "acquisition-write": b"\x22\x08\x5d\x01",
        "native-sleep": b"\x09\x0a\x1e\0",
        "malformed-sleep": b"\x09\x0b\x1e\0",
    }
    cameras = (0,) if case == "camera-number-only" else (0, 3)
    result = compile_source(
        profile,
        receipt,
        item() + END,
        (callback() + END, END, delivery(prefixes[case])),
        cameras=cameras,
    )
    assert len(result) == (
        0
        if case
        in (
            "camera-number-only",
            "acquisition-write",
            "malformed-sleep",
            "scheduler-stop-write",
            "system-write",
        )
        else 1
    )


def test_copy_cannot_redirect_the_declared_identity(profile, receipt):
    # Copy's target is the following item's type halfword.
    init = bytes((0x1D, 0, 14, 1)) + item() + END
    result = compile_source(profile, receipt, init, (callback() + END, END, delivery()))
    assert result is KnownDeclaredItemFailure.SourceMutation


@pytest.mark.parametrize("target", ["aot-slot", "cut-camera", "object-mode"])
def test_copy_cannot_change_any_operand_used_by_the_positive_proof(
    profile, receipt, target
):
    copy_packet = bytes((0x1D, 0, 0, 0))
    models, cameras = (), (0, 3)
    if target == "object-mode":
        obj = bytearray(38)
        obj[:2] = bytes((0x2D, 0))
        obj[10], obj[12] = 10, 16
        # The writer is in the other enforced scenario, but its fixed target
        # still may not rewrite an operand consumed by this proof.
        init = (
            conditional(1, 6, 1, END) + item() + conditional(1, 6, 1, copy_packet) + END
        )
        main = (
            conditional(1, 6, 1, END) + bytes(obj) + callback() + END,
            END,
            delivery(),
        )
        models = (md1(1, 1),)
    else:
        init = item() + END
        main = (
            callback(procedure=3) + END,
            END,
            copy_packet + END,
            delivery(b"\x29\x03"),
        )
    data, room, _ = source(init, main, models, cameras)
    writer = next(
        row
        for program in room["programs"].values()
        for row in program["commands"]
        if row["opcode"] == 0x1D
    )
    opcode, operand = {
        "aot-slot": (0x47, 1),
        "cut-camera": (0x29, 1),
        "object-mode": (0x2D, 6),
    }[target]
    destination = (
        next(
            row
            for program in room["programs"].values()
            for row in program["commands"]
            if row["opcode"] == opcode
        )["offset"]
        + operand
    )
    assert 0 <= destination - writer["next"] <= 255
    changed = bytearray(data)
    changed[writer["offset"] + 2] = destination - writer["next"]
    room = decode_room(
        bytes(changed), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    assert (
        puzzle_items(
            bytes(changed), room, profile, receipt, script_item_dispatch(profile)
        )
        is KnownDeclaredItemFailure.SourceMutation
    )


def test_unrelated_later_numeric_camera_copy_does_not_erase_known_target(
    profile, receipt
):
    later = bytes((0x1D, 0, 2, 1, 0x6D, 0, 0, 0)) + END
    result = compile_source(
        profile, receipt, item() + END, (callback() + END, END, delivery(), later)
    )
    assert len(result) == 1


def test_long_startup_is_a_modeled_analysis_limit(profile, receipt):
    result = compile_source(
        profile, receipt, bytes(300) + item() + END, (callback() + END, END, delivery())
    )
    assert result is KnownDeclaredItemFailure.Prefix


def test_retained_source_may_not_overlap_native_upper_graphics_work(profile, receipt):
    data, _, layout = source(
        item() + END, (callback() + END, END, delivery()), (), (0,)
    )
    data = bytearray(data)
    data[layout["floor"] : layout["floor"]] = bytes(0x90000)
    struct.pack_into("<I", data, 8 + 2 * 4, layout["floor"] + 0x90000)
    room = decode_room(
        bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    assert (
        puzzle_items(bytes(data), room, profile, receipt, script_item_dispatch(profile))
        is KnownDeclaredItemFailure.NativeContract
    )


@pytest.mark.parametrize(
    "case",
    [
        "source-hash",
        "procedure-table",
        "callback-metadata",
        "item-metadata",
        "revision",
        "stage",
    ],
)
def test_exact_source_entry_and_revision_binding_is_mandatory(profile, receipt, case):
    data, room, _ = source(item() + END, (callback() + END, END, delivery()), (), (0,))
    room["stage"] = 1
    if case == "source-hash":
        room["sha256"] = "0" * 64
    elif case == "procedure-table":
        room["programs"]["17:2"]["entry"] += 1
    elif case == "callback-metadata":
        room["programs"]["17:2"]["commands"][0]["target"] += 2
    elif case == "item-metadata":
        room["items"][0]["type"] += 1
    elif case == "revision":
        profile = copy.deepcopy(profile)
        profile["executable_identity"] = "SLUS_007.48 SHA256 " + "0" * 64
    else:
        room["stage"] = 2
    result = puzzle_items(data, room, profile, receipt, script_item_dispatch(profile))
    assert isinstance(result, KnownDeclaredItemFailure)


def mode_worker_source(worker, frame):
    # The declaration guard lives in the second root. Under the opposite
    # setting only the frame task and its independent worker remain reachable.
    data, room, layout = source(
        END,
        (
            conditional(1, 6, 1, END) + item() + callback() + END,
            frame + END,
            delivery(),
            worker + END,
        ),
        (),
        (0,),
    )
    room["stage"] = 1
    return data, room, layout


def test_second_root_guard_can_establish_a_target_after_first_root_finishes(
    profile, receipt
):
    data, room, _ = mode_worker_source(b"\0", b"\x04\xff\x18\x03")
    result = puzzle_items(data, room, profile, receipt, script_item_dispatch(profile))
    assert len(result) == 1
    assert result[0].context_conditions == [
        {"kind": "conditions", "any_of": [[{"bank": 1, "bit": 6, "expected": 0}]]}
    ]


def test_independent_leading_guards_cannot_be_flipped_together(profile, receipt):
    result = compile_source(
        profile,
        receipt,
        conditional(1, 1, 1, END) + END,
        (conditional(1, 6, 1, END) + item() + callback() + END, END, delivery()),
    )
    assert isinstance(result, KnownDeclaredItemFailure) or result == ()


@pytest.mark.parametrize("predicate", [b"\x23\0\x1a\0\x07\0", b"\x50\x01\0\x10"])
@pytest.mark.parametrize("unsafe", [False, True])
def test_readonly_predicates_keep_both_possible_opposite_branches(
    profile, receipt, predicate, unsafe
):
    body = bytes((0x54,)) + bytes(21) if unsafe else b"\x22\x04\x18\x01"
    worker = b"\x06\0" + struct.pack("<H", len(predicate) + len(body) + 2)
    worker += predicate + body + b"\x08\0"
    data, room, _ = mode_worker_source(worker, b"\x04\xff\x18\x03")
    result = puzzle_items(data, room, profile, receipt, script_item_dispatch(profile))
    assert isinstance(result, KnownDeclaredItemFailure) if unsafe else len(result) == 1


def test_worker_work_selection_survives_a_call_and_return(profile, receipt):
    data, room, _ = source(
        END,
        (
            conditional(1, 6, 1, END) + item() + callback() + END,
            b"\x04\xff\x18\x03" + END,
            delivery(),
            b"\x18\x04\x30" + END,
            b"\x2e\x04\x04" + END,
        ),
        (),
        (0,),
    )
    room["stage"] = 1
    assert (
        len(puzzle_items(data, room, profile, receipt, script_item_dispatch(profile)))
        == 1
    )


@pytest.mark.parametrize(
    "worker,frame",
    [
        (b"\x30", b"\x04\xff\x18\x03"),
        (b"\x30", b"\x2e\x04\x04\x04\xff\x18\x03"),
        (b"\x2e\x03\x04\x30", b"\x04\xff\x18\x03"),
        (b"\x2e\x04\x20\x30", b"\x04\xff\x18\x03"),
        (b"\x2f\x0c\0\0", b"\x04\xff\x18\x03"),
        (b"\x2a", b"\x04\xff\x18\x03"),
        (b"\x04\xff\x18\x03", b"\x04\xff\x18\x03"),
        (b"\0", b"\x04\x02\x18\x03"),
    ],
)
def test_worker_cannot_inherit_unproved_work_or_replace_itself(
    profile, receipt, worker, frame
):
    data, room, _ = mode_worker_source(worker, frame)
    assert isinstance(
        puzzle_items(data, room, profile, receipt, script_item_dispatch(profile)),
        KnownDeclaredItemFailure,
    )


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "missing-work",
        "condition-width",
        "member",
        "tail",
        "call",
        "sleep",
        "nested",
    ],
)
def test_opposite_while_requires_a_balanced_immutable_coordinate_body(
    profile, receipt, case
):
    body = {
        "call": b"\x18\x02",
        "sleep": b"\x09\x0a\x05\0",
        "nested": b"\x0f\x06\x08\0\x3e\0\x0c\x04\0\xfb\x10\0",
    }.get(case, b"\x02\x30\x31\0")
    condition = b"\x3e\0" + bytes((13 if case == "member" else 12, 4)) + b"\0\xfb"
    loop = bytes((0x0F, 4 if case == "condition-width" else 6))
    loop += struct.pack("<h", len(condition) + len(body) + 2) + condition + body
    loop += b"\x10\x01" if case == "tail" else b"\x10\0"
    work = b"" if case == "missing-work" else b"\x2e\x04\x04"
    worker = work + b"\x09\x0a\x05\0" + loop + b"\x34\x0c\xe0\xac\x09\x0a\x0f\0"
    data, room, _ = mode_worker_source(worker, b"\x04\xff\x18\x03")
    result = puzzle_items(data, room, profile, receipt, script_item_dispatch(profile))
    assert (
        len(result) == 1
        if case == "valid"
        else isinstance(result, KnownDeclaredItemFailure)
    )


@pytest.mark.parametrize(
    "target", ["unrelated-bit", "proof-bit", "bank", "operation", "alias"]
)
def test_copied_flag_indices_require_a_disjoint_bank_and_immutable_proof_path(
    profile, receipt, target
):
    # Put an independent later Copy before a flag packet, then re-decode so
    # offsets and source identities remain real input bindings.
    init = item() + END
    later = bytes((0x1D, 0, 2, 0)) + b"\x22\x05\0\x01" + END
    if target == "proof-bit":
        later = bytes((0x1D, 0, 6, 0)) + conditional(5, 0, 1, b"\0") + END
        data, room, _ = mode_worker_source(later[:-2], b"\x04\xff\x18\x03")
    else:
        if target == "bank":
            later = later[:2] + b"\x01" + later[3:]
        elif target == "operation":
            later = later[:2] + b"\x03" + later[3:]
        data, room, _ = source(
            init, (callback() + END, END, delivery(), later), (), (0,)
        )
        room["stage"] = 1
    if target == "alias":
        profile = copy.deepcopy(profile)
        next(row for row in profile["flag_banks"] if row["bank"] == 5)[
            "address_ps1"
        ] = "0x800CFB74"
    result = puzzle_items(data, room, profile, receipt, script_item_dispatch(profile))
    assert (
        len(result) == 1
        if target == "unrelated-bit"
        else isinstance(result, KnownDeclaredItemFailure)
    )


@pytest.mark.parametrize(
    "case", ["valid", "compactor", "unbound-bank", "mutable-resource"]
)
def test_worker_sound_requires_owned_immutable_resources_and_closed_entries(
    profile, receipt, case
):
    worker = (
        b"\x36" + bytes((1 if case == "unbound-bank" else 2, 10, 1, 4, 4)) + bytes(6)
    )
    if case == "compactor":
        worker += b"\x6c\0\0\0"
    if case == "mutable-resource":
        worker = bytes((0x1D, 0, 0, 0)) + worker
    original, original_room, layout = mode_worker_source(worker, b"\x04\xff\x18\x03")
    data = bytearray(original[: layout["floor"]])
    sections = list(struct.unpack_from("<23I", data, 8))
    edt = sections[0] = len(data)
    data.extend(b"\xff" * 192)
    data[edt + 40 : edt + 44] = b"\0\0\x44\0"
    vab = sections[1] = len(data)
    data.extend(bytes(0xC20))
    data[vab : vab + 4] = b"pBAV"
    struct.pack_into("<I", data, vab + 4, 7)
    struct.pack_into("<H", data, vab + 18, 1)
    data[vab + 32] = 16
    sections[2] = len(data)
    # A nonzero compaction directory does not matter when no admitted entry
    # can invoke the compactor. The parser grants no such lifetime permission.
    sections[22] = edt
    data.extend(bytes(32))
    if case == "mutable-resource":
        at = original_room["programs"]["17:3"]["entry"]
        data[at + 2] = edt - (at + 4)
    struct.pack_into("<23I", data, 8, *sections)
    room = decode_room(
        bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    result = puzzle_items(
        bytes(data), room, profile, receipt, script_item_dispatch(profile)
    )
    assert (
        len(result) == 1
        if case == "valid"
        else isinstance(result, KnownDeclaredItemFailure)
    )


@pytest.mark.parametrize(
    "case", ["valid", "missing-owner", "conditional-owner", "choice"]
)
def test_opposite_reset_requires_a_fresh_owner_and_bounded_nonchoice_callback(
    profile, receipt, case
):
    door = bytearray(32)
    door[:4] = b"\x3b\x02\x01\x31"
    door[26] = 13
    reset = b"\x46\x02\x04\x31\0\0\0\0\xff\xff"
    owner = b"" if case == "missing-owner" else bytes(door)
    if case == "conditional-owner":
        owner = conditional(4, 0, 1, owner)
    init = owner + conditional(1, 6, 1, reset) + END
    main = (conditional(1, 6, 1, END) + item() + callback() + END, END, delivery())
    original, _, layout = source(init, main, (), (0,))
    data = bytearray(original)
    floor = layout["floor"]
    text = b"\x02\0A\xfe\0\0\0\0"
    data[floor:floor] = text * 2
    struct.pack_into("<I", data, 8 + 2 * 4, floor + 16)
    struct.pack_into("<I", data, 8 + 13 * 4, floor)
    struct.pack_into("<I", data, 8 + 14 * 4, floor + 8)
    if case == "choice":
        data[floor + 2] = 0xF7
    room = decode_room(
        bytes(data), "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room["stage"] = 1
    result = puzzle_items(
        bytes(data), room, profile, receipt, script_item_dispatch(profile)
    )
    assert (
        len(result) == 1
        if case == "valid"
        else isinstance(result, KnownDeclaredItemFailure)
    )
