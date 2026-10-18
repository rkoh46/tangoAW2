#!/usr/bin/env python3
"""Generates the 5-army pre-deployed map of five/maps.txt (the block `map <NAME>` .. its rows).

Five armies on a regular pentagon around a central lagoon: the terrain is one sector (the army's axis, mirrored left
and right) turned by 72 degrees, sampled on the grid, so the map is 5-fold symmetric up to rounding. No base, airport
or port at all (neutral or owned): the armies fight with what they start with.

usage: pentagon.py [--print]      prints the map block (rows included) for maps.txt, and checks connectivity
"""
import math
import sys

W = H = 35
CX = CY = 17
NAME = 'Pentagon Atoll'
AXES = [math.radians(-90 + 72 * k) for k in range(5)]
LAGOON = 3.3
RING = 8.4


# the river pieces the game draws (map.py RIVER), by what lies N, E, S, W of the cell (r river, s sea, l land)
VALID_RIVER = {'rlrl', 'lrlr', 'llrr', 'lrrl', 'rllr', 'rrll', 'rrlr', 'rrrl', 'rlrr', 'lrrr', 'rrrr', 'llrl', 'rlll', 'lrll',
               'lllr', 'slrl', 'rlsl', 'lslr', 'lrls', 'rsss', 'ssrs', 'sssr', 'srss'}
SEA_END = {'slrl', 'rlsl', 'lslr', 'lrls', 'rsss', 'ssrs', 'sssr', 'srss'}


def river_key(g, x, y):
    cell = lambda px, py: g[py][px] if 0 <= px < W and 0 <= py < H else '~'
    around = [(x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)]
    return around, ''.join('r' if cell(*p) in '-=' else 's' if cell(*p) == '~' else 'l' for p in around)


def try_river(g, k):
    """Draws river k (the border after army k's axis) as one channel from the lagoon to the outer sea in a copy of g: the
    first line that the game can draw end to end (every piece one it has, both ends running straight into the sea,
    the water beside an end or a bend shaved to land). Returns (the grid, the river's cells), or None."""
    a = AXES[k] + math.radians(36)
    for eps in (0.0, 0.3, -0.3, 0.6, -0.6, 0.9, -0.9, 1.2, -1.2):
        for swap in (False, True):
            def pt(r):
                return (round(CX + r * math.cos(a) - eps * math.sin(a)), round(CY + r * math.sin(a) + eps * math.cos(a)))
            p0, p1 = pt(2.2), pt(17.0)
            p1 = (min(max(p1[0], 0), W - 1), min(max(p1[1], 0), H - 1))
            path = line(p0, p1) if not swap else [(x, y) for y, x in line(p0[::-1], p1[::-1])]
            h = [row[:] for row in g]
            cells = [(x, y) for x, y in path if h[y][x] != '~']
            for x, y in cells:
                h[y][x] = '-'
            ok = True
            for _ in range(6):
                for x, y in cells:
                    around, key = river_key(h, x, y)
                    for i, (px, py) in enumerate(around):
                        # sea beside the channel (not the one it runs on into) becomes land
                        if key[i] == 's' and 0 <= px < W and 0 <= py < H and not (key.count('r') == 1 and key[(i + 2) % 4] == 'r'):
                            h[py][px] = '.'
            ends = []
            for x, y in cells:
                around, key = river_key(h, x, y)
                if key not in VALID_RIVER:
                    ok = False
                if key in SEA_END:
                    ends.append((x, y))
            if ok and len(ends) == 2:
                return h, cells
    return None


def fold(x, y):
    """(sector, u, v, psi): the cell in the frame of the nearest army's axis (u along it, v the distance beside it)."""
    dx, dy = x - CX, y - CY
    r = math.hypot(dx, dy)
    if r == 0:
        return 0, 0, 0, 0, 0
    phi = math.atan2(dy, dx)
    best = min(range(5), key=lambda k: abs(math.remainder(phi - AXES[k], 2 * math.pi)))
    psi = math.remainder(phi - AXES[best], 2 * math.pi)
    return best, r * math.cos(psi), abs(r * math.sin(psi)), psi, r


