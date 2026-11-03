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


def gauntlet_days(ctx, days, map=0, me=1, armies=(2, 3, 4)):
    """A Gauntlet map with the player (army `me`) passive: the enemy armies' units' cells after each CPU day (index 0: before the first)."""
    from aw2test import gauntlet as ga
    from aw2test import paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    e = Emu(save=paths.base_save(), ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    d = ga.Gauntlet(g)
    from aw2test import gauntlet_maps as gm
    from tests.test_gauntlet_map2 import to_player_turn
    d.start(ga.ANDY, map=map)
    to_player_turn(e, g, d, army=gm.player_army(map))

    def snap():
        g._units_base = g._players_base = None
        return {u["id"]: (u["army"], romlib.UNIT_NAMES[u["type"]], u["x"], u["y"], u["hp"], u["flags"], u["raw"][0x0B], u["ammo"])
                for a in armies for u in g.units(army=a)}
    out = []
    mine0 = [(u["x"], u["y"], u["hp"]) for u in g.units(army=me) if not u["flags"] & 8]
    for day in range(days):
        out.append(snap())
        over = False
        for attempt in range(4):
            try:
                d.wait_control()
                d.end_turn()
                break
            except NavError as ex:
                if "mission is over" in str(ex):          # (a passive player can lose to a strong line: the days so far are the sample)
                    ctx.log(f"day {day}: the mission is over (the passive player's army fell)")
                    over = True
                    break
                ctx.log(f"end turn, try {attempt}: {ex}")
                for _ in range(20):
                    e.press("B" if attempt % 2 else "A", 4)
                    e.wait(20)
        if over:
            break
        left = False
        for _ in range(3000):
            left = left or g.current_army() != me
            if left and g.current_army() == me and d.in_battle() and not d.scripts_running():
                break
            if d.scripts_running():
                e.press("A", 4)
            e.wait(10)
        try:
            d.wait_control()
        except NavError as ex:
            if "mission is over" not in str(ex):
                raise
            from aw2test import dscampaign as _dc
            ctx.log(f"day {day}: the mission is over after the computer's turn (result {e.u8(_dc.LAST_RESULT)}; the player's units {len(g.units(army=me))}, the line's {len(g.units(army=armies[0]))})")
            break
    out.append(snap())
    mine1 = [(u["x"], u["y"], u["hp"]) for u in g.units(army=me) if not u["flags"] & 8]
    return g, out, (mine0, mine1)


@test(modes=DS)
def cpu_unit_use_gauntlet_cinder_sea(ctx):
    """Cinder Sea's fleets: every Black Boat the enemy has (they build them) leaves its port the turn after it is built, and none sits on a port two days running."""
    g, days, _ = gauntlet_days(ctx, 5)
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


def acted_fractions(ctx, days, label):
    """Per CPU day the share of the CPU's units (present at its start) that moved, changed hp or used ammo; the idle ones are logged."""
    out = []
    for before, after in zip(days, days[1:]):
        moved = [i for i, v in before.items() if i not in after or (after[i][2:5], after[i][-1]) != (v[2:5], v[-1])]
        out.append(len(moved) / max(1, len(before)))
        ctx.log(f"{label}: {len(before)} units, {len(moved)} acted; idle: {sorted(v[1] for i, v in before.items() if i not in moved)}")
    return out


def closing_in(ctx, days, mine, label):
    """The CPU makes progress: its units' mean distance to the nearest of the passive player's units fell, or the player lost hit points."""
    def mean_gap(day, units):
        cells = [(x, y) for x, y, _ in units]
        pts = [(v[2], v[3]) for v in day.values()]
        return sum(min(abs(x - a) + abs(y - b) for a, b in cells) for x, y in pts) / max(1, len(pts))
    first, last = mean_gap(days[0], mine[0]), mean_gap(days[-1], mine[0])
    lost = sum(h for *_, h in mine[0]) - sum(h for *_, h in mine[1])
    ctx.log(f"{label}: mean distance to the player's units {first:.1f} -> {last:.1f}, the player lost {lost} hp")
    ctx.check(last <= first - 3 or lost > 0, f"{label}: the CPU closes in or attacks ({first:.1f} -> {last:.1f}, {lost} hp lost)")


def check_share(ctx, shares, floor, label):
    late = shares[1:] or shares
    avg = sum(late) / len(late)
    ctx.check(avg >= floor, f"{label}: on average {avg:.0%} of the CPU's units act each turn (at least {floor:.0%}: {[f'{x:.0%}' for x in shares]})")


@test(modes=DS)
def cpu_progress_gauntlet_cinder_sea(ctx):
    g, days, mine = gauntlet_days(ctx, 6)
    for n, d in enumerate(days):
        ctx.log(f"day {n} transports and foot: " + str(sorted((v[1], v[2], v[3]) for v in d.values() if v[1] in ("Lander", "Infantry", "Mech"))))
    log = [l for l in g.e.decisions() if "dsai ferry" in l]
    ctx.log("\n".join(log[:12]))
    ctx.check(any("takes the soldier" in l for l in log) and any("drops a soldier" in l for l in log), "a CPU Black Boat took soldiers aboard and dropped them in Cinder Sea")
    check_share(ctx, acted_fractions(ctx, days, "cinder sea"), 0.6, "Cinder Sea")
    closing_in(ctx, days, mine, "Cinder Sea")


@test(modes=DS)
def cpu_progress_gauntlet_iron_crown(ctx):
    g, days, mine = gauntlet_days(ctx, 5, map=1, me=5, armies=(1, 2, 3, 4))
    check_share(ctx, acted_fractions(ctx, days, "iron crown"), 0.6, "Iron Crown")
    closing_in(ctx, days, mine, "Iron Crown")


def _cpu_progress_new_map(info):
    def fn(ctx):
        # (only the first line is on the field: the later lines' armies are asleep; the CPU's units are the first line's)
        g, days, mine = gauntlet_days(ctx, 5, map=info.mission, me=info.player, armies=info.armies[:1])
        if info.sealed:
            # (Last Eclipse: the first line is shut in by pipe seams the computer does not break: its units hold their chamber, so only that they stay put and none idles on a production tile is asked
            # (cpu_port_idle_gauntlet_11))
            ctx.check(len(days) >= 2, f"{info.title}: the computer's turns end (the sealed line does not stall the game)")
            return
        check_share(ctx, acted_fractions(ctx, days, info.title.lower()), 0.6, info.title)
        closing_in(ctx, days, mine, info.title)
    fn.__name__ = f"cpu_progress_gauntlet_{info.title.lower().replace(' ', '_')}"
    test(modes=DS)(fn)


def _register_new_gauntlet_maps():
    from aw2test import gauntlet_maps as gm
    for info in gm.MAPS.values():
        _cpu_progress_new_map(info)


_register_new_gauntlet_maps()


def land_map(ctx):
    """A Versus-style land map: HQs in opposite corners, a river of mountains and woods in between, cities, a base and an army of every ground type each."""
    m = ctx.map()
    for y in range(4, 16):
        m.terrain(15, y, "mountain")
    for x, y in ((12, 8), (13, 12), (18, 6), (17, 13)):
        m.terrain(x, y, "wood")
    for x, y, a in ((10, 10, 0), (20, 9, 0), (8, 3, 0), (22, 16, 0)):
        m.terrain(x, y, "city", a)
    m.terrain(3, 3, "base", 1).terrain(26, 16, "base", 2).terrain(27, 17, "base", 2)
    for kind, x, y in (("infantry", 25, 17), ("infantry", 24, 16), ("mech", 26, 15), ("tank", 25, 15), ("tank", 24, 17), ("mdtank", 23, 16),
                       ("artillery", 27, 16), ("rockets", 26, 14), ("recon", 23, 14), ("antiair", 24, 14), ("apc", 25, 16), ("missiles", 22, 15)):
        m.unit(2, kind, x, y)
    for kind, x, y in (("infantry", 4, 3), ("tank", 5, 4), ("tank", 4, 5)):
        m.unit(1, kind, x, y)
    return m


@test(modes=DS)
def cpu_progress_versus(ctx):
    g = ctx.start(land_map(ctx), ["andy", "andy"])
    g.e.w32(g.player(2)["addr"], 0)
    days = [sheet(g)]
    for _ in range(6):
        g.end_turn()
        days.append(sheet(g))
    days = [{i: v[:5] + (v[5], 0, 0) for i, v in d.items()} for d in days]
    mine = ([(u["x"], u["y"], u["hp"]) for u in g.units(army=1)],) * 2
    check_share(ctx, acted_fractions(ctx, days, "versus"), 0.8, "Versus")
    closing_in(ctx, days, mine, "Versus")


def strait_map(ctx, boats=(("blackboat", 14, 12),), foot=(("infantry", 8, 10), ("infantry", 7, 11), ("mech", 8, 9))):
    """Two lands split by a sea strait (x 10..20): the CPU (army 2, west) has foot soldiers and only the boats given; cities and the player (army 1) are east."""
    m = ctx.map(hq=((1, 29, 0), (2, 0, 19)))
    for x in range(10, 21):
        for y in range(0, 20):
            m.terrain(x, y, "shoal" if x in (10, 20) else "sea")
    for x, y in ((22, 10), (24, 12), (23, 7), (26, 15)):
        m.terrain(x, y, "city", 0)
    for kind, x, y in foot + boats:
        m.unit(2, kind, x, y)
    m.unit(1, "tank", 27, 3).unit(1, "infantry", 28, 2)
    return m


@test(modes=DS)
def cpu_unit_use_black_boat_ferries_infantry(ctx):
    """Only a Black Boat can take the CPU's foot soldiers over the strait: within six CPU days one has boarded it, crossed and been dropped on the far shore, and none is left aboard."""
    g = ctx.start(strait_map(ctx), ["andy", "andy"])
    g.e.w32(g.player(2)["addr"], 0)
    days = [sheet(g)]
    west = {i for i, v in days[0].items() if v[1] in ("Infantry", "Mech") and v[2] < 10}
    for _ in range(6):
        g.end_turn()
        days.append(sheet(g))
    for n, d in enumerate(days):
        ctx.log(f"day {n}: " + str(sorted((v[1], v[2], v[3]) for v in d.values() if v[1] in ("Infantry", "Mech", "Black Boat", "Lander"))))
    crossed = [i for i in west if i in days[-1] and days[-1][i][2] >= 20]
    ctx.check(crossed, f"a CPU foot soldier crossed the strait in the Black Boat ({[days[-1].get(i) for i in west]})")
    ctx.check(any(i not in d for d in days for i in west), "soldiers were aboard (off the map) on some day")


def carrier_map(ctx, fuel_low=2):
    m = ctx.map(hq=((1, 29, 0), (2, 0, 19)))
    for x in range(8, 24):
        for y in range(4, 16):
            m.terrain(x, y, "sea")
    m.unit(2, "carrier", 15, 10)
    for k in range(fuel_low):
        m.unit(2, "fighter", 13, 9 + 2 * k)
    m.unit(1, "bomber", 24, 10).unit(1, "infantry", 28, 2)
    return m


def fighters(g):
    return [u for u in g.units(army=2) if u["type"] == 16]


@test(modes=DS)
def cpu_unit_use_low_fuel_fighters_land_on_a_carrier(ctx):
    g = ctx.start(carrier_map(ctx), ["andy", "andy"])
    g.e.w32(g.player(2)["addr"], 0)
    for u in fighters(g):
        g.e.w8(g.unit_addr(u["id"]) + 6, 8)
    g.end_turn()
    ship = [u for u in g.units(army=2) if u["type"] == 26][0]
    fs = fighters(g)
    ctx.log(f"carrier {ship['cargo']} flags {ship['flags']:#x}; fighters {[(u['x'], u['y'], u['flags'], u['fuel']) for u in fs]}")
    ctx.check(all(u["flags"] & 0x08 for u in fs) and len(fs) == 2, "both low-fuel Fighters landed on the Carrier (carried)")
    ctx.check(sorted(ship["cargo"]) == sorted(u["id"] for u in fs), f"the Carrier holds them ({ship['cargo']})")


@test(modes=DS)
def cpu_unit_use_carrier_launches_its_fighters(ctx):
    g = ctx.start(carrier_map(ctx), ["andy", "andy"])
    g.e.w32(g.player(2)["addr"], 0)
    for u in fighters(g):
        g.e.w8(g.unit_addr(u["id"]) + 6, 8)
    g.end_turn()
    g.end_turn()
    fs = fighters(g)
    ship = [u for u in g.units(army=2) if u["type"] == 26][0]
    log = [l for l in g.e.decisions() if "launches" in l]
    ctx.log("\n".join(log))
    ctx.check(log, "the Carrier launched its Fighters with an enemy Bomber near")
    ctx.check(len(fs) == 2 and not any(u["flags"] & 0x08 for u in fs) and not [c for c in ship["cargo"] if c], f"the Fighters are out ({[(u['x'], u['y'], u['fuel']) for u in fs]}, cargo {ship['cargo']})")
    ctx.check(all(u["fuel"] > 40 for u in fs), "refuelled by the Carrier before they launched")
