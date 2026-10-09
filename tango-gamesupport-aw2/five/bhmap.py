#!/usr/bin/env python3
"""The BH Campaign's map tool: text maps -> `src/bh_map_data.rs`, with the
tiles joined as Advance Wars 2 draws them and the maps checked.

Usage:  bhmap.py <rom.gba> [maps.txt ...]    (default: five/bh/*.txt)
        bhmap.py --check <rom.gba> [maps.txt ...]   (checks only, writes nothing)

A map file is `five/maps.txt`'s format (legend in five/map.py: sea, reef,
plain, wood, mountain, road, pipe, river, bridge, shoal, properties, Black
Hole's inventions ...: every road, river, pipe, sea edge, coast, shoal and
mountain is drawn by the rules learned from the game's own maps) with these
lines more, before a map's rows:

    team 1 2 1 1 2          the armies' teams (default: every army its own)
    objective 1 3           the armies that must reach every enemy HQ (default: army 1,
                            the player's; an army the computer holds back needs not)
    unit ARMY TYPE X Y [hp=1..100] [hold] [name=courier]
                            a unit placed on a cell (the `units` lines of
                            maps.txt, which place units by rule, are not
                            used here); a `name` is the mission's handle for
                            it (UnitDef::named): its death latch is its id

A mission uses it as `MapSrc::Built("name")` (its units too, unless the
mission lists its own).

Checks (every problem is printed; the exit status is 1 if there is one):
  - every tile as the game draws it (five/tilecheck.py);
  - every army that has an objective (army 1 unless `objective` says
    more) can reach it: from its HQ by land to each enemy HQ, or, where the sea or a river is between, it has the ships and
    Landers that can (below) or aircraft;
  - every Lander can load at a port or beach (a shoal) next to land its
    army stands on, and has a beach to unload on next to land with
    something on it (an enemy HQ, a property, units) that its own land does
    not reach;
  - no stranded island: land with properties or units that no army's
    ground units, and no Lander, can reach;
  - no unit boxed in (every neighbour cell closed to it).
"""
import collections
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import map as mappy        # noqa: E402
import tilecheck           # noqa: E402

FOOT, TIRES, TREADS, SEA, LANDER, AIR, PIPE = 'foot', 'tires', 'treads', 'sea', 'lander', 'air', 'pipe'
CLASS = {1: FOOT, 2: FOOT, 3: TREADS, 4: TREADS, 5: TREADS, 6: TIRES, 7: TREADS, 8: TREADS, 9: PIPE, 10: TREADS,
         11: TIRES, 12: AIR, 13: AIR, 14: TREADS, 15: TIRES, 16: AIR, 17: AIR, 18: SEA, 19: AIR, 20: AIR,
         21: SEA, 22: SEA, 23: LANDER, 24: SEA, 26: SEA, 27: FOOT}
UNIT_NAMES = {1: 'Infantry', 2: 'Mech', 3: 'Md Tank', 4: 'Megatank', 5: 'Tank', 6: 'Recon', 7: 'APC', 8: 'Neotank',
              9: 'Piperunner', 10: 'Artillery', 11: 'Rockets', 12: 'Stealth', 13: 'Black Bomb', 14: 'Anti-Air',
              15: 'Missiles', 16: 'Fighter', 17: 'Bomber', 18: 'Black Boat', 19: 'B Copter', 20: 'T Copter',
              21: 'Battleship', 22: 'Cruiser', 23: 'Lander', 24: 'Submarine', 26: 'Carrier', 27: 'Oozium'}
STRUCTURE = set('SNWELvnFVDXO#')
LAND_PROPS = set('HBCAPbcapTt12345')


def passable(c, cls, around=''):
    """May a unit of movement class `cls` stand on the map character `c`?"""
    if cls == AIR:
        return True
    if c in STRUCTURE:
        return False
    if cls == PIPE:
        return c in 'IZ' or c in 'BCAHb'
    if c in 'IZ':
        return False
    if cls == SEA:
        return c in '~r' or c in 'Pp' or (c == '=' and '~' in around)
    if cls == LANDER:
        return c in '~r,' or c in 'Pp' or (c == '=' and '~' in around)
    if c in '~r':
        return False
    if cls == FOOT:
        return True
    # vehicles: no mountains, no open river (a bridge crosses it)
    return c not in '^-'


