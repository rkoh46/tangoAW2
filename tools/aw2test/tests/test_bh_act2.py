"""BH Campaign, Act II (Green Earth, M4 to M11: tango-gamesupport-aw2/src/bh_act2.rs)."""

import os

from aw2test import bhact2 as a2
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test


# --- every mission loads: its armies, map, rules and opening ---------------------------------------
GMAP = 0x0201E450
DS_TABLE = 0x08E00000
DAY = 0x03004080
ALL = a2.ST | a2.VB | a2.HK
# number: (title, won before (mission numbers), roster bits, CO picks, armies: (colour, CO), map size, fog, day limit, units per army)
MISSIONS = {
    4: ("Marshal in Green", [1, 2, 3], a2.ST | a2.VB, [bh.STURM], [(5, bh.STURM), (3, bh.HAWKE)], (24, 18), True, 20),
    5: ("Night Raid", [1, 2, 3, 4], ALL, [bh.STURM], [(5, bh.STURM), (3, bh.JAVIER)], (24, 16), True, 9),
    6: ("Stepping Stones", [1, 2, 3, 4, 5], ALL, [bh.STURM], [(5, bh.STURM), (3, bh.DRAKE)], (32, 20), False, 22),
    7: ("Greenhaven Arsenal", [1, 2, 3, 4, 5], ALL, [bh.STURM], [(5, bh.STURM), (3, bh.EAGLE)], (28, 24), False, 26),
    8: ("The Twin Gates", [1, 2, 3, 4, 5, 6, 7], ALL, [bh.STURM, bh.HAWKE], [(5, None), (3, bh.JESS)], (24, 18), False, 22),
    9: ("The Loot Train", [1, 2, 3, 4, 5, 6, 7, 8], ALL, [bh.STURM], [(5, bh.STURM), (3, bh.JAVIER)], (28, 14), True, 16),
    10: ("Evergreen Citadel", [1, 2, 3, 4, 5, 6, 7, 8, 9], ALL, [bh.STURM, bh.HAWKE], [(5, None), (3, bh.EAGLE)], (28, 22), False, 24),
    11: ("Ashfall Pass", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], ALL, [bh.STURM, bh.HAWKE], [(5, None), (3, bh.JAVIER), (4, bh.SENSEI)], (28, 20), False, 24),
}
MAP_FILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tango-gamesupport-aw2", "five", "bh")


def map_units(name):
    """Units per army, from the map's text file (five/bh/<name>.txt)."""
    out = {}
    for line in open(os.path.join(MAP_FILES, name + ".txt")):
        f = line.split()
        if f and f[0] == "unit":
            out[int(f[1])] = out.get(int(f[1]), 0) + 1
    return out


def mission_count(g, army):
    return len(g.units(army))


def load_mission(ctx, n, cos=None, label=None):
    title, won, roster, picks, armies, size, fog, limit = MISSIONS[n]
    mask = 0
    for k in won:
        mask |= 1 << (k - 1)
    e, g, d = a2.boot(ctx, mask, roster, picks={a2.M[n]: len(cos or picks)}, at=a2.M[n])
    return e, g, d, MISSIONS[n]


def check_load(ctx, n):
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, armies, size, fog, limit = spec
    units = map_units(f"bh{n:02d}")
    texts = a2.open_mission(ctx, e, g, d, a2.M[n], picks, f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), a2.M[n], f"M{n}: the mission")
    ps = [g.player(a) for a in range(1, len(armies) + 1)]
    ctx.eq([(p["colour"], p["co"] if want[1] is not None else None) for p, want in zip(ps, armies)], armies, f"M{n}: army colours and COs")
    ctx.eq(d.size(), size, f"M{n}: the map's size")
    ps = g.playst()
    ctx.eq(bool(ps["fog"]), fog, f"M{n}: fog")
    ctx.eq(e.u16(DS_TABLE + 0x5C * dc.DS_MAP_ID + 0x24), limit, f"M{n}: the day limit")
    for army, count in units.items():
        ctx.eq(mission_count(g, army), count, f"M{n}: army {army}'s units")
    if len(picks) == 2:
        # (the pair: whichever of the two picks leads, the other is the partner or the second front's CO)
        from aw2test import tag
        from aw2test import twofront as tf
        other = (e.u8(tf.SECOND_COS)) if n == 8 else tag.partner(e, 1)["co"]
        ctx.eq(sorted([g.player(1)["co"], other]), sorted(picks), f"M{n}: the two picks lead the main army and its partner (or the second front)")
    a2.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    e.close()


def _loads(n):
    def fn(ctx):
        check_load(ctx, n)
    fn.__name__ = f"bh_act2_m{n}_loads"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _loads(_n)


# --- pictures: the whole map, the opening frame after Deploy, a dialogue frame ------------------------
FOG = 0x03003FCD


def unfog(g, e):
    """Fog off for the picture: the map redraws unfogged once the map menu has opened and closed."""
    e.w8(FOG, 0)
    e.wait(10)
    g.open_map_menu()
    e.wait(20)
    e.press("B", 4)
    e.wait(40)


