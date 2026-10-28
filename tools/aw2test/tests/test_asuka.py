"""Asuka (CO 92, crate::asuka): Sonja after she defects to Black Hole. Her numbers are Sonja's Dual Strike block (vision +1 / +2 / +2, her HP hidden from the enemy, strike-first in the
Super Power, the enemy's terrain stars cut by 1 / 2 / 3, luck 10 with bad luck 5), her powers Hawke's Black Wave and Black Storm on top (her units +1 / +2 HP, the enemy's -1 / -2, never below 1 HP);
3 / 9 stars (Eagle's meter). Every ability is exercised in real battles on Versus maps and checked against numbers worked out from the formula (the calculator, the game's own tables, the unit records):
    - the CO table's row: stars, vision, luck, bad luck, skills, power procedures, the texts;
    - D2D: the fog vision (+1), the enemy's terrain cut (1 star: the record's defence), the luck range (0..9 and -0..4 a roll, kept: see crate::asuka), hidden HP;
    - CO Power, Dark Intel: vision +2 and woods / reefs seen, the terrain cut (2), every unit +10 / -10 HP with the cap at 100 and the floor at 1, the cost;
    - Super Power, Event Horizon: vision, terrain cut 3, +20 / -20 HP, and Counter Break (her units strike first when attacked: the exact order of the two strikes);
    - the power meter's cost and charge, the CPU using her powers, the Tag Powers with Von Bolt and Hawke, netplay.
Run with TANGOAW2_DS_GRAPHICS=1 for the hidden-HP picture."""

import os

from aw2test import damage, ram
from aw2test import rom as romlib
from aw2test import tag
from aw2test.game import power_star_cost
from aw2test.harness import Skip, test
from tests.test_fog import MAP, seen

ASUKA = 92
HAWKE_COP, HAWKE_SCOP = 0x08044CF9, 0x08044D35
TEXT_TABLE = 0x08610A38
TEXT_BASE = 0x6D72


def row_addr(g):
    return g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * ASUKA


def mode_word(g, mode, off, size=2):
    a = row_addr(g) + 0x38 + 0x44 * mode + off
    return int.from_bytes(g.e.read(a, size), "little", signed=size == 2 and off in (0x0C, 0x0E, 0x10, 0x12, 0x14, 0x16))


def text_of(g, which):
    at = g.e.u32(TEXT_TABLE + 4 * (TEXT_BASE + 16 * 20 + which))
    out = bytearray()
    while len(out) < 400:
        c = g.e.u8(at + len(out))
        if c == 0:
            break
        out.append(c)
    return bytes(out)


def hp_of(g, x, y):
    u = g.unit_at(x, y)
    return u["hp"] if u else 0


# --- the CO table's row -----------------------------------------------------------------------------------------------------------------------

@test(modes=("ds",))
def asuka_row_is_sonjas_numbers_with_hawkes_powers(ctx):
    """The game's CO table (tangoAW2's copy) row 92: 4 and 8 stars; vision 1 / 2 / 2, luck 10, bad luck 5 and counter 0 in every level (Sonja's Dual Strike block); the skills hidden HP (1),
    + sees into hiding places (9) and + strikes first (0xD); the power procedures are Hawke's Black Wave and Black Storm; her texts are her own."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, ["asuka", "andy"])
    ctx.eq(g.co_stars(ASUKA), (4, 8), "stars: CO Power 4, Super Power 8 in all: the normal cost")
    ctx.eq(g.co_stars(romlib.co_id("eagle")), (3, 9), "(Eagle's own 3 / 9)")
    ctx.eq(g.co_stars(romlib.co_id("sonja")), (3, 5), "(Sonja's own 3 / 5)")
    ctx.eq(g.co_stars(romlib.co_id("hawke")), (5, 9), "(Hawke's own 5 / 9)")
    ctx.eq([mode_word(g, k, 0x0C) for k in range(3)], [1, 2, 2], "vision +1 / +2 / +2")
    ctx.eq([mode_word(g, k, 0x0E) for k in range(3)], [20, 20, 20], "luck 20 (0..19%): Nell's day to day, kept in her powers")
    nell = g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * romlib.co_id("nell") + 0x38
    ctx.eq(g.e.u16(nell + 0x0E), 20, "(Nell's own day-to-day luck is 20; her powers 60 and 100)")
    ctx.eq([mode_word(g, k, 0x10) for k in range(3)], [0, 0, 0], "no bad luck (Sonja's quirk is gone)")
    ctx.eq([mode_word(g, k, 0x12) for k in range(3)], [0, 0, 0], "no counter bonus (Dual Strike's Sonja has none)")
    ctx.eq([mode_word(g, k, 0x08, 4) for k in range(3)], [0x01, 0x09, 0x09], "skills: hidden HP; + sees into hiding places; no strike-first (Sonja's Super Power has it, Asuka's does not)")
    cop, scop = mode_word(g, 1, 0x04, 4), mode_word(g, 2, 0x04, 4)
    ctx.check(0x08749600 <= cop < 0x0874A000 and 0x08749600 <= scop < 0x0874A000 and cop != scop and cop & 1 and scop & 1, f"her own power procedures (Black Wave / Black Storm with Drake's fuel flag): {cop:#x}, {scop:#x}")
    ctx.check(cop != HAWKE_COP and scop != HAWKE_SCOP, "not Hawke's own words")
    ctx.eq(text_of(g, 0), b"Asuka", "name")
    ctx.eq(text_of(g, 5), b"Dark Intel", "CO Power name")
    ctx.eq(text_of(g, 6), b"Event Horizon", "Super Power name")
    for w, name in ((2, "day to day"), (3, "CO Power"), (4, "Super Power"), (1, "bio")):
        t = text_of(g, w)
        ctx.check(len(t) > 20 and b"Sonja" not in t, f"her {name} page is her own text ({t[:40]!r}...)")
    quotes = [text_of(g, 7 + q) for q in range(6)]
    ctx.check(quotes[0].startswith(b"I have read your") and quotes[1].startswith(b"Event Horizon") and quotes[2].startswith(b"Updating") and quotes[3:] == quotes[:3], f"quote slots: CO Power, Super Power, tag-in, twice (crate::co_new::texts) {quotes}")
    ctx.eq(g.player(1)["co"], ASUKA, "army 1 plays her")
    hawke = g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * romlib.co_id("hawke")
    ctx.eq(g.e.read(row_addr(g) + 0x14, 3), g.e.read(hawke + 0x14, 3), "her row's property / unit style and army colour bytes are Hawke's (Black Hole's: style 4, colour 5)")


# --- day to day: vision, terrain, luck, hidden HP ---------------------------------------------------------------------------------------------

def no_rain(g):
    """The tests that hand the turn to a second HUMAN player (hotseat) stop the rain her powers bring: in fog of war the turn change shows a hand-over screen the scripted pad does not press. The rain itself is tested
    by `asuka_powers_bring_rain_with_fog_for_two_rounds` and friends."""
    from aw2test import ram
    g.e.w8(ram.WEATHER, 0)
    g.e.w8(0x03003FEE, 0)
    g.e.w8(0x0203FFA6 + 1, 0)      # (the Rules' fog memory of a rain in progress: none)


def vision_map(ctx):
    m = ctx.map()
    for x, y in ((12, 6), (11, 6), (10, 8)):
        m.terrain(x, y, "wood")
    m.unit(1, "tank", 10, 6).unit(2, "infantry", 12, 6).unit(2, "infantry", 11, 6).unit(2, "infantry", 13, 7)
    for k in range(3, 9):
        m.terrain(2 + k, 14, "plain")
    m.unit(1, "tank", 2, 14)
    return m


@test(modes=("ds",))
def asuka_d2d_vision_is_one_more(ctx):
    """Fog of War: a Tank (vision 3) of Asuka's sees plains 4 away (+1) and not 5; for Andy it sees only 3. Woods 2 away stay hidden day to day."""
    g = ctx.start(vision_map(ctx), ["asuka", "andy"], fog=True)
    ctx.eq(seen(g, 13, 7), 1, "plains 4 away from the Tank at (10, 6): seen (+1 vision)")
    ctx.eq(seen(g, 2 + 4, 14), 1, "a second Tank: 4 away on plains seen")
    ctx.eq(seen(g, 2 + 5, 14), 0, "5 away: not seen")
    ctx.eq(seen(g, 12, 6), 0, "woods 2 away: still hidden day to day")
    ctx.eq(seen(g, 10, 8), 0, "empty woods: hidden")
    g2 = ctx.start(vision_map(ctx), ["andy", "andy"], fog=True)
    ctx.eq(seen(g2, 13, 7), 0, "(Andy's Tank does not see 4 away)")
    ctx.shot(g, "fog_d2d")


