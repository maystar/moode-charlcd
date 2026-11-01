"""Turns a :class:`NowPlaying` into a frame.

The standard layout reproduces mopidy-charlcd on a 20x4 display::

    ⏸|⏮|⏭|⏻   ∞⤨© ►01:23
    Title
    Artist
    Album          12:34

and degrades gracefully on smaller displays (fewer indicators, fewer rows).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from ..glyphs import Symbol
from ..model import Action, NowPlaying, PlaybackState
from .frame import Frame, FrameBuilder

CLOCK_WIDTH = 5  # "HH:MM"
LEGEND_WIDTH = 7  # "P|B|F|Q"
INDICATOR_WIDTH = 5  # repeat, random, consume, gap, playing


def format_time(seconds: float) -> str:
    total = int(seconds)
    hours, rest = divmod(total, 3600)
    minutes, secs = divmod(rest, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


class Layout(ABC):
    def __init__(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows

    @abstractmethod
    def render(self, now_playing: NowPlaying, wall_clock: datetime, monotonic: float) -> Frame:
        """Frame for the current playback information."""

    def message(self, *lines: str) -> Frame:
        """Frame with centered lines, e.g. for start-up and shutdown."""
        builder = FrameBuilder(self.cols, self.rows)
        first = 1 if self.rows > 2 and len(lines) < self.rows else 0
        for index, line in enumerate(lines):
            builder.text(first + index, 0, line, align="center")
        return builder.build()


class StandardLayout(Layout):
    def __init__(self, cols: int, rows: int, show_legend: bool = True) -> None:
        super().__init__(cols, rows)
        self.show_legend = show_legend

    def render(self, now_playing: NowPlaying, wall_clock: datetime, monotonic: float) -> Frame:
        builder = FrameBuilder(self.cols, self.rows)
        np = now_playing
        legend = self.show_legend and bool(np.actions)

        self._status_row(builder, np, monotonic, legend)

        lines = self._info_lines(np, legend)
        clock = wall_clock.strftime("%H:%M")
        show_clock = self.rows >= 3 and self.cols >= CLOCK_WIDTH + 6
        for offset, text in enumerate(lines[: self.rows - 1]):
            row = offset + 1
            last = row == self.rows - 1
            margin = CLOCK_WIDTH + 1 if last and show_clock else 0
            builder.text(row, 0, text, width=self.cols - margin)
        if show_clock:
            builder.text(self.rows - 1, self.cols - CLOCK_WIDTH, clock, width=CLOCK_WIDTH)
        return builder.build()

    def _status_row(
        self, builder: FrameBuilder, np: NowPlaying, monotonic: float, legend: bool
    ) -> None:
        playing = np.state == PlaybackState.PLAY

        elapsed = np.elapsed_at(monotonic)
        time_text = format_time(elapsed) if elapsed else ""
        time_width = max(CLOCK_WIDTH, len(time_text))
        builder.text(0, self.cols - time_width, time_text, width=time_width, align="right")

        playing_col = self.cols - time_width - 1
        full = self.cols >= LEGEND_WIDTH + 1 + INDICATOR_WIDTH + time_width
        options = full and (np.repeat or np.random or np.consume)
        indicator_col = self.cols - time_width - INDICATOR_WIDTH
        if options:
            builder.symbol(0, indicator_col, Symbol.REPEAT if np.repeat else None)
            builder.symbol(0, indicator_col + 1, Symbol.SHUFFLE if np.random else None)
            builder.symbol(0, indicator_col + 2, Symbol.CONSUME if np.consume else None)
        builder.symbol(0, playing_col, Symbol.PLAYING if playing else None)

        if legend:
            self._legend(builder, np, playing)
        else:
            label_end = indicator_col if options else playing_col
            builder.text(0, 0, np.source_label, width=max(0, label_end - 1))

    @staticmethod
    def _legend(builder: FrameBuilder, np: NowPlaying, playing: bool) -> None:
        def slot(action: Action, symbol: Symbol) -> Symbol | None:
            return symbol if action in np.actions else None

        builder.symbol(0, 0, slot(Action.PLAY_PAUSE, Symbol.PAUSE if playing else Symbol.PLAY))
        builder.text(0, 1, "|", width=1)
        builder.symbol(0, 2, slot(Action.PREVIOUS, Symbol.PREVIOUS))
        builder.text(0, 3, "|", width=1)
        builder.symbol(0, 4, slot(Action.NEXT, Symbol.NEXT))
        builder.text(0, 5, "|", width=1)
        builder.symbol(0, 6, Symbol.POWER)

    @staticmethod
    def _info_lines(np: NowPlaying, legend: bool) -> list[str]:
        if np.source == "mpd" and np.state == PlaybackState.STOP:
            return []  # like mopidy-charlcd: nothing to show while stopped
        album = np.album
        if not album and legend and np.source != "mpd":
            album = np.source_label  # the label is not shown in the status row
        if not (np.title or np.artist or album) and np.source != "mpd":
            return [np.source_label if legend else ""]
        return [np.title, np.artist, album]