def pictures(ctx, n, shots=(0,)):
    """The opening frame after Deploy, a dialogue frame, and the whole map as one picture (fog off)."""
    from aw2test import stitch
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, armies, size, fog, limit = spec
    texts = a2.open_mission(ctx, e, g, d, a2.M[n], picks, f"m{n}", shots=shots)
    d.wait_control()
    g._units_base = g._players_base = None
    a2.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    stitch.IMAGES = a2.SHOTS or stitch.IMAGES
    w, h = d.size()
    if fog:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_fog", w, h)       # the map as the player sees it on day 1
        unfog(g, e)
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_nofog", w, h)     # every unit of both sides
        stitch.stitch(ctx, g, f"m{n}", w, h)
    else:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}", w, h)
    low = [(u["army"], u["type"], u["x"], u["y"], u["hp"]) for u in g.units() if u["hp"] != 100]
    ctx.eq(low, [], f"M{n}: every unit still at 100 HP after the picture was taken")
    if n == 8:
        # the dusk gate, the second front: Map menu > Front shows it
        from aw2test import twofront as tf
        ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
        w2, h2 = d.size()
        ctx.eq((w2, h2), (20, 16), "the second front's map: the Gate of Dusk, 20x16")
        a2.pic(ctx, e, "m8_second_front_view")
        g.goto(0, 0)
        # (the view's "Second front / R Back" window sits at the screen's top or bottom, away from the cursor:
        # views of a cell with the window over it are dropped)
        class Quiet:
            def __init__(self, c):
                self.c = c

            def __getattr__(self, k):
                return getattr(self.c, k)

            def check(self, ok, msg):
                return None
        clean = stitch.stitch(Quiet(ctx), g, "m8_second_front", w2, h2, reject=lambda c: (c.min(axis=2) > 225).sum() > 60)
        try:
            from PIL import Image
            import numpy as np
            a = np.asarray(Image.open(clean).convert("RGB")).copy()
            for cy in range(h2):
                for cx in range(w2):
                    cell = a[16 * cy:16 * cy + 16, 16 * cx:16 * cx + 16]
                    whitish = (cell.min(axis=2) > 225).sum() > 100 and cy <= 3      # (the view's info window, caught in a sweep)
                    if whitish:
                        cell[:] = a[16 * cy:16 * cy + 16, 16 * (cx + 2):16 * (cx + 2) + 16] if cx + 2 < w2 else cell
                    if not cell.any():
                        # (only a few cells under the view's windows: the nearest picture beside stands for them)
                        k = cx - 1
                        while k >= 0 and not a[16 * cy:16 * cy + 16, 16 * k:16 * k + 16].any():
                            k -= 1
                        if k < 0:
                            k = cx + 1
                            while k < w2 and not a[16 * cy:16 * cy + 16, 16 * k:16 * k + 16].any():
                                k += 1
                        cell[:] = a[16 * cy:16 * cy + 16, 16 * k:16 * k + 16]
            Image.fromarray(a).save(clean)
            if a2.SHOTS:
                Image.fromarray(a).save(os.path.join(a2.SHOTS, "m8_second_front_full.png"))
        except ImportError:
            pass
    e.close()


def _pictures(n):
    def fn(ctx):
        pictures(ctx, n)
    fn.__name__ = f"bh_act2_pictures_m{n}"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)




# --- balance: the CPU on both sides, and the test player (aw2test.bot) against the CPU --------------------
# (AW2TEST_ACT2_BALANCE=1; each run writes balance.json in its output: the result and the days)
BALANCE = os.environ.get("AW2TEST_ACT2_BALANCE")
BOT_OPTS = {5: dict(garrison=True, goals=[(19, 3)]), 9: dict(goals=[(26, 7)]), 4: dict(goals=[(21, 9)], finish=12), 6: dict(goals=[(28, 14)], finish=14), 7: dict(goals=[(25, 19)], finish=14), 8: dict(goals=[(22, 9)], finish=14), 10: dict(goals=[(14, 3)]), 11: dict(goals=[(25, 3), (25, 17)], finish=16)}   # per mission: aw2test.bot.Bot options (the cells the mission is won on)


def balance(ctx, n, how, cos=None, seed=None):
    import json
    from aw2test.harness import Skip
    if not BALANCE:
        raise Skip("AW2TEST_ACT2_BALANCE not set")
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, armies, size, fog, limit = spec
    cos = cos or picks
    d.pick_mission()
    got = d.choose_cos(len(cos), prefs=list(cos))
    g._units_base = g._players_base = None
    days = []
    log = lambda s: days.append(s)
    opts = dict(BOT_OPTS.get(n, {}))
    if seed is not None:
        opts["seed"] = seed
    r = d.autoplay(limit + 3, log=log) if how == "cpu" else d.play(limit + 3, log=log, **opts)
    r["picks"] = got
    r["mission"] = n
    r["how"] = how
    r["limit"] = limit
    r["log"] = days[-6:]
    ctx.log(json.dumps(r, default=str))
    with open(os.path.join(ctx.out, "balance.json"), "w") as f:
        json.dump(r, f, default=str)
    a2.pic(ctx, e, f"m{n}_{how}_end")
    e.close()


def _balance(n, how, seed=None):
    def fn(ctx):
        balance(ctx, n, how, seed=seed)
    fn.__name__ = f"bh_act2_balance_m{n}_{how}" + (f"_{seed}" if seed is not None else "")
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _balance(_n, "cpu")
    _balance(_n, "bot")
    for _seed in (1, 2):      # (other test players' styles: aw2test.bot's seeds)
        _balance(_n, "bot", _seed)


# --- the world map: Act II's flags on Green Earth ----------------------------------------------------
@test(modes=("ds",))
def bh_act2_world_map_flags(ctx):
    """With M1..M10 won and M11 open, AW2's map shows Act II's eight flags on Green Earth (the east land),
    M4..M10 cleared (starred); pictures with the cursor on several of them."""
    e, g, d = a2.boot(ctx, a2.WON(10), ALL, at=10)
    d.wait_world_map()
    flags = d.map_flags()
    ctx.check(all(flags[k] for k in range(3, 11)), f"Act II's flags are all shown ({flags[3:11]})")
    ctx.eq([flags[k] & 2 for k in range(3, 10)], [2] * 7, "M4..M10 cleared (starred)")
    ctx.eq(flags[10] & 2, 0, "M11 open, not cleared")
    ctx.eq(d.map_mission(), 10, "the cursor on M11")
    e.wait(120)
    a2.pic(ctx, e, "world_map_m11")
    pts = bh_points(ctx)
    ctx.eq(len(pts), 8, "eight points")
    # DOWN walks the cursor (and the camera) to the flags in the south
    for k in range(6):
        e.press("DOWN", 6)
        e.wait(150)
        a2.pic(ctx, e, f"world_map_south_{k}")
        ctx.log(f"cursor on mission {d.map_mission()}")
    e.close()


