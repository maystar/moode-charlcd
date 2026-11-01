"""Source independent data model shared by input adapters, service and layout."""

from __future__ import annotations

import enum
import time
from dataclasses import dataclass, field


class PlaybackState(enum.Enum):
    STOP = "stop"
    PLAY = "play"
    PAUSE = "pause"


class Action(enum.Enum):
    """Commands that can be triggered by buttons."""

    PLAY_PAUSE = "play_pause"
    PREVIOUS = "previous"
    NEXT = "next"


ALL_ACTIONS = frozenset(Action)
NO_ACTIONS: frozenset[Action] = frozenset()


@dataclass(frozen=True)
class NowPlaying:
    """What is currently playing, independent of the source.

    ``elapsed`` is the position in seconds at the monotonic time ``updated_at``;
    use :meth:`elapsed_at` to get the interpolated position.
    """

    source: str
    source_label: str
    state: PlaybackState = PlaybackState.STOP
    title: str = ""
    artist: str = ""
    album: str = ""
    elapsed: float | None = None
    duration: float | None = None
    updated_at: float = field(default_factory=time.monotonic)
    random: bool = False
    repeat: bool = False
    consume: bool = False
    single: bool = False
    volume: int | None = None
    actions: frozenset[Action] = NO_ACTIONS

    def elapsed_at(self, now: float) -> float | None:
        if self.elapsed is None:
            return None
        if self.state != PlaybackState.PLAY:
            return self.elapsed
        value = self.elapsed + max(0.0, now - self.updated_at)
        if self.duration:
            value = min(value, self.duration)
        return value

    def same_content(self, other: NowPlaying | None) -> bool:
        """Equality ignoring the timestamp, used to suppress redundant updates."""
        if other is None:
            return False
        a = self.__dict__.copy()
        b = other.__dict__.copy()
        a.pop("updated_at")
        b.pop("updated_at")
        return a == b


def idle(label: str) -> NowPlaying:
    return NowPlaying(source="none", source_label=label)
