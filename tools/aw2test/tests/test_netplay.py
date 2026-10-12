"""Netplay: a scripted battle replayed on two rollback peers.

The offline run's inputs (recorded by the driver) are replayed by
aw2_netplay_script with seat 0 pressing (army 1; army 2 is the CPU) over a
fake network with delay and jitter. Both peers and a straight replay of the
confirmed inputs must end byte-identical, and the units must end exactly as
they did offline.
"""

from aw2test import ram
from aw2test.harness import test


@test()
def netplay_tank_battle_and_cpu_turn(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(1, "artillery", 8, 10)
    g = ctx.start(m, ["andy", "hawke"])
    ctx.attack(g, (10, 10), (10, 10), (11, 10))
    ctx.attack(g, (8, 10), (8, 10), (11, 10))
    g.end_turn(human=1)
    units = (g.units_base + ram.UNIT_SIZE * 1, ram.UNIT_SIZE * 127)
    players = (g.players_base + ram.PLAYER_SIZE, ram.PLAYER_SIZE * 2)
    offline = {a: g.e.read(a, n) for a, n in (units, players)}
    g.e.wait(60)
    identical, values, text = ctx.netplay_replay(g, [units, players])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: all identical: true (both peers and the straight replay)")
    for a, v in offline.items():
        ctx.eq(values.get(a, b"").hex(), v.hex(), f"netplay peer 0 RAM at {a:08x} equals the offline run")


@test()
def netplay_com_towers(ctx):
    """Com Towers over netplay: a tower-boosted attack, a capture and a CPU turn
    that takes a tower, identical on both peers (with the pack: shared)."""
    m = ctx.map()
    m.terrain(2, 2, 0x1DA).terrain(10, 12, 0x1D9).terrain(20, 10, 0x1D9)
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(1, "infantry", 10, 12)
    m.unit(2, "infantry", 21, 10)
    g = ctx.start(m, ["andy", "andy"])
    ctx.attack(g, (10, 10), (10, 10), (11, 10))
    g.select(10, 12)
    g.move_to(10, 12)
    g.choose("Capt", g.ACTION_MENU)
    g.wait_for_input()
    g.end_turn(human=1)
    g.end_turn(human=1)
    units = (g.units_base + ram.UNIT_SIZE * 1, ram.UNIT_SIZE * 127)
    players = (g.players_base + ram.PLAYER_SIZE, ram.PLAYER_SIZE * 2)
    offline = {a: g.e.read(a, n) for a, n in (units, players)}
    g.e.wait(60)
    identical, values, text = ctx.netplay_replay(g, [units, players])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: all identical: true (both peers and the straight replay)")
    for a, v in offline.items():
        ctx.eq(values.get(a, b"").hex(), v.hex(), f"netplay peer 0 RAM at {a:08x} equals the offline run")


@test(modes=("ds",), netplay=True)
def netplay_new_co_powers(ctx):
    """Dual Strike's new COs over netplay: Von Bolt's Ex Machina (its stun is
    kept in RAM) and Sasha's War Bonds, then CPU turns, identical on both peers
    and the replay."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(2, "mech", 20, 10).unit(2, "infantry", 21, 11)
    g = ctx.start(m, ["vonbolt", "sasha"])
    ctx.power(g, 1, "super")
    ctx.attack(g, (10, 10), (10, 10), (11, 10))
    g.end_turn(human=1)
    g.end_turn(human=1)
    units = (g.units_base + ram.UNIT_SIZE * 1, ram.UNIT_SIZE * 127)
    players = (g.players_base + ram.PLAYER_SIZE, ram.PLAYER_SIZE * 2)
    stun = (0x0203FE00, 0x58)
    offline = {a: g.e.read(a, n) for a, n in (units, players, stun)}
    g.e.wait(60)
    identical, values, text = ctx.netplay_replay(g, [units, players, stun])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: all identical: true (both peers and the straight replay)")
    for a, v in offline.items():
        ctx.eq(values.get(a, b"").hex(), v.hex(), f"netplay peer 0 RAM at {a:08x} equals the offline run")


@test()
def netplay_black_hole_hq_captured(ctx):
    """A five-army battle: Orange Star captures Black Hole's HQ (terrain 0x1B4) over two turns, the
    CPU armies play between, and both peers end byte-identical to the offline run and the replay."""
    m = ctx.map(hq=((1, 0, 0), (2, 29, 19), (3, 29, 0), (4, 0, 19)))
    m.terrain(15, 10, 0x1B4)
    m.unit(5, "infantry", 29, 10)
    m.unit(1, "infantry", 15, 9)
    m.colours = [5, 1, 2, 3, 4]
    g = ctx.start(m, None)
    for _ in range(2):
        g.select(15, 9) if g.unit_at(15, 9) else g.select(15, 10)
        pos = (15, 10)
        g.move_to(*pos) if g.unit_at(15, 9) else (g.goto(*pos), g.e.press("A", 6), g.wait_menu(g.ACTION_MENU))
        g.choose("Capt", g.ACTION_MENU)
        g.wait_for_input()
        if g.battle_over() or g.terrain_class(15, 10) != 0xA8:
            break
        g.end_turn(human=1)
    ctx.eq(g.terrain_class(15, 10), 0x06 | 1 << 5, "Black Hole's HQ is Orange Star's city")
    units = (g.units_base + ram.UNIT_SIZE * 1, ram.UNIT_SIZE * 255)
    players = (g.players_base + ram.PLAYER_SIZE, ram.PLAYER_SIZE * 5)
    offline = {a: g.e.read(a, n) for a, n in (units, players)}
    g.e.wait(60)
    identical, values, text = ctx.netplay_replay(g, [units, players])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: all identical: true (both peers and the straight replay)")
    for a, v in offline.items():
        ctx.eq(values.get(a, b"").hex(), v.hex(), f"netplay peer 0 RAM at {a:08x} equals the offline run")