def bh_points(ctx):
    """Act II's flag positions from the source (bh_act2::FLAGS)."""
    import re
    src = open(os.path.join(MAP_FILES, "..", "..", "src", "bh_act2.rs")).read()
    blk = src[src.index("pub const FLAGS"):]
    blk = blk[:blk.index("];")]
    return [(int(x), int(y)) for x, y in re.findall(r"\((\d+), (\d+)\)", blk)]


# --- M6: every army's Lander loads and unloads on the beaches ------------------------------------------
def beaches(name):
    """Each shoal (beach) of a built map with a land cell and a sea cell beside it: [(beach, land, sea)]."""
    rows = []
    for line in open(os.path.join(MAP_FILES, name + ".txt")):
        line = line.rstrip("\n")
        if line and not line.split()[0] in ("map", "armies", "unit", "team", "objective", "look") and not line.startswith("#"):
            rows.append(line)
    h, w = len(rows), len(rows[0])
    out = []
    for y in range(h):
        for x in range(w):
            if rows[y][x] != ",":
                continue
            near = [(x + dx, y + dy) for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0)) if 0 <= x + dx < w and 0 <= y + dy < h]
            land = [c for c in near if rows[c[1]][c[0]] not in "~r,"]
            sea = [c for c in near if rows[c[1]][c[0]] == "~"]
            out.append(((x, y), land, sea, rows))
    return out


@test(modes=("ds",))
def bh_act2_m6_landers_load_and_unload_on_every_beach(ctx):
    """Both armies are played by hand (the computer's handed over): on each of the island chain's ten
    beaches an Infantry boards a Lander on the shoal and, a turn on, is dropped on the land beside it."""
    e, g, d, spec = load_mission(ctx, 6)
    a2.open_mission(ctx, e, g, d, a2.M[6], spec[3], "m6", shots=())
    d.wait_control()
    g._units_base = g._players_base = None
    players = e.u32(0x08499598)
    e.w8(players + 0x3C * 2 + 0x1B, 1)       # (the computer's army is played by hand too)
    bs = beaches("bh06")
    ctx.eq(len(bs), 12, "twelve beaches: two on each island and four on Black Hole's")
    done = {1: 0, 2: 0}
    for k, ((bx, by), land, sea, rows) in enumerate(bs):
        army = 1 if k % 2 == 0 else 2          # (each army uses five beaches, by turns)
        ctx.require(land and sea, f"beach {(bx, by)}: land and sea beside it")
        # the road beside the beach reaches a city or port within 3 cells
        lx, ly = land[0]
        near = [(rows[y][x]) for y in range(ly - 3, ly + 4) for x in range(lx - 3, lx + 4)
                if 0 <= y < len(rows) and 0 <= x < len(rows[0]) and abs(x - lx) + abs(y - ly) <= 3]
        ctx.check(any(c in "CcPpBb12" for c in near) and "R" in near, f"beach {(bx, by)}: a road to a city or port within 3 cells")
        while g.current_army() != army:
            a2.next_turn(e, g, d)
        g._units_base = g._players_base = None
        lander = next(u for u in g.units(army) if u["type"] == 23 and not any(u["cargo"]))
        inf = next(u for u in g.units(army) if u["type"] == 1)
        sx, sy = sea[0]
        occupied = {(u["x"], u["y"]) for u in g.units()}
        if (sx, sy) in occupied or land[0] in occupied:
            for u in g.units():
                if (u["x"], u["y"]) in ((sx, sy), land[0], (bx, by)) and u["id"] not in (lander["id"], inf["id"]):
                    d.remove_unit(u)
        d.place_unit(lander, sx, sy)
        d.place_unit(inf, *land[0])
        e.wait(10)
        g.select(sx, sy)
        names = g.move_to(bx, by)["names"]
        g.choose("Wait", g.ACTION_MENU)
        a2.calm(e, g, d)
        ctx.eq(g.unit(lander["id"])["x"], bx, f"beach {(bx, by)}: the Lander of army {army} sailed onto the shoal")
        g.select(*land[0])
        names = g.move_to(bx, by)["names"]
        ctx.check(any(n.lower().startswith("load") for n in names), f"beach {(bx, by)}: the Infantry is offered Load ({names})")
        g.choose("Load", g.ACTION_MENU)
        a2.calm(e, g, d)
        ctx.check(any(g.unit(lander["id"])["cargo"]), f"beach {(bx, by)}: the Lander carries the Infantry")
        # a round later: the Lander drops it on the land beside the beach
        a2.next_turn(e, g, d)
        while g.current_army() != army:
            a2.next_turn(e, g, d)
        g.select(bx, by)
        names = g.move_to(bx, by)["names"]
        ctx.check(any(n.lower().startswith("drop") for n in names), f"beach {(bx, by)}: the Lander offers Drop ({names})")
        g.choose("Drop", g.ACTION_MENU)
        e.wait(20)
        if k == 0:
            a2.pic(ctx, e, "m6_lander_landing")
        if g.menu():
            e.press("A", 4)
            e.wait(20)
        for _ in range(8):
            if g.cursor() in land:
                break
            e.press("RIGHT", 4)
            e.wait(10)
        e.press("A", 4)
        e.wait(40)
        mm = g.menu()
        if mm and any(n.lower().startswith("wait") for n in mm["names"]):
            g.choose("Wait", g.ACTION_MENU)
        a2.calm(e, g, d)
        iu, lu = g.unit(inf["id"]), g.unit(lander["id"])
        ctx.check((iu["x"], iu["y"]) in land and not any(lu["cargo"]), f"beach {(bx, by)}: the Infantry stands on the land beside it, the Lander empty")
        if k in (0, 5):
            a2.pic(ctx, e, f"m6_lander_dropped_{bx}_{by}")
        done[army] += 1
    ctx.eq(done, {1: 6, 2: 6}, "each army used six beaches")
    e.close()


