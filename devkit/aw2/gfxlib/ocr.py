"""OCR of AW2-font text on a 240x160 console picture, by matching glyph shapes against the game's own font (font.py).

Ink pixels are the dark text colour; the picture is binarised by luminance inside a region you give (never over map art). A glyph cell that matches
no glyph is `?` (a garbled or clobbered glyph); `text_lines` also reports where each line starts."""
import numpy as np
from PIL import Image
from . import font as fontmod


def _templates(rom=None):
    f = fontmod.load(rom)
    t = []
    for ch, (w, ink, _any) in f.items():
        if ch == " ":
            continue
        rows = [[(r >> x) & 1 for x in range(w)] for r in ink]
        a = np.array(rows, dtype=bool)
        ys, xs = np.where(a)
        if len(ys) == 0:
            continue
        t.append((ch, a[ys.min():ys.max() + 1, xs.min():xs.max() + 1], int(ys.min())))
    return t


_T = None


INK_RGB = (131, 123, 115)   # AW2's list/box text ink


def ink_mask(img, region=None, thresh=140, ink=None):
    """Ink pixels: within 36 of the text colour `ink` in every channel (default: luminance below `thresh`, which also catches borders and art)."""
    if ink:
        rgb = np.asarray(img.convert("RGB"), dtype=int)
        a = np.where((np.abs(rgb - np.array(ink)) < 36).all(axis=2), 0, 255)
    else:
        a = np.asarray(img.convert("L"), dtype=int)
    if region:
        x, y, w, h = region
        m = np.zeros(a.shape, bool)
        m[y:y + h, x:x + w] = a[y:y + h, x:x + w] < thresh
        return m
    return a < thresh


def read(img, region=None, rom=None, thresh=140, tol=0.12, ink=None):
    """-> [(y, x, text, n_unknown, y_end)] one entry per text line found in the region (`~` is AW2's apostrophe glyph, returned as ')."""
    global _T
    if _T is None:
        _T = _templates(rom)
    m = ink_mask(img, region, thresh, ink)
    H, W = m.shape
    rows = m.any(axis=1)
    lines, y = [], 0
    while y < H:
        if not rows[y]:
            y += 1
            continue
        y0 = y
        while y < H and rows[y]:
            y += 1
        if 4 <= y - y0 <= 17:
            lines.append((y0, y))
    out = []
    for y0, y1 in lines:
        # a line may carry descenders below the 11-row glyph box: extend the band a little
        band = m[y0:min(H, y1 + 1)]
        cols = band.any(axis=0)
        x, cells = 0, []
        while x < W:
            if not cols[x]:
                x += 1
                continue
            x0 = x
            while x < W and cols[x]:
                x += 1
            cells.append((x0, x))
        text, unknown, last = "", 0, None
        for x0, x1 in cells:
            if last is not None and x0 - last >= 4:
                text += " "
            last = x1
            cell = band[:, x0:x1]
            ys = np.where(cell.any(axis=1))[0]
            cell = cell[ys.min():ys.max() + 1]
            best, bs = "?", 1.0
            for ch, tm, _top in _T:
                if tm.shape != cell.shape:
                    continue
                d = float((tm != cell).mean())
                if d < bs:
                    best, bs = ch, d
            if bs > tol:
                best = "?"
                unknown += 1
            text += best
        if text.strip():
            out.append((y0, cells[0][0] if cells else 0, text.replace('~', "'"), unknown, y1))
    return out
