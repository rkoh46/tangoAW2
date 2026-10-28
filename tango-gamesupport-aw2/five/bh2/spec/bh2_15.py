"""BH2 M15 Every Colour (Act IV): the Orange Star border farmland. A free pair against one Orange Star army under the tag pair Max + Sami. Normal look, clear weather.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: a land border, not an island: wide open farmland that runs to the map's edges, with a coast on the north edge only (a strip of sea with two small harbours and reefs). Black Hole's column holds the west
(HQ, a base district), Max and Sami the east (HQ, a base district). One long river comes down from the north coast, bends five times and leaves the map at the south edge: the border. Four bridges carry the only roads across it: a north trunk, two farm tracks and a south trunk.
Roads are few; the country between them is big fields cut by hedgerows (thin belts of woods that run across the farmland with gates in them) and a few ridges, so the armies fight for the fields as much as the roads.
- Lanes: the two trunk roads, the two farm tracks, the hedgerow gates, the long river's four bridgeheads; the north coast's two harbours for the fleets.
- Where the fight happens: the second and third bridges (24,10) and (27,15) and the Com Towers (22,9) and (30,16) beside them.
- Properties: a farm village at each bridgehead and along the trunks, the two HQ districts, two harbours, a silo in the open middle field.
- Threats and answers: Max's Tanks and Md Tanks, Sami's foot soldiers -> Black Hole's Md Tanks, Rockets and artillery on the near bank; Orange Star fields no air, so neither army fields Anti-Air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 46, 26


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_15/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-1, 1])))
    return out


def build():
    m = Canvas("bh2_15", W, H)
    T = profile(0, W - 1, 2, 3, 1)
    for x in (25, 26, 27):
        T[x] = T[26]
    for x in range(W):
        m.rect("~", x, 0, x, T[x] - 1)
    for (x, y) in [(10, 0), (31, 1), (40, 0)]:
        pass
    river = [(26, T[26]), (26, 8), (24, 8), (24, 13), (27, 13), (27, 18), (25, 18), (25, H - 1)]
    m.river(river)
    C = lambda x, y: (x, max(T[x] + 2, min(H - 2, y)))
    # --- hedgerows: thin belts of woods across the farmland, with gates; ridges and woodlots between the fields
    hedges = [[(2, 8), (9, 7), (14, 9)], [(2, 17), (8, 18), (15, 16)], [(10, 11), (12, 14), (11, 19)], [(15, 5), (20, 4), (22, 6)], [(14, 22), (19, 21), (22, 22)], [(29, 6), (35, 5), (43, 7)], [(31, 11), (37, 10), (44, 12)],
              [(29, 21), (36, 22), (43, 20)], [(31, 16), (38, 17), (44, 16)], [(34, 7), (35, 14), (33, 19)], [(18, 12), (20, 16), (21, 20)]]
    for i, pts in enumerate(hedges):
        belt(m, "f", pts, width=1, seed=10 + i, gaps=[pts[1]], p=0.9)
    for i, (cx, cy, n) in enumerate([(7, 14, 4), (16, 13, 4), (11, 5, 3), (20, 19, 4), (33, 9, 4), (39, 17, 4), (30, 14, 3), (42, 5, 3), (28, 22, 4), (6, 21, 4), (21, 5, 3), (34, 2, 2)]):
        m.cluster("f", cx, cy, n, seed=40 + i)
    for i, (cx, cy, n) in enumerate([(9, 11, 4), (15, 20, 3), (22, 12, 3), (35, 16, 3), (41, 8, 3), (30, 20, 3), (4, 17, 3)]):
        m.cluster("^", cx, cy, n, seed=60 + i)
    belt(m, "^", [(3, 3), (7, 4)], width=1, seed=1); belt(m, "^", [(38, 3), (43, 4)], width=1, seed=2); belt(m, "^", [(17, 8), (19, 10)], width=1, seed=3); belt(m, "^", [(40, 21), (43, 23)], width=1, seed=4); belt(m, "^", [(3, 22), (6, 23)], width=1, seed=5)
    belt(m, "^", [(32, 13), (35, 12)], width=1, seed=6); belt(m, "^", [(12, 22), (15, 23)], width=1, seed=7)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M15 Every Colour (normal look, clear): a free pair (Black Hole, HQ 1 (5,12), the west) against one Orange Star army under Max + Sami (HQ 2 (40,12), the east) on open farmland. The border river runs from the north coast (26,3) to the south edge (25,25), bridges (26,6), (24,10), (27,15), (25,21). "
        "Com Towers (22,9) and (30,16), missile silo (33,12); harbours (10,3) and (36,3). Player: INF5 MECH2 TANK5 MDT2 ART3 ROCK1 RECON1 APC1 CR1 SUB1; Orange Star: INF6 MECH4 TANK6 MDT2 ART3 ROCK2 RECON1 CR1 SUB1."))
    m.put("1", 5, 12).put("2", 40, 12).put("t", 22, 9).put("t", 30, 16).put("M", 33, 12)
    flatT = lambda a, lo, hi: min((x for x in range(lo, hi) if T[x] == T[x - 1] == T[x + 1]), key=lambda x: abs(x - a))
    P1, P2 = flatT(10, 3, 20), flatT(36, 30, 43)
    m.put("P", P1, T[P1]).put("P", P2, T[P2])
    route(m, [(6, 11), C(10, 8), C(15, 7), (24, 6), (26, 6, "="), (28, 6), C(33, 7), C(38, 9), (40, 11)], seed=21, wander=1.3)
    route(m, [(6, 13), C(10, 15), C(14, 19), (22, 21), (25, 21, "="), (27, 21), C(33, 20), C(38, 16), (40, 13)], seed=22, wander=1.3)
    route(m, [C(12, 12), C(18, 11), (22, 10), (24, 10, "="), (26, 10), C(30, 11), (32, 12)], seed=23, wander=1.1)
    route(m, [C(14, 15), C(20, 15), (25, 15), (27, 15, "="), (29, 15), C(32, 15)], seed=24, wander=1.1)
    route(m, [(P1, T[P1] + 1), C(P1, 6), C(10, 8)], seed=25); route(m, [(P2, T[P2] + 1), C(P2, 6), C(38, 9)], seed=26)
    thin_roads(m)
    for bx, by in [(26, 6), (24, 10), (27, 15), (25, 21)]:
        for dx, kinds in ((-3, "c"), (3, "c")):
            try:
                town(m, bx + dx, by, kinds, seed=100 + bx + dx, radius=3)
            except ValueError:
                pass
    for args in [(5, 12, "BBC"), (8, 15, "BC"), (4, 9, "C"), (9, 9, "BC"), (6, 18, "C"), (40, 12, "BBC"), (42, 9, "BC"), (38, 15, "BC"), (43, 13, "C"), (40, 19, "C"), (37, 9, "C"),
                 (13, 12, "C"), (20, 15, "bc"), (30, 11, "bc"), (18, 6, "c"), (13, 20, "c"), (36, 21, "c"), (44, 6, "c"), (20, 22, "c"), (32, 4, "c"), (32, 18, "c"), (16, 17, "c"), (1, 24, "c"), (3, 4, "c"), (4, 22, "c"), (12, 24, "c"), (22, 17, "c"), (28, 9, "c"), (33, 23, "c"), (44, 24, "c"), (36, 13, "c"), (9, 5, "c"), (18, 24, "c"), (24, 3, "c"), (40, 5, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 0, W - 2, 4), dirs="S") if False else None
    shore(m, 1, (1, 0, W - 2, 5), dirs="NS")
    for (x, y) in [(26, T[26] - 1), (P1, T[P1] - 1), (P2, T[P2] - 1)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    for (x, y) in [(6, 0), (20, 0), (30, 0), (44, 0), (14, 1)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2) if m.inside(a, b)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 5, MDT: 2, ART: 3, ROCK: 1, RECON: 1, APC: 1}, (2, 6, 14, 22), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 6, MECH: 4, TANK: 6, MDT: 2, ART: 3, ROCK: 2, RECON: 1}, (35, 5, 44, 22), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P1, 0, 2, box=(2, 0, 18, T[P1] - 1), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P2, 0, 2, box=(30, 0, 44, T[P2] - 1), deep=False)):
        m.unit(2, k_, x, y)
    m.note("hq", 5, 12, "Black Hole's HQ"); m.note("enemy_hq", 40, 12, "Max + Sami's HQ (objective)"); m.note("silo", 33, 12, "the missile silo of the open field")
    return m
