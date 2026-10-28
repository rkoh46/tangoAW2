"""BH2 M20 The Rail East (Act IV), front 2: the rail yard in the sandstorm. A free pick against Hachi. (Front 1 is bh2_20.)

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4; the second front of a two-front mission is a map of its own). The situation: the yard where the rail ends: a long embankment (a pipeline from the west shore to a knot of cliffs, with two seam gates)
splits the yard into Hachi's north yard (HQ, sidings of bases, a port on the north coast) and Black Hole's south yard (HQ, a base district, a port on the south coast). The way round is the east end of the embankment, a gap of eight cells between the cliffs and the east shore.
- Lanes: the two seam gates (7,11) and (16,11), the east gap, the sidings' roads, the beaches.
- Where the fight happens: the gates and the east gap, with the Com Tower (20,15) on the south side of the embankment.
- Threats and answers: Hachi's Tanks and artillery north of the embankment -> Black Hole's artillery and Md Tanks, a broken seam opens a gate; the fleets -> Cruisers and Submarines. No air, no Anti-Air. The sandstorm (a weather of this front: long guns lose a cell of range) is set in the mission.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

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
    T = profile(1, W - 2, 2, 3, 1); B = profile(1, W - 2, 19, 20, 2)
    for x in range(1, W - 1):
        m.rect(".", x, T[x], x, B[x])
    for dx, k in ((1, 5), (2, 3), (3, 1)):
        T[dx] += k; B[dx] -= k; T[W - 1 - dx] += k; B[W - 1 - dx] -= k
        m.rect("~", dx, 0, dx, T[dx] - 1); m.rect("~", dx, B[dx] + 1, dx, H - 1)
        m.rect("~", W - 1 - dx, 0, W - 1 - dx, T[W - 1 - dx] - 1); m.rect("~", W - 1 - dx, B[W - 1 - dx] + 1, W - 1 - dx, H - 1)
    C = lambda x, y: (x, max(T[x] + 2, min(B[x] - 2, y)))
    # --- the embankment: a pipeline from the west shore to a knot of cliffs, two seam gates
    m.pipe([(1, 11), (25, 11)]); m.put("Z", 7, 11).put("Z", 16, 11)
    m.put("^", 26, 11).put("^", 26, 10).put("^", 26, 12).put("^", 27, 11)
    belt(m, "^", [(8, 5), (13, 6)], width=1, seed=1); belt(m, "^", [(18, 5), (23, 6)], width=1, seed=2); belt(m, "^", [(8, 17), (13, 16)], width=1, seed=3, gaps=[(11, 17)]); belt(m, "^", [(22, 17), (26, 16)], width=1, seed=4)
    belt(m, "^", [(29, 6), (31, 9)], width=1, seed=5); belt(m, "^", [(29, 14), (31, 17)], width=1, seed=6)
    belt(m, "f", [(4, 7), (7, 8)], width=1, seed=7); belt(m, "f", [(4, 15), (7, 14)], width=1, seed=8); belt(m, "f", [(14, 8), (18, 9)], width=1, seed=9); belt(m, "f", [(14, 14), (19, 13)], width=1, seed=10)
    belt(m, "f", [(21, 8), (25, 8)], width=1, seed=11); belt(m, "f", [(28, 12), (31, 13)], width=1, seed=12)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M20 The Rail East, front 2 (normal look, the front's weather is a sandstorm): a free pick (Black Hole, HQ 1 (6,15), the south yard) against Hachi (Orange Star, HQ 2 (27,7), the north yard). "
        "The embankment: a pipeline y11 (x1..25) with seam gates (7,11), (16,11), ending in cliffs; the way round is the east gap (x 26..32). Com Tower (20,15). Player: INF4 MECH2 TANK3 MDT1 ART2 ROCK1 RECON1 CR1 SUB1; Hachi: INF4 MECH2 TANK4 MDT2 ART2 ROCK1 RECON1 CR1 SUB1."))
    m.put("1", 6, 15).put("2", 27, 7).put("t", 20, 15)
    flatB = lambda a, lo, hi: min((x for x in range(lo, hi) if B[x] == B[x - 1] == B[x + 1]), key=lambda x: abs(x - a))
    flatT = lambda a, lo, hi: min((x for x in range(lo, hi) if T[x] == T[x - 1] == T[x + 1]), key=lambda x: abs(x - a))
    PB, PT = flatB(9, 3, 18), flatT(24, 14, 30)
    m.put("P", PB, B[PB]).put("P", PT, T[PT])
    route(m, [(6, 14), C(6, 13), (7, 12)], seed=1); route(m, [(7, 10), C(9, 8), C(14, 7), C(20, 6), (26, 7)], seed=2, wander=1.2)
    route(m, [(7, 15), C(12, 15), (16, 12), (16, 12)], seed=3) if False else route(m, [(7, 15), C(12, 15), C(15, 13), (16, 12)], seed=3)
    route(m, [(16, 10), C(16, 8), C(20, 6)], seed=4); route(m, [C(15, 13), C(20, 15), C(25, 15), C(29, 13), C(30, 11), C(30, 8), (28, 7)], seed=5, wander=1.2)
    route(m, [(PB, B[PB] - 1), C(PB, 17), C(9, 15)], seed=6); route(m, [(PT, T[PT] + 1), C(PT, 5), C(24, 6)], seed=7); route(m, [C(20, 15), (20, 15)], seed=8) if False else None
    thin_roads(m)
    for args in [(6, 15, "BBC"), (9, 15, "BC"), (4, 13, "C"), (7, 13, "C"), (12, 15, "Cb"), (15, 13, "Cb"), (20, 15, "c"), (25, 15, "bc"), (29, 13, "bc"), (27, 7, "BBC"), (24, 6, "BC"), (20, 6, "BC"), (28, 9, "C"), (14, 7, "Cb"), (9, 8, "bc"), (16, 8, "b"),
                 (30, 4, "c"), (4, 6, "c"), (30, 17, "c"), (4, 18, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 12)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for (x, y) in [(PB, B[PB] + 1), (PT, T[PT] - 1), (1, 10), (1, 12)]:
        if m.inside(x, y) and m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1}, (2, 13, 14, 19), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1}, (14, 3, 31, 9), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(PB, B[PB] + 2, 2, box=(2, B[PB] + 1, 18, H - 1), deep=True)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(PT, 1, 2, box=(14, 0, 30, 2), deep=True)):
        m.unit(2, k_, x, y)
    m.note("hq", 6, 15, "the second front's Black Hole HQ"); m.note("enemy_hq", 27, 7, "Hachi's HQ (objective)"); m.note("gate_w", 7, 11, "seam gate"); m.note("gate_e", 16, 11, "seam gate")
    return m
