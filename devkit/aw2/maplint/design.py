"""Design-quality metrics and rules ("bad game design", docs/dev/map-lint.md): what makes a map look procedural or play cramped, measured on the tiles and
the map's units and calibrated on AW2's and Dual Strike's own maps (terrain rules, 435 maps) and on the BH Campaign's (the unit rules: only they carry unit
positions). Every metric is a plain function of a `rules.Grid`; `rules.py` calls `checks(G)`, `aw2dev maps rules` prints the hit counts per source, and
`LIMITS` are the thresholds, each the level the games' own maps (almost) never pass."""

PROPS = set("HBCAPT")
PASSABLE_FOOT = set(".R=,fHBCAPTM")      # ground a foot soldier can stand on (plus the shoal), mountain and river aside
PASSABLE_VEH = set(".R=,HBCAPTM")        # ground a vehicle can drive on (wood, mountain and river are not)
OPEN = set(".")


def longest_run(G, chars):
    """The longest straight (row or column) run of cells in `chars`: (length, x, y, horizontal)."""
    best = (0, -1, -1, True)
    for y in range(G.h):
        n = 0
        for x in range(G.w + 1):
            if x < G.w and G.g[y][x] in chars:
                n += 1
                if n > best[0]:
                    best = (n, x - n + 1, y, True)
            else:
                n = 0
    for x in range(G.w):
        n = 0
        for y in range(G.h + 1):
            if y < G.h and G.g[y][x] in chars:
                n += 1
                if n > best[0]:
                    best = (n, x, y - n + 1, False)
            else:
                n = 0
    return best


def inner_run(G, chars):
    """The longest straight run of `chars` that does not lie along the map's edge row or column: (length, x, y)."""
    best = (0, -1, -1)
    for y in range(1, G.h - 1):
        n = 0
        for x in range(G.w + 1):
            if x < G.w and G.g[y][x] in chars:
                n += 1
                if n > best[0]:
                    best = (n, x - n + 1, y)
            else:
                n = 0
    for x in range(1, G.w - 1):
        n = 0
        for y in range(G.h + 1):
            if y < G.h and G.g[y][x] in chars:
                n += 1
                if n > best[0]:
                    best = (n, x, y - n + 1)
            else:
                n = 0
    return best


def parallel_rows(G, ch, span=4):
    """Rows (or columns) of `span`+ identical cells `ch` that lie side by side in a block of 3+ lines: the machine-made stripe of mountains or woods.
    Returns [(x, y, lines)] one per block (top-left cell)."""
    out, seen = [], set()
    for horiz in (True, False):
        W, H = (G.w, G.h) if horiz else (G.h, G.w)
        def cell(a, b):
            return G.g[b][a] if horiz else G.g[a][b]
        runs = {}
        for b in range(H):
            a = 0
            while a < W:
                if cell(a, b) == ch:
                    s = a
                    while a < W and cell(a, b) == ch:
                        a += 1
                    if a - s >= span:
                        runs[(s, a, b)] = True
                else:
                    a += 1
        for (s, e, b) in sorted(runs, key=lambda r: (r[2], r[0])):
            if (s, e, b, horiz) in seen:
                continue
            lines, bb = 1, b
            while (s, e, bb + 1) in runs:
                bb += 1
                seen.add((s, e, bb, horiz))
                lines += 1
            if lines >= 3:
                out.append((s, b, lines) if horiz else (b, s, lines))
    return out


def empty_window(G, units=()):
    """The largest square window of plain cells with nothing on it (no unit, building or other terrain): (size, x, y)."""
    occ = {(u["x"], u["y"]) for u in units}
    n = [[0] * (G.w + 1) for _ in range(G.h + 1)]
    best = (0, -1, -1)
    for y in range(G.h):
        for x in range(G.w):
            if G.g[y][x] == "." and (x, y) not in occ:
                n[y + 1][x + 1] = 1 + min(n[y][x], n[y][x + 1], n[y + 1][x])
                if n[y + 1][x + 1] > best[0]:
                    k = n[y + 1][x + 1]
                    best = (k, x - k + 1, y - k + 1)
    return best


def blobs(units, min_units=8):
    """Armies whose units fill a solid rectangle: [(army, fill, area, x0, y0)], fill = units / bounding box over 8 or more units."""
    out = []
    for a in sorted({u["army"] for u in units}):
        us = [u for u in units if u["army"] == a]
        if len(us) < min_units:
            continue
        xs, ys = [u["x"] for u in us], [u["y"] for u in us]
        area = (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1)
        out.append((a, len(us) / area, area, min(xs), min(ys)))
    return out


