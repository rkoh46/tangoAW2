"""`aw2dev co portrait import`: turns a supplied portrait picture (a bust on a dark background, any size) into game-ready AW2 CO art (docs/dev/co-kit.md):
the large figure (128 x 160), the CO select mug (48 x 48), the Teams mini (32 x 24) and the HUD face (32 x 16), expression faces, one shared palette of 15 colours + transparent
with the outline in index 15, the way AW2's CO presentation rows are (the CO's palette serves every picture of it).

Method: the background is cut out by a flood fill from the picture's top edge; each picture is area-averaged from the source (premultiplied, so the dark background does not bleed into
the edges), the colours of all of a CO's pictures are quantised together (k-means in Lab, the faces weighted up) to 14 colours + the outline, isolated pixels are removed, the silhouette is
cleaned (specks and pinholes) and outlined. The small faces are cut again from the source, not shrunk from the large art. Art credits: CREDITS.md."""
import math
import numpy as np
from PIL import Image
from .. import cfg


# --- source ------------------------------------------------------------------------------------------------------------------------------------------------------

def shift(m, dx, dy):
    o = np.zeros_like(m)
    h, w = m.shape
    ys, yd = slice(max(0, dy), h + min(0, dy)), slice(max(0, -dy), h + min(0, -dy))
    xs, xd = slice(max(0, dx), w + min(0, dx)), slice(max(0, -dx), w + min(0, -dx))
    o[ys, xs] = m[yd, xd]
    return o


def flood(seed, cand):
    m = seed & cand
    while True:
        n = m | ((shift(m, 1, 0) | shift(m, -1, 0) | shift(m, 0, 1) | shift(m, 0, -1)) & cand)
        if (n == m).all():
            return m
        m = n


class Source:
    """The picture with its background cut out: `rgb` (float, h x w x 3) and `alpha` (bool foreground, h x w)."""

    def __init__(self, path, tol=18):
        im = Image.open(path).convert("RGB")
        self.rgb = np.array(im).astype(np.float32)
        h, w, _ = self.rgb.shape
        bg = np.median(self.rgb[:30].reshape(-1, 3), axis=0)
        d = np.sqrt(((self.rgb - bg) ** 2).sum(2))
        seed = np.zeros((h, w), bool)
        seed[:6, :] = True
        back = flood(seed, d < tol)
        fg = ~back
        # specks of the background's texture: keep only what is joined (by 8 x 8 blocks) to the figure at the bottom centre
        bh, bw = h // 8, w // 8
        blocks = fg[:bh * 8, :bw * 8].reshape(bh, 8, bw, 8).any((1, 3))
        seedb = np.zeros_like(blocks)
        seedb[-4, bw // 2] = True
        keep = np.kron(flood(seedb, blocks), np.ones((8, 8), bool))
        out = np.zeros((h, w), bool)
        out[:bh * 8, :bw * 8] = fg[:bh * 8, :bw * 8] & keep
        self.alpha = out
        self.h, self.w = h, w

    def region(self, x0, y0, bw, bh, ow, oh):
        """Area-average the source rectangle (x0, y0, bw, bh) to ow x oh: (rgb float ow x oh x 3, coverage 0..1). Colours are premultiplied, so the background does not bleed in."""
        a = self.alpha.astype(np.float32)
        chans = [self.rgb[:, :, c] * a for c in range(3)] + [a]
        outs = []
        for ch in chans:
            im = Image.fromarray(ch.astype(np.float32), mode="F")
            outs.append(np.array(im.resize((ow, oh), Image.BOX, box=(x0, y0, x0 + bw, y0 + bh))))
        cov = outs[3]
        rgb = np.stack(outs[:3], axis=2) / np.maximum(cov, 1e-6)[:, :, None]
        return rgb, cov


# --- colour ------------------------------------------------------------------------------------------------------------------------------------------------------

def to_lab(rgb):
    c = rgb / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124, 0.3576, 0.1805], [0.2126, 0.7152, 0.0722], [0.0193, 0.1192, 0.9505]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    return np.stack([116 * f[..., 1] - 16, 500 * (f[..., 0] - f[..., 1]), 200 * (f[..., 1] - f[..., 2])], axis=-1)


