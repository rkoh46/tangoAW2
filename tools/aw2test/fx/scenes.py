"""Scenes: each builds a battle that shows one effect, calls rec.on() just before it and rec.off() after."""
import os
from aw2test import bhcampaign as bh
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths


def _boot(ctx, env, extra=None):
    e = Emu(save=paths.base_save(), ds=True, env=dict(env, **(extra or {})))
    g = Game(e, ctx.image)
    ctx.games.append(g)
    return e, g


def bh_turn(e, g, d, rec, after=60):
    rec.on()
    d.end_turn()
    for _ in range(900):
        if e.u16(0x03004080) >= 2 and not d.scripts_running():
            break
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    d.wait_control()
    e.wait(after)
    rec.off()


def m19_structures(ctx, env, Rec):
    """Mission 19 (all four structure kinds): units set in the structures' lines, then Black Hole's turn."""
    from tests.test_dmg_forecast import start_features
    from aw2test.harness import Ctx
    os.environ.update(env)
    e, g, d = start_features(ctx, 18, True)
    g.e.survey_arm  # noqa
    rec = Rec(e)
    cells = [(6, 6), (7, 8), (3, 8), (6, 9), (9, 11), (12, 9), (7, 13), (5, 4)]
    for u, c in zip(g.units(), cells):
        d.place_unit(u, *c)
        e.w8(g.unit_addr(u["id"]) + 0x0B, 0)
    rec.on()
    g.end_turn(human=5, max_frames=60000)
    g._units_base = g._players_base = None
    d.wait_control()
    e.wait(60)
    rec.off()


def _versus(ctx, env, m, cos, humans=(1,), fog=False, weather="clear"):
    os.environ.update(env)
    return ctx.start(m, cos, humans=humans, fog=fog, weather=weather, env=env)


def silo(ctx, env, Rec):
    from tests.test_silo_launch import SILO, aim, settle
    m = ctx.map()
    m.terrain(10, 10, SILO)
    m.unit(1, "infantry", 10, 10)
    m.unit(2, "tank", 14, 10).unit(2, "tank", 15, 10).unit(2, "infantry", 14, 12)
    g = _versus(ctx, env, m, ["andy", "andy"])
    g.wait_for_input()
    rec = Rec(g.e)
    g.select(10, 10); g.move_to(10, 10)
    rec.on()
    g.choose("Launch", g.ACTION_MENU)
    aim(g, (10, 10), (14, 10)); settle(g, None)
    g.e.wait(60)
    rec.off()


def black_bomb(ctx, env, Rec):
    m = ctx.map()
    m.unit(1, "blackbomb", 5, 10).unit(2, "tank", 10, 10).unit(2, "infantry", 11, 11)
    g = _versus(ctx, env, m, ["andy", "andy"])
    g.wait_for_input()
    rec = Rec(g.e)
    g.select(5, 10); g.move_to(9, 10)
    rec.on()
    g.choose("Explode", g.ACTION_MENU)
    g.wait_for_input(); g.e.wait(40)
    rec.off()


def oozium(ctx, env, Rec):
    m = ctx.map()
    m.unit(1, 27, 10, 11).unit(2, "infantry", 11, 11).unit(2, "tank", 9, 11)
    g = _versus(ctx, env, m, ["andy", "andy"])
    g.wait_for_input()
    rec = Rec(g.e)
    g.select(10, 11); g.move_to(10, 11)
    rec.on()
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input(); g.e.wait(40)
    rec.off()


