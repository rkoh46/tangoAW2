"""Screen effects drawn over the battle map keep the Dual Strike tilt (no flat frame, no flat map showing through).
Each scene runs with every frame rendered and reads the tilt's skip and leak logs (aw2test/tiltwatch.py)."""

from aw2test import tiltwatch as tw
from aw2test.harness import test


@test(modes=("ds",))
def tiltfx_supply(ctx):
    m = ctx.map()
    m.unit(1, 7, 10, 10).unit(1, "tank", 11, 10).unit(1, "artillery", 10, 11)
    g = ctx.start(m, ["andy", "drake"], env=tw.env(ctx))
    for (x, y) in ((11, 10), (10, 11)):
        a = g.unit_addr(g.unit_at(x, y)["id"])
        g.e.w16(a + 4, (g.e.u16(a + 4) & ~0x780) | (1 << 7))
    g.wait_for_input()
    tw.on(ctx, g, 3)
    g.select(10, 10)
    g.move_to(10, 10)
    ctx.log(f"choose Supply at {g.e.frame}")
    g.choose("Supply", g.ACTION_MENU)
    g.wait_for_input()
    g.e.wait(30)
    tw.report(ctx, "supply")


def tagfx_battle(ctx, units):
    from aw2test import tag
    m = ctx.map()
    for u in units:
        m.unit(*u)
    g = ctx.boot_teams(m, env=tw.env(ctx))
    tag.set_teams_partner(g.e, 1, "andy")
    tag.set_teams_partner(g.e, 2, None)
    g.set_teams(["max", "olaf"], {1})
    g.teams_to_rules()
    g.set_rules(fog=False)
    g.start_battle()
    g.wait_for_input()
    return g


@test(modes=("ds",))
def tiltfx_tag_power(ctx):
    from aw2test import ram, tag
    from aw2test import rom as romlib
    g = tagfx_battle(ctx, [(1, "tank", 10, 10), (2, "tank", 11, 10), (1, "infantry", 3, 3), (2, "infantry", 25, 12)])
    e = g.e
    p = g.player(1)
    e.w32(p["addr"] + ram.P_CHARGE, tag.star_cost(p["powers_used"]) * g.co_stars(p["co"])[1])
    t = tag.partner(e, 1)
    e.w32(tag.rec(1) + tag.P_CHARGE, tag.star_cost(t["uses"]) * g.co_stars(t["co"])[1])
    g.open_map_menu()
    tw.on(ctx, g, 4)
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "first Super Power")
    g.wait_for_input()
    tw.report(ctx, "tag power, first half")
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co"] == romlib.co_id("andy") and g.player(1)["co_mode"] == 2, 3000, step=10), "second half")
    g.wait_for_input()
    tw.report(ctx, "tag power, both halves")


def hp(g, x, y, v):
    a = g.unit_addr(g.unit_at(x, y)["id"])
    g.e.w16(a + 4, (g.e.u16(a + 4) & ~0x7F) | v)


@test(modes=("ds",))
def tiltfx_join_load_unload(ctx):
    m = ctx.map()
    m.unit(1, "infantry", 10, 10).unit(1, "infantry", 11, 10)
    m.unit(1, "apc", 15, 10).unit(1, "infantry", 14, 10)
    m.terrain(20, 10, "city", 2)
    m.unit(1, "infantry", 19, 10)
    g = ctx.start(m, ["andy", "drake"], env=tw.env(ctx))
    e = g.e
    hp(g, 10, 10, 40)
    hp(g, 11, 10, 30)
    g.wait_for_input()
    tw.on(ctx, g, 4)
    g.select(10, 10)
    g.move_to(11, 10)
    g.choose("Join", g.ACTION_MENU)
    g.wait_for_input()
    e.wait(30)
    tw.report(ctx, "join")
    g.select(14, 10)
    g.move_to(15, 10)
    g.choose("Load", g.ACTION_MENU)
    g.wait_for_input()
    e.wait(30)
    tw.report(ctx, "load")
    g.select(15, 10)
    g.move_to(15, 10)
    g.choose("Drop", g.ACTION_MENU)
    e.wait(20)
    if g.menu():
        e.press("A", 4)
        e.wait(20)
    e.press("A", 4)
    e.wait(40)
    g.wait_for_input()
    e.wait(30)
    ctx.log(("after unload", [(u["type"], u["x"], u["y"], u["hp"]) for u in g.units(1)]))
    tw.report(ctx, "unload")
    g.select(19, 10)
    g.move_to(20, 10)
    g.choose("Capt", g.ACTION_MENU)
    g.wait_for_input()
    e.wait(30)
    tw.report(ctx, "capture")


