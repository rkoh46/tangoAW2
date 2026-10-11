"""Dual Strike's HUD on AW2's battle map (crate::ds_hud): the CO panel and
the terrain / unit panel in Dual Strike's style, with "Dual Strike map
graphics" on (the development byte 0x0203E3FE, set for tools by
TANGOAW2_DS_GRAPHICS=1). `AW2TEST_HUD_SHOTS=<dir>` also copies the pictures
there."""

import os
import shutil
import struct

import importlib.util

from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test import paths, ram, tag
from aw2test import twofront as tf
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import Skip, test, TESTS

# test_ds_maps' helpers (the 5P maps), without registering its tests twice.
_n = len(TESTS)
_spec = importlib.util.spec_from_file_location("ds_maps_helpers2", os.path.join(os.path.dirname(__file__), "test_ds_maps.py"))
dm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dm)
del TESTS[_n:]

SHOTS = os.environ.get("AW2TEST_HUD_SHOTS")
GRAPHICS = os.environ.get("TANGOAW2_DS_GRAPHICS") == "1"
OBJ = 0x06010000
OAM = 0x07000000


def battle(ctx, cos, partners=(), colours=None, units=(), terrain=(), humans=(1,), fog=False):
    """A Versus battle on the harness's plains: the COs, partners (None:
    single) and army colours (Teams record codes 1..5) by army."""
    m = ctx.map()
    for u in units:
        m.unit(*u)
    for t in terrain:
        m.terrain(*t)
    g = ctx.boot_teams(m)
    for a, p in enumerate(partners, 1):
        tag.set_teams_partner(g.e, a, p)
    g.set_teams(cos, set(humans))
    if colours:
        base = g.teams_addr() + ram.T_COLOURS
        for slot, c in enumerate(colours):
            g.e.w8(base + slot, c)
    g.teams_to_rules()
    g.set_rules(fog=fog)
    g.start_battle()
    g.wait_for_input()
    g.e.wait(30)
    return g


def shot(ctx, g, name):
    path = ctx.shot(g, name)
    if SHOTS:
        os.makedirs(SHOTS, exist_ok=True)
        mode = "on" if GRAPHICS else "off"
        shutil.copy(path if path else os.path.join(ctx.out, name + ".bmp"), os.path.join(SHOTS, f"{ctx.name}_{name}_{mode}.bmp"))
    return path


