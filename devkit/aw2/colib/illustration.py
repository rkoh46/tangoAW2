"""`aw2dev co portrait import` for an **illustration**: a clean full-body drawing on a white (or any flat light) background that is NOT upscaled pixel art (Asuka's `art-src/cos/asuka_v1.jpg`,
1136 x 1744). `illustration = true` in the framing file (`art-src/cos/<id>_v1.toml`) or `--illustration` selects it; docs/dev/co-kit.md has the method and the framing keys.

Nothing is drawn, stylised or retouched. The steps are the ones any downscale of a drawing to AW2's CO art needs:
1. **Background cut**: a flood fill from the picture's border over pixels within `bg_tolerance` (default 22, a distance in RGB from the border's median colour) of the background; gaps of the pure
   background colour (`hole_tolerance` 6) of at least `hole_min` (100) pixels enclosed by the figure (the gap between an arm and the body) go too. The off-white inside the figure (eye whites, a highlight) stays. Specks (components below `min_area` source pixels) go.
2. **Soft edge**: the silhouette is the coverage (area average) of the cut figure in each output pixel, opaque from 0.5 up; the colour of an output pixel is the Lanczos (or `resample = "area"`) average of the
   figure's own pixels only (the figure's mask eroded by `halo` source pixels first, so the white halo of an anti-aliased edge does not bleed into the dark outline of the cloth).
3. **Frame**: `scale` output pixels per source pixel, `frame = [x, y]` the source pixel at the output's top left (waist-up like AW2's figures: head 45 to 65 px); `mug = [x, y, size]` the source square of
   the head for the 48 x 48 faces (the 32 x 24 mini and the 32 x 16 HUD face are windows of it round `eyes = [x1, y1, x2, y2]`, cut at the same scale, so nothing is resampled twice). `flip = true` mirrors the picture so
   the CO faces right as AW2's do (all coordinates are of the mirrored picture).
4. **One palette** of at most 15 colours + transparent (index 15 is AW2's outline `201820`): k-means in Lab over the figure's and the mug's pixels (the mug weighs `face_weight` x 3), the pixels weighted so
   that rare colours (a gold button, a red scarf) are not swallowed by the big flat ones (`rare = 0.5` is the exponent of the colour-bin counts the weight divides by), snapped to 5 bits per channel, lightest first.
   No dithering: each pixel takes its nearest colour; isolated pixels are removed; the outline is drawn one pixel wide round the silhouette.
Expressions: the neutral face in every slot (the owner supplies real expression pictures or none)."""
import collections
import numpy as np
from PIL import Image


def _flood(cand, seeds):
    """The 4-connected pixels of `cand` (bool h x w) reachable from the seed pixels `seeds` (list of (y, x)): a queue, one pass."""
    h, w = cand.shape
    flat = cand.ravel()
    seen = np.zeros(h * w, bool)
    q = collections.deque()
    for y, x in seeds:
        i = y * w + x
        if flat[i] and not seen[i]:
            seen[i] = True
            q.append(i)
    while q:
        i = q.popleft()
        y, x = divmod(i, w)
        if x > 0 and flat[i - 1] and not seen[i - 1]:
            seen[i - 1] = True
            q.append(i - 1)
        if x < w - 1 and flat[i + 1] and not seen[i + 1]:
            seen[i + 1] = True
            q.append(i + 1)
        if y > 0 and flat[i - w] and not seen[i - w]:
            seen[i - w] = True
            q.append(i - w)
        if y < h - 1 and flat[i + w] and not seen[i + w]:
            seen[i + w] = True
            q.append(i + w)
    return seen.reshape(h, w)


