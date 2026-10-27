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


def front_game(ctx, army1_presses=3, cos=("asuka", "andy")):
    """Versus on two fronts: the first 2P map of the list marked as the second front (SELECT), the next one the main front; army 1 takes the colour `army1_presses` R presses on."""
    e, g = to_list(ctx)
    e.press("SELECT", 8)
    e.wait(30)
    ctx.eq(e.u8(MARK) != 0, True, "a 2P map is marked as the second front")
    e.press("DOWN", 8)
    e.wait(20)
    e.press("A", 8)
    ok = e.wait_until(g.on_teams, 400, step=10)
    ctx.require(ok, "the Teams screen opens")
    e.wait(150)
    for _ in range(army1_presses):
        e.press("R", 8)
        e.wait(30)
        ctx.log(f"R -> {list(e.read(g.teams_addr() + 0x0D, 2))} {skin_state(e)['ident']}")
    ctx.log(f"after R: colours {list(e.read(g.teams_addr() + 0x0D, 4))} {skin_state(e)}")
    g.set_teams(list(cos), {1, 2})
    ctx.log(f"after COs: colours {list(e.read(g.teams_addr() + 0x0D, 4))} {skin_state(e)}")
    return e, g


from aw2test import twofront as tf


def players(e):
    base = e.u32(0x08499598)
    return [{"colour": e.u8(base + 0x3C * a + 0x1A), "co": e.u8(base + 0x3C * a + 0x1D), "team": e.u8(base + 0x3C * a + 0x2A), "ctl": e.u8(base + 0x3C * a + 0x1B)} for a in (1, 2)]


def to_second_front(ctx, g):
    """Both armies (human) end their turn on the main front; the second front's first round begins."""
    e = g.e
    for _ in range(2):
        army = g.current_army()
        g.open_map_menu()
        g.choose("End", g.MAP_MENU)
        ctx.require(e.wait_until(lambda: g.current_army() != army or e.u8(tf.LIVE) == 1, 900, step=8), "the turn ended")
        e.wait(60)
    ctx.require(e.wait_until(lambda: e.u8(tf.LIVE) == 1 and e.u8(tf.BUSY) == 0, 3000, step=20), f"the second front is on the screen ({tf.state(e)})")
    e.wait(200)


def plate(path):
    """The colours of the first army's HUD plate (top right of the screen)."""
    from PIL import Image
    from collections import Counter
    im = Image.open(path + ".bmp" if not path.endswith(".bmp") else path).convert("RGB").crop((208, 1, 238, 7))
    return Counter(im.getdata()).most_common(1)[0][0]


def fronts_keep_colours(label, presses, cos):
    def fn(ctx):
        e, g = front_game(ctx, presses, cos)
        g.teams_to_rules()
        g.set_rules()
        g.start_battle()
        g.wait_for_input()
        first = players(e)
        skin1 = skin_state(e)
        p1 = ctx.shot(g, "front1")
        ctx.log(f"{label}: first front {first} {skin1}")
        to_second_front(ctx, g)
        p2 = ctx.shot(g, "front2")
        second = players(e)
        ctx.eq([(x["colour"], x["team"], x["co"]) for x in second], [(x["colour"], x["team"], x["co"]) for x in first], f"{label}: the second front's armies keep the first front's colours, teams and COs")
        ctx.eq(skin_state(e)["applied"], skin1["applied"], f"{label}: the skin is on the same colour on both fronts")
        ctx.eq(plate(p2), plate(p1), f"{label}: the army's HUD plate has the same colour on both fronts")
    fn.__name__ = f"versus_fronts_colours_{label}"
    test(modes=("ds",))(fn)


# R presses from Orange Star: 1 Yellow Comet, 3 Black Hole, 4 the Emerald Sun army
fronts_keep_colours("black_hole", 3, ("asuka", "andy"))
fronts_keep_colours("yellow_comet", 1, ("max", "andy"))
fronts_keep_colours("emerald_sun", 4, (86, "andy"))
