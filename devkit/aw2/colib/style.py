"""Style measurements of CO art (docs/dev/co-kit.md): numbers read from AW2's own large figures and faces, and the same numbers for a CO's art, so `co portrait lint --style aw2` can say whether a portrait is
in the game's style. Everything is computed from the pictures (palette indexes + palette); AW2's pictures are read from the player's ROM, never stored."""
import colorsys
import numpy as np
from . import roms


def rgb_of(idx, pal):
    h, w = idx.shape
    out = np.zeros((h, w, 3), float)
    for v in range(1, 16):
        out[idx == v] = pal[v]
    return out, idx != 0


def _hsv(rgb):
    mx, mn = rgb.max(-1), rgb.min(-1)
    v = mx / 255.0
    s = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    return v, s


def components(idx):
    """Number of 4-connected components of equal colour among opaque pixels."""
    h, w = idx.shape
    seen = np.zeros((h, w), bool)
    n = 0
    for y in range(h):
        for x in range(w):
            if idx[y, x] == 0 or seen[y, x]:
                continue
            n += 1
            c = idx[y, x]
            st = [(y, x)]
            seen[y, x] = True
            while st:
                a, b = st.pop()
                for aa, bb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                    if 0 <= aa < h and 0 <= bb < w and not seen[aa, bb] and idx[aa, bb] == c:
                        seen[aa, bb] = True
                        st.append((aa, bb))
    return n


def skin_mask(rgb):
    r, g, b = rgb[..., 0] / 255, rgb[..., 1] / 255, rgb[..., 2] / 255
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    d = mx - mn
    h = np.zeros_like(mx)
    m = d > 0
    rr = m & (mx == r)
    gg = m & (mx == g) & ~rr
    bb = m & ~rr & ~gg
    h[rr] = (60 * (((g - b)[rr] / d[rr]) % 6))
    h[gg] = 60 * ((b - r)[gg] / d[gg] + 2)
    h[bb] = 60 * ((r - g)[bb] / d[bb] + 4)
    s = np.where(mx > 0, d / np.maximum(mx, 1e-9), 0)
    return (h > 8) & (h < 48) & (s > 0.18) & (s < 0.85) & (mx > 0.45)


def head_metrics(idx, pal):
    """(head height, eye line) in pixels of a large figure: the head runs from the top of the figure to the chin (the bottom of the largest skin region near the top); the eye line is the row of the
    darkest short horizontal stroke inside that skin region, measured from the top."""
    rgb, op = rgb_of(idx, pal)
    sk = skin_mask(rgb) & op
    h, w = idx.shape
    top = int(np.nonzero(op.any(1))[0][0])
    # the head's skin: skin pixels in the upper 60% of the figure, the biggest connected blob
    sk[int(h * 0.6):] = False
    seen = np.zeros_like(sk)
    best = []
    for y, x in zip(*np.nonzero(sk)):
        if seen[y, x]:
            continue
        comp, st = [], [(y, x)]
        seen[y, x] = True
        while st:
            a, b = st.pop()
            comp.append((a, b))
            for aa, bb in ((a + 1, b), (a - 1, b), (a, b + 1), (a, b - 1)):
                if 0 <= aa < h and 0 <= bb < w and sk[aa, bb] and not seen[aa, bb]:
                    seen[aa, bb] = True
                    st.append((aa, bb))
        if len(comp) > len(best):
            best = comp
    if not best:
        return None
    ys = [p[0] for p in best]
    chin = max(ys)
    return chin - top + 1, min(ys) - top, top


def measure(idx, pal):
    """The numbers of one picture: mean value, mean saturation, luminance spread, flatness (opaque pixels whose 4-neighbours share more than one of their colour), colours used, regions per 1000 opaque px,
    and the share of the darkest tone (the outline and the deep shadows)."""
    rgb, op = rgb_of(idx, pal)
    v, s = _hsv(rgb)
    lum = rgb @ np.array([0.299, 0.587, 0.114])
    n = int(op.sum())
    same = np.zeros_like(op)
    cnt = np.zeros(idx.shape, int)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        sh = np.roll(np.roll(idx, dy, 0), dx, 1)
        cnt += (sh == idx) & op
    flat = float(((cnt >= 3) & op).sum()) / n
    colours = len({int(c) for c in idx[op]})
    dark = float((lum[op] < 60).sum()) / n
    return {"value": float(v[op].mean()), "saturation": float(s[op].mean()), "contrast": float(lum[op].std()), "flatness": flat, "colours": colours,
            "regions_per_1000": 1000.0 * components(idx) / n, "dark_share": dark, "opaque": n}


