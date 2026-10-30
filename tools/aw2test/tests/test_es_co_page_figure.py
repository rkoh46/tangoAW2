"""The CO page's big picture with an Emerald Sun army in the battle (`-k es_co_page_figure`).

The skin's Infantry and Mech frames are kept in OBJ tiles 464..471 (`army_skin::sync_chart_art`) for the game's own unit chart; on the other pages those tiles are
part of the CO's big picture, so stray orange fragments and a strip lay over the face of the 1P army's CO (Aria, Andy ...) as soon as the CP's army was Emerald Sun.
The figure's pixels must be the same with the CP army Blue Moon or Emerald Sun."""

import os
import shutil

from PIL import Image

from aw2test.harness import test
from tests.test_aria_vengeance_signs import ROW, ENV

BOX = (112, 36, 240, 110)        # the figure's area right of the text window, above the HUD's box


def co_page(ctx, co, es):
    m = ctx.map()
    for k in range(4):
        m.unit(1, "tank", 2 + k, ROW)
    m.unit(2, "tank", 12, ROW)
    g = ctx.boot_teams(m, env=ENV)
    g.set_teams([co, "andy"], {1})
    if es:
        for _ in range(4):          # Blue Moon -> Yellow Comet, Green Earth, Black Hole, Emerald Sun
            g.e.press("R", 6)
            g.e.wait(30)
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    g.goto(12, ROW + 3)
    g.e.wait(40)
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    g.e.wait(110)
    path = ctx.shot(g, f"copage_{co}_{'es' if es else 'bm'}")
    g.e.close()
    return Image.open(path).convert("RGB")


@test(modes=("ds",))
def es_co_page_figure_is_clean(ctx):
    for co in ("aria", "andy"):
        a, b = co_page(ctx, co, 0), co_page(ctx, co, 1)
        # (the world map behind the figure scrolls, out of step between two games: a pixel that is the blue-white background in both is left out; the stray pieces were orange and brown)
        def back(c):
            return c[2] >= c[0] or min(c) >= 190
        bad = [(x, y) for y in range(BOX[1], BOX[3]) for x in range(BOX[0], BOX[2])
               if a.getpixel((x, y)) != b.getpixel((x, y)) and not (back(a.getpixel((x, y))) and back(b.getpixel((x, y))))]
        ctx.check(not bad, f"{co}: the CO page's picture is the same with the CP army Emerald Sun ({len(bad)} pixels differ, e.g. {bad[:3]})")
