"""Pictures of the Silver Nova Campaign's key dialogue scenes (Caulder, Lili and Tabitha's boxes), to look at their fit, faces and speakers
(`-k sn_dialogue_pictures`; AW2TEST_DIALOGUE_SHOTS=<dir> also copies the contact sheets there). Not an assertion of the words (tools/estext/lint.py does that)."""

import os
import shutil

from aw2test import bhact2 as a2
from aw2test import boxshots
from aw2test import escampaign as es
from aw2test.harness import test


def check(ctx, name, paths, minimum):
    sheets = boxshots.sheet(ctx, paths, name)
    dest = boxshots.SHOTS
    if dest:
        os.makedirs(dest, exist_ok=True)
        for p in list(sheets) + list(paths):
            shutil.copy(p, dest)
    ctx.check(len(paths) >= minimum, f"{name}: {len(paths)} boxes photographed (at least {minimum}); sheets: {len(sheets)}")


def pre_scene(ctx, n, name, minimum, **kw):
    e, g, d = es.boot(ctx, n)
    d.wait_world_map()
    a2.open_mission(ctx, e, g, d, n - 1, es.PICKS.get(n, []), f"m{n}", setup_only=True)
    d.leave_setup()
    check(ctx, name, boxshots.shoot(ctx, e, d, name, patience=200, **kw), minimum)
    e.close()


@test(modes=("ds",))
def sn_dialogue_pictures_m04_pre(ctx):
    pre_scene(ctx, 4, "sn_m04_pre", 30, max_boxes=60)


@test(modes=("ds",))
def sn_dialogue_pictures_m14_pre(ctx):
    pre_scene(ctx, 14, "sn_m14_pre", 30, max_boxes=60)
