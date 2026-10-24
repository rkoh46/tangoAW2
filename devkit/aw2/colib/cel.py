"""`co portrait import` for the cel route (docs/dev/co-kit.md): the supplied picture is only the **design reference**; the CO is redrawn the way AW2's artists drew theirs.

1. The picture is area-averaged to the output size and smoothed with an edge-preserving (bilateral) filter, which kills the painterly texture and keeps the edges.
2. Every pixel gets a **material** (skin, hair, steel, bronze, red cloth, white cloth ...). The materials and their rules (hue / saturation / value ranges) and the hand-made polygons that force a material
   somewhere are data (`[[material]]` and `[[region]]` in the picture's framing file, `art-src/cos/<co>_user.toml`); nothing is clustered. The label map is cleaned (majority filter, no specks).
3. Each material is shaded with a few flat tones of its **ramp** (palette indexes, dark to light): the shadow shape is the smoothed lightness of the picture, cut by quantiles of that material, then cleaned
   (majority filter, no blobs below a few pixels), so the shapes are big and simple. Metal and hair may carry a highlight.
4. Line art: the silhouette outline, plus a line along the edge of materials marked `outlined` where they meet another material (jaw, plates, laurel): the region boundaries, never the texture.
5. The faces are drawn again on top in AW2's face style (a small stamp for each eye, a brow stroke, a nose notch and a small mouth), for each of the four expressions, in the mug and in the figure.
The figure is mirrored (`flip`) so that the CO looks to the right, as AW2's COs do.

A framing file may hold several `[variant.X]` tables (palette and rendering choices: tones, line weight); `variant=` picks one, `default_variant` is the committed one."""
import numpy as np
from . import importer as I
from .stylise import hexrgb, gauss, zone_mask


# --- colour helpers --------------------------------------------------------------------------------------------------------------------------------------------

def hsv(rgb):
    r, g, b = rgb[..., 0] / 255.0, rgb[..., 1] / 255.0, rgb[..., 2] / 255.0
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 1e-9
    rr = m & (mx == r)
    gg = m & (mx == g) & ~rr
    bb = m & ~rr & ~gg
    h[rr] = 60 * (((g - b)[rr] / d[rr]) % 6)
    h[gg] = 60 * ((b - r)[gg] / d[gg] + 2)
    h[bb] = 60 * ((r - g)[bb] / d[bb] + 4)
    s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    return h, s, mx


def bilateral(lab, valid, radius=2, sigma_s=1.3, sigma_r=12.0, iters=2):
    """Edge-preserving smoothing of a Lab image (h x w x 3) over the valid pixels."""
    h, w, _ = lab.shape
    cur = lab.copy()
    for _ in range(iters):
        pad = radius
        P = np.pad(cur, ((pad, pad), (pad, pad), (0, 0)), mode="edge")
        V = np.pad(valid.astype(float), pad, mode="constant")
        num = np.zeros_like(cur)
        den = np.zeros((h, w))
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nb = P[pad + dy: pad + dy + h, pad + dx: pad + dx + w]
                vv = V[pad + dy: pad + dy + h, pad + dx: pad + dx + w]
                ws = np.exp(-(dx * dx + dy * dy) / (2 * sigma_s ** 2))
                wr = np.exp(-((nb - cur) ** 2).sum(2) / (2 * sigma_r ** 2))
                wt = ws * wr * vv
                num += nb * wt[..., None]
                den += wt
        cur = np.where(valid[..., None], num / np.maximum(den, 1e-9)[..., None], cur)
    return cur


# --- the material map ------------------------------------------------------------------------------------------------------------------------------------------

def _in(v, rng):
    lo, hi = rng
    return (v >= lo) & (v <= hi)


def _hue_in(h, rng):
    lo, hi = rng
    return ((h >= lo) & (h <= hi)) if lo <= hi else ((h >= lo) | (h <= hi))


