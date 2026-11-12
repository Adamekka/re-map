"""RE2-RESET-001: source possibilities, without presence or completeness authority."""

from __future__ import annotations

import hashlib
import struct
from dataclasses import dataclass
from enum import Enum


class ResetCandidateSupport(Enum):
    Unaudited = "revision has no reset candidate catalog"


@dataclass(frozen=True)
class ResetCandidateConfig:
    executable_sha256: str

    def __post_init__(self) -> None:
        assert (
            self.executable_sha256
            == "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
        )


def reset_candidate_config(
    profile: dict,
) -> ResetCandidateConfig | ResetCandidateSupport:
    if "reset_candidate_catalog" not in profile:
        return ResetCandidateSupport.Unaudited
    raw = profile["reset_candidate_catalog"]
    digest = "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
    if (
        type(raw) is not dict
        or raw != {"schema": 1, "executable_sha256": digest}
        or type(raw["schema"]) is not int
        or profile["profile_id"] != "re2_leon_a_slus00748"
        or profile["executable_identity"] != "SLUS_007.48 SHA256 " + digest
    ):
        raise ValueError("invalid RE2 reset candidate revision opt-in")
    return ResetCandidateConfig(digest)


@dataclass(frozen=True)
class DescriptorOrigin:
    offset: int
    four_point: bool

    def __post_init__(self) -> None:
        assert type(self.offset) is int and self.offset >= 100
        assert type(self.four_point) is bool


class NullOrigin(Enum):
    UnregisteredAlias = "unregistered_null_alias"


def decode_item_resets(data: bytes, programs: dict) -> list[dict]:
    """Decode each physical Reset once, including aliased procedure tables."""
    resets = {}
    for program in programs.values():
        for row in program["commands"]:
            if row["opcode"] != 0x46:
                continue
            packet = data[row["offset"] : row["next"]]
            if (
                len(packet) != 10
                or packet[0] != 0x46
                or row["kind"] != "reset"
                or row["slot"] != packet[1]
                or row["interaction"] != packet[2]
                or row["data"] != list(packet[4:])
            ):
                raise ValueError("RE2 reset command does not match its source")
            if packet[2] == 2:
                item_type, amount, gid = struct.unpack_from("<3H", packet, 4)
                resets[row["offset"]] = {
                    "offset": row["offset"],
                    "slot": packet[1],
                    "type": item_type,
                    "amount": amount,
                    "global_id": gid,
                    "sat": packet[3],
                }
    return [resets[offset] for offset in sorted(resets)]


