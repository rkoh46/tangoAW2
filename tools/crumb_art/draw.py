"""Crumb's original art: drawn here with a few shape helpers, written to
tango-gamesupport-aw2/art/crumb/<version>/*.png (indexed PNGs, 16 colours, 0
transparent). Original tangoAW2 art (not from any game's files).

    python3 tools/crumb_art/draw.py [out_dir]

Pieces per version: body.png (128x160, the CO page, power and tag screens),
face_normal / face_happy / face_sad .png (48x48), mini.png (32x24), hud.png
(32x16). One palette for all of them (the game gives a CO one 16-colour
palette).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

# --- The palette: 15 colours and transparency -----------------------------------
PAL = [
    (0, 0, 0),         # 0 transparent
    (26, 18, 34),      # 1 outline
    (50, 42, 78),      # 2 helmet shade
    (82, 72, 118),     # 3 helmet
    (124, 114, 162),   # 4 helmet light
    (62, 60, 80),      # 5 uniform shade
    (100, 98, 122),    # 6 uniform
    (146, 144, 168),   # 7 uniform light
    (240, 190, 148),   # 8 skin
    (196, 138, 108),   # 9 skin shade
    (214, 44, 52),     # 10 lens red
    (132, 22, 40),     # 11 lens dark
    (150, 70, 190),    # 12 flag purple
    (236, 200, 128),   # 13 biscuit / gold
    (170, 124, 72),    # 14 biscuit shade / pole
    (250, 250, 250),   # 15 white
]
OUT, HS, H, HL, US, U, UL, SK, SKS, LR, LD, FP, BG, BS, WH = range(1, 16)


def q5(c):
    return tuple((v >> 3) << 3 | (v >> 5) for v in c)


class Pen:
    """ImageDraw whose every call draws 255 (a mask), whatever fill it is given."""

    def __init__(self, d):
        self.d = d

    def __getattr__(self, name):
        f = getattr(self.d, name)

        def call(*a, **k):
            k["fill"] = 255
            return f(*a, **k)
        return call


class Canvas:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.a = np.zeros((h, w), np.uint8)

    def mask(self, fn):
        m = Image.new("L", (self.w, self.h), 0)
        fn(Pen(ImageDraw.Draw(m)))
        return np.array(m) > 127

    @staticmethod
    def shift(m, dx, dy):
        """shifted[y, x] = m[y - dy, x - dx] (zero filled)."""
        out = np.zeros_like(m)
        h, w = m.shape
        ys, yd = (slice(0, h - dy), slice(dy, h)) if dy >= 0 else (slice(-dy, h), slice(0, h + dy))
        xs, xd = (slice(0, w - dx), slice(dx, w)) if dx >= 0 else (slice(-dx, w), slice(0, w + dx))
        out[yd, xd] = m[ys, xs]
        return out

    def dilate(self, m):
        return m | self.shift(m, 1, 0) | self.shift(m, -1, 0) | self.shift(m, 0, 1) | self.shift(m, 0, -1)

    def part(self, fn, base, shade=None, light=None, sh=(3, 3), hl=(2, 2), outline=True, clip=None, m=None):
        """A shape: outline, fill, a shaded rim bottom right, a lit rim top left."""
        m = self.mask(fn) if m is None else m
        if clip is not None:
            m = m & clip
        if outline:
            self.a[self.dilate(m) & ~m] = OUT
        self.a[m] = base
        if shade:
            self.a[m & ~self.shift(m, -sh[0], -sh[1])] = shade
        if light:
            lit = m & ~self.shift(m, hl[0], hl[1]) & ~(m & ~self.shift(m, -sh[0], -sh[1]))
            self.a[lit] = light
        return m

    def paint(self, fn, c, clip=None):
        m = self.mask(fn)
        if clip is not None:
            m = m & clip
        self.a[m] = c
        return m

    def clean(self):
        """No stray pixels: an opaque pixel with no opaque 4-neighbour goes."""
        o = self.a != 0
        n = self.shift(o, 1, 0).astype(int) + self.shift(o, -1, 0) + self.shift(o, 0, 1) + self.shift(o, 0, -1)
        self.a[o & (n == 0)] = 0
        # a transparent pixel with three or four opaque neighbours is filled
        o = self.a != 0
        n = self.shift(o, 1, 0).astype(int) + self.shift(o, -1, 0) + self.shift(o, 0, 1) + self.shift(o, 0, -1)
        hole = ~o & (n >= 3)
        self.a[hole] = OUT

    def image(self):
        im = Image.fromarray(self.a, "P")
        flat = []
        for c in PAL:
            flat += list(q5(c))
        im.putpalette(flat + [0] * (768 - len(flat)))
        return im


def save_png(c, path):
    im = c.image()
    im.info["transparency"] = 0
    im.save(path, transparency=0, optimize=True, bits=4) if False else im.save(path, transparency=0)


def rgba(c, bg=None):
    im = c.image().convert("RGBA")
    px = im.load()
    for y in range(c.h):
        for x in range(c.w):
            if c.a[y, x] == 0:
                px[x, y] = (0, 0, 0, 0) if bg is None else bg + (255,)
    return im


# --- The head ---------------------------------------------------------------------

def head(c, cx, cy, s, expr="normal", look=0.0):
    """Crumb's head, its dome centred at (cx, cy), `s` pixels to a unit
    (1.0: the body's, the helmet about 72 wide). Black Hole's trooper: a
    dark helmet a size too big, a gas mask with one round red lens."""
    def P(*pts):
        return [(cx + s * x, cy + s * y) for x, y in pts]

    def E(x, y, rx, ry):
        return (cx + s * (x - rx), cy + s * (y - ry), cx + s * (x + rx), cy + s * (y + ry))

    lx = look * 2  # the lens looks a little to a side
    ly = 24
    # the face: skin, blushing cheeks
    c.part(lambda d: d.rounded_rectangle((cx + s * -27, cy + s * -4, cx + s * 27, cy + s * 47), radius=s * 11, fill=255), SK, SKS, None, sh=(3, 3))
    for sign in (-1, 1):
        c.paint(lambda d, sign=sign: d.ellipse(E(sign * 21, 36, 3.2, 2.2), fill=255), SKS)
    # straps from the mask to the ears
    for sign in (-1, 1):
        c.paint(lambda d, sign=sign: [d.line(P((sign * 20, 27), (sign * 31, 22)), fill=OUT, width=max(1, round(2 * s)))], US)
    # the mask: a snout under the lens
    mask_poly = P((-21, 21), (21, 21), (23, 34), (15, 48), (0, 55), (-15, 48), (-23, 34))
    c.part(lambda d: d.polygon(mask_poly), U, US, UL, sh=(3, 3), hl=(2, 2))
    # filter canister
    c.part(lambda d: d.ellipse(E(0, 46, 6.5, 6), fill=255), US, OUT, UL, sh=(2, 2), hl=(1, 1))
    c.paint(lambda d: [d.line(P((-3, 45), (3, 45)), fill=OUT), d.line(P((-3, 48), (3, 48)), fill=OUT)], OUT)
    # the mouth: vents; the expression in their curve
    if expr == "happy":
        c.paint(lambda d: d.arc(E(0, 36, 11, 6), 20, 160, fill=OUT, width=max(1, round(s))), OUT)
    elif expr == "sad":
        c.paint(lambda d: d.arc(E(0, 45, 11, 6), 200, 340, fill=OUT, width=max(1, round(s))), OUT)
    else:
        c.paint(lambda d: [d.line(P((-9, 38), (9, 38)), fill=OUT), d.line(P((-8, 41), (8, 41)), fill=OUT)], OUT)
    # the lens: big, both eyes behind it, one round red eye
    lens = c.part(lambda d: d.ellipse(E(lx, ly, 14, 12.5), fill=255), UL, U, WH, sh=(2, 2), hl=(1, 1))
    inner = c.mask(lambda d: d.ellipse(E(lx, ly, 10.2, 9), fill=255))
    c.part(None, LR, LD, None, sh=(2, 2), outline=True, m=inner)
    c.paint(lambda d: d.ellipse(E(lx - 4, ly - 4.2, 2.6, 1.9), fill=255), WH)
    if expr == "happy":
        lid = c.mask(lambda d: d.pieslice(E(lx, ly + 12, 19, 14), 180, 360, fill=255))
        c.a[lid & inner] = U
        c.paint(lambda d: d.arc(E(lx, ly + 12, 19, 14), 190, 350, fill=OUT, width=max(1, round(s))), OUT, clip=inner | lid)
    elif expr == "sad":
        lid = c.mask(lambda d: d.polygon(P((lx - 15, ly - 13), (lx + 15, ly - 13), (lx + 15, ly - 6), (lx - 15, ly + 5))))
        c.a[lid & inner] = U
        c.paint(lambda d: d.line(P((lx - 14, ly + 5), (lx + 13, ly - 6)), fill=OUT, width=max(1, round(s))), OUT, clip=inner | lens)
    # eyebrows under the lip (above the lens)
    by = 9
    w = max(1, round(1.6 * s))
    if expr == "happy":
        brows = [((-17, by + 2), (-9, by - 1)), ((17, by + 2), (9, by - 1))]
    elif expr == "sad":
        brows = [((-17, by - 1), (-8, by + 3)), ((17, by - 1), (8, by + 3))]
    else:
        brows = [((-17, by + 1), (-8, by)), ((17, by + 1), (8, by))]
    for (p, q) in brows:
        c.paint(lambda d, p=p, q=q: d.line(P(p, q), fill=OUT, width=w), SKS if False else HS)
    # ear guards
    for sign in (-1, 1):
        c.part(lambda d, sign=sign: d.rounded_rectangle((cx + s * (sign * 35 - 6.5), cy + s * 0, cx + s * (sign * 35 + 6.5), cy + s * 32), radius=s * 6, fill=255), H, HS, HL, sh=(2, 2), hl=(1, 1))
    # the helmet: a dome a size too big, and its brim
    c.part(lambda d: d.ellipse(E(0, -18, 40, 24), fill=255), H, HS, HL, sh=(4, 4), hl=(3, 3))
    c.part(lambda d: d.polygon(P((-40, -6), (40, -6), (38, 0), (-38, 0))), H, HS, HL, sh=(2, 2), hl=(1, 1))
    # a gloss on the dome
    c.paint(lambda d: d.pieslice(E(-15, -26, 15, 10), 200, 270, fill=255), WH)
    c.paint(lambda d: d.arc(E(-15, -26, 18, 12), 195, 265, fill=HL, width=max(1, round(1.5 * s))), HL)
    # a strip of tape across the dome: a scrappy helmet
    c.paint(lambda d: [d.line(P((14, -34), (24, -26)), fill=HS, width=max(1, round(2 * s))), d.line(P((24, -35), (14, -25)), fill=HS, width=max(1, round(2 * s)))], HS)
    # rank patch: a small gold shield with a chevron
    c.part(lambda d: d.polygon(P((-6, -20), (6, -20), (6, -11), (0, -5), (-6, -11))), BG, BS, None, sh=(1, 1))
    c.paint(lambda d: [d.line(P((-4, -15), (0, -18)), fill=BS), d.line(P((0, -18), (4, -15)), fill=BS)], BS)
    # the Black Hole's emblem on the side of the helmet
    c.part(lambda d: d.ellipse(E(-27, -16, 5, 5), fill=255), FP, None, None, sh=(1, 1))
    c.paint(lambda d: d.arc(E(-27, -16, 3, 3), 20, 300, fill=WH, width=1), WH)
