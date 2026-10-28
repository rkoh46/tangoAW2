"""The picture -> GBA world map conversion (docs/dev/worldmap.md).

Pure numpy + Pillow, deterministic, no ROM: the owner's picture is resampled to the map's size, its pixels are classed into the sea and the
nations by colour, the colours are quantised to nine 15-colour palettes whose entries each belong to one class (so a nation can be re-tinted by
swapping its entries), every 8x8 cell takes the palette that draws it best, and the cells are deduplicated (flips count as one tile) and, if
there are still too many, the most alike folded together. Nothing is dithered and nothing is hand-painted.
"""
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

MAX_TILES = 768          # BG tiles the map layer holds (AW2's 704 and 64 more where BG1's tilemap is); tile 0 stays blank
PAL_COUNT = 9            # BG palettes 6..14
PAL_COLOURS = 15         # usable colours a palette (slot 0 is transparent)
WEIGHTS = np.array([3.0, 4.0, 2.0])


@dataclass
class Map:
    name: str
    width: int
    height: int
    region_names: list
    tiles: np.ndarray            # (n, 64) uint8 palette indexes; tile 0 blank
    cells: np.ndarray            # (rows, cols) uint16 tilemap entries (tile | flips | palette << 12)
    palette: np.ndarray          # (9, 16, 3) uint8 5-bit channels
    tags: np.ndarray             # (9, 16) uint8: 0 sea / unused, 1..5 nations
    tinted: np.ndarray           # (9, 16, 3) uint8 5-bit channels: the entries as Black Hole's
    mask: np.ndarray             # (height, width) uint8 class per pixel, 0 sea
    slots: list                  # [(region, x, y)]
    stats: dict = field(default_factory=dict)
    reference: np.ndarray = None  # the resampled picture (height, width, 3) uint8


def load_config(path):
    path = Path(path)
    cfg = tomllib.loads(path.read_text())
    cfg["_dir"] = path.parent
    return cfg


# ---------------------------------------------------------------- the picture

def resample(cfg):
    im = Image.open(cfg["_dir"] / cfg["source"]).convert("RGB").crop(tuple(cfg["crop"]))
    w, h = cfg["size"]
    return np.asarray(im.resize((w, h), Image.LANCZOS)).astype(float), im.size


