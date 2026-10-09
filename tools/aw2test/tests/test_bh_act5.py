"""BH Campaign, Act V (Orange Star: M29 The Orange Gate and M30 Nell's Stand: tango-gamesupport-aw2/src/bh_act5.rs)."""

import os

from aw2test import bhact5 as a5
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test

GMAP = 0x0201E450
DS_TABLE = 0x08E00000
ALL = (1 << 11) - 1   # every roster CO unlocked
# number: (title, won mask, CO picks, armies: (colour, CO), map size, day limit)
MISSIONS = {
    29: ("The Orange Gate", a5.WON(3), [bh.STURM], [(5, bh.STURM), (1, None)], (34, 28), 32),
    30: ("Nell's Stand", a5.WON(4), [bh.STURM, bh.SONJA], [(5, None), (1, None), (1, 1)], (36, 28), 34),
}
MAP_FILES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "tango-gamesupport-aw2", "five", "bh")


def map_units(name):
    out = {}
    for line in open(os.path.join(MAP_FILES, name + ".txt")):
        f = line.split()
        if f and f[0] == "unit":
            out[int(f[1])] = out.get(int(f[1]), 0) + 1
    return out


def load_mission(ctx, n):
    title, won, picks, armies, size, limit = MISSIONS[n]
    e, g, d = a5.boot(ctx, won, ALL, picks={a5.M[n]: len(picks)}, at=a5.M[n])
    return e, g, d, MISSIONS[n]


def check_load(ctx, n):
    e, g, d, spec = load_mission(ctx, n)
    title, won, picks, armies, size, limit = spec
    units = map_units(f"bh{n:02d}")
    texts = a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}")
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(d.mission(), a5.M[n], f"M{n}: the mission")
    ctx.eq(d.size(), size, f"M{n}: the map's size")
    for army, count in units.items():
        # (M29's Black Factory puts its first unit on a door tile at once)
        ctx.eq(len(g.units(army)), count + (1 if (n, army) == (29, 1) else 0), f"M{n}: army {army}'s units")
    a5.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    e.close()


def _loads(n):
    def fn(ctx):
        check_load(ctx, n)
    fn.__name__ = f"bh_act5_m{n}_loads"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _loads(_n)


def _pictures(n):
    def fn(ctx):
        from aw2test import stitch
        e, g, d, spec = load_mission(ctx, n)
        title, won, picks, armies, size, limit = spec
        texts = a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}")
        d.wait_control()
        g._units_base = g._players_base = None
        a5.pic(ctx, e, f"m{n}_opening")
        stitch.IMAGES = a5.SHOTS or stitch.IMAGES
        w, h = d.size()
        ctx.log(f"state: scripts {d.scripts_running()} idle {g.idle()} cursor {g.cursor()} day {e.u16(0x03004080)} army {g.current_army()}")
        for _ in range(6):
            a5.calm(e, g, d)
            e.wait(150)
        FRONT = {29: (13, 13), 30: (18, 17)}[n]
        g.goto(*FRONT)
        e.wait(40)
        a5.pic(ctx, e, f"m{n}_opening_front")
        ctx.log(f"state2: scripts {d.scripts_running()} idle {g.idle()} cursor {g.cursor()}")
        for _ in range(8):
            try:
                g.goto(0, 0)
                break
            except Exception as ex:
                ctx.log(f"retry: {ex}")
                a5.calm(e, g, d)
                e.wait(150)
        stitch.stitch(ctx, g, f"m{n}", w, h)
        e.close()
    fn.__name__ = f"bh_act5_m{n}_pictures"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)
