"""M31: a sleeping nation earns nothing (crate::custom_campaign::cut_funds): over five days (the player ends each turn at once), Olaf's, Kanbei's and Eagle's funds are 0 at every look, their own turns
included (each HQ's income is taken back as it comes in), while Nell's HQ stands; the day-5 scene is logged too (a repeating turn-start SetFunds took the funds back on day 1 only: why the cut is crate::custom_campaign::cut_funds)."""

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test.harness import test


@test(name="bh2_m31_sleeping_nations_earn_nothing", modes=("ds",))
def bh2_m31_sleeping_nations_earn_nothing(ctx):
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    p = g.players_base
    funds = lambda: {a: e.u32(p + 0x3C * a) for a in (2, 3, 4)}
    last, day0, seen = None, e.u16(dc.DAY), []
    for _ in range(20000):
        e.wait(10)
        if g.current_army() == 5 and d.in_battle() and not d.scripts_running():
            for _ in range(40):          # (a turn-start scene shows within a few seconds of the turn's start)
                if d.scripts_running():
                    ctx.log(f"scene: day {e.u16(dc.DAY)} army 5 funds {tuple(funds().values())}")
                    break
                e.wait(10)
            try:
                d.wait_control()
                d.end_turn()             # (the player, a human, ends each turn at once)
            except Exception as ex:
                ctx.log(f"end turn: {ex}")
        if d.scripts_running():
            if not seen or seen[-1] != ("scene", e.u16(dc.DAY)):
                ctx.log(f"scene: day {e.u16(dc.DAY)} army {g.current_army()}")
                seen.append(("scene", e.u16(dc.DAY)))
            e.press("A", 4)
        row = (e.u16(dc.DAY), e.u8(0x0203_0000) if False else g.current_army(), tuple(funds().values()))
        if row != last:
            ctx.log(f"day {row[0]} army {row[1]} funds 2/3/4 {row[2]}")
            last = row
            seen.append(row)
        if row[0] - day0 >= 5:
            break
    seen = [r for r in seen if r[0] != "scene"]
    ctx.check(seen and all(r[2] == (0, 0, 0) for r in seen), "the sleeping nations' funds are 0 throughout: " + str(sorted({r[2] for r in seen})))
    e.close()