def place(k, u, v):
    """The cell of the template point (u, v) turned to army k's sector."""
    a = AXES[k] + math.atan2(v, u)
    r = math.hypot(u, v)
    return round(CX + r * math.cos(a)), round(CY + r * math.sin(a))


def line(a, b):
    """The cells of a 4-connected path from a to b."""
    (x0, y0), (x1, y1) = a, b
    cells = [(x0, y0)]
    n = max(abs(x1 - x0), abs(y1 - y0))
    for i in range(1, n + 1):
        x, y = round(x0 + (x1 - x0) * i / n), round(y0 + (y1 - y0) * i / n)
        px, py = cells[-1]
        if x != px and y != py:
            cells.append((x, py))
        cells.append((x, y))
    return cells


def arc(k, r, d0, d1, steps=90):
    """4-connected cells of the arc of radius r in sector k from d0 to d1 degrees off the axis."""
    pts = []
    for i in range(steps + 1):
        a = AXES[k] + math.radians(d0 + (d1 - d0) * i / steps)
        pts.append((round(CX + r * math.cos(a)), round(CY + r * math.sin(a))))
    cells = [pts[0]]
    for p in pts[1:]:
        if p == cells[-1]:
            continue
        px, py = cells[-1]
        if p[0] != px and p[1] != py:
            cells.append((p[0], py))
        cells.append(p)
    return cells


# (u, v, radius, kind): a wood ('f') or mountain ('^') blob in the template, mirrored left and right
BLOBS = [
    (10.4, 5.2, 1.5, 'f'), (7.4, 6.6, 1.2, '^'), (11.8, 8.6, 1.4, '^'), (14.0, 3.0, 1.1, 'f'),
    (6.4, 3.6, 1.0, 'f'), (9.6, 9.2, 1.1, 'f'), (4.6, 5.0, 0.9, '^'), (13.4, 5.6, 0.8, '^'),
    (8.6, 1.9, 0.8, '^'), (12.2, 2.4, 0.9, '^'), (7.0, 9.0, 1.0, '^'), (10.6, 1.2, 0.8, 'f'),
]
HQ = (12.6, 0.0)
# each army's cities (u, v) and the neutral ones on the borders between armies (radius, degrees off the axis)
CITIES = [(9.0, 3.6), (9.0, -3.6), (5.9, 0.0), (12.4, 6.6), (12.4, -6.6)]
BORDER_CITIES = [(6.6, 36.0), (10.2, 36.0), (13.2, 36.0)]
# The forces each army starts with, 40 units (unit types as in map.py), as (type, u, v): the template's cells, turned to each army.
# Front: 5 infantry, 5 mech and the armour; middle: recon, supply, anti-air; rear: indirects; flanks: air (with the
# APCs and a T-Copter to resupply it). Megatank and Stealth are Dual Strike's: the map is listed only with the pack.
def force_template():
    inf, mech, tank, md, neo, mega = 1, 2, 5, 3, 8, 4
    recon, apc, aa, missiles, art, rockets = 6, 7, 14, 15, 10, 11
    bc, fighter, bomber, stealth, tc = 19, 16, 17, 12, 20
    rows = [
        (9.0, [inf, inf, inf, inf, inf]),
        (10.0, [mech, mech, mech, mech, mech]),
        (11.0, [tank, tank, md, mega, md]),
        (12.0, [tank, tank, tank, md, neo]),
        (13.0, [recon, recon, recon, apc, apc]),
        (14.0, [aa, aa, missiles, art, art]),
        (15.0, [art, rockets, rockets, bc, bc]),
    ]
    out = []
    for u, kinds in rows:
        for i, k in enumerate(kinds):
            out.append((k, u, (i - 2) * 2.0 + (1.0 if k in (inf, mech) and False else 0.0)))
    # the air forces beside the HQ's row
    out += [(bc, 12.6, -6.5), (fighter, 12.6, 6.5), (bomber, 14.0, -6.5), (stealth, 14.0, 6.5), (tc, 12.6, -4.5)]
    return out


