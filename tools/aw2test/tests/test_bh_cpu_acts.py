"""BH Campaign Act III: the Yellow Comet CPU acts (moves, captures, builds)."""

import os

from aw2test import bhact3 as a3
from aw2test import ram
from aw2test.harness import test
from tests.test_bh_act3 import ready, MISSIONS

PROPS = (6, 8, 10, 11, 14, 20)   # city, HQ, airport, port, base, lab
NAMES = {6: "city", 8: "hq", 10: "air", 11: "port", 14: "base", 20: "lab"}


def funds(e, g, army):
    return e.u32(e.u32(ram.PLAYERS_PTR) + 0x3C * army)


def props(g, w, h):
    out = {}
    for y in range(h):
        for x in range(w):
            c = g.terrain_class(x, y)
            if (c & 0x1F) in PROPS:
                out[(x, y)] = (c & 0x1F, c >> 5)
    return out


def snap(e, g, size):
    us = g.units(2)
    return {"units": {u["id"]: (u["type"], u["x"], u["y"], u["hp"]) for u in us},
            "funds": funds(e, g, 2), "props": props(g, *size)}


def run_days(ctx, n, days, cos=None):
    """The player passive: Yellow Comet's snapshots at the start of each day (1..days+1)."""
    e, g, d, texts = ready(ctx, n, cos)
    size = MISSIONS[n][4]
    snaps = [snap(e, g, size)]
    for day in range(2, days + 2):
        try:
            a3.to_day(e, g, d, day)
        except Exception as ex:
            ctx.log(f"stopped before day {day}: {ex}")
            break
        snaps.append(snap(e, g, size))
    return e, g, d, snaps


def report(ctx, n, snaps):
    first = snaps[0]
    ctx.log(f"== M{n}")
    last = snaps[-1]
    still = [(v[0], v[1], v[2]) for k, v in first["units"].items() if k in last["units"] and v[1:3] == last["units"][k][1:3]]
    gone = [v[0] for k, v in first["units"].items() if k not in last["units"]]
    ctx.log(f"never moved: {still} gone {gone}")
    ctx.log("new types: " + str(sorted(v[0] for k, v in last["units"].items() if k not in first["units"])))
    for i, s in enumerate(snaps):
        moved = sum(1 for k, v in s["units"].items() if k in first["units"] and v[1:3] != first["units"][k][1:3])
        new = [v for k, v in s["units"].items() if k not in first["units"]]
        owned = sum(1 for p, (k, o) in s["props"].items() if o == 2)
        theirs = [(NAMES[k], p) for p, (k, o) in s["props"].items() if o == 2 and first["props"].get(p, (0, 0))[1] != 2]
        ctx.log(f"day {i + 1}: units {len(s['units'])} moved-from-start {moved} new {len(new)} funds {s['funds']} props {owned} newprops {theirs}")


SHOTS = os.environ.get("AW2TEST_CPU_SHOTS")   # a folder for pictures of the enemy at work


@test(modes=("ds",))
def bh_cpu_probe(ctx):
    only = os.environ.get("PROBE_M")
    for n in ([int(only)] if only else (12, 13, 15, 16)):
        e, g, d, snaps = run_days(ctx, n, 5)
        report(ctx, n, snaps)
        e.close()


def _enemy_acts(n):
    def fn(ctx):
        e, g, d, snaps = run_days(ctx, n, 5)
        report(ctx, n, snaps)
        first, day3, last = snaps[0], snaps[2], snaps[-1]
        moved = sum(1 for k, v in day3["units"].items() if k in first["units"] and v[1:3] != first["units"][k][1:3])
        ctx.check(moved * 2 >= len(first["units"]) * 0.4, f"M{n}: {moved} of {len(first['units'])} Yellow Comet units moved by day 3")
        new = [k for k in day3["units"] if k not in first["units"]]
        ctx.check(len(new) >= 2, f"M{n}: Yellow Comet built {len(new)} units by day 3")
        ctx.check(snaps[1]["funds"] < first["funds"], f"M{n}: it spent its funds on day 1 ({first['funds']} -> {snaps[1]['funds']})")
        taken = [p for p, (k, o) in last["props"].items() if o == 2 and first["props"].get(p, (0, 0))[1] != 2]
        ctx.check(len(taken) >= 1, f"M{n}: its foot soldiers captured {len(taken)} properties by day 6")
        if SHOTS:
            os.makedirs(SHOTS, exist_ok=True)
            e.shot(os.path.join(SHOTS, f"m{n}_day6"))
        e.close()
    fn.__name__ = f"bh_cpu_m{n}_the_enemy_acts"
    test(modes=("ds",))(fn)


for _n in (12, 13, 15, 16):
    _enemy_acts(_n)
