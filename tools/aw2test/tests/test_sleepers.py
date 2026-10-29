"""M31's gauntlet (the gauntlet engine, crate::custom_campaign: MissionDef::sleepers, ::hidden, ::cut_off): the hidden lines are off the battlefield until their line comes; a rout is a fallen line."""

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


@test(name="bh2_m31_hidden_lines_are_off_the_battlefield", modes=("ds",))
def bh2_m31_hidden_lines_are_off_the_battlefield(ctx):
    """The gauntlet engine (MissionDef::hidden): while Nell fights, Olaf, Kanbei and Eagle are not on the battlefield: no HQ (their cells plain), no units, no funds, no turn (the turn goes from Nell to
    the player, day after day). Nell's HQ taken on day 10: Olaf's HQ is built on his island, his zone's neutral towns become his, his wave lands, he plays (the computer's) and has his war chest
    (25,000 and nine days' savings at 1,000); a base the player raided first is taken back, wave units whose cells the player stands on land on the nearest free cells; Kanbei and Eagle stay hidden."""
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    p = lambda a: g.players_base + 0x3C * a
    ctx.eq([len(g.units(army=a)) for a in (2, 3, 4)], [0, 0, 0], "no units of Olaf, Kanbei or Eagle")
    ctx.eq([bp.owner(e, *c) for _, c, _, _ in bp.HQS[1:]], [0, 0, 0], "no HQ of theirs on the map")
    ctx.eq([e.u8(p(a) + 0x1B) for a in (2, 3, 4)], [0, 0, 0], "not in the battle (controller 0)")
    ctx.eq([e.u32(p(a)) for a in (2, 3, 4)], [0, 0, 0], "no funds")
    # two days with the player ending each turn at once: the turn goes from Nell (1) to the player (5)
    seen = []
    for _ in range(4000):
        a = g.current_army()
        if not seen or seen[-1] != a:
            seen.append(a)
        if len(seen) >= 6:
            break
        if a == 5 and d.in_battle() and not d.scripts_running():
            try:
                d.wait_control()
                d.end_turn()
            except Exception as ex:
                ctx.log(f"end turn: {ex}")
        elif d.scripts_running():
            e.press("A", 4)
        e.wait(10)
    ctx.log(f"turns seen: {seen}")
    ctx.check(set(seen) <= {1, 5}, f"only Nell and the player take turns ({seen})")
    d.wait_control()
    g._units_base = g._players_base = None
    # the player raids first: takes the island's base (23,5) and stands on three of Olaf's landing cells and his HQ's cell
    bp.capture(ctx, e, g, d, (23, 5), 5)
    bp.settle(e, g, d)
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq(bp.owner(e, 23, 5), 5, "the player took the island's base before Olaf came")
    blockers = [u for u in g.units(army=5) if not u["flags"] & 0x08 and (u["x"], u["y"]) != (23, 5)][:4]
    for u, cell in zip(blockers, [(24, 9), (17, 6), (18, 10), (24, 6)]):
        d.place_unit(u, *cell)
    e.wait(4)
    e.w16(0x0300_4080, 10)
    bp.capture(ctx, e, g, d, bp.HQS[0][1], 5)
    bp.settle(e, g, d)
    g._units_base = g._players_base = None
    ctx.eq(bp.owner(e, 24, 6), 2, "Olaf's HQ is built on his island (24,6)")
    towns = sum(1 for y in range(1, 14) for x in range(16, 31) if bp.owner(e, x, y) == 2)
    ctx.check(towns >= 8, f"his lake country's towns are his ({towns})")
    ctx.eq(len(g.units(army=2)), 21, "his whole wave landed (21 units), those whose cells were taken on the nearest free cells")
    ctx.eq(bp.owner(e, 23, 5), 2, "he took the raided base back")
    ctx.check(all(g.unit_at(*c) is not None and g.unit_at(*c)["army"] == 5 for c in [(24, 9), (17, 6), (18, 10)]), "the player's units still stand where they were")
    ctx.eq(e.u8(p(2) + 0x1B), 2, "he is in the battle (the computer's)")
    ctx.eq(e.u32(p(2)), 34000, "his war chest: 25,000 and 9 x 1,000 saved")
    ctx.eq((e.u8(p(2) + 0x2D), e.u8(p(2) + 0x2E)), (24, 6), "his record knows his HQ")
    ctx.eq([len(g.units(army=a)) for a in (3, 4)] + [bp.owner(e, 39, 6), bp.owner(e, 38, 20)], [0, 0, 0, 0], "Kanbei and Eagle are still off the battlefield")
    from tests.test_bh2_review import home
    home(g, e)
    e.wait(30)
    from aw2test import cpuprobe
    cpuprobe.whole_map(ctx, e, g, d, 31, "olaf_revealed")
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
    ctx.log(f"result at the start {e.u8(dc.LAST_RESULT)}")
    nell = g.units(army=1)
    for u in nell[1:]:
        d.remove_unit(u)
    e.wait(30)
    ctx.log(f"result after the removals {e.u8(dc.LAST_RESULT)}")
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
    ctx.log(f"result before the attack {e.u8(dc.LAST_RESULT)}, spot {spot}, target {(last['x'], last['y'])}")
    try:
        g.attack(spot, spot, (last["x"], last["y"]))
    except Exception as ex:          # (the rout's scene starts at once)
        ctx.log(f"after the attack: {ex}")
    ctx.shot(g, "after_attack")
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
