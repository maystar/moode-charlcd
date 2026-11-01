from __future__ import annotations

import json
import subprocess
from collections.abc import Sequence

from moode_charlcd.model import Action
from moode_charlcd.sources.bluez import BluezClient, BluezPlayer, parse_players, unwrap

PLAYER_PATH = "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF/player0"


def busctl_output(status: str = "playing", position: int = 12345) -> str:
    """Output of ``busctl --json=short call ... GetManagedObjects`` (shape as documented)."""
    return json.dumps(
        {
            "type": "a{oa{sa{sv}}}",
            "data": [
                {
                    "/org/bluez/hci0": {
                        "org.bluez.Adapter1": {"Powered": {"type": "b", "data": True}}
                    },
                    PLAYER_PATH: {
                        "org.bluez.MediaPlayer1": {
                            "Status": {"type": "s", "data": status},
                            "Position": {"type": "u", "data": position},
                            "Track": {
                                "type": "a{sv}",
                                "data": {
                                    "Title": {"type": "s", "data": "Song"},
                                    "Artist": {"type": "s", "data": "Band"},
                                    "Album": {"type": "s", "data": "Record"},
                                    "Duration": {"type": "u", "data": 200000},
                                },
                            },
                        }
                    },
                }
            ],
        }
    )


def test_unwrap_nested_variants() -> None:
    assert unwrap({"type": "a{sv}", "data": {"x": {"type": "u", "data": 1}}}) == {"x": 1}
    assert unwrap([{"type": "s", "data": "a"}]) == ["a"]


def test_parse_players() -> None:
    assert parse_players(busctl_output()) == [
        BluezPlayer(
            path=PLAYER_PATH,
            status="playing",
            title="Song",
            artist="Band",
            album="Record",
            position_ms=12345,
            duration_ms=200000,
        )
    ]


def test_parse_players_without_player() -> None:
    assert parse_players(json.dumps({"type": "a{oa{sa{sv}}}", "data": [{}]})) == []


class Runner:
    def __init__(self, output: str = "", error: Exception | None = None) -> None:
        self.output = output
        self.error = error
        self.calls: list[list[str]] = []

    def __call__(self, args: Sequence[str]) -> str:
        self.calls.append(list(args))
        if self.error:
            raise self.error
        return self.output


def test_current_player() -> None:
    runner = Runner(busctl_output())
    player = BluezClient(runner).current_player()
    assert player is not None
    assert player.title == "Song"
    assert runner.calls[0][-1] == "GetManagedObjects"


def test_current_player_handles_busctl_errors() -> None:
    error = subprocess.CalledProcessError(1, "busctl")
    assert BluezClient(Runner(error=error)).current_player() is None
    assert BluezClient(Runner("not json")).current_player() is None


def test_execute_toggles_play_pause() -> None:
    runner = Runner()
    client = BluezClient(runner)
    client.execute(BluezPlayer(PLAYER_PATH, "playing"), Action.PLAY_PAUSE)
    client.execute(BluezPlayer(PLAYER_PATH, "paused"), Action.PLAY_PAUSE)
    client.execute(BluezPlayer(PLAYER_PATH, "playing"), Action.NEXT)
    assert [call[-1] for call in runner.calls] == ["Pause", "Play", "Next"]
    assert runner.calls[0][:4] == ["call", "org.bluez", PLAYER_PATH, "org.bluez.MediaPlayer1"]