def solid_rect(units):
    """The largest fully occupied rectangle (every cell a unit) of the army's units, as (cells, army, x, y)."""
    best = (0, 0, -1, -1)
    for a in sorted({u["army"] for u in units}):
        occ = {(u["x"], u["y"]) for u in units if u["army"] == a}
        for (x, y) in occ:
            w = 0
            while (x + w, y) in occ:
                w += 1
            hmin = 0
            for h in range(1, 12):
                if all((x + i, y + h - 1) in occ for i in range(w)):
                    hmin = h
                else:
                    break
            for ww in range(w, 1, -1):
                hh = 0
                for h in range(1, 12):
                    if all((x + i, y + h - 1) in occ for i in range(ww)):
                        hh = h
                    else:
                        break
                if ww * hh > best[0]:
                    best = (ww * hh, a, x, y)
    return best


def density(G, units):
    """Units per walkable land cell (a vehicle can drive on it), over the whole map."""
    land = sum(1 for y in range(G.h) for x in range(G.w) if G.g[y][x] in PASSABLE_VEH)
    return len(units) / max(1, land), land


def components(G, chars):
    return G.comps(chars)


def rect_share(G, chars="^f", min_cells=6):
    """(rectangles, components of 6+ cells) among the connected patches of `chars`: a patch that fills its bounding box exactly is a drawn block, not terrain."""
    rects, total, first = 0, 0, None
    for ch in chars:
        for comp in G.comps(ch):
            if len(comp) < min_cells:
                continue
            total += 1
            xs, ys = [c[0] for c in comp], [c[1] for c in comp]
            if len(comp) == (max(xs) - min(xs) + 1) * (max(ys) - min(ys) + 1):
                rects += 1
                first = first or (min(xs), min(ys))
    return rects, total, first


def bends(G, ch):
    """(bends, cells, longest straight run) of the line-like terrain `ch` (road or river): a bend is a cell with one neighbour on each axis."""
    cells = [(x, y) for y in range(G.h) for x in range(G.w) if G.g[y][x] == ch]
    n = 0
    for x, y in cells:
        h = G.at(x - 1, y) == ch or G.at(x + 1, y) == ch
        v = G.at(x, y - 1) == ch or G.at(x, y + 1) == ch
        if h and v:
            n += 1
    return n, len(cells)


def feature_share(G):
    """Fraction of land cells (not sea, shoal, reef) that are not plain: how much terrain there is to fight over."""
    land = [G.g[y][x] for y in range(G.h) for x in range(G.w) if G.g[y][x] not in "~r,"]
    return sum(1 for c in land if c != ".") / max(1, len(land))


def open_share(G, units=(), r=2):
    """Fraction of land cells whose (2r+1) square is all plain and empty: open field with no cover at all."""
    occ = {(u["x"], u["y"]) for u in units}
    n = k = 0
    for y in range(G.h):
        for x in range(G.w):
            if G.g[y][x] in "~r,":
                continue
            n += 1
            if all(G.at(x + i, y + j) == "." and (x + i, y + j) not in occ for i in range(-r, r + 1) for j in range(-r, r + 1)):
                k += 1
    return k / max(1, n)


def frontage(G, units, teams=None, chars=None):
    """The narrowest line of vehicle-passable cells between the two strongest sides (side: a team, or an army when the map names none): the width the
    armies must fight through. The axis joins the sides' unit centroids; at each point between 30% and 70% of it, the cells within half a cell of the
    perpendicular line through that point. Returns (width, units of the smaller side, x, y of the narrowest point) or None with fewer than two sides."""
    side_of = (lambda a: teams.get(a, a)) if teams else (lambda a: a)
    sides = {}
    for u in units:
        sides.setdefault(side_of(u["army"]), []).append(u)
    if len(sides) < 2:
        return None
    two = sorted(sides.values(), key=len, reverse=True)[:2]
    cx = [sum(u["x"] for u in s) / len(s) for s in two]
    cy = [sum(u["y"] for u in s) / len(s) for s in two]
    dx, dy = cx[1] - cx[0], cy[1] - cy[0]
    d = (dx * dx + dy * dy) ** 0.5
    if d < 3:
        return None
    dx, dy = dx / d, dy / d
    best = None
    for k in range(9):
        t = 0.3 + 0.05 * k * 1.0
        px, py = cx[0] + dx * d * t, cy[0] + dy * d * t
        n = 0
        for y in range(G.h):
            for x in range(G.w):
                if abs((x - px) * dx + (y - py) * dy) <= 0.5 and G.g[y][x] in (chars or PASSABLE_VEH | set("f^-")):
                    n += 1
        if best is None or n < best[0]:
            best = (n, round(px), round(py))
    return best[0], min(len(s) for s in two), best[1], best[2]


