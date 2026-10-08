"""A minimal PNG writer for the tests' pictures (no Pillow)."""

import struct
import zlib


def write(path, rows, scale=1):
    """rows: lists of (r, g, b) 0..255."""
    h, w = len(rows), len(rows[0])
    raw = b""
    for r in rows:
        line = b"".join(bytes(px) for px in r for _ in range(scale))
        raw += (b"\0" + line) * scale

    def chunk(t, d):
        c = struct.pack(">I", len(d)) + t + d
        return c + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)

    with open(path, "wb") as f:
        f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w * scale, h * scale, 8, 2, 0, 0, 0))
                + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))
