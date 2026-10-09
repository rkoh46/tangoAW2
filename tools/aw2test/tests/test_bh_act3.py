"""BH Campaign, Act III (Yellow Comet, M12 to M16: tango-gamesupport-aw2/src/bh_act3.rs)."""

import os

from aw2test import bhact3 as a3
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test

GMAP = 0x0201E450
DS_TABLE = 0x08E00000
DAY = 0x03004080
FOG = 0x03003FCD
ALL = a3.ST | a3.VB | a3.HK | a3.KO | a3.KI
# number: (title, won before (mission numbers; M11 is the tree's stub), roster bits, CO picks, size, fog, day limit)
MISSIONS = {
    12: ("Highway to the Horizon", [11], a3.ST | a3.VB | a3.HK, [bh.STURM], (36, 18), False, 28),
    13: ("Festival of Flame", [11, 12], a3.ST | a3.VB | a3.HK | a3.KO, [bh.STURM], (22, 16), False, 14),
    14: ("No Soldier Left Behind", [11, 12, 13], ALL, [bh.STURM], (22, 22), True, 15),
    15: ("The Skybridge", [11, 12, 13, 14], ALL, [bh.STURM, bh.HAWKE], (24, 20), False, 24),
    16: ("Comet Keep", [11, 12, 13, 14, 15], ALL, [bh.STURM, bh.HAWKE], (26, 22), False, 24),
}


def load_mission(ctx, n):
    title, won, roster, picks, size, fog, limit = MISSIONS[n]
    mask = 0
    for k in won:
        mask |= 1 << a3.M[k]
    e, g, d = a3.boot(ctx, mask, roster, picks={a3.M[n]: len(picks)}, at=a3.M[n])
    return e, g, d, MISSIONS[n]


def unfog(g, e):
    """Fog off for the picture: the map redraws unfogged once the map menu has opened and closed."""
    e.w8(FOG, 0)
    e.wait(10)
    g.open_map_menu()
    e.wait(20)
    e.press("B", 4)
    e.wait(40)


def pictures(ctx, n):
    from aw2test import stitch
    e, g, d, spec = load_mission(ctx, n)
    title, won, roster, picks, size, fog, limit = spec
    texts = a3.open_mission(ctx, e, g, d, a3.M[n], picks, f"m{n}", shots=(0,))
    d.wait_control()
    g._units_base = g._players_base = None
    a3.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    stitch.IMAGES = a3.SHOTS or stitch.IMAGES
    w, h = d.size()
    ctx.eq((w, h), size, f"M{n}: the map's size")
    if fog:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_fog", w, h)       # the map as the player sees it on day 1
        unfog(g, e)
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_nofog", w, h)     # every unit of both sides
    else:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}", w, h)
    if n == 15:
        from aw2test import twofront as tf
        ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
        w2, h2 = d.size()
        ctx.eq((w2, h2), (20, 14), "the sky front: 20x14")
        a3.pic(ctx, e, "m15_second_front_view")
        g.goto(0, 0)
        class Quiet:
            def __init__(self, c):
                self.c = c

            def __getattr__(self, k):
                return getattr(self.c, k)

            def check(self, ok, msg):
                return None
        clean = stitch.stitch(Quiet(ctx), g, "m15_second_front", w2, h2, exclude=lambda tx, ty: ty <= 2 and 5 <= tx <= 10)
    e.close()


def _pictures(n):
    def fn(ctx):
        pictures(ctx, n)
    fn.__name__ = f"bh_act3_pictures_m{n}"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)
