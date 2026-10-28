"""BH2 M20 The Rail East (Act IV), front 1: the Orange Star rail corridor. A free pick against Andy. (Front 2, the rail yard in the sandstorm against Hachi, is bh2_20b.)

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: the heavy train with the Accord's door-seal machinery runs east along a corridor between the sea in the north and the sea in the south. The rail is the trunk road: it runs
from Black Hole's landing in the west (HQ, a base district, a port) through a chain of station towns to Andy's terminus in the east (HQ, a base district, a port), the one road all the stations stand on. A pond in the hills feeds a river that crosses the corridor with
two bridges, and the rail crosses it on the bigger one. Ridges and woods north and south of the rail make the flanks, with a side road on each.
- Lanes: the rail trunk with its station towns, the north flank road over the hills, the south flank road along the beach, the river's two bridges.
- Where the fight happens: the river crossing and the two Com Towers (20,6) and (24,16), then Andy's terminus.
- Properties: a town at each station on the rail, villages on the flank roads, the two HQ districts and ports, a missile silo in the south hills.
- Threats and answers: Andy's Tanks and Md Tanks along the rail -> Black Hole's Md Tanks, Rockets and artillery across the river; his Cruiser and Submarine -> Black Hole's own. Orange Star fields no air here.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 44, 24


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_20/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-1, 1])))
    return out


def build():
    m = Canvas("bh2_20", W, H, fill="~")
    T = profile(1, W - 2, 2, 4, 1); B = profile(1, W - 2, 19, 21, 2)
    for x in (22, 23, 24):
        B[x] = B[23]
    for x in range(1, W - 1):
        m.rect(".", x, T[x], x, B[x])
    for dx, k in ((1, 6), (2, 4), (3, 2), (4, 1)):
        T[dx] += k; B[dx] -= k; T[W - 1 - dx] += k; B[W - 1 - dx] -= k
        m.rect("~", dx, 0, dx, T[dx] - 1); m.rect("~", dx, B[dx] + 1, dx, H - 1)
        m.rect("~", W - 1 - dx, 0, W - 1 - dx, T[W - 1 - dx] - 1); m.rect("~", W - 1 - dx, B[W - 1 - dx] + 1, W - 1 - dx, H - 1)
    ponds = m.lake(22, 5, 9, seed=1, river_end=(22, 6))
    m.river([(22, 6), (22, 10), (24, 10), (24, 14), (23, 14), (23, B[23])])
    C = lambda x, y: (x, max(T[x] + 2, min(B[x] - 2, y)))
    belt(m, "^", [(8, 5), (13, 6), (17, 5)], width=1, seed=1, gaps=[(11, 5), (15, 6)]); belt(m, "^", [(28, 5), (33, 6), (38, 5)], width=1, seed=2, gaps=[(31, 5), (36, 6)])
    belt(m, "^", [(9, 17), (14, 18)], width=1, seed=3, gaps=[(12, 17)]); belt(m, "^", [(28, 17), (34, 18)], width=1, seed=4, gaps=[(31, 17)]); belt(m, "^", [(18, 13), (20, 15)], width=1, seed=5); belt(m, "^", [(26, 7), (28, 9)], width=1, seed=6)
    belt(m, "f", [(4, 8), (8, 9)], width=1, seed=7); belt(m, "f", [(4, 15), (8, 14)], width=1, seed=8); belt(m, "f", [(14, 8), (18, 8)], width=1, seed=9); belt(m, "f", [(26, 13), (30, 14)], width=1, seed=10)
    belt(m, "f", [(35, 8), (39, 9)], width=1, seed=11); belt(m, "f", [(35, 14), (39, 15)], width=1, seed=12); belt(m, "f", [(18, 15), (22, 17)], width=1, seed=13)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M20 The Rail East, front 1 (normal look, fog): a free pick (Black Hole, HQ 1 (5,11), the west) against Andy (Orange Star, HQ 2 (38,11), the terminus in the east). The rail: the trunk road through the station towns. A pond (22,5) feeds the river with bridges (22,8) and (23,17). "
        "Com Towers (20,6) and (24,16), missile silo (31,16). Player: INF5 MECH2 TANK5 MDT2 ART3 ROCK1 RECON1 CR1 SUB1; Andy: INF5 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1 CR1 SUB1."))
    m.put("1", 5, 11).put("2", 38, 11).put("t", 20, 6).put("t", 24, 16).put("M", 31, 16)
    flatB = lambda a, lo, hi: min((x for x in range(lo, hi) if B[x] == B[x - 1] == B[x + 1] and x not in (22, 23, 24)), key=lambda x: abs(x - a))
    P1, P2 = flatB(8, 3, 18), flatB(36, 28, 42)
    m.put("P", P1, B[P1]).put("P", P2, B[P2])
    rail = [(6, 11), C(10, 12), C(14, 11), C(18, 12), (20, 8) if False else C(19, 10), (20, 8), (22, 8, "="), (24, 8), C(27, 10), C(31, 11), C(35, 11), (37, 11)]
    route(m, rail, seed=21, wander=1.3)
    route(m, [(5, 12), C(9, 15), C(13, 16), C(17, 17), (21, 17), (23, 17, "="), (25, 17), C(29, 16), C(33, 15), C(37, 13), (38, 12)], seed=22, wander=1.3)
    route(m, [(5, 10), C(8, 7), C(13, 5), C(18, 4), C(26, 5), C(32, 5), C(36, 7), (38, 10)], seed=23, wander=1.3)
    route(m, [(P1, B[P1] - 1), C(P1, 15), C(9, 15)], seed=24); route(m, [(P2, B[P2] - 1), C(P2, 15), C(33, 15)], seed=25); route(m, [(20, 7), (20, 8)], seed=26); route(m, [C(23, 15), (24, 17)], seed=27) if False else None
    route(m, [C(24, 15), (24, 16)], seed=28) if False else None; route(m, [C(30, 16), (31, 15)], seed=29) if False else None
    route(m, [C(19, 12), (24, 12, "="), (26, 12), C(29, 11)], seed=30)
    thin_roads(m)
    for args in [(5, 11, "BBC"), (9, 15, "BC"), (8, 8, "BC"), (4, 15, "C"), (10, 12, "C"), (14, 11, "CC"), (18, 12, "Cb"), (19, 10, "bc"), (13, 5, "C"), (13, 16, "C"), (17, 17, "Cb"), (20, 6, "c"), (21, 17, "bc"), (25, 8, "bc"), (25, 17, "bc"), (27, 10, "bc"),
                 (38, 11, "BBC"), (36, 7, "BC"), (37, 13, "BC"), (31, 11, "Cb"), (35, 11, "CC"), (29, 16, "Cb"), (33, 15, "bc"), (26, 5, "c"), (32, 5, "c"), (3, 18, "c"), (40, 18, "c"), (3, 5, "c"), (40, 5, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for (x, y) in ponds:
        m.g[y][x] = "~"
    for (x, y) in [(23, B[23] + 1), (P1, B[P1] + 1), (P2, B[P2] + 1)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    for (x, y) in [(10, 22), (30, 22), (36, 1), (12, 1)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 5, MDT: 2, ART: 3, ROCK: 1, RECON: 1}, (2, 5, 14, 18), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1}, (30, 4, 41, 18), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P1, B[P1] + 2, 2, box=(2, B[P1] + 1, 16, H - 1), deep=True)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(P2, B[P2] + 2, 2, box=(30, B[P2] + 1, 42, H - 1), deep=True)):
        m.unit(2, k_, x, y)
    m.note("hq", 5, 11, "Black Hole's HQ"); m.note("enemy_hq", 38, 11, "Andy's HQ (objective)"); m.note("silo", 31, 16, "the missile silo in the south hills")
    return m
