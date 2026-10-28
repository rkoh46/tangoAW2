"""Aria's Vengeance in numbers and pictures (`aw2dev co sheet vengeance`): the game's own damage forecast (the damage box shown while choosing a target, the attacker's battle record `display`) for common matchups at 10, 8 and 5
displayed HP, for a neutral CO (Andy), Aria without Vengeance (at 10 HP), Aria with Vengeance (8 and 5 HP) and Aria in Build Anew; cross-checked against the damage formula; and screenshots of the forecast box."""

import json
import os

from aw2test import damage
from aw2test.harness import test
from aw2test import coverify as cv

MATCHUPS = [("infantry", "infantry", 1), ("tank", "tank", 1), ("tank", "infantry", 1), ("mdtank", "tank", 1), ("artillery", "tank", 2), ("bcopter", "tank", 1), ("fighter", "bcopter", 1)]
HPS = (100, 80, 50)          # internal HP of 10, 8 and 5 displayed


def forecast_at(ctx, g, att, dfd, x, y, dist):
    """Select the unit at (x, y), keep it there, choose Fire: the target cursor is on the only target and the forecast box is up: the attacker's battle record's `display` is the forecast's number."""
    g.select(x, y)
    g.move_to(x, y)
    g.choose("Fire", g.ACTION_MENU)
    g.e.wait(30)
    ra, rd = ctx.battle_records(g)
    return ra


def cancel(g):
    for _ in range(4):
        g.e.press("B", 4)
        g.e.wait(10)
    g.wait_for_input()


COLUMNS = [(5, 2), (15, 2), (25, 2)]      # three columns of seven matchups, one attacker HP each


@test(modes=("ds",))
def aria_vengeance_forecast_table(ctx):
    """Three games (Andy, Aria, Aria in Build Anew); in each, 21 attackers (7 matchups x 10 / 8 / 5 displayed HP) each fire once at a full-HP target. For each: the forecast box's number (the attacker's battle record's `display`
    while the target cursor is up: the number the game draws) and, after the shot, the same record against the calculator (the game's forecast in Dual Strike's order: `Ctx.attack`'s formula)."""
    rows = {}
    conds = (("Andy", "andy", False), ("Aria", "aria", False), ("Aria, Build Anew", "aria", True))
    shots = None
    for label, co, power in conds:
        m = ctx.map()
        pos = {}
        for k, (a, d, dist) in enumerate(MATCHUPS):
            for c, hp in enumerate(HPS):
                x, y = COLUMNS[c][0], 1 + 2 * k
                m.unit(1, a, x, y).unit(2, d, x + dist, y)
                pos[(k, hp)] = (x, y)
        g = ctx.start(m, [co, "andy"], humans=(1,), env=cv.ENV)
        if power:
            ctx.power(g, 1, "super")
        shots = {(1, 80): f"fc_{co}{'_power' if power else ''}_tank8", (1, 50): f"fc_{co}{'_power' if power else ''}_tank5"}
        for (k, hp), (x, y) in pos.items():
            a, d, dist = MATCHUPS[k]
            ctx.set_hp(g, x, y, hp)
            a0, d0 = g.unit_at(x, y), g.unit_at(x + dist, y)
            side_a = ctx.side(g, a0, terrain=g.terrain_class(x, y))
            g.select(x, y)
            g.move_to(x, y)
            g.choose("Fire", g.ACTION_MENU)
            g.e.wait(30)
            # cycle the target cursor onto this matchup's target (Artillery has the other rows' enemies in range too), read the box, then fire
            for key in ["RIGHT"] * 8 + ["DOWN"] * 8:
                if g.cursor() == (x + dist, y):
                    break
                g.e.press(key, 4)
                g.e.wait(8)
            ctx.eq(g.cursor(), (x + dist, y), "the target cursor is on the matchup's target")
            g.e.wait(30)
            box = ctx.battle_records(g)[0]["display"]
            if shots is not None and (k, hp) in shots:
                ctx.shot(g, shots[(k, hp)])
            g.e.press("A", 4)
            g.wait_for_input()
            ra, rd = ctx.battle_records(g)
            first = damage.strike(ctx.rules, side_a, ctx.side(g, d0), dist, True, a0["hp"])
            want = damage.div(damage.div(first.base * first.acc, 100) * damage.hp_bars(a0["hp"]), 10)
            want = min(999, damage.div((200 - rd["defence"]) * want, 100))
            ctx.eq(ra["display"], want, f"{label}: {a} {hp // 10} HP -> {d}: the game's number after the shot equals the formula's ({want})")
            ctx.eq(ra["base"], first.base, f"{label}: {a} {hp // 10} HP -> {d}: base damage equals the chart's x firepower ({first.base})")
            rows[f"{label}|{a}|{d}|{hp // 10}"] = {"box": box, "after": ra["display"], "formula": want, "base": ra["base"]}
            ctx.log(f"{label}: {a} {hp // 10} HP -> {d}: box {box}%, record {ra['display']}%, formula {want}%, base {ra['base']}")
        g.e.close()
    json.dump(rows, open(os.path.join(ctx.out, "forecast.json"), "w"), indent=1)
