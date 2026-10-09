"""Who leads a tag pair in the BH Campaign: on a free pair (M12, M17, M23, M24) the FIRST pick leads and the second is the
partner, whatever the COs' ids; on a fixed pair the first CO of the CoSpec leads (M10 Sturm + Hawke, M11 Von Bolt + Hawke,
M16 Koal + Kindle, M22 Jugger + Flak). The dialogue's @IF (lead) and @PARTNER groups key on exactly this."""

from aw2test import bhact3 as a3
from aw2test import bhact4 as a4
from aw2test import bhcampaign as bh
from aw2test import tag
from aw2test.harness import test

ST, VB, HK, KO, KI, JU, FL = bh.STURM, bh.VON_BOLT, bh.HAWKE, bh.KOAL, bh.KINDLE, bh.JUGGER, bh.FLAK
FREE = {12: ([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11], 0b111, [(ST, HK), (HK, ST), (VB, ST), (ST, VB), (HK, VB), (VB, HK)])}


def seat(e, g):
    p = tag.partner(e, 1)
    return g.player(1)["co"], (p["co"] if p else None)


@test(modes=("ds",))
def bh_pair_seating_free_pair_first_pick_leads(ctx):
    won, roster, pairs = FREE[12]
    for pair in pairs:
        mask = 0
        for k in won:
            mask |= 1 << a3.M[k]
        e, g, d = a3.boot(ctx, mask, roster, picks={a3.M[12]: 2}, at=a3.M[12])
        d.pick_mission()
        picked = a4.pick_cos(d, e, 2, list(pair))
        ctx.eq(picked, list(pair), f"M12 {pair}: the screen's two picks")
        for _ in range(600):
            if d.in_battle() and e.u32(0x0849_9598) != 0:
                break
            e.wait(10)
        g._units_base = g._players_base = None
        ctx.eq(seat(e, g), pair, f"M12: the first pick {pair[0]} leads, the second {pair[1]} is the partner")
        e.close()


@test(modes=("ds",))
def bh_pair_seating_m17_first_pick_leads(ctx):
    mask = (1 << a3.M[17]) - 1
    for pair in ((ST, VB), (VB, ST), (HK, KO), (KO, HK)):
        e, g, d = a3.boot(ctx, mask, 0x7F, picks={a3.M[17]: 2}, at=a3.M[17])
        d.pick_mission()
        picked = a4.pick_cos(d, e, 2, list(pair))
        ctx.eq(picked, list(pair), f"M17 {pair}: the screen's two picks")
        for _ in range(600):
            if d.in_battle() and e.u32(0x0849_9598) != 0:
                break
            e.wait(10)
        g._units_base = g._players_base = None
        ctx.eq(seat(e, g), pair, f"M17: the first pick {pair[0]} leads, the second {pair[1]} is the partner")
        e.close()


FIXED = {10: (ST, HK), 11: (VB, HK), 16: (KO, KI), 22: (JU, FL)}


def fixed_case(n):
    def fn(ctx):
        mask = (1 << a3.M[n]) - 1
        e, g, d = a3.boot(ctx, mask, 0xFFF, picks={a3.M[n]: 0}, at=a3.M[n])
        d.pick_mission()
        for _ in range(1200):
            if d.in_battle() and e.u32(0x0849_9598) != 0:
                break
            e.press("A", 4) if d.scripts_running() else None
            e.wait(10)
        ctx.require(d.in_battle(), f"M{n}: the battle loaded")
        g._units_base = g._players_base = None
        e.wait(120)
        g._units_base = g._players_base = None
        ctx.eq(seat(e, g), FIXED[n], f"M{n}: the first CO of the pair leads")
        e.close()
    fn.__name__ = f"bh_pair_seating_m{n}_fixed_pair_first_leads"
    test(modes=("ds",))(fn)


for _n in FIXED:
    fixed_case(_n)
