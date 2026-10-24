"""`co portrait stylise` (docs/dev/co-kit.md): the supplied painterly picture is the **design reference**; the CO's art is redrawn in AW2's own CO style from it. The picture's materials (skin, hair, gold,
red cloth, white cloth, steel ...) are found by colour from seed points (`[[material]]` in the picture's framing file), each material is flattened to 2 to 4 flat tones of the CO's own AW2-like
palette (`[palette]`, AW2's layout: index 1 white, 2..6 skin, 7..14 the CO's colours, 15 the outline), noise and texture are removed, the outline and the simple interior lines are redrawn, and the eyes are
drawn again. The numbers of AW2's style (brightness, saturation, flatness, regions) are in `style.py` and are what `co portrait lint --style aw2` checks."""
import numpy as np
from PIL import Image, ImageFilter
from . import importer as I


def hexrgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def seeds_lab(src, mats):
    lab_src = None
    out = []
    for k, m in enumerate(mats):
        for (x, y) in m["points"]:
            patch = src.rgb[max(0, y - 4):y + 5, max(0, x - 4):x + 5].reshape(-1, 3)
            out.append((k, np.median(patch, axis=0)))
    ks = np.array([k for k, _ in out])
    cols = np.array([c for _, c in out])
    return ks, I.to_lab(cols)


def classify(src, mats, chunk=60):
    """Material index per source pixel (-1 where there is no figure): nearest seed colour in Lab, lightness weighed a little less than colour."""
    ks, sl = seeds_lab(src, mats)
    w = np.array([0.55, 1.0, 1.0])
    h, wd = src.alpha.shape
    out = np.full((h, wd), -1, np.int16)
    for y0 in range(0, h, chunk):
        blk = src.rgb[y0:y0 + chunk]
        lab = I.to_lab(blk.reshape(-1, 3))
        d = (((lab[:, None, :] - sl[None]) * w) ** 2).sum(2)
        out[y0:y0 + chunk] = ks[d.argmin(1)].reshape(blk.shape[0], wd)
    out[~src.alpha] = -1
    return out


def box(a, x0, y0, bw, bh, ow, oh):
    im = Image.fromarray(a.astype(np.float32), mode="F")
    return np.array(im.resize((ow, oh), Image.BOX, box=(x0, y0, x0 + bw, y0 + bh)))


def mode_filter(idx, passes=1, keep=(0,), radius=1):
    """The commonest value in each pixel's neighbourhood (a flat colour region keeps its shape, noise goes); `keep` values (transparent) are never changed or spread."""
    h, w = idx.shape
    for _ in range(passes):
        out = idx.copy()
        for y in range(h):
            for x in range(w):
                if idx[y, x] in keep:
                    continue
                win = idx[max(0, y - radius):y + radius + 1, max(0, x - radius):x + radius + 1].ravel()
                win = win[~np.isin(win, keep)]
                vals, cnt = np.unique(win, return_counts=True)
                best = vals[cnt.argmax()]
                if cnt.max() > cnt[vals == idx[y, x]].max() + 1:
                    out[y, x] = best
        idx = out
    return idx


def flatten(src, mats, pal, x0, y0, bw, bh, ow, oh, spec, outline_idx=15, tone_curve=None):
    """The region (x0, y0, bw, bh) of the source as flat-toned AW2-style indexes ow x oh (0 transparent)."""
    cls = classify(src, mats)
    cov = box(src.alpha.astype(np.float32), x0, y0, bw, bh, ow, oh)
    lum = src.rgb @ np.array([0.299, 0.587, 0.114])
    lum_t = box(lum * src.alpha, x0, y0, bw, bh, ow, oh) / np.maximum(cov, 1e-6)
    votes = np.stack([box(((cls == k)).astype(np.float32), x0, y0, bw, bh, ow, oh) for k in range(len(mats))])
    mat = votes.argmax(0)
    mat[cov < 0.5] = -1
    idx = np.zeros((oh, ow), np.uint8)
    # tone: each material's own lightness split by percentiles into its tones (hard edges)
    smooth = np.array(Image.fromarray(lum_t.astype(np.float32), mode="F").filter(ImageFilter.GaussianBlur(0.6))) if False else lum_t
    for k, m in enumerate(mats):
        sel = mat == k
        if not sel.any():
            continue
        tones = m["tones"]
        v = smooth[sel]
        cuts = m.get("cuts") or [100 * (i + 1) / len(tones) for i in range(len(tones) - 1)]
        th = np.percentile(v, cuts)
        t = np.searchsorted(th, v)               # 0 darkest .. len(tones)-1 lightest
        idx[sel] = np.array([tones[len(tones) - 1 - int(i)] for i in t], np.uint8)
    return idx, mat


