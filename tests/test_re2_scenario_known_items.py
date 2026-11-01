"""A scoped scenario receipt does not substitute for a finite positive prefix."""

from dataclasses import replace
import struct

import pytest
from test_re2_initializer_control import initializer_body, music
from test_re2_known_puzzle_items import (
    callback,
    conditional,
    delivery,
    item,
    profile as profile,
    receipt as receipt,
)
from test_re2_room_write_partitions import END, md1, object_command, source
from test_re2_startup_declarations import contract

from games.re2.event_presence import presence_counter_indices, presence_flag_write_proof
from games.re2.known_puzzle_items import (
    KnownDeclaredItemFailure,
    KnownDeclaredItems,
    known_declared_items,
)
from games.re2.room_data import decode_room
from games.re2.room_write_partitions import direct_pickup_packet
from games.re2.scenario_entry_scope import scenario_entry_scope
from games.re2.scenario_selection import (
    VerifiedScenarioContext,
    VerifiedScenarioEntryScope,
    bind_scenario_context,
)
from games.re2.script_dispatch_items import script_item_dispatch


def prepared(profile, init, main, models=(), cameras=(0,)):
    data, _, parts = source(init, main, models, cameras)
    room = decode_room(
        data,
        "PL0/RDT/ROOM1020.RDT",
        frozenset(
            (row["bank"], row["bit"]) for row in profile["presence_condition_flags"]
        ),
        presence_counter_indices(profile),
        presence_flag_write_proof(profile)[0],
    )
    room.update(stage=0, room=2, id="00-02")
    context = bind_scenario_context(profile, contract(profile, room))
    assert isinstance(context, VerifiedScenarioContext)
    entries = scenario_entry_scope(data, room, profile, context)
    assert isinstance(entries, VerifiedScenarioEntryScope), entries
    return data, room, context, entries, parts


def compiled(profile, receipt, prepared_source, *, audited=True):
    data, room, context, entries, _ = prepared_source
    arguments = (
        {"scenario_context": context, "scenario_entries": entries} if audited else {}
    )
    return known_declared_items(
        data,
        room,
        profile,
        receipt,
        script_item_dispatch(profile),
        context.declaration_contract,
        **arguments,
    )


def test_immutable_scenario_prunes_only_the_opposite_prefix(profile, receipt):
    prepared_source = prepared(
        profile,
        conditional(1, 1, 1, b"\x02") + item() + END,
        (callback() + END, END, delivery()),
    )
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems)
    assert [row.global_id for row in result.puzzle_items] == [93]
    assert result.puzzle_items[0].context_conditions == []
    old = compiled(profile, receipt, prepared_source, audited=False)
    assert isinstance(old, KnownDeclaredItems) and not old.puzzle_items


def test_unstable_leading_guard_does_not_flip_immutable_scenario(profile, receipt):
    mode_return = conditional(1, 6, 1, END)
    prepared_source = prepared(
        profile,
        mode_return + conditional(1, 1, 1, b"\x02") + item() + END,
        (mode_return + callback() + END, END, delivery()),
    )
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems)
    assert [row.global_id for row in result.puzzle_items] == [93]
    assert result.puzzle_items[0].context_conditions == [
        {"kind": "conditions", "any_of": [[{"bank": 1, "bit": 6, "expected": 0}]]}
    ]


@pytest.mark.parametrize("leaf_index", [2, 3, 5])
def test_finite_nested_copy_music_prefix_is_scoped_to_its_real_program(
    profile, receipt, leaf_index
):
    procedures = [END] * (leaf_index + 1)
    procedures[0] = bytes((0x18, leaf_index)) + item() + callback(1) + END
    procedures[1] = delivery()
    procedures[leaf_index] = initializer_body() + END
    procedures.append(music(bank=1, mode=2) + END)
    prepared_source = prepared(profile, END, tuple(procedures))
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems)
    assert [row.global_id for row in result.puzzle_items] == [93]
    old = compiled(profile, receipt, prepared_source, audited=False)
    assert isinstance(old, KnownDeclaredItems) and not old.puzzle_items


def test_possible_prefix_does_not_establish_a_declaration(profile, receipt):
    prepared_source = prepared(
        profile,
        conditional(4, 72, 1, item()) + END,
        (callback() + END, END, delivery()),
    )
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems) and not result.puzzle_items
    assert not result.direct_pickups


def test_alternate_pickup_controller_requires_explicit_packet_opt_in():
    for flags in range(256):
        packet = bytearray(item(item_type=21, gid=99, amount=7))
        packet[21] = flags
        assert direct_pickup_packet(bytes(packet)) is (flags == 0)
        assert direct_pickup_packet(bytes(packet), pickup_flags=frozenset((0, 1))) is (
            flags in (0, 1)
        )
    with pytest.raises(AssertionError):
        direct_pickup_packet(item(), pickup_flags=frozenset((0, 2)))


