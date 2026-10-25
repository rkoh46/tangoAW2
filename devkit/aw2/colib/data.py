"""`aw2dev co check`: the CO data files (tango-gamesupport-aw2/cos/*.toml and tags.toml) against AW2's design space (docs/dev/co-kit.md)."""
import itertools, tomllib
from pathlib import Path
from .. import cfg, util
from . import roms

COS_DIR = cfg.REPO / "tango-gamesupport-aw2" / "cos"

UNITS = {"all", "foot", "vehicle", "direct", "indirect", "naval", "air", "artillery", "rockets", "artillery rockets"}
KEYS = {"units", "attack", "defence", "move", "range", "cost"}
MAX_QUOTE = 26   # characters a line of a power quote may have (AW2's quote box is about 24 to 28 characters)


def aw2_stars():
    """{name: (cop, scop)} of AW2's own 19 COs, read from the ROM's CO table (rows of 0x104 bytes, +0x0C and +0x10)."""
    import struct
    rom = roms._aw2()
    return {n: struct.unpack_from("<II", rom, 0x5D3DD0 + 0x104 * i + 0x0C) for i, n in enumerate(roms.AW2_NAMES)}


def load_all():
    cos = {}
    for f in sorted(COS_DIR.glob("*.toml")):
        if f.stem == "tags":
            continue
        cos[f.stem] = tomllib.loads(f.read_text())
    tags = tomllib.loads((COS_DIR / "tags.toml").read_text()) if (COS_DIR / "tags.toml").exists() else {}
    return cos, tags


def tier(compat):
    return 3 if compat >= 125 else 2 if compat >= 115 else 1


def problems(cos, tags, ref=None):
    out = []
    p = lambda co, m: out.append(f"{co}: {m}")
    for co, d in cos.items():
        for k in ("id", "name", "army", "role", "stars", "d2d", "cop", "scop", "bio", "theme"):
            if k not in d:
                p(co, f"missing {k}")
        if d.get("id") != co:
            p(co, "id differs from the file name")
        st = d.get("stars", {})
        if not (1 <= st.get("cop", 0) <= 5 and st.get("cop", 0) < st.get("scop", 0) <= 10):
            p(co, f"stars {st}: a CO Power costs 1..5 and the Super Power (in all) more, at most 10")
        for sect in ("d2d", "cop", "scop"):
            s = d.get(sect, {})
            for k in ("name", "text"):
                if k not in s:
                    p(co, f"{sect}.{k} missing")
            for m in s.get("mods", []):
                if set(m) - KEYS:
                    p(co, f"{sect}: unknown modifier key {set(m) - KEYS}")
                if m.get("units") not in UNITS:
                    p(co, f"{sect}: units {m.get('units')!r} not one of {sorted(UNITS)}")
                for k in ("attack", "defence"):
                    if abs(m.get(k, 0)) > 50:
                        p(co, f"{sect}: {k} {m[k]} is beyond AW2's range (+-50)")
        for sect in ("cop", "scop"):
            for line in d.get(sect, {}).get("quote", []):
                if len(line) > MAX_QUOTE:
                    p(co, f"{sect} quote line {line!r} is longer than {MAX_QUOTE}")
        if len(d.get("name", "")) > 7:
            p(co, "name longer than 7 letters (the 48 x 16 name graphic)")
        port = d.get("portrait", {})
        if d.get("hq", "default") not in ("default", "emerald_sun", "black_hole"):
            p(co, f"hq {d.get('hq')!r}: an army skin's id or \"default\"")
        if port.get("placeholder"):
            continue
        if port.get("base"):          # a recolour of another CO's art: the palette entries are index 1..15 = "RRGGBB"
            rc = port.get("recolour", {})
            if port["base"] not in ("andy",):
                p(co, f"portrait.base {port['base']!r}: only Dual Strike's Andy is wired")
            for k, v in rc.items():
                if not (k.isdigit() and 1 <= int(k) <= 15) or len(str(v)) != 6 or any(ch not in "0123456789abcdefABCDEF" for ch in str(v)):
                    p(co, f"portrait.recolour {k} = {v!r}: want an index 1..15 and RRGGBB")
            if not rc:
                p(co, "portrait.base without a portrait.recolour is just the donor's picture")
            continue
        src = d.get("portrait", {}).get("source")
        if not src:
            p(co, "portrait.source missing (the picture the project owner supplied)")
        elif not (cfg.REPO / src).exists():
            p(co, f"portrait.source {src} does not exist")
        elif not (cfg.REPO / src).with_suffix(".toml").exists():
            p(co, f"{src}: no framing file ({Path(src).with_suffix('.toml').name})")
    names = list(cos)
    seen = {}
    for pr in tags.get("pair", []):
        key = frozenset((pr["a"], pr["b"]))
        seen[key] = pr
        for k in ("compat", "stars", "name", "why"):
            if k not in pr:
                p("tags", f"{pr['a']}+{pr['b']}: {k} missing")
        if not 65 <= pr.get("compat", 0) <= 130:
            p("tags", f"{pr['a']}+{pr['b']}: compat {pr.get('compat')} outside 65..130")
        if pr.get("stars") != tier(pr.get("compat", 0)):
            p("tags", f"{pr['a']}+{pr['b']}: stars {pr.get('stars')} do not match compat {pr.get('compat')} (Sturm's table: 110 is 1 star, 115..120 is 2, 125 is 3)")
        if len(pr.get("name", "")) > 20:
            p("tags", f"{pr['name']}: a Tag Power name is at most 20 letters")
        for s in (pr["a"], pr["b"]):
            if ":" not in s and s not in cos:
                p("tags", f"unknown CO {s}")
    army = [c for c, d in cos.items() if d.get("army") == "emerald_sun"]
    for a, b in itertools.combinations(army, 2):
        if frozenset((a, b)) not in seen:
            p("tags", f"no Tag Power for {a} + {b}")
    return out


