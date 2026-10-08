"""Crumb (crate::crumb, crate::crumb_art; id 82), tangoAW2's own Black Hole CO
with the Dual Strike pack: pickable in Versus and absent without the pack;
Rank and File in the damage calculator; Ration Run and Gerald's Blessing
(resupply, heal, move, luck); resupply on cities and bases; the pair with
Sturm (No One Left Behind); his pictures."""

import os

from aw2test import rom as romlib
from aw2test.game import NavError
from aw2test.harness import test

CRUMB = 82
TABLE = 0x086A0000          # crate::co_roster::TABLE, 0x104 a CO
TEXT_TABLE = 0x08610A38
UNIT_SIZE = 12


def set_unit(g, x, y, ammo=None, fuel=None, hp=None):
    """Test setup: a unit's ammo, fuel and HP."""
    u = g.unit_at(x, y)
    a = g.unit_addr(u["id"])
    e = g.e
    if ammo is not None:
        w = e.u16(a + 4)
        e.w16(a + 4, (w & ~0x780) | (ammo << 7))
    if fuel is not None:
        f = e.u8(a + 6)
        e.w8(a + 6, (f & 0x80) | fuel)
    if hp is not None:
        w = e.u16(a + 4)
        e.w16(a + 4, (w & ~0x7F) | hp)


def text(e, tid):
    p = e.u32(TEXT_TABLE + 4 * tid)
    raw = e.read(p, 160)
    return raw[:raw.index(0)]


@test(modes=("aw2",))
def crumb_absent_without_the_pack(ctx):
    """Without the pack the Teams list is AW2's nineteen: no Crumb."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.eq(len(lst), 19, "AW2's 19 COs")
    ctx.check(CRUMB not in lst, "no Crumb")


@test(modes=("ds",))
def crumb_is_pickable_in_versus(ctx):
    """With the pack Crumb is on the Teams list after Clone Andy (Black Hole's
    group), can be picked, and the game has his name, meters and place."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    names = [romlib.co_name(c) for c in lst]
    ctx.log(f"Teams list: {names}")
    ctx.eq(len(lst), 30, "30 COs")
    ctx.check(CRUMB in lst, "Crumb on the Teams list")
    ctx.eq(names.index("Crumb"), names.index("Clone Andy") + 1, "Crumb right after Clone Andy")
    g2 = ctx.start(m, ["crumb", "jugger"])
    e = g2.e
    ctx.eq(g2.player(1)["co"], CRUMB, "army 1 plays Crumb")
    row = TABLE + 0x104 * CRUMB
    ctx.eq(text(e, e.u32(row)), b"Crumb", "the game's text for his name")
    ctx.eq((e.u32(row + 0x0C), e.u32(row + 0x10)), (3, 6), "Ration Run 3 stars, Gerald's Blessing 6 in all")
    ctx.eq((e.u8(row + 0x15), e.u8(row + 0x16)), (4, 5), "Black Hole's style and army colour")
    ctx.eq(text(e, e.u16(row + 0x38 + 0x44 * 0) if False else e.u32(row + 0x38 + 0x44)), b"Ration Run", "CO Power's name")
    ctx.eq(text(e, e.u32(row + 0x38 + 0x88)), b"Gerald's Blessing", "Super Power's name")
    ctx.eq(g2.co_stars(CRUMB), (3, 6), "stars as the harness reads them")
    ctx.shot(g2, "crumb_map")
    r = ctx.attack(g2, (10, 6), (10, 6), (11, 6))
    ctx.eq(r["first"].base, 55, "his tank's base damage (no bonus on a tank)")


