import logging

from jproperties import Properties

from moode_charlcd.charlcd_config import CharlcdConfig
from moode_charlcd.current_song import CurrentSong
from moode_charlcd.display import Display

logger = logging.getLogger(__name__)


class LcdTextReader:

    def __init__(self, config_file: str = 'config.prop'):
        self.display = None
        self.current_song = None

        configs = Properties()
        with open(config_file, 'rb') as config_file:
            configs.load(config_file)
        self.config = CharlcdConfig(configs)

    def read_file(self):
        current_song_props = Properties()
        with open(self.config.input_file, 'rb') as current_song_file:
            current_song_props.load(current_song_file)
        self.current_song = CurrentSong(current_song_props)
        logger.info(f'{self.current_song}')

    def init_display(self):
        self.display = Display(self.config)
        self.display.start()
        self.display.update_volume(self.core.mixer.get_volume().get())


def main():
    reader = LcdTextReader('config.prop')
    reader.read_file()


if __name__ == '__main__':
    main()
