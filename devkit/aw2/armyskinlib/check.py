"""Checks of an army skin (docs/dev/army-packs.md): the data file, the palette's distance from AW2's armies, the coverage of every unit, and (live) that no
screen in the catalogue is left in the colours of the army the skin sits on."""
import math, tomllib
from pathlib import Path
from PIL import Image
from . import (HQ_ART, BLD_PAL, NAMES, UNIT_PAL, UNIT_SHEET, FRAME, SLOT_TABLE, Rom, dump, toml_art)

def hq_metrics(grid, pal):
    """How an HQ picture (16x32 palette indices) builds its depth: pixels filled, the first row used, the shades used, the share of the commonest shade, the
    value contrast (standard deviation of brightness) and the brightness of the left against the right three columns."""
    import statistics, collections
    px = [(x, y, v) for y, r in enumerate(grid) for x, v in enumerate(r) if v]
    L = [0.299 * pal[v][0] + 0.587 * pal[v][1] + 0.114 * pal[v][2] for x, y, v in px]
    cnt = collections.Counter(v for _, _, v in px)
    side = lambda xs: (lambda sel: sum(sel) / max(1, len(sel)))([0.299 * pal[v][0] + 0.587 * pal[v][1] + 0.114 * pal[v][2] for x, y, v in px if x in xs])
    return dict(fill=len(px), top=min(y for _, y, _ in px), shades=len(cnt), dominant=max(cnt.values()) / len(px), contrast=statistics.pstdev(L),
                left=side((0, 1, 2)), right=side((12, 13, 14)))


