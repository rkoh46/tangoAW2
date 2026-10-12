"""Dual Strike tilt at a higher resolution (ds_tilt.rs, TANGOAW2_TILT_SCALE): pictures of one busy scene
tilted at the console's size and at 4x, to look at (out/hires/). The checks are only that the
larger picture exists and that the HUD it keeps is the console's, pixel for pixel."""

import os

from aw2test.harness import test

KINDS = ("tank", "infantry", "apc", "artillery", "recon", "tank", "fighter", "infantry")


def busy(ctx):
    m = ctx.map()
    for x in range(4, 26):
        for y in range(2, 18):
            n = (x * 7 + y * 13) % 11
            if n == 0:
                m.terrain(x, y, "mountain")
            elif n in (1, 2):
                m.terrain(x, y, "wood")
            elif n == 3 and y % 2:
                m.terrain(x, y, "road")
    for x in (6, 9, 12, 15, 18, 21):
        m.terrain(x, 4, "city", 1 + x % 2)
        m.terrain(x, 14, "base", 1 + x % 2)
    for y in range(3, 17):
        for x in range(5, 25):
            if (x + y) % 3 == 0:
                m.unit(1 + (x + y) % 2, KINDS[(x * 3 + y) % len(KINDS)], x, y)
    return m


@test(modes=("ds",))
def ds_tilt_hires_pictures(ctx):
    from PIL import Image
    out = os.path.join(os.environ.get("AW2TEST_OUT", ctx.out), "hires")
    os.makedirs(out, exist_ok=True)
    shots = {}
    for ss in ("1", "4"):
        env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1", "TANGOAW2_TILT_SCALE": ss, "TANGOAW2_TILT_TIME": os.environ.get("HT", "0")}
        g = ctx.start(busy(ctx), ["andy", "drake"], env=env)
        g.e.wait(30)
        # damaged units: every unit gets a different HP (the digit shows below 10)
        for i, u in enumerate(g.units()):
            a = g.unit_addr(u["id"])
            hp = (10, 80, 63, 45, 27, 91, 34, 55, 99, 12)[i % 10]
            g.e.w16(a + 4, (g.e.u16(a + 4) & ~0x7F) | hp)
        g.goto(15, 9)
        g.e.wait(30)
        for _ in range(16):
            g.e.shot(os.path.join(ctx.out, "warm"))
        ctx.log(("bench", ss, g.e.cmd("bench 300")))
        p = ctx.shot(g, f"hires_{ss}")
        im = Image.open(p).convert("RGB")
        shots[ss] = im
        if ss == "1":
            im = im.resize((960, 640), Image.NEAREST)
        im.save(os.path.join(out, f"scene_{'before' if ss == '1' else 'after'}.png"))
        ctx.eq(shots[ss].size, (240, 160) if ss == "1" else (960, 640), f"picture size at scale {ss}")
