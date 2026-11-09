"""aw2dev conquest: Conquest Run, Select Mode's CONQUEST entry (a five-map roguelike run on the Gauntlet's engine), in the offline harness (docs/dev/conquest.md).

  conquest start [--co N] [--out DIR]   boots the harness straight into a run (title, Select Mode, CONQUEST, the one-row selector "Conquest Run *", the army screen with CO N, map 1, the reward page after its
                                        capture, map 2) and leaves a picture of each screen: 1_wheel, 2_map_selector, 3_army_screen, 4_first_turn, 5_reward_page, 6_reward_units, 7_second_map
                                        (PNG, in DIR or a temp folder; fails when one is missing)
  conquest sheet [--out FILE]           one contact sheet in the three looks (AW2 graphics, Dual Strike graphics + tilt, Dual Strike flat): the reward page, the unit page and each of the nine maps' first turn
  conquest maps [--all]                 the nine maps as the ROM has them (size, HQs, distance) against the constants of `crate::conquest::MAPS` (exit 1 on a mismatch); --all lists every two-player
                                        Versus map with its HQ distance and bases (to choose another map for a stage: docs/dev/conquest.md "Adding or changing a map")
  conquest candidates --out DIR         contact sheets (PNG) + candidates.md of every two-player Versus map that fits Conquest (HQs 20+ apart, equal bases, a ground route) and is not in the
                                        current run, small to large, each tile lettered with name, size, HQ distance, bases, airports and ports (docs/dev/conquest.md "Adding or changing a map")
  conquest test                         the run's regression tests (`run.py -k conquest --mode ds`)
"""
import os
import subprocess
import sys
import tempfile

from .. import cfg, util

START_PICTURES = ["1_wheel", "2_map_selector", "3_army_screen", "4_first_turn", "5_reward_page", "6_reward_units", "7_second_map"]
CONQUEST_RS = cfg.REPO / "tango-gamesupport-aw2" / "src" / "conquest.rs"


def register(sub):
    g = sub.add_parser("conquest", help="Conquest Run: boot into a run with pictures, the contact sheet, the maps check, its tests (docs/dev/conquest.md)")
    gs = g.add_subparsers(dest="conquestcmd", required=True)
    a = gs.add_parser("start", help="title -> CONQUEST -> army screen -> map 1 -> reward page -> map 2, with a picture of each screen")
    a.add_argument("--co", type=int, default=1, help="AW2 CO id to pick (default 1, Andy)")
    a.add_argument("--out", help="folder for the pictures (default: a temp folder, printed)")
    a.add_argument("-v", "--verbose", action="store_true")
    a.set_defaults(fn=start)
    a = gs.add_parser("sheet", help="the reward page and each map's first turn in the three looks, one contact sheet")
    a.add_argument("--out", help="the sheet's PNG (default: devkit/work/conquest/sheet.png)")
    a.set_defaults(fn=sheet)
    a = gs.add_parser("maps", help="the run's nine maps read from the ROM against the Rust constants; --all lists every 2P Versus map")
    a.add_argument("--all", action="store_true", help="every two-player Versus map with its HQ distance and bases")
    a.set_defaults(fn=maps)
    a = gs.add_parser("candidates", help="contact sheets of the Versus maps that fit Conquest and are not in the run, lettered, small to large, plus a markdown table")
    a.add_argument("--out", required=True, help="folder for sheet_N.png and candidates.md (outside the repo: the pictures are drawn from the ROM)")
    a.add_argument("--per-sheet", type=int, default=6, help="tiles on a sheet (default 6)")
    a.add_argument("--equal-only", action="store_true", help="leave out the maps that fit with a 1-base difference (they are listed, flagged, by default)")
    a.set_defaults(fn=candidates)
    a = gs.add_parser("test", help="run the Conquest Run tests")
    a.set_defaults(fn=test)


def _run(extra_env, args):
    run = cfg.REPO / "tools" / "aw2test" / "run.py"
    env = dict(os.environ, **extra_env)
    return subprocess.run([sys.executable, str(run)] + args, env=env, cwd=cfg.REPO, text=True)