def kmeans(lab, weights, k, iters=30, seed=3):
    rng = np.random.default_rng(seed)
    n = len(lab)
    cent = [lab[rng.choice(n, p=weights / weights.sum())]]
    for _ in range(1, k):
        d = np.min([((lab - c) ** 2).sum(1) for c in cent], axis=0) * weights
        cent.append(lab[rng.choice(n, p=d / d.sum())])
    cent = np.array(cent)
    for _ in range(iters):
        d = ((lab[:, None, :] - cent[None]) ** 2).sum(2)
        lab_id = d.argmin(1)
        for j in range(k):
            m = lab_id == j
            if m.any():
                cent[j] = (lab[m] * weights[m][:, None]).sum(0) / weights[m].sum()
    return cent


def lab_to_rgb(lab):
    fy = (lab[..., 0] + 16) / 116
    fx = fy + lab[..., 1] / 500
    fz = fy - lab[..., 2] / 200
    f = np.stack([fx, fy, fz], axis=-1)
    xyz = np.where(f ** 3 > 0.008856, f ** 3, (f - 16 / 116) / 7.787) * np.array([0.95047, 1.0, 1.08883])
    m = np.array([[3.2406, -1.5372, -0.4986], [-0.9689, 1.8758, 0.0415], [0.0557, -0.2040, 1.0570]])
    lin = xyz @ m.T
    c = np.where(lin > 0.0031308, 1.055 * np.clip(lin, 0, None) ** (1 / 2.4) - 0.055, 12.92 * lin)
    return np.clip(c * 255, 0, 255)


def snap555(rgb):
    return (np.round(np.clip(rgb, 0, 255) / 255 * 31) * 255 / 31).round().astype(int)


# --- cleanup -----------------------------------------------------------------------------------------------------------------------------------------------------

def clean_silhouette(mask, min_speck=8, max_hole=6):
    """Remove specks (4-connected components below min_speck pixels) and fill pinholes (background components fully enclosed and below max_hole)."""
    def comps(m):
        out = []
        seen = np.zeros_like(m)
        for y, x in zip(*np.nonzero(m)):
            if seen[y, x]:
                continue
            seed = np.zeros_like(m)
            seed[y, x] = True
            c = flood(seed, m)
            seen |= c
            out.append(c)
        return out
    m = mask.copy()
    for c in comps(m):
        if c.sum() < min_speck:
            m &= ~c
    inv = ~m
    for c in comps(inv):
        touches = c[0].any() or c[-1].any() or c[:, 0].any() or c[:, -1].any()
        if not touches and c.sum() <= max_hole:
            m |= c
    return m


def despeckle(idx, passes=2):
    """A pixel whose colour no 4-neighbour shares (and which is not the outline) takes the commonest colour of its neighbours: the noise of a downscale."""
    idx = idx.copy()
    h, w = idx.shape
    for _ in range(passes):
        out = idx.copy()
        for y in range(h):
            for x in range(w):
                v = idx[y, x]
                if v == 0 or v == 15:
                    continue
                nb = [idx[yy, xx] for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)) if 0 <= yy < h and 0 <= xx < w]
                if v not in nb:
                    cand = [n for n in nb if n not in (0, 15)]
                    if len(cand) >= 3:
                        out[y, x] = max(set(cand), key=cand.count)
        idx = out
    return idx


def outline(idx, sides=(True, True, True, False)):
    """Draw the outline (index 15) on every transparent pixel next to an opaque one, inside the picture. `sides`: (left, right, top, bottom) edges the picture may be outlined along."""
    opaque = idx != 0
    edge = np.zeros_like(opaque)
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        edge |= shift(opaque, dx, dy)
    out = idx.copy()
    out[edge & ~opaque] = 15
    return out


# --- the import ----------------------------------------------------------------------------------------------------------------------------------------------------

class Imported:
    def __init__(self):
        self.palette = []        # 16 RGB, index 0 unused (transparent)
        self.large = None        # 160 x 128 indexes
        self.faces = {}          # expression -> 48 x 48 indexes
        self.mini = None
        self.hud = None


