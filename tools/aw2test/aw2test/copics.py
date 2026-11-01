"""Real-game pictures of the custom COs' powers (`aw2dev co sheet powers`): the harness console (the same ROMs, the Dual Strike pack and map graphics, `TANGOAW2_DS_GRAPHICS=1`) plays
each CO and a frame of the game is saved at each moment worth looking at: the Teams screen's card, the CO page, the HUD with the meter charging and full, the CO Power's and the Super
Power's activation (quote box, cut-in, effect), each Tag Power with its partner, and a battle that shows what the power does. Every picture is a frame the game drew (240 x 160),
written as `<out>/<co>/<key>.png` with its caption in `<out>/<co>/captions.json`; `devkit/aw2/colib/powersheet.py` lays them out.
"""

import json
import os

from . import cospec
from . import rom as romlib
from .coverify import ENV, POWER, funds, set_funds, tag_battle, econ_map, install_tag_spec
from .harness import Ctx

CAMERA = (10, 10)


class Cap:
    """A CO's pictures: `shot` takes the console's frame, `note` writes a caption for a picture."""

    def __init__(self, name, out, ctx):
        self.name, self.dir, self.ctx = name, os.path.join(out, name), ctx
        os.makedirs(self.dir, exist_ok=True)
        self.captions = {}

    def shot(self, g, key, caption=None):
        from PIL import Image
        path = g.e.shot(os.path.join(self.dir, key))
        Image.open(path).convert("RGB").save(os.path.join(self.dir, key + ".png"))
        os.remove(path)
        if caption:
            self.captions[key] = caption
        return os.path.join(self.dir, key + ".png")

    def save(self):
        with open(os.path.join(self.dir, "captions.json"), "w") as f:
            json.dump(self.captions, f, indent=1)


def new_ctx(name, out):
    os.environ["TANGOAW2_DS_GRAPHICS"] = "1"
    os.makedirs(out, exist_ok=True)
    return Ctx(name, ds=True, out=out)


def showcase(ctx, units=(), props=0):
    """A small field of roads, woods and a mountain round (10, 10) with a few properties of army 1."""
    m = ctx.map()
    for x in range(5, 17):
        m.terrain(x, 11, "road")
    for c in ((9, 9), (12, 9), (7, 12), (15, 12)):
        m.terrain(*c, "wood")
    m.terrain(13, 12, "mountain")
    m.terrain(8, 8, "city", 1).terrain(15, 9, "city", 2)
    for k in range(props):
        m.terrain(6 + 2 * k, 13, "city", 1)
    for u in units:
        m.unit(*u)
    return m


def look(g, x=CAMERA[0], y=CAMERA[1]):
    g.goto(x, y)
    g.e.wait(40)


def frames(ctx, cap, g, prefix, until, step=10, limit=260, extra=None):
    """Run the game from now until `until(g)` holds and the map is free, taking a frame every `step` frames. Returns [(path, info)]."""
    e = g.e
    out = []
    for i in range(limit):
        e.wait(step)
        path = cap.shot(g, f"{prefix}_{i:03d}")
        info = {"mode": g.player(1)["co_mode"], "co": g.player(1)["co"]}
        if extra:
            info.update(extra(g))
        out.append((path, info))
        if i > 4 and until(g) and g.idle():
            break
    return out


def metrics(path):
    """Per-frame numbers for picking key frames: map-green share, dark share (a figure's coat), white share, dialogue-box share (top or bottom 48 rows), red share."""
    from PIL import Image
    import numpy as np
    im = np.array(Image.open(path).convert("RGB")).astype(int)
    r, g, b = im[:, :, 0], im[:, :, 1], im[:, :, 2]
    green = ((g > 200) & (r > 180) & (r < 240) & (b < 140)).mean()
    dark = ((r + g + b) < 210).mean()
    white = ((r > 235) & (g > 235) & (b > 225)).mean()
    pale = (r > 232) & (g > 222) & (b > 218)
    band = max(float(pale[:48].mean()), float(pale[-48:].mean()))
    red = ((r > 200) & (g < 90) & (b < 70)).mean()
    return {"green": float(green), "dark": float(dark), "white": float(white), "band": band, "red": float(red)}


