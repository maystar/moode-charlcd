from __future__ import annotations

from collections.abc import Sequence

import pytest

from moode_charlcd.glyphs import Symbol
from moode_charlcd.hal.base import CharacterDisplay
from moode_charlcd.model import NowPlaying, PlaybackState


class FakeDisplay(CharacterDisplay):
    """Records all calls; has ``slots`` programmable characters."""

    def __init__(
        self,
        cols: int = 20,
        rows: int = 4,
        slots: int = 8,
        builtin: dict[Symbol, int] | None = None,
    ) -> None:
        super().__init__(cols, rows)
        self.custom_char_slots = slots
        self.builtin = builtin or {}
        self.writes: list[tuple[int, int, list[int]]] = []
        self.defined: dict[int, tuple[int, ...]] = {}
        self.cells = [[0x20] * cols for _ in range(rows)]
        self.flushes = 0
        self.closed = False

    def encode_char(self, char: str) -> int:
        return ord(char) if ord(char) < 0x80 else ord("?")

    def builtin_symbol(self, symbol: Symbol) -> int | None:
        return self.builtin.get(symbol)

    def define_char(self, slot: int, bitmap: Sequence[int]) -> None:
        self.defined[slot] = tuple(bitmap)

    def write(self, row: int, col: int, codes: Sequence[int]) -> None:
        self.writes.append((row, col, list(codes)))
        for offset, code in enumerate(codes):
            self.cells[row][col + offset] = code

    def clear(self) -> None:
        self.cells = [[0x20] * self.cols for _ in range(self.rows)]

    def flush(self) -> None:
        self.flushes += 1

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def fake_display() -> FakeDisplay:
    return FakeDisplay()


def mpd_playing(**overrides: object) -> NowPlaying:
    from moode_charlcd.model import ALL_ACTIONS

    values: dict[str, object] = {
        "source": "mpd",
        "source_label": "MPD",
        "state": PlaybackState.PLAY,
        "title": "Gasoline",
        "artist": "Audioslave",
        "album": "Audioslave",
        "elapsed": 83.0,
        "duration": 280.0,
        "updated_at": 100.0,
        "actions": ALL_ACTIONS,
    }
    values.update(overrides)
    return NowPlaying(**values)  # type: ignore[arg-type]
