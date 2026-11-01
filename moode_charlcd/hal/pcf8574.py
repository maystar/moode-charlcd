"""PCF8574 I2C port expander as 4-bit bus for an HD44780.

The wiring between expander and display differs between backpacks; it is
described by a :class:`PinMapping`.

Derived from I2C_HD77480_LCD (maystar), which is based on work by Dan Halbert
and RPLCD by Danilo Bargen, both MIT licensed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PinMapping:
    """Bit masks of the control lines and position of the data nibble.

    The data lines D4..D7 are expected on four consecutive pins starting at
    ``data_shift``. RW is always held low (write only).
    """

    rs: int
    enable: int
    backlight: int
    data_shift: int


PIN_MAPPINGS = {
    # P0=RS P1=RW P2=EN P3=BL P4..P7=D4..D7 (most common backpack)
    "standard": PinMapping(rs=0x01, enable=0x04, backlight=0x08, data_shift=4),
    # P0..P3=D4..D7 P4=RS P7=EN, no backlight control (Joy-IT RB-LCD-20x4)
    "joyit": PinMapping(rs=0x10, enable=0x80, backlight=0x00, data_shift=0),
}


class ByteWriter(Protocol):
    """The part of ``smbus2.SMBus`` that is needed here."""

    def write_byte(self, i2c_addr: int, value: int) -> None: ...


class Pcf8574Bus:
    def __init__(
        self, i2c: ByteWriter, address: int, mapping: PinMapping, backlight: bool = True
    ) -> None:
        self._i2c = i2c
        self._address = address
        self._mapping = mapping
        self._backlight = mapping.backlight if backlight else 0

    def write_nibble(self, nibble: int, rs: bool) -> None:
        m = self._mapping
        value = ((nibble & 0x0F) << m.data_shift) | (m.rs if rs else 0) | self._backlight
        # The controller latches the data on the falling edge of enable. The
        # I2C transfer of each byte (~100 us at 100 kHz) is longer than any
        # timing the HD44780 needs for regular commands.
        self._i2c.write_byte(self._address, value & ~m.enable)
        self._i2c.write_byte(self._address, value | m.enable)
        self._i2c.write_byte(self._address, value & ~m.enable)