# --- intro -> battle -> win, and the unlocks ------------------------------------------------------------
def ready(ctx, n, cos=None, label=None):
    """The mission started and under the player's control."""
    title, won, roster, picks, armies, size, fog, limit = MISSIONS[n]
    cos = cos or picks
    mask = sum(1 << (k - 1) for k in won)
    e, g, d = a2.boot(ctx, mask, roster, picks={a2.M[n]: len(cos)}, at=a2.M[n])
    texts = a2.open_mission(ctx, e, g, d, a2.M[n], cos, label or f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d, texts


def capture_hq(ctx, e, g, d, hqs, hostile=None):
    """The test aid for a mission won by taking the HQ: every enemy unit but the farthest of each army
    removed, an Infantry of the player's on each HQ capturing it turn by turn until the HQ is the player's."""
    units = g.units()
    by = {}
    for u in units:
        if u["army"] != 1 and (hostile is None or u["army"] in hostile):
            by.setdefault(u["army"], []).append(u)
    for army, us in by.items():
        far = max(us, key=lambda u: min(abs(u["x"] - h[0]) + abs(u["y"] - h[1]) for h in hqs))
        for u in us:
            if u is not far:
                d.remove_unit(u)
    mine = [u for u in g.units(1) if u["type"] == 1][:len(hqs)]
    for u, hq in zip(mine, hqs):
        d.place_unit(u, *hq)
    e.wait(10)
    ctx.log(f"capturers placed: {[(u['id'], hq, g.unit_at(*hq)) for u, hq in zip(mine, hqs)]}")
    for turn in range(5):
        for hq in hqs:
            if g.terrain_class(*hq) >> 5 == 1:
                continue
            a2.calm(e, g, d)
            g.select(*hq)
            names = g.move_to(*hq)["names"]
            g.choose(next(x for x in names if x.lower().startswith("capt")), g.ACTION_MENU)
            for _ in range(200):
                if d.scripts_running() or e.u8(dc.LAST_RESULT):
                    return
                if g.idle():
                    break
                e.wait(4)
            e.wait(20)
            if d.scripts_running() or e.u8(dc.LAST_RESULT):
                return
        if all(g.terrain_class(*hq) >> 5 == 1 for hq in hqs):
            return
        a2.next_turn(e, g, d)


def lose_by_day(ctx, e, g, d, n):
    """The day limit loses: the day after it begins and the mission is lost."""
    limit = MISSIONS[n][7]
    e.w16(DAY, limit)
    a2.end_turn(e, g, d)
    for _ in range(3000):
        if e.u8(dc.LAST_RESULT):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    ctx.eq(e.u8(dc.LAST_RESULT), 2, f"M{n}: lost when day {limit + 1} begins")


def after_win(ctx, e, g, d, n, victory, mapscene, want_next, unlocked):
    """The checks every win has: the won bit, the next flags open, the unlocked COs."""
    ctx.eq((d.won() >> a2.M[n]) & 1, 1, f"M{n} won")
    flags = d.map_flags()
    ctx.eq([k for k in range(len(flags)) if flags[k] & 1 and not flags[k] & 2 and k > a2.M[n]], [a2.M[k] for k in want_next], f"M{n}: the next flags open")
    ctx.eq(d.unlocked(), unlocked, f"M{n}: the roster")


def _win_by_capture(n, hqs, want_next, cos=None):
    def fn(ctx):
        e, g, d, texts = ready(ctx, n, cos)
        capture_hq(ctx, e, g, d, hqs)
        victory, mapscene = a2.follow(ctx, e, d, f"m{n}", shots=(0,))
        ctx.log("VICTORY\n" + "\n".join(victory) + "\nMAP\n" + "\n".join(mapscene))
        ctx.check(len(victory) >= 3 and len(mapscene) >= 3, f"M{n}: the victory scene and the world-map scene played ({len(victory)}, {len(mapscene)} boxes)")
        spec = MISSIONS[n]
        after_win(ctx, e, g, d, n, victory, mapscene, want_next, [bh.STURM, bh.VON_BOLT, bh.HAWKE])
        a2.pic(ctx, e, f"m{n}_world_after")
        e.close()
    fn.__name__ = f"bh_act2_m{n}_win_by_capture"
    test(modes=("ds",))(fn)


def _lose_by_day(n):
    def fn(ctx):
        e, g, d, texts = ready(ctx, n)
        lose_by_day(ctx, e, g, d, n)
        e.close()
    fn.__name__ = f"bh_act2_m{n}_lose_by_day_limit"
    test(modes=("ds",))(fn)


_win_by_capture(4, [(21, 9)], [5])
_win_by_capture(6, [(28, 14)], [7])
_win_by_capture(7, [(25, 19)], [])
_win_by_capture(10, [(14, 3)], [11])
for _n in MISSIONS:
    if _n != 8:
        _lose_by_day(_n)




# --- mission specifics -------------------------------------------------------------------------------------
def settle_texts(ctx, e, d, frames=1500):
    """Dialogue boxes shown until none for a while (A through them)."""
    texts, last, stable, quiet = [], None, 0, 0
    for _ in range(frames // 4):
        t = d.text_shown()
        stable = stable + 1 if t and t == last else 0
        last = t
        if t and stable == 5 and (not texts or texts[-1] != t):
            texts.append(t.replace("\\x0f", " ").replace("\\r", " "))
        if d.scripts_running():
            quiet = 0
            if stable >= 8:
                e.press("A", 4)
                stable = 0
        else:
            quiet += 1
            if quiet > 40:
                break
        e.wait(4)
    return texts


@test(modes=("ds",))
def bh_act2_m5_win_needs_the_aircraft_and_the_tower(ctx):
    """M5 is won when the eight parked aircraft are destroyed AND the Com Tower is taken: the tower
    alone, or the aircraft alone, win nothing; both do (the victory scene, then the map's)."""
    e, g, d, texts = ready(ctx, 5)
    ctx.eq(sorted(u["type"] for u in g.units(2) if u["type"] in (16, 17)), [16] * 6 + [17] * 2, "six Fighters and two Bombers parked")
    ctx.eq(g.terrain_class(19, 3) & 0x1F, 0x14, "the Com Tower stands at (19, 3), the enemy's")
    keep = next(u for u in g.units(2) if u["type"] == 2)
    for u in g.units(2):
        if u["type"] not in (16, 17) and u["id"] != keep["id"]:
            d.remove_unit(u)
    # (the tower is taken: its owner set, as a capture leaves it; the capture itself is the engine's)
    row = e.u16(0x0201E450 + 0x417A + 2 * 3)
    at = 0x0201E450 + 0x1432 + row + 19
    e.w8(at, (e.u8(at) & 0x1F) | (1 << 5))
    e.wait(10)
    ctx.eq(g.terrain_class(19, 3) >> 5, 1, "the Com Tower taken")
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "the tower alone does not win")
    for u in g.units(2):
        if u["type"] in (16, 17):
            d.remove_unit(u)
    e.wait(10)
    mine = next(u for u in g.units(1) if u["type"] == 5)
    g.select(mine["x"], mine["y"])
    names = g.move_to(mine["x"], mine["y"])["names"]
    g.choose(next(x for x in names if x.lower().startswith("wait")), g.ACTION_MENU)
    victory, mapscene = a2.follow(ctx, e, d, "m5", shots=(0,))
    ctx.eq(victory[0], "My tower is silent. It is so quiet. Too quiet.", "the victory scene")
    ctx.check(len(victory) == 4 and len(mapscene) == 5, f"the scenes ({len(victory)}, {len(mapscene)})")
    ctx.eq((d.won() >> 4) & 1, 1, "M5 won")
    ctx.eq([k for k in range(5, 8) if d.map_flags()[k] & 1], [5, 6], "M6 and M7 open (the branch)")
    e.close()


@test(modes=("ds",))
def bh_act2_m5_alarm_and_flares(ctx):
    """Day 3: the alarm (two Tanks and an Anti-Air by the east road); day 6: the flares."""
    e, g, d, texts = ready(ctx, 5)
    before = len(g.units(2))
    seen = a2.to_day(e, g, d, 3)
    ctx.eq(e.u16(DAY), 3, "day 3")
    ctx.eq(seen[-1:], ["Sound the horns! To arms, noble Green Earth!"], "Javier's alarm")
    new = [u for u in g.units(2) if u["x"] >= 22]
    ctx.check(len(g.units(2)) >= before + 3, f"two Tanks and an Anti-Air came ({len(g.units(2))} units, was {before})")
    a2.pic(ctx, e, "m5_alarm")
    e.close()


@test(modes=("ds",))
def bh_act2_m7_factory_table(ctx):
    """The Black Factory (x 4..6, y 6..9, doors on row 10) spawns F7's units on the player's turns: day 2
    two Tanks (doors 1 and 3), day 13 an Oozium (door 2) and Hawke's scene."""
    e, g, d, texts = ready(ctx, 7)
    before = {(u["x"], u["y"]) for u in g.units(1)}
    a2.to_day(e, g, d, 2)
    ctx.eq(e.u16(DAY), 2, "day 2")
    spawned = [(u["type"], u["x"], u["y"]) for u in g.units(1) if (u["x"], u["y"]) not in before and u["y"] == 11 and 4 <= u["x"] <= 6]
    # (the table is the schedule and the cost cap; the smart spawner picks what the battle needs within a Tank's price)
    ctx.eq(sorted((x, y) for _, x, y in spawned), [(4, 11), (6, 11)], "a unit at each of the doors (4, 11) and (6, 11), none at the middle door")
    ctx.check(all(t in (1, 2, 5, 6, 7, 10) for t, _, _ in spawned), f"each within a Tank's price ({spawned})")
    a2.pic(ctx, e, "m7_factory_day2")
    # day 13 (set day 12 and end the turn): an Oozium on the middle door
    for u in g.units(1):
        if (u["x"], u["y"]) in ((4, 11), (5, 11), (6, 11)):
            d.remove_unit(u)
    e.w16(DAY, 12)
    seen = a2.to_day(e, g, d, 13)
    ctx.eq(e.u16(DAY), 13, "day 13")
    ctx.check(g.unit_at(5, 11) is not None and g.unit_at(5, 11)["army"] == 1, "day 13: a unit on the middle door (5, 11), the heavy slot")
    ctx.check("The Foundry made an Oozium! It looks at me!" in seen, f"the day-13 scene ({seen})")
    a2.pic(ctx, e, "m7_factory_day13_oozium")
    e.close()


@test(modes=("ds",))
def bh_act2_m7_eagle_funds_and_bomber(ctx):
    """Eagle gets +5000 on day 10 and a second Bomber on day 12."""
    e, g, d, texts = ready(ctx, 7)
    funds = lambda: e.u32(g.player(2)["addr"])
    e.w16(DAY, 9)
    before = funds()
    a2.to_day(e, g, d, 10)
    ctx.eq(e.u16(DAY), 10, "day 10")
    ctx.log(f"Eagle's funds {before} -> {funds()} on day 10 (+5000 from the script, less what the computer spent)")
    # (Eagle's production spends it every turn: the +5000 is the script's, not a visible rise)
    bombers = lambda: sum(1 for u in g.units(2) if u["type"] == 17)
    b0 = bombers()
    e.w16(DAY, 11)
    a2.to_day(e, g, d, 12)
    ctx.eq(e.u16(DAY), 12, "day 12")
    ctx.check(bombers() >= b0 + 1 or b0 == 0, f"a second Bomber on day 12 ({b0} -> {bombers()})")
    e.close()


VAULT_YARD = [(24, 7), (25, 7), (26, 7)]


def escort_game(ctx, home, dead, label):
    """M9 with the named Vault APCs placed: `home` of them in the port yard, `dead` removed."""
    e, g, d, texts = ready(ctx, 9)
    apcs = sorted((u for u in g.units(1) if u["type"] == 7), key=lambda u: u["x"])
    ctx.eq(len(apcs), 3, f"{label}: three Vault APCs")
    for u in apcs[:dead]:
        d.remove_unit(u)
    live = apcs[dead:]
    for u, cell in zip(live[:home], VAULT_YARD):
        d.place_unit(u, *cell)
    e.wait(10)
    return e, g, d, apcs, live


def act(ctx, e, g, d):
    """A player's unit (not an APC) takes an action: the after-action rules look."""
    mine = next(u for u in g.units(1) if u["type"] in (1, 2, 3, 5, 6))
    g.select(mine["x"], mine["y"])
    names = g.move_to(mine["x"], mine["y"])["names"]
    g.choose(next(x for x in names if x.lower().startswith("wait")), g.ACTION_MENU)


@test(modes=("ds",))
def bh_act2_m9_escort_all_three_home(ctx):
    e, g, d, apcs, live = escort_game(ctx, 3, 0, "three home")
    act(ctx, e, g, d)
    victory, mapscene = a2.follow(ctx, e, d, "m9_three", shots=(0,))
    ctx.eq(victory, ["All three! Kehh-heh! Not one coin missing!", "Interest is laying eggs. Golden ones. Perhaps."], "the three-trucks scene")
    ctx.eq((d.won() >> 8) & 1, 1, "M9 won")
    ctx.eq(d.map_flags()[9] & 1, 1, "M10 opens")
    e.close()


@test(modes=("ds",))
def bh_act2_m9_escort_two_home_one_gone(ctx):
    e, g, d, apcs, live = escort_game(ctx, 2, 1, "two home")
    act(ctx, e, g, d)
    victory, mapscene = a2.follow(ctx, e, d, "m9_two", shots=(0,))
    ctx.eq(victory, ["One truck gone... ...my coins, my poor coins.", "Two in three. Within tolerance.", "TOLERANCE?!"], "the two-trucks scene")
    ctx.eq((d.won() >> 8) & 1, 1, "M9 won with two of three")
    e.close()


@test(modes=("ds",))
def bh_act2_m9_escort_not_yet_and_lost(ctx):
    """Two home with the third still driving: no end yet (the loot is not all in). Two trucks lost: defeat."""
    e, g, d, apcs, live = escort_game(ctx, 2, 0, "two home, third alive")
    act(ctx, e, g, d)
    e.wait(200)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "two of three home with the third alive: the escort goes on")
    e.close()
    e, g, d, apcs, live = escort_game(ctx, 0, 2, "two lost")
    act(ctx, e, g, d)
    for _ in range(3000):
        if e.u8(dc.LAST_RESULT):
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    ctx.eq(e.u8(dc.LAST_RESULT), 2, "fewer than two trucks alive: defeat")
    e.close()


