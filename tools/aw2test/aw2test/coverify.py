"""Scenarios of `aw2dev co verify`: real Versus battles in which a custom CO's day to day, CO Power, Super Power and Tag Power are played and every number the game produced is
compared with the CO's SPECIFICATION (`aw2test.cospec`: the data files and the design docs), not with the engine's own tables.

Every check is tagged `[<co> <ability>] ...` in the test's log; `aw2dev co verify` collects the tags into the pass / fail table.
Abilities: `d2d`, `cop`, `scop` (stats, rules, heal, funds), `meter` (star costs, the exact meter threshold), `tag` (the Tag Powers), `cpu`, `net`.
"""

from . import cospec, damage
from . import rom as romlib
from .game import NavError

ENV = {"TANGOAW2_ES_VERSUS": "1"}
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
    keep = 75 if (name == "klaus" and mode == 1) else 100
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
    for mode in (1, 2):
        label = tag(name, mode)
        before = {u["id"]: u for u in g.units()}
        f0 = funds(g)
        cost = g.charge_power(1, POWER[mode])
        g.power(POWER[mode])
        after = {u["id"]: u for u in g.units()}
        got = funds(g) - f0
        want = spec.tribute[mode] * props
        chk(ctx, label, got == want, f"funds collected {got} (specification {spec.tribute[mode]} x {props} properties = {want})", "power funds")
        ctx.expect_hp_change(before, after, {1: spec.heal[mode] * 10}, f"{label}: heal {spec.heal[mode]} HP", repair=True)
        mine_ok = all(after[i]["hp"] == before[i]["hp"] for i in before if before[i]["army"] == 2)
        chk(ctx, label, mine_ok, "the enemy's units are not healed", "heal")
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
        for charge, want in ((pc - 1, (False, False)), (pc, (True, False)), (sc - 1, (True, False)), (sc, (True, True))):
            got = offered(charge)
            lab = f"{name} {'cop' if charge < sc - 1 or charge == pc else 'scop'}"
            chk(ctx, lab, got == want, f"after {uses} power(s): meter {charge} of {pc} / {sc} -> Power {got[0]}, Super {got[1]} (want {want[0]}, {want[1]})", "meter threshold")
        if uses == 0:
            ctx.power(g, 1, "power")
            g.end_turn(human=1)
            g.e.w32(addr, 0)
    return g


# --- Tag Powers --------------------------------------------------------------------------------------------------------------------------

_TAG_PATCHED = []


def install_tag_spec():
    """The harness's `tag.compatibility` (Dual Strike's table, Sturm's, Vault Breakers) learns the Emerald Sun pairs from the data file `cos/tags.toml`: a pair with one of the custom
    COs is the file's number, every unlisted one 95 (the file's header: "Every unlisted pair is 95") -- or the neutral 100 for Crumb, whose documented rule it is, and Andy's own for Clone Andy (crate::tag)."""
    from . import tag
    if _TAG_PATCHED:
        return
    table = {frozenset((cospec.co_id(p["a"]), cospec.co_id(p["b"]))): p["compat"] for p in cospec.tags()}
    custom = {s.id for s in cospec.all_specs().values() if s.name not in ("crumb", "varro", "cloneandy")}
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
    """tests.test_tag.tag_battle with the Emerald Sun COs on (ENV) and optionally the economy map."""
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
    if "aurelia" in (a_name, b_name):      # two Artillery with Andy's units round the target (one for each half)
        units += [(1, "artillery", 6, 14), (2, "tank", 9, 14), (2, "infantry", 9, 13), (2, "mech", 10, 14),
                  (1, "artillery", 6, 18), (2, "tank", 9, 18), (2, "infantry", 9, 17), (2, "mech", 10, 18)]
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
        chk(ctx, label, got == s1.tribute[2] * props, f"first half: funds collected {got} (specification {s1.tribute[2]} x {props})", "funds")
    fight(ctx, label, f"first half {a_name}", g, (10, 10), (10, 10), (11, 10))
    special_hook(ctx, g, a_name, label, "first half", (10, 10), (6, 14), (9, 14), [(9, 13), (10, 14)])
    # the second half: Change, the partner's Super Power
    f1 = funds(g)
    set_unit(g, 3, 3, hp=45)
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
        chk(ctx, label, got == s2.tribute[2] * props, f"second half: funds collected {got} (specification {s2.tribute[2]} x {props})", "funds")
    fight(ctx, label, f"second half {b_name}", g, (10, 12), (10, 12), (11, 12))
    special_hook(ctx, g, b_name, label, "second half", (10, 12), (6, 18), (9, 18), [(9, 17), (10, 18)])
    return g


