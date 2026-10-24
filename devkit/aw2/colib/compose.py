"""Portrait composition (docs/dev/co-kit.md): a donor CO's parts (read from the ROMs, never stored) are recoloured and overlaid with our own pixel motifs
(`tango-gamesupport-aw2/cos/art/*.toml`), as a recipe in `cos/<id>.toml` says. Truecolour inside, fitted to the game's 15 colours + transparent at the end."""
import colorsys, tomllib
from pathlib import Path
from .. import cfg
from . import roms

COS_DIR = cfg.REPO / "tango-gamesupport-aw2" / "cos"
ART_DIR = COS_DIR / "art"
PARTS = ("body", "face", "mini", "hud")


def hexrgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def donor(spec):
    """'aw2:max' / 'aw2:4' / 'ds:grimm' / 'ds:24' -> roms.Portrait."""
    src, _, who = spec.partition(":")
    if src == "aw2":
        return roms.aw2_portrait(int(who) if who.isdigit() else [n.lower() for n in roms.AW2_NAMES].index(who.lower()))
    if src == "ds":
        if who.isdigit():
            return roms.ds_portrait(int(who))
        ids = [k for k, v in roms.DS_NAMES.items() if v.lower() == who.lower()]
        return roms.ds_portrait(ids[-1] if who.lower() in ("hawke", "sturm", "nell") else ids[0])
    raise ValueError(f"donor {spec!r}: aw2:<name|id> or ds:<name|id>")


class Pic:
    """RGB or None per pixel, plus the donor's palette index per pixel (for role-based recolouring)."""

    def __init__(self, idx, pal):
        self.h, self.w = len(idx), len(idx[0])
        self.idx = [r[:] for r in idx]
        self.px = [[roms.bgr(pal[v]) if v else None for v in r] for r in idx]

    def put(self, x, y, c, clip=False):
        x, y = int(round(x)), int(round(y))
        if 0 <= x < self.w and 0 <= y < self.h and (not clip or self.px[y][x] is not None):
            self.px[y][x] = c
            self.idx[y][x] = -1


def lum(c):
    return 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]


def is_skin(c):
    if c is None:
        return False
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
    return 0.015 < h < 0.12 and 0.2 < s < 0.8 and v > 0.45


def skin_box(pic, ymax=None):
    """Bounding box (x0, y0, x1, y1) of the largest connected skin region whose top is above `ymax` (the head, not a hand)."""
    seen, best = set(), None
    for y0 in range(pic.h if ymax is None else min(pic.h, ymax)):
        for x0 in range(pic.w):
            if (x0, y0) in seen or not is_skin(pic.px[y0][x0]):
                continue
            stack, comp = [(x0, y0)], []
            seen.add((x0, y0))
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < pic.w and 0 <= ny < pic.h and (nx, ny) not in seen and is_skin(pic.px[ny][nx]):
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            if len(comp) >= 30 and (best is None or min(p[1] for p in comp) < min(p[1] for p in best) - 3 or (abs(min(p[1] for p in comp) - min(p[1] for p in best)) <= 3 and len(comp) > len(best))):
                best = comp
    if not best:
        return None
    xs, ys = [p[0] for p in best], [p[1] for p in best]
    return min(xs), min(ys), max(xs), max(ys)


def anchors(pic, part):
    """Named points of the head found from the skin: brow (top centre), chin, ear_l, ear_r, neck (a little below the chin), and the picture's corners."""
    box = skin_box(pic, 70 if part == "body" else None)
    if not box:
        return {}
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    return {"brow": (cx, y0), "chin": (cx, y1), "ear_l": (x0, cy), "ear_r": (x1, cy), "neck": (cx, y1 + 3), "centre": (cx, cy), "top": (cx, 0), "bottom": (cx, pic.h - 1),
            "left": (0, cy), "right": (pic.w - 1, cy)}


def load_ramps():
    f = ART_DIR / "palette.toml"
    return tomllib.loads(f.read_text()).get("ramp", {}) if f.exists() else {}


def load_motifs():
    out = {}
    for f in sorted(ART_DIR.glob("*.toml")):
        d = tomllib.loads(f.read_text())
        for k, m in d.get("motif", {}).items():
            out[k] = m
    return out


