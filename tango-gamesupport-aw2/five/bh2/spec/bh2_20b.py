"""BH2 M20 The Rail East (Act IV), front 2: the rail yard in the sandstorm. A free pick against Hachi. (Front 1 is bh2_20.)

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4; the second front of a two-front mission is a map of its own). The shape: land off the west, north and south edges with a diagonal coast on the east that comes to a point (a wedge), so the east gap is the wedge's last cells. The situation: the yard where the rail ends: a long embankment (a pipeline from the west shore to a knot of cliffs, with two seam gates)
splits the yard into Hachi's north yard (HQ, sidings of bases, a port on the north coast) and Black Hole's south yard (HQ, a base district, a port on the south coast). The way round is the east end of the embankment, a gap of eight cells between the cliffs and the east shore.
- Lanes: the two seam gates (7,11) and (16,11), the east gap, the sidings' roads, the beaches.
- Where the fight happens: the gates and the east gap, with the Com Tower (20,15) on the south side of the embankment.
- Threats and answers: Hachi's Tanks and artillery north of the embankment -> Black Hole's artillery and Md Tanks, a broken seam opens a gate; the fleets -> Cruisers and Submarines. No air, no Anti-Air. The sandstorm (a weather of this front: long guns lose a cell of range) is set in the mission.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 34, 24


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_20b/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-1, 1])))
    return out


def build():
    m = Canvas("bh2_20b", W, H, fill="~")
    for y in range(H):                                              # a diagonal coast: the land narrows to a wedge pointing east at row 11
        m.rect(".", 0, y, W - 2 - abs(y - 11), y)
    S = lambda x, y: snap(m, x, y)
    # --- the embankment: a pipeline from the west edge to a knot of cliffs, two seam gates
    m.pipe([(0, 11), (25, 11)]); m.put("Z", 7, 11).put("Z", 16, 11)
    m.put("^", 26, 11).put("^", 26, 10).put("^", 26, 12).put("^", 27, 11)
    belt(m, "^", [(8, 5), (13, 6)], width=1, seed=1); belt(m, "^", [(18, 5), (23, 6)], width=1, seed=2); belt(m, "^", [(8, 17), (13, 16)], width=1, seed=3, gaps=[(11, 17)]); belt(m, "^", [(22, 17), (26, 16)], width=1, seed=4)
    for i, (cx, cy, n, ch) in enumerate([(12, 19, 3, "^"), (18, 19, 3, "f"), (3, 8, 3, "f"), (22, 13, 3, "^"), (30, 14, 3, "f"), (5, 18, 3, "^"), (24, 3, 3, "f"), (29, 4, 2, "^")]):
        m.cluster(ch, cx, cy, n, seed=50 + i)
    belt(m, "^", [(1, 2), (6, 3)], width=1, seed=5); belt(m, "^", [(1, 20), (6, 21)], width=1, seed=6)
    belt(m, "f", [(4, 7), (7, 8)], width=1, seed=7); belt(m, "f", [(4, 15), (7, 14)], width=1, seed=8); belt(m, "f", [(14, 8), (18, 9)], width=1, seed=9); belt(m, "f", [(14, 14), (19, 13)], width=1, seed=10)
    belt(m, "f", [(21, 8), (25, 8)], width=1, seed=11); belt(m, "f", [(28, 12), (31, 13)], width=1, seed=12); belt(m, "f", [(10, 20), (15, 21)], width=1, seed=13)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M20 The Rail East, front 2 (normal look, the front's weather is a sandstorm): a free pick (Black Hole, HQ 1 (6,15), the south yard) against Hachi (Orange Star, HQ 2 (27,7), the north yard). "
        "The embankment: a pipeline y11 (x0..25) with seam gates (7,11), (16,11), ending in cliffs; the way round is the wedge's last cells in the east (x 27..33). Com Tower (20,15). Player: INF4 MECH2 TANK3 MDT1 ART2 ROCK1 RECON1 CR1 SUB1; Hachi: INF4 MECH2 TANK4 MDT2 ART2 ROCK1 RECON1 CR1 SUB1."))
    m.put("1", 6, 15).put("2", 27, 7).put("t", 20, 15)
    PORTS = [snap_coast(m, 28, 3), snap_coast(m, 28, 19)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    route(m, [S(6, 14), S(6, 13), (7, 12)], seed=1); route(m, [(7, 10), S(9, 8), S(14, 7), S(20, 6), S(26, 7)], seed=2, wander=1.2)
    route(m, [(7, 15), S(12, 15), S(15, 13), (16, 12)], seed=3)
    route(m, [(16, 10), S(16, 8), S(20, 6)], seed=4); route(m, [S(15, 13), S(20, 15), S(25, 15), S(29, 13), S(30, 11), S(30, 8), (28, 7)], seed=5, wander=1.2)
    route(m, [PORTS[0], S(PORTS[0][0] - 1, PORTS[0][1] + 2), S(24, 6)], seed=7); route(m, [PORTS[1], S(PORTS[1][0] - 1, PORTS[1][1] - 2), S(25, 15)], seed=6)
    route(m, [S(9, 15), S(8, 19), S(3, 21)], seed=20); route(m, [S(15, 13), S(16, 17), S(12, 21)], seed=21)
    thin_roads(m); fix_rungs(m)
    for args in [(6, 15, "BBC"), (9, 15, "BC"), (4, 13, "C"), (7, 13, "C"), (12, 15, "Cb"), (15, 13, "Cb"), (20, 15, "c"), (25, 15, "bc"), (29, 13, "bc"), (27, 7, "BBC"), (24, 6, "BC"), (20, 6, "BC"), (28, 9, "C"), (14, 7, "Cb"), (9, 8, "bc"), (16, 8, "b"),
                 (3, 21, "cc"), (4, 4, "c"), (2, 2, "cc"), (11, 21, "cc"), (17, 18, "c"), (20, 20, "c"), (20, 2, "c"), (10, 2, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 12)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    for y in (10, 11, 12):
        pass
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1}, (1, 13, 14, 22), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1}, (14, 1, 30, 9), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(PORTS[1][0], PORTS[1][1], 2, box=(22, 12, 33, 23), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(PORTS[0][0], PORTS[0][1], 2, box=(22, 0, 33, 10), deep=False)):
        m.unit(2, k_, x, y)
    m.note("hq", 6, 15, "the second front's Black Hole HQ"); m.note("enemy_hq", 27, 7, "Hachi's HQ (objective)"); m.note("gate_w", 7, 11, "seam gate"); m.note("gate_e", 16, 11, "seam gate")
    return m
