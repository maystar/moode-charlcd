from jproperties import Properties
from lcd.pin_mapping import PinMapping


class CharlcdConfig:
    def __init__(self, config: Properties):
        self.i2c_port = config.get("i2c_port", 0x27).data
        self.num_cols = config.get("num_cols", 20).data
        self.num_rows = config.get("num_rows", 4).data
        self.input_file = config.get("input_file", "/var/local/www/currentsong.txt").data
        self.pin_mapping = (
            PinMapping.MAPPING1
            if config.get("pin_mapping_variant", 2).data == 1
            else PinMapping.MAPPING2
        )