def _components(mask):
    """-> label image (0 background, 1.. components, 4-connected) and the areas."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    areas = [0]
    n = 0
    for i in np.flatnonzero(mask.ravel()):
        y, x = divmod(int(i), w)
        if lab[y, x]:
            continue
        n += 1
        comp = _flood(mask & (lab == 0), [(y, x)])
        lab[comp] = n
        areas.append(int(comp.sum()))
    return lab, areas


def _erode(m, r):
    out = m.copy()
    for _ in range(r):
        s = out.copy()
        s[1:, :] &= out[:-1, :]
        s[:-1, :] &= out[1:, :]
        s[:, 1:] &= out[:, :-1]
        s[:, :-1] &= out[:, 1:]
        out = s
    return out


def cut_background(rgb, tol=22.0, min_area=400, hole_tol=6.0, hole_min=100):
    """rgb: float h x w x 3 -> (foreground bool h x w, background colour). Flood from every border pixel over the pixels within `tol` of the border's median colour; enclosed gaps of the pure
    background colour (within `hole_tol`, at least `hole_min` pixels) go too; what is left is the figure (components below `min_area` pixels, the specks of a JPEG's noise, go)."""
    h, w, _ = rgb.shape
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, axis=0)
    near = np.sqrt(((rgb - bg) ** 2).sum(2)) < tol
    seeds = [(0, x) for x in range(w)] + [(h - 1, x) for x in range(w)] + [(y, 0) for y in range(h)] + [(y, w - 1) for y in range(h)]
    back = _flood(near, seeds)
    # gaps of the same pure background colour enclosed by the figure (between an arm and the body, between the hair and the neck) are background too; the off-white of an eye or a highlight is
    # never that pure, and a hole must be `hole_min` pixels big
    pure = np.sqrt(((rgb - bg) ** 2).sum(2)) < hole_tol
    lab, areas = _components(pure & ~back)
    holes = np.zeros_like(back)
    for k, a in enumerate(areas):
        if k and a >= hole_min:
            holes |= lab == k
    if holes.any():
        # the light fringe round a gap (the edge's anti-aliasing against the white) is background too: grow each gap over the pixels within `tol`
        seeds = [tuple(p) for p in np.argwhere(holes)]
        back |= _flood(near | holes, seeds)
    fg = ~back
    lab, areas = _components(fg)
    keep = np.array([k > 0 and a >= min_area for k, a in enumerate(areas)])
    return keep[lab], bg


def _resize(chan, box, size, method):
    im = Image.fromarray(chan.astype(np.float32), mode="F")
    return np.array(im.resize(size, Image.LANCZOS if method == "lanczos" else Image.BOX, box=box))


def fill_outside(rgb, valid, passes):
    """Extend the colours of the `valid` pixels outwards, one pixel a pass (each empty pixel takes the mean of its valid 4-neighbours): so that a Lanczos kernel reaching past the figure's edge
    reads the figure's own colours there and not the background's."""
    out = rgb.copy()
    ok = valid.copy()
    for _ in range(passes):
        if ok.all():
            break
        acc = np.zeros_like(out)
        cnt = np.zeros(ok.shape, np.float32)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            m = np.zeros_like(ok)
            v = np.zeros_like(out)
            ys, yd = slice(max(0, dy), ok.shape[0] + min(0, dy)), slice(max(0, -dy), ok.shape[0] + min(0, -dy))
            xs, xd = slice(max(0, dx), ok.shape[1] + min(0, dx)), slice(max(0, -dx), ok.shape[1] + min(0, -dx))
            m[ys, xs] = ok[yd, xd]
            v[ys, xs] = out[yd, xd]
            acc += v * m[:, :, None]
            cnt += m
        fill = ~ok & (cnt > 0)
        out[fill] = acc[fill] / cnt[fill][:, None]
        ok = ok | fill
    return out


def region(rgb, fg, colour_mask, box, size, method="lanczos"):
    """The source rectangle `box` = (x0, y0, x1, y1) scaled to `size` = (w, h): (rgb float h x w x 3, coverage 0..1). The coverage is the area average of the figure. The colour is the area average of
    the figure's own pixels (`colour_mask`, premultiplied, so nothing but the figure shows in it); with `method = "lanczos"` it is the Lanczos average wherever the whole footprint is the figure's own
    (a sharper picture: the eyes, the buttons), the area average at the edges (a Lanczos kernel there overshoots)."""
    cov = _resize(fg.astype(np.float32), box, size, "area")
    cm = colour_mask.astype(np.float32)
    den = np.maximum(_resize(cm, box, size, "area"), 1e-4)
    area = np.stack([_resize(rgb[:, :, c] * cm, box, size, "area") / den for c in range(3)], axis=2)
    if method != "lanczos":
        return np.clip(area, 0, 255), cov
    reach = int(3 * max(box[2] - box[0], box[3] - box[1]) / max(size) + 2)
    filled = fill_outside(rgb, colour_mask, reach)
    lan = np.stack([_resize(filled[:, :, c], box, size, "lanczos") for c in range(3)], axis=2)
    inner = (den > 0.97)[:, :, None]
    return np.clip(np.where(inner, lan, area), 0, 255), cov


def rare_weights(rgb, power=0.5, bin=10.0):
    """1 / count^power of the pixel's Lab bin: a rare colour weighs as much as a big flat one up to `power`."""
    from . import importer as I
    lab = I.to_lab(rgb)
    key = np.floor(lab / bin).astype(np.int64) + 60
    k = key[:, 0] * 1000000 + key[:, 1] * 1000 + key[:, 2]
    u, inv, cnt = np.unique(k, return_inverse=True, return_counts=True)
    return 1.0 / cnt[inv] ** power


