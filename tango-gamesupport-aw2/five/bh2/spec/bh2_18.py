"""BH2 M18 The Door Is Open (Act IV): Black Hole's own depot, under attack. Asuka + Crumb (the forced tag pair) against one Orange Star army under Hachi + Jake. Normal look, clear.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The situation: the island is the home island of M2: the depot in the west (HQ 1, a district of bases, the yard where the crate stands) and the quay on the south-east coast (a port).
Hachi and Jake have landed on the north-east shore: their HQ and a beachhead of bases; their army and B Copters push down the island's three roads. A river rises from a pond in the central hills, bends south and reaches the south coast; its three bridges carry the roads.
- Scripted fight (4b): defend the depot until Crumb, a named unit (an APC called `crumb`), reaches the crate tile `mark_crate`: the crate opens and Black Hole's reserve wakes, four Neotanks on the `mark_neo*` cells round the depot. Crumb starts at the quay with the reinforcement column and has to cross the island to the yard.
- Lanes: the three road-and-bridge lines west to east, the beaches on the north and south coasts, the hills round the pond.
- Where the fight happens: the bridges and the Com Tower (20,18) in the central massif, then the yard.
- Threats and answers: Hachi's and Jake's Tanks and artillery -> Black Hole's Tanks and Md Tanks behind the river, the Neotanks of the reserve; Jake's B Copters -> Anti-Air and Tanks.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 40, 28
NEO = [(7, 9), (9, 10), (7, 15), (9, 14)]        # the reserve's Neotanks
CRATE = (8, 12)                                  # the crate tile in the yard


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_18/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-1, 1])))
    return out


def build():
    m = Canvas("bh2_18", W, H, fill="~")
    T = profile(1, W - 2, 3, 5, 1); B = profile(1, W - 2, 22, 24, 2)
    for x in (20, 21, 22):
        B[x] = B[21]
    for x in range(1, W - 1):
        m.rect(".", x, T[x], x, B[x])
    for dx, k in ((1, 6), (2, 4), (3, 2), (4, 1)):
        T[dx] += k; B[dx] -= k; T[W - 1 - dx] += k; B[W - 1 - dx] -= k
        m.rect("~", dx, 0, dx, T[dx] - 1); m.rect("~", dx, B[dx] + 1, dx, H - 1)
        m.rect("~", W - 1 - dx, 0, W - 1 - dx, T[W - 1 - dx] - 1); m.rect("~", W - 1 - dx, B[W - 1 - dx] + 1, W - 1 - dx, H - 1)
    ponds = m.lake(20, 8, 9, seed=1, river_end=(20, 9))
    m.river([(20, 9), (20, 13), (22, 13), (22, 17), (21, 17), (21, B[21])])
    C = lambda x, y: (x, max(T[x] + 2, min(B[x] - 2, y)))
    belt(m, "^", [(12, 6), (16, 5)], width=1, seed=1); belt(m, "^", [(24, 5), (28, 7)], width=1, seed=2, gaps=[(26, 6)]); belt(m, "^", [(15, 18), (19, 20)], width=1, seed=3, gaps=[(17, 19)])
    belt(m, "^", [(26, 18), (30, 21)], width=1, seed=4); belt(m, "^", [(11, 20), (14, 22)], width=1, seed=5); belt(m, "^", [(4, 5), (7, 6)], width=1, seed=6); belt(m, "^", [(34, 11), (36, 15)], width=1, seed=7, gaps=[(35, 13)])
    belt(m, "^", [(17, 11), (18, 14)], width=1, seed=8)
    belt(m, "f", [(3, 17), (7, 19)], width=1, seed=9); belt(m, "f", [(11, 9), (15, 11)], width=1, seed=10); belt(m, "f", [(24, 10), (28, 12)], width=1, seed=11); belt(m, "f", [(30, 4), (34, 5)], width=1, seed=12)
    belt(m, "f", [(25, 15), (29, 16)], width=1, seed=13); belt(m, "f", [(12, 14), (15, 15)], width=1, seed=14); belt(m, "f", [(32, 18), (36, 21)], width=1, seed=15); belt(m, "f", [(3, 9), (5, 11)], width=1, seed=16)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M18 The Door Is Open (normal look, clear): Asuka + Crumb (forced pair, Black Hole, HQ 1 (5,12), the depot in the west) against one Orange Star army under Hachi + Jake (HQ 2 (34,6), the north-east beachhead). "
        "Scripted: Crumb (the named APC `crumb`, starting by the quay's port (30,20)) must reach the crate tile mark_crate (8,12); then the reserve's four Neotanks appear on the mark_neo cells. River from the pond (20,8): bridges (20,11), (22,15), (21,20). "
        "Com Tower (20,18), missile silo (27,9). Player: INF5 MECH2 TANK4 MDT2 ART3 ROCK1 RECON1 AA2 APC1 (crumb) CR1 SUB1; Orange Star: INF6 MECH3 TANK5 MDT2 ART3 ROCK1 RECON1 BCO3 CR1 SUB1."))
    m.put("1", 5, 12).put("2", 34, 6).put("t", 20, 18).put("M", 27, 9)
    flatB = lambda a, lo, hi: min((x for x in range(lo, hi) if B[x] == B[x - 1] == B[x + 1] and x not in (20, 21, 22)), key=lambda x: abs(x - a))
    PQ, PD, PE = flatB(31, 26, 37), flatB(8, 4, 16), flatB(33, 28, 37)
    m.put("P", PQ, B[PQ]).put("P", PD, B[PD]).put("P", 33, T[33] + 1) if False else m.put("P", PQ, B[PQ]).put("P", PD, B[PD])
    PN = min((x for x in range(28, 37) if T[x] == T[x - 1] == T[x + 1]), key=lambda x: abs(x - 33))
    m.put("P", PN, T[PN])
    route(m, [(5, 11), (5, 9), C(10, 8), C(15, 8), (18, 11), (20, 11, "="), (23, 11), C(26, 9), C(30, 7), (34, 7)], seed=21, wander=1.3)
    route(m, [(6, 12), C(11, 12), C(15, 13), (19, 15), (22, 15, "="), (24, 15), C(28, 13), C(32, 9), (34, 7)], seed=22, wander=1.3)
    route(m, [(5, 13), C(9, 17), C(14, 19), (19, 20), (21, 20, "="), (23, 20), C(27, 20), (PQ, B[PQ] - 1)], seed=23, wander=1.3)
    route(m, [C(27, 20), C(30, 17), C(31, 12), C(33, 9)], seed=24); route(m, [(PD, B[PD] - 1), C(PD, 17), C(9, 17)], seed=25); route(m, [(PN, T[PN] + 1), (34, 6)], seed=26)
    route(m, [C(20, 18), (21, 20)], seed=27) if False else route(m, [(19, 15), (19, 18), (20, 18)], seed=27); route(m, [C(24, 15), C(27, 10), (27, 10)], seed=28) if False else None
    route(m, [C(23, 11), C(27, 11), (27, 10)], seed=29)
    thin_roads(m)
    for args in [(5, 12, "BBC"), (8, 15, "BC"), (8, 9, "BC"), (11, 12, "C"), (4, 8, "C"), (4, 17, "C"), (10, 17, "C"), (14, 19, "C"), (15, 8, "CC"), (18, 11, "Cb"), (19, 15, "Cb"), (19, 20, "Cb"), (23, 11, "bc"), (24, 15, "bc"), (23, 20, "bc"),
                 (34, 6, "BBBC"), (30, 7, "BC"), (32, 9, "BC"), (36, 9, "C"), (28, 13, "bc"), (31, 12, "c"), (30, 18, "BC"), (27, 20, "c"), (15, 4, "c"), (36, 18, "c"), (12, 23, "c"), (27, 4, "c"), (36, 14, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    # the yard: the crate tile is road, the four Neotank cells plain (nothing starts there)
    for (x, y) in [CRATE] + NEO:
        if m.g[y][x] in ".fRc^":
            m.g[y][x] = "R" if (x, y) == CRATE else "."
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for (x, y) in ponds:
        m.g[y][x] = "~"
    for (x, y) in [(21, B[21] + 1), (PQ, B[PQ] + 1), (PD, B[PD] + 1), (PN, T[PN] - 1)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    for (x, y) in [(10, 26), (26, 26), (36, 1), (14, 1)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.reserve([CRATE] + NEO)
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 3, ROCK: 1, RECON: 1, AA: 2}, (2, 6, 17, 20), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 6, MECH: 3, TANK: 5, MDT: 2, ART: 3, ROCK: 1, RECON: 1, BCO: 3}, (24, 4, 37, 20), seed=2, gap=0, avoid=av)
    m.unit(1, APC, PQ - 1, B[PQ] - 2, name="crumb")
    for k_, (x, y) in zip([CR, SUB], m.sea_near(PQ, B[PQ] + 2, 2, box=(24, B[PQ] + 1, 38, H - 1), deep=True)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, SUB], m.sea_near(PN, 1, 2, box=(24, 0, 38, 3), deep=True)):
        m.unit(2, k_, x, y)
    m.note("hq", 5, 12, "Asuka + Crumb's HQ"); m.note("enemy_hq", 34, 6, "Hachi + Jake's HQ (objective)"); m.note("mark_crate", CRATE[0], CRATE[1], "the crate tile: Crumb arriving here opens the crate")
    for i, (x, y) in enumerate(NEO):
        m.note(f"mark_neo{i + 1}", x, y, "reserve: a Neotank appears here")
    return m
