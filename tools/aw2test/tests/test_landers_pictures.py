"""Pictures of the islets of Gauntlet's Cinder Sea and Versus' Crystal Isles for the beach (RC05) before / after sheets: with AW2TEST_LANDERS_PICS=<folder> set, each islet is centred and shot
(panels hidden) as <folder>/<look>_<map>_<n>.png. The look comes from the environment of the run: none = AW2's graphics, TANGOAW2_DS_GRAPHICS=1 = Dual Strike's map graphics flat,
TANGOAW2_DS_GRAPHICS=1 TANGOAW2_TILT=1 (and TANGOAW2_TILT_SCALE=2 TANGOAW2_TILT_SNAP=1) = tilted; AW2TEST_LANDERS_LOOK names it. `-k landers_pictures`."""

import os
import subprocess

from aw2test import gauntlet as ga
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import Skip, test
from aw2test.stitch import hide_hud, stitch

OUT = os.environ.get("AW2TEST_LANDERS_PICS")
LOOK = os.environ.get("AW2TEST_LANDERS_LOOK", "aw2")
CINDER = [(15, 10), (15, 3), (16, 18)]
CRYSTAL = [(14, 3), (15, 11), (4, 16), (26, 16)]


def shoot(ctx, g, cells, tag, size):
    """Flat looks: the whole map stitched (<look>_<tag>_full.png); tilted: each islet centred and shot (the tilt is a host-side picture that cannot be stitched)."""
    import shutil
    e = g.e
    os.makedirs(OUT, exist_ok=True)
    if os.environ.get("TANGOAW2_TILT") != "1":
        path = stitch(ctx, g, f"{tag}", *size)
        if path:
            shutil.copy(path, os.path.join(OUT, f"{LOOK}_{tag}_full.png"))
        return
    for n, (x, y) in enumerate(cells):
        g.goto(x, y)
        e.wait(240)
        hide_hud(e)
        p = os.path.join(OUT, f"{LOOK}_{tag}_{n}")
        e.shot(p)
        subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
        os.remove(p + ".bmp")


@test(modes=("ds",))
def landers_pictures_cinder_sea(ctx):
    if not OUT:
        raise Skip("AW2TEST_LANDERS_PICS not set")
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    ga.Gauntlet(g).start(ga.ARIA)
    shoot(ctx, g, CINDER, "cinder", (32, 22))


@test(modes=("ds",))
def landers_pictures_crystal_isles(ctx):
    if not OUT:
        raise Skip("AW2TEST_LANDERS_PICS not set")
    from tests import test_ds_maps as dm
    from tests import test_map_sheet as ms
    ms.dm.ALL.update(ms.EXTRA)
    name = "Crystal Isles"
    if name in dm.REPLACED:
        g, found = ms.select_on_aw2_table(ctx, name)
    else:
        g, found = dm.select_map(ctx, name)
    ctx.require(found, "Crystal Isles is on its tab")
    dm.to_teams(g)
    dm.start(ctx, g, humans=(1,))
    g.wait_for_input()
    shoot(ctx, g, CRYSTAL, "crystal", (30, 26))
