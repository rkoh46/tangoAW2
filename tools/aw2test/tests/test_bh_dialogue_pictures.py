"""Pictures of the BH Campaign's key dialogue scenes, every box of them, to see that no box overflows or is cut off
(`-k bh_dialogue_pictures`; AW2TEST_DIALOGUE_SHOTS=<dir> also copies the contact sheets there). Not an assertion of
the words (the text files and the box-fit lint do that): the pictures are for looking at."""

from aw2test import bhact5b as a5
from aw2test import bhcampaign as bh
from aw2test import boxshots
from aw2test.harness import test

BONDS = 0x1FF << 12
FULL = 0xFFF | BONDS


def go(ctx, n, unlocked, cos, wons=None):
    won = 0
    for k in (wons if wons is not None else range(1, n)):
        won |= 1 << a5.M[k]
    e, g, d = a5.boot(ctx, won, unlocked, picks={a5.M[n]: len(cos)}, at=a5.M[n])
    d.pick_mission()
    if cos:
        d.choose_cos(len(cos), prefs=list(cos))
    for _ in range(600):
        if d.in_battle() and e.u32(0x0849_9598) != 0:
            break
        e.press("A", 4) if d.scripts_running() else None
        e.wait(10)
    ctx.require(d.in_battle(), f"M{n}: the battle loaded")
    g._units_base = g._players_base = None
    return e, g, d


def after_intro(ctx, e, g, d, label):
    d.leave_setup()
    a5.intro(ctx, e, d, label, shots=())
    d.wait_control()


def check(ctx, name, paths, minimum):
    sheets = boxshots.sheet(ctx, paths, name)
    ctx.check(len(paths) >= minimum, f"{name}: {len(paths)} boxes photographed (at least {minimum}); sheets: {len(sheets)}")


@test(modes=("ds",))
def bh_dialogue_pictures_m1_pre(ctx):
    e, g, d = go(ctx, 1, 1, [])
    d.leave_setup()
    check(ctx, "m1_pre", boxshots.shoot(ctx, e, d, "m1_pre", patience=200), 30)
    e.close()


@test(modes=("ds",))
def bh_dialogue_pictures_m14_post(ctx):
    e, g, d = go(ctx, 14, 0x1F | BONDS, [bh.STURM])
    after_intro(ctx, e, g, d, "m14")
    # (M14 is won by Crumb standing on Pad Echo, not by routing the enemy: put him there, then take an action)
    crumb = next(u for u in g.units(1) if u["type"] == 1 and u["hp"] < 100)
    if g.unit_at(19, 18) and g.unit_at(19, 18)["id"] != crumb["id"]:
        d.remove_unit(g.unit_at(19, 18))
    d.place_unit(crumb, 19, 18)
    e.wait(10)
    mine = [u for u in g.units(1) if u["type"] in (1, 2, 3, 5, 6) and u["id"] != crumb["id"]][0]
    g.select(mine["x"], mine["y"])
    names = g.move_to(mine["x"], mine["y"])["names"]
    g.choose(next(x for x in names if x.lower().startswith("wait")), g.ACTION_MENU)
    check(ctx, "m14_post", boxshots.shoot(ctx, e, d, "m14_post", patience=600, wait_map=True), 25)
    e.close()


@test(modes=("ds",))
def bh_dialogue_pictures_m27_post(ctx):
    e, g, d = go(ctx, 27, 0x1FF | BONDS, [])
    after_intro(ctx, e, g, d, "m27")
    ctx.require(d.force_win(), "M27: a forced win")
    check(ctx, "m27_post", boxshots.shoot(ctx, e, d, "m27_post", patience=600, wait_map=True), 25)
    e.close()


@test(modes=("ds",))
def bh_dialogue_pictures_m31_defection_and_secret_epilogue(ctx):
    e, g, d = go(ctx, 31, FULL, [bh.STURM], wons=[22, 23, 24, 25, 26, 27, 28])
    after_intro(ctx, e, g, d, "m31")
    ctx.require(d.force_win(), "M31: a forced win")
    paths = boxshots.shoot(ctx, e, d, "m31", patience=900, max_boxes=220, wait_map=True)
    check(ctx, "m31_post_to_epilogue", paths, 120)
    e.close()
