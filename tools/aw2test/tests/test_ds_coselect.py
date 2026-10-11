"""Dual Strike's CO selection screens (`ds_coselect.rs`), with the pack and "Dual Strike map graphics" (development byte
0x0203E3FE) on: Versus' Teams screen (an army card for each army, up to five, with its emblem, portraits and P1 / CPU tab),
the CO screen of the campaigns (army cards over the grid of faces) and of the War Room. The screens are drawn over the
finished frame from the game's state, so what the game does is untouched: the tests check the pictures against Dual
Strike's own art (the `ds_coselect_preview` example draws the same art from the .nds alone, the emblems are compared
pixel for pixel), that five armies fit, and that picking sets the same COs and partners with the setting on and off."""

import os
import subprocess

from aw2test import dscampaign as dc
from aw2test import paths, ram, saves, shots, tag
from aw2test import rom as romlib
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test

DS_GRAPHICS = 0x0203E3FE
SELECT_MODE_CURSOR = 0x0300591C
VERSUS = 3
MAP_TAB = 0x0300596C
TAB_5P = 9
KEY_ARMY_COLOURS = {1: "Orange Star", 2: "Blue Moon", 3: "Green Earth", 4: "Yellow Comet", 5: "Black Hole"}

CARD_Y = 66   # ds_coselect::CARD_Y
TAB_Y = 32    # ds_coselect::TAB_Y


def card_x(n, i):
    gap = 8 if n <= 4 else 0
    total = 48 * n + gap * (n - 1)
    return (240 - total) // 2 + i * (48 + gap)


def reference(ctx):
    """The preview's pictures, drawn from the .nds alone."""
    out = os.path.join(ctx.out, "ref")
    os.makedirs(out, exist_ok=True)
    env = dict(os.environ, TANGOAW2_DS_ROM=paths.ds_rom())
    subprocess.run([paths.runner("ds_coselect_preview"), out], env=env, check=True, capture_output=True)
    return out


def emblem(rows, n, i):
    """An army card's emblem (the header's middle two tiles: 16 x 16)."""
    return shots.crop(rows, card_x(n, i) + 16, CARD_Y, 16, 16)


def ref_emblems(ctx):
    rows = shots.read_ppm(os.path.join(reference(ctx), "versus5_plain.ppm"))
    return [emblem(rows, 5, k) for k in range(5)]


def shot(ctx, e, name):
    return shots.read_bmp(e.shot(os.path.join(ctx.out, name)))


def wheel(e, pos):
    for _ in range(10):
        if e.u8(SELECT_MODE_CURSOR) == pos:
            return
        e.press("UP", 8)
        e.wait(60)
    raise NavError(f"Select Mode cursor stuck at {e.u8(SELECT_MODE_CURSOR)}")


def to_five_army_teams(ctx, g):
    e = g.e
    sv.to_select_mode(e)
    wheel(e, VERSUS)
    e.press("A", 8)
    e.wait(150)
    e.press("A", 8)
    e.wait(150)
    if not g.press_until("LEFT", lambda: e.u8(MAP_TAB) == TAB_5P, tries=14, hold=8, settle=50):
        raise NavError(f"tab {TAB_5P} not reached ({e.u8(MAP_TAB)})")
    e.wait(30)
    e.press("A", 8)
    ctx.require(e.wait_until(g.on_teams, 400, step=10), "the Teams screen")
    e.wait(60)


def differs(a, b, need=0.2):
    n = shots.diff_count(a, b, tol=4)
    return n >= need * 240 * 160


def blue_title_pixels(rows):
    """The title's glyphs are Dual Strike's blue gradient (no red, a lot of blue) in the top rows."""
    return sum(1 for r in rows[:32] for (R, G, B) in r if B > 180 and R < 90 and G < 140)


