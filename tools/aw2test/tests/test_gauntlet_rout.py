"""The gauntlet engine's rout rule (docs/dev/gauntlet.md, "The rout"): when the player captures a line's HQ the army is routed at once: every unit of it is destroyed (AW2's own DefeatArmy: Dual
Strike's kinds, loaded and hidden units too), every property it owns is neutral, the next line comes and the player keeps control. One test per gauntlet map: `-k gauntlet_rout`
(BH2's M31 is `bh2_m31_hq_capture_routes_the_line`, tests/test_sleepers.py)."""

from aw2test import dscampaign as dc
from aw2test import gauntlet as ga
from aw2test import paths, rout, saves
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test


def boot(ctx):
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g, ga.Gauntlet(g)


def control(ctx, e, g, d, army, name):
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(g.current_army(), army, f"{name}: it is the player's turn")
    ctx.check(d.in_battle() and not e.u8(dc.LAST_RESULT), f"{name}: the battle goes on")


@test(name="gauntlet_rout_cinder_sea", modes=("ds",))
def gauntlet_rout_cinder_sea(ctx):
    """Cinder Sea: Drake's HQ taken (his army holds a Black Boat, a Carrier, a Stealth, a dived Sub, a loaded boat and more): he is routed at once (0 units, 0 properties), Sensei's line is in; Sensei's
    HQ: the same, Hawke's line is in; Hawke's HQ wins."""
    e, g, d = boot(ctx)
    d.start(ga.ANDY)
    n_drake = len(g.units(army=2))
    ctx.check(n_drake > 10, f"Drake's line is on the field ({n_drake})")
    planted = rout.plant_extras(e, g, 2)
    ctx.eq(len(g.units(army=2)), n_drake + len(planted), "the awkward units are on the field")
    ctx.check(len(rout.owned_cells(e, 2)) > 3, "Drake owns properties")
    own2 = rout.owned_cells(e, 2)
    d.capture(ctx, ga.CINDER["drake"])
    d.settle()
    rout.wait_routed(e, g, 2)
    rout.check_routed(ctx, e, g, 2, "Drake", planted)
    control(ctx, e, g, d, 1, "after Drake")
    ctx.eq(d.owner(ga.CINDER["drake"]), 1, "Drake's HQ is the player's")
    rout.check_captured_hq(ctx, e, ga.CINDER["drake"], 1, "Drake")
    rout.check_neutral(ctx, e, own2, ga.CINDER["drake"], "Drake")
    ctx.check(len(g.units(army=3)) >= 10, f"Sensei's wave is on the field ({len(g.units(army=3))})")
    ctx.eq(d.owner(ga.CINDER["sensei"]), 3, "Sensei's HQ is built")
    ctx.eq(d.controllers()[2], 2, "Sensei is the computer's")
    planted3 = rout.plant_extras(e, g, 3)
    own3 = rout.owned_cells(e, 3)
    d.capture(ctx, ga.CINDER["sensei"])
    d.settle()
    rout.wait_routed(e, g, 3)
    rout.check_routed(ctx, e, g, 3, "Sensei", planted3)
    rout.check_routed(ctx, e, g, 2, "Drake (still)")
    rout.check_captured_hq(ctx, e, ga.CINDER["sensei"], 1, "Sensei")
    rout.check_neutral(ctx, e, own3, ga.CINDER["sensei"], "Sensei")
    control(ctx, e, g, d, 1, "after Sensei")
    ctx.check(len(g.units(army=4)) >= 10, f"Hawke's wave is on the field ({len(g.units(army=4))})")
    ctx.eq(d.owner(ga.CINDER["hawke"]), 4, "Hawke's HQ is built")
    d.capture(ctx, ga.CINDER["hawke"])
    ctx.eq(d.through_results(), 1, "Hawke's HQ wins the battle")
    e.close()


@test(name="gauntlet_rout_iron_crown", modes=("ds",))
def gauntlet_rout_iron_crown(ctx):
    """Iron Crown, stage one (five armies, the player is army 5): Grit's HQ taken: Grit is routed (0 units, 0 properties) and Jess's line is in; Jess's HQ: the same with Kanbei's."""
    from tests import test_gauntlet_map2 as m2
    e, g, d = m2.start(ctx)
    for key, army, who, nxt in ga.IRON_ORDER[:2]:
        planted = rout.plant_extras(e, g, army)
        own = rout.owned_cells(e, army)
        d.capture(ctx, ga.IRON[key], army=5)
        d.settle()
        rout.wait_routed(e, g, army)
        rout.check_routed(ctx, e, g, army, f"{who}", planted)
        control(ctx, e, g, d, 5, f"after {who}")
        ctx.eq(d.owner(ga.IRON[key]), 5, f"{who}'s HQ is the player's")
        rout.check_captured_hq(ctx, e, ga.IRON[key], 5, who)
        rout.check_neutral(ctx, e, own, ga.IRON[key], who)
        nk = ga.IRON_ORDER[nxt - 1][0]
        ctx.check(len(g.units(army=nxt)) >= 10, f"army {nxt}'s wave is on the field ({len(g.units(army=nxt))})")
        ctx.eq(d.owner(ga.IRON[nk]), nxt, f"army {nxt}'s HQ is built")
    e.close()


@test(name="gauntlet_rout_pictures", modes=("ds",))
def gauntlet_rout_pictures(ctx):
    """Opt-in (`AW2TEST_ROUT_CKPT=<dir>`): Cinder Sea's first rout as three checkpoints of the console (before the capture, while Drake's units go, after the scenes) in <dir>, for
    `aw2dev gauntlet rout-sheet` to show in the real app in each look (AW2 graphics, Dual Strike graphics, the tilted map). Without the variable it checks only that the rout was seen under way."""
    import os
    ck = os.environ.get("AW2TEST_ROUT_CKPT")
    e = Emu(save=paths.base_save(), ds=ctx.ds, env={"AW2_CKPT_DIR": ck} if ck else None)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.ANDY)
    n = len(g.units(army=2))
    g.goto(24, 17)
    e.wait(60)
    if ck:
        e.cmd("checkpoint save rout_before")
    # the capture: the units go one after another; the picture is taken when about half of them are

    d.capture(ctx, ga.CINDER["drake"])
    left = len(g.units(army=2))
    for _ in range(300):
        left = len(g.units(army=2))
        if left <= n // 2 or left == 0:
            break
        e.wait(3)
        g._units_base = g._players_base = None
    ctx.log(f"Drake's units: {n} before, {left} at the middle picture")
    ctx.check(left < n, "the rout was under way (units gone) at the middle picture")
    if ck:
        e.cmd("checkpoint save rout_during")
    d.settle()
    rout.wait_routed(e, g, 2)
    g.goto(24, 17)
    e.wait(90)
    if ck:
        e.cmd("checkpoint save rout_after")
    rout.check_routed(ctx, e, g, 2, "Drake")
    e.close()