# Name plates. The name is drawn in AW2's text font on most screens (Teams cards, results, the CO page header, tag screens) and as a 48 x 16 name graphic on the Teams cards and CO select.
# Every plate already takes AW2's widest names (23 px: Kanbei, Adder, Hawke) and, with the Dual Strike pack, Von Bolt (28 px); Clone Andy (38 px) only on the plates that were widened for him.
# So a name up to WIDEST_PLATE px fits every plate that takes Von Bolt; wider needs the short form (`short = ...` in the CO file). This is a measurement in the font, not a look at the game:
# the plates are checked at 1x in the game when the CO is built in (phase 2: `aw2dev co check --live`).
WIDEST_PLATE = 28


def text_width(s):
    from ..gfxlib import font
    f = font.load()
    return sum(f[c][0] for c in s if c in f)


def name_plates(cos):
    out = []
    for co, d in cos.items():
        full = d["name"]
        w = text_width(full)
        short = d.get("short")
        out.append((co, full, w, short, text_width(short) if short else None, w <= WIDEST_PLATE))
    return out


def check(a):
    cos, tags = load_all()
    names = a.co or list(cos)
    bad = problems({k: v for k, v in cos.items() if k in names}, tags)
    ref = aw2_stars()
    print("AW2's own power stars (CO Power, Super Power in all) for reference:", ", ".join(f"{n} {c}/{s}" for n, (c, s) in ref.items()))
    for co in names:
        d = cos[co]
        s = d["stars"]
        near = sorted(ref, key=lambda n: abs(ref[n][0] - s["cop"]) + abs(ref[n][1] - s["scop"]))[:3]
        print(f"{co:9} {s['cop']}/{s['scop']}  AW2 COs with nearly these stars: {', '.join(f'{n} {ref[n][0]}/{ref[n][1]}' for n in near)}")
    # the design space: Kanbei is AW2's highest flat bonus (day to day +20 / +20, Super Power +60 / +50 averaged over an army, see `co balance`)
    for co in names:
        for mode, lvl, cap in ((0, "d2d", 40), (1, "cop", 90), (2, "scop", 120)):
            fp, df, mv, rg = summary(file_levels(cos[co])[mode], mode)
            flag = " <- above Kanbei's" if fp + df > cap else ""
            print(f"  {co:9} {lvl:5} firepower {fp:+6.1f}  defence {df:+6.1f}  move {mv:+.2f}  range {rg:+.2f}{flag}")
            bad += [f"{co}: {lvl} averages {fp + df:.0f} points of firepower + defence, above Kanbei's {cap}"] if fp + df > cap else []
    for co, full, w, short, sw, fits in name_plates({k: v for k, v in cos.items() if k in names}):
        print(f"  name {full}: {w} px in AW2's font (widest plate 28, Von Bolt); " + ("fits every plate" if fits else f"TOO WIDE: use the short form {short} ({sw} px)" if short else "TOO WIDE and no short form"))
        if not fits:
            bad += [f"{co}: name is {w} px, the plates take {WIDEST_PLATE}" + ("" if short else " and the file has no `short`")]
    for pr in tags.get("pair", []):
        print(f"tag {pr['a']}+{pr['b']}: {pr['name']} {pr['compat']}% {pr['stars']} stars")
    for b in bad:
        print("PROBLEM", b)
    print("co check:", "FAIL" if bad else "ok")
    return 1 if bad else 0


