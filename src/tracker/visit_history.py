"""Persist exploration only; item and door verdicts always come from the game."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from uuid import UUID, uuid4

from games.game_profile import RoomId
from tracker.exploration_state import RoomCompletion, RoomRecord, Tracker


class HistoryError(Exception):
    """The history cannot be read or saved safely."""


@dataclass(frozen=True)
class HistoryIdentity:
    profile: str
    runtime_sha256: str
    scenario: str

    def __post_init__(self) -> None:
        assert self.profile and self.scenario
        assert len(self.runtime_sha256) == 64 and all(
            c in "0123456789abcdef" for c in self.runtime_sha256
        ), "history identity requires the verified revision fingerprint"


class VisitHistory:
    def __init__(
        self,
        path: Path,
        identity: HistoryIdentity,
        region_rooms: dict[str, set[str]],
        new_playthrough: bool,
    ) -> None:
        self.path = path
        self.identity = identity
        self.region_rooms = region_rooms
        self.playthrough_id = str(uuid4())
        self.rooms: tuple[str, ...] = ()
        self.regions: tuple[tuple[str, str], ...] = ()
        self.needs_write = True
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self.lock = path.with_name(path.name + ".lock").open("a")
        except OSError as exc:
            raise HistoryError(f"Cannot open exploration history: {exc}") from exc
        try:
            # Two trackers must not overwrite each other's exploration. The lock
            # file stays in place; closing this handle releases the OS lock.
            fcntl.flock(self.lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            self.lock.close()
            raise HistoryError(
                "Exploration history is in use. Stop the other tracker or choose "
                "a different --history-file."
            ) from exc
        try:
            if not new_playthrough:
                try:
                    raw = json.loads(path.read_text(encoding="utf-8"))
                except FileNotFoundError:
                    # A missing file is the explicit first-run state. Corrupt or
                    # unreadable history must never silently become a new game.
                    return
                if (
                    not isinstance(raw, dict)
                    or set(raw)
                    != {"schema", "identity", "playthrough_id", "rooms", "regions"}
                    or type(raw["schema"]) is not int
                    or raw["schema"] != 1
                ):
                    raise ValueError("unsupported history format")
                if raw["identity"] != asdict(identity):
                    raise ValueError("history belongs to a different game or scenario")
                if (
                    not isinstance(raw["playthrough_id"], str)
                    or str(UUID(raw["playthrough_id"])) != raw["playthrough_id"]
                ):
                    raise ValueError("invalid playthrough identity")
                if not isinstance(raw["rooms"], list) or any(
                    not isinstance(key, str) for key in raw["rooms"]
                ):
                    raise ValueError("invalid room visits")
                if len(raw["rooms"]) != len(set(raw["rooms"])):
                    raise ValueError("duplicate room visits")
                for key in raw["rooms"]:
                    stage, room = key.split("-")
                    rid = RoomId(int(stage), int(room, 16))
                    if (
                        not 0 <= rid.stage <= 255
                        or not 0 <= rid.room <= 255
                        or str(rid) != key
                    ):
                        raise ValueError("invalid room visit")
                if not isinstance(raw["regions"], dict) or any(
                    not isinstance(region, str)
                    or not isinstance(room, str)
                    or room not in raw["rooms"]
                    or region not in region_rooms
                    or room not in region_rooms[region]
                    for region, room in raw["regions"].items()
                ):
                    raise ValueError("map visits disagree with room history or profile")
                self.playthrough_id = raw["playthrough_id"]
                self.rooms = tuple(sorted(raw["rooms"]))
                self.regions = tuple(sorted(raw["regions"].items()))
                self.needs_write = False
        except (OSError, ValueError, TypeError) as exc:
            self.lock.close()
            raise HistoryError(
                f"Cannot restore exploration history: {exc}. Choose another "
                "--history-file or use --new-playthrough to start fresh."
            ) from exc

    def restore(self) -> Tracker:
        # Saved visits establish exploration, never clearance or current location.
        # The next coherent poll reconstructs these rooms using fresh game flags.
        return Tracker(
            rooms={
                key: RoomRecord(
                    visited=True,
                    completion=RoomCompletion.Unknown,
                    reason="Checking items from the loaded game.",
                    door_reason="Checking door access from the loaded game.",
                )
                for key in self.rooms
            },
            region_visits=dict(self.regions),
        )

    def save(self, tracker: Tracker) -> None:
        rooms = tuple(
            sorted(key for key, room in tracker.rooms.items() if room.visited)
        )
        regions = tuple(sorted(tracker.region_visits.items()))
        assert all(
            room in rooms
            and region in self.region_rooms
            and room in self.region_rooms[region]
            for region, room in regions
        ), "map visits must belong to visited rooms in the configured profile"
        if not self.needs_write and rooms == self.rooms and regions == self.regions:
            return
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, delete=False
            ) as output:
                temporary = Path(output.name)
                json.dump(
                    {
                        "schema": 1,
                        "identity": asdict(self.identity),
                        "playthrough_id": self.playthrough_id,
                        "rooms": rooms,
                        "regions": dict(regions),
                    },
                    output,
                    indent=2,
                )
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            # Replace only a fully written file so an interrupted save preserves
            # the previous history instead of truncating it.
            os.replace(temporary, self.path)
        except OSError as exc:
            raise HistoryError(f"Cannot save exploration history: {exc}") from exc
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        self.rooms, self.regions = rooms, regions
        self.needs_write = False

    def close(self) -> None:
        self.lock.close()
