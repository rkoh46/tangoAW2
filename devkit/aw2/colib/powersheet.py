"""The contact sheets of `aw2dev co sheet powers`: `<co>_powers.png` (every picture of one CO's powers, captioned) and `all_cos_overview.png` (one row a CO).

The pictures are real frames of the game taken by `tools/aw2test/aw2test/copics.py` (the harness console with the Dual Strike pack and map graphics): `<raw>/<co>/<key>.png` and
`captions.json`. This module only lays them out.
"""
import json
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SECTIONS = [
    ("CO select card and CO page", ["select", "page1", "page3"]),
    ("HUD: the power bar charging and full", ["hud_charging", "hud_cop_ready", "hud_full"]),
    ("CO Power", ["cop_before", "cop_quote", "cop_cutin_begins", "cop_cutin", "cop_cutin_ends", "cop_effect", "cop_after", "cop_after_units"]),
    ("Super Power", ["scop_before", "scop_quote", "scop_cutin_begins", "scop_cutin", "scop_cutin_ends", "scop_effect", "scop_after", "scop_after_units"]),
]
BG, INK, DIM, HEAD = (24, 28, 36), (235, 238, 245), (150, 158, 175), (255, 214, 90)


def font(size, bold=False):
    for path in ("/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(path, size, index=1 if bold and path.endswith(".ttc") else 0)
        except Exception:
            continue
    return ImageFont.load_default()


def tiles_of(co_dir, caps):
    """[(section title, [(key, path, caption)])] in sheet order, only what exists."""
    have = {p.stem: p for p in Path(co_dir).glob("*.png")}
    out = []
    used = set()
    for title, keys in SECTIONS:
        rows = [(k, have[k], caps.get(k, k)) for k in keys if k in have]
        used |= {k for k, _, _ in rows}
        if rows:
            out.append((title, rows))
    effects = sorted(k for k in have if k.startswith("effect_"))
    if effects:
        order = sorted(effects, key=lambda k: (k.replace("_before", ""), 0 if "before" in k else 1))
        out.append(("In battle: what the power does", [(k, have[k], caps.get(k, k)) for k in order]))
        used |= set(effects)
    tags = sorted({k.split("_")[1] for k in have if k.startswith("tag_")})
    for t in tags:
        keys = [f"tag_{t}_{k}" for k in ("menu", "quote", "tag_screen", "first_half_cutin", "first_half_after", "second_half_cutin", "second_half_after") if f"tag_{t}_{k}" in have]
        if keys:
            out.append((f"Tag Power with {t.capitalize()}", [(k, have[k], caps.get(k, k)) for k in keys]))
            used |= set(keys)
    return out


def sheet(co, co_dir, out_path, scale=2, cols=3):
    caps = json.loads((Path(co_dir) / "captions.json").read_text()) if (Path(co_dir) / "captions.json").exists() else {}
    secs = tiles_of(co_dir, caps)
    tw, th = 240 * scale, 160 * scale
    pad, capline = 14, 5
    f_cap, f_head, f_title = font(15), font(20, True), font(30, True)
    wrap = (tw // 8)
    # lay out: sections heading, rows of `cols` tiles each with a caption of up to 5 lines
    W = cols * (tw + pad) + pad
    y = pad + 48
    placed = []
    for title, tiles in secs:
        placed.append(("head", title, y))
        y += 36
        for r in range(0, len(tiles), cols):
            row = tiles[r:r + cols]
            lines = max(len(textwrap.wrap(c, wrap)) for _, _, c in row)
            lines = min(lines, 7)
            for k, (key, path, cap) in enumerate(row):
                placed.append(("tile", (key, path, cap), (pad + k * (tw + pad), y)))
            y += th + 8 + lines * 19 + pad
    H = y + pad
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((pad, 10), f"{co.upper()}: powers in the real game", font=f_title, fill=HEAD)
    for kind, a, b in placed:
        if kind == "head":
            d.rectangle([pad, b + 2, W - pad, b + 3], fill=(60, 68, 90))
            d.text((pad, b + 8), a, font=f_head, fill=INK)
        else:
            key, path, cap = a
            x, yy = b
            t = Image.open(path).convert("RGB").resize((tw, th), Image.NEAREST)
            im.paste(t, (x, yy))
            d.rectangle([x - 1, yy - 1, x + tw, yy + th], outline=(70, 78, 100))
            for n, line in enumerate(textwrap.wrap(cap, wrap)[:7]):
                d.text((x, yy + th + 6 + 19 * n), line, font=f_cap, fill=INK if n == 0 else DIM)
    im.save(out_path)
    return out_path


def overview(raw, out_path, cos, scale=1.5):
    """One row a CO: select card, HUD full, CO Power cut-in, Super Power cut-in, first Tag screen, a battle effect."""
    cols = [("select", "CO select"), ("hud_full", "HUD, bar full"), ("cop_cutin", "CO Power"), ("scop_cutin", "Super Power"), ("TAG", "Tag Power screen"), ("EFFECT", "In battle")]
    tw, th = int(240 * scale), int(160 * scale)
    pad = 10
    label_w = 150
    W = label_w + len(cols) * (tw + pad) + pad
    H = 60 + len(cos) * (th + pad + 4)
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    d.text((pad, 10), "Custom COs: overview in the real game", font=font(26, True), fill=HEAD)
    for c, (_, title) in enumerate(cols):
        d.text((label_w + c * (tw + pad), 42), title, font=font(14, True), fill=INK)
    y = 62
    for co in cos:
        co_dir = Path(raw) / co
        have = {p.stem: p for p in co_dir.glob("*.png")}
        d.text((pad, y + th // 2 - 10), co.capitalize() if co != "cloneandy" else "Clone Andy", font=font(20, True), fill=INK)
        for c, (key, _) in enumerate(cols):
            if key == "TAG":
                ks = sorted(k for k in have if k.endswith("_tag_screen"))
                key = ks[0] if ks else None
            elif key == "EFFECT":
                ks = sorted(k for k in have if k.startswith("effect_") and "before" not in k and "plain" not in k)
                key = ks[0] if ks else None
            if key and key in have:
                im.paste(Image.open(have[key]).convert("RGB").resize((tw, th), Image.NEAREST), (label_w + c * (tw + pad), y))
            else:
                d.rectangle([label_w + c * (tw + pad), y, label_w + c * (tw + pad) + tw, y + th], outline=(70, 78, 100))
                d.text((label_w + c * (tw + pad) + 10, y + th // 2), "(none)", font=font(14), fill=DIM)
        y += th + pad + 4
    im.save(out_path)
    return out_path


def hq_sheet(raw, out_path, cols=3):
    """`hq_check.png`: the HQ of the Roman COs on the map: in Versus (beside Andy's, the game's own), on the Dual Strike tilted map (the real app) and in the Emerald Sun missions."""
    raw = Path(raw)
    caps = json.loads((raw / "hq_captions.json").read_text())
    versus = [(k, raw / f"{k}.png", caps[k]) for k in caps if k.startswith("versus_")]
    tilt = [(p.stem, p, f"Tilted map (the app): {p.stem.split('_')[0].capitalize()}'s HQ" + (" (the game's own)" if p.stem.startswith('andy') else "")) for p in sorted(raw.glob("*_hq_tilt.png"))]
    missions = [(k, raw / f"{k}.png", caps[k]) for k in caps if k.startswith("m")]
    secs = [("Versus: each CO's own army (Andy's is the game's plain HQ). The Emerald Sun HQ is the domed tower with gold windows and a finial, drawn in the army's own building colours", versus),
            ("Dual Strike tilted map, the real app", tilt), ("Emerald Sun Campaign missions: the player's HQ and the HQ of every army led by a Roman CO", missions)]
    tw, th, pad = 480, 320, 14
    W = cols * (tw + pad) + pad
    y = pad + 48
    placed = []
    for title, tiles in secs:
        if not tiles:
            continue
        placed.append(("head", title, y))
        y += 36
        for r in range(0, len(tiles), cols):
            for k, t in enumerate(tiles[r:r + cols]):
                placed.append(("tile", t, (pad + k * (tw + pad), y)))
            y += th + 40
    im = Image.new("RGB", (W, y + pad), BG)
    d = ImageDraw.Draw(im)
    d.text((pad, 10), "HQ of the Roman COs on the map", font=font(30, True), fill=HEAD)
    for kind, a, b in placed:
        if kind == "head":
            d.rectangle([pad, b + 2, W - pad, b + 3], fill=(60, 68, 90))
            d.text((pad, b + 8), a, font=font(17, True), fill=INK)
        else:
            _, path, cap = a
            x, yy = b
            im.paste(Image.open(path).convert("RGB").resize((tw, th), Image.NEAREST), (x, yy))
            d.rectangle([x - 1, yy - 1, x + tw, yy + th], outline=(70, 78, 100))
            d.text((x, yy + th + 6), cap, font=font(15), fill=INK)
    im.save(out_path)
    return out_path
