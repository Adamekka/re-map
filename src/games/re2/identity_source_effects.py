"""RE2-SCENARIO-012: unsealed identity-only compaction and opaque IF facts.

The public compiler must still close every source/auxiliary effect and native
producer before sealing these facts. They grant no presence or door rights.
"""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from games.re2.native_control import ControlField, native_bytes, native_nonyielding
from games.re2.native_entry_fields import _TaskFields
from games.re2.native_sound_calls import sound_reader_scalar_calls
from games.re2.room_entry_contract import room_entry_contract
from games.re2.room_sound_bindings import (
    CompactedSoundLayout,
    InitialSoundLayout,
    RoomSoundBindings,
    compacted_sound_layout,
    room_sound_bindings,
)
from games.re2.room_write_partitions import (
    EmbeddedModelResource,
    RoomWritePartitionConfig,
    RoomWritePartitions,
    SourceRange,
    room_write_partitions,
)
from games.re2.scenario_selection import ScenarioSourceWriteWitnesses

if TYPE_CHECKING:
    from games.re2.identity_filtering import IdentityFilteringPolicy


class IdentitySourceFailure(Enum):
    Native = "identity source-effect native binding mismatch"
    Compaction = "identity one-pass compaction is unsupported"
    Allocation = "identity normal primitive reservation is unsupported"


@dataclass(frozen=True)
class IdentityCompaction:
    program: str
    offset: int
    layout: CompactedSoundLayout
    rebind_writes: tuple[SourceRange, ...]


@dataclass(frozen=True)
class MemberIfPredicate:
    program: str
    offset: int
    if_offset: int
    work_offsets: tuple[int, ...]
    task_depths: tuple[tuple[int, int], ...]
    if_cells: tuple[int, ...]


@dataclass(frozen=True)
class IdentityPrimitiveReservation:
    source_sha256: str
    program: str
    offset: int
    count: int
    reservation_width: int
    task_depths: tuple[tuple[int, int], ...]
    call_chain: tuple[tuple[str, int, str], ...]


