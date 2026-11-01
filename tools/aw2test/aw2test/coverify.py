"""Scenarios of `aw2dev co verify`: real Versus battles in which a custom CO's day to day, CO Power, Super Power and Tag Power are played and every number the game produced is
compared with the CO's SPECIFICATION (`aw2test.cospec`: the data files and the design docs), not with the engine's own tables.

Every check is tagged `[<co> <ability>] ...` in the test's log; `aw2dev co verify` collects the tags into the pass / fail table.
Abilities: `d2d`, `cop`, `scop` (stats, rules, heal, funds), `meter` (star costs, the exact meter threshold), `tag` (the Tag Powers), `cpu`, `net`.
"""

from . import cospec, damage
from . import rom as romlib
from .game import NavError

ENV = {}   # (Tabitha, Lili and Caulder are in Versus always; the retired slots 89 and 90 are in no list)
LEVEL = {0: "d2d", 1: "cop", 2: "scop"}
POWER = {1: "power", 2: "super"}


def tag(co, mode):
    return f"{co} {LEVEL[mode]}"


def chk(ctx, label, cond, msg, detail=""):
    """A tagged check: `[<co> <ability>] <detail>: <msg>` (the table of `aw2dev co verify` groups by the tag)."""
    return ctx.check(cond, f"[{label}] {detail + ': ' if detail else ''}{msg}")


class SpecRules(damage.Rules):
    """The damage calculator with the custom COs' numbers taken from their specification instead of the engine's mirror (`damage.es_bonus`)."""

    def __init__(self, base):
        super().__init__(base.image, base.chart, base.name)
        self.by_id = {s.id: s for s in cospec.all_specs().values()}

    def co_bonus(self, co, mode, unit_type, which):
        s = self.by_id.get(co)
        if s is not None and self.chart is not None and unit_type != damage.OOZIUM and s.covers(unit_type):
            return s.bonus(min(mode, 2), unit_type, which)
        return super().co_bonus(co, mode, unit_type, which)

    def co_mode(self, co, mode):
        m = super().co_mode(co, mode)
        s = self.by_id.get(co)
        if s is not None and self.chart is not None:
            m = dict(m)
            m["luck"], m["neg_luck"] = s.luck[min(mode, 2)], 0
        return m


def use_spec(ctx):
    if not isinstance(ctx.rules, SpecRules):
        ctx.rules = SpecRules(ctx.rules)
    return ctx.rules


# --- units ------------------------------------------------------------------------------------------------------------------------------

# AW2's own nineteen units (the unit table of the AW2 ROM has stats for these; the pack's Dual Strike units - Megatank, Piperunner, Stealth, Black Boat, Carrier, Black Bomb - are
# not in it, so the spec calculator cannot know their move or range: `aw2dev co verify` lists them as not covered).
ARMED = [1, 2, 3, 5, 6, 8, 10, 11, 14, 15, 16, 17, 19, 21, 22, 24]
UNARMED = [7, 20, 23]
INFO_ONLY = []
NAV = cospec.NAVAL
AIR = {12, 13, 16, 17, 19, 20}
TARGETS = [5, 3, 8, 2, 1, 6, 14, 10, 11, 19, 17, 22, 21, 23, 24, 16]


def name_of(t):
    return romlib.UNIT_NAMES[t]


def usable(rules, a, d, dist):
    """The chart damage unit `a` can do to unit type `d` at distance `dist` (the game picks the better weapon at 1, the primary beyond)."""
    u = rules.unit(a)
    best = 0
    if dist == 1:
        best = rules.raw(a, d, 1)
        if u["min_range"] == 1:
            best = max(best, rules.raw(a, d, 0))
    elif u["min_range"] <= dist <= u["max_range"]:
        best = rules.raw(a, d, 0)
    return best


def pick_target(rules, a, dist):
    cands = [d for d in TARGETS if d != a]
    for d in cands:
        v = usable(rules, a, d, dist)
        if 22 <= v <= 70:
            return d
    for d in cands:
        if usable(rules, a, d, dist) > 0:
            return d
    return None


def pick_hitter(rules, a):
    """An Andy aircraft that can hit unit type `a` (to measure a's defence on Andy's turn)."""
    for h in ((16,) if a in AIR else (17,)):
        if rules.raw(h, a, 0) > 0 or rules.raw(h, a, 1) > 0:
            return h
    return None


SLOTS = [(x, y) for y in range(1, 18, 2) for x in (5, 13, 21)]


def fight_map(ctx, types, rules):
    """A plains map with, in each slot, the CO's unit at (x, y), Andy's target `dist` cells east and a weak Andy aircraft west of it. Returns (map, plan)."""
    m = ctx.map()
    plan = []
    for (x, y), a in zip(SLOTS, types):
        u = rules.unit(a)
        dist = max(1, u["min_range"])
        d = pick_target(rules, a, dist) if a in ARMED + INFO_ONLY else None
        h = pick_hitter(rules, a)
        naval = a in NAV
        for k in range(-1, dist + 1):
            if naval and k < dist:
                m.terrain(x + k, y, "sea")
        if d is not None and d in NAV:
            m.terrain(x + dist, y, "sea")
        m.unit(1, a, x, y)
        if d is not None:
            m.unit(2, d, x + dist, y)
        if h is not None:
            m.unit(2, h, x - 1, y)
        plan.append({"type": a, "at": (x, y), "dist": dist, "target": d, "hitter": h})
    return m, plan


def fight(ctx, label, detail, g, src, dst, target, keep=100):
    """ctx.attack with the spec calculator, wrapped: tagged, and the game's total defence checked against the calculator's (ctx.attack does not)."""
    i0 = len(ctx.log_lines)
    r = ctx.attack(g, src, dst, target, counter_keep=keep)
    new = ctx.log_lines[i0:]
    bad = [l for l in new if l.startswith("FAIL")]
    ra, rd = r["records"]
    first = r["first"]
    chk(ctx, label, not bad, f"base damage {ra['base']} (calculator {first.base}), HP loss, counter, forecast and meters match" + ("" if not bad else " -- " + bad[0][6:150]), detail)
    chk(ctx, label, rd["defence"] == first.defence, f"target's total defence {rd['defence']} (specification {first.defence})", detail)
    if getattr(ctx, "rows", None) is not None:
        ctx.rows.append({"detail": detail, "base": ra["base"], "defence": rd["defence"], "own_defence": ra["defence"], "weapon": ra["attack_type"]})
    return r


def stat_fights(ctx, name, mode, defence_leg=True):
    """Every unit class of `name` at power level `mode` attacks an Andy unit (army 1's turn: firepower, luck, counter, meter against the specification's calculator), then Andy's
    aircraft hit them on Andy's turn (defence: the power of army 1 still stands). Returns (game, plan)."""
    rules = use_spec(ctx)
    spec = cospec.get(name)
    types = ARMED + UNARMED + INFO_ONLY
    m, plan = fight_map(ctx, types, rules)
    g = ctx.start(m, [spec.id, "andy"], humans=(1, 2), env=ENV)
    label = tag(name, mode)
    if mode:
        ctx.power(g, 1, POWER[mode])
        chk(ctx, label, g.player(1)["co_mode"] == mode, f"the {LEVEL[mode].upper()} is on (power mode {g.player(1)['co_mode']})")
    keep = 100
    for p in plan:
        a, (x, y), dist, d = p["type"], p["at"], p["dist"], p["target"]
        if d is None:
            continue
        lab = f"{name} info" if not spec.covers(a) else label
        fight(ctx, lab, f"{name_of(a)} attacks {name_of(d)}", g, (x, y), (x, y), (x + dist, y), keep)
    if defence_leg:
        g.end_turn(human=2)
        for u in g.units(1):
            ctx.set_hp(g, u["x"], u["y"], 100)      # (the earlier fights' luck must not decide the terrain term of the defence)
        for p in plan:
            a, (x, y), h = p["type"], p["at"], p["hitter"]
            if h is None:
                continue
            ctx.set_hp(g, x - 1, y, 30)
            lab = f"{name} info" if not spec.covers(a) else label
            fight(ctx, lab, f"{name_of(a)} defends against {name_of(h)}", g, (x - 1, y), (x - 1, y), (x, y))
    return g, plan


# --- move and range ---------------------------------------------------------------------------------------------------------------------

MOVERS = [1, 2, 3, 5, 6, 7, 8, 14, 10, 11, 15, 19, 16, 17, 20, 21, 22, 23, 24]


def probe_move(g, src, dst):
    from tests.test_crumb import can_move
    return can_move(g, src, dst)


def move_range_moves(ctx, name, mode):
    """One unit of each of AW2's nineteen types on its own lane of road (sea for the ships), start x = 3: the unit reaches exactly base move + the specification's move bonus and
    not one cell more (the action menu opens at that cell; at the next one the cell is out of the movement range)."""
    rules = use_spec(ctx)
    spec = cospec.get(name)
    m = ctx.map()
    lanes = {}
    for k, t in enumerate(MOVERS):
        y = 1 + k
        lanes[t] = y
        for x in range(3, 28):
            m.terrain(x, y, "sea" if t in NAV else "road")
        m.unit(1, t, 3, y)
    g = ctx.start(m, [spec.id, "andy"], env=ENV)
    label = tag(name, mode)
    if mode:
        ctx.power(g, 1, POWER[mode])
    rows = []
    for t in MOVERS:
        y = lanes[t]
        base = rules.unit(t)["move"]
        want = base + (spec.bonus(mode, t, 2) if spec.covers(t) else 0)
        ok1 = probe_move(g, (3, y), (3 + want, y))
        ok2 = probe_move(g, (3, y), (3 + want + 1, y))
        rows.append((t, base, want, ok1, ok2))
        chk(ctx, label, ok1 and not ok2, f"moves exactly {want} (base {base}{'' if want == base else f' {want - base:+d}'}): reaches +{want} {ok1}, reaches +{want + 1} {ok2}", name_of(t))
    return g


