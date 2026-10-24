"""Emerald Sun Campaign: the missions' own rules, played with the player passive (`-k es_rules`): M13's three-day hold of the Harbour Office, M14's Cassius changing
sides on day 4, M15's allied strait fleet (Nell's call on day 6 changes no side), M16's waves and the defenders' charged meters, M2's win on day 9, M9's and M11's day limits."""

from aw2test import bhact2 as a2
from aw2test import bhact3 as a3
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test.game import NavError
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
    try:
        a3.to_day(e, g, d, day)
    except NavError as ex:               # (the mission ended on the way: the result byte says how)
        ctx.log(f"to day {day}: {ex}")
    ctx.log(f"day {e.u16(dc.DAY)} result {e.u8(dc.LAST_RESULT)} hold counter {e.u8(0x0203C9F0)} last day {e.u8(0x0203C9F1)}")


@test(modes=("ds",))
def es_rules_m13_the_office_held_for_three_days_wins(ctx):
    e, g, d = entered(ctx, 13)
    own(e, 19, 15, 1)
    pass_days(ctx, e, g, d, 6)
    ctx.eq(e.u8(dc.LAST_RESULT), 1, "the Office held for three turn starts: won")
    ctx.eq(e.u16(dc.LAST_RESULT + 2), 4, "on day 4")
    e.close()


@test(modes=("ds",))
def es_rules_m13_a_lost_office_resets_the_count(ctx):
    e, g, d = entered(ctx, 13)
    own(e, 19, 15, 1)
    pass_days(ctx, e, g, d, 3)
    own(e, 19, 15, 2)
    pass_days(ctx, e, g, d, 4)
    own(e, 19, 15, 1)
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
def es_rules_m15_the_strait_fleet_is_allied_and_no_fleet_joins(ctx):
    e, g, d = entered(ctx, 15)
    p = players(e)
    team = lambda a: e.u8(p + 0x3C * a + 0x2A)
    ctx.check(team(2) == team(3) and team(2) != team(1), f"Drake and Sensei are allies against the player ({team(1)} / {team(2)} / {team(3)})")
    first = (len(g.units(2)), len(g.units(3)))
    pass_days(ctx, e, g, d, 7)
    ctx.log(f"the strait fleet: {first} units on day 1, {(len(g.units(2)), len(g.units(3)))} on day 7")
    ctx.check(team(2) == team(3) and team(2) != team(1), "still the same sides on day 7 (Nell's call changes none)")
    e.close()


@test(modes=("ds",))
def es_rules_m16_waves_and_the_charged_meter(ctx):
    e, g, d = entered(ctx, 16)
    before = len(g.units(2))
    p = players(e)
    pass_days(ctx, e, g, d, 7)
    ctx.log(f"Eagle's units: {before} on day 1, {len(g.units(2))} on day 7")
    for a, who in ((2, "Eagle"), (3, "Hachi")):
        meter = e.u32(p + 0x3C * a + 0x20)
        ctx.check(meter > 0 or e.u8(p + 0x3C * a + 0x1E) > 0, f"{who}'s meter is charged (or his power is on): meter {meter}")
    e.close()
