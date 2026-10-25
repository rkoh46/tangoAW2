"""The map-integrity rules. Each rule has an id, a level (error: AW2 and Dual Strike never do it; warn: they do it rarely) and a check that
yields `Problem`s with a cell. Calibration against the games' own maps: `aw2dev maps rules` (docs/dev/map-lint.md).

Maps are checked on their tiles (so the same code reads a BH text map, a Versus map, an AW2 map from the ROM and a Dual Strike map), as the
terrain characters of `terrain.Terrain.ch`: . plain  f wood  ^ mountain  R road  - river  = bridge  ~ sea  , shoal  r reef  I pipe  Z seam
M silo  H B C A P T properties  # structure  ? tile no game map uses."""
import collections, functools, re
from dataclasses import dataclass
from . import load
from .terrain import terrain, PROP_KIND

D4 = ((0, -1), (1, 0), (0, 1), (-1, 0))          # N E S W
WATER = set("~r,")                                # sea, reef, shoal
GROUND_BLOCK = set("^f~r,-IZ#?")                  # not a way for a vehicle
RULES = {
    "RV01": ("error", "river ends dry against plain, wood, road, pipe or a building: a river runs from a source (map edge or mountain) to the sea"),
    "RV02": ("error", "a single river cell with no river or water beside it"),
    "RV03": ("error", "a river that reaches neither the sea or a lake nor the map edge"),
    "RV05": ("error", "a river ends on land against a mountain: AW2 has no source or end tile, so a river must run from the map edge, the sea, a shoal or a lake to the map edge, the sea, a shoal or a lake"),
    "RV04": ("error", "a road meets a river with no bridge (road on both sides of a river cell, or a road running into a river's end)"),
    "BR01": ("error", "a bridge end meets water or a tile no unit can stand on, not ground"),
    "BR02": ("warn", "a bridge end meets a mountain, a wood, a pipe or a structure: vehicles cannot cross"),
    "BR03": ("error", "a bridge with no water beside it"),
    "SE01": ("error", "a one-tile sea or reef with no bridge over it, not at the map edge (a puddle)"),
    "SE02": ("warn", "shoal that touches no sea, reef or river"),
    "SE03": ("error", "a sea cell is not drawn with the coast tile AW2's table gives for the land around it"),
    "TJ01": ("error", "two neighbouring tiles that no AW2 map places side by side (a broken join)"),
    "TJ02": ("error", "a river, shoal, bridge or sea tile that no game map uses for these neighbours (wrong transition tile)"),
    "TJ03": ("warn", "a mountain or the plain over it not drawn as the game draws it"),
    "RD01": ("warn", "a single road tile that joins no road, bridge or property"),
    "RD02": ("warn", "two road ends one or two tiles apart in line, the gap left plain"),
    "PP01": ("error", "a pipe tile that opens onto a tile it does not join"),
    "PP02": ("error", "a pipe seam that is not inside a straight run"),
    "UN01": ("error", "a unit on terrain its kind cannot occupy"),
    "UN02": ("error", "two units on one cell"),
    "UN03": ("error", "a unit boxed in with no free neighbour to move to"),
    "UN04": ("error", "a unit off the map"),
    "RC01": ("error", "a property or unit on land that no army or Lander can reach"),
    "RC02": ("error", "an army cannot reach an enemy HQ it must take"),
    "RC03": ("error", "an HQ or production property no unit can leave (no ground, or no sea for a port)"),
    "RC04": ("error", "a Lander with no beach or port to load or unload at"),
    "GB01": ("error", "a tile id no game map uses (drawn as garbage)"),
    "GB02": ("error", "a building or structure with part of its footprint missing or wrong"),
    "DQ01": ("warn", "a long river with no bend: rivers wander"),
    "DQ02": ("warn", "most mountain or wood patches are exact rectangles: drawn blocks, not terrain"),
    "DQ03": ("warn", "blocks of parallel identical rows of mountains or woods: the procedural look"),
    "DQ04": ("warn", "too little of the land is anything but plain: empty fields and decorative filler"),
    "DQ05": ("warn", "a big empty plain field: a dead corner"),
    "DQ06": ("warn", "a very long straight road with no bend or junction"),
    "DQ07": ("warn", "an army's units start as a solid block (a blob, not a formation)"),
    "DQ08": ("warn", "a property with no road or other property near it: no reason to go there"),
    "DQ09": ("warn", "an HQ in a pocket: little walkable ground around it"),
    "DQ10": ("warn", "a Lander with too few shore cells to unload on"),
    "RN01": ("error", "a river, shoal, bridge or coast tile drawn in the game's picture in a way none of the games' drawings of that tile and 4-neighbour class is (`aw2dev maps render-check`)"),
    "AR01": ("error", "two armies of the map wear the same colour (each army is its own nation: Orange Star, Blue Moon, Green Earth, Yellow Comet, Black Hole)"),
    "AR02": ("error", "an army has more than one HQ"),
    "AR03": ("error", "a silo or an airport that no army's infantry can reach, or an airport whose footprint is wrong"),
    "PP03": ("warn", "a pipeline that is a stub: an end hanging in open terrain (a pipeline ends at the map edge, the sea, mountains or a building) or fewer than 6 cells"),
    "PP04": ("warn", "a pipe seam that changes nothing when broken: it neither joins two parts of the map nor shortens the way between the HQs by at least 6 cells"),
    "PT01": ("error", "a port that leads nowhere: no navigable sea beside it (lava is not navigable), or a sea body too small for ships (a lake of a few cells)"),
    "DQ12": ("warn", "a long straight line of mountains away from the map edge: a drawn wall, not a range"),
    "DQ11": ("warn", "a map meant to be fair (Versus, or a `fair` line) with unequal properties per army"),
    "SP01": ("warn", "not enough room to fight: too many units for the walkable ground or for the frontage between the sides"),
    "ES01": ("error", "Black Hole's inventions on an Emerald Sun map that is not one of the (at most two) missions against Black Hole (the map file's `blackhole` line)"),
}