def move_range_range(ctx, name, mode, beyond):
    """Indirect units (Artillery, Rockets, Missiles, Battleship) and a Tank (the control) each with one Andy Infantry at distance max range + the specification's range bonus
    (`beyond` 0: Fire is offered; Missiles get a B Copter) or one more (`beyond` 1: it is not). Rows are far enough apart that no other row's Infantry is in range (checked)."""
    rules = use_spec(ctx)
    spec = cospec.get(name)
    types = [10, 11, 15, 21, 5]
    m = ctx.map()
    plan = []
    for k, t in enumerate(types):
        y = 2 + 4 * k if t != 5 else 2
        x0 = 3 if t != 5 else 20          # (the Tank control stands far from the others' rows)
        u = rules.unit(t)
        dmax = u["max_range"] + spec.bonus(mode, t, 3)
        d = dmax + beyond
        for x in range(x0, x0 + d + 1):
            if t in NAV:
                m.terrain(x, y, "sea")
        e = 19 if t == 15 else 1            # (Missiles hit aircraft only)
        m.unit(1, t, x0, y).unit(2, e, x0 + d, y)
        plan.append((t, y, dmax, d, x0))
    for t, y, dmax, d, x0 in plan:
        for t2, y2, _, d2, x2 in plan:
            if t2 != t:
                assert abs(y - y2) + abs(x0 - (x2 + d2)) > dmax, f"layout: {name_of(t)} would reach {name_of(t2)}'s Infantry"
    g = ctx.start(m, [spec.id, "andy"], env=ENV)
    label = tag(name, mode)
    if mode:
        ctx.power(g, 1, POWER[mode])
    for t, y, dmax, d, x0 in plan:
        names = g.action_menu_at(x0, y)
        fire = any(n.lower().startswith("fire") and "(greyed)" not in n for n in names)
        chk(ctx, label, fire == (beyond == 0), f"max range {dmax} (base {rules.unit(t)['max_range']}, bonus {spec.bonus(mode, t, 3):+d}): enemy at distance {d} -> Fire {'offered' if fire else 'not offered'} ({'expected' if fire == (beyond == 0) else 'WRONG'})", name_of(t))
    return g


# --- economy: unit cost, income, funds from powers, healing --------------------------------------------------------------------------------

def econ_map(ctx):
    m = ctx.map()
    for x in (5, 7, 9):
        m.terrain(x, 5, "city", 1)
    m.terrain(11, 5, "base", 1).terrain(11, 7, "base", 1).terrain(13, 5, "airport", 1)
    m.terrain(15, 5, "city", 0).terrain(20, 5, "city", 2)
    m.unit(1, "infantry", 3, 3).unit(1, "tank", 4, 3).unit(2, "infantry", 24, 12)
    return m


def funds(g):
    return g.e.u32(g.player(1)["addr"])


def set_funds(g, v):
    g.e.w32(g.player(1)["addr"], v)


FUNDS_RULE = {1000: 0, 2000: 2}      # the Rules screen's Funds item (0..17), value -> funds per property (read back from the game); 0 is the default 1000


def economy(ctx, name, fpp=1000):
    """Unit cost (an Infantry and a Tank bought on two bases), the day's income (CPU turn), then CO Power and Super Power in turn: the funds they collect, the units they heal."""
    from tests.test_crumb import set_unit
    rules = use_spec(ctx)
    spec = cospec.get(name)
    g = ctx.start(econ_map(ctx), [spec.id, "andy"], env=ENV, funds=None if fpp == 1000 else FUNDS_RULE[fpp])
    ctx.eq(g.e.u32(ramaddr("FUNDS_PER_PROPERTY")), fpp, "the Funds rule is")
    mine = lambda: [u for u in g.units(1)]
    props = ctx.properties(g, 1)
    chk(ctx, f"{name} d2d", props == 7, f"the test map gives the army {props} earning properties (HQ, 3 cities, 2 bases, an airport)", "setup")
    set_funds(g, 50000)
    cost_pct = spec.cost_percent()
    for (bx, by), t in (((11, 5), 1), ((11, 7), 5)):
        f0 = funds(g)
        g.buy(bx, by, t)
        paid = f0 - funds(g)
        want = rules.image.unit(t)["cost"] * (100 + cost_pct) // 100
        chk(ctx, f"{name} d2d", paid == want, f"a {name_of(t)} costs {paid} (base {rules.image.unit(t)['cost']}, {cost_pct:+d}% -> {want})", "unit cost")
    for u in g.units(1):
        set_unit(g, u["x"], u["y"], hp=45)
    for u in g.units(2):
        set_unit(g, u["x"], u["y"], hp=45)
    for mode in spec.levels_played[1:]:
        label = tag(name, mode)
        before = {u["id"]: u for u in g.units()}
        f0 = funds(g)
        cost = g.charge_power(1, POWER[mode])
        g.power(POWER[mode])
        after = {u["id"]: u for u in g.units()}
        got = funds(g) - f0
        want = spec.funds(mode, props, fpp)
        chk(ctx, label, got == want, f"funds collected {got} (specification {spec.tribute[mode]} x {props} properties" + (f" + one day's income {fpp} x {props}" if spec.income_grant and mode == 2 else "") + f" = {want})", "power funds")
        ctx.expect_hp_change(before, after, {1: spec.heal[mode] * 10}, f"{label}: heal {spec.heal[mode]} HP", repair=True)
        mine_ok = all(after[i]["hp"] <= before[i]["hp"] and (after[i]["hp"] == before[i]["hp"] or cospec.strike(name)) for i in before if before[i]["army"] == 2)
        chk(ctx, label, mine_ok, "the enemy's units are not healed (a strike's damage is the Firestorm's, not a heal)", "heal")
        chk(ctx, label, g.player(1)["co_mode"] == mode, "power on")
        # The day's income when the turn passes (the power ends at the army's next turn).
        for u in g.units(1):
            set_unit(g, u["x"], u["y"], hp=100)      # (a hurt unit on a property is repaired for money: not part of the income)
        f1 = funds(g)
        g.end_turn(human=1)
        got = funds(g) - f1
        want = props * fpp * (100 + spec.income) // 100
        chk(ctx, tag(name, 0), got == want, f"income {got} (specification {props} properties x {fpp} x {100 + spec.income}% = {want})", "income")
        if mode == 1:
            for u in g.units(1):
                set_unit(g, u["x"], u["y"], hp=45)
    return g


def ramaddr(name):
    from . import ram
    return getattr(ram, name)


# --- the power meter: star costs and the exact threshold ------------------------------------------------------------------------------------------

