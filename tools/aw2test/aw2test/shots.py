"""Reading the console's 240x160 pictures (BMP, 24 bit) and the previews' PPMs, and comparing parts of them (no Pillow)."""

import struct


def read_bmp(path):
    """rows of (r, g, b), top row first."""
    with open(path if path.endswith(".bmp") else path + ".bmp", "rb") as f:
        b = f.read()
    off = struct.unpack_from("<I", b, 10)[0]
    w, h = struct.unpack_from("<ii", b, 18)
    bpp = struct.unpack_from("<H", b, 28)[0]
    assert bpp in (24, 32), bpp
    step = bpp // 8
    stride = (w * step + 3) & ~3
    rows = []
    for y in range(abs(h)):
        sy = abs(h) - 1 - y if h > 0 else y
        line = b[off + sy * stride: off + sy * stride + w * step]
        rows.append([(line[i + 2], line[i + 1], line[i]) for i in range(0, w * step, step)])
    return rows


def read_ppm(path):
    with open(path, "rb") as f:
        b = f.read()
    parts = b.split(b"\n", 3)
    w, h = map(int, parts[1].split())
    data = parts[3]
    return [[tuple(data[3 * (y * w + x): 3 * (y * w + x) + 3]) for x in range(w)] for y in range(h)]


def crop(rows, x, y, w, h):
    return [r[x:x + w] for r in rows[y:y + h]]


def close(a, b, tol=8):
    """Whether two crops match to within `tol` a channel (the console's colours are 15 bit)."""
    return all(abs(p[i] - q[i]) <= tol for ra, rb in zip(a, b) for p, q in zip(ra, rb) for i in range(3))


def diff_count(a, b, tol=8):
    return sum(1 for ra, rb in zip(a, b) for p, q in zip(ra, rb) if any(abs(p[i] - q[i]) > tol for i in range(3)))