def line_art(idx, mat, mats, outline_idx=15, sides=(True, True, True, False)):
    """The outline round the figure, and a line (the material's darkest tone, or the outline for hair and cloth against skin) where two materials meet: drawn on the lower-priority material's side so a line is one pixel."""
    h, w = idx.shape
    out = idx.copy()
    pri = [m.get("priority", 5) for m in mats]
    for y in range(h):
        for x in range(w):
            k = mat[y, x]
            if k < 0:
                continue
            for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                yy, xx = y + dy, x + dx
                if 0 <= yy < h and 0 <= xx < w and mat[yy, xx] >= 0 and mat[yy, xx] != k and pri[k] < pri[mat[yy, xx]]:
                    out[y, x] = mats[k].get("line", outline_idx)
                    break
    return I.outline(out, sides), mat


def eye_pass(src, spec, idx, x0, y0, bw, bh, ow, oh, offx, offy, white=1, dark=15, dark_floor=None):
    """The eyes keep their whites and darks (max-pooling inside each eye's box: a 3-pixel catchlight is not averaged away): white pixels become index 1, dark ones the outline's."""
    lum = src.rgb.mean(2)
    wmask = ((lum > 165) & (src.rgb.max(2) - src.rgb.min(2) < 60) & src.alpha).astype(np.float32)
    dmask = ((lum < 55) & src.alpha).astype(np.float32)
    out = idx.copy()
    e = spec["eyes"]
    k = ow / bw
    for (cx, cy, rx, ry) in ((e[0], e[1], 52, 24), (e[2], e[3], 52, 24)):
        wf, df = box(wmask, x0, y0, bw, bh, ow, oh), box(dmask, x0, y0, bw, bh, ow, oh)
        ax0, ax1 = int((cx - rx - x0) * k), int((cx + rx - x0) * k) + 1
        ay0, ay1 = int((cy - ry - y0) * k), int((cy + ry - y0) * k) + 1
        for y in range(max(0, ay0), min(oh, ay1)):
            for x in range(max(0, ax0), min(ow, ax1)):
                yy, xx = y + offy, x + offx
                if not (0 <= yy < out.shape[0] and 0 <= xx < out.shape[1]) or out[yy, xx] == 0:
                    continue
                if wf[y, x] > spec.get("eye_white", 0.22) and df[y, x] < 0.5:
                    out[yy, xx] = white
                elif df[y, x] > spec.get("eye_dark", 0.45):
                    out[yy, xx] = dark
    return out


def gauss(a, sigma):
    """A separable Gaussian blur (edge-replicated)."""
    r = int(3 * sigma) + 1
    k = np.exp(-np.arange(-r, r + 1) ** 2 / (2 * sigma ** 2))
    k /= k.sum()
    p = np.pad(a, r, mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 0, p)
    p = np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), 1, p)
    return p


def crease_pass(src, spec, idx, x0, y0, bw, bh, ow, oh, offx, offy):
    """Thin dark features of the face (the mouth line, the nose's shadow, the jaw, the eyelids) are kept: where a skin-zone pixel is darker than its surroundings by `crease` lightness points
    (the area-averaged source minus its blur), it takes the dark skin tone `crease_index`."""
    zs = [z for z in spec.get("zone", []) if z.get("exclusive")]
    if not zs:
        return idx
    rgb, cov = src.region(x0, y0, bw, bh, ow, oh)
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    blur = gauss(lum, spec.get("crease_radius", 1.8))
    zone = zone_mask(src, zs[0]["polys"], x0, y0, bw, bh, ow, oh)
    out = idx.copy()
    for y in range(oh):
        for x in range(ow):
            yy, xx = y + offy, x + offx
            if zone[y, x] and 0 <= yy < out.shape[0] and 0 <= xx < out.shape[1] and out[yy, xx] in (2, 3, 4) and lum[y, x] - blur[y, x] < -spec.get("crease", 9):
                out[yy, xx] = spec.get("crease_index", 5)
    return out


