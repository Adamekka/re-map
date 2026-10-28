"""Source-bound continuation receipts for audited synchronous setup effects."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum

from games.re2.clip_effect_proof import ClipEffectProof, ClipEffectSupport


class StartupEffectAuditSupport(Enum):
    Unaudited = "unaudited"


@dataclass(frozen=True)
class StartupEffectAuditConfig:
    audit: str
    executable_sha256: str

    def __post_init__(self) -> None:
        assert self.audit == "slus00748-sca-clipping-v1"
        assert (
            self.executable_sha256
            == "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
        )


def startup_effect_audit(
    profile: dict,
) -> StartupEffectAuditConfig | StartupEffectAuditSupport:
    if "startup_effect_audit" not in profile:
        return StartupEffectAuditSupport.Unaudited
    raw = profile["startup_effect_audit"]
    if (
        type(raw) is not dict
        or raw.keys() != {"audit", "executable_sha256"}
        or type(raw["audit"]) is not str
        or type(raw["executable_sha256"]) is not str
        or raw["audit"] != "slus00748-sca-clipping-v1"
        or raw["executable_sha256"]
        != "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
        or type(profile.get("executable_identity")) is not str
        or profile["executable_identity"].rpartition(" SHA256 ")[2]
        != raw["executable_sha256"]
    ):
        raise ValueError("invalid or unsupported RE2 startup effect audit")
    return StartupEffectAuditConfig(**raw)


@dataclass(frozen=True)
class StartupEffectReceipt:
    source_sha256: str
    locations: frozenset[tuple[str, int]]
    predicate_flags: frozenset[tuple[int, int]]

    def __post_init__(self) -> None:
        assert type(self.source_sha256) is str and len(self.source_sha256) == 64
        assert all(value in "0123456789abcdef" for value in self.source_sha256)
        assert type(self.locations) is frozenset and all(
            type(key) is str and type(offset) is int and offset >= 0
            for key, offset in self.locations
        )
        assert type(self.predicate_flags) is frozenset and all(
            type(bank) is int
            and 0 <= bank <= 255
            and type(bit) is int
            and 0 <= bit <= 255
            for bank, bit in self.predicate_flags
        )

    def locations_for(
        self,
        data: bytes,
        programs: dict,
        condition_flags: frozenset[tuple[int, int]],
        fixed_flags: frozenset[tuple[int, int, int]],
    ) -> frozenset[tuple[str, int]]:
        assert hashlib.sha256(data).hexdigest() == self.source_sha256, (
            "startup receipt belongs to another source"
        )
        requested = {(bank, bit) for bank, bit, _ in fixed_flags} | {
            (row["bank"], row["bit"])
            for program in programs.values()
            for row in program["commands"]
            if row["kind"] == "flag_check"
            and (row["bank"], row["bit"]) in condition_flags
        }
        # A broader query needs its own preservation check. Unused configured
        # predicates do not constrain this source's exported conditions.
        return self.locations if requested <= self.predicate_flags else frozenset()


def certify_startup_effects(
    data: bytes,
    room: dict,
    predicate_flags: frozenset[tuple[int, int]],
    banks: dict[int, tuple[int, int]],
    clipping: ClipEffectProof | ClipEffectSupport,
    audit: StartupEffectAuditConfig | StartupEffectAuditSupport,
) -> StartupEffectReceipt | StartupEffectAuditSupport:
    assert audit is StartupEffectAuditSupport.Unaudited or isinstance(
        audit, StartupEffectAuditConfig
    )
    assert clipping is ClipEffectSupport.Unaudited or isinstance(
        clipping, ClipEffectProof
    )
    if audit is StartupEffectAuditSupport.Unaudited:
        return audit
    # Imports stay here because the source decoder itself uses the presence
    # walker. Native validation runs only after that decoder is initialized.
    from games.re2.room_write_partitions import ScaWritePartition, sca_write_partition

    if not isinstance(clipping, ClipEffectProof):
        return StartupEffectAuditSupport.Unaudited
    required = predicate_flags
    candidates = predicate_flags | frozenset(
        (row["bank"], row["bit"])
        for program in room["programs"].values()
        for row in program["commands"]
        if row["kind"] == "flag_check"
    )
    for bank, bit in candidates:
        if bank not in banks or not 0 <= bit < banks[bank][1] * 8:
            return StartupEffectAuditSupport.Unaudited
    # This revision audit protects the two native game-context words. SCA
    # stores remain in loaded source memory; task/heap aliases need a separate
    # theorem rather than inheriting the ordinary flag-bank interpretation.
    predicate_flags = frozenset(
        (bank, bit)
        for bank, bit in candidates
        if banks[bank][0] + bit // 32 * 4
        in (clipping.system_address, clipping.status_address)
    )
    programs = room["programs"]
    clipping_commands = [
        (key, row["offset"])
        for key, program in programs.items()
        for row in program["commands"]
        if row["opcode"] == 0x73
    ]
    if clipping_commands:
        predicate_flags = frozenset(
            (bank, bit)
            for bank, bit in predicate_flags
            if all(
                clipping.preserves_context(
                    data,
                    programs,
                    key,
                    offset,
                    {banks[bank][0] + bit // 32 * 4: 0x80000000 >> (bit % 32)},
                )
                for key, offset in clipping_commands
            )
        )
    if not required <= predicate_flags:
        return StartupEffectAuditSupport.Unaudited
    words = {}
    for bank, bit in predicate_flags:
        address = banks[bank][0] + bit // 32 * 4
        words[address] = words.get(address, 0) | (0x80000000 >> (bit % 32))
    spans = set(
        (row["offset"], row["next"])
        for program in programs.values()
        for row in program["commands"]
    )
    # A numeric operand must not also decode as another command. Otherwise a
    # source Copy admitted by the fixed-context proof could change setup code.
    ordered = sorted(spans)
    if any(first[1] > second[0] for first, second in zip(ordered, ordered[1:])):
        return StartupEffectAuditSupport.Unaudited
    protected = [
        (
            room["section_offsets"][section],
            max(
                program["limit"]
                for key, program in programs.items()
                if key.startswith(f"{section}:")
            ),
        )
        for section in (16, 17)
    ]
    locations = set()
    for key, program in programs.items():
        for row in program["commands"]:
            position, opcode = row["offset"], row["opcode"]
            if opcode == 0x37:
                collision = sca_write_partition(
                    data, tuple(room["section_offsets"]), position
                )
                if isinstance(collision, ScaWritePartition) and not any(
                    collision.asset.offset < limit
                    and start < collision.asset.offset + collision.asset.width
                    for start, limit in protected
                ):
                    locations.add((key, position))
            elif opcode == 0x73 and clipping.preserves_context(
                data, programs, key, position, words
            ):
                locations.add((key, position))
    if not locations:
        return StartupEffectAuditSupport.Unaudited
    return StartupEffectReceipt(
        hashlib.sha256(data).hexdigest(), frozenset(locations), predicate_flags
    )