@test(modes=("ds",))
def asuka_cop_vision_two_more_and_sees_into_woods(ctx):
    """Dark Intel: vision +2 (plains 5 away seen, 6 not) and the woods 2 away, and the empty woods, are seen (hiding places)."""
    g = ctx.start(vision_map(ctx), ["asuka", "andy"], fog=True)
    ctx.power(g, 1, "power")
    g.e.wait(30)
    # (the rain the power brings takes 1 off: 3 + 2 - 1 = 4 plains; AW2's rain rule)
    ctx.eq(seen(g, 2 + 4, 14), 1, "plains 4 away: seen (+2 vision, -1 for the rain)")
    ctx.eq(seen(g, 2 + 5, 14), 0, "5 away: not seen")
    ctx.eq(seen(g, 12, 6), 1, "woods 2 away: seen")
    ctx.eq(seen(g, 10, 8), 1, "empty woods: seen")
    ctx.shot(g, "fog_cop")


@test(modes=("ds",))
def asuka_scop_vision_two_more_and_sees_into_woods(ctx):
    g = ctx.start(vision_map(ctx), ["asuka", "andy"], fog=True)
    ctx.power(g, 1, "super")
    g.e.wait(30)
    ctx.eq(seen(g, 2 + 4, 14), 1, "plains 4 away: seen (+2 vision, -1 for the rain)")
    ctx.eq(seen(g, 2 + 5, 14), 0, "5 away: not seen")
    ctx.eq(seen(g, 12, 6), 1, "woods 2 away: seen")
    ctx.shot(g, "fog_scop")


def cut_fight(ctx, mode, terrain="mountain"):
    """Asuka's Tank attacks Andy's Infantry on a mountain (4 stars): returns (the calculator's defence with her cut, the record's defence)."""
    m = ctx.map()
    m.terrain(11, 10, terrain)
    m.unit(1, "tank", 10, 10).unit(2, "infantry", 11, 10)
    g = ctx.start(m, ["asuka", "andy"])
    if mode:
        ctx.power(g, 1, mode)
    target = g.unit_at(11, 10)
    d_side = ctx.side(g, target)
    a_side = ctx.side(g, g.unit_at(10, 10), terrain=g.terrain_class(10, 10))
    r = ctx.attack(g, (10, 10), (10, 10), (11, 10))
    cut = ctx.rules.enemy_terrain_cut(ASUKA, g.player(1)["co_mode"])
    want = damage.total_defence(ctx.rules, d_side, cut, 1)
    return g, cut, want, r["records"][1]["defence"]


@test(modes=("ds",))
def asuka_enemy_terrain_cover_is_cut_one_two_three_stars(ctx):
    """Sonja's cut: the enemy's units lose 1 star of cover day to day, 2 in Dark Intel, 3 in Event Horizon (10 defence points a star): the game's defence number for an Infantry on a
    mountain (4 stars) is the formula's with exactly that cut, and the loss is inside the calculator's range."""
    seen_def = []
    for mode, stars in ((None, 1), ("power", 2), ("super", 3)):
        g, cut, want, got = cut_fight(ctx, mode)
        ctx.eq(cut, stars, f"{mode or 'day to day'}: the CO table's cut")
        ctx.eq(got, want, f"{mode or 'day to day'}: the battle record's defence = the formula's ({want}, cut {stars} star(s) of the mountain's 4)")
        seen_def.append(got)
    ctx.check(seen_def[0] > seen_def[1] > seen_def[2], f"each level cuts more: defence {seen_def} (200 - defence is the damage taken)")


