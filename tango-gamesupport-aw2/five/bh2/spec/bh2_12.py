"""BH2 M12 Lot 42 (Act III): Blue Moon's lab island, in the snow and the fog. Lash (forced) with a free tag partner against one Blue Moon army under the pair Sasha + Colin.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Lot 42 is a lab island: Blue Moon's research district (cities, an HQ and two ports) on the east side behind a pipe wall with a seam gate, a pond in the
hills that feeds a river with a mouth on the south coast, and Black Hole's landing on the west side: its HQ, a base district, a port in a bay and, in the heart of the island, a cell on Black Hole's side of the middle, the Black Obelisk (Black Hole's alone) in a crescent of cliffs that every road of the island passes. A small
southern isle (a Com Tower, a missile silo and two villages) lies in the strait; only Landers reach it, and whoever holds it has a long view in the fog.
- Lanes: the river's two bridges (north and south), the coast roads, the lab wall's seam gate and the beaches north and south for Landers, the strait and its reefs for the ships.
- Where the fight happens: the river's bridgeheads and the pond's hills, then the lab wall.
- Properties: the Obelisk's heart and the bases of Black Hole, the lab district's cities and bases for Blue Moon, the isle's Com Tower and silo.
- Threats and answers: Sasha's and Colin's Tanks, Rockets and artillery -> the Obelisk's reach, Md Tanks and Black Hole's own artillery; the ships of both sides -> Cruisers and Submarines and the guns on the beaches. Blue Moon fields no air: Black Hole fields none.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 40, 30


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_12/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-2, -1, 1, 2])))
    return out


def build():
    m = Canvas("bh2_12", W, H, fill="~")
    T = profile(3, 36, 3, 6, 1)
    B = profile(3, 36, 18, 21, 2)
    for x in (22, 23, 24, 25):                      # the river's mouth stands on a straight shore
        B[x] = B[24]
    for dx, k in ((3, 5), (4, 3), (5, 1)):          # the ends taper in
        T[dx] += k; B[dx] -= k; T[39 - dx] += k; B[39 - dx] -= k
    for x in range(3, 37):
        m.rect(".", x, T[x], x, B[x])
    m.rect(".", 2, 11, 5, 16)                       # a headland in the west (the Obelisk's)
    for x in range(8, 12):                          # Black Hole's bay in the south coast (its port)
        for y in range(B[x] - 1, B[x] + 1):
            m.g[y][x] = "~"
    for x in range(17, 21):                         # a bay in the north coast
        for y in range(T[x], T[x] + 2):
            m.g[y][x] = "~"
    land_rows(m, {25: (16, 24), 26: (15, 25), 27: (14, 26), 28: (16, 24)})        # the southern isle
    ponds = m.lake(22, 9, 9, seed=1, river_end=(22, 10))
    m.river([(22, 10), (22, 14), (24, 14), (24, B[24])])
    L = lambda x, y: (x, max(T[x] + 2, min(B[x] - 2, y)))
    belt(m, "^", [(18, 9), (21, 8)], width=1, seed=1); belt(m, "^", [(23, 7), (26, 8)], width=1, seed=2); belt(m, "^", [(25, 17), (30, 19)], width=1, seed=3, gaps=[(27, 18)])
    belt(m, "^", [(12, 7), (15, 8)], width=1, seed=4); belt(m, "^", [(12, 18), (16, 17)], width=1, seed=5, gaps=[(14, 17)]); belt(m, "^", [(32, 5), (35, 7)], width=1, seed=6)
    belt(m, "f", [(8, 16), (12, 14)], width=1, seed=7); belt(m, "f", [(15, 12), (19, 13)], width=2, seed=8); belt(m, "f", [(28, 10), (32, 12)], width=2, seed=9)
    belt(m, "f", [(17, 20), (21, 19)], width=1, seed=10); belt(m, "f", [(30, 14), (34, 15)], width=1, seed=11); belt(m, "f", [(5, 8), (9, 7)], width=1, seed=12); belt(m, "f", [(16, 22), (19, 25)], width=0, seed=13)
    belt(m, "f", [(31, 20), (34, 19)], width=1, seed=14)
    belt(m, "^", [(14, 11), (14, 16)], width=1, seed=21, gaps=[(14, 13)], p=1.0); belt(m, "^", [(15, 17), (21, 17)], width=1, seed=22, gaps=[(18, 17)], p=1.0); belt(m, "^", [(16, 10), (20, 10)], width=1, seed=23, gaps=[(18, 10)], p=1.0)
    m.header(armies=2, colours=(BH, BM), objective=[1], comment=(
        "M12 Lot 42 (snow look, fog): Lash (forced) + a free tag partner (Black Hole, HQ 1 (8,14), the west) against one Blue Moon army under the pair Sasha + Colin (HQ 2 (32,11), the lab district in the east behind the pipe wall x27 with the seam gate (27,7)). "
        "The Black Obelisk (O) stands in the heart of the island at (18,14), a cell on Black Hole's side of the middle, in a crescent of cliffs. A pond (22,9) feeds the river with bridges (22,12) and (24,18); the southern isle (Com Tower (20,27), missile silo (22,26)) is reached by Landers only. "
        "Player: INF4 MECH2 TANK4 MDT1 ART2 ROCK1 RECON1 CR1 SUB1 LAN2; Blue Moon: INF6 MECH3 TANK4 MDT2 ART2 ROCK1 RECON1 CR2 SUB1."))
    m.put("1", 8, 14).put("2", 32, 11).put("t", 20, 27).put("M", 22, 26)
    m.stamp("O", 18, 14)                              # the Black Obelisk stands in the heart of the island, on Black Hole's side of the middle
    PB = (9, B[9] - 2)
    flat = lambda a: min((x for x in range(26, 37) if B[x] == B[x - 1] == B[x + 1]), key=lambda x: abs(x - a))
    P2 = flat(31)
    m.put("P", *PB).put("P", P2, B[P2]).put("p", 18, T[18] + 2)
    m.pipe([(27, T[27]), (27, 12)]); m.put("Z", 27, 7); m.put("^", 26, 13).put("^", 27, 13).put("^", 28, 13)       # the lab wall: a pipeline from the north coast to a knot of cliffs
    # --- roads: the north highway (the river's north bridge, the seam gate), the south highway (the south bridge, the port), the pond's hill road, the isle's loop
    route(m, [(8, 15), L(11, 13), L(16, 12), (20, 12), (22, 12, "="), (24, 12), L(25, 9), L(26, 7), (26, 7)], seed=1)
    route(m, [(28, 7), L(30, 8), (32, 10)], seed=2)
    route(m, [(8, 15), L(11, 17), L(16, 19), (22, 18), (24, 18, "="), (26, 18), L(29, 16), L(31, 13), (32, 12)], seed=3)
    route(m, [(26, 18), L(26, 15), L(26, 14)], seed=4); route(m, [(26, 14), L(28, 14), (31, 12)], seed=5)
    route(m, [(9, B[9] - 3), (9, 16)], seed=6); route(m, [(P2, B[P2] - 1), L(P2, 18), L(31, 16)], seed=7); route(m, [(18, T[18] + 3), L(18, 8), (20, 12)], seed=8)
    route(m, [(4, 15), (8, 15)], seed=9); route(m, [L(8, 12), L(7, 8)], seed=16); route(m, [(16, 27), (24, 27)], seed=10)
    thin_roads(m)
    town(m, 8, 14, "BBC", seed=44); town(m, 11, 17, "BC", seed=2); town(m, 7, 9, "C", seed=3); town(m, 9, 18, "C", seed=4); town(m, 14, 12, "C", seed=5); town(m, 21, 14, "Cb", seed=41, radius=3); town(m, 18, 8, "c", seed=42); town(m, 16, 19, "Cb", seed=6)
    town(m, 20, 12, "Cb", seed=7); town(m, 18, 6, "cc", seed=8); town(m, 22, 18, "c", seed=9); town(m, 25, 11, "C", seed=10); town(m, 26, 16, "Cb", seed=11)
    town(m, 32, 11, "BBBC", seed=12, radius=3); town(m, 30, 8, "BCC", seed=13, radius=3); town(m, 34, 8, "CC", seed=14); town(m, 33, 14, "BC", seed=15); town(m, 29, 15, "CC", seed=16); town(m, 35, 17, "C", seed=17)
    town(m, 31, 18, "C", seed=18); town(m, 6, 20, "c", seed=19); town(m, 14, 22, "c", seed=20); town(m, 16, 27, "c", seed=21); town(m, 24, 27, "c", seed=22); town(m, 12, 6, "c", seed=23)
    if m.g[15][12] == "B":
        m.g[15][12] = "."
    m.g[14][11] = "."
    neutralize(m, 13)
    m.tidy()
    for box in [(3, 1, 16, 2), (21, 1, 36, 2), (3, 25, 7, 25), (13, 25, 22, 25), (26, 25, 36, 25), (13, 24, 28, 24)]:
        pass
    shore(m, 1, (3, 1, 16, 8), dirs="NS"); shore(m, 1, (21, 1, 36, 8), dirs="NS"); shore(m, 1, (3, 17, 7, 28), dirs="NS"); shore(m, 1, (13, 17, 23, 28), dirs="NS"); shore(m, 1, (25, 17, 36, 28), dirs="NS")
    for (x, y) in [(22 + 0, T[22] - 1), (9, PB[1] + 1), (P2, B[P2] + 1), (18, T[18] + 1), (24, B[24] + 1)]:
        if m.inside(x, y) and m.g[y][x] == ",":
            m.g[y][x] = "~"
    for (x, y) in ponds:
        m.g[y][x] = "~"
    m.tidy()
    for (x, y) in [(11, 23), (30, 24), (29, 27), (4, 24)]:         # reefs in the strait, clear of every shore
        if all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 4, MDT: 1, ART: 2, ROCK: 1, RECON: 1}, (3, 7, 14, 20), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1}, (28, 5, 36, 19), seed=2, gap=0, avoid=av)
    m.spread(2, {INF: 1, MECH: 1, TANK: 1, MDT: 1}, (15, 5, 26, 21), seed=3, gap=2, avoid=av)
    for k, (x, y) in zip([LAN, LAN, CR, SUB], m.sea_near(14, B[14] + 2, 4, box=(3, B[9] - 1, 18, 24), deep=False)):
        m.unit(1, k, x, y)
    for k, (x, y) in zip([CR, CR, SUB], m.sea_near(P2, B[P2] + 2, 3, box=(26, B[P2] + 1, 37, 27), deep=False)):
        m.unit(2, k, x, y)
    m.note("hq", 8, 14, "Lash's HQ"); m.note("enemy_hq", 32, 11, "Sasha + Colin's HQ (objective)"); m.note("obelisk", 18, 14, "Black Hole's Black Obelisk, in the heart of the island"); m.note("gate", 27, 7, "seam gate in the lab wall")
    return m