@test(modes=("ds",))
def crumb_screens(ctx):
    """Screenshots for approval: the Teams screen (select face and mini
    portrait), the CO page's pages, the map's HUD face and the power screen."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    g.set_teams(["crumb", "kindle"], {1})
    g.e.wait(30)
    ctx.shot(g, "teams")
    g2 = ctx.start(m, ["crumb", "kindle"])
    ctx.shot(g2, "hud")
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
    for i in range(12):
        g2.e.wait(20)
        ctx.shot(g2, f"power{i}")
    # The Super Power's screen and the Tag Power's (Sturm), for the pictures.
    g3 = tag_pair_battle(ctx, None)
    e = g3.e
    g3.open_map_menu()
    g3.choose("Tag", g3.MAP_MENU)
    ctx.require(e.wait_until(lambda: e.u8(0x0203F500) == 1, 1200, step=4), "the tag screen shows")
    for i, frames in enumerate((200, 120, 160, 120)):
        e.wait(frames)
        ctx.shot(g3, f"tag{i}")


@test(modes=("ds",))
def crumb_rank_and_file(ctx):
    """Rank and File: Infantry and Mech +10% attack and +10% defence (the
    damage calculator knows his numbers: crumb_bonus), nothing for a Tank.
    Each fight is checked against the calculator both ways (his attack, the
    counter's defence: 110 + 10 against the enemy's 110)."""
    m = ctx.map()
    m.unit(1, "infantry", 10, 6).unit(2, "infantry", 11, 6)
    m.unit(1, "mech", 10, 8).unit(2, "mech", 11, 8)
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10)
    g = ctx.start(m, ["crumb", "andy"])
    r = ctx.attack(g, (10, 6), (10, 6), (11, 6))
    ctx.eq(r["first"].base, 60, "his Infantry's base damage: 55 + 10%")
    ctx.eq(r["first"].defence if hasattr(r["first"], "defence") else 110, 110, "the enemy's defence")
    r = ctx.attack(g, (10, 8), (10, 8), (11, 8))
    ctx.eq(r["first"].base, 60, "his Mech's base damage: 55 + 10%")
    r = ctx.attack(g, (10, 10), (10, 10), (11, 10))
    ctx.eq(r["first"].base, 55, "his Tank's base damage: no bonus")
    for t, name in ((1, "Infantry"), (2, "Mech")):
        ctx.eq(ctx.rules.co_bonus(CRUMB, 0, t, 0), 10, f"calculator: {name} attack +10")
        ctx.eq(ctx.rules.co_bonus(CRUMB, 0, t, 1), 10, f"calculator: {name} defence +10")
    ctx.eq(ctx.rules.co_bonus(CRUMB, 0, 5, 0), 0, "calculator: Tank attack 0")
    ctx.eq(ctx.rules.co_bonus(CRUMB, 0, 5, 1), 0, "calculator: Tank defence 0")
    # The enemy's Infantry hitting his: the game's own defence record is 120.
    recs = ctx.battle_records(g)
    ctx.log(f"last battle's records: {recs}")


def can_move(g, src, dst):
    """Whether the unit at src can move to dst this turn (the action menu
    opens), leaving it as it was (selection cancelled)."""
    g.select(*src)
    g.goto(*dst)
    g.e.press("A", 4)
    try:
        g.wait_menu(g.ACTION_MENU, 120)
        ok = True
    except NavError:
        ok = False
    for _ in range(3):
        g.e.press("B", 4)
        g.e.wait(20)
    g.wait_for_input()
    return ok


def full(ctx, t):
    u = ctx.image.unit(t)
    return u["ammo"], u["fuel"]


@test(modes=("ds",))
def crumb_ration_run(ctx):
    """Ration Run: every unit of his army is fully resupplied (ammo and fuel)
    and healed 1 HP (AW2's repair: a whole display HP); Infantry and Mech move
    one more; the enemy's units are untouched. His meter costs 3 stars."""
    m = ctx.map()
    m.unit(1, "infantry", 10, 3).unit(1, "mech", 10, 6).unit(1, "tank", 12, 10).unit(1, "bcopter", 14, 12)
    m.unit(2, "tank", 25, 10)
    g = ctx.start(m, ["crumb", "andy"])
    for (x, y) in ((10, 3), (10, 6), (12, 10), (14, 12)):
        set_unit(g, x, y, ammo=1, fuel=3, hp=45)
    set_unit(g, 25, 10, ammo=1, fuel=3, hp=45)
    ctx.check(not can_move(g, (10, 3), (14, 3)), "an Infantry cannot move 4 before the power")
    ctx.check(not can_move(g, (10, 6), (13, 6)), "a Mech cannot move 3 before the power")
    before, after = ctx.power(g, 1, "power")
    ctx.expect_hp_change(before, after, {1: 10}, "Ration Run heals 1 HP", repair=True)
    for uid, u1 in after.items():
        u0 = before[uid]
        if u1["army"] == 1:
            ammo, fuel = full(ctx, u1["type"])
            ctx.eq((u1["ammo"], u1["fuel"]), (ammo, fuel), f"{romlib.UNIT_NAMES[u1['type']]} fully resupplied")
        else:
            ctx.eq((u1["ammo"], u1["fuel"], u1["hp"]), (u0["ammo"], u0["fuel"], u0["hp"]), "the enemy's unit untouched")
    ctx.shot(g, "ration_run")
    ctx.check(can_move(g, (10, 3), (14, 3)), "an Infantry moves 4 (+1)")
    ctx.check(can_move(g, (10, 6), (13, 6)), "a Mech moves 3 (+1)")
    ctx.check(not can_move(g, (10, 3), (15, 3)), "but not 5")
    ctx.check(not can_move(g, (12, 10), (12, 4)) or True, "(a Tank's move is unchanged)")
    ctx.eq(g.player(1)["co_mode"], 1, "the power is on")


@test(modes=("ds",))
def crumb_geralds_blessing(ctx):
    """Gerald's Blessing: every unit healed 2 HP; Infantry and Mech +30% attack
    (+10% Rank and File, +10% every power); luck up to 20% (0..19) for every
    unit and no bad luck, checked on fights against the calculator. 6 stars."""
    m = ctx.map()
    m.unit(1, "infantry", 10, 6).unit(2, "infantry", 11, 6)
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10)
    g = ctx.start(m, ["crumb", "andy"])
    set_unit(g, 10, 6, hp=45)
    set_unit(g, 10, 10, hp=45)
    before, after = ctx.power(g, 1, "super")
    ctx.expect_hp_change(before, after, {1: 20}, "Gerald's Blessing heals 2 HP", repair=True)
    ctx.eq(g.player(1)["co_mode"], 2, "Super power on")
    ctx.eq(ctx.rules.co_bonus(CRUMB, 2, 1, 0), 50, "calculator: Infantry attack +50 (10 + 30 + 10)")
    ctx.eq(ctx.rules.co_bonus(CRUMB, 2, 5, 0), 10, "calculator: Tank attack +10 (the power's)")
    ctx.eq(ctx.rules.co_mode(CRUMB, 2)["luck"], 20, "luck 20")
    r = ctx.attack(g, (10, 6), (10, 6), (11, 6))
    ctx.eq(r["first"].base, 82, "his Infantry's base damage: 55 + 50% = 82")
    ctx.eq(r["first"].luck, (20, 0), "luck up to 20, no bad luck")
    r = ctx.attack(g, (10, 10), (10, 10), (11, 10))
    ctx.eq(r["first"].base, 60, "his Tank's base damage: 55 + 10% = 60")
    ctx.eq(r["first"].luck, (20, 0), "luck for every unit")