def _feat(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    return np.stack([(r - g) * 2.0, ((r + g) / 2 - b) * 1.5, (r + g + b) / 3 * 0.5], -1)


def _components(mask):
    """4-connected labels of a boolean mask (0 = none) and the areas."""
    h, w = mask.shape
    lab = np.zeros((h, w), np.int32)
    areas = [0]
    n = 0
    for y0 in range(h):
        for x0 in range(w):
            if mask[y0, x0] and not lab[y0, x0]:
                n += 1
                lab[y0, x0] = n
                stack = [(y0, x0)]
                a = 0
                while stack:
                    y, x = stack.pop()
                    a += 1
                    for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
                        if 0 <= yy < h and 0 <= xx < w and mask[yy, xx] and not lab[yy, xx]:
                            lab[yy, xx] = n
                            stack.append((yy, xx))
                areas.append(a)
    return lab, areas


def _tidy(cl, nclass):
    """A class patch too small to be a nation (the text strokes inside a land, a dot of the grey coast line) reads as what surrounds it (the sea too)."""
    h, w = cl.shape
    for _ in range(3):
        for c in range(1, nclass):
            lab, areas = _components(cl == c)
            for i, a in enumerate(areas):
                if i and a < 150:
                    m = lab == i
                    ring = np.zeros_like(m)
                    pad = np.pad(m, 1)
                    for dy in range(3):
                        for dx in range(3):
                            ring |= pad[dy:dy + h, dx:dx + w]
                    ring &= ~m
                    around = np.bincount(cl[ring], minlength=nclass)
                    around[c] = 0
                    if around.sum():
                        cl[m] = around.argmax()
    return cl


def classify(small, cfg, src_size):
    """Per pixel: 0 the sea, 1.. the nations (by the colour of each nation's land)."""
    h, w = small.shape[:2]
    sx, sy = src_size[0] / w, src_size[1] / h
    F = _feat(small)
    refs = []
    for (x, y) in cfg["regions"]["seeds"]:
        xs, ys = int((x - cfg["crop"][0]) / sx), int((y - cfg["crop"][1]) / sy)
        refs.append(F[max(0, ys - 2):ys + 3, max(0, xs - 2):xs + 3].reshape(-1, 3).mean(0))
    refs = np.array(refs)
    cl = ((F[:, :, None, :] - refs[None, None]) ** 2).sum(-1).argmin(-1).astype(np.uint8)
    land = cl != 0
    # Specks of "land" in the sea (text, dashes, the compass) are sea; the sea inside the land (a glow, a dot) is land.
    lab, areas = _components(land)
    for i, a in enumerate(areas):
        if i and a < 40:
            land[lab == i] = False
    slab, sareas = _components(~land)
    border = set(slab[0, :]) | set(slab[-1, :]) | set(slab[:, 0]) | set(slab[:, -1])
    for i, a in enumerate(sareas):
        if i and i not in border and a < 60:
            land[slab == i] = True
    # (areas of the picture that are not map: the compass)
    for (x0, y0, x1, y1) in cfg["regions"].get("sea_boxes", []):
        land[int((y0 - cfg["crop"][1]) / sy):int((y1 - cfg["crop"][1]) / sy) + 1, int((x0 - cfg["crop"][0]) / sx):int((x1 - cfg["crop"][0]) / sx) + 1] = False
    cl = np.where(land, cl, 0).astype(np.uint8)
    cl[land & (cl == 0)] = 1   # (a filled hole: its class follows below)
    cl = _tidy(cl, len(refs))
    land = cl != 0
    # A pixel's class follows the nearest "core" (a pixel whose 5x5 neighbourhood is all one class): coast outlines and fringes that
    # read as another nation (the grey coast line round every land) take their land's.
    core = np.zeros_like(land)
    pad = np.pad(cl, 2, constant_values=255)
    same = np.ones_like(land)
    for dy in range(5):
        for dx in range(5):
            same &= pad[dy:dy + h, dx:dx + w] == cl
    core = same & land
    out = np.where(core, cl, 0).astype(np.uint8)
    frontier = [(y, x) for y, x in zip(*np.nonzero(core))]
    seen = core.copy()
    while frontier:
        nxt = []
        for y, x in frontier:
            for yy, xx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1), (y - 1, x - 1), (y - 1, x + 1), (y + 1, x - 1), (y + 1, x + 1)):
                if 0 <= yy < h and 0 <= xx < w and land[yy, xx] and not seen[yy, xx]:
                    seen[yy, xx] = True
                    out[yy, xx] = out[y, x]
                    nxt.append((yy, xx))
        frontier = nxt
    out = np.where(land & ~seen, cl, out)      # (a land with no core keeps its own reading)
    # The coast's anti-aliased rim reads as sea: sea pixels beside the land and darker than the sea take the land's class.
    lum = small @ np.array([0.3, 0.59, 0.11])
    sea_lum = np.median(lum[out == 0])
    for _ in range(2):
        pad = np.pad(out, 1)
        nb = np.zeros_like(out)
        for dy, dx in ((0, 1), (2, 1), (1, 0), (1, 2)):
            n = pad[dy:dy + h, dx:dx + w]
            nb = np.where((nb == 0) & (n != 0), n, nb)
        out = np.where((out == 0) & (nb != 0) & (lum < sea_lum - 5), nb, out).astype(np.uint8)
    return _tidy(out, len(refs))


# ---------------------------------------------------------------- palettes

def _q5(c):
    """8-bit colour(s) -> the 5-bit channels the GBA keeps (round to nearest)."""
    return np.clip(np.rint(np.asarray(c, float) / 255 * 31), 0, 31).astype(np.uint8)


def _c8(c5):
    return np.asarray(c5, float) * 255 / 31


def _kmeans(px, k, iters=12):
    """Deterministic k-means (centres start at luminance quantiles) over (n, 3) pixels."""
    if len(px) == 0:
        return np.zeros((k, 3))
    order = np.argsort(px @ np.array([0.3, 0.59, 0.11]), kind="stable")
    centres = np.array([px[order[int((i + 0.5) * len(px) / k)]] for i in range(k)], float)
    for _ in range(iters):
        d = (((px[:, None, :] - centres[None]) ** 2) * WEIGHTS).sum(-1)
        a = d.argmin(1)
        for i in range(k):
            m = a == i
            if m.any():
                centres[i] = px[m].mean(0)
    return centres


