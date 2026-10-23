"""Soldier options (docs/dev/army-packs.md): several complete Infantry + Mech designs for a skin, drawn from candidate files and shown on one sheet to choose from.

A candidate file (`A.toml`, `B.toml` ...) is a small skin fragment: `name`, `description`, optionally `[colours]` (a `trim`, `crest`, `ramp` of its own) and the skin file's own
`[infantry]` / `[mech]` tables with their `[[..patch]]` entries, so the chosen one is merged into `skins/<id>.toml` as it is. `grid_of` / `patch_rows` help to author one: draw on a copy
of AW2's soldier and let the difference become the patch (`.` keep, `_` clear, a hex digit a unit palette index)."""
import tomllib
from pathlib import Path
from PIL import Image, ImageDraw
from . import Rom, UNIT_PAL, UNIT_SHEET, FRAME, SLOT_TABLE, tile_px, toml_art, SKIN_DIR, NAMES
from .sheet import label, BG, foot


def hexrgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def grid_of(rom, colour, unit, frame=0):
    """AW2's picture of a foot unit (1 Infantry, 2 Mech) as a 16 x 16 grid of palette indices."""
    slot = rom.u16(SLOT_TABLE + 2 * (25 * (colour - 1) + unit))
    raw = rom.raw(UNIT_SHEET + FRAME * frame + 128 * slot, 128)
    g = [[0] * 16 for _ in range(16)]
    for k in range(4):
        px = tile_px(raw, 32 * k)
        for y in range(8):
            for x in range(8):
                g[(k // 2) * 8 + y][(k % 2) * 8 + x] = px[y][x]
    return g


def patch_rows(base, new, bounds=None):
    """The patch that turns grid `base` into `new`: (x, y, rows) over the bounding box of the difference (or `bounds` = (x0, y0, x1, y1))."""
    diff = [(x, y) for y in range(16) for x in range(16) if base[y][x] != new[y][x]]
    if not diff:
        return 0, 0, ["."]
    x0, y0, x1, y1 = bounds or (min(x for x, _ in diff), min(y for _, y in diff), max(x for x, _ in diff), max(y for _, y in diff))
    rows = []
    for y in range(y0, y1 + 1):
        r = ""
        for x in range(x0, x1 + 1):
            r += "." if base[y][x] == new[y][x] else ("_" if new[y][x] == 0 else "%x" % new[y][x])
        rows.append(r)
    return x0, y0, rows


def toml_for(letter, description, colours, inf_patch, mech_patches):
    """A candidate file's text. `colours`: dict of optional overrides (trim, crest, ramp as lists/strings of RRGGBB)."""
    def arr(rows):
        return "rows = [\n" + "".join(f'  "{r}",\n' for r in rows) + "]\n"
    out = f'name = "{letter}"\ndescription = "{description}"\n\n'
    if colours:
        out += "[colours]\n" + "".join(f"{k} = {v!r}\n".replace("'", '"') for k, v in colours.items()) + "\n"
    out += "[infantry]\nbase = 3\n\n"
    x, y, rows = inf_patch
    out += f"[[infantry.patch]]\nx = {x}\ny = {y}\n" + arr(rows) + "\n[mech]\nbase = 3\n\n"
    for frames, (x, y, rows) in mech_patches:
        out += f"[[mech.patch]]\nframes = {frames}\nx = {x}\ny = {y}\n" + arr(rows) + "\n"
    return out


def load(path):
    return tomllib.loads(Path(path).read_text())


def unit_palette(rom, skin, cand):
    """The skin's unit palette (as `Skin::unit_row` builds it) with the candidate's colour overrides."""
    c = dict(skin["colours"])
    c.update(cand.get("colours", {}))
    p = list(rom.pal(UNIT_PAL + 64))
    for i, h in enumerate(c["ramp"]):
        p[2 + i] = hexrgb(h)
    for i, h in enumerate(c["trim"]):
        p[11 + i] = hexrgb(h)
    p[14] = hexrgb(c["crest"])
    return p


def render_unit(rom, skin, cand, unit, scale=1):
    g = grid_of(rom, 3, unit, 0)
    for pt in cand.get(("infantry", "mech")[unit - 1], {}).get("patch", []):
        if 0 not in pt.get("frames", [0, 1, 2]):
            continue
        for dy, row in enumerate(pt["rows"]):
            for dx, ch in enumerate(row):
                x, y = pt.get("x", 0) + dx, pt.get("y", 0) + dy
                if ch == "." or x >= 16 or y >= 16:
                    continue
                g[y][x] = 0 if ch == "_" else int(ch, 16)
    pal = unit_palette(rom, skin, cand)
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y in range(16):
        for x in range(16):
            if g[y][x]:
                im.putpixel((x, y), pal[g[y][x]] + (255,))
    return im.resize((16 * scale, 16 * scale), Image.NEAREST) if scale != 1 else im


def plain_tile(shot):
    """A 16 x 16 piece of plain ground from a harness frame (the most uniform block of grass)."""
    im = Image.open(shot).convert("RGB")
    best = None
    for ty in range(0, im.height - 15, 8):
        for tx in range(0, im.width - 15, 8):
            blk = im.crop((tx, ty, tx + 16, ty + 16))
            px = list(blk.getdata())
            r = sum(p[0] for p in px) / 256
            g = sum(p[1] for p in px) / 256
            b = sum(p[2] for p in px) / 256
            if not (g > 150 and r > 120 and b < 120):
                continue
            var = sum(abs(p[0] - r) + abs(p[1] - g) + abs(p[2] - b) for p in px)
            if best is None or var < best[0]:
                best = (var, blk)
    return best[1] if best else Image.new("RGB", (16, 16), (200, 224, 64))


def sheet(cand_dir, letters=None, tile=None, awbw_dir=None, skin_path=None):
    """One row per candidate: the letter, its description, the Infantry and Mech at 8x and 1x, and on a map tile at 2x beside a Green Earth and a Black Hole Infantry."""
    skin = toml_art(skin_path)
    base = Rom()
    files = sorted(Path(cand_dir).glob("*.toml"))
    if letters:
        files = [f for f in files if f.stem.upper() in {l.upper() for l in letters}]
    cands = [(f.stem.upper(), load(f)) for f in files]
    W, ROW = 1500, 16 * 8 + 24
    tile = tile or Image.new("RGB", (16, 16), (200, 224, 64))
    H = 70 + (len(cands) + (1 if awbw_dir else 0)) * ROW + 20
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    label(im, "Soldier options for the skin: each a complete Infantry + Mech (idle side frame), the skin's palette; 8x, then 1x, then on a plain tile at 2x beside Green Earth's and Black Hole's Infantry", (8, 6), size=16)
    y = 36
    gpal, bpal = base.pal(UNIT_PAL + 64), base.pal(UNIT_PAL + 128)

    def pair_block(x, y, inf, mech, gi=None, bi=None):
        i8, m8 = inf.resize((128, 128), Image.NEAREST), mech.resize((128, 128), Image.NEAREST)
        im.paste(i8, (x, y), i8)
        im.paste(m8, (x + 136, y), m8)
        im.paste(inf, (x + 280, y + 8), inf)
        im.paste(mech, (x + 300, y + 8), mech)
        # on a map tile at 2x, with Green Earth's and Black Hole's Infantry beside it
        px = x + 340
        for k, pic in enumerate((inf, mech, gi, bi)):
            if pic is None:
                continue
            t = tile.resize((32, 32), Image.NEAREST)
            im.paste(t, (px + 36 * k, y + 8))
            p2 = pic.resize((32, 32), Image.NEAREST)
            im.paste(p2, (px + 36 * k, y + 8), p2)
        return x + 340 + 36 * 4

    if awbw_dir:
        a = Image.open(Path(awbw_dir) / "jsinfantry.gif").convert("RGBA")
        b = Image.open(Path(awbw_dir) / "jsmech.gif").convert("RGBA")
        label(im, "AWBW's\n(reference,\nnot ours)", (8, y + 30), size=14)
        pair_block(120, y, a.transpose(Image.FLIP_LEFT_RIGHT), b.transpose(Image.FLIP_LEFT_RIGHT), foot(base, 3, 1, 0, gpal, 1), foot(base, 5, 1, 0, bpal, 1))
        y += ROW
    for letter, cand in cands:
        d.rectangle([4, y - 2, W - 4, y + ROW - 8], outline=(70, 74, 88))
        label(im, letter, (14, y + 8), size=64)
        label(im, cand.get("description", ""), (120, y + 134), size=13)
        inf, mech = render_unit(base, skin, cand, 1), render_unit(base, skin, cand, 2)
        pair_block(120, y, inf, mech, foot(base, 3, 1, 0, gpal, 1), foot(base, 5, 1, 0, bpal, 1))
        y += ROW
    return im.crop((0, 0, W, y + 10))
