"""Aria (CO 93, crate::aria): Nell's sister, an Orange Star CO with only a Super Power (docs/dev/aria.md). The numbers every CO has (attack, defence, move, heal, funds, meter, Tag Power) are played by
`aw2dev co verify aria` (tests/test_co_verify.py) against `cos/aria.toml`; this file proves the rest with numbers from the game:
    - the CO table's row: 0 stars for the CO Power, 7 for the Super Power, luck 20 and no bad luck in every level, Orange Star's style and colour bytes, her texts and quote slots;
    - Common Cause's luck (Nell's, 0..19%, no bad luck) and movement (Sturm's: every terrain costs 1), as Asuka's;
    - no CO Power: the map menu never offers "Power" and offers "Super" at 7 stars, the CPU plays her with a Super Power only;
    - Build Anew's funds are exactly one day's income, once, and follow the Funds rule;
    - the Orange Star HQ is drawn for her, and netplay agrees."""

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
def aria_row_has_only_a_super_power_and_nells_luck(ctx):
    """The CO table's row 93: 0 stars for the CO Power, 7 in all for the Super Power; luck 20 and no bad luck in every level; Orange Star's style and colour bytes (Nell's); her own texts."""
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, ["aria", "andy"])
    ctx.eq(g.co_stars(ARIA), (0, 7), "stars: no CO Power, a Super Power of 7")
    ctx.eq(g.co_stars(romlib.co_id("sturm")), (0, 10), "(Sturm's own 0 / 10: the precedent)")
    ctx.eq([mode_word(g, k, 0x0E) for k in range(3)], [20, 20, 20], "luck 20 (0..19%) in every level: Nell's day to day")
    ctx.eq([mode_word(g, k, 0x10) for k in range(3)], [0, 0, 0], "no bad luck")
    nell = g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * romlib.co_id("nell")
    ctx.eq(g.e.read(row_addr(g) + 0x14, 3), g.e.read(nell + 0x14, 3), "her row's property / unit style and army colour bytes are Nell's (Orange Star's)")
    sturm = g.e.u32(g.CO_TABLE_POOL) + romlib.CO_RECORD * romlib.co_id("sturm")
    ctx.eq(g.e.read(row_addr(g) + 0x17, 2), g.e.read(sturm + 0x17, 2), "the CPU's power settings are Sturm's (a CO with no CO Power)")
    ctx.eq(text_of(g, 0), b"Aria", "name")
    ctx.eq(text_of(g, 6), b"Build Anew", "Super Power name")
    ctx.check(b"no CO Power" in text_of(g, 3), f"the CO Power page says she has none ({text_of(g, 3)!r})")
    ctx.check(text_of(g, 4).replace(b"\r", b" ").startswith(b"All my units recover 3 HP"), "the Super Power page")
    quotes = [text_of(g, 7 + q) for q in range(6)]
    ctx.check(quotes[1].startswith(b"BUILD ANEW") and quotes[2].startswith(b"Stand with me") and quotes[3:] == quotes[:3], f"quote slots: Super Power's line in both power slots, tag-in third ({quotes[:3]})")
    ctx.eq(g.player(1)["co"], ARIA, "army 1 plays her")


@test(modes=("ds",))
def aria_luck_is_nells_and_there_is_no_bad_luck(ctx):
    """Common Cause's luck, as Asuka's: each hit rolls 0..19%, no bad luck. Ten Tank hits on ten Infantry: every loss inside the calculator's range for luck (20, 0), none under its lower end, some
    above what luck 10 reaches."""
    m = ctx.map()
    for k in range(10):
        m.unit(1, "tank", 3 + 2 * k, 10).unit(2, "infantry", 3 + 2 * k, 11)
    g = ctx.start(m, ["aria", "andy"])
    a, d = g.unit_at(3, 10), g.unit_at(3, 11)
    out = damage.strike(ctx.rules, ctx.side(g, a, terrain=g.terrain_class(3, 10)), ctx.side(g, d), 1, True, a["hp"])
    ctx.eq(out.luck, (20, 0), "the calculator's luck for Aria")
    allowed = sorted(out.losses)
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
def aria_ground_units_pay_one_movement_point_for_every_terrain(ctx):
    """Common Cause's movement is Sturm's, as Asuka's: a Tank (move 6) of Aria's crosses woods at 1 a cell and reaches 6 cells away over woods where Andy's falls short; her Infantry crosses three mountains
    (3 points); the same as Sturm's in clear, rain and snow."""
    from tests.test_tag import can_move
    for weather in ("clear", "rain", "snow"):
        res = {}
        for co in ("aria", "sturm", "andy"):
            m = ctx.map()
            for x in (6, 7, 8):
                m.terrain(x, 10, "wood")
                m.terrain(x, 12, "mountain")
            m.unit(1, "tank", 5, 10).unit(1, "infantry", 5, 12).unit(2, "tank", 25, 3)
            g = ctx.start(m, [co, "olaf"], weather=weather)
            res[co] = (can_move(g, (5, 10), (11, 10)), can_move(g, (5, 12), (8, 12)), can_move(g, (5, 10), (12, 10)))
        ctx.log(f"{weather}: {res}")
        ctx.eq(res["aria"], (True, True, False), f"{weather}: Aria's Tank covers its full move of 6 over woods, her Infantry crosses three mountains, and 7 is too far")
        ctx.eq(res["aria"], res["sturm"], f"{weather}: the same as Sturm's")
        ctx.eq(res["andy"][:2], (False, False), f"{weather}: Andy's units do not")


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
def aria_super_power_pays_exactly_one_days_income_once(ctx):
    """Build Anew's funds are one day's income, the Funds rule's value x the properties that earn, once: 1000 and 2000 a property, 7 properties; the day's income is paid as usual after it; the CO table's
    other levels pay nothing."""
    from aw2test import coverify as cv
    for fpp in (1000, 2000):
        g = ctx.start(cv.econ_map(ctx), ["aria", "andy"], env=cv.ENV, funds=None if fpp == 1000 else cv.FUNDS_RULE[fpp])
        props = ctx.properties(g, 1)
        ctx.eq(props, 7, "earning properties")
        cv.set_funds(g, 10000)
        f0 = cv.funds(g)
        g.charge_power(1, "super")
        f1 = cv.funds(g)
        g.power("super")
        got = cv.funds(g) - f0
        ctx.eq(got, fpp * props, f"{fpp} a property: funds collected = one day's income ({props} x {fpp})")
        f2 = cv.funds(g)
        g.end_turn(human=1)
        ctx.eq(cv.funds(g) - f2, fpp * props, "the day's own income is paid as usual afterwards (one more day, not two)")
        g.e.close()
