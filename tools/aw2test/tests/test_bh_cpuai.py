"""The BH Campaign's enemy acts (docs/AW2.md, "AI roles"): with the player passive, each mission's enemy moves,
captures and builds. `-k bh_cpuai_probe` writes tools/aw2test/out/ds/<test>/probe.json for the audit table."""

import json
import os

from aw2test import cpuprobe as cp
from aw2test.harness import test

SHOTS = os.environ.get("AW2TEST_CPUAI_SHOTS")


def _probe(n):
    def fn(ctx):
        e, g, d, me, snaps, front = cp.run(ctx, n, days=6, shots=(1, 2, 3, 4, 5) if n == 2 else None)
        r = cp.analyse(n, me, snaps)
        if front:
            r["front2"] = cp.analyse(n, 1, front)
        ctx.log(json.dumps(r, default=str))
        with open(os.path.join(ctx.out, "probe.json"), "w") as f:
            json.dump(r, f, default=str)
        e.close()
    fn.__name__ = f"bh_cpuai_probe_m{n}"
    test(modes=("ds",))(fn)


for _n in cp.M:
    _probe(_n)


# --- the test bot as the player (opt-in: AW2TEST_CPUAI_BOT=1; one game takes minutes) ------------------
def _bot(n, seed=None):
    def fn(ctx):
        from aw2test.harness import Skip
        if not os.environ.get("AW2TEST_CPUAI_BOT"):
            raise Skip("AW2TEST_CPUAI_BOT not set")
        e, r = cp.bot_run(ctx, n, seed)
        ctx.log(json.dumps(r))
        with open(os.path.join(ctx.out, "bot.json"), "w") as f:
            json.dump(r, f)
        e.close()
    fn.__name__ = f"bh_cpuai_bot_m{n}" + (f"_{seed}" if seed is not None else "")
    test(modes=("ds",))(fn)


for _n in cp.M:
    _bot(_n)


# --- the enemy acts: every mission, the player passive for five CPU days ----------------------------------
# What a mission may leave undone, and why (everything else must pass):
NO_CAPTURE = {
    14: "the mission is lost on day 2 to the passive player (Crumb): no time to capture",
    28: "the coalition's foot soldiers march 15 cells across a 34 x 30 map to the fortress: first captures after day 6",
    30: "Nell's camp is dug in (the design holds its armour until day 7 and caps its treasury)",
}
NO_BUILD = {
    5: "a pre-deployed raid: Green Earth has no production tiles and no funds",
    9: "a pre-deployed convoy: no production tiles and no funds",
    14: "no production tiles and no funds",
    31: "Sonja's raiders have no funds (her one port is for the trucks)",
}
DESIGNED_CAMPS = {
    14: "Crumb's ring and the gap guards hold until day 3",
    29: "the Orange Gate's guns and Anti-Air hold behind the wall",
    30: "Nell's camp holds its armour until day 7",
    31: "the trucks march and the road blocks hold",
}
TRANSPORTS = (7, 18, 23)    # an APC, a Black Boat, a Lander: the engine's load and unload logic moves them
MOVERS = (1, 3, 4, 7)       # the roles that walk: 1 the enemy HQ, 3 properties, 4 units, 7 by the HQ
ANTI_AIR_ONLY = (15, 16)    # Missiles and Fighters hit aircraft only: with no aircraft against them, role 4 has no target to walk to


def _acts(n):
    def fn(ctx):
        e, g, d, me, snaps, front = cp.run(ctx, n, days=6)
        r = cp.analyse(n, me, snaps)
        with open(os.path.join(ctx.out, "probe.json"), "w") as f:
            json.dump(r, f, default=str)
        ctx.log(json.dumps({k: r[k] for k in ("start_units", "moved_by_day4", "captures", "builds", "max_funds", "producing_tiles")}, default=str))
        ctx.log("roles: " + json.dumps(r["roles"]))
        # 1. the units that are meant to advance did (alive and gone from their start cell, or dead, by day 4)
        movers = [u for u in r["units0"] if u[5] in MOVERS and u[2] not in ANTI_AIR_ONLY]
        went = [u for u in movers if u[8] or not u[7]]
        ctx.check(len(movers) >= 1, f"M{n}: the enemy has units with an advance order ({len(movers)})")
        ctx.check(len(went) * 3 >= len(movers) * 2, f"M{n}: at least two thirds of the {len(movers)} advancing units left their cells by day 4 ({len(went)})")
        # 1b. only a minority holds (the garrisons: HQ guards and what the mission's design calls for)
        started = [u for u in r["units0"] if u[5] != 6 and u[2] not in TRANSPORTS]
        holding = [u for u in started if u[5] == 0]
        if n not in DESIGNED_CAMPS:
            ctx.check(len(holding) * 100 <= len(started) * 35, f"M{n}: at most 35% of the enemy's units hold ({len(holding)} of {len(started)})")
        # 2. foot soldiers capture where properties are within reach
        foot = [u for u in r["units0"] if u[5] == 3 and u[2] in (1, 2)]
        if foot and n not in NO_CAPTURE:
            ctx.check(len(r["captures"]) >= 1, f"M{n}: the enemy's Infantry and Mechs capture a property within five days ({r['captures']})")
        # 3. it builds where it has a base, airport or port and the funds
        tiles = {int(a): v for a, v in r["producing_tiles"].items() if v}
        rich = {a for a, v in tiles.items() if r["max_funds"].get(str(a), 0) >= 1000}
        if rich and n not in NO_BUILD:
            built = [b for b in r["builds"] if b[1] in rich and b[4] is not None]
            ctx.check(len(built) >= 1, f"M{n}: the enemy builds on a base, airport or port ({len(built)} new units there; funds {r['max_funds']})")
        # 4. the other front's enemy advances too
        if len(front) >= 2:
            rf = cp.analyse(n, 1, front)
            ctx.log("front 2: " + json.dumps({k: rf[k] for k in ("start_units", "moved_by_day4", "captures", "builds")}, default=str) + " roles " + json.dumps(rf["roles"]))
            fm = [u for u in rf["units0"] if u[5] in MOVERS and u[2] not in ANTI_AIR_ONLY]
            fwent = [u for u in fm if u[8] or not u[7]]
            ctx.check(len(fm) >= 1 and len(fwent) * 2 >= len(fm), f"M{n}: at least half of the other front's {len(fm)} advancing units left their cells by day 4 ({len(fwent)})")
        e.close()
    fn.__name__ = f"bh_cpuai_acts_m{n}"
    test(modes=("ds",))(fn)


for _n in cp.M:
    _acts(_n)
