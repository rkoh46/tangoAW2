"""Material for the Vengeance sign mock-ups (devkit/aw2/colib/vengeance_mockups.py composes them): Aria's Tanks at 10 down to 1 displayed HP in a row (Vengeance from 8 down), Andy's army facing them,
the unit window on an 8 HP Tank, AW2's low-fuel and low-ammo icons, and the frames of Aria's Super Power (the units' shimmer while a power is on). Opt-in: AW2TEST_VENGEANCE_MOCKUP=1."""

import json
import os

from aw2test.harness import test, Skip
from aw2test import coverify as cv

HPS = [100, 90, 80, 70, 60, 50, 40, 30, 20, 10]
ROW = 7


@test(modes=("ds",))
def aria_vengeance_mockup_frames(ctx):
    if os.environ.get("AW2TEST_VENGEANCE_MOCKUP") != "1":
        raise Skip("AW2TEST_VENGEANCE_MOCKUP not set")
    m = ctx.map()
    for k in range(len(HPS)):
        m.unit(1, "tank", 2 + k, ROW)
    for k in range(5):
        m.unit(2, "tank", 3 + 2 * k, ROW - 3)
    m.unit(1, "recon", 13, ROW + 5)            # (a spare unit: its Wait makes AW2 redraw the units, HP digits and icons included)
    g = ctx.start(m, ["aria", "andy"], humans=(1,), env=cv.ENV)
    for k, hp in enumerate(HPS):
        ctx.set_hp(g, 2 + k, ROW, hp)
    # low fuel and low ammo for AW2's icons (on the Infantry and the Artillery)
    from tests.test_crumb import set_unit
    set_unit(g, 6, ROW, fuel=5)          # (the 6 HP Tank low on fuel, the 4 HP one out of ammo: AW2's icons beside the sign)
    set_unit(g, 8, ROW, ammo=0)
    g.e.wait(30)
    g.wait_unit(13, ROW + 5)
    g.e.wait(30)
    g.goto(2, ROW + 4)
    g.e.wait(40)
    ctx.shot(g, "base")
    g.goto(4, ROW)
    g.e.wait(40)
    ctx.shot(g, "panel_8hp")
    g.goto(2, ROW)
    g.e.wait(40)
    ctx.shot(g, "panel_10hp")
    cells = {"tanks": [(2 + k, ROW, hp // 10) for k, hp in enumerate(HPS)], "low_fuel": (6, ROW), "low_ammo": (8, ROW), "row": ROW,
             "cam": [g.e.u16(0x0201_E450 + 4), g.e.u16(0x0201_E450 + 6)]}
    g.goto(2, ROW + 4)
    g.e.wait(30)
    cells["cam_base"] = [g.e.u16(0x0201_E450 + 4), g.e.u16(0x0201_E450 + 6)]
    ctx.power(g, 1, "super")
    for f in range(12):
        g.e.wait(4)
        ctx.shot(g, f"power_{f:02d}")
    with open(os.path.join(ctx.out, "cells.json"), "w") as fh:
        json.dump(cells, fh)
    g.e.close()