def special_hook(ctx, g, co, label, half, tank_at, art_at, art_target, around):
    """The Super Power's special rule of the CO whose half this is: Aurelia's Onager splash (1 HP to the enemy units beside an Artillery's target), Cassius's Triumph (the Tank that
    attacked is not done and has its extra-move bit)."""
    from tests.test_es_powers import moved_bit
    if co == "aurelia":
        before = {c: g.unit_at(*c)["hp"] for c in around}
        fight(ctx, label, f"{half} Onager", g, art_at, art_at, art_target)
        after = {c: (g.unit_at(*c) or {"hp": 0})["hp"] for c in around}
        chk(ctx, label, all(after[c] == before[c] - 10 for c in around), f"{half}: Onager splash cost the units beside the target 1 HP each: {before} -> {after}", "onager")
    if co == "cassius":
        u = g.unit_at(*tank_at)
        chk(ctx, label, u["flags"] & 1 == 0 and moved_bit(g, u["id"]), f"{half}: Triumph left the Tank that attacked free to move once more (flags {u['flags']:#04x}, extra-move bit {moved_bit(g, u['id'])})", "triumph")


def _heal(hp, bars_up):
    if not bars_up:
        return hp
    for _ in range(bars_up):
        if (hp - 1) // 10 + 1 == 10:
            break
        hp = min(100, hp + 10)
    return ((hp - 1) // 10 + 1) * 10


# --- the special rules: Testudo, Onager, Triumph -------------------------------------------------------------------------------------------

def hook_testudo(ctx):
    """Klaus: in his CO Power the enemy's counterattack against one of his attacks does 25% less (the damage number and the forecast cut to 75%, whole numbers rounded down); with no
    power and in the Super Power the counter is whole; a counter against his Tank when Andy attacks him is not cut."""
    from tests.test_es_powers import klaus_fight, counter_forecast
    use_spec(ctx)
    for mode in (0, 1, 2):
        for kind in ("tank", "infantry", "mech"):
            m = ctx.map()
            m.unit(1, kind, 10, 10).unit(2, kind, 11, 10)
            g = ctx.start(m, [86, "andy"], env=ENV)
            if mode:
                ctx.power(g, 1, POWER[mode])
            keep = 75 if mode == 1 else 100
            r = fight(ctx, f"klaus {LEVEL[mode]}", f"testudo {kind}", g, (10, 10), (10, 10), (11, 10), keep)
            ra, rd = r["records"]
            c = r["counter"]
            if r["after"][1]["hp"] <= 0:
                chk(ctx, f"klaus {LEVEL[mode]}", c is None, f"the enemy {kind} is destroyed and cannot counterattack", f"testudo {kind}")
                g.e.close()
                continue
            chk(ctx, f"klaus {LEVEL[mode]}", c is not None, f"the enemy {kind} counterattacks", f"testudo {kind}")
            if c is None:
                continue
            bars = damage.hp_bars(rd["remaining"])
            rolled = {damage.div(c.acc * c.base, 100) + roll for roll in range(c.luck[0])}
            plain = {damage.div(v * bars, 10) for v in rolled}
            cut = {damage.div(v * 75, 100) for v in plain}
            want = cut if mode == 1 else plain
            chk(ctx, f"klaus {LEVEL[mode]}", rd["damage"] in want and (mode != 1 or rd["damage"] not in plain),
                f"the counter's damage number {rd['damage']} is {'one of the 75% numbers ' + str(sorted(cut)) if mode == 1 else 'whole: one of ' + str(sorted(plain))}", f"testudo {kind}")
            chk(ctx, f"klaus {LEVEL[mode]}", rd["display"] == counter_forecast(r, keep), f"the counter's forecast {rd['display']} is worked on the {'cut' if mode == 1 else 'whole'} number", f"testudo {kind}")
            g.e.close()


def hook_onager(ctx):
    """Aurelia: an indirect hit in her Super Power costs each enemy unit orthogonally beside the target 1 HP (a unit on its last HP stays on it; her own units, the diagonal and
    units two cells away are untouched); no splash with no power or in Ballista, or from a direct unit."""
    from tests.test_es_powers import onager_map, NORTH, EAST, SOUTH, WEST, DIAGONAL, TWO_AWAY, TARGET
    use_spec(ctx)
    for power in (None, "power", "super"):
        mode = {None: 0, "power": 1, "super": 2}[power]
        g = ctx.start(onager_map(ctx), [87, "andy"], env=ENV)
        ctx.set_hp(g, *EAST, 15)
        ctx.set_hp(g, *WEST, 10)
        if power:
            ctx.power(g, 1, power)
        cells = (NORTH, EAST, SOUTH, WEST, DIAGONAL, TWO_AWAY, TARGET)
        before = {c: g.unit_at(*c)["hp"] for c in cells}
        fight(ctx, f"aurelia {LEVEL[mode]}", "onager Artillery hit", g, (10, 10), (10, 10), TARGET)
        after = {c: (g.unit_at(*c) or {"hp": 0})["hp"] for c in cells}
        want = dict(before)
        if power == "super":
            want[NORTH], want[EAST] = before[NORTH] - 10, before[EAST] - 10          # (WEST is on 1 HP: stays; SOUTH is her own)
        label = f"aurelia {LEVEL[mode]}"
        for name, c in (("north (enemy Infantry)", NORTH), ("east (enemy Mech on 2 HP)", EAST), ("west (enemy Recon on 1 HP)", WEST), ("south (her own Infantry)", SOUTH),
                        ("diagonal", DIAGONAL), ("two cells away", TWO_AWAY)):
            chk(ctx, label, after[c] == want[c], f"{name}: {before[c]} -> {after[c]} (specification {want[c]})", "splash")
        g.e.close()
    # a direct unit under Onager: no splash
    m = ctx.map()
    m.unit(1, "tank", 10, 10).unit(2, "tank", 11, 10).unit(2, "infantry", 11, 9).unit(2, "infantry", 12, 10)
    g = ctx.start(m, [87, "andy"], env=ENV)
    ctx.power(g, 1, "super")
    fight(ctx, "aurelia scop", "direct Tank hit", g, (10, 10), (10, 10), (11, 10))
    chk(ctx, "aurelia scop", g.unit_at(11, 9)["hp"] == 100 and g.unit_at(12, 10)["hp"] == 100, "a direct unit's hit splashes nobody", "splash")


def hook_triumph(ctx):
    """Cassius: in his Super Power a Tank that attacked is not done, can move once more (not attack) and is done after; an Infantry is done as ever; with no power or in Charge the
    attacker is done."""
    from tests.test_es_powers import triumph_game, moved_bit, can_select, CASSIUS_AT, TARGET_AT, CONTROL_TANK
    use_spec(ctx)
    for mode in (0, 1, 2):
        label = f"cassius {LEVEL[mode]}"
        m = ctx.map()
        m.unit(1, "tank", *CASSIUS_AT).unit(2, "infantry", *TARGET_AT)
        g = ctx.start(m, [88, "andy"], env=ENV)
        if mode:
            ctx.power(g, 1, POWER[mode])
        uid = g.unit_at(*CASSIUS_AT)["id"]
        fight(ctx, label, "triumph Tank attack", g, CASSIUS_AT, (11, 10), TARGET_AT)
        u = g.unit(uid)
        done = bool(u["flags"] & 1)
        chk(ctx, label, done == (mode != 2), f"after attacking the Tank is {'done' if done else 'not done'} (specification: {'not done' if mode == 2 else 'done'})", "triumph")
        chk(ctx, label, moved_bit(g, uid) == (mode == 2), f"extra-move bit {moved_bit(g, uid)}", "triumph")
        if mode == 2:
            g.select(11, 10)
            names = g.move_to(11, 12)["names"]
            chk(ctx, label, not any(n.lower().startswith("fire") for n in names) and any(n.lower().startswith("wait") for n in names), f"the second move offers {names}: Wait, no Fire", "triumph")
            g.choose("Wait", g.ACTION_MENU)
            g.wait_idle()
            chk(ctx, label, bool(g.unit(uid)["flags"] & 1) and not can_select(g, 11, 12), "and then it is done", "triumph")
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


# --- Cassius's Triumph: where its rule stops (reported as LIMIT lines, not failures: docs/dev/co-verify.md) ---------------------------------------

def triumph_limits(ctx):
    """What Triumph does not cover on this branch: the computer's Cassius never gets the extra move (es_co: its unit loop would fire the unit again), and a game suspended after a Tank
    attacked and continued has lost the extra-move bit (EWRAM state is not in the save). Each is measured and logged as `LIMIT [cassius scop] ...`."""
    import os
    from tests.test_es_powers import moved_bit, triumph_game, CASSIUS_AT, TARGET_AT
    from . import saves
    from .emu import Emu
    from .game import Game
    use_spec(ctx)
    # 1. the computer plays Cassius's Super Power with Tanks next to the player's Infantry
    m = ctx.map()
    m.unit(1, "infantry", 12, 10).unit(1, "infantry", 12, 12)
    m.unit(2, "tank", 13, 10).unit(2, "tank", 13, 12).unit(2, "tank", 16, 10)
    g = ctx.start(m, ["andy", 88], env=ENV)
    seen = {"bit": False, "attacks": 0}
    ids = [u["id"] for u in g.units(2) if u["type"] == 5]

    def watch(gg):
        for _ in range(300):
            gg.e.wait(10)
            if any(moved_bit(gg, i) for i in ids):
                seen["bit"] = True
            if gg.current_army() != 2:
                break
    g.charge_power(2, "super")
    hp0 = sum(u["hp"] for u in g.units(1))
    g.end_turn(observe=watch)
    seen["attacks"] = hp0 - sum(u["hp"] for u in g.units(1) if u["type"])
    ctx.log(f"LIMIT [cassius scop] the computer's Cassius: power mode used {g.player(2)['powers_used']}, his Tanks dealt {seen['attacks']} HP of damage, extra-move bit ever set: {seen['bit']}")
    ctx.log("LIMIT [cassius scop] " + ("the computer's Cassius got an extra move (no limit any more)" if seen["bit"] else "the computer's Cassius never gets the extra move after attacking (es_co::action_done skips computer armies)"))
    g.e.close()
    # 2. suspend after the attack and continue
    m = ctx.map()
    m.unit(1, "tank", *CASSIUS_AT).unit(2, "infantry", *TARGET_AT).unit(2, "infantry", 11, 9)       # (a second enemy beside the cell the Tank attacks from)
    g = ctx.start(m, [88, "andy"], env=ENV)
    ctx.power(g, 1, "super")
    uid = g.unit_at(*CASSIUS_AT)["id"]
    g.attack(CASSIUS_AT, (11, 10), TARGET_AT)
    g.select(11, 10)
    first = g.move_to(11, 10)["names"]
    g.e.press("B", 4)
    g.e.wait(20)
    g.e.press("B", 4)
    g.wait_for_input()
    ctx.log(f"LIMIT [cassius scop] before suspending the Tank's menu beside an enemy offers {first} (Fire hidden by the extra-move bit)")
    before = (bool(g.unit(uid)["flags"] & 1), moved_bit(g, uid))
    saves.suspend(g)
    path = g.e.save(os.path.join(ctx.out, "triumph_saved"))
    e2 = Emu(save=path, ds=True, env=ENV)
    g2 = Game(e2)
    ctx.games.append(g2)
    saves.to_select_mode(e2)
    saves.versus_continue(g2)
    after = (bool(g2.unit(uid)["flags"] & 1), moved_bit(g2, uid))
    ctx.log(f"LIMIT [cassius scop] suspend and continue after a Tank attacked: (done flag, extra-move bit) {before} -> {after}")
    if after[1] and not after[0]:
        ctx.log("LIMIT [cassius scop] the extra-move bit survives suspend and continue (no limit any more)")
    elif not after[1] and not after[0]:
        g2.select(11, 10)
        names = g2.move_to(11, 10)["names"]
        fire = any(n.lower().startswith("fire") and "(greyed)" not in n for n in names)
        ctx.log(f"LIMIT [cassius scop] after continue the Tank is free but the bit is gone: its menu offers {names}" + (" -- Fire is offered: a second attack" if fire else ""))
    else:
        ctx.log("LIMIT [cassius scop] after continue the Tank is done: its extra move is lost")
    return before, after


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
    """Cassius's vehicle move and attack bonuses apply to the Megatank and the Piperunner as to a Tank; Aurelia's vehicle penalty applies to both, and neither gets her indirect bonus or her range."""
    spec = cospec.get(name)
    base = vehicle_probe(ctx, "andy", 0)
    chk(ctx, f"{name} d2d", base["range"] == {5: True, 6: False}, f"Andy's Piperunner reaches 5 and not 6 (control): {base['range']}", "vehicles")
    for mode in (0, 1, 2):
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
    chk(ctx, label, len(found) == shown, f"the Emerald Sun HQ picture is in the OBJ tiles {len(found)} time(s) (tiles {[f // 32 for f in found]}); armies whose CO's data file says hq = emerald_sun"
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
    """Tag pairs: the lead CO decides (Klaus leading with Andy, Andy leading with Klaus)."""
    for lead, par, want in (("klaus", 1, 1), ("andy", 86, 0)):
        g = tag_battle(ctx, [cospec.IDS[lead], "andy"], [par, None], units=[(1, "tank", 10, 10), (2, "tank", 11, 10)])
        vram = hq_tiles(g)
        found = find_art(vram, g.e.read(SKIN_HQ["emerald_sun"], 0x100))
        chk(ctx, f"{lead} d2d", len(found) == want, f"{lead} leading a pair: the Emerald Sun HQ is in the tiles {len(found)} time(s), expected {want} (the HQ follows the lead CO)", "hq")
        g.e.close()


def hq_mission(ctx, n):
    """Emerald Sun Campaign mission n: the player's army (it wears the skin) and every army led by a CO with hq = emerald_sun show the Emerald Sun HQ."""
    from . import escampaign as es
    e, g, d = es.enter(ctx, n)
    g.e.wait(60)
    shown = hq_check(ctx, g, "klaus d2d", skin_armies=(1,))
    chk(ctx, "klaus d2d", shown >= 1, f"M{n}: {shown} army/armies show the Emerald Sun HQ", "hq")
    e.close()