def _plan(cfg):
    out = []
    for p in cfg["palette"]:
        counts = {int(k) if k != "S" else 0: int(v) for k, v in p.items() if k not in ("like",)}
        assert sum(counts.values()) <= PAL_COLOURS, counts
        out.append((counts, p.get("like")))
    assert len(out) == PAL_COUNT
    return out


def fit_palettes(X, T, plan, rounds=10, penalty=4000.0):
    """X (cells, 64, 3) pixel colours (0..255), T (cells, 64) tags. Returns (entries (9, 15, 3) float, tags (9, 15), assignment (cells,))."""
    ncell = len(X)
    ent = np.zeros((PAL_COUNT, PAL_COLOURS, 3))
    gtag = np.full((PAL_COUNT, PAL_COLOURS), 255, np.uint8)
    flat = X.reshape(-1, 3)
    ftag = T.reshape(-1)

    def seed(p, counts, px_of_tag):
        i = 0
        for tag in sorted(counts):
            k = counts[tag]
            ent[p, i:i + k] = _kmeans(px_of_tag(tag), k)
            gtag[p, i:i + k] = tag
            i += k
        # unused slots repeat the first entry (never referenced, kept valid)
        while i < PAL_COLOURS:
            ent[p, i] = ent[p, 0]
            gtag[p, i] = gtag[p, 0]
            i += 1

    for p, (counts, like) in enumerate(plan):
        seed(p, counts, lambda tag: flat[ftag == tag])

    def cost(p):
        d = (((X[:, :, None, :] - ent[p][None, None]) ** 2) * WEIGHTS).sum(-1)       # (cells, 64, 15)
        d = d + penalty * (T[:, :, None] != gtag[p][None, None])
        return d.min(-1).sum(-1)

    assign = np.zeros(ncell, int)
    for rnd in range(rounds):
        costs = np.stack([cost(p) for p in range(PAL_COUNT)])        # (9, cells)
        assign = costs.argmin(0)
        # an empty palette that is "like" another takes half of that one's tiles: split by the tiles' mean lightness
        for p, (counts, like) in enumerate(plan):
            if like is not None and not (assign == p).any():
                q = like
                mine = np.nonzero(assign == q)[0]
                if len(mine) >= 2:
                    lum = X[mine].mean(1) @ np.array([0.3, 0.59, 0.11])
                    assign[mine[lum < np.median(lum)]] = p
                    ent[p] = ent[q]
                    gtag[p] = gtag[q]
        for p, (counts, like) in enumerate(plan):
            mine = X[assign == p].reshape(-1, 3)
            mt = T[assign == p].reshape(-1)
            if len(mine) == 0:
                continue
            i = 0
            for tag in sorted(counts):
                k = counts[tag]
                px = mine[mt == tag]
                if len(px):
                    ent[p, i:i + k] = _kmeans(px, k, 6)
                gtag[p, i:i + k] = tag
                i += k
            while i < PAL_COLOURS:
                ent[p, i] = ent[p, 0]
                gtag[p, i] = gtag[p, 0]
                i += 1
    costs = np.stack([cost(p) for p in range(PAL_COUNT)])
    return ent, gtag, costs.argmin(0)


def _snap(ent, gtag):
    """Entries to 5 bits; return (5-bit (9, 15, 3), tags). Duplicate colours stay (they are free)."""
    return _q5(ent), gtag


def pixels_to_indexes(X, T, ent5, gtag, assign, penalty=4000.0):
    """Index (1..15) of the entry that draws each pixel of each cell in its palette."""
    ent = _c8(ent5)
    idx = np.zeros(X.shape[:2], np.uint8)
    for p in range(PAL_COUNT):
        m = assign == p
        if not m.any():
            continue
        d = (((X[m][:, :, None, :] - ent[p][None, None]) ** 2) * WEIGHTS).sum(-1)
        d = d + penalty * (T[m][:, :, None] != gtag[p][None, None])
        idx[m] = d.argmin(-1) + 1
    return idx