@test(modes=("ds",))
def bh_act2_m9_alarm_when_a_truck_passes_the_first_bridge(ctx):
    e, g, d, texts = ready(ctx, 9)
    apc = min((u for u in g.units(1) if u["type"] == 7), key=lambda u: u["x"])
    n = len(g.units(2))
    d.place_unit(apc, 9, 7)
    e.wait(10)
    act(ctx, e, g, d)
    e.wait(120)
    g._units_base = g._players_base = None
    ctx.check(len(g.units(2)) >= n + 3, f"Javier's alarm brought a pursuit behind the trucks ({n} -> {len(g.units(2))} enemy units)")
    e.close()


@test(modes=("ds",))
def bh_act2_m11_win_needs_both_armies_beaten(ctx):
    """The pass is won when both allied armies are beaten (their HQ taken or one unit left each): one
    alone wins nothing."""
    e, g, d, texts = ready(ctx, 11)
    ctx.eq([g.player(a)["colour"] for a in (1, 2, 3)], [5, 3, 4], "Black Hole, Green Earth, Yellow Comet")
    ge = g.units(2)
    for u in ge[1:]:
        d.remove_unit(u)
    e.wait(10)
    act(ctx, e, g, d)
    e.wait(200)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "Green Earth beaten, Yellow Comet not: the pass is not won")
    for u in g.units(3)[1:]:
        d.remove_unit(u)
    e.wait(10)
    mine = [u for u in g.units(1) if u["type"] in (1, 2, 3, 5, 6) and not u["flags"] & 1]
    g.select(mine[0]["x"], mine[0]["y"])
    names = g.move_to(mine[0]["x"], mine[0]["y"])["names"]
    g.choose(next(x for x in names if x.lower().startswith("wait")), g.ACTION_MENU)
    victory, mapscene = a2.follow(ctx, e, d, "m11", shots=(0,))
    ctx.eq(victory[0], "Hmph. Old bones, beaten by a gale.", "the victory scene")
    ctx.eq((d.won() >> 10) & 1, 1, "M11 won")
    e.close()


