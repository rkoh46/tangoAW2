"""The CO page (map menu > CO) shows a tag army's partner, as Dual Strike's
CO page gives each CO of a pair its own tab (crate::tag_extras: RIGHT goes
from the active CO to the partner, then to the next army's; LEFT the other
way). Pack only."""

from aw2test.harness import test
from aw2test import ram, tag
from aw2test import rom as romlib

EXTRAS = 0x0203F500  # crate::tag_extras::STATE
PARTNER_VIEW = EXTRAS + 0x10


def tag_battle(ctx, cos, partners, units=()):
    m = ctx.map()
    for u in units:
        m.unit(*u)
    g = ctx.boot_teams(m)
    for a, p in enumerate(partners, 1):
        tag.set_teams_partner(g.e, a, p)
    g.set_teams(cos, {1})
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    return g


def cos_of(g, army):
    p = tag.partner(g.e, army)
    return g.player(army)["co"], (p["co"] if p else None)


@test(modes=("ds",))
def co_page_shows_tag_partner(ctx):
    """The CO page of an army with a partner has a second page for the
    partner (RIGHT: the active CO, then the partner, then the next army;
    LEFT back the same way), as Dual Strike's tab a CO. The page shows the
    partner's CO (the army's two COs swapped while it does, AW2's page
    reading the army's player block) and everything is as it was when the
    page closes."""
    andy, max_, olaf = romlib.co_id("andy"), romlib.co_id("max"), romlib.co_id("olaf")
    g = tag_battle(ctx, ["andy", "olaf"], ["max", None], units=[(1, "tank", 10, 4)])
    e = g.e
    ctx.eq(cos_of(g, 1), (andy, max_), "army 1 is Andy + Max")
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    e.wait(90)
    ctx.eq(e.u8(PARTNER_VIEW), 0, "the page opens on the active CO")
    ctx.shot(g, "page_active")
    e.press("RIGHT", 6)
    e.wait(60)
    ctx.eq(e.u8(PARTNER_VIEW), 1, "RIGHT: the partner's page")
    ctx.eq(cos_of(g, 1), (max_, andy), "the page reads Max (the pair swapped)")
    ctx.shot(g, "page_partner")
    e.press("RIGHT", 6)
    e.wait(60)
    ctx.eq(e.u8(PARTNER_VIEW), 0, "RIGHT again: the next army")
    ctx.eq(cos_of(g, 1), (andy, max_), "army 1's pair as it was")
    ctx.shot(g, "page_army2")
    e.press("RIGHT", 6)
    e.wait(60)
    ctx.eq(e.u8(PARTNER_VIEW), 0, "army 2 has no partner: RIGHT wraps to army 1's active CO")
    e.press("LEFT", 6)
    e.wait(60)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 1)), (0, (andy, max_)), "LEFT: army 2 (single)")
    e.press("LEFT", 6)
    e.wait(60)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 1)), (1, (max_, andy)), "LEFT: army 1's partner first")
    e.press("LEFT", 6)
    e.wait(60)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 1)), (0, (andy, max_)), "LEFT: its active CO")
    e.press("RIGHT", 6)
    e.wait(60)
    ctx.eq(e.u8(PARTNER_VIEW), 1, "RIGHT: the partner again")
    e.press("B", 6)
    e.wait(120)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 1)), (0, (andy, max_)), "closed from the partner's page: the pair as it was")
    ctx.eq(cos_of(g, 2), (olaf, None), "army 2 untouched")
    ctx.shot(g, "map_after")


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


@test(modes=("ds",))
def co_page_five_armies_partner(ctx):
    """A five-army battle (Black Hole the fifth, Sturm + Von Bolt): RIGHT
    on the CO page goes through the armies to Black Hole's Sturm, then Von
    Bolt (the page shows him), then back to Orange Star; LEFT from Orange
    Star lands on Von Bolt first."""
    sturm, vonbolt, andy = romlib.co_id("sturm"), romlib.co_id("vonbolt"), romlib.co_id("andy")
    g = five_battle(ctx, ["andy", "olaf", "eagle", "sonja", "sturm"], [None] * 4 + ["vonbolt"], [])
    e = g.e
    ctx.eq(cos_of(g, 5), (sturm, vonbolt), "Black Hole is Sturm + Von Bolt")
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    e.wait(90)
    for n in range(4):
        e.press("RIGHT", 6)
        e.wait(60)
        ctx.eq(e.u8(PARTNER_VIEW), 0, f"army {n + 2}: no partner")
    ctx.shot(g, "five_sturm")
    e.press("RIGHT", 6)
    e.wait(60)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 5)), (1, (vonbolt, sturm)), "RIGHT from Black Hole's Sturm: Von Bolt's page")
    ctx.shot(g, "five_vonbolt")
    e.press("RIGHT", 6)
    e.wait(60)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 5), cos_of(g, 1)[0]), (0, (sturm, vonbolt), andy), "RIGHT: Orange Star's Andy; Black Hole's pair as it was")
    e.press("LEFT", 6)
    e.wait(60)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 5)), (1, (vonbolt, sturm)), "LEFT from Orange Star: Black Hole's Von Bolt first")
    e.press("B", 6)
    e.wait(120)
    ctx.eq((e.u8(PARTNER_VIEW), cos_of(g, 5)), (0, (sturm, vonbolt)), "closed: the pair as it was")
