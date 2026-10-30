"""Results shared by revision-specific live readers."""

from dataclasses import dataclass
from enum import Enum


class PollStatus(Enum):
    Display = "display"
    ReadFailure = "read-failure"
    UnsupportedRoom = "unsupported-room"
    UnsupportedSettings = "unsupported-settings"
    Retry = "retry"
    WrongGame = "wrong-game"
    NonGameplay = "non-gameplay"


@dataclass(frozen=True)
class PollResult:
    status: PollStatus
    text: str