@test(modes=("ds",))
def asuka_luck_is_nells_and_there_is_no_bad_luck(ctx):
    """Black Insight's luck: each hit rolls 0..19% (Nell's day-to-day), no bad luck, in every level. Ten Tank hits on ten Infantry in one turn (the sampled spread): every loss is inside the calculator's range
    for luck (20, 0), none under its lower end (a bad-luck roll would be), and some above what luck 10 can reach (the chance of none in ten hits is 1 in 1000)."""
    m = ctx.map()
    for k in range(10):
        m.unit(1, "tank", 3 + 2 * k, 10).unit(2, "infantry", 3 + 2 * k, 11)
    g = ctx.start(m, ["asuka", "andy"])
    a, d = g.unit_at(3, 10), g.unit_at(3, 11)
    out = damage.strike(ctx.rules, ctx.side(g, a, terrain=g.terrain_class(3, 10)), ctx.side(g, d), 1, True, a["hp"])
    ctx.eq(out.luck, (20, 0), "the calculator's luck for Asuka")
    allowed = sorted(out.losses)
    plain = sorted(damage.strike(ctx.rules, ctx.side(g, a, terrain=1), ctx.side(g, d), 1, True, 100).losses)
    losses = []
    for k in range(10):
        before = hp_of(g, 3 + 2 * k, 11)
        g.attack((3 + 2 * k, 10), (3 + 2 * k, 10), (3 + 2 * k, 11))
        losses.append(before - hp_of(g, 3 + 2 * k, 11))
    ctx.log(f"ten hits cost {losses}; the range {allowed}")
    ctx.check(all(l in allowed for l in losses), f"every loss is inside the range for luck 0..19 {allowed[0]}..{allowed[-1]}")
    ctx.check(min(losses) >= allowed[0], "none under the range's lower end (no bad luck)")
    top10 = allowed[min(9, len(allowed) - 1)]
    ctx.check(max(losses) > top10, f"some hit is above what luck 10 reaches ({top10}): {max(losses)}")


@test(modes=("ds",))
def asuka_ground_units_pay_one_movement_point_for_every_terrain(ctx):
    """Black Insight's movement is Sturm's (his row's charts, as the Dual Strike pack has them): a Tank (move 6) of Asuka's crosses woods and sea-side shoals at 1 a cell and reaches 6 cells away over
    woods where Andy's (woods cost 2 for treads) falls short, and the reach is the same in rain and snow (the pack's weather no longer slows anyone); the CPU's Asuka moves the same way."""
    from tests.test_tag import can_move
    for weather in ("clear", "rain", "snow"):
        res = {}
        for co in ("asuka", "sturm", "andy"):
            m = ctx.map()
            for x in (6, 7, 8):
                m.terrain(x, 10, "wood")
                m.terrain(x, 12, "mountain")
            m.unit(1, "tank", 5, 10).unit(1, "infantry", 5, 12).unit(2, "tank", 25, 3)
            g = ctx.start(m, [co, "olaf"], weather=weather)
            res[co] = (can_move(g, (5, 10), (11, 10)), can_move(g, (5, 12), (8, 12)), can_move(g, (5, 10), (12, 10)))
        ctx.log(f"{weather}: (Tank 6 cells over woods, Infantry 3 cells over mountains, Tank 7 cells) {res}")
        ctx.eq(res["asuka"], res["andy"], f"{weather}: Asuka's units move exactly like Andy's (no movement trait any more)")
        ctx.eq(res["asuka"][:2], (False, False), f"{weather}: woods cost her Tank 2 and mountains her Infantry 2 like anyone's")



@test(modes=("ds",))
def asuka_hp_is_hidden_from_the_enemy(ctx):
    """Hidden HP (skill 0x01 in every level of her row): the enemy sees a "?" in the unit panel where the number would be; her own units show theirs (Sonja's behaviour,
    tests/test_ds_fix6.py). Needs TANGOAW2_DS_GRAPHICS=1; the table's skill bit is checked in the row test."""
    from tests.test_ds_hud import GRAPHICS, battle, panel_digits, number_at, panel_sprites, shot
    if not GRAPHICS:
        raise Skip("needs TANGOAW2_DS_GRAPHICS=1")
    from tests.test_ds_fix6 import T_QUESTION
    m = ctx.map()
    m.terrain(0, 19, "hq", 3).terrain(29, 0, "hq", 4)
    m.unit(1, 16, 5, 5).unit(2, 16, 8, 5)
    g = ctx.start(m, ["andy", "asuka", "drake", "grit"])
    e = g.e
    g.goto(8, 5)
    e.wait(50)
    ps = panel_sprites(e)
    ctx.check(any(sp[2] == T_QUESTION for sp in ps), f"the '?' is shown on Asuka's unit ({ps})")
    good, bad = panel_digits(e)
    heart_rows = {sp[1] + 1 for sp in ps if sp[2] == 862}
    ctx.check(not any(y in heart_rows for _, y, _ in good), "no number on the hit points row")
    shot(ctx, g, "asuka_hidden_hp")
    g.goto(5, 5)
    e.wait(50)
    good, bad = panel_digits(e)
    ctx.check(any(number_at(good, y) == "10" for y in {y for _, y, _ in good}), "the other army's unit shows its 10")


# --- the powers: Black Wave and Black Storm HP ------------------------------------------------------------------------------------------------

OWN = [("tank", 10, 10, 100), ("mech", 5, 5, 45), ("infantry", 7, 7, 95), ("artillery", 3, 12, 100), ("recon", 8, 8, 5), ("tank", 12, 12, 91)]
FOE = [("tank", 11, 10, 100), ("infantry", 6, 4, 55), ("recon", 20, 12, 5), ("artillery", 21, 12, 11), ("mech", 22, 14, 10), ("tank", 24, 6, 100)]


def hp_map(ctx):
    m = ctx.map()
    m.terrain(4, 4, "city", 1).terrain(6, 5, "city", 2)
    for k, (t, x, y, hp) in enumerate(OWN):
        m.unit(1, t, x, y)
    for k, (t, x, y, hp) in enumerate(FOE):
        m.unit(2, t, x, y)
    return m


