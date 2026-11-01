"""moOde renderers (Spotify Connect, Bluetooth, AirPlay, Squeezelite, ...).

moOde stores which renderer is active in its SQLite database (table
``cfg_system``, e.g. ``spotactive=1``) and writes renderer metadata to JSON
files in ``/var/local/www`` (``spotmeta.json``, ``aplmeta.json``, ...). While a
renderer is active, MPD is stopped and this adapter takes precedence.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..model import ALL_ACTIONS, Action, NowPlaying, PlaybackState
from .base import PollingAdapter
from .bluez import BluezClient, BluezPlayer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Renderer:
    flag: str  # parameter in cfg_system
    source: str
    label: str
    metadata_file: str | None = None
    bluetooth: bool = False


# Order = priority if several flags are set at the same time.
RENDERERS = (
    Renderer("btactive", "bluetooth", "Bluetooth", bluetooth=True),
    Renderer("spotactive", "spotify", "Spotify", "spotmeta.json"),
    Renderer("aplactive", "airplay", "AirPlay", "aplmeta.json"),
    Renderer("qbzactive", "qobuz", "Qobuz", "qbzmeta.json"),
    Renderer("deezactive", "deezer", "Deezer", "deezmeta.json"),
    Renderer("slactive", "squeezelite", "Squeezelite"),
    Renderer("rbactive", "roon", "Roon"),
    Renderer("paactive", "plexamp", "Plexamp"),
    Renderer("inpactive", "input", "Eingang"),
)


class RendererStateRepository(Protocol):
    def active_flags(self) -> set[str]:
        """Names of the ``*active`` flags that are currently set."""
        ...


class MetadataRepository(Protocol):
    def read(self, filename: str) -> dict[str, Any] | None: ...


class MoodeDatabase:
    """Reads renderer flags from the moOde SQLite database (read-only)."""

    def __init__(self, path: Path) -> None:
        self._uri = f"file:{path}?mode=ro"

    def active_flags(self) -> set[str]:
        flags = [renderer.flag for renderer in RENDERERS]
        placeholders = ",".join("?" * len(flags))
        connection = sqlite3.connect(self._uri, uri=True, timeout=2)
        try:
            rows = connection.execute(
                f"SELECT param, value FROM cfg_system WHERE param IN ({placeholders})", flags
            ).fetchall()
        finally:
            connection.close()
        return {param for param, value in rows if str(value) == "1"}


class MetadataFiles:
    """Reads the renderer metadata JSON files written by moOde."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def read(self, filename: str) -> dict[str, Any] | None:
        try:
            text = (self._directory / filename).read_text(encoding="utf-8").strip()
        except OSError:
            return None
        if not text:
            return None  # moOde truncates the file when the renderer disconnects
        try:
            data = json.loads(text)
        except ValueError:
            logger.debug("Invalid JSON in %s", filename)
            return None
        return data if isinstance(data, dict) else None


class MoodeRendererAdapter(PollingAdapter):
    name = "moode-renderer"

    def __init__(
        self,
        state: RendererStateRepository,
        metadata: MetadataRepository,
        bluez: BluezClient | None = None,
        poll_interval: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        super().__init__(poll_interval)
        self._state = state
        self._metadata = metadata
        self._bluez = bluez
        self._clock = clock
        self._player: BluezPlayer | None = None
        self._last_error = ""

    def poll(self, previous: NowPlaying | None) -> NowPlaying | None:
        try:
            flags = self._state.active_flags()
        except sqlite3.Error as error:
            # Log once per distinct error, the poll runs every second.
            if str(error) != self._last_error:
                logger.warning("Cannot read moOde database: %s", error)
                self._last_error = str(error)
            return None
        if self._last_error:
            logger.info("moOde database readable again")
            self._last_error = ""
        renderer = next((r for r in RENDERERS if r.flag in flags), None)
        self._player = None
        if renderer is None:
            return None
        if renderer.bluetooth:
            return self._bluetooth(renderer, previous)
        if renderer.metadata_file:
            data = self._metadata.read(renderer.metadata_file)
            if data:
                return self._from_metadata(renderer, data)
        return NowPlaying(
            source=renderer.source, source_label=renderer.label, state=PlaybackState.PLAY
        )

    def _from_metadata(self, renderer: Renderer, data: dict[str, Any]) -> NowPlaying:
        playstate = str(data.get("playstate", "Resume"))
        return NowPlaying(
            source=renderer.source,
            source_label=renderer.label,
            state=PlaybackState.PAUSE if playstate == "Pause" else PlaybackState.PLAY,
            title=str(data.get("title") or ""),
            artist=str(data.get("artist") or ""),
            album=str(data.get("album") or ""),
            updated_at=self._clock(),
        )

    def _bluetooth(self, renderer: Renderer, previous: NowPlaying | None) -> NowPlaying:
        player = self._bluez.current_player() if self._bluez else None
        self._player = player
        if player is None:
            return NowPlaying(
                source=renderer.source, source_label=renderer.label, state=PlaybackState.PLAY
            )
        state = {
            "playing": PlaybackState.PLAY,
            "paused": PlaybackState.PAUSE,
        }.get(player.status, PlaybackState.STOP)
        now = self._clock()
        elapsed = player.position_ms / 1000 if player.position_ms is not None else None
        updated_at = now
        # Some sources only report the position on changes; keep interpolating
        # from the last real change instead of resetting the time stamp.
        if (
            previous is not None
            and previous.source == renderer.source
            and previous.state == state
            and previous.elapsed == elapsed
        ):
            updated_at = previous.updated_at
        return NowPlaying(
            source=renderer.source,
            source_label=renderer.label,
            state=state,
            title=player.title,
            artist=player.artist,
            album=player.album,
            elapsed=elapsed,
            duration=player.duration_ms / 1000 if player.duration_ms else None,
            updated_at=updated_at,
            actions=ALL_ACTIONS,
        )

    def execute(self, action: Action) -> None:
        player = self._player
        if self._bluez is None or player is None:
            logger.info("Action %s is not supported by the active renderer", action.value)
            return
        self._bluez.execute(player, action)
