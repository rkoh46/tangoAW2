"""BH2 M11 Black Lanterns (Act II): Yellow Comet's bay coast in the rain. A free CO pick against Grimm; Black Hole's Black Crystals heal its army, and Grimm's army is built to break them.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: a great bay bites into the coast from the north. Black Hole holds the south-west shore, a bastion round its HQ: three Black Crystals (Black
Hole's alone; they heal the units that stand by them) and a port on the bay's southern beach. Grimm holds the north-eastern cape across the water: his HQ on a plateau of ridges, an airport with Fighters and Bombers
and a port on the cape's bay shore, and the biggest army of the act (Tanks, Md Tanks, Rockets, Artillery) that is meant to break the healing line. A river rises at the south edge, bends three times and reaches the bay at the
middle of its southern beach; it splits the land into Black Hole's west and Grimm's east, with three bridges. The lantern islet (a neutral port and a village) lies in the bay's mouth.
- Lanes: the three bridges (south, middle, north), the bay's long southern beach for landings, the sea of the bay for the fleets, the plateau's passes on the cape.
- Where the fight happens: the middle bridge and the Com Tower beside it, then the crystals' bastion: Grimm has to cross the river and break the healing line.
- Properties: Black Hole's bases and port, a Com Tower and a missile silo in the neutral middle, Grimm's bases, airport and port.
- Threats and answers: Grimm's Bombers and Fighters -> Anti-Air and the Crystals' healing line; his Tanks and Md Tanks -> Md Tanks, Rockets and artillery behind the river; the fleets -> Cruisers, Submarines and artillery on the beach.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 40, 30


def build():
    m = Canvas("bh2_11", W, H, fill="~")
    # --- the land: everything south of the bay, the west headland, the north-eastern cape; the bay's mouth opens to the north-west
    land_rows(m, {y: (xw, 39) for y, xw in {13: 3, 14: 2, 15: 1, 16: 1, 17: 2, 18: 2, 19: 1, 20: 1, 21: 2, 22: 3, 23: 2, 24: 2, 25: 1, 26: 1, 27: 2, 28: 2, 29: 1}.items()})
    land_rows(m, {3: (31, 36), 4: (29, 38), 5: (27, 39), 6: (26, 39), 7: (25, 39), 8: (25, 39), 9: (26, 39), 10: (25, 39), 11: (24, 39), 12: (25, 39)})        # the north-eastern cape and its bay shore
    land_rows(m, {6: (1, 4), 7: (1, 5), 8: (1, 6), 9: (2, 6), 10: (2, 7), 11: (3, 8), 12: (3, 9)})                                                          # the west headland
    land_rows(m, {7: (15, 17), 8: (14, 18), 9: (15, 17)})                                                                                                    # the lantern islet
    m.river([(22, 29), (22, 24), (24, 24), (24, 18), (22, 18), (22, 13)])
    # --- relief: Grimm's plateau of ridges with passes, the ridge that shelters Black Hole's bastion, forest belts
    belt(m, "^", [(28, 5), (34, 6), (38, 9)], width=1, seed=1, gaps=[(32, 6)]); belt(m, "^", [(29, 11), (35, 12)], width=1, seed=2, gaps=[(32, 11)]); belt(m, "^", [(28, 16), (31, 20)], width=1, seed=3)
    belt(m, "^", [(33, 17), (37, 20)], width=1, seed=4, gaps=[(35, 18)]); belt(m, "^", [(4, 16), (8, 15)], width=1, seed=5); belt(m, "^", [(12, 24), (16, 27)], width=1, seed=6, gaps=[(14, 25)])
    belt(m, "^", [(33, 24), (38, 26)], width=1, seed=7); belt(m, "^", [(17, 15), (19, 20)], width=1, seed=8, gaps=[(18, 17)])
    belt(m, "f", [(4, 18), (9, 20)], width=1, seed=9); belt(m, "f", [(9, 14), (13, 15)], width=1, seed=10); belt(m, "f", [(26, 14), (30, 14)], width=1, seed=11)
    belt(m, "f", [(27, 21), (31, 24)], width=1, seed=12); belt(m, "f", [(3, 24), (7, 27)], width=1, seed=13); belt(m, "f", [(17, 21), (20, 23)], width=1, seed=14)
    belt(m, "f", [(35, 14), (38, 16)], width=1, seed=15); belt(m, "f", [(28, 8), (31, 9)], width=1, seed=16); belt(m, "^", [(22, 6), (23, 9)], width=1, seed=17); belt(m, "^", [(2, 20), (3, 23)], width=1, seed=18); belt(m, "f", [(12, 17), (15, 19)], width=1, seed=19); belt(m, "^", [(26, 18), (27, 19)], width=1, seed=20); belt(m, "f", [(13, 28), (19, 28)], width=1, seed=21); belt(m, "^", [(30, 26), (31, 28)], width=1, seed=22)
    m.header(armies=2, colours=(BH, YC), objective=[1], comment=(
        "M11 Black Lanterns (rain): Black Hole (free CO pick, HQ 1 (7,21), the south-west shore) with three Black Crystals (X) against Grimm (Yellow Comet, HQ 2 (33,9), the north-eastern cape). "
        "A river from the south edge to the bay's beach (x 22 to 24), bridges at (22,27), (24,21) and (22,15); Com Tower (20,15), missile silo (28,22); a neutral port on the lantern islet (14,8). "
        "Player: INF5 MECH2 TANK4 MDT2 ART3 ROCK1 RECON1 AA3 CR2 SUB1 BS1; Grimm: INF6 MECH4 TANK8 MDT4 ART4 ROCK3 RECON1 FTR2 BMB2 BS2 CR1 SUB1."))
    m.put("1", 7, 21).put("2", 33, 9).put("t", 20, 15).put("M", 28, 22)
    m.put("P", 11, 13).put("P", 25, 8).put("p", 14, 8)
    m.stamp("X", 5, 18).stamp("X", 10, 18).stamp("X", 6, 24)
    # --- roads that follow the land; the bridges at (22,27), (24,21), (22,15)
    route(m, [(7, 22), (11, 24), (15, 26), (20, 26), (22, 27, "="), (25, 26), (29, 24), (33, 22), (34, 18), (33, 13), (33, 10)], seed=1)
    route(m, [(7, 20), (11, 21), (16, 21), (21, 21), (24, 21, "="), (27, 21), (30, 19), (33, 17)], seed=2)
    route(m, [(8, 20), (10, 16), (11, 14), (14, 15), (19, 15), (22, 15, "="), (25, 15), (29, 13), (33, 11)], seed=3)
    route(m, [(11, 14), (11, 14)], seed=4) if False else None
    route(m, [(33, 10), (30, 8), (26, 8), (25, 8)], seed=5); route(m, [(20, 15), (20, 21)], seed=6); route(m, [(30, 19), (28, 21)], seed=7); route(m, [(33, 9), (35, 7), (36, 5)], seed=8)
    route(m, [(7, 22), (5, 23)], seed=9); route(m, [(11, 24), (12, 26)], seed=10)
    route(m, [(11, 14), (7, 12), (5, 10)], seed=11)
    route(m, [(33, 22), (35, 26), (36, 28)], seed=12)
    thin_roads(m)
    # --- towns: Black Hole's bastion and harbour, the bridgeheads, Grimm's plateau and cape port, the villages of the neutral middle
    town(m, 7, 21, "BBC", seed=1); town(m, 10, 22, "BC", seed=2); town(m, 7, 18, "C", seed=3); town(m, 11, 14, "BC", seed=4); town(m, 9, 26, "C", seed=5); town(m, 4, 21, "C", seed=6)
    town(m, 16, 26, "CC", seed=7); town(m, 18, 21, "Cb", seed=8); town(m, 17, 15, "CC", seed=9); town(m, 20, 15, "C", seed=10); town(m, 26, 26, "Cb", seed=11); town(m, 27, 21, "Cb", seed=12)
    town(m, 26, 15, "CC", seed=13); town(m, 33, 10, "BBC", seed=14); town(m, 35, 8, "AAB", seed=15, radius=3); town(m, 30, 8, "BC", seed=16); town(m, 33, 14, "BC", seed=17)
    town(m, 33, 22, "BC", seed=18); town(m, 34, 18, "CC", seed=19); town(m, 25, 9, "C", seed=20); town(m, 29, 13, "C", seed=21); town(m, 37, 12, "C", seed=22); town(m, 12, 20, "C", seed=23); town(m, 5, 10, "cc", seed=24); town(m, 36, 28, "cc", seed=25)
    neutralize(m, 14)
    m.tidy()
    for box in [(2, 12, 24, 12), (3, 5, 9, 5), (14, 6, 18, 6), (14, 10, 18, 10)]:
        shore(m, 1, box, dirs="NS")
    for (x, y) in [(11, 12), (22, 12), (14, 7), (25, 7)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    # --- units: Black Hole's bastion with the healing line of the crystals, Grimm's cape army and the fleets in the bay
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 5, MECH: 2, TANK: 4, MDT: 2, ART: 3, ROCK: 1, RECON: 1, AA: 3}, (2, 15, 14, 27), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 3, TANK: 5, MDT: 2, ART: 2, ROCK: 2, RECON: 1}, (27, 3, 38, 14), seed=2, gap=0, avoid=av)
    m.spread(2, {INF: 2, MECH: 1, TANK: 3, MDT: 2, ART: 2, ROCK: 1}, (26, 16, 38, 26), seed=3, gap=1, avoid=av)
    m.spread(2, {FTR: 2, BMB: 2}, (30, 4, 38, 12), seed=4, gap=1, avoid=av)
    for (x, y), k in zip(m.sea_near(12, 11, 4, box=(7, 9, 22, 12), deep=False), [CR, CR, SUB, BS]):
        m.unit(1, k, x, y)
    for (x, y), k in zip(m.sea_near(23, 8, 4, box=(18, 4, 25, 11), deep=False), [BS, BS, CR, SUB]):
        m.unit(2, k, x, y)
    m.note("hq", 7, 21, "Black Hole's HQ"); m.note("enemy_hq", 33, 9, "Grimm's HQ (objective)"); m.note("crystals", 5, 18, "Black Crystals (5,18), (10,18), (6,24): the healing line")
    return m