def parse(paths):
    maps = []
    for path in paths:
        lines, extra = [], {}
        cur = None
        for line in open(path):
            s = line.rstrip('\n')
            if s.startswith('map '):
                cur = s[4:].strip()
                extra[cur] = {'units': [], 'team': None, 'objective': [1]}
            if cur and s.startswith('objective '):
                extra[cur]['objective'] = [int(x) for x in s.split()[1:]]
                continue
            if cur and s.startswith('team '):
                extra[cur]['team'] = [int(x) for x in s.split()[1:]]
                continue
            if cur and s.startswith('unit '):
                f = s.split()
                u = {'army': int(f[1]), 'kind': int(f[2]), 'x': int(f[3]), 'y': int(f[4]), 'hp': 100, 'hold': False, 'name': ''}
                for opt in f[5:]:
                    if opt.startswith('hp='):
                        u['hp'] = int(opt[3:])
                    elif opt == 'hold':
                        u['hold'] = True
                    elif opt.startswith('name='):
                        u['name'] = opt[5:]
                extra[cur]['units'].append(u)
                continue
            lines.append(line)
        tmp = path + '.parse.tmp'
        open(tmp, 'w').writelines(lines)
        try:
            for m in mappy.parse(tmp):
                m.update(extra[m['name']])
                maps.append(m)
        finally:
            os.remove(tmp)
    return maps


# --- Checks -------------------------------------------------------------------------

def reach(rows, start, cls):
    """The cells a unit of class `cls` reaches from `start` (4-neighbour)."""
    h, w = len(rows), len(rows[0])
    ch = lambda x, y: rows[y][x]

    def around(x, y):
        return ''.join(ch(X, Y) for X, Y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)) if 0 <= X < w and 0 <= Y < h)

    seen, todo = {start}, [start]
    while todo:
        x, y = todo.pop()
        for X, Y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)):
            if 0 <= X < w and 0 <= Y < h and (X, Y) not in seen and passable(ch(X, Y), cls, around(X, Y)):
                seen.add((X, Y))
                todo.append((X, Y))
    return seen


def components(rows, cls):
    h, w = len(rows), len(rows[0])
    around = lambda x, y: ''.join(rows[Y][X] for X, Y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y)) if 0 <= X < w and 0 <= Y < h)
    left = {(x, y) for y in range(h) for x in range(w) if passable(rows[y][x], cls, around(x, y))}
    comps = []
    while left:
        c = reach(rows, next(iter(left)), cls)
        c &= left | c
        comps.append(c)
        left -= c
    return comps


def check_reach(m):
    rows = m['rows']
    h, w = len(rows), len(rows[0])
    ch = lambda x, y: rows[y][x]
    n = m['armies']
    team = m.get('team') or list(range(1, n + 1))
    hqs = {int(ch(x, y)): (x, y) for y in range(h) for x in range(w) if ch(x, y) in '12345'}
    units = m['units']
    problems = []
    name = m['name']
    by_army = collections.defaultdict(list)
    for u in units:
        by_army[u['army']].append(u)
        if not (0 <= u['x'] < w and 0 <= u['y'] < h):
            problems.append(f'{name}: unit {UNIT_NAMES.get(u["kind"], u["kind"])} of army {u["army"]} is off the map at ({u["x"]}, {u["y"]})')
            continue
        cls = CLASS.get(u['kind'], FOOT)
        around = ''.join(ch(X, Y) for X, Y in ((u['x'], u['y'] - 1), (u['x'] + 1, u['y']), (u['x'], u['y'] + 1), (u['x'] - 1, u['y'])) if 0 <= X < w and 0 <= Y < h)
        if not passable(ch(u['x'], u['y']), cls, around):
            problems.append(f'{name}: {UNIT_NAMES.get(u["kind"], u["kind"])} of army {u["army"]} stands on {ch(u["x"], u["y"])!r} at ({u["x"]}, {u["y"]}), which its kind cannot enter')
        elif len(reach(rows, (u['x'], u['y']), cls)) == 1:
            problems.append(f'{name}: {UNIT_NAMES.get(u["kind"], u["kind"])} of army {u["army"]} at ({u["x"]}, {u["y"]}) is boxed in')
    foot = {a: reach(rows, hqs[a], FOOT) for a in hqs}
    # Objectives: every enemy HQ.
    for a in m.get('objective', [1]):
        mine = by_army[a]
        has_air = any(CLASS.get(u['kind']) == AIR for u in mine)
        landers = [u for u in mine if u['kind'] == 23]
        for b in hqs:
            if team[a - 1] == team[b - 1] or hqs[b] in foot[a]:
                continue
            if has_air:
                continue
            if not landers:
                problems.append(f'{name}: army {a} cannot reach army {b}\'s HQ by land and has no Lander or aircraft')
    # Landers.
    useful = lambda x, y: ch(x, y) in LAND_PROPS or any((u['x'], u['y']) == (x, y) for u in units)
    for u in units:
        if u['kind'] != 23 or not (0 <= u['x'] < w and 0 <= u['y'] < h):
            continue
        a = u['army']
        sea = reach(rows, (u['x'], u['y']), LANDER)
        beaches = [(x, y) for (x, y) in sea if ch(x, y) in ',Pp' or (ch(x, y) in '~' and False)]
        own = foot.get(a, set())
        def land_next(cell):
            x, y = cell
            return [(X, Y) for X, Y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))
                    if 0 <= X < w and 0 <= Y < h and passable(ch(X, Y), FOOT) and ch(X, Y) not in '~r']
        # Where its army loads: a beach or port in its reach next to its own land (or a shoal that is part of it).
        loads = [c for c in beaches if any(n in own for n in land_next(c)) or c in own]
        if not loads:
            problems.append(f'{name}: the Lander of army {a} at ({u["x"]}, {u["y"]}) has no port or beach to load at next to its army\'s land')
        # Where it unloads: a beach next to land its army does not reach by foot, with something on it.
        unload = []
        for c in beaches:
            for n in land_next(c):
                if n in own:
                    continue
                comp = reach(rows, n, FOOT)
                if any(useful(x, y) for (x, y) in comp if ch(x, y) not in ',~'):
                    unload.append(c)
                    break
        if not unload:
            problems.append(f'{name}: the Lander of army {a} at ({u["x"]}, {u["y"]}) has no beach to unload on next to useful land its army cannot walk to')
    # Stranded islands: land with properties or units that nobody reaches.
    comps = components(rows, FOOT)
    for comp in comps:
        things = [(x, y) for (x, y) in comp if ch(x, y) in LAND_PROPS or any((u['x'], u['y']) == (x, y) for u in units)]
        if not things or any(c in comp for c in hqs.values()):
            continue
        walkers = any(CLASS.get(u['kind'], FOOT) in (FOOT, TIRES, TREADS) and (u['x'], u['y']) in comp for u in units)
        if walkers:
            continue
        # reached by a Lander: a beach or port of the component in some Lander's sea.
        landed = False
        for u in units:
            if u['kind'] == 23 and 0 <= u['x'] < w and 0 <= u['y'] < h:
                sea = reach(rows, (u['x'], u['y']), LANDER)
                for (x, y) in comp:
                    if any((X, Y) in sea for X, Y in ((x, y - 1), (x + 1, y), (x, y + 1), (x - 1, y))):
                        landed = True
        if not landed and not any(CLASS.get(u['kind']) == AIR for u in units):
            problems.append(f'{name}: stranded island: {len(comp)} cells with properties or units at {sorted(things)[:3]} that no army and no Lander reaches')
    return problems


