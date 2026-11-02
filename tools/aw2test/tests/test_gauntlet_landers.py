"""RC05 live (the owner's rule: a Lander must be able to land on every island): on Gauntlet's Cinder Sea (five/gauntlet/gauntlet_01.txt) the player's Lander, loaded with an Infantry at
its own island's port, sails onto each islet beach and drops the Infantry onto the islet's land. Both live armies are played by hand (a test aid) so nothing interferes; one case a
round. `-k gauntlet_landers`. Pictures: `landers_<n>_*.png` in the output folder."""

import os
import subprocess

from aw2test import gauntlet as ga
from aw2test import paths
from aw2test.emu import Emu
from aw2test.game import Game
from aw2test.harness import test

ROWS = None
# (islet, beach, sea cell to start the last leg from): the beaches fix_gauntlet_01 gave the islets
CASES = [("middle S", (15, 12), (15, 14)), ("middle SW", (13, 11), (11, 12)), ("middle NE", (17, 9), (19, 9)), ("middle N", (15, 8), (15, 6)),
         ("north W", (13, 2), (11, 2)), ("south W", (14, 18), (12, 18))]


def rows():
    from aw2test import paths as p
    path = os.path.join(p.REPO, "tango-gamesupport-aw2", "five", "gauntlet", "gauntlet_01.txt")
    return [l.rstrip("\n") for l in open(path) if len(l.rstrip("\n")) == 32 and set(l.rstrip("\n")) <= set("~.,rfR^#cCabpPABtVT1234 -=")]


def land_next(rs, b):
    x, y = b
    for X, Y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
        if 0 <= Y < len(rs) and 0 <= X < len(rs[0]) and rs[Y][X] in ".fRcCtab":
            return (X, Y)
    return None


def png(e, out, name):
    p = os.path.join(out, name)
    e.shot(p)
    subprocess.run(["sips", "-s", "format", "png", p + ".bmp", "--out", p + ".png"], capture_output=True)


def pass_turn(e, g, d):
    army = g.current_army()
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    e.wait_until(lambda: g.current_army() != army, 600, step=8)
    d.wait_control()


@test(modes=("ds",))
def gauntlet_landers_land_on_every_islet(ctx):
    """Cinder Sea: a Lander carrying an Infantry sails onto each islet's beach, is offered Drop, and the Infantry ends on the islet's land."""
    rs = rows()
    ctx.require(len(rs) == 22, f"the map's rows were read ({len(rs)})")
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.ARIA)
    for a in (1, 2):
        e.w8(g.player(a)["addr"] + 0x1B, 1)
    lander = next(u for u in g.units(army=1) if u["type"] == 23)
    infs = [u for u in g.units(army=1) if u["type"] == 1]
    ctx.require(infs, "the player has an Infantry")
    for k, (name, b, s0) in enumerate(CASES):
        ctx.check(rs[b[1]][b[0]] == "," and land_next(rs, b) is not None, f"{name}: {b} is a shoal with land beside it")
        land = land_next(rs, b)
        inf = infs[0]                      # (one Infantry, put back at the port each round)
        # load at the player's port: the Lander on the port (8,18) (a Lander loads and drops only on shoal or port), the Infantry beside it
        d.place_unit(g.unit(lander["id"]), 8, 18)
        d.place_unit(g.unit(inf["id"]), 7, 18)
        e.wait(10)
        g.select(7, 18)
        names = g.move_to(8, 18)["names"]
        ctx.check(any(n.lower().startswith("load") for n in names), f"{name}: the Infantry at the port is offered Load ({names})")
        g.choose("Load", g.ACTION_MENU)
        g.wait_idle()
        ctx.check(any(g.unit(lander["id"])["cargo"]), f"{name}: the Lander carries the Infantry")
        # the ferry's last leg: the Lander (with its cargo) from a sea cell near the islet, onto the beach
        d.place_unit(g.unit(lander["id"]), *s0)
        e.wait(10)
        g.goto(*b)
        e.wait(20)
        g.select(*s0)
        names = g.move_to(*b)["names"]
        ctx.check(any(n.lower().startswith("drop") for n in names), f"{name}: the Lander on the beach {b} offers Drop ({names})")
        g.choose("Drop", g.ACTION_MENU)
        e.wait(20)
        if g.menu():
            e.press("A", 4)
            e.wait(20)
        for _ in range(8):
            if g.cursor() == land:
                break
            e.press("RIGHT", 4)
            e.wait(10)
        png(e, ctx.out, f"landers_{k}_target")
        e.press("A", 4)
        e.wait(40)
        mm = g.menu()
        if mm and any(n.lower().startswith("wait") for n in mm["names"]):
            g.choose("Wait", g.ACTION_MENU)
        g.wait_idle()
        iu, lu = g.unit(inf["id"]), g.unit(lander["id"])
        ctx.check((iu["x"], iu["y"]) == land and not any(lu["cargo"]), f"{name}: the Infantry stands on the islet's land {land} (at {(iu['x'], iu['y'])}), the Lander on {(lu['x'], lu['y'])} is empty")
        png(e, ctx.out, f"landers_{k}_landed")
        pass_turn(e, g, d)
        pass_turn(e, g, d)
