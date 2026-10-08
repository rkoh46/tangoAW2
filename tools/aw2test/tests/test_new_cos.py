"""Dual Strike's nine new COs (crate::co_new, ids 72..80) with the pack: they are
on the Teams list in their army's group, play a battle with Dual Strike's
numbers (checked against the calculator), and show their pictures."""

from aw2test import rom as romlib
from aw2test.harness import test

NEW = ["jugger", "koal", "kindle", "vonbolt", "grimm", "javier", "sasha", "jake", "rachel", "cloneandy"]


def order_of(lst, name):
    return [romlib.co_name(c) for c in lst].index(name)


@test(modes=("ds",))
def new_cos_on_the_teams_list(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.log(f"Teams list: {[romlib.co_name(c) for c in lst]}")
    for name in NEW:
        ctx.check(romlib.co_id(name) in lst, f"{name} on the Teams list")
    ctx.eq(len(lst), 29, "29 COs")
    ctx.check(order_of(lst, "Clone Andy") > order_of(lst, "Adder"), "Clone Andy after Adder, among Black Hole's")
    order = [romlib.co_name(c) for c in lst]
    ctx.check(order.index("Jake") == order.index("Hachi") + 1, "Jake after Hachi")
    ctx.check(order.index("Grimm") == order.index("Sensei") + 1, "Grimm after Sensei")


@test(modes=("aw2",))
def clone_andy_absent_without_the_pack(ctx):
    """Without the pack the Teams list is AW2's nineteen: no Clone Andy."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.eq(len(lst), 19, "AW2's 19 COs")
    ctx.check(81 not in lst, "no Clone Andy")


@test(modes=("ds",))
def clone_andy_is_pickable_in_versus(ctx):
    """With the pack Clone Andy is on the Teams list, can be picked, plays a
    battle with Dual Strike's Andy's numbers against the damage calculator
    (his CO table row, checked in the patched image), and the game names him."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["cloneandy", "jugger"])
    ctx.eq(g.player(1)["co"], 81, "army 1 plays Clone Andy")
    e = g.e
    ctx.shot(g, "clone_andy_map")
    r = ctx.attack(g, (10, 6), (10, 6), (11, 6))
    ctx.eq(r["first"].base, 55, "his tank's base damage as Andy's (no bonus on a tank)")
    # his name text (the CO table's row +0x00 is a text id)
    row = e.u32(0x086A_0000 + 0x104 * 81)
    p = e.u32(0x08610A38 + 4 * row)
    raw = e.read(p, 16)
    ctx.eq(raw[:raw.index(0)], b"Clone Andy", "the game's text for his name")


@test(modes=("ds",))
def grimm_vs_jugger(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["grimm", "jugger"])
    ctx.shot(g, "map")
    r = ctx.attack(g, (10, 6), (10, 6), (11, 6))
    # Tank vs tank 55, Grimm +30%.
    ctx.eq(r["first"].base, 71, "Grimm's tank base damage")
    ctx.eq(r["first"].luck, (10, 0), "Grimm's luck")
    if r["counter"]:
        ctx.eq(r["counter"].luck, (30, 15), "Jugger's luck")


@test(modes=("ds",))
def every_new_co_starts(ctx):
    for k in range(0, 9, 2):
        pair = [NEW[k], NEW[(k + 1) % 9]]
        m = ctx.map()
        m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
        g = ctx.start(m, pair)
        ctx.eq(g.player(1)["co"], romlib.co_id(pair[0]), f"army 1 plays {pair[0]}")
        ctx.eq(g.player(2)["co"], romlib.co_id(pair[1]), f"army 2 plays {pair[1]}")
        ctx.shot(g, f"map_{pair[0]}")


@test(modes=("ds",))
def new_co_screens(ctx):
    """Screenshots: the Teams screen, the CO page and a power, for a new CO."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    g.set_teams(["javier", "kindle"], {1})
    g.e.wait(30)
    ctx.shot(g, "teams")
    g2 = ctx.start(m, ["javier", "kindle"])
    g2.open_map_menu()
    g2.choose("CO", g2.MAP_MENU)
    g2.e.wait(90)
    for i, k in enumerate(["", "DOWN", "DOWN", "DOWN", "DOWN", "RIGHT"]):
        if k:
            g2.e.press(k, 4)
        g2.e.wait(60)
        ctx.shot(g2, f"co{i}")
    for _ in range(6):
        g2.e.press("B", 4)
        g2.e.wait(40)
    g2.wait_for_input()
    g2.charge_power(1, "power")
    g2.open_map_menu()
    g2.choose("Power", g2.MAP_MENU)
    for i in range(8):
        g2.e.wait(25)
        ctx.shot(g2, f"power{i}")
