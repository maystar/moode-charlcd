"""Wires adapters, service, layout, screens and buttons together."""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from .buttons import GpioButtons, parse_pins
from .hal.base import CharacterDisplay
from .hal.console import ConsoleDisplay
from .hal.factory import create_display
from .service import NowPlayingService
from .sources.base import PlayerAdapter
from .sources.bluez import BluezClient
from .sources.moode import MetadataFiles, MoodeDatabase, MoodeRendererAdapter
from .sources.mpd import MpdAdapter
from .ui.layout import Layout, StandardLayout
from .ui.screen import Screen

logger = logging.getLogger(__name__)


class App:
    def __init__(
        self,
        service: NowPlayingService,
        screens: Sequence[Screen],
        layout: Layout,
        refresh_hz: float = 4,
        goodbye: str = "",
        buttons_factory: Callable[[NowPlayingService], GpioButtons | None] = lambda _: None,
        wall_clock: Callable[[], datetime] = datetime.now,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self.service = service
        self.screens = list(screens)
        self.layout = layout
        self.period = 1 / max(0.5, refresh_hz)
        self.goodbye = goodbye
        self._buttons_factory = buttons_factory
        self._wall_clock = wall_clock
        self._monotonic = monotonic

    def render_once(self) -> None:
        frame = self.layout.render(self.service.current(), self._wall_clock(), self._monotonic())
        for screen in self.screens:
            screen.show(frame)

    def run(self, stop: threading.Event) -> None:
        self.service.start()
        buttons = None
        try:
            try:
                buttons = self._buttons_factory(self.service)
            except Exception:
                logger.exception("Cannot set up buttons, continuing without them")
            while not stop.is_set():
                self.render_once()
                self.service.wait_for_change(self.period)
        finally:
            if buttons is not None:
                buttons.close()
            self.service.stop()
            if self.goodbye:
                frame = self.layout.message(self.goodbye)
                for screen in self.screens:
                    screen.show(frame)
            for screen in self.screens:
                screen.display.close()


def build_adapters(config: dict[str, Any]) -> list[PlayerAdapter]:
    adapters: list[PlayerAdapter] = []
    moode = config["moode"]
    if moode.get("enabled", True):
        bluez = BluezClient() if config["bluetooth"].get("enabled", True) else None
        adapters.append(
            MoodeRendererAdapter(
                MoodeDatabase(Path(moode["database"])),
                MetadataFiles(Path(moode["metadata_dir"])),
                bluez=bluez,
                poll_interval=float(moode.get("poll_interval", 1.0)),
            )
        )
    mpd = config["mpd"]
    adapters.append(
        MpdAdapter(
            host=mpd["host"],
            port=int(mpd["port"]),
            reconnect_interval=float(mpd.get("reconnect_interval", 3)),
        )
    )
    return adapters


def build_app(config: dict[str, Any], console_mirror: bool = False) -> App:
    display_config = config["display"]
    displays: list[CharacterDisplay] = [create_display(display_config)]
    if (console_mirror or display_config.get("console_mirror")) and not isinstance(
        displays[0], ConsoleDisplay
    ):
        displays.append(ConsoleDisplay(displays[0].cols, displays[0].rows))

    buttons_config = config["buttons"]
    pins = parse_pins(buttons_config.get("pins", {})) if buttons_config.get("enabled") else {}

    def buttons_factory(service: NowPlayingService) -> GpioButtons | None:
        if not pins:
            return None
        return GpioButtons(pins, service.execute, int(buttons_config.get("bounce_ms", 250)))

    first = displays[0]
    return App(
        service=NowPlayingService(build_adapters(config)),
        screens=[Screen(display) for display in displays],
        layout=StandardLayout(first.cols, first.rows, show_legend=bool(pins)),
        refresh_hz=float(display_config.get("refresh_hz", 4)),
        goodbye=str(display_config.get("goodbye", "")),
        buttons_factory=buttons_factory,
    )