def check_tiles(m, rom, edge, learned, rules):
    rows = mappy.tiles(m, edge)
    vs = tilecheck.violations(rows, learned, tilecheck.structure_cells(rows) | tilecheck.editor_sea(rows, rom)) + tilecheck.mountain_violations(rows, rules)
    return rows, [f'{m["name"]}: {tilecheck.describe(v)}' for v in vs]


def rust(maps_tiles):
    o = ['// Generated by five/bhmap.py from five/bh/*.txt; do not edit.\n\n',
         'use crate::custom_campaign::{BuiltMap, BuiltUnit};\n\n', 'pub static MAPS: &[BuiltMap] = &[\n']
    for m, rows in maps_tiles:
        h, w = len(rows), len(rows[0])
        o.append(f'    BuiltMap {{\n        name: "{m["name"]}",\n        width: {w},\n        height: {h},\n        armies: {m["armies"]},\n        tiles: &[\n')
        flat = [t for r in rows for t in r]
        for i in range(0, len(flat), 12):
            o.append('            ' + ', '.join(f'0x{t:03X}' for t in flat[i:i + 12]) + ',\n')
        o.append('        ],\n        units: &[\n')
        for u in m['units']:
            o.append(f'            BuiltUnit {{ army: {u["army"]}, kind: {u["kind"]}, x: {u["x"]}, y: {u["y"]}, hp: {u["hp"]}, hold: {str(u["hold"]).lower()}, name: "{u["name"]}" }},\n')
        o.append('        ],\n    },\n')
    o.append('];\n')
    return ''.join(o)


def main():
    args = sys.argv[1:]
    only = '--check' in args
    args = [a for a in args if a != '--check']
    rom = open(args[0], 'rb').read()
    files = args[1:] or sorted(os.path.join(HERE, 'bh', f) for f in os.listdir(os.path.join(HERE, 'bh')) if f.endswith('.txt')) if os.path.isdir(os.path.join(HERE, 'bh')) else []
    edge = mappy.sea_edges(rom)
    learned = tilecheck.learn(rom)
    rules = tilecheck.mountain_rules(rom)
    maps = parse(files)
    out, problems = [], []
    for m in maps:
        rows, tp = check_tiles(m, rom, edge, learned, rules)
        problems += tp + check_reach(m)
        out.append((m, rows))
        print(f'{m["name"]}: {len(rows[0])}x{len(rows)}, {len(m["units"])} units')
    for p in problems:
        print('PROBLEM', p)
    if not only:
        with open(os.path.join(HERE, '..', 'src', 'bh_map_data.rs'), 'w') as f:
            f.write(rust(out))
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
