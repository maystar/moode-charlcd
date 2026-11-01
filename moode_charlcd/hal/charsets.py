"""Character ROM tables of the HD44780 (and compatible) controllers."""

from __future__ import annotations

import unicodedata


def _ascii_range(exclude: str = "") -> dict[str, int]:
    return {chr(c): c for c in range(0x20, 0x7E) if chr(c) not in exclude}


# ROM code A00 (Japanese standard font, the most common variant).
# 0x5C is a Yen sign and 0x7E/0x7F are arrows instead of '\\' and '~'.
A00: dict[str, int] = {
    **_ascii_range(exclude="\\"),
    "¥": 0x5C,
    "→": 0x7E,
    "←": 0x7F,
    "°": 0xDF,
    "ä": 0xE1,
    "ß": 0xE2,
    "µ": 0xE4,
    "ñ": 0xEE,
    "ö": 0xEF,
    "∞": 0xF3,
    "Ω": 0xF4,
    "ü": 0xF5,
    "Σ": 0xF6,
    "π": 0xF7,
    "÷": 0xFD,
}

# ROM code A02 (European font). The upper half follows ISO 8859-1 for the
# letters used here. Untested on real hardware.
A02: dict[str, int] = {
    **_ascii_range(),
    "~": 0x7E,
    **{ch: ord(ch) for ch in "°ÄÖÜßäöüàáâèéêìíîòóôùúûçñÀÁÂÈÉÊÌÍÎÒÓÔÙÚÛÇÑ"},
}

CHARSETS = {"A00": A00, "A02": A02}

# Substitutes for characters missing in a charset, tried in order.
# Every substitute is a single character so the grid layout stays intact.
_SUBSTITUTES = {
    "Ä": "äA",
    "Ö": "öO",
    "Ü": "üU",
    "ß": "s",
    "\\": "/",
    "’": "'",
    "‘": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "–": "-",
    "—": "-",
    "…": ".",
}


def encode(char: str, table: dict[str, int]) -> int:
    """Encode a single ``char`` with ``table``.

    Falls back to a similar character (``Ä`` -> ``ä`` or ``A``, ``é`` -> ``e``)
    and finally to ``?``. Always returns exactly one code.
    """
    if char in table:
        return table[char]
    for substitute in _SUBSTITUTES.get(char, ""):
        if substitute in table:
            return table[substitute]
    base = unicodedata.normalize("NFKD", char)[:1]
    if base in table:
        return table[base]
    return table["?"]
