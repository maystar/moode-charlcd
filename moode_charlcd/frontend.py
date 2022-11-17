import logging
from typing import Optional

import pykka
from moode import core

from .charlcd_config import CharlcdConfig
from .display import Display

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
        self.options_changed()

    def on_stop(self):
        self.display.stop()
        self.display = None

    def mute_changed(self, mute):
        pass

    def options_changed(self):
        self.display.update_options(
            random=self.core.tracklist.get_random().get(),
            repeat=self.core.tracklist.get_repeat().get(),
            consume=self.core.tracklist.get_consume().get(),
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
        self.update_track(title)

    def track_playback_ended(self, tl_track, time_position):
        self.update_elapsed(time_position)
        self.display.stop_playback()

    def track_playback_paused(self, tl_track, time_position):
        self.update_elapsed(time_position)

    def track_playback_resumed(self, tl_track, time_position):
        self.update_elapsed(time_position)

    def track_playback_started(self, tl_track):
        self.update_track(tl_track.track, 0)

    def playback_state_changed(self, old_state, new_state):
        if new_state == "stopped":
            self.display.stop_playback()
        elif new_state == "playing":
            self.display.start_playback()
        elif new_state == "paused":
            self.display.pause_playback()
        else:
            logger.info(f"Change playback state to unhandled state {new_state}")

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
