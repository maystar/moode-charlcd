import io

import pytest

from moode_charlcd.glyphs import Symbol
from moode_charlcd.hal.console import ConsoleDisplay
from moode_charlcd.ui.frame import FrameBuilder
from moode_charlcd.ui.screen import Screen

from .conftest import FakeDisplay


def text_frame(*lines: str, cols: int = 20, rows: int = 4):
    builder = FrameBuilder(cols, rows)
    for row, line in enumerate(lines):
        builder.text(row, 0, line)
    return builder.build()


def test_first_frame_writes_every_row(fake_display: FakeDisplay) -> None:
    Screen(fake_display).show(text_frame("a", "b", "c", "d"))
    assert [row for row, _col, _codes in fake_display.writes] == [0, 1, 2, 3]
    assert fake_display.flushes == 1


def test_only_changed_span_is_written(fake_display: FakeDisplay) -> None:
    screen = Screen(fake_display)
    screen.show(text_frame("Hello World"))
    fake_display.writes.clear()
    screen.show(text_frame("Hello Wxrxd"))
    assert fake_display.writes == [(0, 7, [ord("x"), ord("r"), ord("x")])]


def test_unchanged_frame_writes_nothing(fake_display: FakeDisplay) -> None:
    screen = Screen(fake_display)
    screen.show(text_frame("same"))
    fake_display.writes.clear()
    screen.show(text_frame("same"))
    assert fake_display.writes == []


def test_invalidate_rewrites_everything(fake_display: FakeDisplay) -> None:
    screen = Screen(fake_display)
    screen.show(text_frame("same"))
    fake_display.writes.clear()
    screen.invalidate()
    screen.show(text_frame("same"))
    assert len(fake_display.writes) == 4


def test_frame_size_must_match(fake_display: FakeDisplay) -> None:
    with pytest.raises(ValueError, match="size"):
        Screen(fake_display).show(text_frame("x", cols=16, rows=2))


def test_symbols_are_programmed_into_slots(fake_display: FakeDisplay) -> None:
    frame = FrameBuilder(20, 4).symbol(0, 0, Symbol.PLAY).symbol(0, 1, Symbol.NEXT).build()
    Screen(fake_display).show(frame)
    slots = {bitmap: slot for slot, bitmap in fake_display.defined.items()}
    assert fake_display.cells[0][0] == slots[Symbol.PLAY.bitmap]
    assert fake_display.cells[0][1] == slots[Symbol.NEXT.bitmap]


def test_builtin_symbol_needs_no_slot() -> None:
    display = FakeDisplay(builtin={Symbol.REPEAT: 0xF3})
    Screen(display).show(FrameBuilder(20, 4).symbol(0, 0, Symbol.REPEAT).build())
    assert display.defined == {}
    assert display.cells[0][0] == 0xF3


def test_ascii_fallback_without_slots() -> None:
    display = FakeDisplay(slots=0)
    Screen(display).show(FrameBuilder(20, 4).symbol(0, 0, Symbol.PLAY).build())
    assert display.cells[0][0] == ord(">")


def test_unused_slots_are_reused_for_new_symbols() -> None:
    display = FakeDisplay(slots=1)
    screen = Screen(display)
    screen.show(FrameBuilder(20, 4).symbol(0, 0, Symbol.PLAY).build())
    screen.show(FrameBuilder(20, 4).symbol(0, 0, Symbol.PAUSE).build())
    assert display.defined == {0: Symbol.PAUSE.bitmap}
    assert display.cells[0][0] == 0


def test_more_symbols_than_slots_falls_back_to_ascii() -> None:
    display = FakeDisplay(slots=1)
    frame = FrameBuilder(20, 4).symbol(0, 0, Symbol.PLAY).symbol(0, 1, Symbol.NEXT).build()
    Screen(display).show(frame)
    assert display.cells[0][:2] == [0, ord("}")]


def test_console_display_renders_unicode_symbols() -> None:
    out = io.StringIO()
    display = ConsoleDisplay(10, 2, out=out, ansi=False)
    frame = FrameBuilder(10, 2).symbol(0, 0, Symbol.PLAY).text(0, 1, "Hallö").build()
    Screen(display).show(frame)
    assert display.text() == ["▶Hallö    ", "          "]
    assert "|▶Hallö    |" in out.getvalue()


def test_console_display_prints_only_changes() -> None:
    out = io.StringIO()
    display = ConsoleDisplay(4, 1, out=out, ansi=False)
    screen = Screen(display)
    screen.show(text_frame("ab", cols=4, rows=1))
    first = out.getvalue()
    screen.show(text_frame("ab", cols=4, rows=1))
    assert out.getvalue() == first