def aw2_hq_grid(base, c):
    from . import tile_px
    raw = base.raw(HQ_ART + 0x100 * (c - 1), 0x100)
    g = [[0] * 16 for _ in range(32)]
    for k in range(8):
        px = tile_px(raw, 32 * k)
        for y in range(8):
            for x in range(8):
                g[(k // 2) * 8 + y][(k % 2) * 8 + x] = px[y][x]
    return g


# ---- thresholds (CIE76 delta E; docs/dev/army-packs.md "The palette's margins") ----
MIN_ARMY = 10.0      # the skin's body colours (ramp 1..4) against every body colour of each of AW2's five armies: the closest pair
MIN_ARMY_MEAN = 16.0  # ... and the mean over the four body colours of the distance to that army's nearest colour
MIN_GREY = 9.0       # ... against the greys of units that have moved
MIN_FOG = 9.0        # ... against the colours the fog gives the terrain
MIN_DONE = 10.0      # the skin's own done unit against its live unit
MAX_CHROMA = 0.4     # the skin's body chroma as a share of Green Earth's: a stone, not a leaf green
MAX_CONTRAST = 1.75  # the HQ's value contrast (std. dev. of brightness) as a multiple of the strongest of AW2's five (it is asked to be stronger than theirs, not wilder)
MIN_DONE_OWN = 6.0   # the skin's done ramp against the other armies' done greys (a done skin unit is still the skin's)
# The terrain's colours under fog (rendered with fog on, Bean Island: grass, road, forest, mountain, sea ...): what a unit stands on in the fog of war.
FOG_TERRAIN = [(131, 156, 148), (148, 164, 148), (98, 98, 123), (106, 131, 148), (57, 123, 123), (82, 131, 106), (115, 90, 139), (74, 74, 197), (82, 57, 172)]


def lab(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(x) for x in c)
    x = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047
    y = 0.2126 * r + 0.7152 * g + 0.0722 * b
    z = (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    g_ = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    fx, fy, fz = g_(x), g_(y), g_(z)
    return (116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz))


def de(a, b):
    return math.dist(lab(a), lab(b))


def hue(c):
    import colorsys
    h, s, v = colorsys.rgb_to_hsv(*(x / 255 for x in c))
    return h * 360


def hex_rgb(s):
    s = s.lstrip("#")
    return tuple(int(s[i:i + 2], 16) for i in (0, 2, 4))


def quant(c):
    return tuple((v >> 3) * 255 // 31 for v in c)


def static(skin_path=None, say=print):
    """Returns (list of failures, list of lines of the report)."""
    fails, rep = [], []
    data = toml_art(skin_path)
    base = Rom()
    # -- the data file
    for key in ("id", "name", "short"):
        if not data.get(key):
            fails.append(f"data file: {key} missing")
    hq, em = data["hq"]["rows"], data["emblem"]["rows"]
    if len(hq) != 32 or any(len(r) != 16 for r in hq):
        fails.append("hq: needs 32 rows of 16")
    if len(em) != 16 or any(len(r) != 16 for r in em):
        fails.append("emblem: needs 16 rows of 16")
    if any(c not in ".0123456789abcdefABCDEF" for r in hq for c in r):
        fails.append("hq: only . and hex digits")
    if any(c not in ".12abc" for r in em for c in r):
        fails.append("emblem: only . 1 2 a b c")
    for unit in ("infantry", "mech"):
        for p in data[unit].get("patch", []):
            if any(c not in "._0123456789abcdefABCDEF" for r in p["rows"] for c in r):
                fails.append(f"{unit}: patch characters")
            if p.get("frames", [0, 1, 2]) and (p.get("x", 0) + max(len(r) for r in p["rows"]) > 16 or p.get("y", 0) + len(p["rows"]) > 16):
                fails.append(f"{unit}: a patch leaves the 16x16 picture")
    # -- the palette against AW2's armies
    ramp = [hex_rgb(x) for x in data["colours"]["ramp"]]
    ramp_q = [quant(c) for c in ramp]
    lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    if not all(lum(ramp[i]) > lum(ramp[i + 1]) for i in range(5)):
        fails.append("palette: the ramp must go from light to dark")
    body = ramp_q[1:5]
    rows = {c: base.pal(UNIT_PAL + 32 * (c - 1)) for c in range(1, 6)}
    greys = {c: base.pal(UNIT_PAL + 0xA0 + 32 * (c - 1)) for c in range(1, 6)}
    rep.append(f"palette margins (delta E, body colours of the skin against ...; needs >= the threshold)")
    for c in range(1, 6):
        d = min(de(a, b) for a in body for b in rows[c][2:8])
        mean = sum(min(de(a, b) for b in rows[c][2:8]) for a in body) / 4
        rep.append(f"  {NAMES[c]:13s} closest {d:5.1f} (>= {MIN_ARMY}), mean {mean:5.1f} (>= {MIN_ARMY_MEAN})")
        if d < MIN_ARMY:
            fails.append(f"palette: too close to {NAMES[c]} ({d:.1f} < {MIN_ARMY})")
        if mean < MIN_ARMY_MEAN:
            fails.append(f"palette: too like {NAMES[c]} on average ({mean:.1f} < {MIN_ARMY_MEAN})")
    dg = min(de(a, b) for a in body for c in range(1, 6) for b in greys[c][2:8])
    rep.append(f"  done greys    {dg:5.1f}  (>= {MIN_GREY})")
    if dg < MIN_GREY:
        fails.append(f"palette: too close to the greys of a unit that has moved ({dg:.1f} < {MIN_GREY})")
    df = min(de(a, b) for a in body for b in FOG_TERRAIN)
    rep.append(f"  fog terrain   {df:5.1f}  (>= {MIN_FOG})")
    if df < MIN_FOG:
        fails.append(f"palette: too close to the terrain in fog ({df:.1f} < {MIN_FOG})")
    chroma = lambda c: math.hypot(*lab(c)[1:])
    cs = sum(chroma(c) for c in body) / 4
    cg = sum(chroma(c) for c in rows[3][3:7]) / 4
    rep.append(f"  chroma {cs:4.1f} = {cs / cg:.2f} of Green Earth's {cg:.1f}  (<= {MAX_CHROMA})")
    if cs / cg > MAX_CHROMA:
        fails.append(f"palette: too saturated, near Green Earth's leaf green ({cs / cg:.2f} > {MAX_CHROMA})")
    # -- the HQ's depth against AW2's five HQs (measured from the ROM)
    aw = [hq_metrics(aw2_hq_grid(base, c), base.pal(BLD_PAL + 32 * (c - 1))) for c in range(1, 6)]
    mine = hq_metrics([[0 if ch == "." else int(ch, 16) for ch in r] for r in hq], Rom(3).pal(BLD_PAL + 64))
    rng = lambda k: (min(a[k] for a in aw), max(a[k] for a in aw))
    rep.append("HQ picture (ours | AW2's five: min..max):")
    for k, lo_t, hi_t in (("fill", 0.93, 1.1), ("shades", 1.0, 1.4), ("dominant", 0.45, 1.2), ("contrast", 0.9, MAX_CONTRAST)):
        lo, hi = rng(k)
        ok = lo * lo_t <= mine[k] <= hi * hi_t
        rep.append(f"  {k:9s} {mine[k]:7.2f} | {lo:7.2f} .. {hi:7.2f}  (allowed {lo * lo_t:.2f} .. {hi * hi_t:.2f})")
        if not ok:
            fails.append(f"hq: {k} {mine[k]:.2f} is outside AW2's HQs ({lo:.2f}..{hi:.2f}, allowed {lo * lo_t:.2f}..{hi * hi_t:.2f})")
    rep.append(f"  first row {mine['top']} (AW2: {rng('top')[0]}..{rng('top')[1]}, needs <= {rng('top')[1]}); left {mine['left']:.0f} vs right {mine['right']:.0f} (the left is the lit side)")
    if mine["top"] > rng("top")[1]:
        fails.append(f"hq: the picture starts at row {mine['top']}: AW2's HQs fill the frame from row {rng('top')[1]} at the latest")
    if mine["left"] < mine["right"]:
        fails.append("hq: the right side is lighter than the left (light comes from the top left)")
    # -- every colour the skin can sit on: the dump works, the rows differ from the colour's own, the done row differs from the live row
    for host in range(1, 6):
        sk = Rom(host)
        live = sk.pal(UNIT_PAL + 32 * (host - 1))
        done = sk.pal(UNIT_PAL + 0xA0 + 32 * (host - 1))
        d = min(de(quant(a), quant(b)) for a in live[2:8] for b in done[2:8])
        dd = min(de(quant(a), quant(b)) for a in live[3:6] for b in done[3:6])
        if dd < MIN_DONE:
            fails.append(f"palette: a done unit is too near a live one on colour {host} ({dd:.1f} < {MIN_DONE})")
        others = [c for c in range(1, 6) if c != host]
        do = min(de(quant(a), quant(b)) for a in done[3:6] for c in others for b in greys[c][3:6])
        rep.append(f"  on colour {host} ({NAMES[host]:13s}): its done ramp vs the other armies' done greys {do:5.1f} (>= {MIN_DONE_OWN}), vs its live ramp {dd:5.1f} (>= {MIN_DONE})")
        if do < MIN_DONE_OWN:
            fails.append(f"palette: the done ramp on colour {host} is the same grey as another army's ({do:.1f} < {MIN_DONE_OWN})")
        own = base.pal(UNIT_PAL + 32 * (host - 1))
        left = [i for i in list(range(2, 8)) + [11, 12, 13] if live[i] == own[i]]
        if left:
            fails.append(f"colour {host}: unit palette entries {left} are still the army's own")
        # unit coverage: every unit's idle frames use palette roles; the roles of the army's colours must have changed
        for t in range(1, 25):
            used = set()
            slot = base.u16(SLOT_TABLE + 2 * (25 * (host - 1) + t))
            for f in range(3):
                pic = base.raw(UNIT_SHEET + FRAME * f + 128 * slot, 128)
                for b in pic:
                    used.add(b & 15)
                    used.add(b >> 4)
            if t in (1, 2):
                continue   # Infantry and Mech have the skin's own pictures
            roles = [i for i in used if 2 <= i <= 7 or 11 <= i <= 13]
            if not roles:
                fails.append(f"unit {t}: its map pictures use no army colour at all")
            elif any(live[i] == own[i] for i in roles):
                fails.append(f"unit {t} on colour {host}: left in the army's colours")
    # -- the battle figures and portraits: the engine's patched frames are the data file's rules applied (Python twin), and most frames have a helmet
    if "battle" in data or "portrait" in data:
        from . import figures
        skf = Rom(3)
        pf = figures.check_parity(base, skf, data)
        fails += pf
        sh = figures.sheets_of(base, skf)
        have = sum(1 for (u, w), (o, m) in sh.items() for a, b in zip(o, m) if a != b)
        total = sum(len(o) for (u, w), (o, m) in sh.items())
        rep.append(f"  battle figures and portraits: the helmet is on {have} of {total} frames (the falling ones have no helmet block); the engine's frames equal the data file's rules: {'yes' if not pf else 'NO'}")
        if have < total // 2:
            fails.append(f"battle figures: the helmet is on only {have} of {total} frames")
    rep.append(f"  every unit (1..24) on every colour: recoloured map pictures; the done grey differs from the live colours by >= {MIN_DONE}")
    return fails, rep


# ---------------------------------------------------------------------------------------------------------------- live
def _colours(path):
    im = Image.open(path).convert("RGB")
    from collections import Counter
    return Counter(im.getdata())


def live(names=None, out=None, ds=False, tolerance=6, say=print, keep=False):
    """Runs the catalogue's scenarios three times (the army's own colour, another colour, the skin on the first colour) and fails on any
    screen where the skin's shot still shows colours that only the first run's army had. Returns (failures, report lines)."""
    from . import scenarios
    from .. import cfg, harness
    from pathlib import Path
    out = Path(out or cfg.work("armyskin", "live"))
    out.mkdir(parents=True, exist_ok=True)
    fails, rep = [], []
    names = names or [n for n, sc in scenarios.SCENARIOS.items() if not sc["five"] and not sc["sheet_only"] and (ds or not sc["ds"])]
    forbidden_all = {}
    for n in names:
        sc = scenarios.SCENARIOS[n]
        if sc.get("compare"):
            # a scenario whose second match must look as if the first never had the skin: run it with and without, compare the named shot
            shots = {}
            for tag, ids in (("skin", sc["ids"]), ("plain", [1] + sc["ids"][1:])):
                d = out / f"{n}_{tag}"
                d.mkdir(parents=True, exist_ok=True)
                (d / "script.txt").write_text(scenarios.script(n, ids))
                rc, log = harness.run_script(d / "script.txt", d, ds=ds)
                if rc:
                    fails.append(f"{n}/{tag}: the harness script failed ({log})")
                shots[tag] = d / f"{sc['compare']}_s0.bmp"
            try:
                a, b = Image.open(shots["skin"]).convert("RGB"), Image.open(shots["plain"]).convert("RGB")
                diff = sum(1 for p, q in zip(a.getdata(), b.getdata()) if p != q)
            except FileNotFoundError:
                fails.append(f"{n}: shot {sc['compare']} was not taken")
                continue
            rep.append(f"  {n}/{sc['compare']}: {diff} pixels differ from a match that never had the skin before")
            if diff > 150:
                fails.append(f"{n}: the second match differs from a plain one in {diff} pixels (the skin was not taken off)")
            continue
        if sc.get("look"):
            # the real app's tilted picture (not a harness frame): the same three runs, compared the same way
            from . import look as lk
            ids = sc["ids"]
            pics = {}
            for v, vids in (("base", [1] + ids[1:]), ("other", [3] + ids[1:]), ("skin", ids)):
                rc, log = lk.checkpoint(f"live_{n}_{v}", n, vids, True)
                if rc:
                    fails.append(f"{n}/{v}: the harness script failed ({log})")
                    continue
                pics[v] = out / f"{n}_{v}.png"
                lk.look(f"live_{n}_{v}", pics[v], tilt=True)
            if len(pics) < 3:
                continue
            skin, base, other = (_colours(pics[k]) for k in ("skin", "base", "other"))
            forb = {c: k for c, k in base.items() if c not in other and k >= tolerance}
            left = {c: skin[c] for c in forb if skin.get(c, 0) >= tolerance}
            rep.append(f"  {n}/tilt: {len(forb)} colours only the base army had, {sum(left.values())} pixels of them left in the skin's tilted picture" + (f"  {sorted(left.items(), key=lambda x: -x[1])[:3]}" if left else ""))
            if left:
                fails.append(f"{n}/tilt: base army colours left: {sorted(left.items(), key=lambda x: -x[1])[:4]}")
            continue
        runs = {}
        if sc["five"]:
            variants = {"skin": sc["ids"]}
        else:
            ids = sc["ids"]
            k = ids.index(6) if 6 in ids else 0   # (the skin's seat; the base and other runs put Orange Star / Green Earth there)
            variants = {"base": ids[:k] + [1] + ids[k + 1:], "other": ids[:k] + [3] + ids[k + 1:], "skin": ids}
        for v, ids in variants.items():
            d = out / f"{n}_{v}"
            d.mkdir(parents=True, exist_ok=True)
            (d / "script.txt").write_text(scenarios.script(n, ids))
            rc, log = harness.run_script(d / "script.txt", d, ds=ds)
            if rc:
                fails.append(f"{n}/{v}: the harness script failed ({log})")
            runs[v] = d
        seats = {}
        for line in scenarios.script(n).splitlines():
            w = line.split()
            if len(w) == 3 and w[0] == "shot":
                seats[w[1]] = int(w[2])
        for shot in sc["shots"]:
            f = f"{shot}_s{seats.get(shot, 0)}.bmp"
            try:
                skin = _colours(runs["skin"] / f)
            except FileNotFoundError:
                fails.append(f"{n}: shot {shot} was not taken")
                continue
            if not sc["five"]:
                base, other = _colours(runs["base"] / f), _colours(runs["other"] / f)
                forb = {c: k for c, k in base.items() if c not in other and k >= tolerance}
                forbidden_all.update(forb)
            else:
                forb = {c: k for c, k in forbidden_all.items()}
            left = {c: skin[c] for c in forb if skin.get(c, 0) >= tolerance}
            need = sc.get("crest", {}).get(shot)
            if need:
                # the skin's own art must be there: the plume's red (the battle figures' and the portraits' helmets are drawn by the skin file)
                reds = sum(k for c, k in skin.items() if c[0] > 150 and c[1] < 100 and c[2] < 100 and c[0] - c[1] > 80)
                rep.append(f"  {n}/{shot}: {reds} pixels of the skin's crest red (needs >= {need})")
                if reds < need:
                    fails.append(f"{n}/{shot}: only {reds} pixels of the skin's crest red (>= {need}): the helmet is missing")
            gold_need = sc.get("gold", {}).get(shot)
            if gold_need:
                # the skin's gold (the domed HQ's windows and finial) must be in the picture
                from PIL import Image as _Img2
                gold = sum(1 for r, g, b in _Img2.open(runs["skin"] / f).convert("RGB").getdata() if abs(r - 232) < 12 and abs(g - 194) < 12 and abs(b - 90) < 16)
                rep.append(f"  {n}/{shot}: {gold} pixels of the skin's gold (needs >= {gold_need})")
                if gold < gold_need:
                    fails.append(f"{n}/{shot}: only {gold} pixels of the skin's gold (>= {gold_need}): the box's HQ is not the skin's")
            for box, need_px in ([] if ds else sc.get("crest_boxes", {}).get(shot, [])):   # (AW2's own CO page; with the pack the page is Dual Strike's, its pictures from the pack)
                # a region (the unit chart's Infantry and Mech cells) must hold the skin's plume
                from PIL import Image as _Img
                px = _Img.open(runs["skin"] / f).convert("RGB").crop(box).getdata()
                got = sum(1 for r, g, b in px if r > 150 and g < 100 and b < 100 and r - g > 80)
                rep.append(f"  {n}/{shot}: {got} pixels of the skin's crest red in {box} (needs >= {need_px})")
                if got < need_px:
                    fails.append(f"{n}/{shot}: only {got} pixels of the skin's crest red in {box} (>= {need_px}): that cell's picture is wrong")
            if sc.get("keep_other"):
                # the other army's own pictures keep its colours: what the runs without the skin both show is still there with it (a third at least)
                shared = {c: min(base[c], other[c]) for c in base if c in other and min(base[c], other[c]) >= tolerance}
                gone = {c: k for c, k in shared.items() if skin.get(c, 0) < k // 3}
                rep.append(f"  {n}/{shot}: {len(shared)} colours the other army shows with or without the skin, {len(gone)} lost")
                if gone:
                    fails.append(f"{n}/{shot}: the other army lost colours it had without the skin: {sorted(gone.items(), key=lambda x: -x[1])[:4]}")
            if sc.get("no_plume"):
                # the plume (palette entries 14 and 15 of the battle scene's unit palette, the same for every army) is only the skin's side's: the other side's soldiers must not show it
                # (as many pixels of those two colours as the same battle without the skin has, none more: the HUD may use them)
                mine, theirs = _plume(runs["skin"] / f), _plume(runs["base"] / f)
                rep.append(f"  {n}/{shot}: {mine} pixels of AW2's plume colours (the same battle without the skin: {theirs})")
                if mine > theirs + 2:
                    fails.append(f"{n}/{shot}: {mine} pixels of AW2's plume colours, {theirs} without the skin: the other army's soldiers wear the skin's helmet")
            rep.append(f"  {n}/{shot}: {len(forb)} colours only the base army had, {sum(left.values())} pixels of them left in the skin's shot" + (f"  {sorted(left.items(), key=lambda x: -x[1])[:3]}" if left else ""))
            if left:
                fails.append(f"{n}/{shot}: base army colours left: {sorted(left.items(), key=lambda x: -x[1])[:4]}")
    if not keep:
        import shutil
        shutil.rmtree(out, ignore_errors=True)
    return fails, rep


PLUME = [(139, 238, 172), (0, 106, 139)]   # AW2's unit palette entries 14 and 15 (unused by the soldiers; the skin's helmet puts its plume there)


def _plume(path):
    """Pixels of a frame that are (within a few levels) one of the plume colours the helmet patch draws with."""
    from PIL import Image
    im = Image.open(path).convert("RGB")
    return sum(1 for px in im.getdata() if any(max(abs(px[i] - c[i]) for i in range(3)) <= 8 for c in PLUME))


# ---------------------------------------------------------------------------------------------------------------- originality
MAX_IDENTICAL = 0.78   # the share of our foreground pixels that sit where the reference has a pixel of the same colour class (offset and mirroring allowed)


def _class(px):
    """A pixel's colour class (not its colour): clear, red, yellow, or one of five brightness steps."""
    r, g, b, a = px
    if a == 0:
        return None
    if r > 140 and r > g * 1.6:
        return "R"
    if r > 200 and g > 150 and b < 160 and r - b > 60:
        return "Y"
    l = 0.299 * r + 0.587 * g + 0.114 * b
    return "K" if l < 50 else "D" if l < 105 else "M" if l < 160 else "L" if l < 210 else "W"


def _classes(im):
    im = im.convert("RGBA")
    return {(x, y): c for y in range(im.height) for x in range(im.width) if (c := _class(im.getpixel((x, y)))) is not None}


def identical(ours, theirs, reach=2):
    """The best share of `ours`' foreground pixels that are, at some offset (up to `reach`) and mirroring, a pixel of the same colour class in `theirs`: (share, dx, dy, mirrored)."""
    a, b0, w = _classes(ours), _classes(theirs), theirs.width
    best = (0.0, 0, 0, False)
    for flip in (False, True):
        b = {((w - 1 - x) if flip else x, y): c for (x, y), c in b0.items()}
        for dy in range(-reach, reach + 1):
            for dx in range(-reach, reach + 1):
                same = sum(1 for (x, y), c in a.items() if b.get((x - dx, y - dy)) == c)
                if same / len(a) > best[0]:
                    best = (same / len(a), dx, dy, flip)
    return best


def originality(awbw_dir, host=3, skin_path=None):
    """Local only: needs the reference pictures (never committed). Our infantry, mech, HQ and logo are drawn to read like AWBW's Jade Sun (its style: a sage steel soldier with a red crest,
    a tall pale-green domed HQ, a pale sun logo), every pixel by hand. What separates drawing from copying is how many pixels are the same: a hand redraw matches the shapes and
    rarely the pixels, a copy matches nearly all. The check counts the share of our foreground pixels that sit where the reference has a pixel of the same colour class (the brightness
    step, red or yellow; the colour itself is ignored), at the best offset (up to 2 pixels, mirrored too), and fails above 0.78."""
    from pathlib import Path
    from . import foot, emblem, hq as hq_img
    d = Path(awbw_dir)
    fails, rep = [], ["originality against the reference pictures (share of our foreground pixels in the same place and the same colour class; needs <= %.2f):" % MAX_IDENTICAL]
    sk = Rom(host, skin_path)
    pal = sk.pal(UNIT_PAL + 32 * (host - 1))
    items = [(f"jsinfantry", f"Infantry f{f}", foot(sk, host, 1, f, pal, 1, skin=True)) for f in range(3)]
    items += [(f"jsmech", f"Mech f{f}", foot(sk, host, 2, f, pal, 1, skin=True)) for f in range(3)]
    items += [("jadesunhq", "HQ", hq_img(sk, host, sk.pal(BLD_PAL + 32 * (host - 1)), 1, skin=True)), ("jslogo", "Logo", emblem(sk, host, 1))]
    for name, who, ours in items:
        ref = d / f"{name}.gif"
        if not ref.exists():
            rep.append(f"  {who}: no reference file ({ref})")
            continue
        r, dx, dy, flip = identical(ours, Image.open(ref))
        rep.append(f"  {who:9s} {r:.2f}  (offset {dx},{dy}{', mirrored' if flip else ''})")
        if r > MAX_IDENTICAL:
            fails.append(f"originality: {r:.2f} of the {who}'s pixels are the reference's ({MAX_IDENTICAL} at most)")
    return fails, rep