def palette_for(px, wt, k=14, dark_k=3, dark_l=32.0, outline=(32, 24, 32), ramp=6.5):
    """k colours + the outline: `dark_k` of the k for the dark pixels (Lab lightness below `dark_l`: black cloth and hair, which would otherwise merge into one flat brown), the rest for everything else
    (weighted k-means in Lab each). -> 15 RGB, lightest first, the outline last."""
    from . import importer as I
    lab = I.to_lab(px.astype(float))
    dark = lab[:, 0] < dark_l
    parts = []
    for sel, n in ((dark, dark_k), (~dark, k - dark_k)):
        if sel.sum() == 0:
            continue
        l = lab[sel]
        w = wt[sel].astype(float)
        n = min(n, len(np.unique(l.round(1), axis=0)))
        parts.append(I.kmeans(l, w, n, iters=40, seed=5))
    cent = np.concatenate(parts)
    # the uniform's own dark ramp: its tones sit above the outline's lightness by at least `ramp` (6, 13 and 20 Lab lightness steps up from the outline's), keeping their hue, so the outline reads against
    # black cloth and hair as it does on Hawke's dark coat (a downscaled black is as dark as the outline and the two blend)
    ol = I.to_lab(np.array([outline], float))[0]
    if dark_k:
        darks = sorted([i for i in range(len(cent)) if cent[i][0] < dark_l], key=lambda i: cent[i][0])
        for rank, i in enumerate(darks):
            cent[i][0] = max(cent[i][0], ol[0] + ramp * (rank + 1))
    rgb = I.snap555(I.lab_to_rgb(cent))
    cols = [tuple(int(v) for v in c) for c in rgb]
    cols.sort(key=lambda c: -(0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]))
    while len(cols) < k:
        cols.append(cols[-1])
    return cols[:k] + [tuple(int(v) for v in I.snap555(np.array(outline, float)))]


def smooth_edge(m):
    """The silhouette's fringe off: a pixel with fewer than two 4-neighbours in the figure (a one-pixel spike or a corner of the downscale's anti-aliasing) goes, an empty pixel with three comes in."""
    def count(a):
        n = np.zeros(a.shape, np.int8)
        n[1:, :] += a[:-1, :]
        n[:-1, :] += a[1:, :]
        n[:, 1:] += a[:, :-1]
        n[:, :-1] += a[:, 1:]
        return n
    m = m & ~(count(m) < 2)
    m = m | (~m & (count(m) >= 3))
    return m


def ring8(m, idx):
    """The outline (index 15), one pixel wide and unbroken in 8-connectivity, on every empty pixel next to the figure including its diagonal corners."""
    out = idx.copy()
    near = np.zeros_like(m)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                near |= I_shift(m, dx, dy)
    out[near & ~m] = 15
    return out


def I_shift(a, dx, dy):
    o = np.zeros_like(a)
    h, w = a.shape
    ys, yd = slice(max(0, dy), h + min(0, dy)), slice(max(0, -dy), h + min(0, -dy))
    xs, xd = slice(max(0, dx), w + min(0, dx)), slice(max(0, -dx), w + min(0, -dx))
    o[ys, xs] = a[yd, xd]
    return o


def families(pal):
    """The palette's 14 colours by material: 0 dark (black cloth, hair), 1 skin, 2 red, 3 white / grey (metal, eye whites), 4 brown / gold. -> (family per index 1..14, mean lightness per family)."""
    from . import importer as I
    lab = I.to_lab(np.array(pal, float))
    fam = []
    for L, a, b in lab:
        chroma = (a * a + b * b) ** 0.5
        hue = np.degrees(np.arctan2(b, a)) % 360
        if L < 36:
            fam.append(0)
        elif chroma < 10:
            fam.append(3)
        elif L >= 60 and 20 <= hue <= 80:
            fam.append(1)
        elif chroma >= 25 and (hue < 25 or hue > 330):
            fam.append(2)
        else:
            fam.append(4)
    return fam, lab[:, 0]