# ---------------------------------------------------------------- tiles

def _flip(px, f):
    a = px.reshape(8, 8)
    if f & 1:
        a = a[:, ::-1]
    if f & 2:
        a = a[::-1, :]
    return np.ascontiguousarray(a).reshape(64)


def build_tiles(idx, assign, ent5, max_tiles):
    """Cells' pixels (cells, 64) + palette per cell -> (tiles list, cell entries (tile, flip, palette)). Flips are one tile; too many are folded."""
    uniq = {}
    order = []
    cellref = []
    for c in range(len(idx)):
        p = int(assign[c])
        best = None
        for f in range(4):
            t = _flip(idx[c], f)
            key = t.tobytes()
            if best is None or key < best[0]:
                best = (key, f, t)
        key = (p, best[0])
        if key not in uniq:
            uniq[key] = len(order)
            order.append((p, best[2]))
        cellref.append((uniq[key], best[1]))
    weights = np.zeros(len(order))
    for t, _ in cellref:
        weights[t] += 1
    folded = 0
    rep = list(range(len(order)))
    if len(order) > max_tiles - 1:
        ent = _c8(ent5)
        col = np.stack([ent[p][t.astype(int) - 1] for p, t in order])      # (n, 64, 3)
        alive = np.ones(len(order), bool)
        pal = np.array([p for p, _ in order])
        # shade (four 4x4 means) counts more than detail: an 8x8 patch of the wrong shade is what shows
        def feat(c):
            c = c.reshape(-1, 8, 8, 3)
            means = np.stack([c[:, :4, :4].mean((1, 2)), c[:, :4, 4:].mean((1, 2)), c[:, 4:, :4].mean((1, 2)), c[:, 4:, 4:].mean((1, 2))], 1)
            full = np.repeat(np.repeat(means.reshape(-1, 2, 2, 3), 4, 1), 4, 2)
            return np.concatenate([(2.0 * means).reshape(len(c), -1), (c - full).reshape(len(c), -1)], 1)
        f = feat(col)
        while alive.sum() > max_tiles - 1:
            best = None
            for p in range(PAL_COUNT):
                ids = np.nonzero(alive & (pal == p))[0]
                if len(ids) < 2:
                    continue
                d = ((f[ids][:, None, :] - f[ids][None]) ** 2).sum(-1)
                np.fill_diagonal(d, np.inf)
                cost = d * weights[ids][:, None]
                i, j = np.unravel_index(cost.argmin(), cost.shape)
                if best is None or cost[i, j] < best[0]:
                    best = (cost[i, j], ids[i], ids[j])
            _, a, b = best
            alive[a] = False
            weights[b] += weights[a]
            for k in range(len(rep)):
                if rep[k] == a:
                    rep[k] = b
            folded += 1
    tiles = [np.zeros(64, np.uint8)]
    number = {}
    for t in range(len(order)):
        if rep[t] == t:
            number[t] = len(tiles)
            tiles.append(order[t][1])
    entries = []
    for c, (t, f) in enumerate(cellref):
        r = rep[t]
        # (folded tiles keep the cell's own flip: a flip undoes itself)
        entries.append(number[r] | ((f & 1) << 10) | ((f >> 1) << 11) | (int(assign[c]) + 6 << 12))
    return np.array(tiles), entries, len(order), folded


# ---------------------------------------------------------------- tint

def tint(c5, cfg):
    t = cfg["tint"]
    c = _c8(c5)
    lum = c @ np.array([0.3, 0.59, 0.11])
    u = np.clip((lum - t["lo"]) / (t["hi"] - t["lo"]), 0, 1)[..., None]
    out = np.array(t["dark"], float) * (1 - u) + np.array(t["light"], float) * u
    return _q5(out)


# ---------------------------------------------------------------- slots

