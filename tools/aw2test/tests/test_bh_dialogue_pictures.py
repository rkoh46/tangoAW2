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
    e, g, d = go(ctx, 31, FULL, [bh.STURM], wons=range(1, 31))
    after_intro(ctx, e, g, d, "m31")
    # (M31 is won when all three Vault Trucks are gone, by the mission's own rule: two destroyed on day 1 (their scene is
    # clicked through), truck C appears on day 3, it is destroyed too, and an action lets the rule look)
    def trucks():
        g._units_base = g._players_base = None
        return [u for u in g.units() if u["army"] == 2 and u["type"] == 7]

    def act():
        mine = next(u for u in g.units() if u["army"] == 1 and u["type"] == 1)
        g.select(mine["x"], mine["y"])
        g.goto(mine["x"], mine["y"])
        e.press("A", 6)
        g.wait_menu(g.ACTION_MENU)
        names = g.menu()["names"]
        g.choose(next(n for n in names if n.lower().startswith("wait")), g.ACTION_MENU)
        e.wait(20)

    ctx.log(f"mission {d.mission()} size {d.size()} armies {[len(g.units(a)) for a in (1,2)]} types2 {sorted(set(u['type'] for u in g.units(2)))}")
    ts = trucks()
    d.remove_unit(ts[0])
    d.remove_unit(ts[1])
    act()
    for _ in range(100):
        if not d.scripts_running():
            break
        e.press("A", 4)
        e.wait(20)
    a5.to_day(e, g, d, 3)
    ts = trucks()
    ctx.require(len(ts) == 1, "truck C appears on day 3")
    e.wait(120)
    d.remove_unit(ts[0])
    e.wait(120)
    g._units_base = g._players_base = None
    act()
    paths = boxshots.shoot(ctx, e, d, "m31", patience=900, max_boxes=220, wait_map=True)
    check(ctx, "m31_post_to_epilogue", paths, 80)
    e.close()


@test(modes=("ds",))
def bh_dialogue_pictures_m1_post_and_map(ctx):
    """M1's win (on_win: the rout shows its victory scene) and the camp scene with Crumb, Mortar and Wick (their own faces)."""
    e, g, d = go(ctx, 1, 1, [])
    after_intro(ctx, e, g, d, "m1")
    ctx.require(d.force_win(), "M1: the enemy routed")
    check(ctx, "m1_post_map", boxshots.shoot(ctx, e, d, "m1_post_map", patience=600, wait_map=True), 40)
    e.close()


@test(modes=("ds",))
def bh_dialogue_pictures_m10_post_and_warroom(ctx):
    e, g, d = go(ctx, 10, FULL, [])
    after_intro(ctx, e, g, d, "m10")
    ctx.require(d.force_win(), "M10: a forced win")
    check(ctx, "m10_post", boxshots.shoot(ctx, e, d, "m10_post", patience=600, wait_map=True), 10)
    e.close()


@test(modes=("ds",))
def bh_dialogue_pictures_m3_map_and_warroom(ctx):
    """M3's world-map scene and the Allied war room that follows it (trimmed between-mission scenes). M3 is entered the way
    test_bh_act1 enters it (its opening read through, then the forced win)."""
    import importlib.util
    import os
    spec = importlib.util.spec_from_file_location("_act1_for_pictures", os.path.join(os.path.dirname(__file__), "test_bh_act1.py"))
    act1 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(act1)
    e, g, d = act1.enter(ctx, 2, wait=False)
    act1.intro_texts(ctx, e, g, d)
    act1.pass_turn(e, g, d, [])                      # (a turn passes first: as test_bh_act1 does before its forced win)
    ctx.require(d.force_win(), "M3: the enemy routed")
    check(ctx, "m3_post_map_warroom", boxshots.shoot(ctx, e, d, "m3", patience=600, wait_map=True), 25)
    e.close()
