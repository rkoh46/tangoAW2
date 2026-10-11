"""Fixes found in the final picture sheets review (Dual Strike look)."""

import os

from aw2test.harness import test


def picture(ctx, name, cursor, snap=False):
    env = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}
    if snap:
        env["TANGOAW2_TILT_SNAP"] = "1"
    m = ctx.map()
    m.unit(1, "tank", 4, 4).unit(2, "tank", 6, 4).unit(2, "tank", 22, 5)
    g = ctx.start(m, ["andy", "drake"], env=env)
    g.e.wait(30)
    g.goto(*cursor)
    g.e.wait(50)
    return ctx.shot(g, name)


@test(modes=("ds",))
def ds_tilt_camera_settles_without_pictures(ctx):
    """The tilted camera glides on console frames, not on pictures: waiting 50 frames and then taking one
    picture shows the cursor's area, the same as a camera that snapped (it used to take one 30% step)."""
    from PIL import Image
    a = Image.open(picture(ctx, "glide", (22, 5))).convert("RGB").load()
    b = Image.open(picture(ctx, "snap", (22, 5), snap=True)).convert("RGB").load()
    diff = sum(1 for y in range(160) for x in range(240) if sum(abs(p - q) for p, q in zip(a[x, y], b[x, y])) > 24)
    ctx.log(f"{diff} pixels differ from the snapped camera")
    ctx.check(diff < 400, f"after 50 frames the camera is where it settles ({diff} pixels differ)")
