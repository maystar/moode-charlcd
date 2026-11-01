from __future__ import annotations

import pytest

from moode_charlcd.glyphs import Symbol
from moode_charlcd.hal.hd44780 import Hd44780
from moode_charlcd.hal.pcf8574 import PIN_MAPPINGS, Pcf8574Bus


class FakeSmbus:
    def __init__(self) -> None:
        self.bytes: list[tuple[int, int]] = []

    def write_byte(self, i2c_addr: int, value: int) -> None:
        self.bytes.append((i2c_addr, value))


class NibbleRecorder:
    def __init__(self) -> None:
        self.nibbles: list[tuple[int, bool]] = []

    def write_nibble(self, nibble: int, rs: bool) -> None:
        self.nibbles.append((nibble, rs))

    def bytes(self, start: int = 0) -> list[tuple[int, bool]]:
        """Combine the recorded nibbles (after ``start``) to (byte, rs) pairs."""
        data = self.nibbles[start:]
        return [(hi << 4 | lo, rs) for (hi, rs), (lo, _) in zip(data[::2], data[1::2], strict=True)]


def make_lcd(cols: int = 20, rows: int = 4) -> tuple[Hd44780, NibbleRecorder, int]:
    bus = NibbleRecorder()
    lcd = Hd44780(bus, cols, rows, sleep=lambda _s: None)
    return lcd, bus, len(bus.nibbles)


def test_init_sequence_switches_to_4bit_mode() -> None:
    _lcd, bus, _ = make_lcd()
    assert bus.nibbles[:4] == [(0x3, False), (0x3, False), (0x3, False), (0x2, False)]
    assert bus.bytes(4) == [(0x28, False), (0x0C, False), (0x06, False), (0x01, False)]


@pytest.mark.parametrize(
    ("row", "col", "address"), [(0, 0, 0x00), (1, 5, 0x45), (2, 3, 0x17), (3, 19, 0x67)]
)
def test_write_sets_ddram_address_for_20x4(row: int, col: int, address: int) -> None:
    lcd, bus, start = make_lcd()
    lcd.write(row, col, [0x41])
    assert bus.bytes(start) == [(0x80 | address, False), (0x41, True)]


def test_write_is_clipped_at_row_end() -> None:
    lcd, bus, start = make_lcd()
    lcd.write(0, 18, [1, 2, 3, 4])
    assert bus.bytes(start)[1:] == [(1, True), (2, True)]


def test_write_rejects_invalid_row() -> None:
    lcd, _bus, _ = make_lcd()
    with pytest.raises(ValueError, match="row"):
        lcd.write(4, 0, [1])


def test_define_char_programs_cgram() -> None:
    lcd, bus, start = make_lcd()
    lcd.define_char(2, Symbol.PLAY.bitmap)
    assert bus.bytes(start) == [(0x40 | 2 << 3, False)] + [(b, True) for b in Symbol.PLAY.bitmap]


def test_define_char_rejects_invalid_slot() -> None:
    lcd, _bus, _ = make_lcd()
    with pytest.raises(ValueError, match="slot"):
        lcd.define_char(8, Symbol.PLAY.bitmap)


def test_builtin_repeat_symbol_in_a00() -> None:
    lcd, _bus, _ = make_lcd()
    assert lcd.builtin_symbol(Symbol.REPEAT) == 0xF3
    assert lcd.builtin_symbol(Symbol.PLAY) is None


def test_encode_char_uses_charset() -> None:
    lcd, _bus, _ = make_lcd()
    assert lcd.encode_char("ü") == 0xF5


def test_unknown_charset() -> None:
    with pytest.raises(ValueError, match="charset"):
        Hd44780(NibbleRecorder(), charset="X", sleep=lambda _s: None)


def test_joyit_mapping_puts_data_in_low_nibble() -> None:
    smbus = FakeSmbus()
    bus = Pcf8574Bus(smbus, 0x27, PIN_MAPPINGS["joyit"])
    bus.write_nibble(0x4, rs=True)
    # RS=0x10, EN=0x80, data in bits 0..3, no backlight bit
    assert smbus.bytes == [(0x27, 0x14), (0x27, 0x94), (0x27, 0x14)]


def test_standard_mapping_puts_data_in_high_nibble() -> None:
    smbus = FakeSmbus()
    bus = Pcf8574Bus(smbus, 0x3F, PIN_MAPPINGS["standard"])
    bus.write_nibble(0x4, rs=True)
    # RS=0x01, EN=0x04, BL=0x08, data in bits 4..7
    assert smbus.bytes == [(0x3F, 0x49), (0x3F, 0x4D), (0x3F, 0x49)]


def test_standard_mapping_backlight_off() -> None:
    smbus = FakeSmbus()
    bus = Pcf8574Bus(smbus, 0x27, PIN_MAPPINGS["standard"], backlight=False)
    bus.write_nibble(0x0, rs=False)
    assert [value for _addr, value in smbus.bytes] == [0x00, 0x04, 0x00]
