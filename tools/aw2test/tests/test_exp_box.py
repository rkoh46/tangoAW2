"""The EXP box (crate::exp_box): after a battle that gave CO EXP (a War Room map, a Gauntlet win; also a campaign mission and the end of a Survival run), AW2's
results page waits for A with its totals worked out and a window of the game's own opens over it: each CO's face, "+N EXP" and a bar from the old EXP to the new
within the rank, "Rank up!" past a rank. A skips the filling, then closes; the page under it gets the next A. A Versus win gives no EXP and shows nothing.
`-k exp_box`."""

import os

from aw2test import gauntlet as ga
from aw2test import paths, saves, shots
from aw2test import survival as sv
from aw2test.emu import Emu
from aw2test.game import Game, NavError
from aw2test.harness import test
from tests.test_co_skills import DATA, CO_SLOTS, PLAYERS, P_YIELD, co_at, co_exp, war_room_battle

BOX = 0x0203C640           # crate::exp_box::STATE: +0 state, +1 COs, +2 page, +4 frame (u16), then 12-byte entries from +8 (CO, army, before u32 at +4, after u32 at +8)
IDLE, PENDING, SHOWN, CLOSING = 0, 1, 2, 3
RESULTS_WAIT = 0x08616184  # the results page's wait-for-A proc
PROCS = 0x0200D610
SETTLED = 84               # crate::exp_box::SETTLED


def results_waits(e):
    return any(e.u32(PROCS + 0x6C * k) == RESULTS_WAIT for k in range(32))


def entries(e):
    return [(e.u8(BOX + 8 + 12 * k), e.u8(BOX + 9 + 12 * k), e.u32(BOX + 12 + 12 * k), e.u32(BOX + 16 + 12 * k)) for k in range(e.u8(BOX + 1))]


