"""The README's battle pictures in Dual Strike's look (`-k readme_`, run with TANGOAW2_DS_GRAPHICS=1 TANGOAW2_TILT=1): raw
240x160 BMPs in the folder named by AW2TEST_SHOWCASE_DIR (scaled 3x nearest to 720x480 PNGs by the caller). The BH
Campaign's pictures come from test_bh_showcase.py (`-k bh_showcase`), taken with the same two variables."""

import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aw2test import dscampaign as dc
from aw2test import rom as romlib
from aw2test import twofront as tf
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths, survival as sv
from aw2test.harness import test
from aw2test.save import DesignMap

OUT = os.environ.get("AW2TEST_SHOWCASE_DIR")


def keep(ctx, e, name):
    p = e.shot(os.path.join(ctx.out, name))
    if OUT:
        os.makedirs(OUT, exist_ok=True)
        shutil.copy(p, os.path.join(OUT, name + ".bmp"))
    return p


def settle(g, x, y, frames=40):
    for _ in range(4):
        try:
            g.goto(x, y)
            break
        except Exception:
            g.e.wait(150)
    g.e.wait(frames)


@test(modes=("ds",))
def readme_versus(ctx):
    # (Black Hole only plays in a five-army map: the other three armies keep to the corners)
    m = ctx.map(hq=((1, 16, 7), (5, 1, 3), (2, 29, 19), (3, 29, 0), (4, 0, 19)))
    m.colours = [5, 1, 2, 3, 4]
    for x in (0, 1, 2, 3):
        m.terrain(x, 5, "city", 5)
    for x, y in ((6, 2), (7, 2), (8, 2), (9, 2), (10, 2)):
        m.terrain(x, y, "city", 0)
    for x, y in ((14, 2), (15, 2), (16, 4), (17, 4)):
        m.terrain(x, y, "city", 1)
    for x in range(4, 16):
        m.terrain(x, 5, "road")
    for x, y in ((5, 1), (5, 2), (11, 6), (11, 7), (12, 6), (12, 7), (4, 8), (5, 8), (6, 8), (13, 9), (14, 9)):
        m.terrain(x, y, "wood")
    for x, y in ((8, 7), (9, 7), (9, 8)):
        m.terrain(x, y, "mountain")
    m.unit(5, "tank", 3, 4).unit(5, "artillery", 2, 4).unit(5, "infantry", 4, 5).unit(5, "recon", 3, 6)
    m.unit(1, "tank", 14, 6).unit(1, "artillery", 15, 6).unit(1, "infantry", 13, 5).unit(1, "tank", 16, 7)
    g = ctx.start(m, None)
    g.e.w8(g.player(5)["addr"] + 0x1D, romlib.co_id("sturm"))
    e = g.e
    e.wait(60)
    for k, (x, y) in enumerate(((3, 4), (2, 3), (4, 5))):
        settle(g, x, y)
        keep(ctx, e, f"versus-{k}")
    e.close()


@test(modes=("ds",))
def readme_second_front(ctx):
    for mission, tag in ((tf_m, n) for tf_m, n in ((10, "lightning"), (21, "ring"), (24, "means"))):
        e = Emu(save=paths.base_save(), ds=ctx.ds)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        d = dc.DsCampaign(g)
        d.start(step=dc.ORDER.index(mission))
        d.wait_map()
        d.wait_control()
        try:
            tf.set_auto_co(g, False)
        except Exception as ex:
            ctx.log(f"{tag}: auto co: {ex}")
        d.end_turn()
        e.wait(30)
        ok = tf.until(e, d, lambda: e.u8(tf.LIVE) == 1 and e.u8(tf.BUSY) == 0 and e.u16(tf.MAP_STATE) == tf.CURSOR_STATE)
        ctx.log(f"{tag}: second front for the player: {ok} {tf.state(e)}")
        e.wait(60)
        keep(ctx, e, f"second-{tag}")
        e.close()


