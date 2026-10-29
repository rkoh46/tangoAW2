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
        d.dialogue()
        try:
            g.attack(spot, spot, (h["x"], h["y"]))
        except Exception:
            # (a scene the mission plays, answered with A; then the attack again)
            for _ in range(30):
                e.press("A", 4)
                e.wait(20)
            d.wait_control()
            g._units_base = g._players_base = None
            g.attack(spot, spot, (h["x"], h["y"]))
        d.dialogue()
    g._units_base = g._players_base = None
    ctx.eq(len(g.units(army=2)), 0, "all of Olaf's holding units are dead")
    e.wait(120)
    ctx.check(alive(e, g, 2), "Olaf is not defeated: no units, but asleep")
    ctx.check(not e.u8(dc.LAST_RESULT), "the mission goes on")
    # Nell's HQ falls on day 10: his wave lands and he has his war chest (25,000 and nine days' savings at 1,000)
    e.w16(0x0300_4080, 10)
    bp.capture(ctx, e, g, d, bp.HQS[0][1], 5)
    bp.settle(e, g, d)
    g._units_base = g._players_base = None
    n = len(g.units(army=2))
    ctx.check(n >= 10, f"Olaf's wave landed ({n} units)")
    ctx.log("olaf record " + g.player(2)["raw"].hex() + f" units {n}")
    ctx.check(alive(e, g, 2), "Olaf is alive after waking")
    ctx.eq(e.u32(g.players_base + 0x3C * 2), 34000, "and has his war chest: 25,000 and 9 x 1,000 saved")
    e.close()


@test(name="bh2_m31_nell_routed_before_her_hq_falls", modes=("ds",))
def bh2_m31_nell_routed_before_her_hq_falls(ctx):
    """Nell's whole army dies before her HQ is taken (the game's own rout check, on a real attack): her HQ turns neutral and that is her line's fall: Olaf wakes after the next action (wave and war chest); the
    neutral HQ can still be captured (nothing wakes twice)."""
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    from tests.test_bh2_review import home
    home(g, e)
    e.wait(60)
    nell = g.units(army=1)
    for u in nell[1:]:
        d.remove_unit(u)
    g._units_base = g._players_base = None
    last = g.units(army=1)[0]
    a = g.unit_addr(last["id"])
    e.w16(a + 4, (e.u16(a + 4) & ~0x7F) | 1)
    att = next(u for u in g.units(army=5) if u["type"] == 1 and not u["flags"] & 0x08)
    aa = g.unit_addr(att["id"])
    e.w8(aa, 4)
    e.w8(aa + 1, 0)
    spot = next(c for c in ((last["x"] + 1, last["y"]), (last["x"] - 1, last["y"]), (last["x"], last["y"] + 1), (last["x"], last["y"] - 1)) if g.unit_at(*c) is None and bp.owner(e, *c) != 1 or g.unit_at(*c) is None)
    d.place_unit(g.unit(att["id"]), *spot)
    e.wait(4)
    d.dialogue()
    g.attack(spot, spot, (last["x"], last["y"]))
    bp.settle(e, g, d)
    g._units_base = g._players_base = None
    row = e.u16(dc.MAP + 0x417A + 2 * 8)
    tile = e.u16(dc.MAP + 0xA22 + 2 * (row + 8))
    p1 = g.players_base + 0x3C
    ctx.log(f"Nell routed: units {len(g.units(army=1))}, defeated {e.u16(p1 + 0x14)}, HQ (8,8) owner {bp.owner(e, 8, 8)} tile {tile:#x} class {e.u8(dc.MAP + 0x1432 + row + 8) & 0x1F:#x}, result {e.u8(dc.LAST_RESULT)}")
    ctx.shot(g, "nell_routed")
    ctx.check(not e.u8(dc.LAST_RESULT), "the mission goes on")
    ctx.eq(bp.owner(e, 8, 8), 0, "Nell's HQ is neutral")
    # (the rout runs after the attack's own after-action check: the next action, anyone's, wakes him)
    other = next(u for u in g.units(army=5) if not u["flags"] & 0x09 and u["id"] != att["id"])
    try:
        g.wait_unit(other["x"], other["y"])
    except Exception as ex:          # (the wake's scene starts at once: the map is not idle)
        ctx.log(f"after the Wait: {ex}")
    bp.settle(e, g, d)
    g._units_base = g._players_base = None
    n2 = len(g.units(army=2))
    ctx.check(n2 >= 10, f"the rout wakes Olaf: his wave landed ({n2} units)")
    ctx.eq(e.u32(g.players_base + 0x3C * 2), 25000, "and his war chest (day 1: nothing saved)")
    bp.capture(ctx, e, g, d, (8, 8), 5)
    bp.settle(e, g, d)
    g._units_base = g._players_base = None
    ctx.log(f"after the capture: HQ owner {bp.owner(e, 8, 8)}, Olaf units {len(g.units(army=2))}")
    ctx.eq(bp.owner(e, 8, 8), 5, "the player holds Nell's HQ")
    ctx.check(len(g.units(army=2)) <= n2, f"no second wave ({len(g.units(army=2))} units)")
    e.close()
