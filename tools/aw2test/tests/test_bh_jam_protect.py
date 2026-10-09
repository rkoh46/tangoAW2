"""A jammed structure (JamDef) is not wrecked by the computer before it comes online (-k jammed_structures)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aw2test import bhact2 as a2
from aw2test.harness import test

INVENTIONS = 0x02028360


def hp_of(e, k):
    return e.u8(INVENTIONS + 8 * k + 4)


def cannon_sprites(e, g):
    """(tile, palette bank) of the Black Cannon's sprites in view of the camera on (27, 4) (the north-east cannon),
    and the colours of those sprites' OBJ palette bank."""
    import struct
    for _ in range(4):
        try:
            g.goto(27, 4)
            break
        except Exception:
            e.wait(150)
    e.wait(40)
    b = e.read(0x03002520, 0x400)
    out = []
    for k in range(128):
        a0, a1, a2 = struct.unpack_from("<HHH", b, 8 * k)
        t = a2 & 1023
        if (a0 >> 8) & 3 != 2 and (a0 & 255) < 160 and (a2 >> 10) & 3 == 3 and 0xC4 <= t <= 0x110:
            out.append((t, a2 >> 12))
    bank = out[0][1] if out else 0
    pal = tuple(e.read(0x05000200 + 32 * bank, 32))
    return sorted(out), pal


@test(modes=("ds",))
def bh_jammed_structures_keep_their_hit_points_until_they_come_online_m31(ctx):
    """M31's two Black Cannons (jammed until day 3, they fire from day 4) have all their 99 hit points on day 4:
    the computer's attack on a human's inventions skips a jammed structure (before this they were at 0 by day 3, and a wrecked
    cannon is drawn with a picture that is not loaded: garbled tiles)."""
    import test_bh_review as r
    e, g, d = r.enter(ctx, 31)
    d.leave_setup()
    a2.intro(ctx, e, d, "m31", shots=())
    d.wait_control()
    g._units_base = g._players_base = None
    ctx.eq([hp_of(e, 0), hp_of(e, 1)], [99, 99], "the cannons start at 99")
    first = cannon_sprites(e, g)
    ctx.check(len(first[0]) == 4, f"the cannon is four sprites ({first[0]})")
    for _ in range(5):
        if e.u16(0x03004080) >= 4:
            break
        a2.end_turn(e, g, d)
        for i in range(400):
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
            if not d.scripts_running() and g.current_army() == 1 and i > 5:
                break
        d.wait_control()
    ctx.check(e.u16(0x03004080) >= 4, "day 4 reached")
    ctx.eq([hp_of(e, 0), hp_of(e, 1)], [99, 99], "both cannons still have 99 hit points on day 4")
    later = cannon_sprites(e, g)
    ctx.eq(later, first, "the cannon is drawn from the same tiles in the same palette bank, with the same colours, in fog on day 4")
    e.close()
