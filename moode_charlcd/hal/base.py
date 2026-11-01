"""Interface every character display driver implements."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from ..glyphs import Symbol


class CharacterDisplay(ABC):
    """A grid of ``cols`` x ``rows`` character cells.

    Characters are addressed by *codes* (ints) in the display's own character
    set. The driver tells how to encode text (:meth:`encode_char`), which
    symbols it has built in (:meth:`builtin_symbol`) and how many
    programmable characters it offers (:attr:`custom_char_slots`). Everything
    else (layout, diffing, slot allocation) happens above this layer in
    :class:`moode_charlcd.ui.screen.Screen`.
    """

    def __init__(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows

    #: Number of programmable 5x8 characters; their codes are ``0..slots-1``.
    custom_char_slots: int = 0

    @abstractmethod
    def encode_char(self, char: str) -> int:
        """Return the code for a single ``char``.

        Characters the display cannot show must be replaced by a similar one
        (or ``?``); exactly one code per character keeps the grid intact.
        """

    def builtin_symbol(self, symbol: Symbol) -> int | None:
        """Return a code from the character ROM that represents ``symbol``."""
        return None

    def define_char(self, slot: int, bitmap: Sequence[int]) -> None:
        """Program custom character ``slot`` with a 5x8 bitmap (8 rows)."""
        raise NotImplementedError("display has no programmable characters")

    @abstractmethod
    def write(self, row: int, col: int, codes: Sequence[int]) -> None:
        """Write character codes starting at (row, col) on a single row."""

    @abstractmethod
    def clear(self) -> None:
        """Blank the whole display."""

    def flush(self) -> None:  # noqa: B027 - optional hook
        """Called after a complete screen update (for buffered displays)."""

    def close(self) -> None:  # noqa: B027 - optional hook
        """Release the hardware; the last content may stay visible."""