def capture_almost(g, x, y, n=19):
    a = g.unit_addr(g.unit_at(x, y)["id"])
    g.e.w8(a + 5, (g.e.u8(a + 5) & 7) | (n << 3))


@test(modes=("ds",))
def tiltfx_victory_hq(ctx):
    m = ctx.map()
    m.unit(1, "infantry", 29, 19)
    g = ctx.start(m, ["andy", "drake"], env=tw.env(ctx))
    e = g.e
    capture_almost(g, 29, 19)
    g.wait_for_input()
    tw.on(ctx, g, 4)
    g.select(29, 19)
    g.move_to(29, 19)
    g.choose("Capt", g.ACTION_MENU)
    e.wait(900)
    tw.report(ctx, "victory (HQ)")


@test(modes=("ds",))
def tiltfx_victory_last_unit(ctx):
    m = ctx.map(spare=False)
    m.unit(1, "tank", 10, 10).unit(2, "infantry", 11, 10)
    g = ctx.start(m, ["andy", "drake"], env=tw.env(ctx))
    e = g.e
    hp(g, 11, 10, 5)
    g.wait_for_input()
    tw.on(ctx, g, 4)
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(11, 10)
    e.wait(900)
    tw.report(ctx, "victory (last unit)")


@test(modes=("ds",))
def tiltfx_defeat_hq(ctx):
    m = ctx.map()
    m.unit(2, "infantry", 0, 0)
    m.unit(1, "tank", 15, 15)
    g = ctx.start(m, ["andy", "drake"], env=tw.env(ctx))
    e = g.e
    capture_almost(g, 0, 0)
    g.wait_for_input()
    tw.on(ctx, g, 4)
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    e.wait(1500)
    ctx.log(("state", [(u["army"], u["type"], u["x"], u["y"]) for u in g.units()]))
    tw.report(ctx, "defeat (HQ)")


