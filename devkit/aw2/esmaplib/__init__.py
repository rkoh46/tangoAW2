"""Emerald Sun map generator: a map is a small Python spec (`five/es/spec/esNN.py`) that paints a `Canvas` and writes `five/es/esNN.txt`, the text map
`five/bhmap.py --campaign es` builds (legend: docs/dev/maps.md; rules: docs/dev/map-lint.md). The text file is generated: edit the spec, then run
`aw2dev maps gen` (all specs) and `aw2dev maps lint --source es`.

    from esmaplib import *
    m = Canvas("es01", 18, 14)               # filled with plain '.'
    m.rect("~", 0, 11, 17, 13)               # sea (inclusive corners)
    m.line("R", [(2, 3), (2, 8), (14, 8)])   # a road: straight legs, an L when two points are not in line
    m.river([(0, 5), (6, 5), (6, 9)])        # '-' ; m.bridge(x, y) puts '='
    m.blob("^", 9, 4, 3, 2, seed=1)          # an organic patch (mountains, woods, lakes)
    m.scatter("f", (0, 0, 17, 5), 0.2, seed=2)   # woods on 20% of the plain cells of a rectangle
    m.put("1", 3, 3); m.puts("C", [(5, 5), (6, 6)])
    m.unit(1, INF, 4, 4); m.units(1, MECH, [(5, 4), (6, 4)])
    m.header(armies=2, colours=(5, 3), objective=[1])
    m.write()                                # five/es/es01.txt (+ prints the map and the unit list)

Characters are the BH map legend: `~` sea, `r` reef, `.` plain, `f` wood, `^` mountain, `R` road, `I` pipe, `Z` pipe seam, `-` river, `=` bridge, `,` shoal,
`1`..`4` HQs, `B C A P` base / city / airport / port of the army whose HQ is nearest (`split`/`owners` change that), `b c a p` neutral ones,
inventions (only in a map with `blackhole`): `S N W E` minicannons, `L` laser, `v n` Black Cannon, `F` Factory, `D` Deathray, `X` Crystal, `O` Obelisk, `#` the rest of a footprint.
"""
import os
import random
from pathlib import Path

HERE = Path(__file__).resolve()
FIVE_DIR = HERE.parents[3] / "tango-gamesupport-aw2" / "five"
ES_DIR = FIVE_DIR / "es"
BH2_DIR = FIVE_DIR / "bh2"           # the BH2 Campaign's maps (docs/dev/bh2-maps.md): the same Canvas, specs in five/bh2/spec/bh2_NN.py

# unit kinds (AW2 / Dual Strike ids)
INF, MECH, MDT, MEGA, TANK, RECON, APC, NEO, PIPER, ART, ROCK = 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11
STEALTH, BBOMB, AA, MIS, FTR, BMB, BBOAT, BCO, TCO, BS, CR, LAN, SUB, CARR = 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 26
# colours
OS, BM, GE, YC, BH = 1, 2, 3, 4, 5
INVENTION_CHARS = set("SNWELvnFVDXOM#")
WATER = set("~r,")