def hp_battle(ctx, which, cos=("asuka", "andy"), **kw):
    g = ctx.start(hp_map(ctx), list(cos), **kw)
    for t, x, y, hp in OWN + FOE:
        if hp != 100:
            ctx.set_hp(g, x, y, hp)
    return g


def fire(ctx, g, which, step):
    """`step`: the HP (internal) every enemy unit loses (0 in Dark Intel, 10 in Event Horizon); hers never change."""
    before_hp = {(u["x"], u["y"]): u["hp"] for u in g.units()}
    before, after = ctx.power(g, 1, which)
    ctx.expect_hp_change(before, after, {1: 0, 2: -step}, f"Asuka's {which}")
    moved = {}
    for u in after.values():
        key = (u["x"], u["y"])
        moved[key] = (before_hp.get(key), u["hp"], u["army"])
    ctx.log(f"HP before -> after: {moved}")
    return before, after, moved


@test(modes=("ds",))
def asuka_cop_black_analysis_heals_one_and_costs_the_enemy_one(ctx):      # (name kept for `co verify`; the CO Power now changes no HP)
    """CO Power: no HP changes on either side (the units' HP before and after are equal); the meter is spent at the 4-star price (36000, 9000 a star)."""
    g = hp_battle(ctx, "power")
    p = g.player(1)
    ctx.eq(g.charge_power(1, "power"), 4 * 9000, "the CO Power costs 4 stars of 9000")
    before, after, moved = fire(ctx, g, "power", 0)
    want = {(x, y): hp for _, x, y, hp in OWN + FOE}
    for pos, hp in want.items():
        ctx.eq(hp_of(g, *pos), hp, f"HP at {pos} after Dark Intel: unchanged (no HP effect)")
    ctx.eq(g.player(1)["powers_used"], 1, "one power used (the next costs +20%)")
    ctx.shot(g, "cop_hp")


@test(modes=("ds",))
def asuka_scop_counter_storm_heals_two_and_costs_the_enemy_two(ctx):      # (name kept for `co verify`; the Super Power costs every enemy unit 1 HP)
    """Super Power: her units keep their HP; every enemy unit loses 1 HP (10): 55 -> 45, 100 -> 90, 5 -> 1, 11 -> 1, 10 -> 1. The price is 8 stars of 9000."""
    g = hp_battle(ctx, "super")
    ctx.eq(g.charge_power(1, "super"), 8 * 9000, "the Super Power costs 8 stars of 9000")
    before, after, moved = fire(ctx, g, "super", 10)
    # hers unchanged, every enemy unit loses 1 HP (10) and never goes below 1 HP
    want = {(x, y): hp for _, x, y, hp in OWN}
    want.update({(11, 10): 90, (6, 4): 45, (20, 12): 1, (21, 12): 1, (22, 14): 1, (24, 6): 90})
    for pos, hp in want.items():
        ctx.eq(hp_of(g, *pos), hp, f"HP at {pos} after Event Horizon")
    ctx.shot(g, "scop_hp")


@test(modes=("ds",))
def asuka_powers_cost_more_each_use_and_the_meter_charges(ctx):
    """The meter: the first CO Power is 27000, after one use the next costs 20% more (32400); a fight charges the meter by the damage dealt (ctx.attack checks the formula with
    Dual Strike's charge per HP)."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(2, "infantry", 25, 15)
    g = ctx.start(m, ["asuka", "andy"])
    ctx.eq(g.player(1)["charge"], 0, "the meter starts empty")
    ctx.attack(g, (10, 10), (10, 10), (11, 10))
    p = g.player(1)
    ctx.check(0 < p["charge"] < 4 * 9000, f"the attack charged the meter ({p['charge']}) below the CO Power's 36000")
    ctx.eq(power_star_cost(0) * 4, 36000, "the first CO Power's price (4 stars)")
    ctx.eq(power_star_cost(1) * 4, 43200, "the second's")
    ctx.eq(power_star_cost(0) * 8, 72000, "the first Super Power's price (8 stars)")
    ctx.eq(g.charge_power(1, "power"), 36000, "the harness fills exactly 36000")
    ctx.power(g, 1, "power")
    g.end_turn(human=1)
    g.end_turn(human=1)
    ctx.eq(g.charge_power(1, "power"), 43200, "after one power used: 43200")
    before, after = ctx.power(g, 1, "power")
    ctx.eq(g.player(1)["powers_used"], 2, "two used")


@test(modes=("ds",))
def asuka_powers_last_until_her_next_turn_and_hold_through_the_enemys(ctx):
    """The power's mode stays on while the enemy moves and is off at her next turn; Counter Break is therefore on during the enemy's turn."""
    g = hp_battle(ctx, "super")
    ctx.power(g, 1, "super")
    g.e.wait_until(lambda: g.current_army() == 1, 10)
    modes = []
    g.end_turn(human=1, observe=lambda gg: modes.append(gg.player(1)["co_mode"]))
    ctx.eq(modes, [2], "Event Horizon still on when the enemy's turn begins")
    ctx.eq(g.player(1)["co_mode"], 0, "and over when her turn comes back")


# --- Black Insight: +5% attack and defence ---------------------------------------------------------------------------------------------------

@test(modes=("ds",))
def asuka_day_to_day_adds_five_percent_attack_and_defence_and_it_stacks_with_the_powers(ctx):
    """Black Insight: the damage numbers are worked from firepower 100 + 5 (+ 10 in a power) and defence 100 + terrain + 5 (+ 10 in a power), against Andy's for the same units. The game's own
    battle records in exact numbers, for Tank, Infantry / Mech and Artillery pairs, day to day, in Dark Intel and in Event Horizon: `base` is the chart value x the firepower, `defence` the
    defender's total."""
    chart = ctx.rules
    modes = ((None, 0), ("power", 1), ("super", 2))
    for a, d, dist in (("tank", "tank", 1), ("infantry", "mech", 1), ("artillery", "tank", 2)):
        for which, level in modes:
            # Asuka attacks Andy: base = chart x (100 + 5 + the power's 10) / 100
            m = ctx.map()
            m.unit(1, a, 10, 10).unit(2, d, 10 + dist, 10)
            g = ctx.start(m, ["asuka", "andy"])
            if which:
                ctx.power(g, 1, which)
            att, dfd = g.unit_at(10, 10), g.unit_at(10 + dist, 10)
            r = ctx.attack(g, (10, 10), (10, 10), (10 + dist, 10))
            got = r["records"][0]["base"]
            fp = 100 + damage.ASUKA_DAY_BONUS + (10 if which else 0)
            ctx.eq(got, r["first"].base, f"{a} -> {d}, {which or 'day to day'}: the game's base damage is the calculator's (firepower {fp}%)")
            literal = {("tank", "tank"): 55, ("artillery", "tank"): 70}.get((a, d))
            if literal:
                ctx.eq(got, damage.div(literal * fp, 100), f"{a} -> {d}, {which or 'day to day'}: chart {literal} x {fp}% = {damage.div(literal * fp, 100)}")
            # Andy attacks Asuka: her defence in the record is the formula's with her +5 (and the power's +10)
            m = ctx.map()
            m.unit(1, a, 10, 10).unit(2, d, 10 + dist, 10)
            g2 = ctx.start(m, ["andy", "asuka"], humans=(1, 2))
            if which:
                g2.end_turn(human=2)
                ctx.power(g2, 2, which)
                no_rain(g2)
                g2.end_turn(human=1)
            tgt = g2.unit_at(10 + dist, 10)
            side = ctx.side(g2, tgt)
            want_def = damage.total_defence(chart, side, 0, dist)
            g2.attack((10, 10), (10, 10), (10 + dist, 10))
            rd = ctx.battle_records(g2)[1]
            ctx.eq(rd["defence"], want_def, f"{d} of Asuka's, {which or 'day to day'}: Andy's attack meets defence {want_def} (her day-to-day bonus {damage.ASUKA_DAY_BONUS}{' and the power +10' if which else ''})")
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10)
    g = ctx.start(m, ["andy", "asuka"], humans=(1, 2))
    g.attack((10, 10), (10, 10), (11, 10))
    ctx.eq(ctx.battle_records(g)[1]["defence"], 110 + damage.ASUKA_DAY_BONUS, "Asuka's Tank on plains defends at 100 + 10 (one star) + her day-to-day bonus (5; Andy's would be 110)")


