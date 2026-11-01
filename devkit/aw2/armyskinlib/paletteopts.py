"""`aw2dev armyskin palette-options`: one comparison sheet of candidate palettes for the skin, each row a letter (A, B, ...): the owner picks one.

A candidate is a fragment `DIR/A.toml` with `name`, `description` and a `[colours]` table that overrides the skin file's own (`ramp`, `building`, `trim`, `moved_tint`,
`moved_dim`, `moved_lift`, `gold`, `orb`). For each letter the skin file is replaced for the length of the run (and always restored), the harness example is rebuilt, and the
real game draws: every unit idle and done (Dual Strike pack, Silver Nova's own soldiers), a map with the army's city, Com Tower, base, airport and port beside an unowned city and
Blue Moon's and Black Hole's, and the HQ and emblem are drawn from the data file in the patched palette. The static check's distances are printed and written under each row."""
import re, subprocess, tomllib
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from . import SKIN_DIR, Rom, BLD_PAL, check as chk, scenarios
from .. import cfg, harness, util

SKIN = SKIN_DIR / "emerald_sun.toml"
SCALE = 4
UNIT_CELLS = [("Infantry", 0, 0), ("Mech", 1, 0), ("Tank", 3, 0), ("Md Tank", 4, 0), ("Fighter", 11, 0), ("Battleship", 0, 1)]   # (name, parade x, parade row)
KEYS = ("emblem_tones", "ramp", "building", "trim", "moved_tint", "moved_dim", "moved_lift", "gold", "orb", "gold_dark")


def merged(base_text, cand):
    """The skin file's text with the candidate's `[colours]` values in place of its own."""
    text = base_text
    for k, v in cand.get("colours", {}).items():
        if k not in KEYS:
            continue
        val = "[" + ", ".join(f'"{x}"' for x in v) + "]" if isinstance(v, list) else (f'"{v}"' if isinstance(v, str) else repr(v))
        text, n = re.subn(rf"(?m)^{k} = .*$", f"{k} = {val}", text, count=1)
        if n != 1:
            raise SystemExit(f"palette option: the skin file has no `{k} =` line")
    return text


