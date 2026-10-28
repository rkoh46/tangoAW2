"""BH2 M4 Talons (Act I), front 1: Black Hole's fortress island against Drake's fleet, in Green Earth's southern sea. (Front 2 is bh2_04b, the sky.)

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole holds a fortress island in the west: its HQ, two ports, an airport, a
missile silo on the high ground, and its own inventions on the east coast: two Lasers and four minicannons (Black Hole's alone) that hold the strait. Drake holds the
big island in the east with his HQ, ports and an airport, and a fleet. Between them lies a strait with a village islet (a neutral port and a silo) and two small
islands each side.
- Lanes: the strait's three channels (north of the islet, south of it, the islet's own shoals), the islet strand, the north and south islets; on each island a ring
  road with a spur to every beach. Long beaches (the west coast, the islet, Drake's west coast) one cell wide, as AW2 draws them.
- Where the fight happens: the islet (a neutral port, a village and the missile silo) in the middle: whoever holds it commands the strait.
- Properties: the player's bases and airport build the Anti-Air and Fighters Drake's airport makes necessary; ports on both sides build the fleets; every island has
  villages near its road.
- Threats and answers: Drake's Battleships and Cruisers -> the Lasers and minicannons, the player's own ships and Submarines; Drake's Fighters and Bomber -> Anti-Air,
  Fighters from the airport; Landers on the strand -> artillery and tanks behind the beach, the minicannons.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, clear_fire_lines

W, H = 36, 26


def build():
    m = Canvas("bh2_04", W, H, fill="~")
    # --- coasts with shape: bays, capes and a peninsula; the north and south coasts keep long flat runs for the beaches and the ports' notches
    land_rows(m, {6: (4, 12), 7: (3, 13), 8: (2, 14), 9: (2, 14), 10: (3, 14), 11: (3, 14), 12: (5, 14), 13: (5, 14), 14: (4, 14), 15: (3, 14), 16: (2, 14), 17: (2, 14),
                  18: (3, 14), 19: (3, 13), 20: (4, 12)})                                                                      # Black Hole's island: a bay in the west, the east coast straight for the Lasers
    land_rows(m, {21: (2, 4), 22: (2, 5), 23: (3, 4)})                                                                            # the south-west peninsula
    land_rows(m, {10: (18, 21), 11: (17, 21), 12: (17, 21), 13: (17, 21), 14: (17, 21), 15: (17, 20)})                              # the islet
    land_rows(m, {2: (26, 33), 3: (25, 34), 4: (24, 34), 5: (24, 33), 6: (24, 34), 7: (25, 34), 8: (24, 34), 9: (25, 33), 10: (24, 34), 11: (24, 34), 12: (26, 34),
                  13: (27, 34), 14: (26, 33), 15: (25, 34), 16: (24, 34), 17: (25, 33), 18: (26, 33)})                              # Drake's island: a bay in the south-west, ragged east
    land_rows(m, {3: (17, 20), 4: (16, 20), 5: (16, 19)})                                                                          # the north islet
    land_rows(m, {20: (18, 22), 21: (17, 22), 22: (17, 21), 23: (18, 22)})                                                         # the south islet
    # --- relief: ridges and forest belts that shape the lanes
    belt(m, "^", [(8, 8), (11, 12), (9, 16)], width=1, seed=1, gaps=[(10, 10)]); belt(m, "^", [(4, 8), (3, 11)], width=1, seed=2); belt(m, "^", [(10, 18), (12, 19)], width=1, seed=3)
    belt(m, "^", [(28, 5), (31, 4), (33, 6)], width=1, seed=4, gaps=[(30, 4)]); belt(m, "^", [(30, 10), (32, 14)], width=1, seed=5, gaps=[(31, 12)]); belt(m, "^", [(25, 16), (27, 16)], width=1, seed=6)
    belt(m, "^", [(33, 14), (33, 17)], width=1, seed=7); belt(m, "^", [(18, 11), (19, 12)], width=1, seed=8, p=0.8)
    belt(m, "f", [(4, 9), (7, 11)], width=1, seed=9); belt(m, "f", [(6, 17), (9, 18)], width=1, seed=10); belt(m, "f", [(11, 8), (13, 9)], width=1, seed=11)
    belt(m, "f", [(25, 8), (27, 11)], width=1, seed=12); belt(m, "f", [(31, 7), (33, 9)], width=1, seed=13); belt(m, "f", [(28, 15), (30, 17)], width=1, seed=14)
    belt(m, "f", [(25, 4), (27, 3)], width=1, seed=15); belt(m, "f", [(18, 14), (20, 14)], width=1, seed=16)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M4 Talons, front 1: Black Hole's fortress island (west, HQ 1 (6,15)) against Drake's island (east, HQ 2 (29,8)) across the strait; the islet (19,12) holds a neutral port (21,14) and a missile silo. "
        "Black Hole's inventions (its side only): Lasers (17,12) on the islet in the middle of the map and (11,9) (their rows and columns cross no Black Hole property: rule IV03), minicannons facing east (14,12) (14,14), south (11,20), north (6,6). Player: free CO pick. Player: CR3 BB2 SUB2 LAN3 INF5 MECH3 TANK3 ART3 AA2 RECON1 APC1; "
        "Drake: BB3 CR3 SUB2 LAN3 INF5 MECH3 TANK3 ART2 AA2 RECON1 FTR2 BMB1."))
    m.put("1", 6, 15).put("2", 29, 8)
    m.puts("P", [(7, 20), (13, 20)]).put("A", 6, 13).put("P", 24, 8).put("P", 27, 18).put("A", 33, 10)
    m.put("p", 21, 14).put("M", 20, 11)
    # --- roads that follow the land
    route(m, [(7, 19), (7, 17), (6, 15), (6, 13), (8, 11), (10, 9), (8, 7)], seed=1); route(m, [(6, 15), (9, 15), (12, 13), (12, 11)], seed=2)
    route(m, [(7, 19), (11, 19), (13, 19)], seed=3); route(m, [(8, 7), (6, 7)], seed=4); route(m, [(9, 15), (11, 17), (11, 19)], seed=5)
    route(m, [(25, 8), (27, 9), (29, 9), (31, 10), (33, 11)], seed=6); route(m, [(29, 9), (30, 6), (32, 3)], seed=7); route(m, [(29, 9), (28, 13), (27, 17)], seed=8)
    route(m, [(31, 10), (30, 14), (28, 17)], seed=9); route(m, [(25, 11), (28, 10)], seed=10)
    route(m, [(16, 4), (20, 4)], seed=13); route(m, [(17, 21), (22, 21)], seed=14); route(m, [(20, 21), (20, 23)], seed=15)
    thin_roads(m)
    # --- towns: Black Hole's HQ district and airfield, the port towns; Drake's capital and harbour towns; the islets' villages
    m.puts("B", [(5, 14), (8, 16)]) if False else None
    town(m, 6, 15, "BBC", seed=1); town(m, 7, 18, "CC", seed=2); town(m, 13, 19, "BC", seed=3); town(m, 9, 10, "CC", seed=4); town(m, 6, 8, "C", seed=5); town(m, 11, 14, "C", seed=6)
    town(m, 28, 8, "BCC", seed=7, radius=3); town(m, 31, 10, "BC", seed=8); town(m, 29, 15, "CC", seed=9); town(m, 26, 8, "C", seed=10); town(m, 32, 4, "Cb", seed=11)
    town(m, 28, 17, "BC", seed=12); town(m, 25, 11, "C", seed=13)
    town(m, 19, 12, "Cc", seed=14); town(m, 18, 4, "CC", seed=15); town(m, 20, 21, "CC", seed=16); town(m, 21, 12, "C", seed=17)
    # --- Black Hole's inventions: Lasers and minicannons on the east coast and the south and north coasts
    m.stamp("L", 17, 12).stamp("L", 11, 9).stamp("E", 14, 12).stamp("E", 14, 14).stamp("S", 11, 20).stamp("N", 6, 6)
    # --- beaches: long, one cell wide, on the north- and south-facing coasts of every island (AW2 draws no long vertical beach); the ports' cells left open
    shore(m, 1, (3, 5, 13, 5), dirs="NS"); shore(m, 1, (3, 21, 13, 21), dirs="NS"); shore(m, 1, (16, 9, 22, 9), dirs="NS"); shore(m, 1, (16, 16, 22, 16), dirs="NS")
    shore(m, 1, (15, 2, 21, 2), dirs="NS"); shore(m, 1, (15, 6, 21, 6), dirs="NS"); shore(m, 1, (15, 19, 25, 19), dirs="NS"); shore(m, 1, (15, 24, 25, 24), dirs="NS")
    shore(m, 1, (24, 1, 34, 1), dirs="NS"); shore(m, 1, (24, 19, 34, 19), dirs="NS")
    for (x, y) in [(7, 21), (13, 21), (27, 19)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    neutralize(m, 14)
    m.tidy()
    # --- Black Hole: the fleet beside its ports, the army on the island behind the Lasers
    for (x, y), k in zip(m.sea_near(7, 22, 3) + m.sea_near(13, 22, 3), [CR, CR, BS, BS, CR, SUB]):
        m.unit(1, k, x, y)
    m.unit(1, SUB, *m.sea_near(1, 18, 1)[0]); m.units(1, LAN, m.sea_near(10, 22, 3, box=(5, 21, 14, 24), deep=False))
    m.spread(1, {INF: 5, MECH: 3, TANK: 3, ART: 3, AA: 2, RECON: 1, APC: 1}, (3, 7, 14, 19), seed=1, gap=0, avoid="~r=-^IZ#LSNWEXvnFDO12345QBCPTbcpt")
    # --- Drake: his fleet in the strait and off his ports, the army on his island, Fighters at the airport
    for (x, y), k in zip(m.sea_near(22, 8, 3) + m.sea_near(27, 20, 3), [BS, BS, CR, CR, BS, CR]):
        m.unit(2, k, x, y)
    m.units(2, SUB, m.sea_near(21, 17, 2)); m.units(2, LAN, m.sea_near(30, 20, 3, box=(24, 19, 34, 22), deep=False))
    m.spread(2, {INF: 5, MECH: 3, TANK: 3, ART: 2, AA: 2, RECON: 1, FTR: 2, BMB: 1}, (24, 3, 34, 17), seed=2, gap=0, avoid="~r=-^IZ#12345QBCPTbcpt")
    clear_fire_lines(m)                    # (nothing may stand in a firing line at the start: the first shot hits nothing)
    m.note("hq", 6, 15, "Black Hole's HQ"); m.note("enemy_hq", 29, 8, "Drake's HQ (objective)"); m.note("islet", 19, 12, "the islet: neutral port, village, missile silo")
    return m
