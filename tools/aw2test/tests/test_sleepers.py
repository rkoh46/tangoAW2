"""A sleeping nation of M31's gauntlet cannot be defeated before it wakes (crate::custom_campaign::sleeping, `MissionDef::sleepers`): the player kills all four of Olaf's holding units (real attacks, the game's own
rout check runs), Olaf's army is still alive (not defeated, HQ and player record intact) and, when Nell's HQ falls, his wave lands and he has his funds."""

import importlib.util
import os

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import harness
from aw2test.harness import test

_n = len(harness.TESTS)
_spec = importlib.util.spec_from_file_location("bh2_progression_helpers4", os.path.join(os.path.dirname(__file__), "test_bh2_progression.py"))
bp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bp)
del harness.TESTS[_n:]


def alive(e, g, army):
    p = g.players_base + 0x3C * army
    return e.u8(p + 0x1B) != 0 and e.u16(p + 0x14) == 0


@test(name="bh2_m31_sleeping_nation_survives_losing_its_holders", modes=("ds",))
def bh2_m31_sleeping_nation_survives_losing_its_holders(ctx):
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    from aw2test import bhact2 as a2
    a2.intro(ctx, e, d, "m31", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    from tests.test_bh2_review import home
    home(g, e)
    e.wait(60)
    holders = g.units(army=2)
    ctx.eq(len(holders), 4, "Olaf has his four holding units")
    ctx.check(alive(e, g, 2), "Olaf is alive")
    mine = [u for u in g.units(army=5) if u["type"] == 1 and not u["flags"] & 0x08]
    for k, h in enumerate(holders):
        g._units_base = g._players_base = None
        cur = g.unit_at(h["x"], h["y"])
        if cur is None or cur["army"] != 2:
            continue
        a = g.unit_addr(cur["id"])
        e.w16(a + 4, (e.u16(a + 4) & ~0x7F) | 1)                   # (one hit point)
        att = mine[k]
        aa = g.unit_addr(att["id"])
        e.w8(aa, 4)                                                  # (a Tank: it fires, and it is put beside its target)
        e.w8(aa + 1, 0)
        spot = next(c for c in ((h["x"] + 1, h["y"]), (h["x"] - 1, h["y"]), (h["x"], h["y"] + 1), (h["x"], h["y"] - 1)) if g.unit_at(*c) is None)
        d.place_unit(g.unit(att["id"]), *spot)
        e.wait(4)
        g.attack(spot, spot, (h["x"], h["y"]))
        d.dialogue()
    g._units_base = g._players_base = None
    ctx.eq(len(g.units(army=2)), 0, "all of Olaf's holding units are dead")
    e.wait(120)
    ctx.check(alive(e, g, 2), "Olaf is not defeated: no units, but asleep")
    ctx.check(not e.u8(dc.LAST_RESULT), "the mission goes on")
    # Nell's HQ falls: his wave lands and he has his funds
    bp.capture(ctx, e, g, d, bp.HQS[0][1], 5)
    bp.settle(e, g, d)
    g._units_base = g._players_base = None
    n = len(g.units(army=2))
    ctx.check(n >= 10, f"Olaf's wave landed ({n} units)")
    ctx.check(alive(e, g, 2), "Olaf is alive after waking")
    ctx.check(e.u32(g.players_base + 0x3C * 2) >= 20000, f"and has his funds ({e.u32(g.players_base + 0x3C * 2)})")
    e.close()
