"""Every unit is on offer in the custom campaigns (`-k campaign_units`): the Silver Nova, BH and BH2 Campaigns' build menus and the CO page's unit chart.

AW2's campaign hides the Neotank until its nation's story flag is set (`sub_080261E8`, called by the build menu at `0x0802D6CA` and by the CO page's unit chart at
`0x0808571C`, which then picks the list with a blank slot where the Neotank goes). The custom campaigns run on AW2's campaign mode with stories of their own, so they
inherited the hiding: `crate::gauntlet::neotank_open` answers yes in the Gauntlet and in every custom campaign (the Dual Strike Campaign and AW2's own are untouched)."""

import os

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import bhcampaign as bh
from aw2test import escampaign as es
from aw2test import ram
from aw2test.harness import test
from tests.test_co_grid import AIR_SEA, GROUND, PAGE, draw, trace_file
from tests.test_es_rules import own
from tests.test_gauntlet_build_menu import PIPERUNNER, NEOTANK, open_menu

# What a base builds in the Dual Strike pack's order (the Piperunner needs a pipe cell: never on a plain base).
BASE_UNITS = sorted(u for u in GROUND if u and u != PIPERUNNER)


def base_cell(g, e):
    w, h = e.u16(ram.MAP_PTR), e.u16(ram.MAP_PTR + 2)
    for y in range(h):
        for x in range(w):
            if g.terrain_class(x, y) & 0x1F == 14 and g.unit_at(x, y) is None:
                return x, y
    return None


def build_menu(ctx, g, e, label):
    """A base handed to army 1 (the map's first free one), its build menu's unit types."""
    cell = base_cell(g, e)
    ctx.require(cell, f"{label}: the map has a free base")
    own(e, cell[0], cell[1], g.current_army())
    g.wait_idle()
    g.goto(*cell)
    e.press("A", 4)
    e.wait(60)
    for _ in range(3):
        e.press("DOWN", 4)
        e.wait(10)
    ctx.shot(g, f"menu_{label.replace(' ', '_')}")
    e.press("B", 4)
    e.wait(60)
    g.wait_idle()
    rows = open_menu(g, e, *cell)
    ctx.log(f"{label}: base {cell} offers {rows}")
    return rows


def chart(ctx, g, label):
    """The CO page's unit chart (AW2's own, as drawn with the setting off): the unit lists of its two pages."""
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    g.e.wait(90)
    for _ in range(6):
        if g.e.u32(PAGE) == 4:
            break
        g.e.press("DOWN", 6)
        g.e.wait(45)
    ctx.eq(g.e.u32(PAGE), 4, f"{label}: the chart's first page")
    g.e.wait(30)
    _, _, slots = draw(g)
    first = [g.e.u16(s["entry"]) for s in slots]
    g.e.press("DOWN", 6)
    g.e.wait(45)
    _, _, slots = draw(g)
    second = [g.e.u16(s["entry"]) for s in slots]
    ctx.log(f"{label}: chart {first} / {second}")
    return first, second


def check(ctx, g, e, label):
    rows = build_menu(ctx, g, e, label)
    ctx.eq(sorted(rows), BASE_UNITS, f"{label}: the base offers every unit (the Neotank too)")
    ctx.check(NEOTANK in rows, f"{label}: the base offers the Neotank {rows}")
    first, second = chart(ctx, g, label)
    ctx.eq(first, GROUND, f"{label}: the chart's ground page has no blank slot for the Neotank")
    ctx.eq(second, AIR_SEA, f"{label}: the chart's air and naval page is whole")


def env(ctx, base):
    return dict(base, AW2_TRACE=trace_file(ctx), TANGOAW2_DS_GRAPHICS="0")


@test(modes=("ds",))
def campaign_units_silver_nova_m1(ctx):
    """Tabitha's M1 (Landfall): the chart and a base of the map offer every unit."""
    e, g, d = es.enter(ctx, 1, env=env(ctx, {}))
    check(ctx, g, e, "SN M1")


@test(modes=("ds",))
def campaign_units_silver_nova_m2(ctx):
    e, g, d = es.enter(ctx, 2, env=env(ctx, {}))
    check(ctx, g, e, "SN M2")


@test(modes=("ds",))
def campaign_units_bh_m1(ctx):
    e, g, d = a2.boot(ctx, 0, 0xFF, at=a2.M[1], env=env(ctx, {}))
    d.wait_world_map()
    a2.open_mission(ctx, e, g, d, a2.M[1], [], "m1", shots=())
    d.wait_control()
    check(ctx, g, e, "BH M1")


@test(modes=("ds",))
def campaign_units_bh2_m1(ctx):
    e, g, d = b2.enter(ctx, 1, env=env(ctx, {}))
    check(ctx, g, e, "BH2 M1")
