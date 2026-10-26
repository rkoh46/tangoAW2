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


def cut_background(nat, tol=9.0, rim=2, hole_min=0, hole_tol=14.0, peel=0):
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
    if hole_min:
        # enclosed gaps of the pure background colour (between an arm and the body, hair and neck) are background too; their pale fringe goes with them
        pure = np.abs(nat - bg).max(2) < hole_tol
        todo = pure & fg
        done = np.zeros((h, w), bool)
        for y0, x0 in zip(*np.where(todo)):
            if done[y0, x0]:
                continue
            comp, st = [(y0, x0)], [(y0, x0)]
            done[y0, x0] = True
            while st:
                y, x = st.pop()
                for yy, xx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                    if 0 <= yy < h and 0 <= xx < w and todo[yy, xx] and not done[yy, xx]:
                        done[yy, xx] = True
                        comp.append((yy, xx))
                        st.append((yy, xx))
            if len(comp) >= hole_min:
                for y, x in comp:
                    fg[y, x] = False
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            yy, xx = y + dy, x + dx
                            if 0 <= yy < h and 0 <= xx < w and fg[yy, xx] and np.abs(nat[yy, xx] - bg).max() < tol:
                                fg[yy, xx] = False
    # the pale grey fringe where a dark edge was blended with the white: boundary cells that are light and nearly colourless (skin and the gold are not) go, `peel` rounds
    sat = nat.max(2) - nat.min(2)
    fringe = (nat.min(2) > 120) & (sat < 28)
    for _ in range(peel):
        t = ~fg
        touch = np.zeros_like(fg)
        touch[1:] |= t[:-1]
        touch[:-1] |= t[1:]
        touch[:, 1:] |= t[:, :-1]
        touch[:, :-1] |= t[:, 1:]
        fg = fg & ~(touch & fringe)
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


def quantise(nat, fg, pal, match="lab"):
    # --- art repal hook (devkit/aw2/artlib/repal.py, docs/dev/art-repal.md): `match` picks the nearest-colour rule; `styled` passes the framing file's
    # `match`, default "luma" (smallest 30/59/11-weighted absolute RGB difference); "rgb": unweighted; "lab": the Lab distance the approved COs were imported
    # with (their framing files pin it). A caller that passes no `match` keeps "lab".
    if match != "lab":
        from ..artlib import repal
        idx = repal.nearest(nat.reshape(-1, 3).round(), np.array(pal), repal.weights(match)).reshape(nat.shape[:2]) + 1
        return np.where(fg, idx, 0).astype(np.uint8)
    # --- end of the art repal hook
    from . import importer as I
    lab = I.to_lab(nat.reshape(-1, 3).astype(float))
    pl = I.to_lab(np.array(pal, float))
    d = ((lab[:, None, :] - pl[None]) ** 2).sum(2)
    idx = d.argmin(1).reshape(nat.shape[:2]) + 1
    return np.where(fg, idx, 0).astype(np.uint8)


def ring(fg, idx, sides=(True, True, True, True), diagonal=False):
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
    if diagonal:
        # corners too: no figure cell touches the empty side without the outline between (an unbroken outline in 8-connectivity, Kanbei's standard)
        for dy in (-1, 1):
            for dx in (-1, 1):
                sh = np.zeros_like(fg)
                sh[max(dy, 0):h + min(dy, 0), max(dx, 0):w + min(dx, 0)] = fg[max(-dy, 0):h + min(-dy, 0), max(-dx, 0):w + min(-dx, 0)]
                edge |= sh
    out[edge & ~fg] = 15
    return out


def despeckle_dark(idx, pal, passes=2, luma=70):
    """The JPEG's noise on black cloth and hair: a cell whose colour no 4-neighbour shares, itself dark and with only dark neighbours, takes their commonest colour. Eyes, the badge, the buckle (light or next to light cells) stay."""
    lum = np.array([0.3 * r + 0.59 * g + 0.11 * b for r, g, b in pal])
    idx = idx.copy()
    h, w = idx.shape
    for _ in range(passes):
        out = idx.copy()
        for y in range(1, h - 1):
            for x in range(1, w - 1):
                v = idx[y, x]
                if v == 0 or v == 15:
                    continue
                nb = [idx[y - 1, x], idx[y + 1, x], idx[y, x - 1], idx[y, x + 1]]
                if v in nb or any(n in (0, 15) for n in nb):
                    continue
                if lum[v - 1] < luma + 20 and all(lum[n - 1] < luma for n in nb):
                    out[y, x] = max(set(nb), key=nb.count)
        idx = out
    return idx


