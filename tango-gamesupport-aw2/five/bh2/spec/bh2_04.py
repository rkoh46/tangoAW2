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

W, H = 36, 26


def build():
    m = Canvas("bh2_04", W, H, fill="~")
    # --- coasts
    land_rows(m, {6: (4, 13), 7: (3, 14), 8: (2, 14), 9: (3, 14), 10: (2, 14), 11: (2, 14), 12: (3, 14), 13: (2, 14), 14: (2, 14), 15: (3, 14), 16: (2, 14), 17: (2, 14),
                  18: (3, 14), 19: (2, 13), 20: (4, 12)})                                                                      # Black Hole's island (flat north and south coasts: the beaches; a ragged west)
    land_rows(m, {10: (18, 21), 11: (17, 21), 12: (17, 21), 13: (17, 21), 14: (17, 21), 15: (17, 20)})                                    # the islet
    land_rows(m, {2: (25, 33), 3: (24, 34), 4: (25, 34), 5: (24, 33), 6: (24, 34), 7: (25, 34), 8: (24, 34), 9: (25, 33), 10: (24, 34), 11: (24, 34), 12: (25, 34),
                  13: (24, 34), 14: (25, 33), 15: (24, 34), 16: (25, 34), 17: (24, 33), 18: (26, 33)})                                  # Drake's island (a ragged west and east)
    land_rows(m, {3: (17, 20), 4: (16, 20), 5: (16, 19)})                                                                              # the north islet
    land_rows(m, {20: (18, 22), 21: (17, 22), 22: (17, 21), 23: (18, 22)})                                                             # the south islet
    # --- roads: the home island's ring and its spurs, the islet's, Drake's island's, the small islands'
    m.road([(5, 9), (12, 9), (12, 17), (5, 17), (5, 9)]); m.road([(8, 17), (8, 20)]); m.road([(8, 9), (8, 7)]); m.road([(12, 13), (14, 13)]); m.road([(5, 13), (2, 13)])
    m.road([(18, 12), (20, 12)]); m.road([(19, 10), (19, 14)])
    m.road([(26, 6), (33, 6)]); m.road([(26, 6), (26, 16)]); m.road([(26, 16), (32, 16)]); m.road([(33, 6), (33, 16)]); m.road([(29, 6), (29, 2)]); m.road([(26, 11), (24, 11)])
    m.road([(16, 4), (20, 4)]); m.road([(17, 21), (22, 21)]); m.road([(20, 21), (20, 23)])
    # --- relief
    m.cluster("^", 9, 12, 12, seed=1, only="."); m.cluster("^", 4, 9, 6, seed=2); m.cluster("^", 11, 20, 4, seed=3)
    m.cluster("^", 31, 10, 14, seed=4); m.cluster("^", 27, 3, 5, seed=5); m.cluster("^", 33, 15, 5, seed=6); m.cluster("^", 19, 12, 3, seed=7, only=".")
    for i, (cx, cy, n) in enumerate([(6, 11, 6), (10, 15, 6), (3, 15, 5), (11, 8, 5), (28, 8, 7), (30, 14, 6), (25, 14, 5), (28, 4, 5), (32, 4, 4), (17, 12, 3), (21, 13, 3),
                                     (7, 19, 3), (22, 21, 3), (16, 2, 3), (30, 18, 3), (26, 9, 4)]):
        m.cluster("f", cx, cy, n, seed=20 + i)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M4 Talons, front 1: Black Hole's fortress island (west, HQ 1 (6,15)) against Drake's island (east, HQ 2 (29,8)) across the strait; the islet (19,12) holds a neutral port and a missile silo. "
        "Black Hole's inventions (its side only): Lasers (13,10) (13,16), minicannons facing east (14,12) (14,14), south (8,21)... Player: free CO pick. Player: CR3 BB2 SUB2 LAN3 INF5 MECH3 TANK3 ART3 AA2 RECON1 APC1; "
        "Drake: BB3 CR3 SUB2 LAN3 INF5 MECH3 TANK3 ART2 AA2 RECON1 FTR2 BMB1."))
    m.put("1", 6, 15).put("2", 29, 8)
    m.puts("P", [(7, 20), (13, 20)]).put("A", 4, 13).place("B", 3, (2, 8, 14, 18), seed=1, gap=3).place("C", 5, (2, 7, 14, 19), seed=2, gap=2, reach=3)
    m.put("P", 24, 8).put("P", 27, 18).put("A", 33, 10).place("B", 3, (24, 3, 34, 17), seed=3, gap=3).place("C", 6, (24, 3, 34, 17), seed=4, gap=2, reach=3)
    m.put("p", 21, 13).put("c", 18, 12).put("M", 20, 11)
    m.place("c", 2, (16, 3, 20, 5), seed=5, gap=2, reach=3).place("c", 3, (17, 20, 22, 23), seed=6, gap=2, reach=3).put("b", 17, 14)
    # --- Black Hole's inventions: Lasers and minicannons on the east coast
    m.stamp("L", 13, 10).stamp("L", 13, 16).stamp("E", 14, 12).stamp("E", 14, 14).stamp("S", 11, 20).stamp("N", 6, 6)
    # --- beaches: long, one cell wide, on the north- and south-facing coasts of every island (AW2 draws no long vertical beach); the ports' cells left open
    shore(m, 1, (2, 5, 14, 5), dirs="NS"); shore(m, 1, (2, 21, 14, 21), dirs="NS"); shore(m, 1, (16, 9, 22, 9), dirs="NS"); shore(m, 1, (16, 16, 22, 16), dirs="NS")
    shore(m, 1, (13, 2, 21, 2), dirs="NS"); shore(m, 1, (13, 6, 21, 6), dirs="NS"); shore(m, 1, (15, 19, 25, 19), dirs="NS"); shore(m, 1, (15, 24, 25, 24), dirs="NS")
    shore(m, 1, (24, 1, 34, 1), dirs="NS"); shore(m, 1, (24, 19, 34, 19), dirs="NS")
    for (x, y) in [(7, 21), (13, 21), (27, 19)]:
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    m.tidy()
    # --- Black Hole: the fleet beside its ports, the army on the island behind the Lasers
    for (x, y), k in zip(m.sea_near(7, 22, 3) + m.sea_near(13, 22, 3), [CR, CR, BS, BS, CR, SUB]):
        m.unit(1, k, x, y)
    m.unit(1, SUB, *m.sea_near(1, 18, 1)[0]); m.units(1, LAN, m.sea_near(10, 22, 3, box=(2, 21, 14, 24), deep=False))
    m.spread(1, {INF: 5, MECH: 3, TANK: 3, ART: 3, AA: 2, RECON: 1, APC: 1}, (2, 8, 14, 19), seed=1, gap=0, avoid="~r=-^IZ#LSNWEXvnFDO")
    # --- Drake: his fleet in the strait and off his ports, the army on his island, Fighters at the airport
    for (x, y), k in zip(m.sea_near(22, 8, 3) + m.sea_near(27, 20, 3), [BS, BS, CR, CR, BS, CR]):
        m.unit(2, k, x, y)
    m.units(2, SUB, m.sea_near(21, 17, 2)); m.units(2, LAN, m.sea_near(30, 20, 3, box=(24, 19, 34, 22), deep=False))
    m.spread(2, {INF: 5, MECH: 3, TANK: 3, ART: 2, AA: 2, RECON: 1, FTR: 2, BMB: 1}, (24, 3, 34, 17), seed=2, gap=0)
    m.note("hq", 6, 15, "Black Hole's HQ"); m.note("enemy_hq", 29, 8, "Drake's HQ (objective)"); m.note("islet", 19, 12, "the islet: neutral port, village, missile silo")
    return m
