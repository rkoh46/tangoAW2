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
            variants = {"base": [1] + ids[1:], "other": [3] + ids[1:], "skin": ids}
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
            rep.append(f"  {n}/{shot}: {len(forb)} colours only the base army had, {sum(left.values())} pixels of them left in the skin's shot" + (f"  {sorted(left.items(), key=lambda x: -x[1])[:3]}" if left else ""))
            if left:
                fails.append(f"{n}/{shot}: base army colours left: {sorted(left.items(), key=lambda x: -x[1])[:4]}")
    if not keep:
        import shutil
        shutil.rmtree(out, ignore_errors=True)
    return fails, rep


# ---------------------------------------------------------------------------------------------------------------- originality
MAX_LOOK_ALIKE = 0.60   # the share of foreground pixels (colour ignored) our helmet's additions or our logo's sun may share with the reference picture's


def _fg(im, rows=None):
    """A unit picture's silhouette (alpha), optionally only its first `rows` rows."""
    im = im.convert("RGBA")
    return {(x, y) for y in range(im.height if rows is None else rows) for x in range(im.width) if im.getpixel((x, y))[3] > 0}


def _shift(m, dx, dy, flip=False, w=16):
    return {((w - 1 - x if flip else x) + dx, y + dy) for x, y in m}


def _jaccard(a, b):
    u = len(a | b)
    return len(a & b) / u if u else 0.0


def _best(a, b, reach=3, w=16):
    """The best Jaccard ratio of `a` with `b` over every offset up to `reach` and both mirrorings: (ratio, dx, dy, mirrored)."""
    return max((_jaccard(a, _shift(b, dx, dy, f, w)), dx, dy, f) for dx in range(-reach, reach + 1) for dy in range(-reach, reach + 1) for f in (False, True))


def _logo_fg(im, margin):
    """The sun of a logo: the pixels inside the frame that are not the commonest colour there (the pale ground), so frames and square backgrounds do not count."""
    from collections import Counter
    im = im.convert("RGBA")
    inner = [(x, y, im.getpixel((x, y))) for y in range(margin, im.height - margin - 1) for x in range(margin, im.width - margin - 1) if im.getpixel((x, y))[3] > 0]
    common = Counter(p[:3] for _, _, p in inner).most_common(1)[0][0]
    return {(x - margin, y - margin) for x, y, p in inner if p[:3] != common}


def originality(awbw_dir, host=3, skin_path=None):
    """Local only: needs the reference pictures (never committed). How much of our helmets and logo is the reference's, by pixel masks, colour ignored, at the best
    offset (mirrored too):
    - helmet: both pictures are AW2's soldier with a helmet, so what is compared is what each changed in the head's rows 0..8 against AW2's own soldier
      (the added and removed pixels), and the whole silhouette must be no closer to the reference than AW2's own soldier is;
    - logo: the sun inside the frame (the frame is drawn differently anyway)."""
    from pathlib import Path
    from . import foot, emblem
    d = Path(awbw_dir)
    fails, rep = [], ["originality against the reference pictures (share of the foreground pixels two pictures have in common at the best offset, colour ignored; needs <= %.2f):" % MAX_LOOK_ALIKE]
    sk, base = Rom(host, skin_path), Rom()
    pal = sk.pal(UNIT_PAL + 32 * (host - 1))
    bpal = base.pal(UNIT_PAL + 32 * (host - 1))
    for name, unit in (("jsinfantry", 1), ("jsmech", 2)):
        ref = d / f"{name}.gif"
        who = ("Infantry", "Mech")[unit - 1]
        if not ref.exists():
            rep.append(f"  {name}: no reference file ({ref})")
            continue
        ours, aw2 = _fg(foot(sk, host, unit, 0, pal, 1, skin=True), 9), _fg(foot(base, host, unit, 0, bpal, 1), 9)
        theirs = _fg(Image.open(ref), 9)
        # (the reference's soldier is AW2's, mirrored: align AW2's to it, then what it changed)
        _, dx, dy, f = _best(theirs, aw2, 2)
        theirs_changed = theirs ^ _shift(aw2, dx, dy, f)
        ours_changed = ours ^ aw2
        r, ox, oy, of = _best(ours_changed, theirs_changed)
        sil, _, _, _ = _best(ours, theirs)
        own = _best(aw2, theirs)[0]
        rep.append(f"  helmet {who:8s} what we changed against what it changed: {r:.2f} (offset {ox},{oy}{', mirrored' if of else ''}); whole silhouette {sil:.2f}, AW2's own soldier {own:.2f}")
        if r > MAX_LOOK_ALIKE:
            fails.append(f"originality: the {who}'s helmet changes {r:.2f} of the same pixels as the reference ({MAX_LOOK_ALIKE} at most)")
        if sil > own + 0.02:
            fails.append(f"originality: the {who}'s silhouette ({sil:.2f}) is closer to the reference than AW2's own soldier is ({own:.2f})")
    ref = d / "jslogo.gif"
    if ref.exists():
        a, b = _logo_fg(emblem(sk, host, 1), 2), _logo_fg(Image.open(ref), 1)
        r, ox, oy, of = _best(a, b, 3, 10)
        rep.append(f"  logo (the sun inside the frame) {r:.2f} (offset {ox},{oy}{', mirrored' if of else ''})")
        if r > MAX_LOOK_ALIKE:
            fails.append(f"originality: the logo's sun shares {r:.2f} of its pixels with the reference ({MAX_LOOK_ALIKE} at most)")
    else:
        rep.append(f"  logo: no reference file ({ref})")
    return fails, rep
