"""RE2-STARTUP-004: guarded direct declarations share the bounded startup walk."""

import struct
from dataclasses import replace

import pytest
from test_re2_immediate_effect_resource import effect_source as effect_source
from test_re2_known_puzzle_items import (
    conditional,
)
from test_re2_known_puzzle_items import (
    profile as profile,
)
from test_re2_known_puzzle_items import (
    receipt as receipt,
)
from test_re2_metadata import PRESENCE_COUNTERS, PRESENCE_FLAGS, PRESENCE_WRITES
from test_re2_room_write_partitions import END, md1, source
from test_re2_startup_declarations import contract, item

from games.re2.known_puzzle_items import (
    KnownDeclaredItemFailure,
    KnownDeclaredItems,
    known_declared_items,
)
from games.re2.room_data import decode_room
from games.re2.script_dispatch_items import script_item_dispatch


def compile_direct(profile, receipt, data, incoming=(1, 13)):
    room = decode_room(
        data, "synthetic", PRESENCE_FLAGS, PRESENCE_COUNTERS, PRESENCE_WRITES
    )
    room.update(stage=0, room=2, id="00-02")
    declaration = contract(profile, room)
    declaration = replace(
        declaration,
        selection=replace(
            declaration.selection, incoming_models=(("00-02", incoming),)
        ),
    )
    return known_declared_items(
        data,
        room,
        profile,
        receipt,
        script_item_dispatch(profile),
        declaration,
    )


def setup_packet(slot):
    packet = bytearray(38)
    packet[:2] = bytes((0x2D, slot))
    packet[10] = 8
    struct.pack_into("<6h", packet, 26, -100, 100, -200, 200, 100, 200)
    return bytes(packet)


def test_guarded_direct_pickup_needs_no_fictional_player_callback(profile, receipt):
    data, _, _ = source(END, (conditional(1, 6, 1, END) + item() + END, END), (), (0,))
    result = compile_direct(profile, receipt, data)
    assert isinstance(result, KnownDeclaredItems) and result.puzzle_items == ()
    (pickup,) = result.direct_pickups
    assert (pickup.global_id, pickup.item_type, pickup.slot) == (154, 20, 7)
    assert pickup.context_conditions == [
        {"kind": "conditions", "any_of": [[{"bank": 1, "bit": 6, "expected": 0}]]}
    ]
    assert not hasattr(pickup, "callback_offsets")
    assert not hasattr(pickup, "amount")


@pytest.mark.parametrize(
    "field,value",
    [("file_type_min", 105), ("script_counter_address_ps1", "0x800D47EE")],
)
def test_revision_bounds_cannot_be_reinterpreted_by_profile_values(
    profile, receipt, field, value
):
    data, _, _ = source(item(kind=104) + END, (END, END), (), (0,))
    profile["runtime_layout"][field] = value
    assert (
        compile_direct(profile, receipt, data)
        is KnownDeclaredItemFailure.NativeContract
    )


@pytest.mark.parametrize("incoming", [(), (2,), (1, 10)])
def test_direct_pickup_requires_every_incoming_model_to_be_audited(
    profile, receipt, incoming
):
    data, _, _ = source(item() + END, (END, END), (), (0,))
    assert compile_direct(profile, receipt, data, incoming).direct_pickups == ()


@pytest.mark.parametrize(
    "packet",
    [item(sat=0), item(width=0), item(height=0), item(amount=0), item(flags=1)],
)
def test_parked_or_nonordinary_packets_cannot_create_direct_knowledge(
    profile, receipt, packet
):
    data, _, _ = source(packet + END, (END, END), (), (0,))
    assert compile_direct(profile, receipt, data).direct_pickups == ()


def test_merged_parked_and_active_branches_do_not_make_a_direct_guarantee(
    profile, receipt
):
    body = conditional(4, 0, 1, item()) + item(sat=0) + END
    data, _, _ = source(body, (END, END), (), (0,))
    assert compile_direct(profile, receipt, data).direct_pickups == ()


def test_unmodeled_predicate_stops_without_erasing_an_earlier_direct_declaration(
    profile, receipt
):
    later = b"\x06\0\x08\0\x23\0\x04\0\x01\0\x08\0"
    data, _, _ = source(
        item() + later + item(gid=155, slot=8) + END, (END, END), (), (0,)
    )
    result = compile_direct(profile, receipt, data)
    assert [pickup.global_id for pickup in result.direct_pickups] == [154]