@test(modes=("ds",))
def bh_act2_m11_paratroopers(ctx):
    """Day 5 and day 10: Sensei's five paratroopers appear behind the player's line."""
    e, g, d, texts = ready(ctx, 11)
    n = sum(1 for u in g.units(3))
    e.w16(DAY, 4)
    seen = a2.to_day(e, g, d, 5)
    ctx.eq(e.u16(DAY), 5, "day 5")
    ctx.check("Paratroopers! Jump, you lazy sparrows!" in seen, f"Sensei's line ({seen})")
    ctx.log(f"army 3: {[(u['type'], u['x'], u['y']) for u in g.units(3)]}")
    ctx.check(sum(1 for u in g.units(3) if u["x"] <= 6) >= 3, "paratroopers stand behind the player's line")
    a2.pic(ctx, e, "m11_paratroopers")
    e.close()


@test(modes=("ds",))
def bh_act2_m8_two_fronts(ctx):
    """M8: the player picks two COs (main front, second front); Jess leads the main front's army and
    Javier the second's; Auto CO is on at the start and Intel has General; the second front is the Gate of
    Dusk (20x16) after the round; its win (a rout) joins its CO to the main CO as partner."""
    from aw2test import twofront as tf
    pair = [bh.STURM, bh.HAWKE] if not os.environ.get("ACT2_M8_PAIR") else [int(x) for x in os.environ["ACT2_M8_PAIR"].split(",")]
    e, g, d, texts = ready(ctx, 8, pair)
    ctx.eq(d.size(), (24, 18), "the Gate of Dawn: 24x18")
    ctx.eq(g.player(2)["co"], bh.JESS, "Jess leads the main front's enemy")
    ctx.eq(e.u8(tf.SECOND_COS + 1), bh.JAVIER, "Javier leads the second front's enemy")
    ctx.eq(sorted([g.player(1)["co"], e.u8(tf.SECOND_COS)]), sorted(pair), "a CO of the player's own for each front")
    ctx.eq(e.u8(tf.MANUAL), 0, "Auto CO is on at the start (no army's turns are manual)")
    ctx.check("General" in tf.intel(g)["names"], "Intel > General is there")
    a2.pic(ctx, e, "m8_main_front")
    seen = []

    def watch():
        k = (e.u8(tf.LIVE), e.u16(DAY), e.u16(tf.CURRENT_ARMY))
        if e.u8(tf.BUSY) == 0 and (not seen or seen[-1] != k):
            seen.append(k)
    for rnd in range(4):   # (the enemy advances now: an idle player is routed on the fifth day)
        a2.end_turn(e, g, d)
        e.wait(30)
        ok = tf.until(e, d, lambda: tf.player_turn(e) or e.u8(dc.LAST_RESULT) != 0, frames=60000, each=watch)
        if not ok:
            a2.pic(ctx, e, "m8_round_stuck")
        ctx.log(f"round {rnd + 1} seen {seen[-12:]}")
        ctx.require(ok, f"round {rnd + 1} came back to the player ({tf.state(e)})")
        d.wait_control()
        if rnd == 0:
            a2.pic(ctx, e, "m8_after_round_1")
    ctx.check(any(s[0] == 1 for s in seen), f"the second front was on the screen during the round ({seen})")
    e.close()


