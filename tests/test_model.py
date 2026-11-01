from moode_charlcd.model import NowPlaying, PlaybackState, idle

from .conftest import mpd_playing


def test_elapsed_is_interpolated_while_playing() -> None:
    np = mpd_playing(elapsed=10.0, updated_at=100.0)
    assert np.elapsed_at(105.5) == 15.5


def test_elapsed_does_not_exceed_duration() -> None:
    np = mpd_playing(elapsed=278.0, duration=280.0, updated_at=100.0)
    assert np.elapsed_at(110.0) == 280.0


def test_elapsed_is_frozen_while_paused() -> None:
    np = mpd_playing(state=PlaybackState.PAUSE, elapsed=10.0, updated_at=100.0)
    assert np.elapsed_at(200.0) == 10.0


def test_elapsed_unknown() -> None:
    assert idle("x").elapsed_at(1.0) is None


def test_same_content_ignores_timestamp() -> None:
    a = mpd_playing(updated_at=1.0)
    b = mpd_playing(updated_at=2.0)
    assert a.same_content(b)
    assert not a.same_content(mpd_playing(title="Other"))
    assert not a.same_content(None)


def test_idle() -> None:
    np = idle("MPD offline")
    assert np == NowPlaying(source="none", source_label="MPD offline", updated_at=np.updated_at)
