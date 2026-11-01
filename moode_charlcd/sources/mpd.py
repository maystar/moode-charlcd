"""MPD adapter: library, radio and UPnP playback in moOde.

Listens for MPD ``idle`` events, so changes made in the moOde web UI show up
immediately. Commands use a separate short-lived connection.
"""

from __future__ import annotations

import contextlib
import logging
import os
import select
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from ..model import ALL_ACTIONS, Action, NowPlaying, PlaybackState
from .base import Notify, PlayerAdapter

logger = logging.getLogger(__name__)

IDLE_SUBSYSTEMS = ("player", "options", "mixer", "playlist")


class MpdClient(Protocol):
    """The subset of ``mpd.MPDClient`` used here."""

    timeout: float | None

    def connect(self, host: str, port: int) -> None: ...
    def disconnect(self) -> None: ...
    def fileno(self) -> int: ...
    def status(self) -> dict[str, Any]: ...
    def currentsong(self) -> dict[str, Any]: ...
    def send_idle(self, *subsystems: str) -> None: ...
    def fetch_idle(self) -> list[str]: ...
    def pause(self, value: int) -> None: ...
    def play(self) -> None: ...
    def previous(self) -> None: ...
    def next(self) -> None: ...


def _default_client_factory() -> MpdClient:
    from mpd import MPDClient

    client: MpdClient = MPDClient()
    return client


def _text(value: Any) -> str:
    """MPD returns a list when a tag occurs several times."""
    if value is None:
        return ""
    if isinstance(value, list):
        return ", ".join(str(v) for v in value if v)
    return str(value)


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _flag(value: Any) -> bool:
    # consume/single may be "oneshot" since MPD 0.21/0.24
    return str(value) not in ("", "0", "None")


def _is_stream(file: str) -> bool:
    return "://" in file


def map_mpd(status: Mapping[str, Any], song: Mapping[str, Any], now: float) -> NowPlaying:
    """Translate MPD ``status`` and ``currentsong`` into :class:`NowPlaying`."""
    state = {
        "play": PlaybackState.PLAY,
        "pause": PlaybackState.PAUSE,
    }.get(str(status.get("state")), PlaybackState.STOP)

    file = _text(song.get("file"))
    title = _text(song.get("title"))
    artist = _text(song.get("artist")) or _text(song.get("albumartist"))
    album = _text(song.get("album"))

    if _is_stream(file) or song.get("name"):
        # Radio: the station name is the "album", the stream title often has
        # the form "Artist - Title".
        station = _text(song.get("name"))
        album = album or station
        if title and not artist and " - " in title:
            artist, title = (part.strip() for part in title.split(" - ", 1))
        title = title or station
    elif not title and file:
        title = os.path.splitext(os.path.basename(file))[0]

    elapsed = _float(status.get("elapsed"))
    duration = _float(status.get("duration"))
    if (elapsed is None or duration is None) and ":" in str(status.get("time", "")):
        old_elapsed, old_duration = str(status["time"]).split(":", 1)
        elapsed = elapsed if elapsed is not None else _float(old_elapsed)
        duration = duration if duration is not None else _float(old_duration)
    if duration is not None and duration <= 0:
        duration = None

    volume = _float(status.get("volume"))
    return NowPlaying(
        source="mpd",
        source_label="MPD",
        state=state,
        title=title,
        artist=artist,
        album=album,
        elapsed=elapsed if state != PlaybackState.STOP else None,
        duration=duration,
        updated_at=now,
        random=_flag(status.get("random")),
        repeat=_flag(status.get("repeat")),
        consume=_flag(status.get("consume")),
        single=_flag(status.get("single")),
        volume=int(volume) if volume is not None and volume >= 0 else None,
        actions=ALL_ACTIONS,
    )


class MpdAdapter(PlayerAdapter):
    name = "mpd"

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6600,
        reconnect_interval: float = 3.0,
        client_factory: Callable[[], MpdClient] = _default_client_factory,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._host = host
        self._port = port
        self._reconnect_interval = reconnect_interval
        self._client_factory = client_factory
        self._clock = clock
        self._lock = threading.Lock()
        self._current: NowPlaying | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._notify: Notify = lambda: None

    # -- lifecycle ---------------------------------------------------------

    def start(self, notify: Notify) -> None:
        self._notify = notify
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="mpd-idle", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def now_playing(self) -> NowPlaying | None:
        with self._lock:
            return self._current

    # -- events ------------------------------------------------------------

    def _connect(self) -> MpdClient:
        client = self._client_factory()
        client.timeout = 10
        client.connect(self._host, self._port)
        return client

    def _run(self) -> None:
        failed = False
        while not self._stop.is_set():
            client = None
            try:
                client = self._connect()
                logger.info("Connected to MPD at %s:%s", self._host, self._port)
                failed = False
                self.refresh(client)
                while not self._stop.is_set():
                    client.send_idle(*IDLE_SUBSYSTEMS)
                    if not self._wait_readable(client):
                        break
                    client.fetch_idle()
                    self.refresh(client)
            except Exception as error:  # connection lost, MPD restarted, ...
                # Warn once when the connection is lost, then retry quietly.
                level = (
                    logging.WARNING
                    if self.now_playing() is not None or not failed
                    else logging.DEBUG
                )
                logger.log(level, "MPD connection failed: %s", error)
                failed = True
                self._set(None)
            finally:
                if client is not None:
                    with contextlib.suppress(Exception):
                        client.disconnect()
            self._stop.wait(self._reconnect_interval)

    def _wait_readable(self, client: MpdClient) -> bool:
        """Wait for an idle response; False if the adapter is stopping."""
        while not self._stop.is_set():
            readable, _, _ = select.select([client.fileno()], [], [], 1.0)
            if readable:
                return True
        return False

    def refresh(self, client: MpdClient) -> None:
        self._set(map_mpd(client.status(), client.currentsong(), self._clock()))

    def _set(self, value: NowPlaying | None) -> None:
        with self._lock:
            changed = not (
                value is self._current or (value is not None and value.same_content(self._current))
            )
            self._current = value
        if changed:
            self._notify()

    # -- commands ----------------------------------------------------------

    def execute(self, action: Action) -> None:
        current = self.now_playing()
        client = self._connect()
        try:
            if action == Action.PLAY_PAUSE:
                state = current.state if current else PlaybackState.STOP
                if state == PlaybackState.PLAY:
                    client.pause(1)
                elif state == PlaybackState.PAUSE:
                    client.pause(0)
                else:
                    client.play()
            elif action == Action.PREVIOUS:
                client.previous()
            elif action == Action.NEXT:
                client.next()
        finally:
            client.disconnect()