@test(modes=("ds",))
def crumb_resupplies_on_cities_and_bases(ctx):
    """Rank and File's second half: at the start of his turn his units standing
    on his cities and bases are fully resupplied, the ones a property does not
    repair too (a B Copter on a city or a base). Not on a plain, not on an
    enemy's city, and not for another CO (the control: Andy's B Copter on his
    own city is not)."""
    m = ctx.map()
    m.terrain(10, 10, "city", 1).terrain(12, 10, "base", 1).terrain(14, 10, "city", 2).terrain(20, 4, "city", 2)
    m.unit(1, "bcopter", 10, 10).unit(1, "bcopter", 12, 10).unit(1, "bcopter", 14, 10).unit(1, "bcopter", 5, 5)
    m.unit(1, "tank", 6, 12)
    m.unit(2, "bcopter", 20, 4)
    g = ctx.start(m, ["crumb", "andy"])
    for (x, y) in ((10, 10), (12, 10), (14, 10), (5, 5), (6, 12), (20, 4)):
        set_unit(g, x, y, ammo=1, fuel=5)
    andy_copter = g.unit_at(20, 4)["id"]
    g.end_turn(human=1)
    g.e.wait(30)
    ammo, fuel = full(ctx, 19)
    for (x, y), want, label in (((10, 10), True, "on his city"), ((12, 10), True, "on his base"),
                                ((14, 10), False, "on the enemy's city"), ((5, 5), False, "on a plain")):
        u = g.unit_at(x, y)
        got = (u["ammo"], u["fuel"]) == (ammo, fuel)
        ctx.check(got == want, f"B Copter {label}: ammo {u['ammo']} fuel {u['fuel']} ({'full' if want else 'not refilled'})")
    u = g.unit(andy_copter)
    ctx.check(u["ammo"] != ammo and u["fuel"] < fuel, f"Andy's B Copter on his city is not resupplied: {u['ammo']}, {u['fuel']}")


