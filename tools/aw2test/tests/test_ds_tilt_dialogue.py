"""The tilt under a campaign dialogue box: the box at the top of the screen is drawn with an HBlank
effect the tilt cannot redo; its rows keep the console's picture and the map below them stays tilted
(it used to fall back to the flat tiles for as long as the box was up)."""

import os

from aw2test import dscampaign as dc
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

OUT = os.environ.get("AW2TEST_FIXES", "")


def boxed_picture(ctx, tilt):
    genv = {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1" if tilt else "0", "TANGOAW2_TILT_SNAP": "1"}     # (the console's own environment: os.environ leaked into every later test of the process)
    e = Emu(save=paths.base_save(), ds=True, env=genv)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = dc.DsCampaign(g)
    d.start(step=2)
    rows = 0
    for _ in range(600):
        if d.on_co_select():
            d.co_screen_a()
        e.wait(10)
        rows = d.top_box_rows() if d.in_battle() else 0
        if rows >= 30:
            break
    ctx.require(rows >= 30, f"a dialogue box is up at the top of the battle map ({rows} rows)")
    e.wait(20)
    rows = d.top_box_rows()
    for _ in range(12):
        e.shot(os.path.join(ctx.out, "warm"))
    return e.shot(os.path.join(ctx.out, f"box_{'tilt' if tilt else 'flat'}")), rows


@test(modes=("ds",))
def ds_tilt_under_the_dialogue_box(ctx):
    from PIL import Image
    flat, rows = boxed_picture(ctx, False)
    tilt, rows_t = boxed_picture(ctx, True)
    a, b = Image.open(flat).convert("RGB").load(), Image.open(tilt).convert("RGB").load()
    top = sum(1 for y in range(rows_t) for x in range(240) if sum(abs(p - q) for p, q in zip(a[x, y], b[x, y])) > 24)
    below = sum(1 for y in range(rows_t + 4, 160) for x in range(240) if sum(abs(p - q) for p, q in zip(a[x, y], b[x, y])) > 24)
    ctx.log(f"box rows {rows} / {rows_t}: {top} differ inside the box, {below} below it")
    ctx.check(top < 200, f"the box's rows keep the console's picture ({top} pixels differ)")
    ctx.check(below > 3000, f"the map below the box is tilted ({below} pixels differ from the flat one)")
    if OUT:
        import shutil
        shutil.copy(flat, os.path.join(OUT, "c_box_flat.bmp"))
        shutil.copy(tilt, os.path.join(OUT, "c_box_tilt.bmp"))
