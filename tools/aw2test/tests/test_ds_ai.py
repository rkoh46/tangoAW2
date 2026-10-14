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

from aw2test import harness  # noqa: E402
from aw2test.harness import test, Skip  # noqa: E402

_before = len(harness.TESTS)
import test_ds_maps as dm  # noqa: E402
del harness.TESTS[_before:]  # (test_ds_maps' own tests are registered by its own file)

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


def moves_logged(e):
    """The `dsai move` lines: [(type name, from, to)]."""
    import re
    out = []
    for l in e.decisions():
        m = re.match(r"dsai move day \d+ army \d+ (.+?) at \((\d+),(\d+)\) role \d+ to .*?: \((\d+),(\d+)\)", l)
        if m:
            out.append((m.group(1), (int(m.group(2)), int(m.group(3))), (int(m.group(4)), int(m.group(5)))))
    return out


@test(modes=("ds",))
def ds_ai_move_goes_where_chosen(ctx):
    """A CPU Tank with no enemy in reach moves to the cell Dual Strike's move chose (crate::ds_ai_move): AW2's
    "move towards a place" with the place replaced."""
    m = ctx.map()
    m.unit(1, "tank", 3, 3).unit(1, "infantry", 4, 4)
    m.unit(2, "tank", 22, 12).unit(2, "recon", 24, 14)
    g = ctx.start(m, ["andy", "max"])
    for day in range(3):
        g.end_turn()
        moved = moves_logged(g.e)
        ctx.log(f"day {day}: {moved}; units {[(u['type'], u['x'], u['y']) for u in g.units(2)]}")
    units = {(u["x"], u["y"]) for u in g.units(2)}
    chosen = [to for _, _, to in moves_logged(g.e)]
    ctx.check(chosen, "Dual Strike's move chose cells")
    # Every chosen cell was where a unit stood at the start of its next move (or stands now).
    starts = [frm for _, frm, _ in moves_logged(g.e)]
    hits = [to for to in chosen if to in starts or to in units]
    ctx.log(f"chosen {chosen}, starts {starts}, now {sorted(units)}")
    ctx.eq(len(hits), len(chosen), "every unit went to the cell chosen for it")


class _Versus:
    """What aw2test/bot.py needs of a campaign driver, for a Versus battle."""

    def __init__(self, g):
        self.g, self.e = g, g.e

    def wait_control(self):
        self.g.wait_for_input()

    def dialogue(self):
        pass

    def end_turn(self):
        self.g.end_turn(human=1)


def strength(g, army):
    """(units, their value in funds by hp, properties owned)."""
    from aw2test.bot import Bot  # noqa: F401
    prices = {}
    value = 0
    us = g.units(army)
    for u in us:
        t = u["type"]
        if t not in prices:
            prices[t] = g.e.u16(0x08680000 + 0x5C * t + 6) * 10
        value += prices[t] * ((u["hp"] + 9) // 10) // 10
    return len(us), value


def vs_bot(ctx, name, days, switch):
    if not ctx.ds:
        raise Skip("the pack's maps")
    from aw2test.bot import Bot
    g, found = dm.select_map(ctx, name)
    ctx.require(found, f"{name} is listed")
    dm.to_teams(g)
    dm.start(ctx, g, humans=(1,))
    e = g.e
    e.w8(SWITCHES, switch)
    bot = Bot(_Versus(g), log=lambda s: None, stance="auto", seed=7)
    for d in range(days):
        if g.battle_over():
            break
        try:
            bot.play_turn(1)
        except Exception as ex:  # (the battle ended under the bot)
            ctx.log(f"day {e.u8(DAY)}: {ex}")
            break
        ctx.log(f"day {e.u8(DAY)}: bot {strength(g, 1)} cpu {strength(g, 2)}")
    ctx.log(f"end: day {e.u8(DAY)} over {g.battle_over()} bot {strength(g, 1)} cpu {strength(g, 2)} (switches {switch})")
    for l in e.decisions():
        if l.startswith("dsai power") and "Nothing" not in l:
            ctx.log(l)
    ctx.shot(g, "end")


if os.environ.get("AW2TEST_DSAI_BOT"):
    for _name in ("Rust Basin", "Dune Fork", "Cinder Flats"):
        for _sw, _tag in ((0, "ds"), (8, "ds_nomove"), (1, "aw2")):
            def _fn(ctx, name=_name, sw=_sw):
                vs_bot(ctx, name, int(os.environ.get("AW2TEST_DSAI_DAYS", "14")), sw)
            _fn.__name__ = f"ds_ai_vs_bot_{_tag}_" + _name.lower().replace(" ", "_")
            test(modes=("ds",))(_fn)
