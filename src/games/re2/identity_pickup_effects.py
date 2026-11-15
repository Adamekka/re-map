"""RE2-SCENARIO-013: ordinary pickup filtering, with no delivery/presence right."""

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum

from games.bit_flags import msb_flag_location
from games.re2.event_presence import presence_counter_indices
from games.re2.native_control import native_bytes, native_nonyielding
from games.re2.normal_engine_binding import (
    NORMAL_ENGINE_BINDING_SHA256,
    semantic_profile_digest,
    typed_binding_digest,
)
from games.re2.positive_entry_domain import _NativeIdentityEntryRoles
from games.re2.scenario_selection import ScenarioSourceWriteWitnesses
from games.re2.script_control_limits import programs_digest
from games.re2.startup_declarations import BoundStartupDeclarations


class NormalPickupFailure(Enum):
    Binding = "ordinary pickup native/source binding mismatch"
    Domain = "ordinary pickup physical origin or controller is unsupported"
    Lifetime = "ordinary pickup source lifetime or UI owner is unproved"


class PickupPhysical(Enum):
    Retained = "Reset retains the physical creator model and flag"


@dataclass(frozen=True)
class PickupOrigin:
    program: str
    offset: int
    width: int
    payload: int
    item_type: int
    amount: int
    global_id: int
    # Reset retains the physical creator's model/flag. This explicit variant
    # avoids treating an absent Reset field as a default controller value.
    physical: tuple[int, int] | PickupPhysical


@dataclass(frozen=True)
class NormalPickupFilteringEffect:
    slot: int
    source_sha256: str
    programs_sha256: str
    dependencies_sha256: str
    origins: tuple[PickupOrigin, ...]
    native_windows: tuple[tuple[int, int, str], ...]
    source_effects: tuple[tuple[int, int, str], ...]
    global_work: tuple[tuple[int, int], ...]
    acquisition_bank: tuple[int, int]
    inventory_extent: tuple[int, int]
    object_writes: tuple[tuple[int, int], ...]
    disabled_counters: frozenset[int]
    header_timeline: tuple[int, int, int, int]


