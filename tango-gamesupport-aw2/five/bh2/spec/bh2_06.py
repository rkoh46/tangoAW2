"""BH2 M6 Forest of Spears (Act I): Green Earth's forest country, a Com Tower network fight. A free pick (Black Hole) against Javier (Green Earth); when Black Hole holds every one of his Com Towers, Eagle takes command of the same army and an air wing lands. Normal look, clear.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: land edge to edge, cut by long wooded ridges that run from the north-west to the south-east like spears laid side by side, each ending in a mountain tip; the lanes between the ridges are the roads, and only a few clearings let a lane cross to the next.
The situation: Black Hole enters from the south-west corner (HQ, a base district); Javier holds the north-east (HQ, bases, an airport) and four Com Towers in the clearings of his half. Two more towers stand in the middle clearings, up for grabs: the army that holds more towers fights with a stronger CO.
- Lanes: the three long lanes between the ridges (south, middle, north) and the clearings that join them.
- Where the fight happens: the two middle towers, then Javier's four, one clearing at a time; the ridges hide the flanks.
- Properties: a district of bases at each HQ, villages in the clearings, the towers.
- Threats and answers: Javier's tanks and artillery on the lanes -> Black Hole's Md Tanks and Rockets; his Anti-Air covers the towers; once all four towers fall Eagle's air wing comes: Anti-Air and Missiles.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 40, 28
TOWERS = [(25, 5), (31, 10), (28, 16), (35, 14)]          # Javier's four Com Towers (the mission's trigger cells)


def build():
    m = Canvas("bh2_06", W, H)
    S = lambda x, y: snap(m, x, y)
    # --- the spears: long wooded ridges north-west to south-east, a mountain tip at each south-east end, with clearings (gaps) between them
    ridges = [[(2, 1), (9, 7), (16, 14)], [(9, 0), (17, 7), (25, 16)], [(18, 0), (26, 7), (33, 14)], [(0, 9), (7, 16), (13, 23)], [(10, 15), (18, 22), (25, 27)], [(24, 13), (31, 20), (38, 26)], [(27, 0), (35, 6), (39, 11)]]
    for i, pts in enumerate(ridges):
        belt(m, "f", pts, width=1, seed=1 + i, gaps=[pts[1]], p=0.97)
        tip = pts[-1]
        m.put("^", *tip) if m.inside(*tip) else None
        m.cluster("^", tip[0], tip[1], 4, seed=20 + i, only=".f")
    m.cluster("^", 21, 11, 5, seed=30); m.cluster("^", 6, 6, 4, seed=31); m.cluster("^", 34, 22, 4, seed=32); m.cluster("f", 28, 23, 7, seed=33); m.cluster("f", 3, 4, 4, seed=34)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M6 Forest of Spears (normal look, clear): a free pick (Black Hole, HQ 1 (5,23), south-west) against Javier (Green Earth, HQ 2 (34,5), north-east). Javier's four Com Towers (25,5) (31,10) (28,16) (35,14): when Black Hole holds them all Eagle takes command of the same army and an air wing lands. "
        "Two neutral towers in the middle clearings (18,11) and (12,18). Player: INF5 MECH3 TANK4 MDT2 ART2 ROCK1 AA1 RECON1 APC1; Javier: INF5 MECH3 TANK4 MDT2 ART2 AA2 RECON1 MIS1."))
    m.put("1", 5, 23).put("2", 34, 5)
    for (x, y) in TOWERS:
        m.put("T", x, y)
    m.put("t", 18, 11).put("t", 12, 18)
    # --- roads: three long lanes between the ridges, joined in the clearings
    route(m, [S(5, 22), S(9, 19), S(14, 16), S(18, 12), S(24, 9), S(29, 6), S(33, 5)], seed=1, wander=0.6)
    route(m, [S(6, 24), S(13, 24), S(19, 24), S(24, 21), S(29, 17), S(33, 13), S(35, 8), S(34, 6)], seed=2, wander=0.6)
    route(m, [S(4, 21), S(4, 13), S(8, 9), S(13, 5), S(20, 3), S(26, 2), S(31, 3), S(33, 4)], seed=3, wander=0.6)
    route(m, [S(18, 12), S(22, 14), S(27, 16)], seed=4); route(m, [S(12, 18), S(17, 20), S(24, 21)], seed=5); route(m, [S(25, 5), S(28, 7), S(31, 10), S(35, 14)], seed=6)
    thin_roads(m); fix_rungs(m)
    for args in [(5, 23, "BBC"), (8, 25, "BC"), (4, 20, "BC"), (9, 21, "C"), (34, 5, "BBAC"), (31, 3, "BC"), (36, 8, "BA"), (30, 8, "C"), (33, 11, "C"), (25, 5, "C"), (28, 16, "C"), (35, 14, "C"),
                 (18, 11, "cb"), (12, 18, "cb"), (14, 7, "cc"), (21, 4, "c"), (22, 14, "c"), (24, 22, "cc"), (16, 24, "c"), (8, 13, "c"), (30, 24, "c"), (37, 19, "c"), (3, 16, "c"), (20, 18, "c"), (3, 6, "c"), (36, 20, "c"), (36, 25, "c"), (10, 10, "c"), (28, 2, "c"), (16, 3, "cc"), (24, 12, "cc"), (6, 13, "c"), (33, 20, "c"), (13, 26, "c"), (36, 10, "c"), (20, 24, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 3, TANK: 4, MDT: 2, ART: 2, ROCK: 1, AA: 1, RECON: 1, APC: 1}, (1, 17, 14, 26), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 4, MDT: 2, ART: 2, AA: 2, RECON: 1, MIS: 1}, (24, 1, 38, 15), seed=2, gap=0, avoid=av)
    m.note("hq", 5, 23, "Black Hole's HQ"); m.note("enemy_hq", 34, 5, "Javier's HQ (objective)")
    for i, (x, y) in enumerate(TOWERS):
        m.note(f"tower{i + 1}", x, y, "one of Javier's four Com Towers")
    return m
