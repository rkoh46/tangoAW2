"""Map design study (`aw2dev maps study`, docs/dev/map-design.md): measures what makes a map play well, on any map: Advance Wars By Web grids (the
community's Hall of Fame, read from a folder the user fetched: nothing of them is stored in the repo), tangoAW2's Emerald Sun and BH Campaign maps,
and AW2's and Dual Strike's own (read from the user's ROMs at run time).

A map is studied as a `StudyMap`: a grid of terrain characters (the linter's: `. f ^ R - = ~ , r I Z M H B C A P T`, plus `L` lab, `m` a fired silo, `X`
a teleport tile), an owner per cell (0 neutral, else the army), the armies' sides (a team, or the army) and the units. `measure(sm)` returns a flat
dict of numbers; `summary(rows)` the median and the 10th and 90th percentile of each over a set. The principles and the lint rules built on them
(`design.py`: MD01..MD06) quote these numbers.

AWBW terrain ids (confirmed against AWBW's own map pages: the preview's tile names and the map API's country codes, Oct 2026):
1 plain, 2 mountain, 3 wood, 4-14 river, 15-25 road, 26-27 bridge, 28 sea, 29-32 shoal, 33 reef, 34-37 neutral city/base/airport/port,
38-57 and 81-100 the first eight armies in groups of five (city, base, airport, port, HQ), 101-110 pipe, 111 silo, 112 fired silo, 113-114 seam,
115-116 broken seam, 117-126 Amber Blaze and Jade Sun in groups of five (airport, base, city, HQ, port), 127-137 com towers (133 neutral),
138-148 labs (145 neutral), 149 onwards the later armies in groups of seven (airport, base, city, com tower, HQ, lab, port; 195 is the teleport tile).
"""
import heapq, math, re, statistics
from dataclasses import dataclass, field
from pathlib import Path

D4 = ((0, -1), (1, 0), (0, 1), (-1, 0))
WATER = set("~r")
INCOME = set("HBCAP")                  # properties that pay 1000 a day (AW2 and AWBW)
PROPS = set("HBCAPTL")                 # properties (com towers and labs too)
PROD = set("BAP")                      # production
# movement cost: foot (infantry) and treads (tank); None = cannot enter
FOOT = {".": 1, "f": 1, "^": 2, "R": 1, "-": 2, "=": 1, ",": 1, "M": 1, "m": 1, "H": 1, "B": 1, "C": 1, "A": 1, "P": 1, "T": 1, "L": 1, "Z": None, "I": None}
TREAD = {".": 1, "f": 2, "R": 1, "=": 1, ",": 1, "M": 1, "m": 1, "H": 1, "B": 1, "C": 1, "A": 1, "P": 1, "T": 1, "L": 1}
VEH_BLOCK = set("^-~rIZ#?X|")          # a vehicle cannot cross (splits lanes)


# ------------------------------------------------------------------ AWBW grids

FIVE_GROUPS = {38: "OS", 43: "BM", 48: "GE", 53: "YC", 81: "RF", 86: "GS", 91: "BH", 96: "BD"}       # city, base, airport, port, HQ
FIVE_GROUPS_B = {117: "AB", 122: "JS"}                                                            # airport, base, city, HQ, port
SEVEN_GROUPS = {149: "CI", 156: "PC", 163: "TG", 170: "PL", 181: "AR", 188: "WN", 196: "AA", 203: "NE", 210: "SC", 217: "UW"}  # airport, base, city, tower, HQ, lab, port
LABS = {138: "AB", 139: "BH", 140: "BM", 141: "BD", 142: "GE", 143: "GS", 144: "JS", 146: "OS", 147: "RF", 148: "YC"}


