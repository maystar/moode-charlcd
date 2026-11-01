# Changelog

## 0.2.0 (2026-11-01)

First version for moOde (target: moOde 10 on Raspberry Pi OS Trixie), replacing the Mopidy extension
[mopidy-charlcd](https://github.com/maystar/mopidy-charlcd). Version 0.2.0 because the
repository already carries a tag `0.1.1` from the earlier, unfinished code.

- Standalone service `moode-charlcd` with TOML configuration.
- MPD via `idle` events: title, artist, album, elapsed time, repeat/random/consume, radio streams.
- moOde renderers (Spotify Connect, AirPlay, Qobuz, Squeezelite, Roon, Plexamp, inputs,
  multiroom receiver) detected from moOde's database and metadata files.
- Bluetooth metadata and control through BlueZ.
- Buttons via gpiozero, triggered on press.
- Display HAL with HD44780/PCF8574 driver (`joyit` and `standard` pin mapping, character ROM
  A00/A02) and console display.
- CI with ruff, mypy (strict) and pytest.
