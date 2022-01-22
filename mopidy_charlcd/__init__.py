import pathlib

import pkg_resources
from mopidy import config, ext

__version__ = pkg_resources.get_distribution("Mopidy-Charlcd").version


class HexInteger(config.Integer):
    def __init__(
        self, minimum=None, maximum=None, choices=None, optional=False
    ):
        super().__init__(minimum, maximum, choices, optional)

    def deserialize(self, value):
        int_value = int(value, 16) if value else value
        return super().deserialize(str(int_value))


class Extension(ext.Extension):
    dist_name = "Mopidy-Charlcd"
    ext_name = "charlcd"
    version = __version__

    def get_default_config(self):
        return config.read(pathlib.Path(__file__).parent / "ext.conf")

    def get_config_schema(self):
        schema = super().get_config_schema()
        schema["i2c_port"] = HexInteger(minimum=0)
        schema["num_cols"] = config.Integer(minimum=1)
        schema["num_rows"] = config.Integer(minimum=1)
        schema["pin_mapping_variant"] = config.Integer(choices=[1, 2])
        return schema

    def setup(self, registry):
        from .frontend import CharlcdFrontend

        registry.add("frontend", CharlcdFrontend)
