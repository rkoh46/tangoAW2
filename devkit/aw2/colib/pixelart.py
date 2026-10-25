"""`co portrait import --pixelart` (docs/dev/co-kit.md): the supplied picture is already pixel art, upscaled by a (possibly fractional) factor and saved as a JPEG. It is imported faithfully:
the native pixel grid is found (cell size and phase per axis), the picture is resampled at the cell centres (the middle of each cell, so JPEG ringing at the cell edges does not count), the
background is cut by an outline-aware flood fill on the native pixels, and the figure is framed and scaled by an integer factor (no blurry resampling)."""
import numpy as np
from PIL import Image


def _profile(a, axis):
    g = np.abs(np.diff(a, axis=axis)).sum(2)
    return g.sum(1 - axis if False else (0 if axis == 1 else 1))


def detect_axis(g, lo=2.5, hi=16.0):
    """-> (period, phase) of the cell edges in an edge profile g (one value per pixel boundary): the pair whose comb of boundaries collects the most edge energy."""
    n = len(g)
    best = (-1, None, None)
    for period in np.arange(lo, hi, 0.01):
        for phase in np.arange(0, period, 0.25):
            pos = np.round(np.arange(phase, n, period)).astype(int)
            pos = pos[(pos >= 0) & (pos < n)]
            score = g[pos].mean()
            if score > best[0]:
                best = (score, period, phase)
    return best[1], best[2]


