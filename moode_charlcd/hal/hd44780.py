"""HD44780 character LCD controller in 4-bit mode.

The controller logic is independent of how the nibbles reach the display;
see :mod:`moode_charlcd.hal.pcf8574` for the I2C backpack.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Protocol

from ..glyphs import Symbol
from .base import CharacterDisplay
from .charsets import CHARSETS, encode

_CLEAR = 0x01
_ENTRY_MODE_INCREMENT = 0x06
_DISPLAY_ON = 0x0C
_FUNCTION_4BIT_2LINE_5X8 = 0x28
_SET_CGRAM = 0x40
_SET_DDRAM = 0x80


class NibbleBus(Protocol):
    """Transfers 4 bits to the controller and pulses *enable*."""

    def write_nibble(self, nibble: int, rs: bool) -> None: ...


class Hd44780(CharacterDisplay):
    custom_char_slots = 8

    def __init__(
        self,
        bus: NibbleBus,
        cols: int = 20,
        rows: int = 4,
        charset: str = "A00",
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        super().__init__(cols, rows)
        if charset not in CHARSETS:
            raise ValueError(f"unknown charset {charset!r}, use one of {sorted(CHARSETS)}")
        self._bus = bus
        self._table = CHARSETS[charset]
        self._sleep = sleep
        # DDRAM start address of each row (works for 1-4 rows, 8-40 columns).
        self._row_offsets = [0x00, 0x40, cols, 0x40 + cols]
        self._init()

    def _init(self) -> None:
        self._sleep(0.05)
        # Reset sequence from the datasheet (figure 24), switches to 4-bit mode.
        for delay in (0.0045, 0.0045, 0.00015):
            self._bus.write_nibble(0x03, rs=False)
            self._sleep(delay)
        self._bus.write_nibble(0x02, rs=False)
        self._command(_FUNCTION_4BIT_2LINE_5X8)
        self._command(_DISPLAY_ON)
        self._command(_ENTRY_MODE_INCREMENT)
        self.clear()

    def _send(self, value: int, rs: bool) -> None:
        self._bus.write_nibble((value >> 4) & 0x0F, rs)
        self._bus.write_nibble(value & 0x0F, rs)

    def _command(self, value: int) -> None:
        self._send(value, rs=False)

    def _data(self, value: int) -> None:
        self._send(value, rs=True)

    def encode_char(self, char: str) -> int:
        return encode(char, self._table)

    def builtin_symbol(self, symbol: Symbol) -> int | None:
        code = self._table.get(symbol.unicode)
        return code

    def define_char(self, slot: int, bitmap: Sequence[int]) -> None:
        if not 0 <= slot < self.custom_char_slots:
            raise ValueError(f"slot {slot} out of range")
        self._command(_SET_CGRAM | (slot << 3))
        for line in list(bitmap)[:8]:
            self._data(line & 0x1F)

    def write(self, row: int, col: int, codes: Sequence[int]) -> None:
        if not 0 <= row < self.rows:
            raise ValueError(f"row {row} out of range")
        self._command(_SET_DDRAM | (self._row_offsets[row] + col))
        for code in codes[: self.cols - col]:
            self._data(code)

    def clear(self) -> None:
        self._command(_CLEAR)
        self._sleep(0.002)