def start(a):
    out = a.out or tempfile.mkdtemp(prefix="conquest_start_")
    r = _run({"AW2TEST_CONQUEST_CO": str(a.co), "AW2TEST_CONQUEST_OUT": out}, ["-k", "conquest_tool_start", "--mode", "ds"] + (["-v"] if a.verbose else []))
    names = sorted(os.listdir(out)) if os.path.isdir(out) else []
    util.say("pictures:", out, names)
    missing = [n for n in START_PICTURES if n + ".png" not in names]
    if missing and not r.returncode:
        util.say("MISSING pictures:", missing)
        return 1
    return r.returncode


def sheet(a):
    out = a.out or str(cfg.work("conquest") / "sheet.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    r = _run({"AW2TEST_SHEET": out}, ["-k", "conquest_pictures", "--mode", "ds"])
    util.say("sheet:", out)
    return r.returncode


def test(a):
    return _run({}, ["-k", "conquest", "--mode", "ds"]).returncode


# -- the maps, from the ROM ----------------------------------------------------------------------------------------------------------------------------------------------

GAME_MAP_TABLE = 0x085C77A0        # AW2's own map table: 0x5C-byte entries, +0x00 the map's LZ77 blob, +0x14 the name's text id
ENTRY = 0x5C
# crate::five::PROPERTY_TILES: [kind][owner] (kinds: HQ, base, city, airport, port, lab; owner 0 neutral, 1..5 the armies)
PROPERTY_TILES = [[0x1C0, 0x1C5, 0x1CA, 0x1CF, 0x1D4, 0x1B4], [0x1C1, 0x1C6, 0x1CB, 0x1D0, 0x1D5, 0x1B5], [0x1C2, 0x1C7, 0x1CC, 0x1D1, 0x1D6, 0x1B6],
                  [0x1C3, 0x1C8, 0x1CD, 0x1D2, 0x1D7, 0x1B7], [0x1C4, 0x1C9, 0x1CE, 0x1D3, 0x1D8, 0x1B8], [0x1D9, 0x1DA, 0x1DB, 0x1DC, 0x1DD, 0x1B9]]
KINDS = ["HQ", "base", "city", "airport", "port", "lab"]
VERSUS_IDS = list(range(0x01, 0x27)) + list(range(0x6C, 0x7C)) + list(range(0x80, 0x8A))


def read_map(data, mid):
    """(width, height, {(kind, owner): [(x, y)]}) of AW2's map `mid`, from the ROM image `data`; None when the entry has no map."""
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import rom
    ptr = int.from_bytes(data[GAME_MAP_TABLE - 0x08000000 + ENTRY * mid:][:4], "little")
    if not 0x08000000 <= ptr < 0x0A000000:
        return None
    raw = rom.lz10(data[ptr - 0x08000000:ptr - 0x08000000 + 0x3000])
    w, h = raw[0], raw[1]
    where = {}
    index = {t: (k, o) for k, row in enumerate(PROPERTY_TILES) for o, t in enumerate(row)}
    for i in range(w * h):
        t = int.from_bytes(raw[2 + 2 * i:4 + 2 * i], "little")
        if t in index:
            where.setdefault(index[t], []).append((i % w, i // w))
    return w, h, where


def rust_stages():
    """crate::conquest::MAPS read from the source: [{id, name, player, enemy}]."""
    import re
    src = CONQUEST_RS.read_text()
    body = src[src.index("pub const MAPS"):src.index("/// The enemy army's colour")]
    out = []
    for m in re.finditer(r"id: (0x[0-9A-Fa-f]+),\s*name: \"([^\"]+)\",\s*player: \((\d+), (\d+)\),\s*enemy: \((\d+), (\d+)\)", body):
        out.append({"id": int(m.group(1), 16), "name": m.group(2), "player": (int(m.group(3)), int(m.group(4))), "enemy": (int(m.group(5)), int(m.group(6)))})
    return out


def maps(a):
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import paths
    data = open(paths.aw2_rom(), "rb").read()
    bad = 0
    if a.all:
        util.say("id   size    HQs apart  bases (army 1 / 2)  airports  ports  land route  equal  fits Conquest  name")
        for r in all_maps(data):
            util.say(f"{r['id']:#04x} {r['w']:>2}x{r['h']:<2}   {r['dist']:>3}       {r['b1']:>2} / {r['b2']:<2}          {r['air']:>2}        {r['port']:>2}     "
                     f"{'yes' if r['route'] else 'NO ':<3}         {'yes' if r['b1'] == r['b2'] else 'no ':<3}    {r['fits']:<13}  {r['name']}")
        return 0
    for s in rust_stages():
        r = read_map(data, s["id"])
        if not r:
            util.say(f"{s['name']}: map {s['id']:#x} is not in the ROM")
            bad += 1
            continue
        w, h, where = r
        p, e = where.get((0, 1), [None])[0], where.get((0, 2), [None])[0]
        ok = p == s["player"] and e == s["enemy"]
        bad += not ok
        d = abs(p[0] - e[0]) + abs(p[1] - e[1]) if p and e else -1
        util.say(f"{'ok ' if ok else 'BAD'} {s['id']:#04x} {s['name']}: {w}x{h}, HQs {p} / {e} ({d} apart); Rust says {s['player']} / {s['enemy']}")
        for army in (1, 2):
            util.say(f"       army {army}: " + ", ".join(f"{len(where.get((k, army), []))} {KINDS[k]}" for k in range(5) if where.get((k, army))))
    util.say(f"conquest maps: {len(rust_stages())} stages, {bad} mismatch(es)")
    return 1 if bad else 0


# -- every Versus map: name, ground route, the Conquest verdict -----------------------------------------------------------------------------------------------------------

TEXT_TABLE = 0x08610A38            # crate::campaign_model::TEXT_TABLE: text id -> pointer
IMPASSABLE = set("~rIZ")           # terrain.py characters a ground unit cannot enter: sea, reef, pipe, pipe seam (everything else, shoals, bridges, roads, mountains, properties, silos, is passable)


def map_name(data, mid):
    """The name AW2 shows for map `mid` in Versus: the entry's text id (+0x14) through the text table."""
    tid = int.from_bytes(data[GAME_MAP_TABLE - 0x08000000 + ENTRY * mid + 0x14:][:2], "little")
    p = int.from_bytes(data[TEXT_TABLE - 0x08000000 + 4 * tid:][:4], "little") - 0x08000000
    return data[p:data.index(b"\0", p)].decode("latin-1")


def read_tiles(data, mid):
    """The map's tile ids as rows (a list of lists), or None."""
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import rom
    ptr = int.from_bytes(data[GAME_MAP_TABLE - 0x08000000 + ENTRY * mid:][:4], "little")
    if not 0x08000000 <= ptr < 0x0A000000:
        return None
    raw = rom.lz10(data[ptr - 0x08000000:ptr - 0x08000000 + 0x3000])
    w, h = raw[0], raw[1]
    t = [int.from_bytes(raw[2 + 2 * i:4 + 2 * i], "little") for i in range(w * h)]
    return [t[y * w:(y + 1) * w] for y in range(h)]


def land_route(rows, a, b):
    """True when a ground unit can walk from cell `a` to cell `b`: a flood fill over the tile classes (sea, reef, pipes and seams block; shoals, bridges, roads and the rest pass)."""
    from ..maplint.terrain import terrain
    T = terrain()
    h, w = len(rows), len(rows[0])
    ok = [[T.ch(rows[y][x]) not in IMPASSABLE for x in range(w)] for y in range(h)]
    seen, todo = {a}, [a]
    while todo:
        x, y = todo.pop()
        if (x, y) == b:
            return True
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and ok[ny][nx] and (nx, ny) not in seen:
                seen.add((nx, ny))
                todo.append((nx, ny))
    return False


def all_maps(data):
    """Every two-player Versus map as a dict: id, name, w, h, dist, b1, b2, air, port, route, fits ('yes', 'yes (1 base off)' or 'no: why'), rows."""
    out = []
    for mid in VERSUS_IDS:
        r = read_map(data, mid)
        if not r:
            continue
        w, h, where = r
        p, e = where.get((0, 1)), where.get((0, 2))
        if not p or not e:
            continue
        rows = read_tiles(data, mid)
        n = lambda k: len(where.get((k, 1), [])) + len(where.get((k, 2), []))
        d = abs(p[0][0] - e[0][0]) + abs(p[0][1] - e[0][1])
        b1, b2 = len(where.get((1, 1), [])), len(where.get((1, 2), []))
        route = land_route(rows, p[0], e[0])
        why = [s for s, bad in (("HQs under 20 apart", d < 20), ("no land route", not route), (f"bases {b1}/{b2}", abs(b1 - b2) > 1)) if bad]
        fits = "no: " + ", ".join(why) if why else ("yes" if b1 == b2 else "yes (1 base off)")
        out.append(dict(id=mid, name=map_name(data, mid), w=w, h=h, dist=d, b1=b1, b2=b2, air=n(3), port=n(4), route=route, fits=fits, rows=rows, hq=(p[0], e[0]),
                        air12=(len(where.get((3, 1), [])), len(where.get((3, 2), []))), port12=(len(where.get((4, 1), [])), len(where.get((4, 2), [])))))
    return out


def candidates(a):
    from PIL import Image, ImageDraw
    from ..maplint import load, render
    sys.path.insert(0, str(cfg.REPO / "tools" / "aw2test"))
    from aw2test import paths
    data = open(paths.aw2_rom(), "rb").read()
    current = {s["id"] for s in rust_stages()}
    pool = [r for r in all_maps(data) if r["id"] not in current and r["fits"].startswith("yes") and (not a.equal_only or r["b1"] == r["b2"])]
    pool.sort(key=lambda r: (r["w"] * r["h"], r["dist"], r["id"]))
    out = a.out
    os.makedirs(out, exist_ok=True)
    for r, letter in zip(pool, (chr(65 + i) if i < 26 else chr(65 + i // 26 - 1) + chr(65 + i % 26) for i in range(len(pool)))):
        r["letter"] = letter
    # (roads and shoals are close in the linter's colours: roads darker, shoals paler here, so the route can be read by eye)
    render.COL[","], render.COL["R"] = (246, 240, 176), (190, 156, 104)
    TILE_W, TILE_H, LAB = 640, 560, 96
    fl, fs = render.font(20), render.font(15)
    per = a.per_sheet
    sheets = []
    for n in range(0, len(pool), per):
        chunk = pool[n:n + per]
        cols = 3 if per >= 6 else 2
        rowsn = (len(chunk) + cols - 1) // cols
        img = Image.new("RGB", (cols * TILE_W, rowsn * TILE_H + 28), (24, 24, 30))
        d = ImageDraw.Draw(img)
        for i, r in enumerate(chunk):
            ox, oy = (i % cols) * TILE_W, (i // cols) * TILE_H
            cell = max(6, min((TILE_W - 16) // r["w"], (TILE_H - LAB - 16) // r["h"]))
            m = load.MapData(r["name"], "aw2", r["rows"])
            pic = render.draw_map(m, cell=cell, legend=False, title=" ")
            pic = pic.crop((0, 22, pic.width, pic.height))
            img.paste(pic, (ox + (TILE_W - pic.width) // 2, oy + LAB + (TILE_H - LAB - pic.height) // 2))
            d.rectangle([ox + 2, oy + 2, ox + TILE_W - 3, oy + TILE_H - 3], outline=(70, 70, 90))
            d.rectangle([ox + 8, oy + 8, ox + 62, oy + 62], fill=(240, 200, 40))
            d.text((ox + 20, oy + 18), r["letter"], fill=(0, 0, 0), font=render.font(34))
            d.text((ox + 72, oy + 10), f"{r['name']}  (id {r['id']:#04x})", fill=(255, 255, 255), font=fl)
            d.text((ox + 72, oy + 36), f"{r['w']}x{r['h']}   HQs {r['dist']} apart   bases {r['b1']}/{r['b2']}", fill=(220, 220, 230), font=fs)
            d.text((ox + 72, oy + 58), f"airports {r['air']}   ports {r['port']}" + ("   (1 base off)" if r["b1"] != r["b2"] else ""), fill=(220, 220, 230), font=fs)
        d.text((8, img.height - 22), "orange = army 1, blue = army 2, grey = neutral | H HQ, B base, C city, A airport, P port | tan road, pale shoal, brown bridge, dark blue sea, teal reef, red silo", fill=(180, 180, 195), font=fs)
        p = os.path.join(out, f"sheet_{n // per + 1}.png")
        img.save(p)
        sheets.append(p)
    md = ["| Letter | Id | Name | Size | HQs apart | Bases | Airports | Ports | Land route | Fits |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in pool:
        md.append(f"| {r['letter']} | {r['id']:#04x} | {r['name']} | {r['w']}x{r['h']} | {r['dist']} | {r['b1']}/{r['b2']} | {r['air']} | {r['port']} | {'yes' if r['route'] else 'no'} | {r['fits']} |")
    open(os.path.join(out, "candidates.md"), "w").write("\n".join(md) + "\n")
    util.say(f"{len(pool)} candidates; sheets:", sheets, "table:", os.path.join(out, "candidates.md"))
    return 0