def build_example():
    env = dict(__import__("os").environ)
    env["PATH"] = str(Path(cfg.cargo_bin()) if hasattr(cfg, "cargo_bin") else Path("~/.rustup/toolchains/stable-aarch64-apple-darwin/bin").expanduser()) + ":" + env["PATH"]
    r = subprocess.run(["cargo", "build", "--release", "-p", "tango-gamesupport-aw2", "--example", "aw2_room_teams", "--example", "aw2_skin_dump"], cwd=cfg.REPO, env=env, capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("cargo build failed: " + r.stderr[-400:])


def props_script():
    """The map with the army's own cities, bases and HQ beside unowned cities, Blue Moon's and Black Hole's soldiers (three seats); nothing is placed: the map's own properties."""
    body = ("aid unit 1 inf 4 6\naid unit 2 inf 5 6\naid unit 3 inf 6 6\naid unit 1 tank 8 6\naid unit 2 tank 9 6\naid unit 3 tank 10 6\n"
            + scenarios.redraw((8, 5)) + "goto 0 0 0\nwait 40\ngoto 0 8 7\nwait 60\nshot props 0\n")
    return scenarios.header([6, 2, 5], ds=True, tabitha=[0]) + body


CAPTURE_KINDS = ["city", "lab", "base", "airport", "port", "hq"]   # (`lab` is the Com Tower's picture)
MAP_CROP = (40, 16, 200, 140)          # the property map's crop (game pixels)
OWNED_CITY, NEUTRAL_CITY = (110, 24, 146, 50), (44, 122, 84, 146)   # where the army's cities and the unowned ones are in that shot
BOX_CROP = (113, 14, 158, 80)


def run_shots(out):
    """The harness runs for one palette (the skin file compiled in): the parade, the property map and each property's capture box."""
    out.mkdir(parents=True, exist_ok=True)
    jobs = [("parade", scenarios.script("parade", ds=True, tabitha=[0])), ("props", props_script())]
    for k in CAPTURE_KINDS:
        jobs.append((f"capture_from_es_{k}", scenarios.script(f"capture_from_es_{k}", ds=True, tabitha=[1])))
    for name, text in jobs:
        d = out / name
        d.mkdir(parents=True, exist_ok=True)
        (d / "script.txt").write_text(text)
        rc, log = harness.run_script(d / "script.txt", d, ds=True)
        if rc:
            raise SystemExit(f"palette option: the {name} script failed ({log})")
    return out


def _body_colours(im):
    from collections import Counter
    out = Counter()
    for r, g, b in im.convert("RGB").getdata():
        if g > r + 18 and g > b + 25:      # the grass
            continue
        if max(r, g, b) < 60:               # outlines
            continue
        out[(r, g, b)] += 1
    return [c for c, k in out.most_common(10) if k >= 5]


def neutral_gap(shot):
    """Mean over the army's city colours of the distance to the nearest colour of the unowned city beside it (CIE76): small means the army's city reads as neutral."""
    im = Image.open(shot).convert("RGB")
    own, neu = _body_colours(im.crop(OWNED_CITY)), _body_colours(im.crop(NEUTRAL_CITY))
    if not own or not neu:
        return None
    return sum(min(chk.de(a, b) for b in neu) for a in own) / len(own)


def up(im, k=SCALE):
    return im.resize((im.width * k, im.height * k), Image.NEAREST)


def hq_picture(skin_path, scale):
    """The skin's HQ (the file's rows) in the building palette as the patched ROM has it on colour 3, and the emblem drawn from the file (its own colours)."""
    data = tomllib.loads(Path(skin_path).read_text())
    pal = Rom(3, skin_path).pal(BLD_PAL + 32 * 2)
    hq = Image.new("RGBA", (16, 32), (0, 0, 0, 0))
    for y, row in enumerate(data["hq"]["rows"]):
        for x, c in enumerate(row):
            if c != ".":
                hq.putpixel((x, y), pal[int(c, 16)] + (255,))
    c = data["colours"]
    h = lambda s: tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))
    ramp = [h(x) for x in c["ramp"]]
    et = [h(x) for x in c["emblem_tones"]] if "emblem_tones" in c else [ramp[0], ramp[4], ramp[2]]
    tone = {"1": (255, 255, 255), "2": tuple(int(v * 0.55) for v in ramp[4]), "a": et[2], "b": et[1], "c": et[0]}
    em = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
    for y, row in enumerate(data["emblem"]["rows"]):
        for x, ch in enumerate(row):
            if ch in tone:
                em.putpixel((x, y), tone[ch] + (255,))
    return up(hq, scale), up(em, scale)


def label(draw, xy, text, size, fill=(255, 255, 255)):
    f = ImageFont.load_default(size=size)
    draw.text(xy, text, font=f, fill=fill)


