"""BH2 M21 The East Tower (Act IV): the castle town on its sea bluff, in the rain. A free pick against one Orange Star army under Andy + Rachel; no scripted escape, a castle assault.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: the castle stands on the north coast: a U of pipe wall (west wall x14, south wall y14, east wall x28) whose arms end in the sea, with three seam gates (west (14,9), south (21,14), east (28,9)),
the keep and the East Tower (a Com Tower) inside, the castle's harbour in a bay of the north coast and the castle town's bases and cities. Black Hole lands in the south-west: its HQ, a base district and a port on the south coast.
Andy and Rachel hold the castle with strong defenders. The castle's one open flank is the sea: only Landers carry an army round to the harbour beach, so a Lander flank is part of the plan (Black Hole's fleet starts with two).
A river rises from a pond in the east hills, bends to the south coast and carries two bridges for the east highway.
- Lanes: the south gate road, the west gate road, the east highway across the river, the sea flank to the harbour beach.
- Where the fight happens: the three gates (broken seams open the wall) and the town's streets, then the keep.
- Properties: Black Hole's district and port, the farm villages along the roads, the castle town (bases, cities), the harbour's ports, the East Tower.
- Threats and answers: Andy's Tanks and Rachel's artillery on the wall -> Black Hole's Md Tanks, Rockets and its own artillery; the harbour's Cruisers and Submarine -> Black Hole's own. Orange Star fields no air.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 42, 30


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_16/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-1, 1])))
    return out


def build():
    m = Canvas("bh2_21", W, H, fill="~")
    rnd = random.Random("bh2_16/coast")
    T = {}
    for x in range(W):
        base = 8 if x <= 10 else 6 if x <= 13 else 3 if x <= 28 else 6 if x <= 31 else 9
        T[x] = base + (rnd.choice([0, 0, 1]) if (x <= 10 or x >= 32) else 0)
    for x in (4, 5, 6, 7):
        T[x] = T[5]
    for x in (35, 36, 37):
        T[x] = T[36]
    for x in range(W):                                               # land edge to edge: the coast is the north edge only, with the castle's headland in it
        m.rect(".", x, T[x], x, H - 1)
    for x in range(18, 25):                                           # the castle's harbour: a bay in the north coast
        for y in range(T[x], T[x] + 3):
            m.g[y][x] = "~"
    ponds = m.lake(36, 13, 9, seed=1, river_end=(36, 14))
    m.river([(36, 14), (36, 19), (34, 19), (34, 24), (35, 24), (35, H - 1)])
    C = lambda x, y: (x, max(T[x] + 4, min(H - 2, y)))
    # --- the castle wall, a U open to the north sea: it ends at the water on both arms
    m.pipe([(14, T[14]), (14, 14), (28, 14), (28, T[28])]); m.put("Z", 14, 9).put("Z", 21, 14).put("Z", 28, 9)
    belt(m, "^", [(8, 12), (12, 15)], width=1, seed=1); belt(m, "^", [(30, 12), (33, 8)], width=1, seed=2); belt(m, "^", [(6, 6), (11, 7)], width=1, seed=3); belt(m, "^", [(30, 18), (32, 22)], width=1, seed=4, gaps=[(31, 20)])
    belt(m, "^", [(4, 18), (7, 20)], width=1, seed=5); belt(m, "^", [(14, 24), (19, 26)], width=1, seed=6); belt(m, "^", [(25, 22), (29, 24)], width=1, seed=7, gaps=[(27, 23)])
    belt(m, "f", [(16, 6), (19, 8)], width=1, seed=8); belt(m, "f", [(24, 6), (26, 8)], width=1, seed=9); belt(m, "f", [(17, 18), (23, 19)], width=2, seed=10); belt(m, "f", [(4, 22), (8, 24)], width=1, seed=11)
    belt(m, "f", [(10, 17), (13, 19)], width=1, seed=12); belt(m, "f", [(37, 18), (40, 22)], width=1, seed=13); belt(m, "f", [(30, 14), (33, 15)], width=1, seed=14); belt(m, "f", [(3, 10), (6, 11)], width=1, seed=15)
    belt(m, "^", [(16, 23), (21, 22), (27, 24)], width=1, seed=31, gaps=[(19, 22), (24, 23)]); belt(m, "f", [(20, 26), (26, 27)], width=2, seed=32); belt(m, "^", [(12, 27), (16, 28)], width=1, seed=33); belt(m, "f", [(28, 18), (31, 21)], width=2, seed=34)
    belt(m, "f", [(8, 25), (12, 24)], width=1, seed=35); belt(m, "^", [(34, 8), (38, 9)], width=1, seed=36)
    m.header(armies=2, colours=(BH, OS), objective=[1], comment=(
        "M21 The East Tower (normal look, rain): a free pick (Black Hole, HQ 1 (8,22), the south-west) against one Orange Star army under Andy + Rachel (HQ 2 (21,9), the keep). The castle: a pipe wall (west x14, south y14, east x28, ending in the sea) with seam gates (14,9), (21,14), (28,9); "
        "the East Tower, a Com Tower, at (21,6); the harbour bay in the north coast. A river from the pond (36,13) to the south edge, bridges (36,16), (34,21) and (35,26). A second Com Tower (10,18), missile silo (25,19). "
        "Player: INF4 MECH2 TANK4 MDT2 ART3 ROCK1 RECON1 APC1 CR1 SUB1 LAN2; Orange Star: INF4 MECH2 TANK5 MDT3 ART4 ROCK3 RECON1 CR2 SUB1."))
    m.put("1", 8, 22).put("2", 21, 9).put("t", 21, 6).put("t", 10, 18).put("M", 25, 19)
    PB, PC = 6, 39
    m.put("P", PB, T[PB]).put("p", PC, T[PC]).put("P", 19, T[19] + 3).put("P", 23, T[23] + 3)
    route(m, [(8, 23), C(12, 21), C(17, 18), C(21, 17), (21, 15)], seed=1, wander=1.2); route(m, [(8, 21), C(9, 15), C(11, 11), (13, 9)], seed=2, wander=1.2)
    route(m, [(15, 9), C(16, 8), (19, 8), (21, 8)], seed=3); route(m, [(21, 13), (21, 10)], seed=4); route(m, [(29, 9), C(31, 11), C(32, 15), C(32, 19)], seed=5); route(m, [(27, 9), (23, 8), (21, 8)], seed=6)
    route(m, [C(21, 17), C(27, 20), (32, 20), (34, 21, "="), (36, 21), C(39, 18), C(40, 14)], seed=7, wander=1.2); route(m, [C(40, 14), (38, 16), (36, 16, "="), (34, 16), C(31, 14)], seed=8)
    route(m, [(PB, T[PB] + 1), C(PB, 14), C(8, 18), (8, 21)], seed=9); route(m, [(PC, T[PC] + 1), C(PC, 12), C(39, 15), C(39, 17)], seed=10); route(m, [(19, T[19] + 4), (19, 8)], seed=11); route(m, [(23, T[23] + 4), (23, 8)], seed=12); route(m, [C(30, 26), (33, 26), (35, 26, "="), (37, 26), C(38, 28)], seed=15)
    route(m, [(10, 18), C(11, 21)], seed=13); route(m, [C(9, 15), C(6, 9), C(5, 6)], seed=16); route(m, [C(27, 18), (25, 18)], seed=14)
    route(m, [C(21, 17), C(22, 21), C(24, 25), C(25, 28)], seed=40)
    thin_roads(m)
    for args in [(8, 22, "BBC"), (11, 21, "BC"), (5, 21, "C"), (9, 15, "C"), (12, 9, "C"), (17, 18, "Cc"), (21, 17, "bc"), (27, 18, "bc"), (21, 9, "BBBC"), (17, 8, "BC"), (25, 8, "BC"), (21, 11, "CC"), (16, 11, "C"), (26, 11, "C"),
                 (31, 11, "bc"), (33, 15, "c"), (32, 17, "c"), (38, 17, "c"), (39, 13, "cc"), (36, 21, "c"), (22, 23, "c"), (14, 22, "c"), (5, 15, "c"), (6, 9, "c"), (36, 6, "c"), (38, 28, "cc"), (30, 6, "c"), (12, 6, "c"), (4, 12, "c"), (5, 6, "cc"), (25, 28, "cc"), (3, 27, "cc"), (2, 20, "cc"), (21, 24, "c"), (37, 5, "cc")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    for (x, y) in ((36, 5),):
        if m.g[y][x] in ".f":
            m.g[y][x] = "c"
    neutralize(m, 14)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for (x, y) in ponds:
        m.g[y][x] = "~"
    for (x, y) in [(PB, T[PB] - 1), (PC, T[PC] - 1), (19, T[19] + 2), (23, T[23] + 2), (19, T[19] + 1), (23, T[23] + 1), (14, T[14] - 1), (28, T[28] - 1)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    for (x, y) in [(20, 1), (23, 1), (4, 1), (35, 3), (9, 1)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2)):
            m.put("r", x, y)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 4, MECH: 2, TANK: 4, MDT: 2, ART: 3, ROCK: 1, RECON: 1, APC: 1}, (2, 17, 16, 28), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 5, MDT: 3, ART: 4, ROCK: 3, RECON: 1}, (15, 4, 27, 13), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([LAN, LAN, CR, SUB], m.sea_near(PB, 1, 4, box=(2, 0, 20, 5), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([CR, CR, SUB], m.sea_near(21, 2, 3, box=(16, 0, 26, 6), deep=True)):
        m.unit(2, k_, x, y)
    m.note("hq", 8, 22, "Black Hole's HQ"); m.note("enemy_hq", 21, 9, "Andy + Rachel's HQ (objective)"); m.note("tower", 21, 6, "the East Tower (Com Tower)")
    for n_, (x, y) in (("gate_w", (14, 9)), ("gate_s", (21, 14)), ("gate_e", (28, 9))):
        m.note(n_, x, y, "seam gate of the castle wall")
    return m
