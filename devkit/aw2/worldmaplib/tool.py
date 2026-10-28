"""The worldmap kit's operations: convert, preview, check (docs/dev/worldmap.md)."""
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from .. import cfg as dcfg
from . import binfmt, convert

REPO = dcfg.REPO
SRC_DIR = REPO / "art-src" / "worldmap"


def config_path(name):
    p = SRC_DIR / f"{name}_world.toml"
    if not p.exists():
        raise SystemExit(f"no world map source '{name}': {p} does not exist (sources: {', '.join(sorted(x.stem[:-6] for x in SRC_DIR.glob('*_world.toml')))})")
    return p


def bin_path(name):
    c = convert.load_config(config_path(name))
    return REPO / c["output"]


def do_convert(name):
    m = convert.convert(config_path(name))
    p = bin_path(name)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(binfmt.pack(m))
    return m, p


def load(name):
    c = convert.load_config(config_path(name))
    return binfmt.unpack(bin_path(name).read_bytes(), c["regions"]["names"]), c


# --------------------------------------------------------------- budgets and checks

def budgets(m):
    """(label, used, limit) for every budget the GBA sets."""
    return [
        ("tiles (tile 0 blank)", len(m.tiles), convert.MAX_TILES),
        ("palettes", len(m.palette), convert.PAL_COUNT),
        ("colours a palette", 15, convert.PAL_COLOURS),
        ("map width / 8", m.width // 8, 64),
        ("map height / 8", m.height // 8, 32),
        ("tilemap bytes (two screens)", 2 * 32 * 32 * 2, 0x1000),
    ]


def check(name):
    """Returns a list of problems (empty: all good)."""
    problems = []
    m, c = load(name)
    for label, used, limit in budgets(m):
        if used > limit:
            problems.append(f"{label}: {used} over the budget {limit}")
    if m.width % 8 or m.height % 8 or m.width > 512 or m.height > 256:
        problems.append(f"size {m.width}x{m.height} does not fit the map layer (multiples of 8, at most 512x256)")
    if int(m.tiles[0].max()) != 0:
        problems.append("tile 0 is not blank")
    if int(m.cells.max() & 0x3FF) >= len(m.tiles):
        problems.append("a cell names a tile that does not exist")
    for e in m.cells.reshape(-1):
        if not 6 <= (int(e) >> 12) < 6 + convert.PAL_COUNT:
            problems.append("a cell's palette is outside BG palettes 6..14")
            break
    if (m.tiles[1:] == 0).any(axis=1).any():
        problems.append("a tile draws the transparent slot 0")
    # every region exists, is a decent size, and its entries are tagged
    for r in range(1, len(m.region_names)):
        area = int((m.mask == r).sum())
        if area < 150:
            problems.append(f"region {m.region_names[r]} covers only {area} pixels")
        if not (m.tags == r).any():
            problems.append(f"no palette entry draws {m.region_names[r]}")
    # the regions cover the land: the picture's clearly-not-sea pixels
    ref, _ = convert.resample(c)
    lum = ref @ np.array([0.3, 0.59, 0.11])
    sea = np.median(lum[m.mask == 0])
    land = lum < sea - 14
    h, w = land.shape
    sx, sy = (c["crop"][2] - c["crop"][0]) / w, (c["crop"][3] - c["crop"][1]) / h
    for (x0, y0, x1, y1) in c["regions"].get("sea_boxes", []):      # (the compass is not land)
        land[int(y0 / sy):int(y1 / sy) + 1, int(x0 / sx):int(x1 / sx) + 1] = False
    cover = float((m.mask[land] != 0).mean())
    if cover < 0.97:
        problems.append(f"the regions cover only {cover:.1%} of the picture's land (need 97%)")
    # slots lie inside their region
    for r, x, y in m.slots:
        if m.mask[y, x] != r:
            problems.append(f"flag place {(x, y)} is not inside {m.region_names[r]}")
    # the re-conversion is the file that is checked in (stable)
    again = binfmt.pack(convert.convert(config_path(name)))
    if again != bin_path(name).read_bytes():
        problems.append(f"{bin_path(name).relative_to(REPO)} is not what `aw2dev worldmap convert {name}` makes now: convert again and commit")
    return problems


# --------------------------------------------------------------- pictures

def _tag(img, text):
    d = ImageDraw.Draw(img)
    d.rectangle((0, 0, 8 * len(text) + 6, 12), fill=(255, 255, 255))
    d.text((3, 1), text, fill=(0, 0, 0))
    return img


def preview(name, conquered_sets=None, scale=2, out=None):
    """A sheet of the map as the game draws it: the picture resampled, the conversion, each state of conquest, the 240x160 camera views."""
    m, c = load(name)
    ref, _ = convert.resample(c)
    ref = ref.astype(np.uint8)
    states = conquered_sets if conquered_sets is not None else [(), (1,), (1, 2), (1, 2, 3, 4, 5)]
    panels = [("source resampled", ref)]
    for s in states:
        label = "converted" if not s else "conquered " + ",".join(m.region_names[i].split()[0] for i in s)
        panels.append((label, convert.render(m, s)))
    tiles = []
    for label, arr in panels:
        im = Image.fromarray(arr).resize((m.width * scale, m.height * scale), Image.NEAREST)
        tiles.append(_tag(im, label))
    # the camera: what the 240 x 160 screen shows at the corners of the scroll range
    views = []
    base = convert.render(m)
    for cx, cy in ((0, 0), (max(0, m.width - 240), 0), (0, m.height - 160), (max(0, m.width - 240), m.height - 160)):
        v = Image.fromarray(base[cy:cy + 160, cx:cx + min(240, m.width)])
        views.append(_tag(v.resize((v.width * scale, v.height * scale), Image.NEAREST), f"camera {cx},{cy}"))
    colour = Image.new("RGB", (max(m.width * scale * len(tiles), 5 * (240 * scale + 8)), m.height * scale + 160 * scale + 4), (255, 255, 255))
    for i, t in enumerate(tiles):
        colour.paste(t, (i * m.width * scale, 0))
    for i, v in enumerate(views):
        colour.paste(v, (i * 240 * scale + (i * 8), m.height * scale + 4))
    # the nations' mask
    pal = np.array([[255, 255, 255], [240, 150, 80], [80, 120, 220], [100, 200, 80], [240, 220, 60], [130, 130, 130]], np.uint8)
    mk = Image.fromarray(pal[m.mask]).resize((m.width * scale, m.height * scale), Image.NEAREST)
    colour.paste(_tag(mk, "regions (mask)"), (len(views) * (240 * scale + 8), m.height * scale + 4))
    out = Path(out) if out else dcfg.work("worldmap") / f"{name}_preview.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    colour.save(out)
    return out, m


def stats(m):
    lines = []
    for label, used, limit in budgets(m):
        lines.append(f"  {label}: {used} / {limit}")
    for r in range(1, len(m.region_names)):
        lines.append(f"  region {r} {m.region_names[r]}: {int((m.mask == r).sum())} px, {int((m.tags == r).sum())} palette entries, "
                     f"{sum(1 for s in m.slots if s[0] == r)} flag places")
    return lines
