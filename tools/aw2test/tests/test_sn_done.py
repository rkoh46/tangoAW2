"""Silver Nova's done (moved) units, battle scenes and CO page emblem keep the skin's colours (`-k sn_moved_units_stay_silver`, `-k sn_co_page_emblem`).

The owner's 0.9.7 reports (iPhone, Silver Nova Campaign): a unit that had moved was drawn in Orange Star's brown done colours, a battle animation drew Silver Nova's Lander in Orange Star's
orange, the CO page's emblem box showed Orange Star's star. Causes (army_skin.rs, es_campaign.rs): the skin was tied to `pvp::in_battle`, which is false in a battle scene, so it came off for
every animation and went back after it (the BH2 mission skin had been fixed for exactly that, the Silver Nova Campaign's had not); and a skin put on after the map's palettes and sprites were
loaded refreshed the sprite palettes only, not the moved units' bank (BG 11) and not the emblem's tiles in OBJ VRAM. Each test is run in the three looks of the map (AW2's graphics, Dual
Strike's with the tilt and Dual Strike's flat), in a Versus match, the Silver Nova Campaign's first mission and the Gauntlet."""
import os

from aw2test import dscampaign as dsc
from aw2test import escampaign as es
from aw2test import gauntlet as ga
from aw2test import paths
from aw2test import sndone as sn
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

CAULDER, SKIN = 0x58, 6
DIRECT_TYPES = (1, 2, 3, 4, 5, 6, 7, 8, 9)


def versus(ctx, env):
    from tests.test_army_designs import ANDY, STATE
    m = ctx.map()
    m.unit(1, "infantry", 4, 3).unit(1, "infantry", 2, 6).unit(1, "infantry", 7, 8).unit(2, "infantry", 5, 3)
    g = ctx.boot_teams(m, env)
    e = g.e
    for _ in range(8):
        if e.u8(STATE + 4):
            break
        e.press("R", 4)
        e.wait(10)
    ctx.require(e.u8(STATE + 4) != 0, "the Teams screen put the skin on army 1")
    g.set_teams([ANDY, ANDY], {1})
    g.teams_to_rules()
    g.set_rules(visuals="a")
    g.start_battle()
    g.wait_for_input()
    e.wait(60)
    return e, g, None


def campaign(ctx, env):
    e, g, d = es.enter(ctx, 1, env)
    return e, g, d


def gauntlet(ctx, env):
    e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(CAULDER, colour=SKIN)
    return e, g, d


SCENARIOS = {"versus": versus, "campaign": campaign, "gauntlet": gauntlet}


def free_neighbour(g, u):
    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
        if g.unit_at(u["x"] + dx, u["y"] + dy) is None:
            return u["x"] + dx, u["y"] + dy
    raise AssertionError("no free cell")


def movers(g):
    return [u for u in g.units(1) if u["type"] in DIRECT_TYPES]


def wait_move(g, u):
    """Pick the unit up, move it one cell and Wait: it is done."""
    e = g.e
    g.select(u["x"], u["y"])
    to = free_neighbour(g, u)
    g.move_to(*to)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    e.wait(30)
    return to


def fire(ctx, g, d, u, tag):
    """The unit fires at an enemy next to it (Versus: the enemy Infantry at (5, 3)); the battle scene is sampled every 10 frames and photographed. Returns (frames the skin was off, the picture)."""
    e = g.e
    if d is None:
        tgt = (u["x"] + 1, u["y"])
    else:
        foe = g.units(2)[0]
        tgt = free_neighbour(g, u)
        d.place_unit(foe, *tgt)
    e.wait(10)
    g.select(u["x"], u["y"])
    g.move_to(u["x"], u["y"])
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(*tgt)
    off, shot = 0, None
    for k in range(16):
        e.wait(10)
        if sn.skin_state(e, colour_of(g))[0] != 1:
            off += 1
        if k == 7:
            shot = sn.png(ctx, e, f"{tag}_scene")
    g.wait_for_input()
    e.wait(30)
    return off, shot