def import_co(spec, root=None, painterly=False):
    """spec: dict with source, scale (output px per source px of the large picture), top (rows above the figure), face = [x, y, size] (the mug's square in the source), and optional eyes / brows / mouth for the
    expression faces. -> Imported."""
    root = root or cfg.REPO
    import tomllib
    side = (root / spec["source"]).with_suffix(".toml")
    if side.exists():
        spec = {**tomllib.loads(side.read_text()), **spec}
    if spec.get("pixelart"):
        from . import pixelart
        return pixelart.styled(spec, root / spec["source"])
    if spec.get("illustration"):
        from . import illustration
        return illustration.styled(spec, root / spec["source"])
    src = Source(root / spec["source"], spec.get("bg_tolerance", 18))
    s = spec.get("scale", 0.1275)
    # --- the large picture: the source scaled by s, the top margin `top`, centred; what falls below 160 or outside 128 is cut
    cut = spec.get("crop_top", 0)
    ow, oh = round(src.w * s), round((src.h - cut) * s)
    top = spec.get("top", 3)
    ox = (128 - ow) // 2 + spec.get("dx", 0)
    rgb, cov = src.region(0, cut, src.w, src.h - cut, ow, oh)
    L = np.zeros((160, 128, 3), np.float32)
    C = np.zeros((160, 128), np.float32)
    ys, xs = slice(top, min(160, top + oh)), slice(max(0, ox), min(128, ox + ow))
    L[ys, xs] = rgb[: ys.stop - top, max(0, -ox): max(0, -ox) + (xs.stop - xs.start)]
    C[ys, xs] = cov[: ys.stop - top, max(0, -ox): max(0, -ox) + (xs.stop - xs.start)]
    # --- the faces: the mug's square, 48 x 48; the mini and the HUD face are windows of it (cut at the same scale from the same source: nothing is shrunk twice)
    fx, fy, fs = spec["face"]
    frgb, fcov = src.region(fx, fy, fs, fs, 48, 48)
    pics = {"large": (L, C), "mug": (frgb, fcov)}
    # --- one palette for all of it: 14 colours (the faces weigh more: they are small and carry the eyes) and the outline
    px, wt = [], []
    for name, (r, c) in pics.items():
        m = c >= 0.5
        px.append(r[m])
        wt.append(np.full(m.sum(), spec.get("face_weight", 6.0) if name == "mug" else 1.0))
    px, wt = np.concatenate(px), np.concatenate(wt)
    lab = to_lab(px)
    cent = kmeans(lab, wt, 13)
    # AW2's art is bright and saturated; the supplied pictures are painterly and dark. A mild lift of the palette (lightness, chroma) brings them to the game's pitch (spec lift = [light gamma, chroma gain]).
    gam, gain = spec.get("lift", [0.88, 1.12])
    cent = cent.copy()
    cent[:, 0] = 100 * (np.clip(cent[:, 0], 0, 100) / 100) ** gam
    cent[:, 1:] *= gain
    rgbc = snap555(lab_to_rgb(cent))
    white = np.array(spec.get("white", [248, 244, 236]))
    rgbc = np.vstack([rgbc, snap555(white)[None]])          # a true white for eyes, teeth and highlights
    dark = snap555(np.array([np.percentile(px[:, c], 1) for c in range(3)]) * 0.45)
    order = np.argsort(-(0.299 * rgbc[:, 0] + 0.587 * rgbc[:, 1] + 0.114 * rgbc[:, 2]))
    pal = [(0, 0, 0)] + [tuple(int(v) for v in rgbc[i]) for i in order] + [tuple(int(v) for v in dark)]
    palab = to_lab(np.array(pal[1:15], float))

    plum = np.array([0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2] for c in pal], float)

    def feature_pass(idx, x0, y0, bw, bh, ow, oh, ox=0, oy=0):
        """The eyes keep their whites and darks: max-pooling instead of averaging inside each eye's box (a small white or dark stroke would otherwise vanish in the mean)."""
        lum = src.rgb.mean(2)
        wmask = ((lum > 165) & (src.rgb.max(2) - src.rgb.min(2) < 60) & src.alpha).astype(np.float32)
        dmask = ((lum < 55) & src.alpha).astype(np.float32)
        out = idx.copy()
        e = spec["eyes"]
        for (cx, cy, rx, ry) in ((e[0], e[1], 52, 24), (e[2], e[3], 52, 24)):
            def pool(mk):
                im = Image.fromarray(mk, mode="F")
                return np.array(im.resize((ow, oh), Image.BOX, box=(x0, y0, x0 + bw, y0 + bh)))
            wf, df = pool(wmask), pool(dmask)
            k = ow / bw
            ax0, ax1 = int((cx - rx - x0) * k), int((cx + rx - x0) * k) + 1
            ay0, ay1 = int((cy - ry - y0) * k), int((cy + ry - y0) * k) + 1
            for y in range(max(0, ay0), min(oh, ay1)):
                for x in range(max(0, ax0), min(ow, ax1)):
                    yy, xx = y + oy, x + ox
                    if not (0 <= yy < out.shape[0] and 0 <= xx < out.shape[1]) or out[yy, xx] == 0:
                        continue
                    if wf[y, x] > spec.get("eye_white", 0.22) and df[y, x] < 0.5:
                        out[yy, xx] = 1
                    elif df[y, x] > spec.get("eye_dark", 0.45) and plum[out[yy, xx]] > 75:
                        out[yy, xx] = 15
        return out

    def index(r, c, sides):
        m = clean_silhouette(c >= 0.5)
        flat = r.reshape(-1, 3)
        d = ((to_lab(flat)[:, None, :] - palab[None]) ** 2).sum(2)
        idx = (d.argmin(1) + 1).reshape(r.shape[:2]).astype(np.uint8)
        idx[~m] = 0
        idx = despeckle(idx)
        return outline(idx, sides)
    im = Imported()
    im.spec = spec
    im.palette = pal
    im.large = index(*pics["large"], (True, True, True, False))
    mug = index(*pics["mug"], (True, True, True, False))
    mug = feature_pass(mug, fx, fy, fs, fs, 48, 48)
    im.large = feature_pass(im.large, 0, cut, src.w, src.h - cut, ow, oh, max(0, ox), top)
    im.faces["normal"] = mug
    k = 48.0 / fs
    e = spec["eyes"]       # the two eyes' centres in the source: x1 y1 x2 y2
    ex, ey = round(((e[0] + e[2]) / 2 - fx) * k), round(((e[1] + e[3]) / 2 - fy) * k)
    im.eye = (ex, ey)
    im.mini = mini_strip(mug, ey)
    im.hud = _window(mug, ex - 16, ey - 6, 32, 16)
    return im


