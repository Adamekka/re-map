"""Compile immutable open-door bindings from independent native write proofs."""

from __future__ import annotations

import struct
from dataclasses import dataclass

from games.re2.room_entry_contract import VerifiedRoomEntryContract
from games.re2.room_lifetime_proof import RoomLifetimeFailure, room_lifetime_proof
from games.re2.room_write_partitions import RoomWritePartitionConfig


@dataclass(frozen=True)
class ImmutableOpenDoor:
    slot: int
    creator_offsets: tuple[int, ...]
    context_conditions: list[dict]

    def __post_init__(self) -> None:
        assert type(self.slot) is int and 0 <= self.slot < 32
        assert type(self.creator_offsets) is tuple and self.creator_offsets
        assert all(
            type(offset) is int and offset >= 0 for offset in self.creator_offsets
        )
        assert tuple(sorted(set(self.creator_offsets))) == self.creator_offsets
        assert type(self.context_conditions) is list


def immutable_open_doors(
    data: bytes,
    room: dict,
    profile: dict,
    entry_contract: VerifiedRoomEntryContract,
    partition_config: RoomWritePartitionConfig,
) -> tuple[ImmutableOpenDoor, ...] | RoomLifetimeFailure:
    """Require whole effect coverage before exporting a departed door fact.

    No observation is cached. The returned constructor conditions must be
    freshly enforced wherever the resulting door bindings are consumed.
    """
    lifetime = room_lifetime_proof(
        data, room, profile, entry_contract, partition_config
    )
    if isinstance(lifetime, RoomLifetimeFailure):
        return lifetime
    # The receipt belongs to this exact source and decoded program graph.
    assert lifetime.matches_source(data, room["programs"])
    try:
        programs = room["programs"]
        commands = {
            key: {row["offset"]: row for row in program["commands"]}
            for key, program in programs.items()
        }
        fixed = {(bank, bit): expected for bank, bit, expected in lifetime.fixed_flags}
        reached = lifetime.actor_write_proof.reached_locations
        # A deterministic startup prefix proves creation before a later event
        # can suspend. Unknown predicates stop this sufficient proof; graph
        # reachability alone never establishes a current registered door.
        key, position = (
            entry_contract.roots[0],
            programs[entry_contract.roots[0]]["entry"],
        )
        prefix, seen = set(), set()
        while position not in seen and (key, position) in reached:
            seen.add(position)
            row = commands[key][position]
            if row["kind"] == "if":
                following, tests = row["next"], []
                while (
                    following in commands[key]
                    and commands[key][following]["kind"] == "flag_check"
                ):
                    test = commands[key][following]
                    tests.append(test)
                    following = test["next"]
                if not tests or any(
                    (test["bank"], test["bit"]) not in fixed for test in tests
                ):
                    break
                matches = all(
                    fixed[test["bank"], test["bit"]] == test["expected"]
                    for test in tests
                )
                if (
                    matches
                    and following in commands[key]
                    and commands[key][following]["opcode"] in (0x23, 0x3E, 0x50, 0x5E)
                ):
                    break
                position = following if matches else row["target"]
                continue
            if row["opcode"] == 7:
                position = row["target"]
                continue
            if (
                row["kind"] == "end"
                or row["kind"] == "call"
                or row["opcode"] in (2, 4)
                or row["opcode"] in range(0x0D, 0x18)
            ):
                break
            prefix.add(position)
            position = row["next"]

        bindings = {}
        for program in programs.values():
            for row in program["commands"]:
                if row["kind"] in ("door", "item", "interaction", "reset"):
                    bindings.setdefault(data[row["offset"] + 1], []).append(row)
        result = []
        for slot, creators in sorted(bindings.items()):
            if any(row["kind"] != "door" or row["opcode"] != 0x3B for row in creators):
                continue
            packets = {data[row["offset"] : row["next"]] for row in creators}
            if len(packets) != 1 or not any(
                row["offset"] in prefix for row in creators
            ):
                continue
            packet = next(iter(packets))
            if packet[3] != 0x31 or packet[29:31] != b"\0\0":
                continue
            result.append(
                ImmutableOpenDoor(
                    slot,
                    tuple(sorted(row["offset"] for row in creators)),
                    list(lifetime.context_conditions),
                )
            )
        return tuple(result)
    except (KeyError, IndexError, TypeError, ValueError, struct.error):
        return RoomLifetimeFailure.InputBinding