@pytest.mark.parametrize(
    "case", ["consecutive", "roots", "call", "nonconsecutive", "same-slot"]
)
def test_model_cache_and_allocation_state_follow_roots_and_calls(
    profile, receipt, case
):
    models = (md1(0, 2), md1(0, 2), md1(0, 2))
    if case == "roots":
        init, main = setup_packet(0) + END, (setup_packet(1) + item() + END, END)
    elif case == "call":
        init, main = (
            END,
            (b"\x18\x02" + setup_packet(1) + item() + END, END, setup_packet(0) + END),
        )
    elif case == "nonconsecutive":
        init, main = (
            END,
            (setup_packet(0) + setup_packet(1) + setup_packet(2) + item() + END, END),
        )
    elif case == "same-slot":
        init, main = END, (setup_packet(0) * 2 + item() + END, END)
    else:
        init, main = END, (setup_packet(0) + setup_packet(1) + item() + END, END)
    data, _, layout = source(init, main, models, (0,))
    data = bytearray(data)
    alias = 2 if case == "nonconsecutive" else 1
    struct.pack_into(
        "<I", data, layout["directory"] + alias * 8 + 4, layout["models"][0]
    )
    result = compile_direct(profile, receipt, bytes(data))
    assert bool(result.direct_pickups) is (case not in ("nonconsecutive", "same-slot"))


@pytest.mark.parametrize("reuses", [1, 2])
def test_cached_model_reuse_still_consumes_new_primitive_heap(profile, receipt, reuses):
    # One use fits. A second use must allocate another packet buffer even
    # though the native cache avoids relocating the shared source twice.
    body = setup_packet(0) + (setup_packet(1) if reuses == 2 else b"") + item() + END
    data, _, layout = source(END, (body, END), (md1(0, 2600), md1(0, 2600)), (0,))
    data = bytearray(data)
    struct.pack_into("<I", data, layout["directory"] + 12, layout["models"][0])
    result = compile_direct(profile, receipt, bytes(data))
    assert bool(result.direct_pickups) is (reuses == 1)


def test_reconverged_paths_keep_different_last_model_cache_values(profile, receipt):
    yes = setup_packet(0) + setup_packet(1)
    no = setup_packet(1) + setup_packet(0)
    branch = b"\x06\0" + struct.pack("<H", 4 + len(yes) + 4) + b"\x21\x04\0\x01" + yes
    # A native false IF enters ELSE without a pushed frame. Its body ends
    # with NOP padding; the true-path ELSE opcode has already popped the frame.
    branch += b"\x07\0" + struct.pack("<H", 4 + len(no) + 2) + no + b"\0\0"
    data, _, layout = source(
        END, (branch + setup_packet(2) + item() + END, END), (md1(0, 2),) * 3, (0,)
    )
    data = bytearray(data)
    struct.pack_into("<I", data, layout["directory"] + 20, layout["models"][0])
    assert compile_direct(profile, receipt, bytes(data)).direct_pickups == ()


@pytest.mark.parametrize("target", ["directory", "asset"])
def test_copy_cannot_change_model_reads_before_the_direct_declaration(
    profile, receipt, target
):
    body = setup_packet(0) + item() + END
    data, room, layout = source(
        END, (body, END, b"\x1d\0\0\0" + END), (md1(0, 2),), (0,)
    )
    data = bytearray(data)
    at = room["programs"]["17:2"]["entry"]
    destination = (
        layout["directory"] + 4 if target == "directory" else layout["models"][0] + 8
    )
    data[at + 2] = destination - (at + 4)
    assert (
        compile_direct(profile, receipt, bytes(data))
        is KnownDeclaredItemFailure.SourceMutation
    )


@pytest.mark.parametrize(
    "case",
    [
        "valid",
        "pool",
        "reference",
        "element-count",
        "binding-id",
        "copy-id",
        "copy-subtype",
        "copy-record",
    ],
)
def test_synchronous_effect_continuation_requires_immutable_owned_reads(
    profile, receipt, effect_source, case
):
    effect_data, _, effect_floor, command = effect_source
    packet = bytes(effect_data[command : command + 22])
    later = b"\x1d\0\0\0" + END if case.startswith("copy-") else END
    original, room, layout = source(END, (packet + item() + END, END, later), (), (0,))
    data = bytearray(original[: layout["floor"]])
    ids = len(data)
    data.extend(effect_data[128:effect_floor])
    sections = list(struct.unpack_from("<23I", data, 8))
    sections[18], sections[19], sections[2] = ids, ids + 508, len(data)
    data.extend(bytes(32))
    struct.pack_into("<23I", data, 8, *sections)
    first = room["programs"]["17:0"]["entry"]
    if case == "pool":
        profile["scenario_effect_pool"]["address_ps1"] = "0x800D8CF4"
    elif case == "reference":
        data[first + 4] = 1
    elif case == "element-count":
        struct.pack_into("<H", data, ids + 48, 0)
    elif case == "binding-id":
        data[ids] = data[first + 2] = 64
    elif case.startswith("copy-"):
        at = room["programs"]["17:2"]["entry"]
        relative = {"copy-id": 0, "copy-subtype": 32, "copy-record": 56}[case]
        data[at + 2] = ids + relative - (at + 4)
    result = compile_direct(profile, receipt, bytes(data))
    if case.startswith("copy-"):
        assert result is KnownDeclaredItemFailure.SourceMutation
    else:
        assert bool(result.direct_pickups) is (case == "valid")