def mini_strip(face, ey):
    """The "mini" is a 48 x 16 strip of the mug, the whole width and the 16 rows round the eyes (`ey`: the eye line): 12 tiles, the first 8 the left 32 x 16 in rows of four, the last 4 the right 16 x 16
    in rows of two. It is what the battle scene's header draws (AW2's Sonja: the same layout; found by poking each tile of a CO's mini with a colour of its own and reading the header), and the two
    sprites of the Teams page (a 32 x 16 and a 16 x 16)."""
    return _window(face, 0, max(0, min(32, ey - 10)), 48, 16)


def _window(a, x0, y0, w, h):
    out = np.zeros((h, w), np.uint8)
    for y in range(h):
        for x in range(w):
            yy, xx = y0 + y, x0 + x
            if 0 <= yy < a.shape[0] and 0 <= xx < a.shape[1]:
                out[y, x] = a[yy, xx]
    return out


def to_image(idx, palette, scale=1, bg=None):
    h, w = idx.shape
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0) if bg is None else bg + (255,))
    for y in range(h):
        for x in range(w):
            v = idx[y, x]
            if v:
                im.putpixel((x, y), tuple(palette[v]) + (255,))
    return im.resize((w * scale, h * scale), Image.NEAREST) if scale != 1 else im


# --- expressions --------------------------------------------------------------------------------------------------------------------------------------------------

def all_expressions(im, spec):
    """Every expression slot the game uses (happy, sad, angry) that the importer did not get a real picture for shows the neutral face, the picture's own, unedited: nothing is drawn or edited
    (the owner rejected the edited faces). Real expression pictures `art-src/cos/<id>_<expression>.*` are picked up by `pixelart.styled`."""
    for kind in ("happy", "sad", "angry"):
        if kind not in im.faces:
            im.faces[kind] = im.faces["normal"].copy()


# --- the committed art: indexed PNGs ----------------------------------------------------------------------------------------------------------------------------------

ART_DIR = cfg.REPO / "tango-gamesupport-aw2" / "art" / "cos"
FILES = {"large": (128, 160), "face_normal": (48, 48), "face_happy": (48, 48), "face_sad": (48, 48), "face_angry": (48, 48), "mini": (48, 16), "hud": (32, 16)}


