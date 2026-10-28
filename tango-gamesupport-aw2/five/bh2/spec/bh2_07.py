"""BH2 M7 Drake's Harbour (Act I): a harbour assault on Green Earth's northern port, desert look, clear. A free pick (Black Hole) against Drake (Green Earth).

Design (docs/dev/map-design.md, docs/BH2_CAMPAIGN.md section 4). The shape: a coast with a deep harbour bay: Drake's land hangs from the top edge with a ragged south coast, and a wide bay bites into it from the south, its mouth strewn with reefs; Black Hole starts on a hooked island of its own in the south-west, a separate islet lies between.
The situation: Drake holds the whole northern land: his HQ inland, a district of bases, three ports round the bay and a fleet in the harbour. Black Hole has a small port on its island, Landers and a fleet; there is no way to Drake's land but by sea (or air): load the Landers, cross the reef-strewn channel and put the army ashore on the beaches.
- Lanes: the channel between the island and the bay (reefs leave three narrow ways in), the beaches west and east of the bay's mouth, the harbour itself, the islet's beach as a stepping stone.
- Where the fight happens: the bay's mouth and the two beaches, then the harbour quays and the road up to Drake's HQ.
- Properties: Drake's bases and ports, villages along the coast road, the islet's village and Black Hole's own port and bases.
- Threats and answers: Drake's Battleship and Cruisers in the bay -> Black Hole's own Cruisers and Subs; his artillery covering the beaches -> an escort of Md Tanks and a fast second wave.
"""
import random
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4] / "devkit"))
from aw2.esmaplib import *
from aw2.esmaplib import route, belt, town, thin_roads, neutralize, snap, snap_coast, fix_rungs

W, H = 40, 28


