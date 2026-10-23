"""Checks of an army skin (docs/dev/army-packs.md): the data file, the palette's distance from AW2's armies, the coverage of every unit, and (live) that no
screen in the catalogue is left in the colours of the army the skin sits on."""
import math, tomllib
from pathlib import Path
from PIL import Image
from . import (BLD_PAL, NAMES, UNIT_PAL, UNIT_SHEET, FRAME, SLOT_TABLE, Rom, dump, toml_art)

# ---- thresholds (CIE76 delta E; docs/dev/army-packs.md "The palette's margins") ----
MIN_ARMY = 22.0      # the skin's body colours (ramp 1..4) against every body colour of each of AW2's five armies
MIN_GREY = 8.0       # ... against the greys of units that have moved
MIN_FOG = 8.0       # ... against the colours the fog gives the terrain
MIN_DONE = 10.0      # the skin's own done unit against its live unit
MIN_HUE = 20.0       # degrees between the skin's main hue and Green Earth's
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
            if p.get("x", 0) + max(len(r) for r in p["rows"]) > 16 or p.get("y", 0) + len(p["rows"]) > 16:
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
        rep.append(f"  {NAMES[c]:13s} {d:5.1f}  (>= {MIN_ARMY})")
        if d < MIN_ARMY:
            fails.append(f"palette: too close to {NAMES[c]} ({d:.1f} < {MIN_ARMY})")
    dg = min(de(a, b) for a in body for c in range(1, 6) for b in greys[c][2:8])
    rep.append(f"  done greys    {dg:5.1f}  (>= {MIN_GREY})")
    if dg < MIN_GREY:
        fails.append(f"palette: too close to the greys of a unit that has moved ({dg:.1f} < {MIN_GREY})")
    df = min(de(a, b) for a in body for b in FOG_TERRAIN)
    rep.append(f"  fog terrain   {df:5.1f}  (>= {MIN_FOG})")
    if df < MIN_FOG:
        fails.append(f"palette: too close to the terrain in fog ({df:.1f} < {MIN_FOG})")
    dh = abs(hue(ramp_q[2]) - hue(rows[3][4]))
    dh = min(dh, 360 - dh)
    rep.append(f"  hue vs Green Earth {dh:5.1f} degrees  (>= {MIN_HUE})")
    if dh < MIN_HUE:
        fails.append(f"palette: hue too near Green Earth's ({dh:.0f} < {MIN_HUE} degrees)")
    # -- every colour the skin can sit on: the dump works, the rows differ from the colour's own, the done row differs from the live row
    for host in range(1, 6):
        sk = Rom(host)
        live = sk.pal(UNIT_PAL + 32 * (host - 1))
        done = sk.pal(UNIT_PAL + 0xA0 + 32 * (host - 1))
        d = min(de(quant(a), quant(b)) for a in live[2:8] for b in done[2:8])
        dd = min(de(quant(a), quant(b)) for a in live[3:6] for b in done[3:6])
        if dd < MIN_DONE:
            fails.append(f"palette: a done unit is too near a live one on colour {host} ({dd:.1f} < {MIN_DONE})")
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
    names = names or [n for n, sc in scenarios.SCENARIOS.items() if not sc["five"] and (ds or not sc["ds"])]
    forbidden_all = {}
    for n in names:
        sc = scenarios.SCENARIOS[n]
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