def _png(idx, palette):
    im = Image.fromarray(idx.astype(np.uint8), mode="P")
    flat = []
    for c in palette[:16]:
        flat += list(c)
    flat += [0] * (48 - len(flat))
    im.putpalette(flat[:48])
    im.info["transparency"] = 0
    return im


def pictures(im):
    return {"large": im.large, "face_normal": im.faces["normal"], "face_happy": im.faces["happy"], "face_sad": im.faces["sad"], "face_angry": im.faces["angry"], "mini": im.mini, "hud": im.hud}


def write_art(co, im, root=None, name=None):
    """The pictures as indexed PNGs (one palette), and the name graphic (48 x 16, the fixed name palette) set in our own letters (namefont.py)."""
    from . import namefont
    d = (root or ART_DIR) / co
    d.mkdir(parents=True, exist_ok=True)
    for pic, idx in pictures(im).items():
        _png(idx, im.palette).save(d / f"{pic}.png", optimize=True, transparency=0, bits=4)
    ex, ey = im.eye
    (d / "crop.toml").write_text(f"# where the 24-pixel cell of Versus' cards and the 16-row strip of the CO grid start in the mug so that the eyes show (made by `aw2dev co portrait import`)\ncell_x = {max(0, min(24, ex - 12))}\nstrip_y = {max(0, min(32, ey - 8))}\n")
    if name:
        _png(namefont.name_grid(name), [(0, 0, 0)] + namefont.name_rgb()[1:]).save(d / "name.png", optimize=True, transparency=0, bits=4)
    return d


def read_art(co, root=None):
    """-> ({name: indexes}, palette) from the committed PNGs."""
    d = (root or ART_DIR) / co
    out, pal = {}, None
    for name in FILES:
        im = Image.open(d / f"{name}.png")
        out[name] = np.array(im)
        p = im.getpalette()[:48]
        pal = [(0, 0, 0)] + [tuple(p[3 * i:3 * i + 3]) for i in range(1, 16)]
    return out, pal


def _is_illustration(co):
    """Whether the CO's picture is imported in illustration mode (its framing file says `illustration = true`): its outline gets the stricter checks."""
    import tomllib
    try:
        d = tomllib.loads((cfg.REPO / "tango-gamesupport-aw2" / "cos" / f"{co}.toml").read_text())
        side = (cfg.REPO / d["portrait"]["source"]).with_suffix(".toml")
        return bool(tomllib.loads(side.read_text()).get("illustration"))
    except Exception:
        return False


def _is_pixelart(co):
    """Whether the CO's picture is a direct pixel-art import (`pixelart = true` in its framing file)."""
    import tomllib
    try:
        d = tomllib.loads((cfg.REPO / "tango-gamesupport-aw2" / "cos" / f"{co}.toml").read_text())
        side = (cfg.REPO / d["portrait"]["source"]).with_suffix(".toml")
        return bool(tomllib.loads(side.read_text()).get("pixelart"))
    except Exception:
        return False


def _framing(co):
    import tomllib
    try:
        d = tomllib.loads((cfg.REPO / "tango-gamesupport-aw2" / "cos" / f"{co}.toml").read_text())
        return tomllib.loads((cfg.REPO / d["portrait"]["source"]).with_suffix(".toml").read_text())
    except Exception:
        return {}


def fringe_problems(co, pics, pal, light=70.0, chroma=15.0):
    """A picture imported with `fringe = "light"` has no white halo: no figure pixel on the outer edge (next to the outline, so next to the empty side) is light (Lab L above `light`) and nearly colourless
    (chroma under `chroma`), unless it is listed in the framing file's `edge_protect` ([[x, y], ...] pixels of the large art). -> list of problems."""
    spec = _framing(co)
    if spec.get("fringe") != "light":
        return []
    keep = {tuple(p) for p in spec.get("edge_protect", [])}
    bad = []
    lab = to_lab(np.array(pal, float))
    lt, ch = lab[:, 0], np.hypot(lab[:, 1], lab[:, 2])
    for name in ("large", "face_normal"):
        a = pics[name]
        o = a == 15
        ins = np.zeros_like(o)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx or dy:
                    ins |= shift(o, dx, dy)
        m = ins & ~o & (a != 0) & (lt[a] > light) & (ch[a] < chroma)
        pts = [(int(x), int(y)) for y, x in zip(*np.where(m)) if name != "large" or (int(x), int(y)) not in keep]
        if pts:
            bad.append(f"{name}: {len(pts)} light, colourless pixels on the outer edge (a white halo): {pts[:6]}")
    return bad


