from datetime import datetime

import pytest

from moode_charlcd.model import ALL_ACTIONS, NO_ACTIONS, Action, NowPlaying, PlaybackState, idle
from moode_charlcd.ui.frame import FrameBuilder, frame_to_text
from moode_charlcd.ui.layout import StandardLayout, format_time

from .conftest import mpd_playing

CLOCK = datetime(2026, 11, 1, 12, 34)
NOW = 100.0


def render(np: NowPlaying, cols: int = 20, rows: int = 4, legend: bool = True) -> list[str]:
    layout = StandardLayout(cols, rows, show_legend=legend)
    return frame_to_text(layout.render(np, CLOCK, NOW))


@pytest.mark.parametrize(
    ("seconds", "text"), [(0, "00:00"), (83.9, "01:23"), (600, "10:00"), (3725, "1:02:05")]
)
def test_format_time(seconds: float, text: str) -> None:
    assert format_time(seconds) == text


def test_mpd_playing_matches_mopidy_layout() -> None:
    np = mpd_playing(repeat=True, random=True, consume=True)
    assert render(np) == [
        "⏸|⏮|⏭|⏻   ∞⤨© ►01:23",
        "Gasoline            ",
        "Audioslave          ",
        "Audioslave     12:34",
    ]


def test_mpd_paused_shows_play_symbol_and_no_playing_indicator() -> None:
    np = mpd_playing(state=PlaybackState.PAUSE)
    assert render(np)[0] == "▶|⏮|⏭|⏻        01:23"


def test_mpd_stopped_shows_only_legend_and_clock() -> None:
    np = mpd_playing(state=PlaybackState.STOP, elapsed=None)
    assert render(np) == [
        "▶|⏮|⏭|⏻             ",
        "                    ",
        "                    ",
        "               12:34",
    ]


def test_long_text_is_truncated_and_album_leaves_room_for_clock() -> None:
    np = mpd_playing(title="A very long title that does not fit", album="An album name too long")
    lines = render(np)
    assert lines[1] == "A very long title th"
    assert lines[3] == "An album name  12:34"


def test_unsupported_actions_are_blank_in_legend() -> None:
    np = mpd_playing(actions=frozenset({Action.PLAY_PAUSE}))
    assert render(np)[0].startswith("⏸| | |⏻")


def test_without_buttons_the_source_label_replaces_the_legend() -> None:
    assert render(mpd_playing(), legend=False)[0] == "MPD           ►01:23"


def test_renderer_without_controls_shows_label() -> None:
    np = NowPlaying(
        source="spotify",
        source_label="Spotify",
        state=PlaybackState.PLAY,
        title="Song",
        artist="Band",
        album="",
        actions=NO_ACTIONS,
    )
    assert render(np) == [
        "Spotify       ►     ",
        "Song                ",
        "Band                ",
        "               12:34",
    ]


def test_renderer_without_metadata_shows_label() -> None:
    np = NowPlaying(source="squeezelite", source_label="Squeezelite", state=PlaybackState.PLAY)
    assert render(np)[0].startswith("Squeezelite")
    assert render(np)[1].strip() == ""


def test_bluetooth_with_controls_shows_label_in_album_row() -> None:
    np = NowPlaying(
        source="bluetooth",
        source_label="Bluetooth",
        state=PlaybackState.PLAY,
        title="Song",
        artist="Band",
        elapsed=5.0,
        updated_at=NOW,
        actions=ALL_ACTIONS,
    )
    assert render(np) == [
        "⏸|⏮|⏭|⏻       ►00:05",
        "Song                ",
        "Band                ",
        "Bluetooth      12:34",
    ]


def test_offline() -> None:
    assert render(idle("MPD offline"))[0] == "MPD offline         "


def test_16x2_drops_indicators_and_clock() -> None:
    np = mpd_playing(repeat=True)
    assert render(np, cols=16, rows=2) == ["⏸|⏮|⏭|⏻   ►01:23", "Gasoline        "]


def test_message_is_centered() -> None:
    frame = StandardLayout(20, 4).message("Und tschüss!")
    assert frame_to_text(frame)[1] == "    Und tschüss!    "


def test_frame_builder_ignores_out_of_range() -> None:
    builder = FrameBuilder(4, 1).text(5, 0, "x").text(0, 9, "x").symbol(3, 3, None)
    assert frame_to_text(builder.build()) == ["    "]


def test_frame_builder_alignment() -> None:
    builder = FrameBuilder(6, 2).text(0, 0, "ab", align="right").text(1, 0, "ab", align="center")
    assert frame_to_text(builder.build()) == ["    ab", "  ab  "]