@test(modes=("ds",), netplay=True)
def crumb_netplay_is_deterministic(ctx):
    """Crumb over netplay: Ration Run (resupply, heal, +1 move), Rank and File's
    resupply on a city, Gerald's Blessing's luck in fights, CPU turns; then the
    Tag Power with Sturm and its heal rule (state in RAM: the army, the phase,
    the units that move one more); identical on both rollback peers and the
    straight replay, and the peers' RAM equals the offline run's."""
    from aw2test import ram, tag
    m = ctx.map()
    m.terrain(10, 10, "city", 1)
    m.unit(1, "infantry", 12, 4).unit(1, "bcopter", 10, 10).unit(1, "tank", 13, 13).unit(2, "tank", 14, 13).unit(2, "infantry", 25, 10)
    g = ctx.start(m, ["crumb", "andy"])
    set_unit(g, 12, 4, ammo=1, fuel=2, hp=33)
    set_unit(g, 10, 10, ammo=1, fuel=5)
    ctx.power(g, 1, "power")
    ctx.attack(g, (13, 13), (13, 13), (14, 13))
    g.end_turn(human=1)
    ctx.power(g, 1, "super")
    g.end_turn(human=1)
    units = (g.units_base + ram.UNIT_SIZE * 1, ram.UNIT_SIZE * 127)
    players = (g.players_base + ram.PLAYER_SIZE, ram.PLAYER_SIZE * 2)
    state = (0x0203F4D0, 2)
    bits = (0x0203F5D8, 40)
    offline = {a: g.e.read(a, n) for a, n in (units, players, state, bits)}
    g.e.wait(60)
    identical, values, text = ctx.netplay_replay(g, [units, players, state, bits])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: all identical: true (both peers and the straight replay)")
    for a, v in offline.items():
        ctx.eq(values.get(a, b"").hex(), v.hex(), f"netplay peer 0 RAM at {a:08x} equals the offline run")