def awbw_char(t):
    """(terrain character, army code) for an AWBW terrain id; army "" for neutral ground and buildings, "?" for an army's com tower (owner unknown:
    given to the nearest player)."""
    if t == 1: return ".", ""
    if t == 2: return "^", ""
    if t == 3: return "f", ""
    if 4 <= t <= 14: return "-", ""
    if 15 <= t <= 25: return "R", ""
    if t in (26, 27): return "=", ""
    if t == 28: return "~", ""
    if 29 <= t <= 32: return ",", ""
    if t == 33: return "r", ""
    if 34 <= t <= 37: return "CBAP"[t - 34], ""
    for b, a in FIVE_GROUPS.items():
        if b <= t < b + 5: return "CBAPH"[t - b], a
    for b, a in FIVE_GROUPS_B.items():
        if b <= t < b + 5: return "ABCHP"[t - b], a
    for b, a in SEVEN_GROUPS.items():
        if b <= t < b + 7: return "ABCTHLP"[t - b], a
    if 101 <= t <= 110: return "I", ""
    if t == 111: return "M", ""
    if t == 112: return "m", ""
    if t in (113, 114): return "Z", ""
    if t in (115, 116): return ".", ""
    if t == 133: return "T", ""
    if 127 <= t <= 137: return "T", "?"
    if t == 145: return "L", ""
    if t in LABS: return "L", LABS[t]
    if t == 195: return "X", ""
    return "?", ""


@dataclass
class StudyMap:
    name: str
    source: str
    g: list                        # rows of terrain characters
    own: list                      # rows of owners: 0 neutral, else army 1..n
    side: dict = field(default_factory=dict)   # army -> side (team); default the army
    units: list = field(default_factory=list)
    player: int = 0                # a campaign's player army (0: a symmetric map)
    meta: dict = field(default_factory=dict)

    @property
    def w(self): return len(self.g[0])

    @property
    def h(self): return len(self.g)

    def at(self, x, y):
        return self.g[y][x] if 0 <= x < self.w and 0 <= y < self.h else "|"

    def cells(self, chars):
        return [(x, y) for y in range(self.h) for x in range(self.w) if self.g[y][x] in chars]

    def hqs(self):
        return {self.own[y][x]: (x, y) for x, y in self.cells("H") if self.own[y][x]}


def parse_awbw(path):
    """Maps of a study file: `# <id> players=N size=WxH [name=...] cats=...` then CSV rows of AWBW ids."""
    out, cur = [], None
    for line in Path(path).read_text().splitlines():
        if line.startswith("#"):
            m = re.match(r"#\s*(\d+)\s+players=(\d+)", line)
            if m:
                nm = re.search(r"name=(.*?)\s+cats=", line)
                cur = {"id": int(m.group(1)), "players": int(m.group(2)), "name": nm.group(1).strip() if nm else m.group(1), "rows": [], "head": line}
                out.append(cur)
        elif cur is not None and re.match(r"^\s*\d+(,\d+)+\s*$", line):
            cur["rows"].append([int(v) for v in line.strip().split(",")])
    return [awbw_study(m) for m in out if m["rows"]]


def awbw_study(m):
    """A StudyMap from a parsed AWBW grid: armies numbered 1..n in reading order of their HQs (a map with labs and no HQs: of their labs)."""
    rows = m["rows"]
    g = [[awbw_char(t)[0] for t in r] for r in rows]
    key = [[awbw_char(t)[1] for t in r] for r in rows]
    h, w = len(g), len(g[0])
    order = []
    for ch in "HL":
        for y in range(h):
            for x in range(w):
                if g[y][x] == ch and key[y][x] not in ("", "?") and key[y][x] not in order:
                    order.append(key[y][x])
    num = {k: i + 1 for i, k in enumerate(order)}
    seat = {}
    for ch in "HL":
        for y in range(h):
            for x in range(w):
                if g[y][x] == ch and key[y][x] in num:
                    seat.setdefault(num[key[y][x]], (x, y))
    own = [[0] * w for _ in range(h)]
    for y in range(h):
        for x in range(w):
            k = key[y][x]
            if k in num:
                own[y][x] = num[k]
            elif k and seat:
                # (an army's com tower, or an army with no HQ or lab here: the nearest player)
                own[y][x] = min(seat, key=lambda a: abs(seat[a][0] - x) + abs(seat[a][1] - y))
    name = re.sub(r"\s+", " ", m["name"])
    side = {}
    if len(seat) == 4 and re.search(r"2\s*v(s)?\s*2", name, re.I):
        # (a 2 vs 2 map: team-mates are each other's nearest seat)
        near = {a: min((b for b in seat if b != a), key=lambda b: abs(seat[a][0] - seat[b][0]) + abs(seat[a][1] - seat[b][1])) for a in seat}
        if all(near[near[a]] == a for a in seat):
            side = {a: min(a, near[a]) for a in seat}
    return StudyMap(f"awbw_{m['id']}", "awbw", g, own, side, meta={"id": m["id"], "players": m["players"], "title": name, "seats": seat})


