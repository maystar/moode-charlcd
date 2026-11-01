from __future__ import annotations

import socket
import threading
from typing import Any

import pytest

from moode_charlcd.model import ALL_ACTIONS, Action, PlaybackState
from moode_charlcd.sources.mpd import MpdAdapter, map_mpd

STATUS = {
    "volume": "62",
    "repeat": "1",
    "random": "0",
    "single": "0",
    "consume": "oneshot",
    "state": "play",
    "elapsed": "83.512",
    "duration": "280.123",
}
SONG = {
    "file": "NAS/rasp4/Audioslave/Audioslave/03 - Gasoline.flac",
    "artist": "Audioslave",
    "album": "Audioslave",
    "title": "Gasoline",
}


def test_map_library_track() -> None:
    np = map_mpd(STATUS, SONG, now=5.0)
    assert (np.title, np.artist, np.album) == ("Gasoline", "Audioslave", "Audioslave")
    assert np.state == PlaybackState.PLAY
    assert np.elapsed == pytest.approx(83.512)
    assert np.duration == pytest.approx(280.123)
    assert np.updated_at == 5.0
    assert (np.repeat, np.random, np.consume, np.single) == (True, False, True, False)
    assert np.volume == 62
    assert np.actions == ALL_ACTIONS


def test_map_multiple_artists_and_missing_title() -> None:
    song = {"file": "music/Some Song.mp3", "artist": ["A", "B"]}
    np = map_mpd(STATUS, song, now=0)
    assert np.artist == "A, B"
    assert np.title == "Some Song"


def test_map_radio_splits_stream_title() -> None:
    song = {"file": "http://stream.example/radio", "name": "Radio Bob", "title": "Band - Song"}
    status = {"state": "play", "elapsed": "12.0"}
    np = map_mpd(status, song, now=0)
    assert (np.title, np.artist, np.album) == ("Song", "Band", "Radio Bob")
    assert np.duration is None


def test_map_radio_without_stream_title_uses_station() -> None:
    song = {"file": "http://stream.example/radio", "name": "Radio Bob"}
    np = map_mpd({"state": "play"}, song, now=0)
    assert np.title == "Radio Bob"


def test_map_legacy_time_field() -> None:
    np = map_mpd({"state": "pause", "time": "10:200"}, SONG, now=0)
    assert np.state == PlaybackState.PAUSE
    assert (np.elapsed, np.duration) == (10.0, 200.0)


def test_map_stopped_has_no_elapsed() -> None:
    np = map_mpd({"state": "stop", "volume": "-1"}, {}, now=0)
    assert np.state == PlaybackState.STOP
    assert np.elapsed is None
    assert np.volume is None


class FakeClient:
    """Minimal MPD client: idle responses are triggered through a socket pair."""

    def __init__(self, status: dict[str, Any] | None = None, fail: bool = False) -> None:
        self.timeout: float | None = None
        self.status_value = dict(status or STATUS)
        self.song = dict(SONG)
        self.calls: list[tuple[Any, ...]] = []
        self.fail = fail
        self._reader, self._writer = socket.socketpair()

    def connect(self, host: str, port: int) -> None:
        if self.fail:
            raise ConnectionRefusedError("no MPD")
        self.calls.append(("connect", host, port))

    def disconnect(self) -> None:
        self.calls.append(("disconnect",))

    def fileno(self) -> int:
        return self._reader.fileno()

    def status(self) -> dict[str, Any]:
        return self.status_value

    def currentsong(self) -> dict[str, Any]:
        return self.song

    def send_idle(self, *subsystems: str) -> None:
        self.calls.append(("send_idle", *subsystems))

    def fetch_idle(self) -> list[str]:
        self._reader.recv(1)
        return ["player"]

    def trigger(self) -> None:
        self._writer.send(b"x")

    def pause(self, value: int) -> None:
        self.calls.append(("pause", value))

    def play(self) -> None:
        self.calls.append(("play",))

    def previous(self) -> None:
        self.calls.append(("previous",))

    def next(self) -> None:
        self.calls.append(("next",))


def wait_until(condition: Any, timeout: float = 3.0) -> None:
    event = threading.Event()
    for _ in range(int(timeout / 0.01)):
        if condition():
            return
        event.wait(0.01)
    raise AssertionError("condition not met")


def test_adapter_follows_idle_events() -> None:
    client = FakeClient()
    adapter = MpdAdapter(client_factory=lambda: client, clock=lambda: 1.0)
    notified = threading.Event()
    adapter.start(notified.set)
    try:
        wait_until(lambda: adapter.now_playing() is not None)
        assert adapter.now_playing().title == "Gasoline"  # type: ignore[union-attr]
        notified.clear()
        client.song = {**SONG, "title": "Show Me How to Live"}
        client.trigger()
        wait_until(notified.is_set)
        assert adapter.now_playing().title == "Show Me How to Live"  # type: ignore[union-attr]
    finally:
        adapter.stop()
    assert ("disconnect",) in client.calls


def test_adapter_reports_none_when_mpd_is_down() -> None:
    adapter = MpdAdapter(client_factory=lambda: FakeClient(fail=True), reconnect_interval=0.01)
    notified = threading.Event()
    adapter.start(notified.set)
    try:
        threading.Event().wait(0.1)
        assert adapter.now_playing() is None
    finally:
        adapter.stop()


@pytest.mark.parametrize(
    ("state", "action", "expected"),
    [
        ("play", Action.PLAY_PAUSE, ("pause", 1)),
        ("pause", Action.PLAY_PAUSE, ("pause", 0)),
        ("stop", Action.PLAY_PAUSE, ("play",)),
        ("play", Action.NEXT, ("next",)),
        ("play", Action.PREVIOUS, ("previous",)),
    ],
)
def test_execute(state: str, action: Action, expected: tuple[Any, ...]) -> None:
    listener = FakeClient({**STATUS, "state": state})
    commands = FakeClient()
    adapter = MpdAdapter(client_factory=lambda: commands)
    adapter.refresh(listener)
    adapter.execute(action)
    assert commands.calls == [("connect", "localhost", 6600), expected, ("disconnect",)]
