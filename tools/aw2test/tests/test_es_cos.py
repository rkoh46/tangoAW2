"""The Emerald Sun Campaign's five COs (crate::es_co, ids 86..90) in Versus (TANGOAW2_ES_VERSUS lists them): their rows, texts and meters; the numbers of each
day to day and power in fights against the calculator (aw2test.damage.es_bonus); Klaus's heal and move, Livia's funds; the Tag pairs."""

from aw2test import rom as romlib
from aw2test.harness import test
from tests.test_crumb import set_unit, text, can_move, TABLE

ENV = {"TANGOAW2_ES_VERSUS": "1"}
KLAUS, AURELIA, CASSIUS, LIVIA, VARRO = 86, 87, 88, 89, 90
NAMES = {KLAUS: b"Klaus", AURELIA: b"Aurelia", CASSIUS: b"Cassius", LIVIA: b"Livia", VARRO: b"Varro"}
STARS = {KLAUS: (4, 8), AURELIA: (3, 7), CASSIUS: (3, 7), LIVIA: (3, 6), VARRO: (4, 8)}
COP_NAMES = {KLAUS: b"Testudo", AURELIA: b"Ballista", CASSIUS: b"Charge", LIVIA: b"Tribute", VARRO: b"Edict"}
SCOP_NAMES = {KLAUS: b"Legio Aeterna", AURELIA: b"Onager", CASSIUS: b"Triumph", LIVIA: b"Mare Nostrum", VARRO: b"Sol Invictus"}


@test(modes=("ds",))
def es_cos_rows_texts_and_meters(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m, env=ENV)
    lst = g.teams()["co_list"]
    ctx.log(f"Teams list: {[romlib.co_name(c) for c in lst]}")
    for co in NAMES:
        ctx.check(co in lst, f"{NAMES[co].decode()} is on the Teams list (with the development flag)")
    for co in NAMES:
        g2 = ctx.start(m, [NAMES[co].decode().lower(), "andy"], env=ENV)
        e = g2.e
        row = TABLE + 0x104 * co
        ctx.eq(text(e, e.u32(row)), NAMES[co], f"{NAMES[co].decode()}: the game's text for his name")
        ctx.eq((e.u32(row + 0x0C), e.u32(row + 0x10)), STARS[co], f"{NAMES[co].decode()}: stars")
        ctx.eq(text(e, e.u32(row + 0x38 + 0x44)), COP_NAMES[co], f"{NAMES[co].decode()}: CO Power's name")
        ctx.eq(text(e, e.u32(row + 0x38 + 0x88)), SCOP_NAMES[co], f"{NAMES[co].decode()}: Super Power's name")
        cost = e.u16(row + 0x38 + 0x14)
        ctx.eq(cost, 110 if co == LIVIA else 100, f"{NAMES[co].decode()}: unit cost {cost}%")
        e.close()


@test(modes=("aw2",))
def es_cos_absent_without_the_pack_and_the_flag(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m, env=ENV)
    ctx.eq(len(g.teams()["co_list"]), 19, "AW2's 19 COs without the pack")


@test(modes=("ds",))
def es_cos_stay_out_of_versus_without_the_flag(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.check(not any(c in lst for c in NAMES), "no Emerald Sun CO on the Teams list until the campaign is approved")


def fight(ctx, co, mode_name, want, types=("infantry", "tank")):
    """`co` leads army 1 (at the power `mode_name`: None day to day, 'power', 'super'); each unit type's base damage against the same enemy type is `want[type]`."""
    m = ctx.map()
    y = 6
    for t in types:
        m.unit(1, t, 10, y).unit(2, t, 11, y)
        y += 2
    g = ctx.start(m, [NAMES[co].decode().lower(), "andy"], env=ENV)
    if mode_name:
        ctx.power(g, 1, mode_name)
    y = 6
    for t in types:
        r = ctx.attack(g, (10, y), (10, y), (11, y))
        ctx.eq(r["first"].base, want[t], f"{NAMES[co].decode()} {mode_name or 'day to day'}: a {t}'s base damage")
        y += 2
    return g


@test(modes=("ds",))
def es_klaus_imperium_testudo_and_legio_aeterna(ctx):
    # Infantry vs Infantry base 55; Tank vs Tank 55. Day to day: Infantry +20%, Tank +10%.
    fight(ctx, KLAUS, None, {"infantry": 66, "tank": 60})
    # Legio Aeterna: Infantry +20 +20 +40 +10 = +90%; Tank +10 +20 +10 = +40%.
    g = fight(ctx, KLAUS, "super", {"infantry": 104, "tank": 77})
    ctx.eq(g.player(1)["co_mode"], 2, "Super power on")


@test(modes=("ds",))
def es_klaus_heals_three_hp_and_moves_further(ctx):
    m = ctx.map()
    m.unit(1, "infantry", 10, 3).unit(1, "tank", 12, 10).unit(2, "tank", 25, 10)
    g = ctx.start(m, ["klaus", "andy"], env=ENV)
    set_unit(g, 10, 3, hp=45)
    set_unit(g, 12, 10, hp=45)
    ctx.check(not can_move(g, (10, 3), (14, 3)), "an Infantry cannot move 4 before the power")
    before, after = ctx.power(g, 1, "power")
    ctx.check(can_move(g, (10, 3), (14, 3)), "Testudo: an Infantry moves 4 (+1)")
    g2 = ctx.start(m, ["klaus", "andy"], env=ENV)
    set_unit(g2, 10, 3, hp=45)
    set_unit(g2, 12, 10, hp=45)
    before, after = ctx.power(g2, 1, "super")
    ctx.expect_hp_change(before, after, {1: 30}, "Legio Aeterna heals 3 HP", repair=True)
    ctx.check(can_move(g2, (10, 3), (14, 3)), "an Infantry moves 4 (+1)")


@test(modes=("ds",))
def es_aurelia_ballistics_and_cassius_impetus(ctx):
    fight(ctx, AURELIA, None, {"infantry": 55, "tank": 50})       # vehicles -10%
    fight(ctx, CASSIUS, None, {"infantry": 55, "tank": 60})       # vehicles +10%
    fight(ctx, CASSIUS, "power", {"infantry": 55, "tank": 83})    # +10 +30 +10
    fight(ctx, LIVIA, None, {"infantry": 55, "tank": 55})
    fight(ctx, VARRO, None, {"infantry": 63, "tank": 63})         # +15%


@test(modes=("ds",))
def es_livia_collects_funds_when_she_pays_for_a_power(ctx):
    m = ctx.map()
    for k in range(4):
        m.terrain(8 + k, 3, "city", 1)
    m.terrain(4, 2, "base", 1)
    m.unit(1, "infantry", 10, 6).unit(2, "infantry", 25, 10)
    g = ctx.start(m, ["livia", "andy"], env=ENV)
    p = g.e.u32(0x08499598)
    before = g.e.u32(p + 0x3C)
    ctx.power(g, 1, "power")
    after = g.e.u32(p + 0x3C)
    n = 1 + 4 + 1          # HQ, four cities, a base
    ctx.eq(after - before, 200 * n, f"Tribute: 200 funds for each of {n} properties")
