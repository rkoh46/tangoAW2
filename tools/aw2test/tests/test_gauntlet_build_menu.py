"""The Gauntlet's build menus (a base, an airport, a port: `-k gauntlet_build_menu`): every Gauntlet map offers the units a Versus map with the Dual Strike pack offers.

AW2's campaign hides the Neotank until its nation's story flag is set (`sub_080261E8`, called by the build menu at `0x0802D6CA`: in campaign mode only, a colour's flag 0x65..0x68; Black Hole's colour never). The Gauntlet
runs as a campaign, so it inherited the hiding: `crate::gauntlet::neotank_open` answers yes in a Gauntlet session."""

from aw2test import dscampaign as dc
from aw2test import gauntlet as ga
from aw2test import gauntlet_maps as gm
from aw2test import ram
from aw2test import tag
from aw2test.harness import test

MENU = 0x02023830            # the build menu's rows: 4 bytes each (+0 the unit type, +1 enabled), their count at MENU_COUNT
MENU_COUNT = 0x0300055A
PIPERUNNER, NEOTANK = 9, 8
KINDS = {14: "base", 10: "airport", 11: "port"}      # the terrain classes (inspect.rs build_menu)
INFO = {
    0: gm.MapInfo(0, "gauntlet_01", "Cinder Sea", 1, (3, 18)),
    1: gm.MapInfo(1, "gauntlet_02", "Iron Crown", 5, (4, 22)),
    **gm.MAPS,
}


def menu_rows(e):
    n = e.u16(MENU_COUNT)
    return [e.u8(MENU + 4 * k) for k in range(n)]


def open_menu(g, e, x, y):
    """The cursor on (x, y), A: the build menu's unit types in the order shown (empty when no menu came up); B closes it."""
    g.wait_idle()
    g.goto(x, y)
    e.press("A", 4)
    e.wait(60)
    rows = menu_rows(e)
    e.press("B", 4)
    e.wait(60)
    g.wait_idle()
    return rows


def own_free_properties(g, e, army):
    """{kind: (x, y)}: one property of each production kind the army owns with no unit on it."""
    w, h = e.u16(ram.MAP_PTR), e.u16(ram.MAP_PTR + 2)
    found = {}
    for y in range(h):
        for x in range(w):
            t = g.terrain_class(x, y)
            kind = KINDS.get(t & 0x1F)
            if kind and t >> 5 == army and kind not in found and g.unit_at(x, y) is None:
                found[kind] = (x, y)
    return found


def versus_menus(ctx):
    """A base, airport and port of army 1 in a Versus battle with the pack: {kind: unit types in the order shown}."""
    m = ctx.map()
    for kind, x, y in (("base", 5, 3), ("airport", 5, 5), ("port", 5, 7)):
        m.terrain(x, y, kind, 1)
    g = ctx.boot_teams(m)
    for a in (1, 2):
        tag.set_teams_partner(g.e, a, None)
    g.set_teams(["andy", "sturm"], {1})
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    out = {}
    for kind, y in (("base", 3), ("airport", 5), ("port", 7)):
        out[kind] = open_menu(g, g.e, 5, y)
    return out


def start(ctx, info):
    from tests.test_gauntlet_lines import start as start_map
    return start_map(ctx, info)


def check_map(ctx, info, expected):
    e, g, d = start(ctx, info)
    army = g.current_army()
    ctx.eq(army, info.player, f"{info.title}: the player's turn")
    props = own_free_properties(g, e, army)
    ctx.check(props, f"{info.title}: the player owns a free production property {props}")
    for kind, (x, y) in props.items():
        rows = open_menu(g, e, x, y)
        want = [t for t in expected[kind] if t != PIPERUNNER]
        got = [t for t in rows if t != PIPERUNNER]
        ctx.log(f"{info.title} {kind} at ({x}, {y}): {rows}")
        ctx.check(kind != "base" or NEOTANK in rows, f"{info.title}: the base offers the Neotank {rows}")
        ctx.eq(got, want, f"{info.title}: the {kind}'s build list is Versus' ({got} against {want})")
    return props


def versus_reference(ctx):
    exp = versus_menus(ctx)
    ctx.check(NEOTANK in exp["base"] and len(exp["base"]) >= 12, f"Versus' base list: {exp['base']}")
    return exp


@test(modes=("ds",))
def gauntlet_build_menu_cinder_sea_and_iron_crown_offer_versus_units(ctx):
    exp = versus_reference(ctx)
    for mission in (0, 1):
        check_map(ctx, INFO[mission], exp)


@test(modes=("ds",))
def gauntlet_build_menu_the_other_maps_offer_versus_units(ctx):
    exp = versus_reference(ctx)
    for mission in sorted(gm.MAPS):
        check_map(ctx, INFO[mission], exp)
