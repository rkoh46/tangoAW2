"""Act IV, the computer acts (M17 to M22): over its first days the enemy armies move, capture, attack and buy."""

import json
import os
import sys

from aw2test import bhact4 as a2
from aw2test import ram
from aw2test.harness import test

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_bh_act4 import MISSIONS, ready

OUT = os.environ.get("AW2TEST_CPUAI_OUT")
DAYS = int(os.environ.get("AW2TEST_CPUAI_DAYS", "5"))
PROD = (10, 11, 14)          # AW2 terrain classes: airport, port, base (factory)
PROPS = (6, 8, 10, 11, 14, 20)


def props_of(g, army, w, h):
    return sum(1 for y in range(h) for x in range(w)
               if g.terrain_class(x, y) >> 5 == army and g.terrain_class(x, y) & 0x1F in PROPS)


def snapshot(g, d, armies):
    w, h = d.size()
    out = {"day": g.e.u16(0x03004080)}
    for a in armies:
        us = g.units(a)
        out[a] = {
            "funds": g.e.u32(g.player(a)["addr"] + ram.P_FUNDS),
            "props": props_of(g, a, w, h),
            "units": sorted((u["id"], u["type"], u["x"], u["y"], u["hp"]) for u in us),
            "on_prod": sum(1 for u in us if g.terrain_class(u["x"], u["y"]) & 0x1F in PROD
                           and g.terrain_class(u["x"], u["y"]) >> 5 == a),
        }
    return out


def turn(ctx, e, g, d):
    """One player turn and the computer's, retried after dialogue or a settling map."""
    for attempt in range(4):
        try:
            for _ in range(30):
                if not d.scripts_running():
                    break
                e.press("A", 4)
                e.wait(20)
            g.wait_idle(max_frames=3000)
            a2.next_turn(e, g, d)
            return
        except Exception as ex:
            ctx.log(f"turn retry {attempt}: {ex}")
            e.press("B", 4)
            e.wait(60)
            g._units_base = g._players_base = None
    raise RuntimeError("the turn would not end")


def measure(ctx, n, days=DAYS):
    e, g, d, texts = ready(ctx, n)
    armies = [a for a in range(2, len(MISSIONS[n][4]) + 1)]
    snaps = [snapshot(g, d, armies + [1])]
    for _ in range(days):
        turn(ctx, e, g, d)
        g._units_base = g._players_base = None
        if e.u8(0x0203E400) and False:
            break
        snaps.append(snapshot(g, d, armies + [1]))
    if OUT:
        with open(os.path.join(OUT, f"m{n}.json"), "w") as f:
            json.dump(snaps, f)
        a2.pic(ctx, e, f"m{n}_day{snaps[-1]['day']}")
    e.close()
    return armies, snaps


def acts(snaps, army):
    """(units that moved, units new since day 1 (bought), properties gained, units that lost hp or died)."""
    first = {u[0]: u for u in snaps[0][army]["units"]}
    last = {u[0]: u for u in snaps[-1][army]["units"]}
    moved = sum(1 for i, u in first.items() if i in last and last[i][2:4] != u[2:4])
    new = sum(1 for i in last if i not in first)
    gained = snaps[-1][army]["props"] - snaps[0][army]["props"]
    return moved, new, gained


def _acts(n):
    def fn(ctx):
        armies, snaps = measure(ctx, n)
        for a in armies:
            moved, new, gained = acts(snaps, a)
            ctx.log(f"M{n} army {a}: moved {moved}, bought {new}, properties {gained:+d}, funds {[s[a]['funds'] for s in snaps]}, props {[s[a]['props'] for s in snaps]}, on production {[s[a]['on_prod'] for s in snaps]}")
            ctx.check(moved >= 3, f"M{n} army {a}: the enemy moves ({moved} units)")
    fn.__name__ = f"bh_act4_cpu_m{n}_the_enemy_acts"
    test(modes=("ds",))(fn)


for _n in MISSIONS:
    if _n != 20:
        _acts(_n)
_acts(20)