@dataclass
class Problem:
    rule: str
    x: int
    y: int
    msg: str

    @property
    def level(self):
        return RULES[self.rule][0]

    def __str__(self):
        loc = f"({self.x},{self.y})" if self.x >= 0 else "(map)"
        return f"{self.rule} {self.level} {loc} {self.msg}"


class Grid:
    def __init__(self, m):
        self.m = m
        self.T = terrain()
        self.t = m.tiles
        self.h, self.w = len(self.t), len(self.t[0])
        self.g = [[self.T.ch(v) for v in r] for r in self.t]

    def at(self, x, y):
        return self.g[y][x] if 0 <= x < self.w and 0 <= y < self.h else "|"

    def nb(self, x, y):
        return [self.at(x + dx, y + dy) for dx, dy in D4]

    def cells(self, chars):
        return [(x, y) for y in range(self.h) for x in range(self.w) if self.g[y][x] in chars]

    def comps(self, chars, joiner=None):
        """4-connected components of cells whose character is in `chars`."""
        seen, out = set(), []
        for x0, y0 in self.cells(chars):
            if (x0, y0) in seen:
                continue
            comp, todo = {(x0, y0)}, [(x0, y0)]
            while todo:
                x, y = todo.pop()
                for dx, dy in D4:
                    X, Y = x + dx, y + dy
                    if (X, Y) not in comp and self.at(X, Y) in chars:
                        comp.add((X, Y))
                        todo.append((X, Y))
            seen |= comp
            out.append(comp)
        return out


# ---------------------------------------------------------------- learned from the game's own maps

@functools.lru_cache(maxsize=1)
def learned():
    """What the games place: neighbour tile pairs (tilecheck), the sea-edge table, and per neighbourhood the transition tiles used."""
    mappy, tc, _ = load._five()
    rom = load.rom_bytes()
    refs = load.aw2_maps(rom) + load.ds_maps()
    L = {"rom": rom, "pairs": tc.learn(rom), "mountain": tc.mountain_rules(rom), "edge": mappy.sea_edges(rom), "tiles": set()}
    keys = collections.defaultdict(set)
    for m in refs:
        G = Grid(m)
        L["tiles"] |= {v for r in m.tiles for v in r}
        for y in range(G.h):
            for x in range(G.w):
                k = trans_key(G, x, y)
                if k:
                    keys[k].add(G.t[y][x])
    L["keys"] = keys
    L["ref_tiles"] = L["tiles"]
    return L


