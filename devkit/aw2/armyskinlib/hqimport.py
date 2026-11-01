"""Import a user's HQ picture faithfully (`aw2dev armyskin import-hq`): the picture is pixel art shown upscaled (with a JPEG's noise, a frame and a
grass background); this finds its pixel grid, samples every cell (the median of its middle, so the noise goes), removes the grass the HQ stands on
(the cells of the grass family joined to the picture's edge) and writes the cells as the skin file's `[hq]` rows in the building palette's indices.
Nothing is redrawn: a cell is the nearest of the picture's own few colours.

The colours of the picture (`--map`) go to the building palette's entries as `NAME=INDEX` pairs; the default is Silver Nova's (docs/dev/army-packs.md)."""
import statistics
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image

# the picture's own colours: name -> (RGB measured from the user's picture, palette index character of the skin file's rows)
DEFAULT = {
    "white": ((254, 254, 254), "1"),   # the ring round the orb, highlights
    "light": ((192, 221, 231), "2"),   # the pale panels (building ramp 1)
    "mid": ((101, 116, 145), "4"),     # the tower's body (building ramp 3)
    "dark": ((83, 92, 120), "5"),      # the shading (building ramp 4)
    "window": ((246, 247, 130), "e"),  # the lit windows: the skin's `gold`
    "orb_light": ((219, 235, 110), "c"),   # the orb's glow: the skin's `orb[0]`
    "orb_mid": ((165, 216, 108), "b"),     # the skin's `orb[1]`
    "orb_dark": ((114, 176, 115), "8"),    # the skin's `orb[2]`
}


def fit_grid(im, lo=8.0, hi=12.0):
    """The period and phase of the pixel grid on one axis each: the boundaries are where neighbouring columns (rows) differ most."""
    a = np.asarray(im.convert("RGB")).astype(int)
    out = []
    for g in (np.abs(np.diff(a, axis=1)).sum((0, 2)), np.abs(np.diff(a, axis=0)).sum((1, 2))):
        best = (0, 0, 0)
        for p in np.arange(lo, hi, 0.01):
            for ph in np.arange(0, p, 0.25):
                xs = (ph + p * np.arange(int((len(g) - ph) / p))).astype(int)
                xs = xs[xs < len(g)]
                s = g[xs].sum()
                if s > best[0]:
                    best = (s, p, ph)
        out.append(best[1:])
    return out   # [(period, phase) for x, for y]


def sample(im, size=(16, 32)):
    """size cells of the picture as an array [rows][cols] of RGB (medians of each cell's middle), from the fitted grid (the first boundary is the sprite's corner)."""
    a = np.asarray(im.convert("RGB")).astype(int)
    (px, fx), (py, fy) = fit_grid(im)
    w, h = size
    g = np.zeros((h, w, 3), int)
    for r in range(h):
        for c in range(w):
            y = int(fy + (r + 0.5) * py)
            x = int(fx + (c + 0.5) * px)
            g[r, c] = np.median(a[max(0, y - 3):y + 4, max(0, x - 3):x + 4].reshape(-1, 3), axis=0)
    return g, (px, py, fx, fy)


def is_grass(c):
    r, g, b = (int(v) for v in c)
    return g - b >= 30 and g >= r - 25


def import_hq(path, size=(16, 32), colours=None):
    """Returns (rows, report): rows is `size[1]` strings of `size[0]` characters (`.` clear)."""
    colours = colours or DEFAULT
    im = Image.open(path)
    g, grid = sample(im, size)
    h, w, _ = g.shape
    # the grass: cells of the grass family joined to the edge (the orb's greens are enclosed by the ring and stay)
    bg = np.zeros((h, w), bool)
    todo = [(r, c) for r in range(h) for c in range(w) if (r in (0, h - 1) or c in (0, w - 1)) and is_grass(g[r, c])]
    while todo:
        r, c = todo.pop()
        if bg[r, c]:
            continue
        bg[r, c] = True
        for dr, dc in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            rr, cc = r + dr, c + dc
            if 0 <= rr < h and 0 <= cc < w and not bg[rr, cc] and is_grass(g[rr, cc]):
                todo.append((rr, cc))
    names = list(colours)
    rows, used = [], Counter()
    for r in range(h):
        s = ""
        for c in range(w):
            if bg[r, c]:
                s += "."
                continue
            d = [sum((int(a) - b) ** 2 for a, b in zip(g[r, c], colours[n][0])) for n in names]
            n = names[int(np.argmin(d))]
            used[n] += 1
            s += colours[n][1]
        rows.append(s)
    rep = [f"grid: period {grid[0]:.2f} x {grid[1]:.2f}, origin ({grid[2]:.1f}, {grid[3]:.1f}); {int(bg.sum())} grass cells removed, {w * h - int(bg.sum())} kept"]
    rep += [f"  {n:10s} {used[n]:4d}  -> index {colours[n][1]}" for n in names]
    return rows, rep


def toml_rows(rows):
    return "rows = [\n" + "".join(f'  "{r}",\n' for r in rows) + "]\n"


def sheet(path, rows, pal, out, scale=10):
    """The user's picture beside the imported pixels (palette `pal`: index char -> RGB), for review."""
    src = Image.open(path).convert("RGB")
    w, h = len(rows[0]), len(rows)
    imp = Image.new("RGB", (w, h), (200, 60, 200))
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch != ".":
                imp.putpixel((x, y), pal[ch])
    big = imp.resize((w * scale, h * scale), Image.NEAREST)
    sh = src.height / big.height
    left = src.resize((int(src.width / sh), big.height), Image.NEAREST)
    img = Image.new("RGB", (left.width + big.width + 30, big.height), (255, 255, 255))
    img.paste(left, (0, 0))
    img.paste(big, (left.width + 30, 0))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