def ramp_shades(src_rgb, out_idx, pal, dark_l=35.0, dark_c=14.0, bin_l=5.0, min_cells=20):
    """(source shades, output shades) of the dark, nearly colourless cells (the uniform): the source's distinct tones (Lab L in bins of `bin_l`, each with at least `min_cells` cells) and the number of
    distinct palette entries those cells take in the output."""
    lab = to_lab(src_rgb.astype(float))
    m = (lab[..., 0] < dark_l) & (np.hypot(lab[..., 1], lab[..., 2]) < dark_c) & (out_idx != 0) & (out_idx != 15)
    bins = np.bincount((lab[..., 0][m] // bin_l).astype(int))
    return int((bins >= min_cells).sum()), int(len(np.unique(out_idx[m])))


def ramp_problems(co, pics, pal):
    """A picture imported with `dark_ramp` keeps the uniform's shades: its dark cells take at least min(4, the source's distinct dark shades) different palette entries. -> list of problems."""
    spec = _framing(co)
    if not spec.get("dark_ramp"):
        return []
    import tomllib
    d = tomllib.loads((cfg.REPO / "tango-gamesupport-aw2" / "cos" / f"{co}.toml").read_text())
    im = import_co({"source": d["portrait"]["source"], **{k: v for k, v in d["portrait"].items() if k != "source"}})
    bad = []
    for name, src in (("large", im.src["large"]),):
        have, got = ramp_shades(src, pics[name], pal)
        if got < min(4, have):
            bad.append(f"{name}: the uniform has {got} distinct shades, the source has {have} (at least {min(4, have)} wanted): the dark ramp is merged")
    return bad


def lightness_problems(co, pics, pal, lo=0.3, hi=0.8):
    """A direct pixel-art import keeps every pixel's lightness class: no source pixel above `hi` (Lab lightness 0..1) takes a palette colour below `lo`, and none below `lo` one above `hi` (an eye white
    gone black, a black gone white). The source cells are re-read through the importer (`Imported.src`: the figure's native colours at the output's resolution). -> list of problems."""
    import tomllib
    if not _is_pixelart(co):
        return []
    d = tomllib.loads((cfg.REPO / "tango-gamesupport-aw2" / "cos" / f"{co}.toml").read_text())
    im = import_co({"source": d["portrait"]["source"], **{k: v for k, v in d["portrait"].items() if k != "source"}})
    bad = []
    pl = to_lab(np.array(pal, float))[:, 0] / 100
    for name, src in (("large", im.src["large"]), ("face_normal", im.src["face"])):
        a = pics[name]
        m = (a != 0) & (a != 15)      # the added outline sits outside her pixels
        ls = to_lab(src.astype(float))[..., 0] / 100
        la = pl[a]
        white = int((m & (ls > hi) & (la < lo)).sum())
        black = int((m & (ls < lo) & (la > hi)).sum())
        if white:
            bad.append(f"{name}: {white} source pixels lighter than {hi} take a palette colour darker than {lo} (a white gone dark)")
        if black:
            bad.append(f"{name}: {black} source pixels darker than {lo} take a palette colour lighter than {hi}")
    return bad


def outline_problems(name, a, pal, blend=True):
    """The outline of an illustration import against Kanbei's (AW2's own figures): continuous in 8-connectivity (no opaque pixel that is not outline touches a transparent one, corners included), one pixel
    wide (every outline pixel touching the empty side is a single layer: no empty pixel is two layers deep in outline), outline colour only (index 15), no fringe (the darkest other tone of the palette is clearly
    lighter than the outline, so the uniform's black does not blend into it), and the outline colour is hardly used inside the figure (at most 3% of its pixels)."""
    bad = []
    t = a == 0
    opaque = ~t
    near8 = np.zeros_like(t)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                near8 |= shift(t, dx, dy)
    gaps = near8 & opaque & (a != 15)
    if name == "large":
        gaps[-1, :] = False
    if gaps.any():
        bad.append(f"{name}: {int(gaps.sum())} figure pixels touch transparency (diagonals included) without being outline: the outline has gaps")
    layer = np.zeros_like(t)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            if dx or dy:
                layer |= shift(a == 15, dx, dy)
    # a pixel of the outline whose every 8 neighbours are outline or transparent and which touches no figure colour is a second layer
    inner = (a == 15)
    figure = opaque & (a != 15)
    figure_near = np.zeros_like(t)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            figure_near |= shift(figure, dx, dy)
    double = inner & ~figure_near & ~(near8 & False)
    if name == "large":
        double[-1, :] = False
    if double.sum() > 0:
        bad.append(f"{name}: {int(double.sum())} outline pixels with no figure colour beside them: the outline is more than one pixel wide")
    interior = inner & ~near8
    if figure.sum() and interior.sum() > 0.03 * opaque.sum():
        bad.append(f"{name}: {int(interior.sum())} outline-coloured pixels inside the figure (more than 3%): the uniform's black blends into the outline")
    if pal is not None and blend:
        lab = lambda c: to_lab(np.array([c], float))[0]
        o = lab(pal[15])
        used = sorted(set(np.unique(a).tolist()) - {0, 15})
        if used:
            d = min(float(np.linalg.norm(lab(pal[i]) - o)) for i in used)
            if d < 8.0:
                bad.append(f"{name}: the darkest tone beside the outline is only {d:.1f} Lab away from it (at least 8): it blends in")
    return bad


def lint_art(co, root=None, max_specks_large=600, max_specks_small=220):
    """-> list of problems of a CO's committed art: sizes, one palette of at most 15 colours + transparent shared by every picture, a solid outline (index 15) wherever the silhouette meets
    transparency inside the picture (no coloured pixel touches transparency), and no noise: opaque pixels no 4-neighbour shares the colour of. AW2's own 19 figures have 183 to 562 of those
    (shading is made of them) and their faces 102 to 202, so the limits are 600 and 220: the check is for a speckled JPEG, not for detail."""
    bad = []
    try:
        pics, pal = read_art(co, root)
    except Exception as e:
        return [f"cannot read the art: {e}"]
    d = (root or ART_DIR) / co
    illus = _is_illustration(co) or co == "asuka"      # her outline gets the stricter checks whichever importer made the picture
    pals = {tuple(Image.open(d / f"{n}.png").getpalette()[:48]) for n in FILES}
    if (d / "name.png").exists():
        nm = np.array(Image.open(d / "name.png"))
        if nm.shape != (16, 48):
            bad.append(f"name: {nm.shape[1]} x {nm.shape[0]}, wanted 48 x 16")
    else:
        bad.append("name.png missing")
    if len(pals) != 1:
        bad.append("the pictures do not share one palette")
    for name, (w, h) in FILES.items():
        a = pics[name]
        if a.shape != (h, w):
            bad.append(f"{name}: {a.shape[1]} x {a.shape[0]}, wanted {w} x {h}")
            continue
        if int(a.max()) > 15:
            bad.append(f"{name}: palette index {int(a.max())} (at most 15)")
        if not (a != 0).any():
            bad.append(f"{name}: empty")
        if name in ("large", "face_normal", "face_happy", "face_sad", "face_angry"):
            transparent = a == 0
            near = np.zeros_like(transparent)
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                near |= shift(transparent, dx, dy)
            # the picture's own border is not transparency: a pixel at the edge is not open
            open_px = near & ~transparent & (a != 15)
            if name == "large":
                open_px[-1, :] = False
            if open_px.any():
                bad.append(f"{name}: {int(open_px.sum())} coloured pixels touch transparency without an outline")
            specks = 0
            for y in range(a.shape[0]):
                for x in range(a.shape[1]):
                    v = a[y, x]
                    if v in (0, 15):
                        continue
                    nb = [a[yy, xx] for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)) if 0 <= yy < a.shape[0] and 0 <= xx < a.shape[1]]
                    if v not in nb:
                        specks += 1
            if illus:
                # a direct pixel-art import keeps the picture's own blacks, which may sit close to the outline colour: that blend is not checked for it
                bad += outline_problems(name, a, pal, blend=not _is_pixelart(co))
            limit = max_specks_large if name == "large" else max_specks_small
            if name == "large" and _framing(co).get("max_specks"):
                limit = int(_framing(co)["max_specks"])      # a picture with a dark ramp keeps its folds' single cells
            if specks > limit:
                bad.append(f"{name}: {specks} isolated pixels (at most {limit})")
    bad += lightness_problems(co, pics, pal)
    bad += fringe_problems(co, pics, pal)
    bad += ramp_problems(co, pics, pal)
    return bad
