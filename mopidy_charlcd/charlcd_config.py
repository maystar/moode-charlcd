from lcd.i2c_pcf8574_interface import PinMapping


class CharlcdConfig:
    def __init__(self, config):
        self.i2c_port = config.get("i2c_port", 0x27)
        self.num_cols = config.get("num_cols", 20)
        self.num_rows = config.get("num_rows", 4)
        self.pin_mapping = (
            PinMapping.MAPPING1
            if config.get("pin_mapping_variant", 2) == 1
            else PinMapping.MAPPING2
        )
