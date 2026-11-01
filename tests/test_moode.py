from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from moode_charlcd.model import ALL_ACTIONS, NO_ACTIONS, Action, PlaybackState
from moode_charlcd.sources.bluez import BluezPlayer
from moode_charlcd.sources.moode import MetadataFiles, MoodeDatabase, MoodeRendererAdapter

# Format written by moOde's spotevent.sh (keys identical for aplmeta.json)
SPOTMETA = {
    "fecmd": "update_spotmeta",
    "title": "Song",
    "artist": "Band",
    "album": "Record",
    "duration": "200000",
    "cover_url": "https://example/cover.jpg",
    "sformat": "Vorbis 320 kbps",
    "oformat": "PCM 16/44.1 kHz, 2ch",
    "playstate": "Resume",
}


def make_db(path: Path, **flags: str) -> Path:
    connection = sqlite3.connect(path)
    connection.execute("CREATE TABLE cfg_system (id INTEGER PRIMARY KEY, param TEXT, value TEXT)")
    defaults = {"btactive": "0", "spotactive": "0", "aplactive": "0", "slactive": "0"}
    for param, value in {**defaults, **flags}.items():
        connection.execute("INSERT INTO cfg_system (param, value) VALUES (?, ?)", (param, value))
    connection.execute("INSERT INTO cfg_system (param, value) VALUES ('volknob', '1')")
    connection.commit()
    connection.close()
    return path


def test_database_reads_active_flags(tmp_path: Path) -> None:
    db = make_db(tmp_path / "moode.db", spotactive="1", slactive="1")
    assert MoodeDatabase(db).active_flags() == {"spotactive", "slactive"}


def test_database_is_opened_read_only(tmp_path: Path) -> None:
    db = make_db(tmp_path / "moode.db")
    MoodeDatabase(db).active_flags()
    assert not (tmp_path / "moode.db-journal").exists()
    with pytest.raises(sqlite3.Error):
        MoodeDatabase(tmp_path / "missing.db").active_flags()


def test_metadata_files(tmp_path: Path) -> None:
    (tmp_path / "spotmeta.json").write_text(json.dumps(SPOTMETA) + "\n")
    (tmp_path / "aplmeta.json").write_text("")
    (tmp_path / "qbzmeta.json").write_text("{broken")
    files = MetadataFiles(tmp_path)
    assert files.read("spotmeta.json") == SPOTMETA
    assert files.read("aplmeta.json") is None
    assert files.read("qbzmeta.json") is None
    assert files.read("missing.json") is None


class FakeState:
    def __init__(self, *flags: str) -> None:
        self.flags = set(flags)
        self.error: Exception | None = None

    def active_flags(self) -> set[str]:
        if self.error:
            raise self.error
        return self.flags


class FakeMetadata:
    def __init__(self, files: dict[str, dict[str, Any]] | None = None) -> None:
        self.files = files or {}

    def read(self, filename: str) -> dict[str, Any] | None:
        return self.files.get(filename)


class FakeBluez:
    def __init__(self, player: BluezPlayer | None) -> None:
        self.player = player
        self.executed: list[tuple[BluezPlayer, Action]] = []

    def current_player(self) -> BluezPlayer | None:
        return self.player

    def execute(self, player: BluezPlayer, action: Action) -> None:
        self.executed.append((player, action))


def adapter(state: FakeState, metadata: FakeMetadata | None = None, bluez: Any = None):
    return MoodeRendererAdapter(state, metadata or FakeMetadata(), bluez=bluez, clock=lambda: 50.0)


def test_no_renderer_active() -> None:
    assert adapter(FakeState()).poll(None) is None


def test_database_error_means_inactive() -> None:
    state = FakeState("spotactive")
    state.error = sqlite3.OperationalError("locked")
    assert adapter(state).poll(None) is None


def test_spotify_with_metadata() -> None:
    np = adapter(FakeState("spotactive"), FakeMetadata({"spotmeta.json": SPOTMETA})).poll(None)
    assert np is not None
    assert (np.source, np.source_label) == ("spotify", "Spotify")
    assert (np.title, np.artist, np.album) == ("Song", "Band", "Record")
    assert np.state == PlaybackState.PLAY
    assert np.actions == NO_ACTIONS


def test_spotify_paused() -> None:
    meta = {"spotmeta.json": {**SPOTMETA, "playstate": "Pause"}}
    np = adapter(FakeState("spotactive"), FakeMetadata(meta)).poll(None)
    assert np is not None
    assert np.state == PlaybackState.PAUSE


def test_renderer_without_metadata() -> None:
    np = adapter(FakeState("slactive")).poll(None)
    assert np is not None
    assert (np.source_label, np.title) == ("Squeezelite", "")


def test_bluetooth_has_priority_and_controls() -> None:
    player = BluezPlayer("/p", "playing", "Song", "Band", "", 5000, 200000)
    bluez = FakeBluez(player)
    a = adapter(FakeState("spotactive", "btactive"), bluez=bluez)
    np = a.poll(None)
    assert np is not None
    assert np.source == "bluetooth"
    assert (np.elapsed, np.duration, np.updated_at) == (5.0, 200.0, 50.0)
    assert np.actions == ALL_ACTIONS
    a.execute(Action.NEXT)
    assert bluez.executed == [(player, Action.NEXT)]


def test_bluetooth_keeps_timestamp_while_position_is_unchanged() -> None:
    player = BluezPlayer("/p", "playing", "Song", "Band", "", 5000, None)
    a = adapter(FakeState("btactive"), bluez=FakeBluez(player))
    first = a.poll(None)
    assert first is not None
    previous = first.__class__(**{**first.__dict__, "updated_at": 10.0})
    second = a.poll(previous)
    assert second is not None
    assert second.updated_at == 10.0  # interpolation continues from the original time stamp


def test_bluetooth_without_player() -> None:
    a = adapter(FakeState("btactive"), bluez=FakeBluez(None))
    np = a.poll(None)
    assert np is not None
    assert (np.source_label, np.actions) == ("Bluetooth", NO_ACTIONS)
    a.execute(Action.NEXT)  # ignored, must not raise


def test_refresh_notifies_only_on_change() -> None:
    state = FakeState("slactive")
    a = adapter(state)
    calls: list[int] = []
    a._notify = lambda: calls.append(1)
    a.refresh()
    a.refresh()
    assert len(calls) == 1
    state.flags = set()
    a.refresh()
    assert len(calls) == 2
    assert a.now_playing() is None


def test_database_error_is_logged_once(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    state = FakeState("slactive")
    state.error = sqlite3.OperationalError("unable to open database file")
    a = adapter(state)
    a.poll(None)
    a.poll(None)
    assert caplog.text.count("Cannot read moOde database") == 1
    state.error = None
    assert a.poll(None) is not None
    assert "readable again" in caplog.text