def compile_reset_candidates(
    data: bytes,
    room: dict,
    config: ResetCandidateConfig,
    profile: dict,
) -> dict:
    """Enumerate origins; shared native write bounds grant no entry/absence proof."""
    from games.re2.room_data import OPCODE_WIDTHS
    from games.re2.scenario_selection import (
        ScenarioSelectionFailure,
        ScenarioSourceWriteWitnesses,
        scenario_source_write_witnesses,
    )

    assert isinstance(config, ResetCandidateConfig)
    if reset_candidate_config(profile) != config:
        raise ValueError("RE2 reset candidate authority disagrees with its revision")
    # Derive bounds here from the same source rather than accepting a receipt
    # from another room or an earlier candidate/source revision.
    writes = scenario_source_write_witnesses(data, room, profile)
    if len(data) != room["size"] or hashlib.sha256(data).hexdigest() != room["sha256"]:
        raise ValueError("RE2 reset candidate source binding mismatch")
    commands = {
        r["offset"]: r for p in room["programs"].values() for r in p["commands"]
    }
    descriptors = []
    protected = [(0, 100)]
    for section in (16, 17):
        offset = room["section_offsets"][section]
        if offset:
            protected.append(
                (offset, offset + int.from_bytes(data[offset : offset + 2], "little"))
            )
    # Numeric payloads may be copied. Control operands, descriptor identity and
    # kind2/kind5 payloads cannot be treated as stable after an intersecting write.
    control = {
        1,
        3,
        4,
        5,
        6,
        7,
        8,
        15,
        17,
        18,
        19,
        20,
        21,
        22,
        23,
        24,
        25,
        26,
        27,
        28,
        29,
        0x8D,
    }
    for offset, row in sorted(commands.items()):
        opcode = row["opcode"]
        packet = data[offset : row["next"]]
        if len(packet) != OPCODE_WIDTHS[opcode] or packet[0] != opcode:
            raise ValueError("RE2 reset candidate command does not match its source")
        protected.append((offset, offset + 1))
        if opcode == 0x09:
            # Native Sleep advances PC by one, exposing its embedded 0A
            # helper as an opcode. Its duration halfword remains numeric.
            protected.append((offset + 1, offset + 2))
        if opcode in control or row["kind"] == "award":
            protected.append((offset, row["next"]))
        if opcode == 0x0D:
            protected.append((offset, offset + 4))
        if opcode in (0x2C, 0x3B, 0x4E, 0x67, 0x68, 0x69):
            four_point = opcode in (0x67, 0x68, 0x69)
            if (
                len(packet) != OPCODE_WIDTHS[opcode]
                or packet[1] >= 32
                or (not four_point and packet[3] & 0x80)
            ):
                raise ValueError("invalid RE2 reset candidate descriptor geometry")
            descriptors.append(
                {
                    "offset": offset,
                    "slot": packet[1],
                    "opcode": opcode,
                    "four_point": four_point,
                }
            )
            protected.append((offset, offset + 4))
            if packet[2] in (2, 5):
                operand = offset + (22 if four_point else 14)
                protected.append((operand, operand + 6))
        elif opcode == 0x46:
            protected.append((offset, offset + (10 if packet[2] in (2, 5) else 4)))
    candidates = []
    for reset in room["reset_item_candidates"]:
        if reset["slot"] >= 32 or reset["global_id"] >= 256 or reset["sat"] & 0x80:
            raise ValueError("invalid RE2 reset candidate payload")
        packet = struct.pack(
            "<4B3H",
            0x46,
            reset["slot"],
            2,
            reset["sat"],
            reset["type"],
            reset["amount"],
            reset["global_id"],
        )
        if data[reset["offset"] : reset["offset"] + 10] != packet:
            raise ValueError("RE2 reset candidate payload does not match its source")
        origins = [
            {"kind": "descriptor", "offset": d["offset"], "four_point": d["four_point"]}
            for d in descriptors
            if d["slot"] == reset["slot"]
        ]
        # Reset cannot allocate. An empty registry slot aliases physical zero;
        # excluding that possibility requires independent registration authority.
        origins.append({"kind": "unregistered_null_alias"})
        candidates.append({**reset, "origins": origins})
    failure = writes.value if isinstance(writes, ScenarioSelectionFailure) else "none"
    if isinstance(writes, ScenarioSourceWriteWitnesses):
        footprints = [(r.offset, r.width) for r in writes.record_writes]
        footprints.extend((r.target_offset, r.width) for r in writes.copies)
        footprints.extend(
            (r.offset, r.width)
            for w in writes.partitions.source_writes
            for r in w.writes
        )
        if any(
            start < end and begin < start + width
            for start, width in footprints
            for begin, end in protected
        ):
            failure = "source write intersects reset candidate identity or control"
    slots = {row["slot"] for row in candidates}
    descriptors = [row for row in descriptors if row["slot"] in slots]
    return {
        "reset_item_candidates": candidates,
        "reset_candidate_descriptors": descriptors,
        "reset_candidate_source_failure": failure,
    }


