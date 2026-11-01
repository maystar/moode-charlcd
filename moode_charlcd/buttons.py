"""Hardware buttons on GPIO pins."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from typing import Any, Protocol

from .model import Action

logger = logging.getLogger(__name__)


class Button(Protocol):
    when_pressed: Callable[[], None] | None

    def close(self) -> None: ...


ButtonFactory = Callable[[int, float], Button]


def _gpiozero_button(pin: int, bounce_time: float) -> Button:
    from gpiozero import Button as GpioButton  # only available on the Pi

    button: Button = GpioButton(pin, pull_up=True, bounce_time=bounce_time)
    return button


def parse_pins(pins: Mapping[str, Any]) -> dict[Action, int]:
    """Map the ``[buttons.pins]`` config section to actions."""
    result = {}
    for name, pin in pins.items():
        try:
            action = Action(name)
        except ValueError:
            raise ValueError(
                f"unknown button action {name!r}, use one of {[a.value for a in Action]}"
            ) from None
        result[action] = int(pin)
    return result


class GpioButtons:
    """Calls ``handler(action)`` when a button is pressed (pin pulled to GND)."""

    def __init__(
        self,
        pins: Mapping[Action, int],
        handler: Callable[[Action], None],
        bounce_ms: int = 250,
        button_factory: ButtonFactory = _gpiozero_button,
    ) -> None:
        self._buttons: list[Button] = []
        for action, pin in pins.items():
            button = button_factory(pin, bounce_ms / 1000)
            button.when_pressed = self._callback(handler, action)
            self._buttons.append(button)
            logger.info("Button on GPIO%d: %s", pin, action.value)

    @staticmethod
    def _callback(handler: Callable[[Action], None], action: Action) -> Callable[[], None]:
        def pressed() -> None:
            try:
                handler(action)
            except Exception:
                logger.exception("Button action %s failed", action.value)

        return pressed

    def close(self) -> None:
        for button in self._buttons:
            button.close()
        self._buttons.clear()
