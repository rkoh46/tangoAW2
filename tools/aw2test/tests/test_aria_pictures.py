"""Pictures of Aria for the review sheet (`aw2dev co portrait powers aria`): frames of the real game (240 x 160 BMPs in this test's output folder), picked by what they show.
    - Build Anew's activation: the quote box typed out, the cut-in with the power's name half typed and with the whole name, the HP before and after (heal 3), the funds;
    - the battle scene's header with her face (Aria attacks, animations on);
    - the War Room's CO grid (Dual Strike's) with the cursor on her;
    - the HQ: Orange Star's, drawn exactly as Nell's."""

import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "devkit"))

from aw2test import rom as romlib
from aw2test.harness import test
from tests.test_tag import read_bmp
from tests.test_asuka_pictures import burst, quote_extent, stats

ARIA = 93


def name_extent(path):
    """The width of the power's name on show: its blue outline's leftmost to rightmost column."""
    rows = read_bmp(path)
    xs = [x for r in rows[30:120] for x, (a, b, c) in enumerate(r[:160]) if c > a + 60 and c > b + 20]
    return (max(xs) - min(xs)) if xs else 0


def figure_dark(path):
    rows = read_bmp(path)
    return sum(1 for r in rows for (x, y, z) in r if max(x, y, z) < 60)


def expected_quote():
    import tomllib
    from aw2.gfxlib import font
    d = tomllib.loads(open(os.path.join(os.path.dirname(__file__), "..", "..", "..", "tango-gamesupport-aw2", "cos", "aria.toml")).read())
    f = font.load()
    lines = d["scop"]["quote"]
    return lines, [sum(f[c][0] for c in l if c in f) + len(l) - 1 for l in lines]


@test(modes=("ds",))
def aria_pics_build_anew_activation(ctx):
    """Build Anew from the map menu: frames every 2 emulated frames; the typed-out quote box (both lines, her own text), the cut-in with the name half typed and whole, the units before and after (+3 HP)."""
    from aw2test import coverify as cv
    g = ctx.start(cv.econ_map(ctx), ["aria", "andy"], env=cv.ENV)
    ctx.set_hp(g, 3, 3, 45)
    cv.set_funds(g, 10000)
    ctx.shot(g, "scop_before")
    g.charge_power(1, "super")
    g.e.wait(10)
    g.open_map_menu()
    g.choose("Super", g.MAP_MENU)
    shots = burst(ctx, g, "scop_f", 300, 2)
    d = os.path.dirname(shots[0])
    # the quote box: the last frame whose box shows both lines (the box closes into the next scene on the frames after the text)
    cream = [n for n in shots if stats(n)[2] > 0.9 and stats(n)[0] < 0.07]
    full = [n for n in cream if len(quote_extent(n)) == 2]
    ctx.require(full, "a frame with the quote box typed out in full")
    lines, widths = expected_quote()
    got = quote_extent(full[-1])
    ctx.check(all(abs(a - b) <= 3 for a, b in zip(got, widths)), f"both quote lines are typed out in full and are her own ({lines}): {got} vs {widths}")
    shutil.copyfile(full[-1], os.path.join(d, "scop_quote.bmp"))
    # the cut-in: frames with her figure in (most of the dark outline), the name typed in one letter at a time before its bars wipe it out
    dark = {n: figure_dark(n) for n in shots}
    most = max(dark.values())
    figure_in = [n for n in shots if dark[n] >= 0.6 * most and stats(n)[0] > 0.0]
    ctx.require(figure_in, "cut-in frames")
    ext = {n: name_extent(n) for n in figure_in}
    full_w = max(ext.values())
    whole = [n for n in figure_in if ext[n] >= 0.98 * full_w][0]
    mid = [n for n in figure_in if 0.35 * full_w <= ext[n] <= 0.65 * full_w]
    ctx.log(f"name widths {sorted(set(ext.values()))}: whole {os.path.basename(whole)} ({full_w}), mid frames {len(mid)}")
    shutil.copyfile(whole, os.path.join(d, "scop_cutin.bmp"))
    shutil.copyfile((mid or [whole])[0], os.path.join(d, "scop_cutin_mid.bmp"))
    ctx.require(g.e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "the power is on")
    g.wait_for_input()
    ctx.shot(g, "scop_after")
    ctx.eq(g.unit_at(3, 3)["hp"], 80, "the Infantry 45 (rounded up to 5 HP) -> 80 (3 HP healed)")
    ctx.eq(cv.funds(g), 10000, "no funds are paid")


