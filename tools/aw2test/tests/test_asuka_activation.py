"""Asuka's Super Power activation, frame by frame from the map menu's Super to the cut-in, next to Hawke's (her presentation template, crate::asuka::LIKE): the owner saw a glitch right before the
Super Power screen. Keeps every 2nd frame (out/<mode>/asuka_super_activation_frames/<co>_NNN.png) and a contact sheet."""

import os

from aw2test.harness import test


def run(ctx, co):
    m = ctx.map()
    m.unit(1, "tank", 8, 6).unit(1, "infantry", 9, 7).unit(2, "tank", 12, 6).unit(2, "infantry", 12, 8)
    g = ctx.start(m, [co, "andy"])
    g.wait_for_input()
    g.charge_power(1, "super")
    g.open_map_menu()
    g.choose("Super", g.MAP_MENU)
    shots = []
    for i in range(150):
        g.e.wait(2)
        shots.append(g.e.shot(os.path.join(ctx.out, f"{co}_{i:03d}")))
        if i > 20 and g.player(1)["co_mode"] == 2 and g.idle():
            break
    g.e.close()
    return shots


@test(modes=("ds",))
def asuka_super_activation_frames(ctx):
    """Asuka's and Hawke's Super Power, every 2nd frame: the frames are for looking at (contact sheets <co>_sheet.png)."""
    from PIL import Image
    for co in ("asuka", "hawke"):
        shots = [s for s in run(ctx, co) if s and os.path.exists(s)]
        ctx.check(len(shots) > 20, f"{co}: {len(shots)} frames")
        cols = 10
        ims = [Image.open(s) for s in shots[:120]]
        w, h = ims[0].size
        sheet = Image.new("RGB", (cols * w, ((len(ims) + cols - 1) // cols) * h))
        for k, im in enumerate(ims):
            sheet.paste(im, ((k % cols) * w, (k // cols) * h))
        sheet.save(os.path.join(ctx.out, f"{co}_sheet.png"))
