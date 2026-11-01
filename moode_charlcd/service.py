"""Combines the adapters: picks the active source and routes button actions."""

from __future__ import annotations

import logging
import threading
from collections.abc import Sequence

from .model import Action, NowPlaying, idle
from .sources.base import PlayerAdapter

logger = logging.getLogger(__name__)


class NowPlayingService:
    def __init__(
        self, adapters: Sequence[PlayerAdapter], offline_label: str = "MPD offline"
    ) -> None:
        """``adapters`` are ordered by priority: the first active one wins."""
        self._adapters = list(adapters)
        self._offline = idle(offline_label)
        self._changed = threading.Event()

    def start(self) -> None:
        for adapter in self._adapters:
            adapter.start(self._changed.set)

    def stop(self) -> None:
        for adapter in self._adapters:
            try:
                adapter.stop()
            except Exception:
                logger.exception("Stopping %s failed", adapter.name)

    def _active(self) -> tuple[PlayerAdapter | None, NowPlaying]:
        for adapter in self._adapters:
            now_playing = adapter.now_playing()
            if now_playing is not None:
                return adapter, now_playing
        return None, self._offline

    def current(self) -> NowPlaying:
        return self._active()[1]

    def execute(self, action: Action) -> None:
        adapter, now_playing = self._active()
        if adapter is None or action not in now_playing.actions:
            logger.info("Ignoring %s: not supported by %s", action.value, now_playing.source)
            return
        logger.info("%s -> %s", action.value, adapter.name)
        try:
            adapter.execute(action)
        except Exception:
            logger.exception("Action %s failed", action.value)

    def wait_for_change(self, timeout: float) -> bool:
        """Block until an adapter reported a change or ``timeout`` elapsed."""
        changed = self._changed.wait(timeout)
        self._changed.clear()
        return changed
