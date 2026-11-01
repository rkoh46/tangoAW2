"""The Silver Nova Campaign's three COs (crate::es_co, ids 86..88; the retired slots 89 and 90 copy Lili's and Caulder's rows and are on no list): their rows, texts and meters, read in
a mission of the campaign; their numbers and powers are played against the specification by `aw2dev co verify` (tests/test_co_verify.py)."""

from aw2test import rom as romlib
from aw2test.harness import test
from tests.test_crumb import text, TABLE

TABITHA, LILI, CAULDER, RETIRED_A, RETIRED_B = 86, 87, 88, 89, 90
NAMES = {TABITHA: b"Tabitha", LILI: b"Lili", CAULDER: b"Caulder"}
STARS = {TABITHA: (0, 9), LILI: (3, 0), CAULDER: (0, 4)}
COP_NAMES = {TABITHA: b"", LILI: b"Enigma", CAULDER: b""}
SCOP_NAMES = {TABITHA: b"Firestorm", LILI: b"", CAULDER: b"Cataclysm"}
RETIRED = {RETIRED_A: LILI, RETIRED_B: CAULDER}      # the slot and the CO whose row it copies


@test(modes=("ds",))
def es_cos_are_on_the_teams_list(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.log(f"Teams list: {[romlib.co_name(c) for c in lst]}")
    for co in NAMES:
        ctx.check(co in lst, f"{NAMES[co].decode()} is on the Teams list")
    ctx.check(RETIRED_A not in lst and RETIRED_B not in lst, "the retired slots 89 and 90 are not on the Teams list")


@test(modes=("ds",))
def es_cos_rows_texts_and_meters(ctx):
    """The CO table's rows, read in a battle of the campaign (M2: Tabitha leads): names, stars, power names, unit cost; the retired slots hold copies of Lili's and Caulder's rows."""
    from aw2test import escampaign as es
    e, g, d = es.enter(ctx, 2)
    for co in list(NAMES) + list(RETIRED):
        row = TABLE + 0x104 * co
        src = RETIRED.get(co, co)
        who = f"{NAMES[src].decode()}{' (retired slot ' + str(co) + ')' if co in RETIRED else ''}"
        ctx.eq(text(e, e.u32(row)), NAMES[src], f"{who}: the game's text for the name")
        ctx.eq((e.u32(row + 0x0C), e.u32(row + 0x10)), STARS[src], f"{who}: stars")
        ctx.eq(text(e, e.u32(row + 0x38 + 0x44)), COP_NAMES[src], f"{who}: CO Power's name")
        ctx.eq(text(e, e.u32(row + 0x38 + 0x88)), SCOP_NAMES[src], f"{who}: Super Power's name")
        for mode in range(3):
            ctx.eq(e.u16(row + 0x38 + 0x44 * mode + 0x14), 0, f"{who}: unit cost change (added to 100) at power level {mode}")
    e.close()


@test(modes=("aw2",))
def es_cos_absent_without_the_pack_and_the_flag(ctx):
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    ctx.eq(len(g.teams()["co_list"]), 19, "AW2's 19 COs without the pack")


@test(modes=("ds",))
def es_retired_slots_stay_out_of_versus(ctx):
    """Slots 89 and 90 (once Livia and Varro) are on no Teams list; Tabitha, Lili and Caulder are (the War Room's and Survival's lists: test_all_cos checks every CO once)."""
    m = ctx.map()
    m.unit(1, "tank", 10, 6).unit(2, "tank", 11, 6)
    g = ctx.boot_teams(m)
    lst = g.teams()["co_list"]
    ctx.check(RETIRED_A not in lst and RETIRED_B not in lst, "the retired slots are not on the Teams list")
    ctx.check(all(c in lst for c in NAMES), "the three are")
    ctx.eq(len(lst), 35, "35 COs with the pack")
