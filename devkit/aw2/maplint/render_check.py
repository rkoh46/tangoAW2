"""Render-based tile check (docs/dev/map-lint.md, rule RN01): the game's own picture of a map against the drawings the games use. For the transition tiles only (river, shoal, bridge
and the coast tiles of the sea) every cell of the picture (16 x 16 pixels, no unit on it) is compared with the set of drawings the reference pictures have for the same tile id and
4-neighbour class (`rules.trans_key`); a drawing the games never use there is flagged. Exact comparison, no tolerance: water is animated, so the reference must hold every phase
(the BH Campaign's 35 pictures give hundreds of samples a tile; a key with fewer than MIN_SAMPLES samples has no verdict).

Pictures: `m<N>_full.png` (or `_fogoff`, fog off) as `aw2dev maps boot` (BH) and `aw2dev campaign sheets` (Emerald Sun) keep them, 16 pixels a cell, the whole map, nothing from the games committed."""
import re
from pathlib import Path
from PIL import Image
from . import rules

CELL = 16
MIN_SAMPLES = 6
CLASSES = set("-=,~")


def picture_for(dirs, name):
    """The picture file of map `name` (es05 -> m5_full.png, bh12 -> m12_full.png) in the first of `dirs` that has it."""
    n = int(re.sub(r"\D", "", name))
    for d in dirs:
        for view in ("full", "fogoff"):
            p = Path(d) / f"m{n}_{view}.png"
            if p.exists():
                return p
    return None


def cells(m, picture):
    """[(x, y, key, crop bytes)] for the checkable cells of map m in its picture."""
    G = rules.Grid(m)
    im = Image.open(picture).convert("RGB")
    if im.size != (G.w * CELL, G.h * CELL):
        return None
    units = {(u["x"], u["y"]) for u in (m.units or [])}
    out = []
    for y in range(G.h):
        for x in range(G.w):
            if G.g[y][x] not in CLASSES or (x, y) in units:
                continue
            key = rules.trans_key(G, x, y)
            if key is None:
                continue
            # (sea inland, far from every coast, is one plain tile: only the coast cells are interesting)
            if key[0] == "sea" and key[1] == 0:
                continue
            # (tall things shade the cell to their right, and a cell drawn beside a picture's edge or a unit's overlay differs: the left neighbour's kind is part of the key)
            shade = G.at(x - 1, y) in "f^HBCAPTbcapt12345IZ#"
            out.append((x, y, (G.t[y][x], shade) + tuple(key), im.crop((x * CELL, y * CELL, x * CELL + CELL, y * CELL + CELL)).tobytes()))
    return out


def look_of(m, picture=None):
    """The picture's look (the games draw the same tile in other colours on snow, wasteland, in the desert, in rain or fog): the most common pixel colour of its plain cells."""
    if picture is None:
        return None
    G = rules.Grid(m)
    im = Image.open(picture).convert("RGB")
    cnt = {}
    for y in range(G.h):
        for x in range(G.w):
            if G.g[y][x] == ".":
                px = im.getpixel((x * CELL + 2, y * CELL + 13))
                cnt[px] = cnt.get(px, 0) + 1
    return max(cnt.items(), key=lambda kv: kv[1])[0] if cnt else None


def learn(pairs):
    """{(look, key): [crop bytes, ...]} from [(map, picture)]."""
    ref = {}
    for m, p in pairs:
        cs = cells(m, p)
        if cs is None:
            continue
        lk = look_of(m, p)
        for x, y, key, crop in cs:
            ref.setdefault((lk, key), []).append(crop)
    return ref


def stable(crops):
    """The pixels all the reference drawings of a tile agree on (the rest is water's animation): {byte offset of the pixel: its three bytes} of the majority colour held by 90% or more."""
    n = len(crops)
    out = {}
    for px in range(0, CELL * CELL * 3, 3):
        cnt = {}
        for c in crops:
            v = c[px:px + 3]
            cnt[v] = cnt.get(v, 0) + 1
        v, k = max(cnt.items(), key=lambda kv: kv[1])
        if k >= 0.9 * n:
            out[px] = v
    return out


def check(m, picture, ref):
    """Problems of one map against the reference: [(x, y, text)]; a cell is flagged when a pixel the games always draw one colour in is another colour in the picture."""
    cs = cells(m, picture)
    if cs is None:
        return None
    lk = look_of(m, picture)
    cache = {}
    out = []
    for x, y, key, crop in cs:
        crops = ref.get((lk, key))
        if not crops or len(crops) < MIN_SAMPLES:
            continue
        if (lk, key) not in cache:
            cache[(lk, key)] = stable(crops)
        st = cache[(lk, key)]
        wrong = sum(1 for px, v in st.items() if crop[px:px + 3] != v)
        if wrong > max(12, 0.30 * len(st)):          # (a few pixels more or less are the water's animation phase; a wrong tile differs in dozens)
            out.append((x, y, f"tile 0x{key[0]:03X} ({key[2]} {''.join(map(str, key[3:]))}): {wrong} of {len(st)} fixed pixels differ from the {len(crops)} reference drawings of it"))
    return out
