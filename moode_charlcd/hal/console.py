"""Text console 'display' for development and debugging without hardware."""

from __future__ import annotations

import sys
from collections.abc import Sequence
from typing import TextIO

from ..glyphs import Symbol
from .base import CharacterDisplay

# Symbols are mapped to codes in the Unicode private use area.
_SYMBOL_BASE = 0xF0000
_SYMBOLS = list(Symbol)


class ConsoleDisplay(CharacterDisplay):
    def __init__(
        self, cols: int = 20, rows: int = 4, out: TextIO | None = None, ansi: bool | None = None
    ) -> None:
        super().__init__(cols, rows)
        self._out = out or sys.stdout
        self._ansi = self._out.isatty() if ansi is None else ansi
        self._cells = [[ord(" ")] * cols for _ in range(rows)]
        self._last_output = ""

    def encode_char(self, char: str) -> int:
        return ord(char) if char.isprintable() else ord("?")

    def builtin_symbol(self, symbol: Symbol) -> int:
        return _SYMBOL_BASE + _SYMBOLS.index(symbol)

    def write(self, row: int, col: int, codes: Sequence[int]) -> None:
        for offset, code in enumerate(codes[: self.cols - col]):
            self._cells[row][col + offset] = code

    def clear(self) -> None:
        self._cells = [[ord(" ")] * self.cols for _ in range(self.rows)]

    def text(self) -> list[str]:
        """Current content as strings (symbols shown as Unicode)."""
        return ["".join(self._decode(code) for code in row) for row in self._cells]

    @staticmethod
    def _decode(code: int) -> str:
        if code >= _SYMBOL_BASE:
            return _SYMBOLS[code - _SYMBOL_BASE].unicode
        return chr(code)

    def flush(self) -> None:
        border = "+" + "-" * self.cols + "+"
        output = "\n".join([border, *(f"|{line}|" for line in self.text()), border])
        if output == self._last_output:
            return
        self._last_output = output
        if self._ansi:
            self._out.write("\x1b[H\x1b[2J")
        self._out.write(output + "\n")
        self._out.flush()
