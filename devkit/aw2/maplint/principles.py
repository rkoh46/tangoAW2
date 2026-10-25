"""The map-design principles as rules (MD01..MD08, docs/dev/map-design.md): what Advance Wars By Web's Hall of Fame maps all do, measured by
`study.py` and calibrated so every one of the 43 studied community maps passes, then compared with AW2's and Dual Strike's own maps (campaign and
versus: the games break them more often, so the rules are warnings everywhere and fail only the Emerald Sun maps, as the DQ rules do).

A campaign map is asymmetric: the rules look at the player's side (army 1 and its team) against each enemy side, never at fairness."""
from . import study as st

LIMITS = {
    "density": 5.0,        # MD01 properties per 100 land cells, at least (HoF min 8.5, median 12-14; AW2 p10 5.1, DS p10 4.1)
    "gap": 6,              # MD02 a ground cell this far (Chebyshev) from every property, at most (HoF max 5, median 2; AW2 median 4, p90 7)
    "corridor": 6,         # MD03 the only lane across a cut narrower than this (HoF: never below 8)
    "inf_days": 2,         # MD04 days an enemy infantry needs to reach the player's base or HQ, at least (HoF 2P min 3.5)
    "plain": 0.53,         # MD06 share of land that is plain, at most (HoF max .52, median .31-.33; AW2 p90 .53)
    "river_run": 10,       # MD07 river cells with no bridge or ford, at most (HoF max 9, p90 7; AW2 p90 11)
    "by_road": 0.5,        # MD08 share of properties with a road within 2 cells, at least (HoF min .52)
}


def _p(rule, x, y, msg):
    from .rules import Problem
    return Problem(rule, x, y, msg)


def checks(G):
    """MD01..MD08 on a linter Grid (its MapData)."""
    return check_study(st.from_mapdata(G.m))


def check_study(sm):
    """MD01..MD08 on a StudyMap (any source, AWBW grids too: the calibration in `aw2dev maps study`)."""
    L = LIMITS
    out = []
    props = sm.cells(st.PROPS)
    land = sum(1 for y in range(sm.h) for x in range(sm.w) if sm.g[y][x] not in "~r")
    if land >= 60:
        d = 100 * len(props) / land
        if d < L["density"]:
            out.append(_p("MD01", -1, -1, f"{len(props)} properties on {land} land cells ({d:.1f} per 100; at least {L['density']}: the Hall of Fame's are 8.5 to 22, AW2's median 11.6)"))
    if props:
        gap, cell = 0, None
        for y in range(sm.h):
            for x in range(sm.w):
                if st.FOOT.get(sm.g[y][x]) is None or _massif(sm, x, y):
                    continue
                dd = min(max(abs(x - X), abs(y - Y)) for X, Y in props)
                if dd > gap:
                    gap, cell = dd, (x, y)
        if gap > L["gap"]:
            out.append(_p("MD02", cell[0], cell[1], f"ground {gap} cells from the nearest property: a dead corner (at most {L['gap']}; the Hall of Fame's farthest is 5)"))
    sd = st.sides_of(sm)
    for s1, s2 in st.pairs(sm):
        a, b = st.anchor(sm, sd[s1]), st.anchor(sm, sd[s2])
        if not a or not b:
            continue
        # MD03: never one narrow corridor (a cut mostly across water is a naval front: skipped)
        for cut in st.cuts(sm, a, b):
            ground = [c for c in cut if sm.at(*c) not in "~r,"]
            if len(ground) < L["corridor"] or len(ground) < 0.5 * len(cut):
                continue
            ln = st.lanes_on(sm, cut)
            if len(ln) == 1 and ln[0] < L["corridor"]:
                mid = cut[len(cut) // 2]
                out.append(_p("MD03", mid[0], mid[1], f"the only way between army {sd[s1][0]}'s side and army {sd[s2][0]}'s is a corridor {ln[0]} cells wide (at least two ways, or one {L['corridor']} wide)"))
                break
        # MD05: something to fight over in the middle
        mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        hd = abs(a[0] - b[0]) + abs(a[1] - b[1])
        rad = max(3, 0.2 * hd)
        if hd >= 8 and not any(abs(x - mx) + abs(y - my) <= rad for x, y in props):
            out.append(_p("MD05", round(mx), round(my), f"no property within {rad:.0f} cells of the middle between army {sd[s1][0]}'s side and army {sd[s2][0]}'s: nothing to contest"))
    # MD04: the player's (or, on a symmetric map, any side's) production and HQ out of reach of an enemy infantry on day 1
    out += _base_safety(sm, sd)
    landc = [(x, y) for y in range(sm.h) for x in range(sm.w) if sm.g[y][x] not in "~r"]
    plain = sum(1 for x, y in landc if sm.g[y][x] == ".") / max(1, len(landc))
    if len(landc) >= 60 and plain > L["plain"]:
        out.append(_p("MD06", -1, -1, f"{plain:.0%} of the land is plain (at most {L['plain']:.0%}; the Hall of Fame's median is 31%): open field with nothing to hold"))
    for comp in st._comps(sm, "-"):
        if len(comp) > L["river_run"]:
            c = sorted(comp)[len(comp) // 2]
            out.append(_p("MD07", c[0], c[1], f"{len(comp)} river cells with no bridge or ford (at most {L['river_run']}; the Hall of Fame's longest is 9)"))
    if len(props) >= 6:
        road = set(sm.cells("R="))
        by = sum(1 for x, y in props if any((X, Y) in road for X in range(x - 2, x + 3) for Y in range(y - 2, y + 3))) / len(props)
        if by < L["by_road"]:
            out.append(_p("MD08", -1, -1, f"only {by:.0%} of the properties have a road within 2 cells (at least {L['by_road']:.0%}): roads should lead to what is worth taking"))
    return out


def _massif(sm, x, y):
    """Inside a mountain mass (a mountain with mountains, sea or the map edge all round): terrain, not ground anyone fights over."""
    return sm.g[y][x] == "^" and all(sm.at(x + dx, y + dy) in "^~r|" for dx in (-1, 0, 1) for dy in (-1, 0, 1))


def _base_safety(sm, sd):
    out = []
    side_of = {a: s for s, arms in sd.items() for a in arms}
    if sm.player:
        mine = sm.side.get(sm.player, sm.player)
        guard = [s for s in sd if s == mine]
    else:
        guard = list(sd)
    for s in guard:
        own = [(x, y) for x, y in sm.cells("BH") if side_of.get(sm.own[y][x]) == s]
        if not own:
            continue
        enemy_bases = [(x, y) for x, y in sm.cells("B") if sm.own[y][x] and side_of.get(sm.own[y][x]) != s]
        dist = st.dijkstra(sm, own, st.FOOT)
        for x, y in enemy_bases:
            d = dist.get((x, y))
            if d is not None and -(-d // 3) < LIMITS["inf_days"]:
                out.append(_p("MD04", x, y, f"an infantry built at this enemy base reaches army {s}'s base or HQ in {-(-d // 3)} day(s) (at least {LIMITS['inf_days']})"))
        # (a campaign: the enemy's foot soldiers at the start)
        for u in sm.units:
            if u["kind"] in (1, 2) and side_of.get(u["army"], u["army"]) != s and sm.player:
                d = dist.get((u["x"], u["y"]))
                mv = 3 if u["kind"] == 1 else 2
                if d is not None and d <= mv:
                    out.append(_p("MD04", u["x"], u["y"], f"an enemy {'infantry' if u['kind'] == 1 else 'mech'} starts {d} moves from the player's base or HQ: captured on day 1"))
    return out
