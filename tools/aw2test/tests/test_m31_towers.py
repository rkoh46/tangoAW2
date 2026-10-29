"""M31's three Com Towers (6,6), (28,15), (33,21) (a 46-wide map: one past column 30, which crate::com_tower once read as a Lab, drawn and named so, and counted for nobody) are in AW2's building list (`gProperty`, 0x03003150: class, x, y, 0 per entry; the towers' sprites are drawn from it), at the start and after Olaf's line comes."""

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test.harness import test

GPROPERTY = 0x0300_3150
TOWERS = [(6, 6), (28, 15), (33, 21)]


def listed(e):
    raw = e.read(GPROPERTY, 4 * 100)
    out = []
    for i in range(100):
        c, x, y = raw[4 * i:4 * i + 3]
        if c == 0:
            break
        out.append((c, x, y))
    return out


@test(name="bh2_m31_towers_are_drawn", modes=("ds",))
def bh2_m31_towers_are_drawn(ctx):
    e, g, d = b2.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", (0,))
    d.wait_control()
    ctx.log("raw " + e.read(GPROPERTY, 96).hex())
    lst = listed(e)
    ctx.log(f"gProperty: {len(lst)} entries; last {lst[-5:]}")
    ctx.log(f"towers listed: {[(x, y) for c, x, y in lst if (x, y) in TOWERS]}")
    ctx.check(all(any((x, y) == t for _, x, y in lst) for t in TOWERS), f"every tower is in the building list ({len(lst)} entries)")
    # the tower past column 30 on screen, and its count for an owner (crate::com_tower::count_towers covers the whole map)
    import importlib.util, os
    from aw2test import harness
    _n = len(harness.TESTS)
    spec = importlib.util.spec_from_file_location("bh2_progression_helpers6", os.path.join(os.path.dirname(__file__), "test_bh2_progression.py"))
    bp = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bp)
    del harness.TESTS[_n:]
    bp.to_player_turn(e, g, d)
    d.wait_control()
    g._units_base = g._players_base = None
    for (tx, ty) in TOWERS:
        g.goto(tx, ty)
        e.wait(30)
        ctx.shot(g, f"tower_{tx}_{ty}")
        row = e.u16(0x0201_E450 + 0x417A + 2 * ty)
        ctx.log(f"tower ({tx},{ty}): tile {e.u16(0x0201_E450 + 0xA22 + 2 * (row + tx)):#x} class {e.u8(0x0201_E450 + 0x1432 + row + tx):#x}")
    row = e.u16(0x0201_E450 + 0x417A + 2 * 21)
    e.w8(0x0201_E450 + 0x1432 + row + 33, (e.u8(0x0201_E450 + 0x1432 + row + 33) & 0x1F) | 5 << 5)
    e.wait(4)
    ctx.eq(e.u8(0x0203_FFB0 + 4), 1, "a tower at (33,21) the player owns counts for the player (Com Tower bonus)")
    e.close()