def colour_of(g):
    return g.player(1)["colour"]


def power(g):
    from aw2test import ram
    # (a full meter whatever the CO's star costs are: Silver Nova's COs are tangoAW2's own, the cost the table gives is not the one the menu reads)
    g.e.w32(g.player(1)["addr"] + ram.P_CHARGE, 99999)
    g.power("super")
    g.e.wait(60)


def run(ctx, scenario, look):
    e, g, d = SCENARIOS[scenario](ctx, sn.LOOKS[look])
    colour = colour_of(g)
    tag = f"{scenario}_{look}"
    us = movers(g)
    ctx.require(len(us) >= 3, f"{tag}: three of the player's foot units are on the map ({len(us)})")
    ctx.eq(sn.skin_state(e, colour), (1, colour), f"{tag}: the Silver Nova skin is on the player's colour {colour}")
    ctx.eq(sn.done_palette(e, colour), "skin", f"{tag}: before any move the done palette is the skin's")
    sn.png(ctx, e, f"{tag}_map")
    # 1. a plain move
    to = wait_move(g, us[0])
    g.goto(*to)
    e.wait(20)
    sn.png(ctx, e, f"{tag}_done")
    ctx.eq(sn.done_palette(e, colour), "skin", f"{tag}: after a move the moved unit's greys are Silver Nova's, not the host colour's")
    # 2. after a battle animation
    off, shot = fire(ctx, g, d, us[1], tag)
    ctx.eq(off, 0, f"{tag}: the skin stays on through the battle scene (frames it was off)")
    share = sn.host_share(shot)
    ctx.check(share < 0.02, f"{tag}: the battle scene has no host-colour red or orange ({share:.1%} of the attacker's half)")
    ctx.eq(sn.skin_state(e, colour), (1, colour), f"{tag}: the skin is on after the battle scene")
    ctx.eq(sn.done_palette(e, colour), "skin", f"{tag}: after a battle animation the done palette is the skin's")
    g.goto(us[1]["x"], us[1]["y"])
    e.wait(20)
    sn.png(ctx, e, f"{tag}_done_after_battle")
    # 3. after a CO power
    power(g)
    ctx.eq(sn.skin_state(e, colour), (1, colour), f"{tag}: the skin is on after a CO power")
    ctx.eq(sn.done_palette(e, colour), "skin", f"{tag}: after a CO power the done palette is the skin's")
    to = wait_move(g, us[2])
    ctx.eq(sn.done_palette(e, colour), "skin", f"{tag}: a unit moved after the CO power is drawn in the skin's greys")
    sn.png(ctx, e, f"{tag}_done_after_power")
    e.close()


def emblem(ctx, scenario, look):
    e, g, d = SCENARIOS[scenario](ctx, sn.LOOKS[look])
    colour = colour_of(g)
    tag = f"{scenario}_{look}"
    g.goto(*[(u["x"], u["y"]) for u in g.units(1)][0])
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    e.wait(90)
    sn.png(ctx, e, f"{tag}_co_page")
    host, skin = sn.emblem_in_vram(e, colour)
    ctx.check(skin, f"{tag}: the CO page's emblem is Silver Nova's sun (its tiles are in OBJ VRAM)")
    ctx.check(not host, f"{tag}: the host colour's emblem (Orange Star's star) is not left in OBJ VRAM")
    for k in range(3):
        e.press("RIGHT", 6)
        e.wait(45)
        sn.png(ctx, e, f"{tag}_co_page{k + 2}")
    e.close()


def _make():
    for scenario in SCENARIOS:
        for look in sn.LOOKS:
            def a(ctx, scenario=scenario, look=look):
                run(ctx, scenario, look)

            def b(ctx, scenario=scenario, look=look):
                emblem(ctx, scenario, look)

            a.__name__ = f"sn_moved_units_stay_silver_{scenario}_{look}"
            b.__name__ = f"sn_co_page_emblem_is_the_sun_{scenario}_{look}"
            test(modes=("ds",))(a)
            test(modes=("ds",))(b)


_make()
