"""BH2 M20 The Rail East (Act IV), front 1: the rail corridor. A free pick against Andy. (Front 2, the rail yard in the sandstorm against Hachi, is bh2_20b.)

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: the heavy train with the Accord's door-seal machinery runs east along a long narrow valley between two mountain ranges: a map that is wide and short, 56 columns by 16 rows, all land and all
hill country. The rail is the trunk road down the valley's floor, from Black Hole's landing camp in the west (HQ, a base district) through a chain of five station towns to Andy's terminus in the east (HQ, a base district). Three rivers cut the valley from the northern range to
the southern edge through gorges and the rail crosses each on a bridge: the corridor is a string of river crossings. The ranges have passes and a ledge road on each side that the flanking columns use.
- Lanes: the rail trunk, the north ledge road in the range, the south ledge road, the three gorges' bridges, the passes between the ledges and the valley.
- Where the fight happens: the second and third river crossings (22,8) and (34,7) with the Com Towers (24,6) and (32,10) beside them, then the terminus.
- Properties: a town at each station on the rail, villages on the ledges, the two HQ districts, a missile silo in a pass.
- Threats and answers: Andy's Tanks and Md Tanks along the rail -> Black Hole's Md Tanks, Rockets and artillery behind the gorges; Orange Star fields no air here.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, fix_rungs

W, H = 56, 16


def build():
    m = Canvas("bh2_20", W, H)
    # --- the ranges: mountains along the north and south, thick with passes; the valley floor between
    belt(m, "^", [(1, 2), (10, 3), (19, 2), (28, 3), (37, 2), (46, 3), (54, 2)], width=2, seed=1, gaps=[(7, 3), (16, 2), (25, 3), (34, 3), (43, 2), (51, 3)], p=0.95)
    belt(m, "^", [(1, 13), (10, 12), (19, 13), (28, 12), (37, 13), (46, 12), (54, 13)], width=2, seed=2, gaps=[(5, 12), (14, 13), (23, 12), (31, 13), (40, 12), (49, 13)], p=0.95)
    belt(m, "f", [(3, 5), (9, 6)], width=1, seed=3); belt(m, "f", [(12, 9), (17, 10)], width=1, seed=4); belt(m, "f", [(26, 9), (30, 8)], width=1, seed=5); belt(m, "f", [(36, 5), (41, 6)], width=1, seed=6)
    belt(m, "f", [(44, 9), (49, 10)], width=1, seed=7); belt(m, "f", [(19, 5), (21, 6)], width=1, seed=8); belt(m, "f", [(37, 9), (40, 10)], width=1, seed=9); belt(m, "f", [(4, 9), (7, 10)], width=1, seed=10)
    # --- three rivers: from ponds in the northern range through gorges, across the valley to the southern edge
    ponds = []
    for k, (rx, jog) in enumerate(((14, 1), (28, -1), (42, 1))):
        ponds += m.lake(rx, 1, 6, seed=k + 1, river_end=(rx, 2))
    m.river([(14, 2), (14, 6), (15, 6), (15, H - 1)]); m.river([(28, 2), (28, 7), (27, 7), (27, H - 1)]); m.river([(42, 2), (42, 8), (43, 8), (43, H - 1)])
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M20 The Rail East, front 1 (normal look, fog): a free pick (Black Hole, HQ 1 (5,8), the west) against Andy (Orange Star, HQ 2 (50,8), the terminus in the east) in a long valley (56 x 16). Three rivers from ponds in the northern range to the south edge; the rail crosses them at (14,4), (28,5) and (42,5) "
        "(bridges at the straight reaches). Com Towers (24,6) and (32,10), missile silo (37,3). Player: INF4 MECH2 TANK5 MDT2 ART2 ROCK1 RECON1; Andy: INF5 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1."))
    m.put("1", 5, 8).put("2", 50, 8).put("t", 24, 6).put("t", 32, 10).put("M", 37, 3)
    route(m, [(6, 8), (10, 9), (13, 8), (14, 4, "=") if False else (13, 6), (14, 4, "=") if False else (13, 8)], seed=21) if False else None
    rail = [(6, 8), (10, 9), (13, 8), (14, 4)] if False else None
    # the rail: along the valley floor, bridges at the straight reaches of the rivers (river 1 x14 rows 2..6, river 2 x27 rows 7..15 and x28 rows 2..7, river 3 x43 rows 8..15 and x42 rows 2..8)
    route(m, [(6, 8), (9, 8), (12, 8), (15, 8, "="), (18, 8), (22, 8), (26, 8), (27, 8, "="), (30, 8), (34, 8), (38, 8), (40, 9), (43, 10, "="), (46, 9), (49, 8)], seed=21, wander=0.3)
    route(m, [(5, 9), (7, 12), (11, 11), (15, 12, "="), (19, 11), (24, 11), (27, 12, "="), (30, 11), (35, 10), (39, 11), (43, 12, "="), (47, 11), (51, 9)], seed=22, wander=1.1)
    route(m, [(6, 7), (9, 5), (12, 5), (14, 4, "="), (17, 5), (22, 4), (26, 5), (28, 4, "="), (31, 5), (36, 5), (40, 4), (42, 4, "="), (45, 5), (49, 7)], seed=23, wander=1.1)
    route(m, [(24, 8), (24, 6)], seed=24); route(m, [(32, 11), (32, 10)], seed=25) if False else route(m, [(31, 10), (32, 10)], seed=25); route(m, [(37, 8), (37, 4)], seed=26)
    thin_roads(m); fix_rungs(m)
    for args in [(5, 8, "BBC"), (9, 9, "BC"), (7, 5, "C"), (7, 12, "C"), (12, 9, "CC"), (18, 9, "Cb"), (22, 8, "Cc"), (26, 8, "bc"), (30, 9, "Cb"), (34, 8, "CC"), (38, 8, "Cb"), (41, 8, "bc"), (46, 9, "C"),
                 (50, 8, "BBC"), (47, 6, "BC"), (47, 11, "BC"), (51, 5, "C"), (52, 11, "C"), (12, 5, "c"), (22, 4, "c"), (31, 5, "c"), (40, 4, "c"), (19, 11, "c"), (35, 10, "c"), (47, 11, "c"), (3, 4, "c"), (53, 13, "c"), (3, 12, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 14)
    m.tidy()
    for (x, y) in ponds:
        m.g[y][x] = "~"
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 5, MDT: 2, ART: 2, ROCK: 1, RECON: 1}, (2, 4, 12, 12), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1}, (44, 4, 54, 12), seed=2, gap=0, avoid=av)
    m.note("hq", 5, 8, "Black Hole's HQ"); m.note("enemy_hq", 50, 8, "Andy's HQ (objective)"); m.note("silo", 37, 3, "the missile silo in the pass")
    return m