def flag_slots(mask, counts, border=5):
    """Dummy flag places, by nation: farthest-point sampling over the land that is at least `border` pixels from any other class."""
    h, w = mask.shape
    slots = []
    for region, n in enumerate(counts, 1):
        m = mask == region
        # distance (chessboard, capped) to anything that is not this region
        dist = np.zeros((h, w), int)
        cur = m.copy()
        for d in range(1, border + 1):
            pad = np.pad(cur, 1, constant_values=False)
            cur = cur & pad[:-2, 1:-1] & pad[2:, 1:-1] & pad[1:-1, :-2] & pad[1:-1, 2:]
            dist += cur
        ys, xs = np.nonzero(dist >= border)
        if len(ys) == 0:
            ys, xs = np.nonzero(dist >= 1)
        pts = list(zip(xs.tolist(), ys.tolist()))
        chosen = []
        # start at the centroid-nearest point
        cx, cy = np.mean(xs), np.mean(ys)
        first = min(pts, key=lambda p: ((p[0] - cx) ** 2 + (p[1] - cy) ** 2, p[1], p[0]))
        chosen.append(first)
        while len(chosen) < n and len(chosen) < len(pts):
            far = max(pts, key=lambda p: (min((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 for q in chosen), -p[1], -p[0]))
            chosen.append(far)
        slots += [(region, x, y) for x, y in chosen]
    return slots


# ---------------------------------------------------------------- the whole conversion

def convert(config_path):
    cfg = load_config(config_path)
    small, src_size = resample(cfg)
    h, w = small.shape[:2]
    mask = classify(small, cfg, src_size)
    # (the 5-bit picture is what the palettes are fitted to)
    ref5 = _q5(small)
    X = small.reshape(h // 8, 8, w // 8, 8, 3).transpose(0, 2, 1, 3, 4).reshape(-1, 64, 3)
    T = mask.reshape(h // 8, 8, w // 8, 8).transpose(0, 2, 1, 3).reshape(-1, 64)
    plan = _plan(cfg)
    ent, gtag, assign = fit_palettes(X, T, plan)
    ent5, gtag = _snap(ent, gtag)
    idx = pixels_to_indexes(X, T, ent5, gtag, assign)
    tiles, cells, n_unique, folded = build_tiles(idx, assign, ent5, MAX_TILES)
    palette = np.zeros((PAL_COUNT, 16, 3), np.uint8)
    palette[:, 1:] = ent5
    palette[:, 0] = ent5[:, 0]
    tags = np.zeros((PAL_COUNT, 16), np.uint8)
    tags[:, 1:] = np.where(gtag == 255, 0, gtag)
    tinted = tint(palette, cfg)
    cols = w // 8
    cell_arr = np.array(cells, np.uint16).reshape(h // 8, cols)
    m = Map(cfg["name"], w, h, cfg["regions"]["names"], tiles, cell_arr, palette, tags, tinted, mask,
            flag_slots(mask, cfg["slots"]["counts"]), reference=np.asarray(small, np.uint8))
    rend = render(m)
    err = (rend.astype(float) - ref5.astype(float) * 255 / 31) ** 2
    mse = err.mean()
    m.stats = {
        "tiles": len(tiles), "unique_before_folding": n_unique, "folded": folded,
        "palettes_used": len(set(int(a) for a in assign)),
        "psnr": 99.0 if mse == 0 else float(10 * np.log10(255 ** 2 / mse)),
    }
    return m


# ---------------------------------------------------------------- decoding (what the GBA would draw)

def render(m, conquered=(), mask_out=False):
    """The map as the GBA's BG would draw it from tiles, tilemap and palettes (RGB uint8, height x width); `conquered` regions in Black Hole's colours."""
    pal = m.palette.copy()
    for p in range(PAL_COUNT):
        for i in range(16):
            if int(m.tags[p, i]) in conquered:
                pal[p, i] = m.tinted[p, i]
    rgb = _c8(pal).round().astype(np.uint8)
    out = np.zeros((m.height, m.width, 3), np.uint8)
    for cy in range(m.height // 8):
        for cx in range(m.width // 8):
            e = int(m.cells[cy, cx])
            t = m.tiles[e & 0x3FF]
            f = (e >> 10) & 3
            px = _flip(t, f)
            out[cy * 8:cy * 8 + 8, cx * 8:cx * 8 + 8] = rgb[(e >> 12) - 6][px].reshape(8, 8, 3)
    return out
