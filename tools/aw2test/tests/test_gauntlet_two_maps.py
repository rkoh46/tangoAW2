"""Iron Crown is a two-map Gauntlet (stage one: Grit, Jess, Kanbei, Rachel on Iron Crown; stage two: Asuka's Keep): pictures of what the map selector and the army screen show of that, in AW2's graphics, the DS map
graphics with the tilt and without it (`-k gauntlet_two_maps`; `aw2dev gauntlet two-maps`). The selector is the game's own War Room list; the army screen is ours."""

import os
import subprocess

from aw2test import gauntlet as ga
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

LOOKS = (
    ("aw2", {}),
    ("ds_tilt", {"TANGOAW2_DS_GRAPHICS": "1", "TANGOAW2_TILT": "1"}),
    ("ds_flat", {"TANGOAW2_DS_GRAPHICS": "1"}),
)
IRON_CROWN = 1


def shot(ctx, e, name):
    p = os.path.join(ctx.out, name)
    e.shot(p)
    subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)
    return p + ".png"


def to_iron_crown(d, e):
    """The selector's cursor on Iron Crown (the last row of the list)."""
    for _ in range(len(ga.SELECTOR_ORDER) + 2):
        if e.u8(ga.UI_MAP_CURSOR) == IRON_CROWN:
            break
        e.press("DOWN", 4)
        e.wait(40)
    e.wait(60)


@test(modes=("ds",))
def gauntlet_two_maps_pictures(ctx):
    """Iron Crown's selector (three moments, a few seconds apart) and army screen in the three looks. A sheet `two_maps_sheet.png` (a row a look: selector at once, selector 2 s later, selector 4 s later, the
    army screen); `AW2TEST_SHEET` copies it where a person looks."""
    from PIL import Image
    rows = []
    for look, env in LOOKS:
        e = Emu(save=paths.base_save(), ds=ctx.ds, env=env)
        g = Game(e, ctx.image)
        ctx.games.append(g)
        d = ga.Gauntlet(g)
        d.open(pick=False)
        d.wait_step(ga.SELECTOR)
        to_iron_crown(d, e)
        row = [shot(ctx, e, f"{look}_selector_0")]
        e.wait(120)
        row.append(shot(ctx, e, f"{look}_selector_1"))
        e.wait(120)
        row.append(shot(ctx, e, f"{look}_selector_2"))
        e.press("A", 6)
        d.wait_army()
        e.wait(20)
        row.append(shot(ctx, e, f"{look}_army"))
        rows.append(row)
        e.close()
    ims = [[Image.open(p).convert("RGB") for p in r] for r in rows]
    sheet = Image.new("RGB", (240 * 4, 160 * len(ims)))
    for y, r in enumerate(ims):
        for x, im in enumerate(r):
            sheet.paste(im, (240 * x, 160 * y))
    sheet = sheet.resize((sheet.width * 2, sheet.height * 2), Image.NEAREST)
    sheet.save(os.path.join(ctx.out, "two_maps_sheet.png"))
    if os.environ.get("AW2TEST_SHEET"):
        sheet.save(os.environ["AW2TEST_SHEET"])
