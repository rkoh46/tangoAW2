"""BH2 M22 Von Bolt's Note (Act V): the Orange Star sea fortress, in the rain. Von Bolt (forced) with a free tag partner against one Orange Star army under Jess + Colin. Normal look, rain.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: an archipelago: Black Hole's land hangs from the top edge (a long northern coast with two bays), a five-row strait, and the sea fortress: a big island in the south with two small islets beside it. Two long sea bridges carry the roads from the northern coast
to the fortress island; nothing else joins them.
The situation: Black Hole's army holds the north: its HQ, a base district, a port in each bay, the old foundry (the player's Black Factory, with its supply pipe) and, on the north coast at the very top of the map, the Deathray (Black Hole's alone: it fires down three columns, 13..15, along the west bridge into the fortress wall's seam gate (14,17) and on to the bottom edge; nobody stands in them at the start). Jess and Colin hold the fortress island: a pipe wall along its north shore with two seam gates behind the bridgeheads, bunkers (cities) behind it, a Com Tower and a missile silo inside, the HQ at the south, three ports on the south coast and a fleet.
- Lanes: the two bridges (14,10..16) and (26,10..16) and the gates behind them, the strait for the fleets, the islets' beaches, the fortress's south coast.
- Where the fight happens: the strait and the bridgeheads, then the wall's gates; the Deathray's columns cover the fortress's east side.
- Properties: the foundry's bases and cities in the north, two bays' ports, the fortress's bunkers; the islets' villages.
- Threats and answers: the fortress's Battleship, Cruisers and artillery -> Black Hole's own fleet, the Deathray and the factory's Md Tanks and artillery; its Fighters and Copters -> the factory's Anti-Air (only when air shows) and Black Hole's own.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs, clear_fire_lines

W, H = 40, 30


def build():
    m = Canvas("bh2_22", W, H, fill="~")
    rnd = random.Random("bh2_22/coast")
    # --- the northern land: off the top edge, ragged south coast with two bays
    b = 9
    for x in range(W):
        if x % 3 == 0:
            b = max(7, min(10, b + rnd.choice([-1, 0, 1])))
        m.rect(".", x, 0, x, b)
    for x in range(8, 13):
        m.rect("~", x, 6, x, 10)                          # the west bay
    for x in range(27, 33):
        m.rect("~", x, 6, x, 10)                          # the east bay
    m.rect(".", 12, 0, 16, 10); m.rect(".", 23, 0, 28, 10)           # the two bridgeheads are headlands
    # --- the fortress island and two islets
    land_rows(m, {16: (11, 29), 17: (10, 30), 18: (10, 30), 19: (9, 31), 20: (9, 31), 21: (10, 30), 22: (10, 31), 23: (11, 30), 24: (11, 29), 25: (12, 28), 26: (14, 26)})
    land_rows(m, {18: (2, 5), 19: (1, 5), 20: (2, 5)}); land_rows(m, {19: (35, 37), 20: (34, 38), 21: (34, 38), 22: (35, 37)})
    m.put('~', 7, 8).put('~', 7, 9)                      # the foundry's one water door: an inlet of the west bay
    m.rect(".", 0, 17, 0, 17) if False else None
    S = lambda x, y: snap(m, x, y)
    # --- the bridges: from the north coast over the strait (rows 11..15) to the fortress's shore (row 16)
    for bx in (14, 26):
        m.rect(".", bx - 1, 10, bx + 1, 10)               # the bridgehead
        m.bridge(bx, 11, bx, 15)
    # --- the fortress's wall along its north shore with two gates behind the bridgeheads; ends at the sea
    m.pipe([(10, 17), (30, 17)]); m.put("Z", 14, 17).put("Z", 26, 17)
    m.put("^", 10, 17).put("^", 30, 17) if False else None
    belt(m, "^", [(1, 2), (4, 2)], width=1, seed=1); belt(m, "^", [(14, 3), (22, 2)], width=1, seed=2, gaps=[(18, 3)]); belt(m, "^", [(34, 3), (38, 5)], width=1, seed=3)
    belt(m, "f", [(1, 6), (2, 9)], width=1, seed=4); belt(m, "f", [(16, 5), (22, 7)], width=1, seed=5); belt(m, "f", [(33, 7), (37, 8)], width=1, seed=6); belt(m, "f", [(14, 5), (16, 7)], width=1, seed=7)
    belt(m, "^", [(13, 19), (17, 20)], width=1, seed=8); belt(m, "^", [(24, 19), (28, 21)], width=1, seed=9, gaps=[(26, 20)]); belt(m, "f", [(12, 22), (16, 24)], width=1, seed=10); belt(m, "f", [(24, 23), (28, 24)], width=1, seed=11)
    belt(m, "f", [(2, 19), (4, 19)], width=1, seed=12); belt(m, "f", [(34, 20), (37, 21)], width=1, seed=13)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M22 Von Bolt's Note (normal look, rain): Von Bolt (forced) + a free tag partner (Black Hole, HQ 1 (10,4), the north land) against one Orange Star army under Jess + Colin (HQ 2 (20,23), the sea fortress). "
        "Black Hole's Black Factory (the foundry) at (6,6) with its supply pipe, one water door (7,8) on the west bay; the Deathray D at (14,1): it fires down columns 13..15 along the west bridge to the fortress wall's seam (14,17) and on to the bottom edge (nobody starts in them). Two sea bridges (14,11..15) and (26,11..15); the fortress's wall y17 with seam gates (14,17) and (26,17). "
        "Com Tower (20,19), missile silo (24,19). Player: INF4 MECH2 TANK3 MDT1 ART2 ROCK1 RECON1 AA1 APC1 BS1 CR2 SUB1 LAN2; Orange Star: INF6 MECH3 TANK4 MDT2 ART4 ROCK2 RECON1 AA1 FTR2 BCO2 BS2 CR2 SUB1."))
    m.put("1", 10, 4).put("2", 20, 23).put("t", 20, 19).put("M", 24, 19)
    m.stamp("F", 6, 6).put("I", 6, 3)                    # the foundry, with its supply pipe
    m.stamp("D", 14, 1)                                  # the Deathray, at the top edge on Black Hole's side
    PORTS = [snap_coast(m, 10, 9), snap_coast(m, 29, 9), snap_coast(m, 16, 26), snap_coast(m, 24, 26), snap_coast(m, 20, 26)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    route(m, [S(10, 5), S(12, 4), S(16, 6), S(20, 8), S(26, 9), (26, 10)], seed=31, wander=0.7); route(m, [S(10, 5), S(12, 8), S(14, 9), (14, 10)], seed=2)
    route(m, [S(5, 8), S(6, 8), S(9, 5)], seed=3); route(m, [S(27, 9), S(32, 5), S(36, 6)], seed=4); route(m, [S(10, 5), S(8, 3), S(4, 8), S(2, 5)], seed=5)
    route(m, [(14, 16), (14, 18), S(14, 20), S(18, 21), S(20, 22)], seed=6) if False else route(m, [(14, 18), S(14, 19), S(18, 21), S(20, 22)], seed=6)
    route(m, [(26, 18), S(26, 19), S(23, 21), S(21, 22)], seed=7); route(m, [(14, 15), (14, 16)], seed=17); route(m, [(26, 15), (26, 16)], seed=18); route(m, [S(20, 20), (20, 19)], seed=8) if False else route(m, [S(18, 21), S(20, 20)], seed=8); route(m, [S(24, 21), S(24, 19)], seed=9)
    for p in PORTS[:2]:
        pass
    route(m, [S(PORTS[2][0], PORTS[2][1] - 1), S(18, 22)], seed=10); route(m, [S(PORTS[3][0], PORTS[3][1] - 1), S(22, 22)], seed=11); route(m, [S(PORTS[4][0], PORTS[4][1] - 1), S(20, 23)], seed=12)
    route(m, [S(PORTS[0][0], PORTS[0][1] - 1), S(11, 5)], seed=13); route(m, [S(PORTS[1][0], PORTS[1][1] - 1), S(27, 6)], seed=34)
    route(m, [S(3, 19), S(5, 19)], seed=15); route(m, [S(35, 21), S(37, 21)], seed=16)
    thin_roads(m); fix_rungs(m)
    for args in [(10, 4, "BBC"), (13, 7, "BC"), (4, 10, "BC"), (2, 5, "C"), (16, 6, "C"), (20, 8, "Cb"), (23, 5, "C"), (26, 8, "Cb"), (30, 5, "BC"), (34, 4, "C"), (36, 7, "c"), (2, 4, "c"), (14, 9, "C"),
                 (20, 23, "BBBC"), (16, 21, "BC"), (24, 22, "BC"), (14, 19, "CC"), (26, 19, "CC"), (12, 18, "C"), (28, 18, "C"), (18, 21, "C"), (22, 21, "C"), (13, 22, "c"), (27, 22, "c"), (3, 19, "cc"), (36, 21, "cc"), (20, 17, "c"), (11, 25, "c"), (29, 24, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 15)
    m.tidy()
    shore(m, 1, (0, 1, W - 1, H - 2), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    for (x, y) in [(5, 14), (20, 13), (34, 14), (8, 14), (21, 28), (4, 25), (36, 26), (31, 13), (3, 12), (20, 14)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.reserve([(x, y) for x in (13, 14, 15) for y in range(0, H)])                  # (the Deathray's columns: nobody starts there)
    m.spread(1, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1, AA: 1, APC: 1}, (1, 1, 22, 9), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 6, MECH: 3, TANK: 4, MDT: 2, ART: 4, ROCK: 2, RECON: 1, AA: 1}, (10, 17, 28, 25), seed=2, gap=0, avoid=av)
    m.spread(2, {FTR: 2, BCO: 2}, (11, 18, 28, 25), seed=3, gap=1, avoid=av)
    for k_, (x, y) in zip([BS, CR, CR, SUB, LAN, LAN], m.sea_near(20, 12, 6, box=(8, 11, 32, 15), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([BS, BS, CR, CR, SUB], m.sea_near(20, 28, 5, box=(8, 27, 32, 29), deep=False)):
        m.unit(2, k_, x, y)
    clear_fire_lines(m)
    m.note("hq", 10, 4, "Von Bolt's HQ"); m.note("enemy_hq", 20, 23, "Jess + Colin's HQ (objective)"); m.note("foundry", 6, 6, "the old foundry: Black Hole's Black Factory"); m.note("deathray", 14, 1, "the Deathray (Black Hole's), at the top edge")
    m.note("gate_w", 14, 17, "seam gate in the fortress wall"); m.note("gate_e", 26, 17, "seam gate in the fortress wall")
    return m
