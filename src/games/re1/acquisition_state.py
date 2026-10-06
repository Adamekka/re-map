"""Profile-backed acquisition flags shared by live and reconstructed pickups."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass


@dataclass(frozen=True, order=True)
class AcquisitionFlag:
    address: int
    mask: int
    acquired_when_set: bool

    def __post_init__(self) -> None:
        assert type(self.address) is int and 0x80000000 <= self.address < 0x80200000
        assert type(self.mask) is int and 0 < self.mask <= 128
        assert self.mask & (self.mask - 1) == 0
        assert type(self.acquired_when_set) is bool


@dataclass(frozen=True)
class GlobalIdAcquisitionRule:
    first_type: int
    last_type: int
    acquired_when_set: bool


@dataclass(frozen=True)
class FixedAcquisitionRule:
    first_type: int
    last_type: int
    address: int
    mask: int
    acquired_when_set: bool


@dataclass(frozen=True)
class AcquisitionLayout:
    flags_address: int
    flags_width: int
    rules: tuple[GlobalIdAcquisitionRule | FixedAcquisitionRule, ...]

    def __post_init__(self) -> None:
        if (
            type(self.flags_address) is not int
            or type(self.flags_width) is not int
            or not 1 <= self.flags_width <= 32
            or not 0x80000000
            <= self.flags_address
            < self.flags_address + self.flags_width
            <= 0x80200000
        ):
            raise ValueError("acquisition flags require a bounded PS1 byte block")
        covered = set()
        for rule in self.rules:
            if (
                not isinstance(rule, (GlobalIdAcquisitionRule, FixedAcquisitionRule))
                or type(rule.first_type) is not int
                or type(rule.last_type) is not int
                or not 1 <= rule.first_type <= rule.last_type <= 0x53
                or type(rule.acquired_when_set) is not bool
            ):
                raise ValueError("invalid acquisition rule item range or polarity")
            types = set(range(rule.first_type, rule.last_type + 1))
            if types & covered:
                raise ValueError("acquisition rule item ranges overlap")
            covered.update(types)
            if isinstance(rule, FixedAcquisitionRule) and (
                type(rule.address) is not int
                or not 0x80000000 <= rule.address < 0x80200000
                or type(rule.mask) is not int
                or not 0 < rule.mask <= 128
                or rule.mask & (rule.mask - 1)
            ):
                raise ValueError("fixed acquisition rule requires a bounded single bit")
        if covered != set(range(1, 0x54)):
            raise ValueError("acquisition rules must cover every supported item type")

    @staticmethod
    def load(
        raw: list[dict], flags_address: int, flags_width: int
    ) -> AcquisitionLayout:
        def number(value):
            if type(value) is int:
                return value
            if isinstance(value, str):
                return int(value, 0)
            raise ValueError("acquisition rule numbers must be integers")

        if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
            raise ValueError("acquisition rules must be a list of objects")
        rules = []
        for row in raw:
            if (
                not isinstance(row.get("item_types"), list)
                or len(row["item_types"]) != 2
            ):
                raise ValueError("acquisition rule requires a two-value item range")
            first, last = (number(value) for value in row["item_types"])
            if row["index"] == "global_id":
                if set(row) != {"item_types", "index", "acquired_when_set"}:
                    raise ValueError("unexpected GlobalId acquisition rule fields")
                rule = GlobalIdAcquisitionRule(first, last, row["acquired_when_set"])
            elif row["index"] == "fixed":
                if set(row) != {
                    "item_types",
                    "index",
                    "address_ps1",
                    "mask",
                    "acquired_when_set",
                }:
                    raise ValueError("unexpected fixed acquisition rule fields")
                rule = FixedAcquisitionRule(
                    first,
                    last,
                    number(row["address_ps1"]),
                    number(row["mask"]),
                    row["acquired_when_set"],
                )
            else:
                raise ValueError("unsupported acquisition rule index selector")
            rules.append(rule)
        return AcquisitionLayout(flags_address, flags_width, tuple(rules))

    def flag(self, item_type: int, global_id: int) -> AcquisitionFlag:
        if type(item_type) is not int or not 1 <= item_type <= 0x53:
            raise ValueError("unsupported acquisition item type")
        if type(global_id) is not int or not 0 <= global_id <= 255:
            raise ValueError("item GlobalId must be a byte")
        for rule in self.rules:
            if rule.first_type <= item_type <= rule.last_type:
                if isinstance(rule, FixedAcquisitionRule):
                    return AcquisitionFlag(
                        rule.address, rule.mask, rule.acquired_when_set
                    )
                # RE1-FLAG-001: MSB-first bits sit inside little-endian words.
                index = 4 * (global_id // 32) + 3 - (global_id % 32) // 8
                if index >= self.flags_width:
                    raise ValueError(
                        "item GlobalId is outside the acquisition flag block"
                    )
                return AcquisitionFlag(
                    self.flags_address + index,
                    0x80 >> (global_id % 8),
                    rule.acquired_when_set,
                )
        raise ValueError(f"unsupported acquisition item type 0x{item_type:02X}")

    def collected(
        self,
        flag: AcquisitionFlag,
        ordinary_flags: bytes,
        extra_values: Mapping[int, int],
    ) -> bool:
        assert len(ordinary_flags) == self.flags_width
        if self.flags_address <= flag.address < self.flags_address + self.flags_width:
            value = ordinary_flags[flag.address - self.flags_address]
        else:
            assert flag.address in extra_values, "acquisition dependency was not read"
            value = extra_values[flag.address]
        assert type(value) is int and 0 <= value <= 255
        return bool(value & flag.mask) == flag.acquired_when_set
