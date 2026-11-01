import pytest

from moode_charlcd.hal.charsets import A00, A02, encode


@pytest.mark.parametrize(
    ("char", "code"),
    [
        ("A", 0x41),
        ("z", 0x7A),
        ("ä", 0xE1),
        ("ö", 0xEF),
        ("ü", 0xF5),
        ("ß", 0xE2),
        ("°", 0xDF),
        ("Ä", 0xE1),  # no capital umlauts in A00, use the small one
        ("é", ord("e")),  # accents are stripped
        ("\\", ord("/")),  # 0x5C is a Yen sign in A00
        ("…", ord(".")),
        ("☃", ord("?")),
    ],
)
def test_a00(char: str, code: int) -> None:
    assert encode(char, A00) == code


@pytest.mark.parametrize(("char", "code"), [("Ä", 0xC4), ("é", 0xE9), ("~", 0x7E)])
def test_a02(char: str, code: int) -> None:
    assert encode(char, A02) == code


def test_every_char_is_exactly_one_code() -> None:
    for char in "Und tschüss! Größe Ärger “quoted” — ok…":
        assert isinstance(encode(char, A00), int)
