"""CPU behaviour in M29, M30 and M31 (tango-gamesupport-aw2/src/bh_act5.rs, bh_secret.rs): with the player passing every turn, the
enemy moves, captures, attacks and builds. Each day logs: units, units moved since yesterday, AI roles, properties captured,
funds, new units, units standing on a production tile."""

import struct

from aw2test import bhact5 as a5
from aw2test import bhact5b as a5b
from aw2test import bhcampaign as bh
from aw2test import dscampaign as dc
from aw2test.bot import Bot, CLASSES, BASE, AIRPORT, PORT, HQ, CITY
from aw2test.harness import test

ALL = (1 << 10) - 1
ROSTER = 0xFFF | (0x1FF << 12)


def snapshot(g, d, army):
    g._units_base = g._players_base = None
    b = Bot(d)
    b.props = None
    props = b.properties()
    us = g.units(army)
    roles = {}
    for u in us:
        r = g.e.u8(g.unit_addr(u["id"]) + 0x0B)
        roles[u["id"]] = r
    return us, roles, {c: (k, o) for c, k, o in props}, struct.unpack_from("<I", g.player(army)["raw"], 0)[0]


def watch(ctx, e, g, d, mod, days, label, army=2, pre=None):
    us0, _, props0, _ = snapshot(g, d, army)
    prev = {u["id"]: (u["x"], u["y"]) for u in us0}
    seen = set(prev)
    tot = dict(moved=0, new=0, captured=0, hurt=0)
    rows = []
    for day in range(2, days + 1):
        mod.to_day(e, g, d, day)
        if e.u8(dc.LAST_RESULT):
            break
        us, roles, props, funds = snapshot(g, d, army)
        moved = sum(1 for u in us if u["id"] in prev and (u["x"], u["y"]) != prev[u["id"]])
        new = [u for u in us if u["id"] not in seen]
        mine = sum(1 for c, (k, o) in props.items() if o == army and props0.get(c, (0, 0))[1] != army)
        onprod = [(u["x"], u["y"], u["type"], roles[u["id"]]) for u in us if props.get((u["x"], u["y"]), (0, 0))[0] in (BASE, AIRPORT, PORT)
                  and props[(u["x"], u["y"])][1] == army]
        byrole = {}
        for r in roles.values():
            byrole[r] = byrole.get(r, 0) + 1
        ctx.log(f"{label} day {day}: units {len(us)} moved {moved} new {len(new)} roles {sorted(byrole.items())} "
                f"gained-props {mine} funds {funds} on-own-production {onprod} enemy(1) units {len(g.units(1))}")
        if day in (3, 5):
            import os
            sd = os.environ.get("AW2TEST_CPUAI6_SHOTS")
            if sd:
                os.makedirs(sd, exist_ok=True)
                e.shot(os.path.join(sd, f"{label}_day{day}"))
        tot["moved"] += moved
        tot["new"] += len(new)
        tot["captured"] = mine
        rows.append((day, len(us), moved, len(new), mine, funds, onprod))
        seen |= {u["id"] for u in us}
        prev = {u["id"]: (u["x"], u["y"]) for u in us}
    return tot, rows


@test(modes=("ds",))
def bh_cpu_m29_the_enemy_acts(ctx):
    e, g, d = a5.boot(ctx, a5.WON(28), ALL, picks={a5.M[29]: 1}, at=a5.M[29])
    a5.open_mission(ctx, e, g, d, a5.M[29], [bh.STURM], "m29")
    d.wait_control()
    g._units_base = g._players_base = None
    tot, rows = watch(ctx, e, g, d, a5, 6, "m29")
    ctx.log(f"totals {tot}")
    ctx.check(tot["moved"] >= 20, f"Orange Star's units move ({tot['moved']} moves in 5 days)")
    ctx.check(tot["new"] >= 3, f"Orange Star builds ({tot['new']} new units)")
    e.close()