# --- balance: the same arithmetic for Dual Strike's own COs and for a data file --------------------------------------------------------------------------------
# A typical army's make-up by Dual Strike unit class (0 foot, 1 direct vehicle, 2 indirect vehicle, 3 plane, 4 copter, 5 navy): the weights of the averages below.
SHARE = {0: 0.30, 1: 0.27, 2: 0.12, 3: 0.09, 4: 0.05, 5: 0.17}
CLASS_OF = {"all": [0, 1, 2, 3, 4, 5], "foot": [0], "vehicle": [1], "direct": [0, 1, 3, 4], "indirect": [2], "naval": [5], "air": [3, 4], "artillery": [2], "rockets": [2], "artillery rockets": [2]}
POWER_FIREPOWER = 10      # every power adds 10% firepower in Dual Strike (co_roster.rs POWER_FIREPOWER)


def ds_levels(co):
    """Dual Strike CO -> {level: {class: [fp, def, move, range]}} (classes 0..5; the direct / indirect combat slots are folded in: direct (not foot) onto classes 1,3,4, indirect onto 2)."""
    out = {}
    for mode in range(3):
        st = roms.ds_class_stats(co, mode)
        lv = {c: list(st[c]) for c in range(6)}
        for c in (1, 3, 4):
            lv[c] = [a + b for a, b in zip(lv[c], st[7])]
        lv[2] = [a + b for a, b in zip(lv[2], st[8])]
        out[mode] = lv
    return out


def file_levels(d):
    """A data file -> the same shape; a power's mods are on top of the day-to-day ones."""
    out = {}
    for mode, sect in enumerate(("d2d", "cop", "scop")):
        lv = {c: [0, 0, 0, 0] for c in range(6)}
        for s in ("d2d",) + ((sect,) if mode else ()):
            for m in d.get(s, {}).get("mods", []):
                for c in CLASS_OF.get(m["units"], []):
                    for i, k in enumerate(("attack", "defence", "move", "range")):
                        lv[c][i] += m.get(k, 0)
        out[mode] = lv
    return out


def summary(lv, mode):
    """(average firepower %, average defence %, average move, average range) over a typical army, the power's +10% firepower included."""
    fp = sum(SHARE[c] * lv[c][0] for c in SHARE) + (POWER_FIREPOWER if mode else 0)
    df = sum(SHARE[c] * lv[c][1] for c in SHARE)
    mv = sum(SHARE[c] * lv[c][2] for c in SHARE)
    rg = sum(SHARE[c] * lv[c][3] for c in SHARE)
    return fp, df, mv, rg


def balance(a):
    cos, _ = load_all()
    refs = [(n, roms.DS_NAMES_REV[n]) for n in (a.vs or ["Kanbei", "Hawke", "Max", "Grit", "Eagle", "Sami", "Jess", "Colin", "Olaf", "Drake"])]
    st = aw2_stars()
    print(f"{'CO':10} {'stars':6} {'level':6} {'firepower':>10} {'defence':>8} {'move':>6} {'range':>6}   (averages over a typical army: foot 30%, direct vehicles 27%, indirect 12%, planes 9%, copters 5%, navy 17%; powers include DS's +10% firepower)")
    rows = []
    for n, i in refs:
        for mode, lvl in enumerate(("d2d", "cop", "scop")):
            rows.append((n, st.get(n, ("", ""))[:2], lvl, summary(ds_levels(i)[mode], mode), mode))
    for co in (a.co or list(cos)):
        if cos[co].get("army") == "emerald_sun" or a.co:
            s = cos[co]["stars"]
            for mode, lvl in enumerate(("d2d", "cop", "scop")):
                rows.append((cos[co]["name"] + "*", (s["cop"], s["scop"]), lvl, summary(file_levels(cos[co])[mode], mode), mode))
    for n, s, lvl, (fp, df, mv, rg), mode in rows:
        stars = f"{s[0]}/{s[1]}" if s[0] != "" else "-"
        print(f"{n:10} {stars:6} {lvl:6} {fp:+10.1f} {df:+8.1f} {mv:+6.2f} {rg:+6.2f}")
    return 0
