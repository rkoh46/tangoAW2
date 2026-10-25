"""M8 Hammer and Anvil (Act II, rain): Klaus and Cassius, as a pair, break the Orange Star border force at Ironhold.

Design (docs/dev/map-design.md). The situation: the legion (one army, the first Tag) comes from the west over the Brimwater canal; Max holds Ironhold,
a ring of crags with a front gate and a rear gate, Sasha's column camps on the south-east plain with her own factories. Both are allies.
- Lanes: the canal has three crossings (the north road's bridge, the two-lane causeway in the middle, the south road's bridge) and a farm bridge on the
  ring road; past it the north road runs round the crags to the rear gate (Cassius's flank, the Hammer), the causeway road goes to the front gate
  (Klaus's line, the Anvil) and the south road heads for Sasha's camp.
- Where the fight happens: the causeway head (the silo (16,7), the east-bank villages), the fields north and south of the crags (forward neutral bases
  (21,4) and (21,17)), then the two gates.
- Properties: villages three cells apart on both banks and round the crags; the ring's inside is Max's yard (HQ, two factories, cities); Sasha's camp
  has its HQ, two factories and cities; the player's camp a factory and three cities.
- Threats and answers: Max's guns inside the crags -> recons find them, tanks through the rear gate, the Tag Power; Md tanks at the gate -> Md tanks,
  artillery, mechs; Sasha's rockets -> tanks and the AA along the south road; the rain's fog -> recons on both flanks.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from aw2.esmaplib import *

W, H = 38, 24
FORT = (26, 10)


def build():
    m = Canvas("es08", W, H)
    m.header(armies=3, colours=(GE, OS, BM), team=[1, 2, 2], objective=[1], comment=(
        "M8 Hammer and Anvil (Ironhold, rain): rout both Orange Star armies or take Max's HQ 2 (26,10). The Brimwater canal (x13..16, north edge to south edge) crossed at "
        "(13,3), the causeway (14,8..9), (15,14) and (16,20). Ironhold's crags ring around (26,10): front gate (20,9..11), rear gate (32,9..10). Silo (16,7). "
        "Forward neutral bases (21,4) (21,17). Player INF4 MECH3 TANK4 MDT2 RECON2 ART2 AA1, base (4,8); Max INF3 MECH2 MDT2 TANK1 ART2 AA1; Sasha INF2 TANK2 RECON2 ROCK1, HQ 3 (34,20)."))
    # --- Ironhold's crags: a ragged ring of rock round the fort
    import math
    for y in range(H):
        for x in range(W):
            d = math.hypot((x - FORT[0]) / 6.0, (y - FORT[1]) / 4.6)
            if 0.82 <= d <= 1.08 + 0.12 * math.sin(3 * x + 2 * y):
                m.put("^", x, y)
    for x, y in [(20, 9), (20, 10), (20, 11), (21, 10), (19, 10), (32, 9), (32, 10), (31, 10), (33, 10), (31, 9), (33, 9)]:
        m.put(".", x, y)
    # --- cover and hills outside
    for cx, cy, n, sd, ch in [(9, 5, 7, 1, "f"), (9, 15, 7, 2, "f"), (6, 13, 5, 3, "f"), (18, 5, 5, 4, "f"), (18, 15, 5, 5, "f"), (26, 2, 6, 6, "f"), (27, 19, 6, 7, "f"),
                              (34, 5, 6, 8, "f"), (36, 14, 5, 9, "f"), (11, 21, 6, 11, "f"), (2, 20, 6, 12, "f"), (7, 22, 5, 13, "f"), (37, 2, 4, 14, "f"),
                              (3, 2, 6, 15, "^"), (10, 1, 4, 17, "^"), (37, 12, 4, 18, "^"), (21, 22, 5, 19, "^"), (30, 22, 5, 20, "f"), (1, 12, 4, 21, "f"),
                              (6, 3, 4, 22, "f"), (2, 7, 4, 23, "f"), (11, 11, 4, 24, "f"), (18, 12, 4, 25, "f"), (23, 1, 4, 26, "^"), (12, 16, 4, 34, "f"), (7, 18, 4, 35, "f"), (33, 6, 3, 36, "^"), (17, 22, 3, 37, "f"), (2, 3, 3, 38, "f"), (11, 9, 3, 39, "f"), (36, 21, 3, 40, "^"), (27, 14, 3, 41, "f"), (5, 16, 4, 42, "f"), (22, 6, 3, 43, "f"), (15, 18, 3, 44, "f"), (10, 3, 3, 45, "f"), (30, 4, 5, 27, "f"),
                              (25, 21, 4, 28, "f"), (36, 23, 3, 29, "f"), (18, 20, 4, 30, "f"), (9, 9, 3, 31, "^"), (24, 16, 4, 32, "f"), (29, 16, 3, 33, "^")]:
        m.cluster(ch, cx, cy, n, seed=sd)
    # --- the Brimwater canal, three crossings and the causeway
    m.river([(13, 0), (13, 5), (14, 5), (14, 11), (15, 11), (15, 16), (16, 16), (16, 23)])
    # --- roads
    for pts in ([(4, 11), (4, 3), (12, 3)], [(14, 3), (35, 3), (35, 8), (33, 8), (33, 10)], [(4, 9), (8, 9), (8, 8), (13, 8)], [(15, 8), (18, 8), (18, 10), (25, 10)],
                [(4, 11), (4, 20), (15, 20)], [(17, 20), (34, 20)], [(8, 14), (14, 14)], [(16, 14), (20, 14), (20, 17), (31, 17), (31, 13), (33, 13), (33, 11)],
                [(32, 10), (27, 10)], [(23, 8), (23, 12)], [(28, 12), (28, 8)], [(35, 17), (35, 20)], [(31, 17), (35, 17)], [(21, 3), (21, 4)], [(4, 11), (3, 11)],
                [(8, 14), (8, 11), (4, 11)]):
        m.road(pts)
    for x, y in ((13, 3), (14, 8), (14, 9), (15, 14), (16, 20)):
        m.put("=", x, y)
    # --- properties
    m.put("1", 3, 11).put("B", 4, 8).puts("C", [(2, 14), (6, 6), (6, 12)])
    m.put("2", *FORT).puts("B", [(23, 8), (28, 12)]).puts("C", [(24, 12), (28, 8), (30, 10)])
    m.put("3", 34, 20).puts("B", [(31, 18), (35, 16)]).puts("C", [(32, 22), (36, 19), (29, 21)])
    m.puts("b", [(21, 4), (21, 17)]).put("M", 16, 7)
    m.puts("c", [(2, 1), (7, 1), (1, 5), (8, 5), (10, 7), (1, 9), (11, 12), (7, 16), (2, 17), (10, 18), (6, 21), (12, 23), (1, 22),
                 (16, 1), (19, 2), (17, 11), (19, 7), (17, 18), (19, 23), (16, 5),
                 (25, 1), (29, 1), (33, 1), (37, 5), (31, 6), (36, 9), (35, 12), (26, 16), (23, 19), (27, 23), (37, 17), (23, 15), (30, 14)])
    m.tidy()
    # --- the legion on the west bank
    m.spread(1, {ART: 2, AA: 1}, (1, 7, 7, 15), seed=1, gap=1)
    m.spread(1, {MDT: 2, TANK: 4, RECON: 2}, (5, 5, 12, 17), seed=2, gap=1)
    m.spread(1, {INF: 4, MECH: 3}, (2, 4, 12, 18), seed=3, gap=1)
    # --- Max in Ironhold, Sasha on the plain
    m.units(2, INF, [(21, 9), (21, 11), (24, 8)], hold=True).units(2, MECH, [(23, 11), (25, 9)], hold=True)
    m.units(2, MDT, [(24, 10), (27, 9)]).unit(2, TANK, 27, 11)
    m.units(2, ART, [(29, 9), (29, 11)], hold=True).unit(2, AA, 26, 8)
    m.units(3, INF, [(33, 19), (35, 18)]).units(3, TANK, [(30, 19), (33, 21)]).units(3, RECON, [(31, 16), (36, 20)]).unit(3, ROCK, 35, 21)
    m.note("hq1", 3, 11).note("hq2", 26, 10, "Max's HQ inside the crags").note("hq3", 34, 20, "Sasha's HQ")
    m.note("causeway", 14, 8, "the two-lane causeway (14,8..9)").note("silo", 16, 7, "neutral missile silo by the causeway head")
    m.note("fort_gate", 20, 10, "front gate").note("rear_gate", 32, 10, "rear gate")
    m.note("fwd_n", 21, 4, "neutral base on the north road").note("fwd_s", 21, 17, "neutral base on the south ring road")
    return m
