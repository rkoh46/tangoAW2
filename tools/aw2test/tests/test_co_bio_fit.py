"""The Silver Nova COs' CO pages, AW2's own look and Dual Strike's (`-k co_bio_fit`): the bio shows whole above Hit and Miss.

The fit itself is the unit test `co_new::pack_tests::own_bios_show_whole_on_the_aw2_page` (also run by `aw2dev audit text`): AW2's page has six lines for the bio, Hit and Miss, and
`wrap_page` used to cut a longer bio's last sentences (Tabitha's ended "A daughter of Dr."). This test draws the pages: with `AW2_BIO_SHOTS=<folder>` it also writes them there
as `sn_bio_<co>_<aw2|ds>.png` and `_x3.png` (three times the size) to look at."""

import os

from PIL import Image

from aw2test import coverify as cv, cospec
from aw2test.harness import test

NAMES = ("tabitha", "lili", "caulder")
OUTDIR = os.environ.get("AW2_BIO_SHOTS", "")


def page(ctx, name, graphics):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    env = dict(cv.ENV, TANGOAW2_DS_GRAPHICS="1" if graphics else "0")
    g = ctx.start(m, [cospec.IDS.get(name, name), "andy"], env=env)
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    g.e.wait(90)
    path = ctx.shot(g, f"bio_{name}_{'ds' if graphics else 'aw2'}")
    g.e.close()
    return path


@test(modes=("ds",))
def co_bio_fit_pages_are_drawn(ctx):
    for name in NAMES:
        for graphics in (False, True):
            look = "ds" if graphics else "aw2"
            im = Image.open(page(ctx, name, graphics)).convert("RGB")
            ctx.eq(im.size, (240, 160), f"{name} ({look}): the CO page is drawn")
            if OUTDIR:
                os.makedirs(OUTDIR, exist_ok=True)
                im.save(os.path.join(OUTDIR, f"sn_bio_{name}_{look}.png"))
                im.resize((im.width * 3, im.height * 3), Image.NEAREST).save(os.path.join(OUTDIR, f"sn_bio_{name}_{look}_x3.png"))