@test(modes=("ds",))
def bh_cpu_m30_the_enemy_acts(ctx):
    e, g, d = a5.boot(ctx, a5.WON(29), ALL, picks={a5.M[30]: 1}, at=a5.M[30])
    a5.open_mission(ctx, e, g, d, a5.M[30], [bh.CLONE_ANDY], "m30")
    d.wait_control()
    g._units_base = g._players_base = None
    tot, rows = watch(ctx, e, g, d, a5, 6, "m30")
    ctx.log(f"totals {tot}")
    ctx.check(tot["moved"] >= 20, f"Orange Star's units move ({tot['moved']} moves in 5 days)")
    ctx.check(tot["new"] >= 1, f"Orange Star builds when below its 50-unit cap ({tot['new']} new units)")
    e.close()


@test(modes=("ds",))
def bh_cpu_m31_the_enemy_acts(ctx):
    mask = sum(1 << a5b.M[k] for k in range(1, 31))
    e, g, d = a5b.boot(ctx, mask, ROSTER, picks={a5b.M[31]: 1}, at=a5b.M[31])
    a5b.open_mission(ctx, e, g, d, a5b.M[31], [bh.STURM], "m31")
    d.wait_control()
    g._units_base = g._players_base = None
    tot, rows = watch(ctx, e, g, d, a5b, 6, "m31")
    ctx.log(f"totals {tot}")
    ctx.check(tot["moved"] >= 15, f"Yellow Comet's units move ({tot['moved']} moves in 5 days)")
    e.close()


@test(modes=("ds",))
def bh_cpu_m30_held_guns_fire_without_moving(ctx):
    """Nell's Artillery and Missiles hold (role 0) on the walls: a Black Hole unit set down in range of one is fired on
    (its ammo drops) and none of the guns leaves its cell over three CPU turns."""
    e, g, d = a5.boot(ctx, a5.WON(29), ALL, picks={a5.M[30]: 1}, at=a5.M[30])
    a5.open_mission(ctx, e, g, d, a5.M[30], [bh.CLONE_ANDY], "m30")
    d.wait_control()
    g._units_base = g._players_base = None
    guns = {u["id"]: (u["x"], u["y"]) for u in g.units(2) if u["type"] in (10, 15)}
    ctx.check(len(guns) >= 5, f"Orange has {len(guns)} guns")
    art = next(u for u in g.units(2) if u["type"] == 10)
    occ = {(u["x"], u["y"]) for u in g.units()}
    mine = next(u for u in g.units(1) if u["type"] == 5)
    cell = next((art["x"] + dx, art["y"] + dy) for dx, dy in ((0, 2), (2, 0), (0, -2), (-2, 0), (1, 1), (-1, -1), (1, -1), (-1, 1))
                if (art["x"] + dx, art["y"] + dy) not in occ and g.terrain_class(art["x"] + dx, art["y"] + dy) & 0x1F in (1, 2, 3, 4, 5, 6, 8, 0xE))
    ammo0 = art["ammo"]
    ctx.log(f"artillery {art['id']} at {(art['x'], art['y'])} ammo {ammo0}, my Tank {mine['id']} moved to {cell}")
    a = g.unit_addr(mine["id"])
    e.w8(a + 2, cell[0]); e.w8(a + 3, cell[1])
    fired = False
    ammo_start = {u["id"]: u["ammo"] for u in g.units(2)}
    for k in range(3):
        a5.next_turn(e, g, d)
        g._units_base = g._players_base = None
        now = {u["id"]: u for u in g.units(2)}
        t = g.unit(mine["id"])
        ctx.log(f"turn {k}: tank hp {t['hp']}, artillery ammo {now[art['id']]['ammo'] if art['id'] in now else None}")
        spent = [(i, u["type"]) for i, u in now.items() if u["ammo"] < ammo_start.get(i, 99)]
        ctx.log(f"  units whose ammo dropped: {spent}")
        if any(t in (10, 15) for _, t in spent):
            fired = True
    moved = [i for i, p in guns.items() if i in now and (now[i]["x"], now[i]["y"]) != p]
    ctx.log(f"guns that moved: {moved}")
    ctx.check(fired, "the held Artillery fired at the Tank in reach")
    ctx.check(not moved, "no held gun left its cell")
    e.close()
