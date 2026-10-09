"""Supply: an APC's Supply command and turn-start supply, a Black Boat's and a
Carrier's resupply, and the properties' resupply and repair, for the new units
(Megatank, Piperunner, Stealth, Black Bomb, Black Boat, Carrier, Oozium) and
AW2's own (Md Tank, Neotank, Fighter, Battleship), as in Dual Strike.

Each unit starts full; the test lowers its ammo and fuel (a unit with no ammo
stat keeps 0 ammo and is checked for fuel only) and checks them against the
starting values afterwards."""

from aw2test.harness import test

APC = 7
NEW = {4: "Megatank", 9: "Piperunner", 12: "Stealth", 13: "Black Bomb", 18: "Black Boat", 26: "Carrier", 27: "Oozium"}
VANILLA = {3: "Md Tank", 8: "Neotank", 16: "Fighter", 21: "Battleship"}
SEA = {18, 21, 26}
AIR = {12, 13, 16}
ROW0 = 2


def kinds(ctx):
    k = dict(VANILLA)
    if ctx.mode == "ds":
        k.update(NEW)
    return sorted(k), {**VANILLA, **NEW}


def lower(g, x, y, ammo, fuel, hp=None):
    a = g.unit_addr(g.unit_at(x, y)["id"])
    e = g.e
    w = e.u16(a + 4)
    w = (w & ~0x780) | (ammo << 7)
    if hp is not None:
        w = (w & ~0x7F) | hp
    e.w16(a + 4, w)
    e.w8(a + 6, (e.u8(a + 6) & 0x80) | fuel)


def layout(ctx, with_apc=True):
    """An APC at (10, y) and a unit of each type at (11, y), one row each."""
    ids, names = kinds(ctx)
    m = ctx.map()
    for i, t in enumerate(ids):
        y = ROW0 + i
        if t in SEA:
            for x in (11, 12):
                m.terrain(x, y, "sea")
        if t == 9:
            m.terrain(11, y, "pipe")
        if with_apc:
            m.unit(1, APC, 10, y)
        m.unit(1, t, 11, y)
    return m, ids, names


def snapshot(g, ids):
    full = {}
    for i, t in enumerate(ids):
        u = g.unit_at(11, ROW0 + i)
        ctx_ok = u is not None and u["type"] == t
        assert ctx_ok, (t, u)
        full[t] = (u["ammo"], u["fuel"])
    return full


def lower_all(g, ids, full):
    for i, t in enumerate(ids):
        ammo, fuel = full[t]
        lower(g, 11, ROW0 + i, 1 if ammo else 0, 20)
        assert g.unit_at(11, ROW0 + i)["fuel"] == 20, "test setup: fuel lowered"


def check_all(ctx, g, ids, names, full, label):
    for i, t in enumerate(ids):
        u = g.unit_at(11, ROW0 + i)
        ctx.eq((u["ammo"], u["fuel"]), full[t], f"{label}: {names[t]} ammo and fuel back to its maximum {full[t]}")


@test()
def supply_apc_manual(ctx):
    """The Supply option appears next to each unit and restores ammo and fuel."""
    m, ids, names = layout(ctx)
    g = ctx.start(m, ["andy", "andy"])
    full = snapshot(g, ids)
    ctx.log(f"full (ammo, fuel): { {names[t]: v for t, v in full.items()} }")
    lower_all(g, ids, full)
    ctx.shot(g, "before")
    for i, t in enumerate(ids):
        y = ROW0 + i
        menu = g.action_menu_at(10, y)
        ctx.check("Supply" in menu, f"{names[t]}: the APC offers Supply: {menu}")
        g.select(10, y)
        g.move_to(10, y)
        g.choose("Supply", g.ACTION_MENU)
        g.wait_for_input()
    ctx.shot(g, "after")
    check_all(ctx, g, ids, names, full, "Supply")


@test()
def supply_apc_turn_start(ctx):
    """An APC resupplies adjacent units by itself at its army's turn start."""
    m, ids, names = layout(ctx)
    g = ctx.start(m, ["andy", "andy"])
    full = snapshot(g, ids)
    lower_all(g, ids, full)
    ctx.shot(g, "before")
    g.end_turn()
    ctx.shot(g, "after")
    check_all(ctx, g, ids, names, full, "turn start")


@test()
def supply_apc_ignores_enemies(ctx):
    """No Supply option next to an enemy or with nothing adjacent."""
    m = ctx.map()
    m.unit(1, APC, 10, 10).unit(2, 5, 11, 10).unit(1, APC, 20, 10)
    g = ctx.start(m, ["andy", "andy"])
    lower(g, 11, 10, 1, 20)
    ctx.check("Supply" not in g.action_menu_at(10, 10), "no Supply next to an enemy")
    ctx.check("Supply" not in g.action_menu_at(20, 10), "no Supply with nothing adjacent")


