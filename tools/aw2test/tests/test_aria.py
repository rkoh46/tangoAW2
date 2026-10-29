"""Aria (CO 93, crate::aria): Nell's sister, an Orange Star CO with only a Super Power (docs/dev/aria.md). The numbers every CO has (attack, defence, move, heal, meter, Tag Power) are played by
`aw2dev co verify aria` (tests/test_co_verify.py) against `cos/aria.toml`; this file proves the rest with numbers from the game:
    - the CO table's row: 0 stars for the CO Power, 7 for the Super Power, the game's own luck, Orange Star's style and colour bytes, her texts and quote slots;
    - Vengeance: a unit on 8 HP or less (displayed) attacks and defends harder by its HP (+25% at 8, 6% more per HP lost to +61% at 2, +85% at 1; never an Oozium), 9 and 10 HP do not, in every power level, as attacker,
      as counterattacker and as defender, checked against the calculator's ranges;
    - no CO Power: the map menu never offers "Power" and offers "Super" at 7 stars, the CPU plays her with a Super Power only;
    - Build Anew heals 3 HP, adds 20% firepower and nothing else (no move, no funds);
    - the Orange Star HQ is drawn for her."""

from aw2test import damage
from aw2test import rom as romlib
from aw2test.game import power_star_cost
from aw2test.harness import test

ARIA = 93
TEXT_TABLE = 0x08610A38
TEXT_BASE = 0x6D72


def row_addr(g, co=ARIA):
    return g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * co


def mode_word(g, mode, off, size=2):
    a = row_addr(g) + 0x38 + 0x44 * mode + off
    return int.from_bytes(g.e.read(a, size), "little", signed=size == 2 and off in (0x0C, 0x0E, 0x10, 0x12, 0x14, 0x16))


def text_of(g, which):
    at = g.e.u32(TEXT_TABLE + 4 * (TEXT_BASE + 16 * 21 + which))
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


