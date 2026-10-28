"""Review pictures of the BH2 maps (our own colours and shapes: nothing from the games is in them): the full map with every unit and label, the fog view of the
player's side, a contact sheet, and the world map with the mission flags. Every picture carries "MISSION N - Title" burned in (the owner's rule)."""
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..maplint.render import COL, UNIT_INITIAL, font
from ..maplint.terrain import terrain, PROP_KIND
from . import COLOUR, COLOUR_NAME, FRONT2, MISSIONS, flags, maps

ACTS = {1: (1, 5, "Landfall"), 2: (6, 10, "Comet Chain")}           # act -> (first mission, last mission, title)
FRONT2_LABEL = {4: "front 2 (sky)", 10: "front 2 (Grimm's isles)"}

CELL = 22
DASH = "—"
VISION = {1: 2, 2: 2, 3: 3, 4: 3, 5: 3, 6: 5, 7: 2, 8: 3, 9: 3, 10: 3, 11: 3, 12: 4, 13: 4, 14: 3, 15: 4, 16: 5, 17: 4, 18: 3, 19: 3, 20: 3, 21: 3, 22: 5, 23: 2, 24: 5, 26: 4}
PROP_HINT = {"H": "HQ", "B": "base", "C": "city", "A": "airport", "P": "port", "T": "Com Tower"}


def _title_font(size):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/System/Library/Fonts/Helvetica.ttc", "/Library/Fonts/Arial.ttf"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            pass
    return font(size)


def notes_of(name):
    """The map file's `# key: (x, y) text` comments."""
    from ..esmaplib import BH2_DIR
    out = []
    p = BH2_DIR / f"{name}.txt"
    if p.exists():
        for ln in p.read_text().splitlines():
            m = re.match(r"# (\w+): \((\d+), (\d+)\)\s*(.*)", ln)
            if m:
                out.append((m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)))
    return out


def colour_of(m, army):
    cols = list(m.meta.get("colours") or [])
    return COLOUR.get(cols[army - 1], (200, 200, 200)) if 0 < army <= len(cols) else (200, 200, 200)


def vision_map(m, army=1):
    """The cells the player's side sees (approximate: each unit's vision range by Manhattan distance, owned properties one cell)."""
    h, w = len(m.tiles), len(m.tiles[0])
    T = terrain()
    team = m.meta.get("team") or list(range(1, len(m.meta.get("colours") or []) + 1))
    mine = lambda a: team[a - 1] == team[army - 1]
    seen = [[False] * w for _ in range(h)]
    srcs = [(u["x"], u["y"], VISION.get(u["kind"], 3)) for u in m.units if mine(u["army"])]
    for y in range(h):
        for x in range(w):
            t = m.tiles[y][x]
            if t in PROP_KIND and PROP_KIND[t][1] and mine(PROP_KIND[t][1]):
                srcs.append((x, y, 1))
    for sx, sy, r in srcs:
        for y in range(max(0, sy - r), min(h, sy + r + 1)):
            for x in range(max(0, sx - r), min(w, sx + r + 1)):
                if abs(x - sx) + abs(y - sy) <= r:
                    seen[y][x] = True
    return seen