def label_map(src, spec, rgb, valid, x0, y0, bw, bh, ow, oh):
    """-> (labels int16 (-1 = none), fixed bool) over the materials of the spec."""
    mats = spec["material"]
    names = [m["name"] for m in mats]
    lab = np.full((oh, ow), -1, np.int16)
    h, s, v = hsv(rgb)
    for i, m in enumerate(mats):
        rule = m.get("rule")
        if rule is None:
            continue
        ok = valid & (lab < 0)
        if "hue" in rule:
            ok &= _hue_in(h, rule["hue"])
        if "sat" in rule:
            ok &= _in(s, rule["sat"])
        if "val" in rule:
            ok &= _in(v, rule["val"])
        if m.get("within"):
            ok &= zone_mask(src, m["within"], x0, y0, bw, bh, ow, oh)
        lab[ok] = i
    fb = spec.get("fallback")
    if fb:
        lab[valid & (lab < 0)] = names.index(fb)
    fixed = np.zeros((oh, ow), bool)
    for r in spec.get("region", []):
        zm = zone_mask(src, r["polys"], x0, y0, bw, bh, ow, oh) & valid
        lab[zm] = names.index(r["material"])
        fixed |= zm & bool(r.get("fixed", True))
    lab[~valid] = -1
    return lab, fixed


def majority(lab, fixed, n, passes=2, centre=1.5):
    h, w = lab.shape
    for _ in range(passes):
        pad = np.pad(lab, 1, constant_values=-1)
        counts = np.zeros((n, h, w))
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                nb = pad[1 + dy: 1 + dy + h, 1 + dx: 1 + dx + w]
                wt = centre if (dx == 0 and dy == 0) else 1.0
                for k in range(n):
                    counts[k] += (nb == k) * wt
        best = counts.argmax(0).astype(np.int16)
        change = (lab >= 0) & ~fixed & (counts.max(0) > 0)
        lab = np.where(change, best, lab)
    return lab


def despeckle(idx, grp, min_size=3, protect=()):
    """Components (4-connected, same palette index and same material group) below min_size px take the most common neighbouring index of the same group."""
    h, w = idx.shape
    seen = np.zeros((h, w), bool)
    out = idx.copy()
    for y in range(h):
        for x in range(w):
            if seen[y, x] or idx[y, x] == 0:
                continue
            c, g = idx[y, x], grp[y, x]
            comp, st = [], [(y, x)]
            seen[y, x] = True
            while st:
                a, b = st.pop()
                comp.append((a, b))
                for aa, bb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= aa < h and 0 <= bb < w and not seen[aa, bb] and idx[aa, bb] == c and grp[aa, bb] == g:
                        seen[aa, bb] = True
                        st.append((aa, bb))
            if len(comp) >= min_size or c in protect:
                continue
            cnt = {}
            for a, b in comp:
                for aa, bb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= aa < h and 0 <= bb < w and grp[aa, bb] == g and idx[aa, bb] not in (0, c):
                        cnt[idx[aa, bb]] = cnt.get(idx[aa, bb], 0) + 1
            if cnt:
                best = max(cnt, key=cnt.get)
                for a, b in comp:
                    out[a, b] = best
    return out