def aw2_figures():
    """[(name, idx array, palette rgb list)] of AW2's 19 CO figures."""
    out = []
    for i in range(19):
        d = roms.aw2_portrait(i)
        idx = np.array(d.body)
        pal = [(0, 0, 0)] + [roms.bgr(c) for c in d.palettes[0][1:]]
        out.append((d.name, idx, pal))
    return out


def aw2_faces():
    out = []
    for i in range(19):
        d = roms.aw2_portrait(i)
        idx = np.array(d.faces[0])
        pal = [(0, 0, 0)] + [roms.bgr(c) for c in d.palettes[0][1:]]
        out.append((d.name, idx, pal))
    return out


def aw2_ranges():
    """{metric: (min, mean, max)} over AW2's figures, and the head numbers; for faces the same measures."""
    figs = [(n, measure(i, p), head_metrics(i, p)) for n, i, p in aw2_figures()]
    faces = [(n, measure(i, p)) for n, i, p in aw2_faces()]
    out = {"figure": {}, "face": {}, "head": {}}
    for k in figs[0][1]:
        vals = [m[k] for _, m, _ in figs]
        out["figure"][k] = (min(vals), float(np.mean(vals)), max(vals))
        vals = [m[k] for _, m in faces]
        out["face"][k] = (min(vals), float(np.mean(vals)), max(vals))
    hm = [h for _, _, h in figs if h]
    out["head"] = {"height": (min(h[0] for h in hm), float(np.mean([h[0] for h in hm])), max(h[0] for h in hm)), "eye_line": (min(h[1] for h in hm), float(np.mean([h[1] for h in hm])), max(h[1] for h in hm)),
                   "top_margin": (min(h[2] for h in hm), float(np.mean([h[2] for h in hm])), max(h[2] for h in hm))}
    return out, figs, faces


TOLERANCE = 0.15


def lint(idx_by_name, pal, ranges=None):
    """-> (rows, problems): each measure of the large figure (`large`) and the normal face (`face_normal`) against AW2's own range, widened by 15% either way: (name, value, low, high, ok)."""
    r = ranges or aw2_ranges()[0]
    rows, bad = [], []
    for part, key in (("figure", "large"), ("face", "face_normal")):
        m = measure(idx_by_name[key], pal)
        for k in ("value", "saturation", "contrast", "flatness", "regions_per_1000", "dark_share"):
            lo, mean, hi = r[part][k]
            tol = 0.35 if (part == "face" and k == "regions_per_1000") else TOLERANCE      # (AW2's faces carry the busiest hair of the game; ours are cleaner, a third less is allowed)
            lo2, hi2 = lo * (1 - tol), min(hi * (1 + TOLERANCE), 1.0 if k in ("value", "saturation", "flatness", "dark_share") else 1e9)
            ok = lo2 <= m[k] <= hi2
            rows.append((f"{part} {k}", m[k], lo2, hi2, mean, ok))
            if not ok:
                bad.append(f"{part} {k} is {m[k]:.2f}, AW2's range is {lo:.2f} to {hi:.2f} (mean {mean:.2f})")
        if m["colours"] > 15:
            bad.append(f"{part}: {m['colours']} colours")
    head = head_metrics(idx_by_name["large"], pal)
    hr = r["head"]
    if head:
        h, eye, top = head
        rows.append(("head height", float(h), hr["height"][0], hr["height"][2], hr["height"][1], hr["height"][0] <= h <= hr["height"][2]))
        rows.append(("eye line", float(eye), hr["eye_line"][0] * 0.8, hr["eye_line"][2], hr["eye_line"][1], hr["eye_line"][0] * 0.8 <= eye <= hr["eye_line"][2]))
        rows.append(("top margin", float(top), 0.0, hr["top_margin"][2], hr["top_margin"][1], 0 <= top <= hr["top_margin"][2]))
        for name, v, lo, hi, mean, ok in rows[-3:]:
            if not ok:
                bad.append(f"{name} is {v:.0f}, AW2's range is {lo:.0f} to {hi:.0f}")
    return rows, bad