def validate_reset_candidates(
    room: dict, config: ResetCandidateConfig | ResetCandidateSupport
) -> None:
    from games.re2.room_data import OPCODE_WIDTHS
    from games.re2.scenario_selection import ScenarioSelectionFailure

    fields = {
        "reset_item_candidates",
        "reset_candidate_descriptors",
        "reset_candidate_source_failure",
    }
    if config is ResetCandidateSupport.Unaudited:
        if fields & room.keys():
            raise ValueError("RE2 reset candidates require a revision opt-in")
        return
    assert isinstance(config, ResetCandidateConfig)
    if (
        not fields <= room.keys()
        or type(room["reset_candidate_source_failure"]) is not str
        or room["reset_candidate_source_failure"]
        not in {
            "none",
            "source write intersects reset candidate identity or control",
            *[failure.value for failure in ScenarioSelectionFailure],
        }
    ):
        raise ValueError("missing RE2 reset candidate source status")
    descriptors = room["reset_candidate_descriptors"]
    candidates = room["reset_item_candidates"]
    if type(descriptors) is not list or type(candidates) is not list:
        raise ValueError("invalid RE2 reset candidate arrays")
    spans = []
    for descriptor in descriptors:
        if (
            type(descriptor) is not dict
            or descriptor.keys() != {"offset", "slot", "opcode", "four_point"}
            or any(type(descriptor[k]) is not int for k in ("offset", "slot", "opcode"))
            or type(descriptor["four_point"]) is not bool
            or descriptor["opcode"] not in (0x2C, 0x3B, 0x4E, 0x67, 0x68, 0x69)
            or not 0 <= descriptor["slot"] < 32
            or descriptor["four_point"] != (descriptor["opcode"] in (0x67, 0x68, 0x69))
            or not 100
            <= descriptor["offset"]
            <= room["size"] - OPCODE_WIDTHS[descriptor["opcode"]]
        ):
            raise ValueError("invalid RE2 reset candidate descriptor")
        spans.append((descriptor["offset"], OPCODE_WIDTHS[descriptor["opcode"]]))
    descriptor_offsets = [d["offset"] for d in descriptors]
    if descriptor_offsets != sorted(set(descriptor_offsets)):
        raise ValueError("unordered RE2 reset candidate descriptors")
    reset_offsets = []
    for row in candidates:
        if (
            type(row) is not dict
            or row.keys()
            != {"offset", "slot", "type", "amount", "global_id", "sat", "origins"}
            or any(
                type(row[k]) is not int
                for k in ("offset", "slot", "type", "amount", "global_id", "sat")
            )
            or not 100 <= row["offset"] <= room["size"] - 10
            or not 0 <= row["slot"] < 32
            or not 0 <= row["type"] <= 65535
            or not 0 <= row["amount"] <= 65535
            or not 0 <= row["global_id"] < 256
            or not 0 <= row["sat"] < 128
            or type(row["origins"]) is not list
        ):
            raise ValueError("invalid RE2 reset item candidate")
        expected = [
            {"kind": "descriptor", "offset": d["offset"], "four_point": d["four_point"]}
            for d in descriptors
            if d["slot"] == row["slot"]
        ] + [{"kind": "unregistered_null_alias"}]
        if row["origins"] != expected or any(
            type(o) is not dict
            or (
                o["kind"] == "descriptor"
                and (type(o["offset"]) is not int or type(o["four_point"]) is not bool)
            )
            for o in row["origins"]
        ):
            raise ValueError("unbound RE2 reset item candidate origins")
        spans.append((row["offset"], 10))
        reset_offsets.append(row["offset"])
    slots = {row["slot"] for row in candidates}
    for item in room["items"] + room["doors"]:
        if item["slot"] not in slots:
            continue
        if not any(
            d["offset"] == item["offset"]
            and d["slot"] == item["slot"]
            and d["four_point"] == item["four_point"]
            for d in descriptors
        ):
            raise ValueError("unbound RE2 reset candidate descriptor")
    spans.sort()
    if reset_offsets != sorted(set(reset_offsets)) or any(
        a + width > b for (a, width), (b, _) in zip(spans, spans[1:])
    ):
        raise ValueError("overlapping or unordered RE2 reset candidate packets")


def tracking_item_candidates(
    room: dict, config: ResetCandidateConfig | ResetCandidateSupport, *, selected: bool
) -> list[dict]:
    """Share one normalized consumer view; legacy proof inputs stay untouched."""
    from games.re2.scenario_items import (
        item_identity_candidates,
        scenario_item_candidates,
    )

    validate_reset_candidates(room, config)
    legacy = (
        scenario_item_candidates(room) if selected else item_identity_candidates(room)
    )
    result = [
        {
            **item,
            "origin": DescriptorOrigin(item["offset"], item["four_point"]),
            "observable": True,
        }
        for item in legacy
    ]
    if config is ResetCandidateSupport.Unaudited:
        return result
    assert isinstance(config, ResetCandidateConfig)
    # The loader and live reader consume this same normalized view so candidate
    # enumeration cannot accidentally become a broader proof interpretation.
    seen = {
        (r["origin"], r["slot"], r["type"], r["global_id"], tuple(r["amounts"]))
        for r in result
    }
    selected_ids = (
        {row["global_id"] for row in room["scenario_item_variants"]}
        if selected
        else set()
    )
    allowed = {(row["global_id"], row["origin"], row["type"]) for row in result}
    allowed_types = {(row["global_id"], row["type"]) for row in result}
    for row in room["reset_item_candidates"]:
        for origin in row["origins"]:
            identity = (
                DescriptorOrigin(origin["offset"], origin["four_point"])
                if origin["kind"] == "descriptor"
                else NullOrigin.UnregisteredAlias
            )
            key = identity, row["slot"], row["type"], row["global_id"], (row["amount"],)
            if key in seen:
                continue
            # Reuse the legacy selection's identity result. Quantity is not a
            # selector: dropping a matching reset amount would cause a false
            # current-identity contradiction. New GIDs gain no scenario proof.
            if row["global_id"] in selected_ids and (
                (row["global_id"], identity, row["type"]) not in allowed
                if isinstance(identity, DescriptorOrigin)
                else (row["global_id"], row["type"]) not in allowed_types
            ):
                continue
            result.append(
                {
                    "origin": identity,
                    "slot": row["slot"],
                    "type": row["type"],
                    "global_id": row["global_id"],
                    "amounts": [row["amount"]],
                    "observable": room["reset_candidate_source_failure"] == "none",
                }
            )
            seen.add(key)
    return result