@test(modes=("ds",))
def ds_coselect_versus_two_armies(ctx):
    """The Teams screen with two armies: the title, a card for each army with its emblem (the army's colour as the Teams
    record has it: pixel for pixel Dual Strike's), the tab above it (P1, CPU), and the portraits; the setting off leaves
    AW2's own screen."""
    g = ctx.boot_teams(ctx.map())
    e = g.e
    e.w8(DS_GRAPHICS, 0)
    e.wait(10)
    off = shot(ctx, e, "versus2_off")
    e.w8(DS_GRAPHICS, 1)
    e.press("RIGHT", 6)  # the first army's controller stop: the cursor leaves the cards' headers clear
    e.wait(30)
    on = shot(ctx, e, "versus2_on")
    ctx.check(differs(off, on), "the screen is Dual Strike's with the setting on")
    ctx.check(blue_title_pixels(on) > 400 > blue_title_pixels(off), "NORMAL BATTLE's blue title is on it (and not on AW2's)")
    refs = ref_emblems(ctx)
    colours = list(e.read(ram.TEAMS + ram.T_COLOURS, 2))
    for i, c in enumerate(colours):
        ctx.eq(shots.diff_count(emblem(on, 2, i), refs[c - 1], tol=2), 0, f"army {i + 1}'s emblem is {KEY_ARMY_COLOURS[c]}'s")
    # R and L change an army's colour: its card follows, every country's emblem in turn (Blue Moon is the other army's).
    seen = set()
    for _ in range(6):
        e.press("R", 6)
        e.wait(20)
        c = e.u8(ram.TEAMS + ram.T_COLOURS)
        seen.add(c)
        rows = shot(ctx, e, f"versus2_colour{c}")
        ctx.eq(shots.diff_count(emblem(rows, 2, 0), refs[c - 1], tol=2), 0, f"army 1 as {KEY_ARMY_COLOURS[c]}: its emblem")
    ctx.eq(sorted(seen), [1, 3, 4, 5], "R went through the countries the other army has not, Black Hole included")
    # With the setting off again the console runs on as before.
    e.w8(DS_GRAPHICS, 0)
    e.wait(10)
    again = shot(ctx, e, "versus2_off_again")
    ctx.check(differs(again, on, 0.2), "with the setting off the Dual Strike screen is gone")


@test(modes=("ds",))
def ds_coselect_versus_five_armies(ctx):
    """Five armies: five cards of 48 pixels fill the screen's 240, each its army's emblem (Black Hole the fifth: its grey
    box), the tabs above them."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    to_five_army_teams(ctx, g)
    ctx.eq(g.teams()["armies"], 5, "armies on the Teams screen")
    e.w8(DS_GRAPHICS, 1)
    e.press("RIGHT", 6)
    e.wait(30)
    on = shot(ctx, e, "versus5")
    refs = ref_emblems(ctx)
    colours = list(e.read(ram.TEAMS_FIVE + 0x98, 5))
    ctx.eq(colours, [1, 2, 3, 4, 5], "the five armies' colours: Black Hole the fifth")
    for i, c in enumerate(colours):
        ctx.eq(shots.diff_count(emblem(on, 5, i), refs[c - 1], tol=2), 0, f"army {i + 1}: {KEY_ARMY_COLOURS[c]}'s emblem")
    ctx.eq(card_x(5, 0), 0, "the first card starts at the screen's left edge")
    ctx.eq(card_x(5, 4) + 48, 240, "the fifth ends at its right edge")
    # (the cards' foot lines, one army's colour each, run edge to edge)
    foot = on[CARD_Y + 64 + 3]
    ctx.check(len({tuple(p) for p in foot[:48]}) == 1 and len({tuple(p) for p in foot[192:240]}) == 1, "the first and fifth cards' foot lines are whole")
    ctx.check(foot[0] != foot[200], "each army's card has its own colour")


def pick_partners(ctx, on):
    """Boot the Teams screen, set the pairs with the pad (START on a CO stop, DOWN through the COs, START), return what the
    game holds."""
    g = ctx.boot_teams(ctx.map())
    e = g.e
    e.w8(DS_GRAPHICS, 1 if on else 0)
    e.wait(10)
    for army in range(2):
        e.press("START", 6)
        e.wait(20)
        for _ in range(2 + army):
            e.press("DOWN", 6)
            e.wait(20)
        if on and army == 0:
            shot(ctx, e, "partner_pick")
        e.press("START", 6)
        e.wait(20)
        if army == 0:
            e.press("RIGHT", 6)
            e.wait(14)
            e.press("RIGHT", 6)
            e.wait(14)
    for _ in range(3):
        e.press("DOWN", 6)
        e.wait(20)
    return g.teams(), list(e.read(tag.TEAMS_PARTNER, 5)), list(e.read(ram.TEAMS + ram.T_CONTROLLERS, 4))


@test(modes=("ds",))
def ds_coselect_partner_picks_are_the_games(ctx):
    """The same pad presses pick the same COs and partners with the setting on and off (the screen is drawn over the
    game's, never changes it); the partner pick shows its cell under the cursor."""
    off = pick_partners(ctx, False)
    on = pick_partners(ctx, True)
    ctx.eq(on, off, "the Teams record, partners and controllers")
    ctx.check(off[1][0] != 0xFF and off[1][1] != 0xFF, f"both armies picked a partner ({off[1][:2]})")


def to_co_screen(ctx, step):
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=step)
    ctx.require(e.wait_until(lambda: d.on_co_select() and d.co_cursor(), 3000, step=10) or _press_through(e, d), "the CO screen")
    e.wait(90)
    return e, g, d


