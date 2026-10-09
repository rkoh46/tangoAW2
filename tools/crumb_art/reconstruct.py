"""Reconstructs the native pixel art from an upscaled (JPEG) picture of it:
detects the pixel grid, samples each cell, snaps the colours to a small
palette and makes the background transparent. A native-size PNG (indexed or
not) is taken as it is (only snapped to the palette).

    python3 tools/crumb_art/reconstruct.py <in.jpg|png> <out.png> [--flip] [--ncolours 15]

The user's Crumb art (side view, facing right) is stored mirrored, facing left
as the game's figures are stored.
"""
import sys
import numpy as np
from PIL import Image


def grid(g, lo=8.0, hi=16.0):
    """(cell size, offset) whose edges best fit the picture's edge energy."""
    best = (0, 0, 0)
    for p in np.arange(lo, hi, 0.02):
        for o in np.arange(0, p, 0.25):
            idx = np.round(np.arange(o, len(g) - 1, p)).astype(int)
            s = g[idx].mean()
            if s > best[0]:
                best = (s, p, o)
    return best[1], best[2]


def sample(im, px, ox, py, oy):
    h, w, _ = im.shape
    nx, ny = int((w - ox) // px), int((h - oy) // py)
    out = np.zeros((ny, nx, 3))
    for j in range(ny):
        for i in range(nx):
            x0, x1 = ox + (i + 0.25) * px, ox + (i + 0.75) * px
            y0, y1 = oy + (j + 0.25) * py, oy + (j + 0.75) * py
            cell = im[int(y0):int(y1) + 1, int(x0):int(x1) + 1].reshape(-1, 3)
            out[j, i] = np.median(cell, axis=0)
    return out


def kmeans(pix, k, iters=40, seed=1):
    rng = np.random.default_rng(seed)
    cent = pix[rng.choice(len(pix), k, replace=False)].astype(float)
    # k-means++ style spread
    cent[0] = pix[0]
    for n in range(1, k):
        d = ((pix[:, None, :] - cent[None, :n, :]) ** 2).sum(-1).min(1)
        cent[n] = pix[np.argmax(d)]
    for _ in range(iters):
        lab = ((pix[:, None, :] - cent[None]) ** 2).sum(-1).argmin(1)
        for n in range(k):
            m = lab == n
            if m.any():
                cent[n] = pix[m].mean(0)
    return cent


def main():
    src, dst = sys.argv[1], sys.argv[2]
    flip = "--flip" in sys.argv
    k = int(sys.argv[sys.argv.index("--ncolours") + 1]) if "--ncolours" in sys.argv else 15
    im = Image.open(src).convert("RGB")
    a = np.array(im).astype(float)
    if max(a.shape[:2]) < 400:
        cells = a
    else:
        gx = np.abs(np.diff(a, axis=1)).sum(axis=(0, 2))
        gy = np.abs(np.diff(a, axis=0)).sum(axis=(1, 2))
        (px, ox), (py, oy) = grid(gx), grid(gy)
        print(f"cell {px:.2f} x {py:.2f}, offset {ox:.2f}, {oy:.2f}")
        cells = sample(a, px, ox - px if ox > 0 else ox, py, oy - py if oy > 0 else oy)
    h, w, _ = cells.shape
    # the background: the commonest colour along the border
    border = np.concatenate([cells[0], cells[-1], cells[:, 0], cells[:, -1]])
    bg = np.median(border, axis=0)
    isbg = np.abs(cells - bg).sum(-1) < 40
    fg = cells[~isbg]
    # k + 1 clusters, then colours closer than 24 are merged (JPEG noise makes twins)
    cent = list(kmeans(fg, k + 1))
    while True:
        pairs = [(((cent[i] - cent[j]) ** 2).sum() ** 0.5, i, j) for i in range(len(cent)) for j in range(i)]
        d, i, j = min(pairs)
        if len(cent) <= k and d >= 24:
            break
        if len(cent) <= 2:
            break
        cent[j] = (cent[i] + cent[j]) / 2
        del cent[i]
    cent = np.array(cent)
    lab = ((cells[:, :, None, :] - cent[None, None]) ** 2).sum(-1).argmin(-1) + 1
    lab[isbg] = 0
    # no stray pixels: a pixel whose four neighbours all agree on another colour takes it
    for _ in range(2):
        p = np.pad(lab, 1, mode="edge")
        for y in range(h):
            for x in range(w):
                n = [p[y, x + 1], p[y + 2, x + 1], p[y + 1, x], p[y + 1, x + 2]]
                if len(set(n)) == 1 and n[0] != lab[y, x]:
                    lab[y, x] = n[0]
    # crop to the opaque box
    ys, xs = np.where(lab > 0)
    lab = lab[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    if flip:
        lab = lab[:, ::-1]
    out = Image.fromarray(lab.astype(np.uint8), "P")
    pal = [0, 0, 0]
    for c in cent:
        q = [int(v) >> 3 for v in c]
        pal += [q[0] << 3 | q[0] >> 2, q[1] << 3 | q[1] >> 2, q[2] << 3 | q[2] >> 2]
    out.putpalette(pal + [0] * (48 - len(pal)))
    out.save(dst, transparency=0, bits=4)
    print("written", dst, out.size, "colours", len(cent))


if __name__ == "__main__":
    main()