def load_dir(d):
    """Every AWBW study file (`*.txt` with the `# <id> players=` header) in a folder; names from its README table when there is one."""
    d = Path(d)
    names = {}
    readme = d / "README.md"
    if readme.exists():
        for mm in re.finditer(r"^\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", readme.read_text(), re.M):
            names[int(mm.group(1))] = mm.group(2)
    out = []
    for p in sorted(d.glob("*.txt")):
        for sm in parse_awbw(p):
            if sm.meta["id"] in names and sm.meta["title"] == str(sm.meta["id"]):
                sm.meta["title"] = names[sm.meta["id"]]
            out.append(sm)
    return out


# ------------------------------------------------------------------ our maps (via the linter's Grid)

def from_mapdata(md):
    """A StudyMap from a linter MapData (es / bh / versus / aw2 / ds)."""
    from .rules import Grid
    G = Grid(md)
    own = [[(G.T.owner(t) or 0) for t in r] for r in G.t]
    side = {}
    team = md.meta.get("team") if isinstance(md.meta, dict) else None
    if team:
        side = {i + 1: t for i, t in enumerate(team)}
    player = 1 if md.source in ("es", "bh") else 0
    return StudyMap(md.name, md.source, [list(r) for r in G.g], own, side, list(md.units or []), player, meta={"title": md.name})


# ------------------------------------------------------------------ measuring

def dijkstra(sm, starts, cost, limit=10 ** 9):
    dist = {s: 0 for s in starts}
    pq = [(0, s) for s in starts]
    while pq:
        d, (x, y) = heapq.heappop(pq)
        if d > dist.get((x, y), 1e9) or d > limit:
            continue
        for dx, dy in D4:
            X, Y = x + dx, y + dy
            c = cost.get(sm.at(X, Y))
            if c is None:
                continue
            nd = d + c
            if nd < dist.get((X, Y), 1e9):
                dist[(X, Y)] = nd
                heapq.heappush(pq, (nd, (X, Y)))
    return dist


def sides_of(sm):
    """{side: [armies]}: armies that own an HQ, a property or units."""
    armies = {o for r in sm.own for o in r if o} | {u["army"] for u in sm.units}
    out = {}
    for a in sorted(armies):
        out.setdefault(sm.side.get(a, a), []).append(a)
    return out


def anchor(sm, armies):
    """Where a side stands: its HQ, else its units' centre, else its properties' centre."""
    hq = dict(sm.meta.get("seats") or {}) or sm.hqs()
    for a in armies:
        if a in hq:
            return hq[a]
    us = [u for u in sm.units if u["army"] in armies]
    if us:
        return (round(sum(u["x"] for u in us) / len(us)), round(sum(u["y"] for u in us) / len(us)))
    ps = [(x, y) for y in range(sm.h) for x in range(sm.w) if sm.own[y][x] in armies]
    if ps:
        return (round(sum(p[0] for p in ps) / len(ps)), round(sum(p[1] for p in ps) / len(ps)))
    return None


def pairs(sm):
    """The pairs of sides the fronts lie between. A campaign map: the player's side against each enemy side that has units or an HQ;
    a symmetric map with two sides: the two; with more: each side against its nearest other side (by anchor)."""
    sd = sides_of(sm)
    anc = {s: anchor(sm, a) for s, a in sd.items()}
    anc = {s: p for s, p in anc.items() if p}
    if sm.player:
        ps = sm.side.get(sm.player, sm.player)
        return [(ps, s) for s in anc if s != ps and ps in anc]
    keys = sorted(anc)
    if len(keys) == 2:
        return [tuple(keys)]
    out = set()
    for s in keys:
        o = min((t for t in keys if t != s), key=lambda t: abs(anc[s][0] - anc[t][0]) + abs(anc[s][1] - anc[t][1]), default=None)
        if o is not None:
            out.add(tuple(sorted((s, o))))
    return sorted(out)


