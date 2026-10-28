"""BH2 M17 Echo, Again (Act IV): the Lab 7 ruins (Wasteland look, fog). Clone Andy (forced) against Andy: the mirror match.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Lab 7's ruins lie on either side of a lava-mouthed river that runs from the north lava to the south lava. The map is drawn as a near mirror: the west half (Clone Andy's) is drawn first and copied
to the east (Andy's), so the two districts, the roads to the river and the Com Towers sit alike; then the halves are made different on purpose, because a clone is never exact:
- the clone's half is a ruin: a collapsed lab wall (a pipe wall with a seam gate and a heap of cliffs), fewer roads, wild ash woods, a broken coast; its army is heavier on Md Tanks and artillery;
- Andy's half is kept: a tidy ring road, a second road district on the east coast, a bay of lava in the south-east instead of the south-west; his army is heavier on Tanks.
Three bridges (rows 7, 14, 21) carry the roads across the river, which wanders between them.
- Lanes: the three bridges and the roads that meet at them, the lab wall's gate on the west side, the ash woods on the east.
- Where the fight happens: the bridges and the two Com Towers (16,9) and (25,9) beside the river.
- Threats and answers: both armies are ground armies: Md Tanks and Neotank-free Tanks against artillery and Rockets; fog hides the second line. No air, no Anti-Air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 42, 30
XM = 20                                         # the river's column (bridges at rows 7, 14, 21); the halves meet here


def build():
    m = Canvas("bh2_17", W, H)
    rnd = random.Random("bh2_17/coast")
    T, B, t, b = {}, {}, 3, 26
    for x in range(0, XM + 1):
        if x % 4 == 0:
            t = max(2, min(5, t + rnd.choice([-1, 0, 1]))); b = max(24, min(27, b + rnd.choice([-1, 0, 1])))
        T[x], B[x] = t, b
    for x in (XM - 1, XM, XM + 1):
        T[x] = T[XM]; B[x] = B[XM]
    for x in range(0, XM + 1):
        for y in range(0, T[x]):
            m.g[y][x] = "~"
        for y in range(B[x] + 1, H):
            m.g[y][x] = "~"
    for (cx, cy, rx, ry) in ((2, 3, 4, 3), (3, 27, 4, 3)):                 # lava bays at the west corners
        m.blob("~", cx, cy, rx, ry, seed=cx, wobble=0.3)
    C = lambda x, y: (x, max(T[min(x, XM)] + 2, min(B[min(x, XM)] - 2, y)))
    # --- the west half (the clone's): ridges, ash woods, roads to the three bridges, the district, the Com Tower
    belt(m, "^", [(8, 5), (13, 6), (17, 5)], width=1, seed=1, gaps=[(11, 5), (15, 6)]); belt(m, "^", [(8, 24), (13, 23), (17, 24)], width=1, seed=2, gaps=[(11, 24), (15, 23)])
    belt(m, "^", [(3, 9), (6, 8)], width=1, seed=3); belt(m, "^", [(3, 20), (6, 21)], width=1, seed=4); belt(m, "^", [(12, 11), (14, 12)], width=1, seed=5); belt(m, "^", [(12, 17), (14, 18)], width=1, seed=6)
    belt(m, "f", [(4, 11), (8, 12)], width=1, seed=7); belt(m, "f", [(4, 18), (8, 17)], width=1, seed=8); belt(m, "f", [(15, 9), (18, 11)], width=1, seed=9); belt(m, "f", [(15, 19), (18, 17)], width=1, seed=10)
    belt(m, "f", [(9, 8), (12, 9)], width=1, seed=11); belt(m, "f", [(9, 21), (12, 20)], width=1, seed=12)
    m.put("1", 6, 15).put("t", 17, 9).put("M", 17, 20)
    route(m, [(6, 14), C(9, 11), C(13, 8), (17, 7), (20, 7)], seed=1, wander=1.2)
    route(m, [(7, 15), C(11, 15), (15, 14), (20, 14)], seed=2, wander=1.2)
    route(m, [(6, 16), C(9, 19), C(13, 22), (17, 21), (20, 21)], seed=3, wander=1.2)
    route(m, [(17, 8), (17, 7)], seed=4); route(m, [(15, 14), (15, 17), (17, 19)], seed=5)
    route(m, [C(9, 19), C(5, 22)], seed=8); route(m, [C(9, 11), C(6, 8)], seed=9)
    thin_roads(m)
    for args in [(4, 22, "cc"), (5, 7, "cc"), (6, 15, "BBC"), (9, 11, "BC"), (9, 19, "BC"), (12, 15, "CC"), (13, 8, "C"), (13, 22, "C"), (17, 7, "Cb"), (17, 21, "Cb"), (15, 14, "Cb"), (3, 14, "C"), (11, 3, "c"), (11, 26, "c"), (17, 12, "c"), (17, 17, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    m.tidy()
    m.g[14][7] = "."                                            # (the road leaves the HQ east and north apart: no three-way knot beside the bases)
    # --- the mirror: the east half is a copy of the west
    m.mirror_x(21)
    for yy in range(H):
        if m.g[yy][41] in "BCcb":
            m.g[yy][41] = "."
    # --- the river between the halves: from the north lava to the south lava, three bridges, wandering
    rv = [(XM, T[XM]), (XM, 9), (XM - 1, 9), (XM - 1, 11), (XM, 11), (XM, 16), (XM + 1, 16), (XM + 1, 18), (XM, 18), (XM, B[XM])]
    for (cx, cy) in m.path(rv):
        m.g[cy][cx] = "."                                                  # (a building the mirror left on the river's way goes)
    m.river(rv)
    for y in (7, 14, 21):
        m.g[y][XM] = "="
    for x in (XM, XM + 1):                                                  # (the mirrored roads meet the bridges in line)
        for y in (7, 14, 21):
            if m.g[y][x] != "=":
                m.g[y][x] = "R"
    m.g[7][XM - 1] = m.g[7][XM - 2] = m.g[14][XM - 1] = m.g[14][XM - 2] = m.g[21][XM - 1] = m.g[21][XM - 2] = "R"
    # --- the east half becomes Andy's: HQ, his tidy ring road, an east-coast district, a bay of lava in the south-east
    for y in range(H):
        for x in range(W):
            if m.g[y][x] == "1" and x > XM:
                m.g[y][x] = "2"
    m.put("1", 6, 15); m.put("2", 35, 15)
    m.put("t", 24, 9) if m.g[9][24] in ".f" else None
    for (cx, cy, rx, ry) in ((38, 27, 4, 3),):
        m.blob("~", cx, cy, rx, ry, seed=7, wobble=0.3)
    # --- the clone's half is a ruin: a collapsed lab wall (pipe wall with a seam gate ending in cliffs) and rubble
    for (x, y) in [(10, 10), (10, 11), (9, 10)]:
        m.put("^", x, y)
    m.pipe([(10, 12), (10, 18)]); m.put("Z", 10, 15); m.put("^", 10, 19).put("^", 9, 19).put("^", 11, 19)
    for i, (cx, cy, n, ch) in enumerate([(30, 8, 4, "f"), (32, 21, 4, "f"), (27, 12, 3, "f"), (27, 18, 3, "f"), (37, 11, 4, "f"), (38, 19, 3, "f"), (24, 4, 3, "^"), (28, 25, 3, "^"), (12, 14, 3, "^"), (4, 17, 3, "^"), (3, 11, 3, "^")]):
        m.cluster(ch, cx, cy, n, seed=80 + i)
    m.cluster("^", 7, 12, 4, seed=71); m.cluster("^", 8, 18, 4, seed=72); m.cluster("^", 14, 6, 3, seed=73)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M17 Echo, Again (Wasteland look, fog, lava for water): Clone Andy (forced, Black Hole, HQ 1 (6,15), the ruined west) against Andy (Orange Star, HQ 2 (35,15), the tidy east). A river (x 19..21) from the north lava to the south lava with bridges (20,7), (20,14), (20,21). "
        "Com Towers (17,9) and (24,9), missile silo (17,20); the west's collapsed lab wall x10 (y12..18) with the seam gate (10,15). Player: INF4 MECH3 TANK5 MDT3 ART3 ROCK2 RECON1; Andy: INF5 MECH2 TANK6 MDT2 ART3 ROCK2 RECON1."))
    for y in range(H):                                                       # (nothing of the mirror may leave a second HQ)
        pass
    for args in [(40, 9, "c"), (40, 20, "c"), (30, 3, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 3, TANK: 5, MDT: 3, ART: 3, ROCK: 2, RECON: 1}, (2, 6, 17, 24), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 2, TANK: 6, MDT: 2, ART: 3, ROCK: 2, RECON: 1}, (24, 6, 39, 24), seed=2, gap=0, avoid=av)
    m.note("hq", 6, 15, "Clone Andy's HQ"); m.note("enemy_hq", 35, 15, "Andy's HQ (objective)"); m.note("gate", 10, 15, "seam gate in the collapsed lab wall")
    return m
