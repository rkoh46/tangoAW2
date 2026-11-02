"""The CPU uses every unit it has (crate::cpu_units, docs/dev/cpu-unit-use.md): no unit of its starting army sits on a base, port or
airport for more than a turn when it can move; a Black Boat leaves its port, repairs a damaged neighbour and follows its fleet; a Lander
idle on a port steps off; every Dual Strike unit type takes an action. `-k cpu_unit_use`."""

from aw2test import rom as romlib
from aw2test.game import NavError
from aw2test.harness import test

DS = ("ds",)
PRODUCTION = {10, 11, 14}      # airport, port, base (terrain classes)
USED = ("Black Boat", "Carrier", "Stealth", "Black Bomb", "Piperunner", "Oozium", "Megatank", "Lander")


def sheet(g, armies=(2,)):
    return {u["id"]: (u["army"], romlib.UNIT_NAMES[u["type"]], u["x"], u["y"], u["hp"], u["flags"])
            for a in armies for u in g.units(army=a) if not u["flags"] & 0x08}


def on_production(g, v):
    return g.terrain_class(v[2], v[3]) in PRODUCTION


def idle_on_production(g, days, first_only=()):
    """Unit ids that stand on a production cell in two snapshots in a row (the starting ids only), with their names."""
    bad = {}
    for before, after in zip(days, days[1:]):
        for i, v in after.items():
            if i in days[0] and i in before and on_production(g, v) and on_production(g, before[i]) and (v[2], v[3]) == (before[i][2], before[i][3]):
                bad[i] = v[1]
    return bad


def acted(days):
    """Names of the unit types that took an action: moved, hid, or are gone (a bomb)."""
    out = set()
    for i, v in days[0].items():
        for later in days[1:]:
            w = later.get(i)
            if w is None or (w[2], w[3]) != (v[2], v[3]) or w[5] & 0x20:
                out.add(v[1])
    return out


def sea_map(ctx):
    m = ctx.map()
    for x in range(6, 28):
        for y in range(8, 18):
            m.terrain(x, y, "sea")
    for x in range(3, 28):
        m.terrain(x, 3, "pipe")
    m.terrain(22, 12, "port", 2).terrain(22, 14, "port", 2)
    m.terrain(25, 5, "base", 2).terrain(27, 4, "base", 2).terrain(27, 6, "airport", 2).terrain(27, 2, "airport", 2)
    m.unit(2, "blackboat", 22, 12).unit(2, "cruiser", 21, 12).unit(2, "lander", 22, 14).unit(2, "infantry", 24, 6)
    m.unit(2, "carrier", 18, 14).unit(2, "megatank", 25, 5).unit(2, "oozium", 27, 4)
    m.unit(2, "stealth", 27, 6).unit(2, "blackbomb", 27, 2).unit(2, "piperunner", 25, 3)
    m.unit(1, "tank", 4, 6).unit(1, "infantry", 5, 8).unit(1, "mdtank", 3, 4).unit(1, "artillery", 3, 6)
    m.unit(1, "cruiser", 9, 12)
    return m


def run_versus(ctx, days=4):
    g = ctx.start(sea_map(ctx), ["andy", "andy"])
    ctx.set_hp(g, 21, 12, 50)
    g.e.w32(g.player(2)["addr"], 20000)
    out = [sheet(g)]
    for _ in range(days):
        g.end_turn()
        out.append(sheet(g))
    return g, out


@test(modes=DS)
def cpu_unit_use_versus_every_unit_acts(ctx):
    g, days = run_versus(ctx)
    for n, d in enumerate(days):
        ctx.log(f"day {n}: " + str({i: v[1:5] for i, v in d.items() if v[1] in USED}))
    names = acted(days)
    for t in USED:
        ctx.check(t in names, f"the CPU's {t} took an action")
    ctx.eq(idle_on_production(g, days), {}, "no starting unit stays on a base, port or airport for a turn")