def refine(g, period, edge0):
    """Fit the cell edges: the strength-weighted centroid of the edge profile around every predicted edge, then a weighted line through them. g[i] is the change between pixels i and i+1,
    so an edge between them lies at pixel coordinate i + 1. -> (period, first edge)."""
    n = len(g)
    ks, ps, ws = [], [], []
    for k in range(int((n - edge0) // period)):
        c = edge0 + k * period
        lo, hi = int(round(c)) - 2, int(round(c)) + 2
        if lo < 0 or hi >= n:
            continue
        seg = g[lo: hi]
        if seg.sum() <= 0:
            continue
        ks.append(k)
        ps.append((np.arange(lo, hi) * seg).sum() / seg.sum() + 1.0)
        ws.append(seg.max())
    ks, ps, ws = np.array(ks), np.array(ps), np.array(ws)
    keep = ws > np.median(ws)       # the strong edges only (flat background has none)
    for _ in range(3):
        A = np.vstack([ks[keep], np.ones(keep.sum())]).T
        coef, *_ = np.linalg.lstsq(A * ws[keep][:, None], ps[keep] * ws[keep], rcond=None)
        res = np.abs(ps - (coef[0] * ks + coef[1]))
        keep = (res < 0.8) & (ws > np.median(ws) * 0.5)
    return float(coef[0]), float(coef[1])


def detect_grid(rgb):
    """rgb: h x w x 3. -> (px, ox, py, oy): the cell size and the first cell edge, per axis."""
    a = rgb.astype(float)
    gx = np.abs(np.diff(a, axis=1)).sum(2).sum(0)
    gy = np.abs(np.diff(a, axis=0)).sum(2).sum(1)
    # coarse: FFT for the period, then a fine search around it
    out = []
    for g in (gx, gy):
        f = np.abs(np.fft.rfft((g - g.mean()) * np.hanning(len(g))))
        cand = [(len(g) / i, f[i]) for i in range(1, len(f)) if 3 <= len(g) / i <= 16]
        p0 = max(cand, key=lambda t: t[1])[0]
        best = (-1, None, None)
        for period in np.arange(p0 - 0.12, p0 + 0.12, 0.002):
            for phase in np.arange(0, period, 0.1):
                pos = np.round(np.arange(phase, len(g), period)).astype(int)
                pos = pos[pos < len(g)]
                sc = g[pos].mean()
                if sc > best[0]:
                    best = (sc, period, phase)
        out.append(refine(g, best[1], best[2] + 1.0))
    (px, ox), (py, oy) = out
    return px, ox, py, oy


def native(rgb, grid, inner=0.5):
    """Resample at the cell centres: the mean of the middle `inner` fraction of every cell. -> float array (rows, cols, 3)."""
    px, ox, py, oy = grid
    h, w, _ = rgb.shape
    cols = int((w - ox) // px)
    rows = int((h - oy) // py)
    out = np.zeros((rows, cols, 3))
    ii = np.pad(rgb.astype(float), ((1, 1), (1, 1), (0, 0)), mode="edge")
    cs = np.cumsum(np.cumsum(np.pad(ii, ((1, 0), (1, 0), (0, 0))), 0), 1)

    def box(y0, y1, x0, x1):
        y0, y1, x0, x1 = int(round(y0)) + 1, int(round(y1)) + 1, int(round(x0)) + 1, int(round(x1)) + 1
        y1, x1 = max(y1, y0 + 1), max(x1, x0 + 1)
        s = cs[y1, x1] - cs[y0, x1] - cs[y1, x0] + cs[y0, x0]
        return s / ((y1 - y0) * (x1 - x0))
    m = (1 - inner) / 2
    for r in range(rows):
        for c in range(cols):
            x0, y0 = ox + c * px, oy + r * py
            out[r, c] = box(y0 + m * py, y0 + (1 - m) * py, x0 + m * px, x0 + (1 - m) * px)
    return out


def cut_background(nat, tol=9.0, rim=2):
    """The figure's mask: what the border's flood fill (over native pixels within `tol` of the background colour) does not reach. -> bool array (rows, cols)."""
    h, w, _ = nat.shape
    edge = np.concatenate([nat[:rim].reshape(-1, 3), nat[-rim:].reshape(-1, 3), nat[:, :rim].reshape(-1, 3), nat[:, -rim:].reshape(-1, 3)])
    bg = np.median(edge, axis=0)
    near = np.abs(nat - bg).max(2) < tol
    seen = np.zeros((h, w), bool)
    st = [(y, x) for y in range(h) for x in (0, w - 1)] + [(y, x) for x in range(w) for y in (0, h - 1)]
    st = [p for p in st if near[p]]
    for p in st:
        seen[p] = True
    while st:
        y, x = st.pop()
        for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= yy < h and 0 <= xx < w and not seen[yy, xx] and near[yy, xx]:
                seen[yy, xx] = True
                st.append((yy, xx))
    fg = ~seen
    return fg, bg


def keep_main(fg, min_size=12):
    """Drop 8-connected specks of the mask below min_size cells (the background's noise); fill one-cell holes."""
    h, w = fg.shape
    out = np.zeros_like(fg)
    seen = np.zeros_like(fg)
    for y in range(h):
        for x in range(w):
            if fg[y, x] and not seen[y, x]:
                comp, st = [], [(y, x)]
                seen[y, x] = True
                while st:
                    a, b = st.pop()
                    comp.append((a, b))
                    for da in (-1, 0, 1):
                        for db in (-1, 0, 1):
                            aa, bb = a + da, b + db
                            if 0 <= aa < h and 0 <= bb < w and fg[aa, bb] and not seen[aa, bb]:
                                seen[aa, bb] = True
                                st.append((aa, bb))
                if len(comp) >= min_size:
                    for a, b in comp:
                        out[a, b] = True
    return out


# --- the import --------------------------------------------------------------------------------------------------------------------------------------------------

def _dilate(m):
    out = m.copy()
    out[1:, :] |= m[:-1, :]
    out[:-1, :] |= m[1:, :]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def palette_for(pixels_rgb, weights, k=14, outline=(32, 24, 32)):
    """k colours of the native pixels (weighted k-means in Lab; JPEG near-duplicates merge), plus the fixed outline colour. -> list of 15 RGB, lightest first, the outline last."""
    from . import importer as I
    lab = I.to_lab(pixels_rgb.astype(float))
    if len(np.unique(lab.round(1), axis=0)) <= k + 1:
        # fewer colours than clusters (a tiny or flat picture): the colours themselves
        cent = np.unique(lab.round(1), axis=0)
    else:
        cent = I.kmeans(lab, weights.astype(float), k + 1, iters=40, seed=5)
    rgb = I.snap555(I.lab_to_rgb(cent))
    olab = I.to_lab(np.array([outline], float))[0]
    d = ((cent - olab) ** 2).sum(1) ** 0.5
    j = int(d.argmin())
    keep = [i for i in range(len(cent)) if i != j] if d[j] < 14 else list(range(len(cent)))[:k]
    cols = [tuple(int(v) for v in rgb[i]) for i in keep]
    lum = [0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] for c in cols]
    cols = [cols[i] for i in np.argsort(lum)[::-1]][:14]
    # a palette needs 14 entries before the outline; pad with the darkest if the clustering found fewer
    while len(cols) < 14:
        cols.append(cols[-1])
    return cols + [tuple(int(v) for v in I.snap555(np.array(outline, float)))]


def quantise(nat, fg, pal):
    from . import importer as I
    lab = I.to_lab(nat.reshape(-1, 3).astype(float))
    pl = I.to_lab(np.array(pal, float))
    d = ((lab[:, None, :] - pl[None]) ** 2).sum(2)
    idx = d.argmin(1).reshape(nat.shape[:2]) + 1
    return np.where(fg, idx, 0).astype(np.uint8)


def ring(fg, idx, sides=(True, True, True, True)):
    """The outline (index 15) one native cell wide around the figure, on the sides given (left, right, top, bottom)."""
    out = idx.copy()
    h, w = fg.shape
    edge = np.zeros_like(fg)
    if sides[0]:
        edge[:, 1:] |= fg[:, :-1]
    if sides[1]:
        edge[:, :-1] |= fg[:, 1:]
    if sides[2]:
        edge[1:, :] |= fg[:-1, :]
    if sides[3]:
        edge[:-1, :] |= fg[1:, :]
    out[edge & ~fg] = 15
    return out


def styled(spec, path):
    from . import importer as I
    img = np.array(Image.open(path).convert("RGB"))
    grid = detect_grid(img)
    nat = native(img, grid)
    if spec.get("flip"):
        nat = nat[:, ::-1].copy()
    fg, bg = cut_background(nat, spec.get("bg_tolerance", 9.0))
    fg = keep_main(fg)
    S = 2
    fw, fh = 128 // S, 160 // S
    if "frame" not in spec:
        # auto framing: the head's top near the top of the 160-row frame (AW2's top margin is a few pixels), the frame centred on the upper body's mass
        ys, xs = np.where(fg)
        top = int(ys.min())
        band = fg[top: top + fh]
        cx = int(round(np.where(band)[1].mean()))
        spec = {**spec, "frame": [cx - fw // 2, top - 2]}
    x0, y0 = spec["frame"]
    for key in ("mug", "eyes", "mouth"):
        if key not in spec:
            raise SystemExit(f"{path}: the framing file needs `{key}` (native cells of the picture; `aw2dev co portrait grid` numbers them)")
    mx0, my0 = spec["mug"]
    ms = 48 // S
    pad = lambda a, ys, xs: a[ys, xs]
    # a frame may reach past the picture (a short figure, a face near an edge): pad with background cells
    P = 64
    nat = np.pad(nat, ((P, P), (P, P), (0, 0)), mode="edge")
    fg = np.pad(fg, P, constant_values=False)
    fr = (slice(y0 + P, y0 + P + fh), slice(x0 + P, x0 + P + fw))
    mu = (slice(my0 + P, my0 + P + ms), slice(mx0 + P, mx0 + P + ms))
    px = np.concatenate([nat[fr][fg[fr]], nat[mu][fg[mu]]])
    wt = np.concatenate([np.ones(fg[fr].sum()), np.full(fg[mu].sum(), spec.get("face_weight", 3.0))])
    pal = palette_for(px, wt, outline=tuple(spec.get("outline", (32, 24, 32))))
    full = quantise(nat, fg, pal[:14])
    full = ring(fg, full)
    # the ring is index 15; nothing else uses index 15 (the palette has 14 clusters, indexes 1..14)
    pal16 = [(0, 0, 0)] + pal[:14] + [pal[14]]
    ex = lambda a, sl: np.kron(a[sl], np.ones((S, S), np.uint8))
    L = ex(full, fr)
    nface = full[mu].copy()
    face = np.kron(nface, np.ones((S, S), np.uint8))
    im = I.Imported()
    im.spec = spec
    im.palette = pal16
    im.large = L
    im.faces["normal"] = face
    e = spec["eyes"]
    k = 48.0 / ms
    exm = round(((e[0] + e[2]) / 2 - mx0) * k)
    eym = round(((e[1] + e[3]) / 2 - my0) * k)
    im.eye = (exm, eym)
    im.mini = I._window(face, exm - 16, eym - 10, 32, 24)
    im.hud = I._window(face, exm - 16, eym - 6, 32, 16)
    # the framing file's coordinates for the expression edits are native cells of the (mirrored) grid; the mug square is `ms` cells at scale k
    im.spec = {**spec, "face": [mx0, my0, ms]}
    for kind in ("happy", "sad", "angry"):
        im.faces[kind] = np.kron(expression_native(nface, spec, pal16, kind), np.ones((S, S), np.uint8))
    return im


# --- expressions at the native resolution (every edit is whole cells, so it has the picture's own pixel size) ---------------------------------------------------------------

def _cheek(face, cx, cy, pal):
    """The commonest skin-like index in the ring around (cx, cy): not the outline, not near-white, not darker than the middle of the palette's lightness."""
    from collections import Counter
    lum = {i: 0.299 * pal[i][0] + 0.587 * pal[i][1] + 0.114 * pal[i][2] for i in range(1, 16)}
    c = Counter()
    for y in range(cy - 3, cy + 4):
        for x in range(cx - 4, cx + 5):
            if 0 <= y < face.shape[0] and 0 <= x < face.shape[1]:
                v = int(face[y, x])
                if v and v != 15 and 110 < lum[v] < 235:
                    c[v] += 1
    return c.most_common(1)[0][0] if c else 2


def _brow_index(face, cx, cy, pal, skin):
    """The darkest non-outline index in the band just above the eye (the brow's own colour)."""
    lum = lambda i: 0.299 * pal[i][0] + 0.587 * pal[i][1] + 0.114 * pal[i][2]
    best = None
    for y in range(cy - 4, cy - 1):
        for x in range(cx - 3, cx + 4):
            if 0 <= y < face.shape[0] and 0 <= x < face.shape[1]:
                v = int(face[y, x])
                if v and v != skin and (best is None or lum(v) < lum(best)):
                    best = v
    return best or 15


def expression_native(face, spec, pal, kind):
    """face: the mug in native cells (ms x ms). -> the same with the eyes, brows and mouth of `kind` (happy, sad, angry); the neutral face is the picture's own."""
    f = face.copy()
    mx0, my0 = spec["mug"]
    e = spec["eyes"]
    eyes = [(round(e[0] - mx0), round(e[1] - my0)), (round(e[2] - mx0), round(e[3] - my0))]
    mx, my = round(spec["mouth"][0] - mx0), round(spec["mouth"][1] - my0)
    h, w = f.shape
    def inside(x, y):
        return 0 <= x < w and 0 <= y < h and face[y, x] != 0 and face[y, x] != 15 or (0 <= x < w and 0 <= y < h and face[y, x] == 15 and False)

    # the silhouette's outline and the cells against it stay as they are
    tr = face == 0
    near = np.zeros_like(tr)
    near[1:, :] |= tr[:-1, :]
    near[:-1, :] |= tr[1:, :]
    near[:, 1:] |= tr[:, :-1]
    near[:, :-1] |= tr[:, 1:]
    prot = near

    def put(x, y, v):
        if 0 <= x < w and 0 <= y < h and f[y, x] != 0 and not prot[y, x]:
            f[y, x] = v

    skin = _cheek(face, (eyes[0][0] + eyes[1][0]) // 2, eyes[0][1] + 3, pal)
    mskin = _cheek(face, mx, my - 3, pal)
    brow = spec.get("brow_index") or _brow_index(face, eyes[0][0], eyes[0][1], pal, skin)
    ink = 15
    # which eye is nearer the face's middle: the inner end of each brow points to the other eye
    for n, (ex, ey) in enumerate(eyes):
        inner = 1 if n == 0 else -1      # the direction of the nose
        if kind == "happy":
            for y in range(ey - 1, ey + 2):
                for x in range(ex - 2, ex + 3):
                    put(x, y, skin)
            for x, y in ((ex - 2, ey + 1), (ex - 1, ey), (ex, ey), (ex + 1, ey), (ex + 2, ey + 1)):
                put(x, y, ink)
        elif kind in ("sad", "angry"):
            for y in range(ey - 3, ey - 1):
                for x in range(ex - 3, ex + 4):
                    if face[y, x] not in (0, 15) and face[y, x] != skin:
                        put(x, y, skin)
            if kind == "sad":      # the inner end of the brow is high
                pts = [(ex - 2 * inner, ey - 2), (ex - inner, ey - 2), (ex, ey - 3), (ex + inner, ey - 3), (ex + 2 * inner, ey - 4)]
            else:                  # the inner end is low
                pts = [(ex - 2 * inner, ey - 4), (ex - inner, ey - 3), (ex, ey - 3), (ex + inner, ey - 2), (ex + 2 * inner, ey - 2)]
            for x, y in pts:
                put(x, y, brow)
            if kind == "angry":
                for x in range(ex - 2, ex + 3):
                    put(x, ey - 1, ink)
    if kind != "normal":
        for y in range(my - 1, my + 2):
            for x in range(mx - 3, mx + 4):
                put(x, y, mskin)
        if kind == "happy":
            for x, y in ((mx - 3, my - 1), (mx - 2, my), (mx + 2, my), (mx + 3, my - 1)):
                put(x, y, ink)
            for x in range(mx - 1, mx + 2):
                put(x, my, 1)
                put(x, my + 1, ink)
            put(mx - 2, my + 1, ink)
            put(mx + 2, my + 1, ink)
        elif kind == "sad":
            for x, y in ((mx - 2, my + 1), (mx - 1, my), (mx, my), (mx + 1, my), (mx + 2, my + 1)):
                put(x, y, ink)
        else:
            for x in range(mx - 2, mx + 3):
                put(x, my, ink)
            put(mx - 3, my + 1, ink)
            put(mx + 3, my + 1, ink)
    return f


def describe(path, flip=False, out=None):
    """The grid, the native size and the figure's box of a pixel-art picture; with `out`, a debug picture of the native cells (mirrored if `flip`) with every tenth cell numbered. -> text."""
    from PIL import ImageDraw
    img = np.array(Image.open(path).convert("RGB"))
    grid = detect_grid(img)
    nat = native(img, grid)
    if flip:
        nat = nat[:, ::-1].copy()
    fg, bg = cut_background(nat)
    fg = keep_main(fg)
    ys, xs = np.where(fg)
    if out:
        S = 6
        show = np.clip(np.where(fg[..., None], nat, nat * 4), 0, 255).astype(np.uint8)
        im = Image.fromarray(show).resize((nat.shape[1] * S, nat.shape[0] * S), Image.NEAREST)
        d = ImageDraw.Draw(im)
        for x in range(0, nat.shape[1], 10):
            d.line((x * S, 0, x * S, im.height), fill=(0, 160, 255))
            d.text((x * S + 2, 2), str(x), fill=(0, 255, 255))
        for y in range(0, nat.shape[0], 10):
            d.line((0, y * S, im.width, y * S), fill=(255, 160, 0))
            d.text((2, y * S + 2), str(y), fill=(255, 255, 0))
        im.save(out)
    px, ox, py, oy = grid
    return (f"cell {px:.3f} x {py:.3f} px, first edge ({ox:.1f}, {oy:.1f}); native {nat.shape[1]} x {nat.shape[0]} cells; background {tuple(int(v) for v in bg)}; "
            f"figure cells x {xs.min()}..{xs.max()}, y {ys.min()}..{ys.max()} ({'mirrored' if flip else 'as is'}); a 128 x 160 frame at 2x shows 64 x 80 cells")