# ---------------------------------------------------------------- the rules

LIMITS = {
    "river_straight": 10,       # a river this long with no bend at all (AW2: a tenth of the maps with a river of 8+ cells have none, none this long)
    "rect_patches": 3,          # drawn rectangles of mountain or wood (AW2: none or one a map, at most 6)
    "stripes": 3,               # blocks of 3+ parallel runs of 4+ identical cells (AW2: p99 2)
    "sparse": 0.36,             # share of land that is not plain (AW2 p10 .43)
    "empty": 6,                 # an empty plain window this wide (AW2 p99 5)
    "road_run": 27,             # a straight road this long (AW2 max 27)
    "blob_cells": 9,            # a solid rectangle of one army's units this big (BH: 4 of 35 maps)
    "blob_fill": 0.75,          # an army of 10+ units filling this much of its bounding box
    "density": 0.17,            # units per vehicle-walkable cell (BH p70; the campaign's own big battles .07 to .17)
    "front_ratio": 1.25,        # units of the smaller side per cell of frontage (BH median .8)
    "mountain_run": 11,         # a straight line of mountains this long away from the map edge (AW2 p95 10)
    "landing": 6,               # shore cells a Lander can unload on
}


def _p(rule, x, y, msg):
    from .rules import Problem
    return Problem(rule, x, y, msg)


def teams_of(m):
    tm = m.meta.get("team")
    return {i + 1: t for i, t in enumerate(tm)} if tm else None


def checks(G):
    """The design-quality rules (all warnings): RV05 DQ01..DQ10 SP01."""
    out = []
    m = G.m
    units = m.units or []
    L = LIMITS
    # a river that never bends
    rb, rc = bends(G, "-")
    if rc >= L["river_straight"] and rb == 0:
        c = next(iter(G.cells("-")))
        out.append(_p("DQ01", c[0], c[1], f"a river of {rc} cells with no bend: AW2's rivers wander (median 1.5 bends per 10 cells)"))
    for ch, name in (("^", "mountain"), ("f", "wood")):
        rects, total, first = rect_share(G, ch)
        if rects >= L["rect_patches"] and rects / max(total, 1) >= 0.5:
            out.append(_p("DQ02", first[0], first[1], f"{rects} of {total} {name} patches are exact rectangles (drawn blocks, not terrain)"))
    blocks = parallel_rows(G, "^") + parallel_rows(G, "f")
    if len(blocks) >= L["stripes"]:
        out.append(_p("DQ03", blocks[0][0], blocks[0][1], f"{len(blocks)} blocks of parallel identical rows of mountains or woods: the procedural look"))
    fs = feature_share(G)
    if fs < L["sparse"]:
        out.append(_p("DQ04", -1, -1, f"only {fs:.0%} of the land is not plain (AW2's maps have 43% or more): empty fields and decorative filler"))
    ew = empty_window(G, units)
    if ew[0] >= L["empty"]:
        out.append(_p("DQ05", ew[1], ew[2], f"an empty plain field {ew[0]} x {ew[0]} cells (AW2's largest is 5): a dead corner"))
    rr = longest_run(G, "R")
    if rr[0] >= L["road_run"]:
        out.append(_p("DQ06", rr[1], rr[2], f"a straight road of {rr[0]} cells with no bend or junction"))
    if units:
        sr = solid_rect(units)
        if sr[0] >= L["blob_cells"]:
            out.append(_p("DQ07", sr[2], sr[3], f"army {sr[1]}'s units fill a solid block of {sr[0]} cells: a blob, not a formation"))
        for a, fill, area, x0, y0 in blobs(units, 10):
            if fill >= L["blob_fill"]:
                out.append(_p("DQ07", x0, y0, f"army {a}'s units fill {fill:.0%} of their bounding box"))
    mr = inner_run(G, "^")
    if mr[0] >= L["mountain_run"]:
        out.append(_p("DQ12", mr[1], mr[2], f"a straight line of {mr[0]} mountains: a drawn wall, not a range (AW2's lines are at most {L['mountain_run'] - 1} away from the edge in 95% of its maps)"))
    out += pointless(G)
    out += fairness(G)
    out += hq_pockets(G)
    if units:
        out += space(G, units)
        out += beaches(G, units)
    return out