# Complete inspected native windows, including original return delay slots.
_COMPACTION_WINDOWS = (
    (
        0x8004A414,
        640,
        "eb2b7be62fe552f7dae5f577b842ae7f924d12e4dd84ad799bd4ef05e6bfdedd",
    ),
    (
        0x80076A00,
        40,
        "00ff8a741221e1a2750aa9deedd21ad70d399e2def4df098ea42665f2bb6e211",
    ),
    (
        0x80054310,
        68,
        "734359dfe61b1a5a819a0a15c958784c9eac860ca6f575ae41c333bc104846f0",
    ),
    (
        0x8005A338,
        220,
        "cc0714c0bd0e53c55236e1659a6df723bef12f1ae57d36cb917016289fa03f36",
    ),
    (
        0x80084EC0,
        132,
        "845fc3d6b10e953daade6d6b3bed3782d453712a9637d4f99e708353990d9f24",
    ),
    (
        0x80084F44,
        124,
        "8589c880d4d493efc7b6c5c11472baeb6856c2e50210deef7097c158b958bdea",
    ),
    (
        0x80084FC0,
        776,
        "13cda70b5f3219f87c1307bd47c31c09dff949fcf8b8793645f4f612dd3a761b",
    ),
    (
        0x800852C8,
        112,
        "9cfb5e3f27fb71dd23ac7216ae4e02df1ba53722407f8f202aef1dad957d9aa3",
    ),
    (
        0x80085398,
        48,
        "8ebb4b1f81bb96ab21d997810983899f1d3f31a431915225e60e5130a377f189",
    ),
    (
        0x800853C8,
        988,
        "0a3e8dd4c387ae027d74525f6a77d4cf3a78a0732d9b5ab5c4b0c23926b09c3d",
    ),
    (
        0x80082710,
        44,
        "0847e691d507dd50f213776783d6d7c1189ec8553649721badc0461c91b468a3",
    ),
    (
        0x8008273C,
        24,
        "b6506c3ff7c1639d5e8e8ce1e410d1dc8ff8c500549c60c2cbaf3e35410dfa88",
    ),
    (
        0x800826BC,
        84,
        "767988274c72168c6deb48cffbfabc43f0a28336e473995dc8af743170e7b577",
    ),
    (
        0x8008239C,
        800,
        "902b5f91b9f111cfd45b2f33b27f9c608d3d967c3592d26f1c8dbb9b40e66796",
    ),
    (
        0x80059654,
        336,
        "282e70cb29bb5b51dd821c71ffd23698bb538db30f0c8ba2ebfa7436c7a2643b",
    ),
    (
        0x80049E48,
        1400,
        "abb25ef30698ec834d7bc8661e0b408b7253d1cb7ac5bdf177ac1786475e8e62",
    ),
    (
        0x8005A09C,
        668,
        "e2e0b125129aada9f85822053a68afae8f28d6c96a7a0469c7a4202aae7a0f93",
    ),
)
_MEMBER_WINDOWS = (
    (
        0x800112D8,
        28,
        "a0dd3e5cc1f2e492657e8215ad3c66b94869efea2519078e1c5d37645fe605d6",
    ),
    (
        0x80053924,
        184,
        "0242027b221cd5f14c187b3bb3254fcd67f52304e4ba0ea3bbb9c601bd159aed",
    ),
    (
        0x80055E8C,
        196,
        "df3ab8bb4d3b9a44d2be7e6dc4168c5562deb06dd9bd12070a40b703c92c4542",
    ),
    (
        0x80055F50,
        568,
        "7d1d81e01e7e3cf37970ff1f5a4b4f4ba799bff81d67664cb06e5f45ca6e340a",
    ),
    (
        0x800536C4,
        264,
        "2d6e34c985401d66077e1c1e6fde4f6555179852fcd2462d75b42c2f7456e298",
    ),
    (
        0x800112F8,
        176,
        "d974b6808c09bacebf43b1e3fa4218914cb5953c7c3bd51c0e496906011e5486",
    ),
    (
        0x80055904,
        204,
        "9f08b1193edd13a0362fe5a46ee6324d5903cb8b2f09be702ac7b9d9fc93dd2e",
    ),
    (
        0x800111F0,
        20,
        "bea46c2e2d06900696fdeb7359ca1a5707bf18f2eebadd583d1f8d9ce343c01c",
    ),
)