def zone_lines(src, spec, idx, x0, y0, bw, bh, ow, oh, offx, offy):
    """A line (`line` = the palette index) round a zone's edge, drawn on the outside pixels that touch it: the jaw, the hairline, the ear: the simple interior line art of AW2's faces."""
    out = idx.copy()
    for z in spec.get("zone", []):
        li = z.get("line")
        if not li:
            continue
        m = zone_mask(src, z["polys"], x0, y0, bw, bh, ow, oh)
        near = np.zeros_like(m)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            near |= I.shift(m, dx, dy)
        edge = near & ~m
        for y, x in zip(*np.nonzero(edge)):
            yy, xx = y + offy, x + offx
            if 0 <= yy < out.shape[0] and 0 <= xx < out.shape[1] and out[yy, xx] not in (0, 1):
                out[yy, xx] = li
    return out


def mouth_pass(src, spec, idx, x0, y0, bw, bh, ow, oh, offx, offy, dark_idx=5, line_idx=15):
    """The mouth keeps its line: dark strokes inside the mouth's box (max-pooled, like the eyes) become the dark skin tone (a lip line) or the outline for the darkest."""
    lum = src.rgb.mean(2)
    dmask = ((lum < spec.get("mouth_dark", 95)) & src.alpha).astype(np.float32)
    df = box(dmask, x0, y0, bw, bh, ow, oh)
    k = ow / bw
    mx, my = spec["mouth"]
    out = idx.copy()
    rx, ry = spec.get("mouth_box", [46, 14])
    for y in range(max(0, int((my - ry - y0) * k)), min(oh, int((my + ry - y0) * k) + 1)):
        for x in range(max(0, int((mx - rx - x0) * k)), min(ow, int((mx + rx - x0) * k) + 1)):
            yy, xx = y + offy, x + offx
            if 0 <= yy < out.shape[0] and 0 <= xx < out.shape[1] and out[yy, xx] != 0 and df[y, x] > spec.get("mouth_frac", 0.3):
                out[yy, xx] = dark_idx
    return out


def styled(spec, src):
    """-> Imported with the AW2-style art."""
    mats = spec.get("material") or []
    pal = [(0, 0, 0)] + [tuple(int(v) for v in I.snap555(np.array(hexrgb(c), float))) for c in spec["palette"]]      # (snapped to the GBA's 5 bits, as the game shows them)
    assert len(pal) == 16, "the palette has 15 colours: index 1 white, 2..6 skin, 7..14 the CO's, 15 the outline"
    cut = spec.get("crop_top", 0)
    s = spec.get("scale", 0.135)
    ow, oh = round(src.w * s), round((src.h - cut) * s)
    top = spec.get("top", 3)
    ox = (128 - ow) // 2 + spec.get("dx", 0)
    if mats:
        idx_l, mat_l = flatten(src, mats, pal, 0, cut, src.w, src.h - cut, ow, oh, spec)
    else:
        idx_l, _ = flatten_palette(src, pal, 0, cut, src.w, src.h - cut, ow, oh, spec, spec.get("flat_radius", 1), spec.get("flat_passes", 2))
        mat_l = np.where(idx_l > 0, 0, -1).astype(np.int16)
    L = np.zeros((160, 128), np.uint8)
    M = np.full((160, 128), -1, np.int16)
    ys, xs = slice(top, min(160, top + oh)), slice(max(0, ox), min(128, ox + ow))
    sx0 = max(0, -ox)
    L[ys, xs] = idx_l[: ys.stop - top, sx0: sx0 + (xs.stop - xs.start)]
    M[ys, xs] = mat_l[: ys.stop - top, sx0: sx0 + (xs.stop - xs.start)]
    fx, fy, fs = spec["face"]
    if mats:
        idx_f, mat_f = flatten(src, mats, pal, fx, fy, fs, fs, 48, 48, spec)
    else:
        idx_f, _ = flatten_palette(src, pal, fx, fy, fs, fs, 48, 48, spec, 1, spec.get("face_flat_passes", 0))
        mat_f = np.where(idx_f > 0, 0, -1).astype(np.int16)
    im = I.Imported()
    im.spec = spec
    im.palette = pal
    L = eye_pass(src, spec, L, 0, cut, src.w, src.h - cut, ow, oh, max(0, ox), top)
    idx_f = eye_pass(src, spec, idx_f, fx, fy, fs, fs, 48, 48, 0, 0)
    idx_f = crease_pass(src, spec, idx_f, fx, fy, fs, fs, 48, 48, 0, 0)
    L = crease_pass(src, spec, L, 0, cut, src.w, src.h - cut, ow, oh, max(0, ox), top)
    keepmask = I.clean_silhouette(L != 0, min_speck=40, max_hole=4)      # specks of the background's texture and pinholes
    L[~keepmask] = 0
    L = mode_filter(L, 1, keep=(0, 1, 15))
    idx_f = mode_filter(idx_f, 1, keep=(0, 1, 15))
    L = zone_lines(src, spec, L, 0, cut, src.w, src.h - cut, ow, oh, max(0, ox), top)
    idx_f = zone_lines(src, spec, idx_f, fx, fy, fs, fs, 48, 48, 0, 0)
    L = I.outline(L, (True, True, True, False))
    mug = I.outline(idx_f, (True, True, True, False))
    im.large = L
    im.faces["normal"] = mug
    k = 48.0 / fs
    e = spec["eyes"]
    ex, ey = round(((e[0] + e[2]) / 2 - fx) * k), round(((e[1] + e[3]) / 2 - fy) * k)
    im.eye = (ex, ey)
    im.mini = I._window(mug, ex - 16, ey - 10, 32, 24)
    im.hud = I._window(mug, ex - 16, ey - 6, 32, 16)
    return im


