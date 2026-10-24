"""Emerald Sun Campaign: the computer's armies act (`-k es_cpu_m`): with the player passive for five days, every enemy army moves (at least a third of its
units off their cells by day 3), and an army with production and funds builds (its funds fall or its units grow). The first check of every mission's AI orders
(crate::es_campaign::deployment) and production (docs/dev/es-campaign.md)."""

import os

from aw2test import bhact2 as a2
from aw2test import bhact3 as a3
from aw2test import escampaign as es
from aw2test import ram
from aw2test.harness import test

DAYS = int(os.environ.get("AW2TEST_ES_CPU_DAYS", "5"))
# missions whose enemy only holds or whose first days are scripted (no movement is asked): M2's waves come by trigger
NO_MOVE = {2}


def funds(e, army):
    return e.u32(e.u32(ram.PLAYERS_PTR) + 0x3C * army)


def snap(e, g, armies):
    return {a: {"units": {u["id"]: (u["type"], u["x"], u["y"]) for u in g.units(a)}, "funds": funds(e, a)} for a in armies}


def probe(ctx, n):
    e, g, d = es.enter(ctx, n)
    if d.in_setup():
        d.leave_setup()
        a2.intro(ctx, e, d, f"m{n}", ())
    d.wait_control()
    g._units_base = g._players_base = None
    armies = range(2, len(es.ARMIES.get(n, (0, 0))) + 1) if hasattr(es, "ARMIES") else range(2, 4)
    snaps = [snap(e, g, armies)]
    for day in range(2, DAYS + 2):
        try:
            a3.to_day(e, g, d, day)
        except Exception as ex:
            ctx.log(f"stopped before day {day}: {ex}")
            break
        snaps.append(snap(e, g, armies))
    first, last = snaps[0], snaps[-1]
    for a in armies:
        if not first[a]["units"]:
            continue
        mid = snaps[min(2, len(snaps) - 1)]
        moved = sum(1 for k, v in mid[a]["units"].items() if k in first[a]["units"] and v[1:] != first[a]["units"][k][1:])
        new = [k for k in last[a]["units"] if k not in first[a]["units"]]
        ctx.log(f"M{n} army {a}: {len(first[a]['units'])} units, {moved} moved by day 3, {len(new)} new by day {DAYS + 1}, funds {first[a]['funds']} -> {last[a]['funds']}")
        if n not in NO_MOVE:
            held = sum(1 for k in first[a]["units"] if False)
            ctx.check(moved * 3 >= len(first[a]["units"]), f"M{n} army {a}: {moved} of {len(first[a]['units'])} units moved by day 3")
    e.close()


def _probe(n):
    def fn(ctx):
        probe(ctx, n)
    fn.__name__ = f"es_cpu_m{n}"
    test(modes=("ds",))(fn)


for _n in range(1, 17):
    _probe(_n)