def draw(m, mission, title, fog=False, cell=CELL, subtitle=""):
    T = terrain()
    h, w = len(m.tiles), len(m.tiles[0])
    notes = notes_of(m.name)
    head, foot = 58, 0
    legend_w = 330
    img = Image.new("RGB", (w * cell + legend_w, max(h * cell + head, head + 420)), (22, 22, 28))
    d = ImageDraw.Draw(img)
    d.text((8, 8), f"MISSION {mission} {DASH} {title}" + ("   (fog of war: the player's view)" if fog else ""), fill=(250, 235, 120), font=_title_font(26))
    d.text((8, 40), f"{m.name}  {w}x{h}   {subtitle}", fill=(200, 200, 210), font=font(11))
    f, fs = font(max(8, cell - 8)), font(11)
    seen = vision_map(m) if fog else None
    for y in range(h):
        for x in range(w):
            t = m.tiles[y][x]
            c = T.ch(t)
            col = COL.get(c, (255, 255, 255))
            x0, y0 = x * cell, y * cell + head
            lab = ""
            if c in "HBCAP":
                own = PROP_KIND[t][1]
                col = colour_of(m, own) if own else (175, 175, 175)
                lab = c
            elif c == "T":
                lab = "T"; col = (220, 220, 235)
            d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=col)
            ch = m.text[y][x] if m.text else ""
            if c == "f":
                d.ellipse([x0 + 3, y0 + 3, x0 + cell - 4, y0 + cell - 4], fill=(30, 95, 45))
            elif c == "^":
                d.polygon([(x0 + 2, y0 + cell - 3), (x0 + cell // 2, y0 + 3), (x0 + cell - 3, y0 + cell - 3)], fill=(105, 88, 72))
            elif c == "=":
                d.line([x0, y0 + cell // 2, x0 + cell, y0 + cell // 2], fill=(235, 200, 120), width=3)
            elif c == "M":
                d.rectangle([x0 + 4, y0 + 4, x0 + cell - 5, y0 + cell - 5], fill=(190, 40, 40)); lab = "S"
            elif c == "r":
                d.ellipse([x0 + 6, y0 + 6, x0 + cell - 7, y0 + cell - 7], fill=(40, 150, 160))
            if c == "#" and ch not in ".#":
                d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=(120, 50, 150)); lab = ch
            if lab:
                d.text((x0 + cell // 2 - 4, y0 + 2), lab, fill=(0, 0, 0) if c != "#" else (255, 255, 255), font=f)
    for u in m.units or []:
        if fog and not seen[u["y"]][u["x"]] and not (m.meta.get("team") and m.meta["team"][u["army"] - 1] == m.meta["team"][0]) and u["army"] != 1:
            continue
        x0, y0 = u["x"] * cell, u["y"] * cell + head
        d.ellipse([x0 + 1, y0 + 1, x0 + cell - 2, y0 + cell - 2], fill=colour_of(m, u["army"]), outline=(0, 0, 0) if not u.get("name") else (255, 255, 255), width=1 if not u.get("name") else 2)
        d.text((x0 + cell // 2 - 4, y0 + 2), UNIT_INITIAL.get(u["kind"], "?"), fill=(255, 255, 255), font=f)
    if fog:
        shade = Image.new("RGBA", img.size, (0, 0, 0, 0))
        sd = ImageDraw.Draw(shade)
        for y in range(h):
            for x in range(w):
                if not seen[y][x]:
                    sd.rectangle([x * cell, y * cell + head, x * cell + cell - 1, y * cell + head + cell - 1], fill=(10, 14, 30, 175))
        img = Image.alpha_composite(img.convert("RGBA"), shade).convert("RGB")
        d = ImageDraw.Draw(img)
    # the marked places (second HQs and the like): small labelled flags; every `mark*` note
    for key, x, y, text in notes:
        if key.startswith("mark"):
            x0, y0 = x * cell, y * cell + head
            d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], outline=(255, 60, 60), width=2)
            label = text.split(":")[0][:22]
            d.rectangle([x0 + cell, y0 - 2, x0 + cell + 7 * len(label) + 6, y0 + 12], fill=(255, 255, 255))
            d.text((x0 + cell + 3, y0 - 1), label, fill=(160, 0, 0), font=fs)
    # legend
    lx = w * cell + 10
    ly = head + 2
    d.text((lx, ly), "armies", fill=(240, 240, 240), font=fs); ly += 16
    cols = list(m.meta.get("colours") or [])
    for i, c in enumerate(cols):
        n = sum(1 for u in m.units if u["army"] == i + 1)
        d.rectangle([lx, ly, lx + 12, ly + 12], fill=COLOUR.get(c, (200, 200, 200)))
        role = "Black Hole (player)" if i == 0 else COLOUR_NAME.get(c, "?") + " (enemy)"
        d.text((lx + 18, ly), f"army {i + 1}: {role}, {n} units", fill=(230, 230, 230), font=fs); ly += 16
    ly += 6
    props = {}
    for y in range(h):
        for x in range(w):
            t = m.tiles[y][x]
            if t in PROP_KIND:
                k, o = PROP_KIND[t]
                props.setdefault(o, {}).setdefault(k, 0)
                props[o][k] += 1
    for o in sorted(props):
        who = "neutral" if not o else f"army {o}"
        d.text((lx, ly), who + ": " + " ".join(f"{k}{n}" for k, n in sorted(props[o].items())), fill=(200, 200, 200), font=fs); ly += 14
    ly += 6
    kinds = {}
    for u in m.units:
        kinds.setdefault(u["army"], {}).setdefault(u["kind"], 0)
        kinds[u["army"]][u["kind"]] += 1
    for a in sorted(kinds):
        d.text((lx, ly), f"a{a}: " + " ".join(f"{UNIT_INITIAL.get(k, '?')}{n}" for k, n in sorted(kinds[a].items())), fill=(200, 200, 200), font=fs); ly += 14
    ly += 6
    for key, x, y, text in notes:
        if ly > img.size[1] - 14:
            break
        d.text((lx, ly), f"{key} ({x},{y})"[:40], fill=(160, 160, 175), font=fs); ly += 13
    return img


def write_all(out_dir, with_fog=(1, 6, 10)):
    """m01.png .. (full map, fog OFF, labelled), the fog views listed in `with_fog`, one contact sheet an act (`act1_sheet.png`, `act2_sheet.png`). Returns the paths."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    ms = maps()
    paths, thumbs = [], {}
    for n, (name, title) in sorted(MISSIONS.items()):
        if name not in ms:
            continue
        subs = [name] + ([FRONT2[n]] if n in FRONT2 and FRONT2[n] in ms else [])
        imgs = []
        for i, nm in enumerate(subs):
            sub = "" if len(subs) == 1 else ("front 1" if i == 0 else FRONT2_LABEL.get(n, "front 2"))
            imgs.append(draw(ms[nm], n, title if len(subs) == 1 else f"{title} {DASH} {sub}", subtitle=sub))
        if len(imgs) == 1:
            img = imgs[0]
        else:
            Wd = max(i.size[0] for i in imgs)
            img = Image.new("RGB", (Wd, sum(i.size[1] for i in imgs)), (22, 22, 28))
            y = 0
            for i in imgs:
                img.paste(i, (0, y)); y += i.size[1]
        p = out / f"m{n:02d}.png"
        img.save(p); paths.append(p)
        act = next(a for a, (lo, hi, _) in ACTS.items() if lo <= n <= hi)
        thumbs.setdefault(act, []).append((n, title, img))
        if n in with_fog:
            fi = draw(ms[name], n, title if len(subs) == 1 else f"{title} {DASH} front 1", fog=True)
            fp = out / f"m{n:02d}_fog.png"
            fi.save(fp); paths.append(fp)
            if len(subs) > 1:                    # (a fogged two-front mission: the second front's view too)
                f2 = draw(ms[subs[1]], n, f"{title} {DASH} {FRONT2_LABEL.get(n, 'front 2')}", fog=True)
                f2p = out / f"m{n:02d}_front2_fog.png"
                f2.save(f2p); paths.append(f2p)
    for act, th in sorted(thumbs.items()):
        sp = out / f"act{act}_sheet.png"
        contact_sheet(th, act=act).save(sp); paths.append(sp)
    return paths


def contact_sheet(thumbs, width=2200, act=1):
    cols = 2
    tw = width // cols - 12
    tiles = []
    for n, title, img in thumbs:
        s = tw / img.size[0]
        tiles.append(img.resize((tw, max(1, int(img.size[1] * s))), Image.LANCZOS))
    rows = [tiles[i:i + cols] for i in range(0, len(tiles), cols)]
    hh = sum(max(t.size[1] for t in r) + 10 for r in rows) + 60
    sheet = Image.new("RGB", (width, hh), (12, 12, 16))
    d = ImageDraw.Draw(sheet)
    lo, hi, name = ACTS[act]
    d.text((14, 10), f"BH2 Campaign {DASH} Act {'I' * act if act < 4 else act}: {name} (missions {lo} to {hi})", fill=(250, 235, 120), font=_title_font(30))
    y = 56
    for r in rows:
        x = 6
        for t in r:
            sheet.paste(t, (x, y)); x += tw + 12
        y += max(t.size[1] for t in r) + 10
    return sheet


def world_flags(out, act=None):
    """The BH2 picture world map as the GBA draws it, scaled up, with the mission flags (number labels) and the nation names. `act`: only that act's flags, the map cropped round them."""
    import numpy as np
    from ..worldmaplib import tool, convert
    m, c = tool.load("bh2")
    sc = 4
    base = Image.fromarray(convert.render(m)).resize((m.width * sc, m.height * sc), Image.NEAREST)
    d = ImageDraw.Draw(base)
    ft = _title_font(22)
    shown = [f for f in flags() if act is None or ACTS[act][0] <= f[0] <= ACTS[act][1]]
    for mission, region, x, y in shown:
        cx, cy = x * sc + sc // 2, y * sc + sc // 2
        col = (140, 60, 190) if region == 5 else (30, 30, 30)
        d.line([cx, cy, cx, cy - 34], fill=(20, 20, 20), width=3)
        d.polygon([(cx, cy - 34), (cx + 26, cy - 26), (cx, cy - 18)], fill=(220, 40, 40))
        d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill=(255, 255, 255), outline=(0, 0, 0), width=2)
        lab = f"M{mission}"
        d.rectangle([cx + 28, cy - 38, cx + 28 + 17 * len(lab) + 6, cy - 14], fill=(20, 20, 30))
        d.text((cx + 32, cy - 36), lab, fill=(250, 235, 120), font=_title_font(20))
    names = {3: ("Green Earth", (96, 150)), 5: ("Black Hole's island", (14, 236)), 4: ("Yellow Comet", (188, 150))}
    if act:
        for nid, (label, (nx, ny)) in names.items():
            if any(f[1] == nid for f in shown):
                ft2 = _title_font(24)
                d.rectangle([nx * sc - 4, ny * sc - 2, nx * sc + 13 * len(label) + 10, ny * sc + 28], fill=(20, 20, 30))
                d.text((nx * sc, ny * sc), label, fill=(240, 240, 240), font=ft2)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if act:
        xs, ys = [f[2] for f in shown], [f[3] for f in shown]
        box = (max(0, (min(xs) - 100) * sc), max(0, (min(ys) - 60) * sc), min(base.size[0], (max(xs) + 21) * sc), min(base.size[1], (max(ys) + 40) * sc))
        base = base.crop(box)
    canvas = Image.new("RGB", (base.size[0], base.size[1] + 50), (22, 22, 28))
    canvas.paste(base, (0, 50))
    title = f"BH2 world map {DASH} flags of M1 to M5 (M26 secret)" if not act else f"BH2 world map {DASH} flags of M{ACTS[act][0]} to M{ACTS[act][1]} (Act {'I' * act})"
    ImageDraw.Draw(canvas).text((10, 10), title, fill=(250, 235, 120), font=_title_font(24))
    canvas.save(out)
    return out


# ------------------------------------------------------------------ the game's own pictures

def _labelled(im, text, scale, size):
    im = im.resize((im.width * scale, im.height * scale), Image.NEAREST) if scale != 1 else im
    bar = size + 16
    out = Image.new("RGB", (max(im.width, 40 * size // 2 + 16), im.height + bar), (20, 20, 28))
    out.paste(im, (0, bar))
    ImageDraw.Draw(out).text((8, 6), text, fill=(250, 235, 120), font=_title_font(size))
    return out


def game_sheets(raw, out, scale=3, acts=None):
    """From the harness's pictures of the game itself (`aw2dev maps boot --campaign bh2`: m<N>_full / fogon / fogoff / front2.png, 16 pixels a cell) the review set: `m0N.png`
    (the full map, fog off, "MISSION N - Title" burned in), `m0N_fog.png` (fogged missions), `m0N_front2.png` (two-front missions) and one `act<A>_game_sheet.png` an act with pictures. Returns the paths."""
    raw, out = Path(raw), Path(out)
    out.mkdir(parents=True, exist_ok=True)
    paths, tiles = [], {}
    for n, (name, title) in sorted(MISSIONS.items()):
        main = next((raw / f"m{n}_{v}.png" for v in ("full", "fogoff") if (raw / f"m{n}_{v}.png").exists()), None)
        if main is None:
            continue
        act = next(a for a, (lo, hi, _) in ACTS.items() if lo <= n <= hi)
        if acts and act not in acts:
            continue
        im = Image.open(main).convert("RGB")
        big = _labelled(im, f"MISSION {n} {DASH} {title}" + ("  (front 1)" if n in FRONT2 else "") + "  (the game's own picture, fog off)", scale, 26)
        p = out / f"m{n:02d}.png"
        big.save(p); paths.append(p)
        tiles.setdefault(act, []).append(_labelled(im, f"MISSION {n} {DASH} {title}" + ("  (front 1)" if n in FRONT2 else ""), 1, 15))
        for view, fname, label in (("fogon", f"m{n:02d}_fog.png", "fog of war: the player's view"), ("front2", f"m{n:02d}_front2.png", FRONT2_LABEL.get(n, "front 2")),
                                   ("front2fog", f"m{n:02d}_front2_fog.png", "front 2, fog of war: the player's view")):
            f = raw / f"m{n}_{view}.png"
            if f.exists():
                im2 = Image.open(f).convert("RGB")
                q = out / fname
                _labelled(im2, f"MISSION {n} {DASH} {title}  ({label})", scale, 26).save(q); paths.append(q)
                tiles[act].append(_labelled(im2, f"MISSION {n} {DASH} {title}  ({label})", 1, 15))
    for act, ts in sorted(tiles.items()):
        cols = 2
        rows = [ts[i:i + cols] for i in range(0, len(ts), cols)]
        W = sum(max(t.width for t in col) for col in zip(*[r + [Image.new("RGB", (1, 1))] * (cols - len(r)) for r in rows])) + 8 * (cols + 1)
        H = sum(max(t.height for t in r) + 8 for r in rows) + 60
        sheet = Image.new("RGB", (W, H), (12, 12, 16))
        ImageDraw.Draw(sheet).text((10, 8), f"BH2 Campaign {DASH} Act {'I' * act}: {ACTS[act][2]} (the game's own pictures)", fill=(250, 235, 120), font=_title_font(30))
        y = 52
        for r in rows:
            x = 8
            for t in r:
                sheet.paste(t, (x, y)); x += max(t.width, 360) + 8
            y += max(t.height for t in r) + 8
        sp = out / f"act{act}_game_sheet.png"
        sheet.save(sp); paths.append(sp)
    return paths