def place_forces(rows):
    """The forces' cells: each template cell turned to the army's sector, then the nearest free ground (plain or wood) of
    that army that no unit has yet. Returns {army: [(type, x, y)]}."""
    hqs = {}
    for y, r in enumerate(rows):
        for x, c in enumerate(r):
            if c in '12345':
                hqs[int(c)] = (x, y)
    owner = lambda x, y: min(hqs, key=lambda a: (abs(hqs[a][0] - x) + abs(hqs[a][1] - y), a))
    used, out = set(), {}
    for k in range(5):
        army = k + 1
        for kind, u, v in force_template():
            a = AXES[k] + math.atan2(v, u)
            r = math.hypot(u, v)
            fx, fy = CX + r * math.cos(a), CY + r * math.sin(a)
            cands = [(math.hypot(x - fx, y - fy), x, y) for y in range(H) for x in range(W)
                     if rows[y][x] in '.f' and (x, y) not in used and owner(x, y) == army]
            _, x, y = min(cands)
            used.add((x, y))
            out.setdefault(army, []).append((kind, x, y))
    return out


def build():
    g = [['.'] * W for _ in range(H)]
    owner_of = {}
    for y in range(H):
        for x in range(W):
            k, u, v, psi, r = fold(x, y)
            coast = 15.4 + 1.0 * math.cos(5 * psi)
            if r < LAGOON or r > coast:
                g[y][x] = '~'
                continue
            for (bu, bv, br, kind) in BLOBS:
                if math.hypot(u - bu, v - bv) <= br:
                    g[y][x] = kind
    # rivers along the borders between the armies, between the lagoon and the coast (open at both ends: the land
    # goes round them), crossed by a bridge on the ring road
    rivers = []
    for k in range(5):
        found = try_river(g, k)
        assert found is not None, ('no river fits', k)
        g[:], cells = found[0], found[1]
        rivers.append(cells)
    # roads: each army's axis from its HQ to the lagoon, and a ring through the sectors
    roads = set()
    ring = []
    for k in range(5):
        hq = place(k, *HQ)
        a = AXES[k]
        shore = (round(CX + 4.3 * math.cos(a)), round(CY + 4.3 * math.sin(a)))
        roads.update(line(hq, shore))
        cells = arc(k, RING, -33, 33)
        ring.append(cells)
        roads.update(cells)
    # the bridges: a straight stretch of each river near the ring, with a road on each side of it, joined to the ring
    isriver = lambda x, y: g[y][x] == '-'
    for k, path in enumerate(rivers):
        best = None
        for (x, y) in path[1:-1]:
            n, e, s, w = isriver(x, y - 1), isriver(x + 1, y), isriver(x, y + 1), isriver(x - 1, y)
            straight = (n and s and not e and not w) or (e and w and not n and not s)
            if straight:
                d = abs(math.hypot(x - CX, y - CY) - RING)
                if best is None or d < best[0]:
                    best = (d, x, y, n and s)
        d, x, y, vertical = best
        g[y][x] = '='
        stubs = [(x - 1, y), (x + 1, y)] if vertical else [(x, y - 1), (x, y + 1)]
        for sx, sy in stubs:
            sector_cells = ring[k] if math.remainder(math.atan2(sy - CY, sx - CX) - AXES[k], 2 * math.pi) < 0.6 * 2 * math.pi / 5 and \
                math.remainder(math.atan2(sy - CY, sx - CX) - AXES[k], 2 * math.pi) > 0 else ring[(k + 1) % 5]
            near = min(sector_cells, key=lambda c: abs(c[0] - sx) + abs(c[1] - sy))
            for px, py in line((sx, sy), near):
                if g[py][px] in '.f^R':
                    roads.add((px, py))
            roads.add((sx, sy))
    for x, y in roads:
        if g[y][x] in '.f^':
            g[y][x] = 'R'
    # properties
    props = {}
    def setp(x, y, ch):
        g[y][x] = ch
        props[(x, y)] = ch
    for k in range(5):
        hx, hy = place(k, *HQ)
        setp(hx, hy, str(k + 1))
        for (u, v) in CITIES:
            x, y = place(k, u, v)
            if g[y][x] != '~':
                setp(x, y, 'C')
    for k in range(5):
        for (r, deg) in BORDER_CITIES:
            a = AXES[k] + math.radians(deg)
            x, y = round(CX + r * math.cos(a)), round(CY + r * math.sin(a))
            # (beside the river, on the land)
            for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)]:
                if g[y + dy][x + dx] in '.f^R':
                    setp(x + dx, y + dy, 'c')
                    break
    return [''.join(r) for r in g]