def cuts(sm, a, b, lo=0.3, hi=0.7, n=9):
    """Lines across the axis a -> b (perpendicular, the cells within half a cell of it) at n points between lo and hi of the way."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    d = math.hypot(dx, dy)
    if d < 3:
        return []
    ux, uy = dx / d, dy / d
    out = []
    for k in range(n):
        t = lo + (hi - lo) * k / max(1, n - 1)
        px, py = a[0] + dx * t, a[1] + dy * t
        cells = [(x, y) for y in range(sm.h) for x in range(sm.w) if abs((x - px) * ux + (y - py) * uy) <= 0.5]
        # order along the cut (perpendicular direction)
        cells.sort(key=lambda c: (c[0] - px) * -uy + (c[1] - py) * ux)
        out.append(cells)
    return out


def lanes_on(sm, cut, gap=2):
    """Lanes across one cut: runs of ground a vehicle can use, split by 2+ cells a vehicle cannot cross (mountain, sea, river with no bridge, pipe).
    Returns the lane widths."""
    lanes, cur, block = [], 0, gap
    for (x, y) in cut:
        if sm.at(x, y) in VEH_BLOCK:
            block += 1
            if block >= gap and cur:
                lanes.append(cur)
                cur = 0
        else:
            if block < gap and lanes and cur == 0:
                cur = lanes.pop()           # (a one-cell block: same lane)
            cur += 1
            block = 0
    if cur:
        lanes.append(cur)
    return lanes


def road_lanes_on(sm, cut, gap=2):
    """Roads across one cut: runs of road or bridge split by 2+ other cells (a diagonal cut is two cells thick)."""
    n, block = 0, gap
    for (x, y) in cut:
        if sm.at(x, y) in "R=":
            if block >= gap:
                n += 1
            block = 0
        else:
            block += 1
    return n


def _pct(vals, q):
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * q
    f = math.floor(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def measure(sm):
    """The design numbers of one map (see docs/dev/map-design.md for what each means)."""
    W, H = sm.w, sm.h
    cells = W * H
    land = [(x, y) for y in range(H) for x in range(W) if sm.g[y][x] not in "~r"]
    nland = max(1, len(land))
    props = sm.cells(PROPS)
    kinds = {k: len(sm.cells(k)) for k in "HBCAPTLMm"}
    r = {"w": W, "h": H, "cells": cells, "land": round(len(land) / cells, 3)}
    r["props"] = len(props)
    r["props_per100"] = round(100 * len(props) / cells, 1)
    r["props_per100_land"] = round(100 * len(props) / nland, 1)
    for k, nm in (("C", "city"), ("B", "base"), ("A", "airport"), ("P", "port"), ("T", "tower"), ("L", "lab")):
        r[f"share_{nm}"] = round(kinds[k] / max(1, len(props)), 3)
    r["silos"] = kinds["M"]
    r["fired_silos"] = kinds["m"]
    r["pipes"] = len(sm.cells("IZ"))
    r["seams"] = len(sm.cells("Z"))
    r["teleports"] = len(sm.cells("X"))
    # spacing: each property's Manhattan distance to the nearest other
    nn = []
    for (x, y) in props:
        nn.append(min((abs(x - X) + abs(y - Y) for X, Y in props if (X, Y) != (x, y)), default=0))
    r["prop_spacing"] = _pct(nn, 0.5) or 0
    # terrain mix (shares of land; sea and reef of all cells)
    def share(chars, of=land):
        return round(sum(1 for x, y in of if sm.g[y][x] in chars) / max(1, len(of)), 3)
    r.update({"t_plain": share("."), "t_wood": share("f"), "t_mountain": share("^"), "t_road": share("R"), "t_river": share("-="),
              "t_shoal": share(","), "t_prop": share(PROPS)})
    r["t_sea"] = round(len(sm.cells("~")) / cells, 3)
    r["t_reef"] = round(len(sm.cells("r")) / cells, 3)
    # roads: components, how many production buildings and properties sit on or by a road
    road = set(sm.cells("R="))
    comps = _comps(sm, "R=")
    r["road_pieces"] = len([c for c in comps if len(c) >= 3])
    near_road = lambda x, y, k: any((X, Y) in road for X in range(x - k, x + k + 1) for Y in range(y - k, y + k + 1))
    prod = sm.cells("B") or []
    r["bases_on_road"] = round(sum(near_road(x, y, 1) for x, y in prod) / len(prod), 2) if prod else None
    r["props_by_road"] = round(sum(near_road(x, y, 2) for x, y in props) / max(1, len(props)), 2)
    # roads that go nowhere: a road piece of 3+ cells that comes within 1 of no property, bridge, map edge or other piece's end
    idle = 0
    for c in comps:
        if len(c) < 3:
            continue
        ok = any(sm.at(x + dx, y + dy) in PROPS or x in (0, W - 1) or y in (0, H - 1) for x, y in c for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        idle += not ok
    r["idle_roads"] = idle
    # rivers and bridges
    rv = _comps(sm, "-=")
    r["rivers"] = len(rv)
    r["bridges"] = len(sm.cells("="))
    r["river_cells_per_bridge"] = round(len(sm.cells("-")) / max(1, len(sm.cells("="))), 1) if sm.cells("-") else None
    # coasts: land cells beside the sea, and how many are beach (shoal)
    coast = [(x, y) for x, y in land if any(sm.at(x + dx, y + dy) in WATER for dx, dy in D4)]
    r["coast"] = len(coast)
    r["beach_share"] = round(sum(sm.g[y][x] == "," for x, y in coast) / len(coast), 2) if coast else None
    seas = [c for c in _comps(sm, "~r,") if any(sm.g[y][x] in "~r" for x, y in c)]
    r["sea_body_max"] = max((len(c) for c in seas), default=0)
    # dead ground: land farther than 6 (Chebyshev) from any property and 3 from any road
    dead = 0
    for x, y in land:
        if sm.g[y][x] in "~r":
            continue
        if not any(max(abs(x - X), abs(y - Y)) <= 6 for X, Y in props) and not near_road(x, y, 3):
            dead += 1
    r["dead_share"] = round(dead / nland, 3)
    r["prop_gap"] = prop_gap(sm)
    r["river_run"] = river_run(sm)
    # properties nobody has a reason to visit (no road or other property within 5): the DQ08 measure
    lonely = sum(1 for x, y in props if sm.g[y][x] != "H" and not any((abs(X - x) + abs(Y - y)) <= 5 and (X, Y) != (x, y) for X, Y in props) and not near_road(x, y, 5))
    r["lonely_props"] = lonely
    # ---- the sides
    sd = sides_of(sm)
    r["sides"] = len(sd)
    owners = {o for row in sm.own for o in row if o}
    inc = {s: 1000 * sum(1 for x, y in sm.cells(INCOME) if sm.own[y][x] in a) for s, a in sd.items()}
    r["funds_day1"] = round(statistics.mean(inc.values())) if inc else 0
    r["funds_sym"] = round(min(inc.values()) / max(inc.values()), 2) if inc and max(inc.values()) else None
    if sm.player and sm.side.get(sm.player, sm.player) in inc:
        ps = sm.side.get(sm.player, sm.player)
        en = [v for s, v in inc.items() if s != ps]
        r["funds_player"] = inc[ps]
        r["funds_enemy"] = sum(en)
    neutral = [(x, y) for x, y in props if not sm.own[y][x]]
    r["neutral_share"] = round(len(neutral) / max(1, len(props)), 2)
    pr = pairs(sm)
    r["pairs"] = len(pr)
    per = []
    for s1, s2 in pr:
        per.append(_pair(sm, sd, s1, s2, neutral))
    if per:
        for k in per[0]:
            vals = [p[k] for p in per if p.get(k) is not None]
            if not vals:
                r[k] = None
            elif isinstance(vals[0], bool):
                r[k] = any(vals)
            else:
                r[k] = round(statistics.median(vals), 2)
    return r


def _pair(sm, sd, s1, s2, neutral):
    """The front between two sides: distances, lanes, chokepoints, the middle, base safety, the neutral split."""
    a1, a2 = sd[s1], sd[s2]
    p1, p2 = anchor(sm, a1), anchor(sm, a2)
    out = {}
    out["hq_dist"] = abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])
    tr = dijkstra(sm, [p1], TREAD)
    out["hq_tread"] = tr.get(p2)
    fo1 = dijkstra(sm, [p1], FOOT)
    out["hq_foot"] = fo1.get(p2)
    b1 = [(x, y) for x, y in sm.cells("B") if sm.own[y][x] in a1] or [p1]
    b2 = [(x, y) for x, y in sm.cells("B") if sm.own[y][x] in a2] or [p2]
    d1 = dijkstra(sm, b1, TREAD)
    out["base_dist"] = min((d1[c] for c in b2 if c in d1), default=None)
    # safety: days an infantry built at the enemy's bases needs to reach a side's base or HQ (3 moves a day)
    f1 = dijkstra(sm, b1, FOOT)
    f2 = dijkstra(sm, b2, FOOT)
    own1 = [(x, y) for x, y in sm.cells("BH") if sm.own[y][x] in a1]
    own2 = [(x, y) for x, y in sm.cells("BH") if sm.own[y][x] in a2]
    reach = [f2[c] for c in own1 if c in f2] + [f1[c] for c in own2 if c in f1]
    out["base_inf_days"] = math.ceil(min(reach) / 3) if reach else None
    # the front: cuts across the axis, lanes and widths
    cs = cuts(sm, p1, p2)
    lanes, widths, narrow, rl = [], [], [], []
    for c in cs:
        rl.append(road_lanes_on(sm, c))
        ln = lanes_on(sm, c)
        lanes.append(len(ln))
        widths.append(sum(ln))
        if ln:
            narrow.append(min(ln))
    out["lanes"] = statistics.median(lanes) if lanes else None
    out["lanes_max"] = max(lanes) if lanes else None
    out["road_lanes"] = statistics.median(rl) if rl else None
    out["front_width"] = statistics.median(widths) if widths else None
    out["front_width_min"] = min(widths) if widths else None
    out["choke"] = min(narrow) if narrow else None
    # the middle band (40% to 60% of the way): cover and properties there
    mid = {c for k in cuts(sm, p1, p2, 0.4, 0.6, 5) for c in k}
    mland = [c for c in mid if sm.at(*c) not in "~r"]
    out["mid_cover"] = round(sum(1 for x, y in mland if sm.g[y][x] in "f^") / max(1, len(mland)), 2)
    mx, my = (p1[0] + p2[0]) / 2, (p1[1] + p2[1]) / 2
    rad = max(3, 0.2 * out["hq_dist"])
    out["contested_centre"] = any(abs(x - mx) + abs(y - my) <= rad and (not sm.own[y][x] or sm.player) for x, y in sm.cells(PROPS))
    out["neutral_prod_mid"] = any(sm.own[y][x] == 0 for x, y in sm.cells("BAP") if (x, y) in mid or abs(x - mx) + abs(y - my) <= rad)
    # forward bases: a base (own or neutral) at least 35% of the way towards the other side
    fwd = 0
    for x, y in sm.cells("B"):
        da, db = abs(x - p1[0]) + abs(y - p1[1]), abs(x - p2[0]) + abs(y - p2[1])
        if min(da, db) >= 0.35 * out["hq_dist"]:
            fwd += 1
    out["forward_bases"] = fwd
    # the neutral split: neutral properties nearer (by foot) to each side; 1.0 = even
    n1 = n2 = 0
    fo2 = dijkstra(sm, [p2], FOOT)
    for c in neutral:
        d1_, d2_ = fo1.get(c, 1e9), fo2.get(c, 1e9)
        if d1_ < d2_:
            n1 += 1
        elif d2_ < d1_:
            n2 += 1
    out["neutral_split"] = round(min(n1, n2) / max(n1, n2), 2) if max(n1, n2) else None
    return out


def prop_gap(sm):
    """The farthest any ground cell (a foot soldier can stand there) lies from the nearest property (Chebyshev): the size of the biggest dead corner."""
    props = sm.cells(PROPS)
    if not props:
        return None
    best = 0
    for y in range(sm.h):
        for x in range(sm.w):
            if FOOT.get(sm.g[y][x]) is None or (sm.g[y][x] == "^" and all(sm.at(x + dx, y + dy) in "^~r|" for dx in (-1, 0, 1) for dy in (-1, 0, 1))):
                continue
            d = min(max(abs(x - X), abs(y - Y)) for X, Y in props)
            best = max(best, d)
    return best


def river_run(sm):
    """The longest stretch of river with no crossing: river cells joined without a bridge or a ford (shoal), the map edge not counting as a crossing."""
    return max((len(c) for c in _comps(sm, "-")), default=0)


def _comps(sm, chars):
    seen, out = set(), []
    for c0 in sm.cells(chars):
        if c0 in seen:
            continue
        comp, todo = {c0}, [c0]
        while todo:
            x, y = todo.pop()
            for dx, dy in D4:
                c = (x + dx, y + dy)
                if c not in comp and sm.at(*c) in chars:
                    comp.add(c)
                    todo.append(c)
        seen |= comp
        out.append(comp)
    return out


# ------------------------------------------------------------------ sets

KEYS = ["props_per100", "props_per100_land", "prop_spacing", "share_city", "share_base", "share_airport", "share_port", "funds_day1", "funds_sym",
        "hq_dist", "hq_tread", "base_dist", "base_inf_days", "lanes", "road_lanes", "front_width", "choke", "mid_cover", "forward_bases", "neutral_share", "neutral_split",
        "t_plain", "t_wood", "t_mountain", "t_road", "t_river", "t_shoal", "t_sea", "t_reef", "road_pieces", "bases_on_road", "props_by_road", "idle_roads",
        "rivers", "bridges", "river_cells_per_bridge", "river_run", "beach_share", "sea_body_max", "dead_share", "prop_gap", "lonely_props"]
FLAGS = ["contested_centre", "neutral_prod_mid"]


def summary(rows):
    """{key: (p10, median, p90)} over a set of `measure` rows, and {flag: share of maps}; plus how often the features appear."""
    out = {}
    for k in KEYS:
        v = [r[k] for r in rows if r.get(k) is not None]
        if v:
            out[k] = (round(_pct(v, 0.1), 2), round(_pct(v, 0.5), 2), round(_pct(v, 0.9), 2))
    for k in FLAGS:
        v = [r[k] for r in rows if r.get(k) is not None]
        if v:
            out[k] = round(sum(v) / len(v), 2)
    for k, test in (("has_tower", lambda r: r["share_tower"] > 0), ("has_silo", lambda r: r["silos"] + r["fired_silos"] > 0), ("has_pipe", lambda r: r["pipes"] > 0),
                    ("has_airport", lambda r: r["share_airport"] > 0), ("has_port", lambda r: r["share_port"] > 0), ("has_river", lambda r: r["rivers"] > 0),
                    ("has_lab", lambda r: r["share_lab"] > 0), ("flank_lanes", lambda r: (r.get("lanes_max") or 0) >= 2),
                    ("forward_base", lambda r: (r.get("forward_bases") or 0) > 0)):
        out[k] = round(sum(1 for r in rows if test(r)) / max(1, len(rows)), 2)
    return out


# ------------------------------------------------------------------ pictures

def draw(sm, cell=16, title=None, notes=()):
    """A picture of a study map in our own colours (render.py's palette: nothing of the games' art), owners coloured, units as discs."""
    from PIL import Image, ImageDraw
    from .render import COL, ARMY, UNIT_INITIAL, font
    head = 22
    lines = list(notes)
    lw = 360 if lines else 0
    img = Image.new("RGB", (sm.w * cell + lw, max(sm.h * cell + head, head + 13 * (len(lines) + 1))), (24, 24, 30))
    d = ImageDraw.Draw(img)
    f, fs = font(max(8, cell - 4)), font(11)
    d.text((4, 4), title or f"{sm.name} {sm.w}x{sm.h}", fill=(240, 240, 240), font=fs)
    extra = {"L": (230, 230, 255), "m": (170, 150, 150), "X": (255, 0, 255)}
    for y in range(sm.h):
        for x in range(sm.w):
            c = sm.g[y][x]
            col = extra.get(c) or COL.get(c, (255, 255, 255))
            lab = ""
            if c in "HBCAPTL":
                col = ARMY.get(min(sm.own[y][x], 5) if sm.own[y][x] <= 5 else 5, (255, 255, 255)) if c != "T" or sm.own[y][x] else COL["T"]
                lab = c
            x0, y0 = x * cell, y * cell + head
            d.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=col)
            if lab:
                d.text((x0 + 3, y0 + 1), lab, fill=(0, 0, 0), font=f)
            elif c == "=":
                d.line([x0, y0 + cell // 2, x0 + cell, y0 + cell // 2], fill=(220, 180, 100), width=2)
    for u in sm.units:
        x0, y0 = u["x"] * cell, u["y"] * cell + head
        d.ellipse([x0 + 1, y0 + 1, x0 + cell - 2, y0 + cell - 2], fill=ARMY.get(u["army"], (255, 255, 255)), outline=(0, 0, 0))
        d.text((x0 + 4, y0 + 1), UNIT_INITIAL.get(u["kind"], "?"), fill=(0, 0, 0), font=f)
    for i, ln in enumerate(lines):
        d.text((sm.w * cell + 8, head + 13 * i), ln[:56], fill=(230, 230, 230), font=fs)
    return img
