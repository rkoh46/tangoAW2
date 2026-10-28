"""BH2 M13 Whiteout Harbour (Act III): Olaf's harbour town in a snowstorm and fog. Flak (forced) against Olaf: a naval and ground mix.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The situation: Blue Moon holds the northern coast: a fjord cuts into it from the north and Olaf's harbour town stands on its shores (three ports: both banks and the head of the fjord), his HQ and a
district of bases on the east lobe, a Fighter field and the fleet in the fjord. Black Hole holds a southern island across a channel of five rows with reefs: its HQ, a base district and two ports on the channel. There is no land link: the armies cross by sea, Landers on the long beaches (the continent's south coast, the island's north coast) under the cover of the fleets in the channel. A river rises from a pond in the east
lobe's hills and reaches the channel with a bridge for the coast road. Snow: the heaviest weather the engine has, with fog.
- Lanes: the channel and its reefs, the beaches, the fjord and its three ports, the river's bridge on the coast road, the lobes' ridges.
- Where the fight happens: the channel (the fleets) and the beaches, then the harbour town's ports and the coast road.
- Properties: Black Hole's two channel ports and bases; the continent's villages along the coast road, Olaf's harbour district (three ports), his Fighter airport.
- Threats and answers: Olaf's Battleship, Cruisers and Submarines -> Black Hole's own and the guns on the island's north coast; his Fighters and Copters -> Anti-Air and Copters; his Tanks and artillery on the beaches -> Md Tanks and artillery.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize

W, H = 40, 30


def build():
    m = Canvas("bh2_13", W, H, fill="~")
    # --- the continent (north) with its fjord, the island (south), the long bridge between them
    land_rows(m, {3: (3, 12), 4: (2, 12), 5: (2, 13), 6: (1, 13), 7: (2, 14), 8: (2, 14), 9: (1, 15), 10: (1, 15), 11: (1, 37), 12: (2, 38), 13: (2, 38), 14: (3, 37)})
    land_rows(m, {3: (24, 36), 4: (24, 37), 5: (23, 38), 6: (23, 38), 7: (22, 38), 8: (22, 37), 9: (21, 38), 10: (21, 38)})
    land_rows(m, {20: (6, 33), 21: (4, 34), 22: (4, 34), 23: (3, 35), 24: (3, 35), 25: (4, 34), 26: (5, 32), 27: (7, 29)})
    m.rect(".", 33, 28, 36, 28) if False else None
    pond = m.lake(34, 5, 8, seed=1, river_end=(34, 6))               # (the river rises from a pond in the east lobe's hills)
    m.river([(34, 6), (34, 14)])
    for (x, y) in [(8, 17), (13, 17), (19, 17), (24, 16), (33, 17), (36, 18)]:
        m.put("r", x, y)
    belt(m, "^", [(4, 5), (9, 7), (12, 8)], width=1, seed=1, gaps=[(8, 7)]); belt(m, "^", [(25, 5), (29, 4), (35, 6)], width=1, seed=2, gaps=[(28, 4)]); belt(m, "^", [(5, 12), (9, 13)], width=1, seed=3)
    belt(m, "^", [(23, 9), (26, 11)], width=1, seed=4); belt(m, "^", [(35, 11), (36, 13)], width=1, seed=5); belt(m, "^", [(5, 22), (9, 24)], width=1, seed=6); belt(m, "^", [(24, 25), (29, 24)], width=1, seed=7, gaps=[(27, 24)])
    belt(m, "^", [(14, 25), (18, 26)], width=1, seed=8); belt(m, "f", [(4, 9), (7, 10)], width=1, seed=9); belt(m, "f", [(14, 12), (21, 13)], width=1, seed=10); belt(m, "f", [(25, 7), (28, 8)], width=1, seed=11)
    belt(m, "f", [(7, 21), (12, 22)], width=1, seed=12); belt(m, "f", [(21, 22), (25, 21)], width=1, seed=13); belt(m, "f", [(30, 21), (33, 23)], width=1, seed=14); belt(m, "f", [(10, 25), (13, 24)], width=1, seed=15)
    belt(m, "f", [(31, 11), (34, 12)], width=1, seed=16)
    m.header(armies=2, colours=(BH, BM), objective=[1], comment=(
        "M13 Whiteout Harbour (snow look, snow weather, fog): Flak (forced, Black Hole, HQ 1 (16,23), the southern island) against Olaf (Blue Moon, HQ 2 (31,8), the east lobe of the northern coast). "
        "A river from a pond (34,5) reaches the channel, its bridge (34,11) on the coast road. The fjord (x 14..22) holds Olaf's three ports (13,6), (23,6), (18,11) and his fleet; the channel (rows 15..19) has reefs and no bridge: Landers only. Com Tower (10,12), missile silo (33,12). "
        "Player: INF3 MECH1 TANK3 ART2 ROCK1 RECON1 AA1 APC1 BCO2 BS1 CR2 SUB2 LAN2; Olaf: INF4 MECH2 TANK3 MDT1 ART2 ROCK1 RECON1 FTR2 BCO3 BS1 CR2 SUB1 LAN1."))
    m.put("1", 16, 23).put("2", 31, 8).put("t", 10, 12).put("M", 33, 12)
    m.put("P", 13, 6).put("P", 23, 6).put("P", 18, 11).put("P", 14, 20).put("P", 22, 20)
    route(m, [(16, 22), (22, 21), (28, 21), (28, 20)], seed=1); route(m, [(28, 14), (30, 12), (31, 9)], seed=2)
    route(m, [(28, 14), (22, 12), (18, 12), (12, 12), (8, 13), (4, 12), (3, 8), (3, 6)], seed=3); route(m, [(31, 9), (28, 6), (25, 4)], seed=4); route(m, [(18, 12), (18, 11)], seed=5)
    route(m, [(12, 12), (10, 12)], seed=6); route(m, [(16, 23), (14, 21), (14, 20)], seed=7); route(m, [(22, 21), (22, 20)], seed=8); route(m, [(16, 23), (11, 24), (6, 22)], seed=9)
    route(m, [(28, 14), (31, 13), (32, 11), (34, 11, "="), (36, 11), (37, 10)], seed=10); route(m, [(12, 12), (11, 8), (12, 6), (13, 6)], seed=11); route(m, [(25, 4), (23, 6)], seed=12)
    route(m, [(22, 21), (30, 23), (33, 24)], seed=13)
    thin_roads(m)
    for args in [(16, 23, "BBC"), (11, 24, "BC"), (22, 22, "BC"), (14, 21, "C"), (6, 22, "C"), (28, 21, "CC"), (33, 24, "C"), (19, 21, "c"),
                 (31, 8, "BBBC"), (28, 6, "BC"), (34, 4, "AB"), (29, 12, "BC"), (25, 12, "C"), (18, 12, "Cc"), (12, 12, "CC"), (8, 13, "C"), (4, 12, "C"), (12, 8, "C"), (22, 4, "C"), (35, 9, "C"),
                 (31, 12, "C"), (10, 6, "c"), (3, 6, "cc"), (36, 6, "c"), (37, 10, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    for box in [(2, 1, 14, 3), (24, 1, 37, 2), (2, 15, 38, 15), (5, 19, 34, 19), (4, 28, 34, 28)]:
        shore(m, 1, box, dirs="NS")
    for (x, y) in [(14, 19), (22, 19), (14, 6), (22, 6), (18, 10), (12, 6), (24, 6)]:          # (the ports' doors stay open water)
        if m.g[y][x] == ",":
            m.g[y][x] = "~"
    for (x, y) in pond:
        m.g[y][x] = "~"
    m.tidy()
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 3, MECH: 1, TANK: 3, ART: 2, ROCK: 1, RECON: 1, AA: 1, APC: 1, BCO: 2}, (4, 20, 34, 27), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1, FTR: 2, BCO: 3}, (3, 3, 38, 13), seed=2, gap=0, avoid=av)
    for k, (x, y) in zip([BS, CR, CR, SUB, SUB, LAN, LAN], m.sea_near(18, 17, 7, box=(8, 16, 30, 18), deep=False)):
        m.unit(1, k, x, y)
    for k, (x, y) in zip([BS, CR, CR, SUB], m.sea_near(18, 6, 4, box=(14, 3, 22, 9), deep=True)):
        m.unit(2, k, x, y)
    m.note("hq", 16, 23, "Flak's HQ"); m.note("enemy_hq", 31, 8, "Olaf's HQ (objective)"); m.note("channel", 20, 17, "the channel: Landers only")
    return m