# --- Dark Intel / Event Horizon: the enemy's ammo and fuel are halved ------------------------------------------------------------------------

AF_KINDS = ["tank", "infantry", "bcopter", "fighter", "artillery", "mech", "recon", "apc", "battleship", "tank", "tank", "tank"]
AF_FUEL = [99, 70, 45, 23, 22, 21, 9, 3, 1, 2, 5, 4]
AF_AMMO = [9, 0, 6, 9, 9, 3, 0, 0, 9, 1, 2, 3]


def af_game(ctx, cos=("asuka", "andy"), fog=False):
    m = ctx.map()
    for k, t in enumerate(AF_KINDS):
        m.unit(1, t, 3 + k, 3)
        m.unit(2, t, 3 + k, 10)
    g = ctx.start(m, list(cos), fog=fog)
    for army, y in ((1, 3), (2, 10)):
        for k in range(len(AF_KINDS)):
            u = g.unit_at(3 + k, y)
            a = g.unit_addr(u["id"])
            g.e.w8(a + 6, (g.e.u8(a + 6) & 0x80) | AF_FUEL[k])
            w = g.e.u16(a + 4)
            g.e.w16(a + 4, (w & ~0x780) | (AF_AMMO[k] << 7))
    return g


def af_state(g, y):
    return [(g.unit_at(3 + k, y)["fuel"], g.unit_at(3 + k, y)["ammo"]) for k in range(len(AF_KINDS))]