def drop_orphan_outline(a):
    """An outline cell whose 8 neighbours hold no figure colour (the window cut the figure away beside it) is empty."""
    a = a.copy()
    h, w = a.shape
    for y in range(h):
        for x in range(w):
            if a[y, x] == 15:
                nb = [a[yy, xx] for yy in range(max(y - 1, 0), min(y + 2, h)) for xx in range(max(x - 1, 0), min(x + 2, w)) if (yy, xx) != (y, x)]
                if not any(v not in (0, 15) for v in nb):
                    a[y, x] = 0
    return a


def styled(spec, path):
    from . import importer as I
    img = np.array(Image.open(path).convert("RGB"))
    grid = detect_grid(img)
    nat = native(img, grid)
    if spec.get("flip"):
        nat = nat[:, ::-1].copy()
    fg, bg = cut_background(nat, spec.get("bg_tolerance", 9.0), hole_min=spec.get("hole_min", 0), hole_tol=spec.get("hole_tolerance", 14.0), peel=spec.get("peel", 0))
    fg = keep_main(fg)
    S = int(spec.get("large_scale", 2))        # cells to output pixels: 2 for the 5 px-cell pictures, 1 for a picture whose head is more than 30 cells
    fw, fh = 128 // S, 160 // S
    if "frame" not in spec:
        # auto framing: the head's top near the top of the 160-row frame (AW2's top margin is a few pixels), the frame centred on the upper body's mass
        ys, xs = np.where(fg)
        top = int(ys.min())
        band = fg[top: top + fh]
        cx = int(round(np.where(band)[1].mean()))
        spec = {**spec, "frame": [cx - fw // 2, top - 2]}
    x0, y0 = spec["frame"]
    for key in ("mug", "eyes"):
        if key not in spec:
            raise SystemExit(f"{path}: the framing file needs `{key}` (native cells of the picture; `aw2dev co portrait grid` numbers them)")
    mx0, my0 = spec["mug"]
    # the mug's own scale: 2 (a 24-cell square, the default of the 5 px-cell pictures) or 1 (a 48-cell square: a picture drawn with finer cells, whose whole head is more than 24 of them)
    MS = int(spec.get("mug_scale", S))
    ms = 48 // MS
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
    full = quantise(nat, fg, pal[:14], spec.get("match", "luma"))      # art repal hook: the framing file's `match`
    if spec.get("despeckle"):
        full = despeckle_dark(full, pal[:14], int(spec["despeckle"]))
    full = ring(fg, full, diagonal=bool(spec.get("outline_diagonal")))
    # the ring is index 15; nothing else uses index 15 (the palette has 14 clusters, indexes 1..14)
    pal16 = [(0, 0, 0)] + pal[:14] + [pal[14]]
    ex = lambda a, sl: np.kron(a[sl], np.ones((S, S), np.uint8))
    L = ex(full, fr)
    nface = drop_orphan_outline(full[mu])
    face = np.kron(nface, np.ones((MS, MS), np.uint8))
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
    im.mini = I.mini_strip(face, eym)
    im.hud = I._window(face, exm - 16, eym - 6, 32, 16)
    # the framing file's coordinates for the expression edits are native cells of the (mirrored) grid; the mug square is `ms` cells at scale k
    im.spec = {**spec, "face": [mx0, my0, ms]}
    # expressions: a real picture of the same CO (`<id>_<expression>.jpg|png` beside the source, drawn on the same grid and framing) or, by default, the neutral face unedited
    for kind in ("happy", "sad", "angry"):
        other = _expression_picture(path, kind)
        if other is None:
            im.faces[kind] = face.copy()
            continue
        nat2 = native(np.array(Image.open(other).convert("RGB")), detect_grid(np.array(Image.open(other).convert("RGB"))))
        if spec.get("flip"):
            nat2 = nat2[:, ::-1].copy()
        fg2, _ = cut_background(nat2, spec.get("bg_tolerance", 9.0))
        fg2 = np.pad(keep_main(fg2), P, constant_values=False)
        nat2 = np.pad(nat2, ((P, P), (P, P), (0, 0)), mode="edge")
        f2 = ring(fg2, quantise(nat2, fg2, pal[:14], spec.get("match", "luma")), diagonal=bool(spec.get("outline_diagonal")))      # art repal hook
        im.faces[kind] = np.kron(drop_orphan_outline(f2[mu]), np.ones((MS, MS), np.uint8))
    return im


def _expression_picture(path, kind):
    """art-src/cos/<id>_<kind>.jpg|png beside <id>_v5.jpg (the owner's own expression picture), or None."""
    from pathlib import Path
    path = Path(path)
    stem = path.stem.rsplit("_", 1)[0]
    for ext in (".png", ".jpg", ".jpeg"):
        q = path.with_name(f"{stem}_{kind}{ext}")
        if q.exists():
            return q
    return None


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
