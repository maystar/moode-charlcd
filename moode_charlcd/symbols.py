class Symbols:
    play = bytearray(
        [0b11111, 0b10111, 0b10011, 0b10001, 0b10011, 0b10111, 0b11111, 0b00000]
    )
    pause = bytearray(
        [0b11111, 0b10101, 0b10101, 0b10101, 0b10101, 0b10101, 0b11111, 0b00000]
    )
    forward = bytearray(
        [0b11111, 0b10111, 0b11011, 0b11101, 0b11011, 0b10111, 0b11111, 0b00000]
    )
    backward = bytearray(
        [0b11111, 0b11101, 0b11011, 0b10111, 0b11011, 0b11101, 0b11111, 0b00000]
    )
    quit = bytearray(
        [0b11111, 0b01110, 0b10101, 0b11011, 0b10101, 0b01110, 0b11111, 0b00000]
    )
    shuffle = bytearray(
        [0b00000, 0b00000, 0b10001, 0b01010, 0b00100, 0b01010, 0b10001, 0b00000]
    )
    consume = bytearray(
        [0b00000, 0b00000, 0b01110, 0b10010, 0b10100, 0b10010, 0b01110, 0b00000]
    )
    playing = bytearray(
        [
            0b00000,
            0b00000,
            0b01000,
            0b01100,
            0b01110,
            0b01100,
            0b01000,
            0b00000,
        ]
    )