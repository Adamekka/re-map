"""Bind the audited normal entry selector to owned resources and source corpus.

This is a logical initialized-engine contract. Native object/geometry work uses
its legitimate owned records; this does not model arbitrary pointer corruption.
Memory-card startup is outside the audited restore protocol.
"""

from __future__ import annotations

import hashlib
import json
import re
import struct
from dataclasses import asdict, dataclass
from enum import Enum

from games.re2.script_control_limits import calls_fit_native_frames

EXECUTABLE_SHA256 = "e576348f64d015ecff6e1ce875a8924ee252ba7f3f9478b0917cbbdeb97db441"
SELECTION_SHA256 = "6a7d7d44abb419f3858e1d04ca3b61f3181e75c5db783f4cc35a9cf54aad1e6e"
RESOURCES_SHA256 = "70c4d593a6e012fa114f175332fbe89a473df62eef34b93719393b8f964bd5d8"


def _manifest_digest(value: dict | list) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()


class EntrySelectionFailure(Enum):
    Revision = "startup entry selector has a different executable"
    Resource = "startup entry selector resource binding failed"
    Corpus = "startup entry selector source corpus binding failed"
    Routing = "startup entry routing is not covered by the native audit"


@dataclass(frozen=True)
class EntrySelectionResource:
    path: str
    width: int
    sha256: str

    def __post_init__(self) -> None:
        assert type(self.path) is str and self.path
        assert type(self.width) is int and self.width > 0
        assert type(self.sha256) is str and re.fullmatch(r"[0-9a-f]{64}", self.sha256)


@dataclass(frozen=True)
class EntrySelectionSource:
    room_id: str
    path: str
    width: int
    sha256: str

    def __post_init__(self) -> None:
        assert type(self.room_id) is str and re.fullmatch(
            r"[0-9a-f]{2}-[0-9a-f]{2}", self.room_id
        )
        assert type(self.path) is str and self.path
        assert type(self.width) is int and self.width > 0
        assert type(self.sha256) is str and re.fullmatch(r"[0-9a-f]{64}", self.sha256)


@dataclass(frozen=True)
class EntrySelectionConfig:
    executable_sha256: str
    resources: tuple[EntrySelectionResource, ...]
    sources: tuple[EntrySelectionSource, ...]
    resource_lookup: tuple[tuple[str, int, int], ...]
    source_lookup: tuple[tuple[str, int, int], ...]

    def __post_init__(self) -> None:
        assert self.executable_sha256 == EXECUTABLE_SHA256
        assert type(self.resources) is tuple and all(
            isinstance(row, EntrySelectionResource) for row in self.resources
        )
        assert type(self.sources) is tuple and all(
            isinstance(row, EntrySelectionSource) for row in self.sources
        )
        assert (
            _manifest_digest([asdict(row) for row in self.resources])
            == RESOURCES_SHA256
        )
        source_lookup = {key: (index, lba) for key, index, lba in self.source_lookup}
        assert len(source_lookup) == len(self.source_lookup) == len(self.sources)
        # Construction is mandatory: callers cannot bypass the pinned native
        # audit by creating a permissive typed config instead of parsing one.
        assert (
            _manifest_digest(
                {
                    "audit": "slus00748-stage0-entry-selection-v1",
                    "scope": "leon-a-original-normal-duckstation-savestates",
                    "resource_lookup": [
                        {"path": path, "file_index": index, "lba": lba}
                        for path, index, lba in self.resource_lookup
                    ],
                    "sources": [
                        {
                            **asdict(row),
                            "file_index": source_lookup[row.room_id][0],
                            "lba": source_lookup[row.room_id][1],
                        }
                        for row in self.sources
                    ],
                }
            )
            == SELECTION_SHA256
        )


