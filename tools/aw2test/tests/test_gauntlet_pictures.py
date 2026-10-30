"""Pictures of a Gauntlet run on Cinder Sea (crate::gauntlet_mode), for review: day 1, then each line's fall: the arrival scene's boxes and the new line on the map (Sensei's island, Hawke's
volcano island), then the victory. A contact sheet `cinder_sea_sheet.png`; the checks are only that each arrival happened (the run's rules are tested in test_gauntlet_mode.py)."""

import os
import subprocess

from aw2test import gauntlet as ga
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test import paths
from aw2test.harness import test


def shot(ctx, e, name):
    p = os.path.join(ctx.out, name)
    e.shot(p)
    subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
    return p + ".png"


@test(modes=("ds",))
def gauntlet_pictures_cinder_sea(ctx):
    """Cinder Sea with Aria: day 1, Sensei's arrival (scene, island), Hawke's arrival (scene, volcano island)."""
    from PIL import Image
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.ARIA)
    pics = []
    g.goto(8, 16)
    e.wait(40)
    pics.append(shot(ctx, e, "a_day1_player"))
    g.goto(24, 16)
    e.wait(40)
    pics.append(shot(ctx, e, "b_day1_drake"))
    for name, at, key in (("drake", (5, 4), "c_sensei"), ("sensei", (26, 4), "d_hawke")):
        d.capture(ctx, ga.CINDER[name])
        k = 0
        for _ in range(400):
            if d.scripts_running():
                if k < 4:
                    e.wait(70)
                    pics.append(shot(ctx, e, f"{key}_scene_{k}"))
                    k += 1
                e.press("A", 4)
            elif k:
                break
            e.wait(20)
        d.settle()
        ctx.check(k > 0, f"{name}'s fall played a scene")
        g.goto(*at)
        e.wait(60)
        pics.append(shot(ctx, e, f"{key}_arrived"))
    ims = [Image.open(p).convert("RGB") for p in pics if os.path.exists(p)]
    cols = 4
    sheet = Image.new("RGB", (240 * cols, 160 * ((len(ims) + cols - 1) // cols)))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * 240, (i // cols) * 160))
    sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST).save(os.path.join(ctx.out, "cinder_sea_sheet.png"))