# The exact original windows/table images bind the inspected normal player,
# UI/input/Message/resource owners. They are not arbitrary callback contracts.
_PICKUP_WINDOWS = (
    (
        0x800514EC,
        40,
        "4962ddf6012ab61a5aed6b86ebb5a77b0dc6baa863c9bd1796c5536bc6331c68",
    ),
    (
        0x80051884,
        188,
        "69ecd0cf14b326dab9e565efe2baa10d580609d0b41cad3dca30d088e4973ee2",
    ),
    (
        0x800551C8,
        152,
        "75b63c9e98d72d170818720da3e2dfd3dc8ece23d0b6d92f68a4f12cacbacf50",
    ),
    (
        0x80054CD4,
        320,
        "663f30109040ffdf804e7438d38eed01cce8850a33f90d176e54bf94cf550083",
    ),
    (
        0x80055008,
        332,
        "82154a90a52b537af4ace9d22dece65a23e55cac09cb3a5661b98a29bc0f5945",
    ),
    (
        0x80055154,
        116,
        "3ac89bd618207ddc7c84953e22b53de29436d99cf95566b48ba2ad5cac9b3b05",
    ),
    (0x8003E1D4, 8, "6d64edf91449c1b17746c1ef18afa2eb25c70bdf1322ab3df5a2630993b7e2f1"),
    (
        0x8003E1DC,
        312,
        "3c8a045f20add4fa549526c47347bc060dc227805285ef98b7697331b3e1e675",
    ),
    (
        0x8002593C,
        1228,
        "bdbcecd8955659d54591cd239b4064ee4f9f65ed83b9379291a61728621be2e5",
    ),
    (
        0x80049E48,
        80,
        "193ba95f11b3621ace41ed0f875690ffd1eb83eba7bc0fb4d25b5645726dbdd4",
    ),
    (
        0x8004A328,
        20,
        "3156bdc16d595c045c7aeba3fb700071847333bd592dd8055a3c3a9609e8bf87",
    ),
    (
        0x80031E80,
        720,
        "1be596d73ada91111855956877511dff820e2b7844e889514bd25d28442d483a",
    ),
    (
        0x800689BC,
        792,
        "d71d738060485003219e926a308f433be5fb64ecaaccf81b7ffed8bba408490d",
    ),
    (
        0x80068CD4,
        564,
        "ba9c26fa39a189d6d0c8014408ae75b6ba7d4c06bfe1a276f7765c8d00ca83e2",
    ),
    (
        0x80068F08,
        148,
        "b3734e13a4f500b9f0a4e796ccf61e11039634218923e8f3838d9280405b2711",
    ),
    (
        0x80071BA0,
        628,
        "933c673fbe05a01d8adc7473fbcedfe3ca7c157dc1f4b6506747ea137c5c7752",
    ),
    (
        0x80071E14,
        160,
        "887cb8516d8770d720c166a8c1abcade5c10c302ed1d73e0e86e25b1a806cc42",
    ),
    (
        0x80071EB4,
        412,
        "87c68dfd3ff099733be152ab791ba68df2391b4b7f823aa0764238fa619092e1",
    ),
    (
        0x80072050,
        1124,
        "cb3f4ba80ea25ea3991a79e8a42db0ba23b0813921e67724bfbba009fcc27462",
    ),
    (
        0x80069668,
        100,
        "8b5158c27fb096f93217086eb124f91b46bc11fd7ee482180bd1502bf3b9e785",
    ),
    (
        0x80069ADC,
        216,
        "7a91c9a61a2d1f2b7f3b12e870b168a21c37f8c000104a96befd9db197d4bfdf",
    ),
    (
        0x8006947C,
        60,
        "31df87b3e94da0b30064aec5bc746626e80be1e578c16b3d632b0cb675ee725e",
    ),
    (
        0x80069590,
        32,
        "899479a7a32d91cdfb3e3ce06ef5197b937121bdd883ef3dd312819254170698",
    ),
    (
        0x80069BB4,
        140,
        "ffba564965906681b0dc29e990979af5cc54a5bad4c1255fd4341d38806b7b34",
    ),
    (
        0x8007730C,
        40,
        "aaa532ce35461ce0a5be626a7f663193b88eac6d73f9e0f32c25a2183a39c2ac",
    ),
    (
        0x800A73C4,
        60,
        "bd5f3053faab22c27a3926da9d199b7af16fe18e20f9b82c325f740427b8ba0f",
    ),
    (
        0x800A74C8,
        576,
        "b33161ce7d3dcade6d8e32b0d4682f50cb6322f6ec9b0d7988e13db7dbfad1aa",
    ),
    (
        0x800A936C,
        60,
        "de11655d8871f2a6f82da9ef5fca4a21338d0b1170cc9e347aa371bfbcbc00f0",
    ),
    (
        0x800A9C9C,
        20,
        "7b3d99eed8835fd1d3674cbd7a5f298ba57d565858a87a233955e65eb3e9f31c",
    ),
    (
        0x80011D64,
        84,
        "eab4530f8c6a7dcbb11f966f890eead55d7a30784dd36597cea303f81bdcb2d4",
    ),
    (0x800A409C, 4, "385d0a9702db443d6c7c97bd42792333b4b2826a729f484420cad756d724d085"),
    (
        0x80010EF8,
        28,
        "6ac53420b5982e989ab9e24afbdf98764304d8398f9f05e7846454e29ac6a851",
    ),
    (
        0x800A93A8,
        16,
        "cc430b8aac64d735415cd8a0534fae3549d4e6c14eda586af05259b8eae44521",
    ),
    (
        0x8002959C,
        1492,
        "2a4dadbc425569c4f0fd86f6fcb15dac9bb23c79d4e3fe44d80a3d73b29cba2f",
    ),
    (
        0x8008E1F4,
        652,
        "682f40cbb1b20d5bfc9765eceae9cc976e3cb69b6d63d0ba10efc6858e65b97e",
    ),
)

_UI_WORK = (
    (0x800EAD94, 4),
    (0x800CE5D8, 4),
    (0x800E873F, 1),
    (0x800D4231, 1),
    (0x800D5C00, 1),
    (0x800DF348, 8),
    (0x800DF38C, 4),
    (0x800DCBCC, 4),
)


