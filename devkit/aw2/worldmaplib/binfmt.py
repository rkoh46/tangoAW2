"""The converted map as one file (art/worldmap/<name>.bin) that tango-gamesupport-aw2's `world_picture.rs` reads. All little endian:

    "PWM1"  u16 width  u16 height  u16 tiles  u8 palettes (9)  u8 classes (6: the sea, then the nations)
    tiles    n * 32 bytes   4bpp as the GBA wants them (low nibble = the left pixel); tile 0 is blank
    cells    (width/8 * height/8) u16, row-major tilemap entries (tile | H flip 0x400 | V flip 0x800 | BG palette (6..14) << 12)
    palette  9 * 16 u16 BGR555, the picture's colours (slot 0 of each is never drawn)
    tinted   9 * 16 u16 BGR555, the same entries as Black Hole's land
    tags     9 * 16 u8: the class each entry draws (0 the sea; a nation's entries are the ones conquest swaps)
    mask     u32 runs, then runs of (u8 class, u16 length) over the pixels row by row: the class of every pixel
    slots    u8 n, then (u8 class, u16 x, u16 y) each: dummy flag places for the development aid
"""
import struct

import numpy as np

from .convert import Map, PAL_COUNT

MAGIC = b"PWM1"


def _bgr(c5):
    c = np.asarray(c5, np.uint16)
    return (c[..., 0] | (c[..., 1] << 5) | (c[..., 2] << 10)).astype("<u2")


def _unbgr(v):
    v = np.asarray(v, np.uint16)
    return np.stack([v & 31, (v >> 5) & 31, (v >> 10) & 31], -1).astype(np.uint8)


def pack(m):
    out = bytearray(MAGIC)
    out += struct.pack("<HHHBB", m.width, m.height, len(m.tiles), PAL_COUNT, len(m.region_names))
    for t in m.tiles:
        for i in range(0, 64, 2):
            out.append(int(t[i]) | (int(t[i + 1]) << 4))
    out += m.cells.astype("<u2").tobytes()
    out += _bgr(m.palette).tobytes()
    out += _bgr(m.tinted).tobytes()
    out += m.tags.astype(np.uint8).tobytes()
    runs = []
    flat = m.mask.reshape(-1)
    start = 0
    for i in range(1, len(flat) + 1):
        if i == len(flat) or flat[i] != flat[start] or i - start == 0xFFFF:
            runs.append((int(flat[start]), i - start))
            start = i
    out += struct.pack("<I", len(runs))
    for v, n in runs:
        out += struct.pack("<BH", v, n)
    out += struct.pack("<B", len(m.slots))
    for r, x, y in m.slots:
        out += struct.pack("<BHH", r, x, y)
    return bytes(out)


def unpack(b, names=None):
    assert b[:4] == MAGIC, "not a PWM1 file"
    w, h, nt, npal, ncls = struct.unpack_from("<HHHBB", b, 4)
    o = 4 + 8
    tiles = np.zeros((nt, 64), np.uint8)
    for t in range(nt):
        for i in range(32):
            v = b[o + 32 * t + i]
            tiles[t, 2 * i] = v & 15
            tiles[t, 2 * i + 1] = v >> 4
    o += 32 * nt
    ncell = (w // 8) * (h // 8)
    cells = np.frombuffer(b, "<u2", ncell, o).reshape(h // 8, w // 8).astype(np.uint16)
    o += 2 * ncell
    palette = _unbgr(np.frombuffer(b, "<u2", npal * 16, o)).reshape(npal, 16, 3)
    o += 2 * npal * 16
    tinted = _unbgr(np.frombuffer(b, "<u2", npal * 16, o)).reshape(npal, 16, 3)
    o += 2 * npal * 16
    tags = np.frombuffer(b, np.uint8, npal * 16, o).reshape(npal, 16).copy()
    o += npal * 16
    (nr,) = struct.unpack_from("<I", b, o)
    o += 4
    flat = []
    for _ in range(nr):
        v, n = struct.unpack_from("<BH", b, o)
        o += 3
        flat.extend([v] * n)
    mask = np.array(flat, np.uint8).reshape(h, w)
    ns = b[o]
    o += 1
    slots = []
    for _ in range(ns):
        r, x, y = struct.unpack_from("<BHH", b, o)
        o += 5
        slots.append((r, x, y))
    assert o == len(b), "trailing bytes"
    return Map("", w, h, names or [str(i) for i in range(ncls)], tiles, cells, palette, tags, tinted, mask, slots)
