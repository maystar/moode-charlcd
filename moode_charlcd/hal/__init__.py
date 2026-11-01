"""Hardware abstraction layer for character displays.

A new display type only needs a :class:`~moode_charlcd.hal.base.CharacterDisplay`
implementation and an entry in :mod:`moode_charlcd.hal.factory`.
"""

from .base import CharacterDisplay

__all__ = ["CharacterDisplay"]
