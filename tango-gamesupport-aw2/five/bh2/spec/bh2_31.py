"""BH2 M30 part two: The Last Citadel (Act V, the final mission's second map). The Accord's last stand: Aria (Orange Star), a revived army of brand-new full-strength units, holds a fortress on high ground; Asuka + a free partner (Black Hole) come from the south. 46 x 28 = 1288 cells, no pipes, no walls: the citadel is the land itself.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The shape: a highland massif in the north-east (x 22..44, y 1..11) round a plateau (x 26..41, y 3..9): a ring of mountains with three passes (west (22..25,6), south (33,10..11), east (42..44,6)) climbed by switchback roads; Aria's HQ 2 at (33,5) in the middle of a fortified town cluster.
A wide river, the Aisne, crosses the whole map (y 13..15, two steps) with five bridges (9,14) (16,15) (22,15) (31,13) (40,13): the only ways over it. South of the river lie Black Hole's camp (south-west, HQ 1 at (5,23), three Black Crystals) and a marsh lake with a causeway (south-centre); north of it, west of the massif, a wooded moor with a Com Tower and ridges.
- Lanes: the three bridges and the roads from each to a pass; the moor between the river and the massif; the plateau's inner ring road.
- Where the fight happens: the bridges, then the passes; the last stand is on the plateau.
- Properties: the camp's bases, neutral cities along the roads, the plateau's bases and airports (Aria's: it is her citadel).
- Threats and answers: Aria's Megatanks and Neotanks on the high ground -> Rockets, Missiles and the player's air; her Fighters and Bombers -> Anti-Air and Fighters; her artillery on the plateau -> Black Hole's own artillery from the passes.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 46, 28


def build():
    m = Canvas("bh2_31", W, H)
    S = lambda x, y: snap(m, x, y)
    # --- the highland massif with its plateau and three passes
    m.rect("^", 22, 1, 44, 11); m.rect(".", 26, 3, 41, 9)
    for (x, y) in [(22, 6), (23, 6), (24, 6), (25, 6), (33, 10), (33, 11), (42, 6), (43, 6), (44, 6)]:
        m.put(".", x, y)
    for (x, y) in [(25, 5), (25, 7), (26, 2), (30, 2), (36, 2), (40, 2), (27, 10), (38, 10), (41, 10)]:
        m.put(".", x, y)
    import random as _r
    rr = _r.Random("bh2_25b/massif")
    for y in range(1, 12):
        for x in range(22, 45):
            if m.g[y][x] == "^" and not (26 <= x <= 41 and 3 <= y <= 9):
                v = rr.random()
                if v < 0.11:
                    m.g[y][x] = "."
                elif v < 0.17:
                    m.g[y][x] = "f"
    m.cluster("f", 29, 7, 6, seed=3); m.cluster("f", 38, 4, 6, seed=4)
    # --- the Aisne and its three bridges
    m.river([(0, 14), (12, 14), (12, 15), (28, 15), (28, 13), (45, 13)])
    for x, y in ((9, 14), (16, 15), (22, 15), (31, 13), (40, 13)):
        m.put("=", x, y)
    # --- the marsh lake in the south-centre (irregular) and a small tarn on the moor
    m.blob("~", 29, 21, 4, 3, seed=5, wobble=0.4); m.blob("~", 25, 24, 2, 1, seed=6, wobble=0.3); m.blob("~", 14, 9, 2, 2, seed=7, wobble=0.4)
    # --- the moor: ridges and woods; the camp's hills
    for i, pts in enumerate([[(3, 4), (10, 5)], [(2, 10), (7, 11)], [(13, 2), (19, 4)], [(15, 11), (20, 12)], [(18, 7), (19, 10)]]):
        belt(m, "^", pts, width=1, seed=10 + i, p=0.95)
    for i, (cx, cy, n) in enumerate([(6, 8, 3), (17, 5, 3), (11, 12, 2), (4, 2, 2)]):
        m.cluster("f", cx, cy, n * 3, seed=20 + i)
    belt(m, "f", [(1, 18), (6, 17)], width=1, seed=30); belt(m, "f", [(7, 22), (11, 25)], width=1, seed=31); belt(m, "f", [(2, 25), (7, 26)], width=1, seed=32)
    belt(m, "^", [(1, 20), (4, 19)], width=1, seed=33); belt(m, "^", [(15, 18), (19, 20)], width=1, seed=34); belt(m, "f", [(36, 17), (43, 17)], width=1, seed=35); belt(m, "^", [(38, 24), (44, 23)], width=1, seed=36)
    for i, (cx, cy, n) in enumerate([(41, 21, 3), (20, 25, 2), (35, 26, 2)]):
        m.cluster("^", cx, cy, n * 2, seed=40 + i)
    m.header(armies=2, colours=(BH, OS), objective=[1], zones=[(2, 22, 1, 44, 11)], comment=(
        "M30 part two, The Last Citadel (normal look, no fog, 46 x 28, no time limit): Asuka + a free tag partner (Black Hole, HQ 1 (5,23), the south-west camp) against Aria (Orange Star, HQ 2 (33,5), the plateau of the highland massif). "
        "The Aisne (y 14) with bridges (9,14) (16,15) (22,15) (31,13) (40,13); passes west (22..25,6), south (33,10..11), east (42..44,6). Com Tower (14,6) and (30,24); Black Crystals by Black Hole's HQ. "
        "Player: INF6 MECH3 TANK6 MDT3 ART4 ROCK2 RECON1 AA3 APC2 FTR3 BCO2; Aria: INF4 MECH3 MDT4 NEO4 MEGA3 ART3 ROCK3 MIS2 AA2 RECON1 FTR2 BMB1."))
    m.put("1", 5, 23).put("2", 33, 5).put("t", 14, 6).put("t", 30, 24)
    m.stamp("X", 2, 22).stamp("X", 8, 21).stamp("X", 5, 26)
    # --- roads: each bridge has a straight approach; the roads climb to the passes and round the plateau
    route(m, [S(5, 22), S(7, 19), (9, 17), (9, 16), (9, 15), (9, 14, "="), (9, 13), (9, 12), (9, 11), S(11, 8), S(16, 6), S(21, 6), (22, 6), (25, 6), S(27, 6), S(33, 6)], seed=1, wander=0.5)
    route(m, [S(8, 23), S(12, 20), (16, 18), (16, 17), (16, 16), (16, 15, "="), (16, 14), (16, 13), (16, 12), S(17, 10)], seed=2, wander=0.5)
    route(m, [S(10, 24), S(15, 21), S(20, 19), (22, 18), (22, 17), (22, 16), (22, 15, "="), (22, 14), (22, 13), (22, 12), S(26, 12), S(30, 12), (33, 12), (33, 11), (33, 10), S(33, 7)], seed=3, wander=0.5)
    route(m, [S(22, 23), S(30, 18), (40, 18), (40, 17), (40, 16), (40, 15), (40, 14), (40, 13, "="), (40, 12), (40, 11), S(42, 8), (42, 6), S(40, 6), S(34, 6)], seed=4, wander=0.5)
    route(m, [S(27, 5), S(30, 4), S(36, 4), S(40, 5), S(40, 8), S(34, 8), S(28, 8), S(27, 5)], seed=5, wander=0.3)
    route(m, [S(28, 19), (31, 17), (31, 16), (31, 15), (31, 14), (31, 13, "="), (31, 12)], seed=6, wander=0.4)
    thin_roads(m); fix_rungs(m)
    # (Aria's plateau and the camp are owned: capital letters; the rest is neutral)
    for args in [(5, 23, "BBC"), (8, 20, "BC"), (4, 19, "BC"), (11, 24, "C"), (3, 26, "c"),
                 (33, 5, "BBBC"), (29, 4, "BC"), (38, 4, "BA"), (29, 8, "AC"), (38, 8, "BA"), (33, 8, "C"), (27, 4, "C"), (40, 6, "C"),
                 (14, 17, "c"), (21, 17, "cb"), (25, 13, "c"), (13, 12, "c"), (18, 9, "cb"), (10, 7, "cc"), (6, 5, "c"), (36, 16, "ca"), (41, 18, "c"), (43, 12, "c"), (31, 13, "c"), (24, 20, "c"), (36, 24, "c"), (16, 23, "c"), (2, 12, "c"), (2, 3, "c"), (28, 26, "c"), (44, 26, "c"), (12, 20, "c"), (18, 14, "c"), (40, 14, "c"), (8, 15, "c"), (16, 2, "c"), (44, 17, "c"), (30, 18, "c"), (1, 1, "c"), (43, 1, "c"), (6, 3, "c"), (24, 15, "c"), (37, 21, "c"), (42, 24, "c"), (12, 15, "c"), (35, 19, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 5)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 6, MECH: 3, TANK: 6, MDT: 3, ART: 4, ROCK: 2, RECON: 1, AA: 3, APC: 2}, (1, 16, 14, 26), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 3, BCO: 2}, (1, 16, 14, 26), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 4, MECH: 4, MDT: 6, NEO: 6, MEGA: 8, ART: 4, ROCK: 4, MIS: 3, AA: 3, RECON: 1}, (26, 3, 41, 9), seed=3, gap=0, avoid=av)
    m.spread(2, {FTR: 3, BMB: 2}, (26, 3, 41, 9), seed=4, gap=1, avoid=av)
    m.note("hq", 5, 23, "Asuka's HQ"); m.note("enemy_hq", 33, 5, "Aria's HQ (objective)")
    return m
