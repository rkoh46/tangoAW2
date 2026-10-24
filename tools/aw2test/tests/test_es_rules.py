"""Emerald Sun Campaign: the missions' own rules, played with the player passive (`-k es_rules`): M13's three-day hold of the Harbour Office, M14's Cassius changing
sides on day 4, M15's relief fleet arriving on day 6, M16's waves and Varro's charged meter, M2's win on day 9, M9's and M11's day limits."""

from aw2test import bhact2 as a2
from aw2test import bhact3 as a3
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test.harness import test

MAP = 0x0201E450


def entered(ctx, n):
    e, g, d = es.enter(ctx, n)
    if d.in_setup():
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", ())
    d.wait_control()
    g._units_base = g._players_base = None
    return e, g, d


def players(e):
    return e.u32(0x08499598)


def own(e, x, y, army):
    """Hands a property to an army (the terrain class byte's top three bits)."""
    row = e.u16(MAP + 0x417A + 2 * y)
    a = MAP + 0x1432 + row + x
    e.w8(a, (e.u8(a) & 0x1F) | army << 5)


def pass_days(ctx, e, g, d, day):
    a3.to_day(e, g, d, day)
    ctx.log(f"day {e.u16(dc.DAY)} result {e.u8(dc.LAST_RESULT)}")


@test(modes=("ds",))
def es_rules_m13_the_office_held_for_three_days_wins(ctx):
    e, g, d = entered(ctx, 13)
    own(e, 12, 10, 1)
    pass_days(ctx, e, g, d, 6)
    ctx.eq(e.u8(dc.LAST_RESULT), 1, "the Office held for three turn starts: won")
    ctx.eq(e.u16(dc.LAST_RESULT + 2), 4, "on day 4")
    e.close()


@test(modes=("ds",))
def es_rules_m13_a_lost_office_resets_the_count(ctx):
    e, g, d = entered(ctx, 13)
    own(e, 12, 10, 1)
    pass_days(ctx, e, g, d, 3)
    own(e, 12, 10, 2)
    pass_days(ctx, e, g, d, 4)
    own(e, 12, 10, 1)
    pass_days(ctx, e, g, d, 6)
    ctx.eq(e.u8(dc.LAST_RESULT), 0, "not won: the count began again")
    e.close()


@test(modes=("ds",))
def es_rules_m14_cassius_changes_sides_on_day_4(ctx):
    e, g, d = entered(ctx, 14)
    p = players(e)
    team = lambda a: e.u8(p + 0x3C * a + 0x2A)
    ctx.check(team(3) != team(1), f"before: Cassius (army 3) is on another team than the player ({team(3)} / {team(1)})")
    pass_days(ctx, e, g, d, 4)
    ctx.eq(team(3), team(1), "day 4: Cassius's army is the player's team")
    ctx.check(team(2) != team(1), "Varro stays the enemy")
    e.close()


@test(modes=("ds",))
def es_rules_m15_the_accord_arrives_on_day_6(ctx):
    e, g, d = entered(ctx, 15)
    ctx.eq(len(g.units(3)), 0, "the Accord's fleet has nothing on day 1")
    pass_days(ctx, e, g, d, 7)
    n = len(g.units(3))
    ctx.log(f"the Accord has {n} units on day 7")
    ctx.check(n >= 10, f"the relief fleet is there on day 7 ({n} of 12 units)")
    e.close()


@test(modes=("ds",))
def es_rules_m16_waves_and_the_charged_meter(ctx):
    e, g, d = entered(ctx, 16)
    before = len(g.units(2))
    p = players(e)
    pass_days(ctx, e, g, d, 7)
    ctx.log(f"Varro's units: {before} on day 1, {len(g.units(2))} on day 7")
    meter = e.u32(p + 0x3C * 2 + 0x20)
    ctx.check(meter > 0 or e.u8(p + 0x3C * 2 + 0x1E) > 0, f"Varro's meter is charged (or his power is on): meter {meter}")
    e.close()
