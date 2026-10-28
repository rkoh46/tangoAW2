"""BH2 M9 The Table (Act II): Yellow Comet's capital on its mesa. Father against daughter: Asuka (forced) against Kanbei, with Sensei at his side as the second CO of one Yellow Comet army. No time limit.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md sections 4 and 4b). The situation: the island's capital stands in the north behind a pipe wall that runs from coast to coast, with three seam gates
(west (6,12), middle (21,13), east (35,12)) and, behind it, a ridge of mountains and forest that falls to Kanbei's mesa: his HQ, a district of bases and cities, a harbour. Black Hole lands in the south: its HQ, a port,
two Black Cannons (Black Hole's alone: `n`, firing north in a cone of ten rows) on the field in front of the wall, a Com Tower on each flank and a missile silo in the middle of the field. The cannons' cones cover the
approach to the wall from the gates down to the guns; nobody starts in them (rule IV02). Kanbei's defence is terrain and elite units: Md Tanks, Neotanks and artillery behind the wall and the ridge.
- Lanes: three gates in the wall (a broken seam opens one), the harbour road along the north coast (a ship's way round the wall's end), the ridge's passes behind each gate.
- Where the fight happens: the field between the wall and the guns (the killing ground), then the seam gates, then the mesa.
- Scripted fight (docs/BH2_CAMPAIGN.md 4b): at half strength Kanbei calls Sensei's airlift: B Copters land on the mesa's courtyard (the `mark_air*` cells) and Infantry behind the three gates (`mark_inf*`);
  when Kanbei's last tank falls he yields (a scripted Win). The spawn cells are kept free of start units.
- Threats and answers: Kanbei's Md Tanks and Neotanks -> the Black Cannons, Rockets, artillery and Black Hole's Md Tanks; Sensei's B Copters -> Anti-Air and Tanks; the harbour's Cruiser and Submarine -> Black Hole's own.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, clear_fire_lines

W, H = 42, 30
AIR = [(17, 5), (25, 5), (21, 9), (13, 7)]       # the airlift's B Copters
INF_DROP = [(6, 10), (14, 10), (21, 10), (28, 10), (35, 10)]    # and its Infantry, behind the gates


def profile(x0, x1, lo, hi, seed):
    rnd = random.Random(f"bh2_09/{seed}")
    out, x, v = {}, x0, rnd.randint(lo, hi)
    while x <= x1:
        for _ in range(rnd.randint(3, 6)):
            if x <= x1:
                out[x] = v
                x += 1
        v = max(lo, min(hi, v + rnd.choice([-1, 1])))
    return out


def build():
    m = Canvas("bh2_09", W, H, fill="~")
    T = profile(1, 40, 2, 4, 1)
    B = profile(1, 40, 26, 27, 2)
    for x, k in ((1, 4), (2, 2), (3, 1), (38, 1), (39, 2), (40, 4)):
        T[x] += k; B[x] -= k
    for x in range(1, 41):
        m.rect(".", x, T[x], x, B[x])
    # --- the wall: a pipeline from coast to coast with three gates; the ridge behind it, the forest in front of the guns
    m.pipe([(1, 12), (12, 12), (12, 13), (28, 13), (28, 12), (40, 12)])
    m.put("Z", 6, 12).put("Z", 21, 13).put("Z", 35, 12)
    belt(m, "^", [(3, 9), (10, 8), (17, 9)], width=1, seed=1, gaps=[(6, 9), (14, 9)]); belt(m, "^", [(25, 9), (32, 8), (38, 9)], width=1, seed=2, gaps=[(28, 9), (35, 9)])
    belt(m, "^", [(9, 4), (12, 6)], width=1, seed=3); belt(m, "^", [(29, 4), (32, 6)], width=1, seed=4); belt(m, "^", [(17, 11), (25, 11)], width=1, seed=5, gaps=[(21, 11)])
    belt(m, "f", [(4, 5), (8, 6)], width=1, seed=6); belt(m, "f", [(33, 5), (37, 6)], width=1, seed=7); belt(m, "f", [(14, 5), (16, 7)], width=1, seed=8); belt(m, "f", [(26, 5), (28, 7)], width=1, seed=9)
    belt(m, "^", [(4, 16), (9, 17)], width=1, seed=10); belt(m, "^", [(33, 16), (38, 17)], width=1, seed=11); belt(m, "f", [(2, 21), (8, 22)], width=1, seed=12); belt(m, "f", [(34, 21), (39, 22)], width=1, seed=13)
    belt(m, "f", [(15, 16), (19, 17)], width=1, seed=14); belt(m, "f", [(23, 16), (27, 17)], width=1, seed=15); belt(m, "^", [(1, 14), (3, 19)], width=1, seed=16); belt(m, "^", [(38, 14), (39, 19)], width=1, seed=17)
    for i, (cx, cy, n) in enumerate([(11, 19, 3), (30, 19, 3), (21, 20, 3), (5, 24, 3), (36, 24, 3), (12, 10, 2), (30, 10, 2)]):
        m.cluster("f", cx, cy, n, seed=40 + i)
    m.header(armies=2, colours=(BH, YC), objective=[1], comment=(
        "M9 The Table: Asuka (forced, Black Hole, HQ 1 (21,24), south) against Kanbei + Sensei (one Yellow Comet army, HQ 2 (21,8), the mesa in the north). A pipe wall from coast to coast with seam gates (6,12), (21,13), (35,12). "
        "Black Hole's Black Cannons (n) at (14,23) and (28,23) fire north across the field to the wall. Com Towers (8,17) and (34,17), missile silo (21,17); harbours (11,26) and (21,6). "
        "Scripted: at half strength the airlift (B Copters at the mark_air cells, Infantry at the mark_inf cells); the last Yellow Comet tank falling is Kanbei's surrender. "
        "Player: INF3 MECH3 TANK4 MDT2 ART3 ROCK2 RECON1 AA2 CR2 SUB1 LAN2; Kanbei: INF3 MECH4 TANK3 MDT5 NEO3 ART4 ROCK3 RECON1 CR1 SUB1."))
    m.rect("~", 18, 2, 24, 5)                                      # the harbour bay
    m.put("1", 21, 24).put("2", 21, 8).put("t", 8, 17).put("t", 34, 17).put("M", 21, 17)
    m.put("P", 11, B[11]).put("P", 21, 6)
    m.stamp("n", 14, 23).stamp("n", 28, 23)
    L = lambda x, y: (x, max(T[x] + 1, min(B[x] - 1, y)))
    # --- roads that follow the land: the three approaches to the gates, the guns' road, the harbour roads, the mesa's streets
    route(m, [(21, 23), (21, 18), (21, 14)], seed=1); route(m, [(20, 24), (15, 20), (9, 16), (6, 14), (6, 13)], seed=2); route(m, [(22, 24), (27, 20), (33, 16), (35, 14), (35, 13)], seed=3)
    route(m, [(21, 12), (21, 9)], seed=4); route(m, [(6, 11), (6, 10)], seed=16); route(m, [(35, 11), (35, 10)], seed=17); route(m, [(6, 11), (8, 8), (13, 7), (19, 8)], seed=5); route(m, [(35, 11), (33, 8), (28, 7), (23, 8)], seed=6)
    route(m, [(21, 7), (21, 6)], seed=7); route(m, [(20, 24), (15, 25), (11, 25)], seed=8); route(m, [(15, 22), (15, 25)], seed=9); route(m, [(28, 22), (24, 24)], seed=10)
    route(m, [(9, 16), (8, 17)], seed=11); route(m, [(33, 16), (34, 17)], seed=12); route(m, [(21, 17), (21, 18)], seed=13)
    route(m, [(21, 6), (17, 6), (13, 5), (8, 5)], seed=14); route(m, [(21, 6), (25, 6), (29, 5), (34, 5)], seed=15)
    route(m, [(9, 16), (6, 20), (4, 23)], seed=18); route(m, [(33, 16), (36, 21), (37, 24)], seed=19); route(m, [(15, 22), (10, 21), (8, 19)], seed=20); route(m, [(27, 21), (31, 21), (34, 19)], seed=21)
    thin_roads(m)
    # --- towns: Black Hole's district and harbour, the flanks' Com Tower towns, Kanbei's mesa (bases and cities), the gate towns and the north harbour
    town(m, 21, 24, "BBC", seed=1); town(m, 17, 22, "BC", seed=2); town(m, 25, 22, "BC", seed=3); town(m, 12, 25, "C", seed=4); town(m, 8, 19, "C", seed=5); town(m, 34, 19, "C", seed=6)
    town(m, 6, 14, "Cb", seed=7); town(m, 35, 14, "Cb", seed=8); town(m, 21, 15, "cc", seed=9); town(m, 4, 23, "cc", seed=10); town(m, 37, 24, "cc", seed=11); town(m, 6, 20, "c", seed=22); town(m, 36, 21, "c", seed=23); town(m, 11, 21, "C", seed=24); town(m, 31, 21, "C", seed=25)
    town(m, 21, 8, "BBBC", seed=12, radius=3); town(m, 17, 7, "BC", seed=13); town(m, 25, 7, "BC", seed=14); town(m, 13, 7, "CC", seed=15); town(m, 29, 7, "CC", seed=16)
    town(m, 21, 6, "CC", seed=17); town(m, 8, 5, "C", seed=18); town(m, 34, 5, "C", seed=19); town(m, 6, 9, "C", seed=20); town(m, 35, 9, "C", seed=21)
    town(m, 10, 7, "C", seed=26); town(m, 31, 6, "C", seed=27); town(m, 14, 18, "c", seed=28); town(m, 28, 18, "c", seed=29); town(m, 21, 21, "C", seed=30); town(m, 17, 4, "C", seed=31)
    neutralize(m, 13, keep=[])
    m.tidy()
    shore(m, 1, (1, 1, 40, 28), dirs="NS")
    m.g[B[11] + 1][11] = "~"; m.g[5][21] = "~"
    m.tidy()
    # --- units: Black Hole in the south, Kanbei's elite behind the wall and on the mesa
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.reserve(AIR + INF_DROP)
    m.spread(1, {INF: 3, MECH: 3, TANK: 4, MDT: 2, ART: 3, ROCK: 2, RECON: 1, AA: 2}, (2, 18, 39, 26), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 3, MECH: 4, TANK: 3, MDT: 5, NEO: 3, ART: 4, ROCK: 3, RECON: 1}, (3, 4, 38, 11), seed=2, gap=0, avoid=av)
    for (x, y), k in zip(m.sea_near(11, B[11] + 2, 5, box=(4, B[11] + 1, 20, 28), deep=False), [CR, CR, SUB, LAN, LAN]):
        m.unit(1, k, x, y)
    for (x, y), k in zip(m.sea_near(21, 4, 2, box=(18, 2, 24, 5), deep=False), [CR, SUB]):
        m.unit(2, k, x, y)
    clear_fire_lines(m)
    for i, (x, y) in enumerate(AIR):
        m.note(f"mark_air{i + 1}", x, y, "airlift: a B Copter lands here")
    for i, (x, y) in enumerate(INF_DROP):
        m.note(f"mark_inf{i + 1}", x, y, "airlift: Infantry lands here")
    m.note("hq", 21, 24, "Asuka's HQ"); m.note("enemy_hq", 21, 8, "Kanbei's HQ (objective)")
    return m