@test()
def supply_properties(ctx):
    """Cities and bases (ground), airports (air) and ports (sea) resupply at
    turn start; the wrong property does not."""
    ids, names = kinds(ctx)
    m = ctx.map()
    place = {}
    for i, t in enumerate(ids):
        y = ROW0 + i
        right = "port" if t in SEA else "airport" if t in AIR else "city"
        wrong = "city" if t in SEA | AIR else "airport"
        place[t] = (right, wrong)
        if t in SEA:
            for x in (11, 12, 13, 14, 15, 16, 17, 18):
                m.terrain(x, y, "sea")
        m.terrain(11, y, right, 1)
        m.terrain(20, y, wrong, 1)
        if t == 27:
            pass
        m.unit(1, t, 11, y)
        if t not in SEA:
            m.unit(1, t, 20, y)
    g = ctx.start(m, ["andy", "andy"])
    g.e.w32(g.player(1)["addr"], 900000)    # a repair is paid per HP: the Oozium costs 18900
    full = {}
    for i, t in enumerate(ids):
        full[t] = (g.unit_at(11, ROW0 + i)["ammo"], g.unit_at(11, ROW0 + i)["fuel"])
    for i, t in enumerate(ids):
        lower(g, 11, ROW0 + i, 1 if full[t][0] else 0, 20, hp=50)
        if t not in SEA:
            lower(g, 20, ROW0 + i, 1 if full[t][0] else 0, 20, hp=50)
    ctx.shot(g, "before")
    g.end_turn()
    ctx.shot(g, "after")
    for i, t in enumerate(ids):
        u = g.unit_at(11, ROW0 + i)
        ctx.eq((u["ammo"], u["fuel"]), full[t], f"{names[t]} on a {place[t][0]}: resupplied")
        ctx.eq(u["hp"], 70, f"{names[t]} on a {place[t][0]}: repaired 2 HP")
        if t not in SEA:
            w = g.unit_at(20, ROW0 + i)
            ctx.log(f"{names[t]} on a {place[t][1]} (wrong kind): ammo {w['ammo']} fuel {w['fuel']} hp {w['hp']}")
            ctx.check(w["hp"] == 50, f"{names[t]} on a {place[t][1]}: not repaired")


@test(modes=("ds",))
def supply_black_boat(ctx):
    """A Black Boat's Repair resupplies (and repairs) every adjacent own unit."""
    ids, names = kinds(ctx)
    ids = [t for t in ids if t not in SEA]
    m = ctx.map()
    for x in range(8, 14):
        for y in range(ROW0, ROW0 + 2 * len(ids) + 1):
            m.terrain(x, y, "sea")
    for i, t in enumerate(ids):
        y = ROW0 + 2 * i
        m.terrain(12, y, "plain" if t != 9 else "pipe")
        m.unit(1, 18, 11, y).unit(1, t, 12, y)
    g = ctx.start(m, ["andy", "andy"])
    g.e.w32(g.player(1)["addr"], 90000)
    full = {t: (g.unit_at(12, ROW0 + 2 * i)["ammo"], g.unit_at(12, ROW0 + 2 * i)["fuel"]) for i, t in enumerate(ids)}
    for i, t in enumerate(ids):
        lower(g, 12, ROW0 + 2 * i, 1 if full[t][0] else 0, 20, hp=50)
    ctx.shot(g, "before")
    for i, t in enumerate(ids):
        y = ROW0 + 2 * i
        menu = g.action_menu_at(11, y)
        ctx.check("Repair" in menu, f"{names[t]}: the Black Boat offers Repair: {menu}")
        g.select(11, y)
        g.move_to(11, y)
        g.choose("Repair", g.ACTION_MENU)
        g.wait_for_input()
    ctx.shot(g, "after")
    for i, t in enumerate(ids):
        u = g.unit_at(12, ROW0 + 2 * i)
        ctx.eq((u["ammo"], u["fuel"]), full[t], f"Black Boat: {names[t]} resupplied")
        ctx.check(u["hp"] > 50, f"Black Boat: {names[t]} repaired ({u['hp']})")


@test(modes=("ds",))
def supply_carrier_cargo(ctx):
    """A Carrier resupplies the air units it holds at turn start (Fighter,
    Stealth, Black Bomb, and a Bomber)."""
    air = [16, 12, 13, 17]
    m = ctx.map()
    for x in range(9, 14):
        for y in range(6, 14):
            m.terrain(x, y, "sea")
    m.unit(1, 26, 11, 7).unit(1, 26, 11, 11)
    for k, t in enumerate(air):
        m.unit(1, t, 11 + (k % 2) * 1, 8 if k < 2 else 12) if False else None
    m.unit(1, 16, 10, 7).unit(1, 12, 12, 7).unit(1, 13, 10, 11).unit(1, 17, 12, 11)
    g = ctx.start(m, ["andy", "andy"])
    full = {}
    for (x, y, t) in [(10, 7, 16), (12, 7, 12), (10, 11, 13), (12, 11, 17)]:
        u = g.unit_at(x, y)
        full[t] = (u["ammo"], u["fuel"])
    for (x, y, t) in [(10, 7, 16), (12, 7, 12), (10, 11, 13), (12, 11, 17)]:
        lower(g, x, y, 1 if full[t][0] else 0, 20)
    ctx.shot(g, "before")
    # load each into the Carrier beside it
    for (x, y, cx, cy) in [(10, 7, 11, 7), (12, 7, 11, 7), (10, 11, 11, 11), (12, 11, 11, 11)]:
        g.select(x, y)
        g.move_to(cx, cy)
        g.choose("Load", g.ACTION_MENU)
        g.wait_for_input()
    g.end_turn()
    ctx.shot(g, "after")
    for t, (a, f) in full.items():
        found = [u for u in g.units(1) if u["type"] == t]
        ctx.check(found, f"type {t} still exists")
        u = found[0]
        ctx.eq((u["ammo"], u["fuel"]), (a, f), f"Carrier cargo {t} resupplied")