@test(modes=("ds",))
def aria_row_has_only_a_super_power_and_the_games_luck(ctx):
    """The CO table's row 93: 0 stars for the CO Power, 7 in all for the Super Power; luck 20 and no bad luck in every level; Orange Star's style and colour bytes (Nell's); her own texts."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, ["aria", "andy"])
    ctx.eq(g.co_stars(ARIA), (0, 7), "stars: no CO Power, a Super Power of 7")
    ctx.eq(g.co_stars(romlib.co_id("sturm")), (0, 10), "(Sturm's own 0 / 10: the precedent)")
    andy = g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * romlib.co_id("cloneandy")
    ctx.eq([mode_word(g, k, 0x0E) for k in range(3)], [g.e.u16(andy + 0x38 + 0x44 * k + 0x0E) for k in range(3)], "luck is the game's own (Clone Andy's Dual Strike row, 10): no luck trait")
    ctx.eq([mode_word(g, k, 0x10) for k in range(3)], [0, 0, 0], "no bad luck")
    nell = g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * romlib.co_id("nell")
    ctx.eq(g.e.read(row_addr(g) + 0x14, 3), g.e.read(nell + 0x14, 3), "her row's property / unit style and army colour bytes are Nell's (Orange Star's)")
    sturm = g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * romlib.co_id("sturm")
    ctx.eq(g.e.read(row_addr(g) + 0x17, 2), g.e.read(sturm + 0x17, 2), "the CPU's power settings are Sturm's (a CO with no CO Power)")
    ctx.eq(text_of(g, 0), b"Aria", "name")
    ctx.eq(text_of(g, 6), b"Build Anew", "Super Power name")
    ctx.check(b"no CO Power" in text_of(g, 3), f"the CO Power page says she has none ({text_of(g, 3)!r})")
    ctx.check(text_of(g, 4).replace(b"\r", b" ").startswith(b"Restores 3 HP to all units"), "the Super Power page")
    quotes = [text_of(g, 7 + q) for q in range(6)]
    ctx.check(quotes[1].startswith(b"BUILD ANEW") and quotes[2].startswith(b"Stand with me") and quotes[3:] == quotes[:3], f"quote slots: Super Power's line in both power slots, tag-in third ({quotes[:3]})")
    ctx.eq(g.player(1)["co"], ARIA, "army 1 plays her")


@test(modes=("ds",))
def aria_has_no_power_entry_and_the_super_power_costs_seven_stars(ctx):
    """The map menu never offers "Power" for her (no CO Power: 0 stars), whatever the meter holds; "Super" appears at exactly 7 stars x 9000 and not one point less, and after one power the next costs 20% more."""
    from aw2test.game import power_star_cost
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, ["aria", "andy"])
    addr = g.player(1)["addr"] + 0x20
    for uses in (0, 1):
        full = power_star_cost(uses) * 7
        for charge, want in ((0, False), (full // 2, False), (full - 1, False), (full, True), (full * 2, True)):
            g.e.w32(addr, charge)
            g.e.wait(4)
            names = g.map_menu_names()
            ctx.check("Power" not in names, f"uses {uses}, meter {charge}: no Power entry ({names})")
            ctx.eq("Super" in names, want, f"uses {uses}, meter {charge} of {full}: Super offered")
        if uses == 0:
            ctx.power(g, 1, "super")
            g.end_turn(human=1)
            g.e.w32(addr, 0)


@test(modes=("ds",))
def aria_cpu_uses_only_her_super_power(ctx):
    """A CPU Aria (Von Bolt's profile, `ds_ai::template_of`) with the meter at the Super Power's price uses it on her turn: the mode turns on, her hurt units heal 3 HP, a day's income is paid at
    once, the meter is spent and the turn comes back to the human; with a meter below it she never uses a power."""
    from aw2test.coverify import ENV
    m = ctx.map()
    m.unit(1, "tank", 3, 3).unit(2, "tank", 20, 10).unit(2, "infantry", 22, 12)
    m.terrain(25, 5, "city", 2)
    g = ctx.start(m, ["andy", "aria"], env=ENV)
    ctx.set_hp(g, 22, 12, 40)
    seen = []
    g.charge_power(2, "super")

    def watch(gg):
        gg.e.wait_until(lambda: gg.player(2)["co_mode"] > 0 or gg.current_army() != 2, 6000, step=10)
        seen.append(gg.player(2)["co_mode"])
    g.end_turn(human=1, observe=watch)
    ctx.eq(seen, [2], "the CPU used her Super Power on her turn")
    ctx.eq(g.player(2)["powers_used"], 1, "one power used")
    inf = [u["hp"] for u in g.units(2) if u["type"] == 1]
    ctx.check(inf and inf[0] >= 70, f"her hurt Infantry was healed 3 HP by it (40 -> {inf})")
    ctx.eq(g.current_army(), 1, "the turn came back to the human")


@test(modes=("ds",))
def aria_vengeance_scales_with_hp(ctx):
    """Vengeance: Aria's Tanks at 100, 90, 81 internal HP (10, 9, 9 displayed: nothing) and 80, 71, 60, 50, 40, 30, 20, 10 (8 down to 1) each hit an Infantry; every loss is inside the calculator's range
    (`Ctx.side` adds damage.aria_vengeance), and 9 HP gets no boost while 8 does. The same at the Super Power level (Build Anew's 20% on top) and as the counterattacker of Andy's hit."""
    from aw2test import coverify as cv
    for mode in (0, 2):
        m = ctx.map()
        hps = [100, 90, 81, 80, 71, 60, 50, 40, 30, 20, 10]
        for k, _ in enumerate(hps):
            m.unit(1, "tank", 2 + 2 * k, 10).unit(2, "infantry", 2 + 2 * k, 11)
        g = ctx.start(m, ["aria", "andy"], env=cv.ENV)
        if mode:
            ctx.power(g, 1, "super")
        ranges = {}
        for k, hp in enumerate(hps):
            x = 2 + 2 * k
            ctx.set_hp(g, x, 10, hp)
            a, d = g.unit_at(x, 10), g.unit_at(x, 11)
            out = damage.strike(ctx.rules, ctx.side(g, a, terrain=g.terrain_class(x, 10)), ctx.side(g, d), 1, True, a["hp"])
            before = hp_of(g, x, 11)
            g.attack((x, 10), (x, 10), (x, 11))
            loss = before - hp_of(g, x, 11)
            ranges[hp] = sorted(out.losses)
            ctx.check(loss in out.losses, f"mode {mode}, Tank at {hp} HP: loss {loss} inside the calculator's {sorted(out.losses)}")
        # 9 displayed HP (81, 90) has no Vengeance and 8 (80) does: the calculator's range at 80 HP has 25% more per bar
        ctx.check(max(ranges[80]) * 9 > max(ranges[81]) * 8, "Vengeance shows: 80 HP hits harder per bar than 81")
        ctx.eq([damage.aria_vengeance(h) for h in hps], [0, 0, 0, 25, 25, 37, 43, 49, 55, 61, 85], "the calculator's table: nothing at 9 and 10 HP")
        g.e.close()
    # the counterattack: Andy's Infantry hits Aria's Tank (at 100, 80 and 86 internal HP) and she counters; the counter is worked out from the HP the hit left (the unit record's), Vengeance included:
    # a Tank hit from 86 (9 displayed) down to 8 displayed counters with +25%
    for hp in (100, 80, 86):
        m = ctx.map()
        m.unit(1, "tank", 10, 10).unit(2, "infantry", 11, 10)
        g = ctx.start(m, ["aria", "andy"], humans=(1, 2), env=cv.ENV)
        ctx.set_hp(g, 10, 10, hp)
        g.end_turn(human=2)
        inf_before = ctx.side(g, g.unit_at(11, 10))      # (the Infantry as it stands when the counter hits it: its terrain defence scales with its HP)
        g.select(11, 10)
        g.move_to(11, 10)
        g.choose("Fire", g.ACTION_MENU)
        g.pick_target(10, 10)
        g.wait_for_input()
        after_att, after_dfd = g.unit_at(11, 10), g.unit_at(10, 10)
        if not after_att or not after_dfd:
            ctx.log(f"hp {hp}: a unit was destroyed")
            continue
        start_att = 100
        counter = damage.strike(ctx.rules, ctx.side(g, after_dfd), inf_before, 1, False, after_dfd["hp"])
        got = start_att - after_att["hp"]
        ctx.log(f"Aria's Tank {hp} -> {after_dfd['hp']} HP after the hit; her counter cost the Infantry {got}; calculator {sorted(counter.losses)}")
        ctx.check(got in counter.losses, f"Aria's Tank {hp} -> {after_dfd['hp']} HP counterattacks with the HP the hit left: loss {got} inside {sorted(counter.losses)}")
        g.e.close()


@test(modes=("ds",))
def aria_vengeance_defends_too(ctx):
    """Vengeance defends: Andy's Tanks hit Aria's Tanks at 100, 90 (no boost) and 80, 60, 40, 20 internal HP (+25, +37, +49, +61% defence); every loss is inside the calculator's range, the defence
    included (`Ctx.side`'s temp defence, AW2's cap at 200), and a 9 HP Tank of hers takes the plain hit."""
    from aw2test import coverify as cv
    m = ctx.map()
    hps = [100, 90, 80, 60, 40, 20]
    for k, _ in enumerate(hps):
        m.unit(1, "tank", 3 + 3 * k, 10).unit(2, "tank", 3 + 3 * k, 11)
    g = ctx.start(m, ["aria", "andy"], humans=(1, 2), env=cv.ENV)
    for k, hp in enumerate(hps):
        ctx.set_hp(g, 3 + 3 * k, 10, hp)
    g.end_turn(human=2)
    for k, hp in enumerate(hps):
        x = 3 + 3 * k
        a, d = g.unit_at(x, 11), g.unit_at(x, 10)
        out = damage.strike(ctx.rules, ctx.side(g, a), ctx.side(g, d, terrain=g.terrain_class(x, 10)), 1, True, a["hp"])
        g.attack((x, 11), (x, 11), (x, 10))
        after = g.unit_at(x, 10)
        loss = hp - (after["hp"] if after else 0)
        ctx.check(loss in out.losses, f"Aria's Tank at {hp} HP (Vengeance {damage.aria_vengeance(hp)}% defence): loss {loss} inside the calculator's {sorted(out.losses)}")
    g.e.close()


@test(modes=("ds",))
def aria_build_anew_adds_firepower_and_heals_and_nothing_else(ctx):
    """Build Anew: every unit recovers 3 HP, nothing is paid (funds unchanged), nobody moves farther (a Tank's reach is its base move), and her defence is the power's own +10% only."""
    from aw2test import coverify as cv
    from tests.test_tag import can_move
    m = ctx.map()
    for x in range(4, 14):
        m.terrain(x, 10, "road")
    m.unit(1, "tank", 4, 10).unit(1, "infantry", 3, 3).unit(2, "tank", 25, 15)
    g = ctx.start(m, ["aria", "andy"], env=cv.ENV)
    ctx.set_hp(g, 3, 3, 45)
    cv.set_funds(g, 10000)
    g.charge_power(1, "super")
    f0 = cv.funds(g)
    g.power("super")
    ctx.eq(g.unit_at(3, 3)["hp"], 80, "the Infantry 45 (5 HP) -> 80 (3 HP healed)")
    ctx.eq(cv.funds(g), f0, "no funds paid")
    ctx.eq((can_move(g, (4, 10), (10, 10)), can_move(g, (4, 10), (11, 10))), (True, False), "a Tank (move 6) still reaches 6 cells and not 7: no extra move")
    ctx.eq(g.player(1)["temp_defence"], 10, "defence: the power's own +10% only")