def draw_motif(pic, m, at, flip=False, clip=False):
    cols = {k: hexrgb(v) for k, v in m["colours"].items()}
    rows = m["rows"]
    w = max(len(r) for r in rows)
    ox = {"left": 0, "centre": w // 2, "right": w - 1}[m.get("ox", "centre")]
    oy = {"top": 0, "centre": len(rows) // 2, "bottom": len(rows) - 1}[m.get("oy", "top")]
    for y, r in enumerate(rows):
        for x, ch in enumerate(r):
            if ch in ".":
                continue
            xx = (w - 1 - x) if flip else x
            if ch == "_":   # clears a pixel (e.g. hair under a helmet)
                pic.put(at[0] + xx - ox, at[1] + y - oy, None)
            else:
                pic.put(at[0] + xx - ox, at[1] + y - oy, cols[ch], clip)


def draw_line(pic, p0, p1, width, colours, clip=False):
    """A band from p0 to p1: `colours` lists the stripe colours across its width (edge, ..., edge)."""
    (x0, y0), (x1, y1) = p0, p1
    n = max(abs(x1 - x0), abs(y1 - y0), 1)
    cols = [hexrgb(c) for c in colours]
    for i in range(n + 1):
        x, y = x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n
        for k in range(width):
            c = cols[min(len(cols) - 1, k * len(cols) // width)]
            if abs(x1 - x0) >= abs(y1 - y0):
                pic.put(round(x), round(y) + k - width // 2, c, clip)
            else:
                pic.put(round(x) + k - width // 2, round(y), c, clip)


def shape_laurel(pic, at, width, leaf="6FA83A", leaf_dark="3E7A2A", berry="E8C25A", rise=3, droop=4, clip=False):
    """A laurel wreath: two sprays of paired leaves meeting at the brow's centre `at`, curving down over each temple (width px across)."""
    lc, ld, bc = hexrgb(leaf), hexrgb(leaf_dark), hexrgb(berry)
    half = width // 2
    for side in (-1, 1):
        for k in range(1, half + 1):
            t = k / half
            x = at[0] + side * k
            y = at[1] + round(droop * t ** 2.4)
            main = lc if k % 3 else ld
            pic.put(x, y, main, clip)
            pic.put(x, y + 1, ld, clip)
            if k % 2 == 0:   # a leaf standing off the stem, up-and-out then down-and-out
                pic.put(x + side, y - 1, lc, clip)
                pic.put(x, y - 1, lc, clip)
                pic.put(x + side, y + 2, ld, clip)
    for dx in (-1, 0, 1):
        pic.put(at[0] + dx, at[1], bc, clip)
        pic.put(at[0] + dx, at[1] + 1, bc, clip)
    pic.put(at[0], at[1] - 1, bc, clip)


def shape_helmet(pic, box, steel, crest, trim, plume=True, facing=1, tilt=0, grow=1):
    """A Roman helmet over the head: the hair above the brow is cleared and a clean dome (dark outline, steel shaded from the upper front, a gold rim at the brow) takes its
    place; a red crest runs along the top and streams back. The dome fills the head's own silhouette (`grow` px wider), so it fits the picture's edge."""
    x0, y0, x1, y1 = box
    st = [hexrgb(x) for x in steel]
    cr = [hexrgb(x) for x in crest]
    rim = hexrgb(trim)
    opaque = [(x, y) for y in range(0, y0 + 2) for x in range(pic.w) if pic.px[y][x] is not None]
    if not opaque:
        return
    ox0, ox1 = min(p[0] for p in opaque), max(p[0] for p in opaque)
    top = min(p[1] for p in opaque)
    outline = min((pic.px[y][x] for x, y in opaque), key=lum)
    brow = y0
    for x, y in opaque:
        if y <= brow and not is_skin(pic.px[y][x]):
            pic.px[y][x] = None
    cx = (ox0 + ox1) / 2
    hw = (ox1 - ox0) / 2 + grow
    dtop = top + (2 if plume else 0)
    H = max(4, brow - dtop)
    for y in range(dtop, brow + 1):
        dy = (brow - y) / (H + 0.6)
        w = hw * (1 - dy ** 2.4) ** 0.5
        xa, xb = round(cx - w), round(cx + w)
        for x in range(xa, xb + 1):
            u = (x - xa) / max(1, xb - xa)          # 0 back .. 1 front (facing right)
            if facing < 0:
                u = 1 - u
            v = (y - dtop) / max(1, H)
            k = 0.55 * (1 - u) + 0.45 * v          # light at the upper front
            col = st[min(len(st) - 1, int(k * len(st)))]
            if x in (xa, xb) or y == dtop and plume is False:
                col = outline
            pic.put(x, y, col)
        if y == dtop:
            for x in range(xa, xb + 1):
                pic.put(x, y, outline)
    for x in range(round(cx - hw), round(cx + hw) + 1):
        if pic.px[brow][x] is not None and not is_skin(pic.px[brow][x]):
            pic.put(x, brow, rim)
            pic.put(x, brow + 1, outline) if brow + 1 < pic.h and not is_skin(pic.px[brow + 1][x] or (0, 0, 0)) and pic.px[brow + 1][x] is None else None
    # the neck guard: the hair behind the ear becomes the helmet's dark steel
    ear = y0 + round((y1 - y0) * 0.55)
    for y in range(brow + 1, min(ear, pic.h)):
        for x in range(pic.w):
            c0 = pic.px[y][x]
            if c0 is not None and not is_skin(c0) and lum(c0) > 60 and (x < x0 + 3 if facing > 0 else x > x1 - 3):
                pic.px[y][x] = st[min(len(st) - 1, 2 + (lum(c0) < 120))]
    if plume:
        for x in range(round(cx - hw * 0.55), round(cx + hw * 0.55) + 1):
            pic.put(x, top, cr[0])
            pic.put(x, top + 1, cr[1])
            pic.put(x, top + 2, cr[2])
        back = round(cx - facing * hw * 0.55)
        for k in range(1, 4):
            for j in range(3):
                pic.put(back - facing * k, top + j + k // 2, cr[min(2, j + 1)])


def ramp_map(pic, indices, ramp, pal):
    """Recolour the donor palette entries `indices` by brightness rank onto `ramp` (light to dark colours, interpolated)."""
    ramp = [hexrgb(c) for c in ramp]
    cs = sorted({tuple(roms.bgr(pal[i])): i for i in indices}.items(), key=lambda kv: -lum(kv[0]))
    new = {}
    lo, hi = (0.0, 1.0) if len(cs) > 3 else (0.18, 0.78)
    for r, (c, i) in enumerate(cs):
        t = (lo + (hi - lo) * r / max(1, len(cs) - 1)) * (len(ramp) - 1)
        a, b = ramp[int(t)], ramp[min(len(ramp) - 1, int(t) + 1)]
        f = t - int(t)
        new[c] = tuple(round(a[k] + (b[k] - a[k]) * f) for k in range(3))
    for y in range(pic.h):
        for x in range(pic.w):
            c = pic.px[y][x]
            if c in new and pic.idx[y][x] in indices:
                pic.px[y][x] = new[c]


def hue_deg(c):
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
    return h * 360, s, v


def palette_report(d, scheme=0):
    """[(index, rgb, hue, sat, value, pixel count in the body and faces)] to write a recipe's hue rules from."""
    pal = d.palettes[scheme]
    cnt = {}
    for g in [d.body, *d.faces]:
        for r in g:
            for v in r:
                cnt[v] = cnt.get(v, 0) + 1
    out = []
    for i in range(1, 16):
        c = roms.bgr(pal[i])
        h, s, v = hue_deg(c)
        out.append((i, c, round(h), round(s, 2), round(v, 2), cnt.get(i, 0)))
    return out


def hue_indices(pal, rule, taken):
    lo, hi = rule["hue"]
    smin, smax = rule.get("sat", [0.18, 1.0])
    vmin, vmax = rule.get("val", [0.0, 1.0])
    out = []
    for i in range(1, 16):
        if i in taken:
            continue
        h, s, v = hue_deg(roms.bgr(pal[i]))
        okh = lo <= h <= hi if lo <= hi else (h >= lo or h <= hi)
        if okh and smin <= s <= smax and vmin <= v <= vmax:
            out.append(i)
    return out


def compose(opt, motifs=None, scheme=0):
    """opt: the option's dict (donor, recolour, ramp, motif/line lists). Returns {part: [Pic], ...} and the donor."""
    motifs = motifs or load_motifs()
    d = donor(opt["donor"])
    pal = d.palettes[scheme]
    pics = {"body": Pic(d.body, pal), "face": [Pic(f, pal) for f in d.faces], "mini": Pic(d.mini, pal), "hud": Pic(d.hud, pal)}
    allp = [pics["body"]] + pics["face"] + [pics["mini"], pics["hud"]]
    ramps = load_ramps()
    for r in opt.get("hues", []) + opt.get("ramp", []):
        if isinstance(r["ramp"], str):
            r["ramp"] = ramps[r["ramp"]]
    taken = set()
    for r in opt.get("hues", []):
        idx = hue_indices(pal, r, taken) if "hue" in r else list(r["indices"])
        taken |= set(idx)
        for p in allp:
            ramp_map(p, idx, r["ramp"], pal)
    for r in opt.get("ramp", []):
        for p in allp:
            ramp_map(p, r["indices"], r["ramp"], pal)
    for k, c in opt.get("recolour", {}).items():
        for p in allp:
            for y in range(p.h):
                for x in range(p.w):
                    if p.idx[y][x] == int(k):
                        p.px[y][x] = hexrgb(c)
    for item in opt.get("place", []):
        parts = item.get("target", "body face").split()
        for part in parts:
            tgt = {"body": [pics["body"]], "face": pics["face"], "mini": [pics["mini"]], "hud": [pics["hud"]]}[part]
            for k, p in enumerate(tgt):
                a = anchors(p, part) if part in ("body", "face") else {"centre": (p.w // 2, p.h // 2), "top": (p.w // 2, 0), "bottom": (p.w // 2, p.h - 1)}
                key = item.get("anchor", "brow")
                if key not in a:
                    continue
                dx, dy = item.get("d" + part[0] + "x", item.get("dx", 0)), item.get("d" + part[0] + "y", item.get("dy", 0))
                at = (a[key][0] + dx, a[key][1] + dy)
                if "motif" in item:
                    draw_motif(p, motifs[item["motif"]], at, item.get("flip", False), item.get("clip", False))
                elif item.get("shape") == "laurel":
                    shape_laurel(p, at, item.get("w", 36 if part == "face" else 28), item.get("leaf", "6FA83A"), item.get("leaf_dark", "3E7A2A"), item.get("berry", "E8C25A"), item.get("rise", 3), item.get("droop", 4), item.get("clip", False))
                elif item.get("shape") == "helmet" and part in ("body", "face"):
                    shape_helmet(p, skin_box(p, 70 if part == "body" else None), item.get("steel", ["DEE4C0", "BECB9E", "A0AB85", "7E8769", "464A3B"]), item.get("crest", ["E0505E", "D02C3C", "8E1B28"]),
                                 item.get("trim", "E8C25A"), item.get("plume", True), item.get("cheek", 0.45), item.get("facing", 1))
                elif "line" in item:
                    ex, ey = item["line"][2], item["line"][3]
                    draw_line(p, (at[0] + item["line"][0], at[1] + item["line"][1]), (at[0] + ex, at[1] + ey), item.get("width", 3), item["colours"], item.get("clip", True))
    return pics, d


def fit_palette(pics, n=15):
    """The colours of the whole portrait (body, faces, mini, hud) reduced to `n` by merging the closest pair of the least used until they fit.
    Returns (map colour -> colour, the palette, how many were merged)."""
    count = {}
    flat = [pics["body"], *pics["face"], pics["mini"], pics["hud"]]
    for p in flat:
        for r in p.px:
            for c in r:
                if c is not None:
                    count[c] = count.get(c, 0) + 1
    # AW2's own 5-bit colours: two colours equal in BGR555 are one
    q = lambda c: tuple(((v * 31 + 127) // 255) * 255 // 31 for v in c)
    count2 = {}
    for c, k in count.items():
        count2[q(c)] = count2.get(q(c), 0) + k
    cols = dict(count2)
    merged = 0
    mapping = {c: q(c) for c in count}
    while len(cols) > n:
        items = sorted(cols.items(), key=lambda kv: kv[1])
        best = None
        for a, ka in items[:8]:
            for b, kb in cols.items():
                if a == b:
                    continue
                dist = sum((a[i] - b[i]) ** 2 for i in range(3)) * (1 + 0.3 * (ka / (ka + kb)))
                if best is None or dist < best[0]:
                    best = (dist, a, b)
        _, a, b = best
        for c, t in list(mapping.items()):
            if t == a:
                mapping[c] = b
        cols[b] += cols.pop(a)
        merged += 1
    return mapping, sorted(cols, key=lambda c: -lum(c)), merged


def apply_fit(pics, mapping):
    for p in [pics["body"], *pics["face"], pics["mini"], pics["hud"]]:
        for y in range(p.h):
            for x in range(p.w):
                c = p.px[y][x]
                if c is not None:
                    p.px[y][x] = mapping.get(c, c)