# --- clusters: the picture's own colours, grouped; the framing file says which material each group is ---------------------------------------------------------------------------

def clusters(src, k=24, seed=5):
    """K colour groups of the figure (k-means in Lab, lightness weighed less), ordered by lightness: (label map, mean RGB per group). Deterministic."""
    ys, xs = np.nonzero(src.alpha)
    sel = np.random.default_rng(seed).choice(len(ys), size=min(60000, len(ys)), replace=False)
    pts = src.rgb[ys[sel], xs[sel]]
    w = np.array([0.6, 1.0, 1.0])
    lab = I.to_lab(pts) * w
    cent = I.kmeans(lab, np.ones(len(lab)), k, iters=25, seed=seed)
    order = np.argsort(cent[:, 0])
    cent = cent[order]
    out = np.full(src.alpha.shape, -1, np.int16)
    h, wd = src.alpha.shape
    for y0 in range(0, h, 60):
        blk = src.rgb[y0:y0 + 60]
        l = I.to_lab(blk.reshape(-1, 3)) * w
        d = ((l[:, None, :] - cent[None]) ** 2).sum(2)
        out[y0:y0 + 60] = d.argmin(1).reshape(blk.shape[0], wd)
    out[~src.alpha] = -1
    means = [src.rgb[out == i].mean(0) if (out == i).any() else np.zeros(3) for i in range(k)]
    return out, np.array(means)


def classify_clusters(src, spec, mats):
    """Material index per pixel from the framing file's `cluster = {id = "material"}` (a cluster not listed takes the material of the listed cluster nearest in colour)."""
    k = spec.get("clusters", 24)
    cl, means = clusters(src, k)
    names = [m["name"] for m in mats]
    table = {int(c): names.index(n) for c, n in spec["cluster"].items()}
    lab = I.to_lab(means)
    mapping = np.zeros(k, np.int16)
    for c in range(k):
        if c in table:
            mapping[c] = table[c]
        else:
            best = min(table, key=lambda t: ((lab[c] - lab[t]) ** 2).sum())
            mapping[c] = table[best]
    out = np.where(cl >= 0, mapping[np.maximum(cl, 0)], -1).astype(np.int16)
    return out


