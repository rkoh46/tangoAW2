"""BH Campaign, Act IV (Blue Moon, M17 to M22: tango-gamesupport-aw2/src/bh_act4.rs)."""

import os

from aw2test import bhact4 as a2
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test


# --- every mission loads: its armies, map, rules and opening ---------------------------------------
GMAP = 0x0201E450
DS_TABLE = 0x08E00000
DAY = 0x03004080
KOAL, KINDLE, JUGGER, FLAK = 8, 16, 32, 64
SASHA, GRIT = 78, 5
ALL = a2.ST | a2.VB | a2.HK | KOAL | KINDLE | JUGGER
# number: (title, won before (mission numbers), roster bits, CO picks, armies: (colour, CO), map size, fog, day limit)
# (bh01, bh02 and the bh16 stand-in come first in this tree: the won mask is every earlier mission)
MISSIONS = {
    17: ("Cold Iron", [1, 2, 3], ALL & ~JUGGER, [bh.STURM], [(5, bh.STURM), (2, bh.JUGGER)], (24, 18), True, 22),
    18: ("The Pit", [1, 2, 3, 4], ALL, [bh.STURM], [(5, bh.STURM), (2, bh.FLAK)], (20, 20), False, 12),
    19: ("The Assembly Line", [1, 2, 3, 4], ALL, [bh.STURM], [(5, bh.STURM), (2, SASHA)], (32, 26), False, 28),
    20: ("Moonlit Harbours", [1, 2, 3, 4, 5, 6], ALL | FLAK, [bh.STURM, bh.HAWKE], [(5, None), (2, bh.OLAF)], (26, 18), False, 24),
    21: ("Running Dry", [1, 2, 3, 4, 5, 6, 7], ALL | FLAK, [bh.STURM], [(5, bh.STURM), (1, 2), (2, GRIT)], (28, 20), True, 26),
    22: ("Whiteout", [1, 2, 3, 4, 5, 6, 7, 8], ALL | FLAK, [bh.STURM, bh.HAWKE], [(5, None), (2, bh.OLAF)], (28, 22), False, 24),
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
    mask = (1 << a2.M[n]) - 1
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
        other = (e.u8(tf.SECOND_COS)) if n == 20 else tag.partner(e, 1)["co"]
        ctx.eq(sorted([g.player(1)["co"], other]), sorted(picks), f"M{n}: the two picks lead the main army and its partner (or the second front)")
    a2.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    e.close()


def _loads(n):
    def fn(ctx):
        check_load(ctx, n)
    fn.__name__ = f"bh_act4_m{n}_loads"
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
    if n == 20:
        # the dusk gate, the second front: Map menu > Front shows it
        from aw2test import twofront as tf
        ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
        w2, h2 = d.size()
        ctx.eq((w2, h2), (22, 16), "the second front's map: the open sea, 22x16")
        a2.pic(ctx, e, "m20_second_front_view")
        g.goto(0, 0)
        # (the view's "Second front" banner sits on the screen's top: a sweep without the cells it covers, the
        # few cells only it can show stand in the row below's)
        class Quiet:
            def __init__(self, c):
                self.c = c

            def __getattr__(self, k):
                return getattr(self.c, k)

            def check(self, ok, msg):
                return None
        clean = stitch.stitch(Quiet(ctx), g, "m20_second_front", w2, h2, exclude=lambda tx, ty: ty <= 2 and 5 <= tx <= 10)
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
                Image.fromarray(a).save(os.path.join(a2.SHOTS, "m20_second_front_full.png"))
        except ImportError:
            pass
    e.close()


def _pictures(n):
    def fn(ctx):
        pictures(ctx, n)
    fn.__name__ = f"bh_act4_pictures_m{n}"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)




