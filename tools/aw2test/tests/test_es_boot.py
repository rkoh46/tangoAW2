"""Emerald Sun Campaign: every mission boots (`-k es_boot_m`): entered through its CO screens from a record with the earlier missions won, in the
right mode (the right armies, the map's size, every unit at full HP, ammo and fuel, the skin on the player's colour). The pictures go to
AW2TEST_REVIEW_DIR (m<N>_setup.bmp). The whole-map review sheets: `aw2dev campaign sheets`."""

import os

from aw2test import bhact2 as a2
from aw2test import escampaign as es
from aw2test.harness import test
from tests.test_bh_review import deviations

# mission: (armies, width, height)
SHAPE = {
    1: (2, 30, 27), 2: (2, 28, 19), 3: (2, 22, 16), 4: (2, 18, 16), 5: (2, 26, 14), 6: (3, 18, 18), 7: (3, 22, 16), 8: (3, 22, 16),
    9: (2, 22, 16), 10: (3, 20, 16), 11: (3, 26, 12), 12: (3, 24, 17), 13: (4, 25, 22), 14: (3, 30, 18), 15: (3, 32, 20), 16: (3, 36, 30),
}
# units that do not start at full HP, ammo or fuel by design: none yet


def _boot(n):
    def fn(ctx):
        e, g, d = es.enter(ctx, n)
        armies, w, h = SHAPE.get(n, (None, None, None))
        ctx.eq(d.size(), (w, h), f"M{n}: the map is {w}x{h}") if w else None
        cnt, bad = deviations(e, g)
        ctx.log(f"M{n} {es.TITLES[n]}: {cnt} units; not at full HP/ammo/fuel: {bad}")
        ctx.check(not bad, f"M{n}: every unit starts at full HP, ammo and fuel: {bad}")
        a2.pic(ctx, e, f"m{n}_setup")
        e.close()
    fn.__name__ = f"es_boot_m{n}"
    test(modes=("ds",))(fn)


for _n in es.TITLES:
    if _n in SHAPE:
        _boot(_n)