def bh_boot(ctx, mission, picks, features="inventions"):
    from aw2test import bhcampaign as bh
    from aw2test.emu import Emu
    from aw2test.game import Game
    from aw2test import paths
    env = dict(tw.env(ctx), TANGOAW2_BH_FEATURES=features)
    e = Emu(save=paths.base_save(), ds=True, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = picks
    return e, g, d


def bh_turn(ctx, e, g, d, name):
    tw.on(ctx, g, 4)
    d.end_turn()
    for _ in range(900):
        if e.u16(0x03004080) >= 2 and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    d.wait_control()
    e.wait(30)
    tw.report(ctx, name)


@test(modes=("ds",))
def tiltfx_bh_laser_minicannon(ctx):
    from aw2test import bhcampaign as bh
    e, g, d = bh_boot(ctx, 14, {14: 0}, features="1")
    d.start_at(won_mask=0x3FFF & ~(1 << 5), unlocked_mask=1)
    d.pick_mission()
    d.wait_map()
    bh_turn(ctx, e, g, d, "laser+minicannon")


@test(modes=("ds",))
def tiltfx_bh_cannon(ctx):
    from tests.test_cpu_inventions import fill_ammo
    e, g, d = bh_boot(ctx, 0, {0: 0, 1: 0})
    d.start_at(won_mask=0, unlocked_mask=0b1)
    d.pick_mission()
    d.wait_map()
    g._units_base = g._players_base = None
    fill_ammo(e, g)
    cells = [(12, 8), (11, 9), (10, 10), (16, 10), (17, 11), (18, 12), (14, 8), (10, 8), (18, 10)]
    for u, (x, y) in zip(g.units(army=2), cells):
        d.place_unit(u, x, y)
        e.w8(g.unit_addr(u["id"]) + 0x0B, 0)
    tw.on(ctx, g, 4)
    g.end_turn(human=1, max_frames=60000)
    g._units_base = g._players_base = None
    d.wait_control()
    e.wait(30)
    tw.report(ctx, "black cannon + minicannon")


@test(modes=("ds",))
def tiltfx_silo(ctx):
    from tests.test_silo_launch import SILO, aim, settle
    m = ctx.map()
    m.terrain(10, 10, SILO)
    m.unit(1, "infantry", 10, 10)
    m.unit(2, "tank", 14, 10).unit(2, "tank", 15, 10).unit(2, "infantry", 14, 12)
    g = ctx.start(m, ["andy", "andy"], env=tw.env(ctx))
    g.wait_for_input()
    tw.on(ctx, g, 4)
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Launch", g.ACTION_MENU)
    aim(g, (10, 10), (14, 10))
    settle(g, None)
    g.e.wait(30)
    ctx.log(("hp", [(u["army"], u["hp"]) for u in g.units()]))
    tw.report(ctx, "missile silo")


@test(modes=("ds",))
def tiltfx_weather_notice(ctx):
    m = ctx.map()
    g = ctx.start(m, ["andy", "drake"], weather="random", env=tw.env(ctx))
    g.wait_for_input()
    tw.on(ctx, g, 6)
    for day in range(6):
        g.end_turn(human=1, max_frames=60000)
        g.wait_for_input()
        g.e.wait(20)
        ctx.log(("day", day, g.playst()["weather"]))
    tw.report(ctx, "weather change (random)")


@test(modes=("ds",))
def tiltfx_fog(ctx):
    m = ctx.map()
    m.terrain(12, 10, "wood")
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10).unit(1, "infantry", 11, 10)
    g = ctx.start(m, ["andy", "drake"], fog=True, env=tw.env(ctx))
    g.wait_for_input()
    tw.on(ctx, g, 4)
    # fog goes off and on again through the memory byte where the rules keep it (gPlaySt+0x0D)
    for v in (0, 1, 0, 1):
        g.e.w8(0x03003FC0 + 0x0D, v)
        g.e.wait(40)
    g.select(10, 10)
    g.move_to(13, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input()
    g.end_turn(human=1, max_frames=60000)
    g.wait_for_input()
    g.e.wait(30)
    tw.report(ctx, "fog on/off")


def dialogue_run(ctx, step):
    import os
    from aw2test import dscampaign as dc
    from aw2test import paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    os.environ.update(tw.env(ctx))
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=step)
    tw.on(ctx, g, 5)
    tops = 0
    for _ in range(900):
        if d.on_co_select():
            d.co_screen_a()
        e.wait(10)
        if d.in_battle():
            tops = max(tops, d.top_box_rows())
            if d.scripts_running():
                e.press("A", 4)
            elif tops and not d.scripts_running():
                break
    e.wait(40)
    ctx.log(f"max top box rows {tops}")
    tw.report(ctx, f"dialogue mission step {step}")


@test(modes=("ds",))
def tiltfx_dialogue_2(ctx):
    dialogue_run(ctx, 2)


@test(modes=("ds",))
def tiltfx_dialogue_0(ctx):
    dialogue_run(ctx, 0)


@test(modes=("ds",))
def tiltfx_dialogue_5(ctx):
    dialogue_run(ctx, 5)
