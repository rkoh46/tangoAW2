"""Silver Nova's name on Select Mode's Campaign sub-menu and on the Campaign's own screens, with and without the Dual Strike pack (`-k silver_nova_menu`):
the chooser lists SILVER NOVA (the old name is gone), the pictures go to AW2TEST_REVIEW_DIR / the test's output (menu_<row>.bmp). The text check
`aw2dev audit text` greps the sources for any player-visible 'Emerald' left (`devkit/aw2/armyskinlib/test_armyskin.py::test_no_emerald_text`)."""
import os

from aw2test import bhact2 as a2
from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test


@test(modes=("aw2", "ds"))
def silver_nova_menu(ctx):
    e = Emu(save=es.paths.base_save(), ds=ctx.ds, env=es.ENV)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = es.EsCampaign(g)
    d.open_campaign_box()
    a2.pic(ctx, e, "menu_open")
    if ctx.ds:
        for row in range(0, 6):
            try:
                d.chooser_row(row)
            except Exception:
                break
            e.wait(10)
            a2.pic(ctx, e, f"menu_row{row}")
        d.chooser_row(es.CHOOSER_ROW)
        e.wait(10)
        a2.pic(ctx, e, "menu_silver_nova")
        e.press("A", 8)
        e.wait(30)
        ctx.eq(e.u8(es.SOURCE), es.ES, "the Silver Nova entry opened its own box")
        a2.pic(ctx, e, "menu_box")
    e.close()
