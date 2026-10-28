"""BH2 M9 Paper Lanterns (Act II): a night intel raid on Sensei's B Copter fleet, on Yellow Comet's lantern islands (rain and fog, the normal look).

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Asuka's raiders (a free CO pick) land from Lantern Cove, the grey island in the west (HQ, a base
district, a port in the bay, an airstrip, a fleet of Landers and a Cruiser). Sensei holds Roost, the big island in the east: his HQ, two heliports where the B Copter fleet sits
parked and a Cruiser and a Submarine in his two harbours. Between them lies Lantern Isle in the north (the lantern town of the title: a Com Tower, a missile silo and a village
of neutral cities) joined by a bridge to both Cove and Roost, and Lamp Isle, a small southern island with a neutral port. The raid is won by taking Sensei's HQ.
- Lanes: the north road (Cove, the bridge, Lantern Isle, the second bridge, Roost's north cape), the sea lane south of Lamp Isle for the Landers (long beaches on Cove's south
  coast, Lamp Isle and Roost's south coast), the strait between Lantern Isle and Roost with its reefs for the ships.
- Where the fight happens: Lantern Isle's lantern town (Com Tower, silo and cities) and then the heliports on Roost.
- Properties: Cove's bases and airstrip feed the raid (Anti-Air and Copters), the three ports (Cove's bay, Lamp Isle, Roost) hold the sea; Sensei's bases and two airports are his strength.
- Threats and answers: the B Copter fleet -> Anti-Air, Tanks and Copters from the airstrip; Sensei's Cruiser and Submarine -> the raid's Cruiser and Submarine and the Landers' escort;
  his foot soldiers -> Tanks and artillery.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 40, 28


def build():
    m = Canvas("bh2_09", W, H, fill="~")
    # --- coasts with shape: Lantern Cove (bay on its east side, a flat north and south coast), Lantern Isle (a teardrop with a cape), Roost (ragged west, a bay), Lamp Isle
    land_rows(m, {6: (8, 10), 7: (5, 12), 8: (3, 12), 9: (3, 11), 10: (2, 11), 11: (2, 13), 12: (3, 13), 13: (3, 10), 14: (2, 8), 15: (3, 8), 16: (3, 9), 17: (2, 11), 18: (2, 12),
                  19: (3, 13), 20: (3, 13), 21: (5, 12), 22: (6, 12), 23: (7, 10)})
    land_rows(m, {2: (18, 24), 3: (17, 25), 4: (16, 25), 5: (16, 25), 6: (15, 25), 7: (15, 23), 8: (16, 22), 9: (17, 21), 10: (18, 21), 11: (19, 20)})
    land_rows(m, {6: (28, 31), 7: (28, 33), 8: (29, 35), 9: (30, 37), 10: (29, 37), 11: (27, 37), 12: (26, 37), 13: (25, 36), 14: (25, 37), 15: (27, 37), 16: (29, 36), 17: (30, 36),
                  18: (28, 37), 19: (26, 37), 20: (25, 36), 21: (25, 35), 22: (26, 34), 23: (28, 34), 24: (29, 33)})
    land_rows(m, {19: (16, 22), 20: (15, 23), 21: (15, 23), 22: (16, 22), 23: (17, 21)})
    # --- reefs in the strait and east of Lamp Isle (ships go round them)
    for (x, y) in [(23, 11), (24, 12), (22, 12), (24, 10), (12, 25), (13, 25), (30, 3), (31, 3)]:
        m.put("r", x, y)
    # --- relief: ridges and forest belts that make the lanes
    belt(m, "^", [(4, 9), (9, 8)], width=1, seed=1); belt(m, "^", [(3, 19), (6, 21)], width=1, seed=2); belt(m, "^", [(17, 4), (19, 8)], width=1, seed=3, gaps=[(18, 6)])
    belt(m, "^", [(31, 11), (35, 13)], width=1, seed=4, gaps=[(33, 12)]); belt(m, "^", [(29, 20), (34, 21)], width=1, seed=5); belt(m, "^", [(35, 17), (36, 19)], width=1, seed=6)
    belt(m, "f", [(4, 11), (8, 13)], width=1, seed=7); belt(m, "f", [(10, 18), (12, 21)], width=1, seed=8); belt(m, "f", [(21, 3), (24, 5)], width=1, seed=9)
    belt(m, "f", [(28, 12), (29, 15)], width=1, seed=10); belt(m, "f", [(33, 16), (35, 15)], width=1, seed=11); belt(m, "f", [(29, 8), (33, 9)], width=1, seed=12); belt(m, "f", [(27, 19), (30, 18)], width=1, seed=13)
    belt(m, "f", [(16, 20), (21, 21)], width=1, seed=14)
    m.header(armies=2, colours=(BH, YC), objective=[1], comment=(
        "M9 Paper Lanterns (night, rain and fog): the raid (Black Hole, free CO pick, HQ 1 (6,17), Lantern Cove in the west) against Sensei (Yellow Comet, HQ 2 (32,15), Roost in the east). "
        "Lantern Isle (north, bridged to both): Com Tower (20,5), missile silo (22,8), neutral cities; Lamp Isle (south): a neutral port. Sensei's B Copter fleet is parked on his heliports. "
        "Player: INF4 MECH2 TANK3 ART1 RECON1 AA2 APC1 BCO3 CR2 SUB1 LAN2; Sensei: INF6 MECH3 TANK2 ART1 ROCK1 RECON1 AA1 BCO8 CR2 SUB1 LAN1."))
    m.put("1", 6, 17).put("2", 32, 15).put("t", 20, 5).put("M", 22, 8)
    m.put("P", 8, 15).put("P", 31, 24).put("P", 25, 14).put("p", 23, 21)
    # --- the two bridges of the north road; roads that follow the land
    m.bridge(13, 7, 14, 7); m.bridge(26, 6, 27, 6)
    route(m, [(6, 18), (5, 14), (8, 10), (11, 7), (12, 7)], seed=1); route(m, [(15, 7), (18, 6), (20, 6), (25, 6)], seed=2)
    route(m, [(28, 6), (31, 8), (32, 13), (32, 15)], seed=3); route(m, [(6, 18), (9, 19), (12, 20)], seed=4); route(m, [(7, 15), (8, 16)], seed=5)
    route(m, [(32, 15), (32, 20), (31, 23)], seed=6); route(m, [(32, 15), (29, 14), (26, 14)], seed=7); route(m, [(32, 15), (36, 14)], seed=8)
    route(m, [(20, 6), (21, 8), (19, 10)], seed=9); route(m, [(18, 20), (19, 21)], seed=10)
    thin_roads(m)
    # --- towns: the Cove's district and airstrip, the lantern town, Sensei's capital with its two heliports, the harbours
    town(m, 6, 17, "BBC", seed=1); town(m, 4, 19, "BC", seed=2); town(m, 9, 20, "CC", seed=3); town(m, 10, 10, "AB", seed=4, radius=3); town(m, 6, 11, "C", seed=5); town(m, 9, 7, "C", seed=30)
    town(m, 19, 4, "ccc", seed=7); town(m, 17, 7, "cc", seed=8); town(m, 22, 6, "c", seed=9)
    town(m, 32, 15, "BBC", seed=10); town(m, 33, 11, "AB", seed=11, radius=3); town(m, 31, 19, "AB", seed=12, radius=3); town(m, 30, 8, "CC", seed=13); town(m, 29, 14, "BC", seed=14)
    town(m, 35, 14, "C", seed=15); town(m, 31, 22, "CC", seed=16); town(m, 19, 21, "cc", seed=17); town(m, 26, 15, "C", seed=18)
    neutralize(m, 14)
    m.tidy()
    for box in [(4, 5, 12, 5), (5, 24, 12, 24), (17, 1, 25, 1), (14, 18, 23, 18), (14, 24, 23, 24), (28, 5, 33, 5), (27, 25, 35, 25)]:
        shore(m, 1, box, dirs="NS")
    for (x, y) in [(31, 25), (8, 14), (9, 15), (25, 13), (24, 14), (24, 21)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    # --- units: the raid on Lantern Cove with its fleet in the bay, Sensei's army with the B Copter fleet parked on his heliports
    av = "~r=-^IZ#X12345QBCPTbcpt"
    air = [(x, y) for y in range(H) for x in range(W) if m.g[y][x] == "A"]
    mine = [c for c in air if c[0] < 20]; his = [c for c in air if c[0] >= 20]
    m.reserve(mine + his)
    m.spread(1, {INF: 4, MECH: 2, TANK: 3, ART: 1, RECON: 1, AA: 2, APC: 1}, (2, 8, 12, 22), seed=1, gap=0, avoid=av)
    for (x, y), k in zip(m.sea_near(9, 15, 5, box=(9, 12, 14, 18), deep=False), [LAN, LAN, CR, CR, SUB]):
        m.unit(1, k, x, y)
    m.spread(1, {BCO: 3}, (2, 8, 12, 22), seed=3, gap=1, avoid=av)
    m.spread(2, {INF: 6, MECH: 3, TANK: 2, ART: 1, ROCK: 1, RECON: 1, AA: 1}, (26, 8, 37, 24), seed=2, gap=0, avoid=av)
    for c in his:
        m.unit(2, BCO, c[0], c[1], hold=True)
    m.spread(2, {BCO: 8 - len(his)}, (28, 8, 37, 22), seed=4, gap=1, avoid=av)
    for (x, y), k in zip(m.sea_near(31, 25, 3, deep=False) + m.sea_near(24, 14, 1, box=(21, 9, 24, 16), deep=False), [CR, CR, SUB, LAN]):
        m.unit(2, k, x, y)
    m.note("hq", 6, 17, "Black Hole's HQ"); m.note("enemy_hq", 32, 15, "Sensei's HQ (objective)"); m.note("lanterns", 19, 4, "the lantern town: Com Tower, silo and neutral cities")
    return m