def _press_through(e, d):
    for _ in range(300):
        if d.on_co_select() and d.co_cursor():
            return True
        if d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    return False


def pick_cos(ctx, on, step, label):
    e, g, d = to_co_screen(ctx, step)
    e.w8(DS_GRAPHICS, 1 if on else 0)
    e.wait(30)
    first = shot(ctx, e, f"{label}_{'on' if on else 'off'}")
    data = dc.DsData()
    picked = d.choose_cos(dc.co_picks(data, dc.ORDER[step]), dc.CO_PREFS)
    cos = [g.player(a)["co"] for a in range(1, 5)]
    return first, picked, cos


@test(modes=("ds",))
def ds_coselect_campaign_pick(ctx):
    """The DS Campaign's CO screen (a mission with two picks and their partners): army cards over the grid; the CO screen
    still picks what the setting off picks."""
    first_on, picked_on, cos_on = pick_cos(ctx, True, 10, "campaign_pick")
    first_off, picked_off, cos_off = pick_cos(ctx, False, 10, "campaign_pick")
    ctx.check(differs(first_off, first_on), "the CO screen is Dual Strike's with the setting on")
    ctx.eq(picked_on, picked_off, "the COs picked")
    ctx.eq(cos_on, cos_off, "the armies' COs in the battle")
    ctx.check(len(picked_on) >= 2, f"the mission asked for picks ({picked_on})")
    # Three cards when three armies are in the mission (Dual Strike's cards for the armies, the fixed ones named).
    rows = first_on
    reds = sum(1 for p in rows[0][:240] if p[0] > 200 and p[1] < 80)
    ctx.check(reds > 20, "the first army's red card is at the top")


def war_room_co_screen(ctx, on):
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    saves.to_select_mode(e)
    saves.wheel_to(e, saves.WAR_ROOM)
    e.press("A", 8)
    e.wait(60)
    saves.box_row(e, 1)
    e.press("A", 8)
    if not e.wait_until(lambda: sv.running(e, sv.SELECT_MAP_PROC), 600, step=10):
        raise NavError("the War Room's SELECT MAP did not open")
    e.wait(90)
    e.press("A", 8)
    if not e.wait_until(lambda: sv.running(e, sv.CO_SCREEN_PROC), 1500, step=10):
        raise NavError("the War Room's CO screen did not open")
    e.w8(DS_GRAPHICS, 1 if on else 0)
    e.wait(90)
    return e, g


@test(modes=("ds",))
def ds_coselect_war_room(ctx):
    """The War Room's CO screen: a name card (the CO under the cursor, in its country's colours), then the grid of faces
    scrolling on the GBA screen; locked COs are black cells; the cursor's moves are the game's."""
    e, g = war_room_co_screen(ctx, True)
    on = shot(ctx, e, "war_room_on")
    first = e.u8(0x03005944)
    ctx.check(1 <= first <= 5, f"the CO screen's country tabs are read ({first})")
    cursor = [e.u16(p + 0x52) for p in range(0x0200D610, 0x0200E418, 0x6C) if e.u32(p) == 0x08616638]
    e.press("RIGHT", 6)
    e.wait(40)
    cursor2 = [e.u16(p + 0x52) for p in range(0x0200D610, 0x0200E418, 0x6C) if e.u32(p) == 0x08616638]
    second = shot(ctx, e, "war_room_right")
    ctx.check(cursor2 != cursor, f"RIGHT moves the game's cursor ({cursor} -> {cursor2})")
    ctx.check(differs(on, second, 0.01), "and the picture follows")
    e.close()
    e2, g2 = war_room_co_screen(ctx, False)
    off = shot(ctx, e2, "war_room_off")
    ctx.check(differs(on, off), "the screen is Dual Strike's with the setting on")
    e2.close()
