"""Dual Strike's nine new COs (crate::co_new, ids 72..80) with the pack: they are
on the Teams list in their army's group, play a battle with Dual Strike's
numbers (checked against the calculator), and show their pictures."""

import os

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


NAME_PALETTE = 0x080F6164        # the name graphics' fixed palette (sub_08043B44)
PRESENTATION = 0x08740000        # crate::co_new: 0x44 a CO, +4 the name graphic (LZ77)
AW2_PRESENTATION = 0x084A0090


def name_pixels(e, co):
    """The CO's name graphic as the game reads it: 16 rows of 48 palette indexes."""
    row = PRESENTATION if co >= 19 else AW2_PRESENTATION
    row = (PRESENTATION if co >= 19 else AW2_PRESENTATION) + 0x44 * co
    from aw2test import rom as r
    data = r.lz10(e.read(e.u32(row + 4), 0x300))
    px = [[0] * 48 for _ in range(16)]
    for col in range(6):
        for half in range(2):
            t = data[32 * (2 * col + half):32 * (2 * col + half) + 32]
            for y in range(8):
                for x in range(8):
                    px[8 * half + y][8 * col + x] = (t[4 * y + x // 2] >> (4 * (x & 1))) & 15
    return px


@test(modes=("ds",))
def clone_andy_name_graphic(ctx):
    """Clone Andy's name graphic reads "Clone": five letters (C, o, l, n of
    Colin's and e of Eagle's, AW2's own, composed by crate::co_new), in the
    six sprites and the game's name palette, drawn beside other CO names for
    comparison (clone_andy_name.png) and on his CO page in the game."""
    from aw2test import png
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["cloneandy", "jugger"])
    e = g.e
    pal_raw = e.read(NAME_PALETTE, 32)
    pal = [((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31) for c in (pal_raw[2 * i] | pal_raw[2 * i + 1] << 8 for i in range(16))]
    order = [("Colin", 16), ("Clone Andy", 81), ("Andy", 1), ("Eagle", 8), ("Jugger", 72), ("Kindle", 74), ("Adder", 13)]
    rows = []
    for name, co in order:
        px = name_pixels(e, co)
        rows += [[pal[v] for v in r] for r in px] + [[pal[0]] * 48]
    png.write(os.path.join(ctx.out, "clone_andy_name.png"), rows, 6)
    px = name_pixels(e, 81)
    cols = [any(px[y][x] == 1 for y in range(16)) for x in range(48)]
    runs, s = [], None
    for x, c in enumerate(cols + [False]):
        if c and s is None:
            s = x
        if not c and s is not None:
            runs.append((s, x - 1))
            s = None
    ctx.eq(len(runs), 5, f"five letters ({runs})")
    ctx.check(runs[0][0] >= 3 and runs[-1][1] <= 44, "inside the six sprites, centred")
    used = {v for r in px for v in r}
    colin = {v for r in name_pixels(e, 16) for v in r}
    ctx.check(used <= colin | {v for r in name_pixels(e, 8) for v in r}, "only the colours of AW2's own name graphics")
    ctx.check(px != name_pixels(e, 1), "not Andy's")
    # his CO page in the game (the map menu's CO)
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    e.wait(120)
    ctx.shot(g, "clone_andy_co_page")


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
