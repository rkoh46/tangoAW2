"""Versus: the Emerald Sun army choice (R on the Teams screen) and the menus around it; two fronts."""

from aw2test.harness import test
from aw2test.game import Game, SELECT_MODE_CURSOR, MAP_TAB
from aw2test.emu import Emu
from aw2test import paths

MARK = 0x0203C903
SECOND = 0x0203C906
FRONTS = 0x0203C904


def to_list(ctx):
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    e.wait(700)
    e.press("START", 8)
    e.wait(300)
    e.press("A", 8)
    e.wait(150)
    for _ in range(8):
        cur = e.u8(SELECT_MODE_CURSOR)
        if cur == 3:
            break
        e.press("UP" if cur < 3 else "DOWN", 8)
        e.wait(50)
    e.press("A", 8)
    e.wait(150)
    e.press("A", 8)
    e.wait(250)
    return e, g


STATE = 0x0203C500
APPLIED = 0x09FC0010


def skin_state(e):
    return {"hosts": list(e.read(STATE, 3)), "ident": list(e.read(STATE + 4, 5)), "applied": [e.u8(APPLIED + c) for c in range(1, 6)]}


@test(modes=("ds", "aw2"))
def versus_menus_keep_no_skin(ctx):
    """The Emerald Sun army is picked with R on the Teams screen; backing out to the map list takes the choice back (the skin used to stay on the
    list and on the next Teams screen, where the first army wore it with any CO)."""
    g = ctx.boot_teams(ctx.map())
    e = g.e
    ctx.eq(skin_state(e)["ident"], [0] * 5, "a new Teams screen has no skin chosen")
    for _ in range(6):
        e.press("R", 8)
        e.wait(10)
        if skin_state(e)["ident"][0]:
            break
    on = skin_state(e)
    ctx.check(on["ident"][0] != 0 and any(on["applied"]), f"R reaches the Emerald Sun army and the skin is installed ({on})")
    e.press("B", 8)
    e.wait(120)
    back = skin_state(e)
    ctx.eq(back["ident"], [0] * 5, "back on the map list no skin is chosen")
    ctx.eq(back["hosts"], [0, 0, 0], "no colour is hosting a skin")
    ctx.eq(back["applied"], [0] * 5, "the list shows AW2's own colours: nothing is patched")
    e.press("A", 8)
    e.wait(200)
    ctx.check(g.on_teams(), "the Teams screen again")
    ctx.eq(skin_state(e)["ident"], [0] * 5, "the next Teams screen starts with no skin")