@dataclass(frozen=True)
class PickupSourceDomain:
    origins: tuple[PickupOrigin, ...]
    source_effects: tuple[tuple[int, int, str], ...]
    acquisition_bank: tuple[int, int]


def normal_pickup_source_domain(
    data: bytes, room: dict, writes: ScenarioSourceWriteWitnesses, slot: int
) -> PickupSourceDomain | NormalPickupFailure:
    """Pure unsealed physical packet seam, also used by mutation regressions."""
    if (
        type(slot) is not int
        or not 0 <= slot < 32
        or type(writes) is not ScenarioSourceWriteWitnesses
    ):
        return NormalPickupFailure.Domain
    stage = room["stage"]
    if type(stage) is not int or not 0 <= stage < 9:
        return NormalPickupFailure.Domain
    address, width = (0x800D48BC, 32) if stage < 4 else (0x800D48DC, 16)
    origins, effects = (
        [],
        [(44, 4, "native UI header9 temporary binding and restoration")],
    )
    rows = [(key, r) for key, p in room["programs"].items() for r in p["commands"]]
    creators = 0
    for key, row in rows:
        if (
            row["kind"] not in ("door", "item", "interaction", "reset")
            or data[row["offset"] + 1] != slot
        ):
            continue
        at = row["offset"]
        packet = data[at : row["next"]]
        if row["kind"] == "reset":
            if len(packet) != 10 or packet[2] != 2 or packet[3] & 0x80:
                return NormalPickupFailure.Domain
            operand, physical = 4, PickupPhysical.Retained
        elif row["kind"] == "item" and row["opcode"] in (0x4E, 0x69):
            four = row["opcode"] == 0x69
            if (
                len(packet) != (30 if four else 22)
                or packet[2] != 2
                or not four
                and packet[3] & 0x80
            ):
                return NormalPickupFailure.Domain
            operand = 22 if four else 14
            model, flag = packet[operand + 6 : operand + 8]
            if model != 255 and model >= min(data[2], 32) or flag not in (0, 1):
                return NormalPickupFailure.Domain
            physical = (model, flag)
            creators += 1
            effects.append(
                (at + 2, 1, "accepted selected kind2 becomes disabled kind0")
            )
            if four:
                effects.append((at + 3, 1, "physical69 constructor sets geometry80"))
        else:
            return NormalPickupFailure.Domain
        item_type, amount, gid = struct.unpack_from("<3H", packet, operand)
        if (
            item_type >= 104
            or 14 <= item_type <= 18
            or item_type == 82
            or gid >= width * 8
        ):
            return NormalPickupFailure.Domain
        origins.append(
            PickupOrigin(
                key, at, len(packet), operand, item_type, amount, gid, physical
            )
        )
    if not creators:
        return NormalPickupFailure.Domain
    physical_origins = [o for o in origins if type(o.physical) is tuple]
    if any(o.item_type == 30 for o in origins):
        # Reset changes the installed descriptor, not its own packet. Any
        # same-slot type30 alternative can therefore override each physical
        # creator's amount after selection by the native callback.
        effects.extend(
            (o.offset + o.payload + 2, 2, "SYSTEM40 type30 amount override to2")
            for o in physical_origins
        )
    if any(o.physical is PickupPhysical.Retained for o in origins):
        effects.extend(
            (o.offset + 2, 2, "Reset retains physical geometry and stores kind/SAT")
            for o in physical_origins
        )
        effects.extend(
            (
                o.offset + o.payload,
                6,
                "Reset copies type/amount/GID into physical descriptor",
            )
            for o in physical_origins
        )
    explicit = [(r.offset, r.width) for r in writes.record_writes]
    explicit.extend(
        (r.offset, r.width)
        for effect in writes.partitions.source_writes
        for r in effect.writes
    )
    explicit.extend((r.target_offset, r.width) for r in writes.copies)
    if any(
        at < start + size and start < at + width
        for at, width in explicit
        for start, size in [(44, 4), *((r.offset, r.width) for r in origins)]
    ) or any(row["opcode"] == 0x6C for _, row in rows):
        # Pending/routine6 may span ordinary passes. No retained pointer
        # contract currently qualifies compaction, even if a source is entered.
        return NormalPickupFailure.Lifetime
    return PickupSourceDomain(tuple(origins), tuple(effects), (address, width))


