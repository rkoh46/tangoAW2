"""The build menu (a factory, port or airport) of an army with a tag
partner (crate::tag_ui): the partner's strip stays out of the menu, and the
unit pictures are not touched by the face the strip borrows. Pack only."""

import struct

from aw2test.harness import test
from aw2test import ram, tag
from aw2test import rom as romlib


def five_battle(ctx, cos, partners, props, humans=(1,)):
    """A five-army battle (Black Hole the fifth) on the harness's plains;
    `props` is [(kind, x, y)] of army 1's properties."""
    m = ctx.map(hq=((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19)))
    m.terrain(15, 10, 0x1B4)
    m.unit(5, "infantry", 16, 10)
    m.colours = [5, 1, 2, 3, 4]
    for kind, x, y in props:
        m.terrain(x, y, kind, 1)
    g = ctx.boot_teams(m)
    e = g.e
    e.wait(30)
    for a, p in enumerate(partners, 1):
        tag.set_teams_partner(e, a, p)
    g.set_teams(cos, set(humans))
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    return g


def read_shot(ctx, g, name):
    ctx.shot(g, name)
    return open(f"{ctx.out}/{name}.bmp", "rb").read()


def oam_sprites(e):
    import struct
    b = e.read(0x07000000, 0x400)
    out = []
    for i in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", b, 8 * i)
        if (a0 >> 8) & 3 != 2 and (a0 & 0xFF) < 160:
            out.append((a0, a1, a2))
    return out


STRIP_FACE = 0x309  # crate::tag_ui: the partner's face on the CO panel's strip (OBJ tile, palette 5)


def strip_up(e):
    return any((a2 & 0x3FF) == STRIP_FACE and a2 >> 12 == 5 for _, _, a2 in oam_sprites(e))


def build_menus(ctx, five, pair, tag_name):
    """Army 1's factory, airport and port in a battle (two armies, or five
    with Black Hole the fifth), army 1 Sturm (+ Von Bolt) when `pair`: every
    unit of each build menu looked at (the screen's bytes) while the menu is
    up; returns {(kind, index): bytes} and the strips seen."""
    props = [("base", 5, 3), ("airport", 5, 5), ("port", 5, 7)]
    partners = ["vonbolt" if pair else None] + [None] * (4 if five else 1)
    if five:
        g = five_battle(ctx, ["sturm", "andy", "eagle", "sonja", "vonbolt"], partners, props)
    else:
        m = ctx.map()
        for kind, x, y in props:
            m.terrain(x, y, kind, 1)
        g = ctx.boot_teams(m)
        for a, p in enumerate(partners, 1):
            tag.set_teams_partner(g.e, a, p)
        g.set_teams(["sturm", "andy"], {1})
        g.teams_to_rules()
        g.set_rules()
        g.start_battle()
        g.wait_for_input()
    e = g.e
    shots, strips = {}, []
    ctx.eq(tag.partner(e, 1) is not None, pair, f"{tag_name}: army 1's pair")
    for kind, y in (("base", 3), ("airport", 5), ("port", 7)):
        g.wait_idle()
        g.goto(5, y)
        strip_before = strip_up(e)
        e.press("A", 4)
        e.wait(60)
        n = 0
        while e.u8(0x02023830 + 4 * n):
            n += 1
        ctx.check(n >= 6, f"{tag_name} {kind}: a build menu of {n} units")
        for k in range(n):
            shots[(kind, k)] = read_shot(ctx, g, f"{tag_name}_{kind}_{k:02d}")
            strips.append(strip_up(e))
            e.press("DOWN", 4)
            e.wait(20)
        e.press("B", 4)
        e.wait(60)
        g.wait_idle()
        strips.append(("closed", strip_up(e)))
    return g, shots, strips


@test(modes=("ds",))
def build_menu_with_tag_pair(ctx):
    """The build menu (a factory, port or airport: AW2's list under its CO
    panel, the unit's picture on the right) of an army with a tag partner,
    on a two-army and a five-army map (Black Hole the fifth): the partner's
    strip (under the panel, over the list) is left out while the menu is up
    and comes back when it closes, and the unit pictures (OBJ tiles 0x2E8..0x327
    and the labels' palette 5, which the strip borrowed) are as in a game
    without the pair: every screen of every unit of all three menus the same
    byte for byte as the same game with the partner none."""
    for five in (False, True):
        label = "five" if five else "two"
        _, pair, strips = build_menus(ctx, five, True, f"{label}_pair")
        _, single, _ = build_menus(ctx, five, False, f"{label}_single")
        ctx.eq(sorted(pair), sorted(single), f"{label}: the same menus")
        ctx.check(not any(s is True for s in strips), f"{label}: no strip while a build menu is up")
        ctx.check(all(s[1] for s in strips if isinstance(s, tuple)), f"{label}: the strip is back after each menu")
        bad = [k for k in pair if pair[k] != single[k]]
        ctx.check(not bad, f"{label}: screens differ from the game without the pair: {bad[:6]} ({len(bad)} of {len(pair)})")


@test(modes=("ds",))
def unit_info_with_tag_pair(ctx):
    """The unit information screen (R on a unit; the Oozium's picture and
    labels) of an army with a partner is the same as without."""
    res = {}
    for pair in (True, False):
        m = ctx.map()
        m.unit(1, "oozium", 10, 10).unit(1, "tank", 10, 12)
        g = ctx.boot_teams(m)
        tag.set_teams_partner(g.e, 1, "vonbolt" if pair else None)
        g.set_teams(["sturm", "andy"], {1})
        g.teams_to_rules()
        g.set_rules()
        g.start_battle()
        g.wait_for_input()
        e = g.e
        g.goto(10, 10)
        e.wait(20)
        e.press("R", 30)
        e.wait(40)
        res[pair] = read_shot(ctx, g, f"info_{'pair' if pair else 'single'}")
    ctx.check(res[True] == res[False], "the unit information screen with a partner is the one without")