def cluster_sheet(src, spec):
    """A picture of the clusters: the figure in flat group colours with each group's number, and a legend of swatches (for writing `cluster = {...}`)."""
    from PIL import ImageDraw
    k = spec.get("clusters", 24)
    cl, means = clusters(src, k)
    rng = np.random.default_rng(1)
    pal = rng.integers(40, 255, (k, 3))
    img = np.zeros(cl.shape + (3,), np.uint8)
    for i in range(k):
        img[cl == i] = pal[i]
    im = Image.fromarray(img).resize((392, 584), Image.NEAREST)
    legend = Image.new("RGB", (392, 584), (30, 30, 30))
    d = ImageDraw.Draw(legend)
    for i in range(k):
        y = 6 + (i % 12) * 46
        x = 6 + (i // 12) * 190
        d.rectangle([x, y, x + 40, y + 38], fill=tuple(int(v) for v in pal[i]))
        d.rectangle([x + 46, y, x + 86, y + 38], fill=tuple(int(v) for v in means[i]))
        d.text((x + 92, y + 12), f"#{i}", fill=(255, 255, 255))
    orig = Image.fromarray(src.rgb.astype(np.uint8)).resize((392, 584))
    out = Image.new("RGB", (392 * 3, 584))
    out.paste(orig, (0, 0)), out.paste(im, (392, 0)), out.paste(legend, (784, 0))
    return out


# --- the palette route: every colour of the picture goes to the nearest colour of the CO's own AW2-like palette (after a lift to the game's pitch), then regions are flattened --------------------------------------

def zone_mask(src, polys, x0, y0, bw, bh, ow, oh):
    """A zone (polygons in source pixels) at ow x oh: True where more than half of the pixel is inside."""
    from PIL import ImageDraw
    m = Image.new("L", (src.w, src.h), 0)
    d = ImageDraw.Draw(m)
    for poly in polys:
        d.polygon([tuple(p) for p in poly], fill=255)
    return box(np.array(m) > 0, x0, y0, bw, bh, ow, oh) > 0.5


def lift_lab(lab, gamma, gain, contrast=1.0):
    """Lightness by a gamma (brighter) and a contrast about the middle, chroma by a gain that acts on coloured pixels only (a grey stays grey)."""
    out = lab.copy()
    out[..., 0] = 100 * (np.clip(out[..., 0], 0, 100) / 100) ** gamma
    out[..., 0] = np.clip(50 + (out[..., 0] - 50) * contrast, 0, 100)
    c = np.sqrt(out[..., 1] ** 2 + out[..., 2] ** 2)
    g = 1 + (gain - 1) * np.clip(c / 30.0, 0, 1)
    out[..., 1] *= g
    out[..., 2] *= g
    return out


def flatten_palette(src, pal, x0, y0, bw, bh, ow, oh, spec, flat_radius=1, passes=2):
    """The region as indexes ow x oh: area-averaged, lifted (lightness gamma, chroma gain), each pixel to the nearest palette colour (index 1..14: the outline is not a candidate), then
    flattened by mode filters so a colour region is one flat tone with hard edges. `[[zone]]` (polygons in source pixels, `only` = the palette indexes allowed inside; `exclusive`: nobody
    outside the zone may use them) keep a shadow on the face from becoming gold and a gold plate from becoming skin."""
    rgb, cov = src.region(x0, y0, bw, bh, ow, oh)
    gam, gain = spec.get("lift", [0.72, 1.25])
    lab = lift_lab(I.to_lab(rgb.reshape(-1, 3)), gam, gain, spec.get("contrast", 1.15))
    plab = to_lab_pal(pal[1:16])
    wl = spec.get("lightness_weight", 0.8)
    d = (((lab[:, None, :] - plab[None]) * np.array([wl, 1, 1])) ** 2).sum(2)
    taken = np.zeros(oh * ow, bool)
    banned_outside = np.zeros(15, bool)
    banned_outside[14] = True          # the outline colour is for a zone that lists it (dark hair)
    for z in spec.get("zone", []):
        only = np.zeros(15, bool)
        for t in z["only"]:
            if 1 <= t <= 15:
                only[t - 1] = True
        if z.get("exclusive"):
            for t in z.get("ban", z["only"]):
                if 1 <= t <= 15:
                    banned_outside[t - 1] = True
        m = zone_mask(src, z["polys"], x0, y0, bw, bh, ow, oh).reshape(-1) & ~taken
        d[np.ix_(m, ~only)] += 1e6
        taken |= m
    d[np.ix_(~taken, banned_outside)] += 1e6
    idx = (d.argmin(1) + 1).reshape(oh, ow).astype(np.uint8)
    idx[cov < 0.5] = 0
    idx = mode_filter(idx, passes, keep=(0,), radius=flat_radius)
    return idx, cov


def to_lab_pal(cols):
    return I.to_lab(np.array(cols, float))