def until_box(e, state=SHOWN, frames=4000, through_page=False):
    """A through VICTORY and the quote until the box has `state` (A is not pressed once the page waits or the box is up; `through_page`: A on the results page too,
    for a run's end, whose box waits for Survival's own panel)."""
    for k in range(frames // 5):
        if e.u8(BOX) == state:
            return True
        e.wait(5)
        if k % 12 == 11 and e.u8(BOX) != SHOWN and (through_page or not results_waits(e)):
            e.press("A", 4)
    return e.u8(BOX) == state


def pixels(e, ctx, name):
    return shots.read_bmp(e.shot(os.path.join(ctx.out, name)))


def count(rows, test_px, box=(0, 0, 240, 160)):
    x0, y0, x1, y1 = box
    return sum(1 for y in range(y0, y1) for x in range(x0, x1) if test_px(rows[y][x]))


RED = lambda p: p[0] > 200 and p[1] < 90 and p[2] < 90
BLUE = lambda p: p[0] < 90 and p[1] < 110 and p[2] > 180


def war_room_win(ctx, exp=950):
    """War Room, every CO at `exp`: the battle is won (the computer yields) and A pressed to the results."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    saves.to_select_mode(e)
    e.w32(DATA, 0x314C4B53)
    for c in CO_SLOTS:
        e.w32(co_at(c), exp)
    war_room_battle(e, g)
    co = e.u8(e.u32(PLAYERS) + 0x3C + 0x1D)
    for a in range(2, 5):
        if e.u8(e.u32(PLAYERS) + 0x3C * a + 0x1B):
            e.w8(e.u32(PLAYERS) + 0x3C * a + P_YIELD, 1)
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    return e, g, co


@test(modes=("ds",))
def exp_box_war_room_win(ctx):
    """A War Room win: the box opens over the results page with the CO's old and new EXP (the numbers in EWRAM are the ones the CO has now), the bar fills (the
    first picture shows the old EXP's, the settled one the new), 'Rank up!' is red text past rank 1; A skips the filling, A closes the box, and only the next A
    leaves the results page (the page's wait is still up under the box)."""
    e, g, co = war_room_win(ctx)
    ctx.require(until_box(e), "the box opens")
    es = entries(e)
    ctx.eq(len(es), 1, "one CO")
    c, army, old, new = es[0]
    ctx.eq((c, army, old), (co, 1, 950), "the player's CO, army 1, 950 EXP before")
    ctx.check(new > old and new == co_exp(e, co), f"EXP after {new} is what the CO has now ({co_exp(e, co)}) and more than before")
    ctx.check(results_waits(e), "the results page waits under the box")
    first = pixels(e, ctx, "box_start")
    ctx.eq(e.u8(BOX + 4) < 30, True, "the box has just opened")
    e.wait(40)
    mid = pixels(e, ctx, "box_mid")
    e.wait(60)
    done = pixels(e, ctx, "box_settled")
    ctx.check(e.u16(BOX + 4) >= SETTLED, "the filling is over")
    # the window (red above) is drawn, "Rank up!" appears in red once the bar has passed rank 1, and the bar's blue changes as it fills
    ctx.check(count(done, RED, (6, 40, 234, 60)) > 20, "'Rank up!' in red text in the settled box (950 -> over 1000)")
    ctx.check(count(first, BLUE, (40, 70, 230, 100)) > count(done, BLUE, (40, 70, 230, 100)) * 2, "the bar is nearly full at the start (950 of 1000) and short once it has gone over the rank")
    ctx.check(first != mid and mid != done, "the box animates")
    # A: closes; the page under it still waits; the next A leaves it
    e.press("A", 4)
    e.wait(10)
    ctx.eq(e.u8(BOX) in (CLOSING, IDLE), True, "A closes the box")
    ctx.check(results_waits(e), "the results page is still waiting for its own A")
    e.wait(20)
    ctx.eq(e.u8(BOX), IDLE, "the box is gone once the keys are up")
    e.press("A", 4)
    ctx.check(e.wait_until(lambda: not results_waits(e), 600, step=10), "the next A leaves the results page")
    ctx.check(sv.to_select_map(e), "and SELECT MAP comes back")


@test(modes=("ds",))
def exp_box_a_skips_the_filling(ctx):
    """A while the bar is filling jumps to the settled picture; the box stays until a second A."""
    e, g, co = war_room_win(ctx)
    ctx.require(until_box(e), "the box opens")
    e.wait(12)
    ctx.check(e.u16(BOX + 4) < SETTLED, "still filling")
    e.press("A", 4)
    e.wait(4)
    ctx.check(e.u16(BOX + 4) >= SETTLED and e.u8(BOX) == SHOWN, "A: settled, the box still up")
    e.wait(10)
    e.press("A", 4)
    e.wait(10)
    ctx.check(e.u8(BOX) != SHOWN, "the second A closes it")


@test(modes=("ds",))
def exp_box_gauntlet_win(ctx):
    """A Gauntlet win shows the box with Andy's EXP before and after (the points x2, as crate::battle_points gives)."""
    e = Emu(save=paths.base_save(), ds=True)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.ANDY)
    before = co_exp(e, ga.ANDY)
    d.play_to_the_last_line(ctx)
    ctx.require(until_box(e, frames=9000), "the box opens over the results")
    c, army, old, new = entries(e)[0]
    ctx.eq((c, army, old), (ga.ANDY, 1, before), "Andy's EXP before the win")
    ctx.check(new > old and new == co_exp(e, ga.ANDY), f"{old} -> {new}")
    pic = pixels(e, ctx, "gauntlet_box")
    ctx.check(count(pic, lambda p: p == (255, 255, 255), (6, 30, 234, 130)) > 3000, "the white window is drawn")


@test(modes=("ds",))
def exp_box_versus_win_shows_nothing(ctx):
    """A Versus win gives no EXP, so no box opens (the results page waits for A as ever)."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, ["andy", "max"])
    e = g.e
    for a in (2,):
        e.w8(e.u32(PLAYERS) + 0x3C * a + P_YIELD, 1)
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    waited = False
    for k in range(600):
        e.wait(5)
        if results_waits(e):
            waited = True
            e.wait(20)
            break
        if k % 12 == 11:
            e.press("A", 4)
    ctx.require(waited, "the results page was reached")
    ctx.eq(e.u8(BOX), IDLE, "no box")
    ctx.eq(co_exp(e, 1), 0, "no EXP")


@test(modes=("ds",))
def exp_box_survival_run_end(ctx):
    """A Survival run's end (cleared) gives the player's CO the run's points as EXP and the box shows it over Survival's results panel: A skips, A closes the box,
    and the panel is still up (the run is still CLEARED) until the next A."""
    from tests.test_save_integrity_modes import boot, armies
    e, g = boot(ctx)
    ctx.require(sv.open_survival(e), "Survival's SELECT MAP")
    ctx.require(sv.pick(e, sv.LIST_ORDER.index(sv.MONEY)), "Money Survival starts")
    g._units_base = g._players_base = None
    g.wait_for_input()
    e.w8(sv.STAGE, 10)
    for a in range(2, armies(e) + 1):
        e.w8(e.u32(PLAYERS) + 0x3C * a + P_YIELD, 1)
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    ctx.require(until_box(e, frames=6000, through_page=True), "the box opens (over the run's results panel, not the map's results page)")
    ctx.eq(e.u8(sv.PHASE), sv.CLEARED, "the run is cleared")
    ctx.check(not results_waits(e), "AW2's results page is gone: the box is over Survival's panel")
    c, army, old, new = entries(e)[0]
    ctx.eq((army, old), (1, 0), "army 1's CO, no EXP before")
    ctx.check(new > 0 and new == co_exp(e, c), f"the run's points as EXP: {old} -> {new} (the CO has {co_exp(e, c)})")
    e.wait(100)
    pic = pixels(e, ctx, "survival_box")
    ctx.check(count(pic, lambda p: p == (255, 255, 255), (6, 30, 234, 130)) > 3000, "the white window is drawn")
    e.press("A", 4)
    e.wait(30)
    ctx.eq(e.u8(BOX), IDLE, "A closed the settled box")
    ctx.eq(e.u8(sv.PHASE), sv.CLEARED, "the results panel is still up")
    e.press("A", 8)
    e.wait(30)
    ctx.eq(e.u8(sv.PHASE), sv.CHOOSING, "the next A closes the panel")
