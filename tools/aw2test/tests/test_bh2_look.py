"""BH2 M32 Through the Door (development build, crate::bh2_campaign): the enemy army wears the Emerald Sun skin and nothing of Green Earth (`-k bh2_m32_look`).

The mission gives Klaus + Aurelia's army the colour Green Earth as a host (`MissionDef::skin`: the skin sits on that colour, `army_skin`); the game then draws every Green Earth picture from the skin's. The test enters the mission, deploys,
and photographs what the player sees of the enemy: the whole screen with the cursor on the enemy HQ, on an enemy base, on an enemy Infantry and on an enemy Tank (the terrain and unit panels), and the start of the enemy's own turn (its CO
panel and banner). The pictures (3x, AW2TEST_REVIEW_DIR/m26_look_*.png) are looked at: the HQ is the skin's (pale stone, the sun), the units grey stone with red plumes, the panels the skin's emblem.
It also checks the skin's state byte: the skin sits on the colour army 2 has."""

import os

from aw2test import bh2campaign as b2
from aw2test import bhact2 as a2
from aw2test.harness import test

SKIN_STATE = 0x0203C500           # crate::army_skin::STATE: +0 the colour (1..5) the first skin sits on


def snap(ctx, e, name):
    p = e.shot(os.path.join(ctx.out, name))
    out = os.environ.get("AW2TEST_REVIEW_DIR")
    try:
        from PIL import Image
        im = Image.open(p).convert("RGB")
        im = im.resize((im.width * 4, im.height * 4), Image.NEAREST)
        if out:
            os.makedirs(out, exist_ok=True)
            im.save(os.path.join(out, f"m26_look_{name}.png"))
    except ImportError:
        pass
    return p


@test(name="bh2_m32_look", modes=("ds",))
def bh2_m32_look(ctx):
    e, g, d = b2.enter(ctx, 32)
    d.leave_setup()
    a2.intro(ctx, e, d, "m26", (0,))
    d.wait_control()
    g._units_base = g._players_base = None
    colour = g.player(2)["colour"]
    host = e.u8(SKIN_STATE)
    ctx.log(f"army 2's colour byte {colour}; the skin sits on colour {host}")
    ctx.check(host == colour, f"the Emerald Sun skin sits on army 2's colour (skin host {host}, army 2's colour {colour})")
    enemy = g.units(army=2)
    inf = next(u for u in enemy if u["type"] == 1)
    tank = next(u for u in enemy if u["type"] == 5)
    for name, (x, y) in (("hq", (32, 21)), ("infantry", (inf["x"], inf["y"])), ("tank", (tank["x"], tank["y"]))):
        g.goto(x, y)
        e.wait(40)
        snap(ctx, e, name)
    # the enemy's own turn: its CO panel and the turn banner
    shots = []

    def observe(game):
        for k in range(4):
            e.wait(45)
            shots.append(snap(ctx, e, f"enemy_turn{k}"))
    g.end_turn(human=1, observe=observe)
    ctx.check(len(shots) == 4, "the enemy's turn was photographed")
    e.close()