def explosions(ctx, env, Rec):
    """A tank kills infantry (the unit's explosion), then artillery shells a tank: smoke and fire."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "infantry", 11, 10).unit(1, "artillery", 5, 5).unit(2, "tank", 5, 8)
    g = _versus(ctx, env, m, ["andy", "andy"])
    g.wait_for_input()
    a = g.unit_addr(g.unit_at(11, 10)["id"]); g.e.w16(a + 4, (g.e.u16(a + 4) & ~0x7F) | 3)
    a = g.unit_addr(g.unit_at(5, 8)["id"]); g.e.w16(a + 4, (g.e.u16(a + 4) & ~0x7F) | 3)
    rec = Rec(g.e)
    rec.on()
    g.select(10, 10); g.move_to(10, 10); g.choose("Fire", g.ACTION_MENU); g.pick_target(11, 10)
    g.wait_for_input(); g.e.wait(30)
    g.select(5, 5); g.move_to(5, 5); g.choose("Fire", g.ACTION_MENU); g.pick_target(5, 8)
    g.wait_for_input(); g.e.wait(60)
    rec.off()


def supply_repair(ctx, env, Rec):
    m = ctx.map()
    m.terrain(12, 10, "city", 1)
    m.unit(1, 7, 10, 10).unit(1, "tank", 11, 10).unit(1, "tank", 12, 10)
    g = _versus(ctx, env, m, ["andy", "andy"])
    g.wait_for_input()
    for p in ((11, 10), (12, 10)):
        a = g.unit_addr(g.unit_at(*p)["id"]); g.e.w16(a + 4, (g.e.u16(a + 4) & ~0x7F & ~0x780) | 40 | (1 << 7))
    rec = Rec(g.e)
    rec.on()
    g.end_turn(human=1, max_frames=60000)
    g.wait_for_input(); g.e.wait(60)
    rec.off()


def fog_reveal(ctx, env, Rec):
    m = ctx.map()
    m.terrain(14, 10, "wood")
    m.unit(1, "recon", 8, 10).unit(2, "tank", 14, 10).unit(2, "infantry", 16, 8)
    g = _versus(ctx, env, m, ["andy", "drake"], fog=True)
    g.wait_for_input()
    rec = Rec(g.e)
    g.select(8, 10)
    rec.on()
    g.move_to(12, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_for_input(); g.e.wait(60)
    g.end_turn(human=1, max_frames=60000)
    g.wait_for_input(); g.e.wait(60)
    rec.off()


def _power(ctx, env, Rec, co, which):
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(1, "infantry", 11, 9).unit(2, "tank", 14, 10).unit(2, "infantry", 15, 12).unit(2, "mech", 17, 8)
    g = _versus(ctx, env, m, [co, "andy"])
    g.wait_for_input()
    rec = Rec(g.e)
    g.charge_power(1, which)
    g.open_map_menu()
    rec.on()
    g.choose("Super" if which == "super" else "Power", g.MAP_MENU)
    g.e.wait_until(lambda: g.player(1)["co_mode"] >= 1, 3000, step=10)
    g.wait_for_input(); g.e.wait(60)
    rec.off()


def p_drake_scop(ctx, env, Rec): _power(ctx, env, Rec, "drake", "super")
def p_drake_cop(ctx, env, Rec): _power(ctx, env, Rec, "drake", "power")
def p_sturm_scop(ctx, env, Rec): _power(ctx, env, Rec, "sturm", "super")
def p_sturm_cop(ctx, env, Rec): _power(ctx, env, Rec, "sturm", "power")
def p_vonbolt_scop(ctx, env, Rec): _power(ctx, env, Rec, "vonbolt", "super")
def p_hawke_scop(ctx, env, Rec): _power(ctx, env, Rec, "hawke", "super")
def p_hawke_cop(ctx, env, Rec): _power(ctx, env, Rec, "hawke", "power")
def p_sonja_scop(ctx, env, Rec): _power(ctx, env, Rec, "sonja", "super")
def p_kanbei_scop(ctx, env, Rec): _power(ctx, env, Rec, "kanbei", "super")


def weather(ctx, env, Rec):
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 14, 10)
    for w in ("rain", "snow"):
        pass
    g = _versus(ctx, env, m, ["andy", "drake"], weather="rain")
    g.wait_for_input()
    rec = Rec(g.e)
    rec.on(); g.e.wait(200); rec.off()
