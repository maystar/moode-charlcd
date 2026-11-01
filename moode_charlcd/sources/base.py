"""Interface of the input adapters."""

from __future__ import annotations

import logging
import threading
from abc import ABC, abstractmethod
from collections.abc import Callable

from ..model import Action, NowPlaying

logger = logging.getLogger(__name__)

Notify = Callable[[], None]


class PlayerAdapter(ABC):
    """One source of playback information.

    :meth:`now_playing` returns ``None`` while the source is inactive; the
    service then asks the next adapter (adapters are ordered by priority).
    """

    name: str = "adapter"

    def start(self, notify: Notify) -> None:  # noqa: B027 - optional hook
        """Start background work; call ``notify`` whenever data changed."""

    def stop(self) -> None:  # noqa: B027 - optional hook
        """Stop background work."""

    @abstractmethod
    def now_playing(self) -> NowPlaying | None: ...

    @abstractmethod
    def execute(self, action: Action) -> None:
        """Run a button action. Only called with actions from ``now_playing().actions``."""


class PollingAdapter(PlayerAdapter):
    """Adapter that refreshes its state periodically in a background thread."""

    def __init__(self, interval: float) -> None:
        self._interval = interval
        self._lock = threading.Lock()
        self._current: NowPlaying | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._notify: Notify = lambda: None

    @abstractmethod
    def poll(self, previous: NowPlaying | None) -> NowPlaying | None:
        """Read the current state (runs in the background thread)."""

    def refresh(self) -> None:
        try:
            current = self.poll(self._current)
        except Exception:
            logger.exception("%s: polling failed", self.name)
            current = None
        with self._lock:
            changed = not (
                current is self._current
                or (current is not None and current.same_content(self._current))
            )
            self._current = current
        if changed:
            self._notify()

    def start(self, notify: Notify) -> None:
        self._notify = notify
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name=self.name, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def _run(self) -> None:
        while not self._stop.is_set():
            self.refresh()
            self._stop.wait(self._interval)

    def now_playing(self) -> NowPlaying | None:
        with self._lock:
            return self._current
