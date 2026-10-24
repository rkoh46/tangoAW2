"""Sheets and checks of `aw2dev co portrait ...` (docs/dev/co-kit.md)."""
import tomllib
from pathlib import Path
from PIL import Image, ImageDraw
from .. import cfg, util
from . import compose as cp, render as rd, roms

SPDIR = None


def donors(a):
    ids = list(range(19)) if a.source == "aw2" else [i for i in range(1, 28) if i != 1]
    cols = 5
    cell_w, cell_h = 128 + 8, 160 + 70
    rows = (len(ids) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cell_w + 8, rows * cell_h + 8), rd.BG)
    for n, i in enumerate(ids):
        p = roms.aw2_portrait(i) if a.source == "aw2" else roms.ds_portrait(i)
        x, y = 8 + (n % cols) * cell_w, 8 + (n // cols) * cell_h
        sheet.paste(rd.donor_image(p.body, p.palettes[0]), (x, y), rd.donor_image(p.body, p.palettes[0]))
        f = rd.donor_image(p.faces[0], p.palettes[0])
        f = f.resize((48, 48))
        sheet.paste(f, (x, y + 162), f)
        for k, c in enumerate(p.palettes[0][:16]):
            sw = Image.new("RGB", (8, 8), roms.bgr(c))
            sheet.paste(sw, (x + 52 + (k % 8) * 9, y + 164 + (k // 8) * 9))
        rd.text(sheet, (x, y + 212 - 14), f"{a.source}:{i} {p.name}", size=12)
    out = Path(a.out or cfg.work("co", f"donors_{a.source}.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    util.say("wrote", out)
    return 0


def load_co(co):
    p = cp.COS_DIR / f"{co}.toml"
    if not p.exists():
        util.die(f"no CO data file {p}")
    return tomllib.loads(p.read_text())


def options_of(d):
    return {o["letter"]: o for o in d.get("portrait", {}).get("option", [])}


def render_option(opt, scale=2):
    """-> (pics, fit info, images dict)"""
    pics, donor = cp.compose(opt)
    mapping, pal, merged = cp.fit_palette(pics)
    cp.apply_fit(pics, mapping)
    return pics, donor, pal, merged


def option_cell(opt, d, scale=2):
    pics, donor, pal, merged = render_option(opt)
    big = rd.to_image(pics["body"].px, scale)
    faces = [rd.to_image(f.px, scale) for f in pics["face"]]
    mini = rd.to_image(pics["mini"].px, scale)
    hud = rd.to_image(pics["hud"].px, scale)
    return pics, big, faces, mini, hud, pal, merged


def compose_one(a):
    d = load_co(a.co)
    opt = options_of(d)[a.option]
    pics, big, faces, mini, hud, pal, merged = option_cell(opt, d, a.scale)
    W = big.width + 48 * a.scale * 3 + 20
    sheet = Image.new("RGB", (W + 40, big.height + 40), rd.BG)
    sheet.paste(big, (10, 10), big)
    x = big.width + 20
    for f in faces:
        sheet.paste(f, (x, 10), f)
        x += f.width
    sheet.paste(mini, (big.width + 20, 20 + faces[0].height), mini)
    sheet.paste(hud, (big.width + 20 + mini.width + 10, 20 + faces[0].height), hud)
    out = Path(a.out or cfg.work("co", f"{a.co}_{a.option}.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    util.say(f"wrote {out} ({len(pal)} colours, {merged} merged)")
    return 0


def options(a):
    d = load_co(a.co)
    opts = options_of(d)
    letters = list(a.letters) if a.letters else sorted(opts)
    cw, ch = 440, 470
    cols = 3
    rows = (len(letters) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw + 10, rows * ch + 60), rd.BG)
    name = d.get("name", a.co)
    rd.text(sheet, (14, 10), f"{name}: {d.get('role', '')}", size=24)
    rd.text(sheet, (14, 38), "large portrait (CO page, power and tag screens) 2x   |   faces (CO select) 3x   |   small face (Teams) and HUD face 3x   |   Emerald Sun palette", fill=(170, 176, 190), size=12)
    for n, L in enumerate(letters):
        opt = opts[L]
        pics, big, faces, mini, hud, pal, merged = option_cell(opt, d, 2)
        x0, y0 = 10 + (n % cols) * cw, 60 + (n // cols) * ch
        ImageDraw.Draw(sheet).rounded_rectangle((x0, y0, x0 + cw - 8, y0 + ch - 8), 8, fill=rd.PANEL)
        rd.text(sheet, (x0 + 10, y0 + 6), f"{name} {L}", size=22)
        sheet.paste(big, (x0 + 10, y0 + 34), big)
        f = rd.to_image(pics["face"][0].px, 3)
        sheet.paste(f, (x0 + 10 + 128 * 2 + 14, y0 + 34), f)
        m = rd.to_image(pics["mini"].px, 3)
        sheet.paste(m, (x0 + 10 + 128 * 2 + 14, y0 + 34 + 150), m)
        h = rd.to_image(pics["hud"].px, 3)
        sheet.paste(h, (x0 + 10 + 128 * 2 + 14, y0 + 34 + 150 + 80), h)
        f2 = rd.to_image(pics["face"][1].px, 1)
        sheet.paste(f2, (x0 + 10 + 128 * 2 + 14 + 100, y0 + 34 + 150 + 5), f2)
        for k, line in enumerate(rd.wrap(opt.get("description", ""), 52)[:4]):
            rd.text(sheet, (x0 + 10, y0 + 34 + 330 + 18 * k), line, fill=(225, 228, 235), size=13)
        rd.text(sheet, (x0 + 10, y0 + ch - 30), f"base: {opt['donor']}  |  {len(pal)} colours", fill=(150, 156, 170), size=11)
    out = Path(a.out or cfg.work("co", f"co_{a.co}.png"))
    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out)
    util.say("wrote", out)
    return 0


def pcheck(a):
    """Every option of every CO composes and fits 15 colours; motifs exist."""
    names = a.co or [p.stem for p in sorted(cp.COS_DIR.glob("*.toml"))]
    bad = 0
    for co in names:
        d = load_co(co)
        for L, opt in sorted(options_of(d).items()):
            try:
                pics, donor, pal, merged = render_option(opt)
                ok = len(pal) <= 15
                print(f"{'PASS' if ok else 'FAIL'} {co} {L}: {len(pal)} colours ({merged} merged), donor {opt['donor']}")
                bad += not ok
            except Exception as e:
                print(f"FAIL {co} {L}: {e}")
                bad += 1
    return 1 if bad else 0