def meter(ctx, name):
    """The CO table's stars equal the specification's; the map menu offers the CO Power at exactly stars x 9000 and the Super Power at exactly its stars x 9000 (and not one point
    less); after a power the cost of the next one is 20% more (AW2's rule); the meter grows with the fight (the exact amount is checked by every ctx.attack in the stats tests)."""
    from .game import power_star_cost
    spec = cospec.get(name)
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 20, 10)
    g = ctx.start(m, [spec.id, "andy"], env=ENV)
    cop, scop = g.co_stars(spec.id)
    chk(ctx, f"{name} cop", cop == spec.stars[0], f"CO Power stars: game {cop}, specification {spec.stars[0]}", "meter")
    chk(ctx, f"{name} scop", scop == spec.stars[1], f"Super Power stars (in all): game {scop}, specification {spec.stars[1]}", "meter")
    addr = g.player(1)["addr"] + 0x20

    def offered(charge):
        g.e.w32(addr, charge)
        g.e.wait(4)
        names = g.map_menu_names()
        return "Power" in names, "Super" in names

    for uses in (0, 1):
        pc, sc = power_star_cost(uses) * spec.stars[0], power_star_cost(uses) * spec.stars[1]
        if spec.has_cop and spec.has_scop:
            steps = ((pc - 1, (False, False)), (pc, (True, False)), (sc - 1, (True, False)), (sc, (True, True)))
        elif spec.has_cop:
            # only a CO Power (Lili): "Power" at exactly its cost, and "Super" at no meter at all (a Super Power of 0 stars is none, not a free one)
            steps = ((0, (False, False)), (pc - 1, (False, False)), (pc, (True, False)), (pc * 4, (True, False)))
        else:
            # no CO Power (Aria, Tabitha, Caulder, as Sturm): the menu never offers "Power", whatever the meter; "Super" at exactly the Super Power's cost
            steps = ((0, (False, False)), (sc // 2, (False, False)), (sc - 1, (False, False)), (sc, (False, True)))
        for charge, want in steps:
            got = offered(charge)
            lab = f"{name} {'cop' if spec.has_cop and (not spec.has_scop or charge < sc - 1 or charge == pc) else 'scop'}"
            chk(ctx, lab, got == want, f"after {uses} power(s): meter {charge} of {pc} / {sc} -> Power {got[0]}, Super {got[1]} (want {want[0]}, {want[1]})", "meter threshold")
        if uses == 0:
            ctx.power(g, 1, "power" if spec.has_cop else "super")
            g.end_turn(human=1)
            g.e.w32(addr, 0)
    return g


# --- Tag Powers --------------------------------------------------------------------------------------------------------------------------

_TAG_PATCHED = []


def install_tag_spec():
    """The harness's `tag.compatibility` (Dual Strike's table, Sturm's, Vault Breakers) learns the Silver Nova pairs from the data file `cos/tags.toml`: a pair with one of the custom
    COs is the file's number, every unlisted one 95 (the file's header: "Every unlisted pair is 95") -- or the neutral 100 for Crumb, whose documented rule it is, and Andy's own for Clone Andy (crate::tag)."""
    from . import tag
    if _TAG_PATCHED:
        return
    table = {frozenset((cospec.co_id(p["a"]), cospec.co_id(p["b"]))): p["compat"] for p in cospec.tags()}
    custom = {s.id for s in cospec.all_specs().values() if s.name not in ("crumb", "cloneandy")}
    unlisted = cospec.UNLISTED_COMPAT
    orig = tag.compatibility

    def compat(ds, a, b):
        key = frozenset((a, b))
        if key in table:
            return table[key]
        if a in custom or b in custom:
            return unlisted
        return orig(ds, a, b)
    tag.compatibility = compat
    from . import harness
    stars = {frozenset((cospec.co_id(p["a"]), cospec.co_id(p["b"]))): p["stars"] for p in cospec.tags()}
    orig_stars = harness.Ctx.tag_stars

    def tag_stars(self, g, army, co):
        t = tag.partner(g.e, army) if self.ds else None
        if t and frozenset((co, t["co"])) in stars:
            return stars[frozenset((co, t["co"]))]       # (the pair's luck: 5 per star, from the data file)
        return orig_stars(self, g, army, co)
    harness.Ctx.tag_stars = tag_stars
    _TAG_PATCHED.append(orig)


def pairs_of(name):
    """[(partner display name, stars, tag name, compat)] of a custom CO in tags.toml."""
    out = []
    for p in cospec.tags():
        if p["a"] == name or p["b"] == name:
            other = p["b"] if p["a"] == name else p["a"]
            out.append((other.split(":")[-1].capitalize(), p["stars"], p["name"], p["compat"]))
    return out


def tag_battle(ctx, cos, partners, units=(), props=False):
    """tests.test_tag.tag_battle with the Silver Nova COs on (ENV) and optionally the economy map."""
    from tests.test_tag import co_page_log
    from . import tag
    m = econ_map(ctx) if props else ctx.map()
    for u in units:
        m.unit(*u)
    g = ctx.boot_teams(m, env=dict(ENV, TANGOAW2_CO_PAGE_LOG=co_page_log(ctx)))
    for a, p in enumerate(partners, 1):
        tag.set_teams_partner(g.e, a, p)
    g.set_teams(cos, {1})
    g.teams_to_rules()
    g.set_rules(fog=False)
    g.start_battle()
    g.wait_for_input()
    g.e.survey_arm(ctx.name)
    return g


def tag_pair(ctx, act, par):
    """`act` is the active CO, `par` its tag partner (names: a custom CO, or `aw2:kanbei` / `aw2:colin` / `aw2:sturm`). Both meters full: the map menu offers Tag; the Tag screen shows the
    pair's compatibility; the first half is the active CO's Super Power with the pair's firepower, the second (after Change) the partner's; each half's numbers, heal and funds are the
    specification's; the pair's stars are on the active CO's TAG page."""
    import os
    from . import tag
    from tests.test_tag import EXTRAS, TAG_START, fill, screen_at, power_digits, tag_page_of
    install_tag_spec()
    rules = use_spec(ctx)
    specs = cospec.all_specs()
    pair = next((p for p in cospec.tags() if {p["a"], p["b"]} == {act, par}), None) or {"name": "Dual Strike", "compat": cospec.UNLISTED_COMPAT, "stars": 0}
    a_id, b_id = cospec.co_id(act), cospec.co_id(par)
    a_name, b_name = act.split(":")[-1], par.split(":")[-1]
    label = f"{a_name} tag"
    compat = pair["compat"]
    units = [(1, "tank", 10, 10), (2, "tank", 11, 10), (1, "tank", 10, 12), (2, "infantry", 11, 12)]
    own_units = [(10, 10), (10, 12)]
    enemy_units = [(11, 10), (11, 12)]
    g = tag_battle(ctx, [a_id, "andy"], [b_id, None], units=units, props=True)
    e = g.e
    props = ctx.properties(g, 1)
    from tests.test_crumb import set_unit
    set_unit(g, 3, 3, hp=45)
    # Tag page: the partners and their stars, as the spec lists them (AW2's page; Dual Strike's look lists none).
    if a_name in specs and not os.environ.get("TANGOAW2_DS_GRAPHICS") == "1" and pair["stars"]:
        want = pairs_of(a_name)
        names, stars = tag_page_of(ctx, g)
        listed = [n for n in names.decode().split("\r") if n]
        chk(ctx, label, sorted(listed) == sorted(w[0] for w in want) and stars == sum(w[1] for w in want),
            f"TAG page lists {listed} with {stars} stars (specification {[(w[0], w[1]) for w in want]})", "partners")
        for _ in range(3):
            e.press("B", 4)
            e.wait(30)
        g.wait_for_input()
    fill(g, 1)
    names = g.open_map_menu()["names"]
    chk(ctx, label, "Tag" in names, f"{pair['name']}: the map menu offers Tag with both meters full ({names})", "menu")
    f0 = funds(g)
    i0 = len(ctx.log_lines)
    g.choose("Tag", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: e.u8(EXTRAS) == 1, 1200, step=4), "the tag screen shows")
    ctx.require(screen_at(e, 600 - TAG_START), "the tag screen is done sliding")
    shot = f"tag_{a_name}_{b_name}"
    ctx.shot(g, shot)
    power_digits(ctx, os.path.join(ctx.out, shot + ".bmp"), compat, pair["name"])
    bad = [l for l in ctx.log_lines[i0:] if l.startswith("FAIL")]
    chk(ctx, label, not bad, f"{pair['name']}: the Tag screen shows POWER {compat}%" + ("" if not bad else " -- " + bad[0][6:120]), "screen")
    ctx.require(e.wait_until(lambda: g.player(1)["co_mode"] == 2, 3000, step=10), "the first Super Power starts")
    g.wait_for_input()
    props_first = ctx.properties(g, 1)
    # the first half: the active CO's Super Power and the pair's firepower
    s1 = specs.get(a_name)
    p = g.player(1)
    chk(ctx, label, p["co"] == a_id and p["co_mode"] == 2, f"first half: {a_name}'s Super Power is on (CO {p['co']}, mode {p['co_mode']})", "first half")
    chk(ctx, label, ctx.tag_firepower(g, 1, p["co"]) == compat - 100, f"first half: the pair's firepower is {compat - 100:+d}% (specification {compat}%)", "first half")
    if s1:
        hp = g.unit_at(3, 3)["hp"]
        want_hp = _heal(45, s1.heal[2])
        chk(ctx, label, hp == want_hp, f"first half: {a_name}'s Super Power healed 45 -> {hp} (specification: {s1.heal[2]} HP -> {want_hp})", "heal")
        got = funds(g) - f0
        chk(ctx, label, got == s1.funds(2, props), f"first half: funds collected {got} (specification {s1.funds(2, props)}: {s1.tribute[2]} x {props} a property" + (", one day's income" if s1.income_grant else "") + ")", "funds")
    special_hook(ctx, g, a_name, label, "first half", own_units, enemy_units, {c: 100 for c in own_units + enemy_units})
    fight(ctx, label, f"first half {a_name}", g, (10, 10), (10, 10), (11, 10))
    # the second half: Change, the partner's Super Power
    f1 = funds(g)
    set_unit(g, 3, 3, hp=45)
    before2 = {c: (g.unit_at(*c) or {"hp": 0})["hp"] for c in own_units + enemy_units}
    g.open_map_menu()
    g.choose("Change", g.MAP_MENU)
    ctx.require(e.wait_until(lambda: g.player(1)["co"] == b_id and g.player(1)["co_mode"] == 2, 3000, step=10), "the second half: the partner's Super Power")
    g.wait_for_input()
    s2 = specs.get(b_name)
    chk(ctx, label, ctx.tag_firepower(g, 1, b_id) == compat - 100, f"second half: the pair's firepower is {compat - 100:+d}%", "second half")
    moved = [u for u in g.units(1) if u["flags"] & 1]
    chk(ctx, label, not moved, "second half: every unit may move again", "second half")
    if s2:
        hp = g.unit_at(3, 3)["hp"]
        want_hp = _heal(45, s2.heal[2])
        chk(ctx, label, hp == want_hp, f"second half: {b_name}'s Super Power healed 45 -> {hp} (specification: {s2.heal[2]} HP -> {want_hp})", "heal")
        got = funds(g) - f1
        chk(ctx, label, got == s2.funds(2, props), f"second half: funds collected {got} (specification {s2.funds(2, props)}: {s2.tribute[2]} x {props} a property" + (", one day's income" if s2.income_grant else "") + ")", "funds")
    special_hook(ctx, g, b_name, label, "second half", own_units, enemy_units, before2)
    fight(ctx, label, f"second half {b_name}", g, (10, 12), (10, 12), (11, 12))
    return g


def special_hook(ctx, g, co, label, half, own, enemy, before):
    """The Super Power's special rule of the CO whose half this is: Tabitha's Firestorm (the enemy units on the struck square took 8 HP or were left on 1 HP, her own team's units
    were not hurt) -- read from the hit points the Tag Power left against `before`. (Caulder's heal is checked with every half's heal; Lili has no Super Power: her half is the
    plain +10% of any power.)"""
    if co != "tabitha":
        return
    now = {c: (g.unit_at(*c) or {"hp": 0})["hp"] for c in own + enemy}
    hurt = [c for c in enemy if before[c] and now[c] < before[c]]
    chk(ctx, label, bool(hurt), f"{half}: Firestorm hurt the enemy units beside the site (hit {hurt}: {[(before[c], now[c]) for c in hurt]}; all {[(c, before[c], now[c]) for c in enemy]})", "firestorm")
    chk(ctx, label, all(now[c] == before[c] for c in own if before[c]), f"{half}: and none of her own ({[(before[c], now[c]) for c in own]})", "firestorm")


def _heal(hp, bars_up):
    if not bars_up:
        return hp
    for _ in range(bars_up):
        if (hp - 1) // 10 + 1 == 10:
            break
        hp = min(100, hp + 10)
    return ((hp - 1) // 10 + 1) * 10


# --- the special rules: Firestorm, Enigma, Hypothesis's movement -------------------------------------------------------------------------------

RNG = 0x03001FD4                # the game's random word (crate::co_powers::RNG)
WEATHER = 0x03003FEC            # gPlaySt's weather (0 clear, 1 snow, 2 rain)
WEATHER_MODE = 0x03003FED       # 0 fixed clear, 1 random, 2 permanent, 3 fixed (the Rules screen's weather)
SAND_STATE = 0x03004493         # crate::sandstorm::STATE: low nibble 2 is a one-day sandstorm
LILI_STATE = 0x0203C980         # crate::es_co::LILI_STATE: +0 turn starts left, +1 her army, +2 the weather rolled (1 snow, 2 rain, 3 sand)
STUN_PENDING, STUN_ACTIVE = 0x0203FE00, 0x0203FE28      # crate::co_powers: Ex Machina's stun bits (40 bytes each)
ROLLED = {1: "snow", 2: "rain", 3: "sand"}
# RNG words that make the roll each weather (the game's word goes through `next_random` twice between the poke and the roll: 1 + word % 3 of the second result)
SEEDS = {"snow": 64, "rain": 1, "sand": 76}


def rng_next(r):
    """crate::sandstorm::next_random on a word: the game's own generator."""
    s = (r * 4) & 0xFFFFFFFF
    return ((((s + 2) & 0xFFFFFFFF) * ((s + 3) & 0xFFFFFFFF)) & 0xFFFFFFFF) >> 2


def weather_of(g):
    """"clear", "snow", "rain" or "sand" (a one-day sandstorm of the pack) as the game has it now."""
    w = g.e.u8(WEATHER)
    if w:
        return {1: "snow", 2: "rain"}.get(w, f"weather {w}")
    return "sand" if g.e.u8(SAND_STATE) & 0xF == 2 else "clear"


def lili_state(g):
    """(turn starts left, her army, the weather rolled) of the running Enigma."""
    b = g.e.read(LILI_STATE, 3)
    return b[0], b[1], b[2]


def pass_turn(g, to):
    """End the turn from the map menu and wait for army `to` (two human armies; a fog game shows 'Next turn: press A' between them)."""
    g.open_map_menu()
    g.choose("End", g.MAP_MENU)
    for _ in range(80):
        if g.current_army() == to:
            break
        g.e.press("A", 4)
        g.e.wait(25)
    g.wait_for_input()


def diamond(c, r=2):
    return {(c[0] + dx, c[1] + dy) for dx in range(-r, r + 1) for dy in range(-r, r + 1) if abs(dx) + abs(dy) <= r}


def after_firestorm(hp, damage=80):
    """A strike never kills (sub_08044854): a unit with more than the damage loses it, any other is left on 1 (internal) HP, which the game shows as 1."""
    return hp - damage if hp > damage else 1


# --- Tabitha: Firestorm ----------------------------------------------------------------------------------------------------------------------

FIRE_CENTRE = (20, 10)
FIRE_OWN = [(21, 9), (19, 11), (24, 10)]          # her own Tanks: two inside the diamond, one beyond it
FIRE_HP = {(20, 10): 100, (21, 10): 90, (19, 10): 50, (20, 11): 80, (20, 9): 10, (22, 10): 30}      # internal HP: 9 HP, 5 HP, 8 HP, 1 HP and 3 HP units among the Tanks (the rest 100)


def firestorm_map(ctx):
    """A rich cluster (a Tank in every cell of the 13-cell diamond round (20, 10), three of her own among them) and a poor one far off (three Infantry), one Infantry
    on three of the cells of ring 3 that the diamond does not take."""
    m = ctx.map()
    for c in sorted(diamond(FIRE_CENTRE)):
        m.unit(1 if c in FIRE_OWN else 2, "tank", *c)
    m.unit(1, "tank", FIRE_OWN[2][0], FIRE_OWN[2][1])
    for c in ((23, 10), (17, 10), (20, 13), (20, 7)):
        m.unit(2, "infantry", *c)
    for c in ((6, 15), (7, 15), (6, 16)):
        m.unit(2, "infantry", *c)
    return m


def hp_map(g):
    return {(u["x"], u["y"]): u["hp"] for u in g.units() if u["type"]}


def army_map(g):
    return {(u["x"], u["y"]): u["army"] for u in g.units() if u["type"]}


def firestorm_game(ctx, co=86, power="super"):
    g = ctx.start(firestorm_map(ctx), [co, "andy"], humans=(1, 2), env=ENV)
    for c, hp in FIRE_HP.items():
        ctx.set_hp(g, *c, hp)
    return g


POWER_ANIM = 0x0203F7A0     # crate::power_anim::STATE: +0 kind (1 Ex Machina), +1/+2 the target square, +4 u16 frames played, +0x1E 1 once the bolt's map is written


def hook_firestorm_animation(ctx, shots=None):
    """Firestorm plays Von Bolt's Ex Machina on the map, centred on her target, and not AW2's meteor: during the strike the power animation's state says kind 1 (Ex Machina; the meteor
    draw is replaced by it), its target is the site, its frames advance and its bolt layer is written; and no unit is stunned. With `shots` (a directory) the frames before, during and
    after are kept as BMPs (the game's own 240 x 160 picture)."""
    import os
    g = firestorm_game(ctx)
    g.charge_power(1, "super")
    g.open_map_menu()
    army = g.current_army()
    if shots:
        os.makedirs(shots, exist_ok=True)
        g.e.shot(os.path.join(shots, "1_before"))
    g.choose("Super", g.MAP_MENU)
    seen = {"kind": 0, "bolt": 0, "frames": 0, "target": None}
    during = after = False
    for _ in range(900):
        g.e.wait(2)
        kind, bolt, frames = g.e.u8(POWER_ANIM), g.e.u8(POWER_ANIM + 0x1E), g.e.u16(POWER_ANIM + 4)
        if kind:
            seen["kind"] = kind
            seen["target"] = (g.e.u8(POWER_ANIM + 1), g.e.u8(POWER_ANIM + 2))
            seen["frames"] = max(seen["frames"], frames)
            seen["bolt"] = max(seen["bolt"], bolt)
            if shots and bolt and frames > 30 and not during:
                g.e.shot(os.path.join(shots, "2_during"))
                during = True
        elif seen["kind"] and not after:
            if shots:
                g.e.wait(40)
                g.e.shot(os.path.join(shots, "3_after"))
            after = True
        if after and g.player(army)["co_mode"] == 2:
            break
    g.wait_for_input()
    chk(ctx, "tabitha scop", seen["kind"] == 1, f"the strike plays Von Bolt's Ex Machina (power animation kind {seen['kind']}; 1 is Ex Machina, 0 would be AW2's meteor)", "firestorm animation")
    chk(ctx, "tabitha scop", seen["target"] == FIRE_CENTRE, f"the animation is centred on her target {seen['target']} (the site {FIRE_CENTRE})", "firestorm animation")
    chk(ctx, "tabitha scop", seen["frames"] >= 30 and seen["bolt"] == 1, f"the bolt falls: {seen['frames']} frames played, the bolt layer written ({seen['bolt']})", "firestorm animation")
    marks = bytes(g.e.read(STUN_PENDING, 40)) + bytes(g.e.read(STUN_ACTIVE, 40))
    chk(ctx, "tabitha scop", not any(marks), "and no stun mark carries over from Von Bolt's script", "firestorm animation")
    g.e.close()


def hook_firestorm(ctx):
    """Tabitha's Super Power: 8 HP to every enemy unit within 2 of the site AW2 picks (the richest cluster), a unit never dropping below 1 HP (a 9 HP unit is left on 1 HP and is not
    destroyed), her own team's units untouched, nobody stunned; the damaged units move normally on their turn. Control: Von Bolt's Ex Machina on the same field still stuns."""
    spec = cospec.strike("tabitha")
    chk(ctx, "tabitha scop", spec == {"hp": 8, "radius": 2, "pick": "value", "stun": False, "can_kill": False}, f"the data file's Firestorm is {spec}", "firestorm")
    g = firestorm_game(ctx)
    before, armies = hp_map(g), army_map(g)
    ctx.power(g, 1, "super")
    after = hp_map(g)
    inside = diamond(FIRE_CENTRE, spec["radius"])
    enemy = {c for c in before if armies[c] == 2}
    own = {c for c in before if c not in enemy}
    ok = True
    for c in sorted(before):
        want = after_firestorm(before[c]) if (c in inside and c in enemy) else before[c]
        got = after.get(c, 0)
        if got != want:
            ok = False
            ctx.log(f"firestorm cell {c}: {before[c]} -> {got}, specification {want}")
    chk(ctx, "tabitha scop", ok, f"every enemy unit within 2 of the richest cluster's centre {FIRE_CENTRE} lost 8 HP or was left on 1 HP; every other unit kept its HP ({len(before)} units)", "firestorm")
    chk(ctx, "tabitha scop", all(c in after for c in before), "no unit was destroyed", "firestorm")
    for c, label in (((21, 10), "9 HP"), ((19, 10), "5 HP"), ((20, 11), "8 HP"), ((20, 9), "1 HP"), ((20, 10), "10 HP")):
        shown = damage.hp_bars(after[c])
        want = {"9 HP": 1, "5 HP": 1, "8 HP": 1, "1 HP": 1, "10 HP": 2}[label]
        chk(ctx, "tabitha scop", shown == want, f"the {label} Tank at {c} ends on {shown} HP shown (specification {want}), still on the map", "firestorm")
    ring = [c for c in ((23, 10), (17, 10), (20, 13), (20, 7)) if c in before]
    chk(ctx, "tabitha scop", all(after[c] == 100 for c in ring), "the Infantry on ring 3 (three cells from the centre) were not hit", "firestorm")
    chk(ctx, "tabitha scop", all(after[c] == 100 for c in ((6, 15), (7, 15), (6, 16))), "the poorer cluster far off was not the site", "firestorm")
    chk(ctx, "tabitha scop", all(after[c] == before[c] for c in own), f"her own Tanks, inside the diamond and beyond it, are untouched ({[(c, before[c], after[c]) for c in sorted(own)]})", "firestorm")
    # no stun: no mark, nobody done, and the enemy moves normally on its turn
    marks = bytes(g.e.read(STUN_PENDING, 40)) + bytes(g.e.read(STUN_ACTIVE, 40))
    chk(ctx, "tabitha scop", not any(marks), "no unit is marked as stunned", "no stun")
    chk(ctx, "tabitha scop", not any(u["flags"] & 1 for u in g.units() if u["type"]), "no unit of either army is done for the turn", "no stun")
    pass_turn(g, 2)
    hit = [c for c in sorted(inside & enemy) if c in after]
    done = [c for c in hit if g.unit_at(*c)["flags"] & 1]
    chk(ctx, "tabitha scop", not done, f"on their turn the damaged enemy units are free to move ({len(hit)} units, {len(done)} held)", "no stun")
    t = g.unit_at(20, 10)
    g.select(20, 10)
    g.move_to(20, 14)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    moved = g.unit(t["id"])
    chk(ctx, "tabitha scop", (moved["x"], moved["y"]) == (20, 14), f"a damaged Tank (HP {t['hp']}) moved four cells on its turn: now at {(moved['x'], moved['y'])}", "no stun")
    g.e.close()
    # the control: Von Bolt's Ex Machina on the same field stuns the units it hits
    g = firestorm_game(ctx, co=cospec.DS_IDS["vonbolt"])
    ctx.power(g, 1, "super")
    pass_turn(g, 2)
    held = [c for c in sorted(inside) if g.unit_at(*c) and g.unit_at(*c)["army"] == 2 and g.unit_at(*c)["flags"] & 1]
    chk(ctx, "tabitha scop", len(held) >= 3, f"control: Von Bolt's Ex Machina holds the enemy units it hits on their turn ({len(held)} held)", "no stun")
    g.e.close()
    # her own units beside the enemy do not pull the strike away (they are spared, so they cost a site nothing): two enemy Tanks by her own Tanks against a lone Infantry far off
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(1, "tank", 10, 12).unit(2, "tank", 11, 10).unit(2, "tank", 11, 12).unit(2, "infantry", 24, 12)
    g = ctx.start(m, [86, "andy"], env=ENV)
    ctx.power(g, 1, "super")
    hp = {c: g.unit_at(*c)["hp"] for c in ((11, 10), (11, 12), (24, 12), (10, 10), (10, 12))}
    chk(ctx, "tabitha scop", hp[(11, 10)] == 20 and hp[(11, 12)] == 20 and hp[(24, 12)] == 100 and hp[(10, 10)] == 100 and hp[(10, 12)] == 100,
        f"the site is the enemy Tanks beside her own, not the lone Infantry: {hp}", "firestorm site")
    g.e.close()


def cpu_firestorm(ctx):
    """The computer plays Tabitha (army 2) with the meter paid for: it uses Firestorm within three turns, on the player's richest cluster: every unit of the player's within 2 of one centre
    took 8 HP (or was left on 1 HP), nothing outside that diamond and none of its own was touched."""
    m = ctx.map()
    for c in sorted(diamond((10, 8))):
        m.unit(1, "tank", *c)
    m.unit(1, "infantry", 3, 15)
    m.unit(2, "tank", 25, 15).unit(2, "infantry", 26, 15).unit(2, "mech", 25, 16).unit(2, "artillery", 26, 16)
    g = ctx.start(m, ["andy", 86], env=ENV)
    pos = {u["id"]: (u["x"], u["y"], u["army"], u["hp"]) for u in g.units() if u["type"]}
    for turn in range(3):
        g.charge_power(2, "super")
        g.end_turn()
        if g.player(2)["powers_used"]:
            break
    p = g.player(2)
    chk(ctx, "tabitha scop", p["powers_used"] == 1, f"the computer fired Firestorm on turn {turn + 1} (powers used {p['powers_used']})", "cpu")
    now = {u["id"]: u["hp"] for u in g.units() if u["type"]}
    mine = {i: v for i, v in pos.items() if v[2] == 1}
    hurt = {i for i in mine if now.get(i, 0) < mine[i][3]}
    cells = {i: (mine[i][0], mine[i][1]) for i in mine}
    centres = [c for c in ((x, y) for x in range(30) for y in range(20)) if {i for i in mine if cells[i] in diamond(c)} == hurt]
    chk(ctx, "tabitha scop", bool(hurt) and bool(centres), f"the computer's Firestorm hit {len(hurt)} of the player's units, all within 2 of one site ({centres[:3]})", "cpu")
    chk(ctx, "tabitha scop", all(now[i] == after_firestorm(mine[i][3]) for i in hurt), "each of them lost 8 HP (or was left on 1 HP)", "cpu")
    ours = [i for i, v in pos.items() if v[2] == 2]
    chk(ctx, "tabitha scop", all(now.get(i, 0) == pos[i][3] for i in ours), "its own units were not hurt", "cpu")
    return g


# --- Lili: Enigma ----------------------------------------------------------------------------------------------------------------------------

def enigma_game(ctx, weather="clear", extra=(), humans=(1, 2)):
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(1, "artillery", 5, 5).unit(1, "recon", 10, 14).unit(1, "infantry", 10, 16)
    m.unit(2, "infantry", 8, 5).unit(2, "tank", 20, 10).unit(2, "artillery", 25, 5).unit(2, "infantry", 25, 7)
    for u in extra:
        m.unit(*u)
    return ctx.start(m, [87, "andy"], humans=humans, weather=weather, env=ENV)


def use_enigma(ctx, g, seed):
    """Lili's CO Power with the game's random word set to `seed` first: returns (the word after the roll, the weather the game shows)."""
    g.charge_power(1, "power")
    g.e.w32(RNG, seed)
    g.power("power")
    return g.e.u32(RNG), weather_of(g)


def hook_enigma_roll(ctx):
    """Enigma's weather is drawn from the game's random number generator: the word the roll leaves is the weather's (1 + word % 3: snow, rain, sand), the same word gives the same
    weather on every console (twice), and all three weathers are reachable."""
    seen = {}
    for name, seed in SEEDS.items():
        g = enigma_game(ctx)
        word, w = use_enigma(ctx, g, seed)
        want = ROLLED[1 + word % 3]
        chk(ctx, "lili cop", w == name and want == name, f"random word {seed}: Enigma drew {w} (the game's word {word} says {want}; expected {name})", "roll")
        chk(ctx, "lili cop", word == rng_next(rng_next(seed)), f"the word after the roll is the generator's second step from {seed} ({word})", "roll")
        left, army, rolled = lili_state(g)
        chk(ctx, "lili cop", (left, army, ROLLED.get(rolled)) == (2, 1, name), f"Enigma's state: {left} turn starts left, army {army}, weather {ROLLED.get(rolled)}", "roll")
        seen[name] = (w, bytes(g.e.read(LILI_STATE, 3)))
        g.e.close()
    chk(ctx, "lili cop", {v[0] for v in seen.values()} == {"snow", "rain", "sand"}, f"snow, rain and sand are all reachable ({sorted(v[0] for v in seen.values())})", "roll")
    g = enigma_game(ctx)
    word, w = use_enigma(ctx, g, SEEDS["sand"])
    chk(ctx, "lili cop", (w, bytes(g.e.read(LILI_STATE, 3))) == seen["sand"], "the same word on another console: the same weather and the same state (deterministic)", "roll")
    g.e.close()
    # no Enigma without the power: the weather stays what the game has
    g = enigma_game(ctx)
    chk(ctx, "lili cop", weather_of(g) == "clear" and lili_state(g) == (0, 0, 0), "before the power: clear weather and no Enigma state", "roll")
    g.e.close()


def hook_enigma_days(ctx, rules="clear"):
    """Enigma lasts two days: through the opponent's turn, her next turn and the opponent's turn, and ends when her turn after next begins -- with the Rules screen's weather clear or fixed
    (it goes back to the rule's weather), or random; in all three weathers. With permanent weather (a map's) it changes nothing."""
    from_rules = {"clear": "clear", "snow": "snow", "random": None}[rules]
    for name, seed in SEEDS.items():
        g = enigma_game(ctx, weather=rules)
        rule_weather = weather_of(g)
        word, w = use_enigma(ctx, g, seed)
        line = [(1, w, lili_state(g)[0])]
        for k in range(4):
            pass_turn(g, 2 if k % 2 == 0 else 1)
            line.append((g.current_army(), weather_of(g), lili_state(g)[0]))
        want = [(1, name, 2), (2, name, 2), (1, name, 1), (2, name, 1)]
        chk(ctx, "lili cop", line[:4] == want, f"{name} under Rules weather {rules}: armies, weather and turn starts left {line[:4]} (specification {want})", "days")
        ended = line[4]
        chk(ctx, "lili cop", ended[0] == 1 and ended[2] == 0 and (ended[1] != name or rule_weather == name), f"and it ends when her turn after next begins: {ended}", "days")
        if from_rules:
            chk(ctx, "lili cop", ended[1] == from_rules, f"the Rules weather ({rules}) is back: {ended[1]}", "days")
        sandbit = g.e.u8(SAND_STATE) & 0xF
        chk(ctx, "lili cop", sandbit != 2, f"no sandstorm is left over (state {sandbit:#x})", "days")
        g.e.close()


def hook_enigma_permanent(ctx):
    """A map whose weather is permanent keeps it: Enigma changes nothing but her units' immunity and move (the state never starts)."""
    g = enigma_game(ctx)
    g.e.w8(WEATHER_MODE, 2)
    g.e.w8(WEATHER, 1)
    word, w = use_enigma(ctx, g, SEEDS["sand"])
    chk(ctx, "lili cop", w == "snow" and lili_state(g) == (0, 0, 0), f"permanent snow stays snow and no Enigma state starts ({w}, {lili_state(g)})", "permanent")
    chk(ctx, "lili cop", g.player(1)["co_mode"] == 1, "her CO Power is on all the same", "permanent")
    t = g.unit_at(10, 10)
    g.select(10, 10)
    g.move_to(13, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    for k in range(3):
        pass_turn(g, 2 if k % 2 == 0 else 1)
    chk(ctx, "lili cop", weather_of(g) == "snow" and g.e.u8(WEATHER_MODE) == 2, "after three turn changes the permanent snow is still there", "permanent")
    g.e.close()


def unit_fuel(g, uid):
    return g.unit(uid)["fuel"]


def hook_enigma_immunity(ctx):
    """While Lili is in Enigma her units ignore the weather: in snow a Tank's move costs its plain fuel (3 for 3 cells, an enemy's costs 6), in a sandstorm her Artillery fires at
    distance 3 (an enemy Artillery's range is cut to 2) -- the immunity lasts the weather's two days (through her next turn) and the weather cuts into her army again when her turn after next begins."""
    # snow
    g = enigma_game(ctx)
    word, w = use_enigma(ctx, g, SEEDS["snow"])
    chk(ctx, "lili cop", w == "snow", "Enigma brought snow", "immunity")
    t = g.unit_at(10, 10)
    f0 = unit_fuel(g, t["id"])
    g.select(10, 10)
    g.move_to(13, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    used = f0 - unit_fuel(g, t["id"])
    chk(ctx, "lili cop", used == 3, f"in snow her Tank used {used} fuel for 3 cells (no doubling in the power; the plain price is 3)", "immunity")
    pass_turn(g, 2)
    e = g.unit_at(20, 10)
    f1 = unit_fuel(g, e["id"])
    g.select(20, 10)
    g.move_to(17, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    used = f1 - unit_fuel(g, e["id"])
    chk(ctx, "lili cop", used == 6, f"control: the enemy Tank used {used} fuel for 3 cells in the same snow (doubled: 6)", "immunity")
    pass_turn(g, 1)
    chk(ctx, "lili cop", g.player(1)["co_mode"] == 0 and weather_of(g) == "snow", "her CO Power is over on her next turn and the snow is still on (day 2)", "immunity")
    t = g.unit_at(13, 10)
    f2 = unit_fuel(g, t["id"])
    g.select(13, 10)
    g.move_to(16, 10)
    g.choose("Wait", g.ACTION_MENU)
    g.wait_idle()
    used = f2 - unit_fuel(g, t["id"])
    chk(ctx, "lili cop", used == 3, f"on the second day her Tank still pays {used} for 3 cells in the snow (Enigma's immunity lasts both days; the plain price is 3)", "immunity")
    pass_turn(g, 2)
    pass_turn(g, 1)
    chk(ctx, "lili cop", weather_of(g) != "snow" and lili_state(g)[0] == 0, f"when her turn after next begins the snow and Enigma are over (weather {weather_of(g)}, state {lili_state(g)})", "immunity")
    g.e.close()
    # sandstorm: Artillery range 2..3 -> an enemy's is 2..2
    g = enigma_game(ctx, extra=[(2, "artillery", 5, 14), (1, "infantry", 8, 14), (2, "artillery", 15, 14), (1, "infantry", 15, 12)])
    word, w = use_enigma(ctx, g, SEEDS["sand"])
    chk(ctx, "lili cop", w == "sand", "Enigma brought a sandstorm", "immunity")
    names = g.action_menu_at(5, 5)
    fire = any(n.lower().startswith("fire") and "(greyed)" not in n for n in names)
    chk(ctx, "lili cop", fire, f"her Artillery fires at an enemy 3 cells away in the sandstorm (menu {names})", "immunity")
    g.e.press("B", 4)
    g.e.wait(20)
    pass_turn(g, 2)
    near = g.action_menu_at(15, 14)          # Andy's Artillery with Lili's Infantry 2 cells away
    fire2 = any(n.lower().startswith("fire") and "(greyed)" not in n for n in near)
    chk(ctx, "lili cop", fire2, f"control: an enemy Artillery fires at 2 cells in the sandstorm (menu {near})", "immunity")
    g.e.press("B", 4)
    g.e.wait(20)
    g.wait_for_input()
    far = g.action_menu_at(5, 14)            # Andy's other Artillery with Lili's Infantry 3 cells away
    fire3 = any(n.lower().startswith("fire") and "(greyed)" not in n for n in far)
    chk(ctx, "lili cop", not fire3, f"control: with a target 3 cells away only, an enemy Artillery cannot fire in the sandstorm (menu {far})", "immunity")
    g.e.press("B", 4)
    g.e.wait(20)
    g.wait_for_input()
    pass_turn(g, 1)
    chk(ctx, "lili cop", g.player(1)["co_mode"] == 0 and weather_of(g) == "sand", "her CO Power is over on her next turn, the sandstorm blows on (day 2)", "immunity")
    names = g.action_menu_at(5, 5)
    fire = any(n.lower().startswith("fire") and "(greyed)" not in n for n in names)
    chk(ctx, "lili cop", fire, f"and on the second day her Artillery still fires at 3 cells (Enigma's immunity lasts both days; menu {names})", "immunity")
    g.e.press("B", 4)
    g.e.wait(20)
    g.wait_for_input()
    pass_turn(g, 2)
    pass_turn(g, 1)
    chk(ctx, "lili cop", weather_of(g) != "sand" and lili_state(g)[0] == 0, "when her turn after next begins the sandstorm and Enigma are over", "immunity")
    g.e.close()


def hook_enigma_move(ctx):
    """In Enigma every unit of hers moves 1 more (Tank 6 -> 7, Recon 8 -> 9, Infantry 3 -> 4 on a road lane) on both days, and not one more once the weather is over."""
    rules = use_spec(ctx)
    types = [5, 6, 1]
    m = ctx.map()
    lanes = {}
    for k, t in enumerate(types):
        y = 3 + 2 * k
        lanes[t] = y
        for x in range(3, 28):
            m.terrain(x, y, "road")
        m.unit(1, t, 3, y)
    m.unit(2, "infantry", 25, 18)
    g = ctx.start(m, [87, "andy"], humans=(1, 2), env=ENV)
    word, w = use_enigma(ctx, g, SEEDS["sand"])
    for t in types:
        base = rules.unit(t)["move"]
        ok1, ok2 = probe_move(g, (3, lanes[t]), (3 + base + 1, lanes[t])), probe_move(g, (3, lanes[t]), (3 + base + 2, lanes[t]))
        chk(ctx, "lili cop", ok1 and not ok2, f"in Enigma the {name_of(t)} moves {base + 1} (base {base} +1): reaches +{base + 1} {ok1}, +{base + 2} {ok2}", "move")
    pass_turn(g, 2)
    pass_turn(g, 1)
    for t in types:
        base = rules.unit(t)["move"]
        ok1, ok2 = probe_move(g, (3, lanes[t]), (3 + base + 1, lanes[t])), probe_move(g, (3, lanes[t]), (3 + base + 2, lanes[t]))
        chk(ctx, "lili cop", ok1 and not ok2, f"on Enigma's second day (her CO Power over) the {name_of(t)} still moves {base + 1}: reaches +{base + 1} {ok1}, +{base + 2} {ok2}", "move")
    pass_turn(g, 2)
    pass_turn(g, 1)
    for t in types:
        base = rules.unit(t)["move"]
        ok1, ok2 = probe_move(g, (3, lanes[t]), (3 + base, lanes[t])), probe_move(g, (3, lanes[t]), (3 + base + 1, lanes[t]))
        chk(ctx, "lili cop", ok1 and not ok2, f"when her turn after next begins the {name_of(t)} moves {base} again: reaches +{base} {ok1}, +{base + 1} {ok2}", "move")
    g.e.close()


def hook_enigma_suspend(ctx):
    """A game saved in the middle of Enigma (from her turn, and again from the opponent's) and continued keeps the state: the weather, the turn starts left and the day count; it ends
    when her turn after next begins as if nothing had happened (snow, rain and sand)."""
    import os
    from . import saves
    from .emu import Emu
    from .game import Game
    for name, seed in SEEDS.items():
        g = enigma_game(ctx)
        word, w = use_enigma(ctx, g, seed)
        before = (weather_of(g), lili_state(g), g.e.u8(SAND_STATE) & 0xF)
        saves.suspend(g)
        path = g.e.save(os.path.join(ctx.out, f"enigma_{name}"))
        g.e.close()
        e2 = Emu(save=path, ds=True, env=ENV)
        g2 = Game(e2)
        ctx.games.append(g2)
        saves.to_select_mode(e2)
        saves.versus_continue(g2)
        after = (weather_of(g2), lili_state(g2), g2.e.u8(SAND_STATE) & 0xF)
        chk(ctx, "lili cop", after == before, f"{name}: saved in her turn and continued: weather, state and day bits {before} -> {after}", "suspend")
        pass_turn(g2, 2)
        saves.suspend(g2)
        path = g2.e.save(os.path.join(ctx.out, f"enigma_{name}_2"))
        mid = (weather_of(g2), lili_state(g2))
        g2.e.close()
        e3 = Emu(save=path, ds=True, env=ENV)
        g3 = Game(e3)
        ctx.games.append(g3)
        saves.to_select_mode(e3)
        saves.versus_continue(g3)
        chk(ctx, "lili cop", (weather_of(g3), lili_state(g3)) == mid, f"{name}: saved again in the opponent's turn and continued: {mid} -> {(weather_of(g3), lili_state(g3))}", "suspend")
        line = []
        for k, to in enumerate((1, 2, 1)):
            pass_turn(g3, to)
            line.append((g3.current_army(), weather_of(g3), lili_state(g3)[0]))
        want = [(1, name, 1), (2, name, 1), (1, "clear", 0)]
        chk(ctx, "lili cop", line == want, f"{name}: after the two continues the Enigma still ends when her turn after next begins: {line} (specification {want})", "suspend")
        g3.e.close()


# --- Caulder: Hypothesis (Sturm's movement) and Cataclysm ----------------------------------------------------------------------------------

STURM_TYPES = [1, 2, 5, 6, 10]            # Infantry, Mech, Tank, Recon, Artillery
STURM_TERRAINS = ["wood", "mountain", "river"]


def sturm_reach(ctx, co, mode):
    """Every unit class on a lane of one terrain: the farthest cell it reaches. Returns {(type, terrain): cells}."""
    rules = use_spec(ctx)
    m = ctx.map()
    lanes = {}
    y = 1
    for terrain in STURM_TERRAINS:
        for t in STURM_TYPES:
            lanes[(t, terrain)] = y
            for x in range(3, 28):
                m.terrain(x, y, terrain)
            m.unit(1, t, 3, y)
            y += 1
    g = ctx.start(m, [co, "andy"], env=ENV)
    if mode:
        ctx.power(g, 1, "super")
    out = {}
    for (t, terrain), y in lanes.items():
        base = rules.unit(t)["move"]
        reach = 0
        for d in range(1, base + 3):
            if probe_move(g, (3, y), (3 + d, y)):
                reach = d
            else:
                break
        out[(t, terrain)] = reach
    g.e.close()
    return out


def hook_sturm_move(ctx):
    """Caulder's Hypothesis is Sturm's movement: on a lane of woods, mountains or river every ground unit that can enter the terrain pays 1 a cell, so it reaches exactly its base move
    (Infantry and Mech included on mountains and river, where they pay 2 otherwise; a Tank still cannot enter river or mountains: Sturm's chart keeps the terrain closed to it); every lane
    is Sturm's own (the control), Andy's units on the same lanes fall short. Day to day and in Cataclysm."""
    rules = use_spec(ctx)
    chk(ctx, "caulder d2d", cospec.movement("caulder") == "sturm", f"the data file's movement chart is {cospec.movement('caulder')!r}", "movement")
    sturm = sturm_reach(ctx, cospec.AW2_IDS["sturm"], 0)
    control = sturm_reach(ctx, cospec.IDS["andy"], 0)
    for mode in (0, 2):
        got = sturm_reach(ctx, cospec.IDS["caulder"], mode)
        label = tag("caulder", mode)
        bad = [(name_of(t), terrain, got[(t, terrain)], sturm[(t, terrain)]) for (t, terrain) in got if got[(t, terrain)] != sturm[(t, terrain)]]
        chk(ctx, label, not bad, f"on woods, mountains and river every unit reaches exactly what Sturm's does ({len(got)} lanes; different: {bad})", "movement")
        slow = [(name_of(t), terrain, v, rules.unit(t)["move"]) for (t, terrain), v in got.items() if v and v != rules.unit(t)["move"]]
        chk(ctx, label, not slow, f"and every lane a unit can enter costs 1 a cell: it reaches its base move (not: {slow})", "movement")
        chk(ctx, label, sum(1 for v in got.values() if v) >= 9, f"{sum(1 for v in got.values() if v)} of {len(got)} lanes are passable", "movement")
    shorter = [(name_of(t), terrain) for (t, terrain), v in control.items() if v and v < rules.unit(t)["move"]]
    chk(ctx, "caulder d2d", len(shorter) >= 4, f"control: Andy's units fall short of their base move on {len(shorter)} lanes (Mech and Infantry on mountains and river, wheels and treads in woods)", "movement")


def hook_cataclysm(ctx):
    """Cataclysm: +15% attack and defence over the day to day and the power's own +10%: a unit totals 18 + 15 + 10 = +43% attack (and +43% defence), against +18% day to day; with the +5 HP
    heal (the `economy` facet) and no funds. The fights themselves are the `stats` facet's."""
    spec = cospec.get("caulder")
    use_spec(ctx)
    for t in (1, 5, 10):
        chk(ctx, "caulder scop", spec.bonus(2, t, 0) == 43 and spec.bonus(2, t, 1) == 33 and spec.bonus(0, t, 0) == 18 and spec.bonus(0, t, 1) == 18,
            f"{name_of(t)}: attack {spec.bonus(0, t, 0)} -> {spec.bonus(2, t, 0)} (18 + 15 + the power's own 10), defence {spec.bonus(0, t, 1)} -> {spec.bonus(2, t, 1)} (+10 in the player's block)", "total")
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(1, "infantry", 10, 14).unit(2, "infantry", 11, 14)
    g = ctx.start(m, [88, "andy"], env=ENV)
    ctx.power(g, 1, "super")
    p = g.player(1)
    chk(ctx, "caulder scop", p["temp_defence"] == 10, f"the game's own +10% defence of any power is in the player's block ({p['temp_defence']}; the +10% firepower is added by the engine's bonus)", "total")
    fight(ctx, "caulder scop", "Tank attacks Tank in Cataclysm", g, (10, 10), (10, 10), (11, 10))
    fight(ctx, "caulder scop", "Infantry attacks Infantry in Cataclysm", g, (10, 14), (10, 14), (11, 14))
    g.e.close()



# --- the computer ---------------------------------------------------------------------------------------------------------------------------

def cpu_fires(ctx, name, which):
    """The computer plays `name` as army 2 with the meter at the power's cost: within three of its turns it uses the power (powers used 1, the power mode seen on its turn), and
    the power does what it does (a heal reaches its hurt units)."""
    from tests.test_crumb import set_unit
    spec = cospec.get(name)
    mode = 2 if which == "super" else 1
    label = tag(name, mode)
    m = ctx.map()
    m.unit(1, "tank", 3, 3)
    m.unit(2, "tank", 25, 15).unit(2, "infantry", 26, 15).unit(2, "mech", 25, 16).unit(2, "artillery", 26, 16)
    g = ctx.start(m, ["andy", spec.id], env=ENV)
    for u in g.units(2):
        if u["x"] >= 25:
            set_unit(g, u["x"], u["y"], hp=45)
    modes = set()

    def watch(gg):
        for _ in range(200):
            gg.e.wait(10)
            modes.add(gg.player(2)["co_mode"])
            if gg.current_army() != 2:
                break
    healed = None
    for turn in range(3):
        cost = g.charge_power(2, which)
        before = {u["id"]: u["hp"] for u in g.units(2) if u["x"] >= 22}
        g.end_turn(observe=watch)
        if g.player(2)["powers_used"]:
            ids = [i for i in before if g.unit(i)["type"]]
            healed = {i: (before[i], g.unit(i)["hp"]) for i in ids}
            break
    p = g.player(2)
    log = [l for l in g.e.decisions() if l.startswith("dsai power")]
    chk(ctx, label, p["powers_used"] == 1, f"the computer fired {name}'s {which} on turn {turn + 1} (powers used {p['powers_used']}, modes seen {sorted(modes)}) {log[-1] if log else ''}", "cpu")
    chk(ctx, label, mode in modes, f"power mode {mode} was seen during its turn", "cpu")
    if name == "lili":
        left, army, rolled = lili_state(g)
        chk(ctx, label, left > 0 and army == 2 and rolled in ROLLED and weather_of(g) == ROLLED[rolled], f"the computer's Enigma is running: {left} turn starts left, weather {weather_of(g)}", "cpu")
    if healed and spec.heal[mode]:
        got = sorted(h[1] for h in healed.values() if h[0] == 45)
        want = [_heal(45, spec.heal[mode])] * len(got)
        chk(ctx, label, got and all(abs(a - b) <= 0 for a, b in zip(got, want)) or any(h[1] > 45 for h in healed.values()), f"its hurt units were healed: {healed}", "cpu")
    return g


def cpu_tag(ctx, act, par):
    """The computer plays `act` with `par` as its partner and both meters full: it uses the Tag Power on its turn (the pair's phase goes 1 then 2 and both Super Powers run)."""
    from . import tag, ram
    from tests.test_tag import fill
    install_tag_spec()
    a_id, b_id = cospec.co_id(act), cospec.co_id(par)
    label = f"{act.split(':')[-1]} tag"
    m = ctx.map()
    m.unit(1, "tank", 3, 3)
    m.unit(2, "tank", 25, 15).unit(2, "infantry", 26, 15)
    g = ctx.start(m, ["andy", a_id], env=ENV) if False else None
    from tests.test_tag import co_page_log
    g = ctx.boot_teams(m, env=dict(ENV, TANGOAW2_CO_PAGE_LOG=co_page_log(ctx)))
    tag.set_teams_partner(g.e, 2, b_id)
    g.set_teams(["andy", a_id], {1})
    g.teams_to_rules()
    g.set_rules(fog=False)
    g.start_battle()
    g.wait_for_input()
    seen = set()
    from tests.test_crumb import set_unit
    for u in g.units(2):
        if u["x"] >= 20:
            set_unit(g, u["x"], u["y"], hp=45)      # (Andy's profile, which Clone Andy has, uses a power only with a hurt unit of his own)

    def watch(gg):
        for _ in range(300):
            gg.e.wait(10)
            t = tag.partner(gg.e, 2)
            seen.add((t["phase"] if t else None, gg.player(2)["co"], gg.player(2)["co_mode"]))
            if gg.current_army() != 2:
                break
    for turn in range(3):
        fill(g, 2)
        g.end_turn(observe=watch)
        t = tag.partner(g.e, 2)
        if t and t["uses"]:
            break
    phases = sorted({s[0] for s in seen if s[0] is not None})
    cos_in_power = {s[1] for s in seen if s[2] == 2}
    chk(ctx, label, 1 in phases or 2 in phases, f"the computer used the Tag Power {act}+{par} on turn {turn + 1}: phases seen {phases}", "cpu")
    chk(ctx, label, {a_id, b_id} <= cos_in_power, f"both COs' Super Powers ran on its turn (COs in Super Power: {sorted(cos_in_power)})", "cpu")
    return g


# --- Clone Andy beside Andy: the before / after of his own numbers --------------------------------------------------------------------------

def measure_moves(g, lanes, bases):
    """The farthest cell each lane's unit can reach (scanning from its base move up, at most 4 more)."""
    out = {}
    for t, y in lanes.items():
        reach = 0
        for extra in range(0, 5):
            if probe_move(g, (3, y), (3 + bases[t] + extra, y)):
                reach = bases[t] + extra
            else:
                break
        out[t] = reach
    return out


def clone_vs_andy(ctx, mode):
    """Andy (before) and Clone Andy (after) play the same fights (every unit class, both sides) and the same moves at power level `mode`. Each fight's numbers are logged
    side by side (`before/after` lines: base damage and defence) and checked: his attacks hit at least as hard with the target's defence unchanged, his units' defence is Andy's plus
    the specification's difference (cos/cloneandy.toml, the power's own +10 being the same for both), and every unit moves as far as Andy's less Andy's own Super Power move (+1)."""
    results = {}
    for name in ("andy", "cloneandy"):
        ctx.rows = []
        stat_fights(ctx, name, mode)
        rows = ctx.rows
        ctx.rows = None
        rules = use_spec(ctx)
        m = ctx.map()
        lanes, bases = {}, {}
        for k, t in enumerate(MOVERS):
            y = 1 + k
            lanes[t], bases[t] = y, rules.unit(t)["move"]
            for x in range(3, 28):
                m.terrain(x, y, "sea" if t in NAV else "road")
            m.unit(1, t, 3, y)
        g = ctx.start(m, [cospec.IDS[name], "andy"], env=ENV)
        if mode:
            ctx.power(g, 1, POWER[mode])
        results[name] = (rows, measure_moves(g, lanes, bases))
        g.e.close()
    (ra, ma), (rc, mc) = results["andy"], results["cloneandy"]
    label = f"cloneandy {LEVEL[mode]}"
    spec = cospec.get("cloneandy")
    chk(ctx, label, len(ra) == len(rc) and all(a["detail"] == c["detail"] for a, c in zip(ra, rc)), f"{len(rc)} fights, the same as Andy's", "fights")
    for a, c in zip(ra, rc):
        ctx.log(f"before/after [{label}] {c['detail']}: base damage Andy {a['base']} -> Clone Andy {c['base']}, defence {a['defence']} -> {c['defence']}")
        if " attacks " in c["detail"]:
            ok = c["base"] >= a["base"] and c["defence"] == a["defence"]
            chk(ctx, label, ok, f"{c['detail']}: base damage {a['base']} -> {c['base']}, the target's defence {c['defence']} as against Andy", "vs andy")
        else:
            want = a["defence"] + spec.sum(mode, _type_of(c["detail"]), "defence")
            ok = c["defence"] == want and c["base"] <= a["base"]
            chk(ctx, label, ok, f"{c['detail']}: defence {a['defence']} -> {c['defence']} (specification {want}), damage taken {a['base']} -> {c['base']}", "vs andy")
    want_moves = {t: ma[t] - (1 if mode == 2 else 0) for t in ma}
    chk(ctx, label, mc == want_moves, f"moves are Andy's{' less his Hyper Upgrade +1' if mode == 2 else ''}: {mc}" + ("" if mc == want_moves else f" (want {want_moves})"), "move")


def _type_of(detail):
    """The unit type a fight's detail line starts with ("Tank defends against B Copter")."""
    best = None
    for t in range(1, 27):
        n = name_of(t)
        if n and detail.startswith(n + " ") and (best is None or len(n) > len(name_of(best))):
            best = t
    return best


# --- the Megatank and the Piperunner are vehicles (the user's answer): pinned by comparison with Andy, whose numbers on them are the game's own --------------------------------------

def vehicle_probe(ctx, name, mode):
    """Megatank (4) and Piperunner (9) of `name` at power level `mode`: the farthest cell each reaches on a road lane, the base damage of an attack on an Andy Tank (Piperunner from
    distance 2), and whether the Piperunner's Fire reaches an enemy at distance 5 and at 6. Returns a dict."""
    spec = cospec.get(name)
    use_spec(ctx)
    m = ctx.map()
    for k, t in enumerate((4, 9)):
        for x in range(3, 28):
            m.terrain(x, 1 + 2 * k, "road" if t == 4 else "pipe")        # (the Piperunner moves on pipes only)
        m.unit(1, t, 3, 1 + 2 * k)
    m.unit(1, 4, 5, 9).unit(2, 5, 6, 9)                 # Megatank beside a Tank
    m.unit(1, 9, 5, 12).unit(2, 5, 7, 12)               # Piperunner two cells from a Tank
    m.unit(1, 9, 3, 15).unit(2, 1, 8, 15)               # an enemy at distance 5
    m.unit(1, 9, 3, 19).unit(2, 1, 9, 19)               # an enemy at distance 6
    g = ctx.start(m, [spec.id, "andy"], env=ENV)
    if mode:
        ctx.power(g, 1, POWER[mode])
    out = {"reach": {}, "base": {}, "range": {}}
    for k, t in enumerate((4, 9)):
        reach = 0
        for d in range(1, 16):
            if probe_move(g, (3, 1 + 2 * k), (3 + d, 1 + 2 * k)):
                reach = d
            else:
                break
        out["reach"][t] = reach
    for t, src, tgt in ((4, (5, 9), (6, 9)), (9, (5, 12), (7, 12))):
        g.attack(src, src, tgt)
        out["base"][t] = ctx.battle_records(g)[0]["base"]
    for y, d in ((15, 5), (19, 6)):
        names = g.action_menu_at(3, y)
        out["range"][d] = any(n.lower().startswith("fire") and "(greyed)" not in n for n in names)
    return out


def pin_vehicles(ctx, name):
    """A CO's flat bonuses (Tabitha's and Caulder's +18%, Lili's +10% and her Enigma move) apply to the Megatank and the Piperunner as to a Tank: the same move, base damage and the Piperunner's range
    as Andy's units plus the specification's bonus (the `stats` facet cannot play them: they are not in the unit table the calculator reads)."""
    spec = cospec.get(name)
    base = vehicle_probe(ctx, "andy", 0)
    chk(ctx, f"{name} d2d", base["range"] == {5: True, 6: False}, f"Andy's Piperunner reaches 5 and not 6 (control): {base['range']}", "vehicles")
    for mode in spec.levels_played:
        got = vehicle_probe(ctx, name, mode)
        label = tag(name, mode)
        for t in (4, 9):
            want_move = base["reach"][t] + spec.bonus(mode, 5, 2)
            chk(ctx, label, got["reach"][t] == want_move, f"{name_of(t)} moves {got['reach'][t]} (Andy {base['reach'][t]}, the vehicle bonus {spec.bonus(mode, 5, 2):+d})", "vehicles")
            want_base = max(1, damage.div(base["base"][t] * (100 + spec.bonus(mode, 5, 0)), 100))
            chk(ctx, label, got["base"][t] == want_base, f"{name_of(t)}'s base damage {got['base'][t]} (Andy {base['base'][t]}, a Tank's {spec.bonus(mode, 5, 0):+d}% -> {want_base})", "vehicles")
        chk(ctx, label, got["range"] == {5: True, 6: False}, f"the Piperunner's range is Andy's (reaches 5 {got['range'][5]}, 6 {got['range'][6]})", "vehicles")


# --- the HQ follows the CO (`hq = "emerald_sun"` in the CO's data file) ----------------------------------------------------------------------

SKIN_HQ = {"emerald_sun": 0x09FD0400}        # army_skin::hq_art(skin, clear): where the committed HQ picture (8 tiles) of the skin is kept in the ROM image
OBJ_VRAM = 0x06010000


def hq_tiles(g):
    """The OBJ tile memory as 32-byte tiles."""
    return g.e.read(OBJ_VRAM, 0x8000)


def find_art(vram, art):
    return [i for i in range(0, len(vram) - len(art) + 1, 32) if vram[i:i + len(art)] == art]


def hq_check(ctx, g, label, skin_armies=()):
    """The HQ pictures in OBJ VRAM: every army whose CO's data file names a skin HQ (and every army in `skin_armies`, those wearing the skin) has that skin's HQ picture in its slot of the
    sheet; the picture is in VRAM exactly as many times as armies show it. Returns the number of armies expected to show it."""
    vram = hq_tiles(g)
    shown = 0
    for a in range(1, 6):
        try:
            p = g.player(a)
        except Exception:
            continue
        if not p["raw"][0x1B]:                  # (no such army in this game)
            continue
        if cospec.hq_style_of_id(p["co"]) == "emerald_sun" or a in skin_armies:
            shown += 1
    expected = g.e.read(SKIN_HQ["emerald_sun"], 0x100)
    found = find_art(vram, expected)
    chk(ctx, label, len(found) == shown, f"the Silver Nova HQ picture is in the OBJ tiles {len(found)} time(s) (tiles {[f // 32 for f in found]}); armies whose CO's data file says hq = emerald_sun"
        f"{' or that wear the skin' if skin_armies else ''}: {shown}", "hq")
    chk(ctx, label, len(set(expected)) > 3, "the skin's committed HQ picture is there to compare with (not empty)", "hq")
    return shown


def hq_versus(ctx, name):
    """A Versus game with `name` leading army 1 against Andy: the HQ matches the CO's data file."""
    spec = cospec.get(name)
    g = ctx.start(ctx.map(), [spec.id, "andy"], env=ENV)
    hq_check(ctx, g, f"{name} d2d")
    g.e.close()
    # Tag: the HQ follows the lead CO
    return g


def hq_tag(ctx):
    """Tag pairs: the lead CO decides (Tabitha leading with Andy, Andy leading with Tabitha)."""
    for lead, par, want in (("tabitha", 1, 1), ("andy", 86, 0)):
        g = tag_battle(ctx, [cospec.IDS[lead], "andy"], [par, None], units=[(1, "tank", 10, 10), (2, "tank", 11, 10)])
        vram = hq_tiles(g)
        found = find_art(vram, g.e.read(SKIN_HQ["emerald_sun"], 0x100))
        chk(ctx, f"{lead} d2d", len(found) == want, f"{lead} leading a pair: the Silver Nova HQ is in the tiles {len(found)} time(s), expected {want} (the HQ follows the lead CO)", "hq")
        g.e.close()


def hq_mission(ctx, n):
    """Silver Nova Campaign mission n: the player's army (it wears the skin) and every army led by a CO with hq = emerald_sun show the Silver Nova HQ."""
    from . import escampaign as es
    e, g, d = es.enter(ctx, n)
    g.e.wait(60)
    shown = hq_check(ctx, g, "tabitha d2d", skin_armies=(1,))
    chk(ctx, "tabitha d2d", shown >= 1, f"M{n}: {shown} army/armies show the Silver Nova HQ", "hq")
    e.close()
