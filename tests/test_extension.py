from moode_charlcd import Extension


def test_get_default_config():
    ext = Extension()

    config = ext.get_default_config()

    assert "[charlcd]" in config
    assert "enabled = true" in config


def test_get_config_schema():
    ext = Extension()

    schema = ext.get_config_schema()

    assert "i2c_port" in schema
    assert "pin_mapping_variant" in schema
    assert "num_cols" in schema
    assert "num_rows" in schema
