"""BH Campaign, Act II (Green Earth, M4 to M11: tango-gamesupport-aw2/src/bh_act2.rs)."""

import os

from aw2test import bhact2 as a2
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test


@test(modes=("ds",))
def bh_act2_m4_win(ctx):
    e, g, d = a2.boot(ctx, a2.WON(3), a2.ST | a2.VB, at=3)
    a2.open_mission(ctx, e, g, d, 3, [bh.VON_BOLT], "m4")
    d.wait_control()
    victory, mapscene = a2.win_by_attrition(ctx, e, g, d, "m4", shots=(0, 5))
    ctx.log("VICTORY\n" + "\n".join(victory) + "\nMAP\n" + "\n".join(mapscene))
    ctx.eq(d.won() & 8, 8, "M4 won")
    ctx.eq(d.unlocked(), [bh.STURM, bh.VON_BOLT, bh.HAWKE], "Hawke unlocked")
    ctx.eq(d.bonds(), 2, "Hawke's bond (bit 1)")
    a2.pic(ctx, e, "m4_world_after")
    e.close()



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
    7: ("Greenhaven Arsenal", [1, 2, 3, 4, 5], ALL, [bh.STURM], [(5, bh.STURM), (3, bh.EAGLE)], (24, 20), False, 22),
    8: ("The Twin Gates", [1, 2, 3, 4, 5, 6, 7], ALL, [bh.STURM, bh.HAWKE], [(5, bh.STURM), (3, bh.JESS)], (24, 18), False, 22),
    9: ("The Loot Train", [1, 2, 3, 4, 5, 6, 7, 8], ALL, [bh.STURM], [(5, bh.STURM), (3, bh.JAVIER)], (28, 14), True, 16),
    10: ("Evergreen Citadel", [1, 2, 3, 4, 5, 6, 7, 8, 9], ALL, [bh.STURM, bh.HAWKE], [(5, bh.STURM), (3, bh.EAGLE)], (28, 22), False, 24),
    11: ("Exiles' Last Stand", [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], ALL, [bh.STURM, bh.HAWKE], [(5, bh.STURM), (3, bh.JAVIER), (4, bh.SENSEI)], (26, 18), False, 22),
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
    ctx.eq([(p["colour"], p["co"]) for p in ps], armies, f"M{n}: army colours and COs")
    ctx.eq(d.size(), size, f"M{n}: the map's size")
    ps = g.playst()
    ctx.eq(bool(ps["fog"]), fog, f"M{n}: fog")
    ctx.eq(e.u16(DS_TABLE + 0x5C * dc.DS_MAP_ID + 0x24), limit, f"M{n}: the day limit")
    for army, count in units.items():
        ctx.eq(mission_count(g, army), count, f"M{n}: army {army}'s units")
    if len(picks) == 2:
        from aw2test import tag
        ctx.log(f"partner of army 1: {tag.partner(e, 1)}, army CO {g.player(1)['co']}")
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
        unfog(g, e)
    g.goto(0, 0)
    stitch.stitch(ctx, g, f"m{n}", w, h)
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
BOT_OPTS = {}   # per mission: aw2test.bot.Bot options


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


# --- the world map: Act II's flags on Green Earth ----------------------------------------------------
@test(modes=("ds",))
def bh_act2_world_map_flags(ctx):
    """With M1..M10 won and M11 open, AW2's map shows Act II's eight flags on Green Earth (the east land),
    cleared ones starred; pictures with the cursor on several of them."""
    e, g, d = a2.boot(ctx, a2.WON(10), ALL, at=10)
    d.wait_world_map()
    flags = d.map_flags()
    ctx.eq([flags[k] & 1 for k in range(3, 11)], [1] * 8, "Act II's flags are all shown")
    ctx.eq([flags[k] & 2 for k in range(3, 10)], [2] * 7, "M4..M10 cleared (starred)")
    ctx.eq(d.map_mission(), 10, "the cursor on M11")
    e.wait(90)
    a2.pic(ctx, e, "world_map_m11")
    for k in (9, 8, 7, 6, 5, 4, 3):
        for _ in range(20):
            if d.map_mission() == k:
                break
            e.press("LEFT", 6)
            e.wait(25)
        e.wait(100)
        a2.pic(ctx, e, f"world_map_m{k + 1}")
    e.close()


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
    ctx.eq(len(bs), 10, "ten beaches: two on each island")
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
            d.end_turn()
            g.wait_for_input()
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
        g.wait_idle()
        ctx.eq(g.unit(lander["id"])["x"], bx, f"beach {(bx, by)}: the Lander of army {army} sailed onto the shoal")
        g.select(*land[0])
        names = g.move_to(bx, by)["names"]
        ctx.check(any(n.lower().startswith("load") for n in names), f"beach {(bx, by)}: the Infantry is offered Load ({names})")
        g.choose("Load", g.ACTION_MENU)
        g.wait_idle()
        ctx.check(any(g.unit(lander["id"])["cargo"]), f"beach {(bx, by)}: the Lander carries the Infantry")
        # a round later: the Lander drops it on the land beside the beach
        d.end_turn()
        g.wait_for_input()
        while g.current_army() != army:
            d.end_turn()
            g.wait_for_input()
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
        g.wait_idle()
        iu, lu = g.unit(inf["id"]), g.unit(lander["id"])
        ctx.check((iu["x"], iu["y"]) in land and not any(lu["cargo"]), f"beach {(bx, by)}: the Infantry stands on the land beside it, the Lander empty")
        if k in (0, 5):
            a2.pic(ctx, e, f"m6_lander_dropped_{bx}_{by}")
        done[army] += 1
    ctx.eq(done, {1: 5, 2: 5}, "each army used five beaches")
    e.close()