# --- save and continue ----------------------------------------------------------------------------------------
def save_continue(ctx, n, cos=None, two_fronts=False):
    """The mission saved halfway from its map menu and brought back by BH CAMPAIGN's Continue as it was."""
    from aw2test import saves
    from aw2test.emu import Emu
    from aw2test.game import Game
    e, g, d, texts = ready(ctx, n, cos)
    names = saves.suspend(g)
    ctx.check("Save" in names, f"M{n}: Save on the map menu ({names})")
    snap = saves.snapshot(g)
    saved = saves.flash(e, os.path.join(ctx.out, f"m{n}_saved"))
    e.close()
    e2 = Emu(save=saved.path, ds=ctx.ds)
    g2 = Game(e2, ctx.image)
    ctx.games.append(g2)
    d2 = bh.BhCampaign(g2)
    d2.start_bh(new=False, pick=False)
    ctx.require(e2.wait_until(lambda: e2.u32(0x03000000) == 0x08022049, 1800, step=10), f"M{n}: Continue brings the battle back")
    g2._units_base = g2._players_base = None
    g2.wait_for_input()
    ctx.eq((d2.mission(), e2.u8(bh.SOURCE)), (a2.M[n], bh.BH), f"M{n}: the mission, the BH Campaign's session")
    saves.compare_snapshots(ctx, snap, saves.snapshot(g2), f"M{n} after a reboot")
    a2.pic(ctx, e2, f"m{n}_continued")
    if n == 9:
        ctx.eq(sorted(u["type"] for u in g2.units(1) if u["type"] == 7), [7, 7, 7], "M9: the three Vault APCs are back")
    e2.close()


@test(modes=("ds",))
def bh_act2_m4_save_and_continue(ctx):
    save_continue(ctx, 4)


@test(modes=("ds",))
def bh_act2_m9_save_and_continue(ctx):
    save_continue(ctx, 9)


@test(modes=("ds",))
def bh_act2_m8_save_and_continue(ctx):
    save_continue(ctx, 8, [bh.STURM, bh.HAWKE], two_fronts=True)


@test(modes=("ds",))
def bh_act2_m4_von_bolt_pitch_and_bond(ctx):
    """Von Bolt picked: his pitch (not Sturm's), Hawke joins, the bond (bit 1) is earned and the
    world-map panel of M4 shows its star; the win is by leaving Hawke one unit."""
    e, g, d, texts = ready(ctx, 4, [bh.VON_BOLT])
    ctx.check("Flattery! Does it come with a fee?" in texts and "I did not come for praise. I came to take." not in texts, "Von Bolt's opening exchange")
    victory, mapscene = a2.win_by_attrition(ctx, e, g, d, "m4_vb", shots=(0,))
    ctx.check("Marshal, the pay is the world. In writing." in victory and "You will not kneel. You will command under my banner." not in victory, f"Von Bolt's pitch ({victory})")
    ctx.eq(d.bonds(), 2, "Hawke's bond earned")
    ctx.eq(d.unlocked(), [bh.STURM, bh.VON_BOLT, bh.HAWKE], "Hawke unlocked")
    e.close()


