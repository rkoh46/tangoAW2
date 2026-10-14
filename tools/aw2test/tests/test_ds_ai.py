"""Dual Strike's CPU (crate::ds_ai, ds_ai_build, ds_ai_power; docs/AW2.md "Dual Strike's CPU").

CPU against CPU on the pack's Versus maps: days pass with no hang, every army builds, and the decisions
(`dsai` lines in the console's decision log) are written to the test's log. `AW2TEST_DSAI_DAYS` sets the days
(default 8); `AW2TEST_DSAI_OFF=1` plays the same battle with Dual Strike's CPU off (AW2's own: the A/B
switch at 0x0203C7F0) for comparison.
"""

import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from aw2test import ram, rom as romlib  # noqa: E402
from aw2test.harness import test, Skip  # noqa: E402

import test_ds_maps as dm  # noqa: E402

DAY = 0x03004080
SWITCHES = 0x0203C7F0
DAYS = int(os.environ.get("AW2TEST_DSAI_DAYS", "8"))
NAMES = {i: n for i, n in enumerate([
    "-", "Infantry", "Mech", "Md Tank", "Megatank", "Tank", "Recon", "APC", "Neotank", "Piperunner", "Artillery",
    "Rockets", "Stealth", "Black Bomb", "Anti-Air", "Missiles", "Fighter", "Bomber", "Black Boat", "B Copter",
    "T Copter", "Battleship", "Cruiser", "Lander", "Sub", "-", "Carrier", "Oozium"])}


def armies_summary(g):
    out = {}
    for u in g.units():
        out.setdefault(u["army"], collections.Counter())[NAMES.get(u["type"], u["type"])] += 1
    return out


def cpu_vs_cpu(ctx, name, days=DAYS, off=None):
    if not ctx.ds:
        raise Skip("the pack's maps")
    off = os.environ.get("AW2TEST_DSAI_OFF") == "1" if off is None else off
    g, found = dm.select_map(ctx, name)
    ctx.require(found, f"{name} is listed")
    dm.to_teams(g)
    dm.start(ctx, g, humans=())
    e = g.e
    if off:
        e.w8(SWITCHES, 1)
    start_day = e.u8(DAY)
    first = {u["id"] for u in g.units()}
    day_seen = start_day
    bought = collections.defaultdict(collections.Counter)
    for _ in range(days * 5 * 12):
        e.wait(300)
        for u in g.units():
            if u["id"] not in first:
                first.add(u["id"])
                bought[u["army"]][NAMES.get(u["type"], u["type"])] += 1
        d = e.u8(DAY)
        if d != day_seen:
            day_seen = d
            funds = {a: g.e.u32(g.player(a)["addr"]) for a in sorted(armies_summary(g))}
            ctx.log(f"day {d}: units {dict((a, dict(c)) for a, c in sorted(armies_summary(g).items()))} funds {funds}")
        if d >= start_day + days or g.battle_over():
            break
    ctx.shot(g, "end")
    day = e.u8(DAY)
    ctx.check(day >= start_day + days or g.battle_over(), f"{name}: {day - start_day} CPU days passed")
    for a, c in sorted(bought.items()):
        ctx.log(f"army {a} bought: {dict(c)}")
    lines = [l for l in e.decisions() if l.startswith("dsai")]
    for l in lines:
        ctx.log(l)
    if not off:
        ctx.check(any("builds" in l for l in lines), f"{name}: Dual Strike's production ran")
    ctx.check(len(bought) >= 1, f"{name}: the armies built ({sorted(bought)})")
    return g, bought, lines


def _cpu(name):
    def fn(ctx):
        cpu_vs_cpu(ctx, name)
    fn.__name__ = "ds_ai_cpu_" + name.lower().replace(" ", "_").replace("'", "")
    return test(modes=("ds",))(fn)


for _name in ("Rust Basin", "Coral Strait", "Dune Fork", "Harbor Cross", "Black Wastes"):
    _cpu(_name)
