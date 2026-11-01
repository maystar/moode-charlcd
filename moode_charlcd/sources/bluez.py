"""BlueZ AVRCP media player (Bluetooth source such as a phone).

Uses ``busctl`` (part of systemd) to talk to ``org.bluez`` on the system
D-Bus, so no D-Bus Python binding is needed. The service user must be allowed
to talk to BlueZ (Debian: member of group ``bluetooth``).
"""

from __future__ import annotations

import json
import logging
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from ..model import Action

logger = logging.getLogger(__name__)

PLAYER_INTERFACE = "org.bluez.MediaPlayer1"

Runner = Callable[[Sequence[str]], str]


def run_busctl(args: Sequence[str]) -> str:
    result = subprocess.run(
        ["busctl", "--system", "--json=short", *args],
        capture_output=True,
        text=True,
        timeout=3,
        check=True,
    )
    return result.stdout


@dataclass(frozen=True)
class BluezPlayer:
    path: str
    status: str  # "playing", "paused", "stopped", ...
    title: str = ""
    artist: str = ""
    album: str = ""
    position_ms: int | None = None
    duration_ms: int | None = None


def unwrap(value: Any) -> Any:
    """Remove the ``{"type": ..., "data": ...}`` wrappers of busctl's JSON output."""
    if isinstance(value, dict):
        if set(value) == {"type", "data"}:
            return unwrap(value["data"])
        return {key: unwrap(item) for key, item in value.items()}
    if isinstance(value, list):
        return [unwrap(item) for item in value]
    return value


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def parse_players(managed_objects_json: str) -> list[BluezPlayer]:
    """Extract media players from ``ObjectManager.GetManagedObjects`` output."""
    data = unwrap(json.loads(managed_objects_json))
    objects = data[0] if isinstance(data, list) else data
    players = []
    for path, interfaces in objects.items():
        props = interfaces.get(PLAYER_INTERFACE)
        if props is None:
            continue
        track = props.get("Track") or {}
        players.append(
            BluezPlayer(
                path=path,
                status=str(props.get("Status", "")),
                title=str(track.get("Title", "")),
                artist=str(track.get("Artist", "")),
                album=str(track.get("Album", "")),
                position_ms=_int(props.get("Position")),
                duration_ms=_int(track.get("Duration")) or None,
            )
        )
    return players


_METHODS = {Action.PLAY_PAUSE: None, Action.PREVIOUS: "Previous", Action.NEXT: "Next"}


class BluezClient:
    def __init__(self, runner: Runner = run_busctl) -> None:
        self._runner = runner

    def current_player(self) -> BluezPlayer | None:
        """The playing player, otherwise the first one, or ``None``."""
        try:
            output = self._runner(
                [
                    "call",
                    "org.bluez",
                    "/",
                    "org.freedesktop.DBus.ObjectManager",
                    "GetManagedObjects",
                ]
            )
            players = parse_players(output)
        except (subprocess.SubprocessError, OSError, ValueError) as error:
            logger.debug("Cannot read BlueZ players: %s", error)
            return None
        for player in players:
            if player.status == "playing":
                return player
        return players[0] if players else None

    def execute(self, player: BluezPlayer, action: Action) -> None:
        method = _METHODS[action]
        if method is None:
            method = "Pause" if player.status == "playing" else "Play"
        self._runner(["call", "org.bluez", player.path, PLAYER_INTERFACE, method])