def pointless(G):
    """DQ08: a property with no road, bridge or other property within 5 cells and no unit: nobody has a reason to go there."""
    out = []
    props = [(x, y) for y in range(G.h) for x in range(G.w) if G.g[y][x] in PROPS and G.g[y][x] != "H"]
    for x, y in props:
        near = [(X, Y) for X in range(x - 5, x + 6) for Y in range(y - 5, y + 6) if (X, Y) != (x, y)]
        if not any(G.at(X, Y) in "R=" or (G.at(X, Y) in PROPS) for X, Y in near):
            out.append(_p("DQ08", x, y, "a property with no road or other property within 5 cells"))
    return out


def hq_pockets(G):
    """DQ09: an HQ (or base) whose surroundings (radius 2) hold fewer than 7 walkable cells: no approach, no room to deploy."""
    out = []
    for x, y in G.cells("H"):
        n = sum(1 for X in range(x - 2, x + 3) for Y in range(y - 2, y + 3) if G.at(X, Y) in PASSABLE_FOOT)
        if n < 7:
            out.append(_p("DQ09", x, y, f"an HQ with only {n} walkable cells around it (radius 2)"))
    return out


def space(G, units):
    """SP01: room to fight: units per walkable cell, and the units of the smaller side per cell of the narrowest frontage between the sides."""
    out = []
    d, land = density(G, units)
    if d > LIMITS["density"]:
        out.append(_p("SP01", -1, -1, f"{len(units)} units on {land} walkable cells ({d:.2f} a cell; the campaign's big battles keep to {LIMITS['density']})"))
    # (the frontage of ground armies only: ships and aircraft cross water and sky)
    ground = [u for u in units if 1 <= u["kind"] <= 15]
    fr = frontage(G, ground, teams_of(G.m)) if len(ground) >= 0.6 * len(units) else None
    if fr and fr[0] > 0 and fr[1] / fr[0] > LIMITS["front_ratio"]:
        out.append(_p("SP01", fr[2], fr[3], f"the smaller side's {fr[1]} units meet a frontage of {fr[0]} cells ({fr[1] / fr[0]:.2f} a cell; keep to {LIMITS['front_ratio']})"))
    fv = frontage(G, ground, teams_of(G.m), PASSABLE_VEH) if fr else None
    if fv and fv[0] == 0 and fr and fr[0] > 0:
        out.append(_p("SP01", fv[2], fv[3], "no vehicle can cross between the sides (only foot ground)"))
    return out


def beaches(G, units):
    """DQ10: a Lander at the start needs a shore it can unload on: land cells beside its sea, at least LIMITS['landing'] of them within 8 cells."""
    out = []
    for u in units:
        if u["kind"] != 23:
            continue
        seen, todo = {(u["x"], u["y"])}, [(u["x"], u["y"])]
        shore = set()
        while todo:
            x, y = todo.pop()
            for dx, dy in D4:
                X, Y = x + dx, y + dy
                c = G.at(X, Y)
                if c in "~r" and (X, Y) not in seen and abs(X - u["x"]) + abs(Y - u["y"]) <= 14:
                    seen.add((X, Y))
                    todo.append((X, Y))
                elif c in PASSABLE_FOOT and abs(X - u["x"]) + abs(Y - u["y"]) <= 12:
                    shore.add((X, Y))
        if len(shore) < LIMITS["landing"]:
            out.append(_p("DQ10", u["x"], u["y"], f"a Lander with only {len(shore)} shore cells to unload on"))
    return out


D4 = ((0, -1), (1, 0), (0, 1), (-1, 0))


def fairness(G):
    """DQ11: a map meant to be fair (the map file's `fair` line, or any Versus map) gives each army about as many properties: the most to the fewest within a third."""
    if not (G.m.meta.get("fair") or G.m.source == "versus"):
        return []
    n = {}
    for y in range(G.h):
        for x in range(G.w):
            o = G.T.owner(G.t[y][x])
            if o and 1 <= o <= 4:
                n[o] = n.get(o, 0) + 1
    if len(n) >= 2 and max(n.values()) > 1.34 * min(n.values()):
        return [_p("DQ11", -1, -1, f"unequal properties per army {dict(sorted(n.items()))} on a map meant to be fair")]
    return []