@test(modes=("ds",))
def aria_pics_battle_header(ctx):
    """Aria's Tank attacks Andy's Tank with the battle scene on (animations "a"): frames through the exchange; the header carries her mini face."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(1, "infantry", 3, 3).unit(2, "infantry", 25, 15)
    g = ctx.start(m, ["aria", "andy"], humans=(1, 2), visuals="a")
    ctx.shot(g, "bh_before")
    e = g.e
    g.select(10, 10)
    g.move_to(10, 10)
    g.choose("Fire", g.ACTION_MENU)
    g.pick_target(11, 10)
    names = []
    for k in range(40):
        names.append(ctx.shot(g, f"bh_f{k:02d}"))
        e.wait(10)
    g.wait_for_input()
    ctx.shot(g, "bh_after")
    # the frame with the most of the scene's header drawn (the header is dark blue on top): keep the one with the most distinct colours in the top rows
    def header_ink(n):
        rows = read_bmp(n)
        return len({p for r in rows[0:24] for p in r})
    best = max(names, key=header_ink)
    shutil.copyfile(best, os.path.join(os.path.dirname(best), "bh_header.bmp"))
    ctx.log(f"header frame {os.path.basename(best)}")


@test(modes=("ds",))
def aria_pics_co_select_grid(ctx):
    """The War Room's CO screen in Dual Strike's grid, the cursor on Aria (Survival and Champion use the same screen)."""
    from aw2test import warroom as wr
    from tests.test_ds_coselect import war_room_co_screen
    e, g = war_room_co_screen(ctx, True)
    wr.go_to(e, ARIA)
    e.wait(60)
    ctx.eq(wr.highlighted(e)[1], ARIA, "the game's cursor is on Aria")
    ctx.shot(g, "grid_aria")
    e.close()


@test(modes=("ds",))
def aria_pics_hq_is_orange_stars(ctx):
    """Her HQ is Orange Star's: army 1 is Aria and the HQ picture at the map's corner is drawn exactly as Nell's and Andy's, and not as Black Hole's (Hawke's)."""
    tiles = {}
    for co in ("aria", "nell", "andy", "hawke"):
        m = ctx.map()
        m.unit(1, "tank", 3, 3).unit(2, "tank", 20, 12)
        g = ctx.start(m, [co, "olaf"])
        g.goto(0, 0)
        g.e.wait(60)
        ctx.shot(g, f"hq_{co}")
        rows = read_bmp(os.path.join(ctx.out, f"hq_{co}.bmp"))
        tiles[co] = [row[2:14] for row in rows[92:112]]
    ctx.check(tiles["aria"] == tiles["nell"] and tiles["aria"] == tiles["andy"], "Aria's HQ at army 1's corner is drawn exactly as Nell's and Andy's (Orange Star's)")
    ctx.check(tiles["aria"] != tiles["hawke"], "and is not Black Hole's (Hawke's)")


@test(modes=("ds",))
def aria_pics_co_page_one(ctx):
    """Aria's CO page 1 (her description, the Hit and Miss line) from the map menu's CO entry: `co_page1.bmp`, for `aw2dev bh2 integration`."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, ["aria", "andy"])
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    g.e.wait(110)
    ctx.shot(g, "co_page1")
    g.e.close()


@test(modes=("ds",))
def aria_pics_co_pages(ctx):
    """Aria's CO pages from the map menu's CO entry, one picture per page (DOWN turns the page): `co_page_N.bmp` (the day-to-day page carries Vengeance's description)."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, ["aria", "andy"])
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    g.e.wait(110)
    ctx.shot(g, "co_page_0")
    for k in range(1, 5):
        g.e.press("DOWN", 4)
        g.e.wait(70)
        ctx.shot(g, f"co_page_{k}")
    g.e.close()
