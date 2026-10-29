"""BH2 M30 The Orange Line (Act V): Orange Star's outer defences, after the Gate of Colours and before the final battle. A free pair (Black Hole) against Rachel + Sami, one Orange Star army under a tag pair. Normal look, rain (and so fog).

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: land edge to edge, cut north to south by two stepped rivers and held by a staggered trench of woods and mountains between them: no pipes, no walls, only the ground. The west river (x 13..14) has three bridges and is Black Hole's first obstacle;
the trench (x 17..28) is three broken belts (woods, a mountain ridge, woods again) with gaps for the roads, a Com Tower at its heart and forward bases built into it; the east river (x 30..31) has four bridges, a fortified town at each bridgehead, and behind it the reserve ground.
The situation: Black Hole's camp is in the west (HQ 1 at (4,14)). Orange Star owns everything from the trench east: Sami's infantry, thick on the trench and the east river's bridgeheads; Rachel's HQ 2 at (39,13) with her reserve (tanks, artillery, a few aircraft) and real production: eight bases and an airport behind the river, and the forward bases in the trench.
- Lanes: the three west bridges, the gaps of the trench belts (the north gap, the central road, the south gap), the four east bridges.
- Where the fight happens: the Com Tower in the trench's heart (22,13) and the forward bases round it, then the east bridgeheads.
- Properties: the camp's bases, neutral cities between the west river and the trench (for Black Hole to take), forward bases and cities in the trench and at the bridgeheads (Orange Star's), the reserve's bases and airport.
- Threats and answers: Sami's massed Infantry and Mechs in the woods -> artillery and Rockets from behind the west river and Md Tanks to flush them; Rachel's tanks counter-attacking over the bridges -> Anti-Tank fire (Md Tanks, Rockets) on the bridgeheads; her Fighters and the airport -> Anti-Air.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 44, 28


def build():
    m = Canvas("bh2_30", W, H)
    S = lambda x, y: snap(m, x, y)
    # --- the rivers: stepped north to south, three bridges on the west one, four on the east one
    m.river([(13, 0), (13, 9), (14, 9), (14, 18), (13, 18), (13, 27)])
    m.river([(30, 0), (30, 7), (31, 7), (31, 20), (30, 20), (30, 27)])
    for x, y in ((13, 4), (14, 13), (13, 23), (30, 3), (31, 11), (31, 16), (30, 24)):
        m.put("=", x, y)
    # --- the trench: three broken belts (woods, a mountain ridge, woods), a gap for each road, rubble heaps and copses between
    belt(m, "f", [(18, 0), (19, 7), (18, 13), (19, 20), (18, 27)], width=1, seed=1, gaps=[(19, 7), (18, 13), (19, 20)], p=0.97)
    belt(m, "^", [(22, 1), (23, 6), (22, 10), (23, 17), (22, 21), (23, 26)], width=1, seed=2, gaps=[(23, 6), (22, 10), (23, 17), (22, 21)], p=0.95)
    belt(m, "f", [(27, 1), (26, 8), (27, 14), (26, 20), (27, 27)], width=1, seed=3, gaps=[(26, 8), (27, 14), (26, 20)], p=0.97)
    for i, (cx, cy, n) in enumerate([(20, 4, 3), (20, 22, 3), (25, 4, 3), (25, 23, 3), (24, 14, 2), (16, 3, 3), (16, 25, 3)]):
        m.cluster("f", cx, cy, n * 2, seed=40 + i)
    for i, (cx, cy, n) in enumerate([(24, 8, 2), (24, 19, 2), (21, 16, 2), (28, 11, 2)]):
        m.cluster("^", cx, cy, n * 3, seed=50 + i)
    # --- the camp's hills and the reserve ground's ridges
    belt(m, "^", [(1, 3), (6, 5), (10, 3)], width=1, seed=4, gaps=[(6, 5)]); belt(m, "f", [(2, 21), (8, 23), (11, 22)], width=1, seed=5); belt(m, "f", [(3, 8), (9, 9)], width=1, seed=6)
    belt(m, "^", [(34, 3), (38, 5), (42, 3)], width=1, seed=7, gaps=[(38, 5)]); belt(m, "f", [(33, 22), (38, 23), (42, 21)], width=1, seed=8); belt(m, "^", [(35, 17), (40, 18)], width=1, seed=9, gaps=[(37, 18)])
    for i, (cx, cy, n) in enumerate([(7, 17, 3), (6, 25, 2), (41, 9, 3), (36, 26, 2), (10, 12, 3), (11, 17, 3), (36, 13, 3), (37, 21, 3), (16, 12, 3), (16, 16, 3), (9, 4, 3), (9, 25, 3), (33, 14, 3), (34, 7, 3), (34, 19, 3)]):
        m.cluster("f", cx, cy, n * 2, seed=60 + i)
    m.header(armies=2, colours=(BH, OS), objective=[1], zones=[(2, 18, 0, 43, 27)], comment=(
        "M30 The Orange Line (normal look, rain and so fog): a free pair (Black Hole, HQ 1 (4,14), the west) against Rachel + Sami (one Orange Star army under a tag pair, HQ 2 (39,13), the east). The west river (x 13..14) has bridges (13,4) (14,13) (13,23); the trench (x 17..28) holds the Com Tower (22,13) "
        "and the forward bases; the east river (x 30..31) has bridges (30,3) (31,11) (31,16) (30,24). Everything from x 18 east is Orange Star's (`zone`). Player: INF6 MECH3 TANK6 MDT3 ART4 ROCK2 RECON1 AA2 APC2 FTR2 BCO1; Orange Star: INF14 MECH4 TANK5 MDT3 ART4 ROCK2 AA2 RECON1 FTR2."))
    m.put("1", 4, 14).put("2", 39, 13).put("t", 22, 13)
    # --- roads: each bridge has a straight approach; the trunk runs west to east through the trench's gaps
    def cross(x, y, k=3):
        return [(x - k + i, y) for i in range(0, 2 * k + 1)]
    route(m, [S(4, 14), S(9, 14)] + [(11, 14), (12, 14), (13, 14)] + [(14, 13)] if False else [S(4, 14), S(9, 13), (11, 13), (12, 13), (13, 13), (14, 13, "="), (15, 13), (16, 13)] + [S(18, 13), S(20, 13), S(22, 13), S(25, 13), (28, 13), (29, 12), (30, 12), (31, 11, "="), (32, 11), (33, 11), S(36, 12), S(39, 13)], seed=1, wander=0.4)
    route(m, [S(4, 13), S(7, 5), (10, 4), (11, 4), (12, 4), (13, 4, "="), (14, 4), (15, 4), S(18, 5), S(21, 5), S(24, 3), S(28, 3), (29, 3), (30, 3, "="), (31, 3), (32, 3), S(36, 5), S(39, 12)], seed=2, wander=0.5)
    route(m, [S(4, 15), S(8, 22), (10, 23), (11, 23), (12, 23), (13, 23, "="), (14, 23), (15, 23), S(18, 22), S(21, 22), S(24, 23), S(28, 24), (29, 24), (30, 24, "="), (31, 24), (32, 24), S(36, 22), S(39, 14)], seed=3, wander=0.5)
    route(m, [S(28, 13), (28, 14), (29, 15), (30, 16), (31, 16, "="), (32, 16), (33, 16), S(36, 15)], seed=4)
    route(m, [S(22, 13), S(22, 17), S(22, 22)], seed=5); route(m, [S(22, 13), S(22, 9), S(23, 5)], seed=6); route(m, [S(19, 7), S(19, 13)], seed=7) if False else None
    thin_roads(m); fix_rungs(m)
    # properties: Black Hole's camp; neutral cities between the west river and the trench; Orange Star's forward bases and bridgeheads (zone), the reserve's bases and airport
    for args in [(4, 14, "BBC"), (6, 11, "BC"), (6, 17, "BC"), (3, 12, "C"), (9, 14, "c"), (8, 6, "c"), (9, 22, "c"), (16, 8, "cc"), (16, 19, "cc"), (15, 13, "c"), (11, 26, "c"), (11, 1, "c"),
                 (21, 8, "B"), (21, 19, "B"), (20, 13, "BC"), (25, 11, "C"), (25, 16, "C"), (24, 4, "BC"), (24, 23, "BC"), (28, 13, "C"), (21, 2, "c"), (21, 25, "c"),
                 (32, 10, "BC"), (32, 17, "BC"), (32, 4, "C"), (32, 23, "C"), (29, 8, "C"), (29, 19, "C"),
                 (39, 13, "BBBC"), (36, 9, "BA"), (36, 17, "BA"), (41, 6, "BC"), (41, 21, "BC"), (38, 3, "C"), (38, 24, "C"), (42, 13, "C"), (35, 13, "C"), (34, 26, "c"), (34, 1, "c"), (1, 1, "c"), (2, 25, "cc"), (42, 26, "c"), (42, 1, "c"), (10, 9, "c"), (10, 19, "c"), (17, 22, "c"), (17, 4, "c"), (26, 13, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 6, MECH: 3, TANK: 6, MDT: 3, ART: 4, ROCK: 2, RECON: 1, AA: 2, APC: 2}, (1, 8, 11, 20), seed=1, gap=0, avoid=av)
    m.spread(1, {FTR: 2, BCO: 1}, (1, 8, 11, 20), seed=2, gap=1, avoid=av)
    m.spread(2, {INF: 12, MECH: 3, ROCK: 2, ART: 2, AA: 1}, (19, 2, 29, 25), seed=3, gap=0, avoid=av)          # Sami's line: the trench and the bridgeheads
    m.spread(2, {INF: 2, MECH: 1, TANK: 5, MDT: 3, ART: 2, AA: 1, RECON: 1}, (32, 3, 42, 24), seed=4, gap=0, avoid=av)    # Rachel's reserve
    m.spread(2, {FTR: 2}, (33, 3, 42, 24), seed=5, gap=1, avoid=av)
    m.note("hq", 4, 14, "Black Hole's HQ"); m.note("enemy_hq", 39, 13, "Rachel + Sami's HQ (objective)"); m.note("tower", 22, 13, "the trench's Com Tower")
    return m
