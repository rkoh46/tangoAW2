"""Drawing engine for original CO portraits (docs/dev/co-kit.md): shapes rasterised to masks, painted with a 3-tone cel ramp (highlight rim toward the light, shadow rim away from it)
and a one-pixel outline, in layers (later layers cover earlier ones). Pictures are grids of palette SLOT NAMES; a design's `colours` map the slots to RGB, and the composer
fits the whole portrait (figure, faces, small face, HUD face) to the game's 15 colours. Everything drawn with this module is original art of this repository (GPL-3.0-or-later)."""
import numpy as np
from PIL import Image, ImageDraw


class Art:
    def __init__(self, w, h):
        self.w, self.h = w, h
        self.g = np.full((h, w), "", dtype=object)

    # --- masks --------------------------------------------------------------------
    def _img(self):
        return Image.new("L", (self.w, self.h), 0)

    def poly(self, pts):
        im = self._img()
        ImageDraw.Draw(im).polygon([(float(x), float(y)) for x, y in pts], fill=255)
        return np.array(im) > 0

    def ellipse(self, cx, cy, rx, ry):
        im = self._img()
        ImageDraw.Draw(im).ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=255)
        return np.array(im) > 0

    def rect(self, x0, y0, x1, y1):
        m = np.zeros((self.h, self.w), bool)
        m[max(0, int(y0)):max(0, int(y1) + 1), max(0, int(x0)):max(0, int(x1) + 1)] = True
        return m

    def thick(self, pts, width, round_caps=True):
        """A polyline with width."""
        im = self._img()
        d = ImageDraw.Draw(im)
        d.line([(float(x), float(y)) for x, y in pts], fill=255, width=int(width))
        if round_caps and width > 2:
            r = width / 2
            for x, y in (pts[0], pts[-1]):
                d.ellipse([x - r + 0.5, y - r + 0.5, x + r - 0.5, y + r - 0.5], fill=255)
            for x, y in pts[1:-1]:
                d.ellipse([x - r + 0.5, y - r + 0.5, x + r - 0.5, y + r - 0.5], fill=255)
        return np.array(im) > 0

    @staticmethod
    def shift(m, dx, dy):
        out = np.zeros_like(m)
        h, w = m.shape
        ys, xs = slice(max(0, dy), min(h, h + dy)), slice(max(0, dx), min(w, w + dx))
        yd, xd = slice(max(0, -dy), min(h, h - dy)), slice(max(0, -dx), min(w, w - dx))
        out[ys, xs] = m[yd, xd]
        return out

    @staticmethod
    def ring(m):
        e = m.copy()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            e &= Art.shift(m, dx, dy)
        return m & ~e

    # --- painting -----------------------------------------------------------------
    def fill(self, m, slot):
        self.g[m] = slot

    def paint(self, m, ramp, edge="ol", hi=None, lo=None, light=(-1, -1), clip=None):
        """Fill mask `m` with ramp = (highlight, mid, shadow) slot names (a 2-tuple is (highlight, mid); a 1-tuple flat). The highlight rim faces the light, the shadow rim away."""
        if clip is not None:
            m = m & clip
        if not m.any():
            return m
        size = float(m.sum()) ** 0.5
        hi = hi if hi is not None else int(min(4, max(1, size / 22)))
        lo = lo if lo is not None else int(min(6, max(1, size / 12)))
        mid = ramp[1] if len(ramp) > 1 else ramp[0]
        self.g[m] = mid
        lx, ly = light
        if len(ramp) == 3 and lo:
            shd = m & ~self.shift(m, int(lx * lo), int(ly * lo))      # the rim away from the light
            self.g[shd] = ramp[2]
        if len(ramp) >= 2 and hi:
            hl = m & ~self.shift(m, int(-lx * hi), int(-ly * hi))     # the rim toward the light
            self.g[hl] = ramp[0]
        if edge:
            self.g[self.ring(m)] = edge
        return m

    def line(self, pts, slot, width=1):
        m = self.thick(pts, width, round_caps=False)
        self.g[m] = slot
        return m

    def dot(self, x, y, slot):
        if 0 <= int(y) < self.h and 0 <= int(x) < self.w:
            self.g[int(y), int(x)] = slot

    def grid(self, x0, y0, rows, key, flip=False):
        """Draw a pixel grid: each char looks up `key` (a slot name) or '.' for nothing."""
        for j, r in enumerate(rows):
            r = r[::-1] if flip else r
            for i, ch in enumerate(r):
                if ch != "." and ch in key and key[ch]:
                    self.dot(x0 + i, y0 + j, key[ch])

    def outline_pass(self, slot="ol"):
        """The silhouette: every empty pixel next to a filled one gets the outline (drawn outside, as sprites do)."""
        filled = self.g != ""
        edge = np.zeros_like(filled)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            edge |= self.shift(filled, dx, dy)
        self.g[edge & ~filled] = slot

    def crop(self, x0, y0, w, h):
        a = Art(w, h)
        a.g = self.g[y0:y0 + h, x0:x0 + w].copy()
        return a

    def paste(self, other, x0, y0):
        for y in range(other.h):
            for x in range(other.w):
                v = other.g[y, x]
                if v and 0 <= x0 + x < self.w and 0 <= y0 + y < self.h:
                    self.g[y0 + y, x0 + x] = v

    def mask_of(self):
        return self.g != ""


def hexrgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