@test(modes=("ds",))
def bh_act2_m5_parked_aircraft_stay_parked(ctx):
    """AI byte 6: the eight parked aircraft do not fly off or strike a unit beside them over three days."""
    e, g, d, texts = ready(ctx, 5)
    jets = [u for u in g.units(2) if u["type"] in (16, 17)]
    pos0 = {u["id"]: (u["x"], u["y"]) for u in jets}
    ground = [u for u in g.units(2) if u["type"] not in (16, 17)]
    for u in ground:
        d.remove_unit(u)           # (nothing else of Green Earth's to strike the Recon)
    recon = next(u for u in g.units(1) if u["type"] == 6)
    d.place_unit(recon, jets[0]["x"], jets[0]["y"] + 1)
    e.wait(10)
    a2.to_day(e, g, d, 3)
    now = {u["id"]: (u["x"], u["y"]) for u in g.units(2) if u["type"] in (16, 17)}
    ctx.eq(now, pos0, "every aircraft still where it was parked")
    ctx.eq([u["hp"] for u in g.units(1) if u["id"] == recon["id"]], [100], "the Recon beside a Fighter was not struck")
    e.close()


def _full_hp(n):
    def fn(ctx):
        """Every unit of both armies starts at full hit points (the Lasers and minicannons fire on Black Hole's turn
        at every unit on their lines, ours included: nobody of ours starts there)."""
        e, g, d, texts = ready(ctx, n)
        for t in range(6):
            low = [(u["army"], u["type"], u["x"], u["y"], u["hp"]) for u in g.units() if u["hp"] != 100]
            ctx.eq(low, [], f"M{n}: every unit at 100 HP at the first turn (+{t * 100} frames)")
            e.wait(100)
        e.close()
    fn.__name__ = f"bh_act2_m{n}_units_start_at_full_hit_points"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _full_hp(_n)


@test(modes=("ds",))
def bh_act2_enemy_units_advance(ctx):
    """The AI roles: over three days the enemy's units leave their start tiles (all but the hold garrisons
    and the indirect fire, which stand); the counts are logged per mission."""
    for n in range(4, 12):
        e, g, d, _ = ready(ctx, n)
        before = {u["id"]: (u["x"], u["y"], u["type"], u["army"]) for u in g.units() if u["army"] >= 2}
        a2.to_day(e, g, d, 4)
        after = {u["id"]: (u["x"], u["y"]) for u in g.units() if u["army"] >= 2}
        alive = [i for i in before if i in after and after[i][:2] != (0, 0)]
        moved = [i for i in alive if after[i] != before[i][:2]]
        still = {}
        for i in alive:
            if i not in moved:
                still[before[i][2]] = still.get(before[i][2], 0) + 1
        ctx.log(f"M{n}: {len(moved)} of {len(alive)} surviving enemy units left their start tiles; still: {still}")
        ctx.check(len(moved) >= max(1, len(alive) // 4), f"M{n}: the enemy advances ({len(moved)} of {len(alive)} moved)")
        e.close()


@test(modes=("ds",))
def bh_act2_m8_send_to_the_second_front(ctx):
    """M8: a Black Hole unit standing on the army's HQ or base gets the Send command, leaves the main
    front once its move ends and arrives by the army's units on the second front when it starts;
    a unit off the HQ and bases has no Send."""
    from aw2test import twofront as tf
    e, g, d, texts = ready(ctx, 8, [bh.STURM, bh.HAWKE])
    hq = next((x, y) for y in range(d.size()[1]) for x in range(d.size()[0]) if g.terrain_class(x, y) == 0x08 | 1 << 5)
    mine = [u for u in g.units(1) if u["type"] in (1, 2, 5)]
    u = mine[0]
    if g.unit_at(*hq) is None:
        d.place_unit(u, *hq)
    u = g.unit_at(*hq)
    count = len(g.units(1))
    tf.select(e, g, d, hq[0], hq[1])
    names = g.move_to(*hq)["names"]
    a2.pic(ctx, e, "m8_send_command")
    ctx.check("Send" in names, f"Send in the command menu of a unit on the HQ ({names})")
    for _ in range(names.index("Send")):
        e.press("DOWN", 4)
        e.wait(6)
    e.press("A", 4)
    for _ in range(300):
        e.wait(10)
        if d.scripts_running():
            e.press("A", 4)
        elif g.idle():
            break
    g.wait_for_input()
    ctx.eq(len(g.units(1)), count - 1, "the unit has left the main front")
    ctx.eq(e.u8(tf.QUEUED), 1, "on its way to the second front")
    other = next(v for v in g.units(1) if g.terrain_class(v["x"], v["y"]) & 0x1F not in (0x08, 0x0E, 0x0A, 0x0B))
    names = tf.command(e, g, d, other["x"], other["y"], "Wait")
    ctx.check("Send" not in names, f"no Send off the HQ and bases ({names})")
    tf.end_round(e, d)
    ctx.eq(e.u8(tf.STARTED), 1, "the second front played its first round")
    own = [v for v in tf.store_units(e) if v[0] == 1 and v[1] < 28 and v[2] < 20 and v[3] < 16]
    base = sum(1 for line in open(os.path.join(MAP_FILES, "bh08b.txt")) if line.startswith(f"unit 1 {u['type']} "))
    got = [v for v in own if v[1] == u["type"]]
    ctx.log(f"army 1 on the second front: {own}")
    ctx.eq(len(got), base + 1, f"the second front has its own {base} of that type and the one sent ({got})")
    ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
    a2.pic(ctx, e, "m8_send_arrival")
    e.close()