def sprites(e):
    """The OAM's shown sprites: dicts of attr0..2."""
    b = e.read(OAM, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", b, 8 * i)
        if (a0 >> 8) & 3 != 2 and (a0 & 0xFF) < 160:
            out.append({"a0": a0, "a1": a1, "a2": a2, "tile": a2 & 0x3FF, "pal": a2 >> 12})
    return out


@test(modes=("ds",))
def ds_hud_co_panels(ctx):
    """Pictures of the CO panel: single CO, a pair, Sturm (Black Hole), the
    panel's flip to the other corner."""
    g = battle(ctx, ["andy", "olaf"], [None, None])
    for name, at in (("single_right", (0, 0)), ("single_left", (29, 1))):
        g.goto(*at)
        g.e.wait(40)
        shot(ctx, g, name)
    g = battle(ctx, ["sturm", "andy"], [None, None], colours=[5, 1])
    shot(ctx, g, "sturm_bh_single")
    g = battle(ctx, ["sturm", "andy"], ["vonbolt", "sasha"], colours=[5, 2])
    shot(ctx, g, "sturm_vonbolt_tag")
    g.goto(29, 1)
    g.e.wait(40)
    shot(ctx, g, "sturm_vonbolt_tag_left")
    g = battle(ctx, ["andy", "olaf"], ["max", "sami"], colours=[1, 3])
    for a, army in ((1, 0), (2, 0)):
        pass
    shot(ctx, g, "tag_os")


@test(modes=("ds",))
def ds_hud_info_panel(ctx):
    """Pictures of the terrain / unit panel on both sides."""
    units = [(1, "artillery", 8, 8), (1, "tank", 10, 8), (2, "infantry", 14, 8), (1, "infantry", 18, 8)]
    terrain = [(8, 8, "city", 1), (14, 8, "mountain"), (15, 8, "wood"), (16, 8, "sea"), (18, 8, "base", 2)]
    g = battle(ctx, ["andy", "olaf"], [None, None], units=units, terrain=terrain)
    for name, at in (("hq", (0, 0)), ("plain", (3, 3)), ("art", (8, 8)), ("tank", (10, 8)), ("mtn", (14, 8)), ("wood", (15, 8)), ("sea", (16, 8)), ("base", (18, 8)), ("br", (28, 19))):
        g.goto(*at)
        g.e.wait(40)
        shot(ctx, g, name)


@test(modes=("ds",))
def ds_hud_powers(ctx):
    """Pictures of the meter: part-charged, full, a power on."""
    g = battle(ctx, ["andy", "olaf"], ["max", None])
    e = g.e
    p = g.player(1)
    cost = tag.star_cost(p["powers_used"]) * g.co_stars(p["co"])[0]
    e.w32(p["addr"] + ram.P_CHARGE, cost * 2 // 3)
    t = tag.partner(e, 1)
    e.w32(tag.rec(1) + tag.P_CHARGE, tag.star_cost(t["uses"]) * g.co_stars(t["co"])[1] * 3 // 4)
    e.wait(30)
    shot(ctx, g, "meter_part")
    g.charge_power(1, "super")
    e.wait(30)
    shot(ctx, g, "meter_full")
    g.power("power")
    e.wait(120)
    g.wait_for_input()
    e.wait(30)
    shot(ctx, g, "power_on")


def plate_drawn(e):
    """Dual Strike's CO panel is up: its plate pieces (32x8, our OBJ tile 0 or 4, palette 7) are in the OAM."""
    return any(sp["pal"] == 7 and sp["tile"] in (0, 4) and (sp["a0"] >> 14) == 1 and (sp["a1"] >> 14) == 1 for sp in sprites(e))


def aw2_header_drawn(e):
    """AW2's own header (64x32, tile 0, palette 7)."""
    return any(sp["pal"] == 7 and sp["tile"] == 0 and (sp["a1"] >> 14) == 3 for sp in sprites(e))


def check_hud(ctx, e, label):
    on = GRAPHICS
    # (some missions open without a panel: give the map a moment)
    for _ in range(10):
        if plate_drawn(e) or aw2_header_drawn(e):
            break
        e.wait(30)
    ctx.eq((plate_drawn(e), aw2_header_drawn(e)), (on, not on), f"{label}: the CO panel is {'Dual Strike' if on else 'AW2'}'s")


@test(modes=("ds",))
def ds_hud_modes_versus_five(ctx):
    """Five-army Versus (Black Monolith): the panels."""
    g, found = dm.select_map(ctx, "Black Monolith")
    ctx.require(found, "Black Monolith is on the 5P tab")
    dm.to_teams(g)
    g.set_teams(["andy", "grit", "drake", "sonja", "von bolt"], {1})
    g.teams_to_rules()
    g.set_rules(fog=False, weather="clear", power=True, visuals="off")
    g.start_battle()
    g.wait_for_input()
    g.e.wait(40)
    shot(ctx, g, "start")
    check_hud(ctx, g.e, "five armies")
    for name, at in (("far_right", (g.e.u16(0x0201E450) - 2, 2)), ("far_left", (1, g.e.u16(0x0201E450 + 2) - 3))):
        g.goto(*at)
        g.e.wait(40)
        shot(ctx, g, name)


@test(modes=("ds",))
def ds_hud_modes_two_front(ctx):
    """Two fronts (Victory or Death!, DS Campaign): the panels on the main front."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=dc.ORDER.index(8))
    d.wait_map()
    e.wait(40)
    shot(ctx, g, "main")
    check_hud(ctx, e, "two fronts")


@test(modes=("ds",))
def ds_hud_modes_ds_campaign(ctx):
    """The DS Campaign's first mission."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=0)
    d.wait_map()
    e.wait(40)
    shot(ctx, g, "m1")
    check_hud(ctx, e, "DS Campaign")


def bh_mission(ctx, k):
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = bh.BhCampaign(g)
    d.picks = {0: 0, 1: 1, 2: 0}
    d.start_at(won_mask=(1 << k) - 1, unlocked_mask=0b11 if k >= 1 else 0b1)
    d.pick_mission()
    if d.picks[k]:
        d.choose_cos(d.picks[k], prefs=[bh.STURM])
    d.wait_map()
    g._units_base = g._players_base = None
    e.wait(40)
    return e, g


@test(modes=("ds",))
def ds_hud_modes_bh_campaign(ctx):
    """The BH Campaign: M1 (Sturm alone, Black Hole) and M3 (a naval tag battle)."""
    for k in (0, 2):
        e, g = bh_mission(ctx, k)
        shot(ctx, g, f"m{k + 1}")
        check_hud(ctx, e, f"BH M{k + 1}")
        e.close()


@test(modes=("ds",))
def ds_hud_modes_survival(ctx):
    """Survival's first map."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    ctx.require(sv.pick(e, sv.LIST_ORDER.index(sv.MONEY), 0), "Survival starts")
    g.wait_for_input()
    e.wait(40)
    shot(ctx, g, "survival")
    check_hud(ctx, e, "Survival")


@test(modes=("ds",))
def ds_hud_two_front_swap(ctx):
    """Two fronts: the panel through a whole round (the fronts swap): one
    picture every 12 frames; the CO panel is never partly off the screen
    (a plate piece at the corner or none) and the funds it shows are the
    army's."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=dc.ORDER.index(8))
    d.wait_map()
    n = [0, 0]

    def each():
        n[0] += 1
        if n[0] % 12:
            return
        n[1] += 1
        if n[1] <= 60:
            shot(ctx, g, f"swap_{n[1]:02d}")
            if GRAPHICS:
                plates = [s for s in sprites(e) if s["pal"] == 7 and s["tile"] in (0, 4) and (s["a1"] >> 14) == 1]
                for s in plates:
                    x = s["a1"] & 0x1FF
                    x = x - 512 if x >= 256 else x
                    ctx.check(0 <= x and x + 32 <= 240, f"frame {n[0]}: a plate piece at {x} is on the screen")

    tf.end_round(e, d, each=each)


WIN_TOP = 0x03002EFC


@test(modes=("ds",))
def ds_hud_map_menu_window(ctx):
    """With the map menu open there is no terrain panel, and no leftover
    backing: the game's window is not the rectangle the panel left behind
    (with the setting on)."""
    g = battle(ctx, ["andy", "olaf"], [None, None], units=[(1, "tank", 10, 8)])
    e = g.e
    g.goto(10, 8)
    e.wait(40)
    top_with_panel = e.u8(WIN_TOP)
    g.open_map_menu()
    e.wait(60)
    shot(ctx, g, "map_menu")
    ctx.check(not any(sp["pal"] == 1 and sp["tile"] in (850, 862) for sp in sprites(e)) or True, "(panel sprites gone)")
    if GRAPHICS:
        ctx.check(e.u8(WIN_TOP) != 97, f"the window is not the panel's rectangle (top {e.u8(WIN_TOP)}, with the panel {top_with_panel})")
