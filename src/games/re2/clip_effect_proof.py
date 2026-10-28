"""RE2-CLIP-001: revision-bound clipping writes preserve fixed context.

The audited model constructors derive a positive part count from owned model
headers and allocate matching 0xAC-byte source/scratch records before rendering.
The deferred copy and filter use that same count and stay inside those records.
Player allocation additionally reserves twenty weapon records; the owned player
resources add at most thirteen. This contract assumes initialized game models, as do
the ordinary actor commands. It does not admit arbitrary actor pointers/counts.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ClipEffectSupport(Enum):
    Unaudited = "unaudited"


@dataclass(frozen=True)
class ClipEffectProof:
    system_address: int
    status_address: int
    parameter_writes: tuple[tuple[int, int], ...]

    def __post_init__(self) -> None:
        assert (
            type(self.system_address) is int
            and self.system_address % 4 == 0
            and 0x80000000 <= self.system_address <= 0x80200000 - 4
            and self.system_address != self.status_address
        ), "clipping system flags must use a separate aligned PS1 RAM word"
        assert (
            type(self.status_address) is int
            and self.status_address % 4 == 0
            and 0x80000000 <= self.status_address <= 0x80200000 - 4
        ), "clipping status must be an aligned PS1 RAM word"
        assert type(self.parameter_writes) is tuple and len(self.parameter_writes) == 4
        assert all(
            type(row) is tuple
            and len(row) == 2
            and type(row[0]) is int
            and type(row[1]) is int
            and row[1] == width
            and row[0] % width == 0
            and 0x80000000 <= row[0] <= 0x80200000 - width
            for row, width in zip(self.parameter_writes, (1, 2, 2, 2), strict=True)
        ), "clipping parameters must cover the native byte and three halfword stores"
        regions = ((self.status_address, 4), *self.parameter_writes)
        assert not any(
            first < second + second_width and second < first + first_width
            for index, (first, first_width) in enumerate(regions)
            for second, second_width in regions[index + 1 :]
        ), "clipping fields must not overlap"

    def preserves_context(
        self,
        data: bytes,
        programs: dict,
        program_key: str,
        offset: int,
        fixed_words: dict[int, int],
    ) -> bool:
        assert all(
            type(address) is int
            and address % 4 == 0
            and 0x80000000 <= address <= 0x80200000 - 4
            and type(mask) is int
            and 0 <= mask <= 0xFFFFFFFF
            for address, mask in fixed_words.items()
        ), "fixed clipping predicates must use aligned PS1 words and native masks"
        # The deferred geometry audit preserves these two native context words.
        # A new fixed predicate inside model/heap state needs its own proof.
        if not fixed_words.keys() <= {self.system_address, self.status_address}:
            return False
        if program_key not in ("16:0", "17:0") or program_key not in programs:
            return False
        current = {row["offset"]: row for row in programs[program_key]["commands"]}.get(
            offset
        )
        if current is None or current["opcode"] != 0x73:
            return False
        packet = data[offset : current["next"]]
        if len(packet) != 8 or packet[0] != 0x73 or packet[1] not in (0, 1, 2):
            return False
        if program_key == "17:0":
            # Reentering this initializer from a later event would enable the
            # effect after ordinary models may have been built without scratch.
            for program in programs.values():
                for row in program["commands"]:
                    command = data[row["offset"] : row["next"]]
                    if row["kind"] == "interaction" and row["interaction"] == 5:
                        if len(command) not in (20, 28) or bool(command[3] & 0x80) != (
                            len(command) == 28
                        ):
                            return False
                    if (
                        row["kind"] == "reset"
                        and row["interaction"] == 5
                        and command[3] & 0x80
                    ):
                        return False
                    if (
                        row["kind"] == "call"
                        and row["procedure"] == 0
                        or row["opcode"] in (3, 4)
                        and len(command) >= 4
                        and command[3] == 0
                        or row["kind"] == "interaction"
                        and row["interaction"] == 5
                        and len(command) in (20, 28)
                        and command[(22 if len(command) == 28 else 14) + 3] == 0
                        or row["kind"] == "reset"
                        and row["interaction"] == 5
                        and row["data"][3] == 0
                    ):
                        return False
        for startup in ("16:0",) if program_key == "16:0" else ("16:0", "17:0"):
            if startup not in programs:
                return False
            program = programs[startup]
            commands = {row["offset"]: row for row in program["commands"]}
            if len(commands) > 4096 or program["entry"] not in commands:
                return False
            # The allocation audit covers synchronous startup. Loop frames and
            # encoded jumps need a separate proof before they can reenter it.
            if any(
                0x0D <= row["opcode"] <= 0x17 or row["opcode"] in (0x1A, 0x1B)
                for row in commands.values()
            ):
                return False
            edges = {}
            reverse = {position: set() for position in commands}
            for position, row in commands.items():
                if row["kind"] == "end":
                    targets = ()
                elif row["kind"] == "if":
                    targets = (row["next"], row["target"])
                elif row["kind"] == "jump":
                    targets = (row["target"],)
                else:
                    targets = (row["next"],)
                if any(target not in commands for target in targets):
                    return False
                edges[position] = targets
                for target in targets:
                    reverse[target].add(position)
            reached, pending = set(), [program["entry"]]
            while pending:
                position = pending.pop()
                if position not in reached:
                    reached.add(position)
                    pending.extend(edges[position])
            prefix = reached
            if startup == program_key:
                ancestors, pending = set(), [offset]
                while pending:
                    position = pending.pop()
                    if position not in ancestors:
                        ancestors.add(position)
                        pending.extend(reverse[position])
                if offset not in reached:
                    return False
                prefix = reached & ancestors - {offset}
            if any(
                not (
                    commands[position]["kind"]
                    in (
                        "if",
                        "flag_check",
                        "flag_write",
                        "door",
                        "item",
                        "interaction",
                        "reset",
                        "end",
                    )
                    or commands[position]["opcode"] in (0, 7, 8, 0x23, 0x3E, 0x50, 0x5E)
                )
                for position in prefix
            ):
                return False
        writes = ((self.status_address, 4, 0x00010000),) + tuple(
            (address, width, (1 << (width * 8)) - 1)
            for address, width in self.parameter_writes
        )
        # Distinct flag-bank aliases can identify the same native bits. Compare
        # actual little-endian byte lanes, including partial parameter stores.
        return not any(
            fixed_words.get((address + index) & ~3, 0)
            & (((mask >> (index * 8)) & 0xFF) << (((address + index) & 3) * 8))
            for address, width, mask in writes
            for index in range(width)
        )


def clipping_effect_proof(profile: dict) -> ClipEffectProof | ClipEffectSupport:
    # Unaudited revisions deliberately retain the unsupported-command outcome.
    if "scenario_clipping" not in profile:
        return ClipEffectSupport.Unaudited
    try:
        raw = profile["scenario_clipping"]
        if (
            type(raw) is not dict
            or raw.keys() != {"status_address_ps1", "parameter_writes"}
            or type(raw["status_address_ps1"]) is not str
            or type(raw["parameter_writes"]) is not list
            or any(
                type(row) is not dict
                or row.keys() != {"address_ps1", "width"}
                or type(row["address_ps1"]) is not str
                or type(row["width"]) is not int
                for row in raw["parameter_writes"]
            )
        ):
            raise ValueError("clipping write proof has an invalid shape")
        proof = ClipEffectProof(
            int(profile["runtime_layout"]["system_flags_address_ps1"], 0),
            int(raw["status_address_ps1"], 0),
            tuple(
                (int(row["address_ps1"], 0), row["width"])
                for row in raw["parameter_writes"]
            ),
        )
        if proof.status_address != int(
            profile["runtime_layout"]["status_flags_address_ps1"], 0
        ):
            raise ValueError("clipping status disagrees with the revision layout")
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        raise ValueError("invalid RE2 clipping write proof") from error
    return proof