@dataclass(frozen=True)
class VerifiedEntrySelection:
    executable_sha256: str
    resources: tuple[EntrySelectionResource, ...]
    sources: tuple[EntrySelectionSource, ...]
    stages: frozenset[int]
    incoming_models: tuple[tuple[str, tuple[int, ...]], ...]

    def __post_init__(self) -> None:
        assert type(self.executable_sha256) is str and re.fullmatch(
            r"[0-9a-f]{64}", self.executable_sha256
        )
        assert type(self.sources) is tuple and all(
            isinstance(row, EntrySelectionSource) for row in self.sources
        )
        assert len({row.room_id for row in self.sources}) == len(self.sources)
        assert type(self.resources) is tuple and all(
            isinstance(row, EntrySelectionResource) for row in self.resources
        )
        assert len({row.path for row in self.resources}) == len(self.resources)
        assert type(self.stages) is frozenset and all(
            type(stage) is int and 0 <= stage <= 255 for stage in self.stages
        )
        assert type(self.incoming_models) is tuple
        assert len(dict(self.incoming_models)) == len(self.incoming_models)
        assert all(
            type(key) is str
            and type(models) is tuple
            and models == tuple(sorted(set(models)))
            and all(type(model) is int and 0 <= model <= 255 for model in models)
            for key, models in self.incoming_models
        )

    def covers_source(self, data: bytes, room: dict) -> bool:
        stage, number = room.get("stage"), room.get("room")
        if (
            type(stage) is not int
            or type(number) is not int
            or stage not in self.stages
            or not 0 <= number <= 255
        ):
            return False
        key = f"{stage:02x}-{number:02x}"
        witness = next((row for row in self.sources if row.room_id == key), None)
        return (
            witness is not None
            and room.get("id") == key
            and room.get("source") == witness.path
            and room.get("size") == witness.width
            and len(data) == witness.width
            and room.get("sha256") == witness.sha256
            and hashlib.sha256(data).hexdigest() == witness.sha256
        )

    def models_for(self, room_id: str) -> tuple[int, ...]:
        # No inbound witness is not permission to assume a default door model.
        return dict(self.incoming_models).get(room_id, ())


def entry_selection_config(
    raw: dict, resources: tuple[EntrySelectionResource, ...], executable_sha256: str
) -> EntrySelectionConfig:
    try:
        if (
            executable_sha256 != EXECUTABLE_SHA256
            or _manifest_digest(raw) != SELECTION_SHA256
            or _manifest_digest([asdict(row) for row in resources]) != RESOURCES_SHA256
        ):
            raise ValueError("unsupported entry selection manifest")
        sources = tuple(
            EntrySelectionSource(
                row["room_id"], row["path"], row["width"], row["sha256"]
            )
            for row in raw["sources"]
        )
        return EntrySelectionConfig(
            executable_sha256,
            resources,
            sources,
            tuple(
                (row["path"], row["file_index"], row["lba"])
                for row in raw["resource_lookup"]
            ),
            tuple(
                (row["room_id"], row["file_index"], row["lba"])
                for row in raw["sources"]
            ),
        )
    except (KeyError, TypeError, ValueError, AssertionError, AttributeError) as error:
        raise ValueError("invalid RE2 startup entry selection manifest") from error


