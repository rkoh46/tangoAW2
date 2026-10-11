"""Dual Strike HUD / range fixes from the final review (Dual Strike map graphics, TANGOAW2_DS_GRAPHICS=1)."""

import os
import shutil

from aw2test import paths
from aw2test.editor import Editor
from aw2test.emu import Emu
from aw2test.harness import Skip, test
from tests.test_ds_hud import GRAPHICS, battle, panel_digits, number_at, panel_sprites, shot

WIN = (0x03002B40, 0x03002B4C, 0x03002EFC, 0x03002B44)
T_QUESTION = 988


@test(modes=("ds",))
def ds_fix_design_room_no_backing_band(ctx):
    """The Design Room's map editor has no terrain panel: the game's window (the translucent backing) stays
    full-screen, no dark band over the left panel."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    sav = os.path.join(ctx.out, "ed.sav")
    shutil.copyfile(paths.base_save(), sav)
    e = Emu(save=sav, ds=True)
    ed = Editor(e)
    ed.boot()
    e.wait(40)
    w = [e.u8(a) for a in WIN]
    ctx.check(w[:2] != [2, 44] and w[3] != 158, f"the window is the game's, not the info panel's rectangle ({w})")
    e.shot(os.path.join(ctx.out, "editor"))
    e.close()


@test(modes=("ds",))
def ds_fix_hidden_hp_is_a_question_mark(ctx):
    """A unit whose hit points AW2 hides (Sonja's) shows "?" alone in the box: no number, the true hit points
    never drawn."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    m = ctx.map()
    m.terrain(0, 19, "hq", 3).terrain(29, 0, "hq", 4)
    m.unit(1, 16, 5, 5).unit(2, 16, 8, 5)
    g = ctx.start(m, ["andy", "sonja", "drake", "grit"])
    e = g.e
    g.goto(8, 5)
    e.wait(50)
    ps = panel_sprites(e)
    ctx.check(any(sp[2] == T_QUESTION for sp in ps), f"the '?' is shown ({ps})")
    good, bad = panel_digits(e)
    heart_rows = {sp[1] + 1 for sp in ps if sp[2] == 862}
    ctx.check(not any(y in heart_rows for _, y, _ in good), "no number on the hit points row")
    shot(ctx, g, "hidden_hp")
    g.goto(5, 5)
    e.wait(50)
    good, bad = panel_digits(e)
    ctx.check(any(number_at(good, y) == "100" for y in {y for _, y, _ in good}), "an ordinary unit shows its 100")


@test(modes=("ds",))
def ds_fix_map_menu_leaves_no_dark_box(ctx):
    """With the map menu open (flat and tilted) the game's darkening (BLDCNT, window) is off: no empty dark box where
    the info panel was."""
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    g = battle(ctx, ["andy", "olaf"], [None, None], units=[(1, "tank", 10, 8)])
    e = g.e
    g.goto(10, 8)
    e.wait(40)
    ctx.check(e.u16(0x030030E0) >> 6 & 3 == 3, "(the panel's darkening is on while the panel shows)")
    g.open_map_menu()
    e.wait(60)
    ctx.eq(e.u16(0x030030E0), 0, "BLDCNT is off with the map menu open")
    shot(ctx, g, "map_menu")
