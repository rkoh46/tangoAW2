"""BH2 M13 Whiteout Harbour (Act III): Olaf's harbour town in a snowstorm and fog. Flak (forced) against Olaf: a naval and ground mix.

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: two bands of land, not two ovals: the northern land runs off the map's top edge and its south coast is a jagged fjord coast (a big fjord and a small one biting up into it); the southern land runs off the bottom edge as a broken shelf (two coves cut into it and its east end is split off as an island by a strait). The situation: Blue Moon holds the northern coast: a fjord cuts into it from the north; Olaf's harbour town stands on the shores of the channel (two ports in the bottom-right of the island, so the fleet meets the enemy within a turn), his HQ and a
district of bases on the east lobe, a Fighter field and the fleet in the fjord. Black Hole holds a southern island across a channel of five rows with reefs: its HQ, a base district and two ports on the channel. There is no land link: the armies cross by sea, Landers on the long beaches (the continent's south coast, the island's north coast) under the cover of the fleets in the channel. A river rises from a pond in the east
lobe's hills and reaches the channel with a bridge for the coast road. Snow: the heaviest weather the engine has, with fog.
- Lanes: the channel and its reefs, the beaches, the fjord and the channel ports, the river's bridge on the coast road, the lobes' ridges.
- Where the fight happens: the channel (the fleets) and the beaches, then the harbour town's ports and the coast road.
- Properties: Black Hole's two channel ports and bases; the continent's villages along the coast road, Olaf's harbour district (two channel ports), his Fighter airport.
- Threats and answers: Olaf's Battleship, Cruisers and Submarines -> Black Hole's own and the guns on the island's north coast; his Fighters and Copters -> Anti-Air and Copters; his Tanks and artillery on the beaches -> Md Tanks and artillery.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 40, 30
Y_N = 13                                           # the northern land's south coast (flat in the east, where the ports are)
Y_S = 20                                           # the southern shelf's north coast


def build():
    m = Canvas("bh2_13", W, H, fill="~")
    # --- the northern land: off the top edge; fjords bite up from the channel: a big one (x 16..21, up to row 5), a small one (x 3..5, up to row 8), notches in between
    for x in range(W):
        b = Y_N
        if 16 <= x <= 21:
            b = 5
        elif 3 <= x <= 5:
            b = 8
        elif x in (14, 15, 22, 23):
            b = 9
        elif x in (9, 10, 11):
            b = 11
        elif x in (6, 7, 8, 12, 13):
            b = 12
        m.rect(".", x, 0, x, b)
    # --- the southern shelf: off the bottom edge; two coves cut into its north coast, a strait splits its east end off as an island
    for x in range(W):
        t = Y_S
        if x in (3, 4, 5):
            t = Y_S + 2
        elif x in (14, 15, 28, 29, 30):
            t = Y_S + 1
        if 28 <= x <= 29:
            continue
        m.rect(".", x, t, x, H - 1 if x < 28 else H - 2)
    for x in range(10, 14):                          # cove 1 (Black Hole's west port)
        m.rect("~", x, Y_S, x, Y_S + 3)
    for x in range(22, 26):                          # cove 2 (Black Hole's east port)
        m.rect("~", x, Y_S, x, Y_S + 3)
    m.rect("~", 28, Y_S, 29, H - 1)
    pond = m.lake(34, 5, 8, seed=1, river_end=(34, 6))                 # the river rises from a pond in the east hills and reaches the channel
    m.river([(34, 6), (34, Y_N)])
    belt(m, "^", [(4, 3), (10, 4), (14, 3)], width=1, seed=1, gaps=[(8, 4)]); belt(m, "^", [(24, 3), (29, 4), (36, 6)], width=1, seed=2, gaps=[(27, 3)]); belt(m, "^", [(2, 10), (6, 11)], width=1, seed=3)
    belt(m, "^", [(24, 9), (27, 11)], width=1, seed=4); belt(m, "^", [(36, 10), (38, 12)], width=1, seed=5); belt(m, "^", [(2, 23), (8, 24)], width=1, seed=6); belt(m, "^", [(16, 23), (21, 22)], width=1, seed=7); belt(m, "^", [(30, 24), (36, 23)], width=1, seed=8)
    belt(m, "f", [(6, 5), (12, 7)], width=1, seed=9); belt(m, "f", [(24, 6), (30, 8)], width=1, seed=10); belt(m, "f", [(7, 26), (12, 27)], width=1, seed=11); belt(m, "f", [(17, 26), (22, 27)], width=1, seed=12); belt(m, "f", [(30, 26), (37, 26)], width=1, seed=13)
    belt(m, "f", [(14, 11), (18, 12)], width=1, seed=14); belt(m, "f", [(2, 6), (5, 7)], width=1, seed=15)
    m.header(armies=2, colours=(BH, BM), objective=[1], comment=(
        "M13 Whiteout Harbour (snow look, snow weather, fog): Flak (forced, Black Hole, HQ 1 (16,25), the broken shelf in the south) against Olaf (Blue Moon, HQ 2 (31,8), the east of the northern land). "
        "A river from a pond (34,5) reaches the channel, its bridge (34,9) on the coast road. Olaf's ports (30,13) and (37,13) face the channel at the bottom-right of his land; the channel (rows 14..19) has reefs and no bridge: Landers only. Black Hole's ports sit in the two coves (11,19) and (24,19). Com Tower (10,9), missile silo (34,24) on the split-off island. "
        "Player: INF3 MECH1 TANK3 ART2 ROCK1 RECON1 AA1 APC1 BCO2 BS1 CR2 SUB2 LAN2; Olaf: INF4 MECH2 TANK3 MDT1 ART2 ROCK1 RECON1 FTR2 BCO3 BS1 CR2 SUB1."))
    m.put("1", 16, 25).put("2", 31, 8).put("t", 10, 9).put("M", 34, 24)
    S = lambda x, y: snap(m, x, y)
    PORTS = [(30, Y_N), (37, Y_N)]
    pcs = [snap_coast(m, 11, Y_S - 1), snap_coast(m, 24, Y_S - 1)]
    for (x, y) in PORTS + pcs:
        m.put("P", x, y)
    route(m, [S(16, 24), S(19, 22), S(26, 22)], seed=41, wander=0.6); route(m, [S(16, 25), S(10, 24), S(6, 25), S(2, 26)], seed=2); route(m, [S(16, 25), S(17, 28), S(24, 27)], seed=3)
    route(m, [pcs[0], S(pcs[0][0], pcs[0][1] + 3), S(14, 24)], seed=4); route(m, [pcs[1], S(pcs[1][0], pcs[1][1] + 3), S(21, 23)], seed=5); route(m, [S(31, 25), S(34, 24)], seed=6) if False else None
    route(m, [S(31, 25), S(36, 25), S(34, 24)], seed=7)
    route(m, [S(4, 10), S(10, 9), S(13, 7), S(14, 4), S(20, 3), S(26, 5), S(31, 7)], seed=8, wander=1.1)
    route(m, [S(10, 9), S(14, 10), S(18, 12), S(24, 12), S(28, 12), S(32, 11), (34, 9, "="), S(36, 9)], seed=9) if False else route(m, [S(10, 9), S(14, 11), S(20, 12), S(26, 12), S(30, 10), (32, 9), (34, 9, "="), (36, 9), S(37, 11)], seed=9, wander=1.1)
    route(m, [S(31, 8), S(30, 12), (30, Y_N - 1)], seed=10); route(m, [S(37, 11), (37, Y_N - 1)], seed=11); route(m, [S(10, 9), S(8, 6), S(5, 4)], seed=12)
    thin_roads(m); fix_rungs(m)
    for args in [(16, 25, "BBC"), (11, 24, "BC"), (24, 24, "BC"), (19, 22, "C"), (6, 25, "C"), (2, 26, "c"), (21, 27, "CC"), (14, 27, "C"), (34, 24, "cc"), (36, 26, "c"), (31, 25, "bc"),
                 (31, 8, "BBBC"), (28, 6, "BC"), (34, 4, "AB"), (30, 11, "BC"), (26, 11, "C"), (20, 12, "Cc"), (14, 11, "CC"), (10, 9, "Cc"), (4, 10, "C"), (14, 4, "C"), (22, 4, "C"), (37, 11, "c"), (12, 7, "c"), (6, 4, "cc"), (2, 2, "cc"), (37, 2, "cc"), (36, 7, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=3)
        except ValueError:
            pass
    neutralize(m, 13)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for (x, y) in pond:
        m.g[y][x] = "~"
    for p in PORTS + pcs + [(34, Y_N)]:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    for (x, y) in [(6, 17), (9, 17), (12, 16), (15, 17), (17, 17), (21, 17), (24, 17), (26, 16), (28, 17), (33, 17), (35, 17), (39, 17), (13, 18), (19, 18), (32, 16), (4, 17), (22, 18), (1, 17), (38, 23), (6, 29), (20, 28), (27, 28), (8, 28)]:
        if m.inside(x, y) and all(m.get(a, b) == "~" for a in range(x - 1, x + 2) for b in range(y - 1, y + 2) if m.inside(a, b)):
            m.put("r", x, y)                                                    # (reefs: ships hide in them in the fog; clear of every shore and every port's door)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 3, MECH: 1, TANK: 3, ART: 2, ROCK: 1, RECON: 1, AA: 1, APC: 1, BCO: 2}, (2, 21, 27, 28), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 4, MECH: 2, TANK: 3, MDT: 1, ART: 2, ROCK: 1, RECON: 1, FTR: 2, BCO: 3}, (24, 0, 38, 12), seed=2, gap=0, avoid=av)
    for k, (x, y) in zip([BS, CR, CR, SUB, SUB, LAN, LAN], m.sea_near(18, 17, 7, box=(8, 15, 27, 19), deep=False)):
        m.unit(1, k, x, y)
    for k, (x, y) in zip([BS, CR, CR, SUB], m.sea_near(33, 16, 4, box=(27, 15, 38, 18), deep=False)):
        m.unit(2, k, x, y)
    m.note("hq", 16, 25, "Flak's HQ"); m.note("enemy_hq", 31, 8, "Olaf's HQ (objective)"); m.note("channel", 20, 17, "the channel: Landers only")
    return m