class Canvas:
    def __init__(self, name, w, h, fill=".", campaign=None):
        self.name, self.w, self.h = name, w, h
        # (the campaign key: "bh2_NN" maps belong to the BH2 Campaign, the rest to Emerald Sun)
        self.campaign = campaign or ("bh2" if name.startswith("bh2_") else "es")
        self.dir = FIVE_DIR / self.campaign
        self.g = [[fill] * w for _ in range(h)]
        self.u = []                       # unit dicts
        self.hdr = {"armies": 2, "colours": (5, 3), "tab": 3, "team": None, "objective": [1], "owners": None, "split": None, "blackhole": False,
                    "comment": ""}
        self.notes = []                   # (key, x, y, text): named places, printed with the map and written as comments
        self.reserved = set()             # cells `spread` leaves free (a mission's reinforcement cells: `reserve`)

    # ---- painting ----
    def inside(self, x, y):
        return 0 <= x < self.w and 0 <= y < self.h

    def put(self, ch, x, y):
        if not self.inside(x, y):
            raise ValueError(f"{self.name}: ({x}, {y}) is off the {self.w}x{self.h} map")
        self.g[y][x] = ch
        return self

    def puts(self, ch, cells):
        for x, y in cells:
            self.put(ch, x, y)
        return self

    def get(self, x, y):
        return self.g[y][x] if self.inside(x, y) else "~"

    def rect(self, ch, x0, y0, x1, y1, only=None):
        for y in range(max(y0, 0), min(y1, self.h - 1) + 1):
            for x in range(max(x0, 0), min(x1, self.w - 1) + 1):
                if only is None or self.g[y][x] in only:
                    self.g[y][x] = ch
        return self

    def frame(self, ch, x0, y0, x1, y1):
        """The outline of a rectangle (a wall ring of mountains)."""
        self.rect(ch, x0, y0, x1, y0).rect(ch, x0, y1, x1, y1).rect(ch, x0, y0, x0, y1).rect(ch, x1, y0, x1, y1)
        return self

    def path(self, pts):
        """The cells of a polyline: straight legs; two points not in line are joined by an L (horizontal first)."""
        cells = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            legs = [(x0, y0, x1, y0), (x1, y0, x1, y1)] if x0 != x1 and y0 != y1 else [(x0, y0, x1, y1)]
            for ax, ay, bx, by in legs:
                n = max(abs(bx - ax), abs(by - ay))
                for k in range(n + 1):
                    c = (ax + (bx > ax) * k - (bx < ax) * k, ay + (by > ay) * k - (by < ay) * k)
                    if not cells or cells[-1] != c:
                        cells.append(c)
        return cells or [tuple(pts[0])]

    def line(self, ch, pts, over=None):
        """Paint a polyline with `ch`; `over` = the characters it may replace (default: everything but HQs and properties)."""
        keep = set("12345BCAPTQbcapt") | INVENTION_CHARS
        for x, y in self.path(pts):
            if self.inside(x, y) and (self.g[y][x] not in keep if over is None else self.g[y][x] in over):
                self.g[y][x] = ch
        return self

    def road(self, pts):
        return self.line("R", pts)

    def river(self, pts):
        return self.line("-", pts)

    def pipe(self, pts):
        return self.line("I", pts)

    def bridge(self, x, y, x2=None, y2=None):
        """One bridge cell, or a straight run from (x, y) to (x2, y2)."""
        for cx, cy in self.path([(x, y), (x if x2 is None else x2, y if y2 is None else y2)]):
            self.put("=", cx, cy)
        return self

    def blob(self, ch, cx, cy, rx, ry, seed=0, wobble=0.3, only=None):
        """An organic patch: an ellipse whose edge is jittered (deterministic for `seed`)."""
        rnd = random.Random(f"{self.name}/{seed}")
        for y in range(cy - ry - 2, cy + ry + 3):
            for x in range(cx - rx - 2, cx + rx + 3):
                if not self.inside(x, y):
                    continue
                d = ((x - cx) / max(rx, 0.5)) ** 2 + ((y - cy) / max(ry, 0.5)) ** 2
                if d <= 1 + (rnd.random() - 0.5) * 2 * wobble * (1 if d > 0.4 else 0) and (only is None or self.g[y][x] in only):
                    self.g[y][x] = ch
        return self

    def meander(self, ch, a, b, seed=0, amp=2, only=None):
        """A winding line of `ch` from `a` to `b` (4-connected, so a river or a road is one piece): it heads for `b` but steps sideways now and then, up to `amp`
        cells off the straight line, giving the bends AW2's rivers and roads have. Returns its cells in order (put bridges on some of them)."""
        rnd = random.Random(f"{self.name}/m{seed}")
        (x, y), (bx, by) = a, b
        cells = [(x, y)]
        horiz = abs(bx - x) >= abs(by - y)
        off = 0
        guard = 0
        while (x, y) != (bx, by) and guard < 4000:
            guard += 1
            along_done = (x == bx) if horiz else (y == by)
            across_done = (y == by) if horiz else (x == bx)
            r = rnd.random()
            step_across = (not across_done) and (along_done or r < 0.28) or (across_done and not along_done and r < 0.22 and abs(off) < amp)
            if step_across and not across_done:
                d = (1 if by > y else -1) if horiz else (1 if bx > x else -1)
            elif step_across and across_done:
                d = rnd.choice((-1, 1))
                if abs(off + d) > amp:
                    d = -d
                off += d
                # (a wander away from the line is walked back by the next across steps)
                x, y = (x, y + d) if horiz else (x + d, y)
                cells.append((x, y))
                continue
            else:
                d = None
            if d is not None:
                x, y = (x, y + d) if horiz else (x + d, y)
            else:
                x, y = (x + (1 if bx > x else -1), y) if horiz else (x, y + (1 if by > y else -1))
            cells.append((x, y))
        for cx, cy in cells:
            if self.inside(cx, cy) and (only is None or self.g[cy][cx] in only):
                keep = set("12345BCAPTQbcapt") | INVENTION_CHARS
                if self.g[cy][cx] not in keep:
                    self.g[cy][cx] = ch
        return cells

    def cluster(self, ch, cx, cy, n, seed=0, only="."):
        """About `n` cells of `ch` grown outward from (cx, cy) by a random walk: an irregular wood or mountain patch with no straight edge."""
        rnd = random.Random(f"{self.name}/c{seed}")
        cells = {(cx, cy)}
        todo = [(cx, cy)]
        while len(cells) < n and todo:
            x, y = rnd.choice(todo)
            dx, dy = rnd.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            c = (x + dx, y + dy)
            if self.inside(*c) and c not in cells:
                cells.add(c)
                todo.append(c)
        for x, y in cells:
            if self.g[y][x] in only:
                self.g[y][x] = ch
        return sorted(cells)

    def spread(self, army, kinds, box, seed=0, gap=1, avoid="~r=-^IZ#", prefer="fRC", **kw):
        """Place `kinds` ({kind: count}) for `army` inside `box` (x0, y0, x1, y1) in a loose formation instead of a block: no two units closer than `gap`
        cells (Chebyshev, 1 = never side by side on a row... 2 leaves a cell between), on ground their kind can stand on, woods and roads preferred for the
        heavy kinds. Deterministic for `seed`. Returns the cells."""
        rnd = random.Random(f"{self.name}/u{seed}")
        x0, y0, x1, y1 = box
        taken = {(u["x"], u["y"]) for u in self.u} | self.reserved
        placed = []
        foot = {INF, MECH}
        for kind, count in kinds.items():
            for _ in range(count):
                cand = []
                for y in range(y0, y1 + 1):
                    for x in range(x0, x1 + 1):
                        c = self.g[y][x] if self.inside(x, y) else "~"
                        if (x, y) in taken or c in avoid or c in "12345" and False:
                            continue
                        air = kind in (STEALTH, FTR, BMB, BCO, TCO)
                        if air:
                            if c in "~r" or (x, y) in taken:
                                continue
                        elif c in "f^" and kind not in foot:
                            continue
                        if c == "f" and kind in foot:
                            pass
                        if any(max(abs(x - a), abs(y - b)) < gap + 1 for a, b in placed):
                            continue
                        # (a unit needs ground to move on: two walkable neighbours for a vehicle, one for a foot soldier)
                        ok = ".R=,HBCAPTM" if kind not in foot else ".R=,HBCAPTMf"
                        if not air and sum(1 for a, b in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)) if self.get(a, b) in ok and (a, b) not in taken) < (1 if kind in foot else 2) and c not in "~":
                            continue
                        w = 1 + (3 if c in prefer and kind not in foot else 0) + (2 if c == "f" and kind in foot else 0)
                        cand.append(((x, y), w))
                if not cand:
                    raise ValueError(f"{self.name}: no room for {count} x unit {kind} in {box}")
                tot = sum(w for _, w in cand)
                r = rnd.random() * tot
                for c, w in cand:
                    r -= w
                    if r <= 0:
                        break
                self.unit(army, kind, c[0], c[1], **kw)
                placed.append(c)
                taken.add(c)
        return placed

    def reserve(self, cells):
        """Cells a mission spawns reinforcements on (the Rust's cell constants): `spread` never puts a start unit there."""
        self.reserved |= set(map(tuple, cells))
        return self

    def lake(self, cx, cy, n=12, seed=0, river_end=None):
        """A small lake of about `n` sea cells for a river to start in (AW2 has no source tile: a river starts at the map edge or in water). (cx, cy) is the cell beyond the river's
        last cell `river_end`. The map builder only draws a river mouth on a straight shore (the games' maps open their beach line for the river), so the lake has a
        flat 3-wide shore row at (cx, cy) with two rows of water behind it, and grows irregularly from there, never beside the river's last cell."""
        rnd = random.Random(f"{self.name}/l{seed}")
        ex, ey = river_end if river_end else (cx, cy + 1)
        dx, dy = cx - ex, cy - ey
        px, py = (dy, dx) if dx == 0 else (0, 1)          # (the shore row runs across the river's direction)
        px, py = abs(px), abs(py)
        occupied = {(u["x"], u["y"]) for u in self.u}
        cells = {(cx + dx * t + px * s, cy + dy * t + py * s) for t in range(2) for s in (-1, 0, 1)} - occupied
        todo = list(cells)
        guard = 0
        while len(cells) < n and todo and guard < 400:
            guard += 1
            x, y = rnd.choice(todo)
            ddx, ddy = rnd.choice(((1, 0), (-1, 0), (0, 1), (0, -1)))
            c = (x + ddx, y + ddy)
            ahead = (c[0] - ex) * dx + (c[1] - ey) * dy          # steps along the river's direction from its last cell
            if self.inside(*c) and c not in cells and ahead >= 2 and self.g[c[1]][c[0]] not in "12345BCAPTQbcapt-=RIZ#" and c not in occupied:
                cells.add(c)
                todo.append(c)
        for x, y in cells:
            if self.inside(x, y) and self.g[y][x] not in "12345BCAPTQbcapt-=RIZ#":
                self.g[y][x] = "~"
        return sorted(cells)

    def ragged(self, ch="^", longest=8, seed=0):
        """Breaks every straight line of `ch` longer than `longest` (away from the map edge) into a range: every few cells one is opened to plain and its mountain moves to the
        row (or column) beside it, so the line wanders instead of marching. Deterministic for `seed`."""
        rnd = random.Random(f"{self.name}/g{seed}")
        occupied = {(u["x"], u["y"]) for u in self.u}
        keep = set("12345BCAPTQbcapt-=RI")
        for horiz in (True, False):
            A, B = (self.w, self.h) if horiz else (self.h, self.w)
            for b in range(1, B - 1):
                a = 0
                while a < A:
                    cell = lambda aa: (aa, b) if horiz else (b, aa)
                    if self.g[cell(a)[1]][cell(a)[0]] == ch:
                        s0 = a
                        while a < A and self.g[cell(a)[1]][cell(a)[0]] == ch:
                            a += 1
                        if a - s0 > longest:
                            k = s0 + rnd.randint(3, 4)
                            while k < a - 1:
                                x, y = cell(k)
                                d = rnd.choice((-1, 1))
                                nx, ny = (x, y + d) if horiz else (x + d, y)
                                if (x, y) not in occupied:
                                    self.g[y][x] = "."
                                    if self.inside(nx, ny) and self.g[ny][nx] == "." and (nx, ny) not in occupied:
                                        self.g[ny][nx] = ch
                                k += rnd.randint(3, 5)
                    else:
                        a += 1
        return self

    def desertify(self, keep=0.35, rocks=6, size=5, seed=0):
        """Dresses a map for the desert look: only `keep` of the woods stay (sparse scrub), and `rocks` outcrops of about `size` mountain cells (rock and canyon walls in the desert
        tileset) are set on open plain away from roads, properties, rivers and units. Deterministic for `seed`."""
        rnd = random.Random(f"{self.name}/d{seed}")
        for y in range(self.h):
            for x in range(self.w):
                if self.g[y][x] == "f" and rnd.random() > keep:
                    self.g[y][x] = "."
        occupied = {(u["x"], u["y"]) for u in self.u}
        placed, tries = 0, 0
        while placed < rocks and tries < 400:
            tries += 1
            cx, cy = rnd.randrange(2, self.w - 2), rnd.randrange(2, self.h - 2)
            near = [self.get(x, y) for x in range(cx - 2, cx + 3) for y in range(cy - 2, cy + 3)]
            if any(c not in ".f^" for c in near) or any(abs(cx - ux) <= 2 and abs(cy - uy) <= 2 for ux, uy in occupied):
                continue
            self.cluster("^", cx, cy, size, seed=1000 * seed + tries)
            placed += 1
        return self

    def scatter(self, ch, box, p, seed=0, on="."):
        """`ch` on a share `p` of the cells of `box` (x0, y0, x1, y1) that hold one of `on`."""
        rnd = random.Random(f"{self.name}/s{seed}")
        x0, y0, x1, y1 = box
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if self.inside(x, y) and self.g[y][x] in on and rnd.random() < p:
                    self.g[y][x] = ch
        return self

    def beach(self, x0, y0, x1, y1):
        """Shoal ',' on every sea cell of the rectangle that touches land (a one-cell beach along a coast)."""
        for y in range(y0, y1 + 1):
            for x in range(x0, x1 + 1):
                if self.inside(x, y) and self.g[y][x] == "~" and any(self.inside(X, Y) and self.g[Y][X] not in WATER | set("=-")
                                                                        for X, Y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))):
                    self.g[y][x] = ","
        return self

    def mirror_x(self, x_from):
        """Copy columns 0..x_from-1 mirrored onto the right half (width must be 2 * x_from, or 2 * x_from + 1 with a centre column)."""
        for y in range(self.h):
            for x in range(x_from):
                self.g[y][self.w - 1 - x] = self.g[y][x]
        return self

    def set_rows(self, rows):
        assert len(set(len(r) for r in rows)) == 1, "rows differ in width"
        self.h, self.w = len(rows), len(rows[0])
        self.g = [list(r) for r in rows]
        return self

    def ascii(self, rows):
        """The whole map drawn by hand: one text row per map row, all `self.w` wide (the size given to the Canvas is kept and checked)."""
        rows = [r for r in rows]
        bad = [(i, len(r)) for i, r in enumerate(rows) if len(r) != self.w]
        if len(rows) != self.h or bad:
            raise ValueError(f"{self.name}: drawn rows are {len(rows)} (want {self.h}); rows of the wrong width (want {self.w}): {bad}")
        self.g = [list(r) for r in rows]
        return self

    def tidy(self):
        """Shoal cells the game has no tile for (a lone ford, shoal with land all round) become plain (five/map.py water_tile)."""
        import sys as _sys
        five = str(FIVE_DIR)
        if five not in _sys.path:
            _sys.path.insert(0, five)
        import map as mappy
        for _ in range(30):
            bad = False
            for y in range(self.h):
                for x in range(self.w):
                    if self.g[y][x] == ",":
                        look = [self.get(a, b) if self.inside(a, b) else "," for a, b in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))]
                        try:
                            mappy.water_tile(",", look)
                        except AssertionError:
                            self.g[y][x] = "."
                            bad = True
            if not bad:
                break
        return self

    def study(self):
        """The map as the design study sees it (devkit/aw2/maplint/study.py): no ROM needed, so a spec can be checked against the principles while it is drawn."""
        from ..maplint import study as st
        hq = {int(c): (x, y) for y, r in enumerate(self.g) for x, c in enumerate(r) if c in "12345"}
        owning = self.hdr.get("owners") or sorted(hq)
        split = self.hdr.get("split")

        def owner(x, y):
            if not hq:
                return 0
            if split:
                first, second = sorted(hq)[:2]
                return first if (y if split[0] == "y" else x) <= split[1] else second
            return min(owning, key=lambda a: (abs(hq[a][0] - x) + abs(hq[a][1] - y), a))
        g, own = [], []
        for y, r in enumerate(self.g):
            gr, orow = [], []
            for x, c in enumerate(r):
                if c in "12345":
                    gr.append("H"); orow.append(int(c))
                elif c == "Q":
                    gr.append("H"); orow.append(owner(x, y))
                elif c in "BCAPT":
                    gr.append(c); orow.append(owner(x, y))
                elif c in "bcapt":
                    gr.append(c.upper()); orow.append(0)
                elif c in INVENTION_CHARS and c != "M":
                    gr.append("#"); orow.append(0)
                else:
                    gr.append(c); orow.append(0)
            g.append(gr)
            own.append(orow)
        team = self.hdr.get("team")
        side = {i + 1: t for i, t in enumerate(team)} if team else {}
        return st.StudyMap(self.name, "es", g, own, side, list(self.u), 1, meta={"title": self.name})

    def principles(self):
        """The design-principle findings (MD01..MD08, docs/dev/map-design.md) of the map as drawn: a list of strings."""
        from ..maplint import principles
        return [str(p) for p in principles.check_study(self.study())]

    def thin_neutral_cities(self, fraction=0.12, keep=()):
        """Removes round(fraction x the neutral cities) (`c` only: no base, airport, port, tower, silo or owned property), the ones that add least:
        a city crowded by other properties (two cells or less) and lying by a road goes first; never one in `keep`, one on the coast, one in the contested middle
        (MD05's ring between two sides), or one whose loss breaks MD01 or MD02 (or MD06: then the cell becomes wood). The sides stay balanced: each removal is taken from the side
        (nearest HQ or start units) that holds more of the neutral cities left. The cell becomes wood if two or more woods are beside it, else plain.
        Deterministic. Returns (before, after, removed cells)."""
        from ..maplint import study as st
        from ..maplint import principles as pr
        cities = [(x, y) for y in range(self.h) for x in range(self.w) if self.g[y][x] == "c"]
        want = round(fraction * len(cities))
        sm = self.study()
        sd = st.sides_of(sm)
        anc = {s: st.anchor(sm, a) for s, a in sd.items()}
        anc = {s: p for s, p in anc.items() if p}
        mid = set()
        for s1, s2 in st.pairs(sm):
            a, b = anc.get(s1), anc.get(s2)
            if not a or not b:
                continue
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            rad = max(3, 0.2 * (abs(a[0] - b[0]) + abs(a[1] - b[1])))
            mid |= {c for c in cities if abs(c[0] - mx) + abs(c[1] - my) <= rad}
        # (a coast village is the landing's objective and its drawing is the coast's: kept)
        coast = {c for c in cities if any(self.get(c[0] + dx, c[1] + dy) in "~r," for dx in (-1, 0, 1) for dy in (-1, 0, 1))}
        keep = set(map(tuple, keep)) | mid | coast
        props = set(self.study().cells(st.PROPS))

        def side(c):
            return min(anc, key=lambda s: abs(anc[s][0] - c[0]) + abs(anc[s][1] - c[1])) if anc else 0

        def crowd(c):
            x, y = c
            n = sum(1 for X, Y in props if (X, Y) != c and max(abs(X - x), abs(Y - y)) <= 2)
            road = any(self.get(x + dx, y + dy) in "R=" for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)))
            return (n + (1 if road else 0), n, -x - y * self.w)

        def lonely():
            # (DQ08: a property with no road or other property within 5 cells)
            sm2 = self.study()
            ps = sm2.cells(st.PROPS)
            for x, y in ps:
                if sm2.g[y][x] == "H":
                    continue
                if not any(sm2.at(X, Y) in "R=" or ((X, Y) != (x, y) and (X, Y) in ps) for X in range(x - 5, x + 6) for Y in range(y - 5, y + 6)):
                    return True
            return False

        def passes():
            found = {p.split()[0] for p in self.principles()}
            return not ({"MD01", "MD02", "MD06"} & found) and not lonely()

        base_ok = passes()
        removed = []
        while len(removed) < want:
            left = [c for c in cities if c not in removed and c not in keep]
            if not left:
                break
            count = {}
            for c in left + [c for c in cities if c in keep and c not in removed]:
                count[side(c)] = count.get(side(c), 0) + 1
            rich = max(count, key=lambda s: count[s]) if count else None
            order = sorted(left, key=lambda c: (side(c) != rich, tuple(-v for v in crowd(c)[:2]), crowd(c)[2]))
            done = False
            for c in order:
                x, y = c
                woods = sum(1 for dx, dy in ((0, 1), (1, 0), (0, -1), (-1, 0)) if self.get(x + dx, y + dy) == "f")
                n_, e_, s_, w_ = (self.get(x, y - 1) in "R=", self.get(x + 1, y) in "R=", self.get(x, y + 1) in "R=", self.get(x - 1, y) in "R=")
                # (a city standing in a road's line gives its cell back to the road: no gap is left in it)
                covers = ("R",) if (n_ and s_) or (e_ and w_) else (("f", ".") if woods >= 2 else (".", "f"))
                for cover in covers:
                    self.g[y][x] = cover          # (plain, or wood where the woods are, or where plain would leave too open a field: MD06)
                    if not base_ok or passes():
                        removed.append(c)
                        props.discard(c)
                        done = True
                        break
                if done:
                    break
                self.g[y][x] = "c"
            if not done:
                break
        return len(cities), len(cities) - len(removed), removed

    def patch(self, x, y, rows):
        """Stamp text rows with their top-left at (x, y); a space leaves the cell alone."""
        for dy, r in enumerate(rows):
            for dx, c in enumerate(r):
                if c != " ":
                    self.put(c, x + dx, y + dy)
        return self

    # ---- units, header, notes ----
    def unit(self, army, kind, x, y, hold=False, hp=None, name=None):
        if not self.inside(x, y):
            raise ValueError(f"{self.name}: unit at ({x}, {y}) is off the map")
        self.u.append({"army": army, "kind": kind, "x": x, "y": y, "hp": hp, "hold": hold, "name": name})
        return self

    def units(self, army, kind, cells, **kw):
        for x, y in cells:
            self.unit(army, kind, x, y, **kw)
        return self

    def header(self, **kw):
        self.hdr.update(kw)
        n = self.hdr["armies"]
        self.hdr["tab"] = {2: 3, 3: 5, 4: 6}.get(n, 9)
        return self

    def note(self, key, x, y, text=""):
        """A named place the mission code uses (printed, and written as a comment)."""
        self.notes.append((key, x, y, text))
        return self

    # ---- output ----
    def rows(self):
        return ["".join(r) for r in self.g]

    def text(self):
        h = self.hdr
        out = [f"# {self.name}: generated by five/{self.campaign}/spec/{self.name}.py (aw2dev maps gen); edit the spec, not this file"]
        if h["comment"]:
            out.append("# " + h["comment"])
        for key, x, y, t in self.notes:
            out.append(f"# {key}: ({x}, {y}) {t}".rstrip())
        out += ["", f"map {self.name}", f"armies {h['armies']} {h['tab']} " + " ".join(str(c) for c in h["colours"])]
        if h["team"]:
            out.append("team " + " ".join(str(t) for t in h["team"]))
        if h["owners"]:
            out.append("owners " + " ".join(str(a) for a in h["owners"]))
        if h["split"]:
            out.append(f"split {h['split'][0]} {h['split'][1]}")
        if h["objective"] != [1]:
            out.append("objective " + " ".join(str(a) for a in h["objective"]))
        if h["blackhole"]:
            out.append("blackhole")
        for u in sorted(self.u, key=lambda u: (u["army"], u["kind"], u["y"], u["x"])):
            s = f"unit {u['army']} {u['kind']} {u['x']} {u['y']}"
            if u["hp"]:
                s += f" hp={u['hp']}"
            if u["hold"]:
                s += " hold"
            if u["name"]:
                s += f" name={u['name']}"
            out.append(s)
        out += self.rows()
        return "\n".join(out) + "\n"

    def preview(self):
        cells = {(u["x"], u["y"]): u for u in self.u}
        sym = {1: "i", 2: "m", 3: "T", 5: "t", 6: "r", 7: "a", 8: "N", 10: "A", 11: "K", 14: "G", 15: "M", 16: "F", 17: "B", 19: "H", 20: "h", 21: "Z", 22: "Y", 23: "L", 24: "U"}
        lines = ["    " + "".join(str(x % 10) for x in range(self.w))]
        for y, r in enumerate(self.g):
            lines.append(f"{y:3} " + "".join(str(cells[(x, y)]["army"]) if False else (sym.get(cells[(x, y)]["kind"], "u") if (x, y) in cells else c) for x, c in enumerate(r)))
        return "\n".join(lines)

    def write(self, quiet=False):
        self.dir.mkdir(parents=True, exist_ok=True)
        p = self.dir / f"{self.name}.txt"
        p.write_text(self.text())
        if not quiet:
            print(f"{self.name}: {self.w}x{self.h}, {len(self.u)} units -> {p.relative_to(self.dir.parents[2])}")
        return p


def load_spec(path):
    """Run a spec file and return the Canvas it leaves in `m` (or the one it returns from `build()`)."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("esspec_" + Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.build() if hasattr(mod, "build") else mod.m


def specs(campaign="es"):
    d = FIVE_DIR / campaign / "spec"
    return sorted(d.glob("es[0-9][0-9].py")) if campaign == "es" else sorted(d.glob(f"{campaign}_[0-9][0-9].py"))
