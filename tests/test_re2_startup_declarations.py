"""RE2-STARTUP-002: positive declarations never imply quantity or clearance."""

import copy
import hashlib
import json
import struct
from dataclasses import replace

import pytest
from test_re2_metadata import ROOT
from test_re2_room_write_partitions import END, md1, source

from games.re2.event_presence import source_presence
from games.re2.startup_declarations import (
    StartupDeclarationFailure,
    StartupDeclarationReceipt,
    StartupDeclarationSupport,
    VerifiedStartupDeclarationContract,
    startup_declarations,
)
from games.re2.startup_entry_selection import (
    EntrySelectionSource,
    VerifiedEntrySelection,
)


@pytest.fixture
def profile():
    return json.loads((ROOT / "profiles/re2_leon_a_slus00748.json").read_text())


def item(kind=20, amount=15, gid=154, slot=7, sat=0x31, width=100, height=100, flags=0):
    packet = bytearray(22)
    packet[:4] = bytes((0x4E, slot, 2, sat))
    struct.pack_into("<2H", packet, 10, width, height)
    struct.pack_into("<3H", packet, 14, kind, amount, gid)
    packet[20:22] = bytes((255, flags))
    return bytes(packet)


def conditional(yes, no, bank=0, bit=25):
    return (
        bytes((6, 0))
        + struct.pack("<H", len(yes) + 8)
        + bytes((0x21, bank, bit, 0))
        + yes
        + bytes((7, 0))
        + struct.pack("<H", len(no) + 6)
        + no
        + b"\x08\0"
    )


def described(init=END, main=(END,), models=()):
    data, room, parts = source(init, main, models, (0,))
    room["stage"] = 0
    room["room"] = 2
    room["id"] = "00-02"
    room["source"] = "PL0/RDT/ROOM1020.RDT"
    return data, room, parts


def contract(profile, room):
    # Explicit test receipt isolates source interpretation; native resource and
    # selector binding have their own integration tests, with real owned bytes.
    return VerifiedStartupDeclarationContract(
        profile["executable_identity"].rpartition(" SHA256 ")[2],
        0x8011A6A8,
        0,
        VerifiedEntrySelection(
            profile["executable_identity"].rpartition(" SHA256 ")[2],
            (),
            (
                EntrySelectionSource(
                    "00-02", room["source"], room["size"], room["sha256"]
                ),
            ),
            frozenset((0,)),
            (("00-02", (2, 10)),),
        ),
        tuple(
            next(
                (
                    int(row["address_ps1"], 0)
                    for row in profile["flag_banks"]
                    if row["bank"] == index
                ),
                0,
            )
            for index in range(40)
        ),
        0x1F,
        frozenset((0x46, 0x8046, 0x8040)),
        17,
        27968,
        36120,
        136496,
        0x8018EF3C,
    )


def compile_source(profile, init=END, main=(END,), models=()):
    data, room, _ = described(init, main, models)
    return startup_declarations(data, room, profile, contract(profile, room))


def test_alternate_amounts_are_one_unconditional_identity(profile):
    body = conditional(item(amount=30), item(amount=15)) + bytes((0x5F, 64)) + END
    result = compile_source(profile, main=(body,))
    assert len(result) == 1
    assert (result[0].global_id, result[0].item_type, result[0].slot) == (154, 20, 7)
    assert len(result[0].creator_offsets) == 2
    assert not hasattr(result[0], "amount")
    assert not hasattr(result[0], "context_conditions")
    assert not hasattr(result[0], "cleared")


@pytest.mark.parametrize(
    "body",
    [
        b"\x02",
        bytes((0x54,)) + bytes(21),
        bytes((4, 0, 0x18, 0)),
        bytes((3, 0, 0x18, 0)),
        bytes((5, 0)),
    ],
)
def test_unsupported_or_replacing_effect_before_declaration_withholds(profile, body):
    assert compile_source(profile, main=(body + item() + END,)) == ()


@pytest.mark.parametrize(
    "tail", [b"\x02", bytes((0x54,)) + bytes(21), bytes((4, 0, 0x18, 0)), bytes((5, 0))]
)
def test_late_root17_effect_does_not_erase_earlier_declaration(profile, tail):
    assert len(compile_source(profile, main=(item() + tail + END,))) == 1


def test_root16_must_finish_before_a_root17_declaration(profile):
    assert compile_source(profile, init=b"\x02" + END, main=(item() + END,)) == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"sat": 0},
        {"sat": 0xB1},
        {"width": 0},
        {"height": 0},
        {"amount": 0},
        {"flags": 0x80},
        {"kind": 104},
    ],
)
def test_only_active_nonempty_ordinary_pickups_are_targets(profile, kwargs):
    assert compile_source(profile, main=(item(**kwargs) + END,)) == ()


