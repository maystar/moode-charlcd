"""A frame is the complete content of a character display."""

from __future__ import annotations

from typing import Literal

from ..glyphs import Symbol

Cell = str | Symbol
Frame = tuple[tuple[Cell, ...], ...]


class FrameBuilder:
    def __init__(self, cols: int, rows: int) -> None:
        self.cols = cols
        self.rows = rows
        self._cells: list[list[Cell]] = [[" "] * cols for _ in range(rows)]

    def text(
        self,
        row: int,
        col: int,
        text: str,
        width: int | None = None,
        align: Literal["left", "right", "center"] = "left",
    ) -> FrameBuilder:
        """Write ``text`` into a field of ``width`` cells (padded / truncated)."""
        if not 0 <= row < self.rows or col >= self.cols:
            return self
        available = self.cols - col
        width = available if width is None else max(0, min(width, available))
        text = text[:width]
        if align == "right":
            text = text.rjust(width)
        elif align == "center":
            text = text.center(width)
        else:
            text = text.ljust(width)
        for offset, char in enumerate(text):
            self._cells[row][col + offset] = char
        return self

    def symbol(self, row: int, col: int, symbol: Symbol | None) -> FrameBuilder:
        if 0 <= row < self.rows and 0 <= col < self.cols:
            self._cells[row][col] = symbol if symbol is not None else " "
        return self

    def build(self) -> Frame:
        return tuple(tuple(row) for row in self._cells)


def frame_to_text(frame: Frame) -> list[str]:
    """Human readable representation, mainly for tests and logging."""
    return [
        "".join(cell.unicode if isinstance(cell, Symbol) else cell for cell in row) for row in frame
    ]
