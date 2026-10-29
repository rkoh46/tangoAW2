import os
from aw2test.harness import test, Skip
from aw2test import coverify as cv

@test(modes=("ds",))
def zz_survey(ctx):
    if os.environ.get("ZZ") != "1":
        raise Skip("ZZ")
    m = ctx.map()
    for x in (3, 7):
        m.unit(1, "tank", x, 7).unit(2, "tank", x, 8)
    m.unit(1, "bcopter", 10, 7).unit(1, "artillery", 12, 7).unit(2, "infantry", 12, 9)
    g = ctx.start(m, ["andy", "andy"], humans=(1, 2), env=cv.ENV)
    e = g.e
    for x in (3, 7):
        ctx.set_hp(g, x, 7, 50)
    g.goto(3, 7); e.wait(30)
    e.press("START", 4); e.wait(30); e.press("B", 4); e.wait(30)
    g.charge_power(1, "super"); e.press("START", 4); e.wait(30)
    g.choose("Super", g.MAP_MENU); e.wait(400)
    g.end_turn(human=1)
    for x in (3, 7):
        g.select(x, 8); g.move_to(x, 8); g.choose("Fire", g.ACTION_MENU); e.wait(40)
        for _ in range(3): e.press("B", 4); e.wait(10)
        g.wait_for_input()
    e.close()
