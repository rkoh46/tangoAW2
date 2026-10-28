"""BH2 M17 Lot 42 (Act III): Blue Moon's lab island, in the snow and the fog. Lash (forced) with a free tag partner against one Blue Moon army under the pair Sasha + Colin.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: a coast, not an island: the mainland runs off the west edge and a long peninsula points east into the sea, narrowing to an isthmus (the neck) with a bay on either side; the lab is the peninsula's broad end. The situation: Lot 42 is the lab peninsula: Blue Moon's research district (cities, an HQ and two ports) on the east side behind a pipe wall with a seam gate, a pond in the
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
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 40, 30
OB = (18, 14)


def build():
    m = Canvas("bh2_17", W, H, fill="~")
    # --- the silhouette: the mainland runs off the west edge; the neck (rows 11..17) joins it to the lab peninsula in the east; a bay on each side of the neck; a southern isle
    land_rows(m, {3: (0, 12), 4: (0, 13), 5: (0, 14), 6: (0, 13), 7: (0, 14), 8: (0, 15), 9: (0, 16)})
    land_rows(m, {y: (0, 37) for y in range(10, 19)})
    land_rows(m, {19: (0, 14), 20: (0, 15), 21: (0, 14), 22: (0, 13), 23: (0, 11), 24: (0, 9)})
    land_rows(m, {5: (29, 33), 6: (27, 35), 7: (26, 36), 8: (26, 37), 9: (25, 37), 10: (25, 37), 18: (25, 37), 19: (26, 37), 20: (26, 36), 21: (27, 36), 22: (28, 35), 23: (30, 34)})
    land_rows(m, {26: (14, 25), 27: (13, 26), 28: (15, 24)})
    ponds = m.lake(31, 8, 8, seed=1, river_end=(31, 9))
    m.river([(31, 9), (31, 13), (33, 13), (33, 17), (32, 17), (32, 22)])
    for (x, y) in [(31, 23), (32, 23), (33, 23)]:
        m.g[y][x] = "~"
    belt(m, "^", [(14, 11), (14, 16)], width=1, seed=21, gaps=[(14, 13)], p=1.0); belt(m, "^", [(15, 17), (21, 17)], width=1, seed=22, gaps=[(18, 17)], p=1.0); belt(m, "^", [(16, 10), (21, 10)], width=1, seed=23, gaps=[(18, 10)], p=1.0)
    belt(m, "^", [(3, 6), (9, 5)], width=1, seed=1); belt(m, "^", [(3, 20), (8, 22)], width=1, seed=2); belt(m, "^", [(26, 14), (29, 17)], width=1, seed=3); belt(m, "^", [(34, 7), (36, 10)], width=1, seed=4); belt(m, "^", [(28, 19), (33, 20)], width=1, seed=5)
    belt(m, "f", [(4, 9), (9, 12)], width=2, seed=7); belt(m, "f", [(5, 14), (11, 16)], width=1, seed=8); belt(m, "f", [(22, 12), (25, 15)], width=1, seed=9); belt(m, "f", [(3, 17), (9, 19)], width=1, seed=10); belt(m, "f", [(34, 13), (36, 17)], width=1, seed=11)
    belt(m, "f", [(27, 8), (30, 11)], width=1, seed=12); belt(m, "f", [(7, 3), (12, 4)], width=1, seed=13); belt(m, "f", [(28, 21), (31, 22)], width=1, seed=14)
    m.header(armies=2, colours=(BH, BM), objective=[1], comment=(
        "M17 Lot 42 (snow look, fog): Lash (forced) + a free tag partner (Black Hole, HQ 1 (7,14), the mainland in the west) against one Blue Moon army under the pair Sasha + Colin (HQ 2 (32,14), the lab at the peninsula's end behind the pipe wall x27 with the seam gate (27,7)). "
        "The Black Obelisk (O) stands at the peninsula's neck at (18,14), a cell on Black Hole's side of the middle, in a crescent of cliffs. A pond (31,8) feeds the river with bridges (31,11) and (32,19); the southern isle (Com Tower, missile silo) is reached by Landers only. "
        "Player: INF3 MECH2 TANK3 MDT1 ART1 ROCK1 RECON1 CR1 SUB1 LAN2; Blue Moon: INF6 MECH3 TANK4 MDT2 ART2 ROCK1 RECON1 CR2 SUB1."))
    m.put("1", 7, 14).put("2", 32, 14).put("t", 20, 27).put("M", 22, 27)
    m.stamp("O", *OB)                                  # the Black Obelisk stands in the neck of the peninsula, on Black Hole's side of the middle
    S = lambda x, y: snap(m, x, y)
    m.pipe([(27, 6), (27, 11)]); m.put("Z", 27, 8); m.put("^", 27, 12).put("^", 26, 12).put("^", 28, 12)           # the lab wall: from the peninsula's north coast to a knot of cliffs
    # ports: Black Hole's on the north bay's south shore and in the south bay; Blue Moon's on the peninsula's south coast; a neutral one on the north bay
    PC = lambda x, y: snap_coast(m, x, y)
    PORTS = [PC(8, 9), PC(9, 21), PC(31, 22), PC(14, 8)]
    m.put("P", *PORTS[0]).put("P", *PORTS[1]).put("P", *PORTS[2]).put("p", *PORTS[3])
    route(m, [S(8, 15), S(12, 12), S(16, 12), (22, 12), S(24, 12)], seed=1, wander=1.1); route(m, [(22, 12), S(25, 9), S(26, 7)], seed=2)
    route(m, [S(28, 7), S(30, 7), (29, 9)], seed=3); route(m, [S(24, 13), S(28, 13), (29, 11), (31, 11, "="), (33, 11), S(34, 12), S(33, 13)], seed=4)
    route(m, [S(8, 15), S(12, 16), S(17, 16), (22, 16), S(26, 16), S(29, 17), S(31, 19), (32, 19, "="), S(33, 20), S(33, 21)], seed=5, wander=1.1)
    route(m, [S(8, 15), S(9, 19)], seed=6); route(m, [S(8, 13), S(8, 10)], seed=7); route(m, [(29, 9), (29, 11)], seed=8); route(m, [(16, 27), (24, 27)], seed=10)
    thin_roads(m); fix_rungs(m)
    for args in [(7, 14, "BBC"), (11, 17, "BC"), (6, 9, "C"), (9, 19, "BC"), (12, 12, "C"), (3, 12, "C"), (16, 13, "Cb"), (21, 12, "Cb"), (22, 16, "bc"), (12, 5, "cc"), (25, 9, "bc"), (26, 16, "C"), (30, 12, "Cb"),
                 (32, 14, "BBBC"), (30, 8, "BCC"), (34, 9, "CC"), (34, 18, "BC"), (29, 17, "CC"), (35, 14, "C"), (31, 20, "C"), (4, 21, "cc"), (13, 21, "c"), (16, 27, "c"), (24, 27, "c"), (3, 5, "c"), (35, 21, "c"), (28, 5, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 1, 38, 9), dirs="NS"); shore(m, 1, (1, 18, 38, 28), dirs="NS")
    for (x, y) in ponds:
        m.g[y][x] = "~"
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    for (x, y) in [(19, 5), (21, 24), (6, 26), (30, 26), (36, 26), (34, 3), (3, 28), (24, 22)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 3, MECH: 2, TANK: 3, MDT: 1, ART: 1, ROCK: 1, RECON: 1}, (1, 6, 13, 21), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1}, (28, 6, 36, 21), seed=2, gap=0, avoid=av)
    m.spread(2, {INF: 1, MECH: 1, TANK: 1, MDT: 1}, (15, 11, 25, 17), seed=3, gap=2, avoid=av)
    for k, (x, y) in zip([LAN, LAN, CR, SUB], m.sea_near(18, 22, 4, box=(10, 18, 26, 25), deep=False)):
        m.unit(1, k, x, y)
    for k, (x, y) in zip([CR, CR, SUB], m.sea_near(31, 25, 3, box=(26, 23, 38, 26), deep=False)):
        m.unit(2, k, x, y)
    m.note("hq", 7, 14, "Lash's HQ"); m.note("enemy_hq", 32, 14, "Sasha + Colin's HQ (objective)"); m.note("obelisk", OB[0], OB[1], "Black Hole's Black Obelisk, in the neck of the peninsula"); m.note("gate", 27, 8, "seam gate in the lab wall")
    return m