def red_share(path):
    return metrics(path)["red"]


def band_share(path):
    return metrics(path)["band"]


def text_amount(path):
    """Dark pixels inside the dialogue box (top or bottom 48 rows, whichever is the pale band): how much of the quote is typed."""
    from PIL import Image
    import numpy as np
    im = np.array(Image.open(path).convert("RGB")).astype(int)
    pale = (im[:, :, 0] > 232) & (im[:, :, 1] > 222) & (im[:, :, 2] > 218)
    dark = im.sum(2) < 260
    rows = slice(0, 48) if pale[:48].mean() >= pale[-48:].mean() else slice(-48, None)
    return int(dark[rows][:, 40:].sum())


def is_cut(m):
    return m["green"] < 0.12 and m["dark"] > 0.03 and m["white"] < 0.5


def pick_activation(seq):
    """Key frames of an activation: the quote box (typed out), the Super Power banner, the cut-in coming in, the cut-in whole, going out, the effect on the map, the end.
    A cut-in frame is one the map does not show through (little map green) with the figure's dark coat on it. -> {role: index}."""
    import numpy as np
    from PIL import Image
    ms = [metrics(p) for p, _ in seq]
    n = len(seq)
    cut = [i for i, m in enumerate(ms) if m["green"] < 0.12 and m["dark"] > 0.03 and m["white"] < 0.5]
    pick = {}
    if cut:
        first, last = cut[0], cut[-1]
        before = [i for i in range(first) if ms[i]["band"] > 0.3]
        pick["quote"] = max(before, key=lambda i: text_amount(seq[i][0])) if before else max(0, first - 1)
        banners = [i for i in range(first) if 0.2 < ms[i]["white"] < 0.9 and ms[i]["band"] < 0.5]
        if banners:
            pick["banner"] = banners[len(banners) // 2]
        pick["cut-in begins"] = first
        pick["cut-in"] = cut[int(len(cut) * 0.6)]
        pick["cut-in ends"] = last
        post = [i for i in range(last + 1, n) if ms[i]["green"] > 0.35]
        if post:
            ref = np.array(Image.open(seq[-1][0]).convert("RGB")).astype(int)
            diffs = [(np.abs(np.array(Image.open(seq[i][0]).convert("RGB")).astype(int) - ref).mean(), i) for i in post]
            pick["effect"] = max(diffs)[1]
    pick["after"] = n - 1
    return pick


def activation(ctx, cap, g, which, key, label):
    """Fill the meter, play the power from the map menu and keep the key frames: `<key>_quote`, `_cutin`, `_effect`, `_after` (captioned)."""
    look(g)
    g.charge_power(1, which)
    g.open_map_menu()
    g.choose("Power" if which == "power" else "Super", g.MAP_MENU)
    mode = 2 if which == "super" else 1
    seq = frames(ctx, cap, g, f"tmp_{key}", lambda gg: gg.player(1)["co_mode"] == mode)
    pick = pick_activation(seq)
    keep = {}
    names = {"quote": "quote box", "banner": "Super Power banner", "cut-in begins": "cut-in begins", "cut-in": "cut-in", "cut-in ends": "cut-in ends", "effect": "screen effect", "after": "after"}
    for role, i in pick.items():
        keep[i] = role
    for i, (p, info) in enumerate(seq):
        if i in keep:
            new = os.path.join(cap.dir, f"{key}_{keep[i].replace(' ', '_').replace('-', '')}.png")
            os.replace(p, new)
            cap.captions[os.path.basename(new)[:-4]] = f"{label}: {names[keep[i]]}"
        elif os.path.exists(p) and not os.environ.get("COPICS_KEEP"):
            os.remove(p)
    return seq


def teams_and_page(ctx, cap, co_id, name, partner=None):
    m = showcase(ctx, [(1, "tank", 10, 10), (2, "tank", 11, 10)])
    g = ctx.boot_teams(m, env=ENV)
    g.set_teams([co_id, "andy"], {1})
    g.e.wait(80)
    cap.shot(g, "select", f"CO select: {name}'s card on the Teams screen")
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    g.e.wait(110)
    cap.shot(g, "page1", f"CO page: {name}'s description")
    g.e.press("DOWN", 6)
    g.e.wait(60)
    g.e.press("DOWN", 6)
    g.e.wait(60)
    cap.shot(g, "page3", f"CO page: {name}'s CO Power and Super Power")
    g.e.close()


def hud(ctx, cap, g, co_id, name):
    """The HUD with the meter charging (about 40% of the Super Power) and full."""
    look(g)
    p = g.player(1)
    cop, scop = g.co_stars(co_id)
    cost = 9000 * scop
    g.e.w32(p["addr"] + 0x20, int(cost * 0.4))
    g.e.wait(30)
    cap.shot(g, "hud_charging", f"HUD: the power bar charging ({cop} + {scop - cop} stars, 40% of the Super Power's {scop})")
    g.e.w32(p["addr"] + 0x20, 9000 * cop)
    g.e.wait(30)
    cap.shot(g, "hud_cop_ready", f"HUD: the bar at the CO Power's {cop} stars (CO Power ready)")
    g.e.w32(p["addr"] + 0x20, cost)
    g.e.wait(30)
    cap.shot(g, "hud_full", f"HUD: the bar full, all {scop} stars (Super Power ready)")
    g.e.w32(p["addr"] + 0x20, 0)
    g.e.wait(10)


def start(ctx, m, co_id, partner=None, **kw):
    if partner is None:
        return ctx.start(m, [co_id, "andy"], env=ENV, **kw)
    return tag_battle(ctx, [co_id, "andy"], [partner, None], units=(), props=False)


def hp_digits(g, cells):
    return {c: (g.unit_at(*c) or {"hp": 0})["hp"] for c in cells}


# --- the scenarios -------------------------------------------------------------------------------------------------------------------

def hurt(ctx, g, army=1, hp=45):
    from tests.test_crumb import set_unit
    for u in g.units(army):
        if (u["x"], u["y"]) not in ((0, 1), (1, 1)) and u["x"] > 1:
            set_unit(g, u["x"], u["y"], hp=hp)


def units_row(owner=1):
    return [(1, "infantry", 9, 10), (1, "tank", 10, 10), (1, "mech", 10, 12), (1, "artillery", 9, 12), (2, "tank", 14, 10), (2, "infantry", 14, 12)]


def power_pictures(ctx, cap, spec, which, key, label, props=0):
    """The activation of the CO Power or Super Power with a few hurt units of the CO's army on the field: `<key>_before`, then the activation's key frames."""
    m = showcase(ctx, units_row(), props)
    g = ctx.start(m, [spec.id, "andy"], env=ENV)
    hurt(ctx, g, 1, 45)
    look(g)
    cap.shot(g, f"{key}_before", f"{label}: before (Infantry, Tank, Mech and Artillery of the army hurt to 5 HP)")
    f0 = funds(g)
    seq = activation(ctx, cap, g, which, key, label)
    look(g)
    mode = 2 if which == "super" else 1
    after = {u["type"]: u["hp"] for u in g.units(1) if u["x"] > 1}
    note = f"{label}: after, units now at HP {sorted(after.values())}" + (f", funds {f0} -> {funds(g)}" if funds(g) != f0 else "")
    cap.shot(g, f"{key}_after_units", note)
    g.e.close()
    return seq


def tag_pictures(ctx, cap, act, par):
    """The Tag Power of `act` (active) with `par`: the map menu's Tag, the quote, the tag screen, the first half's cut-in; Change; the second half's cut-in."""
    from tests.test_tag import EXTRAS, SCREEN_FRAME, fill
    install_tag_spec()
    a_id, b_id = cospec.co_id(act), cospec.co_id(par)
    a_name, b_name = act.split(":")[-1].capitalize(), par.split(":")[-1].capitalize()
    pair = next((p for p in cospec.tags() if {p["a"], p["b"]} == {act, par}), None) or {"name": "Dual Strike", "compat": 100, "stars": 0}
    key = f"tag_{b_name.lower()}"
    label = f"Tag Power {pair['name']} ({a_name} + {b_name}, {pair['compat']}%, {pair['stars']} star{'s' if pair['stars'] != 1 else ''})"
    units = [(1, "infantry", 9, 10), (1, "tank", 10, 10), (1, "mech", 10, 12), (2, "tank", 14, 10), (2, "infantry", 14, 12)]
    g = tag_battle(ctx, [a_id, "andy"], [b_id, None], units=units)
    look(g)
    fill(g, 1)
    cap.shot(g, f"{key}_menu_before", f"{label}: both meters full")
    names = g.open_map_menu()["names"]
    cap.shot(g, f"{key}_menu", f"{label}: the map menu offers Tag ({', '.join(names)})")
    g.choose("Tag", g.MAP_MENU)
    seq = frames(ctx, cap, g, f"tmp_{key}", lambda gg: gg.player(1)["co_mode"] == 2 and gg.e.u8(EXTRAS) == 0, step=10, limit=320,
                 extra=lambda gg: {"tag": gg.e.u8(EXTRAS), "tf": gg.e.u16(SCREEN_FRAME)})
    tagged = [i for i, (_, inf) in enumerate(seq) if inf["tag"] == 1]
    reds = [i for i, (p, inf) in enumerate(seq) if is_cut(metrics(p)) and not inf.get("tag")]
    bands = [i for i, (p, _) in enumerate(seq) if band_share(p) > 0.3]
    keep = {}
    early = [i for i in bands if i < (tagged[0] if tagged else 999)]
    if early:
        keep[max(early, key=lambda i: text_amount(seq[i][0]))] = "quote"
    if tagged:
        keep[tagged[int(len(tagged) * 0.8)]] = "tag screen"
    after_tag = [i for i in reds if not tagged or i > tagged[-1]]
    if after_tag:
        keep[after_tag[int(len(after_tag) * 0.6)]] = "first half cut-in"
    keep[len(seq) - 1] = "first half after"
    for i, (p, info) in enumerate(seq):
        if i in keep:
            new = os.path.join(cap.dir, f"{key}_{keep[i].replace(' ', '_').replace('-', '')}.png")
            os.replace(p, new)
            cap.captions[os.path.basename(new)[:-4]] = f"{label}: {keep[i]}"
        elif os.path.exists(p) and not os.environ.get("COPICS_KEEP"):
            os.remove(p)
    # the second half
    look(g)
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    seq = frames(ctx, cap, g, f"tmp_{key}b", lambda gg: gg.player(1)["co"] == b_id and gg.player(1)["co_mode"] == 2, step=10, limit=260)
    reds = [i for i, (p, _) in enumerate(seq) if is_cut(metrics(p))]
    keep = {}
    if reds:
        keep[reds[int(len(reds) * 0.6)]] = "second half cut-in"
    keep[len(seq) - 1] = "second half after"
    for i, (p, info) in enumerate(seq):
        if i in keep:
            new = os.path.join(cap.dir, f"{key}_{keep[i].replace(' ', '_').replace('-', '')}.png")
            os.replace(p, new)
            cap.captions[os.path.basename(new)[:-4]] = f"{label}: {keep[i]}"
        elif os.path.exists(p) and not os.environ.get("COPICS_KEEP"):
            os.remove(p)
    g.e.close()


def effect_tabitha(ctx, cap):
    """Firestorm: a field of Tanks, the diamond round the richest cluster loses 8 HP (never the last), her own are untouched."""
    from . import coverify as cv
    g = cv.firestorm_game(ctx)
    cells = sorted(cv.diamond(cv.FIRE_CENTRE)) + [cv.FIRE_OWN[2]]
    look(g, *cv.FIRE_CENTRE)
    before = hp_digits(g, cells)
    cap.shot(g, "effect_firestorm_before", "Firestorm: before the strike: a Tank in each cell of the diamond round (20, 10), two of her own among them")
    ctx.power(g, 1, "super")
    g.e.wait(40)
    look(g, *cv.FIRE_CENTRE)
    after = hp_digits(g, cells)
    cap.shot(g, "effect_firestorm", f"Firestorm: the diamond lost 8 HP ({', '.join(f'{c}: {before[c]} -> {after[c]}' for c in ((20, 10), (21, 10), (19, 10), (20, 11)))}); her own Tank at {cv.FIRE_OWN[0]}: {before[cv.FIRE_OWN[0]]} -> {after[cv.FIRE_OWN[0]]}")
    g.e.close()


def effect_lili(ctx, cap):
    """Enigma: the weather each of the three draws brings, a frame of the field after the power."""
    from . import coverify as cv
    for name, seed in cv.SEEDS.items():
        g = cv.enigma_game(ctx)
        look(g, 10, 10)
        word, w = cv.use_enigma(ctx, g, seed)
        g.e.wait(80)
        look(g, 10, 10)
        cap.shot(g, f"effect_enigma_{name}", f"Enigma: the draw (the game's random word {word}) brought {w}; her units ignore it and move 1 more for two days")
        g.e.close()


def effect_cloneandy(ctx, cap):
    """Before / after: the same Tank-on-Tank fight by Andy, by Clone Andy day to day (+2%) and in his Hyper Upgrade (+30% firepower over the power's +10%, +2% under it)."""
    out = {}
    for key, co, power, who in (("effect_tank_andy_before", "andy", None, "Andy (before)"), ("effect_tank_clone", 81, None, "Clone Andy, day to day"),
                                ("effect_tank_clone_repair", 81, "power", "Clone Andy, Hyper Repair"), ("effect_tank_clone_upgrade", 81, "super", "Clone Andy, Hyper Upgrade")):
        m = showcase(ctx, [(1, "tank", 10, 10), (2, "tank", 11, 10), (1, "infantry", 9, 10), (2, "infantry", 14, 12)])
        g = ctx.start(m, [co, "andy"], env=ENV)
        if power:
            ctx.power(g, 1, power)
        look(g)
        r = ctx.attack(g, (10, 10), (10, 10), (11, 10))
        a0, d0 = r["before"]
        a1, d1 = r["after"]
        base = r["first"].base
        counter = r["counter"].base if r["counter"] else 0
        out[key] = (base, counter)
        look(g)
        cap.shot(g, key, f"{who}: Tank hits Andy's Tank, base damage {base}% ({d0['hp']} -> {d1['hp']} HP); the counter's base damage {counter}% ({a0['hp']} -> {a1['hp']} HP)")
        g.e.close()
    return out


def effect_heal(ctx, cap, spec, which, key, label):
    m = showcase(ctx, [(1, "tank", 10, 10), (1, "infantry", 9, 10), (1, "mech", 10, 12), (2, "tank", 14, 10)])
    g = ctx.start(m, [spec.id, "andy"], env=ENV)
    ctx.set_hp(g, 10, 10, 25)
    ctx.set_hp(g, 9, 10, 45)
    ctx.set_hp(g, 10, 12, 65)
    cells = [(10, 10), (9, 10), (10, 12)]
    before = hp_digits(g, cells)
    look(g)
    cap.shot(g, f"effect_{key}_before", f"{label}: before (HP {list(before.values())})")
    ctx.power(g, 1, which)
    look(g)
    after = hp_digits(g, cells)
    cap.shot(g, f"effect_{key}", f"{label}: HP {list(before.values())} -> {list(after.values())}")
    g.e.close()


NAMES = {"andy": "Andy", "tabitha": "Tabitha", "lili": "Lili", "caulder": "Caulder", "crumb": "Crumb", "cloneandy": "Clone Andy"}


def capture(name, out, parts=("page", "hud", "cop", "scop", "effect", "tag")):
    """All the pictures of one CO into `<out>/<name>/` (see the module doc)."""
    ctx = new_ctx(f"copics_{name}", os.path.join(out, "_work", name))
    spec = cospec.get(name)
    cap = Cap(name, out, ctx)
    disp = NAMES[name]
    if "page" in parts:
        teams_and_page(ctx, cap, spec.id, disp)
    if "hud" in parts:
        g = ctx.start(showcase(ctx, units_row()), [spec.id, "andy"], env=ENV)
        hud(ctx, cap, g, spec.id, disp)
        g.e.close()
    props = 0
    if "cop" in parts and spec.has_cop:
        power_pictures(ctx, cap, spec, "power", "cop", f"{disp}: CO Power {spec.power_names[0]}", props)
    if "scop" in parts and spec.has_scop:
        power_pictures(ctx, cap, spec, "super", "scop", f"{disp}: Super Power {spec.power_names[1]}", props)
    if "effect" in parts:
        if name == "tabitha":
            effect_tabitha(ctx, cap)
        elif name == "lili":
            effect_lili(ctx, cap)
        elif name == "caulder":
            effect_heal(ctx, cap, spec, "super", "cataclysm", "Cataclysm heals 5 HP")
        elif name == "crumb":
            effect_heal(ctx, cap, spec, "power", "ration", "Ration Run heals 1 HP")
            effect_heal(ctx, cap, spec, "super", "blessing", "Gerald's Blessing heals 2 HP")
        elif name == "cloneandy":
            effect_heal(ctx, cap, spec, "power", "repair", "Hyper Repair heals 2 HP")
            effect_heal(ctx, cap, spec, "super", "upgrade", "Hyper Upgrade heals 4 HP")
            effect_cloneandy(ctx, cap)
    if "tag" in parts and name == "andy":
        tag_pictures(ctx, cap, "andy", "aw2:sturm")
    elif "tag" in parts:
        for p in cospec.tags():
            for act, par in ((p["a"], p["b"]), (p["b"], p["a"])):
                if act == name:
                    tag_pictures(ctx, cap, act, par)
    cap.save()
    ctx.finish()
    return cap


# --- the HQ of the Silver Nova COs (`aw2dev co sheet hq`) --------------------------------------------------------------------------------------

def hq_cell(g, army):
    from . import ram
    w = g.e.u16(0x0201E450) or 30
    h = g.e.u16(0x0201E452) or 20
    for y in range(h):
        for x in range(w):
            c = g.terrain_class(x, y)
            if c & 0x1F == 8 and c >> 5 == army:
                return x, y
    return None


def hq_frame(g, out, key, army):
    cell = hq_cell(g, army)
    if cell is None:
        return None
    g.goto(*cell)
    g.e.wait(60)
    g.e.shot(os.path.join(out, key))
    from PIL import Image
    Image.open(os.path.join(out, key + ".bmp")).convert("RGB").save(os.path.join(out, key + ".png"))
    os.remove(os.path.join(out, key + ".bmp"))
    return key


def capture_hq(out):
    """Frames of the HQ on the map: each Silver Nova CO's in Versus (its own army, beside Andy's plain one) and in the missions M1, M7, M8, M11, M14, M16 (every army led by a CO with an Silver Nova HQ
    and the player's). Returns {key: caption}."""
    from . import escampaign as es
    os.makedirs(out, exist_ok=True)
    ctx = new_ctx("copics_hq", os.path.join(out, "_work"))
    caps = {}
    for name in ("tabitha", "lili", "caulder", "andy"):
        spec = cospec.get(name)
        m = ctx.map(hq=((1, 5, 5), (2, 24, 12)), spare=False)
        m.unit(1, "infantry", 3, 3).unit(2, "infantry", 20, 12)
        g = ctx.start(m, [spec.id, "andy"], env=ENV)
        k = hq_frame(g, out, f"versus_{name}", 1)
        caps[k] = f"Versus: {NAMES[name]}'s HQ" + (" (the game's own, for comparison)" if name == "andy" else "")
        g.e.close()
    for n in (1, 7, 8, 11, 14, 16):
        e, g, d = es.enter(ctx, n)
        g.e.wait(30)
        for a in range(1, 6):
            try:
                p = g.player(a)
            except Exception:
                continue
            if not p["raw"][0x1B]:
                continue
            style = cospec.hq_style_of_id(p["co"])
            if a == 1 or style == "emerald_sun":
                k = hq_frame(g, out, f"m{n}_army{a}", a)
                if k:
                    nm = next((c for c, i in cospec.IDS.items() if i == p["co"]), f"CO {p['co']}")
                    caps[k] = f"M{n}: army {a}'s HQ (CO {NAMES.get(nm, nm)})"
        e.close()
    ctx.finish()
    with open(os.path.join(out, "hq_captions.json"), "w") as f:
        json.dump(caps, f, indent=1)
    return caps
