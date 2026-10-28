"""BH2 M19 Thirty Years of Iron (Act III, the last): the foundry valley, on blasted ground (Wasteland look). A free pair against one Blue Moon army under the tag pair Olaf + Grit.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: the valley runs west to east between two ridges, with a lava bay eating into each end of the ridges. Black Hole holds the west end: its HQ and a district of
bases, and the old Accord foundry, a Black Factory that is Black Hole's from the first turn (the smart spawner), fed by its supply pipe. Mount Cinder, a volcano with its one-cell wall of cliffs, stands in the middle of the valley; from day 3 it
erupts on the ring road round it. Blue Moon holds the east: its HQ and a big district (bases, two airports, a Com Tower of its own), the biggest army of the act and real production, behind a pipe wall with a seam gate that
shuts the northern pass. The map is big because the enemy needs room to answer the factory's output.
- Lanes: the northern road along the ridge (to the wall's gate and round its end by the cliffs), the southern road, the ring road round the volcano that both cross, the passes in the two ridges.
- Where the fight happens: the ring road and the two Com Towers (18,8) and (32,20); then the wall's gate (36,9) and the eastern district.
- Properties: the foundry's side buildings and bases for Black Hole, bases, airports and villages for Blue Moon, neutral villages on the roads, a missile silo in the south pass.
- Threats and answers: Blue Moon's Fighters and Copters -> the factory's Anti-Air (only when air shows) and Black Hole's own; Neotanks and Md Tanks -> the factory's Md Tanks and artillery; Olaf's wasteland-proof army is the factory's reason to exist.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 46, 28


def build():
    m = Canvas("bh2_19", W, H)
    # --- lava bays: the north and south edges are ragged lava (the wasteland's water), deep at both ends
    rnd = random.Random("bh2_14/lava")
    T, B, t, b = {}, {}, 2, 25
    for x in range(W):
        if x % 4 == 0:
            t = max(1, min(4, t + rnd.choice([-1, 0, 1]))); b = max(23, min(26, b + rnd.choice([-1, 0, 1])))
        T[x], B[x] = t, b
    for x in range(W):
        for y in range(0, T[x]):
            m.g[y][x] = "~"
        for y in range(B[x] + 1, H):
            m.g[y][x] = "~"
    for (cx, cy, rx, ry) in ((3, 2, 4, 3), (42, 2, 4, 3), (4, 25, 4, 3), (41, 25, 4, 3)):
        m.blob("~", cx, cy, rx, ry, seed=cx, wobble=0.3)
    C = lambda x, y: (x, max(T[x] + 2, min(B[x] - 2, y)))
    # --- the ridges and the passes, the wasteland's cinder woods and ash heaps
    belt(m, "^", [(8, 5), (16, 4), (24, 5), (33, 4)], width=1, seed=1, gaps=[(12, 4), (20, 5), (28, 4)]); belt(m, "^", [(8, 22), (16, 23), (24, 22), (33, 23)], width=1, seed=2, gaps=[(12, 23), (20, 22), (28, 23)])
    belt(m, "^", [(37, 5), (42, 7)], width=1, seed=3); belt(m, "^", [(37, 22), (42, 20)], width=1, seed=4, gaps=[(40, 21)]); belt(m, "^", [(3, 9), (6, 7)], width=1, seed=5); belt(m, "^", [(3, 19), (6, 21)], width=1, seed=6)
    belt(m, "^", [(14, 9), (17, 11)], width=1, seed=7); belt(m, "^", [(29, 17), (33, 18)], width=1, seed=8); belt(m, "^", [(14, 17), (17, 19)], width=1, seed=9); belt(m, "^", [(29, 9), (32, 11)], width=1, seed=10)
    belt(m, "f", [(5, 11), (8, 10)], width=1, seed=11); belt(m, "f", [(5, 17), (8, 18)], width=1, seed=12); belt(m, "f", [(19, 17), (22, 19)], width=1, seed=13); belt(m, "f", [(25, 8), (28, 9)], width=1, seed=14)
    belt(m, "f", [(38, 11), (42, 12)], width=1, seed=15); belt(m, "f", [(38, 16), (42, 17)], width=1, seed=16); belt(m, "f", [(11, 7), (14, 8)], width=1, seed=17); belt(m, "f", [(33, 13), (36, 15)], width=1, seed=18)
    for i, (cx, cy, n) in enumerate([(10, 19, 3), (35, 7, 3), (12, 14, 3), (30, 24, 3), (20, 12, 2), (44, 14, 3), (6, 14, 2)]):
        m.cluster("f", cx, cy, n, seed=40 + i)
    # --- Mount Cinder in the middle: a volcano (footprint x22..25, y12..15); its eruptions hit the ring of lane cells (20..27, 9..16... see the ring below)
    m.stamp("V", 23, 14)
    # --- the wall of the northern pass: a pipeline from the north lava to the cliffs, with its gate
    m.pipe([(36, T[36]), (36, 11)]); m.put("Z", 36, 8); m.put("^", 36, 12).put("^", 35, 12).put("^", 37, 12)
    # --- the foundry (Black Hole's Black Factory) and its supply pipe
    m.stamp("F", 9, 14).put("I", 9, 11)
    m.header(armies=2, colours=(BH, BM), objective=[1], comment=(
        "M19 Thirty Years of Iron (Wasteland look, lava for water): a free pair (Black Hole, HQ 1 (4,14)) with the old foundry, a Black Factory at (9,14), against one Blue Moon army under Olaf + Grit (HQ 2 (41,14)). "
        "Mount Cinder (volcano, footprint x22..25 y12..15) erupts from day 3 on its ring road; pipe wall x36 with the gate (36,8). Com Towers (18,8) and (32,20), missile silo (23,24). "
        "Player: INF5 MECH2 TANK4 MDT2 ART2 ROCK1 RECON1 AA2 APC1; Blue Moon: INF5 MECH4 TANK5 MDT4 NEO3 ART4 ROCK3 RECON1 AA1 FTR2 BCO2."))
    m.put("1", 4, 14).put("2", 41, 14).put("t", 18, 8).put("t", 32, 20).put("M", 23, 24)
    route(m, [C(5, 15), C(10, 17), C(15, 20), C(20, 18), C(21, 17), C(21, 15)], seed=1, wander=1.2)
    route(m, [C(5, 13), C(8, 9), C(13, 8), C(17, 8), C(20, 9), C(22, 9), C(26, 9)], seed=2, wander=1.2)
    route(m, [C(20, 9), C(20, 12), C(21, 15), C(21, 17)], seed=3)
    route(m, [C(21, 17), C(27, 17), C(32, 20), C(38, 18), C(41, 15)], seed=4, wander=1.2); route(m, [C(26, 9), C(30, 8), C(35, 8)], seed=5); route(m, [C(37, 8), C(40, 10), C(41, 13)], seed=6)
    route(m, [C(27, 9), C(27, 12), C(27, 17)], seed=7); route(m, [C(32, 20), C(32, 22), C(23, 24)], seed=8); route(m, [C(38, 18), C(43, 17)], seed=9); route(m, [C(41, 14), C(44, 12)], seed=10)
    route(m, [C(15, 20), C(13, 23)], seed=11); route(m, [C(8, 9), C(5, 8)], seed=12); route(m, [C(10, 17), C(9, 17)], seed=13)
    route(m, [C(20, 10), C(27, 10), C(27, 17), C(20, 17), C(20, 10)], seed=30)         # the ring road round Mount Cinder: every lane of the middle passes its eruptions
    route(m, [C(5, 8), C(2, 6)], seed=31)
    thin_roads(m)
    for args in [(4, 14, "BBC"), (7, 11, "BC"), (7, 18, "BC"), (12, 17, "CC"), (13, 8, "C"), (17, 8, "Cb"), (20, 9, "bc"), (15, 20, "Cc"), (21, 17, "c"), (26, 9, "c"), (27, 17, "c"), (30, 8, "c"),
                 (32, 20, "Cb"), (23, 22, "c"), (41, 14, "BBBC"), (38, 11, "BCC"), (38, 18, "BCC"), (43, 12, "AB"), (43, 17, "AB"), (40, 8, "BC"), (40, 21, "BC"), (35, 8, "C"), (36, 16, "C"), (44, 9, "c"), (44, 20, "c"),
                 (11, 22, "c"), (30, 14, "c"), (16, 13, "c"), (33, 11, "C"), (7, 22, "c"), (7, 6, "c"), (2, 6, "cc"), (25, 20, "c"), (39, 14, "C"), (42, 4, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 2, ROCK: 1, RECON: 1, AA: 2, APC: 1}, (2, 7, 14, 21), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 4, TANK: 5, MDT: 4, NEO: 3, ART: 4, ROCK: 3, RECON: 1, AA: 1}, (35, 6, 45, 21), seed=2, gap=0, avoid=av)
    m.spread(2, {FTR: 2, BCO: 2}, (38, 6, 45, 21), seed=3, gap=1, avoid=av)
    m.spread(2, {TANK: 1, MDT: 1, ART: 1}, (28, 6, 34, 22), seed=4, gap=2, avoid=av)
    m.note("hq", 4, 14, "Black Hole's HQ"); m.note("enemy_hq", 41, 14, "Olaf + Grit's HQ (objective)"); m.note("foundry", 9, 14, "the old Accord foundry: Black Hole's Black Factory")
    m.note("volcano", 23, 14, "Mount Cinder"); m.note("gate", 36, 8, "pipe seam: the northern pass's gate")
    return m
