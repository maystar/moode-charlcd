"""Display independent symbols.

Each symbol carries a 5x8 bitmap (for displays with programmable characters),
a Unicode representation (for text displays such as the console) and an ASCII
fallback (for displays that can show neither).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


@dataclass(frozen=True)
class Glyph:
    unicode: str
    ascii: str
    bitmap: tuple[int, ...]


class Symbol(enum.Enum):
    PLAY = Glyph(
        "▶",
        ">",
        (0b11111, 0b10111, 0b10011, 0b10001, 0b10011, 0b10111, 0b11111, 0b00000),
    )
    PAUSE = Glyph(
        "⏸",
        "=",
        (0b11111, 0b10101, 0b10101, 0b10101, 0b10101, 0b10101, 0b11111, 0b00000),
    )
    NEXT = Glyph(
        "⏭",
        "}",
        (0b11111, 0b10111, 0b11011, 0b11101, 0b11011, 0b10111, 0b11111, 0b00000),
    )
    PREVIOUS = Glyph(
        "⏮",
        "{",
        (0b11111, 0b11101, 0b11011, 0b10111, 0b11011, 0b11101, 0b11111, 0b00000),
    )
    POWER = Glyph(
        "⏻",
        "O",
        (0b11111, 0b01110, 0b10101, 0b11011, 0b10101, 0b01110, 0b11111, 0b00000),
    )
    SHUFFLE = Glyph(
        "⤨",
        "S",
        (0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b00000),
    )
    CONSUME = Glyph(
        "©",
        "C",
        (0b00000, 0b00000, 0b01110, 0b10010, 0b10100, 0b10010, 0b01110, 0b00000),
    )
    REPEAT = Glyph(
        "∞",
        "R",
        (0b00000, 0b00000, 0b01010, 0b10101, 0b10101, 0b01010, 0b00000, 0b00000),
    )
    PLAYING = Glyph(
        "►",
        "*",
        (0b00000, 0b00000, 0b01000, 0b01100, 0b01110, 0b01100, 0b01000, 0b00000),
    )

    @property
    def unicode(self) -> str:
        return self.value.unicode

    @property
    def ascii(self) -> str:
        return self.value.ascii

    @property
    def bitmap(self) -> tuple[int, ...]:
        return self.value.bitmap
