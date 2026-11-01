from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from typing import Any

import pytest

from moode_charlcd import __main__ as cli
from moode_charlcd.hal.factory import create_display
from moode_charlcd.hal.hd44780 import Hd44780
from moode_charlcd.model import Action, NowPlaying
from moode_charlcd.sources.base import PollingAdapter

from .conftest import mpd_playing


class FakeSmbus:
    def __init__(self, bus: int) -> None:
        self.bus = bus
        self.written: list[tuple[int, int]] = []

    def write_byte(self, address: int, value: int) -> None:
        self.written.append((address, value))


@pytest.fixture
def fake_smbus2(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("smbus2")
    module.SMBus = FakeSmbus  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "smbus2", module)
    monkeypatch.setattr("time.sleep", lambda _s: None)


@pytest.mark.usefixtures("fake_smbus2")
def test_factory_creates_hd44780_on_pcf8574() -> None:
    display = create_display(
        {
            "driver": "hd44780-pcf8574",
            "cols": 16,
            "rows": 2,
            "hd44780-pcf8574": {"i2c_bus": 1, "i2c_address": 0x3F, "pin_mapping": "joyit"},
        }
    )
    assert isinstance(display, Hd44780)
    assert (display.cols, display.rows) == (16, 2)


@pytest.mark.usefixtures("fake_smbus2")
def test_factory_rejects_unknown_pin_mapping() -> None:
    with pytest.raises(ValueError, match="pin_mapping"):
        create_display(
            {
                "driver": "hd44780-pcf8574",
                "cols": 20,
                "rows": 4,
                "hd44780-pcf8574": {"pin_mapping": "x"},
            }
        )


def test_parse_args_defaults() -> None:
    args = cli.parse_args([])
    assert args.config == Path("/etc/moode-charlcd.toml")
    assert args.display is None
    assert not args.console


def test_main_builds_and_runs_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class FakeApp:
        def run(self, stop: threading.Event) -> None:
            captured["stop"] = stop

    def fake_build_app(config: dict[str, Any], console_mirror: bool = False) -> FakeApp:
        captured["config"] = config
        captured["mirror"] = console_mirror
        return FakeApp()

    monkeypatch.setattr(cli, "build_app", fake_build_app)
    monkeypatch.setattr("signal.signal", lambda *_args: None)
    cli.main(["--config", str(tmp_path / "none.toml"), "--display", "console", "--console"])
    assert captured["config"]["display"]["driver"] == "console"
    assert captured["mirror"] is True
    assert isinstance(captured["stop"], threading.Event)


class CountingAdapter(PollingAdapter):
    name = "counting"

    def __init__(self) -> None:
        super().__init__(interval=0.01)
        self.polls = 0

    def poll(self, previous: NowPlaying | None) -> NowPlaying | None:
        self.polls += 1
        if self.polls == 3:
            raise RuntimeError("temporary failure")
        return mpd_playing(title=f"poll {self.polls}")

    def execute(self, action: Action) -> None:
        pass


def test_polling_adapter_thread_survives_errors() -> None:
    adapter = CountingAdapter()
    changed = threading.Event()
    adapter.start(changed.set)
    try:
        for _ in range(300):
            if adapter.polls >= 5:
                break
            threading.Event().wait(0.01)
    finally:
        adapter.stop()
    assert adapter.polls >= 5
    assert changed.is_set()
    assert adapter.now_playing() is not None