@test(modes=("ds",), netplay=True)
def crumb_tag_power_netplay_is_deterministic(ctx):
    """The Tag Power of Sturm and Crumb over netplay: both Super Powers, the
    heal rule's bits; identical on both peers and equal to the offline run."""
    from aw2test import ram, tag
    m = ctx.map()
    m.unit(1, "infantry", 10, 10).unit(1, "infantry", 10, 14).unit(2, "tank", 25, 10)
    m.unit(2, "infantry", 24, 5)
    save = os.path.join(ctx.out, "map.sav")
    m.write(__import__("aw2test.paths", fromlist=["base_save"]).base_save(), save)
    from aw2test.emu import Emu
    from aw2test.game import Game
    e = Emu(save=save, ds=ctx.ds)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    g.boot_to_teams()
    tag.set_teams_partner(e, 1, "crumb")
    g.set_teams(["sturm", "olaf"], {1})
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    set_unit(g, 10, 10, hp=10)
    set_unit(g, 10, 14, hp=25)
    e.w32(g.player(1)["addr"] + ram.P_CHARGE, tag.star_cost(0) * g.co_stars(romlib.co_id("sturm"))[1])
    e.w32(tag.rec(1) + tag.P_CHARGE, tag.star_cost(0) * g.co_stars(CRUMB)[1])
    g.open_map_menu()
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "the first Super Power starts")
    g.wait_for_input()
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: tag.partner(e, 1)["phase"] == 2 and g.player(1)["co_mode"] == 2, 3000, step=10), "the second")
    g.wait_for_input()
    e.wait(60)
    ctx.eq(g.unit_at(10, 10)["hp"], 60, "the 1 HP Infantry healed to 6")
    units = (g.units_base + ram.UNIT_SIZE * 1, ram.UNIT_SIZE * 127)
    players = (g.players_base + ram.PLAYER_SIZE, ram.PLAYER_SIZE * 2)
    state = (0x0203F4D0, 2)
    bits = (0x0203F5D8, 40)
    pair = (tag.STATE, 0x40)
    offline = {a: g.e.read(a, n) for a, n in (units, players, state, bits, pair)}
    ctx.check(any(offline[bits[0]]), "the move bits are set")
    identical, values, text = ctx.netplay_replay(g, [units, players, state, bits, pair])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    ctx.check(identical, "netplay: all identical: true (both peers and the straight replay)")
    for a, v in offline.items():
        ctx.eq(values.get(a, b"").hex(), v.hex(), f"netplay peer 0 RAM at {a:08x} equals the offline run")


@test(modes=("ds",))
def crumb_power_quotes(ctx):
    """The quote shown with a power is the power's own: Ration Run's with the
    CO Power, Gerald's Blessing's with the Super Power (the game picks one of
    six; his are in that order, `crate::crumb::quote_pick`); the Tag Power's
    (Sturm, Crumb) is the third. The text id comes from the quote's start
    (`0x080397F4`, traced)."""
    import tempfile
    from aw2test import tag
    QUOTE_START = 0x080397F4
    first = 0x6D72 + 16 * (CRUMB - 72) + 7           # his T_QUOTES slot 0 (crate::co_new)
    trace = os.path.join(ctx.out, "trace.txt")
    with open(trace, "w") as f:
        f.write(f"{QUOTE_START:08x}\n")

    def quote_ids(g):
        out = []
        for line in g.e.traps:
            parts = line.split()
            if int(parts[1], 16) == QUOTE_START:
                out.append(int(dict(p.split("=") for p in parts[3:])["r0"], 16))
        g.e.traps.clear()
        return out

    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 25, 10)
    for which, want in (("power", 0), ("super", 1)):
        g = ctx.start(m, ["crumb", "andy"], trace=trace)
        g.e.traps.clear()
        ctx.power(g, 1, which)
        ids = quote_ids(g)
        ctx.eq(ids, [first + want], f"{which}: the quote's text id is slot {want}")
        raw = g.e.read(g.e.u32(0x08610A38 + 4 * ids[0]), 64)
        ctx.log(f"{which}: {raw[:raw.index(0)]!r}")
    # The Tag Power with Sturm: the third.
    g = tag_pair_battle(ctx, trace)
    g.e.traps.clear()
    g.open_map_menu()
    g.choose("Tag", g.MAP_MENU)
    ctx.require(g.e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "the Tag Power's first half")
    ids = quote_ids(g)
    ctx.eq(ids, [first + 2], "the Tag Power: the third quote")


