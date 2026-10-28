"""BH2 M1 Black Insight (Act I): Asuka's first landing, on Drake's Halyard Isle. Fog.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Black Hole's home island lies in the south with its HQ, two ports and the Landers;
Drake's marines hold Halyard Isle in the north, his HQ in the fort on the ridge, a port in the headland, his cruisers in the strait. In the fog the player
cannot see a thing: Asuka's intel (a Recon, the Cruisers' sight) is the lesson.
- Lanes: two long beaches on the isle's south coast either side of a central bay (the west strand x 3..11 and the east strand x 19..26, one cell wide and long: AW2 draws no wider), a mid-strait islet with a village between the west and east channels, a road inland from each strand (west, headland, east), two lateral
  roads between them, the river bridged where the roads cross.
- Where the fight happens: the strands and the farms above them (villages and a neutral base each side), the headland town, then the fort's three approaches.
- Threats and answers: Drake's two Cruisers and Submarine -> the player's Cruisers and the Battleships the home ports build; his tanks on the strands ->
  Tanks of the second Lander trip, Mechs and artillery; the fort's artillery -> the river-road approach through the woods. Drake has no airfield, so the player
  needs no Anti-Air.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 30, 28


def build():
    m = Canvas("bh2_01", W, H, fill="~")
    # --- coasts with shape: Halyard Isle's cape and bays, the central bay between the two strands, the home island's capes
    land_rows(m, {0: (9, 23), 1: (6, 24), 2: (4, 26), 3: (3, 27), 4: (2, 28), 5: (3, 28), 6: (5, 28), 7: (6, 27), 8: (5, 28), 9: (3, 28), 10: (2, 28),
                  11: (2, 12), 12: (2, 11), 13: (3, 11)})
    land_rows(m, {11: (18, 27), 12: (19, 27), 13: (19, 26)})                                       # (the bay: sea at x13..17 on row 11, x12..18 on rows 12 and 13)
    land_rows(m, {21: (5, 24), 22: (3, 26), 23: (2, 27), 24: (1, 27), 25: (3, 28), 26: (3, 26), 27: (5, 24)})
    m.rect("~", 7, 21, 7, 21); m.rect("~", 22, 21, 22, 21)                                         # the harbour notches of the two ports
    m.rect("~", 1, 24, 1, 24); m.rect("~", 27, 21, 27, 21)
    m.rect(".", 13, 15, 15, 17)                                                                     # the islet
    # --- the river: source at the north edge, bends, mouth on the east strand
    m.river([(22, 0), (22, 5), (21, 5), (21, 13)])
    # --- relief: the fort's wall (gaps are its gates), ranges, forest belts; open plain between
    belt(m, "^", [(10, 1), (18, 1)], width=1, seed=1, p=1.0); belt(m, "^", [(10, 2), (10, 5)], width=1, seed=2, gaps=[(10, 3)], p=1.0); belt(m, "^", [(18, 2), (18, 5)], width=1, seed=3, gaps=[(18, 3)], p=1.0)
    belt(m, "^", [(10, 5), (12, 6)], width=1, seed=4, p=1.0); belt(m, "^", [(16, 6), (18, 5)], width=1, seed=5, p=1.0)
    belt(m, "^", [(4, 3), (5, 7)], width=1, seed=6); belt(m, "^", [(24, 2), (27, 5)], width=1, seed=7); belt(m, "^", [(7, 9), (11, 11)], width=1, seed=8, gaps=[(9, 10)])
    belt(m, "^", [(3, 10), (4, 12)], width=1, seed=9); belt(m, "^", [(2, 24), (4, 27)], width=1, seed=10); belt(m, "^", [(24, 24), (27, 26)], width=1, seed=11)
    belt(m, "f", [(3, 9), (6, 11)], width=1, seed=12); belt(m, "f", [(24, 9), (26, 12)], width=1, seed=13); belt(m, "f", [(13, 8), (15, 9)], width=1, seed=14)
    belt(m, "f", [(19, 6), (20, 10)], width=1, seed=15); belt(m, "f", [(7, 4), (9, 7)], width=1, seed=16); belt(m, "f", [(23, 6), (25, 8)], width=1, seed=17)
    belt(m, "f", [(6, 24), (10, 26)], width=1, seed=18); belt(m, "f", [(18, 25), (22, 26)], width=1, seed=19); belt(m, "f", [(3, 22), (5, 23)], width=1, seed=20)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M1 Black Insight (fog): Black Hole's home island (south) against Drake on Halyard Isle (north). Take Drake's HQ 2 (14,3) in the fort. Beaches: the west strand x3..11 and "
        "the east strand x19..26 (row 14, one cell wide and long), either side of the central bay (x12..18, rows 11..13) whose head holds a neutral port (15,10); the islet (14,16). Roads follow the land: the west road, the cove road and the east road to the fort, bridged over the river x21..22; "
        "neutral bases and farms in towns; missile silo (26,6). Player: Asuka (forced), LAN4 CR2 INF4 MECH2 TANK2 RECON1 APC1 ART1. Enemy (Drake): INF8 MECH2 TANK3 ART2 RECON1 CR2 SUB1."))
    m.put("2", 14, 3).put("1", 14, 24).put("p", 15, 10).put("M", 26, 6).puts("P", [(7, 22), (22, 22)])
    # --- the roads
    route(m, [(5, 12), (8, 8), (12, 5), (13, 4)], seed=1, wander=0.3); route(m, [(14, 9), (14, 5)], seed=2, wander=0.3)                       # the west road and the cove road to the fort's gates
    route(m, [(23, 12), (24, 8), (21, 9, "="), (19, 6), (17, 4)], seed=3, wander=0.3)
    route(m, [(24, 8), (26, 7)], seed=6); route(m, [(7, 23), (10, 23), (14, 24), (18, 23), (22, 23)], seed=7)
    route(m, [(14, 24), (14, 26)], seed=8); route(m, [(10, 23), (8, 25)], seed=9); route(m, [(18, 23), (20, 25)], seed=10)
    thin_roads(m)
    # --- towns: Drake's fort and districts, the west and east strands' villages, the cove port, the farms; Black Hole's HQ district and its two port towns
    town(m, 12, 3, "C", seed=1); town(m, 16, 3, "C", seed=2); town(m, 14, 5, "B", seed=3); town(m, 8, 7, "CCb", seed=4); town(m, 5, 11, "CC", seed=5)
    town(m, 15, 9, "CC", seed=6); town(m, 23, 11, "CC", seed=7); town(m, 24, 7, "Cb", seed=8); town(m, 19, 6, "C", seed=9); town(m, 11, 9, "C", seed=10)
    town(m, 15, 24, "BC", seed=11); town(m, 13, 24, "BC", seed=12); town(m, 8, 23, "CC", seed=13); town(m, 21, 23, "CC", seed=14); town(m, 14, 26, "C", seed=15)
    town(m, 8, 25, "C", seed=16); town(m, 20, 25, "C", seed=17)
    neutralize(m, 14)
    m.put("c", 14, 16).put("c", 14, 15)
    m.tidy()
    # --- beaches: long, one cell wide, on the strands (north- and south-facing coasts), ports' notches and the river mouth left open
    shore(m, 1, (3, 14, 11, 14), dirs="NS"); shore(m, 1, (19, 14, 26, 14), dirs="NS"); shore(m, 1, (12, 14, 16, 14), dirs="NS")
    shore(m, 1, (9, 20, 19, 20), dirs="NS")
    m.g[14][21] = "~"
    m.put("r", 9, 18).put("r", 10, 18).put("r", 10, 19).put("r", 19, 18).put("r", 20, 18).put("r", 19, 19)     # reefs off the islet
    # --- Black Hole: the Landers wait in the two harbours and off the home beach, the ground army ashore beside them
    av = "~r=-^IZ#12345QBCPTbcpt"
    m.units(1, LAN, [(7, 21), (22, 21), (8, 20), (21, 20)]).units(1, CR, [(11, 19), (17, 19)])
    m.spread(1, {INF: 4, MECH: 2, TANK: 2, RECON: 1, APC: 1, ART: 1}, (3, 22, 26, 26), seed=1, gap=0, avoid=av)
    # --- Drake: the fort's garrison (holds), the farms and strands' pickets, the cruisers and a submarine in the strait
    m.spread(2, {INF: 4, ART: 2, MECH: 1}, (11, 2, 17, 5), seed=2, gap=0, hold=True, avoid=av)
    m.spread(2, {INF: 4, TANK: 3, MECH: 1, RECON: 1}, (3, 7, 27, 12), seed=3, gap=1, avoid=av)
    m.units(2, CR, [(6, 18), (22, 17)]).unit(2, SUB, 11, 18)
    m.note("hq", 14, 24, "Black Hole's HQ on the home island")
    m.note("enemy_hq", 14, 3, "Drake's HQ in the fort (objective)")
    m.note("strand_w", 6, 15, "west strand"); m.note("strand_e", 23, 15, "east strand"); m.note("islet", 14, 16, "the islet village between the channels"); m.note("bay", 15, 12, "the central bay: a cove port at its head")
    return m
