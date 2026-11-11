"""make_blank_figure.py <toy id> <variant> <out .dump> [<serial hex, 8 digits>]: a new, empty figure file, as
skylanders-portal's CreateBlankFigure makes it (src/portal/figure_file.cpp): the serial and its check byte, the
manufacturer bytes, the toy id and variant with their CRC, and the sector trailers' access bits; everything else
zero, as a toy fresh out of the box. For the 3DS portal experiments (SKYLANDERS_PORTAL_FIGURE), so no one's own
figure is needed. Stdlib only."""
import pathlib
import sys

toy_id = int(sys.argv[1], 0)
variant = int(sys.argv[2], 0)
out = pathlib.Path(sys.argv[3])
serial = bytes.fromhex(sys.argv[4]) if len(sys.argv) > 4 else bytes.fromhex("1a2b3c4d")
assert len(serial) == 4


def crc16_ccitt(data, crc=0xFFFF):
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


data = bytearray(1024)
data[0:4] = serial
data[4] = serial[0] ^ serial[1] ^ serial[2] ^ serial[3]
data[5:8] = bytes([0x81, 0x01, 0x0F])
data[0x10:0x12] = toy_id.to_bytes(2, "little")
data[0x1C:0x1E] = variant.to_bytes(2, "little")
data[0x1E:0x20] = crc16_ccitt(data[:0x1E]).to_bytes(2, "little")
for sector in range(16):
    offset = sector * 0x40 + 0x36
    data[offset:offset + 4] = bytes([0x0F, 0x0F, 0x0F, 0x69]) if sector == 0 else bytes([0x7F, 0x0F, 0x08, 0x69])
out.write_bytes(bytes(data))
print(f"{out}: toy {toy_id}, variant {variant:#06x}, serial {serial.hex()}")