def seams(idx, pal14, min_body=14):
    """Where two materials meet (skin / collar, neckerchief / uniform, hand / sleeve, book edge) a one-pixel line in the darker material's shadow tone, on the lighter material's pixel: the way AW2's own figures
    have a dark seam between cloth and cloth. Only where the lighter material has body there (at least `min_body` of the 25 pixels round the pixel are its own): an eye's white or a button is not cut."""
    fam, lum = families(pal14)
    fam = np.array(fam)
    h, w = idx.shape
    out = idx.copy()
    f = np.full(idx.shape, -1)
    inner = (idx >= 1) & (idx <= 14)
    f[inner] = fam[idx[inner] - 1]
    fam_l = {k: lum[fam == k].mean() for k in set(fam.tolist())}
    shadow = {k: 1 + int(np.argmin(np.where(fam == k, lum, 1e9))) for k in fam_l}
    for y in range(1, h - 1):
        for x in range(1, w - 1):
            a = f[y, x]
            if a < 0:
                continue
            best = None
            for dy, dx in ((0, 1), (1, 0), (0, -1), (-1, 0)):
                b = f[y + dy, x + dx]
                if b >= 0 and b != a and fam_l[b] < fam_l[a]:
                    best = b
            if best is None:
                continue
            win = f[max(0, y - 2):y + 3, max(0, x - 2):x + 3]
            if (win == a).sum() < min_body or (win == best).sum() < min_body:
                continue          # both materials need body here: a seam between two big areas, not an edge of a detail
            out[y, x] = shadow[best]
    return out


def styled(spec, path):
    from . import importer as I, pixelart as P
    img = np.array(Image.open(path).convert("RGB")).astype(np.float32)
    if spec.get("flip"):
        img = img[:, ::-1].copy()
    fg, bg = cut_background(img, spec.get("bg_tolerance", 22.0), spec.get("min_area", 400), spec.get("hole_tolerance", 6.0), spec.get("hole_min", 100))
    colour_mask = _erode(fg, spec.get("halo", 2))
    method = spec.get("resample", "lanczos")
    s = float(spec.get("scale", 0.2))
    fx, fy = spec.get("frame", [0, 0])
    for key in ("mug", "eyes"):
        if key not in spec:
            raise SystemExit(f"{path}: the framing file needs `{key}` (source pixels of the picture, of the mirrored picture when `flip`)")
    # the large art: 128 x 160 output pixels from (128 / s) x (160 / s) source pixels at (fx, fy); a frame reaching past the picture is padded with background
    pad = int(160 / s)
    imgp = np.pad(img, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
    fgp = np.pad(fg, pad, constant_values=False)
    cmp_ = np.pad(colour_mask, pad, constant_values=False)
    box = (fx + pad, fy + pad, fx + pad + 128 / s, fy + pad + 160 / s)
    L, C = region(imgp, fgp, cmp_, box, (128, 160), method)
    mx, my, ms = spec["mug"]
    mbox = (mx + pad, my + pad, mx + pad + ms, my + pad + ms)
    M, MC = region(imgp, fgp, cmp_, mbox, (48, 48), method)
    # one palette: the figure's pixels and the mug's (weighing more: small, and they carry the eyes)
    px, wt = [], []
    for r, c, base in ((L, C, 1.0), (M, MC, spec.get("face_weight", 3.0))):
        v = r[c >= 0.5]
        px.append(v)
        wt.append(rare_weights(v, spec.get("rare", 0.5)) * base)
    px, wt = np.concatenate(px), np.concatenate(wt)
    pal = palette_for(px, wt, dark_k=spec.get("dark_colours", 3), dark_l=spec.get("dark_below", 32.0), outline=tuple(spec.get("outline", (32, 24, 32))))

    def index(r, c, bottom_cut, with_seams=True):
        m = smooth_edge(I.clean_silhouette(c >= 0.5))          # a hard silhouette: the coverage cut at one half, its spikes and fringe off
        idx = P.quantise(r, m, pal[:14])
        idx = I.despeckle(idx)
        if with_seams and spec.get("seams", True):
            idx = seams(idx, pal[:14])
        return ring8(m, idx)
    im = I.Imported()
    im.spec = spec
    im.palette = [(0, 0, 0)] + pal[:14] + [pal[14]]
    im.large = index(L, C, True)
    face = index(M, MC, False, with_seams=False)          # (no seams on the faces: the eyes and the brows are already the lines)
    im.faces["normal"] = face
    e = spec["eyes"]
    k = 48.0 / ms
    ex, ey = round(((e[0] + e[2]) / 2 - mx) * k), round(((e[1] + e[3]) / 2 - my) * k)
    im.eye = (ex, ey)
    im.mini = I.mini_strip(face, ey)
    im.hud = I._window(face, ex - 16, ey - 6, 32, 16)
    for kind in ("happy", "sad", "angry"):
        im.faces[kind] = face.copy()
    return im