def identity_compactions(
    data: bytes,
    room: dict,
    profile: dict,
    fields: _TaskFields,
    writes: ScenarioSourceWriteWitnesses,
    executable: bytes,
    flag_addresses: tuple[int, ...],
) -> tuple[IdentityCompaction, ...] | IdentitySourceFailure:
    """Propagate only mask/count facts on the existing shared native CFG."""
    programs = room["programs"]
    all_rows = [(key, row) for key, p in programs.items() for row in p["commands"]]
    compactions = {(key, r["offset"]) for key, r in all_rows if r["opcode"] == 0x6C}
    if not compactions:
        return ()
    if any(
        hashlib.sha256(native_bytes(executable, at, width)).hexdigest() != digest
        for at, width, digest in _COMPACTION_WINDOWS
    ):
        return IdentitySourceFailure.Native
    calls = sound_reader_scalar_calls(executable)
    if type(calls) is not tuple or not native_nonyielding(
        executable, 0x8005C040, {}, scalar_calls=calls
    ):
        return IdentitySourceFailure.Native
    if not all(
        native_nonyielding(executable, at, {})
        for at in (0x80054310, 0x8005A338, 0x8005BA28, 0x8005BD6C)
    ):
        return IdentitySourceFailure.Native
    if (
        flag_addresses[30] != 0x800CFB70
        or native_bytes(executable, 0x80049E74, 8) != bytes.fromhex("0d80013c70fb20ac")
        or int.from_bytes(native_bytes(executable, 0x800A7940, 4), "little")
        != flag_addresses[30]
        or int.from_bytes(native_bytes(executable, 0x800A74C8 + 0x6C * 4, 4), "little")
        != 0x80054310
    ):
        return IdentitySourceFailure.Native
    # Room_load explicitly clears this native mask before initial main entry.
    # Ordinary initialized clock/ownership also bounds cached EDT/VH to one
    # non-rescheduling reader call. No idle flag or new interrupt premise is used.
    root = "17:0"
    if (
        any(key != root for key, _ in compactions)
        or {(task, depth) for key, task, depth in fields.entries if key == root}
        != {(1, 0)}
        or any(
            target == root and owner != "native"
            for owner, _, target, _ in fields.producers
        )
        or any(target == root for _, target in fields.calls)
        or any(target == root for _, _, target in fields.replacements)
    ):
        return IdentitySourceFailure.Compaction
    graph = dict(dict(fields.frames)[root].edges)
    rows = {row["offset"]: row for row in programs[root]["commands"]}
    reverse = {at: set() for at in rows}
    for before, targets in graph.items():
        for target in targets:
            reverse[target].add(before)
    ancestors = {at for _, at in compactions}
    pending = list(ancestors)
    while pending:
        for prev in reverse[pending.pop()]:
            if prev not in ancestors:
                ancestors.add(prev)
                pending.append(prev)
    # No cooperative side task/callback/call can change the historical mask
    # before this one pass. All later source producers still undergo preflight.
    if any(
        rows[at]["opcode"] not in (0, 6, 7, 8, 0x21, 0x22, 0x23, 0x2E, 0x3E, 0x6C)
        for at in ancestors
    ):
        return IdentitySourceFailure.Compaction
    mask_writers = set()
    for key, row in all_rows:
        if (
            row["kind"] == "flag_write"
            and flag_addresses[row["bank"]] + 4 * (row["bit"] >> 5)
            == flag_addresses[30]
        ):
            if (
                key != root
                or row["offset"] not in ancestors
                or row["bank"] != 30
                or row["operation"] not in (0, 1, 2)
            ):
                return IdentitySourceFailure.Compaction
            mask_writers.add(row["offset"])
        if row["kind"] in ("interaction", "reset") and row["interaction"] == 6:
            operand = (
                4 if row["kind"] == "reset" else 22 if row["opcode"] == 0x67 else 14
            )
            bank, bit, _ = struct.unpack_from("<3H", data, row["offset"] + operand)
            if flag_addresses[bank] + 4 * ((bit & 255) >> 5) == flag_addresses[30]:
                return IdentitySourceFailure.Compaction
    origin = InitialSoundLayout(
        data, tuple(room["section_offsets"]), room["section_offsets"][2]
    )
    original = room_sound_bindings(origin, frozenset(range(48)))
    if type(original) is not RoomSoundBindings:
        return IdentitySourceFailure.Compaction
    config = room_entry_contract(profile).write_partitions
    partitions = room_write_partitions(
        data,
        room,
        RoomWritePartitionConfig(
            int(config.aot_address_ps1, 0),
            config.aot_capacity,
            int(config.object_address_ps1, 0),
            config.object_capacity,
            config.item_flag_count,
            config.interaction_flag_count,
        ),
    )
    if type(partitions) is not RoomWritePartitions:
        return IdentitySourceFailure.Compaction
    section = origin.section_offsets[22]
    # Both copy epochs must preserve all scripts, creator/reset bytes, models,
    # source-write dependencies and mutable source domains, even unentered ones.
    protected = (
        *(SourceRange(r["offset"], r["next"] - r["offset"]) for _, r in all_rows),
        *(r for r in partitions.protected_source if r.offset >= 100),
        *(
            o.model.asset
            for o in partitions.objects
            if type(o.model) is EmbeddedModelResource
        ),
        *(r for write in partitions.source_writes for r in write.writes),
        *writes.record_reads,
        *(SourceRange(copy.target_offset, copy.width) for copy in writes.copies),
    )
    if any(r.offset + r.width > section for r in protected):
        return IdentitySourceFailure.Compaction
    pending, seen, facts = [(programs[root]["entry"], 0, False)], set(), {}
    while pending:
        at, mask, compacted = pending.pop()
        state = at, mask, compacted
        if state in seen:
            continue
        if len(seen) >= 4096:
            return IdentitySourceFailure.Compaction
        seen.add(state)
        row = rows[at]
        if at in mask_writers:
            if compacted:
                return IdentitySourceFailure.Compaction
            bit = 0x80000000 >> row["bit"]
            mask = (
                mask & ~bit
                if row["operation"] == 0
                else mask | bit
                if row["operation"] == 1
                else mask ^ bit
            )
        if row["opcode"] == 0x6C:
            if compacted:
                return IdentitySourceFailure.Compaction
            layout = compacted_sound_layout(origin, mask)
            if type(layout) is not CompactedSoundLayout:
                return IdentitySourceFailure.Compaction
            sound = room_sound_bindings(layout, frozenset(range(48)))
            if type(sound) is not RoomSoundBindings:
                return IdentitySourceFailure.Compaction
            vh = origin.section_offsets[1]
            programs_count = struct.unpack_from("<H", data, vh + 0x12)[0]
            samples_count = data[vh + 0x16]
            table = vh + 0x820 + 0x200 * programs_count
            if table + 2 * (samples_count + 1) > origin.retained_floor:
                return IdentitySourceFailure.Compaction
            sizes = struct.unpack_from("<" + "H" * (samples_count + 1), data, table)
            if 0x14440 + sum(size * 8 for size in sizes) > 0x80000:
                return IdentitySourceFailure.Compaction
            rebind = tuple(
                SourceRange(layout.vab + 0x28 + 16 * i, 4) for i in range(128)
            ) + tuple(
                SourceRange(
                    layout.vab + 0x20 + 16 * (i // 2) + (0xC if i % 2 == 0 else 0xE), 2
                )
                for i in range(samples_count + 1)
            )
            if any(
                not layout.vab <= r.offset <= layout.retained_floor - r.width
                for r in rebind
            ):
                return IdentitySourceFailure.Compaction
            directory = struct.unpack_from("<I", data, section)[0]
            for index in layout.retained_indices:
                first = struct.unpack_from("<I", data, section + directory + index * 8)[
                    0
                ]
                # The two original post-source consumers use bitmap bits0/1.
                # Other record namespaces need a separate lifetime contract.
                if not 0 < struct.unpack_from("<I", data, section + first)[0] < 4:
                    return IdentitySourceFailure.Compaction
            facts[at, mask] = IdentityCompaction(root, at, layout, rebind)
            mask = mask << struct.unpack_from("<I", data, section + 4)[0] & 0xFFFFFFFF
            compacted = True
        pending.extend((target, mask, compacted) for target in graph.get(at, ()))
    if {fact.offset for fact in facts.values()} != {at for _, at in compactions}:
        return IdentitySourceFailure.Compaction
    return tuple(facts[key] for key in sorted(facts))


def member_if_predicates(
    data: bytes, programs: dict, fields: _TaskFields, executable: bytes
) -> tuple[MemberIfPredicate, ...] | IdentitySourceFailure:
    """Reaching Work definitions use shared CFG edges, never a second IF walk."""
    if any(
        hashlib.sha256(native_bytes(executable, at, width)).hexdigest() != digest
        for at, width, digest in _MEMBER_WINDOWS
    ):
        return IdentitySourceFailure.Native
    switches = {
        0x80055EE8: struct.unpack("<7I", native_bytes(executable, 0x800112D8, 28)),
        0x80055F70: struct.unpack("<44I", native_bytes(executable, 0x800112F8, 176)),
    }
    if not native_nonyielding(executable, 0x80055E8C, switches):
        return IdentitySourceFailure.Native
    facts = []
    for key, frame in fields.frames:
        rows = {r["offset"]: r for r in programs[key]["commands"]}
        graph = dict(frame.edges)
        roles = tuple(
            (task, depth) for owner, task, depth in fields.entries if owner == key
        )
        if not roles or any(task not in (0, 1) or depth != 0 for task, depth in roles):
            continue
        prefixes = {}
        for row in rows.values():
            if row["kind"] != "if":
                continue
            cursor = row["next"]
            while cursor in rows:
                test = rows[cursor]
                packet = data[cursor : test["next"]]
                if test["opcode"] == 0x3E:
                    if (
                        len(packet) != 6
                        or packet[:3] != b"\x3e\0\x06"
                        or packet[3] >= 7
                        or cursor % 2
                    ):
                        break
                    prefixes[cursor] = row["offset"]
                elif not (
                    test["kind"] == "flag_check"
                    or test["opcode"] == 0x23
                    and packet[1] == 0
                    and packet[3] < 7
                    or test["opcode"] == 0x86
                ):
                    break
                cursor = test["next"]
        # Unknown incoming Work is a real reaching definition. A new explicit
        # canonical player Work_set kills it; no sampled player pointer is read.
        definitions = {at: set() for at in rows}
        definitions[programs[key]["entry"]].add(-1)
        changed = True
        while changed:
            changed = False
            for at in sorted(rows):
                incoming = definitions[at]
                if not incoming:
                    continue
                row = rows[at]
                opcode = row["opcode"]
                if opcode == 0x2E:
                    outgoing = {at}
                elif (
                    opcode in (0, 6, 7, 8, 0x21, 0x22, 0x23, 0x3E, 0x44, 0x6C)
                    or opcode == 4
                    and data[at + 1 : at + 3] == b"\xff\x18"
                ):
                    # These bound effects preserve current task+154. AUTO can
                    # allocate only2..9, disjoint from these initial owners0/1.
                    outgoing = incoming
                else:
                    outgoing = {-1}
                for target in graph.get(at, ()):
                    added = outgoing - definitions[target]
                    if added:
                        definitions[target].update(added)
                        changed = True
        for at, if_at in sorted(prefixes.items()):
            work = definitions[at]
            cells = tuple(
                sorted(
                    {
                        index
                        for pos, field, index, writing in frame.accesses
                        if pos == at and field is ControlField.IfTarget and not writing
                    }
                )
            )
            if (
                work
                and -1 not in work
                and all(data[d : rows[d]["next"]] == b"\x2e\x01\0" for d in work)
                and cells
                and all(cell in range(0xC0, 0xE0, 4) for cell in cells)
            ):
                facts.append(
                    MemberIfPredicate(
                        key, at, if_at, tuple(sorted(work)), tuple(sorted(roles)), cells
                    )
                )
    return tuple(facts)


def identity_primitive_reservations(
    data: bytes,
    room: dict,
    profile: dict,
    fields: _TaskFields,
    writes: ScenarioSourceWriteWitnesses,
    executable: bytes,
    compactions: tuple[IdentityCompaction, ...],
    owner: IdentityFilteringPolicy,
) -> tuple[IdentityPrimitiveReservation, ...] | IdentitySourceFailure:
    """Compose a positive one-pass reservation with normal allocator ownership.

    This is an unsealed effect, never a numeric free-tail or startup1F receipt.
    """
    from games.re2.identity_filtering import IdentityFilteringPolicy

    assert type(owner) is IdentityFilteringPolicy
    programs = room["programs"]
    rows = [(key, r) for key, p in programs.items() for r in p["commands"]]
    locations = [(key, r) for key, r in rows if r["opcode"] == 0x5D]
    if not locations:
        return ()
    if owner is not IdentityFilteringPolicy.TrustedNormalEngine:
        return IdentitySourceFailure.Allocation
    windows = (
        (
            0x800582F0,
            512,
            "8dd5d1fe99af691b8e3b83fe9f51dbc7ec69175c53675801b974edd9119945ca",
        ),
        (
            0x8009DDCC,
            104,
            "49bfdd9e4377a72bd5b4d90a70be34fb47ddfd63f6b0aa8123b07d4385253593",
        ),
        (
            0x80052F3C,
            388,
            "9640bd4f67bf1e37b43e99bc78768185e283e7de8b5609f208192415d16d23db",
        ),
    )
    if (
        any(
            hashlib.sha256(native_bytes(executable, at, width)).hexdigest() != digest
            for at, width, digest in windows
        )
        or int.from_bytes(native_bytes(executable, 0x800A74C8 + 0x5D * 4, 4), "little")
        != 0x800582F0
        or native_bytes(executable, 0x80052FB0, 8) != bytes.fromhex("0e80013ccd8c20a0")
        or int.from_bytes(native_bytes(executable, 0x800535B8, 4), "little")
        != 0x0C014BCF
        or not native_nonyielding(executable, 0x800582F0, {})
    ):
        return IdentitySourceFailure.Native
    # The fixed metadata is outside all14 task records. Normal source/object
    # domains are separate; configured flag aliases must also stay separate.
    fixed = ((0x800D8CCD, 1), (0x800D8CC4, 4), (0x800CE32C, 4))
    protected = [
        (0x800D7860, 14 * 0x174),
        (0x800D8CBC, 4),
        (0x800D8CC8, 1),
        (0x800CE5D8, 4),
    ]
    protected.extend(
        (int(r["address_ps1"], 0), r["width"]) for r in profile["flag_banks"]
    )
    layout = profile["runtime_layout"]
    protected.extend(
        (
            int(layout[name], 0),
            layout["aot_capacity"] * 4 if name == "aot_table_address_ps1" else 4,
        )
        for name in (
            "system_flags_address_ps1",
            "status_flags_address_ps1",
            "loaded_rdt_address_ps1",
            "aot_table_address_ps1",
        )
    )
    if any(
        at < start + width and start < at + size
        for at, size in fixed
        for start, width in protected
    ):
        return IdentitySourceFailure.Allocation
    # One buffer publication per initialization. Multiple sites, even on
    # different symbolic branches, need an explicit release/rebind relation.
    if len(locations) != 1:
        return IdentitySourceFailure.Allocation
    key, row = locations[0]
    at = row["offset"]
    packet = data[at : row["next"]]
    if len(packet) != 2 or packet[0] != 0x5D or packet[1] == 0:
        # Count0 skips PC+2 and return1 in the original native handler.
        return IdentitySourceFailure.Allocation
    references = {}
    for caller, command in rows:
        if command["kind"] == "call":
            references.setdefault(f"17:{command['procedure']}", []).append(
                (caller, command["offset"])
            )
    chain, members, current = [], {key}, key
    while current != "17:0":
        incoming = references.get(current, [])
        if len(incoming) != 1:
            return IdentitySourceFailure.Allocation
        caller, callsite = incoming[0]
        if caller in members:
            return IdentitySourceFailure.Allocation
        chain.append((caller, callsite, current))
        members.add(caller)
        current = caller
    if (
        references.get("17:0")
        or any(
            target in members and (origin != "native" or target != "17:0")
            for origin, _, target, _ in fields.producers
        )
        or any(target in members for _, _, target in fields.replacements)
    ):
        return IdentitySourceFailure.Allocation
    if {(task, depth) for entry, task, depth in fields.entries if entry == "17:0"} != {
        (1, 0)
    }:
        return IdentitySourceFailure.Allocation
    frames = dict(fields.frames)
    if any(
        target < before
        for member in members
        for before, targets in frames[member].edges
        for target in targets
    ):
        return IdentitySourceFailure.Allocation
    chain.reverse()
    task_depths = tuple(
        sorted((task, depth) for entry, task, depth in fields.entries if entry == key)
    )
    if task_depths != ((1, len(chain)),) or at not in frames[key].reached:
        return IdentitySourceFailure.Allocation
    anchor = chain[0][1] if chain else at
    compaction_locations = {(f.program, f.offset) for f in compactions}
    if any(
        (program, command["offset"]) not in compaction_locations
        or program != "17:0"
        or command["offset"] >= anchor
        for program, command in rows
        if command["opcode"] == 0x6C
    ):
        return IdentitySourceFailure.Allocation
    dependencies = [(at, row["next"])]
    dependencies.extend((callsite, callsite + 2) for _, callsite, _ in chain)
    if any(
        copy.target_offset < end and begin < copy.target_offset + copy.width
        for copy in writes.copies
        for begin, end in dependencies
    ):
        return IdentitySourceFailure.Allocation
    # The normal initialized allocator transfers its actual current interval
    # [F,F+1352*N). Earlier Actor44 allocations and temporary releases preserve
    # live owners under that same premise. No numeric F/free-count is invented,
    # and neither compacted source floor is used as the later allocator cursor.
    # 1352 is13 fixed table rows * two primitives *52 bytes, not a capacity.
    return (
        IdentityPrimitiveReservation(
            hashlib.sha256(data).hexdigest(),
            key,
            at,
            packet[1],
            packet[1] * 13 * 2 * 52,
            task_depths,
            tuple(chain),
        ),
    )