def row_picture(letter, cand, skin_path, shots, rep):
    """One row of the sheet at 4x."""
    parts = []
    parade, done = Image.open(shots / "parade" / "parade_s0.bmp").convert("RGB"), Image.open(shots / "parade" / "parade_done_s0.bmp").convert("RGB")
    for src in (parade, done):
        strip = Image.new("RGB", (6 * 16 * SCALE + 5 * 8, 16 * SCALE), (45, 48, 56))
        for i, (name, x, r) in enumerate(UNIT_CELLS):
            cell = src.crop((x * 16, 60 + 16 * r, x * 16 + 16, 76 + 16 * r))
            strip.paste(up(cell), (i * (16 * SCALE + 8), 0))
        parts.append(strip)
    boxes = Image.new("RGB", (len(CAPTURE_KINDS) * (45 * SCALE + 6), 66 * SCALE), (45, 48, 56))
    for i, k in enumerate(CAPTURE_KINDS):
        shot = shots / f"capture_from_es_{k}" / "capture2_s0.bmp"
        boxes.paste(up(Image.open(shot).convert("RGB").crop(BOX_CROP)), (i * (45 * SCALE + 6), 0))
    hq, em = hq_picture(skin_path, SCALE)
    hqem = Image.new("RGB", (hq.width + em.width + 20, hq.height), (96, 104, 116))
    hqem.paste(hq, (0, 0), hq)
    hqem.paste(em, (hq.width + 20, 0), em)
    mp = up(Image.open(shots / "props" / "props_s0.bmp").convert("RGB").crop(MAP_CROP), SCALE // 2 * 2 if False else 3)
    return parts, boxes, hqem, mp


def run(dir, letters, out_png, say=print):
    dir = Path(dir)
    base = SKIN.read_text()
    letters = list(letters)
    rows, notes = [], {}
    try:
        for L in letters:
            cand = tomllib.loads((dir / f"{L}.toml").read_text())
            SKIN.write_text(merged(base, cand))
            say(f"{L}: {cand.get('name', '')}: building the harness with the palette")
            build_example()
            work = cfg.work("armyskin", "palette_options", L)
            shots = run_shots(work)
            fails, rep = chk.static(str(SKIN))
            gap = neutral_gap(shots / "props" / "props_s0.bmp")
            pic = row_picture(L, cand, str(SKIN), shots, rep)
            rows.append((L, cand, pic, fails, rep, gap))
    finally:
        SKIN.write_text(base)
    # the sheet
    W = 40 + 200 + 12 * 0
    cols = []
    for L, cand, (units, boxes, hqem, mp), fails, rep, gap in rows:
        h = max(units[0].height, boxes.height, hqem.height, mp.height) + 130
        w = 180 + units[0].width + 20 + units[1].width + 20 + boxes.width + 20 + hqem.width + 20 + mp.width + 20
        cols.append((w, h))
    SW = max(c[0] for c in cols)
    SH = sum(c[1] for c in cols) + 60
    sheet = Image.new("RGB", (SW, SH), (30, 32, 38))
    d = ImageDraw.Draw(sheet)
    label(d, (10, 6), "Silver Nova palette options (4x; per row: units idle, done, capture boxes city / Com Tower / base / airport / port / HQ, HQ + emblem, map crop beside Blue Moon and Black Hole at 3x)", 18)
    y = 40
    for (L, cand, (units, boxes, hqem, mp), fails, rep, gap), (w, h) in zip(rows, cols):
        d.rectangle([0, y, SW, y + h - 6], outline=(90, 94, 104))
        label(d, (14, y + 10), L, 120, (255, 220, 90))
        label(d, (14, y + 140), cand.get("name", ""), 20)
        x = 180
        ty = y + 70
        for im in (units[0], units[1]):
            sheet.paste(im, (x, ty)); x += im.width + 20
        sheet.paste(boxes, (x, y + 20)); x += boxes.width + 20
        sheet.paste(hqem, (x, y + 20), None); x += hqem.width + 20
        sheet.paste(mp, (x, y + 20)); x += mp.width + 20
        pick = lambda key: next((re.search(r"closest\s+([\d.]+)|(?<=\s)([\d.]+)\s+\(>=", l) for l in rep if key in l), None)
        def num(key, closest=True):
            for l in rep:
                if key in l:
                    m = re.search(r"closest\s+([\d.]+)" if closest else r"([\d.]+)\s+\(>=", l)
                    if m:
                        return float(m.group(1))
            return float("nan")
        vals = f"Blue Moon {num('Blue Moon'):.1f}   Black Hole {num('Black Hole'):.1f}   done greys {num('done greys', False):.1f}   fog {num('fog terrain', False):.1f}   city vs unowned city {gap:.1f}" if gap is not None else ""
        label(d, (14, y + h - 70), "distances (need >= 10, 10, 9, 9):  " + vals, 22)
        label(d, (14, y + h - 38), ("FAIL: " + "; ".join(fails)) if fails else "check ok", 22, (255, 120, 120) if fails else (140, 230, 140))
        y += h
    Path(out_png).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    notes = {L: (fails, rep, gap) for L, cand, pic, fails, rep, gap in rows}
    return notes
