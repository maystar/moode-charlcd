import logging

import board
import busio
from lcd.i2c_pcf8574_interface import I2CPCF8574Interface
from lcd.lcd import LCD

from .charlcd_config import CharlcdConfig
from .current_song import CurrentSong
from .playback_state import PlaybackState
from .symbols import Symbols

logger = logging.getLogger(__name__)

PLAY = 0
PAUSE = 1
FORWARD = 2
BACKWARD = 3
QUIT = 4
SPACE = 0x20


class Display:
    def __init__(self, config: CharlcdConfig, current_song: CurrentSong):
        self.artist = None
        self.album = None
        self.title = None
        self.volume = None
        self.state = None

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

        self.update_current_song(current_song)

        self.print_to_display()

    def update_current_song(self, current_song):
        self.state = PlaybackState.PLAY if current_song.state == "play" \
            else PlaybackState.PAUSE if current_song.state == "pause" \
            else PlaybackState.STOP
        self.volume = current_song.volume
        self.title = current_song.title
        self.album = current_song.album
        self.artist = current_song.artist

    def stop(self):
        self.display.clear()
        self.display.set_cursor_pos(1, 0)
        self.display.print("Und tschüss!")

    def print_to_display(self):
        self.print_button_info(0)
        self.print_track_info(1, 2, 3)

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

    def print_track_info(self, row_title: int, row_artist: int, row_album):
        self.print_row(row_title, self.title)
        self.print_row(row_artist, self.artist)
        self.print_row(row_album, self.album, margin_right=0)

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
