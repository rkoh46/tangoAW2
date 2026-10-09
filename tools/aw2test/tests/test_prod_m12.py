"""Unit production in the BH Campaign's M12 "Highway to the Horizon" (needs the act 3 tree: skipped without it).
Yellow Comet's base at (32, 6) touches a long pipe, so the CPU can build a Piperunner there; Black Hole's
factory never does (its table F12 has a Md Tank where it once had a Piperunner)."""

from aw2test import ram
from aw2test.game import NavError
from aw2test.harness import Skip, test

PIPERUNNER = 9


@test(modes=("ds",))
def bh_act3_m12_cpu_piperunner_by_the_highway_factory_never(ctx):
    import importlib.util
    import os
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "test_bh_act3.py")
    if not os.path.exists(path):
        raise Skip("act 3 is not in this tree")
    spec = importlib.util.spec_from_file_location("test_bh_act3_for_prod", path)
    t3 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(t3)
    a3 = t3.a3
    e, g, d, _ = t3.ready(ctx, 12)
    cls = lambda x, y: g.terrain_class(x, y) & 0x1F
    ctx.log("terrain around (32, 6): " + str([[cls(x, y) for x in range(28, 37)] for y in range(3, 10)]))
    pipes = {(x, y) for x in range(36) for y in range(18) if cls(x, y) in (15, 16)}
    seen, stack = set(), [p for p in ((32, 5), (33, 6), (32, 7), (31, 6)) if p in pipes]
    while stack:
        p = stack.pop()
        if p not in seen:
            seen.add(p)
            stack += [(p[0] + dx, p[1] + dy) for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)) if (p[0] + dx, p[1] + dy) in pipes]
    ctx.log(f"the pipe network at (32, 6): {len(seen)} cells; base class {cls(32, 6)}")
    # The map's own Piperunners count against the CPU's buying rule (half as many as the unit it stands in for):
    # turn them into Infantry so the rule under test is the pipe network.
    for u in g.units(2):
        if u["type"] == PIPERUNNER:
            e.w8(g.unit_addr(u["id"]), 1)
    start_ids = {u["id"] for u in g.units()}
    seen_cpu, seen_bh, bases = [], [], set()
    for day in range(2, 22):
        g._units_base = g._players_base = None
        e.w32(g.player(2)["addr"] + ram.P_FUNDS, 40000)
        try:
            a3.to_day(e, g, d, day)
        except NavError:
            ctx.log(f"the mission ended on day {day}")
            break
        seen_bh += [(day, u["x"], u["y"]) for u in g.units(1) if u["type"] == PIPERUNNER and u["id"] not in start_ids]
        for u in g.units(2):
            if u["type"] == PIPERUNNER and u["id"] not in start_ids:
                bases.add((u["x"], u["y"]))
                seen_cpu.append(day)
    ctx.log(f"Yellow Comet Piperunners on days {sorted(set(seen_cpu))} at {sorted(bases)}; Black Hole's: {seen_bh}")
    ctx.check(seen_cpu, "the CPU builds a Piperunner at Yellow Comet's base by the highway pipe")
    ctx.check(not seen_bh, "the Black Hole factory never builds a Piperunner (F12 once asked for one on day 7; its slot is now a Md Tank)")
    e.close()
