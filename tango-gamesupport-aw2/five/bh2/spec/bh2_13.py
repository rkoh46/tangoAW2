"""BH2 M13 Two Tides (Act II), front 1: Kanbei's last stand, on blasted ground between two lava tides (the Wasteland look, fog). Asuka (forced) against Kanbei. (Front 2, Grimm's isles, is bh2_13b.)

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Yellow Comet's last great island is pinched in the middle by two tides of lava, one from the north and one from the south, that leave a
broad belt of land between their tips: the island is two halves joined by the belt. Black Hole lands on the western half (HQ, a district of bases, a Com Tower beside the belt); Kanbei stands on the eastern half with his
elite: Md Tanks and Neotanks on the high ground round his HQ, his guard in the passes. Two lava-locked isles hang off the tides' shores on long bridges: the shrine isle in the north tide (a missile silo and a village) and
a ledger isle in the south tide (a Com Tower and a village); whoever crosses holds a long view in the fog. There is no sea here (the wasteland's water is lava): no port, no ship.
- Lanes: the belt (two roads across it and a ridge of mountains with passes between them), the long bridges to the isles, the west half's coast road and the east half's ring of ridges round Kanbei.
- Where the fight happens: the belt's Com Tower and the crossing road, then Kanbei's ridges.
- Threats and answers: Kanbei's Md Tanks and Neotanks -> Black Hole's Md Tanks, Rockets and artillery; his artillery -> Black Hole's own and a fast flank by the coast road; Black Hole fields no aircraft, so Yellow Comet fields no Anti-Air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 40, 30


def build():
    m = Canvas("bh2_13", W, H, fill="~")
    # --- the island: ragged west and east coasts (bays and capes) and the two tides of lava
    XW = [11, 6, 4, 3, 3, 4, 6, 7, 6, 4, 2, 2, 4, 7, 8, 8, 6, 4, 3, 3, 4, 5, 4, 3, 3, 5, 7, 10]
    XE = [30, 33, 35, 36, 35, 34, 35, 36, 37, 38, 38, 37, 35, 34, 35, 37, 38, 38, 37, 35, 34, 35, 36, 37, 36, 34, 32, 29]
    for y in range(1, 29):
        m.rect(".", XW[y - 1], y, XE[y - 1], y)
    m.rect("~", 0, 1, 12, 1)
    land_rows(m, {y: (x0, x1) for y, (x0, x1) in {1: (12, 28), 2: (12, 28), 3: (13, 27), 4: (14, 27), 5: (15, 25), 6: (16, 24), 7: (17, 23), 8: (18, 22)}.items()}, ch="~")       # the north tide
    land_rows(m, {y: (x0, x1) for y, (x0, x1) in {28: (16, 32), 27: (16, 31), 26: (17, 30), 25: (17, 29), 24: (19, 28), 23: (20, 27), 22: (21, 26), 21: (22, 25)}.items()}, ch="~")  # the south tide
    land_rows(m, {2: (18, 22), 3: (17, 23), 4: (18, 22)})                                      # the shrine isle in the north tide
    land_rows(m, {25: (21, 26), 26: (20, 27), 27: (21, 26)})                                    # the ledger isle in the south tide
    # --- relief: the belt's ridge with its passes, Kanbei's ring of ridges, the west half's hills, ash woods
    belt(m, "^", [(19, 12), (25, 15)], width=1, seed=1, gaps=[(21, 13), (24, 15)]); belt(m, "^", [(28, 5), (33, 6), (37, 10)], width=1, seed=2, gaps=[(31, 5)])
    belt(m, "^", [(27, 13), (31, 14), (36, 14)], width=1, seed=3, gaps=[(32, 14)]); belt(m, "^", [(29, 17), (33, 20), (36, 24)], width=1, seed=4, gaps=[(34, 21)])
    belt(m, "^", [(4, 6), (9, 8), (12, 12)], width=1, seed=5, gaps=[(8, 8)]); belt(m, "^", [(3, 14), (8, 14)], width=1, seed=6, gaps=[(5, 14)]); belt(m, "^", [(5, 24), (11, 25), (14, 22)], width=1, seed=7, gaps=[(10, 25)])
    belt(m, "f", [(14, 12), (17, 15)], width=1, seed=8); belt(m, "f", [(8, 18), (12, 20)], width=1, seed=9); belt(m, "f", [(28, 9), (31, 11)], width=1, seed=10); belt(m, "f", [(31, 17), (34, 18)], width=1, seed=11)
    belt(m, "f", [(5, 10), (8, 11)], width=1, seed=12); belt(m, "f", [(12, 26), (15, 25)], width=1, seed=13); belt(m, "f", [(34, 7), (37, 8)], width=1, seed=14); belt(m, "f", [(26, 19), (28, 21)], width=1, seed=15)
    for i, (cx, cy, n) in enumerate([(9, 16, 3), (30, 24, 3), (16, 18, 3), (26, 10, 3), (7, 5, 2), (35, 26, 2)]):
        m.cluster("f", cx, cy, n, seed=40 + i)
    m.header(armies=2, colours=(BH, YC), objective=[1], comment=(
        "M13 Two Tides, front 1 (Wasteland look, fog, no sea: the water is lava): Asuka (forced, Black Hole, HQ 1 (7,20)) against Kanbei (Yellow Comet, HQ 2 (32,10)). Two tides of lava pinch the island, leaving the belt between (x 17..27, y 9..20). "
        "Com Tower (22,14) on the belt; the shrine isle (north tide: missile silo) and the ledger isle (south tide: Com Tower) hang on long bridges. Player: INF4 MECH2 TANK4 MDT2 ART2 ROCK1 RECON1; Kanbei: INF3 MECH3 TANK4 MDT5 NEO3 ART2 ROCK2."))
    m.put("1", 7, 20).put("2", 32, 10).put("t", 22, 14).put("M", 20, 3).put("t", 23, 26)
    C = lambda x, y: (max(XW[y - 1] + 1, min(XE[y - 1] - 1, x)), y)      # (a waypoint kept on land)
    # --- the long bridges to the isles (across the lava) and the roads that follow the land
    m.bridge(24, 3, 27, 3); m.bridge(17, 26, 19, 26)
    route(m, [C(7, 21), C(10, 17), C(14, 15), C(18, 14), C(22, 15), C(26, 14), C(29, 12), C(32, 11)], seed=1)
    route(m, [C(7, 19), C(5, 13), C(8, 9), C(12, 9), C(17, 10), C(21, 10), C(26, 12)], seed=2)
    route(m, [C(8, 21), C(12, 24), C(17, 22), C(21, 19), C(26, 17), C(30, 16), C(33, 13)], seed=3)
    route(m, [C(32, 9), C(30, 6), C(26, 5)], seed=4); route(m, [C(32, 11), C(35, 14), C(35, 20), C(32, 23)], seed=5); route(m, [C(22, 14), C(22, 12), C(21, 10)], seed=6)
    route(m, [C(22, 15), C(22, 17), C(21, 19)], seed=7); route(m, [C(12, 24), C(12, 27)], seed=8); route(m, [C(5, 13), C(4, 16)], seed=9); route(m, [C(28, 3), C(31, 5)], seed=10); route(m, [C(23, 3), C(21, 3)], seed=11); route(m, [C(12, 24), C(16, 26)], seed=12); route(m, [C(20, 26), C(22, 26)], seed=13)
    thin_roads(m)
    # --- towns
    town(m, 7, 20, "BBC", seed=1); town(m, 9, 23, "BC", seed=2); town(m, 5, 17, "BC", seed=3); town(m, 8, 9, "CC", seed=4); town(m, 12, 24, "C", seed=5); town(m, 14, 15, "Cb", seed=6)
    town(m, 18, 14, "Cb", seed=7); town(m, 21, 10, "C", seed=8); town(m, 21, 19, "C", seed=9); town(m, 26, 14, "Cb", seed=10); town(m, 26, 17, "C", seed=11)
    town(m, 32, 10, "BBBC", seed=12, radius=3); town(m, 30, 6, "BC", seed=13); town(m, 35, 14, "BC", seed=14); town(m, 33, 22, "BC", seed=15); town(m, 29, 12, "C", seed=16)
    town(m, 26, 5, "C", seed=17); town(m, 35, 20, "C", seed=18); town(m, 5, 13, "C", seed=19); town(m, 12, 9, "C", seed=20); town(m, 17, 22, "C", seed=21); town(m, 36, 6, "C", seed=22); town(m, 21, 4, "c", seed=23); town(m, 21, 25, "c", seed=24)
    neutralize(m, 13)
    m.tidy()
    # --- units (fog: the first sight is short; the army is a handful of strong units)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1}, (2, 10, 14, 26), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 3, MECH: 3, TANK: 4, MDT: 5, NEO: 3, ART: 2, ROCK: 2}, (27, 3, 37, 24), seed=2, gap=0, avoid=av)
    m.note("hq", 7, 20, "Asuka's HQ"); m.note("enemy_hq", 32, 10, "Kanbei's HQ (objective)"); m.note("belt", 22, 14, "the belt's Com Tower")
    return m
