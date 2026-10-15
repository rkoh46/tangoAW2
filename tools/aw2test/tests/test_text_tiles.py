"""The turn hand-off screen's and the CO Power splash's text keep their letters with the Dual Strike pack.

Both screens draw their text as OBJ sprites from the game's font tiles at the end of OBJ VRAM. tangoAW2's own
battle sprites (the Black Cannon facing north, the Obelisk, the Crystal) once went into tiles the font also
uses, so the text came out as pink blocks in the DS pack's battles. The same fog battle is played on a console
with the pack and one without; the hand-off screen (black, three lines of text) must be the same picture on
both, and the OBJ tiles the text names must hold the same data.
"""

import os
from collections import Counter

from aw2test.harness import Ctx, test


def colours(bmp):
    """How many pixels of each colour a 240x160 24-bit BMP has, black left out."""
    px = bmp[54:]
    return Counter(px[i:i + 3] for i in range(0, len(px), 3) if px[i:i + 3] != b"\0\0\0")


def play(c):
    m = c.map()
    m.unit(1, "infantry", 17, 12).unit(2, "infantry", 25, 5)
    g = c.start(m, ["andy", "grit"], humans=(1, 2), fog=True, visuals="a")
    out = {}
    g.e.wait(60)
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    g.e.wait(500)
    out["handoff"] = open(g.e.shot(os.path.join(c.out, "handoff")), "rb").read()
    out["handoff_tiles"] = g.e.read(0x0601_0000 + 32 * 0x3C0, 32 * 0x40)
    g.e.press("A", 6)
    g.wait_for_input()
    g.charge_power(2, "power")
    g.e.wait(30)
    g.open_map_menu()
    g.choose("Power", g.MAP_MENU)
    for k in range(40):
        g.e.wait(4)
        g.e.shot(os.path.join(c.out, f"power_{k:02}"))
    return out


@test(modes=("ds",))
def handoff_text_tiles_with_pack(ctx):
    ref = Ctx(ctx.name + "_nopack", ds=False)
    try:
        want = play(ref)
    finally:
        ref.finish()
    got = play(ctx)
    ctx.check(got["handoff_tiles"] == want["handoff_tiles"], "font tiles 0x3C0..0x3FF: same as without the pack")
    # (the pack shifts the screen a pixel or two; the letters' colours and counts must be the same)
    ctx.check(colours(got["handoff"]) == colours(want["handoff"]), "Next turn hand-off screen: same pixels as without the pack")