@pytest.mark.parametrize("flags", [0, 1, 2, 3, 128, 255])
def test_alternate_pickup_mode_agrees_on_the_guaranteed_declared_identity(
    profile, receipt, flags
):
    ordinary = item(item_type=21, gid=99, amount=7)
    alternate = bytearray(ordinary)
    alternate[21] = flags
    # Native ELSE pops the IF frame. Both branches meet directly at END;
    # an extra ENDIF would underflow that already-popped condition stack.
    body = (
        b"\x06\0"
        + struct.pack("<H", len(ordinary) + 8)
        + b"\x21\0\x19\0"
        + ordinary
        + b"\x07\0"
        + struct.pack("<H", len(alternate) + 4)
        + bytes(alternate)
    )
    prepared_source = prepared(profile, END, (body + END, END))
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems)
    assert not result.puzzle_items
    if flags in (0, 1):
        assert len(result.direct_pickups) == 1
        direct = result.direct_pickups[0]
        assert (direct.global_id, direct.item_type, len(direct.creator_offsets)) == (
            99,
            21,
            2,
        )
        assert direct.context_conditions == []
        assert not hasattr(direct, "amount") and not hasattr(direct, "access")
    else:
        assert not result.direct_pickups


def test_native_entry_receipt_does_not_prove_a_callee_returns(profile, receipt):
    prepared_source = prepared(
        profile,
        bytes((0x18, 3)) + item() + END,
        (callback() + END, END, delivery(), b"\x02" + END),
    )
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems) and not result.puzzle_items
    assert not result.direct_pickups


def test_one_native_receipt_cannot_implicitly_opt_into_the_other(profile, receipt):
    data, room, context, _entries, _parts = prepared(
        profile, item() + END, (callback() + END, END, delivery())
    )
    with pytest.raises(AssertionError, match="both independent native receipts"):
        known_declared_items(
            data,
            room,
            profile,
            receipt,
            script_item_dispatch(profile),
            context.declaration_contract,
            scenario_context=context,
        )


def test_audited_flags12_keeps_model_and_cache_checks(profile, receipt):
    packet = bytearray(object_command(0))
    packet[10] = 10
    packet[12] = 0x12
    prepared_source = prepared(
        profile,
        bytes(packet) + item() + END,
        (callback() + END, END, delivery()),
        (md1(1, 1),),
    )
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems)
    assert [row.global_id for row in result.puzzle_items] == [93]
    old = compiled(profile, receipt, prepared_source, audited=False)
    assert isinstance(old, KnownDeclaredItems) and not old.puzzle_items
    duplicate = prepared(
        profile,
        bytes(packet) * 2 + item() + END,
        (callback() + END, END, delivery()),
        (md1(1, 1),),
    )
    result = compiled(profile, receipt, duplicate)
    assert isinstance(result, KnownDeclaredItems) and not result.puzzle_items


def test_bounded_camera_swaps_and_relative_flag_writes_are_finite(profile, receipt):
    prepared_source = prepared(
        profile,
        bytes((0x4B, 0, 1, 0x61, 0, 0, 0)) + item() + END,
        (callback() + END, END, delivery()),
        cameras=(0, 1),
    )
    result = compiled(profile, receipt, prepared_source)
    assert isinstance(result, KnownDeclaredItems)
    assert [row.global_id for row in result.puzzle_items] == [93]


def test_receipt_from_another_source_is_a_modeled_failure(profile, receipt):
    first = prepared(profile, item() + END, (callback() + END, END, delivery()))
    second = prepared(
        profile, b"\0" + item() + END, (callback() + END, END, delivery())
    )
    data, room, context, _, parts = second
    mixed = data, room, context, first[3], parts
    assert compiled(profile, receipt, mixed) is KnownDeclaredItemFailure.NativeContract


def test_missing_scope_does_not_authorize_a_called_prefix(profile, receipt):
    prepared_source = prepared(
        profile,
        bytes((0x18, 3)) + item() + END,
        (callback() + END, END, delivery(), initializer_body() + END),
    )
    data, room, context, entries, parts = prepared_source
    entries = replace(
        entries,
        protected_programs=entries.protected_programs - {"17:3"},
        entry_locations=frozenset(
            entry for entry in entries.entry_locations if entry[0] != "17:3"
        ),
    )
    assert (
        compiled(profile, receipt, (data, room, context, entries, parts))
        is KnownDeclaredItemFailure.NativeContract
    )