@test(modes=DS)
def cpu_unit_use_black_boat_repairs_a_neighbour(ctx):
    g, days = run_versus(ctx, 2)
    cruiser = [v for v in days[-1].values() if v[1] == "Cruiser"]
    boat = [v for v in days[-1].values() if v[1] == "Black Boat"]
    ctx.log(f"cruiser {cruiser}, boat {boat}")
    ctx.check(cruiser and cruiser[0][4] >= 60, f"the Black Boat repaired the damaged Cruiser by day 2 ({cruiser})")
    ctx.check(boat and not on_production(g, boat[0]), "the Black Boat is not on a port")


@test(modes=DS)
def cpu_unit_use_boat_frees_the_port_to_build(ctx):
    """A boat on a port and funds: the port builds on the CPU's turn (the cell is free after the boat leaves)."""
    m = ctx.map()
    for x in range(6, 28):
        for y in range(8, 18):
            m.terrain(x, y, "sea")
    m.terrain(22, 12, "port", 2)
    m.unit(2, "blackboat", 22, 12).unit(2, "cruiser", 21, 12).unit(1, "tank", 4, 6)
    g = ctx.start(m, ["andy", "andy"])
    ctx.set_hp(g, 21, 12, 40)
    g.e.w32(g.player(2)["addr"], 30000)
    g.end_turn()
    boat = [u for u in g.units(2) if u["type"] == 18][0]
    ctx.check((boat["x"], boat["y"]) != (22, 12), f"the Black Boat left the port ({boat['x'], boat['y']})")
    ships = [u for u in g.units(2) if (u["x"], u["y"]) == (22, 12)]
    ctx.log(f"the port's cell: {ships}")


@test(modes=DS, netplay=True)
def netplay_cpu_unit_use(ctx):
    g, _ = run_versus(ctx, 2)
    identical, _, text = ctx.netplay_replay(g, [])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: both peers and the straight replay identical")


def gauntlet_days(ctx, days):
    """Cinder Sea in the Gauntlet (docs/dev/gauntlet-mode.md) with the player passive: the enemy armies' DS units' cells after each CPU day."""
    from aw2test import gauntlet as ga
    from aw2test import paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    d.start(ga.ANDY)
    out = []
    for day in range(days):
        g._units_base = g._players_base = None
        out.append({u["id"]: (u["army"], romlib.UNIT_NAMES[u["type"]], u["x"], u["y"], u["hp"]) for a in (2, 3, 4) for u in g.units(army=a)})
        for attempt in range(4):
            try:
                d.wait_control()
                d.end_turn()
                break
            except NavError as ex:
                ctx.log(f"end turn, try {attempt}: {ex}")
                for _ in range(20):
                    e.press("B" if attempt % 2 else "A", 4)
                    e.wait(20)
        for _ in range(3000):
            if g.current_army() == 1 and d.in_battle() and not d.scripts_running():
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        d.wait_control()
    g._units_base = g._players_base = None
    out.append({u["id"]: (u["army"], romlib.UNIT_NAMES[u["type"]], u["x"], u["y"], u["hp"]) for a in (2, 3, 4) for u in g.units(army=a)})
    return g, out


@test(modes=DS)
def cpu_unit_use_gauntlet_cinder_sea(ctx):
    """Cinder Sea's fleets: every Black Boat the enemy has (they build them) leaves its port the turn after it is built, and none sits on a port two days running."""
    g, days = gauntlet_days(ctx, 5)
    boats = {}
    for n, d in enumerate(days):
        ctx.log(f"day {n}: " + str({i: v[1:] for i, v in d.items() if v[1] in ("Black Boat", "Carrier", "Lander")}))
        for i, v in d.items():
            if v[1] == "Black Boat":
                boats.setdefault(i, []).append((v[2], v[3]))
    ctx.check(boats, "the enemy has Black Boats in Cinder Sea")
    for i, cells in boats.items():
        stuck = [c for c, nxt in zip(cells, cells[1:]) if c == nxt and g.terrain_class(*c) == 11]
        ctx.check(not stuck, f"Black Boat {i} never stays on a port ({cells})")
