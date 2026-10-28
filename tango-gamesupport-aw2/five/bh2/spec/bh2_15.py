"""BH2 M15 Iron Gate Pass (Act III): the Blue Moon mountains just before the snow. Hawke (forced, Black Hole) against Olaf (Blue Moon): the pass is the map. Snow look, clear.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: land edge to edge, a great mountain massif across the middle (a band of cliffs and peaks nine rows deep) with three ways through: the Iron Gate in the centre (a two-wide road between two hill-forts), a goat path in the west and a gorge in the east, each one cell wide.
The situation: Black Hole holds the south (HQ, bases, a Com Tower at the foot of the gate); Olaf holds the north (HQ, bases and the heights behind the gate, his Neotanks and artillery covering the pass). Whoever controls the gate controls the map; the side paths are for a small fast force to turn it.
- Lanes: the Iron Gate road, the west goat path, the east gorge, and the valley roads on either side of the massif.
- Where the fight happens: the gate's southern fort and its Com Tower, then the passes' mouths; artillery on the heights shells the approach.
- Properties: a district of bases at each HQ, two villages at the gate, a village in each side pass.
- Threats and answers: Olaf's artillery on the heights -> Black Hole's Rockets and Missiles and a push through the side paths; his Neotanks at the gate's mouth -> Md Tanks and Anti-Tank fire from the forts.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, fix_rungs

W, H = 38, 26


def build():
    m = Canvas("bh2_15", W, H)
    S = lambda x, y: snap(m, x, y)
    # --- the massif: a deep band of mountains with three ways through (centre road, west path, east gorge)
    import random as _r
    rr = _r.Random("bh2_15/massif")
    top = bot = 0
    for x in range(W):
        top = max(-2, min(2, top + rr.choice([-1, 0, 0, 1]))); bot = max(-2, min(2, bot + rr.choice([-1, 0, 0, 1])))
        for y in range(9 + top, 16 + bot):
            m.put("^" if rr.random() > 0.2 else "f", x, y)
    for y in range(9, 16):
        m.put(".", 18, y).put(".", 19, y)                      # the Iron Gate: two cells wide
    for y in range(9, 16):
        m.put(".", 6 + (y % 3 == 0), y)                        # the west goat path, one cell wide, meandering
        m.put(".", 31 - (y % 4 == 0), y)                       # the east gorge
    for (x, y) in [(12, 11), (13, 12), (14, 11), (25, 12), (26, 13), (24, 12), (9, 10), (28, 14), (3, 12), (4, 12), (34, 12)]:
        m.put(".", x, y)                                       # clearings in the massif (breaks the wall's look)
    m.put("f", 20, 11).put("f", 17, 13).put(".", 20, 13).put("f", 20, 9).put("f", 17, 10)
    belt(m, "f", [(15, 9), (16, 12)], width=1, seed=1); belt(m, "f", [(22, 12), (23, 15)], width=1, seed=2)
    # --- relief north and south: woods and hills
    belt(m, "f", [(3, 5), (9, 7)], width=1, seed=3); belt(m, "f", [(26, 6), (33, 4)], width=1, seed=4); belt(m, "^", [(1, 1), (6, 2)], width=1, seed=5); belt(m, "^", [(30, 1), (36, 3)], width=1, seed=6)
    belt(m, "f", [(4, 19), (10, 21)], width=1, seed=7); belt(m, "f", [(27, 19), (34, 21)], width=1, seed=8); belt(m, "^", [(2, 23), (8, 24)], width=1, seed=9); belt(m, "^", [(28, 24), (35, 23)], width=1, seed=10)
    for i, (cx, cy, n) in enumerate([(12, 4, 3), (24, 3, 3), (13, 20, 3), (24, 21, 3), (3, 17, 2), (34, 7, 2)]):
        m.cluster("f", cx, cy, n * 2, seed=40 + i)
    m.header(armies=2, colours=(BH, BM), objective=[1], comment=(
        "M15 Iron Gate Pass (snow look, clear): Hawke (forced, Black Hole, HQ 1 (19,22), south) against Olaf (Blue Moon, HQ 2 (19,3), north). A massif (rows 9..15) with three ways through: the Iron Gate (x 18..19), the west goat path (x 6..7) and the east gorge (x 30..31). "
        "Com Tower (19,18) at the gate's foot; a missile silo (19,6) behind Olaf's gate. Player: INF5 MECH3 TANK5 MDT3 ART2 ROCK2 RECON1 AA1 MIS1; Olaf: INF4 MECH2 TANK3 NEO3 MDT2 ART3 ROCK2 AA2 RECON1."))
    m.put("1", 19, 22).put("2", 19, 3).put("t", 19, 18).put("M", 19, 6)
    route(m, [S(19, 21), (19, 18), (19, 17), (19, 16), (19, 15), (19, 12), (19, 9), (19, 8), (19, 7), S(19, 4)], seed=1, wander=0.2)
    route(m, [S(18, 21), (18, 18), (18, 16), (18, 9), (18, 8)], seed=2, wander=0.0) if False else None
    route(m, [S(9, 22), S(6, 18), (6, 16), (6, 12), (6, 9), (6, 8), S(7, 5), S(12, 3), S(17, 3)], seed=3, wander=0.4)
    route(m, [S(29, 22), S(31, 18), (31, 16), (31, 12), (31, 9), (31, 8), S(30, 5), S(25, 3), S(21, 3)], seed=4, wander=0.4)
    route(m, [S(6, 18), S(12, 19), S(19, 19)], seed=5); route(m, [S(31, 18), S(25, 19), S(19, 19)], seed=6); route(m, [S(7, 5), S(13, 6), S(19, 6)], seed=7); route(m, [S(30, 5), S(25, 6), S(19, 6)], seed=8)
    route(m, [(19, 12), (19, 13)], seed=9)
    thin_roads(m); fix_rungs(m)
    for args in [(19, 22, "BBC"), (15, 23, "BC"), (23, 23, "BC"), (19, 25, "C"), (19, 3, "BBC"), (15, 2, "BC"), (23, 2, "BC"), (19, 1, "C"),
                 (17, 18, "C"), (21, 18, "C"), (17, 7, "C"), (21, 7, "C"), (6, 14, "C"), (31, 14, "C"), (6, 19, "c"), (31, 19, "c"), (6, 5, "c"), (31, 5, "c"), (11, 22, "c"), (27, 22, "c"), (11, 3, "c"), (27, 3, "c"), (2, 12, "c"), (35, 12, "c"), (19, 12, "cc"), (14, 12, "c"), (24, 12, "c"), (2, 1, "c"), (36, 1, "c"), (36, 24, "c"), (2, 25, "c"), (10, 15, "cc"), (27, 15, "cc"), (12, 12, "c"), (27, 11, "c"), (4, 21, "c"), (34, 21, "c"), (4, 5, "c"), (34, 5, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 7)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 3, TANK: 5, MDT: 3, ART: 2, ROCK: 2, RECON: 1, AA: 1, MIS: 1}, (6, 17, 32, 24), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 3, NEO: 3, MDT: 2, ART: 3, ROCK: 2, AA: 2, RECON: 1}, (6, 1, 32, 8), seed=2, gap=0, avoid=av)
    m.note("hq", 19, 22, "Hawke's HQ"); m.note("enemy_hq", 19, 3, "Olaf's HQ (objective)")
    return m
