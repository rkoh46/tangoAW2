"""BH Campaign, Act V first half (M23 to M28) and the secret M31: pictures of every map
(tango-gamesupport-aw2/src/bh_act5b.rs, bh_secret.rs)."""

import os

from aw2test import bhact5b as a5
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.harness import test

FOG = 0x03003FCD
ALL_ROSTER = 0x7FF | (0x1FF << 12)
# number: (title, won (mission numbers incl. the 22 stub), CO picks, fog, size)
MISSIONS = {
    23: ("Laboratory 7", [22], [bh.STURM], True, (22, 18)),
    24: ("Sky Gala", [22, 23], [bh.STURM], False, (22, 16)),
    25: ("Twin Harbours", [22, 23], [bh.STURM, bh.HAWKE], False, (26, 18)),
    26: ("The Last Alliance", [22, 23, 24, 25], [bh.STURM, bh.SONJA], False, (30, 24)),
    27: ("Echo", [22, 23, 24, 25, 26], [bh.STURM], True, (24, 18)),
    28: ("Home Is Where The Black Is", [22, 23, 24, 25, 26, 27], [], False, (29, 29)),
    31: ("The Colonel's Vault", [22, 23, 24, 25, 26, 27, 28], [bh.STURM], True, (29, 20)),
}


def unfog(g, e):
    e.w8(FOG, 0)
    e.wait(10)
    g.open_map_menu()
    e.wait(20)
    e.press("B", 4)
    e.wait(40)


def pictures(ctx, n):
    from aw2test import stitch
    title, won, picks, fog, size = MISSIONS[n]
    mask = 0
    for k in won:
        mask |= 1 << a5.M[k]
    e, g, d = a5.boot(ctx, mask, ALL_ROSTER, picks={a5.M[n]: len(picks)}, at=a5.M[n])
    texts = a5.open_mission(ctx, e, g, d, a5.M[n], picks, f"m{n}")
    if n == 28:
        # five armies: the player (army 5) moves last; the computer's four turns pass first
        for _ in range(3000):
            if g.current_army() == 5 and not d.scripts_running():
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(20)
    d.wait_control()
    g._units_base = g._players_base = None
    a5.pic(ctx, e, f"m{n}_opening")
    ctx.log("\n".join(texts))
    stitch.IMAGES = a5.SHOTS or stitch.IMAGES
    w, h = d.size()
    ctx.eq((w, h), size, f"M{n}: map size")
    if fog:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_fog", w, h)
        unfog(g, e)
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}_nofog", w, h)
    else:
        g.goto(0, 0)
        stitch.stitch(ctx, g, f"m{n}", w, h)
    if n == 25:
        from aw2test import twofront as tf
        ctx.require(tf.look_at_other_front(e, g), "the other front is shown")
        w2, h2 = d.size()
        a5.pic(ctx, e, "m25_second_front_view")
        g.goto(0, 0)

        class Quiet:
            def __init__(self, c):
                self.c = c

            def __getattr__(self, k):
                return getattr(self.c, k)

            def check(self, ok, msg):
                return None
        stitch.stitch(Quiet(ctx), g, "m25_second_front", w2, h2, exclude=lambda tx, ty: ty <= 2 and 5 <= tx <= 10)
    e.close()


def _pictures(n):
    def fn(ctx):
        pictures(ctx, n)
    fn.__name__ = f"bh_act5b_pictures_m{n}"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    _pictures(_n)