def build():
    m = Canvas("bh2_07", W, H, fill="~")
    rnd = random.Random("bh2_07/coast")
    # --- Drake's land: hangs from the top edge, ragged south coast, a deep bay in the middle
    b = 12
    for x in range(W):
        if x % 3 == 0:
            b = max(10, min(14, b + rnd.choice([-1, 0, 1])))
        m.rect(".", x, 0, x, b)
    for x in range(17, 30):
        m.rect("~", x, 7, x, 15)                                    # the harbour bay (opens to the south)
    for x in range(14, 17):
        m.rect("~", x, 11 + (x - 14), x, 15)                        # a ragged west shoulder
    # --- Black Hole's hooked island in the south-west, an islet between
    land_rows(m, {17: (6, 10), 18: (4, 12), 19: (3, 13), 20: (3, 11), 21: (3, 9), 22: (4, 10), 23: (6, 16), 24: (9, 18), 25: (12, 17)})
    land_rows(m, {19: (24, 28), 20: (23, 29), 21: (24, 28), 22: (25, 27)})
    S = lambda x, y: snap(m, x, y)
    # reefs across the bay's mouth and the channel (narrow ways remain)
    for (x, y) in [(18, 16), (20, 16), (23, 16), (26, 16), (28, 16), (21, 18), (25, 18), (19, 20), (16, 16), (30, 17), (14, 20), (21, 22), (31, 21)]:
        if m.inside(x, y) and all(m.get(a, c) == "~" for a in range(x - 1, x + 2) for c in range(y - 1, y + 2)):
            m.put("r", x, y)
    belt(m, "^", [(1, 2), (6, 3), (9, 1)], width=1, seed=1); belt(m, "^", [(31, 2), (36, 4), (39, 8)], width=1, seed=2, gaps=[(35, 4)]); belt(m, "f", [(10, 5), (14, 8)], width=1, seed=3); belt(m, "f", [(30, 8), (34, 10)], width=1, seed=4)
    belt(m, "^", [(4, 18), (9, 18)], width=1, seed=6, gaps=[(6, 18)])
    belt(m, "f", [(3, 6), (8, 9), (11, 11)], width=1, seed=11); belt(m, "^", [(14, 1), (20, 2), (26, 1)], width=1, seed=12, gaps=[(20, 2)]); belt(m, "f", [(31, 5), (35, 7)], width=1, seed=13); belt(m, "f", [(2, 12), (6, 11)], width=1, seed=14)
    belt(m, "^", [(27, 4), (30, 6)], width=1, seed=15); belt(m, "f", [(18, 5), (20, 6)], width=1, seed=16); belt(m, "^", [(36, 11), (39, 12)], width=1, seed=17)
    for i, (cx, cy, n) in enumerate([(8, 4, 5), (33, 3, 5), (25, 9, 4), (4, 9, 4)]):
        m.cluster("f", cx, cy, n * 2, seed=50 + i)
    m.header(armies=2, colours=(BH, GE), objective=[1], comment=(
        "M7 Drake's Harbour (desert look, clear): a free pick (Black Hole, HQ 1 (8,21), the hooked south-west island) against Drake (Green Earth, HQ 2 (23,3), inland on the north coast). The harbour bay (x 17..29) has three ports; a reef-strewn channel separates the island from the north. "
        "Player: INF4 MECH2 TANK3 MDT2 ART2 ROCK1 RECON1 APC1 LAN3 CR2 SUB1 BS1; two silos (11,19) (4,20), a neutral airport (12,18) and a second port (north coast) on the left island; Drake: INF5 MECH3 TANK4 MDT2 ART3 ROCK2 AA2 RECON1 BS1 CR2 SUB1."))
    m.put("1", 8, 21).put("2", 23, 3)
    PORTS = [snap_coast(m, 8, 24), snap_coast(m, 16, 9), snap_coast(m, 30, 9), snap_coast(m, 23, 6), snap_coast(m, 8, 17)]
    for (x, y) in PORTS:
        m.put("P", x, y)
    m.put("M", 11, 19).put("M", 4, 20).put("a", 12, 18)                      # (the left island's prizes: two missile silos and a neutral airport)
    route(m, [S(8, 20), S(7, 22), S(PORTS[0][0], PORTS[0][1] - 1)], seed=1); route(m, [S(8, 20), S(10, 19), S(12, 18)], seed=21); route(m, [S(7, 20), S(5, 20)], seed=22); route(m, [S(7, 19), S(PORTS[4][0], PORTS[4][1] + 1)], seed=23); route(m, [S(5, 19), S(10, 19), S(12, 23)], seed=2)
    route(m, [S(23, 4), S(19, 5), S(PORTS[1][0] - 1, PORTS[1][1] - 1), S(PORTS[1][0], PORTS[1][1] - 1)], seed=3); route(m, [S(23, 4), S(27, 5), S(PORTS[2][0] + 1, PORTS[2][1] - 1), S(PORTS[2][0], PORTS[2][1] - 1)], seed=4)
    route(m, [S(3, 8), S(10, 9), S(16, 8), S(23, 5), S(31, 8), S(37, 9)], seed=5, wander=0.7); route(m, [S(23, 4), S(23, 2), S(18, 2)], seed=6); route(m, [S(9, 4), S(14, 4), S(22, 3)], seed=7)
    route(m, [S(PORTS[3][0], PORTS[3][1] - 1), S(23, 4)], seed=8)
    thin_roads(m); fix_rungs(m)
    for args in [(8, 21, "BBC"), (6, 19, "BC"), (11, 23, "C"), (9, 24, "B"), (25, 21, "c"),
                 (23, 3, "BBBC"), (19, 4, "BC"), (28, 4, "BC"), (23, 6, "C"), (16, 9, "C"), (31, 8, "C"), (12, 4, "C"), (5, 6, "c"), (3, 10, "C"), (36, 8, "C"), (37, 3, "c"), (20, 9, "c"), (27, 9, "c"), (14, 2, "c"), (2, 2, "c"), (34, 5, "c"), (29, 21, "c"), (10, 8, "c")]:
        try:
            town(m, args[0], args[1], args[2], seed=args[0] * 31 + args[1], radius=2)
        except ValueError:
            pass
    neutralize(m, 6)
    m.tidy()
    shore(m, 1, (1, 1, W - 2, H - 2), dirs="NS")
    for p in PORTS:
        for dx, dy in ((0, -1), (0, 1), (1, 0), (-1, 0), (0, -2), (0, 2), (2, 0), (-2, 0)):
            if m.inside(p[0] + dx, p[1] + dy) and m.g[p[1] + dy][p[0] + dx] == ",":
                m.g[p[1] + dy][p[0] + dx] = "~"
    m.tidy()
    m.desertify(keep=0.6, rocks=3, size=5, seed=7)
    av = "~r=-^IZ#X12345QBCPTbcpt"
    m.spread(1, {INF: 3, MECH: 1, TANK: 3, MDT: 1, ART: 1, ROCK: 1, RECON: 1, APC: 1}, (3, 17, 14, 24), seed=1, gap=0, avoid=av)
    m.spread(2, {INF: 5, MECH: 3, TANK: 4, MDT: 2, ART: 3, ROCK: 2, AA: 2, RECON: 1}, (12, 1, 34, 10), seed=2, gap=0, avoid=av)
    for k_, (x, y) in zip([LAN, LAN, LAN, CR, CR, SUB, BS], m.sea_near(PORTS[0][0], PORTS[0][1] + 1, 7, box=(2, 24, 22, 27), deep=False)):
        m.unit(1, k_, x, y)
    for k_, (x, y) in zip([BS, CR, CR, SUB], m.sea_near(23, 11, 4, box=(19, 8, 28, 14), deep=False)):
        m.unit(2, k_, x, y)
    m.note("hq", 8, 21, "Black Hole's HQ"); m.note("enemy_hq", 23, 3, "Drake's HQ (objective)")
    return m
