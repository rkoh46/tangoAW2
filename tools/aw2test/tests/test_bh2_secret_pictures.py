"""Pictures of the BH2 Campaign's secret mission M32 Through the Door for review (`-k bh2_secret_pictures`; AW2TEST_REVIEW_DIR copies them): per look (AW2, Dual Strike with the tilt, Dual Strike flat)
the day-1 game window and the whole map stitched (the tilt is a host-side overlay, so its stitch is the flat one); the pre-scene's boxes with the Silver Nova faces. Facts of the map go to the log."""

import os
import shutil

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test import boxshots, stitch
from aw2test.harness import test
from tests.test_bh_review import Quiet
from tests.test_gauntlet_lines_pictures import LOOKS, settled_png


def keep(ctx, path, name):
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    if out and path:
        os.makedirs(out, exist_ok=True)
        shutil.copy(path, os.path.join(out, name))


@test(modes=("ds",))
def bh2_secret_pictures_maps(ctx):
    for look, env in LOOKS:
        e, g, d = b2.enter(ctx, 32, env=env)
        w, h = d.size()
        if look == "aw2":
            ctx.log(f"M32: map {w} x {h}")
            for a in range(1, 6):
                try:
                    p = g.player(a)
                    ctx.log(f"army {a}: co {p.get('co')} colour {p.get('colour')} funds {p.get('funds')} units {len(g.units(army=a))}")
                except Exception as ex:
                    ctx.log(f"army {a}: {ex}")
        keep(ctx, settled_png(ctx, e, f"{look}_day1"), f"m32_{look}_day1.png")
        if look != "ds_tilt":
            p = stitch.stitch(Quiet(ctx), g, f"{look}_whole", w, h)
            keep(ctx, p, f"m32_{look}_whole_full.png")
        e.close()


@test(modes=("ds",))
def bh2_secret_pictures_scene(ctx):
    e, g, d = b2.boot(ctx, 32)
    d.wait_world_map()
    a2.open_mission(ctx, e, g, d, 31, b2.PICKS.get(32, []), "m32", setup_only=True)
    d.leave_setup()
    paths = boxshots.shoot(ctx, e, d, "m32_pre", patience=200, max_boxes=45)
    sheets = boxshots.sheet(ctx, paths, "m32_pre")
    for p in sheets:
        keep(ctx, p, os.path.basename(p))
    ctx.check(len(paths) >= 20, f"{len(paths)} boxes photographed")
    e.close()
