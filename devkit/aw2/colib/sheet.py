"""The review sheet of the imported portraits (docs/dev/co-kit.md): per CO the source picture, the large art at 1x and 2x beside AW2's own large art, the four expression faces, the Teams mini
and the HUD face, the CO select strip and the HUD strip with the real COs around them, and (when `aw2dev co portrait ingame` has run) the game's own screens."""
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from .. import cfg
from . import importer as I, render as rd, roms

REAL_FIG = ["aw2:hawke", "aw2:kanbei", "aw2:sonja"]
REAL_FACES = ["aw2:andy", "aw2:max", "aw2:sami", "aw2:hawke", "aw2:kanbei", "aw2:sonja", "aw2:eagle", "aw2:nell"]
INGAME = lambda co: cfg.work("co", "ingame", co)


def _real(name):
    n = name.split(":")[1]
    return roms.aw2_portrait([x.lower() for x in roms.AW2_NAMES].index(n))


def _px(grid, pal):
    return [[roms.bgr(pal[v]) if v else None for v in r] for r in grid]


def _arr(a, pal, scale=1, bg=None):
    return I.to_image(a, pal, scale, bg)


def sheet(cos, specs, title=None):
    """cos: [CO ids]; specs: {co: data file dict}. -> PIL image."""
    cw, ch = 2350, 830
    img = Image.new("RGB", (cw, ch * len(cos) + 50), rd.BG)
    rd.text(img, (14, 10), title or "Imported portraits: the project owner's pixel art as AW2 CO art (native grid, 2x, one palette of 15 colours + transparent, outline, 128 x 160 figure, 48 x 48 mugs, 32 x 24 mini, 32 x 16 HUD face)", size=17)
    reals = [_real(n) for n in REAL_FIG]
    for r, co in enumerate(cos):
        pics, pal = I.read_art(co)
        pal = [tuple(p) for p in pal]
        y0 = 50 + r * ch
        ImageDraw.Draw(img).rounded_rectangle((6, y0, cw - 6, y0 + ch - 8), 8, fill=rd.PANEL)
        rd.text(img, (16, y0 + 8), co.title(), size=22)
        src = Image.open(cfg.REPO / specs[co]["portrait"]["source"]).convert("RGB")
        s = src.resize((src.width * 560 // src.height, 560), Image.LANCZOS)
        img.paste(s, (16, y0 + 40))
        rd.text(img, (16, y0 + 604), "source: the design reference (as supplied)", size=12)
        x = 16 + s.width + 20
        # the large art next to AW2's own: 1x row, then 2x
        rd.text(img, (x, y0 + 8), "1x: Hawke, Kanbei, Sonja (AW2), ours", size=13)
        row = Image.new("RGB", (136 * 4, 164), (36, 40, 52))
        for i, d in enumerate(reals):
            im = rd.to_image(_px(d.body, d.palettes[0]), 1)
            row.paste(im, (i * 136 + 4, 2), im)
        big = _arr(pics["large"], pal, 1)
        row.paste(big, (3 * 136 + 4, 2), big)
        img.paste(row, (x, y0 + 28))
        rd.text(img, (x, y0 + 200), "large art, 2x: Hawke (AW2) and ours", size=13)
        row2 = Image.new("RGB", (268 * 2, 324), (36, 40, 52))
        im = rd.to_image(_px(reals[0].body, reals[0].palettes[0]), 2)
        row2.paste(im, (4, 2), im)
        big2 = _arr(pics["large"], pal, 2)
        row2.paste(big2, (272, 2), big2)
        img.paste(row2, (x, y0 + 220))
        # faces, small faces, strips
        fx = x + 560
        rd.text(img, (fx, y0 + 8), "expression faces 2x: normal, happy, sad, angry", size=13)
        for i, n in enumerate(("face_normal", "face_happy", "face_sad", "face_angry")):
            f = _arr(pics[n], pal, 2, (36, 40, 52))
            img.paste(f, (fx + i * 100, y0 + 28))
        rd.text(img, (fx, y0 + 130), "Teams mini and HUD face 2x", size=13)
        img.paste(_arr(pics["mini"], pal, 2, (36, 40, 52)), (fx, y0 + 150))
        img.paste(_arr(pics["hud"], pal, 2, (36, 40, 52)), (fx + 80, y0 + 150))
        sy = y0 + 215
        rd.text(img, (fx, sy - 18), "CO select faces and HUD faces next to AW2's own (1x)", size=13)
        order = REAL_FACES[:4] + ["me"] + REAL_FACES[4:]
        strip = Image.new("RGB", (len(order) * 52, 52), (36, 40, 52))
        hs = Image.new("RGB", (len(order) * 36, 20), (36, 40, 52))
        for i, n in enumerate(order):
            if n == "me":
                f, h = _arr(pics["face_normal"], pal, 1), _arr(pics["hud"], pal, 1)
            else:
                d = _real(n)
                f, h = rd.to_image(_px(d.faces[0], d.palettes[0]), 1), rd.to_image(_px(d.hud, d.palettes[0]), 1)
            strip.paste(f, (i * 52 + 2, 2), f)
            hs.paste(h, (i * 36 + 2, 2), h)
        img.paste(strip, (fx, sy))
        img.paste(hs, (fx, sy + 58))
        # the game's own screens
        gy = sy + 90
        rd.text(img, (fx, gy), "in the game: CO page, CO select, HUD, dialogue", size=13)
        shots = [INGAME(co) / f"{co}_{n}.png" for n in ("select", "figure", "page", "hud", "dialogue")]
        shots = [p for p in shots if p.exists()]
        if not shots:
            rd.text(img, (fx, gy + 20), "(the CO is not in the game yet: no screens)", fill=(190, 150, 150), size=12)
        for i, p in enumerate(shots[:5]):
            g = Image.open(p).convert("RGB")
            g = g.resize((g.width * 3 // 2, g.height * 3 // 2), Image.NEAREST)
            img.paste(g, (fx + (i % 3) * 372, gy + 20 + (i // 3) * 250))
    return img