def gauss2(a, sx, sy):
    r = lambda sg: np.exp(-np.arange(-(int(3 * sg) + 1), int(3 * sg) + 2) ** 2 / (2 * sg ** 2))
    kx, ky = r(sx), r(sy)
    kx, ky = kx / kx.sum(), ky / ky.sum()
    p = np.pad(a, ((len(ky) // 2, len(ky) // 2), (len(kx) // 2, len(kx) // 2)), mode="edge")
    p = np.apply_along_axis(lambda v: np.convolve(v, ky, mode="valid"), 0, p)
    return np.apply_along_axis(lambda v: np.convolve(v, kx, mode="valid"), 1, p)


def shade(lab_L, lab, mats, variant, spec):
    """Palette index per pixel from the labels and the smoothed lightness."""
    idx = np.zeros(lab.shape, np.uint8)
    two = variant.get("tones", 3) <= 2
    for i, m in enumerate(mats):
        ramp = list(m["ramp"])
        sel = lab == i
        if not sel.any():
            continue
        if len(ramp) == 1:
            idx[sel] = ramp[0]
            continue
        n = len(ramp)
        fr = list(m.get("frac") or {1: [1], 2: [0.35, 0.65], 3: [0.25, 0.5, 0.25], 4: [0.2, 0.4, 0.3, 0.1]}[n])
        use = list(range(n))
        if two:
            # the bold variant: shadow and base; metal and hair keep a small highlight
            use = list(m.get("two", [0, 1])) + ([n - 1] if m.get("shine") and n >= 3 else [])
            fr = [0.32, 0.55, 0.13][: len(use)] if len(use) == 3 else [0.35, 0.65]
        fr = np.array(fr, float) * np.array([1.0] * len(use))
        fr = fr / fr.sum()
        Lm = lab_L
        if m.get("smooth"):
            Lm = gauss2(lab_L, *m["smooth"])
        vals = Lm[sel]
        if sel.sum() < 12:
            idx[sel] = ramp[use[min(1, len(use) - 1)]]
            continue
        cuts = np.quantile(vals, np.cumsum(fr)[:-1])
        tone = np.digitize(Lm, cuts)
        shift = variant.get("shade_shift", 0.0)
        if shift:
            cuts = np.quantile(vals, np.clip(np.cumsum(fr)[:-1] + shift, 0.02, 0.98))
            tone = np.digitize(Lm, cuts)
        for t, k in enumerate(use):
            idx[sel & (tone == t)] = ramp[k]
    return idx


def material_edges(idx, lab, mats, variant):
    """Interior line art along the edge of the materials marked `outlined` where they meet another material (or nothing)."""
    out = idx.copy()
    h, w = lab.shape
    pad = np.pad(lab, 1, constant_values=-1)
    bold = variant.get("bold", False)
    for i, m in enumerate(mats):
        if not (m.get("outlined") or (bold and m.get("ramp") != [15])):
            continue
        z = m.get("z", i)
        edge = np.zeros((h, w), bool)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nb = pad[1 + dy: 1 + dy + h, 1 + dx: 1 + dx + w]
            zn = np.array([mats[k].get("z", k) if k >= 0 else -99 for k in range(-1, len(mats))])[nb + 1]
            edge |= (nb != i) & (nb >= 0) & (zn < z)
        sel = (lab == i) & edge
        out[sel] = 15 if bold else m.get("edge", 15)
    return out


# --- the faces: AW2-style features drawn on top ----------------------------------------------------------------------------------------------------------------

NEAR = {
    "normal": [".xxxxxx.",
               "xwDDhDDx",
               ".wDDDDx.",
               "..ssss.."],
    "happy": [".xxxxxx.",
              "x......x",
              "........",
              "........"],
    "sad": ["xxxxxxx.",
            "xwDDhDDx",
            ".wDDDDx.",
            "..ssss.."],
    "angry": ["xxxxxxxx",
              "xwxDhDDx",
              ".wDDDDx.",
              "..ss.s.."],
}
FAR = {
    "normal": [".xxxx.",
               "xDDhDx",
               ".DDDx.",
               "..ss.."],
    "happy": [".xxxx.",
              "x....x",
              "......",
              "......"],
    "sad": ["xxxxx.",
            "xDDhDx",
            ".DDDx.",
            "..ss.."],
    "angry": ["xxxxxx",
              "xxDhDx",
              ".DDDx.",
              "..s..."],
}
NEAR_S = {
    "normal": [".xxx.",
               "wDhDx",
               ".DDx."],
    "happy": [".xxx.", "x...x", "....."],
    "sad": ["xxxx.", "wDhDx", ".DDx."],
    "angry": ["xxxxx", "wxDDx", ".DDx."],
}
FAR_S = {
    "normal": ["xxx.",
               "DhDx",
               ".Dx."],
    "happy": ["xxx.", "x..x", "...."],
    "sad": ["xxx.", "DhDx", ".Dx."],
    "angry": ["xxxx", "xDDx", ".Dx."],
}


def put(a, grid, cx, cy, legend, skip_zero=False):
    """Stamp a grid centred on (cx, cy): the legend maps characters to palette indexes ('.' leaves the pixel)."""
    gh, gw = len(grid), len(grid[0])
    x0, y0 = cx - gw // 2, cy - gh // 2
    for j, row in enumerate(grid):
        for i, ch in enumerate(row):
            if ch == "." or ch not in legend:
                continue
            x, y = x0 + i, y0 + j
            if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
                a[y, x] = legend[ch]


def line(a, pts, v):
    for x, y in pts:
        if 0 <= y < a.shape[0] and 0 <= x < a.shape[1]:
            a[y, x] = v


def draw_face(a, spec, kind, eyes, mouth, nose, big, sk_deep=5):
    """Draw the features of one expression on `a` (palette indexes). eyes: ((x_near, y), (x_far, y)) in a's pixels; mouth, nose: (x, y)."""
    d = spec.get("face_style", {})
    dark = d.get("iris", 15)
    brow = d.get("brow", 15)
    legend = {"x": 15, "w": 1, "D": dark, "h": 1, "s": d.get("lid", 4)}
    mi = d.get("mouth", 5)
    (nx, ny), (fx, fy) = eyes
    near = (NEAR if big else NEAR_S)[kind]
    far = (FAR if big else FAR_S)[kind]
    # the whites of AW2's eyes are a light skin tone at this size when the stamp is small
    put(a, near, nx, ny, legend)
    put(a, far, fx, fy, legend)
    # brows
    bl = 8 if big else 5
    th = 2 if big else 1
    by = 3 if big else 2
    tilt = {"normal": 0, "happy": 0, "sad": -1, "angry": 1}[kind]
    for (ex, ey, w, inner_right) in ((nx, ny, bl, True), (fx, fy, bl - 2, False)):
        x0 = ex - w // 2
        for i in range(w):
            frac = i / max(1, w - 1)
            inner = frac if inner_right else 1 - frac
            dy = round(tilt * 2.0 * inner) if big else round(tilt * 1.2 * inner)
            if kind == "happy":
                dy = -1 - (1 if 0.2 < frac < 0.8 else 0)
            for t in range(th):
                y = ey - by - 1 + dy - (0 if kind != "happy" else 1) + t
                if 0 <= y < a.shape[0] and 0 <= x0 + i < a.shape[1]:
                    a[y, x0 + i] = brow
    # nose: a small shadow notch
    if nose and big:
        line(a, [(nose[0], nose[1]), (nose[0] + 1, nose[1])], 4)
        line(a, [(nose[0] - 1, nose[1] + 1), (nose[0], nose[1] + 1)], sk_deep)
    elif nose:
        line(a, [(nose[0], nose[1])], 4)
    # mouth
    mx, my = mouth
    if big:
        if kind == "happy":
            line(a, [(mx - 3, my - 1), (mx + 3, my - 1)] + [(mx + i, my) for i in range(-2, 3)], 15)
            line(a, [(mx + i, my) for i in range(-1, 2)], 1)
            line(a, [(mx + i, my + 1) for i in range(-1, 2)], 15)
        elif kind == "sad":
            line(a, [(mx - 2, my + 1), (mx + 2, my + 1)] + [(mx + i, my) for i in range(-1, 2)], mi)
        elif kind == "angry":
            line(a, [(mx + i, my) for i in range(-2, 3)] + [(mx - 3, my + 1), (mx + 3, my + 1)], mi)
        else:
            line(a, [(mx + i, my) for i in range(-2, 2)], mi)
            line(a, [(mx + i, my + 1) for i in range(-1, 1)], d.get("lip", 4))
    else:
        if kind == "happy":
            line(a, [(mx - 1, my), (mx, my + 1), (mx + 1, my)], 15)
        elif kind in ("sad", "angry"):
            line(a, [(mx - 1, my + 1), (mx, my), (mx + 1, my)] if kind == "sad" else [(mx - 1, my), (mx, my), (mx + 1, my + 1)], mi)
        else:
            line(a, [(mx - 1, my), (mx, my)], mi)


# --- the whole thing -------------------------------------------------------------------------------------------------------------------------------------------

def render(src, spec, variant, x0, y0, bw, bh, ow, oh):
    """-> (idx uint8 oh x ow, labels): the cel-shaded picture of one source rectangle."""
    mats = spec["material"]
    rgb, cov = src.region(x0, y0, bw, bh, ow, oh)
    valid = cov >= 0.5
    lab = I.to_lab(rgb.reshape(-1, 3)).reshape(oh, ow, 3)
    sm = bilateral(lab, valid, sigma_r=variant.get("smooth", 12.0), iters=variant.get("smooth_iters", 2))
    rgbs = np.clip(I.lab_to_rgb(sm), 0, 255)
    labels, fixed = label_map(src, spec, rgbs, valid, x0, y0, bw, bh, ow, oh)
    labels = majority(labels, fixed, len(mats), passes=variant.get("label_passes", 2))
    L = gauss(np.where(valid, sm[..., 0], np.nanmedian(sm[..., 0][valid])), variant.get("tone_blur", 0.9))
    idx = shade(L, labels, mats, variant, spec)
    idx[~valid] = 0
    for _ in range(variant.get("tone_passes", 1)):
        # majority filter within each material's tones
        out = idx.copy()
        pad = np.pad(idx, 1)
        padl = np.pad(labels, 1, constant_values=-1)
        for y in range(oh):
            for x in range(ow):
                if idx[y, x] == 0:
                    continue
                cnt = {}
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if padl[y + 1 + dy, x + 1 + dx] == labels[y, x] and pad[y + 1 + dy, x + 1 + dx]:
                            k = pad[y + 1 + dy, x + 1 + dx]
                            cnt[k] = cnt.get(k, 0) + (1.5 if (dx == 0 and dy == 0) else 1.0)
                out[y, x] = max(cnt, key=cnt.get)
        idx = out
    idx = despeckle(idx, labels, variant.get("min_blob", 3))
    idx = material_edges(idx, labels, mats, variant)
    return idx, labels


def eye_points(spec, fx, fy, k, flipw, ox=0, oy=0):
    """Eye, brow, mouth and nose positions of the source (framing file, source pixels) in an output picture whose origin is (fx, fy) at scale k; flipw: the width to mirror in (or 0)."""
    def p(x, y):
        X, Y = (x - fx) * k + ox, (y - fy) * k + oy
        return (round(flipw - 1 - X) if flipw else round(X)), round(Y)
    e = spec["eyes"]
    a, b = p(e[0], e[1]), p(e[2], e[3])
    # the nearer eye (the one on the face's own side towards the viewer) is the left one after the mirror
    near, far = (a, b) if a[0] <= b[0] else (b, a)
    mouth = p(*spec["mouth"])
    nose = p(*spec["nose"]) if spec.get("nose") else None
    return (near, far), mouth, nose


def styled(spec, src, variant_name=None):
    name = variant_name or spec.get("default_variant", "B")
    var = dict(spec.get("variant", {}).get(name, {}))
    var = {**spec.get("params", {}), **var}
    if "palette_from" in var:
        var = {**spec["variant"][var["palette_from"]], **var}
    spec = {**spec, "palette": var["palette"]}
    pal = [(0, 0, 0)] + [tuple(int(v) for v in I.snap555(np.array(hexrgb(c), float))) for c in spec["palette"]]
    assert len(pal) == 16, "the palette has 15 colours: index 1 white, 2..6 skin, 7..14 the CO's, 15 the outline"
    flip = spec.get("flip", True)
    cut = spec.get("crop_top", 0)
    s = spec.get("scale", 0.135)
    ow, oh = round(src.w * s), round((src.h - cut) * s)
    top = spec.get("top", 3)
    ox = (128 - ow) // 2 + spec.get("dx", 0)
    idx_l, lab_l = render(src, spec, var, 0, cut, src.w, src.h - cut, ow, oh)
    L = np.zeros((160, 128), np.uint8)
    ys, xs = slice(top, min(160, top + oh)), slice(max(0, ox), min(128, ox + ow))
    sx0 = max(0, -ox)
    L[ys, xs] = idx_l[: ys.stop - top, sx0: sx0 + (xs.stop - xs.start)]
    fx, fy, fs = spec["face"]
    idx_f, _ = render(src, spec, var, fx, fy, fs, fs, 48, 48)
    keep = I.clean_silhouette(L != 0, min_speck=40, max_hole=4)
    L[~keep] = 0
    if flip:
        L = L[:, ::-1].copy()
        idx_f = idx_f[:, ::-1].copy()
    # eyes, brows, mouth in the output orientation
    k = 48.0 / fs
    fig_eyes, fig_mouth, fig_nose = eye_points(spec, 0, cut, s, 128 if flip else 0, ox, top)
    mug_eyes, mug_mouth, mug_nose = eye_points(spec, fx, fy, k, 48 if flip else 0)
    fig_big = spec.get("figure_big_eyes", False)
    im = I.Imported()
    im.spec = spec
    im.palette = pal
    L = I.outline(L, (True, True, True, False))
    draw_face(L, spec, "normal", fig_eyes, fig_mouth, fig_nose, fig_big)
    for kind in ("normal", "happy", "sad", "angry"):
        m = idx_f.copy()
        draw_face(m, spec, kind, mug_eyes, mug_mouth, mug_nose, True)
        im.faces[kind] = I.outline(m, (True, True, True, False))
    im.large = L
    ex, ey = round((mug_eyes[0][0] + mug_eyes[1][0]) / 2), round((mug_eyes[0][1] + mug_eyes[1][1]) / 2)
    im.eye = (ex, ey)
    mug = im.faces["normal"]
    im.mini = I._window(mug, ex - 16, ey - 10, 32, 24)
    im.hud = I._window(mug, ex - 16, ey - 6, 32, 16)
    return im
