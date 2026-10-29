"""BH2 Campaign, Act I (development build, crate::bh2_campaign): the review pictures, one test a mission (`-k bh2_review_m`). Every mission is entered through its CO screens,
photographed whole by the cursor's sweep (the real game's tiles, 16 pixels a cell): the full map (fog OFF), M1 also fogged, M4 also its second front. Every unit's HP, ammo and fuel
are checked against the full values. The pictures go to the folder AW2TEST_REVIEW_DIR (m<N>_<view>.png); `aw2dev maps boot --campaign bh2` labels them "MISSION N - Title"."""

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import stitch
from aw2test.harness import test
from tests.test_bh_review import BANNER, Quiet, Sweep, blank_cells, deviations, fill_blank
from tests.test_bh_review import unfog as _unfog

NEXT_WEATHER = 0x03003FEE       # crate::ds_weather: while the forecast is rain the rain forces fog every frame (M9 is rain AND fog): the review clears it to take the fog-off picture


def unfog(g, e):
    e.w8(NEXT_WEATHER, 0)
    _unfog(g, e)


def save(ctx, path, n, view):
    import os
    import shutil
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out and path:
        os.makedirs(out, exist_ok=True)
        shutil.copy(path, os.path.join(out, f"m{n}_{view}.png"))


def home(g, e):
    for _ in range(6):
        try:
            g.goto(0, 0)
            return
        except Exception:
            e.wait(150)


def sweeps(ctx, e, g, d, n, tag, exclude, front_too=True):
    w, h = d.size()
    out = {}
    home(g, e)
    if n in b2.FOG:
        out["fogon"] = stitch.stitch(Sweep(ctx), g, f"m{n}_{tag}fogon", w, h, exclude=exclude)
        unfog(g, e)
        ctx.log(f"M{n} {tag}: fog byte after unfog {e.u8(0x03003FCD)}")
        home(g, e)
        out["fogoff"] = stitch.stitch(Sweep(ctx), g, f"m{n}_{tag}fogoff", w, h, exclude=exclude)
    else:
        out["full"] = stitch.stitch(Sweep(ctx), g, f"m{n}_{tag}full", w, h, exclude=exclude)
    if n in b2.FRONT2 and front_too:
        from aw2test import twofront as tf
        views = (("front2fog", False), ("front2", True)) if n in b2.FOG else (("front2", False),)
        for view, lift in views:
            try:
                ctx.require(tf.look_at_other_front(e, g), f"M{n}: the other front is shown")
                if lift:                              # (the second front's own fog: lifted for the full-map picture)
                    e.w8(NEXT_WEATHER, 0)
                    e.w8(0x03003FCD, 0)
                    e.wait(30)
                w2, h2 = d.size()
                g.goto(0, 0)
                out[view] = stitch.stitch(Quiet(ctx), g, f"m{n}_{tag}{view}", w2, h2, exclude=exclude)
                ctx.require(tf.come_back(e, g), f"M{n}: back from the other front")
            except Exception as ex:
                if not tag:
                    raise
                ctx.log(f"M{n}: the second front after Deploy could not be shown ({ex})")
    return out


def review(ctx, n):
    e, g, d = b2.enter(ctx, n)
    cnt, bad = deviations(e, g)
    ctx.log(f"M{n} {b2.TITLES[n]}: {cnt} units; not at full HP/ammo/fuel: {bad}")
    ctx.check(not bad, f"M{n}: every unit starts at full HP, ammo and fuel: {bad}")
    w, h = d.size()
    setup = bool(b2.PICKS.get(n))
    ctx.log(f"M{n}: map {w}x{h}")
    pre = sweeps(ctx, e, g, d, n, "", BANNER if setup else None)
    if setup:
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", (0,))
        d.wait_control()
        g._units_base = g._players_base = None
        cnt2, bad2 = deviations(e, g)
        if n == 31:                                       # (a five-army mission: Nell, the first army, moves before the player's turn: her units' fuel is spent, nothing is hit)
            bad2 = [b for b in bad2 if b[4] != 'fuel']
        ctx.check(not bad2, f"M{n}: the first turn's shots hit nothing (every unit still at full HP after Deploy and the first turn start): {bad2}")
        post = sweeps(ctx, e, g, d, n, "post_", None, front_too=False)
        for view, p in pre.items():
            fill_blank(p, post.get(view))
        if n in b2.FOG and n not in b2.FRONT2:      # (a fogged mission with a Setup phase: Deploy lifts the Setup view; take the fog-off picture after it)
            for view in ("fogoff",):
                if post.get(view):
                    pre[view] = post[view]
    for view, p in pre.items():
        save(ctx, p, n, view)
    e.close()


def _review(n):
    def fn(ctx):
        review(ctx, n)
    fn.__name__ = f"bh2_review_m{n}"
    test(modes=("ds",))(fn)


for _n in b2.TITLES:
    _review(_n)
