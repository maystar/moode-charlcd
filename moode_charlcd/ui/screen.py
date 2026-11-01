"""Shows frames on a :class:`CharacterDisplay`.

Responsibilities:

* map symbols to built-in characters, programmable slots or ASCII fallbacks
  (slots are reprogrammed on demand when more symbols than slots are used),
* encode text with the display's character set,
* only transfer the parts of a row that changed (I2C is slow).
"""

from __future__ import annotations

import logging

from ..glyphs import Symbol
from ..hal.base import CharacterDisplay
from .frame import Frame

logger = logging.getLogger(__name__)


class Screen:
    def __init__(self, display: CharacterDisplay) -> None:
        self.display = display
        self.cols = display.cols
        self.rows = display.rows
        self._slots: dict[Symbol, int] = {}
        self._shown: list[list[int] | None] = [None] * display.rows
        display.clear()

    def show(self, frame: Frame) -> None:
        if len(frame) != self.rows or any(len(row) != self.cols for row in frame):
            raise ValueError(f"frame does not match display size {self.cols}x{self.rows}")
        self._allocate_slots(frame)
        for row_index, row in enumerate(frame):
            codes = [self._encode(cell) for cell in row]
            self._write_changes(row_index, codes)
        self.display.flush()

    def invalidate(self) -> None:
        """Forget what is shown, e.g. after the display was reset."""
        self._shown = [None] * self.rows
        self._slots.clear()

    def _allocate_slots(self, frame: Frame) -> None:
        needed = {
            cell
            for row in frame
            for cell in row
            if isinstance(cell, Symbol) and self.display.builtin_symbol(cell) is None
        }
        missing = [symbol for symbol in Symbol if symbol in needed and symbol not in self._slots]
        if not missing or self.display.custom_char_slots == 0:
            return
        used = set(self._slots.values())
        free = [slot for slot in range(self.display.custom_char_slots) if slot not in used]
        evictable = [symbol for symbol in self._slots if symbol not in needed]
        for symbol in missing:
            if free:
                slot = free.pop(0)
            elif evictable:
                slot = self._slots.pop(evictable.pop(0))
            else:
                logger.debug("No free character slot for %s, using ASCII fallback", symbol)
                continue
            self.display.define_char(slot, symbol.bitmap)
            self._slots[symbol] = slot
            # Cells still showing the old character of this slot are part of
            # the diff anyway because the new frame does not contain it.

    def _encode(self, cell: str | Symbol) -> int:
        if isinstance(cell, Symbol):
            builtin = self.display.builtin_symbol(cell)
            if builtin is not None:
                return builtin
            if cell in self._slots:
                return self._slots[cell]
            return self.display.encode_char(cell.ascii)
        return self.display.encode_char(cell)

    def _write_changes(self, row: int, codes: list[int]) -> None:
        shown = self._shown[row]
        if shown is None:
            start, end = 0, len(codes)
        else:
            changed = [i for i, (a, b) in enumerate(zip(shown, codes, strict=True)) if a != b]
            if not changed:
                return
            start, end = changed[0], changed[-1] + 1
        self.display.write(row, start, codes[start:end])
        self._shown[row] = codes
