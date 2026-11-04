"""`aw2dev co consistency CO`: one sheet of a CO on every screen the kit can photograph, and the cheap static checks that a portrait agrees with itself (docs/dev/co-kit.md "Consistency").

Static (no ROM, no game): the committed art of art/cos/<co>/ (large figure, four faces, mini, HUD) sits on one palette; no two pictures lean clearly opposite ways (the mass against the middle of the box: a CO the importer
mirrored for one picture and not another does); Pictures (when they exist): the files of
`aw2dev co portrait ingame CO` (CO select, HUD, CO page, power box), `aw2dev gauntlet faces --map NN` (the dialogue-box face next to the army screen)."""
from pathlib import Path
from PIL import Image, ImageDraw
from .. import cfg

ART = cfg.REPO / "tango-gamesupport-aw2" / "art" / "cos"
PARTS = ["large", "face_normal", "face_happy", "face_sad", "face_angry", "mini", "hud"]


def lean(im):
    """(mass centroid x - box middle) / width of the opaque pixels: positive when the mass sits right of the middle."""
    im = im.convert("RGBA")
    px = im.load()
    xs = [x for y in range(im.height) for x in range(im.width) if px[x, y][3] > 0 and sum(px[x, y][:3]) > 120]
    if not xs:
        return 0.0
    return (sum(xs) / len(xs) - im.width / 2) / im.width


def static(co):
    """[(name, ok, detail)] for the committed art."""
    d = ART / co
    out = []
    ims = {p: Image.open(d / f"{p}.png") for p in PARTS if (d / f"{p}.png").exists()}
    out.append(("art present", len(ims) == len(PARTS), f"{len(ims)} of {len(PARTS)} pictures in art/cos/{co}"))
    if len(ims) != len(PARTS):
        return out
    leans = {p: lean(ims[p]) for p in ("large", "face_normal", "face_happy", "face_sad", "face_angry")}
    # (a heuristic: a figure's mass sits left of its box middle by its pose, so only a clear opposite lean of two pictures counts)
    clear = {s for p, v in leans.items() for s in [1 if v > 0.04 else -1 if v < -0.04 else 0] if s}
    out.append(("lean", len(clear) <= 1, "lean by picture (mass vs box middle; look at the sheet): " + ", ".join(f"{p} {v:+.3f}" for p, v in leans.items())))
    return out


def sheet(co, out_path, extra):
    d = ART / co
    tiles = [(p, Image.open(d / f"{p}.png").convert("RGBA")) for p in PARTS if (d / f"{p}.png").exists()]
    for f in extra:
        tiles.append((f.name, Image.open(f).convert("RGBA")))
    k = 3
    cw = max(im.width * (k if im.width <= 64 else 1) for _, im in tiles) + 8
    cols = 4
    rows = (len(tiles) + cols - 1) // cols
    ch = max(im.height * (k if im.width <= 64 else 1) for _, im in tiles) + 16
    sh = Image.new("RGB", (cols * cw, rows * ch), (24, 24, 32))
    dr = ImageDraw.Draw(sh)
    for i, (name, im) in enumerate(tiles):
        x, y = (i % cols) * cw, (i // cols) * ch
        z = k if im.width <= 64 else 1
        bg = Image.new("RGBA", im.size, (60, 60, 80, 255))
        bg.alpha_composite(im)
        sh.paste(bg.convert("RGB").resize((im.width * z, im.height * z), Image.NEAREST), (x + 4, y + 14))
        dr.text((x + 4, y + 2), f"{co}: {name}", fill=(255, 220, 120))
    sh.save(out_path)
    return out_path


def run(co, out=None):
    """(ok, lines, sheet path)."""
    res = static(co)
    lines = [f"{'ok' if ok else 'FAIL'}: {n}: {d}" for n, ok, d in res]
    extra = sorted((cfg.work("co", "ingame", co)).glob("*.png")) if (cfg.work("co", "ingame", co)).exists() else []
    extra += sorted((cfg.work("gauntlet", "faces")).glob(f"screen_*.png"))[:0]
    path = Path(out or cfg.work("co", f"consistency_{co}.png"))
    path.parent.mkdir(parents=True, exist_ok=True)
    if (ART / co).exists():
        sheet(co, path, extra)
    lines.append(f"sheet: {path} ({len(extra)} game pictures from `aw2dev co portrait ingame {co}`)")
    return all(ok for _, ok, _ in res), lines, path