@test(modes=("ds",))
def readme_laser(ctx):
    import test_ds_onyx as o
    e, g, d = o.start(ctx)
    e.w16(o.CHARGE, o.FULL * 9 // 10 - 3)
    o.wait_text(e, d, "Check out Black Onyx")
    d.wait_control()
    e.w16(o.CHARGE, o.FULL - 3)
    ctx.require(e.wait_until(lambda: e.u8(o.PHASE) == o.FIRING, 120, step=1), "fires")
    ctx.require(e.wait_until(lambda: e.u8(o.STRIKE) == 3, 400, step=1), "strike")
    seen = set()
    for k in range(200):
        if e.u8(o.STRIKE) != 3:
            break
        t = e.u16(o.STRIKE + 4)
        b = e.u16(o.BLDCNT)
        if b == 0x3E41 and e.u16(o.DISPCNT) & 0x100 and t % 6 == 0:
            keep(ctx, e, f"laser-beam-{t}")
        if b == 0x00BF and "f" not in seen:
            seen.add("f")
            keep(ctx, e, "laser-flash")
        e.wait(1)
    e.close()


@test(modes=("ds",))
def readme_crumb(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["crumb", "jugger"])
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    for k in range(4):
        g.e.wait(90 if k == 0 else 40)
        keep(ctx, g.e, f"crumb-{k}")
    g.e.close()


@test(modes=("ds",))
def readme_teams(ctx):
    import test_ds_coselect as c
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    c.to_five_army_teams(ctx, g)
    e.wait(60)
    keep(ctx, e, "teams-0")
    from aw2test import tag
    for army in range(5):
        e.press("START", 6)
        e.wait(20)
        for _ in range((2, 3, 5, 7, 9)[army]):
            e.press("DOWN", 6)
            e.wait(20)
        e.press("START", 6)
        e.wait(20)
        keep(ctx, e, f"teams-pick{army}")
        ctx.log(f"army {army}: partners {list(e.read(tag.TEAMS_PARTNER, 5))}")
        e.press("RIGHT", 6)
        e.wait(14)
        e.press("RIGHT", 6)
        e.wait(14)
        ctx.log(f"after right: partners {list(e.read(tag.TEAMS_PARTNER, 5))}")
    e.wait(60)
    keep(ctx, e, "teams-final")
    e.close()


@test(modes=("ds",))
def readme_fortress(ctx):
    import test_bh_review as r
    from aw2test import bhact2 as a2
    e, g, d = r.enter(ctx, 28)
    d.leave_setup()
    a2.intro(ctx, e, d, "m28", shots=())
    stable = 0
    for _ in range(3000):
        stable = stable + 1 if g.current_army() == 5 and not d.scripts_running() else 0
        if stable >= 5:
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(20)
    d.wait_control()
    g._units_base = g._players_base = None
    for k, (x, y) in enumerate(((9, 18), (10, 19), (12, 17), (5, 16), (14, 15), (6, 19), (12, 19), (3, 12), (14, 19))):
        settle(g, x, y, 60)
        keep(ctx, e, f"fortress-{k}")
    e.close()


@test(modes=("ds",))
def readme_takeover(ctx):
    """M30's stage-two takeover: the existing proof test's frames (in this test's folder), HUD and cursor left on."""
    import test_bh_act5 as t5
    t5.bh_act5_m30_takeover_proof(ctx)


@test(modes=("ds",))
def readme_laser_lead_in(ctx):
    """The laser's panel beam before the strike, and the map just after it (the tilt steps aside during the strike itself)."""
    import test_ds_onyx as o
    e, g, d = o.start(ctx)
    e.w16(o.CHARGE, o.FULL * 9 // 10 - 3)
    o.wait_text(e, d, "Check out Black Onyx")
    d.wait_control()
    e.w16(o.CHARGE, o.FULL - 3)
    ctx.require(e.wait_until(lambda: e.u8(o.PHASE) == o.FIRING, 120, step=1), "fires")
    for k in range(60):
        if e.u8(o.STRIKE) == 3:
            break
        if k % 3 == 0:
            keep(ctx, e, f"lead-{k:02d}")
        e.wait(2)
    while e.u8(o.STRIKE) == 3:
        e.wait(1)
    for k in range(6):
        e.wait(10)
        keep(ctx, e, f"after-{k}")
    e.close()
