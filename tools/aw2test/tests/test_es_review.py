"""Emerald Sun Campaign, all 16 missions: the review pictures, one test a mission (`-k es_review_m`). Every mission is entered through its CO screens,
its opening played out (Deploy, the intro's boxes), and photographed whole by the cursor's sweep: the full map (fog OFF) and, for a fog mission, the
fogged view as well (the player sees the fogged one in play; the sheets show both). The pictures go to the folder AW2TEST_REVIEW_DIR (m<N>_<view>.png,
16 pixels a cell); `es_sheets.py` labels them "MISSION N - Title" and makes a contact sheet per act (`aw2dev campaign sheets`)."""

from aw2test import bhact2 as a2
from aw2test import escampaign as es
from aw2test import stitch
from aw2test.harness import test
from tests.test_bh_review import Sweep, save, unfog


def review(ctx, n):
    e, g, d = es.enter(ctx, n)
    w, h = d.size()
    if d.in_setup():
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", (0,))
        d.wait_control()
        g._units_base = g._players_base = None
    for _ in range(6):
        try:
            g.goto(0, 0)
            break
        except Exception:
            e.wait(150)
    if n in es.FOG:
        save(ctx, stitch.stitch(Sweep(ctx), g, f"m{n}_fogon", w, h), n, "fogon")
        unfog(g, e)
        g.goto(0, 0)
        save(ctx, stitch.stitch(Sweep(ctx), g, f"m{n}_fogoff", w, h), n, "fogoff")
    else:
        save(ctx, stitch.stitch(Sweep(ctx), g, f"m{n}_full", w, h), n, "full")
    e.close()


def _review(n):
    def fn(ctx):
        review(ctx, n)
    fn.__name__ = f"es_review_m{n}"
    test(modes=("ds",))(fn)


for _n in range(1, 17):
    _review(_n)