def trans_key(G, x, y):
    """The neighbourhood of a transition tile (river, bridge, shoal, sea): None for other tiles."""
    c = G.g[y][x]
    if c not in "-=,~":
        return None
    t = G.t[y][x]
    if c == "~" and t >= 0x1B4:
        return None
    if c == "~":
        mask = 0
        for i, (dx, dy) in enumerate([(-1, -1), (0, -1), (1, -1), (-1, 0), (0, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]):
            X, Y = x + dx, y + dy
            if 0 <= X < G.w and 0 <= Y < G.h and G.g[Y][X] not in "~r,=-":
                mask |= 0x100 >> i
        return ("sea", mask)
    look = [G.g[Y][X] if 0 <= X < G.w and 0 <= Y < G.h else c for X, Y in ((x + dx, y + dy) for dx, dy in D4)]
    if c == "-":
        return ("river",) + tuple("r" if n in "-=" else "s" if n in "~r," else "l" for n in look)
    if c == "=":
        return ("bridge",) + tuple("w" if n in "~r-" else "b" if n in "=R" else "l" for n in look)
    return ("shoal",) + tuple("s" if n in "~r" else "h" if n == "," else "l" for n in look)


# ---------------------------------------------------------------- rules

def river(G):
    out = []
    wet = lambda n: n in "-="
    for x, y in G.cells("-"):
        nb = G.nb(x, y)
        riv = [wet(n) for n in nb]
        sea = [n in WATER for n in nb]
        if not any(riv) and not any(sea):
            out.append(Problem("RV02", x, y, "single river cell"))
            continue
        if sum(riv) + sum(sea) == 1 and not any(sea):
            i = riv.index(True)
            opp = nb[(i + 2) % 4]
            if opp == "|":
                continue
            if opp == "^":
                out.append(Problem("RV05", x, y, "river ends against a mountain (a 'spring' is a cut-off end: AW2 has no source tile)"))
                continue
            names = {".": "plain", "f": "wood", "R": "road", "I": "pipe", "Z": "pipe", "#": "a structure", "M": "a silo", "-": "river"}
            out.append(Problem("RV01", x, y, f"river ends dry against {names.get(opp, 'a building' if opp in 'HBCAPT' else repr(opp))}"))
        # a road on both sides across the flow
        for sides, flow in (((1, 3), (0, 2)), ((0, 2), (1, 3))):
            if nb[sides[0]] == "R" and nb[sides[1]] == "R" and any(riv[f] or sea[f] for f in flow):
                out.append(Problem("RV04", x, y, "road crosses the river with no bridge"))
                break
    # a road running into a river's end
    for x, y in G.cells("R"):
        nb = G.nb(x, y)
        conn = [n in "R=HBCAPTZ" for n in nb]
        if sum(conn) == 1:
            i = conn.index(True)
            o = (i + 2) % 4
            if nb[o] == "-":
                out.append(Problem("RV04", x, y, "road runs into a river with no bridge"))
    # components: does the river reach the sea/lake or the edge?
    seen = set()
    for x0, y0 in G.cells("-"):
        if (x0, y0) in seen:
            continue
        comp, todo = {(x0, y0)}, [(x0, y0)]
        while todo:
            x, y = todo.pop()
            for dx, dy in D4:
                X, Y = x + dx, y + dy
                if (X, Y) not in comp and G.at(X, Y) in "-=":
                    comp.add((X, Y))
                    todo.append((X, Y))
        seen |= comp
        rivers = [c for c in comp if G.at(*c) == "-"]
        sink = False
        for x, y in rivers:
            nb = G.nb(x, y)
            if any(n in WATER for n in nb):
                sink = True
            # runs off the map
            for i, (dx, dy) in enumerate(D4):
                if nb[i] == "|" and nb[(i + 2) % 4] in "-=":
                    sink = True
        if not sink:
            x, y = min(rivers)
            out.append(Problem("RV03", x, y, f"river of {len(rivers)} cells reaches neither sea, lake nor map edge"))
    return out


def bridges(G):
    out = []
    for x, y in G.cells("="):
        nb = G.nb(x, y)
        wetn = lambda n: n in "~r-,"
        wet = [wetn(n) for n in nb]
        if not any(wet):
            # a lane of a wide bridge: water at the far side of the lanes beside it
            def far(dx, dy):
                X, Y = x + dx, y + dy
                while G.at(X, Y) == "=":
                    X, Y = X + dx, Y + dy
                return wetn(G.at(X, Y))
            if not any(far(dx, dy) for dx, dy in D4):
                out.append(Problem("BR03", x, y, "bridge with no water beside it"))
            continue
        # travel axis = the axis whose sides are not water
        if wet[0] or wet[2]:
            if wet[1] or wet[3]:
                continue        # a bridge corner / junction over water: skip
            ends = (1, 3)
        else:
            ends = (0, 2)
        for i in ends:
            n = nb[i]
            if n == "=":
                continue
            if n == "|" or n == ",":
                continue                 # (off the map the road runs on; a shoal is ground a unit walks, a ford)
            if n in "~r-?":
                what = {"~": "sea", "r": "reef", "-": "a river", "?": "an unknown tile"}[n]
                out.append(Problem("BR01", x, y, f"bridge end meets {what}"))
            elif n in "^fIZ#":
                out.append(Problem("BR02", x, y, "bridge end meets " + {"^": "a mountain", "f": "a wood", "I": "a pipe", "Z": "a pipe", "#": "a structure"}[n]))
    return out


def sea(G):
    out = []
    L = learned()
    # enclosed one-tile sea / reef
    for comp in G.comps("~r"):
        if len(comp) == 1:
            x, y = next(iter(comp))
            if x in (0, G.w - 1) or y in (0, G.h - 1):
                continue
            if any(n in "=-," for n in G.nb(x, y)):
                continue
            out.append(Problem("SE01", x, y, "one-tile sea or reef (a puddle)"))
    for comp in G.comps(","):
        touches = False
        for x, y in comp:
            if any(n in "~r-" for n in G.nb(x, y)):
                touches = True
        if not touches:
            x, y = min(comp)
            if x in (0, G.w - 1) or y in (0, G.h - 1):
                continue
            out.append(Problem("SE02", x, y, f"shoal of {len(comp)} cells touches no sea"))
    # coast tiles: the editor table
    edge = L["edge"]
    mappy, tc, _ = load._five()
    mouths = {0x11C, 0x11D, 0xFC, 0xFD}
    for y in range(G.h):
        for x in range(G.w):
            t = G.t[y][x]
            if G.g[y][x] != "~" or t >= 0x1B4:
                continue
            k = trans_key(G, x, y)
            want = edge(k[1])
            if want > 0 and t != want and t not in {v.get(want) for v in mappy.RIVER_INTO_SEA.values()}:
                if t in L["keys"].get(k, ()):
                    continue         # (the game's own maps draw this neighbourhood so)
                out.append(Problem("SE03", x, y, f"sea tile 0x{t:03X} where the table gives 0x{want:03X}"))
    return out


def joins(G):
    mappy, tc, _ = load._five()
    L = learned()
    out = []
    skip = tc.structure_cells(G.t) | tc.editor_sea(G.t, L["rom"])
    for x, y, p in tc.violations(G.t, L["pairs"], skip):
        out.append(Problem("TJ01", x, y, tc.describe((x, y, p)).split(") ", 1)[1]))
    if G.m.source in ("bh", "es", "versus", "aw2"):
        for x, y, p in tc.mountain_violations(G.t, L["mountain"]):
            out.append(Problem("TJ03", x, y, tc.describe((x, y, p)).split(") ", 1)[1]))
    for y in range(G.h):
        for x in range(G.w):
            k = trans_key(G, x, y)
            if k is None:
                continue
            t = G.t[y][x]
            seen = L["keys"].get(k)
            if k[0] == "bridge" and any(n == "b" for n in k[1:]) and any(G.at(x + dx, y + dy) == "=" for dx, dy in D4):
                if t in (0x13, 0x14, 0x15, 0x16, 0x36):
                    continue             # (lanes of a wide bridge: the game draws them with the bridge family, pair rules apply)
            if k[0] == "sea" and t in {v for vs in mappy.RIVER_INTO_SEA.values() for v in vs.values()}:
                continue
            if k[0] == "sea":
                continue                 # (sea tiles are SE03's)
            if seen is None:
                out.append(Problem("TJ02", x, y, f"{k[0]} tile 0x{t:03X} in a neighbourhood {''.join(k[1:])} no game map has"))
            elif t not in seen:
                out.append(Problem("TJ02", x, y, f"{k[0]} tile 0x{t:03X} where the games draw {'/'.join(f'0x{v:03X}' for v in sorted(seen))}"))
    return out


def roads(G):
    out = []
    for x, y in G.cells("R"):
        nb = G.nb(x, y)
        if not any(n in "R=HBCAPTZ" for n in nb):
            out.append(Problem("RD01", x, y, "isolated road tile"))
    # two road ends in line with a 1-2 tile gap of plain
    ends = {}
    for x, y in G.cells("R"):
        nb = G.nb(x, y)
        conn = [n in "R=HBCAPTZ" for n in nb]
        if sum(conn) == 1:
            i = conn.index(True)
            ends[(x, y)] = (i + 2) % 4          # the direction it points
    for (x, y), d in ends.items():
        dx, dy = D4[d]
        for gap in (1, 2):
            X, Y = x + dx * (gap + 1), y + dy * (gap + 1)
            mids = [G.at(x + dx * k, y + dy * k) for k in range(1, gap + 1)]
            if (X, Y) in ends and ends[(X, Y)] == (d + 2) % 4 and all(c in ".f" for c in mids) and (x, y) < (X, Y):
                out.append(Problem("RD02", x, y, f"road ends {gap} tile(s) short of the road at ({X},{Y})"))
    return out


def pipes(G):
    mappy, tc, _ = load._five()
    links = tc.pipe_links()
    out = []
    bases = {"B", "H"}
    for y in range(G.h):
        for x in range(G.w):
            t = G.t[y][x]
            if t not in links:
                continue
            sides = links[t]
            for bit, (dx, dy), back in ((8, D4[0], 2), (4, D4[1], 1), (2, D4[2], 8), (1, D4[3], 4)):
                if not sides & bit:
                    continue
                X, Y = x + dx, y + dy
                if not (0 <= X < G.w and 0 <= Y < G.h):
                    continue            # a pipe running off the map
                n = G.t[Y][X]
                if links.get(n, 0) & back or G.g[Y][X] in bases or G.g[Y][X] in "#M":
                    continue
                if G.g[Y][X] in "C" or True:
                    out.append(Problem("PP01", x, y, f"pipe 0x{t:03X} opens toward ({X},{Y}) which is {G.g[Y][X]!r}, not a pipe"))
            if t in (mappy.SEAM_ACROSS, mappy.SEAM_DOWN):
                a, b = ((G.at(x - 1, y), G.at(x + 1, y)) if t == mappy.SEAM_ACROSS else (G.at(x, y - 1), G.at(x, y + 1)))
                if not (a in "IZB" and b in "IZB") and not (a in "IZBH" or b in "IZBH"):
                    out.append(Problem("PP02", x, y, "seam outside a straight pipe run"))
    return out


def garbage(G):
    L = learned()
    mappy, tc, _ = load._five()
    out = []
    known = L["ref_tiles"] | set(tile for t in mappy.PROPS.values() for tile in t)
    known |= {v for rows, _, _ in mappy.INVENTIONS.values() for r in rows for v in r}
    for y in range(G.h):
        for x in range(G.w):
            t = G.t[y][x]
            if t not in known:
                out.append(Problem("GB01", x, y, f"tile 0x{t:03X} is in no game map"))
    # inventions: footprints
    for ch, (rows, ac, ar) in mappy.INVENTIONS.items():
        if len(rows) == 1 and len(rows[0]) == 1:
            continue
        anchor = rows[ar][ac]
        for y in range(G.h):
            for x in range(G.w):
                if G.t[y][x] != anchor:
                    continue
                for j, row in enumerate(rows):
                    for i, want in enumerate(row):
                        X, Y = x - ac + i, y - ar + j
                        got = G.t[Y][X] if 0 <= X < G.w and 0 <= Y < G.h else None
                        if got != want and want not in (0x1A4, 0x1A5):
                            out.append(Problem("GB02", X if got is not None else x, Y if got is not None else y,
                                               f"structure {ch!r} at ({x},{y}): tile 0x{want:03X} missing at ({X},{Y}), found {('0x%03X' % got) if got is not None else 'the map edge'}"))
    return out


# ---------------------------------------------------------------- units, reach and access (need movement classes: bhmap.py's)

def _bh():
    return load._five()[2]


def _pass_char(G, x, y):
    return G.g[y][x]


def access(G):
    bh = _bh()
    out = []
    for y in range(G.h):
        for x in range(G.w):
            c = G.g[y][x]
            if c in "HBA":
                around = "".join(G.nb(x, y))
                free = [n for n in G.nb(x, y) if n != "|" and bh.passable(n, bh.TREADS)]
                if not free:
                    out.append(Problem("RC03", x, y, f"{ {'H': 'HQ', 'B': 'base', 'A': 'airport'}[c] } with no ground beside it to drive onto"))
            elif c == "P":
                if not any(n in "~r=" or n == "," for n in G.nb(x, y)):
                    out.append(Problem("RC03", x, y, "port with no sea beside it"))
    return out


def units(G):
    bh = _bh()
    out = []
    seen = {}
    for u in G.m.units:
        x, y = u["x"], u["y"]
        name = bh.UNIT_NAMES.get(u["kind"], u["kind"])
        if not (0 <= x < G.w and 0 <= y < G.h):
            out.append(Problem("UN04", x, y, f"{name} of army {u['army']} is off the map"))
            continue
        if (x, y) in seen:
            out.append(Problem("UN02", x, y, f"{name} of army {u['army']} shares the cell with kind {seen[(x, y)]}"))
        seen[(x, y)] = name
        cls = bh.CLASS.get(u["kind"], bh.FOOT)
        around = "".join(G.nb(x, y))
        c = G.g[y][x]
        if c in "T":
            c = "T"
        if not bh.passable(c, cls, around):
            out.append(Problem("UN01", x, y, f"{name} of army {u['army']} stands on {c!r} ({_desc(c)}), which it cannot enter"))
        elif cls != bh.AIR and not any(n != "|" and bh.passable(n, cls, "") for n in G.nb(x, y)):
            out.append(Problem("UN03", x, y, f"{name} of army {u['army']} has no free neighbour"))
    return out


def _desc(c):
    return {".": "plain", "f": "wood", "^": "mountain", "R": "road", "-": "river", "=": "bridge", "~": "sea", ",": "shoal", "r": "reef", "I": "pipe", "Z": "seam", "#": "structure", "?": "unknown"}.get(c, "building")


def reach(G):
    """The BH Campaign's reachability checks (five/bhmap.py check_reach), on a text map; needs the map's text rows."""
    bh = _bh()
    if G.m.source not in ("bh", "es"):
        return []
    out = []
    for p in bh.check_reach(G.m.meta):
        rule = "RC02" if "cannot reach army" in p else "RC04" if "Lander" in p else "RC01"
        loc = re.search(r"\((\d+), (\d+)\)", p)
        x, y = (int(loc.group(1)), int(loc.group(2))) if loc else (-1, -1)
        if "stands on" in p or "boxed in" in p:
            continue            # (UN01 / UN03 say it)
        out.append(Problem(rule, x, y, p.split(": ", 1)[-1]))
    return out


def _unit_problem(G, u, bh, rule_prefix=""):
    """A unit (map line or mission spawn) on terrain its kind cannot occupy; the message, or None."""
    x, y = u["x"], u["y"]
    if not (0 <= x < G.w and 0 <= y < G.h):
        return "off"
    cls = bh.CLASS.get(u["kind"], bh.FOOT)
    if not bh.passable(G.g[y][x], cls, "".join(G.nb(x, y))):
        return G.g[y][x]
    return None


@functools.lru_cache(maxsize=2)
def _bh_grids(source="bh"):
    if source != "es":
        return {m.name: Grid(m) for m in load.bh_maps()}
    out = {}
    for p in sorted((load.FIVE / "es").glob("es[0-9][0-9]*.txt")):
        try:
            for m in load.es_maps(files=[p]):
                out[m.name] = Grid(m)
        except Exception:      # (a map still being written by its author)
            pass
    return out


def spawned(G):
    """Units the mission's code places by literal coordinates (spawns.py): on terrain they can enter, and not on a unit of the map file.
    A mission with a second front (`bh08` and `bh08b`) is checked against both maps: the spawn must fit at least one."""
    from . import spawns as sp
    if G.m.source not in ("bh", "es"):
        return []
    bh = _bh()
    name = G.m.name
    base = name[:-1] if name.endswith("b") and name[:-1] in _bh_grids(G.m.source) else name
    mine = sp.spawns(G.m.source).get(base, [])
    sibs = [g for n, g in _bh_grids(G.m.source).items() if n == base or n == base + "b"]
    out = []
    occupied = {(u["x"], u["y"]) for u in G.m.units}
    for u in mine:
        bad = _unit_problem(G, u, bh)
        if bad is None:
            if (u["x"], u["y"]) in occupied:
                out.append(Problem("UN02", u["x"], u["y"], f"{bh.UNIT_NAMES.get(u['kind'])} placed by {u['spawn']} lands on a unit of the map file"))
            continue
        if any(g is not G and _unit_problem(g, u, bh) is None for g in sibs):
            continue
        name_ = bh.UNIT_NAMES.get(u["kind"])
        out.append(Problem("UN01" if bad != "off" else "UN04", u["x"], u["y"], f"{name_} placed by {u['spawn']} " +
                           ("is off the map" if bad == "off" else f"stands on {bad!r} ({_desc(bad)}), which it cannot enter")))
    return out


def inventions(G):
    """ES01: Black Hole's inventions only on the (at most two) Emerald Sun maps that fight Black Hole."""
    if G.m.source != "es":
        return []
    out = []
    # (a missile silo, tile 0x180, is AW2's own terrain, not an invention: it is fine in any mission)
    # (a volcano is a natural hazard, allowed anywhere: its rim and slope tiles 0x1A5..0x1A9 and the underlay inside their box)
    vol = [(x, y) for y in range(G.h) for x in range(G.w) if 0x1A5 <= G.t[y][x] <= 0x1A9]
    box = (min(c[0] for c in vol) - 1, min(c[1] for c in vol) - 1, max(c[0] for c in vol) + 1, max(c[1] for c in vol) + 1) if vol else None
    in_vol = lambda x, y: box and box[0] <= x <= box[2] and box[1] <= y <= box[3] and (0x1A4 <= G.t[y][x] <= 0x1A9)
    tiles = [(x, y) for y in range(G.h) for x in range(G.w) if (G.g[y][x] == "#" or 0x181 <= G.t[y][x] <= 0x1A9) and not in_vol(x, y)]
    if tiles and not G.m.meta.get("blackhole"):
        x, y = tiles[0]
        out.append(Problem("ES01", x, y, f"{len(tiles)} invention tiles on a map with no `blackhole` line (only the missions against Black Hole may have them)"))
    if G.m.meta.get("blackhole"):
        try:
            n = sum(1 for p in sorted((load.FIVE / "es").glob("es[0-9][0-9]*.txt")) if "\nblackhole\n" in p.read_text())
        except OSError:
            n = 0
        if n > 2:
            out.append(Problem("ES01", -1, -1, f"{n} maps are tagged `blackhole` (at most two missions fight Black Hole)"))
    return out


def reachables(G):
    """AR03: a missile silo and an airport must be reachable on foot from some army's HQ (infantry capture the airport, a foot soldier on the silo launches it): a flood from the HQs over
    every cell a foot soldier can stand on (plain, wood, mountain, road, bridge, shoal, river ford, property, silo). Reported once per cell."""
    out = []
    targets = [(x, y) for y in range(G.h) for x in range(G.w) if G.g[y][x] in "MAa"]
    if not targets:
        return out
    foot = set(".fR^=-,HBCAPTMbcapt")
    if not G.cells("H"):
        return out                       # (a second front has no HQ of its own: its units arrive from the other front)
    if G.cells("Pp") or any(u.get("kind") == 23 for u in (G.m.units or [])):
        foot = foot | set("~r")          # (a port or a Lander: infantry cross the water by transport and land on any shore)
    seen, todo = set(), [(x, y) for y in range(G.h) for x in range(G.w) if G.g[y][x] == "H"]
    seen.update(todo)
    while todo:
        x, y = todo.pop()
        for dx, dy in D4:
            c = (x + dx, y + dy)
            if c not in seen and G.at(*c) in foot:
                seen.add(c)
                todo.append(c)
    for x, y in targets:
        if (x, y) not in seen:
            out.append(Problem("AR03", x, y, f"the {'silo' if G.g[y][x] == 'M' else 'airport'} cannot be reached on foot from any HQ"))
    return out


PIPE = set("IZ")
VEH = set(".R=,HBCAPTMbcapt")


def pipe_parts(G):
    """The connected pipelines (4-connected cells of pipe or seam): [set of cells]."""
    return G.comps(PIPE)


def pipe_ends(G, comp):
    """(cell, the cell beyond it) of every end of a pipeline (a cell with one pipe neighbour; the cell beyond lies opposite that neighbour)."""
    out = []
    for x, y in comp:
        nb = [(dx, dy) for dx, dy in D4 if (x + dx, y + dy) in comp]
        if len(nb) == 1:
            dx, dy = nb[0]
            out.append(((x, y), (x - dx, y - dy)))
        elif len(nb) == 0:
            out.append(((x, y), (x, y)))
    return out


def closed_beyond(G, c, back=None):
    """Whether the pipeline stops properly at the cell `c` beyond its end: the map edge, a mountain, water or a river (a barrier ends there), a building or structure (a supply line ends
    in the base or factory it feeds), or a GATE: a gap of up to 3 cells in the line with the wall resuming on the other side (`back` is the direction the line runs in)."""
    x, y = c
    if not (0 <= x < G.w and 0 <= y < G.h):
        return True                                  # the map edge
    if G.g[y][x] in "^~r,#-" or G.g[y][x] in "HBCAPTbcapt12345":
        return True
    if back:
        for i in range(1, 4):
            nx, ny = x + back[0] * i, y + back[1] * i
            if G.at(nx, ny) in PIPE:
                return True
            if G.at(nx, ny) in "^~#|":
                break
    return False


def supply_line(G, comp):
    """A pipeline with an end in a building or structure feeds it (a base, a factory, a cannon): a supply line, not a barrier."""
    for cell, beyond in pipe_ends(G, comp):
        if 0 <= beyond[0] < G.w and 0 <= beyond[1] < G.h and (G.g[beyond[1]][beyond[0]] in "HBCAPTbcapt#" or any(G.at(cell[0] + dx, cell[1] + dy) in "BAbaHCc#" for dx, dy in D4)):
            return True
    return False


def dist_map(G, start, seams_open):
    """BFS over vehicle ground from `start` (a cell): {cell: steps}, seams passable when `seams_open` (a set of cells)."""
    ok = lambda c: G.at(*c) in VEH or c in seams_open
    d = {start: 0}
    todo = [start]
    for c in todo:
        for dx, dy in D4:
            n = (c[0] + dx, c[1] + dy)
            if n not in d and ok(n):
                d[n] = d[c] + 1
                todo.append(n)
    return d


def pipelines(G):
    """PP03: a pipeline is a barrier built like infrastructure: 6 or more cells and no end hanging in open terrain. PP04: each seam must change something: broken, it joins two parts
    of the ground (vehicles) that were apart, or shortens the way between two HQs by 6 cells or more."""
    out = []
    parts = pipe_parts(G)
    hqs = G.cells("H")
    for comp in parts:
        if any(G.at(x + dx, y + dy) == "#" for x, y in comp for dx, dy in D4):
            continue                                     # (the supply pipe of a Black Hole factory or cannon)
        if len(comp) < 6:
            x, y = min(comp, key=lambda c: (c[1], c[0]))
            out.append(Problem("PP03", x, y, f"a pipe stub of {len(comp)} cells"))
            continue
        for cell, beyond in pipe_ends(G, comp):
            if not closed_beyond(G, beyond, (beyond[0] - cell[0], beyond[1] - cell[1])):
                out.append(Problem("PP03", cell[0], cell[1], f"a pipeline ends in open terrain at {cell} (it must reach the map edge, the sea, mountains or a building)"))
        for seam in [c for c in comp if G.g[c[1]][c[0]] == "Z"]:
            if not hqs or supply_line(G, comp):
                continue                                 # (a supply line's seam cuts the feed, it is not a gate of the map)
            gained = False
            for hq in hqs:
                before = dist_map(G, hq, set())
                after = dist_map(G, hq, {seam})
                if len(after) > len(before) + 0 and any(c not in before for c in after if c != seam and c in after and G.at(*c) in VEH):
                    gained = True                    # the seam joins ground that was cut off
                    break
                if any(c in before and before[c] - after[c] >= 6 for c in after if c in before and after[c] < before[c]):
                    gained = True
                    break
            if not gained:
                out.append(Problem("PP04", seam[0], seam[1], "breaking this seam changes nothing (no ground joined, no way shortened by 6 cells from an HQ)"))
    return out


SEA_MIN = 12


def ports(G):
    """PT01: every port (own or neutral) touches navigable sea of a body of 12 or more cells (AW2's smallest is 23, Dual Strike's 16), so a ship built there can leave. On a wasteland map
    (Dual Strike's look 3) the water is drawn as lava, which no ship sails: a port there leads nowhere."""
    out = []
    cells = G.cells("Pp")
    if not cells:
        return out
    lava = load.look_of(G.m.name) == 3
    body = {}
    for y in range(G.h):
        for x in range(G.w):
            if G.g[y][x] in "~r" and (x, y) not in body:
                comp, todo = {(x, y)}, [(x, y)]
                while todo:
                    a, b = todo.pop()
                    for dx, dy in D4:
                        c = (a + dx, b + dy)
                        if c not in comp and G.at(*c) in "~r,":
                            comp.add(c)
                            todo.append(c)
                for c in comp:
                    body[c] = len(comp)
    for x, y in cells:
        size = max([body.get((x + dx, y + dy), 0) for dx, dy in D4] + [0])
        if lava and size:
            out.append(Problem("PT01", x, y, "the port opens on lava (a wasteland map's water): no ship sails there"))
        elif size < SEA_MIN:
            out.append(Problem("PT01", x, y, f"the port's sea is a body of {size} cells (at least {SEA_MIN}: a ship built here must be able to leave)"))
    return out


def armies(G):
    """AR01 / AR02: every army its own colour, at most one HQ each."""
    out = []
    cols = list(G.m.meta.get("colours") or [])
    n = int(G.m.meta.get("armies") or len(cols) or 0)
    cols = cols[:n]
    for c in sorted({c for c in cols if cols.count(c) > 1}):
        out.append(Problem("AR01", -1, -1, f"{cols.count(c)} armies wear colour {c} (colours {cols})"))
    hq = {}
    for y in range(G.h):
        for x in range(G.w):
            t = G.t[y][x]
            if G.g[y][x] == "H" and G.T.owner(t):
                hq.setdefault(G.T.owner(t), []).append((x, y))
    for o, cells in hq.items():
        if len(cells) > 1:
            out.append(Problem("AR02", cells[1][0], cells[1][1], f"army {o} has {len(cells)} HQs at {cells}"))
    return out


def design_checks(G):
    from . import design
    return design.checks(G)


# Findings in the BH Campaign's and Versus maps that the user has not approved changing: reported, not failing (map name -> rule -> how many). Never add to it for an Emerald Sun map.
KNOWN = {"bh10": {"RV05": 1}, "bh31": {"RV05": 1}, "bh30": {"AR02": 1}}


CHECKS = [river, bridges, sea, joins, roads, pipes, garbage, access, units, spawned, reach, inventions, armies, reachables, pipelines, ports, design_checks]


def lint(m, only=None):
    G = Grid(m)
    probs = []
    for fn in CHECKS:
        probs += fn(G)
    probs = [p for p in probs if not only or p.rule in only]
    # one report per (rule, cell, message)
    uniq = {}
    for p in probs:
        uniq.setdefault((p.rule, p.x, p.y, p.msg), p)
    return sorted(uniq.values(), key=lambda p: (p.rule, p.y, p.x))