def check(rows):
    """Every property can be reached on foot from every HQ (rivers only at bridges)."""
    land = lambda x, y: 0 <= x < W and 0 <= y < H and rows[y][x] not in '~-'
    hq = {int(c): (x, y) for y, r in enumerate(rows) for x, c in enumerate(r) if c in '12345'}
    start = hq[1]
    seen = {start}
    todo = [start]
    while todo:
        x, y = todo.pop()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n not in seen and land(*n):
                seen.add(n)
                todo.append(n)
    miss = [(x, y, c) for y, r in enumerate(rows) for x, c in enumerate(r) if c in '12345Ccp' and (x, y) not in seen]
    return miss


def violations_of(rows, rom_state):
    """(count, cells) of the tiles not as the game draws them (five/tilecheck.py), or None when a tile has no drawing."""
    import map as mappy
    import tilecheck
    rom, seen, rules, edge = rom_state
    m = {'name': NAME, 'rows': rows, 'armies': 5, 'colours': [1, 2, 3, 4, 5], 'units': {}, 'wasteland': False}
    try:
        t = mappy.tiles(m, edge)
    except AssertionError:
        return None
    v = tilecheck.violations(t, seen, tilecheck.structure_cells(t) | tilecheck.editor_sea(t, rom)) + tilecheck.mountain_violations(t, rules)
    cells = set()
    for x, y, (a, d, b) in v:
        cells.add((x, y))
        if d == 'E':
            cells.add((x + 1, y))
        elif d == 'S':
            cells.add((x, y + 1))
    return len(v), cells


def fix(rows, rom_path):
    """Local edits (a road piece to plain, a wood to plain ...) until every tile is as the game draws it."""
    import map as mappy
    import tilecheck
    rom = open(rom_path, 'rb').read()
    state = (rom, tilecheck.learn(rom), tilecheck.mountain_rules(rom), mappy.sea_edges(rom))
    rows = [list(r) for r in rows]
    best = violations_of([''.join(r) for r in rows], state)
    for _ in range(200):
        if best is not None and best[0] == 0:
            break
        cells = sorted(best[1]) if best else [(x, y) for y in range(H) for x in range(W)]
        # (also the neighbours: a road bend is mended by its neighbour as often as by itself)
        around = set(cells)
        for x, y in cells:
            around.update((x + dx, y + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1))
        tried = None
        for x, y in sorted(around):
            if not (0 <= x < W and 0 <= y < H) or rows[y][x] in '12345Cc~=':
                continue
            old = rows[y][x]
            for new in '.Rf^=':
                if new == old or (new == '=' and old != '-') or (old == '-' and new != '.' and new != '='):
                    continue
                rows[y][x] = new
                v = violations_of([''.join(r) for r in rows], state)
                rows[y][x] = old
                if v is not None and (best is None or v[0] < best[0]) and (tried is None or v[0] < tried[0]):
                    tried = (v[0], x, y, new, v)
        if tried is None:
            break
        rows[tried[2]][tried[1]] = tried[3]
        best = tried[4]
    return [''.join(r) for r in rows], best


def main():
    rows = build()
    if len(sys.argv) > 2 and sys.argv[1] == '--fix':
        rows, left = fix(rows, sys.argv[2])
        print('violations left:', left and left[0], file=sys.stderr)
    miss = check(rows)
    if miss:
        print('unreachable:', miss, file=sys.stderr)
    out = [f'map {NAME}', 'armies 5 9 1 2 3 4 5']
    for a, units in sorted(place_forces(rows).items()):
        for kind, x, y in units:
            out.append(f'at {a} {kind} {x} {y}')
    out += rows
    print('\n'.join(out))
    counts = {c: sum(r.count(c) for r in rows) for c in '12345Cc'}
    print(counts, file=sys.stderr)


if __name__ == '__main__':
    main()
