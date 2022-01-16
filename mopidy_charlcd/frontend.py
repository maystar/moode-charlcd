import logging
import pykka
from enum import Enum
from mopidy import core

from .charlcd_config import CharlcdConfig
from .display import Display
from .playback_state import PlaybackState

logger = logging.getLogger(__name__)


class CharlcdFrontend(pykka.ThreadingActor, core.CoreListener):
    def __init__(self, config, core):
        super().__init__()
        self.core = core
        self.config = CharlcdConfig(config["charlcd"])
        self.current_track = None
        self.display: Optional[Display] = None

    def on_start(self):
        self.display = Display(self.config)
        self.display.start()
        self.display.update_volume(self.core.mixer.get_volume().get())

    def on_stop(self):
        self.display.stop()
        self.display = None

    def mute_changed(self, mute):
        pass

    def options_changed(self):
        self.display.update_options(
            shuffle=self.core.tracklist.get_random(),
            repeat=self.core.tracklist.get_repeat(),
        )

    def playlist_changed(self, playlist):
        pass

    def playlist_deleted(self, playlist):
        pass

    def playlists_loaded(self):
        pass

    def seeked(self, time_position):
        self.update_elapsed(time_position)

    def stream_title_changed(self, title):
        logger.info("stream_title_changed: %s %s", title, type(title))
        self.update_track(title)

    def track_playback_ended(self, tl_track, time_position):
        self.update_elapsed(time_position)
        self.display.update_state(PlaybackState.STOP)
        self.display.update_track("", "", "")

    def track_playback_paused(self, tl_track, time_position):
        self.update_elapsed(time_position)
        self.display.update_state(PlaybackState.PAUSE)

    def track_playback_resumed(self, tl_track, time_position):
        self.update_elapsed(time_position)
        self.display.update_state(PlaybackState.PLAY)

    def track_playback_started(self, tl_track):
        self.update_track(tl_track.track, 0)
        self.display.update_state(PlaybackState.PLAY)

    def update_elapsed(self, time_position):
        self.display.update_elapsed(float(time_position))

    def update_track(self, track, time_position=None):
        if track is None:
            track = self.core.playback.get_current_track().get()

        title = track.name if track.name is not None else ""
        album = (
            track.album.name
            if track.album is not None and track.album.name is not None
            else ""
        )
        artist = (
            ", ".join([artist.name for artist in track.artists])
            if track.artists is not None
            else ""
        )

        self.display.update_track(title=title, album=album, artist=artist)

        if time_position is not None:
            length = track.length
            # Default to 60s long and loop the transport bar
            if length is None:
                length = 60
                time_position %= length

            self.display.update_elapsed(
                elapsed=float(time_position), length=float(length)
            )

    def tracklist_changed(self):
        pass

    def volume_changed(self, volume):
        if volume is None:
            return

        self.display.update_volume(volume)
