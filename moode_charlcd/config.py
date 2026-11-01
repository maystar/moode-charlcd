"""Loads the TOML configuration (package defaults merged with a user file)."""

from __future__ import annotations

import tomllib
from importlib import resources
from pathlib import Path
from typing import Any

DEFAULT_PATH = Path("/etc/moode-charlcd.toml")


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def default_config() -> dict[str, Any]:
    text = (
        resources.files("moode_charlcd").joinpath("default_config.toml").read_text(encoding="utf-8")
    )
    return tomllib.loads(text)


def load_config(path: Path | None) -> dict[str, Any]:
    """Return the defaults merged with ``path`` (missing file = defaults only).

    The ``buttons.pins`` table is replaced as a whole, so removing a pin from the
    user file disables that button.
    """
    config = default_config()
    if path is None or not path.exists():
        return config
    with path.open("rb") as file:
        user = tomllib.load(file)
    merged = _merge(config, user)
    user_pins = user.get("buttons", {}).get("pins")
    if user_pins is not None:
        merged["buttons"]["pins"] = dict(user_pins)
    return merged