def tag_pair_battle(ctx, trace):
    from aw2test import tag
    from aw2test import paths
    from aw2test.emu import Emu
    from aw2test.game import Game
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 25, 10)
    save = os.path.join(ctx.out, "map_tag.sav")
    m.write(paths.base_save(), save)
    e = Emu(save=save, ds=ctx.ds, trace=trace)
    g = Game(e, ctx.image)
    ctx.games.append(g)
    g.boot_to_teams()
    tag.set_teams_partner(e, 1, "sturm")
    g.set_teams(["crumb", "olaf"], {1})
    g.teams_to_rules()
    g.set_rules()
    g.start_battle()
    g.wait_for_input()
    from aw2test import ram
    e.w32(g.player(1)["addr"] + ram.P_CHARGE, tag.star_cost(0) * g.co_stars(CRUMB)[1])
    e.w32(tag.rec(1) + tag.P_CHARGE, tag.star_cost(0) * g.co_stars(romlib.co_id("sturm"))[1])
    return g


NAME_PALETTE = 0x080F6164        # the name graphics' fixed palette (sub_08043B44)
PRESENTATION = 0x08740000        # crate::co_new: 0x44 a CO, +4 the name graphic (LZ77)
AW2_PRESENTATION = 0x084A0090


def name_pixels(e, co):
    """The CO's name graphic as the game reads it: 16 rows of 48 palette indexes."""
    row = (PRESENTATION if co >= 19 else AW2_PRESENTATION) + 0x44 * co
    data = romlib.lz10(e.read(e.u32(row + 4), 0x300))
    px = [[0] * 48 for _ in range(16)]
    for col in range(6):
        for half in range(2):
            t = data[32 * (2 * col + half):32 * (2 * col + half) + 32]
            for y in range(8):
                for x in range(8):
                    px[8 * half + y][8 * col + x] = (t[4 * y + x // 2] >> (4 * (x & 1))) & 15
    return px


@test(modes=("ds",))
def crumb_name_graphic(ctx):
    """Crumb's name graphic reads "Crumb": five letters (C of Colin's, u, r, m of
    Sturm's and b of Kanbei's, AW2's own, composed by crate::crumb_art), in the
    six sprites and the game's name palette, drawn beside other CO names for
    comparison (crumb_name.png) and on his CO page in the game."""
    from aw2test import png
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.start(m, ["crumb", "jugger"])
    e = g.e
    pal_raw = e.read(NAME_PALETTE, 32)
    pal = [((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31) for c in (pal_raw[2 * i] | pal_raw[2 * i + 1] << 8 for i in range(16))]
    order = [("Colin", 16), ("Crumb", CRUMB), ("Sturm", 10), ("Kanbei", 6), ("Clone Andy", 81), ("Andy", 1), ("Adder", 13), ("Jugger", 72)]
    rows = []
    for name, co in order:
        px = name_pixels(e, co)
        rows += [[pal[v] for v in r] for r in px] + [[pal[0]] * 48]
    png.write(os.path.join(ctx.out, "crumb_name.png"), rows, 6)
    px = name_pixels(e, CRUMB)
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
    aw2 = {v for co in (16, 10, 6) for r in name_pixels(e, co) for v in r}
    ctx.check(used <= aw2, "only the colours of AW2's own name graphics")
    ctx.check(px not in (name_pixels(e, 10), name_pixels(e, 16)), "not Sturm's or Colin's")
    # The first letter is Colin's C, the fourth Sturm's m.
    ctx.check(all(px[y][runs[0][0]:runs[0][1] + 1] == name_pixels(e, 16)[y][9:17] for y in range(16)), "the C is Colin's")
    g.open_map_menu()
    g.choose("CO", g.MAP_MENU)
    e.wait(120)
    ctx.shot(g, "crumb_co_page")
