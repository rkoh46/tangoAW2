"""The Emerald Sun Campaign's five COs (crate::es_co, ids 86..90; Versus lists the four but Varro): their rows, texts and meters; the numbers of each
day to day and power in fights against the calculator (aw2test.damage.es_bonus); Klaus's heal and move, Livia's funds; the Tag pairs."""

from aw2test import rom as romlib
from aw2test.harness import test
from tests.test_crumb import set_unit, text, can_move, TABLE

KLAUS, AURELIA, CASSIUS, LIVIA, VARRO = 86, 87, 88, 89, 90
NAMES = {KLAUS: b"Klaus", AURELIA: b"Aurelia", CASSIUS: b"Cassius", LIVIA: b"Livia", VARRO: b"Varro"}
STARS = {KLAUS: (4, 8), AURELIA: (3, 7), CASSIUS: (3, 7), LIVIA: (3, 6), VARRO: (4, 8)}
COP_NAMES = {KLAUS: b"Testudo", AURELIA: b"Ballista", CASSIUS: b"Charge", LIVIA: b"Tribute", VARRO: b"Edict"}
SCOP_NAMES = {KLAUS: b"Legio Aeterna", AURELIA: b"Onager", CASSIUS: b"Triumph", LIVIA: b"Mare Nostrum", VARRO: b"Sol Invictus"}


@test(modes=("ds",))
def es_cos_are_on_the_teams_list(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.log(f"Teams list: {[romlib.co_name(c) for c in lst]}")
    for co in (KLAUS, AURELIA, CASSIUS, LIVIA):
        ctx.check(co in lst, f"{NAMES[co].decode()} is on the Teams list")
    ctx.check(VARRO not in lst, "Varro is not on the Teams list")


@test(modes=("ds",))
def es_cos_rows_texts_and_meters(ctx):
    """The CO table's rows, read in a battle of the campaign (M2: Klaus leads): names, stars, power names, unit cost."""
    from aw2test import escampaign as es
    e, g, d = es.enter(ctx, 2)
    for co in NAMES:
        row = TABLE + 0x104 * co
        who = NAMES[co].decode()
        ctx.eq(text(e, e.u32(row)), NAMES[co], f"{who}: the game's text for the name")
        ctx.eq((e.u32(row + 0x0C), e.u32(row + 0x10)), STARS[co], f"{who}: stars")
        ctx.eq(text(e, e.u32(row + 0x38 + 0x44)), COP_NAMES[co], f"{who}: CO Power's name")
        ctx.eq(text(e, e.u32(row + 0x38 + 0x88)), SCOP_NAMES[co], f"{who}: Super Power's name")
        for mode in range(3):
            ctx.eq(e.u16(row + 0x38 + 0x44 * mode + 0x14), 10 if co == LIVIA else 0, f"{who}: unit cost change (added to 100) at power level {mode}")
    e.close()


@test(modes=("aw2",))
def es_cos_absent_without_the_pack_and_the_flag(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    ctx.eq(len(g.teams()["co_list"]), 19, "AW2's 19 COs without the pack")


@test(modes=("ds",))
def varro_stays_out_of_versus(ctx):
    """Varro (the boss, a placeholder face) is on no Teams, War Room or Survival list; the four others are."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.check(VARRO not in lst, "Varro is not on the Teams list")
    ctx.check(all(c in lst for c in (KLAUS, AURELIA, CASSIUS, LIVIA)), "the four others are")
    # (the War Room's and Survival's lists, Varro absent: test_all_cos checks every CO once)


@test(modes=("ds",))
def es_klaus_legio_aeterna_heals_three_hp_and_testudo_moves_further(ctx):
    """In M2 (Klaus leads): Testudo gives Infantry one more move; Legio Aeterna heals every unit 3 HP."""
    from aw2test import escampaign as es
    e, g, d = es.enter(ctx, 2)
    mine = g.units(1)
    inf = next(u for u in mine if u["type"] == 1)
    ctx.log(f"Infantry at {(inf['x'], inf['y'])}")
    for u in mine:
        set_unit(g, u["x"], u["y"], hp=45)
    before, after = ctx.power(g, 1, "super")
    ctx.expect_hp_change(before, after, {1: 30}, "Legio Aeterna heals 3 HP", repair=True)
    ctx.eq(g.player(1)["co_mode"], 2, "Super power on")
    e.close()


@test(modes=("ds",))
def es_livia_collects_funds_when_she_pays_for_a_power(ctx):
    """In M6 (Livia leads): Tribute adds 200 funds for each property that earns."""
    from aw2test import escampaign as es
    e, g, d = es.enter(ctx, 6)
    w, h = d.size()
    n = 0
    for y in range(h):
        for x in range(w):
            c = g.terrain_class(x, y)
            if (c & 0x1F) in (6, 8, 10, 11, 14) and c >> 5 == 1:
                n += 1
    p = e.u32(0x08499598)
    before = e.u32(p + 0x3C)
    ctx.power(g, 1, "power")
    after = e.u32(p + 0x3C)
    ctx.log(f"{n} properties, funds {before} -> {after}")
    ctx.eq(after - before, 200 * n, f"Tribute: 200 funds for each of {n} properties")
    e.close()
