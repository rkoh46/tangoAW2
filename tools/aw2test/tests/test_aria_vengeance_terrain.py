"""Aria's Vengeance defence on 1, 2, 3 and 4 star terrain (crate::aria, co_roster::defence_total): her Infantry on plain, wood, city and
an HQ (4 stars), and her Tanks on the same four, at 10, 8, 5, 2 and 1 displayed HP, struck
by Andy's Mech / Tank. For every cell: the game's damage forecast equals the calculator's (terrain stars x HP bars + 100 + her flat 8% +
Vengeance, under AW2's cap at 200), the real loss is inside the calculator's range, and the forecast is lower than the same strike on Andy's
own unit (the twin). The forecast frames are kept for the review sheet (python3 -m aw2.colib.vengeance_terrain_sheet)."""

import os

from aw2test import damage
from aw2test.harness import test

HPS = [100, 80, 50, 20, 10]
CASES = {
    "infantry": ("mech", ["plain", "wood", "city", "hq"]),
    "tank": ("tank", ["plain", "wood", "city", "hq"]),
}


def play(ctx, co, kind, cells, hq=None):
    """One game: her `kind` on each (terrain, hp, x, y) with Andy's attacker below; `hq` = (x, y) puts her own HQ there (one HQ per army)."""
    from aw2test import coverify as cv
    attacker = CASES[kind][0]
    m = ctx.map(hq=((1, *hq), (2, 29, 19)) if hq else ((1, 0, 0), (2, 29, 19)))
    for ter, hp, x, y in cells:
        if ter != "hq":
            m.terrain(x, y, ter)
        m.unit(1, kind, x, y).unit(2, attacker, x, y + 1)
    g = ctx.start(m, [co, "andy"], humans=(1, 2), env=cv.ENV)
    for _, hp, x, y in cells:
        ctx.set_hp(g, x, y, hp)
    g.end_turn(human=2)
    res = {}
    for ter, hp, x, y in cells:
        a, d = g.unit_at(x, y + 1), g.unit_at(x, y)
        out = damage.strike(ctx.rules, ctx.side(g, a), ctx.side(g, d, terrain=g.terrain_class(x, y)), 1, True, a["hp"])
        g.select(x, y + 1)
        g.move_to(x, y + 1)
        g.choose("Fire", g.ACTION_MENU)
        g.e.wait(40)
        shot = g.e.shot(os.path.join(ctx.out, f"{co}_{kind}_{ter}_hp{(hp + 9) // 10}"))
        shown = ctx.battle_records(g)[0]["display"]
        for _ in range(3):
            g.e.press("B", 4)
            g.e.wait(10)
        g.wait_for_input()
        g.attack((x, y + 1), (x, y + 1), (x, y))
        after = g.unit_at(x, y)
        loss = hp - (after["hp"] if after else 0)
        res[(ter, hp)] = dict(shot=shot, shown=shown, loss=loss, out=out, stars=ctx.rules.stars(g.terrain_class(x, y)))
    g.e.close()
    return res


def run(ctx, co, kind):
    terrains = CASES[kind][1]
    cells = [(ter, hp, 3 + 5 * k, 2 + 4 * t) for t, ter in enumerate(terrains) if ter != "hq" for k, hp in enumerate(HPS)]
    res = play(ctx, co, kind, cells)
    if "hq" in terrains:
        for hp in HPS:
            res.update(play(ctx, co, kind, [("hq", hp, 14, 14)], hq=(14, 14)))
    return res


def check_kind(ctx, kind):
    aria = run(ctx, "aria", kind)
    andy = run(ctx, "andy", kind)
    for (ter, hp), r in aria.items():
        out, tw = r["out"], andy[(ter, hp)]
        h = (hp + 9) // 10
        v = damage.aria_vengeance(hp)
        ctx.check(out.defence <= 200, f"{kind} on {ter} ({r['stars']} stars) at {h} HP: defence {out.defence} is under AW2's cap")
        ctx.check(r["shown"] == min(out.losses), f"{kind} on {ter} ({r['stars']} stars) at {h} HP (+{damage.ARIA_FLAT + v}%): forecast {r['shown']}% = the calculator's {min(out.losses)}% (defence {out.defence})")
        ctx.check(r["loss"] in out.losses, f"{kind} on {ter} at {h} HP: real loss {r['loss']} inside {sorted(out.losses)}")
        ctx.check(r["shown"] < tw["shown"] or tw["shown"] == 0, f"{kind} on {ter} at {h} HP: {r['shown']}% against Andy's {tw['shown']}%")
        ctx.log(f"{kind} on {ter} ({r['stars']}*) {h} HP: Aria {r['shown']}% / Andy {tw['shown']}% (defence {out.defence})")


@test(modes=("ds",))
def aria_vengeance_terrain_infantry(ctx):
    """Her Infantry on plain, wood, city and an HQ (1 to 4 stars) under Andy's Mech: forecast, real loss and the twin."""
    check_kind(ctx, "infantry")


@test(modes=("ds",))
def aria_vengeance_terrain_tank(ctx):
    """Her Tanks on plain, wood, city and an HQ (1 to 4 stars) under Andy's Tank: forecast, real loss and the twin."""
    check_kind(ctx, "tank")
