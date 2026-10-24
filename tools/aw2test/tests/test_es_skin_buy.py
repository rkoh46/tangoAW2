"""Emerald Sun: a skinned army buys an Infantry and a Mech from the build menu (`-k es_skin_buy`). The skin's portraits (army_skin.rs `portrait_blob`) are put in
for the build menu's panel and the unit panel; the game's memory must stay sane (the day, the mission's result byte and the funds) and the panel shows the skin's plume."""

import os

from PIL import Image

from aw2test import dscampaign as dc
from aw2test import escampaign as es
from aw2test.bot import Bot, BASE
from aw2test.game import NavError
from aw2test.harness import test

MISSION = int(os.environ.get("AW2TEST_ES_BUY_MISSION", "8"))
NEED = 20          # (the pixels of the skin's crest red the build panel's portrait has: M8's player wears Blue Moon, whose own soldier has none)


# The build menu's portrait panel (the picture's box), 240 x 160 pixels: the list's Infantry and Mech icons wear red caps too, so only the panel counts.
PANEL = (151, 25, 176, 56)


def crest(path):
    im = Image.open(path).convert("RGB").crop(PANEL)
    return sum(1 for r, g, b in im.getdata() if r > 150 and g < 100 and b < 100 and r - g > 80)


FIG_TABLE_AT = 0x09FC7000      # army_skin::fig_at(0): the first skin's table of battle figures and portraits in free ROM (six words, then the pictures)
FIG_ROOM = 0x3000


def check_figure_table(ctx, e):
    """The table the portraits and the battle figures are handed from holds pointers into its own room at LZ77 streams (once the Dual Strike picture palettes'
    backup of colour 5 sat on it, and the build menu's portrait made the game decompress a palette over its memory)."""
    for k in range(6):
        at = e.u32(FIG_TABLE_AT + 4 * k)
        ctx.check(FIG_TABLE_AT + 0x20 <= at < FIG_TABLE_AT + FIG_ROOM and at % 4 == 0 and e.u8(at) == 0x10, f"the skin's figure table, word {k}: {at:#x} is an LZ77 stream in its room")


def open_menu(g, e, x, y, unit_type):
    """The build menu on the base at (x, y) with `unit_type` highlighted; returns the menu's ids."""
    g.wait_idle()
    g.goto(x, y)
    e.press("A", 4)
    e.wait(60)
    ids = []
    for k in range(30):
        t = e.u8(0x02023830 + 4 * k)
        if t == 0:
            break
        ids.append(t)
    if unit_type not in ids:
        raise NavError(f"{unit_type} not in the build menu {ids}")
    for _ in range(ids.index(unit_type)):
        e.press("DOWN", 4)
        e.wait(8)
    e.wait(20)


@test(name="es_skin_buy_infantry_and_mech", modes=("ds",))
def es_skin_buy_infantry_and_mech(ctx):
    e, g, d = es.enter(ctx, MISSION)
    bot = Bot(d)
    bases = [c for c, kind, owner in bot.properties() if kind == BASE and owner == 1 and not any((u["x"], u["y"]) == c for u in g.units())]
    ctx.log(f"properties {[(c, k, o) for c, k, o in bot.properties() if o == 1]}")
    ctx.require(bases, f"M{MISSION}: the player has a free base")
    check_figure_table(ctx, e)
    sane = lambda: (e.u16(dc.DAY), e.u8(dc.LAST_RESULT))
    day, result = sane()
    ctx.log(f"before: day {day} result {result}")
    for k, (unit, name) in enumerate(((1, "inf"), (2, "mech"))):
        x, y = bases[k] if k < len(bases) else bases[0]
        # (the funds the purchase needs)
        p = e.u32(0x08499598)
        e.w32(p + 0x3C, 100000)
        open_menu(g, e, x, y, unit)
        shot = ctx.shot(g, f"build_{name}")
        reds = crest(shot)
        ctx.log(f"{name}: {reds} pixels of crest red in the build menu")
        ctx.check(reds >= NEED, f"the {name}'s build panel shows the skin's plume ({reds} >= {NEED})")
        e.press("A", 4)
        g.wait_for_input()
        e.wait(120)
        ctx.eq(sane(), (day, result), f"after buying the {name}: day and result byte are unchanged")
        built = [u for u in g.units(1) if u["type"] == unit and (u["x"], u["y"]) == (x, y)]
        ctx.check(bool(built), f"the {name} was built at {(x, y)}")
        # (the unit panel: the cursor on the new unit)
        g.goto(x, y)
        e.wait(40)
        shot = ctx.shot(g, f"panel_{name}")
        ctx.log(f"{name}: {crest(shot)} pixels of crest red with the cursor on it")
        # (one base: the new unit makes room for the next purchase)
        for u in built:
            d.remove_unit(u)
        g._units_base = g._players_base = None
        e.wait(10)
    ctx.eq(sane(), (day, result), "day and result byte stay sane")
    e.close()
