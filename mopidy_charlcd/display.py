import logging
import threading
import time

import board
import busio
from lcd.i2c_pcf8574_interface import I2CPCF8574Interface
from lcd.lcd import LCD

from .charlcd_config import CharlcdConfig
from .playback_state import PlaybackState
from .symbols import Symbols

logger = logging.getLogger(__name__)

PLAY = 0
PAUSE = 1
FORWARD = 2
BACKWARD = 3
QUIT = 4
SHUFFLE = 5
CONSUME = 6
PLAYING = 7
REPEAT = 0xF3
SPACE = 0x20


class TrackTime:
    def __init__(self, milliseconds: float):
        all_seconds = milliseconds / 1000
        self.minutes = all_seconds // 60
        self.seconds = all_seconds % 60

    def __str__(self):
        return "{0:02.0f}:{1:02.0f}".format(self.minutes, self.seconds)


class PlaybackOptions:
    def __init__(self, repeat: bool = False, random: bool = False, consume: bool = False):
        self.repeat = repeat
        self.random = random
        self.consume = consume


class Display:
    def __init__(self, config: CharlcdConfig):
        self.config = config
        comm_port = busio.I2C(board.SCL, board.SDA)
        interface = I2CPCF8574Interface(
            comm_port, config.i2c_port, config.pin_mapping
        )
        self.display = LCD(
            interface, num_cols=config.num_cols, num_rows=config.num_rows
        )
        self.prog_playback_symbols()
        self.display.clear()

        self._running = threading.Event()
        self._delay = 1.0 / 30
        self._thread = None

        self.state = PlaybackState.STOP
        self.volume = 100
        self.progress = 0
        self.elapsed = 0
        self.length = 0

        self.title = ""
        self.album = ""
        self.artist = ""
        self._last_progress_update = time.time()
        self._last_progress_value = 0
        self._last_state_change = 0
        self._last_art = ""
        self._last_elapsed_update = time.time()
        self._last_elapsed_value = 0
        self.options = PlaybackOptions()

    def start(self):
        if self._thread is not None:
            return

        self._running = threading.Event()
        self._running.set()
        self._thread = threading.Thread(target=self._loop)
        self._thread.start()

    def stop(self):
        self._running.clear()
        self._thread.join()
        self._thread = None

        self.display.clear()
        self.display.set_cursor_pos(1, 0)
        self.display.print("Und tschüss!")

    def stop_playback(self):
        self.update_state(PlaybackState.STOP)
        self.update_track("", "", "")
        self.update_elapsed(0)

    def pause_playback(self):
        self.update_state(PlaybackState.PAUSE)

    def start_playback(self):
        self.update_state(PlaybackState.PLAY)

    def update_state(self, state: PlaybackState):
        self._last_state_change = time.time()
        self.state = state

    def update_volume(self, volume: int):
        self.volume = volume

    def update_options(self, random: bool, repeat: bool, consume: bool):
        self.options = PlaybackOptions(repeat=repeat, random=random, consume=consume)

    def update_track(self, title: str, album: str = None, artist: str = None):
        self.title = title
        self.artist = artist
        self.album = album

    def update_elapsed(self, elapsed: float, length: float = None):
        self.elapsed = elapsed
        if length:
            self.length = length
            self.progress = float(elapsed) / float(length)
        self._last_elapsed_update = time.time()
        self._last_elapsed_value = elapsed

    def _loop(self):
        while self._running.is_set():
            if self.state == PlaybackState.PLAY:
                t_elapsed_ms = (time.time() - self._last_elapsed_update) * 1000
                self.elapsed = float(self._last_elapsed_value + t_elapsed_ms)
                self.progress = self.elapsed / self.length
            self.print_to_display()
            time.sleep(self._delay)

    def print_to_display(self):
        self.print_button_info(0)
        self.print_progress(0)
        self.print_track_info(1, 2, 3)
        self.print_day_time(3)

    def print_button_info(self, row: int):
        self.display.set_cursor_pos(row, 0)
        if self.state == PlaybackState.PLAY:
            self.display.write(PAUSE)
        else:
            self.display.write(PLAY)
        self.display.print("|")
        self.display.write(BACKWARD)
        self.display.print("|")
        self.display.write(FORWARD)
        self.display.print("|")
        self.display.write(QUIT)

    def print_progress(self, row: int):
        elapsed = TrackTime(self.elapsed)
        progress = f"{elapsed}"
        t = progress if self.elapsed else "{0:>{1}}".format(" ", len(progress))
        self.print_row(row, t, margin_left=self.config.num_cols - len(progress))

        repeat_symbol = REPEAT if self.options.repeat else SPACE
        random_symbol = SHUFFLE if self.options.random else SPACE
        consume_symbol = CONSUME if self.options.consume else SPACE
        playing_symbol = PLAYING if self.state == PlaybackState.PLAY else SPACE
        self.display.set_cursor_pos(row, self.config.num_cols - len(progress) - 5)
        self.display.write(repeat_symbol)
        self.display.write(random_symbol)
        self.display.write(consume_symbol)
        self.display.write(SPACE)
        self.display.write(playing_symbol)

    def print_track_info(self, row_title: int, row_artist: int, row_album):
        self.print_row(row_title, self.title)
        self.print_row(row_artist, self.artist)
        self.print_row(row_album, self.album, margin_right=6)

    def print_day_time(self, row):
        localtime = time.localtime()
        result = time.strftime("%H:%M", localtime)
        self.print_row(
            row, result, margin_left=self.config.num_cols - len(result)
        )

    def print_row(
            self, row: int, text: str, margin_left: int = 0, margin_right: int = 0
    ):
        max_length = self.config.num_cols - margin_left - margin_right
        truncated_text = text if len(text) <= max_length else text[:max_length]
        aligned_text = "{0:<{1}}".format(truncated_text, max_length)
        self.display.set_cursor_pos(row, margin_left)
        self.display.print(aligned_text)

    def prog_playback_symbols(self):
        self.display.create_char(PLAY, Symbols.play)
        self.display.create_char(PAUSE, Symbols.pause)
        self.display.create_char(FORWARD, Symbols.forward)
        self.display.create_char(BACKWARD, Symbols.backward)
        self.display.create_char(QUIT, Symbols.quit)
        self.display.create_char(SHUFFLE, Symbols.shuffle)
        self.display.create_char(CONSUME, Symbols.consume)
        self.display.create_char(PLAYING, Symbols.playing)
