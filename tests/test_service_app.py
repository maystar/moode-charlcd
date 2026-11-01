from __future__ import annotations

import io
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pytest

from moode_charlcd.buttons import Button, GpioButtons, parse_pins
from moode_charlcd.config import load_config
from moode_charlcd.hal.console import ConsoleDisplay
from moode_charlcd.model import Action, NowPlaying
from moode_charlcd.service import NowPlayingService
from moode_charlcd.sources.base import Notify, PlayerAdapter
from moode_charlcd.ui.layout import StandardLayout
from moode_charlcd.ui.screen import Screen

from .conftest import mpd_playing


class StaticAdapter(PlayerAdapter):
    def __init__(self, name: str, value: NowPlaying | None) -> None:
        self.name = name
        self.value = value
        self.executed: list[Action] = []
        self.started = False
        self.notify: Notify | None = None

    def start(self, notify: Notify) -> None:
        self.started = True
        self.notify = notify

    def stop(self) -> None:
        self.started = False

    def now_playing(self) -> NowPlaying | None:
        return self.value

    def execute(self, action: Action) -> None:
        self.executed.append(action)


# -- service ---------------------------------------------------------------


def test_first_active_adapter_wins() -> None:
    renderer = StaticAdapter("renderer", None)
    mpd = StaticAdapter("mpd", mpd_playing())
    service = NowPlayingService([renderer, mpd])
    assert service.current().source == "mpd"
    renderer.value = mpd_playing(source="spotify")
    assert service.current().source == "spotify"


def test_offline_when_no_adapter_is_active() -> None:
    service = NowPlayingService([StaticAdapter("mpd", None)], offline_label="offline")
    assert service.current().source_label == "offline"
    service.execute(Action.NEXT)  # nothing to do, must not raise


def test_actions_are_routed_to_active_adapter_if_supported() -> None:
    mpd = StaticAdapter("mpd", mpd_playing(actions=frozenset({Action.NEXT})))
    service = NowPlayingService([mpd])
    service.execute(Action.NEXT)
    service.execute(Action.PREVIOUS)
    assert mpd.executed == [Action.NEXT]


def test_failing_action_is_logged_not_raised() -> None:
    mpd = StaticAdapter("mpd", mpd_playing())
    mpd.execute = lambda action: (_ for _ in ()).throw(RuntimeError("boom"))  # type: ignore[method-assign]
    NowPlayingService([mpd]).execute(Action.NEXT)


def test_start_stop_and_change_notification() -> None:
    mpd = StaticAdapter("mpd", mpd_playing())
    service = NowPlayingService([mpd])
    service.start()
    assert mpd.started
    assert not service.wait_for_change(0.01)
    assert mpd.notify is not None
    mpd.notify()
    assert service.wait_for_change(0.01)
    service.stop()
    assert not mpd.started


# -- buttons ---------------------------------------------------------------


class FakeButton:
    def __init__(self, pin: int, bounce_time: float) -> None:
        self.pin = pin
        self.bounce_time = bounce_time
        self.when_pressed: Callable[[], None] | None = None
        self.closed = False

    def press(self) -> None:
        assert self.when_pressed is not None
        self.when_pressed()

    def close(self) -> None:
        self.closed = True


def test_parse_pins() -> None:
    assert parse_pins({"play_pause": 4, "next": "10"}) == {Action.PLAY_PAUSE: 4, Action.NEXT: 10}
    with pytest.raises(ValueError, match="unknown button action"):
        parse_pins({"shutdown": 9})


class ButtonFactory:
    def __init__(self) -> None:
        self.created: list[FakeButton] = []

    def __call__(self, pin: int, bounce: float) -> Button:
        self.created.append(FakeButton(pin, bounce))
        return self.created[-1]


def test_buttons_call_handler() -> None:
    factory = ButtonFactory()
    created = factory.created
    received: list[Action] = []
    buttons = GpioButtons({Action.NEXT: 10, Action.PREVIOUS: 16}, received.append, 250, factory)
    assert [(b.pin, b.bounce_time) for b in created] == [(10, 0.25), (16, 0.25)]
    created[0].press()
    assert received == [Action.NEXT]
    buttons.close()
    assert all(b.closed for b in created)


def test_button_handler_errors_are_caught() -> None:
    factory = ButtonFactory()

    def failing(_action: Action) -> None:
        raise RuntimeError("boom")

    GpioButtons({Action.NEXT: 10}, failing, 250, factory)
    factory.created[0].press()


# -- config ----------------------------------------------------------------


def test_defaults_without_user_file(tmp_path: Path) -> None:
    config = load_config(tmp_path / "missing.toml")
    assert config["display"]["hd44780-pcf8574"]["i2c_address"] == 0x27
    assert config["buttons"]["pins"] == {"play_pause": 4, "previous": 16, "next": 10}


def test_user_file_overrides_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        '[display]\ncols = 16\n[display.hd44780-pcf8574]\npin_mapping = "standard"\n'
        "[buttons.pins]\nnext = 21\n"
    )
    config = load_config(path)
    assert config["display"]["cols"] == 16
    assert config["display"]["rows"] == 4
    assert config["display"]["hd44780-pcf8574"]["pin_mapping"] == "standard"
    assert config["display"]["hd44780-pcf8574"]["i2c_address"] == 0x27
    assert config["buttons"]["pins"] == {"next": 21}  # replaced as a whole


# -- app -------------------------------------------------------------------


def test_app_renders_until_stopped_and_says_goodbye() -> None:
    from moode_charlcd.app import App

    out = io.StringIO()
    display = ConsoleDisplay(20, 4, out=out, ansi=False)
    mpd = StaticAdapter("mpd", mpd_playing())
    stop = threading.Event()
    renders = 0

    class CountingLayout(StandardLayout):
        def render(self, *args, **kwargs):
            nonlocal renders
            renders += 1
            if renders == 2:
                stop.set()
            return super().render(*args, **kwargs)

    app = App(
        NowPlayingService([mpd]),
        [Screen(display)],
        CountingLayout(20, 4),
        refresh_hz=100,
        goodbye="Bye",
        wall_clock=lambda: datetime(2026, 1, 1, 8, 15),
        monotonic=lambda: 100.0,
    )
    app.run(stop)
    assert renders == 2
    assert "Gasoline" in out.getvalue()
    assert display.text()[1].strip() == "Bye"
    assert not mpd.started


def test_build_app_with_console_display(tmp_path: Path) -> None:
    from moode_charlcd.app import build_app

    config = load_config(None)
    config["display"]["driver"] = "console"
    config["buttons"]["enabled"] = False
    app = build_app(config)
    assert len(app.screens) == 1
    assert isinstance(app.screens[0].display, ConsoleDisplay)
    assert isinstance(app.layout, StandardLayout)
    assert not app.layout.show_legend


def test_unknown_display_driver() -> None:
    from moode_charlcd.hal.factory import create_display

    with pytest.raises(ValueError, match="driver"):
        create_display({"driver": "oled", "cols": 20, "rows": 4})


def test_app_continues_without_buttons_if_setup_fails() -> None:
    from moode_charlcd.app import App

    display = ConsoleDisplay(20, 4, out=io.StringIO(), ansi=False)
    stop = threading.Event()

    def broken_buttons(_service: NowPlayingService) -> None:
        stop.set()
        raise RuntimeError("no GPIO")

    app = App(
        NowPlayingService([StaticAdapter("mpd", mpd_playing())]),
        [Screen(display)],
        StandardLayout(20, 4),
        goodbye="Bye",
        buttons_factory=broken_buttons,
    )
    app.run(stop)
    assert display.text()[1].strip() == "Bye"
