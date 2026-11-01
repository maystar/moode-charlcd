"""Creates the configured display driver."""

from __future__ import annotations

from typing import Any

from .base import CharacterDisplay


def create_display(config: dict[str, Any]) -> CharacterDisplay:
    """Create a display from the ``[display]`` configuration section."""
    driver = config["driver"]
    cols = int(config["cols"])
    rows = int(config["rows"])

    if driver == "console":
        from .console import ConsoleDisplay

        return ConsoleDisplay(cols, rows)

    if driver == "hd44780-pcf8574":
        from smbus2 import SMBus  # imported lazily: only needed on real hardware

        from .hd44780 import Hd44780
        from .pcf8574 import PIN_MAPPINGS, Pcf8574Bus

        options = config.get(driver, {})
        mapping_name = options.get("pin_mapping", "standard")
        if mapping_name not in PIN_MAPPINGS:
            raise ValueError(
                f"unknown pin_mapping {mapping_name!r}, use one of {sorted(PIN_MAPPINGS)}"
            )
        i2c = SMBus(int(options.get("i2c_bus", 1)))
        bus = Pcf8574Bus(i2c, int(options.get("i2c_address", 0x27)), PIN_MAPPINGS[mapping_name])
        return Hd44780(bus, cols, rows, charset=options.get("charset", "A00"))

    raise ValueError(f"unknown display driver {driver!r}")