def test_two_unrelated_branch_items_cannot_satisfy_each_other(profile):
    assert (
        compile_source(
            profile, main=(conditional(item(), item(gid=153, slot=6)) + END,)
        )
        == ()
    )


@pytest.mark.parametrize(
    "rebind", [item(kind=21), item(gid=153), bytes((0x46, 7, 0, 0)) + bytes(6)]
)
def test_later_slot_rebinding_withholds_identity(profile, rebind):
    assert compile_source(profile, main=(item() + END, rebind + END)) == ()


def test_copy_anywhere_withholds_instead_of_inventing_immutable_control(profile):
    result = compile_source(profile, main=(item() + END, bytes((0x1D, 0, 0, 0)) + END))
    assert result is StartupDeclarationFailure.SourceMutation


def test_unaudited_or_other_stage_cannot_create_declarations(profile):
    data, room, _ = described(main=(item() + END,))
    assert (
        startup_declarations(data, room, profile, StartupDeclarationSupport.Unaudited)
        == ()
    )
    assert (
        startup_declarations(
            data, room, profile, replace(contract(profile, room), source_stage=1)
        )
        == ()
    )


def test_receipt_binds_bytes_and_exact_decoded_programs(profile):
    data, room, _ = described(main=(item() + END,))
    targets = {("17:0", room["items"][0]["offset"])}
    raw = StartupDeclarationReceipt(
        room["sha256"],
        hashlib.sha256(
            json.dumps(room["programs"], sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        frozenset(),
    )
    assert source_presence(
        data,
        room["programs"],
        targets,
        "declaration",
        frozenset(),
        frozenset(),
        declaration_effects=raw,
    ) == {"kind": "required"}
    altered = copy.deepcopy(room["programs"])
    altered["17:0"]["entry"] += 1
    assert source_presence(
        data,
        altered,
        targets,
        "declaration",
        frozenset(),
        frozenset(),
        declaration_effects=raw,
    ) == {"kind": "unresolved"}
    assert source_presence(
        data, room["programs"], targets, "declaration", frozenset(), frozenset()
    ) == {"kind": "unresolved"}
    assert source_presence(
        data,
        room["programs"],
        targets,
        "declaration",
        frozenset({(0, 25)}),
        frozenset(),
        declaration_effects=raw,
    ) == {"kind": "unresolved"}


def test_source_cannot_forge_a_decoded_branch(profile):
    data, room, _ = described(main=(item() + END,))
    changed = copy.deepcopy(room)
    changed["programs"]["17:0"]["commands"][0]["slot"] = 4
    assert (
        startup_declarations(data, changed, profile, contract(profile, room))
        is StartupDeclarationFailure.SourceBinding
    )


@pytest.mark.parametrize("depth,expected", [(8, True), (9, False)])
def test_native_if_storage_is_bounded(profile, depth, expected):
    body = item()
    for _ in range(depth):
        body = conditional(body, item())
    result = compile_source(profile, main=(body + END,))
    assert bool(result) is expected


def test_repeated_setup_callee_does_not_inherit_fresh_model_storage(profile):
    packet = bytearray(38)
    packet[0] = 0x2D
    packet[10] = 10
    result = compile_source(
        profile,
        main=(bytes((0x18, 1, 0x18, 1)) + item() + END, bytes(packet) + END),
        models=(md1(1, 0),),
    )
    assert result == ()


def test_shared_md1_resource_and_numeric_yaw_write_preserve_prefix(profile):
    packet = bytearray(38)
    packet[0] = 0x2D
    packet[10] = 10
    body = bytes((0x2E, 4, 0, 0, 0x34, 15, 0, 8)) + item() + END
    result = compile_source(
        profile, init=bytes(packet) + END, main=(body,), models=(md1(1, 0),)
    )
    assert len(result) == 1


def test_branch_entering_member_write_without_work_owner_withholds(profile):
    packet = bytearray(38)
    packet[0] = 0x2D
    packet[10] = 10
    body = (
        bytes((6, 0, 8, 0, 0x21, 4, 1, 0, 0x2E, 4, 0, 0, 0x34, 15, 0, 8)) + item() + END
    )
    assert (
        compile_source(
            profile, init=bytes(packet) + END, main=(body,), models=(md1(1, 0),)
        )
        == ()
    )


def test_late_model_declaration_does_not_initialize_earlier_member_write(profile):
    packet = bytearray(38)
    packet[0] = 0x2D
    packet[10] = 10
    body = bytes((0x2E, 4, 0, 0, 0x34, 15, 0, 8)) + item() + END
    assert (
        compile_source(profile, main=(body, bytes(packet) + END), models=(md1(1, 0),))
        == ()
    )


def test_conditionally_initialized_root16_model_is_not_a_guaranteed_owner(profile):
    packet = bytearray(38)
    packet[0] = 0x2D
    packet[10] = 10
    body = bytes((0x2E, 4, 0, 0, 0x34, 15, 0, 8)) + item() + END
    assert (
        compile_source(
            profile,
            init=conditional(bytes(packet), b"") + END,
            main=(body,),
            models=(md1(1, 0),),
        )
        == ()
    )


def test_shared_allocation_callee_cannot_be_fresh_in_both_roots(profile):
    packet = bytearray(38)
    packet[0] = 0x2D
    packet[10] = 10
    result = compile_source(
        profile,
        init=bytes((0x18, 1)) + END,
        main=(bytes((0x18, 1)) + item() + END, bytes(packet) + END),
        models=(md1(1, 0),),
    )
    assert result is StartupDeclarationFailure.Prefix


def test_metadata_owned_outcome_shape_when_opted_in():
    catalog = json.loads((ROOT / "data/rooms_slus00748.json").read_text())
    room = next(
        r
        for r in catalog["rooms"]
        if r["sha256"]
        == "30fc267de1ad566dcb61403822731ec5eae099d934f244538d34c33ebe64dddf"
    )
    assert room["startup_item_declarations"] == [
        {"global_id": 154, "item_type": 20, "slot": 7, "creator_offsets": [7838, 7864]}
    ]


def test_new_declaration_audit_is_explicit_and_revision_bound(profile):
    from games.re2.startup_declarations import (
        StartupDeclarationAuditConfig,
        startup_declaration_audit,
    )

    assert startup_declaration_audit({}) is StartupDeclarationSupport.Unaudited
    config = startup_declaration_audit(profile)
    assert isinstance(config, StartupDeclarationAuditConfig)
    assert len(config.resources) == 69
    assert len(config.selection.sources) == 125


@pytest.mark.parametrize("fault", ["null", "extra", "resource", "source", "revision"])
def test_invalid_required_audit_fails_startup_clearly(profile, fault):
    from games.re2.startup_declarations import startup_declaration_audit

    if fault == "null":
        profile["startup_declaration_audit"] = None
    elif fault == "extra":
        profile["startup_declaration_audit"]["other"] = True
    elif fault == "resource":
        profile["startup_declaration_audit"]["resources"][0]["sha256"] = "0" * 64
    elif fault == "source":
        profile["startup_declaration_audit"]["selection"]["sources"][0]["sha256"] = (
            "0" * 64
        )
    else:
        profile["executable_identity"] = "different SHA256 " + "0" * 64
    with pytest.raises(ValueError, match="startup declaration audit"):
        startup_declaration_audit(profile)


def test_direct_audit_config_keeps_the_selectors_required_resources(profile):
    from games.re2.startup_declarations import startup_declaration_audit

    config = startup_declaration_audit(profile)
    with pytest.raises(AssertionError):
        replace(config, resources=config.resources[:-1])


def test_resource_or_corpus_mismatch_withholds_native_receipt(profile):
    from games.re2.startup_declarations import (
        bind_startup_declaration_audit,
        startup_declaration_audit,
    )

    config = startup_declaration_audit(profile)
    assert (
        bind_startup_declaration_audit(config, b"", {}, {})
        is StartupDeclarationFailure.NativeContract
    )


def test_identical_source_bytes_cannot_inherit_another_room_entry_receipt(profile):
    data, room, _ = described(main=(item() + END,))
    receipt = contract(profile, room)
    room["id"] = "00-18"
    room["room"] = 24
    assert startup_declarations(data, room, profile, receipt) == ()


@pytest.mark.parametrize("models", [(), (13,)])
def test_missing_or_uncovered_incoming_asset_has_no_default(profile, models):
    data, room, _ = described(main=(item() + END,))
    receipt = contract(profile, room)
    receipt = replace(
        receipt,
        selection=replace(receipt.selection, incoming_models=(("00-02", models),)),
    )
    assert startup_declarations(data, room, profile, receipt) == ()


def test_native_flag_aliases_cannot_be_relabelled_as_saved_state(profile):
    data, room, _ = described(main=(bytes((0x22, 2, 7, 1)) + item() + END,))
    receipt = contract(profile, room)
    next(row for row in profile["flag_banks"] if row["bank"] == 2)["address_ps1"] = (
        "0x800D4874"
    )
    assert (
        startup_declarations(data, room, profile, receipt)
        is StartupDeclarationFailure.NativeContract
    )


def test_undecoded_later_bytes_cannot_hide_an_identity_rebinding(profile):
    data, room, _ = described(main=(item() + END,))
    end = next(
        row["offset"]
        for row in room["programs"]["17:0"]["commands"]
        if row["kind"] == "end"
    )
    data = data[:end] + b"\xff" + data[end + 1 :]
    room["sha256"] = hashlib.sha256(data).hexdigest()
    assert (
        startup_declarations(data, room, profile, contract(profile, room))
        is StartupDeclarationFailure.SourceBinding
    )