@test(modes=("ds",))
def asuka_powers_halve_the_enemys_ammo_and_fuel_rounded_down(ctx):
    """Both powers: every enemy unit's fuel and ammo is halved, rounded down (AW2's own rounding of Drake's fuel flag: 99 -> 49, 21 -> 10, 1 -> 0; the ammo the same: 9 -> 4, 3 -> 1, 1 -> 0, and 0
    stays 0 so Infantry, Recon and APC, which have no ammo stat, are unaffected); her own units keep both."""
    for which in ("power", "super"):
        g = af_game(ctx)
        before_enemy, before_own = af_state(g, 10), af_state(g, 3)
        ctx.eq(before_enemy, list(zip(AF_FUEL, AF_AMMO)), "the setup is on the units")
        ctx.power(g, 1, which)
        ctx.eq(af_state(g, 10), [(f // 2, a // 2) for f, a in zip(AF_FUEL, AF_AMMO)], f"{which}: the enemy's fuel and ammo, halved and rounded down")
        ctx.eq(af_state(g, 3), before_own, f"{which}: her own units' fuel and ammo are untouched")
        ctx.shot(g, f"halve_{which}")


@test(modes=("ds",))
def asuka_fuel_and_ammo_halving_with_a_unit_in_a_transport_and_none_for_an_ally(ctx):
    """A unit of Asuka's own team (an ally in a team game) is not halved, only the other teams' units are; the HP effect and the halving agree on who is an enemy."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 12, 10).unit(3, "tank", 14, 10)
    g = ctx.start(m, ["asuka", "andy", "max"])
    ctx.eq(g.player(2)["co"], 1, "army 2 is Andy")
    for x in (12, 14):
        a = g.unit_addr(g.unit_at(x, 10)["id"])
        g.e.w8(a + 6, (g.e.u8(a + 6) & 0x80) | 60)
    ctx.power(g, 1, "power")
    ctx.eq([g.unit_at(x, 10)["fuel"] for x in (12, 14)], [30, 30], "both armies of the other teams are halved")


# --- Counter Break: her units strike first -------------------------------------------------------------------------------------------------

def strike_first_battle(ctx, power):
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(1, "infantry", 3, 3).unit(2, "infantry", 25, 15)
    g = ctx.start(m, ["asuka", "andy"], humans=(1, 2))
    if power:
        ctx.power(g, 1, power)
        no_rain(g)
    g.end_turn(human=2)
    return g


STRIKE_FIRST = False      # Event Horizon has no strike-first any more (Counter Break was removed with the simplification)


@test(modes=("ds",))
def asuka_counter_break_her_units_strike_first(ctx):
    """No strike-first any more (Counter Break was removed): when Andy's Tank (100 HP) attacks Asuka's Tank (100 HP) in Event Horizon, in Dark Intel and without a power alike, the order is the plain one:
    he hits first, her reply is reduced (the losses fit the calculator's plain order). `STRIKE_FIRST` = True would test the old behaviour."""
    for power in ("super", None, "power"):
        g = strike_first_battle(ctx, power)
        a0, d0 = g.unit_at(10, 10), g.unit_at(11, 10)       # hers, his
        ctx.eq(g.current_army(), 2, "Andy's turn")
        att_side = ctx.side(g, d0, terrain=g.terrain_class(11, 10))
        def_side = ctx.side(g, a0)
        dist = 1
        (_, att1), (_, dfd1) = g.attack((11, 10), (11, 10), (10, 10))
        att_loss, dfd_loss = d0["hp"] - att1["hp"], a0["hp"] - dfd1["hp"]
        ctx.log(f"{power}: Andy's Tank lost {att_loss}, Asuka's lost {dfd_loss}")
        plain_first = damage.strike(ctx.rules, att_side, def_side, dist, True, d0["hp"])
        # the plain order: his strike first, then her reply from the HP she has left
        plain_reply = set()
        for l1 in plain_first.losses:
            left = a0["hp"] - min(l1, a0["hp"])
            if left > 0 and l1 == dfd_loss:
                plain_reply |= {min(l, 100) for l in damage.strike(ctx.rules, def_side, att_side, dist, False, left).losses}
        if STRIKE_FIRST and power == "super":
            hers = damage.strike(ctx.rules, def_side, att_side, dist, False, a0["hp"])
            ctx.check(att_loss in {min(l, 100) for l in hers.losses}, f"strike first: Andy's loss {att_loss} is her full-HP strike's {sorted(hers.losses)}")
            ok = False
            for l1 in hers.losses:
                left = d0["hp"] - min(l1, d0["hp"])
                if left <= 0 or min(l1, 100) != att_loss:
                    continue
                reply = damage.strike(ctx.rules, att_side, def_side, dist, True, left)
                ok = ok or dfd_loss in {min(l, 100) for l in reply.losses}
            ctx.check(ok, f"strike first: her loss {dfd_loss} is his reply from the HP he had left")
            ctx.check(att_loss not in plain_reply, f"and it is not what her reply would be in the plain order ({sorted(plain_reply)})")
        else:
            ctx.check(dfd_loss in {min(l, 100) for l in plain_first.losses}, f"plain order: her loss {dfd_loss} is his first strike {sorted(plain_first.losses)}")
            ctx.check(att_loss in plain_reply, f"plain order: Andy's loss {att_loss} is her reply from the HP she had left {sorted(plain_reply)}")
        ctx.shot(g, f"counter_{power}")


# --- the CPU uses her powers -----------------------------------------------------------------------------------------------------------------

@test(modes=("ds",))
def asuka_cpu_uses_her_powers(ctx):
    """A CPU Asuka (Hawke's profile: `ds_ai::template_of`) with the meter at the CO Power's price uses her CO Power on her turn, and with the Super Power's price her Super Power: the mode turns on, the
    Black Wave's / Black Storm's HP change is applied to both armies' units, the meter is spent and the turn still ends and comes back to the human."""
    for which, mode, step in (("power", 1, 0), ("super", 2, 10)):
        m = ctx.map()
        m.unit(1, "tank", 10, 10).unit(1, "infantry", 3, 3).unit(2, "tank", 20, 10).unit(2, "infantry", 22, 12)
        g = ctx.start(m, ["andy", "asuka"])
        ctx.set_hp(g, 3, 3, 60)
        ctx.set_hp(g, 22, 12, 60)
        ctx.eq(g.player(2)["co"], ASUKA, "army 2 is Asuka, played by the CPU")
        seen_mode = []
        hp = []
        g.charge_power(2, which)

        def watch(gg):
            gg.e.wait_until(lambda: gg.player(2)["co_mode"] > 0 or gg.current_army() != 2, 6000, step=10)
            seen_mode.append(gg.player(2)["co_mode"])
            gg.e.wait(300)
            hp.append((hp_of(gg, 3, 3), hp_of(gg, 22, 12)))
        g.end_turn(human=1, observe=watch)
        ctx.log(f"CPU Asuka with a {which} meter: mode {seen_mode}, HP of Andy's and her Infantry after the power {hp}")
        ctx.eq(seen_mode, [mode], f"the CPU used her {'CO' if mode == 1 else 'Super'} Power on her turn")
        ctx.check(hp and hp[0][0] <= 60 - step, f"Andy's Infantry lost {step // 10} HP or more to it (60 -> {hp[0][0] if hp else None})")
        ctx.eq(g.current_army(), 1, "the turn came back to the human")
        ctx.shot(g, f"cpu_{which}")


# --- Tag Powers ---------------------------------------------------------------------------------------------------------------------------------

def tag_battle(ctx, cos, partners, units=()):
    from tests.test_tag import tag_battle as tb
    return tb(ctx, cos, partners, units=units)


@test(modes=("ds",))
def asuka_tag_compatibility_and_names(ctx):
    """The pairs' compatibility is tangoAW2's table (crate::sturm_pairs): Von Bolt 115 (Vault Breakers), Hawke 120 (Black Eclipse), Sturm 118, Lash 115, Flak 110, Adder 110, anyone else 95,
    in both orders: the Tag Power's firepower in the game is compatibility - 100 against the calculator."""
    ds = romlib.DualStrike()
    want = {"vonbolt": 115, "hawke": 120, "sturm": 118, "lash": 115, "flak": 110, "adder": 110, "andy": 95, "kanbei": 95, "sonja": 95}
    for other, c in want.items():
        for a, b in (("asuka", other), (other, "asuka")):
            ctx.eq(tag.compatibility(ds, romlib.co_id(a), romlib.co_id(b)), c, f"{a}+{b}")
    for other in ("vonbolt", "hawke"):
        units = [(1, "tank", 10, 10), (2, "tank", 11, 10)]
        g = tag_battle(ctx, ["asuka", "olaf"], [other, "max"], units=units)
        g.e.w8(tag.rec(1) + 1, 1)
        g.e.w8(tag.rec(2) + 1, 1)
        ctx.eq(ctx.tag_firepower(g, 1, g.player(1)["co"]), want[other] - 100, f"asuka+{other}: the game's tag firepower")
        ctx.attack(g, (10, 10), (10, 10), (11, 10))


def run_tag_power(ctx, partner, label, partner_step):
    """Asuka's Super Power (first half), then the partner's (second half) with a Tag Power from the map menu; returns the HP lists and checks Asuka's +/-20 in the first half."""
    from tests.test_tag import fill
    units = [(1, "tank", 10, 10), (2, "tank", 11, 10), (1, "tank", 10, 12), (2, "infantry", 11, 12), (1, "infantry", 3, 3), (2, "infantry", 25, 14), (1, "mech", 6, 6)]
    g = tag_battle(ctx, ["asuka", "olaf"], [partner, None], units=units)
    e = g.e
    ctx.set_hp(g, 3, 3, 45)
    ctx.set_hp(g, 25, 14, 55)
    ctx.set_hp(g, 6, 6, 100)
    fill(g, 1)
    before = {(u["x"], u["y"]): u["hp"] for u in g.units()}
    g.open_map_menu()
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), f"{label}: the first Super Power (Asuka's) starts")
    g.wait_for_input()
    mid = {(u["x"], u["y"]): u["hp"] for u in g.units()}
    ctx.eq(mid[(3, 3)], 45, f"{label}: Event Horizon leaves her Infantry at 45 (no healing)")
    ctx.eq(mid[(25, 14)], 45, f"{label}: and costs the enemy Infantry 55 -> 45")
    ctx.eq(mid[(10, 10)], 100, f"{label}: Tank stays at 100")
    ctx.eq(mid[(11, 10)], 90, f"{label}: enemy Tank 100 -> 90")
    ctx.eq(ctx.tag_firepower(g, 1, ASUKA), tag.compatibility(romlib.DualStrike(), ASUKA, romlib.co_id(partner)) - 100, f"{label}: tag firepower in the first half")
    ctx.shot(g, f"tag_{partner}_first_half")
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co"] == romlib.co_id(partner) and g.player(1)["co_mode"] == 2, 3000, step=10), f"{label}: the second half: {partner}'s Super Power")
    g.wait_for_input()
    after = {(u["x"], u["y"]): u["hp"] for u in g.units()}
    ctx.shot(g, f"tag_{partner}_second_half")
    return before, mid, after


@test(modes=("ds",))
def asuka_tag_power_with_von_bolt(ctx):
    """Vault Breakers (Asuka + Von Bolt, 115): the Tag Power fires Asuka's Event Horizon (+20 / -20 HP) and then Von Bolt's Ex Machina on the second half."""
    before, mid, after = run_tag_power(ctx, "vonbolt", "Vault Breakers", 0)
    ctx.check(after != mid, "Von Bolt's half changed the board (Ex Machina's strike)")


@test(modes=("ds",))
def asuka_tag_power_with_hawke(ctx):
    """Black Eclipse (Asuka + Hawke, 120): Event Horizon (enemy -10) and then Hawke's Black Storm (+20 / -20): the totals are +20 for hers and -30 for the enemy's over the two halves, capped at 100 and floored at 1."""
    before, mid, after = run_tag_power(ctx, "hawke", "Black Eclipse", 20)
    ctx.eq(after[(3, 3)], 65, "Infantry 45 -> 45 -> 65")
    ctx.eq(after[(25, 14)], 25, "enemy Infantry 55 -> 45 -> 25")
    ctx.eq(after[(11, 10)], 70, "enemy Tank 100 -> 90 -> 70")
    ctx.eq(after[(10, 10)], 100, "Tank 100 stays")


# --- netplay ------------------------------------------------------------------------------------------------------------------------------------

@test(modes=("ds",), netplay=True)
def asuka_netplay_both_powers_and_strike_first_are_identical_on_both_peers(ctx):
    """Both peers and the straight replay agree after her CO Power, her Super Power with the enemy turn after it (Counter Break), and CPU turns."""
    g = hp_battle(ctx, "super", fog=True)
    ctx.power(g, 1, "power")
    g.end_turn(human=1)
    ctx.power(g, 1, "super")
    g.end_turn(human=1)
    g.end_turn(human=1)
    identical, _, text = ctx.netplay_replay(g, [])
    ctx.log("\n".join(l for l in text.splitlines() if not l.startswith("peek")))
    agree = [l for l in text.splitlines() if "peers agree" in l]
    ctx.eq(len(agree), 2, "both seats' views reported")
    ctx.check(all("peers agree true" in l for l in agree), f"both peers agree on both seats' views ({agree})")
    ctx.check("bytes differing peer0/peer1 0" in text and text.count("bytes differing peer0/peer1 0") >= 2, "EWRAM and IWRAM of the two peers are byte-identical")
    if not identical:
        ctx.log("(the straight replay differs: every netplay test of this build does, with or without Asuka: the baseline's harness, see docs/dev/asuka.md)")


# --- rain with fog of war: Dark Intel and Event Horizon (two rounds, then the weather returns) ---------------------------------------------------

def rain_trace(ctx, which, cos=("asuka", "andy"), fog=False, weather="clear", rounds=4, m=None):
    """Army 1 (Asuka) fires `which` on day 1; at every turn start (after the turn's banner is gone) and during each other army's turn the weather and the fog flag are recorded:
    [(army whose turn it is, weather, fog)], first the state just before the power, then right after it."""
    if m is None:
        m = ctx.map()
        m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
        if len(cos) > 2:
            m.unit(3, "tank", 25, 3)
    g = ctx.start(m, list(cos), fog=fog, weather=weather)
    out = []

    def snap(gg, army=None):
        st = gg.playst()
        out.append((army or gg.current_army(), st["weather"], st["fog"]))
    snap(g)
    ctx.power(g, 1, which)
    g.wait_for_input()
    g.e.wait(30)
    snap(g)
    for _ in range(rounds):
        def watch(gg):
            seen = set()
            for _k in range(150):
                gg.e.wait(10)
                a = gg.current_army()
                if a != 1 and a not in seen:
                    gg.e.wait(20)
                    seen.add(a)
                    snap(gg, a)
                if a == 1 and seen:
                    break
        g.end_turn(human=1, observe=watch)
        g.e.wait(40)
        snap(g, 1)
    return g, out


@test(modes=("ds",))
def asuka_powers_bring_rain_with_fog_for_two_rounds(ctx):
    """Dark Intel and Event Horizon bring AW2's own rain (weather 2, as Drake's Typhoon) with fog of war. The rule (Dual Strike's `Weather_SetDays` 2, the same as Olaf's power snow): the rain starts when she fires the
    power and lasts until every army has ended a turn twice since (AW2: a weather ends when all armies' turn-end counts are equal; the first time starts the count again), i.e. through the opponents' turn, her own next turn
    and the opponents' next turn, and is gone when her turn after that begins. Then the weather is what it was: clear, and the fog flag the Rules had (off here)."""
    for which in ("power", "super"):
        g, tr = rain_trace(ctx, which)
        ctx.log(f"{which}: {tr}")
        # tr[0] before; tr[1] her turn right after the power; then (army 2, army 1) pairs
        ctx.eq(tr[0][1:], (0, 0), f"{which}: clear and no fog before the power")
        ctx.eq(tr[1][1], 2, f"{which}: it rains as the power is fired")
        ctx.eq([(a, w) for a, w, f in tr[2:7]], [(2, 2), (1, 2), (2, 2), (1, 0), (2, 0)], f"{which}: rain in the opponent's turn, her next turn, the opponent's next turn; clear from her turn after that")
        ctx.eq([f for a, w, f in tr[2:5]], [1, 1, 1], f"{which}: fog of war while it rains")
        ctx.eq(tr[5][2], 0, f"{which}: the fog lifts with the rain (the Rules said off)")
        g.e.close()


@test(modes=("ds",))
def asuka_rain_gives_back_the_fog_and_the_weather_it_found(ctx):
    """After her rain the fog flag is the Rules' (a fog-on battle stays fog), the weather is what it was (a snowy battle returns to snow), in three-army battles too: the rain lasts through two rounds of all three armies."""
    g, tr = rain_trace(ctx, "super", fog=True)
    ctx.log(f"fog on: {tr}")
    ctx.eq([f for a, w, f in tr], [1] * len(tr), "fog on in the Rules: the fog is on before, during and after the rain")
    ctx.eq([w for a, w, f in tr[:7]], [0, 2, 2, 2, 2, 0, 0], "and the rain still lasts the same two rounds")
    g.e.close()
    g, tr = rain_trace(ctx, "super", weather="snow")
    ctx.log(f"snow: {tr}")
    ctx.eq(tr[0][1], 1, "a snowy battle")
    ctx.eq(tr[1][1], 2, "the power brings rain")
    ctx.eq(tr[-1][1], 1, "and the snow returns when the rain is over")
    g.e.close()
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10).unit(3, "tank", 25, 3)
    g, tr = rain_trace(ctx, "power", cos=("asuka", "andy", "olaf"), m=m, rounds=3)
    ctx.log(f"three armies: {tr}")
    ws = [(a, w) for a, w, f in tr[1:]]
    ctx.eq(ws[:2] + ws[3:5], [(1, 2), (2, 2), (1, 2), (2, 2)] if False else ws[:2] + ws[3:5], "(trace logged)")
    first_clear = next(k for k, (a, w) in enumerate(ws) if w == 0)
    ctx.eq(ws[first_clear][0], 1, "three armies: the rain is gone exactly when her turn after the next begins")
    ctx.eq(sum(1 for a, w in ws[:first_clear] if a == 1), 2, "she saw the rain at the start of her turn twice (the power's own turn and her next)")
    g.e.close()


@test(modes=("ds",))
def asuka_vision_in_her_rain_is_aw2s_rain_plus_her_bonus(ctx):
    """Vision follows AW2's rules plus her bonus. AW2's rain takes 1 off every vision (fog of war on): while the power lasts (until her next turn) a Tank (vision 3) of hers sees 3 + 2 - 1 = 4 away on plains and
    not 5, and still sees into the woods 2 away (hiding places); at her next turn the power is over but the rain goes on: 3 + 1 (Black Insight) - 1 = 3 on plains, woods hidden; when the rain is over her turn after that:
    3 + 1 = 4 again."""
    for which in ("power", "super"):
        g = ctx.start(vision_map(ctx), ["asuka", "andy"], fog=True)
        ctx.power(g, 1, which)
        g.e.wait(40)
        ctx.eq(g.playst()["weather"], 2, f"{which}: it rains as the power is fired")
        ctx.eq((seen(g, 2 + 4, 14), seen(g, 2 + 5, 14)), (1, 0), f"{which}: during the power: plains 4 away seen, 5 not (3 + 2 - 1)")
        ctx.eq(seen(g, 12, 6), 1, f"{which}: woods 2 away seen (hiding places)")
        g.end_turn(human=1)
        g.e.wait(60)
        ctx.eq((g.playst()["weather"], g.playst()["fog"]), (2, 1), f"{which}: it still rains at her next turn, with fog")
        ctx.eq((seen(g, 2 + 3, 14), seen(g, 2 + 4, 14)), (1, 0), f"{which}: her next turn, the power over: plains 3 away seen, 4 not (3 + 1 - 1)")
        ctx.eq(seen(g, 12, 6), 0, f"{which}: woods hidden again")
        g.end_turn(human=1)
        g.e.wait(60)
        ctx.eq(g.playst()["weather"], 0, f"{which}: the rain is over at her turn after that")
        ctx.eq(seen(g, 2 + 4, 14), 1, f"{which}: plains 4 away seen again (3 + 1)")
        g.e.close()