def normal_pickup_filtering_effect(
    data: bytes,
    room: dict,
    profile: dict,
    bound: BoundStartupDeclarations,
    source: _NativeIdentityEntryRoles,
    writes: ScenarioSourceWriteWitnesses,
    slot: int,
) -> NormalPickupFilteringEffect | NormalPickupFailure:
    """Bind every raw alternative before the complete entered operative preflight."""
    if (
        type(slot) is not int
        or not 0 <= slot < 32
        or type(source) is not _NativeIdentityEntryRoles
        or type(writes) is not ScenarioSourceWriteWitnesses
        or hashlib.sha256(data).hexdigest() != room["sha256"]
        or not bound.ordinary_ingress.covers(data, room)
        or typed_binding_digest((bound.entry_resources, bound.declarations))
        != NORMAL_ENGINE_BINDING_SHA256
    ):
        return NormalPickupFailure.Binding
    executable = bound.entry_resources.executable
    if not _PICKUP_WINDOWS or any(
        hashlib.sha256(native_bytes(executable, at, width)).hexdigest() != digest
        for at, width, digest in _PICKUP_WINDOWS
    ):
        return NormalPickupFailure.Binding
    switches = {
        0x8003E210: struct.unpack("<7I", native_bytes(executable, 0x80010EF8, 28))
    }
    if not all(
        native_nonyielding(executable, at, switches)
        for at in (0x800514EC, 0x80051884, 0x8003E1DC)
    ):
        return NormalPickupFailure.Binding
    domain = normal_pickup_source_domain(data, room, writes, slot)
    if type(domain) is not PickupSourceDomain:
        return domain
    address, width = domain.acquisition_bank
    bank_id = 8 if room["stage"] < 4 else 34
    banks = [r for r in profile["flag_banks"] if r["bank"] == bank_id]
    if (
        len(banks) != 1
        or int(banks[0]["address_ps1"], 0) != address
        or banks[0]["width"] != width
    ):
        return NormalPickupFailure.Binding
    layout = profile["runtime_layout"]
    numeric = [(int(r["address_ps1"], 0), r["width"]) for r in profile["flag_banks"]]
    numeric.extend(
        (int(layout["script_counter_address_ps1"], 0) + 2 * i, 2)
        for i in presence_counter_indices(profile)
    )
    numeric.extend(
        (o.record.address, o.record.width) for o in writes.partitions.objects
    )
    if any(
        at < start + size and start < at + width
        for at, width in numeric
        for start, size in _UI_WORK
    ):
        return NormalPickupFailure.Lifetime
    # Logical bank labels do not identify storage. STOP and STATUS writers
    # remain ordinary source effects; only UI-selected work is excluded here.
    for row in (r for p in room["programs"].values() for r in p["commands"]):
        if row["kind"] == "flag_write":
            bank = next(r for r in profile["flag_banks"] if r["bank"] == row["bank"])
            word, _ = msb_flag_location(int(bank["address_ps1"], 0), row["bit"])
            if any(word < at + size and at < word + 4 for at, size in _UI_WORK):
                return NormalPickupFailure.Lifetime
    return NormalPickupFilteringEffect(
        slot,
        room["sha256"],
        programs_digest(room["programs"]),
        typed_binding_digest(
            (
                data,
                semantic_profile_digest(profile),
                source,
                writes,
                bound.ordinary_ingress,
            )
        ),
        domain.origins,
        _PICKUP_WINDOWS,
        domain.source_effects,
        _UI_WORK,
        (address, width),
        # Retain the no-space sentinel and byte-index alternatives. This is
        # only a bounded write extent, never a free-slot or capacity assertion.
        (0x800D4A38, 0x800D4E38),
        tuple(
            sorted(
                {
                    (0x800D0324 + o.physical[0] * 0x1F8, 4)
                    for o in domain.origins
                    if type(o.physical) is tuple and o.physical[0] != 255
                }
            )
        ),
        frozenset((0, 1)),
        # Header9 is saved in DCBCC and restored in the delay slot before
        # native task0 release. UI yields never imply ordinary SCD progress.
        (0x800DCBCC, 0x800A93A8, 0x80068EE4, 0x8003210C),
    )