def bind_entry_selection(
    config: EntrySelectionConfig,
    executable: bytes,
    native_resources: dict[str, bytes],
    sources: dict[str, bytes],
) -> VerifiedEntrySelection | EntrySelectionFailure:
    assert isinstance(config, EntrySelectionConfig)
    assert (
        type(executable) is bytes
        and type(native_resources) is dict
        and type(sources) is dict
    )
    if (
        hashlib.sha256(executable).hexdigest() != config.executable_sha256
        or config.executable_sha256 != EXECUTABLE_SHA256
    ):
        return EntrySelectionFailure.Revision
    if native_resources.keys() != {row.path for row in config.resources} or any(
        type(native_resources[row.path]) is not bytes
        or len(native_resources[row.path]) != row.width
        or hashlib.sha256(native_resources[row.path]).hexdigest() != row.sha256
        for row in config.resources
    ):
        return EntrySelectionFailure.Resource
    if sources.keys() != {row.room_id for row in config.sources} or any(
        type(sources[row.room_id]) is not bytes
        or len(sources[row.room_id]) != row.width
        or hashlib.sha256(sources[row.room_id]).hexdigest() != row.sha256
        for row in config.sources
    ):
        return EntrySelectionFailure.Corpus
    # room_data imports the presence interpreters. Keep the native selector's
    # shared source decoding on this mandatory binding path, after imports.
    from games.re2.room_data import decode_room

    def native(address: int, width: int) -> bytes:
        offset = address - 0x80010000 + 0x800
        if not 0x800 <= offset <= len(executable) - width:
            raise ValueError("native entry selector lookup is outside the executable")
        return executable[offset : offset + width]

    def integer(address: int, width: int) -> int:
        return int.from_bytes(native(address, width), "little")

    try:
        resource_specs = {row.path: row for row in config.resources}
        resource_indices = {}
        for path, index, lba in config.resource_lookup:
            record = native(0x800988A4 + index * 8, 8)
            if (
                int.from_bytes(record[:4], "little") != resource_specs[path].width
                or int.from_bytes(record[4:7], "little") != lba
            ):
                return EntrySelectionFailure.Resource
            resource_indices[path] = index
        specs = {row.room_id: row for row in config.sources}
        for key, index, lba in config.source_lookup:
            stage, number = (int(part, 16) for part in key.split("-"))
            table = integer(0x800A7210 + stage * 4, 4)
            record = native(0x800988A4 + index * 8, 8)
            if (
                integer(table + number * 2, 2) != index
                or int.from_bytes(record[:4], "little") != specs[key].width
                or int.from_bytes(record[4:7], "little") != lba
            ):
                return EntrySelectionFailure.Corpus

        incoming: dict[str, set[int]] = {}
        models = set()
        for key, data in sources.items():
            room = decode_room(
                data, specs[key].path, frozenset(), frozenset(), frozenset()
            )
            commands = [
                row
                for program in room["programs"].values()
                for row in program["commands"]
            ]
            # Reset retains geometry and changes only kind/SAT plus the first
            # six payload bytes. Routing bytes follow those six bytes.
            reset_slots = {
                row["slot"]
                for row in commands
                if row["kind"] == "reset" and row["interaction"] == 1
            }
            routes = []
            for row in commands:
                if row["kind"] not in ("door", "item", "interaction"):
                    continue
                at = row["offset"]
                if row["kind"] != "door" and data[at + 1] not in reset_slots:
                    continue
                # Four-point creators install the geometry bit natively; the
                # raw SAT operand need not already contain that bit.
                operand = 30 if row["opcode"] in (0x67, 0x68, 0x69) else 22
                target_stage, target_room, model = (
                    data[at + operand],
                    data[at + operand + 1],
                    data[at + operand + 4],
                )
                routes.append((at + operand, at + operand + 5))
                incoming.setdefault(
                    f"{target_stage % 9:02x}-{target_room:02x}", set()
                ).add(model)
                if row["kind"] == "door":
                    models.add(model)
                elif model not in range(55):
                    # This one frozen cross-kind alternative routes outside
                    # the audited stage-zero namespace, not to a covered entry.
                    if target_stage % 9 == 0:
                        return EntrySelectionFailure.Routing
            for program in room["programs"].values():
                ordered = sorted(program["commands"], key=lambda row: row["offset"])
                if any(
                    left["next"] > right["offset"]
                    for left, right in zip(ordered, ordered[1:])
                ):
                    return EntrySelectionFailure.Routing
                for row in ordered:
                    at, opcode = row["offset"], row["opcode"]
                    packet = data[at : row["next"]]
                    index = {0x24: 1, 0x25: 1, 0x26: 3, 0x27: 2, 0x3D: 1}.get(opcode)
                    if index is not None and packet[index] in (24, 25):
                        return EntrySelectionFailure.Routing
                    if opcode == 0x22:
                        base = integer(0x800A78C8 + packet[1] * 4, 4)
                        if not 0x80000000 <= base <= 0x80100000 - 32 or any(
                            base < end and start < base + 32
                            for start, end in (
                                (0x800CE550, 0x800CE554),
                                (0x800D481C, 0x800D4820),
                            )
                        ):
                            return EntrySelectionFailure.Routing
                    if opcode != 0x1D:
                        continue
                    width = 2 if packet[3] else 1
                    target = row["next"] + packet[2]
                    owner = next(
                        (
                            candidate
                            for candidate in ordered
                            if candidate["offset"] <= target
                            and target + width <= candidate["next"]
                        ),
                        None,
                    )
                    if (
                        owner is None
                        or target == owner["offset"]
                        or owner["opcode"] in (0x24, 0x25, 0x26, 0x27, 0x3D)
                        or any(
                            target < end and start < target + width
                            for start, end in routes
                        )
                        or owner["kind"] in ("door", "item", "interaction")
                        or owner["kind"] == "reset"
                        and target < owner["offset"] + 4
                    ):
                        return EntrySelectionFailure.Routing

        for stage in range(7):
            path = f"COMMON/BIN/STAGE{stage + 1}.BIN"
            if integer(0x800A20B8 + (stage + 8) * 12, 4) != resource_indices[path]:
                return EntrySelectionFailure.Resource
        for model in sorted(models):
            path = f"COMMON/DOOR/DOOR{model:02X}.DO2"
            if integer(0x8009A4B0 + model * 2, 2) != resource_indices[path]:
                return EntrySelectionFailure.Resource
            raw = native_resources[path]
            descriptor = native(0x8009A520 + model * 12, 12)
            width, sector = (
                int.from_bytes(descriptor[2:4], "little"),
                int.from_bytes(descriptor[4:8], "little"),
            )
            payload = raw[sector * 2048 : sector * 2048 + width]
            if len(payload) != width or len(payload) < 10:
                return EntrySelectionFailure.Resource
            script_end = int.from_bytes(payload[:4], "little")
            if not 10 <= script_end <= len(payload):
                return EntrySelectionFailure.Resource
            # Auxiliary scripts use a separate main procedure table. Bind all
            # procedures, not only the native root's apparent linear prefix.
            fake = bytearray(136)
            fake[1] = 1
            struct.pack_into("<I", fake, 8 + 7 * 4, 100)
            struct.pack_into("<I", fake, 8 + 16 * 4, 132)
            struct.pack_into("<I", fake, 8 + 17 * 4, 136)
            fake[132:136] = b"\x02\0\x01\0"
            fake.extend(payload[8:script_end])
            auxiliary = decode_room(
                bytes(fake), path, frozenset(), frozenset(), frozenset()
            )
            edges = {key: set() for key in auxiliary["programs"]}
            for key, program in auxiliary["programs"].items():
                commands = program["commands"]
                for row in commands:
                    at, opcode = row["offset"], row["opcode"]
                    packet = fake[at : row["next"]]
                    if opcode in (0x22, 0x2C, 0x3B, 0x46, 0x47, 0x67, 0x68):
                        return EntrySelectionFailure.Routing
                    if row["kind"] == "call":
                        edges[key].add(f"17:{row['procedure']}")
                    if opcode == 0x17 and packet[1:3] != b"\xff\xff":
                        return EntrySelectionFailure.Routing
                    if (
                        opcode == 0x2E
                        and packet[1] != 5
                        or opcode in (0x34, 0x35)
                        and packet[1] not in (11, 12, 13)
                    ):
                        return EntrySelectionFailure.Routing
                    if opcode == 0x1D:
                        target, width = row["next"] + packet[2], 2 if packet[3] else 1
                        owner = next(
                            (
                                candidate
                                for candidate in commands
                                if candidate["offset"] <= target
                                and target + width <= candidate["next"]
                            ),
                            None,
                        )
                        if owner is None or not (
                            owner["opcode"] == 0x2E
                            and target == owner["offset"] + 2
                            and width == 1
                            or owner["opcode"] == 0x34
                            and target == owner["offset"] + 2
                            and width == 2
                        ):
                            return EntrySelectionFailure.Routing
            if not calls_fit_native_frames(edges):
                return EntrySelectionFailure.Routing
        # The pinned native setter writes room from pending payload+9 and
        # stage from payload+8 modulo9 *after* auxiliary execution. Other
        # counter stores cannot change that final route. Native normal AOT
        # dispatch and Aot_on are the only pending-payload producers; the
        # auxiliary contract above has neither an AOT sink nor opcode writes.
        # TITLE's direct loader uses fixed normal starts; variable destinations
        # require demo2000 or excluded memory-card startup. Demo exit clears
        # gameplay before returning, and a new load precedes its next setting.
        return VerifiedEntrySelection(
            config.executable_sha256,
            config.resources,
            config.sources,
            frozenset({0}),
            tuple(
                (key, tuple(sorted(value))) for key, value in sorted(incoming.items())
            ),
        )
    except (KeyError, IndexError, TypeError, ValueError, struct.error, AssertionError):
        return EntrySelectionFailure.Routing
